"""Storage ports (mission §17).

The domain (engine, temporal, provenance, retrieval) depends only on this abstract
:class:`Store` — never on SQLite, Neo4j, pgvector or any concrete backend. A backend is
a "dumb" persistence + structural-index layer; all *semantics* live in the domain.

Two invariants a conforming store must uphold:

* **Atomicity** — everything inside ``atomic()`` commits or rolls back together, so the
  ledger append and the projection update can never diverge across a crash.
* **Scope filtering** — every query filters strictly by ``(tenant, namespace)``. This is
  defense-in-depth for tenant isolation: even an engine bug cannot leak across tenants
  through a store query.

The event-sealing math is shared here so all adapters chain identically; adapters only
implement how to read the head and how to persist a sealed record.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ..ledger import GENESIS_HASH, Event, LedgerRecord, seal

__all__ = ["Store"]


class Store(ABC):
    # -- lifecycle -----------------------------------------------------------
    @abstractmethod
    def close(self) -> None: ...

    @contextmanager
    @abstractmethod
    def atomic(self) -> Iterator[None]:
        """Transaction boundary. Nested use must be a no-op join, not a new tx."""
        raise NotImplementedError
        yield  # pragma: no cover

    # -- ledger (append-only) ------------------------------------------------
    def append(self, event: Event) -> LedgerRecord:
        """Seal ``event`` onto the chain and persist it. Call inside ``atomic()``."""
        prev_hash, seq = self._head_link()
        record = seal(seq=seq, event=event, prev_hash=prev_hash)
        self._persist_record(record)
        return record

    def _head_link(self) -> tuple[str, int]:
        head = self.head()
        if head is None:
            return GENESIS_HASH, 1
        return head.entry_hash, head.seq + 1

    @abstractmethod
    def _persist_record(self, record: LedgerRecord) -> None: ...

    @abstractmethod
    def head(self) -> LedgerRecord | None: ...

    @abstractmethod
    def read_events(self, since_seq: int = 0) -> list[LedgerRecord]: ...

    def records_by_seq(self, seqs: list[int]) -> list[LedgerRecord]:
        """Fetch specific sealed records by sequence number, ascending.

        The default is a correct O(events) filter so every adapter works unchanged; a backend
        that can index the ledger overrides it. Used by the provenance index (ADR-022) to turn
        a whole-ledger scan into a keyed lookup — the *result* must be identical either way.
        """
        wanted = set(seqs)
        return [r for r in self.read_events() if r.seq in wanted]

    @abstractmethod
    def event_count(self) -> int: ...

    # -- object projection (latest materialized state) -----------------------
    @abstractmethod
    def put_object(self, obj: dict[str, Any]) -> None:
        """Upsert the latest state of an object keyed by ``obj['id']``."""

    @abstractmethod
    def get_object(self, obj_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def objects(
        self, tenant: str, namespace: str, kind: str | None = None
    ) -> Iterator[dict[str, Any]]: ...

    # -- structural indexes --------------------------------------------------
    @abstractmethod
    def facts(
        self,
        tenant: str,
        namespace: str,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,  # noqa: A002 - domain vocabulary
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def relations(
        self,
        tenant: str,
        namespace: str,
        *,
        source_entity: str | None = None,
        target_entity: str | None = None,
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def counts(self, tenant: str, namespace: str) -> dict[str, int]: ...

    # -- maintenance ---------------------------------------------------------
    @abstractmethod
    def clear_projection(self) -> None:
        """Drop all materialized objects/indexes (NOT the ledger). For rebuilds."""
