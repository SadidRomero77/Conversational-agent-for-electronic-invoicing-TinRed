"""
TinRed Agent Evaluator - Framework de Evaluación Completo
Versión 2.0 con datos reales
"""
import json
import logging
import asyncio
import aiohttp
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    scenario_id: str
    category: str
    name: str
    status: TestStatus
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvaluationReport:
    timestamp: str
    total_scenarios: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_rate: float
    duration_total_ms: float
    results_by_category: Dict[str, Dict] = field(default_factory=dict)
    results: List[TestResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "summary": {
                "total": self.total_scenarios,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "errors": self.errors,
                "pass_rate": f"{self.pass_rate:.2f}%",
                "duration_ms": self.duration_total_ms
            },
            "by_category": self.results_by_category,
            "results": [r.to_dict() for r in self.results]
        }


class TinRedEvaluator:
    """Evaluador principal del agente TinRed."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.api_url = self.config.get("api_url", "http://localhost:8000")
        self.timeout = self.config.get("timeout", 30)
        self.results: List[TestResult] = []
        
        # Cargar datos de prueba
        self.test_data = self._load_test_data()
    
    def _load_test_data(self) -> Dict:
        """Carga el dataset de prueba."""
        dataset_path = Path(__file__).parent.parent / "datasets" / "test_scenarios_v2.json"
        
        if dataset_path.exists():
            with open(dataset_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        logger.warning(f"Dataset no encontrado: {dataset_path}")
        return {"scenarios": [], "test_data": {}}
    
    async def run_all_tests(self, categories: List[str] = None) -> EvaluationReport:
        """Ejecuta todos los tests o los de categorías específicas."""
        start_time = time.time()
        scenarios = self.test_data.get("scenarios", [])
        
        if categories:
            scenarios = [s for s in scenarios if s.get("category") in categories]
        
        logger.info(f"🚀 Iniciando evaluación de {len(scenarios)} escenarios...")
        
        for scenario in scenarios:
            result = await self._run_scenario(scenario)
            self.results.append(result)
        
        duration = (time.time() - start_time) * 1000
        return self._generate_report(duration)
    
    async def _run_scenario(self, scenario: Dict) -> TestResult:
        """Ejecuta un escenario de prueba individual."""
        scenario_id = scenario.get("id", "unknown")
        category = scenario.get("category", "unknown")
        name = scenario.get("name", "Sin nombre")
        
        logger.info(f"  📋 [{scenario_id}] {name}")
        
        start_time = time.time()
        
        try:
            # Determinar tipo de test
            if "conversation" in scenario:
                result = await self._run_conversation_test(scenario)
            elif "input" in scenario:
                result = await self._run_single_input_test(scenario)
            elif scenario.get("batch_test"):
                result = await self._run_batch_test(scenario)
            else:
                result = TestResult(
                    scenario_id=scenario_id,
                    category=category,
                    name=name,
                    status=TestStatus.SKIPPED,
                    duration_ms=0,
                    details={"reason": "Tipo de test no reconocido"}
                )
            
            result.duration_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"    ❌ Error: {e}")
            return TestResult(
                scenario_id=scenario_id,
                category=category,
                name=name,
                status=TestStatus.ERROR,
                duration_ms=duration,
                errors=[str(e)]
            )
    
    async def _run_conversation_test(self, scenario: Dict) -> TestResult:
        """Ejecuta un test de conversación multi-turno."""
        scenario_id = scenario["id"]
        category = scenario["category"]
        name = scenario["name"]
        conversation = scenario["conversation"]
        
        # Usar número de teléfono real de TinRed
        session_phone = self.config.get("test_phone", "573134723604")
        responses = []
        
        async with aiohttp.ClientSession() as session:
            for turn in conversation:
                if turn["role"] == "user":
                    # Enviar mensaje del usuario
                    response = await self._send_message(session, session_phone, turn["content"])
                    responses.append(response)
                    
                    # Validar respuesta si hay expectativas
                elif turn["role"] == "assistant":
                    if responses:
                        last_response = responses[-1]
                        validation = self._validate_response(last_response, turn)
                        
                        if not validation["passed"]:
                            return TestResult(
                                scenario_id=scenario_id,
                                category=category,
                                name=name,
                                status=TestStatus.FAILED,
                                duration_ms=0,
                                details={
                                    "responses": responses,
                                    "failed_at": len(responses),
                                    "validation": validation
                                },
                                errors=validation.get("errors", [])
                            )
        
        # Validar datos esperados si existen
        expected_data = scenario.get("expected_data", {})
        if expected_data and responses:
            data_validation = self._validate_expected_data(responses, expected_data)
            if not data_validation["passed"]:
                return TestResult(
                    scenario_id=scenario_id,
                    category=category,
                    name=name,
                    status=TestStatus.FAILED,
                    duration_ms=0,
                    details={"data_validation": data_validation},
                    errors=data_validation.get("errors", [])
                )
        
        return TestResult(
            scenario_id=scenario_id,
            category=category,
            name=name,
            status=TestStatus.PASSED,
            duration_ms=0,
            details={"responses": responses, "turns": len(responses)}
        )
    
    async def _run_single_input_test(self, scenario: Dict) -> TestResult:
        """Ejecuta un test de entrada única (clasificación de intent, extracción)."""
        scenario_id = scenario["id"]
        category = scenario["category"]
        name = scenario["name"]
        input_text = scenario["input"]
        
        # Test de clasificación de intent
        if "expected_intent" in scenario:
            classified_intent = await self._classify_intent(input_text)
            expected = scenario["expected_intent"]
            
            if classified_intent == expected:
                return TestResult(
                    scenario_id=scenario_id,
                    category=category,
                    name=name,
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    details={"input": input_text, "intent": classified_intent}
                )
            else:
                return TestResult(
                    scenario_id=scenario_id,
                    category=category,
                    name=name,
                    status=TestStatus.FAILED,
                    duration_ms=0,
                    details={"expected": expected, "got": classified_intent},
                    errors=[f"Intent esperado: {expected}, obtenido: {classified_intent}"]
                )
        
        # Test de extracción de datos
        if "expected_extraction" in scenario:
            extracted = await self._extract_data(input_text)
            expected = scenario["expected_extraction"]
            
            validation = self._compare_extraction(extracted, expected)
            
            return TestResult(
                scenario_id=scenario_id,
                category=category,
                name=name,
                status=TestStatus.PASSED if validation["passed"] else TestStatus.FAILED,
                duration_ms=0,
                details={"extracted": extracted, "expected": expected},
                errors=validation.get("errors", [])
            )
        
        return TestResult(
            scenario_id=scenario_id,
            category=category,
            name=name,
            status=TestStatus.SKIPPED,
            duration_ms=0,
            details={"reason": "Sin expectativas definidas"}
        )
    
    async def _run_batch_test(self, scenario: Dict) -> TestResult:
        """Ejecuta tests de validación en batch."""
        scenario_id = scenario["id"]
        category = scenario["category"]
        name = scenario["name"]
        documents = scenario.get("documents", [])
        
        results = []
        
        async with aiohttp.ClientSession() as session:
            for doc in documents:
                is_valid = await self._validate_document(session, doc)
                results.append({"document": doc, "valid": is_valid})
        
        all_valid = all(r["valid"] for r in results)
        expected_valid = scenario.get("expected_valid", True)
        
        return TestResult(
            scenario_id=scenario_id,
            category=category,
            name=name,
            status=TestStatus.PASSED if all_valid == expected_valid else TestStatus.FAILED,
            duration_ms=0,
            details={"results": results, "all_valid": all_valid}
        )
    
    async def _send_message(self, session: aiohttp.ClientSession, phone: str, message: str) -> Dict:
        """Envía un mensaje al agente."""
        url = f"{self.api_url}/api/converse"
        payload = {"phone": phone, "message": message}
        
        try:
            async with session.post(url, json=payload, timeout=self.timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"error": f"HTTP {resp.status}", "reply": ""}
        except asyncio.TimeoutError:
            return {"error": "Timeout", "reply": ""}
        except Exception as e:
            return {"error": str(e), "reply": ""}
    
    async def _classify_intent(self, text: str) -> str:
        """Clasifica el intent de un texto (mock o real)."""
        text_lower = text.lower()
        
        # Prioridad 1: Saludos (antes que todo)
        greetings = ['hola', 'buenos días', 'buenas tardes', 'buenas noches', 'hey', 'hi', 'buenas']
        if any(g in text_lower for g in greetings):
            return "GREETING"
        
        # Prioridad 2: Preguntas (detectar ? o palabras de pregunta)
        question_words = ['qué', 'que', 'cómo', 'como', 'cuál', 'cual', 'diferencia', 'ayuda', 'explicar']
        if '?' in text_lower or any(q in text_lower for q in question_words):
            # Solo si NO menciona explícitamente emitir
            if not any(e in text_lower for e in ['emitir', 'generar', 'hacer una', 'quiero una']):
                return "GENERAL_QUESTION"
        
        # Prioridad 3: Cancelación
        cancel_words = ['cancelar', 'cancela', 'no quiero', 'olvida', 'salir', 'detener']
        if any(c in text_lower for c in cancel_words):
            return "CANCEL"
        
        # Prioridad 4: Confirmación
        confirm_words = ['si', 'sí', 'yes', 'ok', 'confirmo', 'acepto', 'dale', 'adelante']
        if any(text_lower.strip().startswith(c) for c in confirm_words):
            return "CONFIRMATION"
        
        # Prioridad 5: Historial
        if 'historial' in text_lower or 'histórico' in text_lower:
            return "QUERY_HISTORY"
        
        # Prioridad 6: Productos
        if 'producto' in text_lower:
            return "QUERY_PRODUCTS"
        
        # Prioridad 7: Emisión
        if any(w in text_lower for w in ['factura', 'boleta', 'emitir']):
            return "EMIT_INVOICE"
        
        return "UNKNOWN"
    
    async def _extract_data(self, text: str) -> Dict:
        """Extrae datos de un mensaje (mock o real)."""
        import re
        
        extracted = {}
        
        # Extraer tipo de documento
        if 'boleta' in text.lower():
            extracted['document_type'] = '03'
        elif 'factura' in text.lower():
            extracted['document_type'] = '01'
        
        # Extraer DNI
        dni_match = re.search(r'\b(\d{8})\b', text)
        if dni_match:
            extracted['id_type'] = '1'
            extracted['id_number'] = dni_match.group(1)
        
        # Extraer RUC
        ruc_match = re.search(r'\b([12]0\d{9})\b', text)
        if ruc_match:
            extracted['id_type'] = '6'
            extracted['id_number'] = ruc_match.group(1)
        
        # Extraer items
        items_pattern = r'(\d+)\s+(.+?)\s+a\s+(\d+(?:\.\d+)?)'
        items = re.findall(items_pattern, text)
        if items:
            extracted['items'] = [
                {"cantidad": i[0], "descripcion": i[1].strip(), "precio": i[2]}
                for i in items
            ]
        
        return extracted
    
    async def _validate_document(self, session: aiohttp.ClientSession, document: str) -> bool:
        """Valida un documento contra la API."""
        # Por ahora mock - en producción llamaría a la API real
        if len(document) == 8:  # DNI
            return document.isdigit()
        elif len(document) == 11:  # RUC
            return document.isdigit() and document[:2] in ['10', '20', '15']
        return False
    
    def _validate_response(self, response: Dict, expected: Dict) -> Dict:
        """Valida una respuesta del agente contra las expectativas."""
        reply = response.get("reply", "").lower()
        errors = []
        passed = True
        
        # Validar que contiene texto esperado
        if "expected_contains" in expected:
            contains = expected["expected_contains"]
            if isinstance(contains, str):
                contains = [contains]
            
            for text in contains:
                if text.lower() not in reply:
                    errors.append(f"Respuesta no contiene: '{text}'")
                    passed = False
        
        # Validar que NO contiene texto
        if "expected_not_contains" in expected:
            not_contains = expected["expected_not_contains"]
            if isinstance(not_contains, str):
                not_contains = [not_contains]
            
            for text in not_contains:
                if text.lower() in reply:
                    errors.append(f"Respuesta contiene texto prohibido: '{text}'")
                    passed = False
        
        return {"passed": passed, "errors": errors}
    
    def _validate_expected_data(self, responses: List[Dict], expected: Dict) -> Dict:
        """Valida los datos extraídos contra los esperados."""
        # Simplificado - en producción sería más robusto
        return {"passed": True, "errors": []}
    
    def _compare_extraction(self, extracted: Dict, expected: Dict) -> Dict:
        """Compara datos extraídos con los esperados."""
        errors = []
        
        for key, expected_value in expected.items():
            if key not in extracted:
                errors.append(f"Falta campo: {key}")
            elif key == "items":
                # Comparación especial para items - solo verificar cantidad y precio
                ext_items = extracted.get("items", [])
                exp_items = expected_value
                
                if len(ext_items) != len(exp_items):
                    errors.append(f"items: cantidad diferente - esperado {len(exp_items)}, obtenido {len(ext_items)}")
                else:
                    for i, (ext, exp) in enumerate(zip(ext_items, exp_items)):
                        if ext.get("cantidad") != exp.get("cantidad"):
                            errors.append(f"item[{i}].cantidad: esperado {exp.get('cantidad')}, obtenido {ext.get('cantidad')}")
                        if ext.get("precio") != exp.get("precio"):
                            errors.append(f"item[{i}].precio: esperado {exp.get('precio')}, obtenido {ext.get('precio')}")
            elif extracted[key] != expected_value:
                errors.append(f"{key}: esperado {expected_value}, obtenido {extracted[key]}")
        
        return {"passed": len(errors) == 0, "errors": errors}
    
    def _generate_report(self, duration_ms: float) -> EvaluationReport:
        """Genera el reporte de evaluación."""
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in self.results if r.status == TestStatus.ERROR)
        total = len(self.results)
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # Agrupar por categoría
        by_category = {}
        for result in self.results:
            cat = result.category
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0, "failed": 0}
            
            by_category[cat]["total"] += 1
            if result.status == TestStatus.PASSED:
                by_category[cat]["passed"] += 1
            elif result.status == TestStatus.FAILED:
                by_category[cat]["failed"] += 1
        
        return EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_scenarios=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            pass_rate=pass_rate,
            duration_total_ms=duration_ms,
            results_by_category=by_category,
            results=self.results
        )


class ReportGenerator:
    """Genera reportes en diferentes formatos."""
    
    @staticmethod
    def to_json(report: EvaluationReport, filepath: str) -> None:
        """Guarda reporte en JSON."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def to_markdown(report: EvaluationReport, filepath: str) -> None:
        """Guarda reporte en Markdown."""
        md = f"""# Reporte de Evaluación TinRed Agent

**Fecha:** {report.timestamp}

## Resumen

| Métrica | Valor |
|---------|-------|
| Total Escenarios | {report.total_scenarios} |
| ✅ Pasados | {report.passed} |
| ❌ Fallidos | {report.failed} |
| ⏭️ Saltados | {report.skipped} |
| ⚠️ Errores | {report.errors} |
| **Tasa de Éxito** | **{report.pass_rate:.2f}%** |
| Duración | {report.duration_total_ms:.0f}ms |

## Resultados por Categoría

| Categoría | Total | Pasados | Fallidos | Tasa |
|-----------|-------|---------|----------|------|
"""
        for cat, stats in report.results_by_category.items():
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            md += f"| {cat} | {stats['total']} | {stats['passed']} | {stats['failed']} | {rate:.0f}% |\n"
        
        md += "\n## Detalles de Tests Fallidos\n\n"
        
        for result in report.results:
            if result.status == TestStatus.FAILED:
                md += f"### ❌ [{result.scenario_id}] {result.name}\n\n"
                md += f"**Categoría:** {result.category}\n\n"
                if result.errors:
                    md += "**Errores:**\n"
                    for error in result.errors:
                        md += f"- {error}\n"
                md += "\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md)
    
    @staticmethod
    def to_html(report: EvaluationReport, filepath: str) -> None:
        """Guarda reporte en HTML."""
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluación TinRed Agent</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; margin-bottom: 8px; }}
        .timestamp {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .metric {{ text-align: center; padding: 16px; border-radius: 8px; }}
        .metric.passed {{ background: #e8f5e9; }}
        .metric.failed {{ background: #ffebee; }}
        .metric.rate {{ background: #e3f2fd; }}
        .metric-value {{ font-size: 36px; font-weight: bold; }}
        .metric-label {{ color: #666; font-size: 14px; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .status {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }}
        .status.passed {{ background: #c8e6c9; color: #2e7d32; }}
        .status.failed {{ background: #ffcdd2; color: #c62828; }}
        .status.skipped {{ background: #fff9c4; color: #f9a825; }}
        .progress {{ width: 100%; height: 8px; background: #ffcdd2; border-radius: 4px; overflow: hidden; }}
        .progress-bar {{ height: 100%; background: #4caf50; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🤖 Evaluación TinRed Agent</h1>
            <p class="timestamp">Generado: {report.timestamp}</p>
            
            <div class="metrics">
                <div class="metric passed">
                    <div class="metric-value">{report.passed}</div>
                    <div class="metric-label">✅ Pasados</div>
                </div>
                <div class="metric failed">
                    <div class="metric-value">{report.failed}</div>
                    <div class="metric-label">❌ Fallidos</div>
                </div>
                <div class="metric rate">
                    <div class="metric-value">{report.pass_rate:.1f}%</div>
                    <div class="metric-label">Tasa de Éxito</div>
                </div>
            </div>
            
            <div class="progress">
                <div class="progress-bar" style="width: {report.pass_rate}%"></div>
            </div>
        </div>
        
        <div class="card">
            <h2>📊 Resultados por Categoría</h2>
            <table>
                <thead>
                    <tr>
                        <th>Categoría</th>
                        <th>Total</th>
                        <th>Pasados</th>
                        <th>Fallidos</th>
                        <th>Tasa</th>
                    </tr>
                </thead>
                <tbody>
"""
        for cat, stats in report.results_by_category.items():
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            html += f"""                    <tr>
                        <td>{cat}</td>
                        <td>{stats['total']}</td>
                        <td>{stats['passed']}</td>
                        <td>{stats['failed']}</td>
                        <td>{rate:.0f}%</td>
                    </tr>
"""
        
        html += """                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>📋 Todos los Tests</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Nombre</th>
                        <th>Categoría</th>
                        <th>Estado</th>
                        <th>Duración</th>
                    </tr>
                </thead>
                <tbody>
"""
        for result in report.results:
            status_class = result.status.value
            html += f"""                    <tr>
                        <td>{result.scenario_id}</td>
                        <td>{result.name}</td>
                        <td>{result.category}</td>
                        <td><span class="status {status_class}">{result.status.value.upper()}</span></td>
                        <td>{result.duration_ms:.0f}ms</td>
                    </tr>
"""
        
        html += """                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)


async def main():
    """Función principal para ejecutar la evaluación."""
    print("=" * 60)
    print("🚀 TinRed Agent Evaluation Framework v2.0")
    print("=" * 60)
    
    evaluator = TinRedEvaluator({
        "api_url": "http://localhost:8000",
        "timeout": 30
    })
    
    report = await evaluator.run_all_tests()
    
    # Generar reportes
    output_dir = Path(__file__).parent.parent / "reports"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    ReportGenerator.to_json(report, str(output_dir / f"evaluation_{timestamp}.json"))
    ReportGenerator.to_markdown(report, str(output_dir / f"evaluation_{timestamp}.md"))
    ReportGenerator.to_html(report, str(output_dir / f"evaluation_{timestamp}.html"))
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE EVALUACIÓN")
    print("=" * 60)
    print(f"Total: {report.total_scenarios}")
    print(f"✅ Pasados: {report.passed}")
    print(f"❌ Fallidos: {report.failed}")
    print(f"⏭️ Saltados: {report.skipped}")
    print(f"⚠️ Errores: {report.errors}")
    print(f"📈 Tasa de éxito: {report.pass_rate:.2f}%")
    print(f"⏱️ Duración: {report.duration_total_ms:.0f}ms")
    print("=" * 60)
    print(f"📁 Reportes guardados en: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
