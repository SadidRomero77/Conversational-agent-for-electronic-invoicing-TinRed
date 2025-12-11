"""
TinRed Invoice Agent v2
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from app.api.routes import router
from app.core.config import settings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando TinRed Agent v2...")
    logger.info(f"   TinRed: {settings.TINRED_API_URL}")
    logger.info(f"   Modelo: {settings.MODEL_NAME}")
    
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY requerida")
    
    logger.info("✅ Agente listo")
    yield
    logger.info("🛑 Cerrando...")


app = FastAPI(
    title="TinRed Invoice Agent",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"service": "TinRed Agent v2", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
