"""Canonical serialization and integrity for EPCTX/1 (mission §5, §6).

One logical context must serialize to one byte string, so a ``context_hash`` is meaningful and
runtimes agree. We use **canonical JSON**: UTF-8, sorted keys, no insignificant whitespace, and
``ensure_ascii=False`` so text compares by real characters, not escapes. No pickle,
no runtime-specific binary format (§5).

Integrity is a plain content digest, not cryptography (§6): ``context_hash`` = SHA-256 over the
canonical JSON of the document *without* its own ``integrity`` block. It detects alteration in
transit or storage. Signing, if it ever comes, is a separate port over this same canonical form.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["canonical_json", "canonical_bytes", "context_hash", "HASH_ALGO"]

HASH_ALGO = "sha256/canonical-json-1"


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, real Unicode. Same logical value in →
    same string out (§5), given no intentionally-variable fields (ids/timestamps) differ."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def canonical_bytes(obj: Any) -> bytes:
    return canonical_json(obj).encode("utf-8")


def context_hash(document: dict[str, Any]) -> str:
    """SHA-256 over the canonical form of the document with any ``integrity`` block removed,
    so the hash never depends on itself. Returned as ``"<algo>:<hex>"``."""
    body = {k: v for k, v in document.items() if k != "integrity"}
    digest = hashlib.sha256(canonical_bytes(body)).hexdigest()
    return f"{HASH_ALGO}:{digest}"
