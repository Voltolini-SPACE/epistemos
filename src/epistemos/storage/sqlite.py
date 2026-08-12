"""SQLite-backed :class:`Store` — the default local, crash-consistent backend.

Single file, no server, no network. WAL + ``synchronous=FULL`` so a committed
transaction survives a process ``kill -9`` (the crash-recovery gate). Writes serialize
through a lock and ``BEGIN IMMEDIATE`` to make the race battery deterministic and avoid
lock-upgrade deadlocks. Structured triple/relation columns are materialized alongside the
canonical JSON so lookups are indexed rather than JSON scans.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .._util import canonical_json
from ..errors import StorageError, ValidationError
from ..ledger import LedgerRecord
from .ports import Store

__all__ = ["SQLiteStore"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger (
    seq          INTEGER PRIMARY KEY,
    ts           TEXT NOT NULL,
    op           TEXT NOT NULL,
    tenant       TEXT NOT NULL,
    namespace    TEXT NOT NULL,
    actor        TEXT NOT NULL,
    principal    TEXT,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    prev_hash    TEXT NOT NULL,
    entry_hash   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS objects (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    tenant        TEXT NOT NULL,
    namespace     TEXT NOT NULL,
    owner         TEXT,
    created_at    TEXT,
    subject       TEXT,
    predicate     TEXT,
    object        TEXT,
    source_entity TEXT,
    target_entity TEXT,
    rel_type      TEXT,
    json          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obj_scope ON objects(tenant, namespace, kind);
CREATE INDEX IF NOT EXISTS idx_obj_fact ON objects(tenant, namespace, subject, predicate);
CREATE INDEX IF NOT EXISTS idx_obj_rel ON objects(tenant, namespace, source_entity, target_entity);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

_LEDGER_COLS = (
    "seq, ts, op, tenant, namespace, actor, principal, payload_json, "
    "content_hash, prev_hash, entry_hash"
)


class SQLiteStore(Store):
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._depth = 0
        self._configure()

    def _configure(self) -> None:
        cur = self._conn
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=FULL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA busy_timeout=5000;")
        cur.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        self._lock.acquire()
        try:
            outermost = self._depth == 0
            if outermost:
                self._conn.execute("BEGIN IMMEDIATE;")
            self._depth += 1
            try:
                yield
            except BaseException:
                if outermost:
                    self._conn.execute("ROLLBACK;")
                raise
            else:
                if outermost:
                    self._conn.execute("COMMIT;")
            finally:
                self._depth -= 1
        finally:
            self._lock.release()

    # -- ledger --------------------------------------------------------------
    def _persist_record(self, record: LedgerRecord) -> None:
        self._conn.execute(
            f"INSERT INTO ledger ({_LEDGER_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                record.seq,
                record.ts,
                record.op,
                record.tenant,
                record.namespace,
                record.actor,
                record.principal,
                canonical_json(dict(record.payload)),
                record.content_hash,
                record.prev_hash,
                record.entry_hash,
            ),
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> LedgerRecord:
        import json

        return LedgerRecord(
            seq=row["seq"],
            ts=row["ts"],
            op=row["op"],
            tenant=row["tenant"],
            namespace=row["namespace"],
            actor=row["actor"],
            principal=row["principal"],
            payload=json.loads(row["payload_json"]),
            content_hash=row["content_hash"],
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
        )

    def head(self) -> LedgerRecord | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_LEDGER_COLS} FROM ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def read_events(self, since_seq: int = 0) -> list[LedgerRecord]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_LEDGER_COLS} FROM ledger WHERE seq > ? ORDER BY seq", (since_seq,)
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def records_by_seq(self, seqs: list[int]) -> list[LedgerRecord]:
        if not seqs:
            return []
        placeholders = ",".join("?" for _ in seqs)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_LEDGER_COLS} FROM ledger WHERE seq IN ({placeholders}) ORDER BY seq",
                [int(s) for s in seqs],
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def event_count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0])

    # -- objects -------------------------------------------------------------
    def put_object(self, obj: dict[str, Any]) -> None:
        for req in ("id", "kind", "tenant", "namespace"):
            if req not in obj:
                raise ValidationError(f"object missing required key {req!r}")
        self._conn.execute(
            "INSERT OR REPLACE INTO objects "
            "(id, kind, tenant, namespace, owner, created_at, subject, predicate, object, "
            " source_entity, target_entity, rel_type, json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                obj["id"],
                obj["kind"],
                obj["tenant"],
                obj["namespace"],
                obj.get("owner"),
                obj.get("created_at"),
                obj.get("subject"),
                obj.get("predicate"),
                obj.get("object"),
                obj.get("source_entity"),
                obj.get("target_entity"),
                obj.get("rel_type"),
                canonical_json(obj),
            ),
        )

    def get_object(self, obj_id: str) -> dict[str, Any] | None:
        import json

        with self._lock:
            row = self._conn.execute(
                "SELECT json FROM objects WHERE id = ?", (obj_id,)
            ).fetchone()
        return json.loads(row["json"]) if row is not None else None

    def objects(
        self, tenant: str, namespace: str, kind: str | None = None
    ) -> Iterator[dict[str, Any]]:
        import json

        sql = "SELECT json FROM objects WHERE tenant = ? AND namespace = ?"
        params: list[Any] = [tenant, namespace]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        for r in rows:
            yield json.loads(r["json"])

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
        import json

        sql = "SELECT json FROM objects WHERE tenant = ? AND namespace = ? AND kind = 'fact'"
        params: list[Any] = [tenant, namespace]
        if subject is not None:
            sql += " AND subject = ?"
            params.append(subject)
        if predicate is not None:
            sql += " AND predicate = ?"
            params.append(predicate)
        if object is not None:
            sql += " AND object = ?"
            params.append(object)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def relations(
        self,
        tenant: str,
        namespace: str,
        *,
        source_entity: str | None = None,
        target_entity: str | None = None,
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]:
        import json

        sql = "SELECT json FROM objects WHERE tenant = ? AND namespace = ? AND kind = 'relation'"
        params: list[Any] = [tenant, namespace]
        if source_entity is not None:
            sql += " AND source_entity = ?"
            params.append(source_entity)
        if target_entity is not None:
            sql += " AND target_entity = ?"
            params.append(target_entity)
        if rel_type is not None:
            sql += " AND rel_type = ?"
            params.append(rel_type)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def counts(self, tenant: str, namespace: str) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT kind, COUNT(*) c FROM objects WHERE tenant = ? AND namespace = ? "
                "GROUP BY kind",
                (tenant, namespace),
            ).fetchall()
        return {r["kind"]: int(r["c"]) for r in rows}

    def clear_projection(self) -> None:
        self._conn.execute("DELETE FROM objects")

    # -- adapter-specific: physical hot backup -------------------------------
    def backup(self, dest_path: str | Path) -> None:
        """Consistent physical snapshot via SQLite's online backup API.

        Safe to call concurrently with writers — the snapshot is transactionally
        consistent. Used by the "backup during writes" chaos test.
        """
        dest = str(dest_path)
        try:
            with self._lock:
                target = sqlite3.connect(dest)
                try:
                    self._conn.backup(target)
                finally:
                    target.close()
        except sqlite3.Error as exc:  # pragma: no cover - platform dependent
            raise StorageError(f"backup failed: {exc}") from exc
