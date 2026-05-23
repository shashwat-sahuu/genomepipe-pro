# 🧬 GenomePipe Pro - Clinical Genomics Platform

A comprehensive, production-ready platform for variant analysis, clinical annotation, and genomic interpretation using modern web technologies and AI-powered analysis.

**Status**: ✅ Fully integrated frontend + backend | 🚀 Ready to deploy

---

## 📁 Project Structure

```
genomepipe-pro/
├── backend/                    # FastAPI REST API
│   ├── main.py                # Application entry point
│   ├── database.py            # SQLAlchemy & database setup
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile             # Container configuration
│   ├── docker-compose.yml     # Multi-service orchestration
│   ├── models/                # Data models & schemas
│   ├── routers/               # API endpoints (6 routers)
│   ├── services/              # Business logic services
│   ├── data/                  # Local database files
│   └── README.md              # Backend documentation
│
├── frontend/                   # Vanilla JavaScript SPA
│   ├── index.html             # Main application (6600+ lines)
│   ├── api.js                 # API client library
│   ├── init.js                # Frontend initialization
│   ├── INTEGRATION.md         # Integration guide
│   └── .gitignore
│
├── .gitignore                 # Root .gitignore
└── README.md                  # This file
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.9+** with FastAPI
- **Node.js** (optional, not required for vanilla JS frontend)
- **Git** for version control
- **Ollama** (optional, for AI features)

### 1. Start the Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Backend will be available at**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/`

### 2. Start Ollama AI (Optional)

```bash
# Install from https://ollama.com/download
ollama serve

# In another terminal, pull a model:
ollama pull llama3  # or biomistral for biomedical tasks
```

**Ollama will be available at**: `http://localhost:11434`

### 3. Open the Frontend

```bash
# Open directly in browser:
start frontend/index.html

# Or serve with Python:
cd frontend
python -m http.server 8001
# Visit: http://localhost:8001
```

---

## 📋 Backend API Overview

### FastAPI Server
- **Framework**: FastAPI (async Python web framework)
- **Database**: SQLAlchemy ORM with SQLite
- **Middleware**: CORS (enabled for all origins in dev), GZip compression
- **Real-time**: Server-Sent Events (SSE) for streaming responses

### 6 Specialized Routers

#### 1. **NCBI Router** (`/api/ncbi/`)
NCBI E-utilities proxy to overcome CORS limitations
- `GET /clinvar` - Search ClinVar variants
- `GET /pubmed` - Search PubMed literature
- `GET /dbsnp/{rsid}` - Lookup SNP by rsID
- `GET /genbank/search` - Search GenBank genes
- `GET /genbank/{accession}` - Fetch GenBank record

#### 2. **Variants Router** (`/api/variants/`)
Variant CRUD operations with database persistence
- `GET /` - List variants with filters
- `POST /` - Create variant
- `POST /batch` - Create multiple variants
- `GET /{id}` - Retrieve variant
- `PATCH /{id}` - Update variant
- `DELETE /{id}` - Delete variant

#### 3. **Annotation Router** (`/api/annotation/`)
VEP and pathogenicity predictions
- `POST /vep` - Ensembl VEP consequence prediction
- `POST /popfreq` - Population frequency lookup
- `POST /pathogenicity` - Multi-tool pathogenicity scoring

#### 4. **AI Router** (`/api/ai/`)
Ollama LLM integration for clinical analysis
- `GET /status` - Check Ollama availability
- `POST /analyze/stream` - Stream AI analysis via SSE

#### 5. **Pipeline Router** (`/api/pipeline/`)
NGS pipeline execution with real-time monitoring
- `POST /run` - Execute pipeline with SSE streaming
- `POST /jobs` - Create pipeline job
- `GET /jobs/{id}/stream` - Monitor job progress

#### 6. **Reports Router** (`/api/reports/`)
Clinical report generation
- `POST /generate` - Generate CAP/CLIA-style clinical report

---

## 🎨 Frontend Architecture

### Vanilla JavaScript SPA
- **No framework dependencies** - Pure JavaScript
- **Single-page application** - Fast, responsive navigation
- **12+ pages** for different genomic analyses
- **6,600+ lines** of well-organized code
- **CSS design system** with 100+ variables for theming

### Key Pages

| Page | Purpose |
|------|---------|
| **ClinVar** | Search clinical variant database |
| **PubMed** | Search biomedical literature |
| **GenBank** | Search gene sequences |
| **dbSNP** | Lookup SNP information |
| **My Variants** | Personal variant library |
| **Workbench** | Active variant analysis |
| **AI Analysis** | AI-powered clinical interpretation |
| **Annotation** | VEP & pathogenicity prediction |
| **Reports** | Generate clinical reports |
| **Pipeline** | NGS data processing |
| **Compare** | Multi-variant comparison |
| **Pathway** | Gene pathway analysis |

### External Libraries
- **IGV.js v2.15.5** - Genome browser visualization
- **jsPDF v2.5.1** - PDF report generation

---

## 🔌 API Integration

### api.js - Complete Client Library
The `frontend/api.js` file provides clean, async/await-based access to all backend endpoints:

```javascript
// Import in HTML:
<script src="api.js"></script>

// Use in JavaScript:
const results = await API.searchClinVar('BRCA1', 'H1047R', 'pathogenic', 50);
const variants = await API.listVariants({ workbench: 0 });
await API.createVariant({ chromosome: 'chr17', position: 43044295, ... });
```

### Features
- ✅ Error handling with try-catch
- ✅ Caching (LRU with 5-min TTL)
- ✅ Retry logic for failed requests
- ✅ Streaming support (SSE) for long-running operations
- ✅ CORS-safe NCBI proxy
- ✅ Global `window.API` namespace

---

## 🔧 Configuration

### Backend Configuration

**Environment Variables** (in `backend/.env`):
```env
DATABASE_URL=sqlite:///./data/genomepipe.db
NCBI_API_KEY=your_ncbi_api_key
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

**Get an NCBI API Key**:
- Register at https://www.ncbi.nlm.nih.gov/account/
- Improves rate limits: 3/sec → 10/sec

### Frontend Configuration

**Browser localStorage**:
```javascript
localStorage.setItem('gp_api_url', 'http://localhost:8000');
localStorage.setItem('gp_ncbi_key', 'your_ncbi_key');
localStorage.setItem('gp_ollama_url', 'http://localhost:11434');
localStorage.setItem('gp_ollama_model', 'llama3');
```

Or configure in **Settings → API Keys** page in the app.

---

## 🐳 Docker Deployment

### Build and Run with Docker Compose

```bash
cd backend
docker-compose up -d
```

This starts:
- FastAPI backend on port 8000
- SQLite database (persisted)
- All required services

**Access the app**:
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Frontend: Open `frontend/index.html` in browser

---

## 📊 Database Schema

### Variants Table
```sql
CREATE TABLE variant (
    id INTEGER PRIMARY KEY,
    chromosome TEXT,
    position INTEGER,
    ref TEXT,
    alt TEXT,
    gene TEXT,
    significance TEXT,
    workbench INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### Pipeline Jobs Table
```sql
CREATE TABLE pipeline_job (
    id TEXT PRIMARY KEY,
    status TEXT,
    progress REAL,
    results JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

---

## 🧪 Testing the Connection

**Test in browser console**:
```javascript
// Check backend health
await API.checkBackendHealth()
// Expected: {online: true, version: "4.0.0"}

// Check Ollama AI
await API.checkOllamaStatus()
// Expected: {online: true, models: [...]}

// Try a ClinVar search
const results = await API.searchClinVar('BRCA1', null, 'pathogenic', 10)
// Shows real NCBI results
```

---

## 🚨 Troubleshooting

### Backend not connecting
```javascript
await API.checkBackendHealth()
// Should return {online: true}
```
**Solutions**:
1. Ensure backend is running: `uvicorn main:app --reload`
2. Check port 8000 is not blocked
3. Verify `api.js` has correct API_BASE URL
4. Check browser console for CORS errors

### Ollama not responding
```javascript
await API.checkOllamaStatus()
// Should return {online: true, models: [...]}
```
**Solutions**:
1. Start Ollama: `ollama serve`
2. Pull a model: `ollama pull llama3`
3. Verify URL in settings (default: `http://localhost:11434`)

### NCBI APIs timing out
- Make sure you're not in a restricted network/sandbox
- Add NCBI API key in Settings for better rate limits
- Check NCBI status at https://www.ncbi.nlm.nih.gov/

---

## 📈 Development Workflow

### Making Changes

**Backend changes**:
```bash
cd backend
git add .
git commit -m "Feature: Add new endpoint"
git push
```

**Frontend changes**:
```bash
cd frontend
git add .
git commit -m "Feature: Add new UI page"
git push
```

**Entire repo**:
```bash
git add .
git commit -m "Feature: Update both frontend and backend"
git push
```

---

## 📦 Dependencies

### Backend (`requirements.txt`)
- fastapi - Web framework
- uvicorn - ASGI server
- sqlalchemy - ORM
- requests - HTTP client
- aiohttp - Async HTTP client
- pydantic - Data validation

### Frontend
- Vanilla JavaScript (no npm required)
- IGV.js - Genome visualization
- jsPDF - PDF generation

---

## 🔐 Security Notes

⚠️ **Development Mode** (Current State):
- CORS enabled for all origins (`allow_origins=["*"]`)
- Debug mode active

✅ **For Production**:
1. Restrict CORS to your domain:
   ```python
   allow_origins=["https://yourdomain.com"]
   ```
2. Use HTTPS/SSL certificates
3. Add authentication (JWT, OAuth)
4. Use environment variables for secrets
5. Enable HTTPS in docker-compose.yml
6. Use strong database passwords
7. Add rate limiting

---

## 🎓 Learning Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/
- **NCBI E-utilities**: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- **Ensembl VEP**: https://useast.ensembl.org/info/docs/tools/vep/index.html
- **Ollama**: https://ollama.com/

---

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes in `backend/` or `frontend/`
3. Test thoroughly
4. Commit with clear messages
5. Push and create pull request

---

## 📄 License

This project is provided as-is for educational and research purposes.

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review API documentation at `http://localhost:8000/docs`
3. Check browser console for JavaScript errors
4. Review server logs for backend errors

---

## 🎉 What's Next?

- [ ] Deploy to cloud (AWS, Azure, GCP)
- [ ] Add user authentication & multi-tenancy
- [ ] Implement advanced filtering & searching
- [ ] Add multi-user collaboration features
- [ ] Create mobile app version
- [ ] Add bioinformatics tool integrations
- [ ] Implement genomic data import/export formats
- [ ] Add advanced variant prediction models
- [ ] Create admin dashboard
- [ ] Set up CI/CD pipeline

---

**Built with ❤️ for clinical genomics** | **v4.0.0** | **May 2026**
