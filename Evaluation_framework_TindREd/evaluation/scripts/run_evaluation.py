#!/usr/bin/env python3
"""
Script de ejecución del framework de evaluación.
Uso: python run_evaluation.py [--categories CATEGORY1,CATEGORY2] [--api-url URL]
"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluators.tinred_evaluator import TinRedEvaluator, ReportGenerator


def parse_args():
    parser = argparse.ArgumentParser(description="Ejecutar evaluación del agente TinRed")
    
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL de la API")
    parser.add_argument("--phone", default="573134723604", help="Número de teléfono para tests")
    parser.add_argument("--categories", type=str, help="Categorías a evaluar (separadas por coma)")
    parser.add_argument("--output-dir", default="reports", help="Directorio de salida")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout en segundos")
    
    return parser.parse_args()


async def main():
    args = parse_args()
    
    print("\n" + "=" * 60)
    print("🤖 TinRed Agent Evaluation Framework v2.0")
    print("=" * 60)
    print(f"📞 Teléfono: {args.phone}")
    print(f"🔗 API: {args.api_url}")
    print("=" * 60)
    
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None
    
    evaluator = TinRedEvaluator({
        "api_url": args.api_url, 
        "timeout": args.timeout,
        "test_phone": args.phone
    })
    report = await evaluator.run_all_tests(categories)
    
    # Guardar reportes
    output_dir = Path(__file__).parent.parent / args.output_dir
    output_dir.mkdir(exist_ok=True)
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    ReportGenerator.to_json(report, str(output_dir / f"eval_{ts}.json"))
    ReportGenerator.to_markdown(report, str(output_dir / f"eval_{ts}.md"))
    ReportGenerator.to_html(report, str(output_dir / f"eval_{ts}.html"))
    
    # Resumen
    print(f"\n📊 Resultados: {report.passed}/{report.total_scenarios} ({report.pass_rate:.1f}%)")
    print(f"📁 Reportes en: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
