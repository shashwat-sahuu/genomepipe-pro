"""Structure prediction and analysis routes"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
import tempfile
import os

from app.models.schemas import (
    StructurePredictionRequest,
    StructurePredictionResponse,
    PDBFileResponse,
)
from app.models.database import StructurePrediction, JobStatus
from app.models.db_manager import get_db
from app.services.structure_service import StructurePredictionService
from app.services.task_service import TaskService
from app.utils.security import SecurityService
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/structure", tags=["Structure Prediction"])


@router.post("/predict", response_model=dict)
async def predict_protein_structure(
    request: StructurePredictionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> dict:
    """
    Predict protein structure using ESMFold API

    Returns a job ID that can be used to check status and download results
    """
    # Validate protein sequence
    if not StructurePredictionService.validate_protein_sequence(request.protein_sequence):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid protein sequence (only standard amino acids allowed)"
        )

    # Check length
    from app.config import get_settings
    settings = get_settings()

    if len(request.protein_sequence) > settings.MAX_PROTEIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Protein sequence too long. Max: {settings.MAX_PROTEIN_LENGTH} amino acids"
        )

    # Get or create demo user
    from app.models.database import User
    demo_user = db.query(User).filter(User.email == "demo@genomepipe.local").first()
    if not demo_user:
        demo_user = User(
            email="demo@genomepipe.local",
            username="demo_user",
            password_hash=SecurityService.hash_password("demo_password_123"),
            full_name="Demo User",
            is_active=True
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)

    # Create prediction record
    prediction = StructurePrediction(
        user_id=demo_user.id,
        protein_sequence=request.protein_sequence,
        model_used=request.model,
        status=JobStatus.PENDING.value,
        meta={"description": request.description}
    )

    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    # Submit background task
    try:
        task_id = TaskService.submit_structure_task(
            prediction_id=prediction.id,
            protein_sequence=request.protein_sequence,
            model=request.model
        )

        prediction.celery_task_id = task_id
        db.commit()

        logger.info(f"Structure prediction submitted: {prediction.id} (Task: {task_id})")

    except Exception as e:
        logger.warning(f"Celery unavailable, completing structure prediction locally: {e}")
        prediction.pdb_data = StructurePredictionService.generate_mock_pdb(
            request.protein_sequence
        )
        prediction.confidence_scores = StructurePredictionService.extract_confidence_scores(
            prediction.pdb_data
        )
        prediction.status = JobStatus.COMPLETED.value
        prediction.completed_at = datetime.utcnow()
        prediction.error_message = None
        task_id = "local_mock"
        db.commit()

    return {
        "prediction_id": prediction.id,
        "task_id": task_id,
        "status": prediction.status,
        "message": "Structure prediction submitted. Check status using prediction_id."
                   if task_id != "local_mock"
                   else "Celery is unavailable locally, so a mock structure was generated immediately.",
        "created_at": prediction.created_at
    }


@router.get("/{prediction_id}/status", response_model=StructurePredictionResponse)
async def get_prediction_status(
    prediction_id: str,
    db: Session = Depends(get_db)
) -> StructurePredictionResponse:
    """
    Get status of structure prediction

    Returns:
        Prediction status and results (if completed)
    """
    # Get demo user
    from app.models.database import User
    demo_user = db.query(User).filter(User.email == "demo@genomepipe.local").first()
    if not demo_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

    prediction = db.query(StructurePrediction).filter(
        StructurePrediction.id == prediction_id,
        StructurePrediction.user_id == demo_user.id
    ).first()

    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )

    # Check Celery task status if still processing
    if prediction.status in [JobStatus.PENDING.value, JobStatus.PROCESSING.value]:
        if prediction.celery_task_id:
            task_status = TaskService.get_task_status(prediction.celery_task_id)

            # Update status from Celery
            if task_status["status"] == "SUCCESS":
                prediction.status = JobStatus.COMPLETED.value
                prediction.completed_at = datetime.utcnow()
                db.commit()
            elif task_status["status"] == "FAILURE":
                prediction.status = JobStatus.FAILED.value
                prediction.error_message = task_status.get("error", "Unknown error")
                prediction.completed_at = datetime.utcnow()
                db.commit()

    return StructurePredictionResponse(
        id=prediction.id,
        status=prediction.status,
        model_used=prediction.model_used,
        created_at=prediction.created_at,
        completed_at=prediction.completed_at,
        pdb_url=f"/api/structure/{prediction.id}/download" if prediction.pdb_data else None,
        confidence_score=prediction.confidence_scores.get("pae_mean") if prediction.confidence_scores else None,
        error_message=prediction.error_message,
    )


@router.get("/{prediction_id}/download")
async def download_pdb_file(
    prediction_id: str,
    db: Session = Depends(get_db)
):
    """
    Download PDB file for completed structure prediction

    Returns:
        PDB file as downloadable attachment
    """
    # Get demo user
    from app.models.database import User
    demo_user = db.query(User).filter(User.email == "demo@genomepipe.local").first()
    if not demo_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

    prediction = db.query(StructurePrediction).filter(
        StructurePrediction.id == prediction_id,
        StructurePrediction.user_id == demo_user.id
    ).first()

    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )

    if prediction.status != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prediction not yet completed. Current status: {prediction.status}"
        )

    if not prediction.pdb_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDB data not available"
        )

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False) as f:
        f.write(prediction.pdb_data)
        temp_path = f.name

    try:
        return FileResponse(
            path=temp_path,
            media_type="application/x-pdb",
            filename=f"structure_{prediction_id}.pdb",
            headers={"Content-Disposition": f"attachment; filename=structure_{prediction_id}.pdb"},
            background=BackgroundTask(os.remove, temp_path),
        )
    except Exception as e:
        logger.error(f"Error downloading PDB file: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading file"
        )


@router.post("/quick-predict")
async def quick_predict_structure(
    protein_sequence: str,
) -> dict:
    """
    Quick synchronous structure prediction using mock data

    For development/testing when ESMFold API is unavailable

    Returns:
        Mock PDB structure data
    """
    # Validate protein sequence
    if not StructurePredictionService.validate_protein_sequence(protein_sequence):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid protein sequence"
        )

    # Generate mock structure
    pdb_data = StructurePredictionService.generate_mock_pdb(protein_sequence)

    return {
        "status": "completed",
        "model": "Mock",
        "pdb_data": pdb_data,
        "note": "This is mock data for development purposes"
    }


@router.get("/list", response_model=list[StructurePredictionResponse])
async def list_predictions(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
) -> list[StructurePredictionResponse]:
    """
    List user's structure predictions

    Parameters:
    - skip: Number of records to skip (pagination)
    - limit: Number of records to return (max 100)
    """
    if limit > 100:
        limit = 100

    # Get demo user
    from app.models.database import User
    demo_user = db.query(User).filter(User.email == "demo@genomepipe.local").first()
    if not demo_user:
        return []

    predictions = db.query(StructurePrediction).filter(
        StructurePrediction.user_id == demo_user.id
    ).offset(skip).limit(limit).all()

    return [
        StructurePredictionResponse(
            id=pred.id,
            status=pred.status,
            model_used=pred.model_used,
            created_at=pred.created_at,
            completed_at=pred.completed_at,
            pdb_url=f"/api/structure/{pred.id}/download" if pred.pdb_data else None,
            confidence_score=pred.confidence_scores.get("pae_mean") if pred.confidence_scores else None,
            error_message=pred.error_message,
        )
        for pred in predictions
    ]
