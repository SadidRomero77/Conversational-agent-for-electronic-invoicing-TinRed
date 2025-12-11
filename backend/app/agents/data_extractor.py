"""
Data Extractor - Extrae datos de facturación con inferencia inteligente.
VERSIÓN CORREGIDA - Mejor manejo de DNI/RUC y productos sin precio.
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from app.models.schemas import UserSession, InvoiceItem

logger = logging.getLogger(__name__)


class DataExtractor:
    
    def extract_all(self, message: str, session: UserSession) -> Dict[str, Any]:
        """Extrae todos los datos posibles del mensaje."""
        extracted = {
            "document_type": None,
            "id_type": None,
            "id_number": None,
            "currency": None,
            "items": [],
            "items_sin_precio": []  # Productos mencionados sin precio
        }
        
        text_lower = message.lower()
        
        # 1. Tipo de documento
        if re.search(r'\bfactura\b', text_lower):
            extracted["document_type"] = "01"
        elif re.search(r'\bboleta\b', text_lower):
            extracted["document_type"] = "03"
        
        # 2. Identificación (ANTES de items para no confundir)
        id_info = self._extract_id(message)
        if id_info:
            extracted["id_type"] = id_info["type"]
            extracted["id_number"] = id_info["number"]
            
            # INFERENCIA: DNI → Boleta automáticamente
            if not extracted["document_type"] and id_info["type"] == "1":
                extracted["document_type"] = "03"
                logger.info("[Extractor] 💡 Inferido: DNI → Boleta")
        
        # 3. Moneda
        if any(w in text_lower for w in ["dólar", "dolar", "dolares", "usd", "$"]):
            extracted["currency"] = "USD"
        else:
            extracted["currency"] = "PEN"
        
        # 4. Items (productos con precio)
        items, items_sin_precio = self._extract_items(message, extracted.get("id_number"))
        extracted["items"] = items
        extracted["items_sin_precio"] = items_sin_precio
        
        logger.info(f"[Extractor] Resultado: doc={extracted['document_type']}, id={extracted['id_number']}, items={len(items)}, sin_precio={len(items_sin_precio)}")
        return extracted
    
    def _extract_id(self, message: str) -> Optional[Dict[str, str]]:
        """
        Extrae identificación (DNI o RUC).
        MEJORADO: Evita confundir cantidades con parte del DNI.
        """
        text_upper = message.upper()
        
        # 1. DNI explícito: "DNI 12345678" o "DNI: 12345678"
        dni_explicit = re.search(r'DNI\s*[:\s]?\s*(\d{8})\b', text_upper)
        if dni_explicit:
            return {"type": "1", "number": dni_explicit.group(1)}
        
        # 2. RUC explícito: "RUC 20123456789"
        ruc_explicit = re.search(r'RUC\s*[:\s]?\s*([12]0\d{9})\b', text_upper)
        if ruc_explicit:
            return {"type": "6", "number": ruc_explicit.group(1)}
        
        # 3. Buscar RUC suelto (11 dígitos que empiezan con 10 o 20)
        ruc_match = re.search(r'\b([12]0\d{9})\b', message)
        if ruc_match:
            return {"type": "6", "number": ruc_match.group(1)}
        
        # 4. Buscar DNI suelto (exactamente 8 dígitos)
        # IMPORTANTE: Debe estar separado por espacios o puntuación
        # No debe tener más dígitos pegados
        dni_matches = re.findall(r'(?:^|[^\d])(\d{8})(?:[^\d]|$)', message)
        
        for num in dni_matches:
            # Validar que sea un DNI válido
            if int(num) >= 1000000:  # DNIs válidos son > 1 millón
                return {"type": "1", "number": num}
        
        return None
    
    def _extract_items(self, message: str, exclude_number: str = None) -> Tuple[List[InvoiceItem], List[Dict]]:
        """
        Extrae items/productos del mensaje.
        Retorna: (items_con_precio, items_sin_precio)
        """
        items = []
        items_sin_precio = []
        seen = set()
        seen_sin_precio = set()
        
        # Si hay un DNI/RUC, removerlo del texto para no confundir
        text = message
        if exclude_number:
            text = text.replace(exclude_number, " ")
        
        # Convertir palabras numéricas a dígitos
        palabras_numero = {
            'un ': '1 ', 'uno ': '1 ', 'una ': '1 ',
            'dos ': '2 ', 'tres ': '3 ', 'cuatro ': '4 ', 'cinco ': '5 ',
            'seis ': '6 ', 'siete ': '7 ', 'ocho ': '8 ', 'nueve ': '9 ', 'diez ': '10 '
        }
        
        text_normalized = text.lower()
        for palabra, num in palabras_numero.items():
            text_normalized = text_normalized.replace(palabra, num)
        
        # =========================================================
        # PATRONES CON PRECIO
        # =========================================================
        
        # Patrón 1: "N producto a/@ precio" (ej: "2 laptops a 2500")
        pattern1 = re.finditer(
            r'(\d{1,4})\s*[xX×]?\s*([a-záéíóúñ][a-záéíóúñs\s]{1,30}?)\s*[@aA]\s*(?:PEN|USD|S/|s/|\$)?\s*(\d+(?:[.,]\d{1,2})?)',
            text_normalized, re.IGNORECASE
        )
        
        for match in pattern1:
            cant = match.group(1)
            desc = match.group(2).strip()
            precio = match.group(3).replace(',', '.')
            
            if len(cant) >= 5:  # Probablemente es un documento
                continue
                
            key = (desc.lower(), precio)
            if key not in seen and desc and float(precio) > 0:
                items.append(InvoiceItem(cantidad=cant, descripcion=desc, precio=precio))
                seen.add(key)
                logger.info(f"[Extractor] Item: {cant}x {desc} @ {precio}")
        
        # Patrón 2: "N producto por precio" (ej: "2 laptops por 2500")
        pattern2 = re.finditer(
            r'(\d{1,4})\s+([a-záéíóúñ][a-záéíóúñs\s]{1,30}?)\s+(?:por|de)\s+(?:PEN|USD|S/|s/|\$)?\s*(\d+(?:[.,]\d{1,2})?)',
            text_normalized, re.IGNORECASE
        )
        
        for match in pattern2:
            cant = match.group(1)
            desc = match.group(2).strip()
            precio = match.group(3).replace(',', '.')
            
            if len(cant) >= 5:
                continue
                
            key = (desc.lower(), precio)
            if key not in seen and desc and float(precio) > 0:
                items.append(InvoiceItem(cantidad=cant, descripcion=desc, precio=precio))
                seen.add(key)
                logger.info(f"[Extractor] Item: {cant}x {desc} @ {precio}")
        
        # Patrón 3: "producto a precio" sin cantidad (cantidad = 1)
        pattern3 = re.finditer(
            r'\b([a-záéíóúñ][a-záéíóúñs]{2,20})\s+(?:a|@|por)\s+(?:PEN|USD|S/|s/|\$)?\s*(\d+(?:[.,]\d{1,2})?)\b',
            text_normalized, re.IGNORECASE
        )
        
        for match in pattern3:
            desc = match.group(1).strip()
            precio = match.group(2).replace(',', '.')
            
            # Evitar palabras clave
            if desc.lower() in ['factura', 'boleta', 'dni', 'ruc', 'para', 'cliente', 'documento']:
                continue
            
            key = (desc.lower(), precio)
            if key not in seen and desc and float(precio) > 0:
                items.append(InvoiceItem(cantidad="1", descripcion=desc, precio=precio))
                seen.add(key)
                logger.info(f"[Extractor] Item: 1x {desc} @ {precio}")
        
        # =========================================================
        # PATRONES SIN PRECIO (para preguntar)
        # =========================================================
        if not items:
            # Buscar "N producto" sin precio
            pattern_sin_precio = re.finditer(
                r'(\d{1,3})\s+([a-záéíóúñ][a-záéíóúñs]{2,25})',
                text_normalized, re.IGNORECASE
            )
            
            for match in pattern_sin_precio:
                cant = match.group(1)
                desc = match.group(2).strip()
                
                # Validar
                if desc.lower() in ['dni', 'ruc', 'para', 'cliente', 'boleta', 'factura', 'soles', 'dolares', 'documento']:
                    continue
                
                key = desc.lower()
                if key not in seen_sin_precio:
                    items_sin_precio.append({
                        "cantidad": cant,
                        "descripcion": desc
                    })
                    seen_sin_precio.add(key)
                    logger.info(f"[Extractor] Sin precio: {cant}x {desc}")
        
        return items, items_sin_precio
    
    def update_session(self, session: UserSession, extracted: Dict[str, Any]):
        """Actualiza la sesión con los datos extraídos."""
        emission = session.emission_data
        
        if extracted["document_type"] and not emission.document_type:
            emission.document_type = extracted["document_type"]
        
        if extracted["id_type"] and not emission.id_type:
            emission.id_type = extracted["id_type"]
            emission.id_number = extracted["id_number"]
        
        if extracted["currency"]:
            emission.currency = extracted["currency"]
        
        if extracted["items"]:
            existing = set((i.descripcion.lower(), i.precio) for i in emission.items)
            for item in extracted["items"]:
                key = (item.descripcion.lower(), item.precio)
                if key not in existing:
                    emission.items.append(item)
                    existing.add(key)


_extractor: Optional[DataExtractor] = None

def get_data_extractor() -> DataExtractor:
    global _extractor
    if _extractor is None:
        _extractor = DataExtractor()
    return _extractor
