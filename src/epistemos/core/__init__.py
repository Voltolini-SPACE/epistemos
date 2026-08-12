"""The EPISTEMOS Engine — the single, consistent domain surface (mission §19).

Every mutation follows exactly one path:

    command -> validation -> auth/tenant check -> event -> ledger -> projection -> result

There is no way to write state that bypasses the ledger: the only code that writes the
projection is :meth:`Engine._persist` (store + lexical index), called only from
:meth:`Engine._apply`, whose only caller is :meth:`Engine._emit`, which appends the sealed
event first. Live writes and ledger import/rebuild share ``_apply``, so a restored database
(and its index) is the same logical state as the original (event sourcing).

Security posture: no operation runs without a :class:`~epistemos.identity.Principal`;
tenant/namespace isolation is enforced on every read and write; ingested content is inert
data (never executed, never dereferenced); the core makes no network calls.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, overload

from .._util import Clock, canonical_json, hash_obj, new_id, now_utc, parse_instant, to_iso
from ..authz import can_read_object
from ..claims import (
    Claim,
    ClaimStatus,
    ContributorKind,
    Evidence,
    EvidenceKind,
    EvidenceRelation,
    Review,
    Verdict,
)
from ..claims.belief import derive_belief
from ..claims.policy import LocalDefaultPolicy, Policy, PolicyRequest
from ..errors import (
    AuthorizationError,
    ConflictError,
    IntegrityError,
    NotFoundError,
    SchemaError,
    ValidationError,
)
from ..identity import Principal, validate_name
from ..identity import require_principal as _require_principal
from ..index import IndexHealth
from ..index.fts import SqliteFtsIndex
from ..index.provenance import SqliteProvenanceIndex
from ..index.text import Tokenizer, get_tokenizer
from ..ledger import GENESIS_HASH, Event, LedgerRecord, Op, seal, verify_chain
from ..model import (
    SCHEMA_VERSION,
    BeliefStatus,
    Decision,
    Document,
    Entity,
    Episode,
    Fact,
    MemoryClass,
    Observation,
    Relation,
    Source,
)
from ..provenance import explain as _explain_obj
from ..provenance import explain_decision as _explain_decision
from ..retrieval import IndexedRetriever, LegacyScanRetriever, Retriever, Weights
from ..spaces import KnowledgeSpace, Visibility, resolve_visibility
from ..storage import SQLiteStore, Store, open_store
from ..temporal import resolve_current

__all__ = ["Engine", "EngineLimits"]

_UNSET: Any = object()

_KIND_TO_CLS: dict[str, Any] = {
    "fact": Fact,
    "source": Source,
    "entity": Entity,
    "relation": Relation,
    "decision": Decision,
    "episode": Episode,
    "observation": Observation,
    "document": Document,
    "claim": Claim,
    "evidence": Evidence,
    "review": Review,
}

EXPORT_FORMAT = "epistemos-events"

# Bound the projected corroboration/contradiction annotation lists so repeated (cross-agent)
# confirm/contradict cannot grow an object's metadata past its cap (B-06). The ledger keeps the
# full history; the object metadata keeps only the most recent N as a convenience projection.
_MAX_ANNOTATIONS = 256


@dataclass(frozen=True, slots=True)
class EngineLimits:
    max_str: int = 4096
    max_uri: int = 2048
    max_text: int = 1_000_000
    max_document_bytes: int = 5 * 1024 * 1024
    max_metadata_bytes: int = 64 * 1024
    max_json_depth: int = 32
    max_graph_nodes: int = 10_000
    max_hops: int = 8
    allowed_doc_mime: frozenset[str] = frozenset(
        {"text/plain", "text/markdown", "application/json", "text/html", "text/csv"}
    )


class Engine:
    def __init__(
        self,
        store: Store,
        *,
        clock: Clock = now_utc,
        retriever: Retriever | None = None,
        limits: EngineLimits | None = None,
        tokenizer: str | Tokenizer = "ascii",
        policy: Policy | None = None,
    ) -> None:
        self.store = store
        self.clock = clock
        self.limits = limits or EngineLimits()
        # Governed-acceptance policy (EPISTEMOS-05): the DECISION to accept a claim as knowledge is
        # delegated to a pluggable policy. Default is local + deterministic, so the engine works
        # standalone; a NOMOS/other PDP adapter can replace it without the core depending on it.
        self.policy: Policy = policy or LocalDefaultPolicy()
        weights = retriever.weights if retriever is not None else None
        # Tokenizer selects how text is split for search. "ascii" (default) is the v0.1/v0.2
        # behaviour; "unicode" (ADR-023) folds diacritics and indexes non-ASCII scripts, using
        # SQLite as the single tokenization authority so the scan and index agree exactly.
        self.tokenizer = get_tokenizer(tokenizer)
        self.legacy = LegacyScanRetriever(weights, self.tokenizer)
        self.retriever = self.legacy  # back-compat attribute
        # A lexical index accelerates TEXT search on the SQLite backend (FTS5). The in-memory
        # backend keeps the O(N) scan (fine at test scale). The index is a rebuildable projection
        # of the authoritative store — never a source of truth.
        self.lexical_index: SqliteFtsIndex | None = None
        self.indexed: IndexedRetriever | None = None
        # A provenance index turns explain()'s per-node ledger scan into a keyed lookup
        # (ADR-022). Like the lexical index it is a rebuildable projection with a scan fallback.
        self.provenance_index: SqliteProvenanceIndex | None = None
        if isinstance(store, SQLiteStore):
            idx = SqliteFtsIndex(store, tokenizer=self.tokenizer)
            self.lexical_index = idx
            self.indexed = IndexedRetriever(idx, weights, self.tokenizer)
            idx.ensure_built(store)  # rebuild once if opening a pre-existing / unindexed DB
            prov = SqliteProvenanceIndex(store)
            self.provenance_index = prov
            prov.ensure_built()

    @classmethod
    def open(
        cls,
        target: str | None = None,
        *,
        clock: Clock = now_utc,
        weights: Weights | None = None,
        limits: EngineLimits | None = None,
        tokenizer: str | Tokenizer = "ascii",
    ) -> Engine:
        """Open an engine over a local file (SQLite) or ``None``/``":memory:"`` (in-memory).

        ``tokenizer="unicode"`` enables diacritic-folding, non-ASCII search (ADR-023); the FTS
        index is rebuilt automatically if the stored tokenizer differs from the requested one.
        """
        return cls(
            open_store(target),
            clock=clock,
            retriever=Retriever(weights),
            limits=limits,
            tokenizer=tokenizer,
        )

    def close(self) -> None:
        self.store.close()

    # ======================================================================
    # validation helpers
    # ======================================================================
    def _now(self) -> str:
        return to_iso(self.clock())

    @overload
    def _str(
        self, value: Any, field: str, *, max_len: int | None = ..., allow_none: Literal[False] = ...
    ) -> str: ...
    @overload
    def _str(
        self, value: Any, field: str, *, max_len: int | None = ..., allow_none: Literal[True]
    ) -> str | None: ...
    def _str(
        self, value: Any, field: str, *, max_len: int | None = None, allow_none: bool = False
    ) -> str | None:
        if value is None:
            if allow_none:
                return None
            raise ValidationError(f"{field} must not be None")
        if not isinstance(value, str):
            raise ValidationError(f"{field} must be a string, got {type(value).__name__}")
        limit = max_len or self.limits.max_str
        if len(value) > limit:
            raise ValidationError(f"{field} exceeds {limit} chars")
        if any(ord(c) < 0x20 and c not in "\t\n\r" for c in value) or "\x00" in value:
            raise ValidationError(f"{field} contains control characters")
        return value

    def _confidence(self, value: Any) -> float:
        try:
            f = float(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"confidence must be numeric: {value!r}") from exc
        if not math.isfinite(f):
            raise ValidationError("confidence must be finite (no NaN/Infinity)")
        if not (0.0 <= f <= 1.0):
            raise ValidationError(f"confidence must be in [0,1], got {f}")
        return f

    def _instant(self, value: Any, field: str) -> Any:
        try:
            parse_instant(value)  # validates; raises ValueError on garbage
        except ValueError as exc:
            raise ValidationError(f"{field}: {exc}") from exc
        return value

    def _metadata(self, meta: Any) -> dict[str, Any]:
        if meta is None:
            return {}
        if not isinstance(meta, dict):
            raise ValidationError("metadata must be a dict")
        blob = canonical_json(meta)  # raises on non-JSON / NaN
        if len(blob.encode("utf-8")) > self.limits.max_metadata_bytes:
            raise ValidationError("metadata exceeds size limit")
        if _json_depth(meta) > self.limits.max_json_depth:
            raise ValidationError("metadata nesting too deep")
        return dict(meta)

    def _open_belief(self, principal: Principal, fact_id: str, *, action: str) -> dict[str, Any]:
        """Load a fact that is still believed, refusing to re-close a closed belief.

        Transaction time is append-only: once the system stopped believing a fact at ``tx_to``,
        nothing may move that instant, or ``as_of(at_tx=T)`` would answer differently depending
        on what happened after T (EPISTEMOS-03, A-12). Supersede the *current* generation.
        """
        old = self._ref_in_scope(principal, fact_id, what="fact")
        if old.get("kind") != "fact":
            raise ValidationError(f"{fact_id} is not a fact")
        if old.get("tx_to") is not None:
            raise ConflictError(
                f"{action} denied: belief in {fact_id} is already closed at {old['tx_to']} "
                f"(status {old.get('status')!r}); transaction time is append-only — "
                "act on the fact that is currently believed"
            )
        return old

    def _ref_in_scope(self, principal: Principal, ref_id: str, *, what: str) -> dict[str, Any]:
        obj = self.store.get_object(ref_id)
        if obj is None:
            raise NotFoundError(f"{what} {ref_id!r} not found")
        if obj.get("tenant") != principal.tenant or obj.get("namespace") != principal.namespace:
            # Never confirm existence across a scope boundary.
            raise NotFoundError(f"{what} {ref_id!r} not found")
        return obj

    # ======================================================================
    # Knowledge Spaces authorization (EPISTEMOS-04) — the read firewall
    # ======================================================================
    def _space_of(self, space_id: str) -> tuple[Visibility, str, str] | None:
        """(visibility, owner, tenant) of a space id, or None if unknown (fail closed)."""
        sp = self.store.get_object(space_id)
        if sp is None or sp.get("kind") != "space":
            return None
        return (resolve_visibility(sp.get("visibility")), sp.get("owner", ""), sp.get("tenant", ""))

    def _is_member(self, space_id: str, agent: str) -> bool:
        """Is ``agent`` an ACTIVE granted member of ``space_id``? Reads projected server-side grant
        state (never a caller-supplied Principal field), so a client cannot claim membership."""
        grant = self.store.get_object(_grant_id(space_id, agent))
        return grant is not None and grant.get("kind") == "grant" and bool(grant.get("active"))

    def _can_read(self, principal: Principal, obj: dict[str, Any]) -> bool:
        """The full read decision: IDENTITY→TENANT→SPACE→CAPABILITY→POLICY (fail closed)."""
        return can_read_object(
            principal, obj, space_of=self._space_of, is_member=self._is_member
        )

    def _readable(
        self, principal: Principal, objs: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter a candidate set to the objects the principal may read — applied BEFORE any
        ranking/scoring so an unauthorized object never influences a result (mission §12)."""
        return [o for o in objs if self._can_read(principal, o)]

    # ======================================================================
    # event emission — the ONLY mutation path
    # ======================================================================
    def _emit(
        self, principal: Principal, op: str, ts: str, payload: dict[str, Any]
    ) -> LedgerRecord:
        event = Event(
            op=op,
            ts=ts,
            tenant=principal.tenant,
            namespace=principal.namespace,
            actor=principal.agent,
            principal=principal.principal,
            payload=payload,
        )
        record = self.store.append(event)
        self._apply(record)
        return record

    def _persist(self, obj: dict[str, Any]) -> None:
        """Write an object to the projection AND the lexical index. Index failures are isolated
        (marked DEGRADED) so the authoritative core write still commits (ADR-019)."""
        store = self.store
        store.put_object(obj)
        if self.lexical_index is not None:
            try:
                self.lexical_index.reindex(obj)
            except Exception:  # noqa: BLE001 - the core write must never depend on the index
                self.lexical_index.mark_degraded()

    # -- scope authority ----------------------------------------------------
    # The sealed record header is the ONLY authority for (tenant, namespace). Payload-level
    # scope fields are attacker-controlled on the import path: a hand-built export whose chain
    # is internally valid could otherwise project objects into any tenant (EPISTEMOS-03, A-01).
    def _guard_payload_scope(self, record: LedgerRecord, obj: dict[str, Any]) -> None:
        if obj.get("tenant") != record.tenant or obj.get("namespace") != record.namespace:
            raise IntegrityError(
                f"ledger seq {record.seq}: payload scope "
                f"{obj.get('tenant')!r}/{obj.get('namespace')!r} does not match the sealed "
                f"record scope {record.tenant!r}/{record.namespace!r}"
            )

    def _in_record_scope(self, record: LedgerRecord, obj_id: str, *, what: str) -> dict[str, Any]:
        """Load an object a record mutates, refusing to cross the record's own scope."""
        obj = self.store.get_object(obj_id)
        if obj is None:
            raise IntegrityError(f"projection: missing {what} {obj_id} for {record.op}")
        self._guard_payload_scope(record, obj)
        return obj

    def _apply(self, record: LedgerRecord) -> None:
        """Project a sealed ledger record onto queryable state. Shared by live + import."""
        op = record.op
        p = dict(record.payload)
        if self.provenance_index is not None:
            self.provenance_index.record(record.seq, p)
        if op in _PUT_OPS:
            self._guard_payload_scope(record, p)
            self._persist(p)
        elif op in (Op.FACT_SUPERSEDED, Op.FACT_RETRACTED):
            obj = self._in_record_scope(record, p["fact_id"], what="fact")
            # Append-only transaction time: the FIRST close stands. A ledger written before
            # A-12 was fixed — or a crafted import — cannot move tx_to forward and thereby
            # change what the system is said to have believed in the past.
            if obj.get("tx_to") is None:
                obj["tx_to"] = p["tx_to"]
                obj["status"] = p["status"]
                self._persist(obj)
        elif op == Op.FACT_CONFIRMED:
            obj = self._in_record_scope(record, p["fact_id"], what="fact")
            obj["confidence"] = p["confidence"]
            corr = list(obj.get("metadata", {}).get("corroborations", []))
            corr.append({"source": p.get("source"), "ts": record.ts})
            # Bound the projected list so repeated cross-agent confirms cannot grow an object's
            # metadata without limit (B-06). The full history stays in the ledger; this is only a
            # convenience projection, so keeping the most recent N is lossless for the truth.
            obj.setdefault("metadata", {})["corroborations"] = corr[-_MAX_ANNOTATIONS:]
            self._persist(obj)
        elif op == Op.CONTRADICTION_RECORDED:
            self._apply_contradiction(record, p, record.ts)
        elif op == Op.ENTITY_MERGED:
            self._apply_merge(record, p, record.ts)
        elif op == Op.ENTITY_SPLIT:
            self._apply_split(record, p)
        elif op == Op.SPACE_CREATED:
            self._guard_payload_scope(record, p)
            self._persist(p)  # a space is a store object (kind="space")
        elif op == Op.CAPABILITY_GRANTED:
            self._guard_payload_scope(record, p)
            self._persist(p)  # grant object (kind="grant"), active=True in payload
        elif op == Op.CAPABILITY_REVOKED:
            grant = self.store.get_object(p["grant_id"])
            if grant is not None:
                self._guard_payload_scope(record, grant)
                grant["active"] = False
                grant["revoked_at"] = record.ts
                self._persist(grant)
        elif op in (Op.KNOWLEDGE_SHARED, Op.KNOWLEDGE_PROMOTED):
            self._apply_placement(record, p)
        elif op in (Op.CLAIM_ASSERTED, Op.EVIDENCE_RECORDED, Op.CLAIM_REVIEWED):
            self._guard_payload_scope(record, p)
            self._persist(p)  # claim / evidence / review objects
        elif op in (Op.CLAIM_RETRACTED, Op.CLAIM_SUPERSEDED):
            obj = self._in_record_scope(record, p["claim_id"], what="claim")
            if obj.get("status") == ClaimStatus.OPEN.value:  # append-only: first close stands
                obj["status"] = p["status"]
                obj["tx_to"] = p.get("tx_to")
                self._persist(obj)
        elif op == Op.EVIDENCE_ATTACHED:
            self._apply_evidence_attached(record, p)
        elif op in (Op.CLAIM_ACCEPTED, Op.CLAIM_REJECTED):
            claim = self._in_record_scope(record, p["claim_id"], what="claim")
            # governance is recorded on the claim as a marker; belief is still DERIVED from it plus
            # reviews (never a bare boolean). The full decision stays in the ledger.
            gov = {"actor": record.actor, "at": record.ts, "reason": p.get("reason")}
            claim.setdefault("metadata", {})[
                "accepted" if op == Op.CLAIM_ACCEPTED else "rejected"
            ] = gov
            self._persist(claim)
        else:  # pragma: no cover - defensive
            raise IntegrityError(f"unknown ledger op {op!r}")

    def _apply_evidence_attached(self, record: LedgerRecord, p: dict[str, Any]) -> None:
        """Record a typed evidence->claim link on the claim (space-safe: the link stores only the
        evidence id + relation; reading the evidence content is authorized separately)."""
        claim = self._in_record_scope(record, p["claim_id"], what="claim")
        links = list(claim.get("metadata", {}).get("evidence_links", []))
        entry = {"evidence": p["evidence_id"], "relation": p["relation"]}
        if entry not in links:
            links.append(entry)
        claim.setdefault("metadata", {})["evidence_links"] = links[-_MAX_ANNOTATIONS:]
        self._persist(claim)

    def _apply_placement(self, record: LedgerRecord, p: dict[str, Any]) -> None:
        """Append a space placement to an object (share/promote). Append-only: the object's whole
        visibility history is reconstructable from the ledger; this only widens ``spaces``."""
        obj = self._in_record_scope(record, p["object_id"], what="object")
        placed = list(obj.get("spaces", ()))
        dest = p["destination_space"]
        if dest not in placed:
            placed.append(dest)
        obj["spaces"] = placed
        self._persist(obj)

    def _apply_contradiction(self, record: LedgerRecord, p: dict[str, Any], ts: str) -> None:
        for a, b in ((p["fact_id"], p["other_id"]), (p["other_id"], p["fact_id"])):
            obj = self._in_record_scope(record, a, what="fact")
            contradicts = list(obj.get("contradicts", []))
            if b not in contradicts:
                contradicts.append(b)
            obj["contradicts"] = contradicts
            if p.get("note"):
                notes = list(obj.get("metadata", {}).get("contradiction_notes", []))
                notes.append({"other": b, "note": p["note"], "ts": ts})
                obj.setdefault("metadata", {})["contradiction_notes"] = notes[-_MAX_ANNOTATIONS:]
            self._persist(obj)

    def _apply_merge(self, record: LedgerRecord, p: dict[str, Any], ts: str) -> None:
        canonical = self._in_record_scope(record, p["canonical"], what="canonical entity")
        aliases = list(canonical.get("aliases", []))
        for a in p.get("aliases", []):
            if a not in aliases:
                aliases.append(a)
        canonical["aliases"] = aliases
        merged = list(canonical.get("metadata", {}).get("merged_from", []))
        merged.extend(d for d in p["duplicates"] if d not in merged)
        canonical.setdefault("metadata", {})["merged_from"] = merged
        self._persist(canonical)
        for dup_id in p["duplicates"]:
            dup = self._in_record_scope(record, dup_id, what="duplicate entity")
            dup.setdefault("metadata", {})["merged_into"] = p["canonical"]
            dup["metadata"]["merged_at"] = ts
            self._persist(dup)

    def _apply_split(self, record: LedgerRecord, p: dict[str, Any]) -> None:
        origin = self._in_record_scope(record, p["entity"], what="entity")
        into_ids = [e["id"] for e in p["into"]]
        origin.setdefault("metadata", {})["split_into"] = into_ids
        self._persist(origin)
        for ent in p["into"]:
            self._guard_payload_scope(record, ent)
            self._persist(ent)

    def _envelope(
        self, principal: Principal, kind: str, obj_id: str, ts: str, **extra: Any
    ) -> dict[str, Any]:
        base = {
            "id": obj_id,
            "kind": kind,
            "tenant": principal.tenant,
            "namespace": principal.namespace,
            "owner": principal.agent,
            "created_at": ts,
            "schema_version": SCHEMA_VERSION,
        }
        base.update(extra)
        return base

    # ======================================================================
    # sources / observations / documents (ingestion — content is inert data)
    # ======================================================================
    def add_source(
        self,
        principal: Principal,
        *,
        uri: str,
        source_kind: str = "unknown",
        trust: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> Source:
        principal = _require_principal(principal)
        principal.require("ingest")
        uri = self._str(uri, "uri", max_len=self.limits.max_uri)
        # NB: EPISTEMOS never dereferences this URI. It is an identifier, not a fetch target.
        source_kind = self._str(source_kind, "source_kind", max_len=64)
        trust = self._confidence(trust)  # trust shares the [0,1] finite constraint
        ts = self._now()
        src = Source(
            **self._envelope(principal, "source", new_id("src"), ts),
            uri=uri,
            source_kind=source_kind,
            trust=trust,
            metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.SOURCE_ADDED, ts, src.to_dict())
        return src

    def observe(
        self,
        principal: Principal,
        *,
        text: str,
        source: str | None = None,
        session: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Observation:
        principal = _require_principal(principal)
        principal.require("ingest")
        text = self._str(text, "text", max_len=self.limits.max_text)
        if source is not None:
            self._ref_in_scope(principal, source, what="source")
        if session is not None:
            session = self._str(session, "session", max_len=128)
        ts = self._now()
        obs = Observation(
            **self._envelope(
                principal, "observation", new_id("obs"), ts, source=source, source_hash=None
            ),
            text=text,
            session=session,
            metadata=self._metadata(metadata),
        )
        obj = obs.to_dict()
        obj["source_hash"] = hash_obj({"text": text})
        with self.store.atomic():
            self._emit(principal, Op.OBSERVATION_RECORDED, ts, obj)
        return Observation.from_dict(obj)

    def ingest_document(
        self,
        principal: Principal,
        *,
        title: str,
        text: str,
        mime: str = "text/plain",
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        principal = _require_principal(principal)
        principal.require("ingest")
        title = self._str(title, "title", max_len=self.limits.max_str)
        if not isinstance(text, str):
            raise ValidationError("document text must be a string")
        if len(text.encode("utf-8")) > self.limits.max_document_bytes:
            raise ValidationError("document exceeds size limit")
        mime = self._str(mime, "mime", max_len=128)
        if mime not in self.limits.allowed_doc_mime:
            raise ValidationError(f"unsupported mime {mime!r}")
        if source is not None:
            self._ref_in_scope(principal, source, what="source")
        ts = self._now()
        doc = Document(
            **self._envelope(principal, "document", new_id("doc"), ts, source=source),
            title=title,
            text=text,
            mime=mime,
            metadata=self._metadata(metadata),
        )
        obj = doc.to_dict()
        obj["source_hash"] = hash_obj({"title": title, "text": text, "mime": mime})
        with self.store.atomic():
            self._emit(principal, Op.DOCUMENT_INGESTED, ts, obj)
        return Document.from_dict(obj)

    # ======================================================================
    # facts (bitemporal)
    # ======================================================================
    def assert_fact(
        self,
        principal: Principal,
        *,
        subject: str,
        predicate: str,
        object: str | None = None,  # noqa: A002
        valid_from: str | None = None,
        valid_to: str | None = None,
        source: str | None = None,
        confidence: float = 1.0,
        derived_from: Iterable[str] | None = None,
        memory_class: str = MemoryClass.SEMANTIC.value,
        metadata: dict[str, Any] | None = None,
    ) -> Fact:
        principal = _require_principal(principal)
        principal.require("assert")
        subject = self._str(subject, "subject")
        predicate = self._str(predicate, "predicate")
        object = self._str(object, "object", allow_none=True)  # noqa: A002
        self._instant(valid_from, "valid_from")
        self._instant(valid_to, "valid_to")
        confidence = self._confidence(confidence)
        derived = tuple(derived_from or ())
        for ref in derived:
            self._ref_in_scope(principal, ref, what="derived_from")
        if source is not None:
            self._ref_in_scope(principal, source, what="source")
        MemoryClass(memory_class)  # validates the enum
        ts = self._now()
        fact = Fact(
            **self._envelope(
                principal,
                "fact",
                new_id("fact"),
                ts,
                source=source,
                confidence=confidence,
                derived_from=derived,
            ),
            subject=subject,
            predicate=predicate,
            object=object,
            valid_from=valid_from,
            valid_to=valid_to,
            tx_from=ts,
            tx_to=None,
            status=BeliefStatus.ASSERTED.value,
            memory_class=memory_class,
            metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.FACT_ASSERTED, ts, fact.to_dict())
        return fact

    def supersede(
        self,
        principal: Principal,
        fact_id: str,
        *,
        new: dict[str, Any],
        reason: str | None = None,
        source: str | None = None,
    ) -> Fact:
        """Replace the *value* of a fact. Old belief is closed (not deleted); the new
        fact links back via ``supersedes``. Use for "we said X, it is actually Y"."""
        principal = _require_principal(principal)
        principal.require("supersede")
        old = self._open_belief(principal, fact_id, action="supersede")
        principal.guard_owner(old.get("owner", principal.agent), action="supersede")
        if reason is not None:
            reason = self._str(reason, "reason", max_len=self.limits.max_str)
        if source is not None:
            self._ref_in_scope(principal, source, what="source")
        ts = self._now()
        new_obj = Fact(
            **self._envelope(
                principal,
                "fact",
                new_id("fact"),
                ts,
                source=source if source is not None else old.get("source"),
                confidence=self._confidence(new.get("confidence", old.get("confidence", 1.0))),
                supersedes=(fact_id,),
                derived_from=tuple(old.get("derived_from", ())),
                # Inherit the superseded fact's owner AND space placement so a correction preserves
                # the audience: the replacement stays visible to exactly whoever could see the
                # original (the ledger still records who performed the supersede). Without this, an
                # admin correcting another agent's fact would make the current value private to the
                # admin (EPISTEMOS-04).
                owner=old.get("owner", principal.agent),
                spaces=tuple(old.get("spaces", ())),
            ),
            subject=self._str(new.get("subject", old["subject"]), "subject"),
            predicate=self._str(new.get("predicate", old["predicate"]), "predicate"),
            object=self._str(new.get("object"), "object", allow_none=True),
            valid_from=self._instant(new.get("valid_from", ts), "valid_from"),
            valid_to=self._instant(new.get("valid_to"), "valid_to"),
            tx_from=ts,
            tx_to=None,
            status=BeliefStatus.ASSERTED.value,
            memory_class=old.get("memory_class", MemoryClass.SEMANTIC.value),
            metadata=self._metadata(new.get("metadata")),
        )
        with self.store.atomic():
            self._emit(
                principal,
                Op.FACT_SUPERSEDED,
                ts,
                {"fact_id": fact_id, "tx_to": ts, "status": BeliefStatus.SUPERSEDED.value,
                 "reason": reason, "replacement": new_obj.id},
            )
            self._emit(principal, Op.FACT_ASSERTED, ts, new_obj.to_dict())
        return new_obj

    def correct_validity(
        self,
        principal: Principal,
        fact_id: str,
        *,
        valid_from: Any = _UNSET,
        valid_to: Any = _UNSET,
        reason: str | None = None,
        source: str | None = None,
    ) -> Fact:
        """Bitemporal correction of a fact's *world-time* interval, keeping the value.

        Models "the relation ended / began at a different time" (e.g. "Alice left X on
        2026-02-01") without destroying what the system believed before the correction.
        """
        principal = _require_principal(principal)
        principal.require("supersede")
        old = self._open_belief(principal, fact_id, action="correct_validity")
        principal.guard_owner(old.get("owner", principal.agent), action="correct_validity")
        def _pick(value: Any, current: Any, field: str) -> Any:
            return current if value is _UNSET else self._instant(value, field)

        new_vf = _pick(valid_from, old.get("valid_from"), "valid_from")
        new_vt = _pick(valid_to, old.get("valid_to"), "valid_to")
        if reason is not None:
            reason = self._str(reason, "reason", max_len=self.limits.max_str)
        if source is not None:
            self._ref_in_scope(principal, source, what="source")
        ts = self._now()
        corrected = Fact(
            **self._envelope(
                principal,
                "fact",
                new_id("fact"),
                ts,
                source=source if source is not None else old.get("source"),
                confidence=old.get("confidence", 1.0),
                supersedes=(fact_id,),
                derived_from=tuple(old.get("derived_from", ())),
                owner=old.get("owner", principal.agent),  # preserve audience across correction
                spaces=tuple(old.get("spaces", ())),
            ),
            subject=old["subject"],
            predicate=old["predicate"],
            object=old.get("object"),
            valid_from=new_vf,
            valid_to=new_vt,
            tx_from=ts,
            tx_to=None,
            status=BeliefStatus.ASSERTED.value,
            memory_class=old.get("memory_class", MemoryClass.SEMANTIC.value),
            metadata=(
                {"correction_of": fact_id, "reason": reason}
                if reason
                else {"correction_of": fact_id}
            ),
        )
        with self.store.atomic():
            self._emit(
                principal,
                Op.FACT_SUPERSEDED,
                ts,
                {"fact_id": fact_id, "tx_to": ts, "status": BeliefStatus.SUPERSEDED.value,
                 "reason": reason, "replacement": corrected.id},
            )
            self._emit(principal, Op.FACT_ASSERTED, ts, corrected.to_dict())
        return corrected

    def end_fact(
        self,
        principal: Principal,
        fact_id: str,
        *,
        valid_to: str,
        reason: str | None = None,
        source: str | None = None,
    ) -> Fact:
        """Convenience: mark a fact's world-validity as ending at ``valid_to``."""
        return self.correct_validity(
            principal, fact_id, valid_to=valid_to, reason=reason, source=source
        )

    def retract(
        self, principal: Principal, fact_id: str, *, reason: str | None = None
    ) -> None:
        """Withdraw belief entirely (no replacement). History is preserved."""
        principal = _require_principal(principal)
        principal.require("retract")
        old = self._open_belief(principal, fact_id, action="retract")
        principal.guard_owner(old.get("owner", principal.agent), action="retract")
        if reason is not None:
            reason = self._str(reason, "reason", max_len=self.limits.max_str)
        ts = self._now()
        with self.store.atomic():
            self._emit(
                principal,
                Op.FACT_RETRACTED,
                ts,
                {"fact_id": fact_id, "tx_to": ts, "status": BeliefStatus.RETRACTED.value,
                 "reason": reason},
            )

    def contradict(
        self, principal: Principal, fact_id: str, *, by: str, note: str | None = None
    ) -> None:
        """Record that two facts contradict each other. Neither is deleted or unbelieved."""
        principal = _require_principal(principal)
        principal.require("contradict")
        a = self._ref_in_scope(principal, fact_id, what="fact")
        b = self._ref_in_scope(principal, by, what="fact")
        # You can only dispute facts you can see: an unauthorized fact is reported as not-found
        # (no existence oracle, and no blind mutation of an object outside your space).
        if not self._can_read(principal, a) or not self._can_read(principal, b):
            raise NotFoundError("fact not found")
        if fact_id == by:
            raise ValidationError("a fact cannot contradict itself")
        if note is not None:
            note = self._str(note, "note", max_len=self.limits.max_str)
        ts = self._now()
        with self.store.atomic():
            self._emit(
                principal,
                Op.CONTRADICTION_RECORDED,
                ts,
                {"fact_id": fact_id, "other_id": by, "note": note},
            )

    def confirm(
        self, principal: Principal, fact_id: str, *, source: str, delta_confidence: float = 0.0
    ) -> Fact:
        """Add corroborating evidence to a fact, optionally raising its confidence."""
        principal = _require_principal(principal)
        principal.require("confirm")
        obj = self._ref_in_scope(principal, fact_id, what="fact")
        if obj.get("kind") != "fact":
            raise ValidationError(f"{fact_id} is not a fact")
        if not self._can_read(principal, obj):  # only corroborate a fact you can see
            raise NotFoundError(f"fact {fact_id!r} not found")
        self._ref_in_scope(principal, source, what="source")
        try:
            delta = float(delta_confidence)
        except (TypeError, ValueError) as exc:
            raise ValidationError("delta_confidence must be numeric") from exc
        if not math.isfinite(delta):
            raise ValidationError("delta_confidence must be finite")
        # confirm() is *corroboration*: it may only raise confidence. A negative delta would turn
        # this additive, cross-agent primitive into a way to lower a rival's confidence and flip
        # which fact is "current" (EPISTEMOS-03, B-03). To weaken belief, contradict or supersede.
        if delta < 0.0:
            raise ValidationError(
                "delta_confidence must be non-negative (confirm only corroborates)"
            )
        new_conf = max(0.0, min(1.0, float(obj.get("confidence", 1.0)) + delta))
        ts = self._now()
        with self.store.atomic():
            self._emit(
                principal,
                Op.FACT_CONFIRMED,
                ts,
                {"fact_id": fact_id, "source": source, "confidence": new_conf},
            )
        updated = self.store.get_object(fact_id)
        assert updated is not None
        return Fact.from_dict(updated)

    # ======================================================================
    # temporal queries
    # ======================================================================
    def _trust_lookup(self) -> Any:
        """A cached fact -> source-trust function for authority-aware current resolution."""
        cache: dict[str, float] = {}

        def trust_of(fact: dict[str, Any]) -> float:
            src_id = fact.get("source")
            if not src_id:
                return 0.0
            if src_id not in cache:
                src = self.store.get_object(src_id)
                # a source pointer that dangles outside the fact's own scope carries no authority
                # (B-06): never let a cross-tenant source's trust rank a fact as "current".
                if (
                    src is not None
                    and src.get("tenant") == fact.get("tenant")
                    and src.get("namespace") == fact.get("namespace")
                ):
                    cache[src_id] = float(src.get("trust", 0.0))
                else:
                    cache[src_id] = 0.0
            return cache[src_id]

        return trust_of

    def current_fact(
        self, principal: Principal, *, subject: str, predicate: str, at_valid: Any = None
    ) -> Fact | None:
        principal = _require_principal(principal)
        principal.require("read")
        # "current" is anchored to *now* on the valid-time axis unless a moment is given. On the
        # transaction axis, "believed now" means the belief interval is still OPEN (tx_to is None)
        # — a clock-independent definition. Anchoring the tx axis on a clock instant made current()
        # depend on clock skew: a clock ahead of the data, or data imported from another clock,
        # could make a genuinely-open belief look "not yet / no longer believed" (T-05).
        anchor = at_valid if at_valid is not None else self._now()
        self._instant(anchor, "at_valid")
        facts = self._readable(principal, self.store.facts(
            principal.tenant, principal.namespace, subject=subject, predicate=predicate
        ))
        best = resolve_current(facts, at_valid=anchor, at_tx=None, trust_of=self._trust_lookup())
        return Fact.from_dict(best) if best is not None else None

    def current(
        self, principal: Principal, *, subject: str, predicate: str, at_valid: Any = None
    ) -> str | None:
        f = self.current_fact(principal, subject=subject, predicate=predicate, at_valid=at_valid)
        return f.object if f is not None else None

    def as_of(
        self,
        principal: Principal,
        at_valid: Any,
        *,
        subject: str,
        predicate: str,
        at_tx: Any = None,
    ) -> str | None:
        """Value believed (as of transaction time ``at_tx``, default now) about world-time
        ``at_valid``. Answers "what did the system know at T?"."""
        principal = _require_principal(principal)
        principal.require("read")
        self._instant(at_valid, "at_valid")
        if at_tx is not None:
            self._instant(at_tx, "at_tx")
        facts = self._readable(principal, self.store.facts(
            principal.tenant, principal.namespace, subject=subject, predicate=predicate
        ))
        best = resolve_current(facts, at_valid=at_valid, at_tx=at_tx, trust_of=self._trust_lookup())
        return best.get("object") if best is not None else None

    def facts_for(
        self,
        principal: Principal,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,  # noqa: A002
        believed_only: bool = False,
    ) -> list[Fact]:
        principal = _require_principal(principal)
        principal.require("read")
        rows = self._readable(principal, self.store.facts(
            principal.tenant, principal.namespace,
            subject=subject, predicate=predicate, object=object,
        ))
        if believed_only:
            rows = [r for r in rows if r.get("tx_to") is None]
        return [Fact.from_dict(r) for r in rows]

    def timeline(
        self, principal: Principal, *, subject: str, predicate: str | None = None
    ) -> list[dict[str, Any]]:
        """Full history for a subject (+optional predicate): every fact, its temporal
        state and a provenance summary, ordered by assertion then validity."""
        principal = _require_principal(principal)
        principal.require("read")
        rows = self._readable(
            principal, self.store.facts(principal.tenant, principal.namespace, subject=subject)
        )
        if predicate is not None:
            rows = [r for r in rows if r.get("predicate") == predicate]
        # Order by real instants, not lexicographically over ISO strings: mixed UTC-offset forms
        # (e.g. "...+05:00" vs "...Z") sort wrong as text (T-07). Undated facts sort first.
        _floor = datetime.min.replace(tzinfo=UTC)
        rows.sort(key=lambda r: (
            parse_instant(r.get("tx_from")) or _floor,
            parse_instant(r.get("valid_from")) or _floor,
        ))
        out = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "statement": {
                        "subject": r["subject"],
                        "predicate": r["predicate"],
                        "object": r.get("object"),
                    },
                    "valid_from": r.get("valid_from"),
                    "valid_to": r.get("valid_to"),
                    "tx_from": r.get("tx_from"),
                    "tx_to": r.get("tx_to"),
                    "status": r.get("status"),
                    "believed": r.get("tx_to") is None,
                    "confidence": r.get("confidence"),
                    "source": r.get("source"),
                    "supersedes": list(r.get("supersedes", [])),
                    "contradicts": list(r.get("contradicts", [])),
                }
            )
        return out

    # ======================================================================
    # graph
    # ======================================================================
    def add_entity(
        self,
        principal: Principal,
        *,
        name: str,
        entity_type: str = "thing",
        aliases: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Entity:
        principal = _require_principal(principal)
        principal.require("assert")
        name = self._str(name, "name")
        entity_type = self._str(entity_type, "entity_type", max_len=128)
        alias_tuple = tuple(self._str(a, "alias") for a in (aliases or ()))
        ts = self._now()
        ent = Entity(
            **self._envelope(principal, "entity", new_id("ent"), ts),
            name=name,
            entity_type=entity_type,
            aliases=alias_tuple,
            metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.ENTITY_ADDED, ts, ent.to_dict())
        return ent

    def add_relation(
        self,
        principal: Principal,
        *,
        source_entity: str,
        target_entity: str,
        rel_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Relation:
        principal = _require_principal(principal)
        principal.require("assert")
        self._ref_in_scope(principal, source_entity, what="entity")
        self._ref_in_scope(principal, target_entity, what="entity")
        rel_type = self._str(rel_type, "rel_type", max_len=128)
        ts = self._now()
        rel = Relation(
            **self._envelope(principal, "relation", new_id("rel"), ts),
            source_entity=source_entity,
            target_entity=target_entity,
            rel_type=rel_type,
            metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.RELATION_ADDED, ts, rel.to_dict())
        return rel

    def neighbors(
        self,
        principal: Principal,
        entity_id: str,
        *,
        direction: str = "both",
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]:
        principal = _require_principal(principal)
        principal.require("read")
        start = self._ref_in_scope(principal, entity_id, what="entity")
        if not self._can_read(principal, start):
            raise NotFoundError(f"entity {entity_id!r} not found")
        out = []
        if direction in ("out", "both"):
            out += self.store.relations(
                principal.tenant, principal.namespace,
                source_entity=entity_id, rel_type=rel_type,
            )
        if direction in ("in", "both"):
            out += self.store.relations(
                principal.tenant, principal.namespace,
                target_entity=entity_id, rel_type=rel_type,
            )
        # Graph space isolation (§19): return an edge only if the relation AND its far endpoint are
        # readable — so a private node's existence cannot be inferred through a readable public one.
        result = []
        for rel in out:
            if not self._can_read(principal, rel):
                continue
            other = (rel["target_entity"] if rel["source_entity"] == entity_id
                     else rel["source_entity"])
            other_obj = self.store.get_object(other)
            if other_obj is not None and not self._can_read(principal, other_obj):
                continue
            result.append(rel)
        return result

    def query_graph(
        self,
        principal: Principal,
        start: str,
        *,
        max_hops: int = 2,
        rel_type: str | None = None,
        direction: str = "both",
    ) -> dict[str, Any]:
        """Bounded BFS traversal. ``max_hops`` and a node budget cap expansion so a
        pathological graph cannot cause unbounded work (graph-expansion DoS defense)."""
        principal = _require_principal(principal)
        principal.require("read")
        self._ref_in_scope(principal, start, what="entity")
        hops = min(int(max_hops), self.limits.max_hops)
        if hops < 0:
            raise ValidationError("max_hops must be >= 0")
        visited: set[str] = {start}
        edges: list[dict[str, Any]] = []
        frontier = [start]
        for _ in range(hops):
            next_frontier: list[str] = []
            for node in frontier:
                for rel in self.neighbors(principal, node, direction=direction, rel_type=rel_type):
                    edges.append(
                        {
                            "source": rel["source_entity"],
                            "target": rel["target_entity"],
                            "rel_type": rel["rel_type"],
                            "id": rel["id"],
                        }
                    )
                    for nxt in (rel["source_entity"], rel["target_entity"]):
                        if nxt not in visited:
                            if len(visited) >= self.limits.max_graph_nodes:
                                return {"start": start, "nodes": sorted(visited),
                                        "edges": _dedup_edges(edges), "truncated": True}
                            visited.add(nxt)
                            next_frontier.append(nxt)
            frontier = next_frontier
            if not frontier:
                break
        return {"start": start, "nodes": sorted(visited), "edges": _dedup_edges(edges),
                "truncated": False}

    def merge_entities(
        self,
        principal: Principal,
        *,
        canonical: str,
        duplicates: Iterable[str],
        aliases: Iterable[str] | None = None,
    ) -> Entity:
        """Explicit, traceable entity resolution. Duplicates are annotated
        ``merged_into`` (kept, not deleted); the merge is a ledger event."""
        principal = _require_principal(principal)
        principal.require("assert")
        canon = self._ref_in_scope(principal, canonical, what="entity")
        # merge rewrites the canonical entity (aliases/metadata) in place, so it is a clobber, not
        # an additive write — same owner guard as supersede (EPISTEMOS-03, B-04).
        principal.guard_owner(canon.get("owner", principal.agent), action="merge_entities")
        dup_ids = [self._str(d, "duplicate") for d in duplicates]
        if not dup_ids:
            raise ValidationError("merge requires at least one duplicate")
        alias_list = list(canon.get("aliases", []))
        for d in dup_ids:
            dup = self._ref_in_scope(principal, d, what="entity")
            if d == canonical:
                raise ValidationError("cannot merge an entity into itself")
            alias_list.append(dup["name"])
        for a in aliases or ():
            alias_list.append(self._str(a, "alias"))
        ts = self._now()
        with self.store.atomic():
            self._emit(
                principal,
                Op.ENTITY_MERGED,
                ts,
                {"canonical": canonical, "duplicates": dup_ids,
                 "aliases": sorted(set(alias_list))},
            )
        updated = self.store.get_object(canonical)
        assert updated is not None
        return Entity.from_dict(updated)

    def split_entity(
        self,
        principal: Principal,
        entity_id: str,
        *,
        into: list[dict[str, Any]],
    ) -> list[Entity]:
        """Reverse of merge: create new distinct entities from one, keeping lineage."""
        principal = _require_principal(principal)
        principal.require("assert")
        origin = self._ref_in_scope(principal, entity_id, what="entity")
        # split annotates the origin entity (split_into) in place — clobber, so owner-guarded.
        principal.guard_owner(origin.get("owner", principal.agent), action="split_entity")
        if not into:
            raise ValidationError("split requires at least one target entity spec")
        ts = self._now()
        new_entities = []
        for spec in into:
            ent = Entity(
                **self._envelope(principal, "entity", new_id("ent"), ts),
                name=self._str(spec.get("name"), "name"),
                entity_type=self._str(spec.get("entity_type", "thing"), "entity_type", max_len=128),
                aliases=tuple(self._str(a, "alias") for a in spec.get("aliases", ())),
                metadata={"split_from": entity_id},
            )
            new_entities.append(ent)
        with self.store.atomic():
            self._emit(
                principal,
                Op.ENTITY_SPLIT,
                ts,
                {"entity": entity_id, "into": [e.to_dict() for e in new_entities]},
            )
        return new_entities

    # ======================================================================
    # decisions & episodic memory
    # ======================================================================
    def record_decision(
        self,
        principal: Principal,
        *,
        statement: str,
        evidence: Iterable[str] | None = None,
        alternatives: Iterable[str] | None = None,
        outcome: str | None = None,
        reversible: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Decision:
        principal = _require_principal(principal)
        principal.require("decide")
        statement = self._str(statement, "statement", max_len=self.limits.max_text)
        ev = tuple(evidence or ())
        for ev_id in ev:
            self._ref_in_scope(principal, ev_id, what="evidence")  # lineage must resolve
        alts = tuple(
            self._str(a, "alternative", max_len=self.limits.max_str) for a in (alternatives or ())
        )
        if outcome is not None:
            outcome = self._str(outcome, "outcome", max_len=self.limits.max_str)
        ts = self._now()
        dec = Decision(
            **self._envelope(principal, "decision", new_id("dec"), ts, derived_from=ev),
            statement=statement,
            evidence=ev,
            alternatives=alts,
            outcome=outcome,
            reversible=bool(reversible),
            metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.DECISION_RECORDED, ts, dec.to_dict())
        return dec

    def remember(
        self,
        principal: Principal,
        *,
        summary: str,
        occurred_at: str | None = None,
        session: str | None = None,
        facts: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Episode:
        principal = _require_principal(principal)
        principal.require("ingest")
        summary = self._str(summary, "summary", max_len=self.limits.max_text)
        occurred = occurred_at if occurred_at is not None else self._now()
        self._instant(occurred, "occurred_at")
        if session is not None:
            session = self._str(session, "session", max_len=128)
        fact_ids = tuple(facts or ())
        for fid in fact_ids:
            self._ref_in_scope(principal, fid, what="fact")
        ts = self._now()
        ep = Episode(
            **self._envelope(principal, "episode", new_id("ep"), ts),
            summary=summary,
            occurred_at=occurred,
            session=session,
            facts=fact_ids,
            metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.EPISODE_RECORDED, ts, ep.to_dict())
        return ep

    def recall(
        self,
        principal: Principal,
        *,
        memory_class: str | None = None,
        session: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query memory by taxonomy class and/or session (mission §12)."""
        principal = _require_principal(principal)
        principal.require("read")
        if memory_class is not None:
            MemoryClass(memory_class)
        out: list[dict[str, Any]] = []
        for obj in self.store.objects(principal.tenant, principal.namespace):
            if obj.get("kind") in ("space", "grant"):
                continue  # control-plane objects are not recallable knowledge
            if not self._can_read(principal, obj):  # space firewall before any listing
                continue
            if memory_class is not None:
                if obj.get("kind") == "episode" and memory_class == MemoryClass.EPISODIC.value:
                    pass
                elif obj.get("memory_class") != memory_class:
                    continue
            if session is not None and obj.get("session") != session:
                continue
            out.append(obj)
        out.sort(key=lambda o: str(o.get("created_at")), reverse=True)
        return out[:limit]

    # ======================================================================
    # Knowledge Spaces: create / grant / share / promote (EPISTEMOS-04)
    # ======================================================================
    def create_space(
        self,
        principal: Principal,
        *,
        name: str,
        visibility: str | Visibility = "TEAM",
        kind: str | None = None,
        policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeSpace:
        """Create a visibility container the caller owns. Fail-closed: an unknown visibility raises;
        creating a space does not grant anyone (including the owner) any capability elsewhere."""
        principal = _require_principal(principal)
        principal.require("space.create")
        name = self._str(name, "name", max_len=self.limits.max_str)
        vis = resolve_visibility(visibility)
        ts = self._now()
        space = KnowledgeSpace(
            id=new_id("spc"),
            tenant=principal.tenant,
            name=name,
            kind=(kind or vis.name),
            visibility=vis,
            owner=principal.agent,
            created_at=ts,
            policy=self._metadata(policy),
            metadata={**self._metadata(metadata), "namespace": principal.namespace},
        )
        with self.store.atomic():
            self._emit(principal, Op.SPACE_CREATED, ts, space.to_dict())
        return space

    def get_space(self, principal: Principal, space_id: str) -> KnowledgeSpace | None:
        principal = _require_principal(principal)
        principal.require("space.read")
        sp = self.store.get_object(space_id)
        if sp is None or sp.get("kind") != "space" or sp.get("tenant") != principal.tenant:
            return None
        return KnowledgeSpace.from_dict(sp)

    def _load_space(self, principal: Principal, space_id: str) -> dict[str, Any]:
        sp = self.store.get_object(space_id)
        if sp is None or sp.get("kind") != "space" or sp.get("tenant") != principal.tenant:
            raise NotFoundError(f"space {space_id!r} not found")
        return sp

    def grant_capability(
        self,
        principal: Principal,
        *,
        space_id: str,
        agent: str,
        capabilities: Iterable[str] = ("knowledge.read",),
    ) -> None:
        """Grant ``agent`` membership (capabilities) on a space the caller manages. Server-side:
        the grant is a ledger event projected into authoritative state, never a client claim."""
        principal = _require_principal(principal)
        sp = self._load_space(principal, space_id)
        self._require_space_admin(principal, sp, action="grant_capability")
        agent = validate_name(agent, what="agent")
        caps = sorted({self._str(c, "capability", max_len=64) for c in capabilities})
        if not caps:
            raise ValidationError("grant requires at least one capability")
        ts = self._now()
        grant = {
            "id": _grant_id(space_id, agent),
            "kind": "grant",
            "tenant": principal.tenant,
            "namespace": principal.namespace,
            "owner": principal.agent,
            "created_at": ts,
            "space": space_id,
            "agent": agent,
            "caps": caps,
            "active": True,
        }
        with self.store.atomic():
            self._emit(principal, Op.CAPABILITY_GRANTED, ts, grant)

    def revoke_capability(self, principal: Principal, *, space_id: str, agent: str) -> None:
        """Revoke ``agent``'s membership on a space. Current access is denied immediately; the
        historical fact that access existed remains in the ledger (auditable)."""
        principal = _require_principal(principal)
        sp = self._load_space(principal, space_id)
        self._require_space_admin(principal, sp, action="revoke_capability")
        agent = validate_name(agent, what="agent")
        ts = self._now()
        with self.store.atomic():
            self._emit(
                principal, Op.CAPABILITY_REVOKED, ts,
                {"grant_id": _grant_id(space_id, agent), "space": space_id, "agent": agent},
            )

    def share(self, principal: Principal, obj_id: str, *, into: str,
              reason: str | None = None) -> None:
        """Explicitly place one of the caller's objects into a space (lateral share). The origin
        placement is preserved (append-only); nothing is moved or rewritten (mission §9/§10)."""
        self._place(principal, obj_id, into, Op.KNOWLEDGE_SHARED, "knowledge.share", reason,
                    monotone=False)

    def promote(self, principal: Principal, obj_id: str, *, into: str,
                reason: str | None = None) -> None:
        """Promote an object UP the visibility lattice into a wider space. Requires the promote
        capability; the destination visibility must be >= every current placement (monotone). The
        whole visibility history stays in the ledger — this is the ONLY path toward PUBLIC."""
        self._place(principal, obj_id, into, Op.KNOWLEDGE_PROMOTED, "knowledge.promote", reason,
                    monotone=True)

    def _require_space_admin(
        self, principal: Principal, sp: dict[str, Any], *, action: str
    ) -> None:
        """A space's owner (or admin, or a holder of space.manage) may manage its membership."""
        if (
            sp.get("owner") == principal.agent
            or "admin" in principal.capabilities
            or "space.manage" in principal.capabilities
        ):
            return
        raise AuthorizationError(f"{action} denied: not the owner of space {sp.get('id')!r}")

    def _place(self, principal: Principal, obj_id: str, dest: str, op: str, cap: str,
               reason: str | None, *, monotone: bool) -> None:
        principal = _require_principal(principal)
        obj = self._ref_in_scope(principal, obj_id, what="object")
        # only the owner (or admin) may expose their own object to a wider audience
        principal.guard_owner(obj.get("owner", principal.agent), action=op)
        dest_sp = self._load_space(principal, dest)
        dest_vis = resolve_visibility(dest_sp.get("visibility"))
        # The caller must be able to place into the destination: own it, be a member, or it is
        # tenant-wide (ORG+). And the DESTINATION VISIBILITY is what gates authority: placing into
        # PRIVATE/TEAM is a normal collaboration right for the object owner; placing into
        # ORGANIZATION or wider (the path toward PUBLIC) requires the explicit `knowledge.promote`
        # capability, which is NOT in the default set (fail closed — the P0 guard, mission §11).
        can_reach_dest = (
            dest_sp.get("owner") == principal.agent
            or self._is_member(dest, principal.agent)
            or dest_vis >= Visibility.ORGANIZATION
            or "admin" in principal.capabilities
        )
        if not can_reach_dest:
            raise AuthorizationError(f"{op} denied: no access to destination space {dest!r}")
        if dest_vis >= Visibility.ORGANIZATION and "admin" not in principal.capabilities:
            principal.require("knowledge.promote")
        _ = cap  # capability gating is by destination visibility, computed above
        if monotone:
            for placed in obj.get("spaces", ()):
                cur = self._space_of(placed)
                cur_vis = cur[0] if cur is not None else Visibility.PRIVATE
                if dest_vis < cur_vis:
                    raise ValidationError(
                        f"promotion must not lower visibility: {dest_vis.name} < {cur_vis.name}"
                    )
        if reason is not None:
            reason = self._str(reason, "reason", max_len=self.limits.max_str)
        ts = self._now()
        with self.store.atomic():
            self._emit(principal, op, ts, {
                "object_id": obj_id,
                "destination_space": dest,
                "source_spaces": list(obj.get("spaces", ())),
                "shared_by": principal.agent if op == Op.KNOWLEDGE_SHARED else None,
                "promoted_by": principal.agent if op == Op.KNOWLEDGE_PROMOTED else None,
                "reason": reason,
            })

    # ======================================================================
    # Collaborative claims (EPISTEMOS-05): contribution != truth
    # ======================================================================
    def create_claim(
        self,
        principal: Principal,
        *,
        subject: str,
        predicate: str,
        object: str | None = None,  # noqa: A002
        claimant: str | None = None,
        contributor_kind: str = ContributorKind.AGENT.value,
        source: str | None = None,
        confidence: float = 1.0,
        valid_from: str | None = None,
        valid_to: str | None = None,
        space: str | None = None,
        derived_from: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Claim:
        """Assert a claim (a contribution, NOT truth). ``claimant`` defaults to the caller's agent
        but may name a distinct identity (human/service) on whose behalf the agent ingests it; the
        caller's agent is recorded as ``owner`` (the ingesting agent), and ``source`` is the
        external origin — three separate identities (§3). PRIVATE by default; a ``space`` places it."""
        principal = _require_principal(principal)
        principal.require("claim.create")
        subject = self._str(subject, "subject")
        predicate = self._str(predicate, "predicate")
        object = self._str(object, "object", allow_none=True)  # noqa: A002
        claimant = self._str(claimant or principal.agent, "claimant", max_len=128)
        ContributorKind(contributor_kind)  # validate
        self._instant(valid_from, "valid_from")
        self._instant(valid_to, "valid_to")
        confidence = self._confidence(confidence)
        derived = tuple(derived_from or ())
        for ref in derived:
            self._ref_readable(principal, ref, what="derived_from")
        if source is not None:
            self._ref_in_scope(principal, source, what="source")
        spaces = self._resolve_placement(principal, space)
        ts = self._now()
        claim = Claim(
            **self._envelope(principal, "claim", new_id("clm"), ts, source=source,
                             confidence=confidence, derived_from=derived, spaces=spaces),
            subject=subject, predicate=predicate, object=object,
            claimant=claimant, contributor_kind=contributor_kind,
            valid_from=valid_from, valid_to=valid_to, tx_from=ts, tx_to=None,
            status=ClaimStatus.OPEN.value, metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.CLAIM_ASSERTED, ts, claim.to_dict())
        return claim

    def retract_claim(self, principal: Principal, claim_id: str, *, reason: str | None = None) -> None:
        """Withdraw a claim. History preserved; the claim remains, its belief becomes RETRACTED."""
        principal = _require_principal(principal)
        principal.require("claim.retract")
        claim = self._ref_readable(principal, claim_id, what="claim")
        if claim.get("kind") != "claim":
            raise ValidationError(f"{claim_id} is not a claim")
        principal.guard_owner(claim.get("owner", principal.agent), action="retract_claim")
        if claim.get("status") != ClaimStatus.OPEN.value:
            raise ConflictError(f"claim {claim_id} is already {claim.get('status')}")
        if reason is not None:
            reason = self._str(reason, "reason", max_len=self.limits.max_str)
        ts = self._now()
        with self.store.atomic():
            self._emit(principal, Op.CLAIM_RETRACTED, ts, {
                "claim_id": claim_id, "status": ClaimStatus.RETRACTED.value,
                "tx_to": ts, "reason": reason,
            })

    def create_evidence(
        self,
        principal: Principal,
        *,
        evidence_kind: str = EvidenceKind.URI.value,
        title: str | None = None,
        uri: str | None = None,
        content_hash: str | None = None,
        origin: str | None = None,
        captured_at: str | None = None,
        space: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Evidence:
        """Record a typed piece of evidence. The full content need not be stored — a URI + content
        hash is a valid, integrity-checkable reference (§5). PRIVATE by default (its own space)."""
        principal = _require_principal(principal)
        principal.require("evidence.create")
        EvidenceKind(evidence_kind)
        title = self._str(title, "title", allow_none=True)
        uri = self._str(uri, "uri", max_len=self.limits.max_uri, allow_none=True)
        content_hash = self._str(content_hash, "content_hash", max_len=256, allow_none=True)
        origin = self._str(origin, "origin", allow_none=True)
        if captured_at is not None:
            self._instant(captured_at, "captured_at")
        spaces = self._resolve_placement(principal, space)
        ts = self._now()
        ev = Evidence(
            **self._envelope(principal, "evidence", new_id("evd"), ts, spaces=spaces),
            evidence_kind=evidence_kind, title=title, uri=uri, content_hash=content_hash,
            origin=origin, captured_at=captured_at, metadata=self._metadata(metadata),
        )
        with self.store.atomic():
            self._emit(principal, Op.EVIDENCE_RECORDED, ts, ev.to_dict())
        return ev

    def attach_evidence(
        self, principal: Principal, *, evidence_id: str, to_claim: str,
        relation: str = EvidenceRelation.SUPPORTS.value,
    ) -> None:
        """Link evidence to a claim with a TYPED relation. 'attached' is not 'supports' — a piece
        of evidence may CONTRADICT/WEAKEN a claim (§6). Requires read access to BOTH."""
        principal = _require_principal(principal)
        principal.require("evidence.attach")
        EvidenceRelation(relation)
        claim = self._ref_readable(principal, to_claim, what="claim")
        ev = self._ref_readable(principal, evidence_id, what="evidence")
        if claim.get("kind") != "claim":
            raise ValidationError(f"{to_claim} is not a claim")
        if ev.get("kind") != "evidence":
            raise ValidationError(f"{evidence_id} is not evidence")
        ts = self._now()
        with self.store.atomic():
            self._emit(principal, Op.EVIDENCE_ATTACHED, ts, {
                "claim_id": to_claim, "evidence_id": evidence_id, "relation": relation,
            })

    def review_claim(
        self, principal: Principal, claim_id: str, *, verdict: str,
        rationale: str | None = None, evidence_refs: Iterable[str] | None = None,
    ) -> Review:
        """Record ONE reviewer's individual assessment. Verdicts are preserved verbatim; majority
        is not truth (§9). Requires read access to the claim + capability (§17). Self-review is
        allowed but disclosed (the reviewer == claimant is visible); it cannot itself accept (§32)."""
        principal = _require_principal(principal)
        Verdict(verdict)
        cap = {"confirm": "claim.confirm", "dispute": "claim.dispute"}.get(verdict, "claim.review")
        principal.require(cap)
        claim = self._ref_readable(principal, claim_id, what="claim")
        if claim.get("kind") != "claim":
            raise ValidationError(f"{claim_id} is not a claim")
        refs = tuple(evidence_refs or ())
        for r in refs:
            self._ref_readable(principal, r, what="evidence")
        if rationale is not None:
            rationale = self._str(rationale, "rationale", max_len=self.limits.max_text)
        ts = self._now()
        review = Review(
            **self._envelope(principal, "review", new_id("rev"), ts,
                             spaces=tuple(claim.get("spaces", ()))),  # review inherits claim's audience
            claim_id=claim_id, verdict=verdict, rationale=rationale, evidence_refs=refs,
        )
        with self.store.atomic():
            self._emit(principal, Op.CLAIM_REVIEWED, ts, review.to_dict())
        return review

    def accept_claim(self, principal: Principal, claim_id: str, *, reason: str | None = None) -> None:
        """Governed acceptance of a claim as knowledge — a policy decision, NOT a vote (§18). Needs
        the ``knowledge.accept`` capability; the policy port decides. A claimant cannot accept their
        own claim (§32, DENY self-acceptance). History and any coexisting dispute are preserved."""
        self._govern(principal, claim_id, Op.CLAIM_ACCEPTED, "accept", reason)

    def reject_claim(self, principal: Principal, claim_id: str, *, reason: str | None = None) -> None:
        """Governed rejection (mirror of accept). The claim remains on record (never deleted)."""
        self._govern(principal, claim_id, Op.CLAIM_REJECTED, "reject", reason)

    def _govern(self, principal: Principal, claim_id: str, op: str, action: str,
                reason: str | None) -> None:
        principal = _require_principal(principal)
        principal.require("knowledge.accept")
        claim = self._ref_readable(principal, claim_id, what="claim")
        if claim.get("kind") != "claim":
            raise ValidationError(f"{claim_id} is not a claim")
        if (claim.get("claimant") == principal.agent
                and "admin" not in principal.capabilities):
            raise AuthorizationError(f"{action} denied: a claimant cannot govern their own claim")
        reviews = self._readable_reviews(principal, claim_id)
        decision = self.policy(PolicyRequest(
            action=action, principal_agent=principal.agent,
            principal_caps=frozenset(principal.capabilities), claim=claim, reviews=reviews,
            destination_space=(claim.get("spaces") or (None,))[0],
        ))
        if not decision.allow:
            raise AuthorizationError(f"{action} denied by policy: {decision.reason}")
        note = self._str(reason, "reason", max_len=self.limits.max_str, allow_none=True)
        ts = self._now()
        with self.store.atomic():
            self._emit(principal, op, ts, {
                "claim_id": claim_id, "reason": note or decision.reason,
            })

    # -- claim reads (belief, evidence, reviews, explain) --------------------
    def _readable_reviews(self, principal: Principal, claim_id: str) -> list[dict[str, Any]]:
        return self._readable(principal, (
            r for r in self.store.objects(principal.tenant, principal.namespace, kind="review")
            if r.get("claim_id") == claim_id
        ))

    def belief(self, principal: Principal, claim_id: str) -> dict[str, Any]:
        """The DERIVED, explainable belief state of a claim (never a stored boolean, §10). Only the
        reviews the caller may read contribute — belief is computed over authorized material."""
        principal = _require_principal(principal)
        principal.require("claim.read")
        claim = self._ref_readable(principal, claim_id, what="claim")
        if claim.get("kind") != "claim":
            raise ValidationError(f"{claim_id} is not a claim")
        meta = claim.get("metadata", {})
        return derive_belief(
            claim, self._readable_reviews(principal, claim_id),
            accepted=meta.get("accepted"), rejected=meta.get("rejected"),
        )

    def claim_evidence(self, principal: Principal, claim_id: str) -> list[dict[str, Any]]:
        """Evidence links for a claim, filtered to the evidence the caller may read (§15: a public
        claim does not expose private evidence)."""
        principal = _require_principal(principal)
        principal.require("claim.read")
        claim = self._ref_readable(principal, claim_id, what="claim")
        out = []
        for link in claim.get("metadata", {}).get("evidence_links", []):
            ev = self.store.get_object(link.get("evidence"))
            if ev is not None and self._can_read(principal, ev):
                out.append({"evidence": ev["id"], "relation": link.get("relation"),
                            "evidence_kind": ev.get("evidence_kind"), "uri": ev.get("uri"),
                            "title": ev.get("title")})
        return out

    def explain_claim(self, principal: Principal, claim_id: str) -> dict[str, Any]:
        """Full genealogy of a claim: claimant/source, evidence, reviews, belief, contradictions,
        space, temporal — with authorization applied BEFORE traversal (the v0.4 explain leak stays
        permanently closed: an unreadable ancestor/evidence/review is elided, never exposed)."""
        principal = _require_principal(principal)
        principal.require("claim.read")
        claim = self._ref_readable(principal, claim_id, what="claim")
        if claim.get("kind") != "claim":
            raise ValidationError(f"{claim_id} is not a claim")
        return {
            "id": claim_id,
            "statement": {"subject": claim.get("subject"), "predicate": claim.get("predicate"),
                          "object": claim.get("object")},
            "claimant": claim.get("claimant"),
            "contributor_kind": claim.get("contributor_kind"),
            "ingested_by": claim.get("owner"),
            "source": self._scoped_source_view(principal, claim),
            "evidence": self.claim_evidence(principal, claim_id),
            "reviews": self._readable_reviews_view(principal, claim_id),
            "contradictions": list(claim.get("contradicts", [])),
            "belief": self.belief(principal, claim_id),
            "space": (claim.get("spaces") or [None])[0],
            "temporal": {"valid_from": claim.get("valid_from"), "valid_to": claim.get("valid_to"),
                         "tx_from": claim.get("tx_from"), "tx_to": claim.get("tx_to"),
                         "status": claim.get("status")},
        }

    def _readable_reviews_view(self, principal: Principal, claim_id: str) -> list[dict[str, Any]]:
        return [
            {"reviewer": r.get("owner"), "verdict": r.get("verdict"),
             "rationale": r.get("rationale"), "at": r.get("created_at"),
             "self_review": r.get("owner") == r.get("claimant_of_review_target")}
            for r in self._readable_reviews(principal, claim_id)
        ]

    # -- placement helper reused by claims/evidence -------------------------
    def _resolve_placement(self, principal: Principal, space: str | None) -> tuple[str, ...]:
        """Resolve an optional destination space to a placement tuple. None -> PRIVATE (owner-only,
        the fail-closed default). A named space must exist and be reachable by the caller."""
        if space is None:
            return ()
        dest_sp = self._load_space(principal, space)
        dest_vis = resolve_visibility(dest_sp.get("visibility"))
        reachable = (
            dest_sp.get("owner") == principal.agent
            or self._is_member(space, principal.agent)
            or dest_vis >= Visibility.ORGANIZATION
            or "admin" in principal.capabilities
        )
        if not reachable:
            raise AuthorizationError(f"cannot create into space {space!r}: no access")
        if dest_vis >= Visibility.ORGANIZATION and "admin" not in principal.capabilities:
            principal.require("knowledge.promote")  # placing directly into ORG+ needs the gate
        return (space,)

    def _ref_readable(self, principal: Principal, ref_id: str, *, what: str) -> dict[str, Any]:
        """Load an object the caller must be able to READ (scope + space firewall). Refuses with
        NotFoundError otherwise — no existence oracle across the space boundary (§17)."""
        obj = self._ref_in_scope(principal, ref_id, what=what)
        if not self._can_read(principal, obj):
            raise NotFoundError(f"{what} {ref_id!r} not found")
        return obj

    def _scoped_source_view(
        self, principal: Principal, obj: dict[str, Any]
    ) -> dict[str, Any] | None:
        """A source view only if the source is readable in the object's scope (never leak a
        cross-scope source's uri/trust — the B-06 rule, applied to claims)."""
        src_id = obj.get("source")
        if not src_id:
            return None
        src = self.store.get_object(src_id)
        if src is None or not self._can_read(principal, src):
            return None
        return {"id": src["id"], "uri": src.get("uri"), "trust": src.get("trust")}

    # ======================================================================
    # retrieval & explanation
    # ======================================================================
    def get(self, principal: Principal, obj_id: str) -> Any:
        principal = _require_principal(principal)
        principal.require("read")
        obj = self.store.get_object(obj_id)
        # Return None for BOTH an absent id and one that exists only in another scope, so get()
        # cannot be used as an existence oracle (EPISTEMOS-03, B-01). Previously absent -> None
        # but cross-scope -> NotFoundError, which distinguished the two.
        if obj is None:
            return None
        if obj.get("tenant") != principal.tenant or obj.get("namespace") != principal.namespace:
            return None
        # Space firewall (EPISTEMOS-04): an object the caller is not authorized to see in its space
        # is indistinguishable from absent (no existence oracle across the space boundary).
        if not self._can_read(principal, obj):
            return None
        cls = _KIND_TO_CLS.get(obj.get("kind", ""))
        return cls.from_dict(obj) if cls else obj

    def search(
        self,
        principal: Principal,
        *,
        text: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,  # noqa: A002
        kinds: tuple[str, ...] | None = None,
        limit: int = 10,
        believed_only: bool = False,
        at_valid: Any = None,
        at_tx: Any = None,
    ) -> list[dict[str, Any]]:
        principal = _require_principal(principal)
        principal.require("read")
        if text is not None:
            self._str(text, "text", max_len=self.limits.max_text)
        try:
            limit_int = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"limit must be an integer: {limit!r}") from exc
        if limit_int < 0:  # a negative limit becomes a Python slice that returns all-but-N (B-08)
            raise ValidationError("limit must be >= 0")
        if kinds is not None:  # a bare str or non-str element is interpreted incompatibly (B-05)
            if isinstance(kinds, str) or not isinstance(kinds, (tuple, list)):
                raise ValidationError("kinds must be a tuple of strings")
            if not all(isinstance(k, str) for k in kinds):
                raise ValidationError("every kind must be a string")
            kinds = tuple(kinds)
        kw = dict(
            text=text, subject=subject, predicate=predicate, object=object,
            kinds=kinds, limit=limit_int, believed_only=believed_only,
            at_valid=at_valid, at_tx=at_tx,
            # Space firewall: candidates the caller cannot read are dropped BEFORE scoring/ranking,
            # so an unauthorized object never influences a result's score, rank, count or timing
            # ranking (mission §12). Authorization precedes retrieval, not the reverse.
            authorize=lambda o: self._can_read(principal, o),
        )
        # Use the FTS index only when it is HEALTHY (complete + consistent). Otherwise fall back
        # to the correct O(N) scan — never return stale/incomplete results from a degraded index.
        use_index = (
            self.indexed is not None
            and self.lexical_index is not None
            and self.lexical_index.health() == IndexHealth.HEALTHY
        )
        method = "scan-tfidf+structural+temporal+authority"
        if use_index:
            assert self.indexed is not None  # narrowed by use_index
            try:
                results = self.indexed.search(
                    self.store, principal.tenant, principal.namespace, **kw
                )
                method = "fts5-bm25+structural+temporal+authority"
            except Exception:  # noqa: BLE001 - any index error -> safe fallback
                if self.lexical_index is not None:
                    self.lexical_index.mark_degraded()
                results = self.legacy.search(
                    self.store, principal.tenant, principal.namespace, **kw
                )
        else:
            results = self.legacy.search(self.store, principal.tenant, principal.namespace, **kw)
        return [
            {
                "id": r.id,
                "kind": r.kind,
                "score": r.score,
                "score_components": r.score_components,
                "retrieval_method": method,
                "source": r.source,
                "temporal_state": r.temporal_state,
                "why_returned": r.why,
            }
            for r in results
        ]

    def explain(self, principal: Principal, obj_id: str, *, depth: int = 3) -> dict[str, Any]:
        principal = _require_principal(principal)
        principal.require("read")
        obj = self.store.get_object(obj_id)
        if obj is None:
            raise NotFoundError(f"{obj_id!r} not found")
        if obj.get("tenant") != principal.tenant or obj.get("namespace") != principal.namespace:
            raise NotFoundError(f"{obj_id!r} not found")
        if not self._can_read(principal, obj):  # provenance space isolation (§15/§19)
            raise NotFoundError(f"{obj_id!r} not found")
        idx = self.provenance_index
        can_read = lambda o: self._can_read(principal, o)  # noqa: E731 - elide unreadable lineage
        if obj.get("kind") == "decision":
            return _explain_decision(
                self.store, principal.tenant, principal.namespace, obj_id, index=idx,
                can_read=can_read,
            )
        return _explain_obj(
            self.store, principal.tenant, principal.namespace, obj_id, depth=depth, index=idx,
            can_read=can_read,
        )

    # ======================================================================
    # integrity, export/import, health, rebuild
    # ======================================================================
    def verify_integrity(
        self, *, expected_count: int | None = None, expected_head: str | None = None
    ) -> int:
        """Verify the full hash chain. Returns the number of events verified.

        Pass ``expected_count``/``expected_head`` (an anchor pinned outside the store) to
        also detect tail-truncation and full re-chained rewrites (mission checkpoint G).
        """
        return verify_chain(
            self.store.read_events(),
            expected_count=expected_count,
            expected_head=expected_head,
        )

    def rebuild_projection(self) -> int:
        """Rebuild all queryable state (and every index) purely from the ledger."""
        with self.store.atomic():
            self.store.clear_projection()
            if self.lexical_index is not None:
                self.lexical_index.clear()
            if self.provenance_index is not None:
                self.provenance_index.clear()
            count = 0
            for rec in self.store.read_events():
                self._apply(rec)  # _apply -> _persist -> reindex rebuilds the indexes too
                count += 1
        # The indexes were just rebuilt from authoritative state, so a previously DEGRADED index
        # is healthy again — restore it, or search would fall back to the O(N) scan forever (LT-07).
        if self.lexical_index is not None and self.lexical_index.verify(self.store):
            self.lexical_index.restore_healthy()
        if self.provenance_index is not None and self.provenance_index.verify(self.store):
            self.provenance_index.restore_healthy()
        return count

    def verify_index_consistency(self) -> bool:
        """True iff every index matches the authoritative state it projects.

        The scan backend (in-memory) is always consistent because it reads live state.
        """
        ok = True
        if self.lexical_index is not None:
            ok = self.lexical_index.verify(self.store) and ok
        if self.provenance_index is not None:
            ok = self.provenance_index.verify(self.store) and ok
        return ok

    def rebuild_index(self) -> int:
        """Drop and rebuild the lexical index from the authoritative store. Returns objects done."""
        if self.provenance_index is not None:
            self.provenance_index.rebuild(self.store)
        if self.lexical_index is None:
            return 0
        return self.lexical_index.rebuild(self.store)

    def export(
        self, principal: Principal | None = None, *, scope: str = "principal"
    ) -> dict[str, Any]:
        """Versioned, human-readable export of the tamper-evident ledger.

        * ``principal=None`` — whole-store export for the **in-process library caller**, who
          already holds the database file. Unchanged v0.1 behaviour.
        * ``principal`` given (the only form any remote boundary may use) — a **scope-limited**
          export of that principal's ``(tenant, namespace)``. Filtering a hash chain breaks its
          linkage, so the scoped slice is **re-sealed** into a fresh, self-consistent chain: it
          verifies and re-imports, but its entry hashes are new (flagged by ``resealed``).
        * ``scope="all"`` with a principal — whole-store export, gated on ``admin``.

        Before EPISTEMOS-03 this method took no principal, so REST's ``GET /export`` handed any
        authenticated caller every tenant's complete history (A-11).
        """
        if principal is None:
            events = [_record_to_dict(r) for r in self.store.read_events()]
            return {
                "format": EXPORT_FORMAT,
                "schema_version": SCHEMA_VERSION,
                "exported_at": self._now(),
                "event_count": len(events),
                "events": events,
            }

        principal = _require_principal(principal)
        principal.require("export")
        if scope not in ("principal", "all"):
            raise ValidationError(f"unknown export scope {scope!r}")
        if scope == "all":
            if "admin" not in principal.capabilities:
                raise AuthorizationError(
                    "whole-store export requires the 'admin' capability; "
                    "omit scope='all' for a scope-limited export"
                )
            events = [_record_to_dict(r) for r in self.store.read_events()]
            return {
                "format": EXPORT_FORMAT,
                "schema_version": SCHEMA_VERSION,
                "exported_at": self._now(),
                "event_count": len(events),
                "events": events,
                "scope": {"tenant": None, "namespace": None},
            }

        # Space firewall on export (EPISTEMOS-04, §18): the slice contains ONLY events for objects
        # the principal may currently read. An event referencing an object outside the caller's
        # authorized spaces is dropped, so a scoped export cannot exfiltrate a namespace-mate's
        # private knowledge. Space/grant control-plane events are omitted too.
        readable_ids = {
            o["id"] for o in self.store.objects(principal.tenant, principal.namespace)
            if o.get("kind") not in ("space", "grant") and self._can_read(principal, o)
        }
        selected = [
            r for r in self.store.read_events()
            if r.tenant == principal.tenant and r.namespace == principal.namespace
            and _event_object_id(r.payload) in readable_ids
        ]
        resealed: list[dict[str, Any]] = []
        prev = GENESIS_HASH
        for seq, rec in enumerate(selected, start=1):
            sealed = seal(
                seq=seq,
                event=Event(
                    op=rec.op, ts=rec.ts, tenant=rec.tenant, namespace=rec.namespace,
                    actor=rec.actor, principal=rec.principal, payload=rec.payload,
                ),
                prev_hash=prev,
            )
            prev = sealed.entry_hash
            resealed.append(_record_to_dict(sealed))
        return {
            "format": EXPORT_FORMAT,
            "schema_version": SCHEMA_VERSION,
            "exported_at": self._now(),
            "event_count": len(resealed),
            "events": resealed,
            "scope": {"tenant": principal.tenant, "namespace": principal.namespace},
            "resealed": True,
        }

    def import_events(
        self, payload: dict[str, Any], *, verify: bool = True, migrate: bool = False
    ) -> int:
        """Import a full ledger export into an EMPTY engine.

        Refuses to import into a non-empty store (fail closed) so import cannot silently
        interleave with existing history.

        * Same-schema import is **verbatim**: original hashes are preserved and the chain
          is verified (tamper-evident continuity).
        * ``migrate=True`` upgrades an older-schema export via
          :func:`epistemos.schema.migrate_export` and **re-seals** it into a fresh chain
          (payloads changed shape, so original content hashes cannot be preserved).
        """
        if not isinstance(payload, dict) or payload.get("format") != EXPORT_FORMAT:
            raise SchemaError("unrecognized export format")
        if self.store.event_count() != 0:
            raise ConflictError("import target store is not empty")

        # An export with no chain fields cannot be verified at all. Say so plainly instead of
        # failing later with a confusing "malformed record" — and never treat "nothing to
        # check" as "checked and fine".
        if verify and not _carries_chain(payload.get("events", [])):
            raise IntegrityError(
                "export carries no verifiable hash chain (missing seq/content_hash/"
                "prev_hash/entry_hash); pass verify=False to import it as UNVERIFIED — "
                "the result is trusted input, not tamper-evident history"
            )

        version = int(payload.get("schema_version", -1))
        if version != SCHEMA_VERSION:
            if not migrate:
                raise SchemaError(
                    f"unsupported schema_version {payload.get('schema_version')} "
                    f"(engine supports {SCHEMA_VERSION}); pass migrate=True to upgrade"
                )
            from ..schema import migrate_export

            # Verify the chain AS RECEIVED, before migration reshapes payloads and invalidates
            # the original content hashes. Before EPISTEMOS-03 the migrate path re-sealed
            # whatever it was handed without ever verifying it, so `migrate=True` silently
            # disabled tamper-evidence (A-02).
            if verify:
                verify_chain([_dict_to_record(e) for e in payload.get("events", [])])
            payload = migrate_export(payload)
            return self._reseal_import(payload.get("events", []))

        records = [_dict_to_record(e) for e in payload.get("events", [])]
        if verify:
            verify_chain(records)
        with self.store.atomic():
            for rec in records:
                self.store._persist_record(rec)  # verbatim, preserving original hashes
            self.store.clear_projection()
            for rec in self.store.read_events():
                self._apply(rec)
        return len(records)

    def _reseal_import(self, events: list[dict[str, Any]]) -> int:
        """Re-seal migrated events into a fresh chain and project them."""
        with self.store.atomic():
            for e in events:
                try:
                    ev = Event(
                        op=e["op"], ts=e["ts"], tenant=e["tenant"], namespace=e["namespace"],
                        actor=e["actor"], principal=e.get("principal"), payload=e["payload"],
                    )
                except (KeyError, TypeError) as exc:
                    raise SchemaError(f"malformed migrated event: {exc}") from exc
                self._apply(self.store.append(ev))
        return self.store.event_count()

    def health(self, principal: Principal | None = None, *, verify: bool = False) -> dict[str, Any]:
        # A scoped caller (a principal) sees only its own scope's event count and never the
        # store-global chain head — those reveal cross-tenant write activity (EPISTEMOS-03,
        # B-06/B-07). The operator (principal=None, in-process) still gets the global view.
        if principal is not None:
            scope_events = sum(
                1 for r in self.store.read_events()
                if r.tenant == principal.tenant and r.namespace == principal.namespace
            )
            event_count: int = scope_events
            head_hash: str | None = None
        else:
            head = self.store.head()
            event_count = self.store.event_count()
            head_hash = head.entry_hash if head is not None else None
        info: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "event_count": event_count,
            "head_hash": head_hash,
            # Unverified is reported as unknown (None), never as True: before EPISTEMOS-03 a
            # corrupted ledger reported integrity_ok=True simply because nobody checked (A-06).
            "integrity_verified": bool(verify),
            "integrity_ok": None,
        }
        if verify:
            info["integrity_ok"] = True
            try:
                self.verify_integrity()
            except IntegrityError as exc:
                info["integrity_ok"] = False
                info["integrity_error"] = str(exc)
        # lexical index state (EPISTEMOS-02): explicit, never hidden. verify() may DOWNGRADE the
        # state (content drift -> DEGRADED), so run it BEFORE reading the reported state, or
        # health could claim HEALTHY alongside consistent=False (LT-02).
        if self.lexical_index is not None:
            index_info: dict[str, Any] = {"count": self.lexical_index.count(),
                                          "backend": "sqlite-fts5"}
            if verify:
                index_info["consistent"] = self.lexical_index.verify(self.store)
            index_info["state"] = str(self.lexical_index.health())
            info["index"] = index_info
        else:
            info["index"] = {"state": str(IndexHealth.UNAVAILABLE), "backend": "scan"}
        if self.provenance_index is not None:
            prov_info: dict[str, Any] = {"count": self.provenance_index.count(),
                                         "backend": "sqlite-prov-ref"}
            if verify:
                prov_info["consistent"] = self.provenance_index.verify(self.store)
            prov_info["state"] = str(self.provenance_index.health())
            info["provenance_index"] = prov_info
        else:
            info["provenance_index"] = {"state": str(IndexHealth.UNAVAILABLE), "backend": "scan"}
        if principal is not None:
            principal = _require_principal(principal)
            info["scope"] = {"tenant": principal.tenant, "namespace": principal.namespace}
            info["counts"] = self.store.counts(principal.tenant, principal.namespace)
        return info


# ==========================================================================
# module helpers
# ==========================================================================
_PUT_OPS = frozenset(
    {
        Op.SOURCE_ADDED,
        Op.OBSERVATION_RECORDED,
        Op.DOCUMENT_INGESTED,
        Op.FACT_ASSERTED,
        Op.ENTITY_ADDED,
        Op.RELATION_ADDED,
        Op.DECISION_RECORDED,
        Op.EPISODE_RECORDED,
    }
)


_CHAIN_FIELDS = ("seq", "content_hash", "prev_hash", "entry_hash")


def _carries_chain(events: Any) -> bool:
    """True iff every event presents the fields :func:`verify_chain` needs."""
    if not isinstance(events, list) or not events:
        return True  # an empty export is vacuously verifiable
    return all(
        isinstance(e, dict) and all(f in e for f in _CHAIN_FIELDS) for e in events
    )


def _event_object_id(payload: Any) -> str | None:
    """The primary object id an event pertains to (for scoped, space-filtered export)."""
    if not isinstance(payload, dict):
        return None
    for key in ("id", "fact_id", "object_id", "entity", "canonical"):
        val = payload.get(key)
        if isinstance(val, str):
            return val
    return None


def _grant_id(space_id: str, agent: str) -> str:
    """Deterministic id for a (space, agent) grant so grant/revoke address the same object."""
    return f"grant_{space_id}_{agent}"


def _json_depth(obj: Any, current: int = 0) -> int:
    if isinstance(obj, dict):
        return max((_json_depth(v, current + 1) for v in obj.values()), default=current)
    if isinstance(obj, (list, tuple)):
        return max((_json_depth(v, current + 1) for v in obj), default=current)
    return current


def _dedup_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for e in edges:
        if e["id"] not in seen:
            seen.add(e["id"])
            out.append(e)
    return out


def _record_to_dict(r: LedgerRecord) -> dict[str, Any]:
    return {
        "seq": r.seq,
        "ts": r.ts,
        "op": r.op,
        "tenant": r.tenant,
        "namespace": r.namespace,
        "actor": r.actor,
        "principal": r.principal,
        "payload": dict(r.payload),
        "content_hash": r.content_hash,
        "prev_hash": r.prev_hash,
        "entry_hash": r.entry_hash,
    }


def _dict_to_record(d: dict[str, Any]) -> LedgerRecord:
    try:
        return LedgerRecord(
            seq=int(d["seq"]),
            ts=d["ts"],
            op=d["op"],
            tenant=d["tenant"],
            namespace=d["namespace"],
            actor=d["actor"],
            principal=d.get("principal"),
            payload=d["payload"],
            content_hash=d["content_hash"],
            prev_hash=d["prev_hash"],
            entry_hash=d["entry_hash"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SchemaError(f"malformed ledger record in import: {exc}") from exc


def _iter_all_records(store: Store) -> Iterator[LedgerRecord]:  # pragma: no cover - helper
    yield from store.read_events()
