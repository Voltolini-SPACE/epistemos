# EPISTEMOS — Claim / Evidence / Belief / Trust Model (EPISTEMOS-05)

> **Status: DESIGN — DEFERRED.** This document is part of the owner-mandated *collaborative /
> federated architecture assessment* (see `COLLABORATIVE_KNOWLEDGE_MODEL.md`, the anchor). **Nothing
> in it ships in v0.3.** Per the addendum §28/§31, v0.3 ships only current-defect fixes and
> backward-compatible hardening. Everything proposed here is classified `FUTURE_CAPABILITY` /
> `FOUNDATIONAL_PRIMITIVE` and targets **EPISTEMOS-05** (with tie-ins to 06/07). The anchor's
> mandated output block records this doc as `CLAIM_MODEL = PARTIAL_PRESENT` — the claim/belief
> split *exists today*; the review pipeline and claim graph are *designed, not built*.
>
> This document draws a hard line between **WHAT EXISTS TODAY** (with file/line evidence) and
> **WHAT IS PROPOSED** (deferred, ADR-shaped). Do not read a proposal as a shipped feature.

---

## 0. Scope and non-negotiables carried from the anchor

This model must respect the invariants the anchor and the audit already pinned down:

- **Local-first & zero-egress preserved.** A standalone, offline, single-agent EPISTEMOS keeps
  behaving exactly as today. The claim-review pipeline is *additive* and only activates for shared
  spaces; it never auto-syncs, uploads, or contributes without explicit authorization + policy +
  provenance + destination scope (anchor Q13/§25).
- **PRIVATE by default, fail-closed.** A claim's default visibility is PRIVATE. Absence of a policy
  never yields ACCEPT and never yields PUBLIC.
- **Four separate dimensions, never collapsed:** source-trust, contributor-reputation,
  claim-confidence, evidence-strength (anchor §6/§7; audit B-06). Collapsing any pair is a
  `REJECTED_DIRECTION`.
- **AGENT_OUTPUT ≠ VERIFIED FACT** (anchor §20). An agent's assertion is a *claim*, not truth.
- **EPISTEMOS enforces knowledge mechanics; it never grants capabilities.** The decision to *accept*
  or *promote* a claim under policy is a PDP concern (NOMOS or another) — EPISTEMOS records and
  enforces the mechanics of the decision, it does not author the policy. NOMOS is not a mandatory
  dependency (`identity/__init__.py` docstring: "EPISTEMOS is **not** a policy authority").

---

## 1. The target pipeline (PROPOSED — EPISTEMOS-05)

The addendum §1 mandates one pipeline. This is its EPISTEMOS-05 shape. Each stage is *additive over
today's primitives*; the stages marked **[today]** already exist, the rest are designed.

```
 Contributor
     │  (identity: tenant/agent/namespace + human principal + shared-space contributor id)
     ▼
 CLAIM  ── source · evidence · author · timestamp · provenance · scope · confidence
     │        [today: Observation carries source/author(owner)/timestamp/provenance/confidence]
     │        [proposed: explicit `scope`/visibility + `contributor` id + evidence refs]
     ▼
 VALIDATION  (a fail-closed gate, decided by policy — PDP, not EPISTEMOS)
     │   ├─ duplicate?          (content hash + subject/predicate match)
     │   ├─ corroborated?       [today: confirm() adds corroboration, delta ≥ 0]
     │   ├─ contradicted?       [today: contradict() is first-class, no silent overwrite]
     │   ├─ provenance valid?   (source pointer resolves in-scope — [today: B-06 scope check])
     │   ├─ source trusted?     [today: Source.trust dereferenced scope-safely]
     │   └─ policy allows?      (capability + space visibility — EPISTEMOS-04 prerequisite)
     ▼
 KNOWLEDGE CANDIDATE
     │        [proposed: a claim that passed structural/provenance checks, awaiting a belief verdict]
     ▼
   ┌── ACCEPT ──────► becomes/updates a believed Fact  [today: assert_fact / supersede]
   ├── DISPUTED ────► coexists with rivals, contradiction edge recorded  [today: contradict]
   └── REJECT ──────► not believed; retained in the ledger as an attributable claim
     ▼
 VERIFIED KNOWLEDGE   (addendum §1 — a Fact that survived validation + has an evidence trail)
```

**Key honesty point.** Today EPISTEMOS has the *endpoints* (Observation=claim, Fact=belief) and the
*edges* (contradiction, supersession, corroboration, derivation). What it does **not** have is the
**named intermediate `KNOWLEDGE CANDIDATE` state** or a **review/verdict record** distinct from
"assert a fact". EPISTEMOS-05 adds those as ledger events, not as a rewrite.

---

## 2. What EXISTS TODAY — claim vs belief (with evidence)

The claim/belief separation the anchor calls "the hard part" is real and shipped.

| Concept | Type today | Evidence |
|---|---|---|
| **Raw claim** | `Observation` — "A raw claim as delivered by a source, before it becomes a believed fact." | `model/__init__.py:240-250` |
| **Believed statement** | `Fact` — bitemporal `(subject, predicate, object)`; `believed` ⇔ `tx_to is None` | `model/__init__.py:110-141` |
| **External origin** | `Source(uri, source_kind, trust)`; URI is an identifier, **never dereferenced** | `model/__init__.py:148-158`; `core:405` "never dereferences this URI" |
| **Author (who ingested)** | `Envelope.owner` = the agent | `model/__init__.py:90` |
| **On whose behalf** | `Principal.principal` = optional human/service | `identity/__init__.py:81` |
| **Timestamp** | `Envelope.created_at` (tx time); `Fact.tx_from/tx_to`, `valid_from/valid_to` | `model/__init__.py:91,123-126` |
| **Provenance links** | `provenance`, `supersedes`, `contradicts`, `derived_from` tuples | `model/__init__.py:95-98` |
| **Claim confidence** | `Envelope.confidence ∈ [0,1]` | `model/__init__.py:94,102-104` |

An `Observation` is recorded via `observe()` (`core:420`); it is a claim. It becomes belief only
when someone `assert_fact()`s (`core:490`). The two are distinct `Kind`s in distinct ledger ops
(`OBSERVATION_RECORDED` vs `FACT_ASSERTED`). **Ingestion does not create belief.**

### 2.1 Contradiction is first-class; there is no silent overwrite

`contradict()` records a mutual `contradicts` edge and **neither fact is deleted or unbelieved**
(`core:698-717`, docstring: "Neither is deleted or unbelieved"). Rival claims coexist. This is the
mechanical basis for the `DISPUTED` verdict — EPISTEMOS-05 does not need to invent conflict storage,
only to name the verdict.

### 2.2 Supersession preserves genealogy

`supersede()` closes the old belief's `tx_to` (append-only — the *first* close stands, A-12) and
emits a **new** fact linking back via `supersedes=(fact_id,)`, carrying forward `derived_from`
(`core:545-596`). The old generation is never destroyed; `as_of()`/`timeline()` still see it. This is
the "no silent overwrite" property the poisoning defense (anchor Q14) leans on.

### 2.3 `confirm()` = corroboration only, delta ≥ 0 (B-03)

`confirm()` adds a corroboration annotation and may **only raise** confidence — a negative delta is
rejected (`core:738-741`). Before EPISTEMOS-03 a negative delta let any agent zero a rival's
confidence and flip which fact is "current" (audit B-03, isolation). Corroboration is now strictly
additive, which is exactly what the pipeline's "corroborated?" check needs.

**Residual (T-03, carried forward).** `confirm()` mutates confidence **in place** — confidence is a
mutable annotation, **not** a bitemporally-versioned quantity. So a later confirmation retroactively
changes the winner of a *past* `as_of()`. The `delta ≥ 0` fix removed the *weaponization*, but the
underlying property remains: **confidence is not yet generational.** Generational (versioned)
confidence is deferred to EPISTEMOS-05 (audit T-03; ADR-003 note). This is the single most important
"needs work" item for a faithful claim model.

---

## 3. The claim's fields (PROPOSED — additive over the Envelope)

A CLAIM in the EPISTEMOS-05 sense is an `Observation`-shaped record extended with the fields the
pipeline validates against. Nothing here removes an existing field ("não criar campos
arbitrariamente" — every field earns its place, `model` docstring).

| Field | Today? | Notes |
|---|---|---|
| `source` (→ `Source.trust`) | ✅ `Envelope.source` | external origin, scope-checked (B-06) |
| `author` (ingesting agent) | ✅ `Envelope.owner` | WHO CONTRIBUTED |
| `principal` (human/service) | ✅ `Principal.principal` | on whose behalf |
| `timestamp` | ✅ `created_at`/`tx_from` | transaction time |
| `provenance` / `derived_from` | ✅ tuples | derivation lineage |
| `confidence` | ✅ `[0,1]` | claim confidence (see §6) |
| `evidence[]` | ⚠️ partial | `Decision.evidence` exists (`model:204`); claims need the same refs |
| `scope` / `visibility` | ❌ proposed | first-class field, fail-closed PRIVATE — **EPISTEMOS-04 prerequisite** |
| `contributor` id | ❌ proposed | distinct from owner/principal/source, for shared spaces (anchor §5/§79) |
| `agent_provenance` | ❌ proposed | model/provider/tool/inputs/derivation — see §8 |

`scope`/`visibility` and `contributor` are **not** EPISTEMOS-05's to introduce — they are
EPISTEMOS-04 foundational primitives that EPISTEMOS-05 *consumes*. This doc assumes they land first.

---

## 4. The FOUR separate dimensions (and why collapsing them is REJECTED)

The anchor (§6/§7) and the audit (B-06) are emphatic: four independent axes, never one score.

| Dimension | Question it answers | Attached to | Today? |
|---|---|---|---|
| **Source trust** | Is the *origin* authoritative? | `Source.trust ∈ [0,1]` | ✅ `model:158` |
| **Contributor reputation** | Is the *contributor* reliable, per domain? | contributor identity | ❌ proposed (§7) |
| **Claim confidence** | How strongly is *this statement* asserted? | `Envelope.confidence` | ✅ `model:94` |
| **Evidence strength** | How well does the *evidence* support the claim? | evidence refs | ❌ proposed (§8) |

### 4.1 The audit PROVED trust and confidence are already independent

They are not merely *documented* as separate — they are *structurally* separate in the ranking that
decides which contradictory fact is "current":

```python
# temporal/__init__.py:100-114  — _rank_key(fact, trust_of)
def _rank_key(...) -> tuple[float, float, str, str]:
    return (
        float(trust_of(fact)) if trust_of is not None else 0.0,   # 1. source trust
        float(fact.get("confidence", 1.0)),                       # 2. claim confidence
        ...valid_from..., ...id...,                               # 3,4. recency, tie-break
    )
```

Trust and confidence are **distinct tuple components**, not a blended product (docstring: "Trust and
confidence stay *separate* dimensions"). B-06 further proved trust is dereferenced **scope-safely**:
a cross-tenant `source` pointer contributes **zero** trust, never leaking a foreign source's
authority into local ranking (`core:_trust_lookup` 758-780; audit B-06 FIXED). So the two axes are
independent *and* isolation-safe today.

### 4.2 Why collapsing is a REJECTED_DIRECTION

- Collapsing **source-trust + contributor-reputation** into one "reliability" score is explicitly
  rejected (anchor §6, classification table). A trusted *source* handed over by an unreliable
  *contributor* — and vice versa — must remain distinguishable, or evidence-laundering (anchor Q14)
  becomes invisible.
- Collapsing **confidence + evidence-strength** hides the difference between "asserted loudly" and
  "well-supported". An agent can emit high `confidence` on nothing; evidence strength is what a
  reviewer weighs.
- `likes = truth` / social scoring as *authority* is rejected (anchor §7). Reputation is an
  **input**, never the verdict (see §7).

The four axes feed a *policy* that produces a verdict; EPISTEMOS stores all four and the verdict, and
never silently combines them into one number that becomes "the truth".

---

## 5. The questions EPISTEMOS must answer (§8) — today vs deferred

The addendum §8 lists the questions the engine must answer about claims and belief. Honest status:

| # | Question | Answerable TODAY | Primitive |
|---|---|---|---|
| Q-a | **What do we believe now?** | ✅ | `current()`/`current_fact()` (`core:782,800`) |
| Q-b | **What claims exist (believed or not)?** | ✅ | `facts_for()` (`core:828`); `search()` (`core:1202`) |
| Q-c | **What was believed on date X?** | ✅ | `as_of(at_valid, at_tx)` (`core:806`) |
| Q-d | **Why did belief change?** | ⚠️ partial | `timeline()` (`core:847`) + `explain()` (`core:1274`) show supersession/derivation; a first-class *"reason"* is stored on supersede/retract but not yet a queryable review record |
| Q-e | **Who disputed this?** | ⚠️ partial | `contradicts` edges + `contradiction_notes` metadata exist; *contributor identity* of the disputer is EPISTEMOS-04/05 |
| Q-f | **What evidence supports each position?** | ⚠️ partial | `derived_from`/`Decision.evidence` + `explain()` walk lineage; a symmetric *per-claim evidence set with strength* is proposed (§8) |

**Fully answerable today: Q-a, Q-b, Q-c** — via `current`, `as_of`, `timeline`, `facts_for`,
`contradict`, `explain`. These are the bitemporal core and they are solid (audit "negative results":
tenant isolation and bitemporal queries survived the adversarial pass). **Needs work: Q-d, Q-e, Q-f**
— each blocked on either the contributor identity (EPISTEMOS-04) or the evidence/review record
(EPISTEMOS-05), not on the temporal engine.

---

## 6. Claim confidence today, and the T-03 residual

Confidence is a first-class `[0,1]` field on every object, validated finite and in range
(`core:_confidence` 192-201). It participates in ranking (§4.1) as a dimension *separate* from trust.
`confirm()` adjusts it additively (§2.3).

The one gap the audit is explicit about: **confidence is not bitemporally versioned (T-03).** A
`confirm()` overwrites the live value rather than creating a new generation, so
`as_of(past_instant)` re-ranked *after* a later confirm can pick a different winner than it would
have at the time. For a faithful "what did we believe on date X, *and how sure were we then*" answer,
confidence must become generational — a new fact generation (or a versioned confidence event) per
change, mirroring how belief itself is versioned via `tx_to`. **This is the headline EPISTEMOS-05
work item for the claim model.**

---

## 7. Per-domain reputation — EVALUATION INPUT, never AUTHORITY (PROPOSED)

Contributor reputation is the fourth dimension and the one most easily abused. Design constraints
(anchor §7):

- **Input, not verdict.** Reputation feeds the *policy* that a PDP evaluates; it never *is* the
  acceptance decision. EPISTEMOS supplies the number; it does not grant acceptance
  (`identity` docstring: "EPISTEMOS never *grants* capabilities").
- **Per-domain.** A contributor reliable about payments infrastructure is not thereby reliable about
  medicine. Reputation is scoped to a knowledge domain, not global.
- **Explainable.** Every reputation value must trace to the ledger events that produced it
  (corroborations landed, contradictions raised, supersessions of one's claims). No opaque score.
- **Auditable & temporal.** Reputation is itself a projection of attributable, timestamped events —
  reconstructible via replay, queryable "as of" a past instant, like every other belief.
- **Contestable.** A contributor (or reviewer) can dispute a reputation-affecting event; the dispute
  is a first-class contradiction, not a silent adjustment.

**REJECTED:** `likes = truth`, vote-counting as authority, or a single global reputation scalar that
overrides source trust and evidence. Sybil/coordinated-confirmation resistance for reputation is
**EPISTEMOS-07** (anchor Q14), not EPISTEMOS-05 — this doc only fixes reputation's *role*
(input/explainable/contestable), not its manipulation-resistance.

---

## 8. AGENT_OUTPUT ≠ VERIFIED FACT (§20) — provenance to record (PROPOSED)

An agent's output is a **claim** (an `Observation` / an unverified `Fact` candidate), never
automatically verified knowledge. To make agent-derived claims auditable, EPISTEMOS-05 records
agent-specific provenance on the claim (additive to the `Envelope`, likely in `metadata` first, a
typed field later):

| Provenance field | Purpose |
|---|---|
| **agent identity** | which agent emitted the claim (`owner` today; contributor id in shared spaces) |
| **model / provider** | the underlying model + provider that produced the text/derivation |
| **tool provenance** | which tool(s) the agent invoked, and their outputs, if any |
| **input sources** | the `source`/`derived_from` refs the claim was built from (must resolve in-scope) |
| **derivation** | how the output was produced from the inputs (prompt/plan reference, not the secret) |

With this, `explain()` (already O(1) via the provenance index, ADR-022; `core:1274-1289`) can walk
from a believed fact back through *"asserted by agent A, running model M via provider P, from
sources S1..Sn, derived by D"* — turning "an agent said so" into an inspectable chain rather than an
authority. **Belief still requires the validation gate (§1); agent provenance is what makes the
gate's verdict defensible, not a shortcut around it.**

---

## 9. The proposed Claim Graph vs today's fact/relation graph (ADR-style comparison)

The addendum §9 asks for a **Claim Graph**: `SOURCE → EVIDENCE → CLAIM` nodes with
`SUPPORTS / CONTRADICTS / SUPERSEDES / DERIVED_FROM` edges — and asks explicitly whether the current
fact/relation graph already represents it or whether a separate structure is needed. Here is that
comparison.

### 9.1 What the current graph already gives us

EPISTEMOS already stores a **typed, provenance-rich DAG** — not as a dedicated "claim graph", but as
edges on the `Envelope` plus the ledger:

| Claim-graph edge | Represented today by | Evidence |
|---|---|---|
| `SUPERSEDES` | `Fact.supersedes` tuple + `FACT_SUPERSEDED` op | `model:96`, `core:592` |
| `CONTRADICTS` | mutual `contradicts` tuple + `CONTRADICTION_RECORDED` op | `model:97`, `core:336-347` |
| `DERIVED_FROM` | `derived_from` tuple + `Decision.evidence` | `model:98,204` |
| `SUPPORTS` | ⚠️ *approximated* by `derived_from` + `confirm()` corroboration; **no explicit SUPPORTS edge** | `core:317-326` |
| `SOURCE → CLAIM` | `Envelope.source` pointer (scope-checked) | `model:92`, B-06 |
| `EVIDENCE → CLAIM` | `Decision.evidence`; not yet symmetric for `Fact`/`Observation` | `model:204` |

The `Entity`/`Relation` graph (`add_relation`, `query_graph`, `neighbors`) is a **separate,
world-modeling graph** — entities and their real-world relationships — **not** an epistemic graph of
claims and evidence. Conflating the two would be a category error: `query_graph` traverses "who
works for whom", not "which claim supports which".

### 9.2 The decision

**ADR-05x (PROPOSED): represent the Claim Graph as a typed VIEW/projection over existing ledger
edges, NOT as a new authoritative store — with two additive edge types.**

| Option | Verdict | Rationale |
|---|---|---|
| **A. Reuse the fact/relation `Entity`/`Relation` graph as-is** | ❌ Rejected | It models the *world*, not *claims about the world*. Overloading `rel_type` to carry SUPPORTS/CONTRADICTS would collapse two distinct graphs and break `query_graph` semantics. |
| **B. New standalone authoritative Claim-Graph store** | ❌ Rejected | Violates event-sourcing: the ledger is already the single source of truth (`core` docstring "no way to write state that bypasses the ledger"). A second authoritative graph could drift and would need its own tamper-evidence. |
| **C. Claim Graph = a projection over ledger edges + 2 new edge types (`SUPPORTS`, and explicit `EVIDENCE`)** | ✅ **Chosen** | SUPERSEDES/CONTRADICTS/DERIVED_FROM already exist as authoritative edges; the graph is a *reprojection* (like the FTS and provenance indexes — rebuildable, never a source of truth). Only `SUPPORTS` (positive corroboration as an edge) and a symmetric `EVIDENCE→CLAIM` link are genuinely new, and both are additive `Op`s. |

**Consequences of C:**
- The Claim Graph inherits tamper-evidence for free (it is a projection of the hash-chained ledger).
- It rebuilds via the existing `rebuild_projection()` path (`core:1308`) — `_apply` gains two edge
  ops, nothing else changes.
- `explain()` already walks `derived_from`/`supersedes`/`contradicts` generically (anchor Q3) — it
  extends to `SUPPORTS`/`EVIDENCE` with no structural rework.
- It stays **orthogonal to the entity/relation graph**: two graphs, two purposes, no overload.

**Answer to §9's direct question:** the current fact/relation graph does **not** already represent
the Claim Graph — it represents the *world graph*. But the *ledger's provenance edges* mostly do, so
the Claim Graph is a **new projection over existing structure plus two additive edges**, not a new
authoritative subsystem. This keeps EPISTEMOS single-source-of-truth and avoids an irreversible
storage decision (anchor Q10).

---

## 10. Verdicts as ledger events (PROPOSED — EPISTEMOS-05)

To make ACCEPT / DISPUTED / REJECT and the candidate state first-class *without* rewriting the
engine, add additive ledger ops (the anchor Q3 shows the `Op` set is open and `_apply` extends
generically):

| New Op (proposed) | Meaning | Reuses today |
|---|---|---|
| `claim_recorded` | a CLAIM entered a shared space | `OBSERVATION_RECORDED` shape |
| `claim_reviewed` | a verdict (accept/disputed/reject) + reviewer + rationale | new payload; `_apply` projection |
| `claim_disputed` | a dispute raised (who/why) | maps onto `CONTRADICTION_RECORDED` |
| `evidence_linked` | `EVIDENCE → CLAIM` with a strength | new edge (§9) |
| `claim_supported` | `SUPPORTS` edge | new edge (§9) |

Each is an *append-only, attributable, tamper-evident* event — so "who disputed this" (Q-e) and "why
did belief change" (Q-d) become directly queryable, closing the two big partials in §5. **A verdict
event records the mechanics of a decision made by a policy/PDP; EPISTEMOS does not itself decide
acceptance** (§0).

---

## 11. Consistency check against the anchor

| Anchor decision | This doc |
|---|---|
| `CLAIM_MODEL = PARTIAL_PRESENT` | §2 (present: Observation/Fact/edges) vs §1,§10 (designed: pipeline/verdicts) |
| Contributor a 4th identity, distinct from owner/principal/source | §3, §4 (proposed; EPISTEMOS-04 supplies it) |
| Four dimensions never collapsed; trust≠confidence proven (B-06, `_rank_key`) | §4.1–§4.2 |
| Claim graph = SUPPORTS/CONTRADICTS/SUPERSEDES/DERIVED_FROM (FUTURE_CAPABILITY) | §9 (projection + 2 additive edges) |
| Generational confidence (T-03) deferred | §2.3, §6 |
| Reputation as input, never authority; `likes=truth` rejected | §7 |
| AGENT_OUTPUT ≠ VERIFIED FACT (§20) | §8 |
| EPISTEMOS enforces mechanics, never grants capability; NOMOS not mandatory | §0, §7, §10 |
| Local-first / zero-egress / PRIVATE-by-default preserved | §0 |

---

## 12. What EPISTEMOS-05 must build (summary), and what it must NOT

**Build (deferred to EPISTEMOS-05):**
1. Generational (bitemporally-versioned) confidence — closes T-03; the top item.
2. `KNOWLEDGE CANDIDATE` state + verdict ledger events (`claim_reviewed`/`claim_disputed`) — §10.
3. Symmetric per-claim evidence set + `SUPPORTS`/`EVIDENCE` edges (Claim-Graph projection, ADR-05x).
4. Per-domain contributor reputation as an explainable/auditable/temporal/contestable **input** — §7.
5. Agent-provenance fields (model/provider/tool/inputs/derivation) on agent-emitted claims — §8.

**Do NOT (rejected / out of scope for -05):**
- Do not collapse any of the four dimensions into one score (§4.2).
- Do not make the Claim Graph a second authoritative store (§9.1, Option B).
- Do not treat agent output, corroboration count, or reputation as an acceptance authority.
- Do not add Sybil/poisoning resistance here — that is EPISTEMOS-07.
- Do not weaken PRIVATE-by-default, zero-egress, or fail-closed to make review "convenient".

**Depends on (must precede -05):** EPISTEMOS-04 `space`/`visibility` first-class field and
contributor identity. The claim-review pipeline cannot be safe until visibility and authorization
are first-class and fail-closed (anchor `EPISTEMOS_04_RECOMMENDATION`).

---

*End — EPISTEMOS-05 claim/evidence/belief/trust model. DESIGN, DEFERRED. No code ships from this
document in v0.3.*
