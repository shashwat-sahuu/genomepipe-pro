"""Pydantic schemas for request/response validation"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, EmailStr, Field, validator


# ============ Authentication Schemas ============
class UserRegisterRequest(BaseModel):
    """User registration request"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None

    @validator("password")
    def validate_password(cls, v):
        """Validate password strength"""
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """User login request"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User response model"""

    id: str
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Sequence Schemas ============
class SequenceUploadRequest(BaseModel):
    """Sequence file upload request"""

    file_name: str
    sequence_type: str = Field(..., regex="^(DNA|RNA|PROTEIN)$")
    description: Optional[str] = None


class SequenceResponse(BaseModel):
    """Sequence response model"""

    id: str
    name: str
    sequence_type: str
    length: int
    gc_content: Optional[float]
    created_at: datetime
    description: Optional[str]

    class Config:
        from_attributes = True


# ============ Analysis Job Schemas ============
class AnalysisRequest(BaseModel):
    """Sequence analysis request"""

    sequence_data: str = Field(..., min_length=1, max_length=1000000)
    job_type: str = Field(..., regex="^(DNA_ANALYSIS|TRANSLATION|ORF_DETECTION|FULL_PIPELINE)$")
    description: Optional[str] = None
    include_reverse_complement: bool = False
    reading_frames: Optional[List[int]] = [1, 2, 3]


class AnalysisResultResponse(BaseModel):
    """Analysis result response"""

    dna: str
    rna: str
    protein: str
    orfs: Optional[List[Dict[str, Any]]]
    gc_content: float
    sequence_length: int
    translation_frames: Optional[Dict[int, str]]
    stop_codon_positions: List[int]


class JobStatusResponse(BaseModel):
    """Job status response"""

    id: str
    job_type: str
    status: str
    progress_percentage: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_json: Optional[Dict[str, Any]]
    error_message: Optional[str]

    class Config:
        from_attributes = True


# ============ Structure Prediction Schemas ============
class StructurePredictionRequest(BaseModel):
    """Protein structure prediction request"""

    protein_sequence: str = Field(..., min_length=1, max_length=10000)
    model: str = Field("ESMFold", regex="^(ESMFold|AlphaFold2)$")
    description: Optional[str] = None


class StructurePredictionResponse(BaseModel):
    """Structure prediction response"""

    id: str
    status: str
    model_used: str
    created_at: datetime
    completed_at: Optional[datetime]
    pdb_url: Optional[str]
    confidence_score: Optional[float]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class PDBFileResponse(BaseModel):
    """PDB file response"""

    pdb_content: str
    prediction_id: str
    file_name: str
    confidence_scores: Optional[Dict[str, Any]]


# ============ Error Response Schemas ============
class ErrorResponse(BaseModel):
    """Standard error response"""

    status_code: int
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorDetail(BaseModel):
    """Validation error detail"""

    field: str
    message: str
    position: Optional[int] = None


class ValidationErrorResponse(ErrorResponse):
    """Validation error response"""

    error_type: str = "VALIDATION_ERROR"
    details: Optional[List[ValidationErrorDetail]] = None


# ============ Health Check Schemas ============
class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    environment: str
    database: str
    redis: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============ Admin Schemas ============
class JobStatistics(BaseModel):
    """Job statistics"""

    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    pending_jobs: int
    average_processing_time: float


class SystemStatistics(BaseModel):
    """System statistics"""

    active_users: int
    total_users: int
    job_statistics: JobStatistics
    cache_hit_rate: float
    uptime_seconds: float
