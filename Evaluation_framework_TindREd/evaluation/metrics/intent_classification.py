"""
Métrica de Clasificación de Intención
Evalúa la precisión del clasificador de intenciones
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import re

class IntentType(Enum):
    """Tipos de intención del agente"""
    EMIT_INVOICE = "emit_invoice"
    QUERY_HISTORY = "query_history"
    QUERY_PRODUCTS = "query_products"
    GREETING = "greeting"
    HELP = "help"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
    UNKNOWN = "unknown"

@dataclass
class IntentClassificationResult:
    """Resultado de clasificación de intención"""
    expected_intent: str
    predicted_intent: str
    correct: bool
    confidence: float = 0.0

class IntentClassificationMetric:
    """
    Métrica de Clasificación de Intención
    
    Evalúa si el agente clasificó correctamente la intención del usuario.
    Basado en los criterios de AgentBench para "instruction following".
    """
    
    name: str = "intent_classification"
    description: str = "Mide la precisión de clasificación de intención"
    
    def __init__(self):
        # Patrones para inferir intención de la respuesta
        self.intent_patterns = {
            IntentType.EMIT_INVOICE: [
                r"boleta",
                r"factura",
                r"emitir",
                r"comprobante",
                r"¿?dni.*ruc",
                r"¿?qué productos",
                r"resumen.*emisión",
                r"¿?confirmas?",
            ],
            IntentType.QUERY_HISTORY: [
                r"historial",
                r"emitiste",
                r"última.*boleta",
                r"última.*factura",
                r"vendiste",
                r"comprobantes.*emitidos",
            ],
            IntentType.QUERY_PRODUCTS: [
                r"productos.*disponibles",
                r"lista.*productos",
                r"catálogo",
            ],
            IntentType.GREETING: [
                r"hola",
                r"buenos.*días",
                r"bienvenid[oa]",
                r"¿?en qué.*ayudar",
                r"menú",
            ],
            IntentType.HELP: [
                r"ayuda",
                r"cómo.*funciona",
                r"instrucciones",
                r"opciones.*disponibles",
            ],
            IntentType.CONFIRMATION: [
                r"confirma",
                r"emitiendo",
                r"procesando",
            ],
            IntentType.CANCELLATION: [
                r"cancelad[oa]",
                r"no.*emitir",
                r"operación.*cancelada",
            ],
        }
    
    def evaluate(
        self,
        user_message: str,
        agent_response: str,
        expected_intent: str,
        classifier_output: Optional[str] = None
    ) -> IntentClassificationResult:
        """
        Evalúa la clasificación de intención
        
        Args:
            user_message: Mensaje del usuario
            agent_response: Respuesta del agente
            expected_intent: Intención esperada según el escenario
            classifier_output: Output directo del clasificador (si disponible)
        """
        # Si tenemos output del clasificador, usarlo
        if classifier_output:
            predicted = classifier_output
        else:
            # Inferir de la respuesta del agente
            predicted = self._infer_intent_from_response(agent_response)
        
        # Normalizar
        expected_normalized = self._normalize_intent(expected_intent)
        predicted_normalized = self._normalize_intent(predicted)
        
        correct = expected_normalized == predicted_normalized
        
        # Calcular confianza basada en cuántos patrones coinciden
        confidence = self._calculate_confidence(agent_response, predicted_normalized)
        
        return IntentClassificationResult(
            expected_intent=expected_normalized,
            predicted_intent=predicted_normalized,
            correct=correct,
            confidence=confidence
        )
    
    def _infer_intent_from_response(self, response: str) -> str:
        """Infiere la intención desde la respuesta del agente"""
        response_lower = response.lower()
        
        scores = {}
        for intent, patterns in self.intent_patterns.items():
            score = sum(1 for p in patterns if re.search(p, response_lower, re.IGNORECASE))
            if score > 0:
                scores[intent] = score
        
        if not scores:
            return IntentType.UNKNOWN.value
        
        # Retornar intención con mayor score
        best_intent = max(scores, key=scores.get)
        return best_intent.value
    
    def _normalize_intent(self, intent: str) -> str:
        """Normaliza el nombre de la intención"""
        intent_lower = intent.lower().strip()
        
        # Mapeo de aliases
        aliases = {
            "emission": "emit_invoice",
            "emit": "emit_invoice",
            "invoice": "emit_invoice",
            "boleta": "emit_invoice",
            "factura": "emit_invoice",
            "history": "query_history",
            "historial": "query_history",
            "products": "query_products",
            "productos": "query_products",
            "hello": "greeting",
            "hola": "greeting",
            "saludo": "greeting",
            "ayuda": "help",
            "cancel": "cancellation",
            "cancelar": "cancellation",
            "confirm": "confirmation",
            "confirmar": "confirmation",
        }
        
        return aliases.get(intent_lower, intent_lower)
    
    def _calculate_confidence(self, response: str, intent: str) -> float:
        """Calcula confianza de la clasificación"""
        try:
            intent_enum = IntentType(intent)
        except ValueError:
            return 0.0
        
        patterns = self.intent_patterns.get(intent_enum, [])
        if not patterns:
            return 0.0
        
        matches = sum(1 for p in patterns if re.search(p, response.lower(), re.IGNORECASE))
        return min(matches / len(patterns), 1.0)


def calculate_intent_f1(results: list[IntentClassificationResult]) -> dict:
    """
    Calcula F1-score para clasificación de intenciones
    
    Returns:
        Dict con precision, recall, f1 por clase y macro-average
    """
    if not results:
        return {"f1_macro": 0.0}
    
    # Obtener todas las clases
    all_intents = set()
    for r in results:
        all_intents.add(r.expected_intent)
        all_intents.add(r.predicted_intent)
    
    # Calcular métricas por clase
    metrics_per_class = {}
    
    for intent in all_intents:
        tp = sum(1 for r in results if r.expected_intent == intent and r.predicted_intent == intent)
        fp = sum(1 for r in results if r.expected_intent != intent and r.predicted_intent == intent)
        fn = sum(1 for r in results if r.expected_intent == intent and r.predicted_intent != intent)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        metrics_per_class[intent] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for r in results if r.expected_intent == intent)
        }
    
    # Calcular macro-average
    f1_scores = [m["f1"] for m in metrics_per_class.values()]
    f1_macro = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    
    # Accuracy general
    accuracy = sum(1 for r in results if r.correct) / len(results)
    
    return {
        "accuracy": accuracy,
        "f1_macro": f1_macro,
        "per_class": metrics_per_class
    }


def create_confusion_matrix(results: list[IntentClassificationResult]) -> dict:
    """
    Crea matriz de confusión para visualización
    
    Returns:
        Dict con matriz y labels
    """
    labels = sorted(set(r.expected_intent for r in results) | set(r.predicted_intent for r in results))
    
    matrix = [[0 for _ in labels] for _ in labels]
    
    label_to_idx = {label: i for i, label in enumerate(labels)}
    
    for r in results:
        true_idx = label_to_idx.get(r.expected_intent, 0)
        pred_idx = label_to_idx.get(r.predicted_intent, 0)
        matrix[true_idx][pred_idx] += 1
    
    return {
        "labels": labels,
        "matrix": matrix
    }
