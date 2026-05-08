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

# Add the project backend to the Python path - handle both local and Vercel environments
try:
    project_path = Path(__file__).resolve().parents[1] / "project" / "backend"
    sys.path.insert(0, str(project_path))
    logger.info(f"Added to sys.path: {project_path}")
except Exception as e:
    logger.warning(f"Could not set up path: {e}")

# Create a minimal FastAPI app first
from fastapi import FastAPI
from fastapi.responses import JSONResponse

application = FastAPI(
    title="GenomePipe Pro",
    version="1.0.0",
    description="Production-grade bioinformatics analysis platform"
)

# Try to import the full app, but fall back to minimal app
try:
    logger.info("Attempting to import FastAPI app...")
    from app.main import app as full_app
    logger.info("✓ FastAPI app imported successfully")
    application = full_app
    
except ImportError as e:
    logger.error(f"❌ ImportError while importing FastAPI app: {e}", exc_info=True)
    
    # Minimal health endpoints for debugging
    @application.get("/health")
    async def health():
        return {"status": "error", "type": "import_error", "message": str(e)}
    
    @application.get("/api/health")
    async def api_health():
        return {"status": "error", "type": "import_error", "message": str(e)}
        
except Exception as e:
    logger.error(f"❌ Failed to import FastAPI app: {e}", exc_info=True)
    
    # Minimal health endpoints
    @application.get("/health")
    async def health():
        return {"status": "error", "type": "runtime_error", "message": str(e)}
    
    @application.get("/api/health")
    async def api_health():
        return {"status": "error", "type": "runtime_error", "message": str(e)}

logger.info("✓ Application handler configured successfully")

# For Vercel serverless
app = application
__all__ = ["app"]
