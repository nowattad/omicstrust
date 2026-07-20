from __future__ import annotations

from pathlib import Path

import pytest
from defusedxml.common import EntitiesForbidden

import omicstrust.copilot.public_search as public_search
from omicstrust.api.jobs import JobStore


def test_public_search_rejects_file_scheme():
    with pytest.raises(public_search.UnsafeFetchError):
        public_search._fetch_json("file:///etc/passwd")


def test_public_search_rejects_localhost():
    for url in ["http://localhost:8000/metadata.json", "http://127.0.0.1/metadata.json", "http://[::1]/metadata.json"]:
        with pytest.raises(public_search.UnsafeFetchError):
            public_search._fetch_json(url)


def test_public_search_rejects_private_ip():
    for url in ["http://10.0.0.1/metadata.json", "http://172.16.0.1/metadata.json", "http://192.168.1.2/metadata.json"]:
        with pytest.raises(public_search.UnsafeFetchError):
            public_search._fetch_json(url)


def test_public_search_response_size_limit(monkeypatch):
    class FakeResponse:
        status = 200

        def __init__(self):
            self._sent = False

        def getheader(self, name):
            if name.lower() == "content-type":
                return "application/json"
            return None

        def read(self, _size):
            if self._sent:
                return b""
            self._sent = True
            return b"x" * 11

    class FakeConnection:
        def close(self):
            return None

    monkeypatch.setattr(public_search, "_open_safe_http_response", lambda parsed, timeout: (FakeConnection(), FakeResponse()))

    with pytest.raises(public_search.UnsafeFetchError):
        public_search._safe_fetch_bytes("https://93.184.216.34/metadata.json", max_bytes=10)


def test_public_search_uses_defusedxml():
    malicious = """<?xml version="1.0"?>
<!DOCTYPE root [
<!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>
"""
    with pytest.raises(EntitiesForbidden):
        public_search._xml_to_dict(malicious)
    assert "defusedxml.ElementTree" in Path(public_search.__file__).read_text(encoding="utf-8")
    assert "xml.etree.ElementTree" not in Path(public_search.__file__).read_text(encoding="utf-8")


def test_jobs_update_rejects_unknown_fields(tmp_path):
    store = JobStore(tmp_path / "platform")
    job = store.create_job(data_path=tmp_path / "data.h5ad")

    with pytest.raises(ValueError):
        store._update(job["job_id"], **{"status = 'completed' --": "owned"})

    fetched = store.get_job(job["job_id"])
    assert fetched["status"] == "queued"


def test_no_unverified_ssl_in_release_code():
    checked_roots = [Path("omicstrust"), Path("scripts")]
    offenders = []
    for root in checked_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "_create_unverified_context" in text or "CERT_NONE" in text:
                offenders.append(str(path))

    assert offenders == []
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")
    assert "prune scripts" in manifest

