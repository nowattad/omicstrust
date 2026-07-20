from __future__ import annotations

import json
import http.client
import ipaddress
import re
import socket
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any

import defusedxml.ElementTree as DET

from omicstrust.case_studies.registry import list_case_studies


RUO_DISCLAIMER = "Research Use Only. Public dataset search is not clinical decision-making and does not prove treatment efficacy."
SAFE_FETCH_MAX_BYTES = 5_000_000
SAFE_FETCH_TIMEOUT_SECONDS = 15
SAFE_FETCH_ACCEPTED_TYPES = {
    "application/json",
    "application/xml",
    "application/problem+json",
    "text/json",
    "text/plain",
    "text/xml",
}
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "0.0.0.0"}
BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".test")

DEFAULT_SOURCES = ["GEO", "PubMed", "ArrayExpress", "BioStudies", "local_reference_registry"]
BASELINE_TERMS = [
    "baseline",
    "pre-treatment",
    "pretreatment",
    "pre treatment",
    "pre therapy",
    "pre-therapy",
    "before treatment",
    "prior to treatment",
    "pre immunotherapy",
    "pre-immunotherapy",
    "treatment-naive",
    "treatment naive",
]
RESPONSE_TERMS = [
    "response",
    "responder",
    "non-responder",
    "nonresponder",
    "non-response",
    "resistance",
    "sensitive",
    "mortality",
    "survival",
    "outcome",
    "clinical response",
    "treatment outcome",
    "disease activity",
    "remission",
    "non-remission",
    "mucosal healing",
    "recist",
    "complete response",
    "partial response",
    "stable disease",
    "progressive disease",
]
OMICS_TERMS = {
    "rna_seq": ["rna-seq", "rnaseq", "rna seq", "rna sequencing", "bulk rna-seq", "transcriptome sequencing"],
    "single_cell": ["single-cell", "single cell", "scrna", "scRNA-seq".lower()],
    "miRNA_expression": ["mirna", "microRNA".lower(), "mirna expression", "microrna expression", "micro-rna", "micro rna"],
    "gene_expression": ["gene expression", "microarray", "transcriptomic", "transcriptomics"],
    "expression_profiling": ["expression profiling", "expression profile", "expression data", "expression dataset", "expression datasets"],
    "ncounter": ["nanostring", "nCounter".lower()],
}
DISEASE_ALIASES = {
    "melanoma": ["melanoma", "metastatic melanoma", "cutaneous melanoma", "advanced melanoma"],
    "rheumatoid arthritis": ["rheumatoid arthritis", "RA", "arthritis rheumatoid", "inflammatory arthritis"],
    "inflammatory bowel disease": [
        "inflammatory bowel disease",
        "IBD",
        "Crohn's disease",
        "Crohn disease",
        "Crohns disease",
        "CD",
        "ulcerative colitis",
        "UC",
        "colitis",
        "ileitis",
    ],
    "sepsis": ["sepsis", "septic shock", "bloodstream infection", "critical illness", "ICU infection"],
    "breast cancer": ["breast cancer", "breast carcinoma"],
    "lung cancer": ["lung cancer", "NSCLC", "non-small cell lung"],
    "colorectal cancer": ["colorectal cancer", "colon cancer"],
    "systemic lupus erythematosus": ["systemic lupus erythematosus", "SLE", "lupus"],
    "multiple sclerosis": ["multiple sclerosis", "relapsing-remitting multiple sclerosis", "relapsing remitting multiple sclerosis", "RRMS", "MS"],
    "asthma": ["asthma", "severe asthma"],
    "transplant rejection": ["transplant rejection", "allograft rejection", "graft rejection"],
}
TREATMENT_ALIASES = {
    "anti-PD1 immunotherapy": [
        "anti-pd1",
        "anti-pd-1",
        "pd1",
        "pd-1",
        "pdcd1",
        "pd-1 blockade",
        "pd1 blockade",
        "checkpoint blockade",
        "immune checkpoint blockade",
        "ICI",
        "pembrolizumab",
        "nivolumab",
        "immune checkpoint inhibitor",
    ],
    "TNF inhibitor": [
        "tnf inhibitor",
        "tnf inhibitors",
        "tnf antagonist",
        "anti-tnf",
        "anti tnf",
        "infliximab",
        "adalimumab",
        "golimumab",
        "certolizumab",
        "etanercept",
        "IFX",
    ],
    "interferon beta": [
        "interferon beta",
        "interferon-beta",
        "ifn beta",
        "ifn-beta",
        "IFN beta",
        "IFN-beta",
        "ifnb",
        "IFNB",
        "avonex",
        "rebif",
        "betaseron",
        "betaferon",
        "Avonex",
        "Rebif",
        "Betaseron",
        "Betaferon",
    ],
    "biologic therapy": [
        "biologic therapy",
        "biologic",
        "biologics",
        "monoclonal antibody",
        "targeted therapy",
    ],
    "vasopressor": ["vasopressor", "vasopressin", "norepinephrine", "noradrenaline", "catecholamine", "shock treatment"],
    "chemotherapy": ["chemotherapy", "chemo", "taxane", "anthracycline"],
    "immunotherapy": ["immunotherapy", "checkpoint", "checkpoint blockade", "immune checkpoint"],
}
SAMPLE_CONTEXT_TERMS = {
    "blood": ["blood", "whole blood", "peripheral blood", "pbmc", "pbmcs"],
    "tumor": ["tumor", "tumour", "metastasis", "lesion"],
    "biopsy": ["biopsy", "biopsies"],
    "tissue": ["tissue", "specimen"],
    "mucosa": ["mucosa", "mucosal", "colonic mucosa", "ileal mucosa", "colon biopsy"],
    "single-cell": ["single-cell", "single cell", "scrna", "scRNA-seq".lower()],
    "patient": ["patient", "patients", "human subject", "cohort"],
}
CONTEXTUAL_TREATMENT_EXPANSIONS = {
    "asthma": [
        "omalizumab",
        "mepolizumab",
        "reslizumab",
        "benralizumab",
        "dupilumab",
        "tezepelumab",
        "anti-IgE",
        "anti-IL5",
        "anti-IL-5",
        "anti-IL5R",
        "anti-IL-5R",
        "anti-IL4R",
        "anti-IL-4R",
        "anti-IL13",
        "anti-IL-13",
        "anti-TSLP",
    ],
    "systemic lupus erythematosus": [
        "belimumab",
        "rituximab",
        "anifrolumab",
        "anti-BAFF",
        "anti-BLyS",
        "anti-CD20",
        "type I interferon blockade",
    ],
    "inflammatory bowel disease": [
        "infliximab",
        "adalimumab",
        "golimumab",
        "certolizumab",
        "vedolizumab",
        "ustekinumab",
        "anti-TNF",
        "anti-integrin",
        "anti-IL12/23",
    ],
    "psoriasis": [
        "secukinumab",
        "ixekizumab",
        "brodalumab",
        "ustekinumab",
        "guselkumab",
        "risankizumab",
        "tildrakizumab",
        "IL17 inhibitor",
        "IL-17 inhibitor",
        "IL23 inhibitor",
        "IL-23 inhibitor",
    ],
}
EXPLICIT_TREATMENT_CLASS_EXPANSIONS = {
    "secukinumab": ["IL17 inhibitor", "IL-17 inhibitor"],
    "ixekizumab": ["IL17 inhibitor", "IL-17 inhibitor"],
    "brodalumab": ["IL17 inhibitor", "IL-17 inhibitor"],
    "omalizumab": ["anti-IgE"],
    "mepolizumab": ["anti-IL5", "anti-IL-5"],
    "reslizumab": ["anti-IL5", "anti-IL-5"],
    "benralizumab": ["anti-IL5R", "anti-IL-5R"],
    "dupilumab": ["anti-IL4R", "anti-IL-4R", "anti-IL13", "anti-IL-13"],
    "tezepelumab": ["anti-TSLP"],
    "belimumab": ["anti-BAFF", "anti-BLyS"],
    "rituximab": ["anti-CD20"],
    "infliximab": ["anti-TNF"],
    "adalimumab": ["anti-TNF"],
    "golimumab": ["anti-TNF"],
    "certolizumab": ["anti-TNF"],
    "vedolizumab": ["anti-integrin"],
    "ustekinumab": ["anti-IL12/23"],
}


@dataclass
class PublicDatasetSearchQuery:
    user_goal: str | None = None
    disease: str | None = None
    disease_terms_explicit: list[str] = field(default_factory=list)
    disease_terms_expanded: list[str] = field(default_factory=list)
    disease_terms: list[str] = field(default_factory=list)
    disease_synonyms: list[str] = field(default_factory=list)
    treatment: str | None = None
    treatment_terms_explicit: list[str] = field(default_factory=list)
    treatment_terms_expanded: list[str] = field(default_factory=list)
    treatment_terms: list[str] = field(default_factory=list)
    treatment_synonyms: list[str] = field(default_factory=list)
    response_terms_explicit: list[str] = field(default_factory=list)
    response_terms_expanded: list[str] = field(default_factory=list)
    response_terms: list[str] = field(default_factory=list)
    omics_types: list[str] = field(default_factory=list)
    omics_terms_explicit: list[str] = field(default_factory=list)
    omics_terms_expanded: list[str] = field(default_factory=list)
    omics_terms: list[str] = field(default_factory=list)
    organism: str = "Homo sapiens"
    sample_context: list[str] = field(default_factory=list)
    sample_terms_explicit: list[str] = field(default_factory=list)
    sample_terms_expanded: list[str] = field(default_factory=list)
    sample_terms: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCES))
    require_baseline: bool = False
    baseline_terms_explicit: list[str] = field(default_factory=list)
    baseline_terms_expanded: list[str] = field(default_factory=list)
    baseline_terms: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    excluded_diseases: list[str] = field(default_factory=list)
    excluded_treatments: list[str] = field(default_factory=list)
    excluded_contexts: list[str] = field(default_factory=list)
    excluded_organisms: list[str] = field(default_factory=list)
    excluded_dataset_types: list[str] = field(default_factory=list)
    human_only: bool = True
    baseline_preferred: bool = False
    return_candidates_only: bool = True
    ruo_only: bool = True
    max_results: int = 10
    metadata_only: bool = True
    allow_download: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PublicDatasetCandidate:
    accession_id: str
    title: str
    source: str
    url: str
    metadata_source: str | None = None
    organism: str | None = None
    disease: str | None = None
    disease_match: str = "unknown"
    treatment_terms_found: list[str] = field(default_factory=list)
    treatment_match: str = "unknown"
    response_terms_found: list[str] = field(default_factory=list)
    omics_type: str | None = None
    sample_context_found: list[str] = field(default_factory=list)
    sample_count: int | None = None
    baseline_or_pretreatment_evidence: bool = False
    treatment_label_likelihood: str = "unknown"
    response_label_likelihood: str = "unknown"
    metadata_sufficiency: str = "unknown"
    source_confidence: str = "unknown"
    suitability_category: str = "unscored"
    suitability_score: int = 0
    limitations: list[str] = field(default_factory=list)
    recommended_next_action: str = "Review source metadata and confirm before any download."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PublicDatasetSearchResult:
    query: dict[str, Any]
    candidates: list[dict[str, Any]]
    warnings: list[str]
    high_suitability_candidates: list[dict[str, Any]] = field(default_factory=list)
    medium_suitability_candidates: list[dict[str, Any]] = field(default_factory=list)
    weak_literature_leads: list[dict[str, Any]] = field(default_factory=list)
    excluded_or_low_relevance: list[dict[str, Any]] = field(default_factory=list)
    search_strategy: dict[str, Any] = field(default_factory=dict)
    ruo_disclaimer: str = RUO_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_public_dataset_request(text: str, *, max_results: int = 10) -> PublicDatasetSearchQuery:
    lowered = text.lower()
    positive_text = _strip_exclusion_clauses(text)
    positive_lowered = positive_text.lower()
    exclusions = _extract_exclusions(text)
    excluded_diseases, excluded_treatments, excluded_contexts, excluded_organisms, excluded_dataset_types = exclusions
    disease = _extract_alias(positive_lowered, DISEASE_ALIASES) or _extract_primary_disease_phrase(positive_text) or _extract_after_in_phrase(positive_text)
    treatment = _extract_alias(positive_lowered, TREATMENT_ALIASES) or _extract_treatment_phrase(positive_text)
    if treatment == "interferon beta" and re.search(r"\binterferon-beta\b", positive_text, flags=re.IGNORECASE):
        treatment = "interferon-beta"
    disease_terms_explicit = _explicit_disease_terms(positive_text, disease)
    disease_terms_expanded = _expanded_disease_terms(disease, disease_terms_explicit)
    treatment_terms_explicit = _explicit_treatment_terms(positive_text, treatment)
    treatment_terms_expanded = _expanded_treatment_terms(disease, treatment, treatment_terms_explicit)
    response_terms_explicit = _explicit_terms_from_list(lowered, RESPONSE_TERMS)
    if not response_terms_explicit and any(term in lowered for term in ["responder", "non-response", "nonresponse"]):
        response_terms_explicit = ["response", "responder", "non-responder"]
    response_terms_expanded = _expanded_response_terms(response_terms_explicit)
    omics_types = _extract_omics_types(positive_lowered)
    omics_terms_explicit = _explicit_omics_terms(positive_lowered)
    omics_terms_expanded = _omics_query_terms(omics_types or ["gene_expression", "rna_seq"])
    require_baseline = any(term in lowered for term in BASELINE_TERMS)
    baseline_terms_explicit = [term for term in BASELINE_TERMS if term in lowered] if require_baseline else []
    baseline_terms_expanded = ["baseline", "pre-treatment", "pretreatment"] if require_baseline else []
    sample_context = _extract_sample_context(positive_lowered)
    sample_terms_explicit = _explicit_sample_terms(positive_lowered)
    sample_terms_expanded = sample_context
    disease_terms = _dedupe(disease_terms_explicit + disease_terms_expanded + _dynamic_disease_terms(positive_text, disease))
    treatment_terms = _dedupe(treatment_terms_explicit + treatment_terms_expanded + _dynamic_treatment_terms(positive_text, treatment))
    response_terms = _dedupe(response_terms_explicit + response_terms_expanded)
    omics_terms = _dedupe(omics_terms_explicit + omics_terms_expanded)
    baseline_terms = _dedupe(baseline_terms_explicit + baseline_terms_expanded)
    return PublicDatasetSearchQuery(
        user_goal=positive_text,
        disease=disease,
        disease_terms_explicit=disease_terms_explicit,
        disease_terms_expanded=disease_terms_expanded,
        disease_terms=disease_terms,
        disease_synonyms=_expand_term(disease, DISEASE_ALIASES),
        treatment=treatment,
        treatment_terms_explicit=treatment_terms_explicit,
        treatment_terms_expanded=treatment_terms_expanded,
        treatment_terms=treatment_terms,
        treatment_synonyms=_expand_term(treatment, TREATMENT_ALIASES),
        response_terms_explicit=response_terms_explicit,
        response_terms_expanded=response_terms_expanded,
        response_terms=response_terms,
        omics_types=omics_types or ["gene_expression", "rna_seq"],
        omics_terms_explicit=omics_terms_explicit,
        omics_terms_expanded=omics_terms_expanded,
        omics_terms=omics_terms,
        organism="Homo sapiens",
        sample_context=sample_context,
        sample_terms_explicit=sample_terms_explicit,
        sample_terms_expanded=sample_terms_expanded,
        sample_terms=_dedupe(sample_terms_explicit + sample_terms_expanded),
        sources=list(DEFAULT_SOURCES),
        require_baseline=require_baseline,
        baseline_terms_explicit=baseline_terms_explicit,
        baseline_terms_expanded=baseline_terms_expanded,
        baseline_terms=baseline_terms,
        constraints=_extract_constraints(lowered),
        excluded_diseases=excluded_diseases,
        excluded_treatments=excluded_treatments,
        excluded_contexts=excluded_contexts,
        excluded_organisms=excluded_organisms,
        excluded_dataset_types=excluded_dataset_types,
        human_only=not any(term in lowered for term in ["animal", "mouse", "murine"]) or any(term in lowered for term in ["human", "patient"]),
        baseline_preferred=require_baseline,
        return_candidates_only=any(term in lowered for term in ["candidate", "candidates", "datasets only", "accessions only"]) or True,
        ruo_only=True,
        max_results=max(1, min(int(max_results), 25)),
        metadata_only=True,
        allow_download=False,
    )


def public_search_needs_clarification(query: PublicDatasetSearchQuery) -> list[str]:
    missing: list[str] = []
    has_discovery_axis = bool(
        query.disease or query.disease_terms or query.treatment or query.treatment_terms or query.response_terms or query.require_baseline
    )
    if not has_discovery_axis:
        missing.append("disease or treatment context")
    if not query.omics_types:
        missing.append("omics data type")
    return missing


def search_public_datasets(query: PublicDatasetSearchQuery) -> PublicDatasetSearchResult:
    warnings: list[str] = []
    candidates: list[PublicDatasetCandidate] = []
    search_strategy = _initial_search_strategy(query)
    if "GEO" in query.sources:
        geo_candidates, geo_warnings = _search_geo(query)
        candidates.extend(geo_candidates)
        warnings.extend(geo_warnings)
        search_strategy["raw_hits_by_source"]["GEO"] = len(geo_candidates)
    if "PubMed" in query.sources:
        pubmed_candidates, pubmed_warnings = _search_pubmed_geo_links(query)
        candidates.extend(pubmed_candidates)
        warnings.extend(pubmed_warnings)
        search_strategy["raw_hits_by_source"]["PubMed"] = len(pubmed_candidates)
    if any(source in query.sources for source in ["ArrayExpress", "BioStudies", "ArrayExpress/BioStudies"]):
        bio_candidates, bio_warnings = _search_biostudies(query)
        candidates.extend(bio_candidates)
        warnings.extend(bio_warnings)
        search_strategy["raw_hits_by_source"]["ArrayExpress/BioStudies"] = len(bio_candidates)
    if "local_case_studies" in query.sources:
        local_candidates = _search_local_case_studies(query)
        candidates.extend(local_candidates)
        search_strategy["raw_hits_by_source"]["local_case_studies"] = len(local_candidates)
    candidates = _dedupe_candidates(candidates)
    scored = [_score_candidate(candidate, query) for candidate in candidates]
    categorized = _categorize_candidates(scored, query)
    if _live_search_had_problem(warnings):
        warnings.append("Live public metadata search was rate-limited or unavailable.")
    search_strategy["live_search_errors"] = [warning for warning in warnings if "unavailable" in warning.lower()]
    search_strategy["rate_limit_warnings"] = [
        warning for warning in warnings if "429" in warning or "too many requests" in warning.lower() or "rate" in warning.lower()
    ]
    if "local_reference_registry" in query.sources and _should_use_reference_fallback(categorized["primary"], warnings):
        from omicstrust.copilot.reference_registry import search_reference_registry

        fallback = search_reference_registry(query)
        if fallback:
            warnings.append("using_local_reference_registry_after_low_recall_or_unavailable_live_search")
            candidates = _dedupe_candidates(candidates + fallback)
            search_strategy["raw_hits_by_source"]["local_reference_registry"] = len(fallback)
            scored = [_score_candidate(candidate, query) for candidate in candidates]
            categorized = _categorize_candidates(scored, query)
    high = categorized["high"][: query.max_results]
    medium = categorized["medium"][: max(0, query.max_results - len(high))]
    primary = high + medium
    weak = categorized["weak"][: query.max_results]
    excluded = categorized["excluded"][: query.max_results]
    search_strategy["candidates_kept"] = len(primary)
    search_strategy["weak_leads_count"] = len(weak)
    search_strategy["excluded_count"] = len(categorized["excluded"])
    search_strategy["why_candidates_were_rejected"] = _rejection_summary(categorized["excluded"], query)
    search_strategy["suggested_refined_queries"] = _suggested_refined_queries(query)
    if categorized["excluded"]:
        warnings.append(f"filtered_low_relevance_candidates:{len(categorized['excluded'])}")
    if not primary and weak:
        warnings.append("no_high_suitability_candidates_found")
        warnings.append(f"suggested_refined_terms:{_query_text(query)}")
    elif not primary:
        warnings.append("no_candidates_found")
        warnings.append(f"suggested_refined_terms:{_query_text(query)}")
    return PublicDatasetSearchResult(
        query=query.to_dict(),
        candidates=[candidate.to_dict() for candidate in primary],
        warnings=_dedupe(warnings),
        high_suitability_candidates=[candidate.to_dict() for candidate in high],
        medium_suitability_candidates=[candidate.to_dict() for candidate in medium],
        weak_literature_leads=[candidate.to_dict() for candidate in weak],
        excluded_or_low_relevance=[candidate.to_dict() for candidate in excluded],
        search_strategy=search_strategy,
    )


def _should_use_reference_fallback(candidates: list[PublicDatasetCandidate], warnings: list[str]) -> bool:
    if not candidates:
        return True
    best_score = max(candidate.suitability_score for candidate in candidates)
    live_low_recall = any(
        "GEO search unavailable" in warning
        or "PubMed-linked GEO search unavailable" in warning
        or "ArrayExpress/BioStudies search unavailable" in warning
        or "GEO returned no IDs" in warning
        or "Live public metadata search was rate-limited or unavailable" in warning
        for warning in warnings
    )
    return live_low_recall or best_score < 50


def _search_geo(query: PublicDatasetSearchQuery) -> tuple[list[PublicDatasetCandidate], list[str]]:
    warnings: list[str] = []
    try:
        ids: list[str] = []
        for term in _expanded_query_texts(query):
            ids_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
                {"db": "gds", "term": term, "retmode": "json", "retmax": str(max(query.max_results * 3, 20))}
            )
            search_payload = _fetch_json(ids_url)
            ids.extend(search_payload.get("esearchresult", {}).get("idlist", []))
            ids = _dedupe(ids)
            if len(ids) >= max(query.max_results * 3, 20):
                break
        if not ids:
            return [], ["GEO returned no IDs for the search terms."]
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode(
            {"db": "gds", "id": ",".join(ids), "retmode": "json"}
        )
        summary_payload = _fetch_json(summary_url)
        result = summary_payload.get("result", {})
        candidates = []
        for uid in result.get("uids", []):
            record = result.get(uid, {})
            candidates.append(_geo_record_to_candidate(record, query))
        return candidates, warnings
    except Exception as exc:
        return [], [f"GEO search unavailable: {exc}"]


def _search_pubmed_geo_links(query: PublicDatasetSearchQuery) -> tuple[list[PublicDatasetCandidate], list[str]]:
    try:
        ids: list[str] = []
        for term in _expanded_query_texts(query):
            ids_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
                {"db": "pubmed", "term": f"{term} GEO GSE", "retmode": "json", "retmax": str(min(query.max_results * 2, 20))}
            )
            search_payload = _fetch_json(ids_url)
            ids.extend(search_payload.get("esearchresult", {}).get("idlist", []))
            ids = _dedupe(ids)
            if len(ids) >= min(query.max_results * 2, 20):
                break
        if not ids:
            return [], []
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        )
        result = _fetch_json(summary_url).get("result", {})
        candidates = []
        for uid in result.get("uids", []):
            record = result.get(uid, {})
            title = str(record.get("title") or "")
            text = json.dumps(record, default=str).lower()
            accessions = _extract_accessions(f"{title} {text}")
            if accessions:
                for accession in accessions:
                    candidates.append(_candidate_from_extracted_accession(accession, title, "PubMed", f"https://pubmed.ncbi.nlm.nih.gov/{uid}/", text, query))
            else:
                candidates.append(
                    PublicDatasetCandidate(
                        accession_id=f"PMID:{uid}",
                        title=title,
                        source="PubMed",
                        metadata_source="literature_search",
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                        organism=query.organism,
                        disease=_infer_disease_from_text(text),
                        treatment_terms_found=_terms_found(text, _query_treatment_terms(query) + _flatten_aliases(TREATMENT_ALIASES)),
                        response_terms_found=_terms_found(text, query.response_terms + RESPONSE_TERMS),
                        omics_type=_omics_type_from_text(text),
                        sample_context_found=_sample_context_from_text(text),
                        baseline_or_pretreatment_evidence=any(term in text for term in BASELINE_TERMS),
                        limitations=["PubMed hit requires manual verification of linked dataset accession and metadata columns."],
                    )
                )
        return candidates, []
    except Exception as exc:
        return [], [f"PubMed-linked GEO search unavailable: {exc}"]


def _search_biostudies(query: PublicDatasetSearchQuery) -> tuple[list[PublicDatasetCandidate], list[str]]:
    try:
        url = "https://www.ebi.ac.uk/biostudies/api/v1/search?" + urllib.parse.urlencode(
            {"query": _query_text(query), "pageSize": str(query.max_results)}
        )
        payload = _fetch_json(url)
        hits = payload.get("hits") or payload.get("entries") or []
        candidates = []
        for hit in hits[: query.max_results]:
            accession = str(hit.get("accession") or hit.get("accno") or hit.get("id") or "unknown")
            title = str(hit.get("title") or hit.get("name") or accession)
            text = json.dumps(hit, default=str).lower()
            candidates.append(
                PublicDatasetCandidate(
                    accession_id=accession,
                    title=title,
                    source="ArrayExpress/BioStudies",
                    metadata_source="biostudies_metadata",
                    url=f"https://www.ebi.ac.uk/biostudies/studies/{urllib.parse.quote(accession)}",
                    organism=query.organism,
                    disease=_infer_disease_from_text(text),
                    treatment_terms_found=_terms_found(text, _query_treatment_terms(query) + _flatten_aliases(TREATMENT_ALIASES)),
                    response_terms_found=_terms_found(text, query.response_terms + RESPONSE_TERMS),
                    omics_type=_omics_type_from_text(text),
                    sample_context_found=_sample_context_from_text(text),
                    sample_count=_sample_count(hit, text),
                    baseline_or_pretreatment_evidence=any(term in text for term in BASELINE_TERMS),
                    limitations=["BioStudies metadata requires manual confirmation before download or analysis."],
                )
            )
            for extracted in _extract_accessions(text):
                if extracted != accession:
                    candidates.append(
                        _candidate_from_extracted_accession(
                            extracted,
                            title,
                            "ArrayExpress/BioStudies",
                            f"https://www.ebi.ac.uk/biostudies/studies/{urllib.parse.quote(accession)}",
                            text,
                            query,
                        )
                    )
        return candidates, []
    except Exception as exc:
        return [], [f"ArrayExpress/BioStudies search unavailable: {exc}"]


def _search_local_case_studies(query: PublicDatasetSearchQuery) -> list[PublicDatasetCandidate]:
    query_terms = _query_text(query).lower().split()
    candidates = []
    for study in list_case_studies():
        text = " ".join(
            [
                str(study.get("title", "")),
                str(study.get("dataset_description", "")),
                str(study.get("scientific_claim", "")),
                " ".join(study.get("required_metadata", [])),
            ]
        )
        lowered = text.lower()
        if query_terms and not any(term in lowered for term in query_terms if len(term) > 3):
            continue
        candidates.append(
            PublicDatasetCandidate(
                accession_id=str(study.get("id")),
                title=str(study.get("title")),
                source="local_case_studies",
                url=str(study.get("output") or "buyer_demo/case_studies.md"),
                organism=query.organism,
                disease=_infer_disease_from_text(lowered),
                treatment_terms_found=_terms_found(lowered, _query_treatment_terms(query) + _flatten_aliases(TREATMENT_ALIASES)),
                response_terms_found=_terms_found(lowered, query.response_terms + RESPONSE_TERMS),
                omics_type=_omics_type_from_text(lowered) or "gene_expression",
                sample_context_found=_sample_context_from_text(lowered),
                sample_count=None,
                baseline_or_pretreatment_evidence=any(term in lowered for term in BASELINE_TERMS),
                limitations=[
                    "Packaged case-study metadata is for demo/pilot orientation and is not a substitute for live source metadata review."
                ],
            )
        )
    return candidates


def _geo_record_to_candidate(record: dict[str, Any], query: PublicDatasetSearchQuery) -> PublicDatasetCandidate:
    accession = str(record.get("accession") or record.get("Accession") or record.get("gse") or record.get("uid") or "unknown")
    title = str(record.get("title") or record.get("Title") or accession)
    summary = str(record.get("summary") or record.get("Summary") or "")
    organism = str(record.get("taxon") or record.get("Taxon") or query.organism or "")
    sample_count = _sample_count(record, f"{title} {summary}")
    text = f"{title} {summary} {organism}".lower()
    return PublicDatasetCandidate(
        accession_id=accession,
        title=title,
        source="GEO",
        url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={urllib.parse.quote(accession)}",
        organism=organism or query.organism,
        disease=_infer_disease_from_text(text),
        treatment_terms_found=_terms_found(text, _query_treatment_terms(query) + _flatten_aliases(TREATMENT_ALIASES)),
        response_terms_found=_terms_found(text, query.response_terms + RESPONSE_TERMS),
        omics_type=_omics_type_from_text(text),
        sample_context_found=_sample_context_from_text(text),
        sample_count=sample_count,
        baseline_or_pretreatment_evidence=any(term in text for term in BASELINE_TERMS),
    )


def _score_candidate(candidate: PublicDatasetCandidate, query: PublicDatasetSearchQuery) -> PublicDatasetCandidate:
    text = _candidate_text(candidate)
    score = 0
    limitations: list[str] = []
    if _query_disease_terms(query) and _matches_query_terms(text, _query_disease_terms(query)):
        score += 35
        candidate.disease_match = "strong"
        if query.disease:
            candidate.disease = query.disease
    elif _query_disease_terms(query):
        score -= 80
        candidate.disease_match = "missing_or_mismatch"
        limitations.append(f"Wrong or missing disease context for query disease: {query.disease}.")
    if _query_treatment_terms(query) and _matches_query_terms(text, _query_treatment_terms(query)):
        score += 30
        candidate.treatment_match = "strong"
    elif _query_treatment_terms(query):
        score -= 70
        candidate.treatment_match = "missing_or_mismatch"
        limitations.append(f"Wrong or missing treatment context for query treatment: {query.treatment}.")
    if candidate.response_terms_found:
        score += 25
    elif query.response_terms:
        score -= 25
        limitations.append("Response/responder/outcome labels are not clearly visible in summary metadata.")
    if candidate.baseline_or_pretreatment_evidence:
        score += 15
    elif query.require_baseline:
        score -= 15
        limitations.append("Baseline or pre-treatment sampling is not explicit in summary metadata.")
    if candidate.omics_type:
        score += 20
    else:
        score -= 30
        limitations.append("Omics assay type is unclear from summary metadata.")
    if candidate.sample_count:
        score += 10
    else:
        score -= 25
        limitations.append("Sample count is not visible in summary metadata.")
    if _has_human_patient_evidence(text):
        score += 10
    elif query.organism.lower() in text or "homo sapiens" in text or "human" in text:
        limitations.append("Human metadata is visible, but patient/sample context is not explicit.")
    else:
        score -= 50
        limitations.append("Human organism evidence is not explicit in the returned metadata.")
    if query.sample_context and _sample_context_matches(candidate, query):
        score += 10
    elif query.sample_context:
        limitations.append("Requested tissue/sample context is not clearly visible in summary metadata.")
    if _is_literature_only(candidate):
        score -= 45
        limitations.append("Literature-only hit; no directly usable dataset accession was visible in metadata.")
    if _is_fallback_reference(candidate):
        score -= 20
        limitations.append("Fallback-only metadata has lower confidence than live source metadata.")
    elif not _is_literature_only(candidate):
        score += 10

    if candidate.omics_type == "ncounter":
        score = max(0, score - 30)
        limitations.append("Panel-only nCounter-style data may be less suitable than genome-wide transcriptomics.")
    if candidate.omics_type in {"miRNA_expression", "expression_profiling"}:
        limitations.append("miRNA/expression dataset; response labels and baseline timing require manual confirmation.")
    if _is_cell_line_only(text):
        score -= 35
        limitations.append("Cell-line-only metadata is not a human patient cohort.")
    if _has_unknown_core_metadata(candidate):
        score = min(score, 40)
        limitations.append("Core metadata are too sparse for high suitability scoring.")

    candidate.treatment_label_likelihood = _likelihood(candidate.treatment_terms_found)
    candidate.response_label_likelihood = _likelihood(candidate.response_terms_found)
    candidate.metadata_sufficiency = _metadata_sufficiency(candidate, query)
    candidate.source_confidence = _source_confidence(candidate)
    candidate.suitability_score = int(max(0, min(100, score)))
    candidate.limitations = _dedupe(candidate.limitations + limitations)
    candidate.recommended_next_action = (
        "Inspect source metadata and sample annotations; ask for confirmation before any download or OmicsTrust audit."
    )
    return candidate


def _categorize_candidates(
    candidates: list[PublicDatasetCandidate], query: PublicDatasetSearchQuery
) -> dict[str, list[PublicDatasetCandidate]]:
    buckets: dict[str, list[PublicDatasetCandidate]] = {"high": [], "medium": [], "weak": [], "excluded": [], "primary": []}
    for candidate in candidates:
        bucket = _bucket_for_candidate(candidate, query)
        if bucket == "excluded":
            failures = _relevance_failures(candidate, query)
            candidate.limitations = _dedupe(candidate.limitations + [f"Excluded from primary candidates: {', '.join(failures)}."])
        buckets[bucket].append(candidate)
        candidate.suitability_category = _category_for_bucket(bucket)
    for key in buckets:
        if key != "primary":
            buckets[key].sort(key=lambda item: item.suitability_score, reverse=True)
    buckets["primary"] = buckets["high"] + buckets["medium"]
    return buckets


def _bucket_for_candidate(candidate: PublicDatasetCandidate, query: PublicDatasetSearchQuery) -> str:
    if _relevance_failures(candidate, query):
        return "excluded"
    if candidate.suitability_score < 30 and not _is_literature_only(candidate):
        return "excluded"
    if _is_literature_only(candidate) or not candidate.omics_type or candidate.suitability_score < 50:
        return "weak"
    if candidate.suitability_score >= 75 and not _must_stay_medium(candidate):
        return "high"
    return "medium"


def _relevance_failures(candidate: PublicDatasetCandidate, query: PublicDatasetSearchQuery) -> list[str]:
    text = _candidate_text(candidate)
    failures = []
    if _matches_excluded_disease(text, query):
        failures.append("excluded_disease")
    if _matches_excluded_treatment(text, query):
        failures.append("excluded_treatment")
    if _matches_excluded_context(text, query):
        failures.append("excluded_context")
    if _query_disease_terms(query) and not _matches_query_terms(text, _query_disease_terms(query)):
        failures.append("disease_mismatch")
    if _query_treatment_terms(query) and not _matches_query_terms(text, _query_treatment_terms(query)):
        failures.append("treatment_mismatch")
    return failures


def _candidate_text(candidate: PublicDatasetCandidate) -> str:
    return " ".join(
        [
            candidate.accession_id,
            candidate.title,
            candidate.source,
            candidate.metadata_source or "",
            candidate.organism or "",
            candidate.disease or "",
            " ".join(candidate.treatment_terms_found),
            " ".join(candidate.response_terms_found),
            " ".join(candidate.sample_context_found),
            candidate.omics_type or "",
        ]
    ).lower()


def _is_literature_only(candidate: PublicDatasetCandidate) -> bool:
    return (candidate.source == "PubMed" and candidate.accession_id.startswith("PMID:")) or (
        candidate.source == "ArrayExpress/BioStudies" and candidate.accession_id.startswith("S-EPMC")
    )


def _is_fallback_reference(candidate: PublicDatasetCandidate) -> bool:
    return candidate.source == "local_reference_registry" or candidate.metadata_source == "fallback_registry"


def _source_confidence(candidate: PublicDatasetCandidate) -> str:
    if _is_fallback_reference(candidate):
        return "fallback_reference"
    if candidate.metadata_source == "accession_extracted_from_literature":
        return "accession_extracted_from_literature"
    if _is_literature_only(candidate):
        return "weak_literature_lead"
    return "live_metadata_verified"


def _live_search_had_problem(warnings: list[str]) -> bool:
    text = " ".join(warnings).lower()
    return any(term in text for term in ["unavailable", "429", "too many requests", "rate limit", "rate-limited"])


def _has_human_patient_evidence(text: str) -> bool:
    return any(term in text for term in ["homo sapiens", "human", "patient", "patients", "cohort", "subject", "subjects"])


def _is_cell_line_only(text: str) -> bool:
    cell_line_terms = ["cell line", "cell-line", "cell lines", "in vitro", "xenograft"]
    patient_terms = ["patient", "patients", "clinical", "cohort", "biopsy", "blood", "tissue"]
    return any(term in text for term in cell_line_terms) and not any(term in text for term in patient_terms)


def _sample_context_matches(candidate: PublicDatasetCandidate, query: PublicDatasetSearchQuery) -> bool:
    if not query.sample_context:
        return True
    found = set(candidate.sample_context_found)
    return any(context in found for context in query.sample_context)


def _has_unknown_core_metadata(candidate: PublicDatasetCandidate) -> bool:
    return not candidate.omics_type and not candidate.treatment_terms_found and not candidate.response_terms_found


def _must_stay_medium(candidate: PublicDatasetCandidate) -> bool:
    text = _candidate_text(candidate)
    if candidate.omics_type in {"ncounter", "miRNA_expression", "expression_profiling"}:
        return True
    if any(term in text for term in ["mixed", "multi-disease", "multiple diseases", "crohn", "rheumatoid arthritis"]) and _is_fallback_reference(candidate):
        return "mixed" in text or "crohn" in text and "rheumatoid arthritis" in text
    return False


def _category_for_candidate(candidate: PublicDatasetCandidate, query: PublicDatasetSearchQuery) -> str:
    return _category_for_bucket(_bucket_for_candidate(candidate, query))


def _category_for_bucket(bucket: str) -> str:
    if bucket == "excluded":
        return "excluded_or_low_relevance"
    if bucket == "weak":
        return "weak_literature_lead"
    if bucket == "high":
        return "high_suitability"
    return "medium_suitability"


def _query_text(query: PublicDatasetSearchQuery) -> str:
    parts = [
        query.disease or (_query_disease_terms(query)[0] if _query_disease_terms(query) else ""),
        query.treatment or (_query_treatment_terms(query)[0] if _query_treatment_terms(query) else ""),
        " ".join(query.response_terms),
        " ".join(query.omics_types),
        " ".join(query.sample_context),
        query.organism,
    ]
    if query.require_baseline:
        parts.append(" ".join(query.baseline_terms or ["baseline", "pre-treatment"]))
    return " ".join(part for part in parts if part).strip()


def _initial_search_strategy(query: PublicDatasetSearchQuery) -> dict[str, Any]:
    levels = _adaptive_query_plan(query)
    target = {
        "disease_terms_explicit": query.disease_terms_explicit,
        "disease_terms_expanded": query.disease_terms_expanded,
        "treatment_terms_explicit": query.treatment_terms_explicit,
        "treatment_terms_expanded": query.treatment_terms_expanded,
        "response_terms_explicit": query.response_terms_explicit,
        "response_terms_expanded": query.response_terms_expanded,
        "omics_terms_explicit": query.omics_terms_explicit,
        "omics_terms_expanded": query.omics_terms_expanded,
        "sample_terms_explicit": query.sample_terms_explicit,
        "sample_terms_expanded": query.sample_terms_expanded,
        "baseline_terms_explicit": query.baseline_terms_explicit,
        "baseline_terms_expanded": query.baseline_terms_expanded,
        "organism": query.organism,
    }
    constraints = {
        "metadata_only": query.metadata_only,
        "allow_download": query.allow_download,
        "human_only": query.human_only,
        "baseline_preferred": query.baseline_preferred,
        "return_candidates_only": query.return_candidates_only,
        "ruo_only": query.ruo_only,
    }
    exclusions = {
        "excluded_diseases": query.excluded_diseases,
        "excluded_treatments": query.excluded_treatments,
        "excluded_contexts": query.excluded_contexts,
        "excluded_organisms": query.excluded_organisms,
        "excluded_dataset_types": query.excluded_dataset_types,
    }
    return {
        "user_goal": query.user_goal,
        "target": target,
        "constraints": constraints,
        "exclusions": exclusions,
        "search_plan": {
            "queries_generated": _dedupe([item["query"] for level in levels for item in level["queries"]]),
            "relaxation_levels": levels,
            "sources": list(query.sources),
        },
        "parsed": {
            "disease": query.disease,
            "disease_terms_explicit": query.disease_terms_explicit,
            "disease_terms_expanded": query.disease_terms_expanded,
            "disease_terms": _query_disease_terms(query),
            "treatment": query.treatment,
            "treatment_terms_explicit": query.treatment_terms_explicit,
            "treatment_terms_expanded": query.treatment_terms_expanded,
            "treatment_terms": _query_treatment_terms(query),
            "response_terms_explicit": query.response_terms_explicit,
            "response_terms_expanded": query.response_terms_expanded,
            "response_terms": query.response_terms,
            "omics_terms_explicit": query.omics_terms_explicit,
            "omics_terms_expanded": query.omics_terms_expanded,
            "omics_terms": query.omics_terms or _omics_query_terms(query.omics_types),
            "sample_terms_explicit": query.sample_terms_explicit,
            "sample_terms_expanded": query.sample_terms_expanded,
            "sample_terms": query.sample_terms or query.sample_context,
            "baseline_terms_explicit": query.baseline_terms_explicit,
            "baseline_terms_expanded": query.baseline_terms_expanded,
            "baseline_terms": query.baseline_terms,
            "constraints": query.constraints,
            "excluded_diseases": query.excluded_diseases,
            "excluded_treatments": query.excluded_treatments,
            "excluded_contexts": query.excluded_contexts,
            "excluded_organisms": query.excluded_organisms,
            "excluded_dataset_types": query.excluded_dataset_types,
            "organism": query.organism,
        },
        "queries_run": _dedupe([item["query"] for level in levels for item in level["queries"]]),
        "relaxation_levels_attempted": levels,
        "sources_searched": list(query.sources),
        "raw_hits_by_source": {},
        "live_search_errors": [],
        "rate_limit_warnings": [],
        "candidates_kept": 0,
        "weak_leads_count": 0,
        "excluded_count": 0,
        "why_candidates_were_rejected": [],
        "suggested_refined_queries": [],
    }


def _expanded_query_texts(query: PublicDatasetSearchQuery) -> list[str]:
    return _dedupe([item["query"] for level in _adaptive_query_plan(query) for item in level["queries"]])


def _adaptive_query_plan(query: PublicDatasetSearchQuery) -> list[dict[str, Any]]:
    disease_terms = _query_disease_terms(query)
    treatment_terms = _query_treatment_terms(query)
    response_terms = query.response_terms or ["response", "responder", "non-responder", "RECIST"]
    omics_terms = query.omics_terms or _omics_query_terms(query.omics_types)
    baseline_terms = query.baseline_terms or (["baseline", "pre-treatment", "pretreatment"] if query.require_baseline else [])
    sample_terms = query.sample_terms or query.sample_context or []
    organism = query.organism or "Homo sapiens"

    primary_disease = disease_terms[0] if disease_terms else query.disease
    primary_treatment = treatment_terms[0] if treatment_terms else query.treatment
    levels: list[dict[str, Any]] = []

    def add_level(name: str, query_texts: list[str]) -> None:
        cleaned = []
        for text in query_texts:
            if not text or not text.strip():
                continue
            q = f"{text} {organism}".strip()
            cleaned.append({"query": q, "source_hint": "public_metadata", "reason": name, "hits": None})
        if cleaned:
            levels.append({"level": len(levels) + 1, "name": name, "queries": _dedupe_query_items(cleaned)})

    strict = []
    if primary_disease and primary_treatment:
        if baseline_terms:
            strict.extend([f"{baseline_terms[0]} {primary_disease} {primary_treatment} {' '.join(response_terms[:2])} {' '.join(omics_terms[:2])}"])
        strict.append(f"{primary_disease} {primary_treatment} {' '.join(response_terms[:2])} {' '.join(omics_terms[:2])}")
    else:
        strict.append(_query_text(query))
    add_level("disease+treatment+response+omics+baseline", strict)

    if primary_disease and primary_treatment:
        add_level(
            "disease+treatment+response+omics",
            [
                f"{primary_disease} {primary_treatment} {' '.join(response_terms[:3])} {' '.join(omics_terms[:2])}",
                f"{primary_treatment} {primary_disease} responder non-responder transcriptomics",
            ],
        )
        add_level(
            "disease+treatment+response",
            [
                f"{primary_disease} {primary_treatment} {' '.join(response_terms[:3])}",
                f"{primary_treatment} {primary_disease} treatment response",
            ],
        )
        add_level(
            "disease+treatment+gene_expression",
            [
                f"{primary_disease} {primary_treatment} gene expression",
                f"{primary_disease} {primary_treatment} microarray",
                f"{primary_disease} {primary_treatment} RNA-seq",
            ],
        )
        add_level(
            "disease+therapy_response+transcriptomics",
            [
                f"{primary_disease} therapy response transcriptomics",
                f"{primary_disease} treatment outcome gene expression",
            ],
        )
        add_level(
            "disease+omics+clinical_outcome",
            [
                f"{primary_disease} {' '.join(omics_terms[:2])} clinical outcome",
                f"{primary_disease} disease activity transcriptome",
            ],
        )
    else:
        add_level("literal_prompt_terms", [_query_text(query)])

    if primary_disease and primary_treatment:
        extra = [
            f"GEO {primary_disease} {primary_treatment} gene expression response",
            f"PubMed GEO {primary_disease} {primary_treatment} gene expression response",
        ]
        for treatment in treatment_terms[1:6]:
            extra.append(f"{primary_disease} {treatment} response transcriptomics")
        for disease in disease_terms[1:5]:
            extra.append(f"{disease} {primary_treatment} response gene expression")
        for sample in sample_terms[:3]:
            extra.append(f"{primary_disease} {primary_treatment} {sample} expression response")
        add_level("synonym_expansion", extra)

    return levels


def _legacy_expanded_query_texts(query: PublicDatasetSearchQuery) -> list[str]:
    disease_terms = _query_disease_terms(query)
    treatment_terms = _query_treatment_terms(query)
    response_terms = query.response_terms or ["response", "responder", "non-responder", "RECIST"]
    omics_terms = query.omics_terms or _omics_query_terms(query.omics_types)
    baseline_terms = query.baseline_terms or (["baseline", "pre-treatment", "pretreatment"] if query.require_baseline else [])
    sample_terms = query.sample_terms or query.sample_context or []
    organism = query.organism or "Homo sapiens"

    queries = [_query_text(query)]
    primary_disease = disease_terms[0] if disease_terms else query.disease
    primary_treatment = treatment_terms[0] if treatment_terms else query.treatment
    if primary_disease and primary_treatment:
        queries.extend(
            [
                f"{primary_treatment} {primary_disease} response",
                f"{primary_treatment} {primary_disease} responder non-responder",
                f"{primary_disease} {primary_treatment} transcriptome response",
            ]
        )
        if _is_checkpoint_context(primary_treatment, treatment_terms):
            queries.append(f"{primary_disease} checkpoint blockade transcriptome response")
        if query.require_baseline:
            queries.extend(
                [
                    f"pre-treatment {primary_disease} {primary_treatment} responder non-responder",
                    f"baseline {primary_disease} {primary_treatment} RNA-seq response",
                ]
            )
            if _is_checkpoint_context(primary_treatment, treatment_terms):
                queries.append(f"pretreatment {primary_disease} immune checkpoint inhibitor transcriptomics response")
    for disease in disease_terms[:4] or [query.disease]:
        for treatment in treatment_terms[:6] or [query.treatment]:
            if disease and treatment:
                queries.append(f"{disease} {treatment} {' '.join(response_terms[:3])}")
                queries.append(f"{disease} {treatment} {' '.join(omics_terms[:2])}")
                queries.append(f"{disease} {treatment} treatment outcome transcriptomics")
                for sample in sample_terms[:2]:
                    queries.append(f"{disease} {treatment} {sample} response gene expression")
    for disease in disease_terms[:3] or [query.disease]:
        if disease:
            queries.append(f"{disease} {' '.join(response_terms[:3])} {' '.join(omics_terms[:2])}")
            for baseline in baseline_terms:
                queries.append(f"{baseline} {disease} {' '.join(omics_terms[:2])} response")
    for treatment in treatment_terms[:5] or [query.treatment]:
        if treatment:
            queries.append(f"{treatment} {' '.join(response_terms[:3])} {' '.join(omics_terms[:2])}")
            for sample in sample_terms[:2]:
                queries.append(f"{treatment} {sample} responder non-responder expression profiling")
    queries = [f"{query} {organism}".strip() for query in queries if query and query.strip()]
    return _dedupe(queries)


def _query_disease_terms(query: PublicDatasetSearchQuery) -> list[str]:
    terms: list[str] = []
    terms.extend(query.disease_terms)
    terms.extend(query.disease_synonyms)
    terms.extend(_expand_term(query.disease, DISEASE_ALIASES))
    if query.disease:
        terms.append(query.disease)
    return _dedupe([term for term in terms if _is_useful_query_term(term)])


def _query_treatment_terms(query: PublicDatasetSearchQuery) -> list[str]:
    terms: list[str] = []
    terms.extend(query.treatment_terms_explicit)
    terms.extend(query.treatment_terms_expanded)
    terms.extend(query.treatment_terms)
    terms.extend(query.treatment_synonyms)
    terms.extend(_expand_term(query.treatment, TREATMENT_ALIASES))
    if query.treatment:
        terms.append(query.treatment)
    return _dedupe([term for term in terms if _is_useful_query_term(term)])


def _extract_primary_disease_phrase(text: str) -> str | None:
    patterns = [
        r"\bfor\s+([A-Za-z][A-Za-z\-\s'’]{2,60})\s+patients?\s+(?:treated|with|receiving)",
        r"\b([A-Za-z][A-Za-z\-\s'’]{2,60})\s+patients?\s+(?:treated|with|receiving)",
        r"\bin\s+([A-Za-z][A-Za-z\-\s'’]{2,60})\s+patients?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            phrase = _strip_entity_noise(match.group(1))
            return phrase or None
    return None


def _explicit_disease_terms(text: str, disease: str | None) -> list[str]:
    normalized = _normalize_search_text(text)
    explicit: list[str] = []
    if disease:
        for term in _expand_term(disease, DISEASE_ALIASES):
            if _term_in_text(normalized, term):
                explicit.append(term)
        explicit.append(disease)
        return _dedupe(explicit)
    phrase = _extract_primary_disease_phrase(text) or _extract_after_in_phrase(text)
    if phrase:
        explicit.append(phrase)
    return _dedupe(explicit)


def _expanded_disease_terms(disease: str | None, explicit_terms: list[str]) -> list[str]:
    if disease:
        return _dedupe([term for term in _expand_term(disease, DISEASE_ALIASES) if term not in explicit_terms])
    return []


def _explicit_treatment_terms(text: str, treatment: str | None) -> list[str]:
    normalized = _normalize_search_text(text)
    explicit: list[str] = []
    for canonical, terms in TREATMENT_ALIASES.items():
        for term in [canonical] + terms:
            if _term_in_text(normalized, term):
                explicit.append(term)
    explicit.extend(_explicit_treatment_list_terms(text))
    if treatment and not _is_generic_treatment_term(treatment):
        explicit.append(treatment)
    return _dedupe([term for term in explicit if _is_useful_query_term(term)])


def _explicit_treatment_list_terms(text: str) -> list[str]:
    spans: list[str] = []
    for pattern in [
        r"\btreated\s+with\s+([^.;\n]+)",
        r"\breceiving\s+([^.;\n]+)",
        r"\btherapy\s+with\s+([^.;\n]+)",
        r";\s*([^.;\n]+)",
    ]:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            spans.append(match.group(1))
    explicit: list[str] = []
    for span in spans:
        cleaned = re.split(
            r"\b(?:with|for|associated|response|responder|non-responder|nonresponse|non-response|transcriptomics|rna-seq|omics|datasets?)\b",
            span,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        for term in _split_term_list(cleaned):
            normalized = _normalize_search_text(term)
            if len(normalized) < 3:
                continue
            if _is_generic_treatment_term(normalized):
                explicit.append(term.strip())
            elif re.search(r"(mab|nib|zumab|lizumab|limab|cept|stat|vir|pril|sartan|platin|taxel|ximab|umab)$", normalized):
                explicit.append(term.strip())
            elif any(_term_in_text(normalized, known) for known in _flatten_aliases(CONTEXTUAL_TREATMENT_EXPANSIONS)):
                explicit.append(term.strip())
            elif any(_term_in_text(normalized, known) for known in _flatten_aliases(TREATMENT_ALIASES)):
                explicit.append(term.strip())
    return explicit


def _expanded_treatment_terms(disease: str | None, treatment: str | None, explicit_terms: list[str]) -> list[str]:
    expanded: list[str] = []
    generic_requested = bool(treatment and _is_generic_treatment_term(treatment)) or any(_is_generic_treatment_term(term) for term in explicit_terms)
    if treatment:
        expanded.extend(term for term in _expand_term(treatment, TREATMENT_ALIASES) if term not in explicit_terms)
    disease_key = _context_disease_key(disease, explicit_terms)
    if disease_key and generic_requested:
        expanded.extend(CONTEXTUAL_TREATMENT_EXPANSIONS.get(disease_key, []))
    if disease_key and disease_key in CONTEXTUAL_TREATMENT_EXPANSIONS:
        for term in CONTEXTUAL_TREATMENT_EXPANSIONS[disease_key]:
            if any(_term_in_text(_normalize_search_text(explicit), term) for explicit in explicit_terms):
                expanded.extend([term])
    for explicit in explicit_terms:
        expanded.extend(EXPLICIT_TREATMENT_CLASS_EXPANSIONS.get(_normalize_search_text(explicit), []))
    explicit_normalized = {_normalize_search_text(term) for term in explicit_terms}
    return _dedupe(
        [
            term
            for term in expanded
            if _is_useful_query_term(term) and _normalize_search_text(term) not in explicit_normalized
        ]
    )


def _context_disease_key(disease: str | None, explicit_terms: list[str]) -> str | None:
    if disease in CONTEXTUAL_TREATMENT_EXPANSIONS:
        return disease
    normalized = _normalize_search_text(" ".join([disease or "", " ".join(explicit_terms)]))
    for key in CONTEXTUAL_TREATMENT_EXPANSIONS:
        if _term_in_text(normalized, key):
            return key
    return None


def _is_generic_treatment_term(term: str | None) -> bool:
    normalized = _normalize_search_text(term or "")
    return normalized in {
        "biologic therapy",
        "biologic",
        "biologics",
        "monoclonal antibody",
        "targeted therapy",
        "immunotherapy",
        "chemotherapy",
        "antiviral therapy",
        "vasopressor therapy",
    }


def _explicit_terms_from_list(text: str, terms: list[str]) -> list[str]:
    return _dedupe([term for term in terms if _term_in_text(text, term)])


def _expanded_response_terms(explicit_terms: list[str]) -> list[str]:
    if not explicit_terms:
        return []
    defaults = ["response", "responder", "non-responder", "clinical response", "treatment outcome"]
    return _dedupe([term for term in defaults if term not in explicit_terms])


def _explicit_omics_terms(text: str) -> list[str]:
    explicit: list[str] = []
    for terms in OMICS_TERMS.values():
        for term in terms:
            if _term_in_text(text, term):
                explicit.append(term)
    return _dedupe(explicit)


def _explicit_sample_terms(text: str) -> list[str]:
    explicit: list[str] = []
    for terms in SAMPLE_CONTEXT_TERMS.values():
        for term in terms:
            if _term_in_text(text, term):
                explicit.append(term)
    return _dedupe(explicit)


def _split_term_list(text: str) -> list[str]:
    return [
        _strip_entity_noise(part)
        for part in re.split(r"\s*(?:,|/|\bor\b|\band\b)\s*", text, flags=re.IGNORECASE)
        if _strip_entity_noise(part)
    ]


def _strip_entity_noise(text: str) -> str:
    cleaned = re.sub(
        r"\b(search|find|public|datasets?|data|for|baseline|pre-treatment|pretreatment|omics|patients?|samples?|human|treated|receiving|with|the|a|an)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return " ".join(cleaned.strip(" .,:;").split())


def _dynamic_disease_terms(text: str, disease: str | None) -> list[str]:
    if disease:
        return _expand_term(disease, DISEASE_ALIASES)
    phrase = _extract_after_in_phrase(text)
    if phrase:
        return _dedupe([phrase])
    before_response = _phrase_before_response(text)
    if before_response:
        tokens = _clean_entity_tokens(before_response)
        if len(tokens) >= 2:
            return _dedupe([" ".join(tokens[:-1]), tokens[0]])
        if tokens:
            return [tokens[0]]
    cleaned = _clean_entity_tokens(text)
    if cleaned:
        return _dedupe([" ".join(cleaned[:3]), cleaned[0]])
    return []


def _dynamic_treatment_terms(text: str, treatment: str | None) -> list[str]:
    if treatment:
        return _expand_term(treatment, TREATMENT_ALIASES)
    before_response = _phrase_before_response(text)
    if before_response:
        tokens = _clean_entity_tokens(before_response)
        if len(tokens) >= 2:
            return _dedupe([tokens[-1], " ".join(tokens[-2:])])
        if tokens:
            return [tokens[-1]]
    treatment_match = re.search(
        r"\b(?:treated\s+with|therapy\s+with|drug|treatment|inhibitor|blockade)\s+([A-Za-z0-9\-/]{3,40})",
        text,
        flags=re.IGNORECASE,
    )
    if treatment_match:
        return [treatment_match.group(1).strip()]
    return []


def _strip_exclusion_clauses(text: str) -> str:
    stripped = re.sub(r"\b(?:exclude|excluding|excluded)\b[^.;\n]*", " ", text, flags=re.IGNORECASE)
    stripped = re.sub(
        r"\b(?:not|without)\s+(?:cancer|melanoma|rheumatoid arthritis|RA|IBD|sepsis|septic shock|animal-only|animal only|mouse|mice|rat|murine)(?:\s+datasets?|\s+data|\s+candidates?)?",
        " ",
        stripped,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(
        r"\bno\s+(?:animal-only|animal only|mouse|mice|rat|murine)(?:\s+datasets?|\s+data|\s+candidates?)?",
        " ",
        stripped,
        flags=re.IGNORECASE,
    )
    return " ".join(stripped.split())


def _extract_exclusions(text: str) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    excluded_diseases: list[str] = []
    excluded_treatments: list[str] = []
    excluded_contexts: list[str] = []
    excluded_organisms: list[str] = []
    excluded_dataset_types: list[str] = []
    for segment in _exclusion_segments(text):
        normalized = _normalize_search_text(segment)
        if _term_in_text(normalized, "cancer"):
            excluded_diseases.append("cancer")
        for canonical, terms in DISEASE_ALIASES.items():
            for term in terms:
                if _term_in_text(normalized, term):
                    excluded_diseases.append(_excluded_disease_display_name(canonical, term))
        for canonical, terms in TREATMENT_ALIASES.items():
            for term in [canonical] + terms:
                if _term_in_text(normalized, term) and not _is_generic_treatment_term(term):
                    excluded_treatments.append(term)
        if any(
            _term_in_text(normalized, term)
            for term in ["animal-only", "animal only", "animal model", "mouse", "mice", "rat", "murine", "non-human", "non human"]
        ):
            excluded_contexts.append("animal-only")
            excluded_organisms.extend(["mouse", "rat", "non-human"])
        if any(_term_in_text(normalized, term) for term in ["cell-line-only", "cell line only", "cell-line", "cell line"]):
            excluded_contexts.append("cell-line-only")
            excluded_dataset_types.append("cell-line-only")
    return (
        _dedupe(excluded_diseases),
        _dedupe(excluded_treatments),
        _dedupe(excluded_contexts),
        _dedupe(excluded_organisms),
        _dedupe(excluded_dataset_types),
    )


def _exclusion_segments(text: str) -> list[str]:
    segments = [match.group(0) for match in re.finditer(r"\b(?:exclude|excluding|excluded)\b[^.;\n]*", text, flags=re.IGNORECASE)]
    for match in re.finditer(
        r"\b(?:not|without)\s+(?:cancer|melanoma|rheumatoid arthritis|RA|IBD|sepsis|septic shock|animal-only|animal only|mouse|mice|rat|murine)(?:\s+datasets?|\s+data|\s+candidates?)?",
        text,
        flags=re.IGNORECASE,
    ):
        segments.append(match.group(0))
    for match in re.finditer(
        r"\bno\s+(?:animal-only|animal only|mouse|mice|rat|murine)(?:\s+datasets?|\s+data|\s+candidates?)?",
        text,
        flags=re.IGNORECASE,
    ):
        segments.append(match.group(0))
    return segments


def _excluded_disease_display_name(canonical: str, matched_term: str) -> str:
    if canonical == "inflammatory bowel disease" and _normalize_search_text(matched_term) == "ibd":
        return "IBD"
    return canonical


def _matches_excluded_disease(text: str, query: PublicDatasetSearchQuery) -> bool:
    if not query.excluded_diseases:
        return False
    terms: list[str] = []
    for disease in query.excluded_diseases:
        if _normalize_search_text(disease) == "cancer":
            terms.extend(["cancer", "carcinoma", "tumor", "tumour", "melanoma", "sarcoma"])
        elif disease == "IBD":
            terms.extend(_expand_term("inflammatory bowel disease", DISEASE_ALIASES))
            terms.append("IBD")
        else:
            terms.extend(_expand_term(disease, DISEASE_ALIASES))
            terms.append(disease)
    return _matches_query_terms(text, _dedupe(terms))


def _matches_excluded_treatment(text: str, query: PublicDatasetSearchQuery) -> bool:
    return bool(query.excluded_treatments and _matches_query_terms(text, query.excluded_treatments))


def _matches_excluded_context(text: str, query: PublicDatasetSearchQuery) -> bool:
    if "animal-only" in query.excluded_contexts and _is_animal_only_context(text):
        return True
    if "cell-line-only" in query.excluded_contexts and _is_cell_line_only(text):
        return True
    return False


def _is_animal_only_context(text: str) -> bool:
    normalized = _normalize_search_text(text)
    animal_terms = ["animal only", "animal model", "mouse", "mice", "murine", "rat", "zebrafish", "drosophila", "mus musculus", "rattus"]
    return any(_term_in_text(normalized, term) for term in animal_terms) and not _has_human_patient_evidence(normalized)


def _extract_constraints(lowered: str) -> list[str]:
    constraints = ["metadata_only", "no_automatic_download", "ruo_only"]
    if any(term in lowered for term in ["candidate datasets only", "candidates only", "accessions only"]):
        constraints.append("candidate_cards_only")
    if any(term in lowered for term in ["do not download", "don't download", "dont download", "no download", "without download"]):
        constraints.append("explicit_no_download")
    if "baseline" in lowered or "pre-treatment" in lowered or "pretreatment" in lowered:
        constraints.append("baseline_or_pretreatment_required")
    return _dedupe(constraints)


def _phrase_before_response(text: str) -> str | None:
    match = re.search(
        r"([A-Za-z0-9][A-Za-z0-9\-/\s'’]{2,90})\s+(?:response|responder|non-responder|nonresponse|non-response|outcome|survival|mortality)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    phrase = match.group(1)
    phrase = re.sub(
        r"\b(search|find|public|datasets?|data|for|baseline|pre-treatment|pretreatment|omics|associated|with|or|and|the|a|an)\b",
        " ",
        phrase,
        flags=re.IGNORECASE,
    )
    return " ".join(phrase.split()).strip(" .,:;") or None


def _clean_entity_tokens(text: str) -> list[str]:
    normalized = _normalize_search_text(text)
    removable_terms = (
        BASELINE_TERMS
        + RESPONSE_TERMS
        + _flatten_aliases(TREATMENT_ALIASES)
        + _flatten_aliases(OMICS_TERMS)
        + ["homo sapiens", "human", "public", "dataset", "datasets", "search", "find", "candidate", "candidates", "download", "files"]
    )
    for term in sorted(removable_terms, key=len, reverse=True):
        normalized = re.sub(rf"\b{re.escape(_normalize_search_text(term))}\b", " ", normalized)
    stop = {
        "for",
        "and",
        "or",
        "with",
        "associated",
        "only",
        "large",
        "ruo",
        "metadata",
        "baseline",
        "pretreatment",
        "pre",
        "post",
        "data",
        "omics",
        "gene",
        "expression",
        "rna",
        "seq",
        "sequencing",
        "transcriptomics",
        "therapy",
        "treatment",
        "useful",
        "cancer",
        "tumor",
        "tumour",
        "disease",
        "study",
        "studies",
    }
    return [token for token in normalized.split() if len(token) > 2 and token not in stop]


def _matches_query_terms(text: str, terms: list[str]) -> bool:
    if not terms:
        return False
    normalized = _normalize_search_text(text)
    for term in terms:
        if not _is_useful_query_term(term):
            continue
        if _term_in_text(normalized, term):
            return True
        pieces = [
            piece
            for piece in _normalize_search_text(term).split()
            if len(piece) > 2 and piece not in {"response", "therapy", "disease", "human", "public", "dataset"}
        ]
        if len(pieces) > 1 and all(re.search(rf"\b{re.escape(piece)}\b", normalized) for piece in pieces):
            return True
    return False


def _is_useful_query_term(term: str | None) -> bool:
    if not term:
        return False
    normalized = _normalize_search_text(term)
    if len(normalized) < 2:
        return False
    return normalized not in {"response", "responder", "non responder", "dataset", "datasets", "public", "omics", "data"}


def _dedupe_query_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for item in items:
        key = _normalize_search_text(str(item.get("query") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _extract_accessions(text: str) -> list[str]:
    matches = re.findall(
        r"\b(?:GSE\d+|GSM\d+|GDS\d+|E-MTAB-\d+|E-GEOD-\d+|SRP\d+|PRJNA\d+)\b",
        text,
        flags=re.IGNORECASE,
    )
    return _dedupe([match.upper() for match in matches])


def _candidate_from_extracted_accession(
    accession: str,
    title: str,
    source: str,
    literature_url: str,
    text: str,
    query: PublicDatasetSearchQuery,
) -> PublicDatasetCandidate:
    accession = accession.upper()
    lowered = _normalize_search_text(f"{title} {text}")
    return PublicDatasetCandidate(
        accession_id=accession,
        title=title or f"Public dataset accession mentioned in {source}: {accession}",
        source=source,
        metadata_source="accession_extracted_from_literature",
        url=_accession_url(accession) or literature_url,
        organism=query.organism if _has_human_patient_evidence(lowered) else query.organism,
        disease=_infer_disease_from_text(lowered) or query.disease,
        treatment_terms_found=_terms_found(lowered, _query_treatment_terms(query) + _flatten_aliases(TREATMENT_ALIASES)),
        response_terms_found=_terms_found(lowered, query.response_terms + RESPONSE_TERMS),
        omics_type=_omics_type_from_text(lowered),
        sample_context_found=_sample_context_from_text(lowered),
        sample_count=_sample_count({}, lowered),
        baseline_or_pretreatment_evidence=any(term in lowered for term in BASELINE_TERMS),
        limitations=[
            "Accession was extracted from public literature metadata; verify source metadata before download or audit.",
            f"Literature source: {literature_url}",
        ],
    )


def _accession_url(accession: str) -> str | None:
    upper = accession.upper()
    if re.match(r"^(GSE|GSM|GDS)\d+$", upper):
        return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={urllib.parse.quote(upper)}"
    if upper.startswith("E-MTAB-") or upper.startswith("E-GEOD-"):
        return f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{urllib.parse.quote(upper)}"
    if upper.startswith("SRP"):
        return f"https://www.ncbi.nlm.nih.gov/sra/?term={urllib.parse.quote(upper)}"
    if upper.startswith("PRJNA"):
        return f"https://www.ncbi.nlm.nih.gov/bioproject/{urllib.parse.quote(upper)}"
    return None


def _rejection_summary(excluded: list[PublicDatasetCandidate], query: PublicDatasetSearchQuery) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}
    for candidate in excluded:
        failures = _relevance_failures(candidate, query)
        if not failures:
            text = " ".join(candidate.limitations).lower()
            failures = []
            if "disease" in text:
                failures.append("disease_mismatch")
            if "treatment" in text:
                failures.append("treatment_mismatch")
            if not failures:
                failures.append("low_metadata_relevance")
        for failure in failures:
            counts[failure] = counts.get(failure, 0) + 1
            examples.setdefault(failure, candidate.accession_id)
    return [{"reason": reason, "count": count, "example_accession": examples.get(reason)} for reason, count in sorted(counts.items())]


def _suggested_refined_queries(query: PublicDatasetSearchQuery) -> list[str]:
    suggestions = []
    disease = (_query_disease_terms(query) or [query.disease or "disease"])[0]
    treatment = (_query_treatment_terms(query) or [query.treatment or "treatment"])[0]
    suggestions.append(f"{disease} {treatment} responder non-responder gene expression")
    suggestions.append(f"{disease} {treatment} baseline transcriptomics response")
    suggestions.append(f"{disease} {treatment} GEO accession clinical response")
    return _dedupe([item for item in suggestions if "None" not in item])


class UnsafeFetchError(ValueError):
    """Raised when public metadata fetch would leave the allowed internet boundary."""


def _fetch_json(url: str, timeout: int = SAFE_FETCH_TIMEOUT_SECONDS) -> dict[str, Any]:
    raw_bytes, _content_type = _safe_fetch_bytes(
        url,
        timeout=timeout,
        max_bytes=SAFE_FETCH_MAX_BYTES,
        accepted_content_types=SAFE_FETCH_ACCEPTED_TYPES,
    )
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _xml_to_dict(raw)


def _safe_fetch_bytes(
    url: str,
    *,
    timeout: int = SAFE_FETCH_TIMEOUT_SECONDS,
    max_bytes: int = SAFE_FETCH_MAX_BYTES,
    accepted_content_types: set[str] | None = None,
) -> tuple[bytes, str | None]:
    parsed = _validate_public_url(url)
    conn, response = _open_safe_http_response(parsed, timeout)
    try:
        status = int(getattr(response, "status", 0) or 0)
        if status and (status < 200 or status >= 300):
            raise UnsafeFetchError(f"HTTP metadata fetch failed with status {status}")
        content_type = _content_type_base(_response_header(response, "Content-Type"))
        if accepted_content_types and content_type and not _content_type_allowed(content_type, accepted_content_types):
            raise UnsafeFetchError(f"Unexpected response content-type: {content_type}")
        content_length = _response_header(response, "Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise UnsafeFetchError(f"Response too large: {content_length} bytes exceeds {max_bytes}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise UnsafeFetchError(f"Response exceeded max size: {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks), content_type
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _validate_public_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeFetchError(f"Blocked URL scheme: {parsed.scheme or 'none'}")
    if not parsed.hostname:
        raise UnsafeFetchError("Blocked URL without hostname")
    if parsed.username or parsed.password:
        raise UnsafeFetchError("Blocked URL with embedded credentials")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise UnsafeFetchError("Blocked URL with invalid port")
    _assert_public_host(parsed.hostname)
    return parsed


def _assert_public_host(hostname: str) -> None:
    host = hostname.strip().lower().rstrip(".")
    if host in BLOCKED_HOSTNAMES or any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        raise UnsafeFetchError(f"Blocked internal hostname: {hostname}")
    try:
        ip = ipaddress.ip_address(host)
        _assert_public_ip(ip, hostname)
        return
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeFetchError(f"Could not resolve public metadata host: {hostname}") from exc
    if not infos:
        raise UnsafeFetchError(f"Could not resolve public metadata host: {hostname}")
    for info in infos:
        ip_text = info[4][0]
        _assert_public_ip(ipaddress.ip_address(ip_text), hostname)


def _assert_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise UnsafeFetchError(f"Blocked non-public metadata host: {hostname}")


def _open_safe_http_response(parsed: urllib.parse.ParseResult, timeout: int) -> tuple[Any, Any]:
    host = parsed.hostname
    if not host:
        raise UnsafeFetchError("Blocked URL without hostname")
    path = urllib.parse.urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = connection_class(host, port=parsed.port, timeout=timeout)
    headers = {"User-Agent": "OmicsTrust-Evidence-Copilot/0.2", "Accept": "application/json, application/xml, text/xml;q=0.8, text/plain;q=0.5"}
    conn.request("GET", path, headers=headers)
    return conn, conn.getresponse()


def _response_header(response: Any, name: str) -> str | None:
    if hasattr(response, "getheader"):
        value = response.getheader(name)
    else:
        headers = getattr(response, "headers", {}) or {}
        value = headers.get(name) or headers.get(name.lower())
    return str(value) if value is not None else None


def _content_type_base(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower()


def _content_type_allowed(content_type: str, accepted: set[str]) -> bool:
    if content_type in accepted:
        return True
    return content_type.endswith("+json") or content_type.endswith("+xml")


def _xml_to_dict(raw: str) -> dict[str, Any]:
    root = DET.fromstring(raw)
    return {"xml_root": root.tag, "text": "".join(root.itertext())}


def _extract_alias(lowered: str, aliases: dict[str, list[str]]) -> str | None:
    normalized = _normalize_search_text(lowered)
    for canonical, terms in aliases.items():
        for term in terms:
            term_lower = _normalize_search_text(term)
            if len(term_lower) <= 3:
                if re.search(rf"\b{re.escape(term_lower)}\b", normalized):
                    return canonical
            elif term_lower in normalized:
                return canonical
    return None


def _extract_omics_types(lowered: str) -> list[str]:
    normalized = _normalize_search_text(lowered)
    found = []
    for canonical, terms in OMICS_TERMS.items():
        if any(_normalize_search_text(term) in normalized for term in terms):
            found.append(canonical)
    return found


def _expand_term(term: str | None, aliases: dict[str, list[str]]) -> list[str]:
    if not term:
        return []
    lowered = term.lower()
    for canonical, terms in aliases.items():
        if canonical.lower() == lowered or any(alias.lower() == lowered for alias in terms):
            return _dedupe([canonical] + terms)
    return [term]


def _omics_query_terms(omics_types: list[str]) -> list[str]:
    terms: list[str] = []
    for omics_type in omics_types:
        if omics_type in OMICS_TERMS:
            terms.append(omics_type)
            terms.extend(OMICS_TERMS[omics_type])
        else:
            terms.append(omics_type)
    return _dedupe(terms or ["gene expression", "rna-seq", "transcriptomics"])


def _extract_after_in_phrase(text: str) -> str | None:
    match = re.search(r"\bin\s+([A-Za-z][A-Za-z\-\s'’]{3,80})(?:\s+response|\s+datasets|\s+transcriptomics|$)", text, flags=re.IGNORECASE)
    if not match:
        return None
    phrase = match.group(1).strip(" .,:;")
    return phrase if phrase else None


def _extract_treatment_phrase(text: str) -> str | None:
    treated = re.search(r"\b(?:treated\s+with|receiving|therapy\s+with)\s+([^.;\n]+)", text, flags=re.IGNORECASE)
    if treated:
        phrase = re.split(
            r"\b(?:with|for|associated|response|responder|non-responder|nonresponse|non-response|transcriptomics|rna-seq|omics|datasets?)\b",
            treated.group(1),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        terms = _split_term_list(phrase)
        if terms:
            return terms[0]
    match = re.search(r"([A-Za-z0-9\-/\s]{3,50})\s+response", text, flags=re.IGNORECASE)
    if not match:
        return None
    phrase = match.group(1).strip(" .,:;")
    for stop in ["dataset", "datasets", "public", "baseline", "gene expression"]:
        phrase = phrase.replace(stop, "")
    phrase = phrase.strip()
    return phrase or None


def _terms_found(text: str, terms: list[str | None]) -> list[str]:
    found = []
    for term in terms:
        if term and _term_in_text(text, term) and term not in found:
            found.append(term)
    return found


def _extract_sample_context(lowered: str) -> list[str]:
    return _sample_context_from_text(lowered)


def _infer_disease_from_text(text: str) -> str | None:
    for canonical, terms in DISEASE_ALIASES.items():
        if _matches_alias_context(text, canonical, {canonical: terms}):
            return canonical
    return None


def _matches_alias_context(text: str, term: str | None, aliases: dict[str, list[str]]) -> bool:
    return any(_term_in_text(text, candidate) for candidate in _expand_term(term, aliases))


def _term_in_text(text: str, term: str | None) -> bool:
    if not term:
        return False
    haystack = _normalize_search_text(text)
    lowered = _normalize_search_text(term)
    if len(lowered) <= 3 or lowered.isupper():
        return re.search(rf"\b{re.escape(lowered)}\b", haystack) is not None
    return lowered in haystack


def _is_checkpoint_context(primary_treatment: str | None, treatment_terms: list[str]) -> bool:
    text = " ".join([primary_treatment or "", " ".join(treatment_terms)]).lower()
    return any(term in text for term in ["pd-1", "pd1", "checkpoint", "immunotherapy", "pembrolizumab", "nivolumab"])


def _omics_type_from_text(text: str) -> str | None:
    normalized = _normalize_search_text(text)
    for canonical, terms in OMICS_TERMS.items():
        if any(_normalize_search_text(term) in normalized for term in terms):
            return canonical
    return None


def _sample_context_from_text(text: str) -> list[str]:
    normalized = _normalize_search_text(text)
    found = []
    for canonical, terms in SAMPLE_CONTEXT_TERMS.items():
        if any(_normalize_search_text(term) in normalized for term in terms):
            found.append(canonical)
    return found


def _normalize_search_text(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").replace("-", " ").replace("_", " ").split())


def _sample_count(record: dict[str, Any], text: str) -> int | None:
    for key in ["n_samples", "samples", "sample_count", "Samples", "n_samples_ch1"]:
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            match = re.search(r"\d+", value)
            if match:
                return int(match.group(0))
    match = re.search(r"(\d{1,5})\s+(?:samples|sample|specimens|patients)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_accession(text: str) -> str | None:
    accessions = _extract_accessions(text)
    return accessions[0] if accessions else None


def _likelihood(terms: list[str]) -> str:
    if len(terms) >= 2:
        return "high"
    if len(terms) == 1:
        return "medium"
    return "unknown"


def _metadata_sufficiency(candidate: PublicDatasetCandidate, query: PublicDatasetSearchQuery) -> str:
    score = 0
    if candidate.sample_count:
        score += 1
    if candidate.treatment_terms_found:
        score += 1
    if candidate.response_terms_found:
        score += 1
    if candidate.baseline_or_pretreatment_evidence or not query.require_baseline:
        score += 1
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    if score == 1:
        return "low"
    return "unknown"


def _dedupe_candidates(candidates: list[PublicDatasetCandidate]) -> list[PublicDatasetCandidate]:
    seen = set()
    output = []
    for candidate in candidates:
        key = (candidate.source, candidate.accession_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    return output


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _flatten_aliases(aliases: dict[str, list[str]]) -> list[str]:
    values: list[str] = []
    for canonical, terms in aliases.items():
        values.append(canonical)
        values.extend(terms)
    return values
