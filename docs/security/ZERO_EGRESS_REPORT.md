# Zero-Egress Report

**Gate:** `ZERO_EGRESS_DEFAULT = PASS` — measured, not assumed (mission §L).

## Claim

The EPISTEMOS core makes **no network calls** for any operation. This is a property of the code
(zero third-party runtime deps; no `socket`/`urllib`/`http` client usage in the core; the only
`http.server`/`socketserver` usage is the *optional* REST adapter which the caller must explicitly
start and which binds `127.0.0.1`), and it is **verified by test**, not merely reasoned about.

## Measurement method

`tests/security/test_zero_egress.py` booby-traps the socket layer for the duration of a full core
lifecycle:

```python
monkeypatch.setattr(socket, "socket", boom)             # any socket construction -> raise
monkeypatch.setattr(socket, "create_connection", boom)  # any outbound connection -> raise
monkeypatch.setattr(socket, "socketpair", boom)
```

Then it exercises the entire surface under the trap: `add_source`, `observe`, `ingest_document`,
`assert_fact`, `supersede`, `confirm`, `add_entity`, `add_relation`, `query_graph`,
`record_decision`, `search`, `timeline`, `explain`, `health(verify=True)`, `export`,
`verify_integrity`, and a full `import_events` into a fresh store — on **both** the in-memory and
SQLite backends (the `engine` fixture is parametrized).

If any of those paths attempted to open a socket, `boom` would raise `NetworkAttempted` and the
test would fail.

## Result

```
$ python -m pytest tests/security/test_zero_egress.py -v
test_full_lifecycle_makes_no_network_calls[memory] PASSED
test_full_lifecycle_makes_no_network_calls[sqlite] PASSED
test_source_uri_is_never_dereferenced[memory]      PASSED
test_source_uri_is_never_dereferenced[sqlite]      PASSED
```

- **No implicit egress** on startup, DB init, write, read, search, export, import, or health.
- **SSRF-style URIs are never dereferenced:** `add_source(uri="http://169.254.169.254/…")` stores
  the string as an opaque identifier; the core never fetches it. Verified.

## Scope & honesty notes

- **Dev tooling does not count** as runtime egress: installing `pytest`/`ruff`/`mypy` via `uv` hits
  PyPI, but that is build-time, not the running engine (mission §L).
- The **optional REST server** and **MCP server** are *interfaces the operator starts on purpose*;
  they listen locally (REST binds `127.0.0.1` by default, never `0.0.0.0`) and still make no
  *outbound* connections. They are not part of the zero-egress *core* guarantee but do not violate it.
- A future `ModelProvider` that talks to a remote model WOULD egress — by design that is opt-in,
  behind an explicit provider, and never the default (`NullModelProvider`). The core never calls it.
