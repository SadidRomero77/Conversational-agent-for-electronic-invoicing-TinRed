"""
Main Orchestrator - ACTUALIZADO: Maneja reconfirmación de cliente.
"""
import logging
import re
from typing import Optional
from datetime import datetime
from app.models.schemas import UserSession, IntentType
from app.services.session_manager import get_session_manager
from app.services.audio_service import transcribe_audio, AudioTranscriptionError
from app.agents.intent_classifier import get_intent_classifier
from app.agents.conversation_agent import get_conversation_agent
from app.agents.emission_agent import get_emission_agent
from app.agents.data_extractor import get_data_extractor

logger = logging.getLogger(__name__)


class MainOrchestrator:
    def __init__(self):
        self.session_manager = get_session_manager()
        self.intent_classifier = get_intent_classifier()
        self.conversation_agent = get_conversation_agent()
        self.emission_agent = get_emission_agent()
        self.extractor = get_data_extractor()
        logger.info("[Orchestrator] ✅ Inicializado")
    
    def handle_message(
        self,
        phone: str,
        message: str = "",
        file_base64: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> str:
        logger.info("=" * 50)
        logger.info(f"📩 MENSAJE: {phone}")
        
        # Audio
        if file_base64 and mime_type and mime_type.startswith("audio"):
            try:
                message = transcribe_audio(file_base64, mime_type)
                logger.info(f"🎤 Transcrito: {message[:40]}...")
            except AudioTranscriptionError as e:
                return f"🎤 {str(e)}"
        
        if not message or not message.strip():
            return "No recibí ningún mensaje. ¿En qué puedo ayudarte?"
        
        message = message.strip()
        logger.info(f"💬 Mensaje: {message[:50]}...")
        
        session = self.session_manager.get_session(phone)
        
        # ============================================
        # PASO 1: AUTENTICAR
        # ============================================
        if not session.authenticated:
            logger.info("[Orchestrator] 🔐 Autenticando...")
            error = self.session_manager.authenticate_user(session)
            
            if error:
                return "❌ No encontré tu número en TinRed.\n📧 soporte@tinred.pe"
            
            self.session_manager.load_user_context(session)
            products_count = len(session.context.products) if session.context.products else 0
            
            return f"""¡Hola {session.user_name}! 👋

Soy Jack, tu asistente de facturación de TinRed.

Tengo {products_count} productos en tu cuenta.

Para continuar, acepta nuestros términos y políticas:
📋 https://www.tinred.pe/terminos.html
🔒 https://www.tinred.pe/privacidad.html
🛡️ https://www.tinred.pe/seguridad_informacion.html
📜 https://www.tinred.pe/declaracion_seguridad.html

¿Aceptas los términos? Responde "Sí"."""
        
        # ============================================
        # PASO 2: VERIFICAR TÉRMINOS
        # ============================================
        if not session.terms_accepted:
            if self.intent_classifier.is_confirmation(message):
                session.terms_accepted = True
                return f"""✅ ¡Términos aceptados!

¿Qué necesitas, {session.user_name}?

📄 Emitir Factura
🧾 Emitir Boleta
📦 Ver productos
📊 Historial"""
            
            if self.intent_classifier.is_cancellation(message):
                return "Sin aceptar términos no puedo ayudarte. 👋"
            
            return "Necesito que aceptes los términos. ¿Aceptas? Sí/No"
        
        # ============================================
        # PASO 3: CARGAR CONTEXTO
        # ============================================
        if not session.context.is_loaded():
            self.session_manager.load_user_context(session)
        
        session.add_message("user", message)
        
        # ============================================
        # PASO 4: PRIORIDAD - Reconfirmación de cliente
        # ============================================
        if session.awaiting_client_reconfirmation:
            logger.info("[Orchestrator] → Esperando reconfirmación de cliente")
            response = self.emission_agent.process_message(message, session)
            session.add_message("assistant", response)
            session.last_activity = datetime.now()
            return response
        
        # ============================================
        # PASO 5: Confirmación pendiente de emisión
        # ============================================
        if session.awaiting_confirmation:
            if self.intent_classifier.is_confirmation(message):
                logger.info("[Orchestrator] → Confirmó emisión")
                session.awaiting_confirmation = False
                response = self.emission_agent.execute_emission(session)
                session.add_message("assistant", response)
                return response
            
            if self.intent_classifier.is_cancellation(message):
                session.awaiting_confirmation = False
                session.reset_emission()
                return "❌ Cancelado.\n\n¿Qué más necesitas?"
        
        # ============================================
        # PASO 6: Emisión activa en sesión
        # ============================================
        if self._has_active_emission(session):
            logger.info("[Orchestrator] → Emisión activa, usando emission_agent")
            response = self.emission_agent.process_message(message, session)
            session.add_message("assistant", response)
            session.last_activity = datetime.now()
            logger.info(f"✅ Respuesta: {response[:50]}...")
            return response
        
        # ============================================
        # PASO 7: Detectar datos de emisión en mensaje
        # ============================================
        if self._message_has_emission_data(message):
            logger.info("[Orchestrator] → Datos de emisión detectados")
            response = self.emission_agent.process_message(message, session)
            session.add_message("assistant", response)
            session.last_activity = datetime.now()
            return response
        
        # ============================================
        # PASO 8: CLASIFICAR INTENCIÓN
        # ============================================
        intent, conf = self.intent_classifier.classify(message, session)
        logger.info(f"🎯 Intent: {intent.value} ({conf:.2f})")
        
        # ============================================
        # PASO 9: ROUTING
        # ============================================
        response = self._route(message, intent, session)
        
        session.add_message("assistant", response)
        session.last_activity = datetime.now()
        
        logger.info(f"✅ Respuesta: {response[:50]}...")
        logger.info("=" * 50)
        
        return response
    
    def _route(self, message: str, intent: IntentType, session: UserSession) -> str:
        
        # Emisión
        if intent == IntentType.EMIT_INVOICE:
            return self.emission_agent.process_message(message, session)
        
        # Saludo
        if intent == IntentType.GREETING:
            return self.conversation_agent.handle_greeting(session)
        
        # Cancelar
        if intent == IntentType.CANCEL:
            session.reset_emission()
            return "❌ Cancelado.\n\n📄 Factura | 🧾 Boleta | 📊 Historial"
        
        # Consultas
        if intent in [IntentType.QUERY_PRODUCTS, IntentType.QUERY_CLIENTS, 
                      IntentType.QUERY_HISTORY, IntentType.GENERAL_QUESTION]:
            return self.conversation_agent.handle_query(message, intent, session)
        
        # Desconocido - Verificar si parece emisión
        if self._looks_like_emission(message, session):
            return self.emission_agent.process_message(message, session)
        
        return f"""¿En qué te ayudo, {session.user_name}?

📄 Emitir Factura
🧾 Emitir Boleta
📦 Ver productos
📊 Historial"""
    
    def _has_active_emission(self, session: UserSession) -> bool:
        """Verifica si hay emisión en progreso."""
        emission = session.emission_data
        return bool(emission.document_type or emission.id_number or emission.items)
    
    def _message_has_emission_data(self, message: str) -> bool:
        """Detecta si el mensaje tiene datos de emisión."""
        msg_lower = message.lower()
        
        # Palabras clave de emisión
        if any(w in msg_lower for w in ['factura', 'boleta', 'emitir', 'emite']):
            return True
        
        # DNI (8 dígitos)
        if re.search(r'\b\d{8}\b', message):
            return True
        
        # RUC (11 dígitos empezando con 10 o 20)
        if re.search(r'\b[12]0\d{9}\b', message):
            return True
        
        # Productos con precio (ej: "2 laptops a 2500")
        if re.search(r'\d+\s+\w+\s+(a|@|por)\s+\d+', msg_lower):
            return True
        
        return False
    
    def _looks_like_emission(self, message: str, session: UserSession) -> bool:
        """Verifica si el mensaje parece relacionado con emisión."""
        msg_lower = message.lower()
        
        # Si menciona confirmar y hay historial de emisión en conversación
        if any(w in msg_lower for w in ['confirmo', 'si', 'sí', 'ok']):
            for msg in session.messages[-3:]:
                if msg.role == "assistant":
                    if any(w in msg.content.lower() for w in ['boleta', 'factura', 'emitir', 'confirmas']):
                        return True
        
        return False


_orchestrator: Optional[MainOrchestrator] = None

def get_orchestrator() -> MainOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MainOrchestrator()
    return _orchestrator






