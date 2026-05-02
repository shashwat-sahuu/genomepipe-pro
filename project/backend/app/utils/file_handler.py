"""File handling utilities for bioinformatics file formats"""
import logging
import re
from typing import List, Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FastaParser:
    """Parser for FASTA and FASTQ file formats"""

    @staticmethod
    def parse_fasta(content: str) -> List[Dict[str, str]]:
        """
        Parse FASTA format file content

        Returns:
            List of dictionaries with 'id' and 'sequence' keys
        """
        sequences = []
        current_id = None
        current_seq = ""

        for line in content.strip().split('\n'):
            line = line.strip()

            if not line:
                continue

            if line.startswith('>'):
                # Save previous sequence
                if current_id:
                    sequences.append({
                        "id": current_id,
                        "sequence": current_seq,
                        "length": len(current_seq),
                        "format": "FASTA"
                    })

                # Start new sequence
                current_id = line[1:].split()[0]
                current_seq = ""

            else:
                # Add to current sequence
                current_seq += line.replace(" ", "").replace("\t", "")

        # Save last sequence
        if current_id:
            sequences.append({
                "id": current_id,
                "sequence": current_seq,
                "length": len(current_seq),
                "format": "FASTA"
            })

        return sequences

    @staticmethod
    def parse_fastq(content: str) -> List[Dict[str, str]]:
        """
        Parse FASTQ format file content

        Returns:
            List of dictionaries with sequence and quality info
        """
        sequences = []
        lines = content.strip().split('\n')

        i = 0
        while i < len(lines):
            if i + 3 >= len(lines):
                break

            header = lines[i].strip()
            sequence = lines[i + 1].strip()
            plus = lines[i + 2].strip()
            quality = lines[i + 3].strip()

            if not (header.startswith('@') and plus.startswith('+')):
                i += 1
                continue

            sequences.append({
                "id": header[1:].split()[0],
                "sequence": sequence,
                "quality": quality,
                "length": len(sequence),
                "format": "FASTQ"
            })

            i += 4

        return sequences

    @staticmethod
    def guess_format(content: str) -> str:
        """Guess file format from content"""
        lines = content.strip().split('\n')

        # Check first non-empty line
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith('>'):
                return "FASTA"
            elif line.startswith('@'):
                return "FASTQ"
            else:
                return "UNKNOWN"

        return "UNKNOWN"

    @staticmethod
    def parse_file(file_path: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Parse sequence file (FASTA or FASTQ)

        Returns:
            Tuple of (format, sequences)
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            file_format = FastaParser.guess_format(content)

            if file_format == "FASTA":
                sequences = FastaParser.parse_fasta(content)
            elif file_format == "FASTQ":
                sequences = FastaParser.parse_fastq(content)
            else:
                raise ValueError(f"Unknown file format")

            return file_format, sequences

        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            raise


class SequenceValidator:
    """Sequence format validation"""

    VALID_DNA_CHARS = set('ATGCN')
    VALID_RNA_CHARS = set('AUGCN')
    VALID_PROTEIN_CHARS = set('ACDEFGHIKLMNPQRSTVWYXU*')

    @staticmethod
    def validate_dna_file(sequences: List[Dict[str, str]]) -> Tuple[bool, str]:
        """Validate DNA sequences in file"""
        for seq_data in sequences:
            sequence = seq_data['sequence'].upper()
            invalid_chars = set(sequence) - SequenceValidator.VALID_DNA_CHARS

            if invalid_chars:
                return False, f"Invalid DNA characters in {seq_data['id']}: {invalid_chars}"

        return True, "Valid"

    @staticmethod
    def validate_fasta_file(file_path: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Comprehensive FASTA file validation

        Returns:
            Tuple of (is_valid, message, sequences)
        """
        try:
            file_format, sequences = FastaParser.parse_file(file_path)

            if not sequences:
                return False, "No sequences found in file", []

            # Check for empty sequences
            for seq_data in sequences:
                if not seq_data['sequence']:
                    return False, f"Empty sequence: {seq_data['id']}", []

            # Get file size in MB
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)

            if file_size_mb > 100:
                return False, f"File too large: {file_size_mb:.2f} MB (max 100 MB)", []

            return True, "Valid FASTA file", sequences

        except Exception as e:
            return False, f"Error validating file: {str(e)}", []


class FileProcessor:
    """General file processing utilities"""

    @staticmethod
    def save_upload(file_content: bytes, upload_dir: str, file_name: str) -> str:
        """
        Save uploaded file

        Returns:
            Path to saved file
        """
        import os
        import uuid

        # Create upload directory if it doesn't exist
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename
        unique_name = f"{uuid.uuid4()}_{file_name}"
        file_path = os.path.join(upload_dir, unique_name)

        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_content)

        return file_path

    @staticmethod
    def is_allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

    @staticmethod
    def get_file_size_mb(file_path: str) -> float:
        """Get file size in MB"""
        return Path(file_path).stat().st_size / (1024 * 1024)
