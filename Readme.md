# TinRed Invoice Agent v2

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Gemini-2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/WhatsApp-Business_API-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" alt="WhatsApp">
</p>

<p align="center">
  <strong>AI-powered electronic invoicing agent for WhatsApp integration with Peru's SUNAT tax system</strong>
</p>

---

## 📋 Overview

TinRed Invoice Agent is an intelligent conversational system that enables businesses to issue electronic invoices and receipts through WhatsApp. Built with a multi-agent architecture following industry best practices from IBM, Microsoft, AWS, and Anthropic.

### Key Features

- 🤖 **Natural Language Processing** - Understands user intent in Spanish with multiple expression variations
- 📱 **WhatsApp Integration** - Seamless messaging via Baileys (WhatsApp Web API)
- 🎤 **Voice Support** - Automatic audio transcription (OGG, WebM, MP3, M4A)
- 🔐 **Secure by Design** - Phone-based authentication, no local data storage
- 📄 **SUNAT Compliant** - Electronic invoices (Facturas) and receipts (Boletas) following Peru's tax regulations
- ⚡ **Fast Response** - Average latency ~550ms per turn

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER (WhatsApp)                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              FRONTEND (TypeScript + Baileys)                │
│  • WhatsApp connection    • Message handling                │
│  • Audio download         • PDF delivery                    │
└─────────────────────────────┬───────────────────────────────┘
                              │ POST /api/converse
┌─────────────────────────────▼───────────────────────────────┐
│                BACKEND (Python + FastAPI)                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │              MainOrchestrator                       │    │
│  │  ┌──────────┬──────────┬──────────┬─────────────┐  │    │
│  │  │ Intent   │ Session  │  Audio   │    Data     │  │    │
│  │  │Classifier│ Manager  │ Service  │  Extractor  │  │    │
│  │  └──────────┴──────────┴──────────┴─────────────┘  │    │
│  └─────────────────────────┬──────────────────────────┘    │
│              ┌─────────────┼─────────────┐                  │
│              ▼             ▼             ▼                  │
│      ┌────────────┐ ┌────────────┐ ┌──────────┐            │
│      │ Emission   │ │Conversation│ │ Anomaly  │            │
│      │   Agent    │ │   Agent    │ │ Detector │            │
│      └─────┬──────┘ └─────┬──────┘ └──────────┘            │
│            └──────────────┼─────────────────────────────    │
│                           ▼                                 │
│                   ┌─────────────┐                           │
│                   │TinRedClient │───► TinRed API (SUNAT)    │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| **MainOrchestrator** | Central coordinator that routes messages to appropriate agents |
| **IntentClassifier** | Classifies user intent (emit invoice, cancel, history, etc.) |
| **EmissionAgent** | Handles 6-step invoice emission flow |
| **ConversationAgent** | General conversation powered by Gemini 2.0 Flash |
| **DataExtractor** | Extracts DNI, RUC, products, and prices from natural language |
| **SessionManager** | Manages user sessions in volatile memory |
| **TinRedClient** | HTTP client for TinRed API with retry logic |
| **AudioService** | Transcribes voice messages using Google Speech Recognition |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud API Key (for Gemini)
- TinRed API credentials

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/SadidRomero77/Conversational-agent-for-electronic-invoicing-TinRed.git
cd Conversational-agent-for-electronic-invoicing-TinRed
```

2. **Backend Setup**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Frontend Setup**
```bash
cd frontend
npm install
```

4. **Environment Configuration**

Create `.env` file in the root directory:
```env
# Google AI
GOOGLE_API_KEY=your_google_api_key

# TinRed API
TINRED_API_URL=https://api.tinred.pe/v1
TINRED_API_KEY=your_tinred_api_key

# Server
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

### Running the Application

1. **Start Backend**
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

2. **Start Frontend**
```bash
cd frontend
npm run start
```

3. **Connect WhatsApp**
- Scan the QR code displayed in the terminal
- Start chatting!

---

## 📱 Usage Examples

### Emit a Receipt (Boleta)
```
User: Quiero emitir una boleta
Agent: Perfecto, vamos a emitir una boleta. ¿Cuál es el DNI del cliente?

User: 12345678
Agent: ✓ Cliente: Juan Pérez. Ahora ingresa los productos:

User: 2 laptops a 2500 y 3 mouses por 50
Agent: 📋 Resumen:
       • 2 laptops - S/ 5,000.00
       • 3 mouses - S/ 150.00
       Subtotal: S/ 5,150.00
       IGV (18%): S/ 927.00
       Total: S/ 6,077.00
       ¿Confirmas la emisión? (Sí/No)

User: Sí
Agent: ✅ ¡Comprobante emitido!
       📄 Número: B001-00001234
       [PDF attachment]
```

### Voice Message Support
```
User: [Audio] "Boleta para DNI uno dos tres cuatro cinco seis siete ocho"
Agent: ✓ Cliente identificado: DNI 12345678...
```

---

## 🧪 Testing

### Run Evaluation Framework
```bash
cd backend
python -m pytest tests/ -v
```

### Metrics
| Metric | Result |
|--------|--------|
| Success Rate | 89.29% (50/56 scenarios) |
| Categories with 100% | 12 of 16 |
| Average Latency | ~550ms |
| AgentBench Compliance | 6/8 criteria |

---

## 📁 Project Structure

```
tinred-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── api/
│   │   │   └── routes.py           # API endpoints
│   │   ├── agents/
│   │   │   ├── orchestrator.py     # Main coordinator
│   │   │   ├── intent_classifier.py
│   │   │   ├── emission_agent.py
│   │   │   ├── conversation_agent.py
│   │   │   └── data_extractor.py
│   │   ├── services/
│   │   │   ├── session_manager.py
│   │   │   ├── tinred_client.py
│   │   │   └── audio_service.py
│   │   ├── models/
│   │   │   └── schemas.py
│   │   └── core/
│   │       └── config.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── whatsapp_handler.ts
│   ├── package.json
│   └── tsconfig.json
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🔒 Security

- **No Local Storage**: All session data is kept in volatile memory only
- **Phone Authentication**: Only pre-registered phone numbers can interact
- **End-to-End Encryption**: WhatsApp's native E2E encryption
- **HTTPS**: All API communications over TLS
- **Idempotency Keys**: Prevents duplicate invoice emissions

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | TypeScript + Baileys | WhatsApp Web API connection |
| Backend | Python + FastAPI | Async API server |
| AI/LLM | Gemini 2.0 Flash | Natural language understanding |
| Audio | speech_recognition + ffmpeg | Voice transcription |
| Validation | Pydantic v2 | Data validation |
| HTTP Client | httpx | Async HTTP requests |

---

## 📚 References

- [AgentBench: Evaluating LLMs as Agents (ICLR 2024)](https://arxiv.org/abs/2308.03688)
- [Anthropic: Building Multi-Agent Systems](https://www.anthropic.com/research/building-effective-agents)
- [Microsoft Magentic-One](https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/)
- [SUNAT Electronic Invoicing Regulations](https://www.sunat.gob.pe/)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Sadid Romero**
- University Thesis Project
- December 2025

---

<p align="center">
  Made with ❤️ for electronic invoicing in Peru
</p>