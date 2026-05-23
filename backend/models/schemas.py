from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Variant ──────────────────────────────────────────────────────────────────

class VariantCreate(BaseModel):
    chromosome:    str
    position:      int
    ref:           str
    alt:           str
    gene:          Optional[str] = None
    significance:  Optional[str] = "Unknown"
    zygosity:      Optional[str] = "Unknown"
    rsid:          Optional[str] = None
    hgvs:          Optional[str] = None
    condition:     Optional[str] = None
    review_status: Optional[str] = None
    clinvar_id:    Optional[str] = None
    cadd_score:    Optional[str] = None
    source:        Optional[str] = "Manual"
    workbench:     Optional[int] = 0
    notes:         Optional[str] = None

class VariantUpdate(BaseModel):
    significance:  Optional[str] = None
    zygosity:      Optional[str] = None
    notes:         Optional[str] = None
    workbench:     Optional[int] = None

class VariantOut(VariantCreate):
    id:         int
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    sample_id:  str
    patient_id: Optional[str] = ""
    aligner:    Optional[str] = "BWA-MEM2"
    caller:     Optional[str] = "GATK HaplotypeCaller 4.4"
    reference:  Optional[str] = "GRCh38"
    min_bq:     Optional[int] = 20
    min_mq:     Optional[int] = 20
    min_dp:     Optional[int] = 10
    min_af:     Optional[float] = 0.05
    bqsr:       Optional[bool] = True
    mark_dup:   Optional[bool] = True

class PipelineJobOut(BaseModel):
    job_id:        str
    sample_id:     str
    status:        str
    progress:      int
    aligner:       Optional[str]
    caller:        Optional[str]
    total_reads:   Optional[int]
    mapped_reads:  Optional[int]
    mapping_pct:   Optional[float]
    mean_depth:    Optional[float]
    mean_quality:  Optional[float]
    variant_count: Optional[int]
    pathogenic_cnt:Optional[int]
    log:           Optional[str]
    error:         Optional[str]
    elapsed_sec:   Optional[int]
    created_at:    Optional[datetime]
    class Config:
        from_attributes = True


# ── AI / Ollama ───────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str   # user | assistant
    content: str

class AIAnalysisRequest(BaseModel):
    mode:     str = "clinical"           # clinical|acmg|cancer|pharma|vus|qc|trio|population|splicing|cnv|report|chat
    message:  str
    history:  Optional[List[ChatMessage]] = []
    variants: Optional[List[dict]] = []
    model:    Optional[str] = "llama3"
    stream:   Optional[bool] = True

class AIAnalysisResponse(BaseModel):
    response: str
    model:    str
    mode:     str


# ── Annotation ───────────────────────────────────────────────────────────────

class AnnotationRequest(BaseModel):
    chromosome: str
    position:   int
    ref:        str
    alt:        str
    gene:       Optional[str] = None
    rsid:       Optional[str] = None

class PopFreqRequest(BaseModel):
    chromosome: str
    position:   int
    ref:        str
    alt:        str

class PathogenicityRequest(BaseModel):
    chromosome: str
    position:   int
    ref:        str
    alt:        str
    gene:       Optional[str] = None
    rsid:       Optional[str] = None
