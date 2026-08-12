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
from ..errors import (
    AuthorizationError,
    ConflictError,
    IntegrityError,
    NotFoundError,
    SchemaError,
    ValidationError,
)
from ..identity import Principal
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
    ) -> None:
        self.store = store
        self.clock = clock
        self.limits = limits or EngineLimits()
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
        else:  # pragma: no cover - defensive
            raise IntegrityError(f"unknown ledger op {op!r}")

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
        self._ref_in_scope(principal, fact_id, what="fact")
        self._ref_in_scope(principal, by, what="fact")
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
        facts = self.store.facts(
            principal.tenant, principal.namespace, subject=subject, predicate=predicate
        )
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
        facts = self.store.facts(
            principal.tenant, principal.namespace, subject=subject, predicate=predicate
        )
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
        rows = self.store.facts(
            principal.tenant, principal.namespace,
            subject=subject, predicate=predicate, object=object,
        )
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
        rows = self.store.facts(principal.tenant, principal.namespace, subject=subject)
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
        self._ref_in_scope(principal, entity_id, what="entity")
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
        return out

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
        idx = self.provenance_index
        if obj.get("kind") == "decision":
            return _explain_decision(
                self.store, principal.tenant, principal.namespace, obj_id, index=idx
            )
        return _explain_obj(
            self.store, principal.tenant, principal.namespace, obj_id, depth=depth, index=idx
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

        selected = [
            r for r in self.store.read_events()
            if r.tenant == principal.tenant and r.namespace == principal.namespace
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
