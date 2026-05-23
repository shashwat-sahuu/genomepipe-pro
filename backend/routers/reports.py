from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database import get_db
from models.variant import Variant
from services.ollama_service import full_response, check_ollama

router = APIRouter()


class ReportRequest(BaseModel):
    report_title:      Optional[str] = "Clinical Genomics Report"
    patient_id:        Optional[str] = ""
    sample_id:         Optional[str] = ""
    ordering_physician:Optional[str] = ""
    laboratory:        Optional[str] = "GenomePipe Pro Laboratory"
    clinical_indication: Optional[str] = "Hereditary Cancer Predisposition"
    report_type:       Optional[str] = "Germline Variant Interpretation"
    variant_source:    Optional[str] = "both"   # my_variants | workbench | both
    model:             Optional[str] = "llama3"
    include_sections:  Optional[List[str]] = ["summary", "variants", "recommendations"]


@router.post("/generate")
async def generate_report(
    req: ReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a clinical genomics report using Ollama AI."""
    # Fetch variants
    q = select(Variant)
    if req.variant_source == "my_variants":
        q = q.where(Variant.workbench == 0)
    elif req.variant_source == "workbench":
        q = q.where(Variant.workbench == 1)
    result = await db.execute(q)
    variants = result.scalars().all()

    if not variants:
        raise HTTPException(400, "No variants found. Add variants before generating a report.")

    # Build variant summary for the prompt
    variant_lines = []
    for v in variants:
        variant_lines.append(
            f"- {v.chromosome}:{v.position} {v.ref}>{v.alt} "
            f"Gene={v.gene or 'Unknown'} "
            f"Significance={v.significance or 'Unknown'} "
            f"Condition={v.condition or 'Unknown'}"
        )

    prompt = f"""Generate a {req.report_type} clinical genomics report with the following details:

**Report Information:**
- Title: {req.report_title}
- Patient ID: {req.patient_id or 'Not provided'}
- Sample ID: {req.sample_id or 'Not provided'}
- Ordering Physician: {req.ordering_physician or 'Not provided'}
- Laboratory: {req.laboratory}
- Clinical Indication: {req.clinical_indication}
- Report Date: {datetime.now().strftime('%B %d, %Y')}

**Variants Analyzed ({len(variants)} total):**
{chr(10).join(variant_lines)}

Generate a professional CAP/CLIA-style report including:
1. Executive Summary (1-2 paragraphs)
2. Clinical Findings — detailed interpretation of each significant variant
3. Methodology section
4. Recommendations for patient management
5. Clinical disclaimer

Format with clear headers. Be specific about ACMG classification for each variant."""

    status = await check_ollama()
    if not status["online"]:
        # Return a template report if Ollama is offline
        return _template_report(req, variants)

    try:
        report_text = await full_response(
            message=prompt,
            mode="report",
            model=req.model,
        )
    except Exception as e:
        raise HTTPException(503, f"AI report generation failed: {e}")

    return {
        "report":       report_text,
        "variant_count": len(variants),
        "generated_at": datetime.now().isoformat(),
        "model":        req.model,
        "ai_generated": True,
    }


def _template_report(req: ReportRequest, variants) -> dict:
    """Fallback template report when Ollama is offline."""
    path_count = sum(1 for v in variants if "pathogenic" in (v.significance or "").lower())
    vus_count  = sum(1 for v in variants if "uncertain" in (v.significance or "").lower())

    lines = [
        f"# {req.report_title}",
        f"**Date:** {datetime.now().strftime('%B %d, %Y')}",
        f"**Patient:** {req.patient_id or 'Not provided'}",
        f"**Indication:** {req.clinical_indication}",
        "",
        "## Summary",
        f"Genetic analysis identified {len(variants)} variants across the analyzed genes. "
        f"{path_count} variant(s) classified as Pathogenic/Likely Pathogenic. "
        f"{vus_count} variant(s) of Uncertain Significance (VUS).",
        "",
        "## Variants",
    ]
    for v in variants:
        lines.append(f"- **{v.gene or '?'} {v.hgvs or f'{v.ref}>{v.alt}'}** — {v.significance or 'Unknown'}")
        if v.condition:
            lines.append(f"  - Condition: {v.condition}")

    lines += [
        "",
        "## Disclaimer",
        "This report is generated for research purposes. Clinical decisions should be made "
        "by a qualified healthcare professional in consultation with a certified clinical geneticist.",
    ]

    return {
        "report":        "\n".join(lines),
        "variant_count": len(variants),
        "generated_at":  datetime.now().isoformat(),
        "model":         "template",
        "ai_generated":  False,
    }
