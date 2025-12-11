"""
Métrica de Completación de Tareas
Basada en AgentBench - mide si el agente completa exitosamente la tarea asignada
"""
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class TaskCompletionResult:
    """Resultado de evaluación de completación"""
    success: bool
    score: float  # 0.0 - 1.0
    reason: str
    pdf_generated: bool = False
    api_called: bool = False
    correct_data: bool = False
    
@dataclass
class TaskCompletionMetric:
    """
    Métrica de Completación de Tareas
    
    Evalúa si una emisión se completó exitosamente basándose en:
    1. ¿Se llamó al API de TinRed?
    2. ¿Se generó un PDF?
    3. ¿Los datos en el PDF son correctos?
    """
    
    name: str = "task_completion"
    description: str = "Mide si la emisión se completó con éxito"
    
    def evaluate(
        self,
        response: str,
        expected: dict,
        api_response: Optional[dict] = None
    ) -> TaskCompletionResult:
        """
        Evalúa si la tarea se completó exitosamente
        
        Args:
            response: Respuesta del agente
            expected: Resultado esperado del escenario
            api_response: Respuesta real del API (si disponible)
        """
        # Si no se esperaba emisión, verificar que no se emitió
        if not expected.get("should_emit", True):
            if "emitida" in response.lower() or "PDF:" in response:
                return TaskCompletionResult(
                    success=False,
                    score=0.0,
                    reason="Se emitió cuando no debía emitirse"
                )
            return TaskCompletionResult(
                success=True,
                score=1.0,
                reason="Correctamente no emitió"
            )
        
        # Verificar indicadores de éxito en la respuesta
        pdf_generated = self._check_pdf_generated(response)
        api_called = self._check_api_called(response, api_response)
        correct_data = self._check_correct_data(response, expected)
        
        # Calcular score
        score = 0.0
        reasons = []
        
        if pdf_generated:
            score += 0.4
            reasons.append("PDF generado")
        else:
            reasons.append("PDF no generado")
            
        if api_called:
            score += 0.3
            reasons.append("API llamado")
        else:
            reasons.append("API no llamado")
            
        if correct_data:
            score += 0.3
            reasons.append("Datos correctos")
        else:
            reasons.append("Datos incorrectos o faltantes")
        
        success = score >= 0.7  # Umbral de éxito
        
        return TaskCompletionResult(
            success=success,
            score=score,
            reason="; ".join(reasons),
            pdf_generated=pdf_generated,
            api_called=api_called,
            correct_data=correct_data
        )
    
    def _check_pdf_generated(self, response: str) -> bool:
        """Verifica si se generó un PDF"""
        pdf_indicators = [
            r"PDF:",
            r"📥\s*PDF",
            r"http.*\.pdf",
            r"factpdf",
            r"¡.*emitida!",
            r"✅.*emitida"
        ]
        return any(re.search(pattern, response, re.IGNORECASE) for pattern in pdf_indicators)
    
    def _check_api_called(self, response: str, api_response: Optional[dict]) -> bool:
        """Verifica si se llamó al API"""
        # Si tenemos respuesta del API, es definitivo
        if api_response is not None:
            return api_response.get("success") == "TRUE"
        
        # Sino, inferir de la respuesta
        api_indicators = [
            r"B\d{3}-\d{8}",  # Número de boleta
            r"F\d{3}-\d{8}",  # Número de factura
            r"serie.*número",
            r"comprobante.*generado"
        ]
        return any(re.search(pattern, response, re.IGNORECASE) for pattern in api_indicators)
    
    def _check_correct_data(self, response: str, expected: dict) -> bool:
        """Verifica si los datos son correctos"""
        checks_passed = 0
        checks_total = 0
        
        # Verificar total si está esperado
        if "total" in expected:
            checks_total += 1
            expected_total = expected["total"]
            # Buscar el total en la respuesta
            total_match = re.search(r"S/\s*([\d,]+\.?\d*)", response)
            if total_match:
                found_total = float(total_match.group(1).replace(",", ""))
                if abs(found_total - expected_total) < 0.01:
                    checks_passed += 1
        
        # Verificar tipo de documento
        if "document_type" in expected:
            checks_total += 1
            doc_type = expected["document_type"]
            if doc_type == "03" and "boleta" in response.lower():
                checks_passed += 1
            elif doc_type == "01" and "factura" in response.lower():
                checks_passed += 1
        
        # Verificar número de identificación
        if "id_number" in expected:
            checks_total += 1
            if expected["id_number"] in response:
                checks_passed += 1
        
        # Si no hay checks, asumir correcto
        if checks_total == 0:
            return True
            
        return checks_passed / checks_total >= 0.5


def calculate_task_success_rate(results: list[TaskCompletionResult]) -> float:
    """
    Calcula la tasa de éxito de tareas
    
    Args:
        results: Lista de resultados de evaluación
        
    Returns:
        Tasa de éxito (0.0 - 1.0)
    """
    if not results:
        return 0.0
    successful = sum(1 for r in results if r.success)
    return successful / len(results)
