"""Fixtures for the panel boundary tests. A multi-principal corpus with a PRIVATE object whose
marker (``SECRETXYZ``) must never appear in any surface an unauthorized principal can reach."""
from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.api.panel import PanelService
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import MemoryStore

SECRET = "SECRETXYZ"
TENANT = "acme"
NS = "kb"


def principal(agent: str, *, tenant: str = TENANT, ns: str = NS,
              extra: frozenset[str] = frozenset()) -> Principal:
    return Principal(tenant=tenant, agent=agent, namespace=ns, capabilities=_DEFAULT_CAPS | extra)


@pytest.fixture
def corpus():
    """(engine, panel, ids) with alice/bob/curator/outsider and a private claim only alice sees."""
    eng = Engine(MemoryStore())
    panel = PanelService(eng)
    alice = principal("alice", extra=frozenset({"knowledge.share"}))
    bob = principal("bob")
    curator = principal("curator", extra=frozenset({"knowledge.accept"}))
    outsider = principal("mallory", tenant="evilcorp")  # different tenant

    team = eng.create_space(alice, name="team", visibility="TEAM")
    for a in ("bob", "curator"):
        eng.grant_capability(alice, space_id=team.id, agent=a)
    src = eng.add_source(alice, uri="https://public/src", trust=0.8)
    eng.share(alice, src.id, into=team.id)
    shared = eng.create_claim(alice, subject="Shared", predicate="is", object="visible",
                              space=team.id, source=src.id)
    ev = eng.create_evidence(alice, title="shared doc", uri="https://public/doc", space=team.id)
    eng.attach_evidence(alice, evidence_id=ev.id, to_claim=shared.id, relation="supports")
    eng.review_claim(bob, shared.id, verdict="confirm")

    # PRIVATE to alice — nobody else may see it or its marker in ANY surface
    secret_claim = eng.create_claim(alice, subject="Secret", predicate="is", object=SECRET)
    secret_ev = eng.create_evidence(alice, title=SECRET, uri="https://secret/x")

    ids = {"team": team.id, "shared": shared.id, "shared_ev": ev.id,
           "secret_claim": secret_claim.id, "secret_ev": secret_ev.id,
           "alice": alice, "bob": bob, "curator": curator, "outsider": outsider}
    yield eng, panel, ids
    eng.close()
