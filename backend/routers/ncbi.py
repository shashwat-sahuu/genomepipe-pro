from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from services.ncbi_service import (
    search_clinvar, search_pubmed, lookup_dbsnp,
    search_genbank_gene, fetch_genbank_accession,
)

router = APIRouter()


@router.get("/clinvar")
async def clinvar_search(
    gene:         str,
    variant:      Optional[str] = None,
    significance: Optional[str] = None,
    retmax:       int = Query(50, ge=1, le=200),
):
    """Proxy ClinVar search — resolves browser CORS issues."""
    try:
        return await search_clinvar(gene, variant, significance, retmax)
    except Exception as e:
        raise HTTPException(502, f"ClinVar error: {e}")


@router.get("/pubmed")
async def pubmed_search(
    query:  str,
    retmax: int = Query(20, ge=1, le=100),
):
    """Proxy PubMed search."""
    try:
        return await search_pubmed(query, retmax)
    except Exception as e:
        raise HTTPException(502, f"PubMed error: {e}")


@router.get("/dbsnp/{rsid}")
async def dbsnp_lookup(rsid: str):
    """Proxy dbSNP single-SNP lookup."""
    try:
        result = await lookup_dbsnp(rsid)
        if not result:
            raise HTTPException(404, f"rs{rsid.lstrip('rs')} not found in dbSNP")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"dbSNP error: {e}")


@router.get("/genbank/search")
async def genbank_gene_search(
    gene:   str,
    retmax: int = Query(10, ge=1, le=50),
):
    """Search GenBank nucleotide DB for a gene."""
    try:
        return await search_genbank_gene(gene, retmax)
    except Exception as e:
        raise HTTPException(502, f"GenBank error: {e}")


@router.get("/genbank/{accession}")
async def genbank_accession(accession: str):
    """Fetch a specific GenBank record by accession number."""
    try:
        return await fetch_genbank_accession(accession)
    except Exception as e:
        raise HTTPException(502, f"GenBank error: {e}")
