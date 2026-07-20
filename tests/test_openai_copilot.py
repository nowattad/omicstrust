from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

from omicstrust.copilot.openai_layer import (
    DEFAULT_OPENAI_MODEL,
    apply_gpt_workflow_suggestion,
    explain_result_with_gpt,
    interpret_request_with_gpt,
)
from omicstrust.copilot.planner import build_copilot_plan
from omicstrust.copilot.schemas import CopilotRequest


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(id="resp_test", output_text=json.dumps(self.payload))


class FakeClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


def _intent_payload(workflow="batch_risk_audit"):
    return {
        "analysis_intent": "Audit batch confounding before interpretation.",
        "suggested_workflow": workflow,
        "confidence": 0.94,
        "metadata_hints": {
            "batch_key": "batch",
            "donor_key": None,
            "label_key": "condition",
            "treatment_key": None,
            "outcome_key": None,
            "patient_id_key": None,
        },
        "clarification_needed": False,
        "clarifying_question": None,
        "safety_classification": "ruo_supported",
        "reasoning_summary": "The request asks for a confounding audit.",
        "claim_boundary": "Research Use Only.",
    }


def _explanation_payload():
    return {
        "executive_summary": "The deterministic audit found stable structure but interpretation remains limited.",
        "claim_status": "limited",
        "evidence_supporting": ["Structural signal was detected."],
        "evidence_limiting": ["Batch metadata were unavailable."],
        "next_validation_step": "Provide batch metadata and rerun the locked audit.",
        "model_did_not_change_statistics": True,
    }


def test_gpt_5_6_is_default_model():
    assert DEFAULT_OPENAI_MODEL == "gpt-5.6"


def test_gpt_never_overrides_explicit_workflow():
    request = CopilotRequest(
        user_request="Search public data, but run the exact inspection workflow.",
        workflow="dataset_inspection",
        data_mode="local_path",
        data_path="study.h5ad",
        use_ai=True,
    )
    plan = build_copilot_plan(request)
    client = FakeClient(_intent_payload("public_dataset_search"))

    ai_plan = interpret_request_with_gpt(request, plan, client=client)
    final_plan = apply_gpt_workflow_suggestion(request, plan, ai_plan)

    assert ai_plan["suggested_workflow"] == "dataset_inspection"
    assert final_plan.workflow == "dataset_inspection"
    assert final_plan.ai_assistance["boundary"]["may_change_explicit_workflow"] is False


def test_gpt_request_excludes_file_contents_and_data_path():
    request = CopilotRequest(
        user_request="Audit batch leakage.",
        data_mode="local_path",
        data_path="/private/patient_expression.h5ad",
        batch_key="batch",
        use_ai=True,
    )
    plan = build_copilot_plan(request)
    client = FakeClient(_intent_payload())

    interpret_request_with_gpt(request, plan, client=client)

    sent = json.loads(client.responses.last_kwargs["input"])
    assert "data_path" not in sent
    assert "/private/patient_expression.h5ad" not in client.responses.last_kwargs["input"]
    assert client.responses.last_kwargs["store"] is False
    assert client.responses.last_kwargs["model"] == "gpt-5.6"


def test_gpt_explanation_cannot_change_deterministic_statistics():
    request = CopilotRequest(user_request="Explain this RUO result.", use_ai=True)
    result = {
        "status": "completed",
        "selected_workflow": "de_novo_treatment_response_discovery",
        "statistics": {"OR": 0.16881, "fdr": 0.03145},
        "what_cannot_be_claimed": ["No treatment recommendation."],
    }
    original = deepcopy(result)
    client = FakeClient(_explanation_payload())

    explanation = explain_result_with_gpt(request, result, client=client)

    assert result == original
    assert explanation["model_did_not_change_statistics"] is True
    assert explanation["authoritative_source"] == "deterministic_omicstrust_result"
    sent = json.loads(client.responses.last_kwargs["input"])
    assert sent["deterministic_result"]["statistics"]["OR"] == 0.16881


def test_gpt_explanation_redacts_local_paths_and_row_level_data():
    request = CopilotRequest(user_request="Explain this RUO result.", use_ai=True)
    result = {
        "status": "completed",
        "dataset_summary": {
            "shape": [116, 28_220],
            "data_path": "/private/vanish_patient_expression.h5ad",
            "patient_rows": [{"patient_id": "secret-001", "outcome": 1}],
        },
        "statistics": {"fdr": 0.03145},
    }
    client = FakeClient(_explanation_payload())

    explain_result_with_gpt(request, result, client=client)

    serialized = client.responses.last_kwargs["input"]
    sent = json.loads(serialized)
    assert "/private/vanish_patient_expression.h5ad" not in serialized
    assert "secret-001" not in serialized
    assert sent["deterministic_result"]["dataset_summary"]["shape"] == [116, 28_220]


def test_ai_disabled_is_explicit_deterministic_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = CopilotRequest(user_request="Audit batch leakage.", data_mode="no_data")
    plan = build_copilot_plan(request)

    ai_plan = interpret_request_with_gpt(request, plan)

    assert ai_plan["status"] == "not_used"
    assert ai_plan["reason"] == "disabled_or_api_key_missing"
