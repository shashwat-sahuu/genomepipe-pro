"""Protein structure prediction service"""
import logging
import asyncio
import time
from typing import Optional, Dict, Any
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StructurePredictionService:
    """Protein structure prediction using ESMFold API"""

    @staticmethod
    async def predict_structure_esmatlas(
        protein_sequence: str,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Predict protein structure using ESMFold API
        
        Args:
            protein_sequence: Amino acid sequence
            timeout: Request timeout in seconds
        
        Returns:
            Dictionary with PDB data and confidence scores
        """
        # Validate protein sequence
        if not StructurePredictionService.validate_protein_sequence(protein_sequence):
            raise ValueError("Invalid protein sequence")
        
        # Length check
        if len(protein_sequence) > settings.MAX_PROTEIN_LENGTH:
            logger.warning(
                f"Protein sequence length {len(protein_sequence)} exceeds "
                f"max {settings.MAX_PROTEIN_LENGTH}. Truncating."
            )
            protein_sequence = protein_sequence[:settings.MAX_PROTEIN_LENGTH]
        
        url = settings.ESMATLAS_API_URL
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = protein_sequence.encode("utf-8")
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    content=data,
                    headers=headers
                )
                response.raise_for_status()
                
                pdb_content = response.text
                
                return {
                    "status": "completed",
                    "pdb_data": pdb_content,
                    "model": "ESMFold",
                    "sequence_length": len(protein_sequence),
                    "timestamp": time.time(),
                    "confidence_scores": StructurePredictionService.extract_confidence_scores(pdb_content),
                }
        
        except httpx.TimeoutException as e:
            logger.error(f"ESMFold prediction timeout: {e}")
            raise RuntimeError(f"Structure prediction timed out after {timeout}s")
        except httpx.HTTPError as e:
            logger.error(f"ESMFold API error: {e}")
            raise RuntimeError(f"Structure prediction failed: {str(e)}")

    @staticmethod
    def validate_protein_sequence(sequence: str) -> bool:
        """Validate protein sequence (standard amino acids only)"""
        valid_aa = set("ACDEFGHIKLMNPQRSTVWY*XU")
        sequence = sequence.upper().strip()
        
        if len(sequence) < 1:
            return False
        
        return all(c in valid_aa for c in sequence)

    @staticmethod
    def extract_confidence_scores(pdb_content: str) -> Dict[str, float]:
        """
        Extract confidence scores from PDB file
        (Typically stored in B-factor column for ESMFold)
        """
        scores = {
            "pae_mean": 0.0,
            "plddt_mean": 0.0,
            "pae_min": float('inf'),
            "pae_max": 0.0,
        }
        
        lines = pdb_content.split('\n')
        b_factors = []
        
        for line in lines:
            if line.startswith("ATOM"):
                try:
                    # B-factor is in columns 60-66 of PDB file
                    b_factor = float(line[60:66])
                    b_factors.append(b_factor)
                except (ValueError, IndexError):
                    continue
        
        if b_factors:
            scores["plddt_mean"] = sum(b_factors) / len(b_factors)
            scores["pae_min"] = min(b_factors)
            scores["pae_max"] = max(b_factors)
            scores["pae_mean"] = scores["plddt_mean"]
        
        return scores

    @staticmethod
    def generate_mock_pdb(protein_sequence: str, name: str = "GENOMEPIPE") -> str:
        """
        Generate realistic mock PDB when API is unavailable
        
        This is a fallback for development/testing
        """
        pdb_header = f"""HEADER    MOCK STRUCTURE                          
TITLE     GENOMEPIPE PRO - STRUCTURE PREDICTION
REMARK    Mock structure for sequence: {protein_sequence[:50]}...
REMARK    Model: ESMFold (Mock)
REMARK    Sequence length: {len(protein_sequence)}
"""
        
        atoms = []
        x, y, z = 0.0, 0.0, 0.0
        
        # Simple alpha helix simulation
        for i, aa in enumerate(protein_sequence[:400]):  # Limit to 400 residues for PDB
            atom_line = f"ATOM  {i+1:5d}  CA  {aa:3s} A{i+1:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n"
            atoms.append(atom_line)
            
            # Simulate alpha helix coordinates
            x += 1.5 * (-0.866)
            y += 1.5 * 0.5
            z += 1.5 * 0.0
            
            # Helical pitch (rise per residue)
            z += 0.1
        
        pdb_content = pdb_header + "".join(atoms) + "END\n"
        return pdb_content

    @staticmethod
    def parse_pdb_structure(pdb_content: str) -> Dict[str, Any]:
        """
        Parse PDB file and extract structure information
        """
        atoms = []
        hetatm = []
        
        for line in pdb_content.split('\n'):
            if line.startswith("ATOM"):
                try:
                    atom_info = {
                        "number": int(line[6:11]),
                        "name": line[12:16].strip(),
                        "residue": line[17:20].strip(),
                        "chain": line[21],
                        "seq_num": int(line[22:26]),
                        "x": float(line[30:38]),
                        "y": float(line[38:46]),
                        "z": float(line[46:54]),
                        "occupancy": float(line[54:60]),
                        "b_factor": float(line[60:66]),
                        "element": line[76:78].strip(),
                    }
                    atoms.append(atom_info)
                except (ValueError, IndexError):
                    continue
            
            elif line.startswith("HETATM"):
                try:
                    atom_info = {
                        "number": int(line[6:11]),
                        "name": line[12:16].strip(),
                        "residue": line[17:20].strip(),
                    }
                    hetatm.append(atom_info)
                except (ValueError, IndexError):
                    continue
        
        return {
            "atom_count": len(atoms),
            "hetatm_count": len(hetatm),
            "atoms": atoms[:100],  # Return first 100 atoms for visualization
            "center_of_mass": StructurePredictionService.calculate_center_of_mass(atoms),
        }

    @staticmethod
    def calculate_center_of_mass(atoms: list) -> Dict[str, float]:
        """Calculate center of mass of protein structure"""
        if not atoms:
            return {"x": 0.0, "y": 0.0, "z": 0.0}
        
        total_x = sum(a["x"] for a in atoms)
        total_y = sum(a["y"] for a in atoms)
        total_z = sum(a["z"] for a in atoms)
        n = len(atoms)
        
        return {
            "x": total_x / n,
            "y": total_y / n,
            "z": total_z / n,
        }

    @staticmethod
    def get_secondary_structure(pdb_content: str) -> Dict[str, int]:
        """
        Detect secondary structure elements from PDB
        (Simplified - in production use DSSP or similar)
        """
        # Count beta sheets (SHEET records) and alpha helices (HELIX records)
        helices = sum(1 for line in pdb_content.split('\n') if line.startswith("HELIX"))
        sheets = sum(1 for line in pdb_content.split('\n') if line.startswith("SHEET"))
        
        return {
            "helix_count": helices,
            "sheet_count": sheets,
            "turn_count": 0,  # Could be calculated
        }

    @staticmethod
    def calculate_rmsd(pdb1: str, pdb2: str) -> Optional[float]:
        """
        Calculate RMSD between two structures
        (Simplified - in production use BioPython)
        """
        # Extract CA atoms from both PDB structures
        atoms1 = []
        atoms2 = []
        
        for line in pdb1.split('\n'):
            if line.startswith("ATOM") and "CA" in line:
                try:
                    atoms1.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
                except (ValueError, IndexError):
                    continue
        
        for line in pdb2.split('\n'):
            if line.startswith("ATOM") and "CA" in line:
                try:
                    atoms2.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
                except (ValueError, IndexError):
                    continue
        
        if not atoms1 or not atoms2 or len(atoms1) != len(atoms2):
            return None
        
        # Simple RMSD calculation
        sum_sq_dist = sum(
            (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2
            for a, b in zip(atoms1, atoms2)
        )
        
        rmsd = (sum_sq_dist / len(atoms1)) ** 0.5
        return round(rmsd, 3)