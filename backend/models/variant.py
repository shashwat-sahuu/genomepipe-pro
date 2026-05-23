from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Variant(Base):
    __tablename__ = "variants"

    id            = Column(Integer, primary_key=True, index=True)
    chromosome    = Column(String(10), nullable=False)
    position      = Column(Integer, nullable=False)
    ref           = Column(String(500), nullable=False)
    alt           = Column(String(500), nullable=False)
    gene          = Column(String(100))
    significance  = Column(String(100), default="Unknown")
    zygosity      = Column(String(50), default="Unknown")
    rsid          = Column(String(50))
    hgvs          = Column(String(500))
    condition     = Column(Text)
    review_status = Column(String(200))
    clinvar_id    = Column(String(50))
    cadd_score    = Column(String(20))
    source        = Column(String(50), default="Manual")  # ClinVar | dbSNP | Manual | VEP
    workbench     = Column(Integer, default=0)             # 0=MyVariants  1=Workbench
    notes         = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
