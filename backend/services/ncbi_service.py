"""
Async NCBI E-utilities service.
All calls go through the backend so the browser never hits CORS issues.
"""
import httpx
import os
import asyncio
from typing import Optional, List
import xml.etree.ElementTree as ET

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY   = os.getenv("NCBI_API_KEY", "")          # optional — raises rate limit 3→10 req/s
TIMEOUT   = 15.0


def _key_param() -> str:
    return f"&api_key={API_KEY}" if API_KEY else ""


async def search_clinvar(
    gene: str,
    variant: Optional[str] = None,
    significance: Optional[str] = None,
    retmax: int = 50,
) -> List[dict]:
    """Search ClinVar and return structured variant records."""
    query_parts = [f"{gene}[gene]"]
    if variant:
        query_parts.append(variant)
    if significance and significance.lower() not in ("all", ""):
        sig_map = {
            "pathogenic":        "Pathogenic",
            "likely pathogenic":  "Likely pathogenic",
            "uncertain":         "Uncertain significance",
            "likely benign":     "Likely benign",
            "benign":            "Benign",
            "risk factor":       "risk factor",
        }
        sig_val = sig_map.get(significance.lower(), significance)
        query_parts.append(f'"{sig_val}"[clinsig]')

    query = " AND ".join(query_parts)

    search_url = (
        f"{NCBI_BASE}/esearch.fcgi?db=clinvar&term={query}"
        f"&retmax={retmax}&retmode=json{_key_param()}"
    )

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        search_resp = await client.get(search_url)
        search_resp.raise_for_status()
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])

    if not ids:
        return []

    summary_url = (
        f"{NCBI_BASE}/esummary.fcgi?db=clinvar&id={','.join(ids)}"
        f"&retmode=json{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        summ_resp = await client.get(summary_url)
        summ_resp.raise_for_status()
        result = summ_resp.json().get("result", {})

    records = []
    for uid in result.get("uids", []):
        r = result.get(uid, {})
        germline = r.get("germline_classification", {})
        records.append({
            "clinvar_id":    uid,
            "title":         r.get("title", ""),
            "gene":          r.get("genes", [{}])[0].get("symbol", gene) if r.get("genes") else gene,
            "significance":  germline.get("description", "Unknown"),
            "review_status": germline.get("review_status", ""),
            "condition":     ", ".join(
                [t.get("trait_name", "") for t in r.get("trait_set", [])[:3]]
            ),
            "hgvs":          r.get("title", ""),
            "last_evaluated": germline.get("last_evaluated", ""),
            "accession":     r.get("accession", ""),
        })
    return records


async def search_pubmed(query: str, retmax: int = 20) -> List[dict]:
    """Search PubMed and return article summaries."""
    search_url = (
        f"{NCBI_BASE}/esearch.fcgi?db=pubmed&term={query}"
        f"&retmax={retmax}&retmode=json{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(search_url)
        resp.raise_for_status()
        ids = resp.json().get("esearchresult", {}).get("idlist", [])

    if not ids:
        return []

    summary_url = (
        f"{NCBI_BASE}/esummary.fcgi?db=pubmed&id={','.join(ids)}"
        f"&retmode=json{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(summary_url)
        resp.raise_for_status()
        result = resp.json().get("result", {})

    articles = []
    for uid in result.get("uids", []):
        r = result.get(uid, {})
        authors = [a.get("name", "") for a in r.get("authors", [])[:3]]
        articles.append({
            "pmid":     uid,
            "title":    r.get("title", ""),
            "authors":  authors,
            "journal":  r.get("fulljournalname", r.get("source", "")),
            "year":     r.get("pubdate", "")[:4],
            "doi":      next((e.get("value","") for e in r.get("articleids",[]) if e.get("idtype")=="doi"), ""),
            "url":      f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })
    return articles


async def lookup_dbsnp(rsid: str) -> dict:
    """Fetch a single SNP record from dbSNP."""
    rsid_clean = rsid.lstrip("rRsS")
    url = (
        f"{NCBI_BASE}/esummary.fcgi?db=snp&id={rsid_clean}"
        f"&retmode=json{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        result = resp.json().get("result", {})

    r = result.get(rsid_clean, {})
    if not r:
        return {}

    # Parse allele frequencies if present
    freq_list = []
    for study in r.get("primary_snapshot_data", {}).get("allele_annotations", []):
        for freq in study.get("frequency", []):
            freq_list.append({
                "study": freq.get("study_name", ""),
                "ref_allele": freq.get("observation", {}).get("deleted_sequence", ""),
                "alt_allele": freq.get("observation", {}).get("inserted_sequence", ""),
                "allele_count": freq.get("allele_count", 0),
                "total_count": freq.get("total_count", 0),
            })

    return {
        "rsid":            f"rs{rsid_clean}",
        "refsnp_id":       r.get("refsnp_id", rsid_clean),
        "organism":        r.get("organism", ""),
        "genes":           [g.get("locus", "") for g in r.get("genes", [])],
        "hgvs":            r.get("hgvs", []),
        "clinical_sig":    r.get("clinical_significance", []),
        "allele_origin":   r.get("allele_origin", ""),
        "variant_type":    r.get("variant_type", ""),
        "frequencies":     freq_list[:10],
        "last_update":     r.get("update_date", ""),
    }


async def search_genbank_gene(gene: str, retmax: int = 10) -> List[dict]:
    """Search GenBank nucleotide DB for mRNA records of a gene."""
    query = f"{gene}[gene] AND Homo sapiens[organism] AND mRNA[filter]"
    search_url = (
        f"{NCBI_BASE}/esearch.fcgi?db=nucleotide&term={query}"
        f"&retmax={retmax}&retmode=json{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(search_url)
        resp.raise_for_status()
        ids = resp.json().get("esearchresult", {}).get("idlist", [])

    if not ids:
        return []

    summary_url = (
        f"{NCBI_BASE}/esummary.fcgi?db=nucleotide&id={','.join(ids)}"
        f"&retmode=json{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(summary_url)
        resp.raise_for_status()
        result = resp.json().get("result", {})

    records = []
    for uid in result.get("uids", []):
        r = result.get(uid, {})
        records.append({
            "accession":   r.get("accessionversion", ""),
            "title":       r.get("title", ""),
            "length":      r.get("slen", 0),
            "organism":    r.get("organism", ""),
            "update_date": r.get("updatedate", ""),
            "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{r.get('accessionversion','')}",
        })
    return records


async def fetch_genbank_accession(accession: str) -> dict:
    """Fetch details for a specific GenBank accession."""
    url = (
        f"{NCBI_BASE}/efetch.fcgi?db=nucleotide&id={accession}"
        f"&rettype=gb&retmode=text{_key_param()}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    # Return raw GenBank flat-file text (truncated)
    text = resp.text[:5000]
    return {"accession": accession, "genbank_text": text}
