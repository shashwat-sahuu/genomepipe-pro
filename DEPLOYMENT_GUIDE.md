# GenomePipe Pro - Deployment & Getting Started Guide

## Quick Start (5 Minutes)

### 1. Clone & Setup
```bash
# Clone repository
git clone https://github.com/your-org/genomepipe-pro.git
cd genomepipe-pro

# Setup environment
cp project/backend/.env.example project/backend/.env

# Edit .env if needed
nano project/backend/.env
```

### 2. Start with Docker
```bash
# Start all services
docker-compose up -d

# Watch logs
docker-compose logs -f backend

# Verify services
docker-compose ps
```

### 3. Initialize Database & Create Admin
```bash
# Create tables
docker-compose exec backend python -m alembic upgrade head

# Create admin user (optional, for testing)
docker-compose exec backend python << 'EOF'
from app.models.db_manager import DatabaseManager
from app.models.database import User
from app.utils.security import SecurityService

db = DatabaseManager.get_session()
admin = User(
    email='admin@example.com',
    username='admin',
    password_hash=SecurityService.hash_password('AdminPass123'),
    is_admin=True
)
db.add(admin)
db.commit()
print("✅ Admin user created: admin@example.com / AdminPass123")
EOF
```

### 4. Access Services
```
API & Docs:    http://localhost:8000/docs
API:           http://localhost:8000/api
Health Check:  http://localhost:8000/health
Flower (Tasks):http://localhost:5555
```

---

## Development Environment

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git
- 4GB RAM (minimum)
- 2GB disk space

### Local Setup (Without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd project/backend
pip install -r requirements.txt

# Setup database
export DATABASE_URL="postgresql://postgres:password@localhost:5432/genomepipe"
python -c "from app.models.db_manager import DatabaseManager; DatabaseManager.create_tables()"

# Start Redis (in another terminal)
redis-server

# Start Celery worker (in another terminal)
celery -A app.services.task_service worker --loglevel=info

# Run FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Testing the API

### 1. Register User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "researcher@example.com",
    "username": "researcher",
    "password": "SecurePass123",
    "full_name": "Dr. Researcher"
  }'
```

### 2. Login (Get JWT)
```bash
RESPONSE=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "researcher@example.com",
    "password": "SecurePass123"
  }')

TOKEN=$(echo $RESPONSE | jq -r '.access_token')
echo "Token: $TOKEN"
```

### 3. Analyze Sequence
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sequence_data": "ATGATGATGATGTAA",
    "job_type": "DNA_ANALYSIS",
    "include_reverse_complement": false,
    "reading_frames": [1, 2, 3]
  }'
```

### 4. Upload FASTA File
```bash
# Create test FASTA file
cat > test.fasta << 'EOF'
>sequence_1
ATGATGATGATGTAA
EOF

# Upload
curl -X POST http://localhost:8000/api/sequences/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.fasta" \
  -F "description=Test sequence"
```

### 5. Predict Protein Structure
```bash
curl -X POST http://localhost:8000/api/structure/quick-predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "protein_sequence": "MKKLAVLSLLSALAAGFEAA"
  }'
```

---

## Production Deployment

### AWS Deployment (ECS + RDS)

#### 1. Create AWS Resources
```bash
# Create RDS PostgreSQL
aws rds create-db-instance \
  --db-instance-identifier genomepipe-prod \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username postgres \
  --master-user-password $(openssl rand -base64 32) \
  --allocated-storage 100

# Create ElastiCache Redis
aws elasticache create-cache-cluster \
  --cache-cluster-id genomepipe-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1

# Create S3 bucket for uploads
aws s3api create-bucket --bucket genomepipe-pro-uploads
```

#### 2. Build & Push Docker Image
```bash
# Build Docker image
docker build -t genomepipe-pro:latest ./project/backend

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

docker tag genomepipe-pro:latest \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/genomepipe-pro:latest

docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/genomepipe-pro:latest
```

#### 3. Deploy to ECS
```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name genomepipe-prod

# Register task definition
aws ecs register-task-definition \
  --family genomepipe-backend \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 256 \
  --memory 512 \
  --container-definitions '[
    {
      "name": "backend",
      "image": "YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/genomepipe-pro:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "hostPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "REDIS_URL", "value": "redis://..."}
      ]
    }
  ]'

# Create service
aws ecs create-service \
  --cluster genomepipe-prod \
  --service-name genomepipe-backend \
  --task-definition genomepipe-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

#### 4. Setup Load Balancer
```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name genomepipe-alb \
  --subnets subnet-xxx subnet-yyy

# Create target group
aws elbv2 create-target-group \
  --name genomepipe-backend \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=...
```

### GCP Deployment (Cloud Run + Cloud SQL)

```bash
# Create Cloud SQL instance
gcloud sql instances create genomepipe-prod \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Deploy to Cloud Run
gcloud run deploy genomepipe-backend \
  --source ./project/backend \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --cpu 1 \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=postgresql://...,REDIS_URL=redis://..."
```

### Kubernetes Deployment

```yaml
# backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: genomepipe-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: genomepipe-backend
  template:
    metadata:
      labels:
        app: genomepipe-backend
    spec:
      containers:
      - name: backend
        image: your-registry/genomepipe-pro:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: genomepipe-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: genomepipe-backend-service
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: genomepipe-backend

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: genomepipe-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: genomepipe-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

Deploy with:
```bash
kubectl apply -f backend-deployment.yaml
```

---

## Monitoring & Maintenance

### Health Checks
```bash
# API health
curl http://localhost:8000/health

# Database health
docker-compose exec backend python -c "
from app.models.db_manager import DatabaseManager
print('DB OK' if DatabaseManager.health_check() else 'DB FAILED')
"

# Celery worker status
docker-compose exec backend celery -A app.services.task_service inspect active
```

### Logs
```bash
# Backend logs
docker-compose logs -f backend

# Celery worker logs
docker-compose logs -f celery_worker

# Flower web UI
open http://localhost:5555
```

### Backup Database
```bash
# Backup
docker-compose exec postgres pg_dump -U postgres genomepipe > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres genomepipe < backup.sql
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Troubleshooting

### Issue: "Connection refused"
```bash
# Check if services are running
docker-compose ps

# Restart failed service
docker-compose restart postgres
docker-compose restart backend
```

### Issue: "Database connection error"
```bash
# Check database URL
echo $DATABASE_URL

# Test connection
docker-compose exec postgres psql -U postgres -c "SELECT 1"
```

### Issue: "Celery task not processing"
```bash
# Check queue
docker-compose exec backend celery -A app.services.task_service inspect active_queues

# Restart worker
docker-compose restart celery_worker
```

### Issue: "Out of memory"
```bash
# Increase Docker memory
# Edit docker-compose.yml or Docker Desktop settings

# Check memory usage
docker stats
```

---

## Performance Tuning

### Database
```sql
-- Create indexes
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_sequence_user_id ON sequences(user_id);
CREATE INDEX idx_job_status ON analysis_jobs(status);

-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM sequences WHERE user_id = 'xxx';
```

### Redis
```bash
# Monitor Redis
redis-cli monitor

# Check memory
redis-cli info memory
```

### FastAPI
```python
# config.py - Increase workers
# For production, use Gunicorn:
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

---

## Security Hardening

### Production Checklist
- [ ] Change all default passwords
- [ ] Update SECRET_KEY to long random string
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall rules
- [ ] Setup VPC/security groups
- [ ] Enable database encryption
- [ ] Enable backups
- [ ] Configure monitoring/alerts
- [ ] Setup log aggregation
- [ ] Enable rate limiting
- [ ] Setup DDoS protection

### Environment Variables
```bash
# Secure your secrets
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
export DATABASE_PASSWORD=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')

# Use secrets manager
# AWS: AWS Secrets Manager
# GCP: Google Cloud Secret Manager
# K8s: Kubernetes Secrets
```

---

## Support & Resources

### Documentation
- API Docs: http://localhost:8000/docs
- Architecture: See `ARCHITECTURE_DETAILED.md`
- Project Summary: See `PROJECT_COMPLETE_SUMMARY.md`

### External APIs
- ESMFold: https://www.esmatlas.com/
- AlphaFold: https://github.com/deepmind/alphafold

### Communities
- FastAPI: https://fastapi.tiangolo.com/
- Bioinformatics: https://biopython.org/
- Docker: https://docs.docker.com/

---

## License

GenomePipe Pro © 2024. All rights reserved.

Built for production use in research, healthcare, and bioinformatics applications.
