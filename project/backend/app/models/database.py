"""SQLAlchemy ORM models for database entities"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, Enum, Float, JSON, Integer, ForeignKey, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
import uuid

Base = declarative_base()


class User(Base):
    """User model for authentication and authorization"""

    __tablename__ = "users"

    id = String(36, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = String(255, unique=True, nullable=False, index=True)
    username = String(100, unique=True, nullable=False)
    password_hash = String(255, nullable=False)
    full_name = String(255)
    is_active = Boolean(default=True)
    is_admin = Boolean(default=False)
    created_at = DateTime(timezone=True, default=datetime.utcnow)
    updated_at = DateTime(timezone=True, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sequences = relationship("Sequence", back_populates="user", cascade="all, delete-orphan")
    analysis_jobs = relationship("AnalysisJob", back_populates="user", cascade="all, delete-orphan")
    structure_predictions = relationship("StructurePrediction", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_is_active", "is_active"),
    )


class Sequence(Base):
    """DNA/RNA sequence storage"""

    __tablename__ = "sequences"

    id = String(36, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = String(36, ForeignKey("users.id"), nullable=False)
    name = String(255, nullable=False)
    description = Text()
    sequence_type = String(20, nullable=False)  # DNA, RNA, PROTEIN
    sequence_data = Text(nullable=False)
    length = Integer(nullable=False)
    gc_content = Float()
    created_at = DateTime(timezone=True, default=datetime.utcnow)
    metadata = JSON(default=dict)

    # Relationships
    user = relationship("User", back_populates="sequences")
    analysis_jobs = relationship("AnalysisJob", back_populates="sequence")

    __table_args__ = (
        Index("idx_sequence_user_id", "user_id"),
        Index("idx_sequence_type", "sequence_type"),
    )


class JobStatus(str, enum.Enum):
    """Job status enumeration"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AnalysisJob(Base):
    """Bioinformatics analysis job tracking"""

    __tablename__ = "analysis_jobs"

    id = String(36, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = String(36, ForeignKey("users.id"), nullable=False)
    sequence_id = String(36, ForeignKey("sequences.id"), nullable=True)
    job_type = String(50, nullable=False)  # DNA_ANALYSIS, TRANSLATION, ORF_DETECTION
    status = String(20, default=JobStatus.PENDING.value)
    description = Text()
    created_at = DateTime(timezone=True, default=datetime.utcnow)
    started_at = DateTime(timezone=True)
    completed_at = DateTime(timezone=True)
    result_json = JSON()
    error_message = Text()
    celery_task_id = String(255)
    progress_percentage = Integer(default=0)

    # Relationships
    user = relationship("User", back_populates="analysis_jobs")
    sequence = relationship("Sequence", back_populates="analysis_jobs")

    __table_args__ = (
        Index("idx_job_user_id", "user_id"),
        Index("idx_job_status", "status"),
        Index("idx_job_created_at", "created_at"),
    )


class StructurePrediction(Base):
    """Protein structure prediction results"""

    __tablename__ = "structure_predictions"

    id = String(36, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = String(36, ForeignKey("users.id"), nullable=False)
    protein_sequence = Text(nullable=False)
    model_used = String(100, default="ESMFold")
    status = String(20, default=JobStatus.PENDING.value)
    pdb_data = Text()
    confidence_scores = JSON()
    metadata = JSON()
    celery_task_id = String(255)
    created_at = DateTime(timezone=True, default=datetime.utcnow)
    completed_at = DateTime(timezone=True)
    error_message = Text()

    # Relationships
    user = relationship("User", back_populates="structure_predictions")

    __table_args__ = (
        Index("idx_structure_user_id", "user_id"),
        Index("idx_structure_status", "status"),
    )
