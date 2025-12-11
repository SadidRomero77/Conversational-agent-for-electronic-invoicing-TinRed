"""
Modelos Pydantic para el sistema.
ACTUALIZADO: Campos para validación de cliente.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    EMIT_INVOICE = "emit_invoice"
    QUERY_PRODUCTS = "query_products"
    QUERY_CLIENTS = "query_clients"
    QUERY_HISTORY = "query_history"
    GENERAL_QUESTION = "general_question"
    CONFIRMATION = "confirmation"
    CANCEL = "cancel"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class ClientIdentification(BaseModel):
    IdEmpresa: str
    IdEstablecimiento: str = "0001"
    IdUsuario: int
    Nombre: Optional[str] = None


class InvoiceItem(BaseModel):
    cantidad: str
    descripcion: str
    precio: str
    
    def subtotal(self) -> float:
        try:
            return float(self.cantidad) * float(self.precio)
        except:
            return 0.0


class InvoicePayload(BaseModel):
    idEmpresa: str
    idEstablecimiento: str
    idUsuario: str
    tdocod: str
    mondoc: str
    tdicod: str
    clinum: str
    cant: List[str]
    detpro: List[str]
    preuni: List[str]
    total: str


class InvoiceResponse(BaseModel):
    success: str
    estado: str
    serie: str
    numero: str
    id: int
    mensaje: str
    pdf: str
    
    def is_successful(self) -> bool:
        return self.success.upper() == "TRUE"
    
    def get_full_number(self) -> str:
        return f"{self.serie}-{self.numero}"
    
    def get_pdf_url(self) -> str:
        return self.pdf


class EmissionData(BaseModel):
    document_type: Optional[str] = None
    currency: Optional[str] = "PEN"
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    items: List[InvoiceItem] = []
    
    # NUEVOS CAMPOS - Validación de cliente
    client_validated: bool = False       # Si el cliente fue validado con API
    client_name: Optional[str] = None    # Nombre del cliente si fue encontrado
    
    def is_complete(self) -> bool:
        return all([
            self.document_type,
            self.currency,
            self.id_type,
            self.id_number,
            len(self.items) > 0
        ])
    
    def get_missing_fields(self) -> List[str]:
        missing = []
        if not self.document_type:
            missing.append("tipo_documento")
        if not self.id_type or not self.id_number:
            missing.append("identificacion_cliente")
        if not self.items:
            missing.append("productos")
        return missing
    
    def calculate_total(self) -> float:
        return sum(item.subtotal() for item in self.items)
    
    def reset(self):
        self.document_type = None
        self.currency = "PEN"
        self.id_type = None
        self.id_number = None
        self.items = []
        # NUEVOS - Limpiar validación de cliente
        self.client_validated = False
        self.client_name = None


class EmissionRecord(BaseModel):
    timestamp: datetime
    document_type: str
    serie_numero: str
    client_id: str
    total: float
    currency: str
    pdf_url: str
    items_count: int


class UserContext(BaseModel):
    clients: List[Dict[str, Any]] = []
    products: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []
    loaded_at: Optional[datetime] = None
    
    def is_loaded(self) -> bool:
        return self.loaded_at is not None
    
    def is_stale(self, ttl_minutes: int = 60) -> bool:
        if not self.loaded_at:
            return True
        age = datetime.now() - self.loaded_at
        return age.total_seconds() > ttl_minutes * 60


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    intent: Optional[str] = None


class UserSession(BaseModel):
    phone: str
    user_name: Optional[str] = None
    client_data: Optional[ClientIdentification] = None
    authenticated: bool = False
    terms_accepted: bool = False
    
    emission_data: EmissionData = Field(default_factory=EmissionData)
    awaiting_confirmation: bool = False
    
    # NUEVO - Flag para reconfirmación de cliente
    awaiting_client_reconfirmation: bool = False
    
    # NUEVO - Items pendientes (sin precio)
    pending_items: List[Dict[str, str]] = []
    
    # NUEVO - Contexto de conversación (qué está viendo el usuario)
    conversation_context: Optional[str] = None  # "history", "products", "search_results", "product_detail"
    
    # NUEVO - Resultados de búsqueda (para selección por número)
    search_results: List[Dict[str, Any]] = []
    
    # NUEVO - Producto seleccionado para emitir
    selected_product: Optional[Dict[str, Any]] = None
    
    context: UserContext = Field(default_factory=UserContext)
    messages: List[ConversationMessage] = []
    session_emissions: List[EmissionRecord] = []
    
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str, intent: str = None):
        self.messages.append(ConversationMessage(
            role=role,
            content=content,
            intent=intent
        ))
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
        self.last_activity = datetime.now()
    
    def reset_emission(self):
        """Resetea todos los datos de emisión."""
        self.emission_data.reset()
        self.awaiting_confirmation = False
        # NUEVOS - Limpiar flags adicionales
        self.awaiting_client_reconfirmation = False
        self.pending_items = []
        self.selected_product = None
    
    def set_context(self, context: str, search_results: List[Dict] = None):
        """Establece el contexto de conversación."""
        self.conversation_context = context
        if search_results is not None:
            self.search_results = search_results
    
    def clear_context(self):
        """Limpia el contexto de conversación."""
        self.conversation_context = None
        self.search_results = []
        self.selected_product = None


class ConversationRequest(BaseModel):
    phone: str
    message: Optional[str] = ""
    mime_type: Optional[str] = None
    file_base64: Optional[str] = None


class ConversationResponse(BaseModel):
    reply: str





