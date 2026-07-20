# OmicsTrust Evidence Copilot

Evidence Copilot is an optional natural-language layer on top of the existing
OmicsTrust CLI, Web UI, REST API, upload, and local-path workflows. It does not
replace the core audit engine.

## GPT-5.6 Evidence Layer

When `OPENAI_API_KEY` is configured, Evidence Copilot uses `gpt-5.6` through the
Responses API for two constrained tasks:

1. Interpret a natural-language RUO request and suggest a registered workflow
   only when the user did not explicitly select one.
2. Explain a completed deterministic OmicsTrust result under its existing claim
   boundary.

The model does not compute, recalculate, or change audit statistics. Explicit
workflow selection has precedence over model suggestions. Clinical or treatment
recommendation requests are rejected by deterministic safety logic.

Privacy controls:

- Responses are requested with `store=false`.
- Raw expression matrices, patient rows, uploaded file contents, sample IDs, and
  local paths are excluded or redacted.
- Only the user prompt, selected metadata field names, aggregate summaries,
  deterministic findings, and claim boundaries may be sent.
- A hashed deployment safety identifier is used.

Install and enable the optional layer:

```bash
.venv/bin/pip install -e '.[ai]'
export OPENAI_API_KEY="your-key"
```

The deterministic CLI, Web, API, and upload workflows continue to work without
an OpenAI key or when the Web checkbox is disabled.

## Phase 2 Public Dataset Search

Public Dataset Search lets a user write an RUO biomedical dataset-discovery
request, such as:

- anti-PD1 melanoma response RNA-seq
- TNF inhibitor response in rheumatoid arthritis
- sepsis vasopressor response transcriptomics
- chemotherapy response in breast cancer
- single-cell immunotherapy response datasets

The Copilot converts the request into a structured metadata-search query:

```json
{
  "user_goal": "...",
  "target": {
    "disease_terms_explicit": ["psoriasis"],
    "disease_terms_expanded": [],
    "treatment_terms_explicit": ["secukinumab", "ixekizumab"],
    "treatment_terms_expanded": ["IL17 inhibitor"],
    "response_terms_explicit": ["responder", "non-responder"],
    "response_terms_expanded": ["response", "treatment outcome"],
    "omics_terms_explicit": ["transcriptomics"],
    "omics_terms_expanded": ["gene expression", "rna-seq"],
    "sample_terms_explicit": [],
    "sample_terms_expanded": [],
    "baseline_terms_explicit": ["baseline"],
    "baseline_terms_expanded": ["pre-treatment", "pretreatment"],
    "organism": "Homo sapiens"
  },
  "constraints": {
    "metadata_only": true,
    "allow_download": false,
    "human_only": true,
    "baseline_preferred": true,
    "return_candidates_only": true,
    "ruo_only": true
  },
  "exclusions": {
    "excluded_diseases": ["cancer", "melanoma", "rheumatoid arthritis", "IBD", "sepsis"],
    "excluded_treatments": [],
    "excluded_contexts": ["animal-only"],
    "excluded_organisms": ["mouse", "rat", "non-human"],
    "excluded_dataset_types": ["cell-line-only"]
  },
  "search_plan": {
    "queries_generated": ["psoriasis secukinumab response transcriptomics"],
    "relaxation_levels": [],
    "sources": ["GEO", "PubMed", "ArrayExpress", "BioStudies", "local_reference_registry"]
  }
}
```

It then searches public scientific metadata sources and returns candidate cards
only when disease/treatment relevance is visible in metadata.

## What It Searches

Phase 2 supports metadata search over:

- NCBI GEO via E-utilities
- PubMed records likely linked to GEO accessions
- ArrayExpress / BioStudies metadata when available
- context-matched local reference registry fallback

It does not scrape arbitrary websites.

The search is adaptive and disease-agnostic. Copilot first extracts literal and
canonical disease/treatment/omics terms, then builds a relaxation cascade from
strict queries to broader synonym-expanded queries. Unknown diseases are still
searched through public metadata; the local reference registry is only a
fallback/reference source and is never allowed to satisfy a wrong-disease query.
User-explicit disease, treatment, response, omics, sample, and baseline terms
remain primary. Expanded terms are secondary and context-aware; generic therapy
classes such as `biologic therapy` expand differently for asthma, lupus, IBD,
or psoriasis and do not inject unrelated disease-specific drugs.
Negative phrases such as `exclude melanoma`, `not cancer`, or `no animal-only
datasets` are parsed as exclusions and are never allowed to become target
disease terms or search-query terms.

Each result includes `search_strategy`, containing:

- parsed disease, treatment, response, omics, sample, baseline, and constraint terms
- excluded diseases and excluded contexts, separated from target terms
- query strings attempted across relaxation levels
- sources searched and raw hit counts
- live search errors or rate-limit warnings
- rejected-candidate reason counts
- suggested refined search strings

## What It Returns

Results are separated into:

- `high_suitability_candidates`
- `medium_suitability_candidates`
- `weak_literature_leads`
- `excluded_or_low_relevance`

Only high and medium suitability records are shown as primary candidates in the
Web UI. Literature-only hits and low-relevance records are kept separate so they
do not look like audit-ready datasets.

Each candidate card includes:

- accession ID
- title
- source and source URL
- organism
- omics type
- sample count when visible
- treatment term evidence
- response/outcome term evidence
- baseline or pre-treatment evidence
- metadata sufficiency estimate
- suitability score
- limitations
- recommended next action
- source confidence: `live_metadata_verified`, `accession_extracted_from_literature`, `fallback_reference`, or `weak_literature_lead`

The score is metadata triage only. It is not an analysis result.
Expression metadata is normalized when visible in titles or summaries, including
`miRNA_expression`, `gene_expression`, and `expression_profiling`, so usable
accession records are not downgraded solely because the source uses broad
"expression data" wording.

PubMed and BioStudies records can create candidate cards when public accessions
such as `GSE`, `GDS`, `E-MTAB`, `SRP`, or `PRJNA` identifiers are visible in
the literature metadata. Literature-only hits without an accession stay weak
and separate from primary candidate datasets.

Fallback registry candidates are injected only when the parsed disease/context
and treatment/context match the request. For example, melanoma anti-PD1 fallback
records must not appear for a rheumatoid arthritis anti-TNF query.

The search result JSON separates records into:

- `high_suitability_candidates`
- `medium_suitability_candidates`
- `weak_literature_leads`
- `excluded_or_low_relevance`

Wrong-disease and wrong-treatment records are never primary high/medium
candidates. Literature-only PubMed leads are never primary candidates.

## What It Does Not Do

Public Dataset Search does not:

- download large expression matrices automatically
- run OmicsTrust audits before a dataset is selected and confirmed
- execute arbitrary code
- make clinical, diagnostic, prognostic, or treatment-selection claims
- prove treatment efficacy from search results

If a request asks for large automatic download, Copilot returns
`needs_confirmation_for_download`.

If the prompt says not to download large files, Copilot treats that as an
explicit metadata-only constraint and still runs public metadata search.

## RUO Boundary

All Evidence Copilot outputs are Research Use Only.

Candidate search is a discovery aid. A dataset must still be downloaded or
provided by the user, inspected, audited, and externally validated before any
scientific or commercial claim is strengthened.
