# TinRed Agent Evaluation Framework v2.0

Framework de evaluación completo para el agente de facturación electrónica TinRed.

## 📋 Características

- **62 escenarios de prueba** en 20 categorías
- **54 DNIs válidos** y **59 RUCs válidos** reales
- **77 productos** con precios reales
- Generación de reportes en JSON, Markdown y HTML
- Soporte para evaluación por categorías

## 🚀 Uso Rápido

```bash
cd evaluation
python scripts/run_evaluation.py
```

### Con categorías específicas

```bash
python scripts/run_evaluation.py --categories emission_boleta,emission_factura
```

## 📁 Estructura

```
evaluation/
├── datasets/
│   └── test_scenarios_v2.json    # Dataset con datos reales
├── evaluators/
│   └── tinred_evaluator.py       # Evaluador principal
├── scripts/
│   └── run_evaluation.py         # Script de ejecución
├── reports/                      # Reportes generados
└── README.md
```

## 🎯 Categorías de Tests

| Categoría | Tests | Descripción |
|-----------|-------|-------------|
| emission_boleta | 3 | Emisión de boletas |
| emission_factura | 3 | Emisión de facturas |
| validation_dni | 3 | Validación de DNI |
| validation_ruc | 2 | Validación de RUC |
| validation_client | 2 | Validación de cliente |
| cancellation | 3 | Flujos de cancelación |
| history | 4 | Consulta de historial |
| products | 5 | Gestión de productos |
| general_questions | 4 | Preguntas generales |
| context_switching | 2 | Cambio de contexto |
| edge_cases | 5 | Casos límite |
| intent_classification | 7 | Clasificación de intent |
| data_extraction | 4 | Extracción de datos |
| real_emission_tests | 3 | Emisiones reales |

## 📊 Datos de Prueba Reales

### DNIs Válidos (54)
22462864, 22494016, 41580986, 22477390, 22502870, 22664744, 42152812, ...

### RUCs Válidos (59)
10422980925, 20609029189, 20573293275, 20601080134, 20362427798, ...

### Productos (77)
- PANETON DONOFRIO LATA 880GR X 6UNI - S/41.00
- DETERGENTE ARIEL REG-REV 720GR X14 - S/56.00
- JABON NEKO BOLSA 110GR X 48UNI - S/147.02
- HARINA DOÑA ANGELICA PANAD ESP 50KG - S/285.00
- Y 73 más...

## 📈 Métricas Objetivo

| Métrica | Objetivo |
|---------|----------|
| Task Completion | > 95% |
| Data Extraction | > 98% |
| Intent F1 Score | > 0.92 |
| Latency P95 | < 3000ms |

## 📄 Reportes

Se generan en 3 formatos:
- **JSON**: Datos para procesamiento
- **Markdown**: Documentación
- **HTML**: Visualización

TinRed © 2025
