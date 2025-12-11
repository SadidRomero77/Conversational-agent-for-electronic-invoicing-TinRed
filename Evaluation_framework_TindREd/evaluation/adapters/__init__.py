"""
Adaptador del Agente TinRed para Evaluación
============================================

Este módulo provee la integración entre el framework de evaluación
y el agente real de Mia Gente.

Uso:
    from adapters.tinred_adapter import create_tinred_agent
    
    agent = create_tinred_agent()
    response = await agent("Boleta DNI 12345678", session)
"""
import sys
from pathlib import Path
from typing import Optional, Callable, Awaitable
import asyncio

# Agregar path del proyecto TinRed si está disponible
TINRED_PROJECT_PATHS = [
    Path("/home/user/tinred-ai-agent"),
    Path("../../tinred-ai-agent"),
    Path("../tinred-ai-agent"),
]

def find_tinred_project() -> Optional[Path]:
    """Busca el proyecto TinRed en ubicaciones conocidas"""
    for path in TINRED_PROJECT_PATHS:
        if path.exists() and (path / "src").exists():
            return path
    return None


class TinRedAgentAdapter:
    """
    Adaptador que envuelve el orquestador de TinRed
    para hacerlo compatible con el framework de evaluación.
    """
    
    def __init__(
        self,
        orchestrator=None,
        session_manager=None,
        model_name: str = "gemini-2.5-flash"
    ):
        """
        Args:
            orchestrator: Instancia de MainOrchestrator
            session_manager: Instancia de SessionManager
            model_name: Nombre del modelo a usar
        """
        self.orchestrator = orchestrator
        self.session_manager = session_manager
        self.model_name = model_name
        
        # Intentar importar si no se proporcionaron
        if orchestrator is None:
            self._try_import()
    
    def _try_import(self):
        """Intenta importar los componentes del agente TinRed"""
        project_path = find_tinred_project()
        
        if project_path:
            sys.path.insert(0, str(project_path / "src"))
            
            try:
                from orchestrator import MainOrchestrator
                from session_manager import SessionManager
                
                self.session_manager = SessionManager()
                self.orchestrator = MainOrchestrator(
                    session_manager=self.session_manager
                )
                print(f"✅ Agente TinRed cargado desde {project_path}")
                
            except ImportError as e:
                print(f"⚠️ No se pudo importar el agente TinRed: {e}")
                self.orchestrator = None
        else:
            print("⚠️ Proyecto TinRed no encontrado")
    
    async def __call__(
        self,
        message: str,
        session: dict
    ) -> str:
        """
        Procesa un mensaje y retorna la respuesta del agente
        
        Args:
            message: Mensaje del usuario
            session: Diccionario de sesión del framework de evaluación
            
        Returns:
            Respuesta del agente
        """
        if self.orchestrator is None:
            return "[ERROR: Agente TinRed no disponible]"
        
        try:
            # Convertir sesión del framework a formato TinRed
            tinred_session = self._convert_session(session)
            
            # Llamar al orquestador
            response = await self.orchestrator.process_message(
                message=message,
                session_id=tinred_session.get("session_id", "eval_session"),
                user_id=tinred_session.get("user_id", "eval_user")
            )
            
            # Actualizar sesión del framework con datos de TinRed
            self._sync_session_back(session, tinred_session)
            
            return response
            
        except Exception as e:
            return f"[ERROR: {str(e)}]"
    
    def _convert_session(self, eval_session: dict) -> dict:
        """Convierte sesión del framework a formato TinRed"""
        return {
            "session_id": eval_session.get("session_id", "eval_session"),
            "user_id": eval_session.get("user_id", "eval_user"),
            "messages": eval_session.get("messages", []),
            "emission_data": eval_session.get("emission_data", {}),
            "awaiting_confirmation": eval_session.get("awaiting_confirmation", False),
            "emission_active": eval_session.get("emission_active", False),
        }
    
    def _sync_session_back(self, eval_session: dict, tinred_session: dict):
        """Sincroniza cambios de TinRed de vuelta al framework"""
        if self.session_manager:
            try:
                sm_session = self.session_manager.get_session(
                    tinred_session.get("session_id", "eval_session")
                )
                if sm_session:
                    eval_session["emission_data"] = getattr(sm_session, "emission_data", {})
                    eval_session["awaiting_confirmation"] = getattr(sm_session, "awaiting_confirmation", False)
                    eval_session["emission_active"] = getattr(sm_session, "emission_active", False)
            except Exception:
                pass


class TinRedAPIAdapter:
    """
    Adaptador que se conecta con el agente TinRed via API HTTP.
    Útil cuando el agente está corriendo como servicio.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None
    ):
        """
        Args:
            base_url: URL base del servicio
            api_key: API key si es requerida
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = None
    
    async def _get_client(self):
        """Obtiene o crea el cliente HTTP"""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})
                }
            )
        return self._client
    
    async def __call__(
        self,
        message: str,
        session: dict
    ) -> str:
        """
        Procesa un mensaje via API
        
        Args:
            message: Mensaje del usuario
            session: Diccionario de sesión
            
        Returns:
            Respuesta del agente
        """
        try:
            client = await self._get_client()
            
            response = await client.post(
                "/api/chat",
                json={
                    "message": message,
                    "session_id": session.get("session_id", "eval_session"),
                    "user_id": session.get("user_id", "eval_user"),
                    "context": {
                        "emission_data": session.get("emission_data", {}),
                        "awaiting_confirmation": session.get("awaiting_confirmation", False)
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "[Sin respuesta]")
            else:
                return f"[ERROR HTTP {response.status_code}]"
                
        except Exception as e:
            return f"[ERROR: {str(e)}]"
    
    async def close(self):
        """Cierra el cliente HTTP"""
        if self._client:
            await self._client.aclose()
            self._client = None


def create_tinred_agent(
    mode: str = "direct",
    **kwargs
) -> Callable[[str, dict], Awaitable[str]]:
    """
    Factory para crear el adaptador del agente TinRed
    
    Args:
        mode: Modo de conexión
            - "direct": Importar directamente el orquestador
            - "api": Conectar via API HTTP
            - "mock": Usar mock para testing
        **kwargs: Argumentos adicionales según el modo
        
    Returns:
        Callable async para procesar mensajes
    """
    if mode == "direct":
        adapter = TinRedAgentAdapter(**kwargs)
        return adapter
        
    elif mode == "api":
        adapter = TinRedAPIAdapter(
            base_url=kwargs.get("base_url", "http://localhost:8000"),
            api_key=kwargs.get("api_key")
        )
        return adapter
        
    elif mode == "mock":
        # Importar mock del simulador
        from evaluators.conversation_simulator import MockAgent
        mock = MockAgent()
        
        async def mock_fn(message: str, session: dict) -> str:
            return await mock(message, session)
        
        return mock_fn
    
    else:
        raise ValueError(f"Modo no soportado: {mode}")


# Función de conveniencia para testing
async def test_adapter():
    """Prueba básica del adaptador"""
    print("🧪 Probando adaptador TinRed...\n")
    
    # Probar cada modo
    for mode in ["mock", "direct"]:
        print(f"--- Modo: {mode} ---")
        
        try:
            agent = create_tinred_agent(mode=mode)
            session = {"session_id": "test", "messages": []}
            
            response = await agent("Hola", session)
            print(f"Respuesta: {response[:100]}...")
            print("✅ OK\n")
            
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(test_adapter())
