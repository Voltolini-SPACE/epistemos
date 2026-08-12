"""Authorization pipeline for Knowledge Spaces (EPISTEMOS-04).

The knowledge firewall every shared read/write passes through:

    IDENTITY -> TENANT -> SPACE -> CAPABILITY -> POLICY -> AUTHORIZED

Failure at any stage is ``DENY`` (fail closed). This module is **pure**: it decides access given
the projected space/grant state, which the engine supplies. Grants are **server-side** state
(projected from ``capability_granted``/``capability_revoked`` ledger events) — never taken from a
caller-supplied ``Principal`` field, so a client cannot claim a membership it was not granted
(the A-01/A-11 lesson: identity/authority come from sealed state, not the request).

The read decision, in words:

* An object with **no explicit placement** (``spaces == ()``) is PRIVATE to its owner: readable
  only by ``owner`` within the same ``(tenant, namespace)`` (or ``admin``). This is the fail-closed
  default and reproduces the v0.3 single-agent case exactly.
* An object placed in one or more spaces is readable if the principal can access **any** of them:
  a ``TEAM`` space if the principal owns it or is a granted member; an ``ORGANIZATION`` (or higher)
  space if it is in the principal's tenant (tenant-wide); a ``PRIVATE`` space only by its owner.
* ``admin`` overrides. A cross-tenant object is never readable. A dangling placement (space id with
  no space object) grants nothing (fail closed).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..spaces import Visibility

__all__ = ["can_read_object", "SpaceResolver", "MemberCheck"]

# space_id -> visibility level + owner + tenant  (the fields the decision needs)
SpaceResolver = Callable[[str], "tuple[Visibility, str, str] | None"]
# (space_id, agent) -> is the agent a granted member (has been granted any capability on the space)?
MemberCheck = Callable[[str, str], bool]


def can_read_object(
    principal: Any,
    obj: dict[str, Any],
    *,
    space_of: SpaceResolver,
    is_member: MemberCheck,
) -> bool:
    """Can ``principal`` read ``obj``? Pure; ``space_of``/``is_member`` read projected state."""
    # TENANT — hard boundary, never crossed.
    if obj.get("tenant") != principal.tenant:
        return False
    if "admin" in principal.capabilities:
        return True
    obj_spaces = tuple(obj.get("spaces") or ())
    if not obj_spaces:
        # implicit PRIVATE space: only the owner, and only within its own namespace.
        return bool(
            obj.get("owner") == principal.agent
            and obj.get("namespace") == principal.namespace
        )
    # explicit placement(s): readable if ANY placed space is accessible.
    for sid in obj_spaces:
        resolved = space_of(sid)
        if resolved is None:
            continue  # dangling placement -> no access (fail closed)
        vis, owner, tenant = resolved
        if tenant != principal.tenant:
            continue  # a space is within one tenant; never cross it
        if vis >= Visibility.ORGANIZATION:
            return True  # ORG / COMMUNITY / PUBLIC are tenant-wide readable (federation is future)
        if vis == Visibility.TEAM and (owner == principal.agent or is_member(sid, principal.agent)):
            return True
        if vis == Visibility.PRIVATE and owner == principal.agent:
            return True
    return False
