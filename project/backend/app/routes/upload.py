"""File upload and sequence management routes"""
import logging
import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, Form
from sqlalchemy.orm import Session

from app.models.schemas import SequenceResponse, ErrorResponse
from app.models.database import Sequence, User
from app.models.db_manager import get_db
from app.utils.security import SecurityService
from app.utils.file_handler import FastaParser, SequenceValidator, FileProcessor
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sequences", tags=["Sequences"])
settings = get_settings()


@router.post("/upload", response_model=SequenceResponse)
async def upload_sequence(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(SecurityService.get_current_user),
    db: Session = Depends(get_db)
) -> SequenceResponse:
    """
    Upload a FASTA or FASTQ sequence file

    Supported formats:
    - FASTA (.fa, .fasta, .fq, .fastq)
    - FASTQ (.fq, .fastq)

    Returns:
        Uploaded sequence information
    """
    # Check file extension
    if not FileProcessor.is_allowed_file(file.filename, settings.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Check file size
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {file_size_mb:.2f} MB (max {settings.MAX_FILE_SIZE_MB} MB)"
        )

    # Save file
    file_path = FileProcessor.save_upload(content, settings.UPLOAD_DIR, file.filename)

    try:
        # Parse file
        file_format, sequences = FastaParser.parse_file(file_path)

        if not sequences:
            os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No sequences found in file"
            )

        # Use first sequence for main record
        first_seq = sequences[0]
        sequence_data = first_seq['sequence']
        sequence_length = len(sequence_data)

        # Determine sequence type
        sequence_upper = sequence_data.upper()
        if all(base in 'ATGCN' for base in sequence_upper):
            sequence_type = "DNA"
        elif all(base in 'AUGCN' for base in sequence_upper):
            sequence_type = "RNA"
        elif all(base in 'ACDEFGHIKLMNPQRSTVWYXU*' for base in sequence_upper):
            sequence_type = "PROTEIN"
        else:
            sequence_type = "UNKNOWN"

        # Calculate GC content if DNA
        gc_content = None
        if sequence_type == "DNA":
            g_count = sequence_upper.count('G')
            c_count = sequence_upper.count('C')
            gc_content = ((g_count + c_count) / sequence_length * 100) if sequence_length > 0 else 0

        # Create database record
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        sequence_record = Sequence(
            user_id=user.id,
            name=first_seq['id'],
            sequence_type=sequence_type,
            sequence_data=sequence_data,
            length=sequence_length,
            gc_content=gc_content,
            description=description or f"Uploaded from {file.filename}",
            meta={
                "file_name": file.filename,
                "file_format": file_format,
                "file_path": file_path,
                "total_sequences": len(sequences),
            }
        )

        db.add(sequence_record)
        db.commit()
        db.refresh(sequence_record)

        logger.info(f"Sequence uploaded by {user.email}: {first_seq['id']} ({sequence_length} bp)")

        return SequenceResponse(
            id=sequence_record.id,
            name=sequence_record.name,
            sequence_type=sequence_record.sequence_type,
            length=sequence_record.length,
            gc_content=sequence_record.gc_content,
            created_at=sequence_record.created_at,
            description=sequence_record.description,
        )

    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )


@router.get("/list", response_model=list[SequenceResponse])
async def list_sequences(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(SecurityService.get_current_user),
    db: Session = Depends(get_db)
) -> list[SequenceResponse]:
    """
    List user's uploaded sequences

    Parameters:
    - skip: Number of records to skip (pagination)
    - limit: Number of records to return (max 100)
    """
    if limit > 100:
        limit = 100

    sequences = db.query(Sequence).filter(
        Sequence.user_id == current_user["user_id"]
    ).offset(skip).limit(limit).all()

    return [
        SequenceResponse(
            id=seq.id,
            name=seq.name,
            sequence_type=seq.sequence_type,
            length=seq.length,
            gc_content=seq.gc_content,
            created_at=seq.created_at,
            description=seq.description,
        )
        for seq in sequences
    ]


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(
    sequence_id: str,
    current_user: dict = Depends(SecurityService.get_current_user),
    db: Session = Depends(get_db)
) -> SequenceResponse:
    """
    Get specific sequence details

    Parameters:
    - sequence_id: ID of the sequence
    """
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user["user_id"]
    ).first()

    if not sequence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sequence not found"
        )

    return SequenceResponse(
        id=sequence.id,
        name=sequence.name,
        sequence_type=sequence.sequence_type,
        length=sequence.length,
        gc_content=sequence.gc_content,
        created_at=sequence.created_at,
        description=sequence.description,
    )


@router.delete("/{sequence_id}")
async def delete_sequence(
    sequence_id: str,
    current_user: dict = Depends(SecurityService.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a sequence

    Parameters:
    - sequence_id: ID of the sequence to delete
    """
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user["user_id"]
    ).first()

    if not sequence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sequence not found"
        )

    # Delete uploaded file if exists
    if sequence.meta and "file_path" in sequence.meta:
        file_path = sequence.meta["file_path"]
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete file {file_path}: {e}")

    db.delete(sequence)
    db.commit()

    logger.info(f"Sequence deleted: {sequence_id}")

    return {"message": "Sequence deleted successfully"}
