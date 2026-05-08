"""Vercel serverless handler for FastAPI"""
import sys
import os
import logging
from pathlib import Path

# Set up logging to see errors
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Available Python paths: {sys.path[:3]}")

# Create a minimal FastAPI app first
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    application = FastAPI(
        title="GenomePipe Pro",
        version="1.0.0",
        description="Production-grade bioinformatics analysis platform"
    )
    logger.info("✓ FastAPI imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import FastAPI: {e}", exc_info=True)
    raise

# Add the project backend to the Python path
try:
    project_path = Path(__file__).resolve().parents[1] / "project" / "backend"
    if project_path.exists():
        sys.path.insert(0, str(project_path))
        logger.info(f"Added to sys.path: {project_path}")
    else:
        logger.warning(f"Project path does not exist: {project_path}")
except Exception as e:
    logger.warning(f"Could not set up path: {e}")

# Try to import the full app, but fall back to minimal app
try:
    logger.info("Attempting to import app.config...")
    from app.config import get_settings
    settings = get_settings()
    logger.info("✓ Config imported successfully")
    
    logger.info("Attempting to import FastAPI app...")
    from app.main import app as full_app
    logger.info("✓ FastAPI app imported successfully")
    application = full_app
    
except ImportError as e:
    logger.error(f"❌ ImportError: {e}", exc_info=True)
    
    # Add minimal health endpoints for debugging
    @application.get("/health")
    async def health():
        return {"status": "error", "type": "import_error", "message": str(e)}
    
    @application.get("/api/health")
    async def api_health():
        return {"status": "error", "type": "import_error", "message": str(e)}
        
except Exception as e:
    logger.error(f"❌ Unexpected error: {e}", exc_info=True)
    
    # Add minimal health endpoints
    @application.get("/health")
    async def health():
        return {"status": "error", "type": "runtime_error", "message": str(e)}
    
    @application.get("/api/health")
    async def api_health():
        return {"status": "error", "type": "runtime_error", "message": str(e)}

logger.info("✓ Application handler configured successfully")

# For Vercel serverless
app = application
