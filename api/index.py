"""Vercel serverless handler for FastAPI"""
import sys
import os
import logging
from pathlib import Path

# Set up logging to see errors
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")

# Add the project backend to the Python path
project_path = Path(__file__).resolve().parents[1] / "project" / "backend"
sys.path.insert(0, str(project_path))
logger.info(f"Added to sys.path: {project_path}")

try:
    # Import and export the FastAPI app
    logger.info("Attempting to import FastAPI app...")
    from app.main import app as application
    logger.info("✓ FastAPI app imported successfully")
except ImportError as e:
    logger.error(f"❌ ImportError while importing FastAPI app: {e}", exc_info=True)
    from fastapi import FastAPI
    application = FastAPI(title="GenomePipe Pro - Error Mode")
    
    @application.get("/health")
    async def health():
        return {"status": "error", "error": f"ImportError: {e}"}
        
except Exception as e:
    logger.error(f"❌ Failed to import FastAPI app: {e}", exc_info=True)
    # Create a minimal app if import fails
    from fastapi import FastAPI
    application = FastAPI(title="GenomePipe Pro - Error Mode")
    
    @application.get("/health")
    async def health():
        return {"status": "error", "message": str(e)}
    
    @application.get("/api/health")
    async def api_health():
        return {"status": "error", "message": str(e)}

logger.info("✓ Application handler configured successfully")

# For Vercel serverless (also export as 'app' for reference)
app = application
__all__ = ["application", "app"]
