"""Expansion handles (mission §21, §22) — EXPERIMENTAL.

A handle lets a consumer ask for a redundancy group's collapsed members without the maker
ever exposing raw private ids up front. Safety comes from two rules:

1. **The token is opaque and carries nothing.** It is a random id; the private ids it stands for
   live only in a server-side registry keyed by the :class:`~epistemos.core.Engine`. A consumer
   cannot read ids out of the token, forge one, or point it at another group.
2. **Redemption re-authorizes, live.** ``expand`` binds the handle to the *identity* that minted it
   (tenant / agent / namespace) and to a temporal snapshot (``as_of``). On redemption it re-checks
   the presenting principal's fingerprint AND re-runs ``Engine.is_readable`` for every member at the
   bound snapshot. Capabilities are deliberately NOT baked in — a since-revoked reader is refused,
   because authorization is evaluated now, not when the handle was minted.

Result: a stale, revoked, cross-principal, or cross-tenant handle yields nothing it should not
(``STALE_EXPANSION_PRIVATE_LEAK = 0``). Handles are per-engine; a handle from one engine is unknown
to another. This is not a stable feature yet (ADR-042).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from ..identity import Principal

if TYPE_CHECKING:
    from ..core import Engine

__all__ = ["ExpansionRegistry", "registry_for", "principal_fingerprint"]


def principal_fingerprint(p: Principal) -> str:
    """Identity binding for a handle: tenant / agent / namespace. NOT capabilities — those are
    re-evaluated live on redemption so a revoked reader is refused."""
    return f"{p.tenant}/{p.agent}/{p.namespace}"


@dataclass
class _Handle:
    fingerprint: str
    tenant: str
    at_tx: str | None
    member_ids: tuple[str, ...]
    group_kind: str


@dataclass
class ExpansionRegistry:
    """Per-engine store of opaque handles. Thread-safe."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _handles: dict[str, _Handle] = field(default_factory=dict)

    def mint(self, principal: Principal, *, member_ids: list[str], at_tx: str | None,
             group_kind: str) -> str:
        token = "xph_" + uuid.uuid4().hex
        h = _Handle(fingerprint=principal_fingerprint(principal), tenant=principal.tenant,
                    at_tx=at_tx, member_ids=tuple(member_ids), group_kind=group_kind)
        with self._lock:
            self._handles[token] = h
        return token

    def peek(self, token: str) -> _Handle | None:
        with self._lock:
            return self._handles.get(token)


# One registry per Engine, created lazily. A WeakKeyDictionary means handles vanish when the
# engine is garbage-collected and never bleed between engines.
_REGISTRIES: WeakKeyDictionary[Engine, ExpansionRegistry] = WeakKeyDictionary()
_REGISTRIES_LOCK = threading.Lock()


def registry_for(engine: Engine) -> ExpansionRegistry:
    with _REGISTRIES_LOCK:
        reg = _REGISTRIES.get(engine)
        if reg is None:
            reg = ExpansionRegistry()
            _REGISTRIES[engine] = reg
        return reg


def expand(engine: Engine, principal: Principal, token: str) -> dict[str, Any]:
    """Redeem a handle. Returns the readable members at the bound snapshot, or an empty set with a
    reason — never a private object. Raises nothing that distinguishes "wrong principal" from
    "unknown handle" (no existence oracle): both yield ``members: []``, ``authorized: false``."""
    from .wire import project_object  # local import: wire depends on nothing here at import time

    reg = registry_for(engine)
    h = reg.peek(token)
    fp = principal_fingerprint(principal)
    # Unknown handle OR bound to a different identity OR different tenant -> refuse identically.
    if h is None or h.fingerprint != fp or h.tenant != principal.tenant:
        return {"handle": token, "authorized": False, "members": [],
                "reason": "unknown_or_unauthorized_handle"}
    members: list[dict[str, Any]] = []
    for oid in h.member_ids:
        obj = engine.store.get_object(oid)
        # Re-authorize LIVE for the presenting principal at the bound snapshot. Revoked access,
        # retraction, or a space change since minting all drop the member here.
        if obj is None or not engine.is_readable(principal, obj):
            continue
        members.append(project_object(engine, principal, obj, role="history", at_tx=h.at_tx))
    complete = len(members) == len(h.member_ids)
    return {"handle": token, "authorized": True, "group_kind": h.group_kind,
            "members": members, "complete": complete,
            "reason": None if complete else "some_members_no_longer_readable"}
