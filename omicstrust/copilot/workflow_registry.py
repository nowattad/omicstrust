from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


RUO_CLAIM_BOUNDARY = (
    "Research Use Only. This workflow can generate audit or discovery evidence for "
    "scientific follow-up, but it cannot support diagnosis, prognosis, treatment "
    "selection, or regulated clinical decision-making without locked external validation."
)


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    display_name: str
    allowed_data_modes: tuple[str, ...]
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...] = ()
    executor: str = ""
    result_schema: dict[str, Any] = field(default_factory=dict)
    safety_level: str = "ruo_controlled"
    ruo_claim_boundary: str = RUO_CLAIM_BOUNDARY
    route_action: str = "audit"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DISCOVERY_RESULT_SCHEMA = {
    "selected_workflow": "de_novo_treatment_response_discovery",
    "status": "completed|missing_inputs|unsupported_workflow|failed",
    "dataset_summary": "sample and feature counts plus screened axes",
    "result_summary": "top candidate axis and verdict",
    "statistics": [
        "top_candidate_axis",
        "interaction_term",
        "beta",
        "effect_size",
        "p_value",
        "lrt_p",
        "fdr",
        "permutation_p",
        "bootstrap_stability",
        "metadata_r2",
        "subgroup_descriptive_summary",
    ],
    "claim_boundary": ["what_can_be_claimed", "what_cannot_be_claimed", "ruo_disclaimer"],
}


WORKFLOW_REGISTRY: dict[str, WorkflowSpec] = {
    "public_dataset_search": WorkflowSpec(
        workflow_id="public_dataset_search",
        display_name="Public Dataset Search",
        allowed_data_modes=("public_search", "no_data"),
        required_inputs=("user_request",),
        optional_inputs=("sources", "max_results", "metadata_only"),
        executor="omicstrust.copilot.public_search.search_public_datasets",
        result_schema={"candidates": "metadata-only public dataset candidate cards"},
        route_action="public_search",
    ),
    "dataset_inspection": WorkflowSpec(
        workflow_id="dataset_inspection",
        display_name="Dataset Inspection",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=("metadata_path",),
        executor="omicstrust.copilot.data_discovery.inspect_copilot_data",
        result_schema={"data_inspection": "shape, columns, and metadata suggestions"},
        route_action="inspect",
    ),
    "singlecell_audit": WorkflowSpec(
        workflow_id="singlecell_audit",
        display_name="Single-cell Audit",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=("batch_key", "donor_key", "label_key", "config_path"),
        executor="omicstrust.audit.run_audit",
        result_schema={"summary": "OmicsTrust audit summary and claim matrix"},
        route_action="audit",
    ),
    "treatment_response_audit": WorkflowSpec(
        workflow_id="treatment_response_audit",
        display_name="Treatment Response Audit",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=("treatment_key", "outcome_key", "patient_id_key", "config_path"),
        executor="omicstrust.audit.run_audit",
        result_schema={"summary": "OmicsTrust treatment response audit summary"},
        route_action="audit",
    ),
    "batch_risk_audit": WorkflowSpec(
        workflow_id="batch_risk_audit",
        display_name="Batch Risk Audit",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=("batch_key", "donor_key", "label_key", "config_path"),
        executor="omicstrust.audit.run_audit",
        result_schema={"summary": "Batch, metadata, and interpretation risk summary"},
        route_action="audit",
    ),
    "metadata_audit": WorkflowSpec(
        workflow_id="metadata_audit",
        display_name="Metadata Audit",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=("batch_key", "donor_key", "label_key", "metadata_path"),
        executor="omicstrust.audit.run_audit",
        result_schema={"summary": "Metadata-aware trust and failure report"},
        route_action="audit",
    ),
    "locked_validation": WorkflowSpec(
        workflow_id="locked_validation",
        display_name="Locked Axis Validation",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path", "locked_axis_path"),
        optional_inputs=("batch_key", "donor_key", "label_key", "config_path"),
        executor="omicstrust.workflows.locked_validation.validate_locked_axis",
        result_schema={"locked_validation": "locked axis pass/fail evidence"},
        route_action="locked_validation",
    ),
    "de_novo_treatment_response_discovery": WorkflowSpec(
        workflow_id="de_novo_treatment_response_discovery",
        display_name="De Novo Treatment Response Discovery",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=(
            "dataset_adapter",
            "treatment_key",
            "outcome_key",
            "covariate_keys",
            "patient_id_key",
            "batch_key",
            "known_endotype_key",
            "n_top_variable_features",
            "n_axes",
            "n_pcs",
            "model_family",
            "permutation_n",
            "bootstrap_n",
        ),
        executor="omicstrust.workflows.de_novo_treatment_response.run_de_novo_treatment_response_discovery",
        result_schema=DISCOVERY_RESULT_SCHEMA,
        safety_level="ruo_discovery_requires_external_validation",
        route_action="de_novo_discovery",
    ),
    "scvi_benchmark_if_available": WorkflowSpec(
        workflow_id="scvi_benchmark_if_available",
        display_name="Comparative scVI/Scanpy Benchmark",
        allowed_data_modes=("local_path", "uploaded"),
        required_inputs=("data_path",),
        optional_inputs=("batch_key", "label_key", "config_path"),
        executor="omicstrust.benchmarks.comparative.run_real_dataset_benchmark",
        result_schema={"benchmark": "comparative benchmark report"},
        route_action="benchmark",
    ),
    "case_study_demo": WorkflowSpec(
        workflow_id="case_study_demo",
        display_name="RUO Case Study Demo",
        allowed_data_modes=("no_data", "local_path", "uploaded"),
        required_inputs=(),
        optional_inputs=("case_study_id",),
        executor="omicstrust.case_studies.registry.list_case_studies",
        result_schema={"case_studies": "packaged RUO demo case studies"},
        route_action="case_study",
    ),
}


def workflow_ids() -> set[str]:
    return set(WORKFLOW_REGISTRY)


def get_workflow_spec(workflow_id: str | None) -> WorkflowSpec | None:
    if not workflow_id:
        return None
    return WORKFLOW_REGISTRY.get(workflow_id)


def is_registered_workflow(workflow_id: str | None) -> bool:
    return bool(workflow_id and workflow_id in WORKFLOW_REGISTRY)


def route_action_for_workflow(workflow_id: str) -> str | None:
    spec = get_workflow_spec(workflow_id)
    return spec.route_action if spec else None


def registry_as_dict() -> dict[str, dict[str, Any]]:
    return {workflow_id: spec.to_dict() for workflow_id, spec in WORKFLOW_REGISTRY.items()}

