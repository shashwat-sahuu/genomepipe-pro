"""API routes for sequence analysis"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional
import uuid

from app.models.schemas import (
    AnalysisRequest,
    AnalysisResultResponse,
    JobStatusResponse,
    ErrorResponse,
    ValidationErrorResponse,
)
from app.services.bioinformatics_service import SequenceAnalysisService
from app.services.structure_service import StructurePredictionService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze")
async def analyze_sequence(
    request: AnalysisRequest
) -> AnalysisResultResponse:
    """
    Comprehensive DNA sequence analysis

    Performs:
    - DNA to RNA to Protein translation
    - ORF (Open Reading Frame) detection
    - Codon usage analysis
    - Restriction site identification
    - GC content calculation
    - Reading frame translations
    """
    try:
        # Validate input
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(
            request.sequence_data
        )
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_type": "VALIDATION_ERROR",
                    "message": error_msg,
                    "position": position,
                }
            )

        # Perform comprehensive analysis
        analysis = SequenceAnalysisService.comprehensive_analysis(
            dna_sequence=request.sequence_data,
            include_reverse=request.include_reverse_complement,
            reading_frames=request.reading_frames,
        )

        # Extract results
        stats = analysis["sequence_stats"]
        conversions = analysis["conversions"]
        orfs = analysis["orfs"]
        translations = analysis["translations"]

        return AnalysisResultResponse(
            dna=conversions["dna"],
            rna=conversions["rna"],
            protein=conversions["protein"],
            orfs=orfs[:10],  # Top 10 ORFs
            gc_content=stats["gc_content"],
            sequence_length=stats["length"],
            translation_frames=translations,
            stop_codon_positions=[i * 3 for i in range(len(conversions["protein"]))
                                 if conversions["protein"][i] == "*"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/translate")
async def translate_dna(
    sequence: str = Query(..., min_length=3, max_length=1000000),
    frame: int = Query(1, ge=1, le=3),
) -> dict:
    """
    Translate DNA sequence to protein using specified reading frame

    Parameters:
    - sequence: DNA sequence (ATGC only)
    - frame: Reading frame (1, 2, or 3)
    """
    try:
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(sequence)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"{error_msg} at position {position}")

        protein = SequenceAnalysisService.translate_sequence(sequence, frame)

        return {
            "dna_length": len(sequence),
            "frame": frame,
            "protein": protein,
            "protein_length": len(protein),
            "contains_stop_codon": "*" in protein,
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/find-orfs")
async def find_open_reading_frames(
    sequence: str = Query(..., min_length=3, max_length=1000000),
    min_length: int = Query(100, ge=30, le=10000),
) -> dict:
    """
    Find all Open Reading Frames (ORFs) in DNA sequence

    Returns ORFs in all 6 reading frames (3 forward + 3 reverse complement)
    """
    try:
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(sequence)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"{error_msg} at position {position}")

        orfs = SequenceAnalysisService.find_orfs(sequence, min_length)

        return {
            "total_orfs": len(orfs),
            "min_orf_length": min_length,
            "sequence_length": len(sequence),
            "orfs": [
                {
                    "id": str(uuid.uuid4()),
                    "start": orf["start"],
                    "end": orf["end"],
                    "length": orf["length"],
                    "strand": orf["strand"],
                    "frame": orf["frame"],
                    "protein_length": orf["protein_length"],
                    "protein": orf["protein"][:50] + "..." if len(orf["protein"]) > 50 else orf["protein"],
                }
                for orf in orfs[:50]  # Return top 50 ORFs
            ],
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/gc-content")
async def get_gc_content(
    sequence: str = Query(..., min_length=1, max_length=1000000),
) -> dict:
    """Calculate GC content of DNA sequence"""
    try:
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(sequence)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"{error_msg} at position {position}")

        gc = SequenceAnalysisService.calculate_gc_content(sequence)
        sequence_upper = sequence.upper()

        return {
            "sequence_length": len(sequence),
            "gc_content": gc,
            "at_content": 100 - gc,
            "g_count": sequence_upper.count("G"),
            "c_count": sequence_upper.count("C"),
            "a_count": sequence_upper.count("A"),
            "t_count": sequence_upper.count("T"),
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/restriction-sites")
async def find_restriction_sites(
    sequence: str = Query(..., min_length=1, max_length=1000000),
) -> dict:
    """Find common restriction enzyme sites in DNA sequence"""
    try:
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(sequence)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"{error_msg} at position {position}")

        sites = SequenceAnalysisService.find_restriction_sites(sequence)

        return {
            "sequence_length": len(sequence),
            "restriction_sites_found": len(sites),
            "sites": sites,
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/process")
async def process_dna(dna: str):
    """
    Legacy endpoint for backward compatibility

    Process DNA sequence and return complete analysis
    """
    try:
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(dna)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        dna = dna.upper()
        rna = SequenceAnalysisService.dna_to_rna(dna)
        protein = SequenceAnalysisService.translate_sequence(dna, 1)

        # Simple mock structure for backward compatibility
        structure = StructurePredictionService.generate_mock_pdb(protein)

        return {
            "dna": dna,
            "rna": rna,
            "protein": protein,
            "structure": structure,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/structure")
async def analyze_structure(dna: str):
    """
    Legacy endpoint for backward compatibility

    Predict protein structure from DNA sequence
    """
    try:
        is_valid, error_msg, position = SequenceAnalysisService.validate_dna_sequence(dna)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        dna = dna.upper()
        protein = SequenceAnalysisService.translate_sequence(dna, 1)
        pdb = StructurePredictionService.generate_mock_pdb(protein)

        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(pdb)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
