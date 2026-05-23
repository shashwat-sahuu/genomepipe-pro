from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from database import get_db
from models.schemas import PipelineRunRequest, PipelineJobOut
from services.pipeline_service import (
    create_job, get_job, list_jobs, run_pipeline_simulation
)

router = APIRouter()


@router.post("/run")
async def start_pipeline(
    req: PipelineRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a pipeline job and stream live progress as SSE events.
    Connect with:  EventSource('/api/pipeline/run', { method: 'POST', body: ... })
    or use /api/pipeline/run/{job_id}/stream after creating the job via /api/pipeline/jobs.
    """
    job = await create_job(db, req)

    async def event_stream():
        async for chunk in run_pipeline_simulation(db, job.job_id, req):
            yield chunk
        # Send a final keep-alive then close
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Job-Id": job.job_id,
        },
    )


@router.post("/jobs", response_model=PipelineJobOut, status_code=201)
async def create_pipeline_job(
    req: PipelineRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a job record without starting it (for polling-based clients)."""
    job = await create_job(db, req)
    return job


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stream progress of an existing job via SSE.
    Frontend: const es = new EventSource(`/api/pipeline/jobs/${jobId}/stream`)
    """
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    # Re-run the simulation attached to the existing job record
    req = PipelineRunRequest(
        sample_id=job.sample_id,
        patient_id=job.patient_id,
        aligner=job.aligner or "BWA-MEM2",
        caller=job.caller or "GATK HaplotypeCaller 4.4",
        reference=job.reference or "GRCh38",
    )

    async def event_stream():
        async for chunk in run_pipeline_simulation(db, job_id, req):
            yield chunk
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs", response_model=list[PipelineJobOut])
async def get_all_jobs(db: AsyncSession = Depends(get_db)):
    return await list_jobs(db)


@router.get("/jobs/{job_id}", response_model=PipelineJobOut)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return job
