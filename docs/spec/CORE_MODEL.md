# CORE MODEL

The formal data model (mission §9). Types live in `src/epistemos/model/`. Every object is a typed,
frozen dataclass with a `to_dict`/`from_dict` boundary; internally the engine and stores exchange
JSON-able dicts. **No field exists without a reason.**

## Envelope (shared by every object)

| field | type | meaning |
|-------|------|---------|
| `id` | str | opaque, engine-generated (`<prefix>_<uuid4hex>`); never caller-supplied |
| `kind` | str | discriminator (`fact`/`source`/`entity`/…) |
| `tenant` | str | hard isolation boundary |
| `namespace` | str | partition within a tenant (also the agent-private boundary) |
| `owner` | str | the agent that created the object |
| `created_at` | str | transaction time (ISO-8601 UTC) |
| `source` | str? | id of the backing `Source` |
| `source_hash` | str? | content hash of the backing payload |
| `confidence` | float | assertion confidence in `[0,1]` (≠ source trust, ≠ truth) |
| `provenance` | str[] | activity ids that produced it |
| `supersedes` / `contradicts` / `derived_from` | str[] | genealogy edges |
| `schema_version` | int | for migration (ADR-014) |
| `metadata` | dict | bounded (64 KiB, depth ≤ 32), JSON-only |

## Object types

- **Fact** — a bitemporal `(subject, predicate, object)` triple. `object` may be `None` (relation
  ended). Adds `valid_from`/`valid_to` (valid time), `tx_from`/`tx_to` (transaction time),
  `status` (`asserted`/`superseded`/`retracted`), `memory_class`. `believed == (tx_to is None)`.
- **Source** — `uri` (opaque, never dereferenced), `source_kind`, `trust` in `[0,1]` (authority).
- **Entity** — `name`, `entity_type`, `aliases`. Never auto-merged by similarity.
- **Relation** — `source_entity`, `target_entity`, `rel_type`.
- **Decision** — `statement`, `evidence[]` (must resolve in scope), `alternatives[]`, `outcome`,
  `reversible`.
- **Episode** — `summary`, `occurred_at`, `session`, `facts[]` (episodic memory unit).
- **Observation** — raw `text` from a source before it becomes a believed fact (carries `source_hash`).
- **Document** — `title`, `text`, `mime` (allow-listed, size-capped).

## Objects the model references but does not yet type as classes

`Actor`, `Session`, `Artifact`, `PolicyReference`, `ToolInvocation` are represented via the
`owner`/`principal`/`session` fields and `metadata` in v0.1; they become first-class types only if a
measured need appears (mission §39). This is a deliberate non-expansion, not an omission.

## Validation (fail closed)

Construction validates: non-empty subject/predicate; `valid_to ≥ valid_from`; finite confidence in
`[0,1]`; trust in `[0,1]`; strict ISO timestamps; no control characters / NUL in strings; bounded
metadata size and depth. See `docs/security/THREAT_MODEL.md` (S41–S50) and ADR-003/004/010.
