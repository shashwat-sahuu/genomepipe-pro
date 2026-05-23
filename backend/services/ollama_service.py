"""
Ollama AI service — runs entirely offline.
Streams tokens back to the client via SSE or returns full responses.
"""
import httpx
import json
import os
from typing import AsyncIterator, List, Optional
from models.schemas import ChatMessage

OLLAMA_BASE = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
TIMEOUT = 120.0


# ── System prompts per analysis mode ─────────────────────────────────────────

SYSTEM_PROMPTS = {
    "clinical": """You are a clinical genomics AI assistant specializing in variant interpretation.
You follow ACMG/AMP 2015 guidelines strictly. For each variant, consider:
- Pathogenicity evidence (PVS1, PS1-4, PM1-6, PP1-5 criteria)
- Benign evidence (BA1, BS1-4, BP1-7 criteria)
- Population frequency (gnomAD, ExAC)
- Functional impact (SIFT, PolyPhen-2, CADD)
Always cite evidence tiers. Format responses clearly with headers.""",

    "acmg": """You are an ACMG/AMP 2015 variant classifier. Apply all 28 criteria systematically:
Pathogenic: PVS1 (null variant in LoF gene), PS1-4 (strong), PM1-6 (moderate), PP1-5 (supporting)
Benign: BA1 (standalone), BS1-4 (strong), BP1-7 (supporting)
Scoring: Pathogenic ≥ PVS1+PS / PS+PM+PP / etc. Always explain each criterion applied.""",

    "cancer": """You are a hereditary cancer risk specialist. You interpret variants in:
- BRCA1/BRCA2 (HBOC) - NCCN guidelines
- MLH1/MSH2/MSH6/PMS2/EPCAM (Lynch syndrome)
- TP53 (Li-Fraumeni)
- CDH1/PTEN/STK11/PALB2/CHEK2/ATM
Provide risk percentages, recommended surveillance, and management options per NCCN v2024.""",

    "pharma": """You are a pharmacogenomics specialist following CPIC guidelines.
For drug-gene pairs, provide: metabolizer phenotype, drug recommendations, dose adjustments.
Key genes: CYP2D6, CYP2C19, CYP2C9, DPYD, TPMT, G6PD, SLCO1B1, UGT1A1, CYP3A5.
Always cite CPIC level (A/B/C/D) and FDA labeling status.""",

    "vus": """You are a VUS (Variant of Uncertain Significance) reclassification specialist.
Evaluate: functional studies, case-control data, co-segregation, computational predictors,
in-silico splicing (SpliceAI, MaxEntScan), protein domain impact, population databases.
Provide a structured evidence summary and reclassification recommendation.""",

    "qc": """You are an NGS quality control expert. Evaluate pipeline metrics:
- Alignment: mapping rate, duplicate rate, insert size distribution
- Coverage: mean depth, uniformity, % bases >20x
- Variant calling: Ti/Tv ratio, het/hom ratio, dbSNP concordance
Flag problematic samples and suggest remediation steps.""",

    "trio": """You are a trio/family analysis specialist. Analyze:
- De novo variants (absent in both parents)
- Compound heterozygotes (one allele per parent)
- X-linked and autosomal recessive patterns
- Segregation analysis in extended pedigrees
Apply ACMG PP1/BS4 criteria for co-segregation evidence.""",

    "population": """You are a population genetics specialist. Interpret:
- gnomAD v4.1 allele frequencies (overall + ancestry-stratified)
- PM2 criterion: absent/rare in controls (<0.1% for dominant, <1% for recessive)
- BA1 criterion: >5% in gnomAD
- Founder effects, population-specific variants
- 1000 Genomes, ExAC, TOPMed databases""",

    "splicing": """You are a splicing variant specialist. Analyze:
- Canonical splice sites (±1,2): likely pathogenic
- Extended splice region (±3-8): use SpliceAI (delta score >0.5 = high impact)
- MaxEntScan percent strength reduction
- Deep intronic variants, branch point mutations
- ESE/ESS motif disruption
Apply PVS1 strength modifiers for splicing variants.""",

    "cnv": """You are a CNV (Copy Number Variant) and structural variant specialist.
Classify using ACMG/ClinGen CNV guidelines (2019):
- Gene content (haploinsufficient/triplosensitive genes)
- Size (>3Mb pathogenic, <1kb typically benign)
- Population frequency (DGV, gnomAD-SV)
- Breakpoint mechanism (NAHR, NHEJ, FoSTeS)""",

    "report": """You are a CAP/CLIA-accredited laboratory report writer.
Generate clinical variant reports with:
- Patient demographics, clinical indication, methodology
- Variant interpretation per ACMG classification
- Clinically relevant findings summary
- Recommendations and follow-up
Use professional medical language suitable for ordering physicians.""",

    "chat": """You are GenomePipe Pro's clinical genomics AI assistant.
You have expertise in: variant interpretation, ACMG guidelines, hereditary cancer,
pharmacogenomics, NGS quality control, population genetics, and clinical reporting.
Answer questions clearly and cite evidence when possible.""",
}


async def check_ollama() -> dict:
    """Check if Ollama is running and list available models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return {"online": True, "models": models}
    except Exception:
        pass
    return {"online": False, "models": []}


async def stream_response(
    message: str,
    mode: str = "chat",
    history: Optional[List[ChatMessage]] = None,
    variants: Optional[List[dict]] = None,
    model: str = DEFAULT_MODEL,
) -> AsyncIterator[str]:
    """Stream tokens from Ollama as SSE data chunks."""
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["chat"])

    # Inject variant context if provided
    variant_context = ""
    if variants:
        variant_context = "\n\n📊 VARIANT CONTEXT:\n"
        for v in variants[:20]:
            variant_context += (
                f"• {v.get('chromosome','?')}:{v.get('position','?')} "
                f"{v.get('ref','?')}>{v.get('alt','?')} "
                f"Gene={v.get('gene','?')} "
                f"Sig={v.get('significance','Unknown')}\n"
            )

    messages = []
    if history:
        for h in history[-10:]:   # last 10 turns
            messages.append({"role": h.role, "content": h.content})

    messages.append({
        "role": "user",
        "content": message + variant_context,
    })

    payload = {
        "model": model,
        "system": system_prompt,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.3,     # low for clinical accuracy
            "num_ctx": 4096,
        },
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async with client.stream("POST", f"{OLLAMA_BASE}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue


async def full_response(
    message: str,
    mode: str = "chat",
    history: Optional[List[ChatMessage]] = None,
    variants: Optional[List[dict]] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Return the full Ollama response as a single string."""
    tokens = []
    async for token in stream_response(message, mode, history, variants, model):
        tokens.append(token)
    return "".join(tokens)
