"""Internal utilities: canonical serialization, hashing, time, ids.

Kept dependency-free (standard library only) and side-effect-free. Everything that
must be reproducible across processes (content hashes, the event chain) flows through
:func:`canonical_json` so the byte representation is stable.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "canonical_json",
    "sha256_hex",
    "hash_obj",
    "now_utc",
    "to_iso",
    "parse_instant",
    "new_id",
    "Clock",
]

Clock = Callable[[], datetime]


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, tight separators, UTF-8, no NaN.

    This is the single canonical byte representation used for every content hash and
    for the tamper-evident event chain. Do not "prettify" it.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj: Any) -> str:
    """Content hash of an arbitrary JSON-serializable object."""
    return sha256_hex(canonical_json(obj))


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_iso(dt: datetime) -> str:
    """UTC ISO-8601 with a trailing ``Z``. Naive datetimes are treated as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_instant(value: str | datetime | None) -> datetime | None:
    """Parse a date or datetime into a UTC-aware datetime. ``None`` stays ``None``.

    Accepts ``YYYY-MM-DD``, full ISO-8601, and a trailing ``Z``. A bare date is
    interpreted as midnight UTC. Raises ``ValueError`` on anything else — fail closed
    rather than silently coercing garbage into a timestamp.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):  # pragma: no cover - defensive
        raise ValueError(f"not a timestamp: {value!r}")
    text = value.strip()
    if not text:
        raise ValueError("empty timestamp")
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 instant: {value!r}") from exc
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def new_id(prefix: str) -> str:
    """Opaque, collision-resistant id with a human-readable type prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"
