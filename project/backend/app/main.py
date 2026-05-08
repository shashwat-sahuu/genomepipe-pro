import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import datetime

logger = logging.getLogger(__name__)

# Track initialization status
_initialized = False
_init_error = None

try:
    from app.config import get_settings, init_upload_dir
    settings = get_settings()
    logger.info("Config loaded successfully")
except Exception as e:
    logger.error(f"Failed to load config: {e}", exc_info=True)
    raise

# Import optional dependencies
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    HAS_SLOWAPI = True
except Exception as e:
    logger.warning(f"slowapi import failed: {e}")
    HAS_SLOWAPI = False

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    HAS_SENTRY = True
except Exception as e:
    logger.warning(f"sentry_sdk import failed: {e}")
    HAS_SENTRY = False

# Import routes - handle failures gracefully
sequence = None
auth = None
upload = None
structure = None

try:
    from app.routes import sequence as seq_router
    sequence = seq_router
    logger.info("Sequence routes imported")
except Exception as e:
    logger.error(f"Failed to import sequence routes: {e}", exc_info=True)

try:
    from app.routes import auth as auth_router
    auth = auth_router
    logger.info("Auth routes imported")
except Exception as e:
    logger.error(f"Failed to import auth routes: {e}", exc_info=True)

try:
    from app.routes import upload as upload_router
    upload = upload_router
    logger.info("Upload routes imported")
except Exception as e:
    logger.error(f"Failed to import upload routes: {e}", exc_info=True)

try:
    from app.routes import structure as structure_router
    structure = structure_router
    logger.info("Structure routes imported")
except Exception as e:
    logger.error(f"Failed to import structure routes: {e}", exc_info=True)

# Import database manager - defer initialization
try:
    from app.models.db_manager import DatabaseManager
    logger.info("DatabaseManager imported successfully")
except Exception as e:
    logger.error(f"Failed to import DatabaseManager: {e}", exc_info=True)
    raise

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade bioinformatics analysis platform",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Initialize Sentry for error tracking (optional)
if HAS_SENTRY:
    try:
        if settings.SENTRY_DSN:
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                integrations=[FastApiIntegration()],
                traces_sample_rate=0.1,
                environment=settings.ENVIRONMENT,
            )
            logger.info("Sentry initialized successfully")
    except Exception as e:
        logger.warning(f"Sentry initialization failed: {e}")

# Startup event - deferred initialization
@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    global _initialized, _init_error
    
    try:
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        
        try:
            # Initialize upload directory
            init_upload_dir()
            logger.info("Upload directory initialized")
        except Exception as e:
            logger.warning(f"Upload directory initialization failed: {e}")
        
        # Initialize database
        try:
            if DatabaseManager:
                DatabaseManager.init_db()
                DatabaseManager.create_tables()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            logger.warning("Continuing without database - some features will be unavailable")
        
        _initialized = True
        logger.info(f"{settings.APP_NAME} started successfully")
    except Exception as e:
        _init_error = str(e)
        logger.error(f"Startup event failed: {e}", exc_info=True)
        # Don't re-raise - allow app to continue running

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info(f"Shutting down {settings.APP_NAME}")
    try:
        # Close database connections if available
        if hasattr(DatabaseManager, 'close'):
            DatabaseManager.close()
    except Exception as e:
        logger.warning(f"Shutdown error: {e}")

# Configure rate limiter (optional)
if HAS_SLOWAPI:
    try:
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        logger.info("Rate limiter configured")
    except Exception as e:
        logger.warning(f"Rate limiter configuration failed: {e}")

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
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request error: {e}", exc_info=True)
        raise

# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/health")
async def api_health_check():
    """API health check endpoint"""
    db_status = "unavailable"
    try:
        session = DatabaseManager.get_session()
        if session:
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
        "initialized": _initialized,
        "error": _init_error,
    }

# Include routers
if sequence:
    try:
        app.include_router(sequence.router, prefix="/api", tags=["Sequence Analysis"])
    except Exception as e:
        logger.warning(f"Failed to include sequence router: {e}")

if auth:
    try:
        app.include_router(auth.router, prefix="/api", tags=["Authentication"])
    except Exception as e:
        logger.warning(f"Failed to include auth router: {e}")

if upload:
    try:
        app.include_router(upload.router, prefix="/api", tags=["Sequences"])
    except Exception as e:
        logger.warning(f"Failed to include upload router: {e}")

if structure:
    try:
        app.include_router(structure.router, prefix="/api", tags=["Structure Prediction"])
    except Exception as e:
        logger.warning(f"Failed to include structure router: {e}")

if any([sequence, auth, upload, structure]):
    logger.info("Routers included successfully")
else:
    logger.warning("No routers were included")

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
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
    )

# Serve static files if available (optional)
try:
    from fastapi.staticfiles import StaticFiles
    static_path = Path(__file__).resolve().parents[2] / "frontend"
    if static_path.exists():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
        logger.info(f"Static files mounted from {static_path}")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

logger.info("Application initialization complete")