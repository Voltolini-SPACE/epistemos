# EPISTEMOS Threat Model

Mission §25. Every attack class is reproduced as a red test where reachable, then mitigated and
locked with a green + anti-regression test. This document maps each `Sxx` to its mechanism and
evidence, and is honest about **RESIDUAL** risks that a memory engine cannot eliminate.

## Assets

- **Knowledge integrity** — facts/entities/relations/decisions and their bitemporal state.
- **Provenance & audit** — the tamper-evident event ledger and the genealogy it anchors.
- **Tenant/agent isolation** — no cross-tenant or unauthorized cross-agent read/write.
- **Availability & recoverability** — crash consistency, backup/restore, rebuildable projection.
- **Confidentiality** — no exfiltration; secrets never logged.

## Trust boundaries

1. **Caller ↔ Engine** — every call carries a `Principal`; unknown scope/auth ⇒ refuse (fail closed).
2. **Ingested content ↔ Engine** — all ingested text/URIs are **inert data**, never instructions,
   never dereferenced, never fed to a model by the core.
3. **Network boundary (REST/MCP) ↔ Engine** — treated as **hostile**; identity is server-side; the
   MCP tool surface is a fixed, narrow allow-list; REST binds localhost.
4. **Storage ↔ Domain** — the store is a dumb, scope-filtering persistence layer; semantics live in
   the domain; a store bug cannot leak across tenants (query methods filter by `(tenant, namespace)`).

## Core principle: UNKNOWN ≠ ALLOW (mission §26)

When tenant, authorization, source, schema, or integrity cannot be determined, the operation is
refused. Ingested content is data until an explicitly authorized component interprets it.

## Attack battery S1–S50

| # | Attack | Status | Mechanism / evidence |
|---|--------|--------|----------------------|
| S1 | Prompt injection via ingested docs | **MITIGATED** | ingested text is inert; core never sends it to a model. `tests/security/test_injection.py::test_stored_prompt_injection_is_data` |
| S2 | Stored prompt injection | **MITIGATED** | same; only the ingest op is recorded, nothing is executed. same test |
| S3 | Graph injection | **MITIGATED (by design)** | no query language; graph via typed methods; strings inert. `test_injection` |
| S4 | Cypher injection | **N/A (no surface)** | no Cypher anywhere. `test_cypher_and_sparql_payloads_are_inert` |
| S5 | SPARQL injection | **N/A (no surface)** | no SPARQL anywhere. same test |
| S6 | SQL injection | **MITIGATED** | 100% parameterized SQL; static fragments only. `test_sql_injection_payload_is_inert` (runs on SQLite) |
| S7 | SSRF | **MITIGATED** | core makes no outbound calls; URIs never dereferenced. `test_zero_egress.py` |
| S8 | Path traversal | **MITIGATED** | identifiers reject `..`/`/`/`\`/NUL; URIs stored, never opened. `test_validation` + `identity.validate_name` |
| S9 | Malicious URI | **MITIGATED** | URI stored as opaque string; control chars rejected; never fetched. `test_source_uri_is_never_dereferenced` |
| S10 | Hostile MIME | **MITIGATED** | mime allow-list. `test_s10_hostile_mime_rejected` |
| S11 | Parser bomb | **MITIGATED** | no XML/YAML; JSON via stdlib with size + depth caps. `test_s45` + `test_s12` |
| S12 | Oversized document | **MITIGATED** | 5 MiB cap. `test_s12_oversized_document` |
| S13 | Graph expansion DoS | **MITIGATED** | hop cap + node budget in `query_graph`. `test_s13_graph_traversal_is_bounded` |
| S14 | Recursive relationship DoS | **MITIGATED** | visited-set + node budget; provenance walk has depth + cycle guard. `query_graph` + `provenance.explain(depth,_seen)` |
| S15 | Poisoning | **MITIGATED / RESIDUAL** | content inert; low-trust can't become "current"; contradictions kept not overwritten. RESIDUAL: a *high-trust* source can assert falsehoods — provenance makes it auditable & reversible. `test_quality_corpus` |
| S16 | Memory poisoning | **MITIGATED** | no destructive delete; supersede/retract preserve history; trust-aware resolution. `test_contradiction` |
| S17 | False provenance | **MITIGATED / RESIDUAL** | `source_hash` binds observation content; ledger hash-chain makes edits evident; actor recorded. RESIDUAL: the engine records *who asserted what*, it cannot verify external-world truth. `test_provenance`, `test_ledger` |
| S18 | Forged source | **MITIGATED** | sources are scoped ledger-created objects; cross-scope source refs ⇒ NotFound. `_ref_in_scope`, `test_tenant_isolation` |
| S19 | Forged agent identity | **MITIGATED** | `owner` set by the engine from the Principal, not from payload; REST identity from token, MCP from server config. `test_rest`, `test_mcp` |
| S20 | Cross-tenant access | **MITIGATED (fail-closed)** | scope guard on every read/write. `tests/security/test_tenant_isolation.py` |
| S21 | Cross-agent access | **MITIGATED** | shared read in-namespace, owner-guarded writes, per-agent namespace for private. `test_agent_isolation.py` |
| S22 | Unauthorized write | **MITIGATED** | capability check + owner guard + scope. `test_agent_isolation` |
| S23 | Unauthorized retract | **MITIGATED** | `retract` needs capability + owner guard. `test_other_agent_cannot_clobber` |
| S24 | Decision history tampering | **MITIGATED** | decisions live in the hash-chained ledger; tamper detected. `test_ledger`, `test_export_import` |
| S25 | Replay attack | **MITIGATED** | import into non-empty store refused; events seq-ordered + chained. `test_duplicate_delivery_rejected` |
| S26 | Stale context | **MITIGATED** | bitemporal `current` vs `as_of`; superseded ≠ current. `test_temporal`, `test_quality_corpus` |
| S27 | Rollback failure | **MITIGATED** | atomic transactions; fault injection proves clean rollback. `tests/unit/test_atomic.py` |
| S28 | Concurrent writes | **MITIGATED** | serialized writers + atomic; 30-cycle race battery. `tests/race/` |
| S29 | Partial transaction | **MITIGATED** | no intermediate state at any stage. `test_atomic` (before/during-ledger/during-projection) |
| S30 | Process crash | **MITIGATED** | WAL + `synchronous=FULL`; real SIGKILL recovery. `tests/chaos/test_sigkill_during_write_recovers` |
| S31 | Filesystem corruption | **MITIGATED / RESIDUAL** | ledger `verify_chain` (hash-chain integrity) + FTS `verify()` content-drift detection (EPISTEMOS-03) + rebuild-from-ledger after crash. RESIDUAL: hardware bit-rot is out of scope; logical tamper IS detected. *(EPISTEMOS-03 OV-07 correction: `PRAGMA integrity_check` was cited but is not invoked by the shipped code; SQLite still enforces WAL+synchronous=FULL for crash-consistency. Integrity is proven by the hash chain, not by that pragma.)* `test_chaos`, `test_index_robustness` |
| S32 | Network outage | **N/A (core) / TOLERATED** | core is zero-egress; REST/MCP are local. no network dependency to fail |
| S33 | Model outage | **MITIGATED** | `NullModelProvider`; core needs no model. `tests/unit/test_null_llm.py` |
| S34 | Embedding outage | **MITIGATED** | no embeddings required; retrieval has no vector component by default. `test_null_llm`, `test_retrieval` |
| S35 | Malicious MCP client | **MITIGATED** | fixed safe tool registry; server-side identity; validated args; injection inert. `tests/integration/test_mcp.py` |
| S36 | Malicious MCP server/tool output | **N/A (server role) / PRINCIPLE** | EPISTEMOS is the MCP *server* here; a future MCP *client* adapter must treat tool output as untrusted data (documented in `OTHER_PROJECTS.md`, adapter specs) |
| S37 | Dependency compromise | **MITIGATED** | **zero runtime dependencies** ⇒ no runtime supply chain. `SBOM.md`, `DEPENDENCY_INVENTORY.md` |
| S38 | Serialization attack | **MITIGATED** | JSON only, **no pickle**; export/import validates schema + verifies chain. `test_export_import`, `test_s48` |
| S39 | Deserialization attack | **MITIGATED** | `json.loads` only; no `eval`/`pickle`; size caps. `test_s48_import_takes_data_not_paths` |
| S40 | Secret exfiltration | **MITIGATED** | zero-egress (nothing can leave); structured events never dump payloads/secrets; metadata capped. `test_zero_egress`, observability policy |
| S41 | Malformed timestamps | **MITIGATED** | strict ISO parsing; reject garbage. `test_s41_malformed_timestamp` |
| S42 | NaN/Infinity confidence | **MITIGATED** | `math.isfinite` + `[0,1]` bound. `test_s42_nan_inf_confidence` |
| S43 | Unicode confusables | **MITIGATED / RESIDUAL** | control chars rejected; identifiers ASCII-restricted; entities never auto-merged so look-alikes stay distinct. RESIDUAL: display-layer homoglyphs are a UI concern. `test_s43`, `test_entity_identity` |
| S44 | Oversized metadata | **MITIGATED** | 64 KiB canonical-JSON cap. `test_s44_oversized_metadata` |
| S45 | Deeply nested JSON | **MITIGATED** | depth cap (32). `test_s45_deeply_nested_metadata` |
| S46 | Duplicate IDs | **MITIGATED** | ids are engine-generated uuid4; no external id accepted on create. `test_s46` |
| S47 | Hash collision handling | **MITIGATED (contract)** | sha256; canonical + deterministic + content-distinct. `test_s47`. RESIDUAL: sha256 collision computationally infeasible |
| S48 | Malicious import archive/path | **MITIGATED** | import takes a JSON dict, not a path/archive; malformed records ⇒ SchemaError. `test_s48` |
| S49 | Zip bomb | **N/A** | no archive ingestion; document size caps bound any decompression-style blowup |
| S50 | Namespace unicode collision | **MITIGATED** | identifier regex rejects non-ASCII / zero-width. `test_s50_namespace_unicode_confusable_rejected` |

## Residual risks (stated plainly)

- **Truth vs. record.** EPISTEMOS guarantees *provenance and integrity of what was asserted*, not the
  external-world *truth* of a high-trust source's assertions. Poisoning by a trusted principal is
  auditable and reversible (supersede/retract, full history) but not preventable by the store.
- **Hardware/OS-level corruption** below SQLite (bit-rot, a lying `fsync`) is out of scope; logical
  tampering of history IS detected by the hash chain.
- **Tail-truncation / full re-chain** of the ledger require an external anchor (`expected_head`/
  `expected_count`) to detect — provided and tested, but the anchor must be stored out-of-band.
- **Display-layer homoglyphs** (S43) are a rendering concern for consumers, not the engine.

## Fail-closed summary

Missing principal ⇒ `IdentityError`. Out-of-scope ref ⇒ `NotFoundError` (no existence leak) or
`TenantIsolationError` on write. Unknown schema ⇒ `SchemaError`. Broken chain ⇒ `IntegrityError`.
Unknown capability ⇒ `AuthorizationError`. None of these degrade to "allow".
