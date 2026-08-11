"""BACKUP_RESTORE gate (checkpoint P). Distinct from export/import.

Operational SQLite backup: populate -> hot backup -> destroy -> restore -> reopen ->
verify counts/head-hash/state -> keep writing.
"""

from __future__ import annotations

import os

from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore


def _populate(engine: Engine, ctx: Principal) -> None:
    s = engine.add_source(ctx, uri="mem://s", trust=0.7)
    f = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=s.id)
    engine.supersede(ctx, f.id, new={"object": "Beta"})
    engine.record_decision(ctx, statement="d", evidence=[
        engine.facts_for(ctx, subject="Alice", believed_only=True)[0].id])


def test_backup_restore_roundtrip(tmp_path) -> None:
    ctx = Principal(tenant="t", agent="a", namespace="n")
    src_path = tmp_path / "live.db"
    bak_path = tmp_path / "backup.db"

    store = SQLiteStore(src_path)
    eng = Engine(store, clock=ManualClock())
    _populate(eng, ctx)

    head_before = store.head().entry_hash
    count_before = store.event_count()
    # anchor to a fixed valid-time so the assertion is independent of any engine clock
    current_before = eng.as_of(ctx, "2026-09-01", subject="Alice", predicate="works_at")

    store.backup(bak_path)  # hot, consistent snapshot
    eng.close()

    # destroy the original DB (and its WAL sidecars)
    for suffix in ("", "-wal", "-shm"):
        p = str(src_path) + suffix
        if os.path.exists(p):
            os.remove(p)
    assert not os.path.exists(src_path)

    # restore = open the backup
    restored = SQLiteStore(bak_path)
    reng = Engine(restored, clock=ManualClock())
    assert restored.event_count() == count_before
    assert restored.head().entry_hash == head_before
    assert reng.verify_integrity() == count_before
    assert reng.as_of(ctx, "2026-09-01", subject="Alice", predicate="works_at") == current_before
    assert current_before == "Beta"

    # can keep writing on the restored DB, chain continues cleanly
    reng.assert_fact(ctx, subject="Bob", predicate="works_at", object="Gamma")
    assert reng.verify_integrity() == count_before + 1
    reng.close()
