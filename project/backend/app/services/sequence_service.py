# Backward compatibility - import from bioinformatics service
from app.services.bioinformatics_service import SequenceAnalysisService

def dna_to_rna(dna: str):
    """Convert DNA to RNA - maintained for backward compatibility"""
    return SequenceAnalysisService.dna_to_rna(dna)


def rna_to_protein(rna: str):
    """Convert RNA to protein - maintained for backward compatibility"""
    # Convert RNA back to DNA for the translation function
    dna = rna.upper().replace("U", "T")
    return SequenceAnalysisService.translate_sequence(dna, 1)