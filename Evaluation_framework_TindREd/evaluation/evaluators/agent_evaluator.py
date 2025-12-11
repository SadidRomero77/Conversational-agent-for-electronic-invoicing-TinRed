"""
Evaluador Principal del Agente
Orquesta la evaluación completa usando todas las métricas
"""
import sys
import json
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from datetime import datetime

# Asegurar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import eval_config, DATASETS_DIR
from metrics import (
    TaskCompletionMetric, 
    DataExtractionMetric, 
    IntentClassificationMetric,
    LatencyMetric
)
from metrics.task_completion import TaskCompletionResult, calculate_task_success_rate
from metrics.data_extraction import DataExtractionResult, calculate_extraction_accuracy
from metrics.intent_classification import IntentClassificationResult, calculate_intent_f1
from metrics.latency import LatencyResult

@dataclass
class ScenarioResult:
    """Resultado de un escenario individual"""
    scenario_id: str
    category: str
    success: bool
    task_completion: Optional[TaskCompletionResult] = None
    data_extraction: Optional[DataExtractionResult] = None
    intent_classification: Optional[IntentClassificationResult] = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    agent_response: str = ""

@dataclass
class EvaluationReport:
    """Reporte completo de evaluación"""
    timestamp: str
    model_name: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    
    # Métricas agregadas
    task_success_rate: float
    data_extraction_accuracy: float
    intent_f1_score: float
    latency_p95_ms: float
    
    # Targets
    meets_task_success_target: bool
    meets_extraction_target: bool
    meets_intent_f1_target: bool
    meets_latency_target: bool
    
    # Detalles
    scenario_results: list[ScenarioResult] = field(default_factory=list)
    latency_result: Optional[LatencyResult] = None
    intent_metrics: Optional[dict] = None
    extraction_metrics: Optional[dict] = None
    
    def overall_pass(self) -> bool:
        """Verifica si pasa todos los targets"""
        return all([
            self.meets_task_success_target,
            self.meets_extraction_target,
            self.meets_intent_f1_target,
            self.meets_latency_target
        ])


class AgentEvaluator:
    """
    Evaluador Principal del Agente Mia Gente
    
    Ejecuta evaluación completa contra el dataset de 50 escenarios,
    midiendo todas las métricas definidas.
    """
    
    def __init__(
        self,
        agent_callable: callable,
        model_name: str = "gemini-2.5-flash",
        dataset_path: Optional[Path] = None
    ):
        """
        Args:
            agent_callable: Función que recibe mensaje y retorna respuesta
                           Signature: async def agent(message: str, session: dict) -> str
            model_name: Nombre del modelo para el reporte
            dataset_path: Ruta al dataset de escenarios
        """
        self.agent = agent_callable
        self.model_name = model_name
        self.dataset_path = dataset_path or DATASETS_DIR / "test_scenarios.json"
        
        # Inicializar métricas
        self.task_completion_metric = TaskCompletionMetric()
        self.data_extraction_metric = DataExtractionMetric()
        self.intent_classification_metric = IntentClassificationMetric()
        self.latency_metric = LatencyMetric(target_ms=eval_config.latency_target_seconds * 1000)
        
        # Cargar dataset
        self.scenarios = self._load_scenarios()
    
    def _load_scenarios(self) -> list[dict]:
        """Carga el dataset de escenarios"""
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("scenarios", [])
    
    async def evaluate_scenario(self, scenario: dict) -> ScenarioResult:
        """
        Evalúa un escenario individual
        
        Args:
            scenario: Diccionario con el escenario de prueba
            
        Returns:
            ScenarioResult con los resultados
        """
        scenario_id = scenario.get("id", "unknown")
        category = scenario.get("category", "unknown")
        expected = scenario.get("expected", {})
        conversation = scenario.get("conversation", [])
        context = scenario.get("context", {})
        
        try:
            # Preparar sesión simulada
            session = self._create_session(context)
            
            # Ejecutar conversación con medición de latencia
            with self.latency_metric.start_measurement(scenario_id) as timer:
                # Procesar cada mensaje de la conversación
                agent_response = ""
                for msg in conversation:
                    if msg["role"] == "user":
                        timer.mark_llm_start()
                        agent_response = await self.agent(msg["content"], session)
                        timer.mark_llm_end()
                    elif msg["role"] == "assistant":
                        # Mensaje previo del assistant, actualizar sesión
                        session["messages"].append({
                            "role": "assistant",
                            "content": msg["content"]
                        })
            
            # Evaluar task completion
            task_result = self.task_completion_metric.evaluate(
                response=agent_response,
                expected=expected
            )
            
            # Evaluar data extraction
            extraction_result = self.data_extraction_metric.evaluate(
                agent_response=agent_response,
                expected=expected,
                session_data=session
            )
            
            # Evaluar intent classification
            user_message = conversation[-1]["content"] if conversation else ""
            intent_result = self.intent_classification_metric.evaluate(
                user_message=user_message,
                agent_response=agent_response,
                expected_intent=expected.get("intent", "unknown")
            )
            
            # Determinar éxito general
            success = task_result.success and extraction_result.accuracy >= 0.8
            
            return ScenarioResult(
                scenario_id=scenario_id,
                category=category,
                success=success,
                task_completion=task_result,
                data_extraction=extraction_result,
                intent_classification=intent_result,
                latency_ms=self.latency_metric.measurements[-1].total_time_ms if self.latency_metric.measurements else 0,
                agent_response=agent_response
            )
            
        except Exception as e:
            return ScenarioResult(
                scenario_id=scenario_id,
                category=category,
                success=False,
                error=str(e)
            )
    
    def _create_session(self, context: dict) -> dict:
        """Crea una sesión simulada para el agente"""
        session = {
            "messages": [],
            "emission_data": {},
            "awaiting_confirmation": context.get("awaiting_confirmation", False),
            "emission_active": context.get("emission_active", False),
        }
        return session
    
    async def run_evaluation(self, max_scenarios: Optional[int] = None) -> EvaluationReport:
        """
        Ejecuta la evaluación completa
        
        Args:
            max_scenarios: Límite de escenarios a evaluar (None = todos)
            
        Returns:
            EvaluationReport con todos los resultados
        """
        scenarios_to_run = self.scenarios[:max_scenarios] if max_scenarios else self.scenarios
        
        print(f"🚀 Iniciando evaluación de {len(scenarios_to_run)} escenarios...")
        print(f"📊 Modelo: {self.model_name}")
        print("-" * 50)
        
        results: list[ScenarioResult] = []
        
        for i, scenario in enumerate(scenarios_to_run, 1):
            scenario_id = scenario.get("id", f"scenario_{i}")
            print(f"[{i}/{len(scenarios_to_run)}] Evaluando {scenario_id}...", end=" ")
            
            result = await self.evaluate_scenario(scenario)
            results.append(result)
            
            status = "✅" if result.success else "❌"
            print(f"{status}")
        
        print("-" * 50)
        
        # Calcular métricas agregadas
        task_results = [r.task_completion for r in results if r.task_completion]
        extraction_results = [r.data_extraction for r in results if r.data_extraction]
        intent_results = [r.intent_classification for r in results if r.intent_classification]
        
        task_success_rate = calculate_task_success_rate(task_results)
        extraction_metrics = calculate_extraction_accuracy(extraction_results)
        intent_metrics = calculate_intent_f1(intent_results)
        latency_result = self.latency_metric.evaluate()
        
        # Crear reporte
        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            model_name=self.model_name,
            total_scenarios=len(results),
            passed_scenarios=sum(1 for r in results if r.success),
            failed_scenarios=sum(1 for r in results if not r.success),
            
            task_success_rate=task_success_rate,
            data_extraction_accuracy=extraction_metrics.get("overall", 0.0),
            intent_f1_score=intent_metrics.get("f1_macro", 0.0),
            latency_p95_ms=latency_result.p95_ms,
            
            meets_task_success_target=task_success_rate >= eval_config.task_success_rate_target,
            meets_extraction_target=extraction_metrics.get("overall", 0.0) >= eval_config.data_extraction_accuracy_target,
            meets_intent_f1_target=intent_metrics.get("f1_macro", 0.0) >= eval_config.intent_classification_f1_target,
            meets_latency_target=latency_result.within_target,
            
            scenario_results=results,
            latency_result=latency_result,
            intent_metrics=intent_metrics,
            extraction_metrics=extraction_metrics
        )
        
        self._print_summary(report)
        
        return report
    
    def _print_summary(self, report: EvaluationReport):
        """Imprime resumen del reporte"""
        print("\n" + "=" * 60)
        print("               RESUMEN DE EVALUACIÓN")
        print("=" * 60)
        print(f"Modelo: {report.model_name}")
        print(f"Fecha: {report.timestamp}")
        print("-" * 60)
        print(f"Total escenarios: {report.total_scenarios}")
        print(f"Pasados: {report.passed_scenarios} ({report.passed_scenarios/report.total_scenarios*100:.1f}%)")
        print(f"Fallidos: {report.failed_scenarios}")
        print("-" * 60)
        
        def status(meets: bool) -> str:
            return "✅ PASS" if meets else "❌ FAIL"
        
        print(f"Task Success Rate:    {report.task_success_rate*100:.1f}% (target: {eval_config.task_success_rate_target*100:.0f}%) {status(report.meets_task_success_target)}")
        print(f"Data Extraction:      {report.data_extraction_accuracy*100:.1f}% (target: {eval_config.data_extraction_accuracy_target*100:.0f}%) {status(report.meets_extraction_target)}")
        print(f"Intent F1:            {report.intent_f1_score:.3f} (target: {eval_config.intent_classification_f1_target:.2f}) {status(report.meets_intent_f1_target)}")
        print(f"Latency P95:          {report.latency_p95_ms:.0f}ms (target: {eval_config.latency_target_seconds*1000:.0f}ms) {status(report.meets_latency_target)}")
        print("-" * 60)
        
        overall = "✅ TODOS LOS TARGETS CUMPLIDOS" if report.overall_pass() else "❌ ALGUNOS TARGETS NO CUMPLIDOS"
        print(f"Resultado General: {overall}")
        print("=" * 60)


async def run_quick_evaluation(agent_callable: callable, num_scenarios: int = 10) -> EvaluationReport:
    """
    Ejecuta una evaluación rápida con un subconjunto de escenarios
    
    Args:
        agent_callable: Función del agente
        num_scenarios: Número de escenarios a evaluar
        
    Returns:
        EvaluationReport
    """
    evaluator = AgentEvaluator(agent_callable)
    return await evaluator.run_evaluation(max_scenarios=num_scenarios)
