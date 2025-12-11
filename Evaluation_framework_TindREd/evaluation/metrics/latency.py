"""
Métrica de Latencia
Mide tiempos de respuesta del agente
"""
from dataclasses import dataclass, field
from typing import Optional
import time
import statistics

@dataclass
class LatencyMeasurement:
    """Una medición individual de latencia"""
    scenario_id: str
    total_time_ms: float
    llm_time_ms: float = 0.0
    api_time_ms: float = 0.0
    processing_time_ms: float = 0.0
    
@dataclass
class LatencyResult:
    """Resultado agregado de latencia"""
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    within_target: bool
    target_ms: float
    measurements: list[LatencyMeasurement] = field(default_factory=list)

class LatencyMetric:
    """
    Métrica de Latencia
    
    Mide el tiempo de respuesta end-to-end del agente.
    Target: < 3 segundos (3000ms) para respuesta completa.
    """
    
    name: str = "latency"
    description: str = "Mide tiempo de respuesta del agente"
    
    def __init__(self, target_ms: float = 3000.0):
        self.target_ms = target_ms
        self.measurements: list[LatencyMeasurement] = []
    
    def start_measurement(self, scenario_id: str) -> "LatencyTimer":
        """Inicia una medición de latencia"""
        return LatencyTimer(scenario_id, self)
    
    def add_measurement(self, measurement: LatencyMeasurement):
        """Agrega una medición"""
        self.measurements.append(measurement)
    
    def evaluate(self) -> LatencyResult:
        """
        Calcula métricas agregadas de latencia
        """
        if not self.measurements:
            return LatencyResult(
                mean_ms=0.0,
                median_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                min_ms=0.0,
                max_ms=0.0,
                within_target=True,
                target_ms=self.target_ms
            )
        
        times = [m.total_time_ms for m in self.measurements]
        times_sorted = sorted(times)
        
        mean_ms = statistics.mean(times)
        median_ms = statistics.median(times)
        
        # Percentiles
        p95_idx = int(len(times_sorted) * 0.95)
        p99_idx = int(len(times_sorted) * 0.99)
        
        p95_ms = times_sorted[min(p95_idx, len(times_sorted) - 1)]
        p99_ms = times_sorted[min(p99_idx, len(times_sorted) - 1)]
        
        min_ms = min(times)
        max_ms = max(times)
        
        # Verificar si p95 está dentro del target
        within_target = p95_ms <= self.target_ms
        
        return LatencyResult(
            mean_ms=mean_ms,
            median_ms=median_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            min_ms=min_ms,
            max_ms=max_ms,
            within_target=within_target,
            target_ms=self.target_ms,
            measurements=self.measurements
        )
    
    def reset(self):
        """Reinicia las mediciones"""
        self.measurements = []


class LatencyTimer:
    """
    Context manager para medir latencia
    
    Uso:
        with latency_metric.start_measurement("EMI-001") as timer:
            timer.mark_llm_start()
            # llamada al LLM
            timer.mark_llm_end()
            
            timer.mark_api_start()
            # llamada al API
            timer.mark_api_end()
    """
    
    def __init__(self, scenario_id: str, metric: LatencyMetric):
        self.scenario_id = scenario_id
        self.metric = metric
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        
        self.llm_start: float = 0.0
        self.llm_end: float = 0.0
        self.api_start: float = 0.0
        self.api_end: float = 0.0
    
    def __enter__(self) -> "LatencyTimer":
        self.start_time = time.perf_counter() * 1000  # ms
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter() * 1000  # ms
        
        total_time = self.end_time - self.start_time
        llm_time = (self.llm_end - self.llm_start) if self.llm_end > 0 else 0.0
        api_time = (self.api_end - self.api_start) if self.api_end > 0 else 0.0
        processing_time = total_time - llm_time - api_time
        
        measurement = LatencyMeasurement(
            scenario_id=self.scenario_id,
            total_time_ms=total_time,
            llm_time_ms=llm_time,
            api_time_ms=api_time,
            processing_time_ms=max(0, processing_time)
        )
        
        self.metric.add_measurement(measurement)
        return False
    
    def mark_llm_start(self):
        """Marca inicio de llamada al LLM"""
        self.llm_start = time.perf_counter() * 1000
    
    def mark_llm_end(self):
        """Marca fin de llamada al LLM"""
        self.llm_end = time.perf_counter() * 1000
    
    def mark_api_start(self):
        """Marca inicio de llamada al API"""
        self.api_start = time.perf_counter() * 1000
    
    def mark_api_end(self):
        """Marca fin de llamada al API"""
        self.api_end = time.perf_counter() * 1000


def format_latency_report(result: LatencyResult) -> str:
    """
    Formatea un reporte de latencia legible
    """
    status = "✅ PASS" if result.within_target else "❌ FAIL"
    
    report = f"""
╔══════════════════════════════════════════╗
║          REPORTE DE LATENCIA             ║
╠══════════════════════════════════════════╣
║ Target: {result.target_ms:.0f}ms                          
║ Status: {status}                         
╠══════════════════════════════════════════╣
║ Mean:   {result.mean_ms:>8.1f} ms                    
║ Median: {result.median_ms:>8.1f} ms                    
║ P95:    {result.p95_ms:>8.1f} ms                    
║ P99:    {result.p99_ms:>8.1f} ms                    
║ Min:    {result.min_ms:>8.1f} ms                    
║ Max:    {result.max_ms:>8.1f} ms                    
╠══════════════════════════════════════════╣
║ Samples: {len(result.measurements)}                              
╚══════════════════════════════════════════╝
"""
    return report


def analyze_latency_breakdown(result: LatencyResult) -> dict:
    """
    Analiza el breakdown de latencia por componente
    """
    if not result.measurements:
        return {}
    
    llm_times = [m.llm_time_ms for m in result.measurements if m.llm_time_ms > 0]
    api_times = [m.api_time_ms for m in result.measurements if m.api_time_ms > 0]
    proc_times = [m.processing_time_ms for m in result.measurements]
    
    breakdown = {
        "llm": {
            "mean_ms": statistics.mean(llm_times) if llm_times else 0,
            "percentage": (sum(llm_times) / sum(m.total_time_ms for m in result.measurements) * 100) if llm_times else 0
        },
        "api": {
            "mean_ms": statistics.mean(api_times) if api_times else 0,
            "percentage": (sum(api_times) / sum(m.total_time_ms for m in result.measurements) * 100) if api_times else 0
        },
        "processing": {
            "mean_ms": statistics.mean(proc_times) if proc_times else 0,
            "percentage": (sum(proc_times) / sum(m.total_time_ms for m in result.measurements) * 100) if proc_times else 0
        }
    }
    
    return breakdown
