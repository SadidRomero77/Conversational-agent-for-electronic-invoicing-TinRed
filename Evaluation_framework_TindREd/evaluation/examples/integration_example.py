#!/usr/bin/env python3
"""
Ejemplo de Integración con el Agente TinRed Real
=================================================

Este script muestra cómo integrar el framework de evaluación
con el agente real de Mia Gente.

Requisitos:
    1. El proyecto tinred-ai-agent debe estar disponible
    2. Las variables de entorno deben estar configuradas
    3. El API de TinRed debe estar accesible

Uso:
    python examples/integration_example.py
"""
import sys
import asyncio
from pathlib import Path

# Agregar paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import eval_config, api_config
from evaluators import AgentEvaluator
from adapters import create_tinred_agent


async def run_with_real_agent():
    """
    Ejecuta evaluación con el agente real de TinRed
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🏭 Evaluación con Agente Real                              ║
║       Mia Gente - TinRed                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Verificar configuración
    print("📋 Verificando configuración...")
    
    if not api_config.google_api_key:
        print("⚠️  GOOGLE_API_KEY no configurada")
        print("   Usando modo mock")
        mode = "mock"
    else:
        print("✅ GOOGLE_API_KEY configurada")
        mode = "direct"
    
    # Crear agente
    print(f"\n🤖 Creando agente (modo: {mode})...")
    
    try:
        agent = create_tinred_agent(mode=mode)
        print("✅ Agente creado")
    except Exception as e:
        print(f"❌ Error creando agente: {e}")
        print("   Usando mock como fallback")
        agent = create_tinred_agent(mode="mock")
    
    # Crear evaluador
    print("\n🧪 Creando evaluador...")
    evaluator = AgentEvaluator(
        agent_callable=agent,
        model_name="gemini-2.5-flash"
    )
    
    # Ejecutar evaluación (10 escenarios para ejemplo)
    print("\n🚀 Ejecutando evaluación (10 escenarios)...")
    print("-" * 50)
    
    report = await evaluator.run_evaluation(max_scenarios=10)
    
    # Mostrar resultados
    print("\n" + "=" * 60)
    print("                    RESULTADOS")
    print("=" * 60)
    print(f"""
📊 Métricas:
   • Task Success:      {report.task_success_rate*100:.1f}% (target: 95%)
   • Data Extraction:   {report.data_extraction_accuracy*100:.1f}% (target: 98%)
   • Intent F1:         {report.intent_f1_score:.3f} (target: 0.92)
   • Latency P95:       {report.latency_p95_ms:.0f}ms (target: 3000ms)

📋 Escenarios:
   • Total:    {report.total_scenarios}
   • Pasados:  {report.passed_scenarios}
   • Fallidos: {report.failed_scenarios}

🎯 Resultado: {'✅ PASS' if report.overall_pass() else '❌ FAIL'}
""")
    
    return report


async def run_with_api():
    """
    Ejecuta evaluación conectándose al agente via API
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🌐 Evaluación via API                                      ║
║       Mia Gente - TinRed                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # El agente debe estar corriendo en localhost:8000
    agent = create_tinred_agent(
        mode="api",
        base_url="http://localhost:8000"
    )
    
    evaluator = AgentEvaluator(
        agent_callable=agent,
        model_name="gemini-2.5-flash-api"
    )
    
    report = await evaluator.run_evaluation(max_scenarios=5)
    
    return report


async def run_custom_scenarios():
    """
    Ejecuta evaluación con escenarios personalizados
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   📝 Evaluación con Escenarios Personalizados                ║
║       Mia Gente - TinRed                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    from config import DATASETS_DIR
    import json
    
    # Crear dataset personalizado
    custom_scenarios = {
        "version": "1.0.0",
        "description": "Escenarios personalizados de ejemplo",
        "scenarios": [
            {
                "id": "CUSTOM-001",
                "category": "custom",
                "description": "Boleta simple",
                "conversation": [
                    {"role": "user", "content": "Boleta DNI 12345678, 2 productos a 50"}
                ],
                "expected": {
                    "intent": "emit_invoice",
                    "document_type": "03",
                    "id_number": "12345678",
                    "should_emit": True
                }
            },
            {
                "id": "CUSTOM-002",
                "category": "custom",
                "description": "Saludo",
                "conversation": [
                    {"role": "user", "content": "Hola, buenas tardes"}
                ],
                "expected": {
                    "intent": "greeting"
                }
            },
            {
                "id": "CUSTOM-003",
                "category": "custom",
                "description": "Factura con RUC",
                "conversation": [
                    {"role": "user", "content": "Factura para RUC 20447327776, 10 unidades a 100"}
                ],
                "expected": {
                    "intent": "emit_invoice",
                    "document_type": "01",
                    "id_number": "20447327776",
                    "should_emit": True
                }
            }
        ],
        "metadata": {
            "total_scenarios": 3
        }
    }
    
    # Guardar temporalmente
    custom_path = DATASETS_DIR / "custom_scenarios.json"
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(custom_scenarios, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Dataset personalizado creado: {custom_path}")
    
    # Crear agente y evaluador
    agent = create_tinred_agent(mode="mock")
    evaluator = AgentEvaluator(
        agent_callable=agent,
        model_name="mock",
        dataset_path=custom_path
    )
    
    # Ejecutar
    report = await evaluator.run_evaluation()
    
    print(f"\n✅ Evaluación completada: {report.passed_scenarios}/{report.total_scenarios} pasados")
    
    return report


def main():
    """Menú principal de ejemplos"""
    print("""
🔬 Ejemplos de Integración - Framework de Evaluación

Selecciona un ejemplo:
    1. Evaluación con agente real (direct)
    2. Evaluación via API (requiere servicio corriendo)
    3. Evaluación con escenarios personalizados
    4. Salir
""")
    
    choice = input("Opción [1-4]: ").strip()
    
    if choice == "1":
        asyncio.run(run_with_real_agent())
    elif choice == "2":
        asyncio.run(run_with_api())
    elif choice == "3":
        asyncio.run(run_custom_scenarios())
    elif choice == "4":
        print("👋 ¡Hasta luego!")
    else:
        print("⚠️ Opción no válida")


if __name__ == "__main__":
    main()
