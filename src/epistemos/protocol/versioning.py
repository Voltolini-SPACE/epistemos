"""EPCTX protocol versioning rules (mission §4).

The wire is ``protocol_version = "EPCTX/1"``. Compatibility is by **major**: an ``EPCTX/1.x`` maker
may add *optional* fields; a consumer built for ``EPCTX/1`` MUST ignore fields it cannot recognize
rather than fail (forward compatibility). A change that removes or repurposes a required field is
*breaking* and only allowed in ``EPCTX/2`` with its own ADR.

This module is the single authority on: the version string, the required-field set, and the
tolerance function a conservative consumer uses.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "PROTOCOL_VERSION",
    "MAJOR",
    "REQUIRED_TOP_LEVEL",
    "is_compatible",
    "parse_version",
    "assert_required",
]

PROTOCOL_VERSION = "EPCTX/1"
MAJOR = 1

# Top-level fields a conforming EPCTX/1 document MUST carry. Consumers may rely on these existing.
# Everything else (metadata, expansion, tokens_by_section, integrity extras) is optional and a
# consumer that does not understand an optional field MUST ignore it (§4, §33).
REQUIRED_TOP_LEVEL = (
    "protocol_version",
    "request",
    "context",
    "contradictions",
    "temporal",
    "completeness",
    "provenance",
    "token_estimate",
    "integrity",
)


def parse_version(version: str) -> tuple[int, int]:
    """``"EPCTX/1"`` -> (1, 0); ``"EPCTX/1.3"`` -> (1, 3). Raises on a non-EPCTX string."""
    if not version.startswith("EPCTX/"):
        raise ValueError(f"not an EPCTX version: {version!r}")
    rest = version.split("/", 1)[1]
    parts = rest.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
    return major, minor


def is_compatible(producer_version: str, consumer_major: int = MAJOR) -> bool:
    """A consumer for ``consumer_major`` can read any document of the same major. Newer minors add
    only optional fields, so they stay readable; a different major does not."""
    try:
        major, _ = parse_version(producer_version)
    except (ValueError, IndexError):
        return False
    return major == consumer_major


def assert_required(document: dict[str, Any]) -> None:
    """Raise ``ValueError`` if a required top-level field is missing. Used by producers (self-check)
    and by strict consumers; lenient consumers just ignore unknown *optional* fields."""
    missing = [f for f in REQUIRED_TOP_LEVEL if f not in document]
    if missing:
        raise ValueError(f"EPCTX document missing required fields: {missing}")
