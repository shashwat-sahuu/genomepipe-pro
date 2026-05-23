from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from database import Base


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id             = Column(Integer, primary_key=True, index=True)
    job_id         = Column(String(50), unique=True, index=True)
    sample_id      = Column(String(200))
    patient_id     = Column(String(200))
    status         = Column(String(30), default="queued")   # queued|running|done|failed
    progress       = Column(Integer, default=0)             # 0-100
    aligner        = Column(String(50), default="BWA-MEM2")
    caller         = Column(String(50), default="GATK")
    reference      = Column(String(20), default="GRCh38")
    total_reads    = Column(Integer)
    mapped_reads   = Column(Integer)
    mapping_pct    = Column(Float)
    mean_depth     = Column(Float)
    mean_quality   = Column(Float)
    variant_count  = Column(Integer)
    pathogenic_cnt = Column(Integer)
    vcf_output     = Column(Text)    # JSON-serialised variant list
    log            = Column(Text)
    error          = Column(Text)
    elapsed_sec    = Column(Integer)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    finished_at    = Column(DateTime(timezone=True))
