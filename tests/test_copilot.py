from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from omicstrust.api.server import create_app
from omicstrust.copilot.execution import run_copilot_job
from omicstrust.copilot.planner import build_copilot_plan
from omicstrust.copilot.public_search import (
    PublicDatasetCandidate,
    PublicDatasetSearchQuery,
    _expanded_query_texts,
    parse_public_dataset_request,
    search_public_datasets,
)
from omicstrust.copilot.schemas import CopilotRequest
from omicstrust.copilot.workflow_registry import WORKFLOW_REGISTRY
from omicstrust.copilot.workflow_router import route_workflow
from omicstrust.utils.serialization import read_json
from omicstrust.workflows.de_novo_treatment_response import vanish_default_mapping
from tests.conftest import synthetic_h5ad, write_fast_config


VANISH_DATA = Path("data/real/vanish_steroid_safety_gate.h5ad")


@pytest.fixture(scope="module")
def vanish_copilot_result(tmp_path_factory):
    if not VANISH_DATA.exists():
        pytest.skip("VANISH fixture is not available in this checkout.")
    return run_copilot_job(
        tmp_path_factory.mktemp("vanish_copilot") / "copilot",
        {
            "user_request": "Run VANISH PC11 de novo vasopressin treatment-response discovery.",
            "workflow": "de_novo_treatment_response_discovery",
            "data_mode": "local_path",
            "data_path": str(VANISH_DATA),
            "dataset_adapter": "vanish_default_mapping",
            "n_permutations": 20,
            "n_bootstraps": 20,
        },
    )


def test_copilot_rejects_clinical_treatment_recommendation():
    request = CopilotRequest(user_request="Which treatment should I give for this patient?", data_mode="no_data")
    plan = build_copilot_plan(request)

    assert plan.status == "rejected"
    assert plan.reason == "clinical_decision_request_not_supported"
    assert plan.safety["no_free_code_execution"] is True


def test_copilot_treatment_response_needs_clear_metadata(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Find treatment response signal and mortality association.",
            "data_mode": "local_path",
            "data_path": str(h5ad),
        },
    )
    plan = read_json(tmp_path / "copilot" / "copilot_plan.json")

    assert result["status"] == "needs_clarification"
    assert "treatment label" in result["missing"]
    assert "outcome column" in result["missing"]
    assert plan["safety"]["no_free_code_execution"] is True


def test_copilot_api_runs_optional_layer_without_replacing_audit(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    client = TestClient(create_app(results_root=tmp_path / "platform"))

    response = client.post(
        "/api/copilot/jobs",
        json={
            "user_request": "Audit whether this dataset has batch leakage before interpretation.",
            "data_mode": "local_path",
            "data_path": str(h5ad),
            "config_path": str(cfg),
            "batch_key": "batch",
            "label_key": "signal_label",
            "background": False,
        },
    )

    assert response.status_code == 200, response.text
    job = response.json()
    assert job["status"] == "completed"
    job_id = job["job_id"]

    plan = client.get(f"/api/copilot/jobs/{job_id}/plan").json()
    result = client.get(f"/api/copilot/jobs/{job_id}/result").json()

    assert plan["workflow"] == "batch_risk_audit"
    assert plan["safety"]["no_free_code_execution"] is True
    assert result["status"] == "completed"
    assert result["selected_workflow"] == "batch_risk_audit"
    assert result["report_links"]["report.html"].endswith("report.html")
    assert client.get(f"/api/copilot/jobs/{job_id}/audit/report.html").status_code == 200
    assert client.get(f"/api/copilot/jobs/{job_id}/audit/summary.json").json()["structural_signal"] == "detected"

    direct_audit = client.post(
        "/api/audits",
        json={
            "data_path": str(h5ad),
            "config_path": str(cfg),
            "batch_key": "batch",
            "label_key": "signal_label",
            "background": False,
        },
    )
    assert direct_audit.status_code == 200, direct_audit.text
    assert direct_audit.json()["status"] == "completed"


def test_public_search_routes_to_public_dataset_search():
    request = CopilotRequest(
        user_request="Search public datasets for TNF inhibitor response in rheumatoid arthritis RNA-seq.",
        data_mode="public_search",
        public_dataset_search=True,
    )
    plan = build_copilot_plan(request)
    route = route_workflow(plan)

    assert plan.workflow == "public_dataset_search"
    assert route.action == "public_search"
    assert route.workflow != "batch_risk_audit"
    assert plan.public_search_query["disease"] == "rheumatoid arthritis"


def test_explicit_workflow_not_silently_rerouted():
    plan = build_copilot_plan(
        CopilotRequest(
            user_request="Run VANISH de novo vasopressin discovery, not a demo.",
            workflow="de_novo_treatment_response_discovery",
            data_mode="local_path",
        )
    )
    route = route_workflow(plan)

    assert plan.workflow == "de_novo_treatment_response_discovery"
    assert plan.workflow != "case_study_demo"
    assert plan.status == "missing_inputs"
    assert route.runnable is False
    assert route.reason == "missing_inputs"


def test_explicit_workflow_not_rerouted_to_case_study():
    plan = build_copilot_plan(
        CopilotRequest(
            user_request="VANISH VasoGate PC11 treatment-response discovery.",
            workflow="de_novo_treatment_response_discovery",
            data_mode="local_path",
        )
    )

    assert plan.workflow == "de_novo_treatment_response_discovery"
    assert plan.workflow != "case_study_demo"


def test_unknown_explicit_workflow_returns_unsupported():
    plan = build_copilot_plan(
        CopilotRequest(
            user_request="Run this exact workflow.",
            workflow="imaginary_workflow",
            data_mode="local_path",
        )
    )
    route = route_workflow(plan)

    assert plan.workflow == "imaginary_workflow"
    assert plan.status == "unsupported_workflow"
    assert plan.reason == "unsupported_workflow"
    assert route.runnable is False


def test_missing_required_inputs_returns_missing_inputs(tmp_path):
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Run a de novo treatment response discovery.",
            "workflow": "de_novo_treatment_response_discovery",
            "data_mode": "local_path",
        },
    )

    assert result["selected_workflow"] == "de_novo_treatment_response_discovery"
    assert result["status"] == "missing_inputs"
    assert "local data path" in result["missing"]


def test_planner_cannot_override_explicit_workflow():
    plan = build_copilot_plan(
        CopilotRequest(
            user_request="Search public datasets for anti-PD1 melanoma response RNA-seq.",
            workflow="dataset_inspection",
            data_mode="local_path",
        )
    )

    assert plan.workflow == "dataset_inspection"
    assert plan.workflow != "public_dataset_search"
    assert plan.status == "missing_inputs"


def test_public_search_cannot_run_local_discovery():
    plan = build_copilot_plan(
        CopilotRequest(
            user_request="Search public metadata for treatment response datasets.",
            workflow="de_novo_treatment_response_discovery",
            data_mode="public_search",
            public_dataset_search=True,
        )
    )

    assert plan.workflow == "de_novo_treatment_response_discovery"
    assert plan.status == "unsupported_workflow"
    assert plan.reason == "data_mode_not_allowed"


def test_vanish_adapter_maps_columns():
    mapping = vanish_default_mapping()

    assert mapping["treatment_key"] == "audit_vasopressor"
    assert mapping["outcome_key"] == "audit_death_28"
    assert mapping["steroid_key"] == "audit_steroid"
    assert mapping["srs_key"] == "audit_srs"
    assert mapping["patient_key"] == "individual"


def test_ruo_claim_boundary_present_for_all_workflows():
    assert WORKFLOW_REGISTRY
    for workflow_id, spec in WORKFLOW_REGISTRY.items():
        assert spec.workflow_id == workflow_id
        assert "Research Use Only" in spec.ruo_claim_boundary
        assert spec.allowed_data_modes
        assert spec.route_action


def test_vanish_discovery_direct_script_recovers_pc11(tmp_path):
    if not VANISH_DATA.exists():
        pytest.skip("VANISH fixture is not available in this checkout.")
    from scripts.vanish_denovo_vasopressin_endotype_discovery import run_vanish_denovo_vasopressin_endotype_discovery

    result = run_vanish_denovo_vasopressin_endotype_discovery(
        data_path=VANISH_DATA,
        output_path=tmp_path / "vanish_discovery.json",
        pc_table=tmp_path / "pc_scores.csv",
        group_table=tmp_path / "groups.csv",
        n_permutations=20,
        n_bootstraps=20,
    )

    assert result["top_candidate"]["pc"] == "PC11"
    assert result["top_candidate"]["term"] == "C(vasopressor)[T.Vasopressin]:PC11"
    assert result["top_candidate"]["or_per_1sd"] < 0.25
    assert result["top_candidate"]["lrt_fdr_bh"] < 0.05
    assert result["top_candidate_metadata_r2"]["r2"] < 0.05


def test_copilot_runs_de_novo_treatment_response_discovery(vanish_copilot_result):
    result = vanish_copilot_result
    assert result["status"] == "completed"
    assert result["selected_workflow"] == "de_novo_treatment_response_discovery"
    assert result["top_candidate_axis"] == "PC11"
    assert result["interaction_term"] == "C(vasopressor)[T.Vasopressin]:PC11"


def test_local_path_can_run_discovery(vanish_copilot_result):
    result = vanish_copilot_result
    assert result["status"] == "completed"
    assert result["selected_workflow"] == "de_novo_treatment_response_discovery"


def test_vanish_pc11_recovered_through_copilot(vanish_copilot_result):
    result = vanish_copilot_result
    assert result["top_candidate_axis"] == "PC11"
    assert result["OR"] < 0.25
    assert result["wald_p"] < 0.01
    assert result["lrt_p"] < 0.01
    assert result["fdr"] < 0.05
    assert result["metadata_r2"] < 0.05


def test_generic_discovery_result_schema(vanish_copilot_result):
    result = vanish_copilot_result
    for key in [
        "selected_workflow",
        "status",
        "dataset_summary",
        "result_summary",
        "key_findings",
        "statistics",
        "limitations",
        "what_can_be_claimed",
        "what_cannot_be_claimed",
        "ruo_disclaimer",
        "report_links",
        "execution_artifacts",
    ]:
        assert key in result
    assert result["validation_required"] is True
    assert result["clinical_use_allowed"] is False


def test_vanish_pc11_result_fields_exposed_in_copilot_result(vanish_copilot_result):
    result = vanish_copilot_result
    for key in [
        "top_candidate_axis",
        "interaction_term",
        "beta",
        "OR",
        "wald_p",
        "lrt_p",
        "fdr",
        "permutation_p",
        "bootstrap_direction_stability",
        "metadata_r2",
        "subgroup_mortality",
        "verdict",
    ]:
        assert key in result
    assert result["subgroup_mortality"]


def test_vanish_discovery_has_ruo_claim_boundary(vanish_copilot_result):
    result = vanish_copilot_result
    assert "RUO" in result["ruo_claim_boundary"] or "Research Use Only" in result["ruo_claim_boundary"]
    assert result["validation_required"] is True
    assert result["clinical_use_allowed"] is False


def test_public_search_parses_general_ruo_queries():
    examples = [
        ("anti-PD1 melanoma response RNA-seq", "melanoma", "anti-PD1 immunotherapy", ["rna_seq"]),
        ("TNF inhibitor response in rheumatoid arthritis", "rheumatoid arthritis", "TNF inhibitor", ["gene_expression", "rna_seq"]),
        ("inflammatory bowel disease infliximab response transcriptomics", "inflammatory bowel disease", "TNF inhibitor", ["gene_expression"]),
        ("sepsis vasopressor response transcriptomics", "sepsis", "vasopressor", ["gene_expression"]),
        ("chemotherapy response in breast cancer", "breast cancer", "chemotherapy", ["gene_expression", "rna_seq"]),
        ("single-cell immunotherapy response datasets", None, "immunotherapy", ["single_cell"]),
        ("baseline gene expression with responder/non-responder labels", None, None, ["gene_expression"]),
    ]

    for text, disease, treatment, omics_types in examples:
        plan = build_copilot_plan(CopilotRequest(user_request=text, data_mode="public_search", public_dataset_search=True))
        query = plan.public_search_query
        assert plan.workflow == "public_dataset_search"
        assert plan.status == "planned", text
        assert query["disease"] == disease
        assert query["treatment"] == treatment
        assert query["omics_types"] == omics_types
        assert query["metadata_only"] is True
        assert query["allow_download"] is False


def test_public_search_structured_query_includes_synonyms_and_context():
    query = parse_public_dataset_request(
        "Search public datasets for baseline Crohn's disease infliximab response in mucosal biopsy gene expression."
    ).to_dict()

    assert query["disease"] == "inflammatory bowel disease"
    assert "Crohn's disease" in query["disease_synonyms"]
    assert query["treatment"] == "TNF inhibitor"
    assert "infliximab" in query["treatment_synonyms"]
    assert query["sample_context"] == ["biopsy", "mucosa"]
    assert query["require_baseline"] is True
    assert query["metadata_only"] is True


def test_public_search_too_vague_needs_clarification():
    plan = build_copilot_plan(CopilotRequest(user_request="find data", data_mode="public_search", public_dataset_search=True))

    assert plan.workflow == "public_dataset_search"
    assert plan.status == "needs_clarification"
    assert "disease or treatment context" in plan.missing


def test_vague_public_search_needs_clarification():
    plan = build_copilot_plan(
        CopilotRequest(user_request="Find useful cancer datasets", data_mode="public_search", public_dataset_search=True)
    )

    assert plan.workflow == "public_dataset_search"
    assert plan.status == "needs_clarification"
    assert "disease or treatment context" in plan.missing


def test_public_search_implementation_does_not_hardcode_antipd1_accessions():
    import inspect
    import omicstrust.copilot.public_search as public_search

    source = inspect.getsource(public_search)
    assert "GSE78220" not in source
    assert "GSE145996" not in source
    assert "GSE93157" not in source


def test_public_search_returns_candidate_schema(monkeypatch):
    _mock_public_search(monkeypatch)
    query = PublicDatasetSearchQuery(
        disease="melanoma",
        treatment="anti-PD1 immunotherapy",
        response_terms=["response", "responder", "non-responder"],
        omics_types=["rna_seq"],
        require_baseline=True,
        max_results=3,
    )

    result = search_public_datasets(query)

    assert result.candidates
    candidate = result.candidates[0]
    assert candidate["accession_id"]
    assert candidate["title"]
    assert candidate["source"]
    assert isinstance(candidate["suitability_score"], int)
    assert isinstance(candidate["limitations"], list)
    assert candidate["recommended_next_action"]
    assert candidate["source_confidence"]
    assert "Research Use Only" in result.ruo_disclaimer


def test_public_search_no_large_download(monkeypatch, tmp_path):
    _mock_public_search(monkeypatch)
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for baseline anti-PD1 melanoma response RNA-seq.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    assert result["selected_workflow"] == "public_dataset_search"
    assert result["no_large_download_performed"] is True
    assert not (tmp_path / "copilot" / "audit").exists()
    assert (tmp_path / "copilot" / "input_prompt.txt").exists()
    assert (tmp_path / "copilot" / "copilot_plan.json").exists()
    assert (tmp_path / "copilot" / "public_search_query.json").exists()
    assert (tmp_path / "copilot" / "public_dataset_candidates.json").exists()
    assert (tmp_path / "copilot" / "public_search_report.html").exists()
    assert (tmp_path / "copilot" / "result.json").exists()
    assert (tmp_path / "copilot" / "execution_log.txt").exists()


def test_public_search_metadata_only_does_not_require_download_confirmation(monkeypatch, tmp_path):
    _mock_public_search(monkeypatch)
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for baseline or pre-treatment anti-PD1 melanoma response RNA-seq; do not download large files.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    assert result["selected_workflow"] == "public_dataset_search"
    assert result["status"] != "needs_confirmation_for_download"
    assert result["final_status"] == "completed"
    assert result["no_large_download_performed"] is True
    assert result["candidates"]


def test_public_search_known_antipd1_query(monkeypatch, tmp_path):
    _mock_public_search(monkeypatch)
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for baseline/pre-treatment omics data associated with response or non-response to anti-PD1 immunotherapy in metastatic melanoma.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    accessions = {candidate["accession_id"] for candidate in result["candidates"]}
    assert accessions & {"GSE145996", "GSE78220", "GSE93157"}
    assert result["final_status"] == "completed"


def test_antipd1_melanoma_live_or_mocked_search_returns_candidates(monkeypatch, tmp_path):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], ["GEO unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], ["PubMed unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], ["BioStudies unavailable in test"]))
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for baseline/pre-treatment omics data associated with response or non-response to anti-PD1 immunotherapy in metastatic melanoma.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    accessions = {candidate["accession_id"] for candidate in result["candidates"]}
    assert accessions & {"GSE145996", "GSE78220", "GSE93157"}
    assert any(candidate["source"] == "local_reference_registry" for candidate in result["candidates"])
    assert "using_local_reference_registry_after_low_recall_or_unavailable_live_search" in result["warnings"]
    fallback = [candidate for candidate in result["candidates"] if candidate["source"] == "local_reference_registry"]
    assert all(candidate["metadata_source"] == "fallback_registry" for candidate in fallback)
    assert any("Fallback reference registry candidate" in " ".join(candidate["limitations"]) for candidate in fallback)


def test_fallback_registry_requires_disease_and_treatment_match(monkeypatch, tmp_path):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], ["GEO unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], ["PubMed unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], ["BioStudies unavailable in test"]))
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for TNF inhibitor response in rheumatoid arthritis RNA-seq.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    accessions = {candidate["accession_id"] for candidate in result["candidates"]}
    assert "GSE33377" in accessions
    assert not (accessions & {"GSE145996", "GSE78220", "GSE93157"})
    assert not (accessions & {"GSE16879", "GSE14580", "GSE107865", "GSE23597", "GSE191328", "GSE134809"})
    assert all(candidate["disease"] == "rheumatoid arthritis" for candidate in result["candidates"])


def test_wrong_disease_candidate_excluded(monkeypatch):
    def fake_geo(query):
        return [
            PublicDatasetCandidate(
                accession_id="GSE145996",
                title="Melanoma immune checkpoint blockade response transcriptomics",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE145996",
                organism="Homo sapiens",
                disease="melanoma",
                treatment_terms_found=["checkpoint blockade", "immunotherapy"],
                response_terms_found=["response"],
                omics_type="gene_expression",
                sample_count=100,
                baseline_or_pretreatment_evidence=True,
            ),
            PublicDatasetCandidate(
                accession_id="GSE33377",
                title="Rheumatoid arthritis anti-TNF expression profiling of responders and non-responders",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE33377",
                organism="Homo sapiens",
                disease="rheumatoid arthritis",
                treatment_terms_found=["TNF inhibitor", "anti-TNF"],
                response_terms_found=["response", "responder", "non-responder"],
                omics_type="gene_expression",
                sample_count=50,
                baseline_or_pretreatment_evidence=True,
            ),
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", fake_geo)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    result = search_public_datasets(
        PublicDatasetSearchQuery(
            disease="rheumatoid arthritis",
            treatment="TNF inhibitor",
            response_terms=["response"],
            omics_types=["gene_expression"],
        )
    ).to_dict()

    accessions = {candidate["accession_id"] for candidate in result["candidates"]}
    excluded = {candidate["accession_id"] for candidate in result["excluded_or_low_relevance"]}
    assert "GSE33377" in accessions
    assert "GSE145996" not in accessions
    assert "GSE145996" in excluded


def test_wrong_treatment_candidate_excluded(monkeypatch):
    def fake_geo(query):
        return [
            PublicDatasetCandidate(
                accession_id="GSE33377",
                title="Rheumatoid arthritis anti-TNF expression profiling of responders and non-responders",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE33377",
                organism="Homo sapiens",
                disease="rheumatoid arthritis",
                treatment_terms_found=["TNF inhibitor", "anti-TNF"],
                response_terms_found=["response", "responder", "non-responder"],
                omics_type="gene_expression",
                sample_count=50,
                baseline_or_pretreatment_evidence=True,
            )
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", fake_geo)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    result = search_public_datasets(
        PublicDatasetSearchQuery(
            disease="rheumatoid arthritis",
            treatment="interferon beta",
            response_terms=["response"],
            omics_types=["gene_expression"],
        )
    ).to_dict()

    assert result["candidates"] == []
    assert result["excluded_or_low_relevance"][0]["accession_id"] == "GSE33377"
    assert result["excluded_or_low_relevance"][0]["treatment_match"] == "missing_or_mismatch"


def test_literature_only_records_not_primary_candidates(monkeypatch):
    def fake_pubmed(query):
        return [
            PublicDatasetCandidate(
                accession_id="PMID:123456",
                title="Systemic lupus erythematosus belimumab response gene expression study",
                source="PubMed",
                metadata_source="literature_search",
                url="https://pubmed.ncbi.nlm.nih.gov/123456/",
                organism="Homo sapiens",
                disease="systemic lupus erythematosus",
                treatment_terms_found=["belimumab"],
                response_terms_found=["response"],
                omics_type="gene_expression",
            )
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", fake_pubmed)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    result = search_public_datasets(
        PublicDatasetSearchQuery(
            disease="systemic lupus erythematosus",
            treatment="belimumab",
            response_terms=["response"],
            omics_types=["gene_expression"],
        )
    ).to_dict()

    assert result["candidates"] == []
    assert result["weak_literature_leads"]
    assert result["weak_literature_leads"][0]["accession_id"] == "PMID:123456"


def test_sepsis_vasopressor_no_strong_candidates_behavior(monkeypatch, tmp_path):
    def fake_pubmed(query):
        return [
            PublicDatasetCandidate(
                accession_id="PMID:555",
                title="Septic shock vasopressor mortality transcriptomics review",
                source="PubMed",
                metadata_source="literature_search",
                url="https://pubmed.ncbi.nlm.nih.gov/555/",
                organism="Homo sapiens",
                disease="sepsis",
                treatment_terms_found=["vasopressor", "vasopressin"],
                response_terms_found=["mortality", "outcome"],
                omics_type="gene_expression",
            )
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", fake_pubmed)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for sepsis vasopressor response transcriptomics.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    assert result["candidate_count"] == 0
    assert result["weak_leads_count"] == 1
    assert result["final_status"] == "no_high_suitability_candidates_found"
    assert result["weak_literature_leads"][0]["accession_id"] == "PMID:555"


def test_ibd_antitnf_query_returns_ibd_candidates(monkeypatch, tmp_path):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], ["GEO unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], ["PubMed unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], ["BioStudies unavailable in test"]))
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for baseline or pre-treatment omics data associated with response or non-response to anti-TNF therapy in Crohn's disease or ulcerative colitis. Return candidate datasets only. Do not download files. RUO only.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    accessions = {candidate["accession_id"] for candidate in result["candidates"]}
    assert accessions & {"GSE16879", "GSE14580", "GSE107865", "GSE23597", "GSE42296", "GSE191328", "GSE134809"}
    assert not (accessions & {"GSE145996", "GSE78220", "GSE93157"})
    assert all(candidate["disease"] == "inflammatory bowel disease" for candidate in result["candidates"])


def test_live_search_rate_limit_fallback_warning(monkeypatch, tmp_path):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], ["GEO search unavailable: HTTP Error 429: Too Many Requests"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for anti-PD1 melanoma response RNA-seq. Do not download files.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    assert "Live public metadata search was rate-limited or unavailable." in result["warnings"]
    assert any(candidate["source"] == "local_reference_registry" for candidate in result["candidates"])
    assert all(candidate["source_confidence"] == "fallback_reference" for candidate in result["candidates"])


def test_public_search_result_not_a_clinical_claim(monkeypatch, tmp_path):
    _mock_public_search(monkeypatch)
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Analyze the public dataset and prove anti-PD1 works in melanoma.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    combined = " ".join(result["what_cannot_be_claimed"]) + " " + result["ruo"]
    assert "clinical" in combined.lower()
    assert "No expression matrix was downloaded" in result["what_cannot_be_claimed"][0]


def test_clinical_claim_rejected():
    plan = build_copilot_plan(
        CopilotRequest(
            user_request="Find a dataset and prove which treatment is best for this patient.",
            data_mode="public_search",
            public_dataset_search=True,
        )
    )

    assert plan.status == "rejected"
    assert plan.workflow == "unsupported_request"
    assert plan.reason == "clinical_decision_request_not_supported"


def test_ruo_disclaimer_always_present(monkeypatch, tmp_path):
    _mock_public_search(monkeypatch)
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for anti-PD1 melanoma response RNA-seq.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    assert "Research Use Only" in result["ruo"]
    assert "Research Use Only" in result["ruo_disclaimer"]


def test_public_search_no_candidates_found(monkeypatch, tmp_path):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))
    result = run_copilot_job(
        tmp_path / "copilot",
        {
            "user_request": "Search public datasets for ultra-rare imaginary pathway response RNA-seq.",
            "data_mode": "public_search",
            "public_dataset_search": True,
        },
    )

    assert result["final_status"] == "no_candidates_found"
    assert "no_candidates_found" in result["warnings"]
    assert any(str(warning).startswith("suggested_refined_terms:") for warning in result["warnings"])
    assert result["queries_attempted"]
    assert result["search_strategy"]["relaxation_levels_attempted"]
    assert "raw_hits_by_source" in result["search_strategy"]
    assert "excluded_count" in result["search_strategy"]
    assert result["suggested_refined_queries"]


def test_dynamic_query_generation_ms_interferon_beta():
    query = parse_public_dataset_request("multiple sclerosis interferon-beta response omics")
    expanded = " ".join(_expanded_query_texts(query)).lower()

    assert query.disease == "multiple sclerosis"
    assert query.treatment == "interferon-beta"
    assert "interferon beta" in query.treatment_terms
    assert "multiple sclerosis" in expanded
    assert "interferon beta" in expanded
    assert "ifn beta" in expanded or "ifnb" in expanded
    assert "response" in expanded
    assert "gene expression" in expanded or "transcriptomics" in expanded


def test_explicit_terms_preserved_unknown_context():
    query = parse_public_dataset_request(
        "Search public datasets for psoriasis patients treated with secukinumab or ixekizumab "
        "with responder/non-responder transcriptomics."
    )
    generated = " ".join(_expanded_query_texts(query)).lower()
    forbidden = {"melanoma", "rheumatoid arthritis", "inflammatory bowel disease", "multiple sclerosis", "asthma", "anti-pd1", "anti-tnf", "infliximab", "omalizumab"}

    assert query.disease_terms_explicit == ["psoriasis"]
    assert {"secukinumab", "ixekizumab"}.issubset(set(query.treatment_terms_explicit))
    assert "secukinumab" in generated
    assert "ixekizumab" in generated
    assert "il17 inhibitor" in " ".join(query.treatment_terms_expanded).lower()
    assert not any(term in generated for term in forbidden)


def test_generic_biologic_expansion_is_context_aware():
    query = parse_public_dataset_request(
        "severe asthma biologic response omics; omalizumab, mepolizumab, benralizumab, dupilumab"
    )
    terms = {term.lower() for term in query.treatment_terms_explicit + query.treatment_terms_expanded}
    forbidden = {"belimumab", "vedolizumab", "ustekinumab", "infliximab", "rituximab", "tocilizumab"}

    assert query.disease == "asthma"
    assert {"omalizumab", "mepolizumab", "benralizumab", "dupilumab"}.issubset(terms)
    assert {"anti-ige", "anti-il5", "anti-il5r", "anti-il4r", "anti-tslp"} & terms
    assert not (forbidden & terms)


def test_search_strategy_reports_explicit_expanded_and_exclusions(monkeypatch):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    result = search_public_datasets(
        parse_public_dataset_request(
            "Search public datasets for psoriasis patients treated with secukinumab or ixekizumab "
            "with responder/non-responder transcriptomics. Exclude melanoma and animal-only datasets."
        )
    ).to_dict()
    strategy = result["search_strategy"]

    assert strategy["target"]["disease_terms_explicit"] == ["psoriasis"]
    assert {"secukinumab", "ixekizumab"}.issubset(set(strategy["target"]["treatment_terms_explicit"]))
    assert "IL17 inhibitor" in strategy["target"]["treatment_terms_expanded"]
    assert strategy["exclusions"]["excluded_diseases"] == ["melanoma"]
    assert strategy["exclusions"]["excluded_contexts"] == ["animal-only"]
    assert strategy["search_plan"]["queries_generated"]


def test_excluded_disease_not_used_as_target_disease():
    query = parse_public_dataset_request(
        "Search public datasets for baseline or pre-treatment omics data associated with response or non-response "
        "to interferon-beta therapy in multiple sclerosis. exclude cancer, melanoma, rheumatoid arthritis, IBD, "
        "sepsis, and animal-only datasets from primary candidates"
    )
    disease_terms = {term.lower() for term in query.disease_terms}

    assert query.disease == "multiple sclerosis"
    assert "multiple sclerosis" in disease_terms
    assert "rrms" in disease_terms
    assert "ms" in disease_terms
    assert "melanoma" not in disease_terms
    assert "cancer" in query.excluded_diseases
    assert "melanoma" in query.excluded_diseases
    assert "rheumatoid arthritis" in query.excluded_diseases
    assert "IBD" in query.excluded_diseases
    assert "sepsis" in query.excluded_diseases
    assert "animal-only" in query.excluded_contexts


def test_negation_phrases_do_not_become_search_terms():
    query = parse_public_dataset_request(
        "Search public datasets for multiple sclerosis interferon-beta response RNA-seq. "
        "exclude melanoma. not cancer. no animal-only datasets. exclude rheumatoid arthritis."
    )
    positive_terms = " ".join(query.disease_terms + _expanded_query_texts(query)).lower()

    assert query.disease == "multiple sclerosis"
    assert "multiple sclerosis" in positive_terms
    assert "melanoma" not in positive_terms
    assert "rheumatoid arthritis" not in positive_terms
    assert "cancer" in query.excluded_diseases
    assert "melanoma" in query.excluded_diseases
    assert "rheumatoid arthritis" in query.excluded_diseases
    assert "animal-only" in query.excluded_contexts


def test_ms_interferon_search_queries_use_ms_not_melanoma():
    query = parse_public_dataset_request(
        "Search public datasets for multiple sclerosis interferon-beta response transcriptomics; "
        "exclude cancer, melanoma, rheumatoid arthritis, IBD, sepsis, and animal-only datasets."
    )
    generated = " ".join(_expanded_query_texts(query)).lower()

    assert "multiple sclerosis" in generated or "rrms" in generated or " ms " in f" {generated} "
    assert "interferon beta" in generated
    assert "melanoma" not in generated
    assert "rheumatoid arthritis" not in generated


def test_search_strategy_reports_positive_and_excluded_terms_separately(monkeypatch):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    result = search_public_datasets(
        parse_public_dataset_request(
            "Search public datasets for multiple sclerosis interferon-beta response gene expression. "
            "exclude cancer, melanoma, rheumatoid arthritis, IBD, sepsis, and animal-only datasets."
        )
    ).to_dict()
    parsed = result["search_strategy"]["parsed"]

    assert "multiple sclerosis" in parsed["disease_terms"]
    assert "RRMS" in parsed["disease_terms"]
    assert "melanoma" not in parsed["disease_terms"]
    assert parsed["excluded_diseases"] == ["cancer", "melanoma", "rheumatoid arthritis", "IBD", "sepsis"]
    assert parsed["excluded_contexts"] == ["animal-only"]


def test_excluded_disease_candidate_is_rejected(monkeypatch):
    def fake_geo(query):
        return [
            PublicDatasetCandidate(
                accession_id="GSEMS001",
                title="Multiple sclerosis interferon beta responder transcriptomics",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSEMS001",
                organism="Homo sapiens",
                disease="multiple sclerosis",
                treatment_terms_found=["interferon beta"],
                response_terms_found=["response", "responder"],
                omics_type="gene_expression",
                sample_count=30,
            ),
            PublicDatasetCandidate(
                accession_id="GSEMEL001",
                title="Melanoma interferon beta response transcriptomics",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSEMEL001",
                organism="Homo sapiens",
                disease="melanoma",
                treatment_terms_found=["interferon beta"],
                response_terms_found=["response"],
                omics_type="gene_expression",
                sample_count=30,
            ),
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", fake_geo)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    result = search_public_datasets(
        parse_public_dataset_request("multiple sclerosis interferon-beta response RNA-seq; exclude melanoma")
    ).to_dict()

    assert {candidate["accession_id"] for candidate in result["candidates"]} == {"GSEMS001"}
    assert "GSEMEL001" in {candidate["accession_id"] for candidate in result["excluded_or_low_relevance"]}


def test_medium_candidate_not_rendered_as_weak_lead(monkeypatch):
    def fake_fetch(url, timeout=15):
        return {
            "hits": [
                {
                    "accession": "E-GEOD-46282",
                    "title": "miRNA expression data from baseline multiple sclerosis patients treated with interferon beta",
                    "description": "Homo sapiens patient samples with responder and non-responder response labels.",
                    "samples": "24 samples",
                }
            ]
        }

    monkeypatch.setattr("omicstrust.copilot.public_search._fetch_json", fake_fetch)
    query = PublicDatasetSearchQuery(
        disease="multiple sclerosis",
        disease_terms=["multiple sclerosis", "RRMS", "MS"],
        treatment="interferon-beta",
        treatment_terms=["interferon beta", "interferon-beta", "IFN beta"],
        response_terms=["response", "responder", "non-responder"],
        omics_types=["gene_expression"],
        sources=["ArrayExpress"],
    )

    result = search_public_datasets(query).to_dict()

    assert result["medium_suitability_candidates"]
    candidate = result["medium_suitability_candidates"][0]
    assert candidate["accession_id"] == "E-GEOD-46282"
    assert candidate["omics_type"] == "miRNA_expression"
    assert candidate["source_confidence"] == "live_metadata_verified"
    assert candidate["suitability_category"] == "medium_suitability"
    assert result["candidates"][0]["suitability_category"] == "medium_suitability"
    assert "E-GEOD-46282" not in {item["accession_id"] for item in result["weak_literature_leads"]}


def test_unknown_disease_does_not_require_registry(monkeypatch):
    def fake_geo(query):
        return [
            PublicDatasetCandidate(
                accession_id="GSE999001",
                title="Psoriasis apremilast response RNA-seq patient cohort",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE999001",
                organism="Homo sapiens",
                disease="psoriasis",
                treatment_terms_found=["apremilast"],
                response_terms_found=["response", "responder"],
                omics_type="rna_seq",
                sample_count=42,
                baseline_or_pretreatment_evidence=True,
            )
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", fake_geo)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))

    query = parse_public_dataset_request("psoriasis apremilast response RNA-seq")
    result = search_public_datasets(query).to_dict()

    assert query.disease_terms == ["psoriasis"]
    assert result["candidates"][0]["accession_id"] == "GSE999001"
    assert result["candidates"][0]["source"] == "GEO"
    assert result["candidates"][0]["source_confidence"] == "live_metadata_verified"


def test_search_relaxation_cascade_records_levels(monkeypatch):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))
    result = search_public_datasets(parse_public_dataset_request("multiple sclerosis interferon beta response transcriptomics")).to_dict()
    level_names = [level["name"] for level in result["search_strategy"]["relaxation_levels_attempted"]]

    assert len(level_names) >= 5
    assert "disease+treatment+response+omics" in level_names
    assert "synonym_expansion" in level_names


def test_accession_extraction_from_literature(monkeypatch):
    def fake_fetch(url, timeout=15):
        if "esearch.fcgi" in url and "db=pubmed" in url:
            return {"esearchresult": {"idlist": ["123456"]}}
        if "esummary.fcgi" in url and "db=pubmed" in url:
            return {
                "result": {
                    "uids": ["123456"],
                    "123456": {
                        "title": "Multiple sclerosis IFN beta response gene expression cohort GSE99999",
                        "summary": "Human patient baseline transcriptomics with responder labels.",
                    },
                }
            }
        return {"esearchresult": {"idlist": []}}

    monkeypatch.setattr("omicstrust.copilot.public_search._fetch_json", fake_fetch)
    query = PublicDatasetSearchQuery(
        disease="multiple sclerosis",
        disease_terms=["multiple sclerosis"],
        treatment="interferon beta",
        treatment_terms=["interferon beta", "ifn beta", "IFNB"],
        response_terms=["response"],
        omics_types=["gene_expression"],
        omics_terms=["gene expression", "transcriptomics"],
        sources=["PubMed"],
    )

    result = search_public_datasets(query).to_dict()

    assert result["candidates"][0]["accession_id"] == "GSE99999"
    assert result["candidates"][0]["metadata_source"] == "accession_extracted_from_literature"
    assert result["candidates"][0]["source_confidence"] == "accession_extracted_from_literature"


def test_biostudies_accession_extraction_from_literature(monkeypatch):
    def fake_fetch(url, timeout=15):
        return {
            "hits": [
                {
                    "accession": "S-TEST-1",
                    "title": "Psoriasis secukinumab responder expression dataset references GSE12345 and E-MTAB-1234",
                    "description": "Homo sapiens patient baseline transcriptomics with response labels.",
                    "samples": "32 samples",
                }
            ]
        }

    monkeypatch.setattr("omicstrust.copilot.public_search._fetch_json", fake_fetch)
    query = parse_public_dataset_request(
        "Search public datasets for psoriasis patients treated with secukinumab with responder transcriptomics."
    )
    query.sources = ["ArrayExpress"]
    result = search_public_datasets(query).to_dict()
    accessions = {
        candidate["accession_id"]
        for bucket in ["candidates", "weak_literature_leads", "excluded_or_low_relevance"]
        for candidate in result[bucket]
    }

    assert {"GSE12345", "E-MTAB-1234"}.issubset(accessions)
    extracted = [
        candidate
        for bucket in ["candidates", "weak_literature_leads", "excluded_or_low_relevance"]
        for candidate in result[bucket]
        if candidate["accession_id"] in {"GSE12345", "E-MTAB-1234"}
    ]
    assert all(candidate["metadata_source"] == "accession_extracted_from_literature" for candidate in extracted)


def test_registry_not_used_for_wrong_dynamic_context(monkeypatch):
    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", lambda query: ([], ["GEO unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], ["PubMed unavailable in test"]))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], ["BioStudies unavailable in test"]))

    result = search_public_datasets(parse_public_dataset_request("multiple sclerosis interferon beta response RNA-seq")).to_dict()
    accessions = {candidate["accession_id"] for candidate in result["candidates"]}

    assert not (accessions & {"GSE145996", "GSE78220", "GSE93157", "GSE33377"})
    assert result["search_strategy"]["queries_run"]
    assert result["warnings"]


def _mock_public_search(monkeypatch):
    def fake_geo(query):
        return [
            PublicDatasetCandidate(
                accession_id="GSE78220",
                title="Metastatic melanoma pre-treatment RNA-seq with anti-PD1 responder and non-responder labels",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE78220",
                organism="Homo sapiens",
                disease="melanoma",
                treatment_terms_found=["anti-PD1 immunotherapy", "pd-1"],
                response_terms_found=["response", "responder", "non-responder"],
                omics_type="rna_seq",
                sample_count=28,
                baseline_or_pretreatment_evidence=True,
            ),
            PublicDatasetCandidate(
                accession_id="GSE145996",
                title="Checkpoint immunotherapy response transcriptomics in melanoma baseline samples",
                source="GEO",
                url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE145996",
                organism="Homo sapiens",
                disease="melanoma",
                treatment_terms_found=["checkpoint", "immunotherapy"],
                response_terms_found=["response"],
                omics_type="gene_expression",
                sample_count=100,
                baseline_or_pretreatment_evidence=True,
            ),
        ], []

    monkeypatch.setattr("omicstrust.copilot.public_search._search_geo", fake_geo)
    monkeypatch.setattr("omicstrust.copilot.public_search._search_pubmed_geo_links", lambda query: ([], []))
    monkeypatch.setattr("omicstrust.copilot.public_search._search_biostudies", lambda query: ([], []))
