# OmicsTrust Private Deployment

OmicsTrust is designed to run in local/private mode for biotech datasets that should not leave a controlled environment.

## Local Web/API

```bash
omicstrust serve --host 127.0.0.1 --port 8000 --results-root results/platform
```

Open:

```text
http://127.0.0.1:8000
```

## Docker

```bash
cd deploy
docker compose up --build
```

The compose file mounts:

- `../data` as read-only input data
- `../results/platform` as persistent audit output, job history, and reports

## Security Posture

- Default CLI serving uses `127.0.0.1`.
- Uploaded files are stored under the configured local results root.
- No external service is called by the core audit path.
- Optional API token auth is enabled by setting `OMICSTRUST_API_TOKEN`.
- Use network controls, auth, and TLS before exposing beyond a trusted private network.

## Optional API Token

```bash
export OMICSTRUST_API_TOKEN="replace-with-strong-token"
omicstrust serve --host 127.0.0.1 --port 8000 --results-root results/platform
```

Or pass the token explicitly:

```bash
omicstrust serve --host 127.0.0.1 --port 8000 --results-root results/platform --api-token "replace-with-strong-token"
```

Clients may send:

```text
X-OmicsTrust-Token: replace-with-strong-token
```

or:

```text
Authorization: Bearer replace-with-strong-token
```

## API Surface

- `GET /health`
- `GET /`
- `POST /api/inspect/path`
- `POST /api/audits`
- `POST /api/audits/upload`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/summary.json`
- `GET /api/jobs/{job_id}/report.html`
- `GET /api/jobs/{job_id}/report.pdf`
- `GET /api/jobs/{job_id}/evidence_ledger.json`
- `GET /api/case-studies`

Research Use Only. Not for diagnosis, prognosis, treatment selection, or regulated clinical decision-making.
