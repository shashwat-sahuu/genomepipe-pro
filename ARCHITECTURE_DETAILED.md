# GenomePipe Pro - Production Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Client Layer (Frontend)                         │
│                  (Vue.js/React on Vercel CDN)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                ┌────────────▼─────────────┐
                │   API Gateway / Proxy    │
                │   (Rate Limiting)        │
                └────────────┬─────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
    ┌────────────┐    ┌──────────────┐    ┌──────────────┐
    │  FastAPI   │    │   FastAPI    │    │   FastAPI    │
    │  Backend   │    │   Backend    │    │   Backend    │
    │ Instance 1 │    │ Instance 2   │    │ Instance N   │
    └─────┬──────┘    └──────┬───────┘    └──────┬───────┘
          │                  │                    │
          └──────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬──────────────────┐
        │                    │                    │                  │
        ▼                    ▼                    ▼                  ▼
    ┌─────────────┐  ┌──────────────┐   ┌────────────────┐  ┌──────────────┐
    │ PostgreSQL  │  │    Redis     │   │  Celery Queue  │  │   S3/Cloud   │
    │  Database   │  │    Cache     │   │  (Background)  │  │   Storage    │
    └─────────────┘  └──────────────┘   └────────────────┘  └──────────────┘
        │
        ▼
    ┌─────────────────────────────────┐
    │  External APIs (Optional)       │
    │  - ESMFold API                  │
    │  - AlphaFold API                │
    │  - Sentry (Error Tracking)      │
    └─────────────────────────────────┘
```

## Core Components

### 1. FastAPI Backend (`/project/backend/`)

**Purpose**: RESTful API for bioinformatics sequence analysis

**Structure**:
```
app/
├── main.py              # Application entry point
├── config.py            # Configuration management
├── models/
│   ├── database.py      # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic request/response models
│   └── db_manager.py    # Database connection pooling
├── routes/
│   ├── auth.py          # Authentication endpoints
│   ├── sequence.py      # Sequence analysis endpoints
│   ├── upload.py        # File upload endpoints
│   └── structure.py     # Structure prediction endpoints
├── services/
│   ├── bioinformatics_service.py    # Core biology logic
│   ├── structure_service.py         # Protein structure prediction
│   └── task_service.py              # Background job management
└── utils/
    ├── security.py      # JWT & password utilities
    └── file_handler.py  # FASTA/FASTQ parsing
```

### 2. Database Layer

**PostgreSQL** (Production)
- User management (registration, auth, roles)
- Sequence storage (DNA, RNA, Protein sequences)
- Analysis jobs (tracking, results, status)
- Structure predictions (models, confidence scores)

**Schema**:
```
┌─────────────────────────────────────────────────────────┐
│                        users                             │
├─────────────────────────────────────────────────────────┤
│ id (UUID) | email | username | password_hash | is_admin │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴──────────────┐
        ▼                           ▼
    ┌────────────────┐      ┌──────────────────┐
    │  sequences     │      │  analysis_jobs   │
    ├────────────────┤      ├──────────────────┤
    │ id | user_id  │      │ id | user_id     │
    │ sequence_data │      │ job_type | status│
    │ gc_content    │      │ result_json      │
    └────────────────┘      └────────┬─────────┘
                                     │
                    ┌────────────────┴──────────────┐
                    ▼                               ▼
            ┌────────────────────┐      ┌──────────────────────┐
            │ structure_predictions        ├──────────────────────┤
            ├────────────────────┤      │ id | user_id         │
            │ id | user_id      │      │ protein_sequence     │
            │ pdb_data | status │      │ pdb_data | model_used│
            └────────────────────┘      └──────────────────────┘
```

### 3. Task Processing (Celery + Redis)

**Flow**:
```
Client Request
      │
      ├──► FastAPI Handler
      │         │
      │         ├──► Create Database Record (PENDING)
      │         │
      │         └──► Submit Celery Task
      │                 │
      │                 ▼
      │         ┌─────────────────┐
      │         │  Redis Queue    │
      │         │  (Task Broker)  │
      │         └────────┬────────┘
      │                  │
      │                  ▼
      │         ┌─────────────────┐
      │         │ Celery Worker   │
      │         │ (Processing)    │
      │         └────────┬────────┘
      │                  │
      │                  ▼
      │         Update Database (COMPLETED/FAILED)
      │
      └──► Poll Status Endpoint
            ├──► Check Celery Status
            └──► Return Updated Status
```

### 4. Authentication & Security

**JWT Flow**:
```
POST /api/auth/login
    ├─ Verify credentials
    ├─ Create access token (30 min expiry)
    ├─ Create refresh token (7 day expiry)
    └─ Return both tokens

Protected Endpoint:
    ├─ Extract JWT from Authorization header
    ├─ Verify signature and expiry
    ├─ Load user context
    └─ Process request
```

**Password Security**:
- Bcrypt hashing with salt
- Minimum requirements: 8 chars, 1 uppercase, 1 digit
- No plaintext storage

## API Endpoints

### Authentication
```
POST   /api/auth/register        Register new user
POST   /api/auth/login           Login (returns JWT tokens)
POST   /api/auth/refresh         Refresh access token
GET    /api/auth/me              Get current user info
POST   /api/auth/logout          Logout (client-side token invalidation)
```

### Sequence Analysis
```
POST   /api/analyze              Full DNA analysis pipeline
POST   /api/translate            DNA to protein translation
POST   /api/find-orfs            Find open reading frames
GET    /api/gc-content           Calculate GC content
POST   /api/restriction-sites    Find restriction enzyme sites
POST   /process                  Legacy endpoint (backward compatible)
```

### File Upload
```
POST   /api/sequences/upload     Upload FASTA/FASTQ file
GET    /api/sequences/list       List user's sequences
GET    /api/sequences/{id}       Get sequence details
DELETE /api/sequences/{id}       Delete sequence
```

### Structure Prediction
```
POST   /api/structure/predict    Submit structure prediction job
GET    /api/structure/{id}/status    Get prediction status
GET    /api/structure/{id}/download  Download PDB file
POST   /api/structure/quick-predict  Quick mock prediction
GET    /api/structure/list       List user's predictions
```

## Deployment Architecture

### Development (Local)
```
Docker Compose:
├─ PostgreSQL (5432)
├─ Redis (6379)
├─ FastAPI Backend (8000)
├─ Celery Worker
└─ Flower Monitoring (5555)
```

### Production (AWS/GCP)

```
┌─────────────────────────────────────────────────────────┐
│                   CDN (CloudFront/Cloudflare)            │
│                   Frontend Distribution                  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Load Balancer (ALB/NLB)                     │
│           Rate Limiting, SSL/TLS Termination             │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│ ECS Task 1 │ │ ECS Task 2 │ │ ECS Task N │
│ (Backend)  │ │ (Backend)  │ │ (Backend)  │
└────────────┘ └────────────┘ └────────────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
        ┌────────────┼───────────────┐
        │            │               │
        ▼            ▼               ▼
    ┌────────┐  ┌─────────┐  ┌──────────────┐
    │   RDS  │  │ ElastiC │  │    S3        │
    │(PostgreSQL) │ Cache  │  │ (File Store) │
    └────────┘  │ (Redis) │  └──────────────┘
                └─────────┘
                     │
        ┌────────────┴──────────────┐
        ▼                           ▼
    ┌──────────────┐        ┌──────────────┐
    │ SQS/SNS      │        │ CloudWatch   │
    │ (Task Queue) │        │ (Monitoring) │
    └──────────────┘        └──────────────┘
```

## Scalability Considerations

1. **Horizontal Scaling**:
   - Multiple FastAPI instances behind load balancer
   - Stateless design enables easy scaling
   - Database connection pooling

2. **Caching Strategy**:
   - Redis cache for frequently accessed data
   - Sequence analysis results cached for 1 hour
   - User data cached with TTL

3. **Background Jobs**:
   - Long-running analyses offloaded to Celery workers
   - Multiple worker instances for parallelization
   - Job queuing prevents system overload

4. **Database**:
   - Connection pooling (20 connections, max overflow 40)
   - Query optimization with indexes
   - Replication for high availability

## Security Architecture

1. **API Security**:
   - Rate limiting (100 req/min unauthenticated, 1000 authenticated)
   - JWT token-based authentication
   - CORS middleware for cross-origin requests

2. **Data Protection**:
   - TLS/SSL for all communications
   - Bcrypt password hashing
   - SQL injection prevention (parameterized queries)

3. **Infrastructure**:
   - VPC isolation
   - Security groups/firewalls
   - Encrypted secrets management

4. **Monitoring**:
   - Sentry for error tracking
   - CloudWatch/DataDog for metrics
   - Access logging

## Performance Targets

- API Response Time: < 200ms (p99)
- Structure Prediction: 30-60s (depends on protein length)
- Database Query: < 50ms
- Cache Hit Rate: > 80%
- Uptime: 99.99%

## CI/CD Pipeline

```
GitHub Commit
    │
    ├─► Lint & Format Checks
    ├─► Unit Tests
    ├─► Integration Tests
    ├─► Security Scans (Trivy)
    ├─► Build Docker Image
    ├─► Push to Container Registry
    ├─► Deploy to Staging
    └─► Deploy to Production (after approval)
```
