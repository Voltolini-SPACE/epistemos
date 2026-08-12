"""A REAL demo corpus for the panel — real EPISTEMOS objects, not mocks (mission §36).

Everything here is created through the **public, authorized Engine API**: real sources, entities,
facts, claims, evidence, reviews, decisions and spaces, persisted in the real store and appended to
the real hash-chained ledger. The panel then reads them through the real authorized boundary. This
is an isolated *fixture* module (never on the production read path); a deployment points the panel
at its own live Engine instead of calling :func:`seed`.

The corpus is deliberately shaped to exercise every screen and to make authorization *visible*: a
PRIVATE claim only ``alice`` can read sits next to the shared research space, so a screenshot as
``bob`` proves the private object never appears in his graph, search, counts or stream.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import Engine
from ..identity import _DEFAULT_CAPS, Principal


@dataclass(frozen=True)
class DemoIdentities:
    tokens: dict[str, Principal]
    identities: list[dict[str, str]]  # {agent, label} for the demo login picker (no tokens exposed)


_TENANT = "epistemos"
_NS = "kb"


def _p(agent: str, *, caps: frozenset[str] = _DEFAULT_CAPS) -> Principal:
    return Principal(tenant=_TENANT, agent=agent, namespace=_NS, capabilities=caps)


def make_identities() -> DemoIdentities:
    """The demo principals + their bearer tokens (tokens are demo-only, printed at launch)."""
    cur_caps = _DEFAULT_CAPS | {
        "knowledge.accept", "knowledge.promote", "decide", "knowledge.share"}
    curator = _p("curator", caps=cur_caps)
    hermes = _p("hermes", caps=_DEFAULT_CAPS | {"decide", "knowledge.share"})
    tokens = {
        "demo-alice": _p("alice"),
        "demo-bob": _p("bob"),
        "demo-hermes": hermes,
        "demo-curator": curator,
    }
    identities = [
        {"agent": "curator", "label": "Curator — review + acceptance", "token": "demo-curator"},
        {"agent": "hermes", "label": "Hermes — ingesting agent", "token": "demo-hermes"},
        {"agent": "alice", "label": "Alice — analyst (private claim)", "token": "demo-alice"},
        {"agent": "bob", "label": "Bob — team member (no private access)", "token": "demo-bob"},
    ]
    return DemoIdentities(tokens=tokens, identities=identities)


def seed(engine: Engine, identities: DemoIdentities) -> dict[str, str]:
    """Build the real corpus. Returns a small id map (handy for tests). Idempotent-ish: intended for
    a fresh in-memory or empty store."""
    t = identities.tokens
    alice, bob = t["demo-alice"], t["demo-bob"]
    hermes, curator = t["demo-hermes"], t["demo-curator"]

    # -- spaces: a shared research team + an org-wide space (owned by curator) ----------------
    research = engine.create_space(curator, name="Research", visibility="TEAM")
    for a in ("alice", "bob", "hermes", "demo-feed"):  # demo-feed = the optional live generator
        engine.grant_capability(curator, space_id=research.id, agent=a)
    org = engine.create_space(curator, name="Organization", visibility="ORGANIZATION")

    # -- sources with varied authority (trust is authority, NOT truth) ------------------------
    sec = engine.add_source(hermes, uri="https://sec.gov/edgar/filing-8821", source_kind="document",
                            trust=0.95)
    news = engine.add_source(hermes, uri="https://newswire.example/acq-2026",
                             source_kind="document", trust=0.55)
    rumor = engine.add_source(hermes, uri="https://forum.example/thread/991", source_kind="note",
                              trust=0.15)
    internal = engine.add_source(alice, uri="memo://board/2026-07", source_kind="document",
                                 trust=0.8)

    # the research backbone (sources, entities, facts) is shared into the team space so the whole
    # team sees a connected graph. The private claim + its own source/evidence stay PRIVATE below.
    def share(obj):
        engine.share(hermes, obj.id, into=research.id)
        return obj

    for s in (sec, news, rumor):
        share(s)

    # -- entities + relations (the graph backbone) --------------------------------------------
    cx = share(engine.add_entity(hermes, name="Company X", entity_type="organization"))
    cy = share(engine.add_entity(hermes, name="Company Y", entity_type="organization"))
    cz = share(engine.add_entity(hermes, name="Company Z", entity_type="organization"))
    share(engine.add_relation(hermes, source_entity=cx.id, target_entity=cy.id,
                              rel_type="competitor"))
    share(engine.add_relation(hermes, source_entity=cy.id, target_entity=cz.id,
                              rel_type="subsidiary"))

    # -- facts (believed knowledge) -----------------------------------------------------------
    share(engine.assert_fact(hermes, subject="Company X", predicate="sector", object="fintech",
                             source=sec.id, confidence=0.9))
    share(engine.assert_fact(hermes, subject="Company Y", predicate="headquarters", object="Lisbon",
                             source=sec.id))

    # -- the flagship contested claim: X acquired Y -------------------------------------------
    acq = engine.create_claim(hermes, subject="Company X", predicate="acquired", object="Company Y",
                              claimant="analyst_jo", contributor_kind="human", source=sec.id,
                              space=research.id, metadata={"deal": "2026-Q3"})
    ev_filing = engine.create_evidence(hermes, evidence_kind="document", title="SEC 8-K filing",
                                       uri="https://sec.gov/edgar/8k", content_hash="a1b2c3",
                                       origin="SEC", space=research.id)
    ev_news = engine.create_evidence(hermes, evidence_kind="document", title="Newswire report",
                                     uri="https://newswire.example/acq", origin="Newswire",
                                     space=research.id)
    ev_denial = engine.create_evidence(hermes, evidence_kind="document",
                                       title="Company Y press denial",
                                       uri="https://companyy.example/press/denial",
                                       origin="Company Y", space=research.id)
    engine.attach_evidence(hermes, evidence_id=ev_filing.id, to_claim=acq.id, relation="supports")
    engine.attach_evidence(hermes, evidence_id=ev_news.id, to_claim=acq.id, relation="supports")
    engine.attach_evidence(hermes, evidence_id=ev_denial.id, to_claim=acq.id,
                           relation="contradicts")
    engine.review_claim(bob, acq.id, verdict="confirm", rationale="Filing is authentic and clear.")
    engine.review_claim(curator, acq.id, verdict="dispute",
                        rationale="Target denies; await regulatory confirmation.")

    # -- an accepted claim (governed) ---------------------------------------------------------
    rev = engine.create_claim(hermes, subject="Company Z", predicate="revenue_2025",
                              object="$1.2B", source=sec.id, space=research.id)
    ev_10k = engine.create_evidence(hermes, evidence_kind="document", title="Company Z 10-K",
                                    uri="https://sec.gov/edgar/10k", content_hash="d4e5f6",
                                    origin="SEC", space=research.id)
    engine.attach_evidence(hermes, evidence_id=ev_10k.id, to_claim=rev.id, relation="supports")
    engine.review_claim(bob, rev.id, verdict="confirm", rationale="Matches audited statement.")
    engine.review_claim(alice, rev.id, verdict="confirm", rationale="Cross-checked.")
    engine.accept_claim(curator, rev.id, reason="Two independent confirmations vs audited 10-K.")

    # -- a retracted claim --------------------------------------------------------------------
    bad = engine.create_claim(hermes, subject="Company X", predicate="ceo", object="Jane Roe",
                              source=rumor.id, space=research.id)
    engine.review_claim(bob, bad.id, verdict="reject", rationale="Sourced from an anonymous forum.")
    engine.retract_claim(hermes, bad.id, reason="Source unreliable; superseded by filing.")

    # -- a supported-but-unaccepted claim -----------------------------------------------------
    hire = engine.create_claim(alice, subject="Company Y", predicate="hired", object="new CFO",
                               source=news.id, space=research.id)
    engine.review_claim(bob, hire.id, verdict="confirm", rationale="Announced publicly.")

    # -- a decision with lineage --------------------------------------------------------------
    engine.record_decision(curator, statement="Flag Company X acquisition exposure for review",
                           evidence=[ev_filing.id], outcome="escalated", reversible=True,
                           metadata={"space": research.id})

    # -- an ORG-promoted, org-wide claim ------------------------------------------------------
    engine.create_claim(curator, subject="Market", predicate="trend",
                        object="fintech consolidation", source=news.id, space=org.id)

    # -- a PRIVATE claim only alice can read (authorization demo, §33) ------------------------
    secret = engine.create_claim(alice, subject="Company X", predicate="internal_target",
                                 object="Company W (confidential)", source=internal.id)
    engine.create_evidence(alice, evidence_kind="document", title="Board memo (confidential)",
                           uri="memo://board/w", origin="Board")

    return {
        "research_space": research.id, "org_space": org.id,
        "flagship_claim": acq.id, "accepted_claim": rev.id, "retracted_claim": bad.id,
        "private_claim": secret.id,
    }
