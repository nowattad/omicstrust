from __future__ import annotations

from omicstrust.copilot.public_search import parse_public_dataset_request, public_search_needs_clarification
from omicstrust.copilot.safety import evaluate_request_safety, safety_contract
from omicstrust.copilot.schemas import CopilotPlan, CopilotRequest
from omicstrust.copilot.workflow_registry import get_workflow_spec, is_registered_workflow


DEFAULT_AUDITS = [
    "data_qc",
    "batch_leakage",
    "metadata_confounding",
    "fdr",
    "bootstrap_stability",
    "null_controls",
    "claim_matrix",
    "evidence_ledger",
]


def build_copilot_plan(request: CopilotRequest) -> CopilotPlan:
    safety = evaluate_request_safety(request.user_request)
    required_columns = {
        "sample_id": None,
        "patient_id": None,
        "treatment": None,
        "outcome": None,
        "batch": request.batch_key,
        "donor": request.donor_key,
        "label": request.label_key,
    }
    if safety["status"] == "rejected":
        return CopilotPlan(
            user_goal=request.user_request,
            analysis_intent="rejected",
            data_mode=request.data_mode,
            omics_type="unknown",
            required_columns=required_columns,
            workflow="unsupported_request",
            audits=[],
            safety=safety_contract(),
            status="rejected",
            reason=str(safety["reason"]),
            message=str(safety["message"]),
        )

    data_mode = _normalize_data_mode(request)
    explicit_workflow = _normalize_workflow(request.workflow)
    workflow = explicit_workflow or ("public_dataset_search" if data_mode == "public_search" else _classify_workflow(request.user_request))
    intent = workflow
    missing = _initial_missing_items(request, workflow, data_mode)
    status = "needs_clarification" if missing else "planned"
    reason = None
    message = None
    public_search_query = parse_public_dataset_request(request.user_request).to_dict() if workflow == "public_dataset_search" else {}
    public_dataset_search = {
        "requested": data_mode == "public_search" or request.public_dataset_search,
        "enabled": True,
        "message": "Public dataset search inspects public metadata only; no large dataset files are downloaded automatically.",
    }

    if explicit_workflow:
        explicit_status, explicit_reason, explicit_message, explicit_missing = _validate_explicit_workflow(request, explicit_workflow, data_mode)
        if explicit_status != "planned":
            status = explicit_status
            reason = explicit_reason
            message = explicit_message
            missing.extend(explicit_missing)
        elif workflow == "public_dataset_search":
            missing.extend(public_search_needs_clarification(parse_public_dataset_request(request.user_request)))
            status = "needs_clarification" if missing else "planned"
    elif workflow == "unsupported_request":
        status = "unsupported_request"
        reason = "no_supported_workflow_matched"
        message = "This request does not map to a supported OmicsTrust Evidence Copilot workflow."
    if not explicit_workflow and workflow == "public_dataset_search":
        missing.extend(public_search_needs_clarification(parse_public_dataset_request(request.user_request)))
        status = "needs_clarification" if missing else "planned"
    elif not explicit_workflow and public_dataset_search["requested"] and workflow != "case_study_demo":
        status = "needs_clarification"
        missing.append("public dataset search request")
        message = public_dataset_search["message"]

    return CopilotPlan(
        user_goal=request.user_request,
        analysis_intent=intent,
        data_mode=data_mode,
        omics_type=_infer_omics_type(request.user_request),
        required_columns=required_columns,
        workflow=workflow,
        audits=list(DEFAULT_AUDITS),
        safety=safety_contract(),
        status=status,
        missing=_dedupe(missing),
        reason=reason,
        message=message,
        selected_keys={"batch_key": request.batch_key, "donor_key": request.donor_key, "label_key": request.label_key},
        public_dataset_search=public_dataset_search,
        public_search_query=public_search_query,
    )


def _classify_workflow(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["search public", "public dataset", "geo", "arrayexpress", "biostudies", "find datasets", "dataset discovery"]):
        return "public_dataset_search"
    if any(term in lowered for term in ["de novo", "denovo", "discover", "discovery"]) and any(
        term in lowered for term in ["treatment", "therapy", "drug", "vasopressor", "mortality", "response", "survival"]
    ):
        return "de_novo_treatment_response_discovery"
    if any(term in lowered for term in ["case study", "demo", "vanish", "vasogate"]):
        return "case_study_demo"
    if any(term in lowered for term in ["locked axis", "validate axis", "external validation", "locked validation"]):
        return "locked_validation"
    if any(term in lowered for term in ["scvi", "benchmark", "scanpy", "comparative"]):
        return "scvi_benchmark_if_available"
    if any(term in lowered for term in ["batch", "confound", "leakage", "technical"]):
        return "batch_risk_audit"
    if any(term in lowered for term in ["metadata", "donor", "sample", "patient metadata"]):
        return "metadata_audit"
    if any(term in lowered for term in ["treatment", "therapy", "drug", "response", "mortality", "survival", "responder", "arm"]):
        return "treatment_response_audit"
    if any(term in lowered for term in ["inspect", "columns", "metadata columns", "qc", "quality"]):
        return "dataset_inspection"
    if text.strip():
        return "metadata_audit"
    return "unsupported_request"


def _normalize_data_mode(request: CopilotRequest) -> str:
    mode = request.data_mode.lower().replace("-", "_").replace(" ", "_")
    if request.uploaded_files:
        return "uploaded"
    if _normalize_workflow(request.workflow) == "public_dataset_search":
        return "public_search"
    if request.public_dataset_search or mode in {"search_public_datasets", "public", "public_search"}:
        return "public_search"
    if mode in {"own_data", "uploaded", "upload"}:
        return "uploaded"
    if mode in {"local", "local_path", "existing_local_path"}:
        return "local_path"
    if mode in {"none", "no_data"}:
        return "no_data"
    return mode or "local_path"


def _initial_missing_items(request: CopilotRequest, workflow: str, data_mode: str) -> list[str]:
    missing: list[str] = []
    data_workflows = {
        "dataset_inspection",
        "treatment_response_audit",
        "batch_risk_audit",
        "metadata_audit",
        "locked_validation",
        "scvi_benchmark_if_available",
        "de_novo_treatment_response_discovery",
        "singlecell_audit",
    }
    if workflow in data_workflows:
        if data_mode == "uploaded" and not request.uploaded_files and not request.data_path:
            missing.append("uploaded omics data file")
        if data_mode == "local_path" and not request.data_path:
            missing.append("local data path")
    if workflow == "locked_validation" and not request.locked_axis_path:
        missing.append("locked axis path")
    return missing


def _normalize_workflow(workflow: str | None) -> str | None:
    if not workflow:
        return None
    return workflow.strip().replace("-", "_").replace(" ", "_") or None


def _validate_explicit_workflow(request: CopilotRequest, workflow: str, data_mode: str) -> tuple[str, str | None, str | None, list[str]]:
    if not is_registered_workflow(workflow):
        return (
            "unsupported_workflow",
            "unsupported_workflow",
            f"Unsupported explicit workflow: {workflow}. Choose one registered OmicsTrust workflow.",
            [],
        )

    spec = get_workflow_spec(workflow)
    if spec is None:
        return ("unsupported_workflow", "unsupported_workflow", f"Unsupported explicit workflow: {workflow}.", [])

    if data_mode not in spec.allowed_data_modes:
        return (
            "unsupported_workflow",
            "data_mode_not_allowed",
            f"Workflow {workflow} does not support data_mode={data_mode}.",
            [f"allowed data mode: {', '.join(spec.allowed_data_modes)}"],
        )

    missing: list[str] = []
    for item in spec.required_inputs:
        if item == "user_request" and not request.user_request:
            missing.append("user request")
        elif item == "data_path":
            if data_mode == "uploaded":
                if not request.uploaded_files and not request.data_path:
                    missing.append("uploaded omics data file")
            elif not request.data_path:
                missing.append("local data path")
        elif item == "locked_axis_path" and not request.locked_axis_path:
            missing.append("locked axis path")
        elif not getattr(request, item, None):
            missing.append(item.replace("_", " "))

    if missing:
        return (
            "missing_inputs",
            "missing_inputs",
            f"Workflow {workflow} was explicitly requested, but required inputs are missing.",
            missing,
        )

    return ("planned", None, None, [])


def _infer_omics_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["single cell", "single-cell", "scrna", "h5ad", "anndata"]):
        return "single_cell"
    if any(term in lowered for term in ["rna-seq", "rnaseq", "transcriptomic", "expression"]):
        return "rna_seq"
    return "rna_seq_or_single_cell_or_unknown"


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
