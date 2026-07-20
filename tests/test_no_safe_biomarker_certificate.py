import json

from examples.no_safe_biomarker_certificate import build_certificate, _json_safe


def test_no_safe_biomarker_certificate_blocks_batch_dominated_signal(tmp_path):
    run_dir = tmp_path / "audit_run"
    run_dir.mkdir()

    payload = {
        "trust": {
            "trust_level": "unsafe",
            "safe_to_interpret": False,
            "main_failure": "batch_dominated_signal",
        },
        "batch_risk": {
            "status": "high",
        },
        "stability": {
            "status": "high",
        },
        "empirical_null": {
            "status": "passed",
        },
    }

    (run_dir / "audit_result.json").write_text(json.dumps(payload), encoding="utf-8")

    cert = build_certificate(run_dir)

    assert cert["workflow"] == "no_safe_biomarker_claim_certificate"
    assert cert["decision"] == "no_safe_biomarker_claim_found"
    assert cert["biomarker_claim_allowed"] is False
    assert cert["ruo_only"] is True
    assert cert["clinical_use_allowed"] is False
    assert "safe_to_interpret_false_or_limited" in cert["reasons"]
    assert "batch_or_technical_confounding_risk" in cert["reasons"]


def test_no_safe_biomarker_certificate_strict_json_sanitizer():
    payload = {
        "nan": float("nan"),
        "inf": float("inf"),
        "nested": [{"neg_inf": -float("inf")}],
    }

    safe = _json_safe(payload)
    text = json.dumps(safe, allow_nan=False)
    loaded = json.loads(text)

    assert loaded["nan"] is None
    assert loaded["inf"] is None
    assert loaded["nested"][0]["neg_inf"] is None
