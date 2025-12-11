# TinRed Invoice Agent v2

Agente conversacional multi-agente para emisión de facturas y boletas electrónicas vía WhatsApp.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                         │
│  (Coordina flujo, maneja sesiones, delega a agentes)        │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌───────────┐  ┌────────────┐  ┌────────────┐
│  INTENT   │  │ EMISSION   │  │CONVERSATION│
│CLASSIFIER │  │   AGENT    │  │   AGENT    │
│           │  │            │  │   (RAG)    │
│ Clasifica │  │ Flujo de   │  │ Consultas  │
│ intención │  │ emisión    │  │ generales  │
└───────────┘  └─────┬──────┘  └────────────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
        ┌──────────┐  ┌──────────┐
        │  DATA    │  │ ANOMALY  │
        │EXTRACTOR │  │ DETECTOR │
        │          │  │          │
        │ Regex +  │  │ Detecta  │
        │ Patrones │  │ anomalías│
        └──────────┘  └──────────┘
```

## 📁 Estructura del Proyecto

```
backend/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py      # Orquestador principal
│   │   ├── intent_classifier.py # Clasificador de intenciones
│   │   ├── conversation_agent.py # Agente conversacional (RAG)
│   │   ├── emission_agent.py    # Agente de emisión
│   │   ├── data_extractor.py    # Extractor de datos
│   │   └── anomaly_detector.py  # Detector de anomalías
│   │
│   ├── services/
│   │   ├── tinred_client.py     # Cliente HTTP para TinRed API
│   │   ├── session_manager.py   # Gestor de sesiones
│   │   └── audio_service.py     # Transcripción de audio
│   │
│   ├── models/
│   │   └── schemas.py           # Modelos Pydantic
│   │
│   ├── core/
│   │   └── config.py            # Configuración
│   │
│   ├── api/
│   │   └── routes.py            # Endpoints FastAPI
│   │
│   ├── evaluation/
│   │   ├── evaluator.py         # Sistema de evaluación
│   │   └── run_tests.py         # Script de pruebas
│   │
│   └── main.py                  # Aplicación principal
│
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Instalación

### 1. Clonar y configurar entorno

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Ejecutar el servidor

```bash
python -m app.main
# o
uvicorn app.main:app --reload --port 8000
```

## 🎯 Intenciones Soportadas

| Intención | Ejemplos | Agente |
|-----------|----------|--------|
| `emit_invoice` | "Factura para RUC 20123456789" | EmissionAgent |
| `query_products` | "¿Qué productos tengo?" | ConversationAgent |
| `query_clients` | "Muéstrame mis clientes" | ConversationAgent |
| `query_history` | "¿Cuántas facturas emití hoy?" | ConversationAgent |
| `general_question` | "¿Cuál es la diferencia entre factura y boleta?" | ConversationAgent |
| `greeting` | "Hola" | ConversationAgent |
| `confirmation` | "Sí, confirmo" | EmissionAgent |
| `cancel` | "No, cancelar" | Orchestrator |

## 💡 Flujo de Emisión

```
Usuario: "Boleta para DNI 12345678, 2 laptops a 2500"
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. Intent Classifier                     │
│    → emit_invoice (0.85)                 │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 2. Data Extractor                        │
│    → document_type: "03" (boleta)        │
│    → id_type: "1" (DNI)                  │
│    → id_number: "12345678"               │
│    → items: [2 x laptops @ 2500]         │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 3. Anomaly Detector                      │
│    → Verifica precios vs catálogo        │
│    → Verifica cantidades inusuales       │
│    → Verifica monto total                │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 4. Emission Agent                        │
│    → Genera resumen                      │
│    → Espera confirmación                 │
│    → Emite en TinRed API                 │
│    → Retorna PDF                         │
└─────────────────────────────────────────┘
```

## 🔍 Inferencia Inteligente

El agente puede inferir datos faltantes:

| Input | Inferencia |
|-------|------------|
| DNI (8 dígitos) | → Boleta + tipo_id="1" |
| RUC (11 dígitos) | → Factura + tipo_id="6" |
| Sin moneda | → PEN (por defecto) |

**Ejemplo:**
```
Usuario: "Comprobante para 12345678, 3 servicios a 100"
    → Tipo: Boleta (inferido de DNI)
    → DNI: 12345678
    → Items: 3 x servicios @ 100
    → Moneda: PEN (default)
```

## 📊 Evaluación de Métricas

```bash
# Ejecutar todas las pruebas
python -m app.evaluation.run_tests

# Filtrar por tipo
python -m app.evaluation.run_tests --tag emission

# Exportar resultados
python -m app.evaluation.run_tests --export results.json --verbose
```

### Métricas Disponibles

- **Intent Accuracy**: Precisión en clasificación de intenciones
- **Extraction Precision**: Precisión en extracción de datos
- **Extraction Recall**: Cobertura de extracción
- **Extraction F1**: Score F1 combinado
- **Response Relevance**: Relevancia de respuestas
- **Error Rate**: Tasa de errores
- **Response Time**: Tiempos de respuesta (avg, p95)

## 🛡️ Detección de Anomalías

El agente detecta y advierte sobre:

1. **Precios anormales**: Diferencia >50% vs catálogo
2. **Cantidades inusuales**: >100 unidades
3. **Montos altos**: >10x el promedio histórico
4. **Productos fuera de catálogo**

## 🔧 API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/converse` | Procesar mensaje |
| GET | `/api/health` | Health check |
| GET | `/docs` | Documentación Swagger |

### Request `/api/converse`

```json
{
    "phone": "51987654321",
    "message": "Boleta para DNI 12345678",
    "mime_type": null,
    "file_base64": null
}
```

### Response

```json
{
    "reply": "📋 **RESUMEN DE BOLETA**\n..."
}
```

## 🔄 Integración con WhatsApp (Frontend)

El frontend de WhatsApp (Node.js + Baileys) se conecta al endpoint `/api/converse`.

```bash
cd frontend
npm install
npm start
```

## 📝 Notas de Desarrollo

### Agregar Nuevo Tipo de Intención

1. Agregar enum en `models/schemas.py`:
```python
class IntentType(str, Enum):
    NEW_INTENT = "new_intent"
```

2. Agregar patrones en `intent_classifier.py`

3. Agregar routing en `orchestrator.py`

### Agregar Caso de Prueba

```python
from app.evaluation.evaluator import get_evaluator, TestCase

evaluator = get_evaluator()
evaluator.add_test_case(TestCase(
    id="my_test",
    input_message="mensaje de prueba",
    expected_intent="emit_invoice",
    expected_extractions={"document_type": "01"},
    tags=["custom"]
))
```

## 📄 Licencia

Propiedad de TinRed Suite. Todos los derechos reservados.
