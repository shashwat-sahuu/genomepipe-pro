from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Optional, List
import json

from database import get_db
from models.variant import Variant
from models.schemas import VariantCreate, VariantOut, VariantUpdate
from services.vcf_service import parse_vcf

router = APIRouter()


@router.get("/", response_model=List[VariantOut])
async def list_variants(
    workbench:    Optional[int]  = None,
    significance: Optional[str] = None,
    gene:         Optional[str] = None,
    source:       Optional[str] = None,
    skip: int = 0,
    limit: int = Query(500, le=2000),
    db: AsyncSession = Depends(get_db),
):
    q = select(Variant).order_by(Variant.created_at.desc())
    if workbench is not None:
        q = q.where(Variant.workbench == workbench)
    if significance:
        q = q.where(Variant.significance.ilike(f"%{significance}%"))
    if gene:
        q = q.where(Variant.gene.ilike(f"%{gene}%"))
    if source:
        q = q.where(Variant.source == source)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=VariantOut, status_code=201)
async def create_variant(
    payload: VariantCreate,
    db: AsyncSession = Depends(get_db),
):
    v = Variant(**payload.model_dump())
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


@router.post("/batch", response_model=List[VariantOut], status_code=201)
async def batch_create(
    payload: List[VariantCreate],
    db: AsyncSession = Depends(get_db),
):
    variants = [Variant(**p.model_dump()) for p in payload]
    db.add_all(variants)
    await db.commit()
    return variants


@router.get("/{variant_id}", response_model=VariantOut)
async def get_variant(variant_id: int, db: AsyncSession = Depends(get_db)):
    v = await db.get(Variant, variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    return v


@router.patch("/{variant_id}", response_model=VariantOut)
async def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    db: AsyncSession = Depends(get_db),
):
    v = await db.get(Variant, variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    for k, val in payload.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    await db.commit()
    await db.refresh(v)
    return v


@router.delete("/{variant_id}", status_code=204)
async def delete_variant(variant_id: int, db: AsyncSession = Depends(get_db)):
    v = await db.get(Variant, variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    await db.delete(v)
    await db.commit()


@router.delete("/", status_code=204)
async def clear_all(
    workbench: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = delete(Variant)
    if workbench is not None:
        q = q.where(Variant.workbench == workbench)
    await db.execute(q)
    await db.commit()


# ── VCF import ────────────────────────────────────────────────────────────────

@router.post("/import/vcf", response_model=List[VariantOut], status_code=201)
async def import_vcf(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept { "vcf_content": "...", "workbench": 0 } and parse into variants.
    """
    content = body.get("vcf_content", "")
    workbench = int(body.get("workbench", 0))
    if not content:
        raise HTTPException(400, "vcf_content is required")

    parsed = parse_vcf(content)
    if not parsed:
        raise HTTPException(400, "No variants parsed from VCF content")

    variants = []
    for p in parsed:
        p["workbench"] = workbench
        v = Variant(**p)
        db.add(v)
        variants.append(v)

    await db.commit()
    return variants


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export/vcf", response_class=PlainTextResponse)
async def export_vcf(
    workbench: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Variant)
    if workbench is not None:
        q = q.where(Variant.workbench == workbench)
    result = await db.execute(q)
    rows = result.scalars().all()

    lines = [
        "##fileformat=VCFv4.2",
        "##source=GenomePipePro_v4.0",
        '##INFO=<ID=GENE,Number=1,Type=String,Description="Gene symbol">',
        '##INFO=<ID=SIG,Number=1,Type=String,Description="Clinical significance">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
    ]
    for v in rows:
        chrom = v.chromosome.lstrip("chr")
        rsid  = v.rsid or "."
        info  = f"GENE={v.gene or '.'};SIG={v.significance or '.'}"
        lines.append(f"{chrom}\t{v.position}\t{rsid}\t{v.ref}\t{v.alt}\t.\tPASS\t{info}")

    return "\n".join(lines)


@router.get("/export/csv", response_class=PlainTextResponse)
async def export_csv(
    workbench: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Variant)
    if workbench is not None:
        q = q.where(Variant.workbench == workbench)
    result = await db.execute(q)
    rows = result.scalars().all()

    header = "Chr,Position,Ref,Alt,Gene,Significance,Zygosity,rsID,HGVS,Condition,Source,CADD"
    lines = [header]
    for v in rows:
        lines.append(
            f"{v.chromosome},{v.position},{v.ref},{v.alt},"
            f"{v.gene or ''},{v.significance or ''},{v.zygosity or ''},"
            f"{v.rsid or ''},{v.hgvs or ''},{(v.condition or '').replace(',', ';')},"
            f"{v.source or ''},{v.cadd_score or ''}"
        )
    return "\n".join(lines)
