"""
Annotation router — proxies Ensembl VEP REST API and gnomAD/population frequency endpoints.
This solves CORS and allows server-side caching in production.
"""
from fastapi import APIRouter, HTTPException
import httpx
from models.schemas import AnnotationRequest, PopFreqRequest, PathogenicityRequest

router = APIRouter()

ENSEMBL_BASE = "https://rest.ensembl.org"
TIMEOUT = 20.0


def _hg38_to_ensembl(chrom: str, pos: int, ref: str, alt: str) -> str:
    """Convert to Ensembl VEP HGVS-like notation."""
    c = chrom.replace("chr", "")
    if len(ref) == len(alt) == 1:
        return f"{c} {pos} . {ref} {alt} . . ."
    elif len(ref) > len(alt):
        # deletion
        start = pos + 1
        end = pos + len(ref) - len(alt)
        return f"{c} {start} {end} {ref[1:]}/- . . ."
    else:
        # insertion
        return f"{c} {pos} {pos} -/{alt[1:]} . . ."


@router.post("/vep")
async def annotate_vep(req: AnnotationRequest):
    """
    Annotate a variant using Ensembl VEP REST API.
    Returns consequences, SIFT, PolyPhen, gene, transcript data.
    """
    chrom = req.chromosome.replace("chr", "")
    allele_string = f"{req.ref}/{req.alt}"
    url = (
        f"{ENSEMBL_BASE}/vep/human/region"
        f"/{chrom}:{req.position}-{req.position + len(req.ref) - 1}/{req.alt}"
        f"?content-type=application/json&SIFT=b&PolyPhen=b&canonical=1"
        f"&hgvs=1&domains=1&numbers=1"
    )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                url,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 400:
                return {"error": "Variant not found in Ensembl", "results": []}
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "Ensembl VEP timed out")
    except Exception as e:
        raise HTTPException(502, f"VEP error: {e}")

    results = []
    for entry in data:
        for tc in entry.get("transcript_consequences", []):
            sift     = tc.get("sift_prediction", "")
            sift_sc  = tc.get("sift_score", "")
            poly     = tc.get("polyphen_prediction", "")
            poly_sc  = tc.get("polyphen_score", "")
            results.append({
                "gene":          tc.get("gene_symbol", req.gene or ""),
                "transcript":    tc.get("transcript_id", ""),
                "canonical":     tc.get("canonical", 0),
                "consequence":   ", ".join(tc.get("consequence_terms", [])),
                "impact":        tc.get("impact", ""),
                "hgvsc":         tc.get("hgvsc", ""),
                "hgvsp":         tc.get("hgvsp", ""),
                "sift":          f"{sift} ({sift_sc})" if sift else "",
                "polyphen":      f"{poly} ({poly_sc})" if poly else "",
                "exon":          tc.get("exon", ""),
                "amino_acids":   tc.get("amino_acids", ""),
                "codons":        tc.get("codons", ""),
                "biotype":       tc.get("biotype", ""),
            })

    return {
        "chromosome": req.chromosome,
        "position":   req.position,
        "ref":        req.ref,
        "alt":        req.alt,
        "results":    results,
        "most_severe": data[0].get("most_severe_consequence", "") if data else "",
    }


@router.post("/population-freq")
async def population_frequency(req: PopFreqRequest):
    """
    Fetch population allele frequencies from Ensembl (gnomAD, 1000 Genomes, ExAC).
    """
    chrom = req.chromosome.replace("chr", "")
    url = (
        f"{ENSEMBL_BASE}/vep/human/region"
        f"/{chrom}:{req.position}-{req.position + len(req.ref) - 1}/{req.alt}"
        f"?content-type=application/json&af=1&af_gnomad=1&af_1kg=1&af_exac=1"
    )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, headers={"Content-Type": "application/json"})
            if resp.status_code == 400:
                return {"error": "Variant not found", "frequencies": []}
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(502, f"Population freq error: {e}")

    freq_data = {}
    for entry in data:
        for tc in entry.get("transcript_consequences", []):
            if tc.get("canonical"):
                freq_data = {
                    "af_global":    tc.get("af", ""),
                    "af_gnomad":    tc.get("gnomad_af", ""),
                    "af_gnomad_afr": tc.get("gnomad_afr_af", ""),
                    "af_gnomad_amr": tc.get("gnomad_amr_af", ""),
                    "af_gnomad_eas": tc.get("gnomad_eas_af", ""),
                    "af_gnomad_nfe": tc.get("gnomad_nfe_af", ""),
                    "af_gnomad_sas": tc.get("gnomad_sas_af", ""),
                    "af_1kg_afr":   tc.get("af_afr", ""),
                    "af_1kg_amr":   tc.get("af_amr", ""),
                    "af_1kg_eas":   tc.get("af_eas", ""),
                    "af_1kg_eur":   tc.get("af_eur", ""),
                    "af_exac":      tc.get("exac_af", ""),
                }
                break
        if freq_data:
            break

    # PM2/BA1 interpretation helper
    gnomad = float(freq_data.get("af_gnomad") or 0)
    acmg_freq = (
        "BA1 — common (>5%): likely benign" if gnomad > 0.05
        else "BS1 — above expected (>1%)" if gnomad > 0.01
        else "PM2 supporting — absent/rare (<0.1%)" if gnomad < 0.001
        else "PM2 — low frequency (0.1-1%)"
    ) if gnomad else "PM2 supporting — not found in population databases"

    return {
        "chromosome": req.chromosome,
        "position":   req.position,
        "ref":        req.ref,
        "alt":        req.alt,
        "frequencies": freq_data,
        "acmg_interpretation": acmg_freq,
    }


@router.post("/pathogenicity")
async def pathogenicity_scores(req: PathogenicityRequest):
    """
    Retrieve SIFT, PolyPhen-2, CADD, and integrated pathogenicity via VEP.
    Adds an integrated assessment based on score thresholds.
    """
    vep_req = AnnotationRequest(
        chromosome=req.chromosome,
        position=req.position,
        ref=req.ref,
        alt=req.alt,
        gene=req.gene,
        rsid=req.rsid,
    )
    vep_data = await annotate_vep(vep_req)

    # Find canonical transcript scores
    canonical = next(
        (r for r in vep_data.get("results", []) if r.get("canonical")),
        vep_data.get("results", [{}])[0] if vep_data.get("results") else {}
    )

    sift_raw    = canonical.get("sift", "")
    polyphen_raw = canonical.get("polyphen", "")

    # Parse scores from strings like "deleterious (0.02)"
    import re
    def extract_score(s):
        m = re.search(r"\(([0-9.]+)\)", s)
        return float(m.group(1)) if m else None

    sift_score = extract_score(sift_raw)
    poly_score = extract_score(polyphen_raw)

    # Integrated assessment
    evidence = []
    if sift_score is not None:
        if sift_score < 0.05:
            evidence.append(("SIFT deleterious", "pathogenic", sift_score))
        else:
            evidence.append(("SIFT tolerated", "benign", sift_score))

    if poly_score is not None:
        if poly_score > 0.908:
            evidence.append(("PolyPhen-2 probably damaging", "pathogenic", poly_score))
        elif poly_score > 0.446:
            evidence.append(("PolyPhen-2 possibly damaging", "uncertain", poly_score))
        else:
            evidence.append(("PolyPhen-2 benign", "benign", poly_score))

    pathogenic_hits = sum(1 for _, verdict, _ in evidence if verdict == "pathogenic")
    benign_hits     = sum(1 for _, verdict, _ in evidence if verdict == "benign")

    if pathogenic_hits >= 2:
        integrated = "Likely pathogenic (PP3)"
    elif pathogenic_hits == 1 and benign_hits == 0:
        integrated = "Uncertain — weak pathogenic signal"
    elif benign_hits >= 2:
        integrated = "Likely benign (BP4)"
    elif not evidence:
        integrated = "Insufficient in-silico data"
    else:
        integrated = "Conflicting in-silico predictions"

    return {
        "chromosome":         req.chromosome,
        "position":           req.position,
        "ref":                req.ref,
        "alt":                req.alt,
        "gene":               canonical.get("gene", req.gene or ""),
        "consequence":        canonical.get("consequence", ""),
        "hgvsp":              canonical.get("hgvsp", ""),
        "sift":               sift_raw,
        "polyphen":           polyphen_raw,
        "evidence":           [{"tool": t, "verdict": v, "score": s} for t, v, s in evidence],
        "integrated_verdict": integrated,
        "acmg_criteria":      "PP3" if pathogenic_hits >= 2 else ("BP4" if benign_hits >= 2 else ""),
    }
