# Agentic AI × Blockchain — Expense Approval System

> **Binary Hacks 4.0 · PS-10 · Open Innovation**

An autonomous expense approval system where an AI agent makes decisions — and every decision is permanently anchored to a blockchain. The blockchain is not just storage; it is the agent's memory.

---

## What Makes This Different

Most "AI + Blockchain" demos bolt two independent systems together. This project is architecturally different:

1. **Before reasoning**, the agent reads the last 5 decisions directly from the chain
2. **During reasoning**, it uses that on-chain history as live context in its prompt
3. **After deciding**, it writes the full decision + reasoning back as a new block
4. The chain **is** the agent's persistent memory — not a database alongside it

This creates a closed loop: every decision is informed by history, and every decision becomes history.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (HTML)                       │
│         Dashboard · Submit Form · Chain Visualizer           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend                            │
│   POST /api/expense   GET /api/chain   GET /api/decisions    │
└──────────┬───────────────────────────────────┬──────────────┘
           │                                   │
┌──────────▼──────────┐             ┌──────────▼──────────────┐
│   ExpenseApprovalAgent│            │      Blockchain          │
│                      │            │                          │
│  1. Read chain history│◄──────────│  SHA-256 linked blocks   │
│  2. Build prompt      │           │  Append-only             │
│  3. Call Groq LLM     │           │  Persisted to JSON       │
│  4. Parse decision    │──────────►│  Chain integrity checks  │
│  5. Write to chain    │           │                          │
└──────────────────────┘           └──────────────────────────┘
```

---

## Features

- **Autonomous AI decisions** — APPROVE, REJECT, or ESCALATE based on company policy
- **On-chain memory** — agent reads previous decisions before reasoning, enforcing consistency
- **Tamper detection** — every block is SHA-256 hashed and linked; the frontend flags any tampered block visually
- **Policy engine** — built-in rules for amount thresholds, duplicate detection, category-specific limits
- **Live chain visualizer** — scrollable block-by-block view in the dashboard with tamper indicators
- **Full audit trail** — every decision includes reasoning, confidence score, flags, and a block hash proof
- **REST API** — fully documented with Swagger UI at `/docs`

---

## Project Structure

```
.
├── main.py                  # Entry point — starts uvicorn server
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
│
├── agent/
│   └── expense_agent.py     # AI agent — Groq LLM + chain memory loop
│
├── api/
│   └── routes.py            # FastAPI routes + request/response models
│
├── blockchain/
│   └── chain.py             # Block, Blockchain classes — SHA-256 chain
│
├── data/
│   └── chain.json           # Persisted blockchain (auto-created on first run)
│
├── frontend/
│   └── index.html           # Single-page dashboard (no build step needed)
│
└── logs/
    └── errors.log           # Application logs (gitignored)
```

---

## Expense Policy (Agent Rules)

| Condition | Decision |
|-----------|----------|
| Amount ≤ ₹5,000 with reasonable justification | APPROVED |
| Amount ₹5,000 – ₹25,000 with clear business justification | APPROVED |
| Amount > ₹25,000 | ESCALATE (human review) |
| Entertainment > ₹3,000 without strong justification | REJECTED |
| Duplicate claim (same employee + category within 7 days) | REJECTED |
| Travel / Equipment with justification | APPROVED |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/expense` | Submit an expense for AI evaluation |
| `GET` | `/api/chain` | Get all blocks with tamper annotations |
| `GET` | `/api/chain/validate` | Validate full chain integrity |
| `GET` | `/api/decisions` | Get recent AI decisions |
| `GET` | `/` | Serve the frontend dashboard |
| `GET` | `/docs` | Swagger UI (interactive API docs) |

### Example Request

```bash
curl -X POST http://localhost:8004/api/expense \
  -H "Content-Type: application/json" \
  -d '{
    "employee": "Priya Sharma",
    "amount": 4500,
    "category": "Travel",
    "description": "Flight tickets for client meeting in Mumbai",
    "department": "Engineering",
    "date": "2026-10-19"
  }'
```

### Example Response

```json
{
  "decision": "APPROVED",
  "confidence": 0.95,
  "reasoning": "The expense amount of Rs.4,500 falls below the Rs.5,000 threshold for auto-approval. Category is Travel, which is generally approved with business justification.",
  "flags": [],
  "block_index": 1,
  "block_hash": "671fb1958354b760f94cdf364ea6b8a01984f74edb47219d2997b7896c8d1a3e",
  "chain_context_used": 0,
  "model": "openai/gpt-oss-20b"
}
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- A free [Groq API key](https://console.groq.com/)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/saumysingh01/blockchain-ai-agent.git
cd blockchain-ai-agent

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### Configure `.env`

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

> Get a free API key at https://console.groq.com/

### Run

```bash
python main.py
```

Then open:
- **Dashboard** → http://localhost:8004
- **API Docs** → http://localhost:8004/docs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| AI Agent | [Groq](https://groq.com/) (LLM inference) |
| Blockchain | Custom Python implementation (SHA-256, append-only) |
| Frontend | Vanilla HTML/CSS/JS (no framework, no build step) |
| Config | [python-dotenv](https://pypi.org/project/python-dotenv/) |
| Validation | [Pydantic v2](https://docs.pydantic.dev/) |

---

## How the Blockchain Works

Each block contains:

```json
{
  "index": 1,
  "timestamp": "2026-10-19T01:55:00.000Z",
  "previous_hash": "000...000",
  "hash": "671fb195...",
  "data": {
    "type": "expense_decision",
    "request": { "employee": "...", "amount": 4500, ... },
    "decision": "APPROVED",
    "confidence": 0.95,
    "reasoning": "...",
    "flags": [],
    "model": "openai/gpt-oss-20b",
    "chain_context_used": 0
  }
}
```

The `hash` is a SHA-256 digest of `index + timestamp + data + previous_hash`. Any modification to any field breaks the hash chain and is flagged instantly by the `/api/chain/validate` endpoint and highlighted in the frontend.

---

## Built For

**Binary Hacks 4.0** — Problem Statement 10 (Open Innovation)

The core thesis: blockchain immutability + AI reasoning creates an audit trail that is both intelligent and tamper-proof. Decisions aren't just logged — they're proven.
