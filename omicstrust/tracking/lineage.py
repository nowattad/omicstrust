from __future__ import annotations


def build_lineage_record(input_fingerprint: str | None, output_fingerprints: dict[str, str] | None = None) -> dict:
    return {"input_fingerprint": input_fingerprint, "output_fingerprints": output_fingerprints or {}}
