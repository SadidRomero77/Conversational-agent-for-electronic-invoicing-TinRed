"""
Generador de Reportes de Evaluación
Genera reportes en múltiples formatos (JSON, HTML, Markdown)
"""
import sys
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import html

# Asegurar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import REPORTS_DIR

# Template HTML para el reporte - usando string.Template ($variable)
from string import Template

HTML_TEMPLATE_STR = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Evaluación - Mia Gente</title>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --danger: #dc2626;
            --warning: #ca8a04;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--border);
        }
        h1 { font-size: 2rem; color: var(--primary); margin-bottom: 0.5rem; }
        .subtitle { color: var(--text-secondary); }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid var(--border);
        }
        .card h3 {
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }
        .card .value { font-size: 2rem; font-weight: 700; }
        .card .target { font-size: 0.875rem; color: var(--text-secondary); }
        .status-pass { color: var(--success); }
        .status-fail { color: var(--danger); }
        .metric-bar {
            height: 8px;
            background: var(--border);
            border-radius: 4px;
            margin-top: 0.5rem;
            overflow: hidden;
        }
        .metric-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .metric-bar-fill.success { background: var(--success); }
        .metric-bar-fill.warning { background: var(--warning); }
        .metric-bar-fill.danger { background: var(--danger); }
        section { margin-bottom: 2rem; }
        section h2 {
            font-size: 1.25rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        th, td {
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            background: var(--bg);
            font-weight: 600;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        tr:hover { background: var(--bg); }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-success { background: #dcfce7; color: #166534; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .overall-result {
            text-align: center;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
        }
        .overall-result.pass {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            border: 2px solid var(--success);
        }
        .overall-result.fail {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            border: 2px solid var(--danger);
        }
        .overall-result h2 { border: none; font-size: 1.5rem; }
        footer {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🧪 Reporte de Evaluación</h1>
            <p class="subtitle">Mia Gente - Agente de Facturación TinRed</p>
        </header>
        
        <div class="overall-result {overall_class}">
            <h2>{overall_icon} {overall_text}</h2>
            <p>Modelo: {model_name} | Fecha: {timestamp}</p>
        </div>
        
        <div class="summary-grid">
            <div class="card">
                <h3>Task Success Rate</h3>
                <div class="value {task_class}">{task_rate}%</div>
                <div class="target">Target: {task_target}%</div>
                <div class="metric-bar">
                    <div class="metric-bar-fill {task_bar_class}" style="width: {task_rate}%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>Data Extraction</h3>
                <div class="value {extraction_class}">{extraction_rate}%</div>
                <div class="target">Target: {extraction_target}%</div>
                <div class="metric-bar">
                    <div class="metric-bar-fill {extraction_bar_class}" style="width: {extraction_rate}%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>Intent F1 Score</h3>
                <div class="value {intent_class}">{intent_f1}</div>
                <div class="target">Target: {intent_target}</div>
                <div class="metric-bar">
                    <div class="metric-bar-fill {intent_bar_class}" style="width: {intent_percent}%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>Latency P95</h3>
                <div class="value {latency_class}">{latency_p95}ms</div>
                <div class="target">Target: {latency_target}ms</div>
                <div class="metric-bar">
                    <div class="metric-bar-fill {latency_bar_class}" style="width: {latency_percent}%"></div>
                </div>
            </div>
        </div>
        
        <section>
            <h2>📊 Resumen de Escenarios</h2>
            <div class="summary-grid">
                <div class="card">
                    <h3>Total</h3>
                    <div class="value">{total_scenarios}</div>
                </div>
                <div class="card">
                    <h3>Pasados</h3>
                    <div class="value status-pass">{passed_scenarios}</div>
                </div>
                <div class="card">
                    <h3>Fallidos</h3>
                    <div class="value status-fail">{failed_scenarios}</div>
                </div>
            </div>
        </section>
        
        <section>
            <h2>📋 Detalle por Escenario</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Categoría</th>
                        <th>Estado</th>
                        <th>Task</th>
                        <th>Extraction</th>
                        <th>Latencia</th>
                    </tr>
                </thead>
                <tbody>
                    {scenario_rows}
                </tbody>
            </table>
        </section>
        
        <footer>
            <p>Generado por Framework de Evaluación Mia Gente v1.0</p>
            <p>Basado en AgentBench (ICLR 2024) y RAGAS</p>
        </footer>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """
    Generador de Reportes de Evaluación
    
    Genera reportes en múltiples formatos:
    - JSON: Para procesamiento programático
    - HTML: Para visualización interactiva
    - Markdown: Para documentación
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or REPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_json_report(self, report, filename: Optional[str] = None) -> Path:
        """
        Genera reporte en formato JSON
        
        Args:
            report: EvaluationReport object
            filename: Nombre del archivo (sin extensión)
            
        Returns:
            Path al archivo generado
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}"
        
        output_path = self.output_dir / f"{filename}.json"
        
        # Convertir a diccionario serializable
        report_dict = self._report_to_dict(report)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)
        
        return output_path
    
    def generate_html_report(self, report, filename: Optional[str] = None) -> Path:
        """
        Genera reporte en formato HTML
        
        Args:
            report: EvaluationReport object
            filename: Nombre del archivo (sin extensión)
            
        Returns:
            Path al archivo generado
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}"
        
        output_path = self.output_dir / f"{filename}.html"
        
        # Preparar datos para el template
        html_content = self._render_html(report)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return output_path
    
    def generate_markdown_report(self, report, filename: Optional[str] = None) -> Path:
        """
        Genera reporte en formato Markdown
        
        Args:
            report: EvaluationReport object
            filename: Nombre del archivo (sin extensión)
            
        Returns:
            Path al archivo generado
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}"
        
        output_path = self.output_dir / f"{filename}.md"
        
        md_content = self._render_markdown(report)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        return output_path
    
    def generate_all_formats(self, report, base_filename: Optional[str] = None) -> dict[str, Path]:
        """
        Genera reporte en todos los formatos
        
        Returns:
            Dict con paths a cada formato
        """
        if base_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"evaluation_report_{timestamp}"
        
        return {
            "json": self.generate_json_report(report, base_filename),
            "html": self.generate_html_report(report, base_filename),
            "markdown": self.generate_markdown_report(report, base_filename)
        }
    
    def _report_to_dict(self, report) -> dict:
        """Convierte el reporte a diccionario"""
        result = {
            "timestamp": report.timestamp,
            "model_name": report.model_name,
            "total_scenarios": report.total_scenarios,
            "passed_scenarios": report.passed_scenarios,
            "failed_scenarios": report.failed_scenarios,
            "metrics": {
                "task_success_rate": report.task_success_rate,
                "data_extraction_accuracy": report.data_extraction_accuracy,
                "intent_f1_score": report.intent_f1_score,
                "latency_p95_ms": report.latency_p95_ms
            },
            "targets_met": {
                "task_success": report.meets_task_success_target,
                "extraction": report.meets_extraction_target,
                "intent_f1": report.meets_intent_f1_target,
                "latency": report.meets_latency_target
            },
            "overall_pass": report.overall_pass(),
            "scenarios": []
        }
        
        # Agregar detalles de escenarios
        for sr in report.scenario_results:
            scenario_dict = {
                "id": sr.scenario_id,
                "category": sr.category,
                "success": sr.success,
                "error": sr.error,
                "latency_ms": sr.latency_ms
            }
            
            if sr.task_completion:
                scenario_dict["task_completion"] = {
                    "success": sr.task_completion.success,
                    "score": sr.task_completion.score,
                    "reason": sr.task_completion.reason
                }
            
            if sr.data_extraction:
                scenario_dict["data_extraction"] = {
                    "accuracy": sr.data_extraction.accuracy,
                    "dni_correct": sr.data_extraction.dni_correct,
                    "ruc_correct": sr.data_extraction.ruc_correct
                }
            
            result["scenarios"].append(scenario_dict)
        
        return result
    
    def _render_html(self, report) -> str:
        """Renderiza el template HTML construyendo strings directamente"""
        # Determinar clases CSS
        def get_class(meets_target: bool) -> str:
            return "status-pass" if meets_target else "status-fail"
        
        def get_bar_class(value: float, target: float) -> str:
            ratio = value / target if target > 0 else 0
            if ratio >= 1.0:
                return "success"
            elif ratio >= 0.8:
                return "warning"
            return "danger"
        
        # Generar filas de escenarios
        scenario_rows = []
        for sr in report.scenario_results:
            badge_class = "badge-success" if sr.success else "badge-danger"
            badge_text = "✅ Pass" if sr.success else "❌ Fail"
            
            task_score = f"{sr.task_completion.score*100:.0f}%" if sr.task_completion else "-"
            extraction_score = f"{sr.data_extraction.accuracy*100:.0f}%" if sr.data_extraction else "-"
            
            row = f"""
            <tr>
                <td>{html.escape(sr.scenario_id)}</td>
                <td>{html.escape(sr.category)}</td>
                <td><span class="badge {badge_class}">{badge_text}</span></td>
                <td>{task_score}</td>
                <td>{extraction_score}</td>
                <td>{sr.latency_ms:.0f}ms</td>
            </tr>
            """
            scenario_rows.append(row)
        
        # Calcular valores
        latency_target = 3000
        latency_percent = min(100, (latency_target / report.latency_p95_ms * 100)) if report.latency_p95_ms > 0 else 100
        
        overall_pass = report.overall_pass()
        overall_class = "pass" if overall_pass else "fail"
        overall_icon = "✅" if overall_pass else "❌"
        overall_text = "TODOS LOS TARGETS CUMPLIDOS" if overall_pass else "ALGUNOS TARGETS NO CUMPLIDOS"
        
        task_rate = f"{report.task_success_rate*100:.1f}"
        extraction_rate = f"{report.data_extraction_accuracy*100:.1f}"
        intent_f1 = f"{report.intent_f1_score:.3f}"
        intent_percent = f"{report.intent_f1_score*100:.0f}"
        latency_p95 = f"{report.latency_p95_ms:.0f}"
        
        task_class = get_class(report.meets_task_success_target)
        task_bar_class = get_bar_class(report.task_success_rate, 0.95)
        extraction_class = get_class(report.meets_extraction_target)
        extraction_bar_class = get_bar_class(report.data_extraction_accuracy, 0.98)
        intent_class = get_class(report.meets_intent_f1_target)
        intent_bar_class = get_bar_class(report.intent_f1_score, 0.92)
        latency_class = get_class(report.meets_latency_target)
        latency_bar_class = "success" if report.meets_latency_target else "danger"
        
        # Construir HTML directamente
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Evaluación - Mia Gente</title>
    <style>
        :root {{ --primary: #2563eb; --success: #16a34a; --danger: #dc2626; --warning: #ca8a04; --bg: #f8fafc; --card-bg: #ffffff; --text: #1e293b; --text-secondary: #64748b; --border: #e2e8f0; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 2px solid var(--border); }}
        h1 {{ font-size: 2rem; color: var(--primary); margin-bottom: 0.5rem; }}
        .subtitle {{ color: var(--text-secondary); }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: var(--card-bg); border-radius: 12px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid var(--border); }}
        .card h3 {{ font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin-bottom: 0.5rem; }}
        .card .value {{ font-size: 2rem; font-weight: 700; }}
        .card .target {{ font-size: 0.875rem; color: var(--text-secondary); }}
        .status-pass {{ color: var(--success); }}
        .status-fail {{ color: var(--danger); }}
        .metric-bar {{ height: 8px; background: var(--border); border-radius: 4px; margin-top: 0.5rem; overflow: hidden; }}
        .metric-bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s ease; }}
        .metric-bar-fill.success {{ background: var(--success); }}
        .metric-bar-fill.warning {{ background: var(--warning); }}
        .metric-bar-fill.danger {{ background: var(--danger); }}
        section {{ margin-bottom: 2rem; }}
        section h2 {{ font-size: 1.25rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }}
        table {{ width: 100%; border-collapse: collapse; background: var(--card-bg); border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ background: var(--bg); font-weight: 600; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        tr:hover {{ background: var(--bg); }}
        .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .badge-success {{ background: #dcfce7; color: #166534; }}
        .badge-danger {{ background: #fee2e2; color: #991b1b; }}
        .overall-result {{ text-align: center; padding: 2rem; border-radius: 12px; margin-bottom: 2rem; }}
        .overall-result.pass {{ background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); border: 2px solid var(--success); }}
        .overall-result.fail {{ background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); border: 2px solid var(--danger); }}
        .overall-result h2 {{ border: none; font-size: 1.5rem; }}
        footer {{ text-align: center; color: var(--text-secondary); font-size: 0.875rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🧪 Reporte de Evaluación</h1>
            <p class="subtitle">Mia Gente - Agente de Facturación TinRed</p>
        </header>
        
        <div class="overall-result {overall_class}">
            <h2>{overall_icon} {overall_text}</h2>
            <p>Modelo: {html.escape(report.model_name)} | Fecha: {report.timestamp}</p>
        </div>
        
        <div class="summary-grid">
            <div class="card">
                <h3>Task Success Rate</h3>
                <div class="value {task_class}">{task_rate}%</div>
                <div class="target">Target: 95%</div>
                <div class="metric-bar"><div class="metric-bar-fill {task_bar_class}" style="width: {task_rate}%"></div></div>
            </div>
            <div class="card">
                <h3>Data Extraction</h3>
                <div class="value {extraction_class}">{extraction_rate}%</div>
                <div class="target">Target: 98%</div>
                <div class="metric-bar"><div class="metric-bar-fill {extraction_bar_class}" style="width: {extraction_rate}%"></div></div>
            </div>
            <div class="card">
                <h3>Intent F1 Score</h3>
                <div class="value {intent_class}">{intent_f1}</div>
                <div class="target">Target: 0.92</div>
                <div class="metric-bar"><div class="metric-bar-fill {intent_bar_class}" style="width: {intent_percent}%"></div></div>
            </div>
            <div class="card">
                <h3>Latency P95</h3>
                <div class="value {latency_class}">{latency_p95}ms</div>
                <div class="target">Target: 3000ms</div>
                <div class="metric-bar"><div class="metric-bar-fill {latency_bar_class}" style="width: {latency_percent:.0f}%"></div></div>
            </div>
        </div>
        
        <section>
            <h2>📊 Resumen de Escenarios</h2>
            <div class="summary-grid">
                <div class="card"><h3>Total</h3><div class="value">{report.total_scenarios}</div></div>
                <div class="card"><h3>Pasados</h3><div class="value status-pass">{report.passed_scenarios}</div></div>
                <div class="card"><h3>Fallidos</h3><div class="value status-fail">{report.failed_scenarios}</div></div>
            </div>
        </section>
        
        <section>
            <h2>📋 Detalle por Escenario</h2>
            <table>
                <thead><tr><th>ID</th><th>Categoría</th><th>Estado</th><th>Task</th><th>Extraction</th><th>Latencia</th></tr></thead>
                <tbody>{"".join(scenario_rows)}</tbody>
            </table>
        </section>
        
        <footer>
            <p>Generado por Framework de Evaluación Mia Gente v1.0</p>
            <p>Basado en AgentBench (ICLR 2024) y RAGAS</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html_content
    
    def _render_markdown(self, report) -> str:
        """Renderiza el reporte en Markdown"""
        def status(meets: bool) -> str:
            return "✅ PASS" if meets else "❌ FAIL"
        
        overall = "✅ TODOS LOS TARGETS CUMPLIDOS" if report.overall_pass() else "❌ ALGUNOS TARGETS NO CUMPLIDOS"
        
        md = f"""# 🧪 Reporte de Evaluación - Mia Gente

**Modelo:** {report.model_name}  
**Fecha:** {report.timestamp}  
**Resultado:** {overall}

---

## 📊 Métricas Principales

| Métrica | Valor | Target | Estado |
|---------|-------|--------|--------|
| Task Success Rate | {report.task_success_rate*100:.1f}% | 95% | {status(report.meets_task_success_target)} |
| Data Extraction | {report.data_extraction_accuracy*100:.1f}% | 98% | {status(report.meets_extraction_target)} |
| Intent F1 Score | {report.intent_f1_score:.3f} | 0.92 | {status(report.meets_intent_f1_target)} |
| Latency P95 | {report.latency_p95_ms:.0f}ms | 3000ms | {status(report.meets_latency_target)} |

---

## 📋 Resumen de Escenarios

- **Total:** {report.total_scenarios}
- **Pasados:** {report.passed_scenarios} ({report.passed_scenarios/report.total_scenarios*100:.1f}%)
- **Fallidos:** {report.failed_scenarios}

---

## 📝 Detalle por Escenario

| ID | Categoría | Estado | Task | Extraction | Latencia |
|----|-----------|--------|------|------------|----------|
"""
        
        for sr in report.scenario_results:
            state = "✅" if sr.success else "❌"
            task = f"{sr.task_completion.score*100:.0f}%" if sr.task_completion else "-"
            extraction = f"{sr.data_extraction.accuracy*100:.0f}%" if sr.data_extraction else "-"
            
            md += f"| {sr.scenario_id} | {sr.category} | {state} | {task} | {extraction} | {sr.latency_ms:.0f}ms |\n"
        
        md += """
---

## 🔧 Configuración

- **Framework:** Mia Gente Evaluation Framework v1.0
- **Base:** AgentBench (ICLR 2024), RAGAS
- **Métricas:** Task Completion, Data Extraction, Intent Classification, Latency

---

*Generado automáticamente por el Framework de Evaluación*
"""
        
        return md


def generate_comparison_report(reports: list, output_dir: Optional[Path] = None) -> Path:
    """
    Genera un reporte comparativo entre múltiples evaluaciones
    
    Args:
        reports: Lista de EvaluationReport
        output_dir: Directorio de salida
        
    Returns:
        Path al archivo generado
    """
    output_dir = output_dir or REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"comparison_report_{timestamp}.md"
    
    md = """# 📊 Reporte Comparativo de Modelos

## Comparación de Métricas

| Modelo | Task Success | Extraction | Intent F1 | Latency P95 | Overall |
|--------|--------------|------------|-----------|-------------|---------|
"""
    
    for report in reports:
        overall = "✅" if report.overall_pass() else "❌"
        md += f"| {report.model_name} | {report.task_success_rate*100:.1f}% | {report.data_extraction_accuracy*100:.1f}% | {report.intent_f1_score:.3f} | {report.latency_p95_ms:.0f}ms | {overall} |\n"
    
    md += "\n---\n\n*Generado automáticamente*\n"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    
    return output_path
