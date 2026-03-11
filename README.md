# PharmaAI

An AI-powered clinical pharmacology assistant that detects drug-drug interactions, validates prescriptions via OCR, and delivers real-time alerts through Telegram — backed by a BNF-indexed RAG engine and a FastAPI layer for n8n automation.

---

## Features

- **Drug Interaction Detection** — MAJOR / MODERATE / MINOR / NONE severity from BNF80
- **Prescription OCR** — Upload a prescription image; Gemini Vision extracts drug names and checks safety
- **RAG Engine** — ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`) over BNF80.pdf
- **LLM Responses** — Groq (cloud, default) or Ollama BioMistral (local)
- **Streamlit UI** — Interactive chat interface with structured clinical output
- **FastAPI Backend** — REST endpoints (`/query`, `/ocr`, `/ocr/upload`, `/health`) for external automation
- **n8n Workflow** — Webhook → RAG → Severity routing → Telegram alert → JSON response

---

## Architecture

```
Mobile / n8n Webhook
        │
        ▼
   FastAPI (api.py)          ← port 8000
        │
   ┌────┴────────────┐
   │                 │
RAG Query          OCR (Gemini)
(chatbot.py)       (ocr.py)
   │
ChromaDB ← BNF80.pdf
   │
Groq / Ollama LLM
   │
StructuredClinicalResponse
        │
        ▼
   n8n Workflow
        │
   Telegram Bot Alert
```

---

## Requirements

- Python 3.10+
- Node.js 18+ (for n8n)
- A Groq API key — https://console.groq.com
- A Google Gemini API key (OCR only) — https://aistudio.google.com
- A Telegram Bot token (alerts only) — message @BotFather on Telegram

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Ahmed4r/pharmaAI.git
cd pharmaAI
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here   # only needed for OCR
```

### 5. Ingest the BNF knowledge base

The BNF80.pdf must be indexed into ChromaDB before the RAG engine can answer queries. This only needs to be done **once**.

```bash
python ingest.py knowledge_base/BNF80.pdf
```

This will create a `chroma_db/` folder. The process takes 2–5 minutes depending on hardware.

---

## Running

### Option A — Streamlit UI only

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

### Option B — FastAPI backend (for n8n / REST access)

```bash
# Windows PowerShell
$env:GROQ_API_KEY="your_key_here"
$env:GEMINI_API_KEY="your_key_here"
.\.venv\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000

# macOS / Linux
GROQ_API_KEY=your_key GEMINI_API_KEY=your_key uvicorn api:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

### Option C — Both together (background jobs, Windows PowerShell)

```powershell
Start-Job -Name fastapi -ScriptBlock {
  cd C:\path\to\pharmaAI
  $env:GROQ_API_KEY = "your_groq_key"
  $env:GEMINI_API_KEY = "your_gemini_key"
  .\.venv\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000
}
Start-Job -Name streamlit -ScriptBlock {
  cd C:\path\to\pharmaAI
  $env:GROQ_API_KEY = "your_groq_key"
  .\.venv\Scripts\streamlit.exe run app.py
}
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness probe — returns `{"status":"ok","chromadb_ready":true}` |
| `POST` | `/query` | Drug interaction RAG query |
| `POST` | `/ocr` | Prescription OCR from URL or base64 image |
| `POST` | `/ocr/upload` | Prescription OCR from file upload |

### POST /query — example

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "warfarin ibuprofen", "mode": "cloud"}'
```

Response:

```json
{
  "query": "warfarin ibuprofen",
  "drug_name": ["warfarin", "ibuprofen"],
  "interaction_severity": "MODERATE",
  "clinical_rationale_the_why": "...",
  "bnf_source_page": [{"file": "BNF80.pdf", "page": 1227}],
  "full_markdown": "...",
  "confidence_pct": 88,
  "alert_level": "WARNING"
}
```

---

## n8n Automation Workflow

### Install n8n

```bash
npm install -g n8n
# or run without installing:
npx n8n
```

n8n opens at `http://localhost:5678`.

### Import the workflow

1. Open `http://localhost:5678`
2. Click **New workflow** → three-dot menu → **Import from file**
3. Select `n8n_workflow.json`
4. Add your **Telegram credentials**:
   - Go to **Settings → Credentials → New → Telegram**
   - Paste your bot token from @BotFather
   - Assign the credential to both Telegram nodes in the workflow
5. Update the `chatId` field in both Telegram nodes with your chat ID
   (get it by messaging @userinfobot on Telegram)
6. Click **Save** → **Publish**

### Test the workflow

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:5678/webhook/pharma-query" `
  -ContentType "application/json" `
  -Body '{"query": "warfarin ibuprofen"}'
```

Expected: JSON response returned + Telegram alert sent for WARNING/CRITICAL severity.

### Alert routing

| Severity | Alert Level | Telegram |
|----------|-------------|----------|
| MAJOR | CRITICAL | ✅ Urgent (notification on) |
| MODERATE | WARNING | ✅ Standard (notification on) |
| MINOR | INFO | ✅ Standard (silent) |
| NONE | SAFE | ❌ No Telegram sent |

---

## Project Structure

```
pharmaAI/
├── app.py                  # Streamlit UI
├── api.py                  # FastAPI backend
├── chatbot.py              # RAG + LLM core logic
├── rag_engine.py           # ChromaDB retrieval
├── ocr.py                  # Gemini Vision OCR
├── ingest.py               # PDF → ChromaDB indexing pipeline
├── drug_db.py              # Drug interaction SQLite database
├── drug_lookup.py          # Drug name normalisation
├── drug_normalizer.py      # Brand → generic name mapping
├── dosing_validator.py     # Dosing safety checks
├── interaction_checker.py  # Structured interaction DB queries
├── database.py             # SQLite schema and helpers
├── n8n_workflow.json       # Full n8n workflow (with Telegram)
├── requirements.txt
├── .env.example
├── knowledge_base/
│   ├── BNF80.pdf           # British National Formulary (source of truth)
│   ├── drugs.json          # Drug metadata
│   └── brand_map.json      # Brand → generic mappings
├── chroma_db/              # Generated after running ingest.py
└── .streamlit/
    └── config.toml
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Groq cloud LLM key (get from console.groq.com) |
| `GEMINI_API_KEY` | OCR only | Google Gemini Vision key (aistudio.google.com) |
| `PHARMA_API_KEY` | Optional | If set, all `/query` and `/ocr` endpoints require `X-API-Key` header |

---

## Local LLM (Ollama) — Optional

To run fully offline without Groq:

```bash
# Install Ollama: https://ollama.com
ollama pull BioMistral/BioMistral-7B   # or any compatible model
```

In the Streamlit UI, switch the mode to **Local (Ollama)**.

---

## License

MIT
