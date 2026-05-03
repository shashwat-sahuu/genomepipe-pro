"""Vercel serverless handler for FastAPI"""
import sys
from pathlib import Path

# Add the project backend to the Python path
project_path = Path(__file__).resolve().parents[1] / "project" / "backend"
sys.path.insert(0, str(project_path))

# Import and export the FastAPI app
from app.main import app

# For Vercel serverless
__all__ = ["app"]
