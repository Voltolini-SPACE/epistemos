"""EPISTEMOS — sovereign context, memory, provenance and decision-lineage engine.

Public API. The core is local-first, zero-egress and model-agnostic: importing this
package pulls in only the standard library.
"""

from __future__ import annotations

from .claims import (
    BeliefState,
    Claim,
    ClaimStatus,
    ContributorKind,
    Evidence,
    EvidenceKind,
    EvidenceRelation,
    Review,
    Verdict,
)
from .claims.policy import LocalDefaultPolicy, Policy, PolicyDecision, PolicyRequest
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
from .ingest import (
    BUILTIN_RULES,
    CompilationResult,
    Compiler,
    Extraction,
    PatternRule,
    Rule,
    Span,
    compile_text,
)
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
from .receipt import RECEIPT_VERSION, ReceiptChain, RetrievalReceipt
from .retrieval import Retriever, Weights
from .spaces import KnowledgeSpace, Visibility
from .storage import MemoryStore, SQLiteStore, Store, open_store

__version__ = "0.7.0"

__all__ = [
    "__version__",
    "BUILTIN_RULES",
    "CompilationResult",
    "Compiler",
    "Extraction",
    "PatternRule",
    "Rule",
    "Span",
    "compile_text",
    "Engine",
    "EngineLimits",
    "RECEIPT_VERSION",
    "ReceiptChain",
    "RetrievalReceipt",
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
    # knowledge spaces (EPISTEMOS-04)
    "KnowledgeSpace",
    "Visibility",
    # collaborative claims (EPISTEMOS-05)
    "Claim",
    "Evidence",
    "Review",
    "ClaimStatus",
    "BeliefState",
    "Verdict",
    "EvidenceRelation",
    "EvidenceKind",
    "ContributorKind",
    "Policy",
    "PolicyRequest",
    "PolicyDecision",
    "LocalDefaultPolicy",
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
