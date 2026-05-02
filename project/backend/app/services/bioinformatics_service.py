"""Bioinformatics sequence analysis service"""
import logging
from typing import Dict, List, Tuple, Optional
from Bio import Seq, SeqUtils
from Bio.SeqUtils import GC

logger = logging.getLogger(__name__)


class SequenceAnalysisService:
    """Production-grade bioinformatics sequence analysis"""

    # Standard genetic code table
    CODON_TABLE = {
        "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
        "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
        "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
        "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
        "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
        "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
        "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
        "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
        "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
        "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
        "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
        "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
        "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
        "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
        "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
        "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
    }

    START_CODON = "ATG"
    STOP_CODONS = {"TAA", "TAG", "TGA"}

    @staticmethod
    def validate_dna_sequence(sequence: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validate DNA sequence format with position tracking
        
        Returns:
            Tuple[is_valid, error_message, position]
        """
        sequence = sequence.upper().strip()
        valid_chars = set("ATGC")
        
        for pos, char in enumerate(sequence):
            if char not in valid_chars:
                return False, f"Invalid DNA character '{char}'", pos
        
        if len(sequence) < 3:
            return False, "Sequence must be at least 3 bases long", None
            
        return True, None, None

    @staticmethod
    def dna_to_rna(dna: str) -> str:
        """Convert DNA to RNA (T -> U)"""
        return dna.upper().replace("T", "U")

    @staticmethod
    def reverse_complement(dna: str) -> str:
        """Generate reverse complement of DNA sequence"""
        complement_map = {"A": "T", "T": "A", "G": "C", "C": "G"}
        return "".join(complement_map.get(base, base) for base in reversed(dna.upper()))

    @classmethod
    def translate_sequence(cls, dna: str, frame: int = 1) -> str:
        """
        Translate DNA sequence to protein using specified reading frame
        
        Args:
            dna: DNA sequence
            frame: Reading frame (1, 2, or 3)
        
        Returns:
            Protein sequence
        """
        if frame not in [1, 2, 3]:
            raise ValueError("Reading frame must be 1, 2, or 3")
        
        dna = dna.upper()
        rna = cls.dna_to_rna(dna)
        
        # Adjust for reading frame
        start_pos = frame - 1
        rna_frame = rna[start_pos:]
        
        # Translate to protein
        protein = ""
        for i in range(0, len(rna_frame) - 2, 3):
            codon = rna_frame[i:i+3]
            if len(codon) < 3:
                break
            
            # Convert U back to T for codon lookup
            codon_dna = codon.replace("U", "T")
            amino_acid = cls.CODON_TABLE.get(codon_dna, "X")
            protein += amino_acid
        
        return protein

    @classmethod
    def find_orfs(cls, dna: str, min_length: int = 100) -> List[Dict]:
        """
        Find all Open Reading Frames (ORFs) in sequence
        
        Returns:
            List of ORF dictionaries with positions and translations
        """
        dna = dna.upper()
        orfs = []
        
        # Search in all 6 reading frames (3 forward + 3 reverse)
        for strand, sequence in [("forward", dna), ("reverse", cls.reverse_complement(dna))]:
            for frame in range(3):
                frame_seq = sequence[frame:]
                
                # Find all ATG (start codon)
                for i in range(0, len(frame_seq) - 2, 3):
                    codon = frame_seq[i:i+3]
                    
                    if codon == cls.START_CODON:
                        # Look for stop codon
                        for j in range(i + 3, len(frame_seq) - 2, 3):
                            stop_codon = frame_seq[j:j+3]
                            
                            if stop_codon in cls.STOP_CODONS:
                                orf_seq = frame_seq[i:j+3]
                                if len(orf_seq) >= min_length:
                                    protein = cls.translate_sequence(orf_seq, 1)
                                    
                                    orfs.append({
                                        "sequence": orf_seq,
                                        "protein": protein,
                                        "start": i + frame,
                                        "end": j + frame + 3,
                                        "length": len(orf_seq),
                                        "strand": strand,
                                        "frame": frame + 1,
                                        "protein_length": len(protein),
                                    })
                                break
        
        return sorted(orfs, key=lambda x: x["length"], reverse=True)

    @staticmethod
    def calculate_gc_content(sequence: str) -> float:
        """Calculate GC content percentage"""
        sequence = sequence.upper()
        gc_count = sequence.count("G") + sequence.count("C")
        return round((gc_count / len(sequence)) * 100, 2) if sequence else 0

    @staticmethod
    def find_restriction_sites(sequence: str) -> Dict[str, List[int]]:
        """
        Find common restriction enzyme sites
        
        Returns:
            Dictionary of restriction sites and their positions
        """
        # Common restriction enzymes (simplified)
        restriction_sites = {
            "EcoRI": "GAATTC",
            "BamHI": "GGATCC",
            "PstI": "CTGCAG",
            "SmaI": "CCCGGG",
            "HindIII": "AAGCTT",
        }
        
        sequence = sequence.upper()
        results = {}
        
        for enzyme, site in restriction_sites.items():
            positions = []
            for i in range(len(sequence) - len(site) + 1):
                if sequence[i:i+len(site)] == site:
                    positions.append(i)
            
            if positions:
                results[enzyme] = positions
        
        return results

    @classmethod
    def comprehensive_analysis(
        cls,
        dna_sequence: str,
        include_reverse: bool = False,
        reading_frames: Optional[List[int]] = None
    ) -> Dict:
        """
        Comprehensive DNA sequence analysis
        
        Returns:
            Dictionary with complete analysis results
        """
        # Validation
        is_valid, error_msg, position = cls.validate_dna_sequence(dna_sequence)
        if not is_valid:
            raise ValueError(f"{error_msg} at position {position}")
        
        dna = dna_sequence.upper()
        if reading_frames is None:
            reading_frames = [1, 2, 3]
        
        # Basic conversion
        rna = cls.dna_to_rna(dna)
        
        # Translation in multiple frames
        translations = {}
        for frame in reading_frames:
            if 1 <= frame <= 3:
                translations[f"frame_{frame}"] = cls.translate_sequence(dna, frame)
        
        # ORF detection
        orfs = cls.find_orfs(dna, min_length=100)
        
        # GC content
        gc_content = cls.calculate_gc_content(dna)
        
        # Restriction sites
        restriction_sites = cls.find_restriction_sites(dna)
        
        # Codon usage
        codon_usage = cls.analyze_codon_usage(dna)
        
        analysis_result = {
            "sequence_stats": {
                "length": len(dna),
                "gc_content": gc_content,
                "at_content": 100 - gc_content,
                "a_count": dna.count("A"),
                "t_count": dna.count("T"),
                "g_count": dna.count("G"),
                "c_count": dna.count("C"),
            },
            "conversions": {
                "dna": dna,
                "rna": rna,
                "protein": cls.translate_sequence(dna, 1),
            },
            "translations": translations,
            "orfs": orfs,
            "restriction_sites": restriction_sites,
            "codon_usage": codon_usage,
        }
        
        if include_reverse:
            rc_dna = cls.reverse_complement(dna)
            analysis_result["reverse_complement"] = {
                "dna": rc_dna,
                "rna": cls.dna_to_rna(rc_dna),
                "protein": cls.translate_sequence(rc_dna, 1),
            }
        
        return analysis_result

    @classmethod
    def analyze_codon_usage(cls, dna: str) -> Dict[str, int]:
        """Analyze codon usage frequency"""
        dna = dna.upper()
        codon_usage = {}
        
        for i in range(0, len(dna) - 2, 3):
            codon = dna[i:i+3]
            if len(codon) == 3 and all(c in "ATGC" for c in codon):
                codon_usage[codon] = codon_usage.get(codon, 0) + 1
        
        return codon_usage
