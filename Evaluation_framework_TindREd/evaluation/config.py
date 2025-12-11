"""
Configuración del Framework de Evaluación - Mia Gente
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Rutas base
BASE_DIR = Path(__file__).parent
DATASETS_DIR = BASE_DIR / "datasets"
REPORTS_DIR = BASE_DIR / "reports"

@dataclass
class EvaluationConfig:
    """Configuración principal de evaluación"""
    
    # Targets de métricas (basados en análisis AgentBench)
    task_success_rate_target: float = 0.95
    data_extraction_accuracy_target: float = 0.98
    intent_classification_f1_target: float = 0.92
    turns_to_completion_target: int = 4
    abandonment_rate_target: float = 0.10
    latency_target_seconds: float = 3.0
    
    # Configuración de evaluación
    num_evaluation_runs: int = 3  # Runs por escenario para promediar
    timeout_seconds: float = 30.0
    parallel_workers: int = 4
    
    # LangSmith
    langsmith_enabled: bool = True
    langsmith_project: str = "mia-gente-eval"

@dataclass
class ModelConfig:
    """Configuración de modelos LLM"""
    
    # Modelo actual en producción
    current_model: str = "gemini-2.5-flash"
    
    # Modelos disponibles para comparación
    available_models: dict = field(default_factory=lambda: {
        "gemini-2.5-flash": {
            "provider": "google",
            "model_id": "gemini-2.5-flash",
            "cost_input": 0.00015,  # USD por 1K tokens
            "cost_output": 0.0006,
        },
        "gemini-3-pro": {
            "provider": "google", 
            "model_id": "gemini-3-pro",
            "cost_input": 0.002,
            "cost_output": 0.012,
        },
        "gpt-5.1": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "cost_input": 0.00125,
            "cost_output": 0.01,
        },
        "claude-opus-4.5": {
            "provider": "anthropic",
            "model_id": "claude-opus-4-5-20251124",
            "cost_input": 0.005,
            "cost_output": 0.025,
        },
        "claude-sonnet-4.5": {
            "provider": "anthropic",
            "model_id": "claude-sonnet-4-5-20250929",
            "cost_input": 0.003,
            "cost_output": 0.015,
        },
    })

@dataclass  
class APIConfig:
    """Configuración de APIs"""
    
    # Agent API (TU AGENTE LOCAL)
    agent_base_url: str = field(
        default_factory=lambda: os.getenv("AGENT_BASE_URL", "http://localhost:8000")
    )
    agent_endpoint: str = "/api/converse"  # Endpoint correcto
    agent_timeout: int = 30
    
    # TinRed API
    tinred_base_url: str = field(
        default_factory=lambda: os.getenv("TINRED_BASE_URL", "https://test.tinred.pe/SisFact/api")
    )
    
    # LLM APIs
    google_api_key: str = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    
    # LangSmith
    langsmith_api_key: str = field(
        default_factory=lambda: os.getenv("LANGCHAIN_API_KEY", "")
    )
    
    @property
    def agent_full_url(self) -> str:
        return f"{self.agent_base_url}{self.agent_endpoint}"

# Instancias globales
eval_config = EvaluationConfig()
model_config = ModelConfig()
api_config = APIConfig()

# Configurar LangSmith si está habilitado
if eval_config.langsmith_enabled and api_config.langsmith_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_config.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = eval_config.langsmith_project
