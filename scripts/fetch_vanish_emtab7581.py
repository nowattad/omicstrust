from __future__ import annotations

from pathlib import Path
import re
import json
import gzip
import shutil
import urllib.parse

import requests

ACCESSION = "E-MTAB-7581"
OUTDIR = Path("data/real/vanish_sepsis")
RESULTS = Path("results/vanish_emtab7581_file_manifest.json")
OUTDIR.mkdir(parents=True, exist_ok=True)
RESULTS.parent.mkdir(parents=True, exist_ok=True)

BASES = [
    f"https://www.ebi.ac.uk/arrayexpress/files/{ACCESSION}/",
    f"https://ftp.ebi.ac.uk/pub/databases/arrayexpress/data/experiment/MTAB/{ACCESSION}/",
    f"https://www.ebi.ac.uk/biostudies/files/{ACCESSION}/",
]

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

def list_links(base: str):
    print("Listing:", base)
    try:
        r = session.get(base, timeout=60)
        print("  status:", r.status_code, "content-type:", r.headers.get("content-type"))
        if not r.ok:
            return []
        text = r.text
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I)
        urls = []
        for h in hrefs:
            if h in {"../", "./", "/"}:
                continue
            u = urllib.parse.urljoin(base, h)
            urls.append(u)
        return sorted(set(urls))
    except Exception as e:
        print("  ERROR:", repr(e))
        return []

def wanted(url: str):
    low = url.lower()
    keep_ext = (
        ".txt", ".tsv", ".csv", ".sdrf", ".idf",
        ".gz", ".zip", ".xlsx", ".xls",
        ".soft", ".json"
    )
    return any(low.endswith(x) for x in keep_ext) or ACCESSION.lower() in low

def download(url: str):
    name = urllib.parse.unquote(url.rstrip("/").split("/")[-1])
    if not name:
        return None
    dest = OUTDIR / name
    if dest.exists() and dest.stat().st_size > 0:
        print("Already exists:", dest, dest.stat().st_size)
        return dest

    print("Downloading:", url)
    with session.get(url, stream=True, timeout=180) as r:
        print("  status:", r.status_code, "size:", r.headers.get("content-length"))
        if not r.ok:
            return None
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    print("  saved:", dest, dest.stat().st_size)
    return dest

def sniff(path: Path, n=10):
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", errors="replace") as f:
                lines = [next(f, "") for _ in range(n)]
        else:
            with open(path, "rt", errors="replace") as f:
                lines = [next(f, "") for _ in range(n)]
        return "".join(lines)[:3000]
    except Exception as e:
        return f"[could not preview: {e!r}]"

all_links = []
for base in BASES:
    all_links.extend(list_links(base))

all_links = sorted(set(all_links))
candidates = [u for u in all_links if wanted(u)]

print()
print("Total links:", len(all_links))
print("Candidate data files:", len(candidates))
for u in candidates:
    print(" ", u)

downloaded = []
for u in candidates:
    p = download(u)
    if p:
        downloaded.append(p)

manifest = []
for p in sorted(downloaded):
    item = {
        "path": str(p),
        "name": p.name,
        "size_bytes": p.stat().st_size,
        "preview": sniff(p, n=8),
    }
    manifest.append(item)

RESULTS.write_text(json.dumps(manifest, indent=2))

print()
print("=" * 100)
print("DOWNLOADED FILES")
print("=" * 100)
for p in sorted(downloaded):
    print(p, p.stat().st_size)

print()
print("=" * 100)
print("PREVIEWS")
print("=" * 100)
for item in manifest:
    print()
    print("-" * 100)
    print(item["name"], item["size_bytes"])
    print("-" * 100)
    print(item["preview"])

print()
print("Saved manifest:", RESULTS)
