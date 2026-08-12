"""EPISTEMOS — sovereign context, memory, provenance and decision-lineage engine.

Public API. The core is local-first, zero-egress and model-agnostic: importing this
package pulls in only the standard library.
"""

from __future__ import annotations

from .core import Engine, EngineLimits
from .errors import (
    AuthorizationError,
    ConflictError,
    EpistemosError,
    IdentityError,
    IntegrityError,
    NotFoundError,
    SchemaError,
    TemporalError,
    TenantIsolationError,
    ValidationError,
)
from .identity import Principal
from .model import (
    SCHEMA_VERSION,
    BeliefStatus,
    Decision,
    Document,
    Entity,
    Episode,
    Fact,
    MemoryClass,
    Observation,
    Relation,
    Source,
)
from .providers import ModelProvider, NullModelProvider
from .retrieval import Retriever, Weights
from .storage import MemoryStore, SQLiteStore, Store, open_store

__version__ = "0.3.0"

__all__ = [
    "__version__",
    "Engine",
    "EngineLimits",
    "Principal",
    # model
    "SCHEMA_VERSION",
    "Fact",
    "Source",
    "Entity",
    "Relation",
    "Decision",
    "Episode",
    "Observation",
    "Document",
    "BeliefStatus",
    "MemoryClass",
    # storage
    "Store",
    "MemoryStore",
    "SQLiteStore",
    "open_store",
    # providers / retrieval
    "ModelProvider",
    "NullModelProvider",
    "Retriever",
    "Weights",
    # errors
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
]
