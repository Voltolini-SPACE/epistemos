"""Crash-recovery worker: writes facts forever in their own transactions until killed.

Run as a subprocess by tests/chaos/test_chaos.py, then SIGKILL'd mid-write. Because the
SQLite store uses WAL + synchronous=FULL and each write is its own atomic transaction, a
kill leaves the database at the last committed event (never a partial one).
"""

from __future__ import annotations

import sys

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore


def main(path: str) -> None:
    engine = Engine(SQLiteStore(path))
    ctx = Principal(tenant="t", agent="a", namespace="n")
    i = 0
    while True:
        engine.assert_fact(ctx, subject="A", predicate="p", object=str(i))
        i += 1


if __name__ == "__main__":
    main(sys.argv[1])
