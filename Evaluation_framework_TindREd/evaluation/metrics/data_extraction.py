"""
Métrica de Extracción de Datos
Evalúa la precisión en la extracción de DNI, RUC, productos y precios
"""
from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class ExtractionResult:
    """Resultado de una extracción individual"""
    field_name: str
    expected: str
    extracted: Optional[str]
    correct: bool
    
@dataclass
class DataExtractionResult:
    """Resultado completo de evaluación de extracción"""
    accuracy: float  # 0.0 - 1.0
    extractions: list[ExtractionResult] = field(default_factory=list)
    dni_correct: bool = False
    ruc_correct: bool = False
    items_correct: bool = False
    total_correct: bool = False

class DataExtractionMetric:
    """
    Métrica de Extracción de Datos
    
    Evalúa la precisión del agente al extraer:
    - DNI (8 dígitos)
    - RUC (11 dígitos, empieza con 10 o 20)
    - Productos (cantidad, descripción, precio)
    - Total calculado
    """
    
    name: str = "data_extraction"
    description: str = "Mide la precisión de extracción de datos estructurados"
    
    def __init__(self):
        # Patrones de extracción
        self.dni_pattern = r'\b(\d{8})\b'
        self.ruc_pattern = r'\b([12]0\d{9})\b'
        self.item_pattern = r'(\d+)\s*[x×@]\s*([^@\d]+?)\s*[@a]\s*S?/?\.?\s*(\d+(?:\.\d{2})?)'
        self.total_pattern = r'(?:total|suma|monto)[:\s]*S?/?\.?\s*([\d,]+\.?\d*)'
    
    def evaluate(
        self,
        agent_response: str,
        expected: dict,
        session_data: Optional[dict] = None
    ) -> DataExtractionResult:
        """
        Evalúa la precisión de extracción
        
        Args:
            agent_response: Respuesta del agente
            expected: Datos esperados del escenario
            session_data: Datos de sesión del agente (si disponibles)
        """
        extractions = []
        
        # Evaluar DNI
        if "id_number" in expected and expected.get("id_type") == "1":
            dni_result = self._evaluate_dni(agent_response, expected["id_number"], session_data)
            extractions.append(dni_result)
        
        # Evaluar RUC
        if "id_number" in expected and expected.get("id_type") == "6":
            ruc_result = self._evaluate_ruc(agent_response, expected["id_number"], session_data)
            extractions.append(ruc_result)
        
        # Evaluar items
        if "items" in expected:
            items_result = self._evaluate_items(agent_response, expected["items"], session_data)
            extractions.extend(items_result)
        
        # Evaluar total
        if "total" in expected:
            total_result = self._evaluate_total(agent_response, expected["total"], session_data)
            extractions.append(total_result)
        
        # Calcular accuracy
        if not extractions:
            accuracy = 1.0  # No hay nada que evaluar
        else:
            correct = sum(1 for e in extractions if e.correct)
            accuracy = correct / len(extractions)
        
        return DataExtractionResult(
            accuracy=accuracy,
            extractions=extractions,
            dni_correct=any(e.field_name == "dni" and e.correct for e in extractions),
            ruc_correct=any(e.field_name == "ruc" and e.correct for e in extractions),
            items_correct=all(e.correct for e in extractions if e.field_name.startswith("item")),
            total_correct=any(e.field_name == "total" and e.correct for e in extractions)
        )
    
    def _evaluate_dni(
        self, 
        response: str, 
        expected_dni: str,
        session_data: Optional[dict]
    ) -> ExtractionResult:
        """Evalúa extracción de DNI"""
        # Primero buscar en session_data si disponible
        extracted = None
        if session_data and "emission_data" in session_data:
            extracted = session_data["emission_data"].get("id_number")
        
        # Si no, buscar en respuesta
        if not extracted:
            # Normalizar: juntar dígitos separados
            normalized = self._normalize_digits(response)
            match = re.search(self.dni_pattern, normalized)
            if match:
                extracted = match.group(1)
        
        # Normalizar expected también
        expected_normalized = expected_dni.replace(" ", "")
        
        correct = extracted == expected_normalized
        
        return ExtractionResult(
            field_name="dni",
            expected=expected_normalized,
            extracted=extracted,
            correct=correct
        )
    
    def _evaluate_ruc(
        self,
        response: str,
        expected_ruc: str,
        session_data: Optional[dict]
    ) -> ExtractionResult:
        """Evalúa extracción de RUC"""
        extracted = None
        if session_data and "emission_data" in session_data:
            extracted = session_data["emission_data"].get("id_number")
        
        if not extracted:
            normalized = self._normalize_digits(response)
            match = re.search(self.ruc_pattern, normalized)
            if match:
                extracted = match.group(1)
        
        expected_normalized = expected_ruc.replace(" ", "")
        correct = extracted == expected_normalized
        
        return ExtractionResult(
            field_name="ruc",
            expected=expected_normalized,
            extracted=extracted,
            correct=correct
        )
    
    def _evaluate_items(
        self,
        response: str,
        expected_items: list[dict],
        session_data: Optional[dict]
    ) -> list[ExtractionResult]:
        """Evalúa extracción de items"""
        results = []
        
        # Obtener items extraídos
        extracted_items = []
        if session_data and "emission_data" in session_data:
            extracted_items = session_data["emission_data"].get("items", [])
        
        for i, expected_item in enumerate(expected_items):
            expected_qty = str(expected_item.get("cantidad", ""))
            expected_price = expected_item.get("precio", "")
            
            # Buscar item correspondiente
            extracted_qty = None
            extracted_price = None
            
            if i < len(extracted_items):
                extracted_qty = str(extracted_items[i].get("cantidad", ""))
                extracted_price = extracted_items[i].get("precio", "")
            
            # Evaluar cantidad
            qty_correct = self._compare_numbers(expected_qty, extracted_qty)
            results.append(ExtractionResult(
                field_name=f"item_{i}_cantidad",
                expected=expected_qty,
                extracted=extracted_qty,
                correct=qty_correct
            ))
            
            # Evaluar precio
            price_correct = self._compare_prices(expected_price, extracted_price)
            results.append(ExtractionResult(
                field_name=f"item_{i}_precio",
                expected=expected_price,
                extracted=extracted_price,
                correct=price_correct
            ))
        
        return results
    
    def _evaluate_total(
        self,
        response: str,
        expected_total: float,
        session_data: Optional[dict]
    ) -> ExtractionResult:
        """Evalúa el total calculado"""
        extracted = None
        
        # Buscar en respuesta
        match = re.search(r'S/\s*([\d,]+\.?\d*)', response, re.IGNORECASE)
        if match:
            try:
                extracted = float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        
        correct = extracted is not None and abs(extracted - expected_total) < 0.01
        
        return ExtractionResult(
            field_name="total",
            expected=str(expected_total),
            extracted=str(extracted) if extracted else None,
            correct=correct
        )
    
    def _normalize_digits(self, text: str) -> str:
        """Normaliza texto juntando dígitos separados"""
        # Convertir "0 6 1 0 4 0 1 1" a "06104011"
        result = re.sub(r'(\d)\s+(?=\d)', r'\1', text)
        return result
    
    def _compare_numbers(self, expected: str, extracted: Optional[str]) -> bool:
        """Compara dos números como strings"""
        if extracted is None:
            return False
        try:
            return int(float(expected)) == int(float(extracted))
        except (ValueError, TypeError):
            return expected == extracted
    
    def _compare_prices(self, expected: str, extracted: Optional[str]) -> bool:
        """Compara dos precios con tolerancia"""
        if extracted is None:
            return False
        try:
            exp_val = float(expected)
            ext_val = float(extracted)
            return abs(exp_val - ext_val) < 0.01
        except (ValueError, TypeError):
            return False


def calculate_extraction_accuracy(results: list[DataExtractionResult]) -> dict:
    """
    Calcula métricas agregadas de extracción
    
    Returns:
        Dict con accuracy general, por DNI, RUC, items y total
    """
    if not results:
        return {"overall": 0.0}
    
    overall = sum(r.accuracy for r in results) / len(results)
    
    dni_results = [r for r in results if any(e.field_name == "dni" for e in r.extractions)]
    ruc_results = [r for r in results if any(e.field_name == "ruc" for e in r.extractions)]
    
    return {
        "overall": overall,
        "dni_accuracy": sum(1 for r in dni_results if r.dni_correct) / len(dni_results) if dni_results else None,
        "ruc_accuracy": sum(1 for r in ruc_results if r.ruc_correct) / len(ruc_results) if ruc_results else None,
        "items_accuracy": sum(1 for r in results if r.items_correct) / len(results),
        "total_accuracy": sum(1 for r in results if r.total_correct) / len(results)
    }
