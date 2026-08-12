"""Knowledge Spaces — the visibility lattice, orthogonal to the tenant boundary (EPISTEMOS-04).

A **tenant** is the hard isolation boundary (whose data this is). A **space** is a visibility
container within a tenant (who may see it). The two are orthogonal: a `TEAM`-visible object still
belongs to exactly one tenant and is never visible to another tenant. This module owns the value
types; enforcement lives in :mod:`epistemos.authz` and the engine.

Design invariants (mission EPISTEMOS-04, and `docs/collaboration/KNOWLEDGE_SPACES.md`):

* **PRIVATE is the bottom and the default.** An object with no explicit placement is private to
  its owner. Absence/unknown/invalid visibility resolves to ``PRIVATE`` — never ``PUBLIC``.
* **Visibility is a total order.** ``PRIVATE < TEAM < ORGANIZATION < COMMUNITY < PUBLIC``. The
  ordinal drives comparison (can this audience see that level); the space *name* drives membership.
* **``kind`` and ``visibility`` are distinct fields.** A tenant may hold several spaces at the
  same visibility level; the initial kinds map 1:1 to levels but the schema keeps them separate so
  the model can grow without reinterpreting a level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from ..errors import ValidationError

__all__ = [
    "Visibility",
    "KnowledgeSpace",
    "resolve_visibility",
    "PRIVATE_SPACES",
]

# An object whose ``spaces`` tuple is empty is PRIVATE to its owner — no space object required, so
# the local-first single-agent case needs zero configuration.
PRIVATE_SPACES: tuple[str, ...] = ()


class Visibility(IntEnum):
    """The visibility lattice. Ordered: a higher value is visible to a strictly larger audience."""

    PRIVATE = 0
    TEAM = 1
    ORGANIZATION = 2
    COMMUNITY = 3
    PUBLIC = 4

    def __str__(self) -> str:  # stable name in payloads/health
        return self.name


def resolve_visibility(value: Any) -> Visibility:
    """Coerce a visibility to the enum, failing **closed** on anything unusual.

    ``None`` / missing → ``PRIVATE``. An unknown or malformed value **raises** rather than
    guessing — never silently defaults *upward* (mission §5). Accepts enum, name, or ordinal.
    """
    if value is None:
        return Visibility.PRIVATE
    if isinstance(value, Visibility):
        return value
    if isinstance(value, bool):  # guard: bool is an int subclass, never a valid level
        raise ValidationError(f"invalid visibility {value!r}")
    if isinstance(value, int):
        try:
            return Visibility(value)
        except ValueError:
            raise ValidationError(f"unknown visibility ordinal {value!r}") from None
    if isinstance(value, str):
        try:
            return Visibility[value.strip().upper()]
        except KeyError:
            raise ValidationError(f"unknown visibility {value!r}") from None
    raise ValidationError(f"visibility must be a Visibility/str/int, got {type(value).__name__}")


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSpace:
    """A visibility container within a tenant.

    ``kind`` is the space *type* (a name from the initial lattice set); ``visibility`` is its
    *lattice level*. They are separate fields (mission §4) — the initial kinds align with levels but
    the model does not assume they must.
    """

    id: str
    tenant: str
    name: str
    kind: str  # e.g. "PRIVATE" | "TEAM" | "ORGANIZATION" | "COMMUNITY" | "PUBLIC"
    visibility: Visibility
    owner: str  # the agent that created/owns the space
    created_at: str
    policy: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValidationError("space requires a non-empty id and name")
        # normalize visibility through the fail-closed resolver
        object.__setattr__(self, "visibility", resolve_visibility(self.visibility))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": "space",  # the store object kind
            "space_kind": self.kind,
            "tenant": self.tenant,
            "namespace": self.metadata.get("namespace", "default"),
            "owner": self.owner,
            "created_at": self.created_at,
            "name": self.name,
            "visibility": int(self.visibility),
            "policy": dict(self.policy),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeSpace:
        meta = dict(d.get("metadata", {}))
        if "namespace" in d and "namespace" not in meta:
            meta["namespace"] = d["namespace"]
        return cls(
            id=d["id"],
            tenant=d["tenant"],
            name=d["name"],
            kind=d.get("space_kind", d.get("kind", "TEAM")),
            visibility=resolve_visibility(d.get("visibility")),
            owner=d["owner"],
            created_at=d.get("created_at", ""),
            policy=dict(d.get("policy", {})),
            metadata=meta,
        )
