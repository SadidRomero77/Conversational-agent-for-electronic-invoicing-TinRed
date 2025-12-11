"""
Emission Agent - ACTUALIZADO: Validación de cliente antes de continuar.
Flujo optimizado: extrae todo en memoria, valida cliente, muestra resumen.
"""
import logging
import re
from typing import Optional, List, Tuple
from app.models.schemas import UserSession, InvoiceItem
from app.services.tinred_client import get_tinred_client, TinRedAPIError
from app.services.session_manager import get_session_manager
from app.agents.data_extractor import get_data_extractor
from app.agents.anomaly_detector import get_anomaly_detector

logger = logging.getLogger(__name__)


class EmissionAgent:
    def __init__(self):
        self.tinred = get_tinred_client()
        self.extractor = get_data_extractor()
        self.anomaly_detector = get_anomaly_detector()
        self.session_manager = get_session_manager()
    
    def process_message(self, message: str, session: UserSession) -> str:
        """Procesa mensaje para emisión."""
        logger.info(f"[EmissionAgent] Procesando: {message[:40]}...")
        
        msg_lower = message.lower().strip()
        emission = session.emission_data
        
        # =========================================================
        # PRIORIDAD MÁXIMA: Detectar cancelación
        # El usuario puede cancelar en cualquier momento
        # =========================================================
        if self._is_cancellation(msg_lower):
            logger.info("[EmissionAgent] ❌ Usuario canceló la operación")
            session.reset_emission()
            return """❌ Operación cancelada.

¿Qué más necesitas?
📄 Factura | 🧾 Boleta | 📊 Historial"""
        
        # =========================================================
        # CASO: Usuario re-confirma documento después de "no encontrado"
        # =========================================================
        if session.awaiting_client_reconfirmation:
            return self._handle_client_reconfirmation(message, session)
        
        # =========================================================
        # CASO: Usuario confirma ("si", "ok", "dale")
        # =========================================================
        if msg_lower in ['si', 'sí', 'ok', 'dale', 'confirmo', 'claro']:
            if not self._has_complete_data(emission):
                self._extract_from_conversation(session)
            
            if not emission.get_missing_fields():
                # Verificar si el cliente ya fue validado
                if not emission.client_validated:
                    return self._validate_and_continue(session)
                return self._generate_summary(session)
        
        # =========================================================
        # CASO: Solo dice "RUC" o "DNI" sin número
        # =========================================================
        if msg_lower in ['ruc', 'con ruc', 'es ruc']:
            return "Dame el RUC (11 dígitos).\nEjemplo: 20161541991"
        
        if msg_lower in ['dni', 'con dni', 'es dni']:
            return "Dame el DNI (8 dígitos).\nEjemplo: 12345678"
        
        # Extraer datos del mensaje actual
        extracted = self.extractor.extract_all(message, session)
        self.extractor.update_session(session, extracted)
        
        logger.info(f"[EmissionAgent] Estado: doc={emission.document_type}, id={emission.id_number}, items={len(emission.items)}")
        
        # =========================================================
        # CASO: Productos sin precio
        # =========================================================
        items_sin_precio = extracted.get("items_sin_precio", [])
        if items_sin_precio and not extracted.get("items"):
            session.pending_items = items_sin_precio
            
            item = items_sin_precio[0]
            return f"📝 {item['cantidad']} {item['descripcion']}\n\n¿Precio unitario?"
        
        # =========================================================
        # CASO: Precio para item pendiente
        # =========================================================
        if session.pending_items:
            precio = self._extract_price(message)
            if precio:
                for pending in session.pending_items:
                    emission.items.append(InvoiceItem(
                        cantidad=pending['cantidad'],
                        descripcion=pending['descripcion'],
                        precio=precio
                    ))
                session.pending_items = []
        
        # Verificar qué falta
        missing = emission.get_missing_fields()
        
        # Solo dijo tipo documento
        if self._is_initial_request(message, extracted, emission):
            return self._get_initial_instructions(emission.document_type)
        
        # =========================================================
        # CASO: Tenemos documento - VALIDAR CLIENTE
        # =========================================================
        if emission.id_number and not emission.client_validated:
            # Si también tenemos items, guardarlos y validar
            if emission.items:
                return self._validate_and_continue(session)
            # Si solo tenemos documento, validarlo antes de pedir productos
            elif not missing or missing == ["productos"]:
                return self._validate_and_continue(session)
        
        # Datos completos y cliente validado
        if not missing:
            if emission.client_validated:
                logger.info("[EmissionAgent] ✅ Datos completos, cliente validado")
                return self._generate_summary(session)
            else:
                return self._validate_and_continue(session)
        
        # No se extrajo nada útil
        if not extracted.get("id_number") and not extracted.get("items") and not items_sin_precio:
            if "identificacion_cliente" in missing:
                return "Escribe el DNI (8 dígitos) o RUC (11 dígitos):"
            if "productos" in missing:
                return "¿Qué productos?\n📝 Ej: 2 laptops a 2500"
        
        logger.info(f"[EmissionAgent] Faltan: {missing}")
        return self._request_data(missing, session)
    
    def _validate_and_continue(self, session: UserSession) -> str:
        """
        Valida el cliente con el API y continúa el flujo.
        Si el cliente es válido y tenemos productos → muestra resumen
        Si el cliente es válido pero faltan productos → pide productos
        Si el cliente no es válido → pide reconfirmación
        """
        emission = session.emission_data
        
        if not emission.id_number:
            return "Necesito el DNI o RUC del cliente."
        
        logger.info(f"[EmissionAgent] 🔍 Validando cliente: {emission.id_number}")
        
        # Llamar al API de validación
        is_valid, result = self.tinred.check_client(session.phone, emission.id_number)
        
        if is_valid:
            # ✅ Cliente encontrado
            emission.client_validated = True
            emission.client_name = result
            
            logger.info(f"[EmissionAgent] ✅ Cliente válido: {result}")
            
            # Si ya tenemos productos → mostrar resumen completo
            if emission.items:
                return self._generate_summary(session)
            
            # Si no tenemos productos → pedirlos mostrando que el cliente es válido
            id_tipo = "DNI" if emission.id_type == "1" else "RUC"
            return f"""✅ Cliente encontrado:
👤 {result}
📋 {id_tipo}: {emission.id_number}

¿Qué productos incluimos?
📝 Ej: 2 laptops a 2500, 3 cables a 50"""
        
        else:
            # ❌ Cliente no encontrado
            logger.info(f"[EmissionAgent] ❌ Cliente no encontrado: {result}")
            
            # Guardar estado para reconfirmación
            session.awaiting_client_reconfirmation = True
            
            # Mostrar mensaje con productos ya guardados (si los hay)
            response = f"""⚠️ El documento {emission.id_number} no fue encontrado en el sistema.
"""
            
            if emission.items:
                response += f"""
📦 Ya tengo registrados tus productos:
"""
                for item in emission.items:
                    response += f"  • {item.cantidad}x {item.descripcion} @ S/{float(item.precio):.2f}\n"
                response += """
Por favor confirma el número de documento correcto para continuar.
💡 Escribe el DNI (8 dígitos) o RUC (11 dígitos)"""
            else:
                response += """
Por favor verifica e ingresa el número correcto.
💡 DNI: 8 dígitos | RUC: 11 dígitos"""
            
            return response
    
    def _handle_client_reconfirmation(self, message: str, session: UserSession) -> str:
        """
        Maneja cuando el usuario reconfirma/corrige el documento.
        """
        emission = session.emission_data
        msg_lower = message.lower().strip()
        
        # Si quiere cancelar (ya fue verificado arriba, pero por si acaso)
        if self._is_cancellation(msg_lower):
            session.reset_emission()
            return """❌ Operación cancelada.

¿Qué más necesitas?
📄 Factura | 🧾 Boleta | 📊 Historial"""
        
        # Intentar extraer nuevo documento
        new_id = self._extract_document_number(message)
        
        if new_id:
            id_type, id_number = new_id
            
            # Actualizar documento en emisión
            emission.id_type = id_type
            emission.id_number = id_number
            emission.client_validated = False
            emission.client_name = None
            
            # Limpiar flag
            session.awaiting_client_reconfirmation = False
            
            # Validar el nuevo documento
            return self._validate_and_continue(session)
        
        # No se pudo extraer documento válido
        return """No pude identificar un documento válido.

📝 Ingresa:
• DNI: 8 dígitos (ej: 12345678)
• RUC: 11 dígitos (ej: 20161541991)

O escribe "cancelar" para salir."""
    
    def _extract_document_number(self, message: str) -> Optional[Tuple[str, str]]:
        """
        Extrae documento del mensaje.
        Returns: (id_type, id_number) o None
        """
        # Limpiar mensaje de espacios entre dígitos (para audio)
        cleaned = re.sub(r'(\d)\s+(?=\d)', r'\1', message)
        
        # RUC (11 dígitos empezando con 10 o 20)
        ruc_match = re.search(r'\b([12]0\d{9})\b', cleaned)
        if ruc_match:
            return ("6", ruc_match.group(1))
        
        # DNI (8 dígitos)
        dni_match = re.search(r'\b(\d{8})\b', cleaned)
        if dni_match:
            num = dni_match.group(1)
            if int(num) >= 1000000:  # DNI válido
                return ("1", num)
        
        return None
    
    def _is_cancellation(self, msg_lower: str) -> bool:
        """Detecta si el usuario quiere cancelar la operación."""
        cancellation_words = [
            'cancelar', 'cancela', 'cancelalo', 'cancélalo',
            'no quiero', 'no deseo', 'olvida', 'olvidalo', 'olvídalo',
            'salir', 'sal', 'detener', 'parar', 'para',
            'dejalo', 'déjalo', 'ya no', 'mejor no',
            'no gracias', 'nada', 'ninguno'
        ]
        
        # Verificar coincidencia exacta o al inicio
        for word in cancellation_words:
            if msg_lower == word or msg_lower.startswith(word + ' ') or msg_lower.startswith(word + ','):
                return True
        
        # Verificar si contiene palabras clave de cancelación
        if any(word in msg_lower for word in ['cancelar', 'cancela', 'no quiero', 'olvida', 'salir']):
            return True
        
        return False
    
    def _has_complete_data(self, emission) -> bool:
        """Verifica si hay datos suficientes para mostrar resumen."""
        return emission.document_type and emission.id_number and emission.items
    
    def _extract_from_conversation(self, session: UserSession):
        """
        Extrae datos de emisión de la conversación previa.
        """
        emission = session.emission_data
        
        for msg in session.messages[-10:]:
            content = msg.content
            
            # Extraer tipo de documento
            if not emission.document_type:
                if 'factura' in content.lower():
                    emission.document_type = "01"
                elif 'boleta' in content.lower():
                    emission.document_type = "03"
            
            # Extraer RUC (11 dígitos)
            if not emission.id_number:
                ruc_match = re.search(r'\b([12]0\d{9})\b', content)
                if ruc_match:
                    emission.id_type = "6"
                    emission.id_number = ruc_match.group(1)
                    logger.info(f"[EmissionAgent] RUC extraído de conversación: {emission.id_number}")
            
            # Extraer DNI (8 dígitos)
            if not emission.id_number:
                dni_match = re.search(r'\b(\d{8})\b', content)
                if dni_match:
                    num = dni_match.group(1)
                    if int(num) >= 1000000:
                        emission.id_type = "1"
                        emission.id_number = num
                        logger.info(f"[EmissionAgent] DNI extraído de conversación: {emission.id_number}")
            
            # Extraer productos con precio
            if not emission.items:
                items_match = re.findall(r'(\d+)\s+([a-záéíóúñ]+)\s*(?:x|a|@|por)\s*(\d+)', content.lower())
                for cant, desc, precio in items_match:
                    emission.items.append(InvoiceItem(
                        cantidad=cant,
                        descripcion=desc,
                        precio=f"{float(precio):.2f}"
                    ))
                    logger.info(f"[EmissionAgent] Item extraído de conversación: {cant}x {desc} @ {precio}")
        
        # Inferir tipo si tenemos DNI
        if emission.id_type == "1" and not emission.document_type:
            emission.document_type = "03"
    
    def _extract_price(self, message: str) -> Optional[str]:
        match = re.search(r'(\d+(?:[.,]\d{1,2})?)', message)
        if match:
            return f"{float(match.group(1).replace(',', '.')):.2f}"
        return None
    
    def _is_initial_request(self, message: str, extracted: dict, emission) -> bool:
        msg_lower = message.lower().strip()
        patterns = ["factura", "boleta", "emitir factura", "emitir boleta"]
        is_initial = any(msg_lower == p or msg_lower.startswith(p) for p in patterns)
        no_extra = not extracted.get("id_number") and not extracted.get("items")
        no_prev = not emission.id_number and not emission.items
        return is_initial and no_extra and no_prev
    
    def _get_initial_instructions(self, document_type: str) -> str:
        if document_type == "01":
            return """📄 ¡Perfecto! Vamos con la Factura.

Primero necesito validar al cliente.

1️⃣ Dame el RUC (11 dígitos) para verificar que existe en el sistema
2️⃣ Luego me indicas los productos con sus precios

💡 Puedes enviarme todo junto si lo prefieres:
"RUC 20161541991, 3 laptops a 2500"

¿Cuál es el RUC del cliente?"""
        else:
            return """🧾 ¡Perfecto! Vamos con la Boleta.

Primero necesito validar al cliente.

1️⃣ Dame el DNI (8 dígitos) o RUC para verificar que existe
2️⃣ Luego me indicas los productos con sus precios

💡 Puedes enviarme todo junto si lo prefieres:
"DNI 12345678, 2 camisas a 50"

¿Cuál es el documento del cliente?"""
    
    def execute_emission(self, session: UserSession) -> str:
        """Ejecuta la emisión real."""
        emission = session.emission_data
        
        # Si faltan datos, intentar extraer de conversación
        if not self._has_complete_data(emission):
            self._extract_from_conversation(session)
        
        # Verificar que tenemos todo
        missing = emission.get_missing_fields()
        if missing:
            logger.warning(f"[EmissionAgent] Faltan datos para emitir: {missing}")
            return self._request_data(missing, session)
        
        # Verificar que el cliente está validado
        if not emission.client_validated:
            logger.warning("[EmissionAgent] Cliente no validado, validando...")
            return self._validate_and_continue(session)
        
        logger.info("[EmissionAgent] 🚀 Ejecutando emisión...")
        logger.info(f"[EmissionAgent] doc={emission.document_type}, id={emission.id_number}, items={len(emission.items)}")
        
        try:
            response = self.tinred.emit_invoice(
                client_data=session.client_data,
                document_type=emission.document_type,
                currency=emission.currency,
                id_type=emission.id_type,
                id_number=emission.id_number,
                items=emission.items
            )
            
            logger.info(f"[EmissionAgent] API: success={response.success}, serie={response.serie}, numero={response.numero}")
            
            if response.is_successful():
                tipo = "Factura" if emission.document_type == "01" else "Boleta"
                full_number = response.get_full_number()
                pdf_url = response.get_pdf_url()
                total = emission.calculate_total()
                
                # Obtener nombre del cliente si está disponible
                client_info = ""
                if emission.client_name:
                    client_info = f"\n👤 {emission.client_name}"
                
                self.session_manager.record_emission(
                    session, emission.document_type, full_number,
                    emission.id_number, total, emission.currency,
                    pdf_url, len(emission.items)
                )
                
                # RESETEAR
                session.reset_emission()
                
                return f"""✅ ¡{tipo} emitida!{client_info}

📄 {full_number}
💰 S/{total:.2f}

📥 PDF: {pdf_url}

¿Algo más?"""
            
            else:
                return f"⚠️ Error: {response.mensaje}"
        
        except TinRedAPIError as e:
            logger.error(f"[EmissionAgent] Error: {e}")
            return f"❌ Error: {str(e)}"
        
        except Exception as e:
            logger.error(f"[EmissionAgent] Error: {e}", exc_info=True)
            return "❌ Error inesperado."
    
    def _generate_summary(self, session: UserSession) -> str:
        emission = session.emission_data
        
        tipo = "FACTURA 📄" if emission.document_type == "01" else "BOLETA 🧾"
        id_tipo = "DNI" if emission.id_type == "1" else "RUC"
        symbol = "S/" if emission.currency == "PEN" else "$"
        
        # Mostrar nombre del cliente si está validado
        client_line = ""
        if emission.client_name:
            client_line = f"\n👤 {emission.client_name}"
        
        items_text = ""
        for item in emission.items:
            sub = item.subtotal()
            items_text += f"  • {item.cantidad}x {item.descripcion} @ {symbol}{float(item.precio):.2f} = {symbol}{sub:.2f}\n"
        
        total = emission.calculate_total()
        
        session.awaiting_confirmation = True
        
        return f"""📋 {tipo}

📋 {id_tipo}: {emission.id_number}{client_line}

📦 Productos:
{items_text}
━━━━━━━━━━━━
💵 TOTAL: {symbol}{total:.2f}

¿Emitir? ✅ Sí / ❌ No"""
    
    def _request_data(self, missing: List[str], session: UserSession) -> str:
        emission = session.emission_data
        
        if "tipo_documento" in missing:
            if emission.id_type == "1":
                emission.document_type = "03"
                missing.remove("tipo_documento")
            elif emission.id_type == "6":
                return f"RUC {emission.id_number}\n\n¿Factura o Boleta?"
            else:
                return "¿Factura o Boleta?"
        
        if not missing:
            return self._generate_summary(session)
        
        if "identificacion_cliente" in missing:
            return "¿DNI o RUC del cliente?"
        
        if "productos" in missing:
            # Si el cliente ya está validado, mostrar esa info
            if emission.client_validated and emission.client_name:
                return f"""👤 Cliente: {emission.client_name}
📋 Doc: {emission.id_number}

¿Qué productos?
📝 Ej: 2 laptops a 2500"""
            return "¿Qué productos?\n📝 Ej: 2 laptops a 2500"
        
        return f"Falta: {', '.join(missing)}"


_agent: Optional[EmissionAgent] = None

def get_emission_agent() -> EmissionAgent:
    global _agent
    if _agent is None:
        _agent = EmissionAgent()
    return _agent







