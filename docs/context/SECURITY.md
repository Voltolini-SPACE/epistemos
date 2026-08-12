# Context Envelope — Security

**Invariant: `PRIVATE_CONTEXT_LEAK = 0`.** The envelope is a post-retrieval transform over objects
that were *already* authorized; it never lowers a boundary and never dereferences an unauthorized
object.

## Threat model

An attacker is a valid principal (a tenant, an agent, a space member) trying to read something they
are not entitled to — via the *compaction* path rather than raw search.

| attack | defense |
|---|---|
| private **prior version** surfaced through history collapse | only authorized objects enter the pool; a private prior is never retrieved, never folded, never in `reachable_ids` |
| private **contradiction** attached to a shared claim | attached contradictions are re-authorized with `is_readable` per principal (M3) |
| private **collapsed member** leaked via a group handle | group members come only from authorized, retrieved objects |
| **evidence / source / decision** read across a boundary | every candidate passes `is_readable` in `_authorized_hits` (defense-in-depth over `search`) |
| **cross-space** collapse (fold a private version into a shared canonical) | folding is within the authorized set only; a private version isn't in it |
| **cross-tenant** read | `search` firewalls by tenant; the envelope re-checks; an outsider's envelope is empty |

## Mechanisms

1. **Authorize-first pool.** `_authorized_hits` starts from `engine.search` (already firewalled)
   and re-applies `is_readable` to every object, skipping structural kinds
   (`space`, `grant`, `dimension`, `microconnection`).
2. **Re-authorized relation-following.** The one followed relation (attached contradiction) is
   `is_readable`-gated per principal.
3. **No payload-supplied authority.** `engine.context` derives tenant / principal / capabilities
   from the `Principal` object only — never from the query or any request payload. The REST/MCP
   surfaces (if enabled) bind the principal server-side; they do not accept it from the client.
4. **No new cache.** This promotion adds no cache. There is no shared, cross-principal state that
   could serve one principal's compacted view to another.

## Verification

- `tests/context/test_context.py`: `test_private_prior_version_never_leaks`,
  `test_private_contradiction_attached_to_shared_claim_no_leak`, `test_cross_tenant_no_leak`.
- Mutation gate (`tools/eps08_mutation.py`): M3 removes the attached-contradiction authz check and is
  killed → `NON_EQUIVALENT_SURVIVED = 0`.
- Benchmark-scale sweep: no principal sees another tenant's objects across all probe queries
  (`PRIVATE_CONTEXT_LEAK = 0` at 250×4).
- Race: 6 threads × 30 iterations of concurrent `build` for two principals raise nothing and never
  cross-contaminate.
