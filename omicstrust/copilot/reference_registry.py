from __future__ import annotations

import re
from typing import Any

from omicstrust.copilot.public_search import PublicDatasetCandidate, PublicDatasetSearchQuery


REGISTRY_NOTE = "Fallback/reference metadata; verify live source before download or audit."


REFERENCE_DATASETS: list[dict[str, Any]] = [
    {
        "accession_id": "GSE78220",
        "title": "Metastatic melanoma pre-treatment transcriptomics with anti-PD-1 response metadata",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE78220",
        "diseases": ["melanoma", "metastatic melanoma"],
        "treatments": ["anti-PD1 immunotherapy", "anti-pd-1", "pd-1", "pembrolizumab", "nivolumab", "immunotherapy"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["rna_seq"],
        "sample_context": ["tumor", "biopsy", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE145996",
        "title": "Melanoma immune checkpoint blockade response transcriptomic metadata reference",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE145996",
        "diseases": ["melanoma", "metastatic melanoma", "advanced melanoma"],
        "treatments": ["checkpoint blockade", "immune checkpoint inhibitor", "immunotherapy", "anti-PD1 immunotherapy"],
        "response_terms": ["response", "responder", "non-responder", "progressive disease"],
        "omics_types": ["gene_expression"],
        "sample_context": ["tumor", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE93157",
        "title": "Melanoma checkpoint immunotherapy response public dataset metadata reference",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE93157",
        "diseases": ["melanoma", "metastatic melanoma"],
        "treatments": ["anti-PD1 immunotherapy", "pd-1", "checkpoint blockade", "immunotherapy"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["ncounter"],
        "sample_context": ["tumor", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": [
            "Fallback reference registry candidate. Verify live source metadata before download or audit.",
            "Panel-style nCounter metadata may be less suitable than genome-wide RNA-seq.",
        ],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE33377",
        "title": "Rheumatoid arthritis anti-TNF treatment response expression profiling of responders and non-responders",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE33377",
        "diseases": ["rheumatoid arthritis", "RA", "inflammatory arthritis"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "adalimumab", "etanercept"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["gene_expression"],
        "sample_context": ["blood", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE16879",
        "title": "Inflammatory bowel disease mucosal expression profiling before and after first infliximab treatment with response signatures",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE16879",
        "diseases": ["inflammatory bowel disease", "IBD", "Crohn's disease", "ulcerative colitis"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "IFX"],
        "response_terms": ["response", "responder", "non-responder", "mucosal healing"],
        "omics_types": ["gene_expression"],
        "sample_context": ["mucosa", "biopsy", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE14580",
        "title": "Colonic mucosal gene expression for predicting infliximab response in ulcerative colitis",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE14580",
        "diseases": ["inflammatory bowel disease", "IBD", "ulcerative colitis", "UC"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "IFX"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["gene_expression"],
        "sample_context": ["mucosa", "biopsy", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE107865",
        "title": "Whole blood expression from Crohn's disease patients before anti-TNF or infliximab with responder assessment",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE107865",
        "diseases": ["inflammatory bowel disease", "IBD", "Crohn's disease", "Crohn disease"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "IFX"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["gene_expression"],
        "sample_context": ["blood", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE23597",
        "title": "Colonic biopsy expression profiling in ulcerative colitis patients treated with infliximab comparing responders and non-responders",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE23597",
        "diseases": ["inflammatory bowel disease", "IBD", "ulcerative colitis", "UC"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "IFX"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["gene_expression"],
        "sample_context": ["mucosa", "biopsy", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE42296",
        "title": "Peripheral blood gene expression predicting infliximab response in Crohn's disease and rheumatoid arthritis",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE42296",
        "diseases": ["inflammatory bowel disease", "IBD", "Crohn's disease", "rheumatoid arthritis", "RA"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "IFX"],
        "response_terms": ["response", "responder", "non-responder"],
        "omics_types": ["gene_expression"],
        "sample_context": ["blood", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": [
            "Fallback reference registry candidate. Verify live source metadata before download or audit.",
            "Mixed Crohn's disease and rheumatoid arthritis context; inspect sample annotations before treating as disease-specific.",
        ],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE191328",
        "title": "Inflammatory bowel disease longitudinal multi-omics and RNA-seq related to anti-TNF response",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE191328",
        "diseases": ["inflammatory bowel disease", "IBD", "Crohn's disease", "ulcerative colitis"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "adalimumab"],
        "response_terms": ["response", "treatment outcome", "disease activity"],
        "omics_types": ["rna_seq", "gene_expression"],
        "sample_context": ["blood", "tissue", "patient"],
        "organism": "Homo sapiens",
        "baseline": True,
        "known_limitations": ["Fallback reference registry candidate. Verify live source metadata before download or audit."],
        "registry_note": REGISTRY_NOTE,
    },
    {
        "accession_id": "GSE134809",
        "title": "Crohn's disease sequencing and single-cell context associated with resistance to anti-TNF therapy",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE134809",
        "diseases": ["inflammatory bowel disease", "IBD", "Crohn's disease", "Crohn disease"],
        "treatments": ["TNF inhibitor", "anti-TNF", "infliximab", "adalimumab"],
        "response_terms": ["resistance", "response", "non-responder"],
        "omics_types": ["single_cell", "rna_seq"],
        "sample_context": ["single-cell", "tissue", "patient"],
        "organism": "Homo sapiens",
        "baseline": "unknown",
        "known_limitations": [
            "Fallback reference registry candidate. Verify live source metadata before download or audit.",
            "Single-cell/resistance context may require careful metadata review before treating as baseline anti-TNF response.",
        ],
        "registry_note": REGISTRY_NOTE,
    },
]


def search_reference_registry(query: PublicDatasetSearchQuery) -> list[PublicDatasetCandidate]:
    query_disease_terms = query.disease_terms or query.disease_synonyms or _query_terms(query.disease or "")
    query_treatment_terms = query.treatment_terms or query.treatment_synonyms or _query_terms(query.treatment or "")
    if not query_disease_terms and not query_treatment_terms:
        return []
    candidates: list[PublicDatasetCandidate] = []
    for record in REFERENCE_DATASETS:
        if query_disease_terms and not _overlaps(query_disease_terms, record["diseases"]):
            continue
        if query_treatment_terms and not _overlaps(query_treatment_terms, record["treatments"]):
            continue
        response_terms = [
            term for term in record["response_terms"] if not query.response_terms or _overlaps(query.response_terms, [term])
        ]
        if query.response_terms and not response_terms:
            response_terms = list(record["response_terms"][:2])
        candidates.append(
            PublicDatasetCandidate(
                accession_id=record["accession_id"],
                title=record["title"],
                source="local_reference_registry",
                metadata_source="fallback_registry",
                url=record["url"],
                organism=record["organism"],
                disease=query.disease or str(record["diseases"][0]),
                treatment_terms_found=[
                    term for term in record["treatments"] if not query_treatment_terms or _overlaps(query_treatment_terms, [term])
                ],
                response_terms_found=response_terms,
                omics_type=_best_omics(record["omics_types"], query.omics_types),
                sample_context_found=[term for term in record["sample_context"] if not query.sample_context or term in query.sample_context]
                or list(record["sample_context"]),
                sample_count=record.get("sample_count"),
                baseline_or_pretreatment_evidence=record["baseline"] is True,
                limitations=[
                    *record["known_limitations"],
                    record["registry_note"],
                    "This candidate is not an analysis result and is included only when live public metadata search has low recall or is unavailable.",
                ],
            )
        )
    return candidates


def _best_omics(record_omics: list[str], query_omics: list[str]) -> str | None:
    for omics_type in query_omics:
        if omics_type in record_omics:
            return omics_type
    return record_omics[0] if record_omics else None


def _query_terms(query_text: str) -> list[str]:
    stop = {"search", "public", "datasets", "dataset", "for", "with", "and", "or", "data", "omics"}
    return [term for term in _normalize(query_text).split() if len(term) > 1 and term not in stop]


def _overlaps(query_terms: list[str], record_terms: list[str]) -> bool:
    haystack = _normalize(" ".join(record_terms))
    normalized_terms = [_normalize(term) for term in query_terms]
    for term in normalized_terms:
        if not term:
            continue
        if len(term) <= 3:
            if re.search(rf"\b{re.escape(term)}\b", haystack):
                return True
            continue
        if term in haystack:
            return True
        pieces = [piece for piece in term.split() if len(piece) > 1]
        if len(pieces) > 1 and all(re.search(rf"\b{re.escape(piece)}\b", haystack) for piece in pieces):
            return True
    return False


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").replace("-", " ").replace("_", " ").split())
