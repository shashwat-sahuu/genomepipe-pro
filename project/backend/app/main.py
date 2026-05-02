import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.config import get_settings, init_upload_dir
from app.routes import sequence
from app.models.schemas import ErrorResponse

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Sentry for error tracking
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
    )

# Initialize upload directory
init_upload_dir()

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade bioinformatics analysis platform",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# Include routers
app.include_router(sequence.router, prefix="/api", tags=["Sequence Analysis"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all exceptions with consistent error response"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status_code": 500,
            "error_type": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "timestamp": str(__import__("datetime").datetime.utcnow()),
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }

# Root endpoint
@app.get("/")
async def root():
    """API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Advanced bioinformatics analysis platform",
        "docs": "/docs",
        "health": "/health",
    }

# Serve static files if available
try:
    static_path = Path(__file__).resolve().parents[3] / "frontend"
    if static_path.exists():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")
