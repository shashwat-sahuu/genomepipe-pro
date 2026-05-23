"""
VCF parsing utilities.
Parses VCF text/content and returns a list of variant dicts
compatible with the Variant schema.
"""
import re
from typing import List


def parse_vcf(content: str) -> List[dict]:
    """Parse a VCF file content string and return variant dicts."""
    variants = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 5:
            continue

        chrom = parts[0] if parts[0].startswith("chr") else f"chr{parts[0]}"
        try:
            pos = int(parts[1])
        except ValueError:
            continue

        rsid = parts[2] if parts[2] != "." else None
        ref  = parts[3]
        alts = parts[4].split(",")

        info_str = parts[7] if len(parts) > 7 else ""
        info = _parse_info(info_str)
        gene = info.get("GENE", info.get("ANN", "").split("|")[3] if info.get("ANN") else None)

        fmt_values = {}
        if len(parts) > 8:
            fmt_keys = parts[8].split(":")
            if len(parts) > 9:
                fmt_vals = parts[9].split(":")
                fmt_values = dict(zip(fmt_keys, fmt_vals))

        dp = fmt_values.get("DP", info.get("DP", ""))
        af = _parse_af(fmt_values, info)

        for alt in alts:
            variants.append({
                "chromosome":   chrom,
                "position":     pos,
                "ref":          ref,
                "alt":          alt,
                "gene":         gene,
                "rsid":         rsid,
                "significance": "Unknown",
                "source":       "VCF",
                "notes":        f"DP={dp} AF={af}" if dp or af else None,
            })

    return variants


def _parse_info(info_str: str) -> dict:
    result = {}
    for item in info_str.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            result[k] = v
        else:
            result[item] = True
    return result


def _parse_af(fmt: dict, info: dict) -> str:
    for key in ("AF", "VAF", "FREQ", "FA"):
        if key in fmt:
            return fmt[key]
        if key in info:
            return str(info[key])
    # Try AD field
    ad = fmt.get("AD", "")
    if "," in str(ad):
        try:
            parts = str(ad).split(",")
            ref_d, alt_d = int(parts[0]), int(parts[1])
            total = ref_d + alt_d
            if total > 0:
                return f"{alt_d/total:.3f}"
        except Exception:
            pass
    return ""
