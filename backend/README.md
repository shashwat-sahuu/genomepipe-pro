# GenomePipe Pro — Backend API

FastAPI backend for the **GenomePipe Pro** clinical genomics platform.

## Stack
| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Database | SQLite (aiosqlite + SQLAlchemy async) |
| AI | Ollama (offline, local LLM) |
| NCBI Proxy | httpx async — solves browser CORS |
| Annotation | Ensembl VEP REST API |
| Containerisation | Docker + docker-compose |

---

## Quick Start (Docker — recommended)

```bash
# 1. Clone / copy this folder
cd genomepipe-backend

# 2. Start everything (API + Ollama + model pull)
docker compose up -d

# 3. Tail logs
docker compose logs -f api
```

The API will be at **http://localhost:8000**  
Interactive docs at **http://localhost:8000/docs**

> **First run** — Ollama downloads the model (~4 GB for llama3). This takes a few minutes depending on your connection. Check progress with:
> ```bash
> docker compose logs -f ollama-setup
> ```

### Using a biomedical model (recommended for accuracy)
```bash
# Edit docker-compose.yml  OR  set env var:
OLLAMA_MODEL=biomistral docker compose up -d
```

---

## Local Dev (no Docker)

### Prerequisites
- Python 3.11+
- [Ollama installed](https://ollama.com/download)

```bash
# 1. Install Ollama and pull a model
ollama pull llama3
# or: ollama pull biomistral

# 2. Start Ollama with CORS open
OLLAMA_ORIGINS=* ollama serve &

# 3. Create venv and install deps
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — add NCBI_API_KEY if you have one

# 5. Run the server
uvicorn main:app --reload --port 8000
```

---

## API Reference

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check |

### NCBI Proxy `/api/ncbi`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ncbi/clinvar?gene=BRCA1&significance=pathogenic` | ClinVar search |
| GET | `/api/ncbi/pubmed?query=BRCA1+cancer` | PubMed search |
| GET | `/api/ncbi/dbsnp/rs80357906` | dbSNP SNP lookup |
| GET | `/api/ncbi/genbank/search?gene=BRCA1` | GenBank gene search |
| GET | `/api/ncbi/genbank/NM_007294` | GenBank accession fetch |

### Variants `/api/variants`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/variants/` | List variants (filterable) |
| POST | `/api/variants/` | Create variant |
| POST | `/api/variants/batch` | Batch create |
| PATCH | `/api/variants/{id}` | Update variant |
| DELETE | `/api/variants/{id}` | Delete variant |
| DELETE | `/api/variants/` | Clear all |
| POST | `/api/variants/import/vcf` | Import VCF content |
| GET | `/api/variants/export/vcf` | Export as VCF |
| GET | `/api/variants/export/csv` | Export as CSV |

### AI (Ollama) `/api/ai`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ai/status` | Ollama online + model list |
| GET | `/api/ai/models` | Available models |
| POST | `/api/ai/analyze/stream` | **SSE streaming** response |
| POST | `/api/ai/analyze` | Full response (non-streaming) |

**Analysis modes:** `clinical` · `acmg` · `cancer` · `pharma` · `vus` · `qc` · `trio` · `population` · `splicing` · `cnv` · `report` · `chat`

#### Stream example (JavaScript)
```javascript
const response = await fetch('http://localhost:8000/api/ai/analyze/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mode: 'clinical',
    message: 'Interpret BRCA1 c.5266dupC',
    model: 'llama3',
    variants: []          // optional array from My Variants
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  // Parse SSE: "data: <token>\n\n"
  for (const line of chunk.split('\n')) {
    if (line.startsWith('data: ')) {
      const token = line.slice(6);
      if (token === '[DONE]') break;
      process.stdout.write(token);   // or append to UI
    }
  }
}
```

### Pipeline `/api/pipeline`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/pipeline/run` | Start pipeline + stream SSE |
| GET | `/api/pipeline/jobs` | List all jobs |
| GET | `/api/pipeline/jobs/{id}` | Job status |
| GET | `/api/pipeline/jobs/{id}/stream` | Stream existing job |

### Annotation `/api/annotation`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/annotation/vep` | Ensembl VEP consequences |
| POST | `/api/annotation/population-freq` | gnomAD/1000G/ExAC frequencies |
| POST | `/api/annotation/pathogenicity` | SIFT + PolyPhen-2 + integrated verdict |

### Reports `/api/reports`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/generate` | AI-generated clinical report (Ollama) |

---

## Connecting the Frontend

In your `shashwat-sahuu.github.io` frontend, replace direct NCBI fetch calls:

```javascript
// Before (CORS blocked in deployed site):
const res = await fetch(`https://eutils.ncbi.nlm.nih.gov/...`);

// After (route through your backend):
const BASE = 'http://localhost:8000';   // or your deployed URL
const res = await fetch(`${BASE}/api/ncbi/clinvar?gene=${gene}`);
```

For Ollama AI (was connecting to localhost:11434 directly from browser):
```javascript
// Before:
fetch('http://localhost:11434/api/chat', ...)

// After:
fetch('http://localhost:8000/api/ai/analyze/stream', {
  method: 'POST',
  body: JSON.stringify({ mode: 'clinical', message: userMessage, model: 'llama3' })
})
```

---

## Project Structure

```
genomepipe-backend/
├── main.py                  # FastAPI app entry point
├── database.py              # SQLAlchemy async setup
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── models/
│   ├── variant.py           # Variant ORM model
│   ├── pipeline.py          # PipelineJob ORM model
│   └── schemas.py           # Pydantic request/response schemas
│
├── routers/
│   ├── ncbi.py              # /api/ncbi — ClinVar, PubMed, dbSNP, GenBank
│   ├── variants.py          # /api/variants — CRUD + VCF import/export
│   ├── pipeline.py          # /api/pipeline — NGS pipeline + SSE
│   ├── ai.py                # /api/ai — Ollama streaming
│   ├── annotation.py        # /api/annotation — VEP, gnomAD, pathogenicity
│   └── reports.py           # /api/reports — clinical report generation
│
├── services/
│   ├── ncbi_service.py      # Async NCBI E-utilities calls
│   ├── ollama_service.py    # Ollama chat + streaming + mode prompts
│   ├── pipeline_service.py  # Pipeline simulation + real subprocess hooks
│   └── vcf_service.py       # VCF parser
│
└── data/
    └── genomepipe.db        # SQLite database (auto-created)
```

---

## Production Deployment (Railway / Render)

```bash
# Railway
railway login
railway init
railway up

# Set env vars in Railway dashboard:
# NCBI_API_KEY, OLLAMA_URL (point to hosted Ollama), OLLAMA_MODEL
```

> For production, replace SQLite with PostgreSQL by changing `DATABASE_URL` to `postgresql+asyncpg://...` and adding `asyncpg` to requirements.

---

## License
MIT — built by Shashwat Sahu
