"""
Gestor de sesiones - CORREGIDO para mantener estado.
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.models.schemas import UserSession, UserContext, ClientIdentification, EmissionRecord
from app.services.tinred_client import get_tinred_client, TinRedAPIError
from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
        self._tinred = get_tinred_client()
        logger.info("[SessionManager] ✅ Inicializado")
    
    def get_session(self, phone: str) -> UserSession:
        clean_phone = phone.split("@")[0].strip()
        
        if clean_phone not in self._sessions:
            logger.info(f"[SessionManager] 🆕 Nueva sesión: {clean_phone}")
            self._sessions[clean_phone] = UserSession(phone=clean_phone)
        else:
            session = self._sessions[clean_phone]
            age = datetime.now() - session.last_activity
            if age > timedelta(hours=settings.SESSION_TTL_HOURS):
                logger.info(f"[SessionManager] ♻️ Sesión expirada, renovando")
                self._sessions[clean_phone] = UserSession(phone=clean_phone)
        
        return self._sessions[clean_phone]
    
    def authenticate_user(self, session: UserSession) -> Optional[str]:
        if session.authenticated:
            return None
        
        try:
            logger.info(f"[SessionManager] 🔐 Autenticando: {session.phone}")
            client = self._tinred.identify_client(session.phone)
            
            session.client_data = client
            session.user_name = client.Nombre
            session.authenticated = True
            session.terms_accepted = False
            
            logger.info(f"[SessionManager] ✅ Autenticado: {client.Nombre}")
            return None
        except TinRedAPIError as e:
            logger.error(f"[SessionManager] ❌ Error: {e}")
            return str(e)
        except Exception as e:
            logger.error(f"[SessionManager] ❌ Error inesperado: {e}")
            return "Error al verificar tu cuenta"
    
    def load_user_context(self, session: UserSession, force: bool = False) -> bool:
        if not force and session.context.is_loaded() and not session.context.is_stale():
            logger.info("[SessionManager] 📦 Usando contexto cacheado")
            return True
        
        logger.info(f"[SessionManager] 📥 Cargando contexto...")
        
        try:
            products = self._tinred.get_products(session.phone)
            clients = self._tinred.get_clients(session.phone)
            history = self._tinred.get_history(session.phone)
            
            session.context = UserContext(
                clients=clients,
                products=products,
                history=history,
                loaded_at=datetime.now()
            )
            
            logger.info(f"[SessionManager] ✅ Contexto: {len(products)} productos, {len(clients)} clientes, {len(history)} historial")
            return True
        except Exception as e:
            logger.error(f"[SessionManager] ❌ Error cargando contexto: {e}")
            session.context = UserContext(loaded_at=datetime.now())
            return False
    
    def record_emission(self, session: UserSession, document_type: str, serie_numero: str,
                       client_id: str, total: float, currency: str, pdf_url: str, items_count: int):
        record = EmissionRecord(
            timestamp=datetime.now(),
            document_type="Factura" if document_type == "01" else "Boleta",
            serie_numero=serie_numero,
            client_id=client_id,
            total=total,
            currency=currency,
            pdf_url=pdf_url,
            items_count=items_count
        )
        session.session_emissions.append(record)
        logger.info(f"[SessionManager] 📝 Emisión registrada: {serie_numero}")


_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
