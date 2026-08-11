"""Exception hierarchy. Every failure mode is explicit so callers can fail closed.

The cardinal rule (mission §26): UNKNOWN != ALLOW. When tenancy, authorization,
source, schema or integrity cannot be determined, raise — never proceed.
"""

from __future__ import annotations

__all__ = [
    "EpistemosError",
    "ValidationError",
    "SchemaError",
    "IdentityError",
    "AuthorizationError",
    "TenantIsolationError",
    "NotFoundError",
    "ConflictError",
    "IntegrityError",
    "TemporalError",
    "StorageError",
    "EgressBlockedError",
]


class EpistemosError(Exception):
    """Base class for all EPISTEMOS errors."""


class ValidationError(EpistemosError):
    """Input failed validation (missing field, bad type, oversized, unsafe value)."""


class SchemaError(EpistemosError):
    """Persisted/imported data does not match a known, supported schema version."""


class IdentityError(EpistemosError):
    """The calling principal is missing or malformed. Fail closed."""


class AuthorizationError(EpistemosError):
    """The principal is known but not permitted to perform the operation."""


class TenantIsolationError(AuthorizationError):
    """A cross-tenant or cross-namespace boundary was violated. Fail closed."""


class NotFoundError(EpistemosError):
    """A referenced object does not exist within the caller's visible scope."""


class ConflictError(EpistemosError):
    """A concurrent modification or optimistic-lock conflict was detected."""


class IntegrityError(EpistemosError):
    """The event chain, a content hash, or a projection is inconsistent. Fail closed."""


class TemporalError(ValidationError):
    """A temporal interval or query is invalid (e.g. valid_to < valid_from)."""


class StorageError(EpistemosError):
    """The storage backend failed in a way the domain cannot recover from."""


class EgressBlockedError(EpistemosError):
    """Something attempted a network call from the zero-egress core."""
