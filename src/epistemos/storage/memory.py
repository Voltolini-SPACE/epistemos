"""In-memory :class:`Store` — a genuine second, non-SQLite implementation.

Its existence (and passing the same conformance suite as the SQLite adapter) is the
evidence for storage-agnosticism (mission §17, ADR-006). It is also the fast backend
for unit tests. Writes serialize under a re-entrant lock so the race battery is
deterministic.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .._util import canonical_json
from ..errors import ValidationError
from ..ledger import LedgerRecord
from .ports import Store

__all__ = ["MemoryStore"]


class MemoryStore(Store):
    # Objects are held as canonical-JSON strings, exactly like the SQLite adapter. This
    # gives full deep isolation (a returned object shares no mutable structure with the
    # store) and byte-identical read/write semantics across both adapters.
    def __init__(self) -> None:
        self._ledger: list[LedgerRecord] = []
        self._objects: dict[str, str] = {}
        self._lock = threading.RLock()
        self._depth = 0
        self._snap_ledger = 0
        self._snap_objects: dict[str, str] | None = None

    def close(self) -> None:  # nothing to release
        return None

    @contextmanager
    def atomic(self) -> Iterator[None]:
        self._lock.acquire()
        try:
            outermost = self._depth == 0
            if outermost:
                self._snap_ledger = len(self._ledger)
                self._snap_objects = dict(self._objects)
            self._depth += 1
            try:
                yield
            except BaseException:
                if outermost:
                    del self._ledger[self._snap_ledger :]
                    assert self._snap_objects is not None
                    self._objects = self._snap_objects
                raise
            finally:
                self._depth -= 1
                if outermost:
                    self._snap_objects = None
        finally:
            self._lock.release()

    # -- ledger --------------------------------------------------------------
    def _persist_record(self, record: LedgerRecord) -> None:
        self._ledger.append(record)

    def head(self) -> LedgerRecord | None:
        with self._lock:
            return self._ledger[-1] if self._ledger else None

    def read_events(self, since_seq: int = 0) -> list[LedgerRecord]:
        with self._lock:
            return [r for r in self._ledger if r.seq > since_seq]

    def event_count(self) -> int:
        with self._lock:
            return len(self._ledger)

    # -- objects -------------------------------------------------------------
    def put_object(self, obj: dict[str, Any]) -> None:
        for req in ("id", "kind", "tenant", "namespace"):
            if req not in obj:
                raise ValidationError(f"object missing required key {req!r}")
        with self._lock:
            self._objects[obj["id"]] = canonical_json(obj)

    def get_object(self, obj_id: str) -> dict[str, Any] | None:
        with self._lock:
            found = self._objects.get(obj_id)
        return json.loads(found) if found is not None else None

    def objects(
        self, tenant: str, namespace: str, kind: str | None = None
    ) -> Iterator[dict[str, Any]]:
        with self._lock:
            snapshot = [json.loads(o) for o in self._objects.values()]
        for o in snapshot:
            if o["tenant"] == tenant and o["namespace"] == namespace and (
                kind is None or o.get("kind") == kind
            ):
                yield o

    # -- indexes -------------------------------------------------------------
    def facts(
        self,
        tenant: str,
        namespace: str,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,  # noqa: A002
    ) -> list[dict[str, Any]]:
        out = []
        for o in self.objects(tenant, namespace, kind="fact"):
            if subject is not None and o.get("subject") != subject:
                continue
            if predicate is not None and o.get("predicate") != predicate:
                continue
            if object is not None and o.get("object") != object:
                continue
            out.append(o)
        return out

    def relations(
        self,
        tenant: str,
        namespace: str,
        *,
        source_entity: str | None = None,
        target_entity: str | None = None,
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]:
        out = []
        for o in self.objects(tenant, namespace, kind="relation"):
            if source_entity is not None and o.get("source_entity") != source_entity:
                continue
            if target_entity is not None and o.get("target_entity") != target_entity:
                continue
            if rel_type is not None and o.get("rel_type") != rel_type:
                continue
            out.append(o)
        return out

    def counts(self, tenant: str, namespace: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for o in self.objects(tenant, namespace):
            result[o["kind"]] = result.get(o["kind"], 0) + 1
        return result

    def clear_projection(self) -> None:
        with self._lock:
            self._objects.clear()
