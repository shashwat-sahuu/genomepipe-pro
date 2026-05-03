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
from app.routes import sequence, auth, upload, structure
from app.models.schemas import ErrorResponse
from app.models.db_manager import DatabaseManager

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

# Initialize database - handle connection failures gracefully
try:
    DatabaseManager.create_tables()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.warning(f"Database initialization failed: {e}")
    logger.warning("Continuing without database - some features will be unavailable")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade bioinformatics analysis platform",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info(f"Shutting down {settings.APP_NAME}")
    DatabaseManager.close()

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

# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

@app.get("/api/health")
async def api_health_check():
    """API health check endpoint"""
    db_status = "ok"
    try:
        from app.models.db_manager import DatabaseManager
        # Try to get a session to verify database connectivity
        DatabaseManager.get_session()
        db_status = "ok"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        db_status = "unavailable"
    
    return {
        "status": "ok",
        "database": db_status,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

# Include routers
app.include_router(sequence.router, prefix="/api", tags=["Sequence Analysis"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(upload.router, prefix="/api", tags=["Sequences"])
app.include_router(structure.router, prefix="/api", tags=["Structure Prediction"])

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
    """Health check endpoint with system status"""
    db_status = "healthy" if DatabaseManager.health_check() else "unhealthy"

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }

# API information endpoint
@app.get("/api/info")
async def api_info():
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
    static_path = Path(__file__).resolve().parents[2] / "frontend"
    if static_path.exists():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")
