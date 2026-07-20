#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

.venv/bin/omicstrust audit examples/synthetic.h5ad \
  --batch-key batch \
  --donor-key donor \
  --label-key signal_label \
  --output results/build_week_synthetic \
  --config configs/singlecell_audit.yaml

echo "Audit complete: results/build_week_synthetic/report.html"
echo "Starting private local workspace at http://127.0.0.1:8765"
exec .venv/bin/omicstrust serve \
  --host 127.0.0.1 \
  --port 8765 \
  --results-root results/build_week_platform
