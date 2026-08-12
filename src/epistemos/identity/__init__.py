"""Identity, tenancy and authorization — fail-closed by construction.

Every read and write into EPISTEMOS carries an explicit :class:`Principal`
(tenant + agent + namespace, plus optional human principal and capabilities).
There is no ambient/implicit identity: an operation with no principal is refused.

EPISTEMOS is **not** a policy authority (that is NOMOS). This module enforces the
two invariants EPISTEMOS must own regardless of any external authority:

* **tenant/namespace isolation** — data written under one tenant/namespace is never
  visible or mutable under another;
* **capability gating hooks** — a place for a future NOMOS adapter to attenuate
  what a principal may do, defaulting to "the principal may act within its own scope".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from ..errors import AuthorizationError, IdentityError, TenantIsolationError, ValidationError

__all__ = ["Principal", "Capability", "validate_name"]

# Names identify tenants, agents, namespaces, subjects. They appear in storage keys and
# scoping predicates, so they must be simple and free of path/wildcard/whitespace tricks.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-:]{0,127}$")
_TRAVERSAL = ("..", "/", "\\", "\x00", "*", "%", "\n", "\r", "\t")


def validate_name(value: str, *, what: str) -> str:
    """Validate a tenant/agent/namespace identifier. Fail closed on anything unusual."""
    if not isinstance(value, str):
        raise ValidationError(f"{what} must be a string, got {type(value).__name__}")
    if not value:
        raise ValidationError(f"{what} must not be empty")
    if any(t in value for t in _TRAVERSAL):
        raise ValidationError(f"{what} contains an unsafe sequence: {value!r}")
    if not _NAME_RE.match(value):
        raise ValidationError(f"{what} is not a valid identifier: {value!r}")
    return value


class Capability(str):
    """A coarse capability token. Kept as an opaque string for forward-compatibility
    with the NOMOS capability model. EPISTEMOS never *grants* capabilities."""

    __slots__ = ()


# Default capabilities a principal has within its own scope when no external authority
# (NOMOS) is attenuating it. Reads and writes inside one's own tenant/namespace are
# allowed; destructive history operations are still explicit but permitted by default.
#
# EPISTEMOS-04: the collaborative capabilities — sharing a private object into a wider space,
# promoting it up the visibility lattice, and managing spaces/grants — are NOT in the default set.
# They fail closed: a principal cannot share/promote/publish or grant membership unless explicitly
# granted the capability, so no default-caps principal can move knowledge toward PUBLIC. (Creating a
# space and reading are convenience-safe and remain in the default set.)
_DEFAULT_CAPS = frozenset(
    {
        "read",
        "assert",
        "supersede",
        "retract",
        "contradict",
        "confirm",
        "decide",
        "ingest",
        "export",
        "space.create",  # anyone may create a space they own
        "space.read",
        # EPISTEMOS-05: contributing and reviewing are basic collaborative rights — a claim is a
        # contribution, never truth. The TRUTH gates (accepting a claim as knowledge, promoting
        # toward PUBLIC) are NOT default and stay fail-closed.
        "claim.create", "claim.read", "claim.review", "claim.confirm", "claim.dispute",
        "claim.retract",
        "evidence.create", "evidence.attach", "evidence.read",
    }
)

# The full capability vocabulary (mission §6). Roles (VISITOR/MEMBER/CONTRIBUTOR/REVIEWER/CURATOR/
# OWNER) are convenience *sets* of these; enforcement is always by capability, never by role name.
KNOWLEDGE_CAPABILITIES = frozenset(
    {
        "knowledge.read", "knowledge.search", "knowledge.contribute", "knowledge.share",
        "knowledge.review", "knowledge.promote", "knowledge.retract",
        "provenance.read", "history.read", "graph.traverse",
        "space.create", "space.read", "space.manage", "space.invite",
        # Collaborative claims (EPISTEMOS-05): contribution + review are basic rights.
        "claim.create", "claim.read", "claim.review", "claim.confirm", "claim.dispute",
        "claim.retract",
        "evidence.create", "evidence.attach", "evidence.read",
        "knowledge.accept",  # the governed truth gate — NOT in the default set
    }
)


@dataclass(frozen=True, slots=True)
class Principal:
    """The immutable identity context for a single call.

    ``tenant`` is the hard isolation boundary. ``agent`` distinguishes callers within a
    tenant (agent-scoped memory). ``namespace`` partitions knowledge within a tenant.
    ``principal`` is the optional human/service on whose behalf the agent acts.
    """

    tenant: str
    agent: str
    namespace: str = "default"
    principal: str | None = None
    capabilities: frozenset[str] = field(default_factory=lambda: _DEFAULT_CAPS)

    def __post_init__(self) -> None:
        validate_name(self.tenant, what="tenant")
        validate_name(self.agent, what="agent")
        validate_name(self.namespace, what="namespace")
        if self.principal is not None:
            validate_name(self.principal, what="principal")
        if not isinstance(self.capabilities, frozenset):
            object.__setattr__(self, "capabilities", frozenset(self.capabilities))

    # -- scope ---------------------------------------------------------------
    @property
    def scope(self) -> tuple[str, str]:
        """The (tenant, namespace) isolation key."""
        return (self.tenant, self.namespace)

    def with_namespace(self, namespace: str) -> Principal:
        return replace(self, namespace=validate_name(namespace, what="namespace"))

    # -- guards --------------------------------------------------------------
    def require(self, capability: str) -> None:
        """Raise unless the principal holds ``capability``. Fail closed on unknowns."""
        if capability not in self.capabilities:
            raise AuthorizationError(
                f"principal {self.agent}@{self.tenant} lacks capability {capability!r}"
            )

    def guard_scope(self, tenant: str, namespace: str) -> None:
        """Raise if ``(tenant, namespace)`` is outside this principal's scope."""
        if tenant != self.tenant:
            raise TenantIsolationError(
                f"cross-tenant access denied: {self.tenant!r} -> {tenant!r}"
            )
        if namespace != self.namespace:
            raise TenantIsolationError(
                f"cross-namespace access denied: {self.namespace!r} -> {namespace!r}"
            )

    def guard_owner(self, owner_agent: str, *, action: str) -> None:
        """Raise if a write would clobber another agent's owned object.

        Reads within a tenant/namespace are shared; *overwriting* another agent's
        object is refused unless the caller holds the ``admin`` capability.
        """
        if owner_agent != self.agent and "admin" not in self.capabilities:
            raise AuthorizationError(
                f"{action} denied: object owned by agent {owner_agent!r}, "
                f"caller is {self.agent!r}"
            )


def require_principal(principal: object) -> Principal:
    """Coerce/validate that a real principal was supplied. Fail closed."""
    if principal is None or not isinstance(principal, Principal):
        raise IdentityError("a valid Principal is required for every operation")
    return principal
