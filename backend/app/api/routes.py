"""
API Routes
"""
import logging
from fastapi import APIRouter
from app.models.schemas import ConversationRequest, ConversationResponse
from app.agents.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/converse", response_model=ConversationResponse)
async def converse(request: ConversationRequest):
    try:
        orchestrator = get_orchestrator()
        
        reply = orchestrator.handle_message(
            phone=request.phone,
            message=request.message or "",
            file_base64=request.file_base64,
            mime_type=request.mime_type
        )
        
        if not reply:
            reply = "Error al procesar. Intenta nuevamente."
        
        return ConversationResponse(reply=reply)
    
    except Exception as e:
        logger.error(f"[API] Error: {e}", exc_info=True)
        return ConversationResponse(reply="⚠️ Error. Intenta nuevamente.")


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "TinRed Agent v2"}


@router.get("/")
async def root():
    return {"message": "TinRed Invoice Agent API v2", "docs": "/docs"}
