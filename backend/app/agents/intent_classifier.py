"""
Intent Classifier - REESCRITO: Detecta contexto de conversación.
"""
import logging
import re
from typing import Tuple, Optional
from app.models.schemas import IntentType, UserSession

logger = logging.getLogger(__name__)


class IntentClassifier:
    
    AFFIRMATIVE = [
        r'^(si|sí|yes|ok|okey|okay|dale|confirmo|acepto)[\s\.\!\,]*$',
        r'^(adelante|procede|emite|correcto|claro|por supuesto)[\s\.\!\,]*$',
        r'^(está bien|esta bien|de acuerdo|listo|perfecto)[\s\.\!\,]*$',
    ]
    
    NEGATIVE = [
        r'^(no|nop|nope|cancelar|cancela|olvida)[\s\.\!\,]*$',
        r'\b(mejor no|no quiero|detener|parar|salir)\b',
    ]
    
    EMISSION = [
        r'\b(emitir|generar|crear|hacer|necesito|quiero)\s+(una?\s+)?(factura|boleta)\b',
        r'^(factura|boleta)[\s\.\!\,]*$',
        r'\b(factura|boleta)\s+(para|con|de)\b',
        r'\bemite\s+(una?\s+)?(factura|boleta)\b',
    ]
    
    PRODUCTS = [
        r'\b(producto|productos|catálogo|catalogo|inventario)\b',
        r'\b(mis productos|lista de productos|ver productos)\b',
        r'\b(dame|muestra|ver)\s+(los\s+)?productos\b',
    ]
    
    CLIENTS = [
        r'\b(cliente|clientes|mis clientes)\b',
    ]
    
    HISTORY = [
        r'\b(historial|histórico|historico)\b',
        r'\b(ventas|emisiones)\b',
        r'\b(detalle|detalles|info)\s+(?:de\s+)?(?:la|el)\s+(\d+|última|ultimo|ultima)\b',
        r'\b(última|ultimo|ultima|último)\s+(factura|boleta|emisi[oó]n)?\b',
        r'\b(la|el|mi)\s+(de\s+)?hoy\b',
        r'\b(factura|boleta)\s+(de\s+)?hoy\b',
        r'\b(emitida|generada)\s+hoy\b',
    ]
    
    GENERAL_QUESTIONS = [
        r'\b(qué es|que es|cómo funciona|como funciona)\b',
        r'\b(diferencia|diferencias)\b',
        r'\b(ayuda|dudas?|help)\b',
        r'\bigv\b',
        r'\b(explicame|explícame)\b',
        r'\b(cómo|como)\s+(emitir|hacer)\b',
    ]
    
    GREETING = [
        r'^(hola|hey|hi|buenos días|buenas tardes|buenas noches|buenas)[\s\!\.\,]*$',
    ]
    
    PRODUCT_SEARCH = [
        r'\b(busca|buscar|encuentra|encontrar|filtrar|hay|tiene|tengo|existe)\b',
    ]
    
    def __init__(self):
        self._compile_patterns()
        logger.info("[IntentClassifier] ✅ Inicializado")
    
    def _compile_patterns(self):
        self.affirmative_re = [re.compile(p, re.IGNORECASE) for p in self.AFFIRMATIVE]
        self.negative_re = [re.compile(p, re.IGNORECASE) for p in self.NEGATIVE]
        self.emission_re = [re.compile(p, re.IGNORECASE) for p in self.EMISSION]
        self.products_re = [re.compile(p, re.IGNORECASE) for p in self.PRODUCTS]
        self.clients_re = [re.compile(p, re.IGNORECASE) for p in self.CLIENTS]
        self.history_re = [re.compile(p, re.IGNORECASE) for p in self.HISTORY]
        self.general_re = [re.compile(p, re.IGNORECASE) for p in self.GENERAL_QUESTIONS]
        self.greeting_re = [re.compile(p, re.IGNORECASE) for p in self.GREETING]
        self.product_search_re = [re.compile(p, re.IGNORECASE) for p in self.PRODUCT_SEARCH]
    
    def _match(self, text: str, patterns: list) -> bool:
        return any(p.search(text) for p in patterns)
    
    def classify(self, message: str, session: UserSession) -> Tuple[IntentType, float]:
        text = message.strip()
        text_lower = text.lower()
        
        logger.info(f"[Classifier] Analizando: '{text[:50]}'")
        
        # =========================================================
        # DETECTAR CONTEXTO PREVIO
        # =========================================================
        last_context = self._get_conversation_context(session)
        logger.info(f"[Classifier] Contexto: {last_context}")
        
        # =========================================================
        # PRIORIDAD 0: "Sí" después de ver detalle de producto
        # =========================================================
        if last_context == "product_detail":
            if self._match(text, self.affirmative_re):
                logger.info("[Classifier] → QUERY_PRODUCTS (afirmativo en producto)")
                return IntentType.QUERY_PRODUCTS, 0.95
        
        # =========================================================
        # PRIORIDAD 1: Número solo (1-99) - depende del contexto
        # =========================================================
        if re.match(r'^\d{1,2}$', text):
            if last_context in ["history", "products", "search_results", "today_emissions"]:
                if last_context == "products" or last_context == "search_results":
                    logger.info("[Classifier] → QUERY_PRODUCTS (número en contexto productos)")
                    return IntentType.QUERY_PRODUCTS, 0.95
                else:
                    logger.info("[Classifier] → QUERY_HISTORY (número en contexto historial)")
                    return IntentType.QUERY_HISTORY, 0.95
        
        # =========================================================
        # PRIORIDAD 2: Búsqueda de productos en contexto
        # =========================================================
        if last_context == "products":
            if self._match(text, self.product_search_re) or len(text) > 2:
                # Si no es un comando claro de otra cosa
                if not self._match(text, self.emission_re) and not self._match(text, self.history_re):
                    logger.info("[Classifier] → QUERY_PRODUCTS (búsqueda en contexto)")
                    return IntentType.QUERY_PRODUCTS, 0.9
        
        # =========================================================
        # PRIORIDAD 2: Confirmación pendiente de emisión
        # =========================================================
        if session.awaiting_confirmation:
            if self._match(text, self.affirmative_re):
                logger.info("[Classifier] → CONFIRMATION")
                return IntentType.CONFIRMATION, 0.95
            if self._match(text, self.negative_re):
                logger.info("[Classifier] → CANCEL")
                return IntentType.CANCEL, 0.95
        
        # =========================================================
        # PRIORIDAD 3: Emisión en progreso
        # =========================================================
        if self._has_active_emission(session):
            if self._match(text, self.negative_re) and len(text) < 15:
                logger.info("[Classifier] → CANCEL")
                return IntentType.CANCEL, 0.9
            
            # Solo si tiene datos de emisión (DNI/RUC/productos)
            if re.search(r'\b\d{8}\b', text) or re.search(r'\b[12]0\d{9}\b', text):
                logger.info("[Classifier] → EMIT_INVOICE (datos)")
                return IntentType.EMIT_INVOICE, 0.85
            
            if re.search(r'\d+\s+\w+\s+(a|@|por)\s+\d+', text_lower):
                logger.info("[Classifier] → EMIT_INVOICE (productos)")
                return IntentType.EMIT_INVOICE, 0.85
        
        # =========================================================
        # PRIORIDAD 4: Historial y detalles
        # =========================================================
        if self._match(text, self.history_re):
            logger.info("[Classifier] → QUERY_HISTORY")
            return IntentType.QUERY_HISTORY, 0.9
        
        # Detectar "detalles de la X" incluso si no matchea exacto
        if re.search(r'detalle', text_lower) and re.search(r'\d+|última|ultimo', text_lower):
            logger.info("[Classifier] → QUERY_HISTORY (detalle)")
            return IntentType.QUERY_HISTORY, 0.9
        
        # =========================================================
        # PRIORIDAD 5: Preguntas generales
        # =========================================================
        if self._match(text, self.general_re) or ('?' in text and len(text) > 10):
            if not self._match(text, self.emission_re):
                logger.info("[Classifier] → GENERAL_QUESTION")
                return IntentType.GENERAL_QUESTION, 0.9
        
        # =========================================================
        # PRIORIDAD 6: Saludos
        # =========================================================
        if len(text) < 25 and self._match(text, self.greeting_re):
            logger.info("[Classifier] → GREETING")
            return IntentType.GREETING, 0.9
        
        # =========================================================
        # PRIORIDAD 7: Productos
        # =========================================================
        if self._match(text, self.products_re):
            logger.info("[Classifier] → QUERY_PRODUCTS")
            return IntentType.QUERY_PRODUCTS, 0.9
        
        # Búsqueda de productos explícita
        if self._match(text, self.product_search_re) and 'producto' in text_lower:
            logger.info("[Classifier] → QUERY_PRODUCTS (búsqueda)")
            return IntentType.QUERY_PRODUCTS, 0.85
        
        # =========================================================
        # PRIORIDAD 8: Emisión explícita
        # =========================================================
        if self._match(text, self.emission_re):
            logger.info("[Classifier] → EMIT_INVOICE")
            return IntentType.EMIT_INVOICE, 0.85
        
        # =========================================================
        # PRIORIDAD 9: DNI/RUC con contexto de factura/boleta
        # =========================================================
        has_dni = re.search(r'\b\d{8}\b', text)
        has_ruc = re.search(r'\b[12]0\d{9}\b', text)
        
        if (has_dni or has_ruc):
            if self._has_active_emission(session) or 'factura' in text_lower or 'boleta' in text_lower:
                logger.info("[Classifier] → EMIT_INVOICE (documento)")
                return IntentType.EMIT_INVOICE, 0.75
        
        # =========================================================
        # PRIORIDAD 10: Clientes
        # =========================================================
        if self._match(text, self.clients_re):
            logger.info("[Classifier] → QUERY_CLIENTS")
            return IntentType.QUERY_CLIENTS, 0.9
        
        # =========================================================
        # PRIORIDAD 11: Contexto previo como fallback
        # =========================================================
        if last_context == "products" and not self._match(text, self.emission_re):
            logger.info("[Classifier] → QUERY_PRODUCTS (contexto fallback)")
            return IntentType.QUERY_PRODUCTS, 0.7
        
        if last_context == "history" and not self._match(text, self.emission_re):
            logger.info("[Classifier] → QUERY_HISTORY (contexto fallback)")
            return IntentType.QUERY_HISTORY, 0.7
        
        # =========================================================
        # PRIORIDAD 12: Fallback
        # =========================================================
        if '?' in text:
            logger.info("[Classifier] → GENERAL_QUESTION (?)")
            return IntentType.GENERAL_QUESTION, 0.6
        
        logger.info("[Classifier] → UNKNOWN")
        return IntentType.UNKNOWN, 0.5
    
    def _get_conversation_context(self, session: UserSession) -> Optional[str]:
        """Usa el contexto guardado en la sesión."""
        # Primero usar el contexto guardado explícitamente
        if session.conversation_context:
            return session.conversation_context
        
        # Fallback: inferir de los mensajes
        if not session.messages:
            return None
        
        for msg in reversed(session.messages[-4:]):
            if msg.role == "assistant":
                content = msg.content.lower()
                
                if 'tus productos' in content or ('📦' in msg.content and any(f"{i}." in msg.content for i in range(1, 16))):
                    return "products"
                
                if 'historial' in content or 'últimas emisiones' in content:
                    if any(f"{i}." in msg.content for i in range(1, 11)):
                        return "history"
                
                if 'emisiones de hoy' in content:
                    return "today_emissions"
                    
                if 'resultados para' in content:
                    return "search_results"
                
                if 'producto #' in content and '¿deseas emitir' in content:
                    return "product_detail"
        
        return None
    
    def _has_active_emission(self, session: UserSession) -> bool:
        """Verifica si hay emisión en progreso."""
        emission = session.emission_data
        return bool(emission.document_type or emission.id_number or emission.items)
    
    def is_confirmation(self, message: str) -> bool:
        return self._match(message, self.affirmative_re)
    
    def is_cancellation(self, message: str) -> bool:
        return self._match(message, self.negative_re)


_classifier: Optional[IntentClassifier] = None

def get_intent_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier





