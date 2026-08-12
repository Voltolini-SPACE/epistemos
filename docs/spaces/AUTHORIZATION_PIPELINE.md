# Authorization Pipeline — the Knowledge Firewall (EPISTEMOS-04, SHIPPED)

Normative decision: [ADR-026](../adr/ADR-026-authorized-retrieval.md). Every shared read/write
passes through the firewall (mission §8); failure at any stage is **DENY**.

```
   IDENTITY   →   TENANT   →   SPACE   →   CAPABILITY   →   POLICY   →   AUTHORIZED
 require_       obj.tenant   can_read_    principal.       (external    operation
 principal      == p.tenant  object()     require(cap)     PDP hook,    proceeds
 (fail closed)  (hard)       (spaces)     (fail closed)    default:
                                                           in-scope)
```

## The pure read decision — `authz.can_read_object`

```
DENY if obj.tenant != principal.tenant                 # TENANT (hard, never crossed)
ALLOW if "admin" in principal.capabilities             # admin override
if obj.spaces == ():                                    # implicit PRIVATE space
    ALLOW iff obj.owner == principal.agent AND obj.namespace == principal.namespace
for space in obj.spaces:                                # explicit placements (any grants access)
    resolve (visibility, owner, tenant) or skip         # dangling -> no access (fail closed)
    skip if space.tenant != principal.tenant
    ALLOW if visibility >= ORGANIZATION                 # tenant-wide (ORG/COMMUNITY/PUBLIC)
    ALLOW if visibility == TEAM and (owner==agent or is_member(space, agent))
    ALLOW if visibility == PRIVATE and owner==agent
DENY                                                    # default deny
```

`is_member` reads projected server-side grant state — never a caller claim.

## Applied candidate-boundary-first (mission §12)

The predicate `Engine._can_read` is threaded through **every** read surface, applied to candidates
**before** any scoring/ranking/listing so an unauthorized object cannot leak via score, rank, count,
timing (of ranking), metadata or existence:

`get` · `search` (both retrievers, before TF·IDF/BM25) · `current`/`as_of`/`facts_for`/`timeline` ·
`recall` · `explain` (elides unreadable genealogy) · `neighbors`/`query_graph` (edge visible only if
relation AND far endpoint readable) · `export(principal)` (only readable objects' events).

The scan fallback enforces the identical predicate as the FTS path (a degraded index never leaks).

## Write-side firewall

Cross-agent additive writes require read access to the target: `confirm`/`contradict` on a fact you
cannot see raise `NotFoundError` (no blind cross-space mutation). Clobbering writes
(`supersede`/`retract`/`correct_validity`/`merge`/`split`) keep the v0.3 owner guard; a superseding
fact **inherits the original owner + spaces** so a correction preserves the audience.

Placement (`share`/`promote`) requires object ownership + reachable destination; promotion to ORG+
requires `knowledge.promote` (the P0 gate, [PRIVATE_PUBLIC_INVARIANT](PRIVATE_PUBLIC_INVARIANT.md)).

## Evidence

Mutation: `spaces_deny_to_allow`, `spaces_owner_check_removed`, `spaces_member_check_removed`,
`spaces_search_authorize_removed`, `spaces_grant_active_ignored` — all killed (32/32). Tests:
`test_authz_unit.py`, `test_private_public_invariant.py`.
