"""
Simulador de Conversaciones
Simula interacciones multi-turno con el agente para evaluación
"""
import sys
from pathlib import Path
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum
import re
import json

# Asegurar que el path del proyecto esté disponible
sys.path.insert(0, str(Path(__file__).parent.parent))

class ConversationState(Enum):
    """Estados de la conversación"""
    IDLE = "idle"
    EMISSION_STARTED = "emission_started"
    AWAITING_ID = "awaiting_id"
    AWAITING_ITEMS = "awaiting_items"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"

@dataclass
class Message:
    """Un mensaje en la conversación"""
    role: str  # "user" o "assistant"
    content: str
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

@dataclass
class ConversationSession:
    """Sesión de conversación simulada"""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    state: ConversationState = ConversationState.IDLE
    emission_data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, **kwargs):
        """Agrega un mensaje a la sesión"""
        self.messages.append(Message(role=role, content=content, **kwargs))
    
    def get_history(self) -> list[dict]:
        """Retorna historial en formato para el agente"""
        return [{"role": m.role, "content": m.content} for m in self.messages]
    
    def to_dict(self) -> dict:
        """Convierte la sesión a diccionario"""
        return {
            "session_id": self.session_id,
            "messages": self.get_history(),
            "state": self.state.value,
            "emission_data": self.emission_data,
            "metadata": self.metadata
        }


class ConversationSimulator:
    """
    Simulador de Conversaciones Multi-turno
    
    Permite simular conversaciones completas con el agente,
    manejando el estado y siguiendo flujos predefinidos.
    """
    
    def __init__(
        self,
        agent_callable: Callable,
        session_manager: Optional[Any] = None
    ):
        """
        Args:
            agent_callable: Función async que procesa mensajes
                           Signature: async def agent(message: str, session: dict) -> str
            session_manager: Manejador de sesión opcional (para integración con agente real)
        """
        self.agent = agent_callable
        self.session_manager = session_manager
        self.sessions: dict[str, ConversationSession] = {}
    
    def create_session(self, session_id: str) -> ConversationSession:
        """Crea una nueva sesión de conversación"""
        session = ConversationSession(session_id=session_id)
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Obtiene una sesión existente"""
        return self.sessions.get(session_id)
    
    async def send_message(
        self,
        session_id: str,
        user_message: str
    ) -> str:
        """
        Envía un mensaje y obtiene respuesta
        
        Args:
            session_id: ID de la sesión
            user_message: Mensaje del usuario
            
        Returns:
            Respuesta del agente
        """
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)
        
        # Agregar mensaje del usuario
        session.add_message("user", user_message)
        
        # Obtener respuesta del agente
        response = await self.agent(user_message, session.to_dict())
        
        # Agregar respuesta
        session.add_message("assistant", response)
        
        # Actualizar estado basado en la respuesta
        self._update_state(session, response)
        
        return response
    
    def _update_state(self, session: ConversationSession, response: str):
        """Actualiza el estado de la conversación basado en la respuesta"""
        response_lower = response.lower()
        
        # Detectar estado por patrones en la respuesta
        if any(word in response_lower for word in ["cancelad", "no se emitió"]):
            session.state = ConversationState.CANCELLED
        elif any(word in response_lower for word in ["emitida", "pdf:", "comprobante generado"]):
            session.state = ConversationState.COMPLETED
        elif "¿confirma" in response_lower or "confirmar?" in response_lower:
            session.state = ConversationState.AWAITING_CONFIRMATION
        elif any(word in response_lower for word in ["¿qué productos", "¿productos?"]):
            session.state = ConversationState.AWAITING_ITEMS
        elif any(word in response_lower for word in ["dni", "ruc", "documento"]):
            session.state = ConversationState.AWAITING_ID
        elif any(word in response_lower for word in ["boleta", "factura", "comprobante"]):
            session.state = ConversationState.EMISSION_STARTED
    
    async def run_scenario(
        self,
        session_id: str,
        messages: list[str],
        expected_final_state: Optional[ConversationState] = None
    ) -> tuple[list[str], ConversationState]:
        """
        Ejecuta un escenario completo de conversación
        
        Args:
            session_id: ID de sesión
            messages: Lista de mensajes del usuario
            expected_final_state: Estado esperado al final (opcional)
            
        Returns:
            Tupla de (respuestas, estado_final)
        """
        responses = []
        
        for message in messages:
            response = await self.send_message(session_id, message)
            responses.append(response)
        
        session = self.get_session(session_id)
        final_state = session.state if session else ConversationState.ERROR
        
        return responses, final_state
    
    async def simulate_emission_flow(
        self,
        session_id: str,
        document_type: str = "boleta",
        id_number: str = "12345678",
        items: list[dict] = None,
        should_confirm: bool = True
    ) -> dict:
        """
        Simula un flujo completo de emisión
        
        Args:
            session_id: ID de sesión
            document_type: "boleta" o "factura"
            id_number: DNI (8 dígitos) o RUC (11 dígitos)
            items: Lista de items [{cantidad, descripcion, precio}]
            should_confirm: Si debe confirmar la emisión
            
        Returns:
            Dict con resultados de la simulación
        """
        if items is None:
            items = [{"cantidad": "2", "descripcion": "productos", "precio": "50.00"}]
        
        results = {
            "session_id": session_id,
            "document_type": document_type,
            "steps": [],
            "success": False,
            "final_state": None
        }
        
        # Paso 1: Iniciar emisión
        msg1 = f"Quiero emitir una {document_type}"
        resp1 = await self.send_message(session_id, msg1)
        results["steps"].append({"message": msg1, "response": resp1})
        
        # Paso 2: Proporcionar identificación
        msg2 = id_number
        resp2 = await self.send_message(session_id, msg2)
        results["steps"].append({"message": msg2, "response": resp2})
        
        # Paso 3: Proporcionar items
        items_str = ", ".join([
            f"{item['cantidad']} {item.get('descripcion', 'productos')} a {item['precio']}"
            for item in items
        ])
        msg3 = items_str
        resp3 = await self.send_message(session_id, msg3)
        results["steps"].append({"message": msg3, "response": resp3})
        
        # Paso 4: Confirmar o cancelar
        if should_confirm:
            msg4 = "Sí, confirmo"
        else:
            msg4 = "No, cancelar"
        resp4 = await self.send_message(session_id, msg4)
        results["steps"].append({"message": msg4, "response": resp4})
        
        # Evaluar resultado
        session = self.get_session(session_id)
        results["final_state"] = session.state.value if session else "error"
        results["success"] = session.state == ConversationState.COMPLETED if should_confirm else session.state == ConversationState.CANCELLED
        
        return results
    
    def reset_session(self, session_id: str):
        """Reinicia una sesión"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def reset_all(self):
        """Reinicia todas las sesiones"""
        self.sessions.clear()


class MockAgent:
    """
    Agente simulado para pruebas
    Responde de forma determinística según patrones
    """
    
    def __init__(self):
        self.state = {}
    
    async def __call__(self, message: str, session: dict) -> str:
        """Procesa mensaje y retorna respuesta simulada"""
        message_lower = message.lower()
        
        # Detectar intención
        if any(word in message_lower for word in ["boleta", "factura", "emitir", "comprobante"]):
            doc_type = "FACTURA" if "factura" in message_lower else "BOLETA"
            
            # Buscar DNI/RUC en el mensaje
            dni_match = re.search(r'\b(\d{8})\b', message)
            ruc_match = re.search(r'\b([12]0\d{9})\b', message)
            
            if ruc_match or dni_match:
                id_num = ruc_match.group(1) if ruc_match else dni_match.group(1)
                # Buscar productos
                if re.search(r'\d+\s*\w+\s*a\s*\d+', message_lower):
                    return f"""📋 RESUMEN DE {doc_type}
━━━━━━━━━━━━━━━━━━
👤 Cliente: {id_num}
📦 Productos detectados
💰 Total: S/100.00

¿Confirmas la emisión? (Sí/No)"""
                else:
                    return f"✅ {doc_type} - {'RUC' if ruc_match else 'DNI'}: {id_num}\n\n¿Qué productos deseas incluir?"
            else:
                return f"🧾 {doc_type}\n\n¿Cuál es el DNI o RUC del cliente?"
        
        elif any(word in message_lower for word in ["sí", "si", "confirmo", "dale"]):
            return """✅ ¡BOLETA EMITIDA!
━━━━━━━━━━━━━━━━━━
📄 Serie-Número: B001-00000123
💰 Total: S/100.00
📥 PDF: https://example.com/pdf/B001-00000123.pdf"""
        
        elif any(word in message_lower for word in ["no", "cancelar", "cancela"]):
            return "❌ Operación cancelada. ¿En qué más puedo ayudarte?"
        
        elif any(word in message_lower for word in ["hola", "buenos", "buenas"]):
            return """👋 ¡Hola! Soy Mia, tu asistente de facturación.

¿Qué deseas hacer?
• Emitir Boleta
• Emitir Factura
• Ver historial"""
        
        elif any(word in message_lower for word in ["historial", "emití", "vendí"]):
            return """📊 HISTORIAL DE HOY
━━━━━━━━━━━━━━━━━━
1. B001-00000120 - S/45.00
2. B001-00000121 - S/120.00
3. F001-00000050 - S/500.00

Total del día: S/665.00"""
        
        else:
            # Mensaje genérico o número
            if re.search(r'\b\d{8}\b', message):
                return "✅ DNI registrado. ¿Qué productos incluimos?"
            elif re.search(r'\b[12]0\d{9}\b', message):
                return "✅ RUC registrado. ¿Qué productos incluimos?"
            else:
                return "No entendí tu mensaje. ¿Deseas emitir una boleta o factura?"


async def demo_simulation():
    """Demostración del simulador"""
    # Crear agente mock
    mock_agent = MockAgent()
    
    # Crear simulador
    simulator = ConversationSimulator(agent_callable=mock_agent)
    
    print("🎭 Demo del Simulador de Conversaciones")
    print("=" * 50)
    
    # Simular flujo completo
    result = await simulator.simulate_emission_flow(
        session_id="demo-001",
        document_type="boleta",
        id_number="12345678",
        items=[
            {"cantidad": "2", "descripcion": "cuadernos", "precio": "15.00"},
            {"cantidad": "5", "descripcion": "lapiceros", "precio": "3.00"}
        ],
        should_confirm=True
    )
    
    print("\n📝 Pasos de la conversación:")
    for i, step in enumerate(result["steps"], 1):
        print(f"\n--- Paso {i} ---")
        print(f"👤 Usuario: {step['message']}")
        print(f"🤖 Agente: {step['response'][:100]}...")
    
    print(f"\n✅ Éxito: {result['success']}")
    print(f"📊 Estado final: {result['final_state']}")


if __name__ == "__main__":
    asyncio.run(demo_simulation())
