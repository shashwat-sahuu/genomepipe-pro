"""
NGS Pipeline Service.
Simulates a realistic FASTQ → alignment → variant-calling pipeline with
live progress updates. In production, swap the simulation blocks with
real subprocess calls to BWA-MEM2, GATK, DeepVariant, etc.
"""
import asyncio
import random
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.pipeline import PipelineJob
from models.schemas import PipelineRunRequest

# Realistic variant pool for simulation
SIMULATED_VARIANTS = [
    {"chr": "chr17", "pos": 43044295, "ref": "A",  "alt": "T",  "gene": "BRCA1", "type": "SNV",  "cadd": 28.4, "sig": "Pathogenic",            "consequence": "stop_gained"},
    {"chr": "chr13", "pos": 32340300, "ref": "GT", "alt": "G",  "gene": "BRCA2", "type": "DEL",  "cadd": 35.0, "sig": "Pathogenic",            "consequence": "frameshift_variant"},
    {"chr": "chr7",  "pos": 140453136,"ref": "A",  "alt": "T",  "gene": "BRAF",  "type": "SNV",  "cadd": 33.0, "sig": "Pathogenic",            "consequence": "missense_variant"},
    {"chr": "chr17", "pos": 7577538,  "ref": "C",  "alt": "T",  "gene": "TP53",  "type": "SNV",  "cadd": 29.5, "sig": "Likely pathogenic",     "consequence": "missense_variant"},
    {"chr": "chr3",  "pos": 178936091,"ref": "A",  "alt": "G",  "gene": "PIK3CA","type": "SNV",  "cadd": 25.1, "sig": "Pathogenic",            "consequence": "missense_variant"},
    {"chr": "chr12", "pos": 25398284, "ref": "C",  "alt": "A",  "gene": "KRAS",  "type": "SNV",  "cadd": 31.2, "sig": "Pathogenic",            "consequence": "missense_variant"},
    {"chr": "chr10", "pos": 89692905, "ref": "G",  "alt": "A",  "gene": "PTEN",  "type": "SNV",  "cadd": 26.8, "sig": "Likely pathogenic",     "consequence": "missense_variant"},
    {"chr": "chr2",  "pos": 47702381, "ref": "C",  "alt": "T",  "gene": "MSH2",  "type": "SNV",  "cadd": 22.3, "sig": "Uncertain significance", "consequence": "missense_variant"},
    {"chr": "chr5",  "pos": 112175770,"ref": "G",  "alt": "A",  "gene": "APC",   "type": "SNV",  "cadd": 18.5, "sig": "Benign",                "consequence": "synonymous_variant"},
    {"chr": "chr6",  "pos": 7541871,  "ref": "T",  "alt": "C",  "gene": "DSP",   "type": "SNV",  "cadd": 12.1, "sig": "Likely benign",         "consequence": "intron_variant"},
    {"chr": "chr11", "pos": 5246696,  "ref": "A",  "alt": "T",  "gene": "HBB",   "type": "SNV",  "cadd": 32.0, "sig": "Pathogenic",            "consequence": "missense_variant"},
    {"chr": "chr1",  "pos": 45508445, "ref": "C",  "alt": "G",  "gene": "MUTYH", "type": "SNV",  "cadd": 16.4, "sig": "Uncertain significance", "consequence": "missense_variant"},
]


PIPELINE_STEPS = [
    (5,  "📂 Loading FASTQ reads"),
    (12, "🔍 Quality control — FastQC"),
    (18, "✂️  Adapter trimming — Trimmomatic"),
    (30, "🗺  Read alignment — {aligner}"),
    (40, "🔧 Coordinate sorting — samtools sort"),
    (50, "📋 Duplicate marking — Picard MarkDuplicates"),
    (58, "📊 Base quality score recalibration — BQSR"),
    (65, "📈 Coverage analysis — samtools depth"),
    (75, "🧬 Variant calling — {caller}"),
    (83, "🔬 Variant filtration — VQSR / hard filters"),
    (88, "🏷  Variant annotation — VEP / CADD"),
    (93, "🌍 Population frequency lookup — gnomAD"),
    (97, "🏥 ClinVar significance tagging"),
    (100,"✅ Pipeline complete"),
]


async def create_job(db: AsyncSession, req: PipelineRunRequest) -> PipelineJob:
    job = PipelineJob(
        job_id=str(uuid.uuid4())[:8].upper(),
        sample_id=req.sample_id,
        patient_id=req.patient_id or "",
        aligner=req.aligner,
        caller=req.caller,
        reference=req.reference,
        status="queued",
        progress=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: str) -> PipelineJob | None:
    result = await db.execute(select(PipelineJob).where(PipelineJob.job_id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(db: AsyncSession) -> list:
    result = await db.execute(
        select(PipelineJob).order_by(PipelineJob.created_at.desc()).limit(50)
    )
    return result.scalars().all()


async def run_pipeline_simulation(
    db: AsyncSession,
    job_id: str,
    req: PipelineRunRequest,
) -> AsyncIterator[str]:
    """
    Simulates the pipeline with realistic metrics and yields SSE progress events.
    Replace each step body with real subprocess calls in production.
    """
    start_time = datetime.now(timezone.utc)
    logs = []

    async def _update(progress: int, status: str = "running", **kwargs):
        job = await get_job(db, job_id)
        if not job:
            return
        job.progress = progress
        job.status = status
        job.elapsed_sec = int((datetime.now(timezone.utc) - start_time).total_seconds())
        for k, v in kwargs.items():
            setattr(job, k, v)
        if status == "done":
            job.finished_at = datetime.now(timezone.utc)
        await db.commit()

    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        # ── Simulate step-by-step progress ─────────────────────────────────
        total_reads  = random.randint(40_000_000, 120_000_000)
        mapped_reads = int(total_reads * random.uniform(0.96, 0.995))
        mean_depth   = round(random.uniform(30, 150), 1)
        mean_quality = round(random.uniform(33, 39), 1)

        await _update(0, "running", total_reads=total_reads)
        yield _sse("start", {"job_id": job_id, "total_reads": total_reads})

        for (pct, step_label) in PIPELINE_STEPS:
            step = step_label.format(aligner=req.aligner, caller=req.caller)
            log_line = f"[{datetime.now().strftime('%H:%M:%S')}] {step}"
            logs.append(log_line)

            # Simulate realistic step duration
            base_sleep = {
                5: 0.5, 12: 1.0, 18: 0.8, 30: 2.5, 40: 1.0,
                50: 1.5, 58: 2.0, 65: 0.5, 75: 3.0, 83: 1.0,
                88: 0.8, 93: 0.6, 97: 0.4, 100: 0.2,
            }.get(pct, 1.0)
            await asyncio.sleep(base_sleep)

            metrics = {
                "job_id": job_id, "progress": pct,
                "step": step, "log": log_line,
                "mapped_reads": mapped_reads if pct >= 30 else None,
                "mapping_pct": round(mapped_reads / total_reads * 100, 2) if pct >= 30 else None,
                "mean_depth": mean_depth if pct >= 65 else None,
                "mean_quality": mean_quality if pct >= 12 else None,
            }
            await _update(pct, mapped_reads=mapped_reads, mapping_pct=round(mapped_reads/total_reads*100,2),
                          mean_depth=mean_depth, mean_quality=mean_quality)
            yield _sse("progress", metrics)

        # ── Pick variants for this "sample" ────────────────────────────────
        n_variants = random.randint(3, 8)
        called_variants = random.sample(SIMULATED_VARIANTS, min(n_variants, len(SIMULATED_VARIANTS)))

        # Add realistic depth/AF per variant
        for v in called_variants:
            v["dp"] = random.randint(int(mean_depth * 0.6), int(mean_depth * 1.4))
            v["af"] = round(random.uniform(0.45, 0.55) if random.random() > 0.3 else random.uniform(0.92, 1.0), 3)

        path_count = sum(1 for v in called_variants if "pathogenic" in v["sig"].lower())

        await _update(
            100, "done",
            variant_count=len(called_variants),
            pathogenic_cnt=path_count,
            vcf_output=json.dumps(called_variants),
            log="\n".join(logs),
        )

        yield _sse("complete", {
            "job_id":          job_id,
            "status":          "done",
            "variant_count":   len(called_variants),
            "pathogenic_cnt":  path_count,
            "variants":        called_variants,
            "elapsed_sec":     int((datetime.now(timezone.utc) - start_time).total_seconds()),
        })

    except Exception as e:
        err = str(e)
        await _update(0, "failed", error=err, log="\n".join(logs))
        yield _sse("error", {"job_id": job_id, "error": err})
