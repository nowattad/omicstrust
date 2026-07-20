# Private Deployment Security Summary

## Default Mode

The default web console binds to `127.0.0.1`, so it is accessible only from the same machine.

```bash
omicstrust serve --host 127.0.0.1 --port 8000 --results-root results/platform
```

## Optional API Token

Set an API token before starting the server:

```bash
export OMICSTRUST_API_TOKEN="replace-with-strong-token"
omicstrust serve --host 127.0.0.1 --port 8000 --results-root results/platform
```

Clients can send either:

```text
X-OmicsTrust-Token: replace-with-strong-token
```

or:

```text
Authorization: Bearer replace-with-strong-token
```

The web console includes an optional token box and stores the token only in the local browser session storage/cookie for same-origin API calls.

## Network Exposure

Do not bind to `0.0.0.0` unless the service is behind a trusted private network, TLS, and authentication.

## Data Handling

- Uploaded files stay under the configured local results root.
- Core audit does not call external services.
- Evidence ledgers record input fingerprints, configs, package versions, seeds, failure modes, and trust decisions.

Research Use Only. Not for regulated clinical use.
