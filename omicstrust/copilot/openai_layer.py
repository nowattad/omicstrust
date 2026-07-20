from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from omicstrust.copilot.schemas import CopilotPlan, CopilotRequest
from omicstrust.copilot.workflow_registry import get_workflow_spec, workflow_ids


DEFAULT_OPENAI_MODEL = "gpt-5.6"

AI_BOUNDARY = {
    "role": "intent_and_evidence_interpreter",
    "authoritative_statistics": False,
    "may_change_explicit_workflow": False,
    "raw_expression_data_sent": False,
    "clinical_decision_making": False,
    "ruo_only": True,
}


@dataclass(frozen=True)
class OpenAICopilotConfig:
    enabled: bool
    model: str = DEFAULT_OPENAI_MODEL
    reasoning_effort: str = "low"

    @classmethod
    def from_request(cls, request: CopilotRequest) -> "OpenAICopilotConfig":
        requested = request.use_ai
        has_key = bool(os.environ.get("OPENAI_API_KEY"))
        enabled = has_key if requested is None else bool(requested)
        return cls(
            enabled=enabled,
            model=request.ai_model or os.environ.get("OMICSTRUST_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
            reasoning_effort=os.environ.get("OMICSTRUST_OPENAI_REASONING", "low"),
        )


def interpret_request_with_gpt(
    request: CopilotRequest,
    deterministic_plan: CopilotPlan,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    config = OpenAICopilotConfig.from_request(request)
    if not config.enabled:
        return _inactive("disabled_or_api_key_missing", config)

    prompt_payload = {
        "user_request": request.user_request,
        "explicit_workflow": request.workflow,
        "data_mode": request.data_mode,
        "provided_metadata_keys": {
            "batch_key": request.batch_key,
            "donor_key": request.donor_key,
            "label_key": request.label_key,
            "treatment_key": request.treatment_key,
            "outcome_key": request.outcome_key,
            "patient_id_key": request.patient_id_key,
        },
        "deterministic_plan": {
            "workflow": deterministic_plan.workflow,
            "status": deterministic_plan.status,
            "missing": deterministic_plan.missing,
        },
        "registered_workflows": sorted(workflow_ids()),
    }
    system = (
        "You are the RUO intent interpreter for OmicsTrust, an omics evidence-audit platform. "
        "Map the research request to one registered workflow and identify missing metadata. "
        "Never provide diagnosis, treatment selection, dosing, or clinical advice. "
        "An explicit workflow is immutable: repeat it exactly or flag that inputs are missing. "
        "Do not invent dataset columns. Return only the requested structured object."
    )
    try:
        parsed, response_id = _structured_response(
            client=client,
            config=config,
            system=system,
            payload=prompt_payload,
            schema=_intent_schema(),
            schema_name="omicstrust_intent",
        )
        suggestion = str(parsed.get("suggested_workflow") or "")
        if suggestion not in workflow_ids():
            raise ValueError(f"Model returned an unregistered workflow: {suggestion}")
        if request.workflow and suggestion != request.workflow:
            suggestion = request.workflow
            parsed["reasoning_summary"] = "Explicit workflow preserved by the OmicsTrust registry contract."
        parsed["suggested_workflow"] = suggestion
        parsed.update(
            {
                "status": "completed",
                "model": config.model,
                "response_id": response_id,
                "boundary": dict(AI_BOUNDARY),
                "input_scope": "prompt_and_user_provided_field_names_only",
            }
        )
        return parsed
    except Exception as exc:
        return _failure(exc, config)


def apply_gpt_workflow_suggestion(
    request: CopilotRequest,
    plan: CopilotPlan,
    ai_plan: dict[str, Any],
) -> CopilotPlan:
    """Apply a validated suggestion only when deterministic routing was generic.

    Explicit workflow selection always wins. The deterministic registry remains
    the authority for allowed data modes and required inputs.
    """

    plan.ai_assistance = _public_ai_record(ai_plan)
    if request.workflow or ai_plan.get("status") != "completed":
        return plan
    suggested = str(ai_plan.get("suggested_workflow") or "")
    spec = get_workflow_spec(suggested)
    if spec is None or plan.workflow not in {"metadata_audit", "unsupported_request"}:
        return plan
    if plan.data_mode not in spec.allowed_data_modes:
        return plan
    plan.workflow = suggested
    plan.analysis_intent = str(ai_plan.get("analysis_intent") or suggested)
    plan.ai_assistance["suggestion_applied"] = True
    return plan


def explain_result_with_gpt(
    request: CopilotRequest,
    result: dict[str, Any],
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    config = OpenAICopilotConfig.from_request(request)
    if not config.enabled:
        return _inactive("disabled_or_api_key_missing", config)

    system = (
        "You explain completed OmicsTrust Research Use Only evidence audits. "
        "Use only the supplied deterministic result. Do not recalculate, alter, or add statistics. "
        "Do not turn an internal discovery into external validation. Do not provide diagnosis, "
        "treatment advice, dosing, efficacy, or safety claims. State the strongest defensible claim, "
        "the decisive limitation, and one concrete validation step. Return only the structured object."
    )
    try:
        parsed, response_id = _structured_response(
            client=client,
            config=config,
            system=system,
            payload=_compact_result_context(request, result),
            schema=_explanation_schema(),
            schema_name="omicstrust_evidence_explanation",
        )
        parsed.update(
            {
                "status": "completed",
                "model": config.model,
                "response_id": response_id,
                "boundary": dict(AI_BOUNDARY),
                "authoritative_source": "deterministic_omicstrust_result",
            }
        )
        return parsed
    except Exception as exc:
        return _failure(exc, config)


def _structured_response(
    *,
    client: Any | None,
    config: OpenAICopilotConfig,
    system: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
    schema_name: str,
) -> tuple[dict[str, Any], str | None]:
    if client is None:
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError("Install OmicsTrust with the ai extra to enable GPT-5.6.") from exc
        client = OpenAI()

    response = client.responses.create(
        model=config.model,
        instructions=system,
        input=json.dumps(payload, ensure_ascii=False),
        reasoning={"effort": config.reasoning_effort},
        text={
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
        store=False,
        safety_identifier=_safety_identifier(),
    )
    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise RuntimeError("GPT-5.6 returned no structured output.")
    parsed = json.loads(output_text)
    if not isinstance(parsed, dict):
        raise ValueError("GPT-5.6 structured output must be an object.")
    return parsed, getattr(response, "id", None)


def _compact_result_context(request: CopilotRequest, result: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "status",
        "selected_workflow",
        "short_answer",
        "data_qc",
        "signal_summary",
        "batch_risk",
        "metadata_risk",
        "stability",
        "trust_verdict",
        "safe_to_interpret",
        "dataset_summary",
        "result_summary",
        "key_findings",
        "statistics",
        "limitations",
        "what_can_be_claimed",
        "what_cannot_be_claimed",
        "validation_required",
        "clinical_use_allowed",
        "ruo_disclaimer",
    }
    summary = _privacy_safe_value({key: result[key] for key in allowed if key in result})
    return {
        "user_goal": request.user_request,
        "deterministic_result": summary,
        "privacy_note": "No expression matrix, patient rows, or uploaded file contents are included.",
    }


def _privacy_safe_value(value: Any, *, key: str = "") -> Any:
    """Remove local identifiers and row-level payloads from AI context."""

    normalized_key = key.lower()
    blocked_keys = {
        "path",
        "data_path",
        "input_path",
        "output_path",
        "file",
        "filename",
        "source_file",
        "expression_matrix",
        "raw_data",
        "patient_rows",
        "sample_ids",
        "patient_ids",
        "obs",
        "var",
    }
    if normalized_key in blocked_keys or normalized_key.endswith(("_path", "_file", "_filename")):
        return "[local_or_row_level_data_redacted]"
    if isinstance(value, dict):
        return {str(child_key): _privacy_safe_value(child, key=str(child_key)) for child_key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_privacy_safe_value(item, key=key) for item in value[:50]]
    if isinstance(value, str) and (value.startswith(("/", "file://")) or ":\\" in value):
        return "[local_path_redacted]"
    return value


def _intent_schema() -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "analysis_intent",
            "suggested_workflow",
            "confidence",
            "metadata_hints",
            "clarification_needed",
            "clarifying_question",
            "safety_classification",
            "reasoning_summary",
            "claim_boundary",
        ],
        "properties": {
            "analysis_intent": {"type": "string"},
            "suggested_workflow": {"type": "string", "enum": sorted(workflow_ids())},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "metadata_hints": {
                "type": "object",
                "additionalProperties": False,
                "required": ["batch_key", "donor_key", "label_key", "treatment_key", "outcome_key", "patient_id_key"],
                "properties": {
                    "batch_key": nullable_string,
                    "donor_key": nullable_string,
                    "label_key": nullable_string,
                    "treatment_key": nullable_string,
                    "outcome_key": nullable_string,
                    "patient_id_key": nullable_string,
                },
            },
            "clarification_needed": {"type": "boolean"},
            "clarifying_question": nullable_string,
            "safety_classification": {
                "type": "string",
                "enum": ["ruo_supported", "clinical_request", "insufficient_scope"],
            },
            "reasoning_summary": {"type": "string"},
            "claim_boundary": {"type": "string"},
        },
    }


def _explanation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "executive_summary",
            "claim_status",
            "evidence_supporting",
            "evidence_limiting",
            "next_validation_step",
            "model_did_not_change_statistics",
        ],
        "properties": {
            "executive_summary": {"type": "string"},
            "claim_status": {
                "type": "string",
                "enum": ["safe", "limited", "unsafe", "needs_validation", "inconclusive"],
            },
            "evidence_supporting": {"type": "array", "items": {"type": "string"}},
            "evidence_limiting": {"type": "array", "items": {"type": "string"}},
            "next_validation_step": {"type": "string"},
            "model_did_not_change_statistics": {"type": "boolean", "const": True},
        },
    }


def _public_ai_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"response_id"}}


def _inactive(reason: str, config: OpenAICopilotConfig) -> dict[str, Any]:
    return {
        "status": "not_used",
        "reason": reason,
        "model": config.model,
        "boundary": dict(AI_BOUNDARY),
    }


def _failure(exc: Exception, config: OpenAICopilotConfig) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": type(exc).__name__,
        "message": str(exc),
        "model": config.model,
        "boundary": dict(AI_BOUNDARY),
    }


def _safety_identifier() -> str:
    seed = os.environ.get("OMICSTRUST_SAFETY_IDENTIFIER") or "omicstrust-local-ruo"
    return "ot_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
