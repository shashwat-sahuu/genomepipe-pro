"""Background task processing with Celery"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from celery import Celery
    from celery.result import AsyncResult
except ImportError:  # Celery is optional for local single-process development.
    Celery = None
    AsyncResult = None

from app.config import get_settings
from app.models.db_manager import DatabaseManager
from app.models.database import AnalysisJob, JobStatus
from app.services.bioinformatics_service import SequenceAnalysisService
from app.services.structure_service import StructurePredictionService

logger = logging.getLogger(__name__)
settings = get_settings()


if Celery:
    celery_app = Celery(
        "genomepipe",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        result_expires=3600,  # 1 hour
    )
else:
    celery_app = None


def celery_task(*args, **kwargs):
    """Return a Celery task decorator when Celery is installed."""
    if celery_app:
        return celery_app.task(*args, **kwargs)
    return lambda fn: fn


class TaskService:
    """Service for managing background tasks"""

    @staticmethod
    def submit_analysis_task(
        job_id: str,
        sequence_data: str,
        job_type: str,
        include_reverse: bool = False,
        reading_frames: Optional[list] = None
    ) -> str:
        """
        Submit analysis task to Celery

        Returns:
            Celery task ID
        """
        if not celery_app:
            raise RuntimeError("Celery is not installed or configured")

        if reading_frames is None:
            reading_frames = [1, 2, 3]

        task = analyze_sequence_task.apply_async(
            args=[job_id, sequence_data, job_type],
            kwargs={
                "include_reverse": include_reverse,
                "reading_frames": reading_frames
            },
            task_id=f"analysis_{job_id}"
        )

        return task.id

    @staticmethod
    def submit_structure_task(
        prediction_id: str,
        protein_sequence: str,
        model: str = "ESMFold"
    ) -> str:
        """
        Submit structure prediction task to Celery

        Returns:
            Celery task ID
        """
        if not celery_app:
            raise RuntimeError("Celery is not installed or configured")

        task = predict_structure_task.apply_async(
            args=[prediction_id, protein_sequence, model],
            task_id=f"structure_{prediction_id}"
        )

        return task.id

    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """Get status of a Celery task"""
        if not celery_app or not AsyncResult:
            return {
                "task_id": task_id,
                "status": "DISABLED",
                "result": None,
                "error": "Celery is not installed or configured",
            }

        result = AsyncResult(task_id, app=celery_app)

        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.status == "SUCCESS" else None,
            "error": str(result.info) if result.status == "FAILURE" else None,
        }

    @staticmethod
    def cancel_task(task_id: str) -> bool:
        """Cancel a Celery task"""
        if not celery_app or not AsyncResult:
            return False

        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True)
        return True


# Celery tasks
@celery_task(bind=True)
def analyze_sequence_task(
    self,
    job_id: str,
    sequence_data: str,
    job_type: str,
    include_reverse: bool = False,
    reading_frames: Optional[list] = None
):
    """Background task for sequence analysis"""
    if reading_frames is None:
        reading_frames = [1, 2, 3]

    db = DatabaseManager.get_session()

    try:
        # Update job status to PROCESSING
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = JobStatus.PROCESSING.value
            job.started_at = datetime.utcnow()
            job.celery_task_id = self.request.id
            db.commit()

        # Perform analysis
        self.update_state(state='PROGRESS', meta={'progress': 25})

        analysis = SequenceAnalysisService.comprehensive_analysis(
            dna_sequence=sequence_data,
            include_reverse=include_reverse,
            reading_frames=reading_frames
        )

        self.update_state(state='PROGRESS', meta={'progress': 75})

        # Update job with results
        if job:
            job.result_json = analysis
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            job.progress_percentage = 100
            db.commit()

        self.update_state(state='PROGRESS', meta={'progress': 100})

        return {
            "status": "completed",
            "job_id": job_id,
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"Analysis task failed: {e}", exc_info=True)

        if job:
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()

        raise

    finally:
        db.close()


@celery_task(bind=True)
async def predict_structure_task(
    self,
    prediction_id: str,
    protein_sequence: str,
    model: str = "ESMFold"
):
    """Background task for structure prediction"""
    from app.models.database import StructurePrediction

    db = DatabaseManager.get_session()

    try:
        # Update prediction status
        prediction = db.query(StructurePrediction).filter(
            StructurePrediction.id == prediction_id
        ).first()

        if prediction:
            prediction.status = JobStatus.PROCESSING.value
            prediction.celery_task_id = self.request.id
            db.commit()

        self.update_state(state='PROGRESS', meta={'progress': 25})

        # Perform prediction
        result = await StructurePredictionService.predict_structure_esmatlas(
            protein_sequence,
            timeout=300
        )

        self.update_state(state='PROGRESS', meta={'progress': 75})

        # Update prediction with results
        if prediction:
            prediction.pdb_data = result["pdb_data"]
            prediction.confidence_scores = result["confidence_scores"]
            prediction.status = JobStatus.COMPLETED.value
            prediction.completed_at = datetime.utcnow()
            db.commit()

        self.update_state(state='PROGRESS', meta={'progress': 100})

        return {
            "status": "completed",
            "prediction_id": prediction_id,
            "result": result
        }

    except Exception as e:
        logger.error(f"Structure prediction task failed: {e}", exc_info=True)

        if prediction:
            prediction.status = JobStatus.FAILED.value
            prediction.error_message = str(e)
            prediction.completed_at = datetime.utcnow()
            db.commit()

        raise

    finally:
        db.close()
