"""Vercel serverless handler for FastAPI"""
import sys
import logging
from pathlib import Path

# Set up logging to see errors
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the project backend to the Python path
project_path = Path(__file__).resolve().parents[1] / "project" / "backend"
sys.path.insert(0, str(project_path))

try:
    # Import and export the FastAPI app
    from app.main import app as application
    logger.info("FastAPI app imported successfully")
except Exception as e:
    logger.error(f"Failed to import FastAPI app: {e}", exc_info=True)
    # Create a minimal app if import fails
    from fastapi import FastAPI
    application = FastAPI(title="GenomePipe Pro - Error Mode")
    
    @application.get("/health")
    async def health():
        return {"status": "error", "message": str(e)}

# For Vercel serverless (also export as 'app' for reference)
app = application
__all__ = ["application", "app"]
