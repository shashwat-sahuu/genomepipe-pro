from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from app.services.sequence_service import dna_to_rna, rna_to_protein
from app.services.structure_service import predict_structure

router = APIRouter()

@router.get("/")
def read_root():
    index_path = Path(__file__).resolve().parents[3] / "frontend" / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path, media_type="text/html")

@router.post("/process")
def process(dna: str):

    dna = dna.upper()

    for base in dna:
        if base not in ["A", "T", "G", "C"]:
            raise HTTPException(status_code=400, detail="Invalid DNA sequence")

    rna = dna_to_rna(dna)
    protein = rna_to_protein(rna)

    structure = predict_structure(protein)

    return {
        "dna": dna,
        "rna": rna,
        "protein": protein,
        "structure": structure
    }

@router.post("/structure")
def structure(dna: str):
    dna = dna.upper()
    for base in dna:
        if base not in ["A", "T", "G", "C"]:
            raise HTTPException(status_code=400, detail="Invalid DNA sequence")
    rna = dna_to_rna(dna)
    protein = rna_to_protein(rna)
    pdb = predict_structure(protein)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(pdb)