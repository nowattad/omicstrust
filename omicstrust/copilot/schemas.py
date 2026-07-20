from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from omicstrust.copilot.workflow_registry import workflow_ids

SUPPORTED_WORKFLOWS = workflow_ids()

PLAN_STATUSES = {"planned", "needs_clarification", "missing_inputs", "unsupported_workflow", "unsupported_request", "rejected"}


@dataclass
class CopilotRequest:
    user_request: str
    workflow: str | None = None
    data_mode: str = "local_path"
    data_path: str | None = None
    metadata_path: str | None = None
    config_path: str | None = None
    batch_key: str | None = None
    donor_key: str | None = None
    label_key: str | None = None
    locked_axis_path: str | None = None
    public_dataset_search: bool = False
    uploaded_files: list[str] = field(default_factory=list)
    treatment_key: str | None = None
    outcome_key: str | None = None
    patient_id_key: str | None = None
    covariate_keys: list[str] = field(default_factory=list)
    known_endotype_key: str | None = None
    dataset_adapter: str | None = None
    n_top_variable_features: int | None = None
    n_axes: int | None = None
    n_pcs: int | None = None
    model_family: str | None = None
    permutation_n: int | None = None
    bootstrap_n: int | None = None
    use_ai: bool | None = None
    ai_model: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CopilotRequest":
        return cls(
            user_request=str(payload.get("user_request") or payload.get("prompt") or "").strip(),
            workflow=_optional_str(payload.get("workflow")),
            data_mode=str(payload.get("data_mode") or "local_path").strip() or "local_path",
            data_path=_optional_str(payload.get("data_path")),
            metadata_path=_optional_str(payload.get("metadata_path")),
            config_path=_optional_str(payload.get("config_path")),
            batch_key=_optional_str(payload.get("batch_key")),
            donor_key=_optional_str(payload.get("donor_key")),
            label_key=_optional_str(payload.get("label_key")),
            locked_axis_path=_optional_str(payload.get("locked_axis_path")),
            public_dataset_search=bool(payload.get("public_dataset_search", False)),
            uploaded_files=[str(item) for item in payload.get("uploaded_files", []) if item],
            treatment_key=_optional_str(payload.get("treatment_key")),
            outcome_key=_optional_str(payload.get("outcome_key")),
            patient_id_key=_optional_str(payload.get("patient_id_key") or payload.get("patient_key") or payload.get("sample_id_key")),
            covariate_keys=_string_list(payload.get("covariate_keys") or payload.get("covariates")),
            known_endotype_key=_optional_str(payload.get("known_endotype_key")),
            dataset_adapter=_optional_str(payload.get("dataset_adapter") or payload.get("adapter")),
            n_top_variable_features=_optional_int(payload.get("n_top_variable_features")),
            n_axes=_optional_int(payload.get("n_axes")),
            n_pcs=_optional_int(payload.get("n_pcs")),
            model_family=_optional_str(payload.get("model_family")),
            permutation_n=_optional_int(payload.get("permutation_n") or payload.get("n_permutations")),
            bootstrap_n=_optional_int(payload.get("bootstrap_n") or payload.get("n_bootstraps")),
            use_ai=_optional_bool(payload.get("use_ai") if "use_ai" in payload else payload.get("ai_enabled")),
            ai_model=_optional_str(payload.get("ai_model")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CopilotPlan:
    user_goal: str
    analysis_intent: str
    data_mode: str
    omics_type: str
    required_columns: dict[str, str | None]
    workflow: str
    audits: list[str]
    safety: dict[str, bool]
    status: str = "planned"
    missing: list[str] = field(default_factory=list)
    reason: str | None = None
    message: str | None = None
    selected_keys: dict[str, str | None] = field(default_factory=dict)
    public_dataset_search: dict[str, Any] = field(default_factory=dict)
    public_search_query: dict[str, Any] = field(default_factory=dict)
    ai_assistance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowRoute:
    workflow: str
    action: str
    runnable: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return str(Path(path).expanduser())


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    return [str(item).strip() for item in raw if str(item).strip()]


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None
