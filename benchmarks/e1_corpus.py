"""E-1 retrieval benchmark corpus — deterministic, vendored, independently grounded.

Ground truth here is **not** derived from any retriever. Documents are *generated* from an explicit
fact table, and every query is built from that same table, so the expected answer is known before
any search runs. Using retrieval output to label relevance would make the benchmark agree with
whatever it measures (mission §6).

Determinism: a fixed seed and a fixed template order. Regenerating produces byte-identical output,
asserted by a test. No network, no external corpus, no runtime dependency.

Layers (mission §5):
  A. synthetic       — controlled facts, perfect ground truth, edge cases
  B. semi-realistic  — contracts, policies, runbooks, reports, comms, document versions
  C. public real     — NOT INCLUDED. Vendoring third-party text would require per-source licence
                       provenance the benchmark cannot verify offline; declaring the gap is more
                       honest than shipping unattributed text. See docs/benchmarks/E1_CORPUS.md.
"""

from __future__ import annotations

import hashlib

# S311: `random` here seeds a *reproducible corpus*, never a secret. A CSPRNG would make the
# benchmark unrepeatable, which is the opposite of what it is for.
import random
from dataclasses import dataclass, field

SEED = 20260822
N_TARGET = 520

# ---------------------------------------------------------------------------
# Fact table — the source of truth for both documents and queries.

SERVICES = [
    ("payments-api", "payments", "card authorisation", "autorizacao de cartao",
     "autorizacion de tarjeta"),
    ("ledger-api", "ledger", "settlement recording", "registro de liquidacao",
     "registro de liquidacion"),
    ("fraud-scoring", "fraud", "risk scoring", "pontuacao de risco",
     "puntuacion de riesgo"),
    ("people-portal", "hr", "employee records", "registros de funcionarios",
     "registros de empleados"),
    ("billing-gateway", "billing", "invoice issuance", "emissao de faturas",
     "emision de facturas"),
    ("notify-hub", "comms", "message delivery", "entrega de mensagens",
     "entrega de mensajes"),
    ("audit-trail", "audit", "event archival", "arquivamento de eventos",
     "archivado de eventos"),
    ("identity-broker", "identity", "token issuance", "emissao de tokens",
     "emision de tokens"),
]

PEOPLE = [
    "Alice Martins", "Bruno Silva", "Carla Nunes", "Diana Reis", "Eduardo Lima",
    "Fernanda Costa", "Gabriel Souza", "Helena Dias", "Igor Ferreira", "Julia Moreira",
    "Karina Alves", "Lucas Pereira", "Marina Rocha", "Nuno Batista", "Olivia Cardoso",
]

REGIONS = ["eu-west", "us-east", "sa-east", "ap-south", "eu-central"]
TIERS = ["critical", "platinum", "standard", "experimental"]

#: (english, portuguese, spanish, [synonyms], [paraphrase cues])
CONCEPTS = [
    ("retention window", "janela de retencao", "ventana de retencion",
     ["retention period", "data retention", "storage duration"],
     ["how long do we keep the data", "for how long is information stored"]),
    ("holiday policy", "politica de ferias", "politica de vacaciones",
     ["leave policy", "vacation allowance", "time off entitlement"],
     ["how many days off do people get", "what is the time off entitlement"]),
    ("escalation path", "caminho de escalonamento", "ruta de escalamiento",
     ["escalation procedure", "on-call chain", "incident routing"],
     ["who do I call when it breaks", "who gets paged at night"]),
    ("restart procedure", "procedimento de reinicio", "procedimiento de reinicio",
     ["restart runbook", "recovery steps", "bounce instructions"],
     ["bring the service back up safely", "how to recover the process"]),
    ("rate limit", "limite de taxa", "limite de tasa",
     ["throttling policy", "request cap", "quota ceiling"],
     ["how many calls are allowed", "what caps the traffic"]),
    ("encryption standard", "padrao de criptografia", "estandar de cifrado",
     ["cipher policy", "crypto requirement", "key strength"],
     ["how is the data protected at rest", "what secures stored records"]),
    ("audit frequency", "frequencia de auditoria", "frecuencia de auditoria",
     ["review cadence", "inspection interval", "control testing schedule"],
     ["how often is this checked", "what is the review cadence"]),
    ("access approval", "aprovacao de acesso", "aprobacion de acceso",
     ["permission grant", "authorisation workflow", "entitlement review"],
     ["who signs off on permissions", "how does someone get access"]),
]

CONCEPT_VALUES = {
    "retention window": ["thirty days", "ninety days", "five years", "seven years"],
    "holiday policy": ["twenty-five days per year", "thirty days per year"],
    "escalation path": ["platform-team then the duty manager", "the on-call engineer"],
    "restart procedure": ["drain the node, wait for connections to close, then redeploy",
                          "stop the consumer, flush the queue, then restart"],
    "rate limit": ["one thousand requests per minute", "five hundred requests per minute"],
    "encryption standard": ["AES-256-GCM at rest", "ChaCha20-Poly1305 at rest"],
    "audit frequency": ["quarterly", "twice per year"],
    "access approval": ["two named approvers", "the service owner plus security"],
}


@dataclass(frozen=True, slots=True)
class Doc:
    doc_id: str
    title: str
    text: str
    tenant: str
    language: str
    layer: str
    version: int = 1
    #: (subject, predicate, object) triples this document genuinely asserts.
    facts: tuple[tuple[str, str, str], ...] = ()
    #: free-form labels the query builder keys on (concept names, service ids, people).
    topics: frozenset[str] = field(default_factory=frozenset)
    superseded_by: str | None = None
    conflicts_with: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Query:
    query_id: str
    query: str
    expected_documents: frozenset[str]
    category: str
    language: str
    tenant: str
    relevance_grade: int = 1
    temporal_constraint: str | None = None
    note: str = ""


# ---------------------------------------------------------------------------
# Document builders. Each returns text plus the facts it asserts, so ground truth
# is a by-product of construction rather than an interpretation of the output.


def _runbook(rng, svc, owner, deputy, region, tier, concept, value, lang):
    name, domain, en_purpose, pt_purpose, es_purpose = svc
    cname, cpt, ces, _syn, _para = concept
    if lang == "pt":
        purpose, cterm = pt_purpose, cpt
        body = (
            f"---\nResponsavel: {owner}\nServico: {name}\nNivel: {tier}\nRegiao: {region}\n---\n"
            f"# Runbook do {name}\n\n"
            f"O servico {name} executa {purpose} na regiao {region}.\n"
            f"{owner} trabalha na Acme. {owner} reporta para {deputy}.\n"
            f"{cterm.capitalize()}: {value}.\n"
        )
    elif lang == "es":
        purpose, cterm = es_purpose, ces
        body = (
            f"---\nResponsable: {owner}\nServicio: {name}\nNivel: {tier}\nRegion: {region}\n---\n"
            f"# Runbook de {name}\n\n"
            f"El servicio {name} ejecuta {purpose} en la region {region}.\n"
            f"{owner} trabaja en Acme. {owner} reporta a {deputy}.\n"
            f"{cterm.capitalize()}: {value}.\n"
        )
    else:
        purpose, cterm = en_purpose, cname
        body = (
            f"---\nOwner: {owner}\nService: {name}\nTier: {tier}\nRegion: {region}\n---\n"
            f"# {name} runbook\n\n"
            f"The {name} service performs {purpose} in the {region} region.\n"
            f"{owner} works at Acme. {owner} reports to {deputy}.\n"
            f"{cterm.capitalize()}: {value}.\n"
        )
    facts = (
        (name, "owner", owner),
        (name, "tier", tier),
        (name, "region", region),
        (owner, "reports_to", deputy),
        (name, cname.replace(" ", "_"), value),
    )
    return body, facts, frozenset({name, domain, cname, owner, deputy, region, tier})


def _policy(rng, concept, value, scope, lang):
    cname, cpt, ces, _syn, _para = concept
    term = {"pt": cpt, "es": ces}.get(lang, cname)
    if lang == "pt":
        body = (f"# Politica: {term}\n\nEscopo: {scope}.\n"
                f"A {term} definida para {scope} e {value}.\n"
                f"Excecoes exigem aprovacao formal registrada.\n")
    elif lang == "es":
        body = (f"# Politica: {term}\n\nAlcance: {scope}.\n"
                f"La {term} definida para {scope} es {value}.\n"
                f"Las excepciones requieren aprobacion formal registrada.\n")
    else:
        body = (f"# Policy: {term}\n\nScope: {scope}.\n"
                f"The {term} defined for {scope} is {value}.\n"
                f"Exceptions require a recorded formal approval.\n")
    return body, ((scope, cname.replace(" ", "_"), value),), frozenset({cname, scope})


def _report(rng, svc, region, quarter, lang):
    name = svc[0]
    incidents = rng.randint(0, 9)
    body = (f"# Quarterly report — {name} — {quarter}\n\n"
            f"Region: {region}\nIncidents recorded: {incidents}\n"
            f"The {name} service operated within its declared budget for {quarter}.\n"
            f"No change to ownership was recorded in this period.\n")
    facts = ((name, "incidents_" + quarter.lower(), str(incidents)),)
    return body, facts, frozenset({name, region})


def _noise(rng, idx, lang):
    """Adversarial: heavy query-vocabulary repetition, zero assertable facts."""
    filler = rng.choice([
        "This page is a placeholder and asserts nothing.",
        "Draft. TODO: replace with real content before review.",
        "Meeting notes: various options were discussed and nothing was decided.",
    ])
    terms = rng.sample(["retention", "policy", "owner", "service", "tier", "escalation",
                        "restart", "approval", "audit", "encryption", "limit", "region"], 8)
    body = (f"# Working notes {idx}\n\n{filler}\n"
            + " ".join(f"We mentioned {t} several times; {t} came up again regarding {t}."
                       for t in terms) + "\n")
    return body, (), frozenset()


# ---------------------------------------------------------------------------


def build_corpus() -> tuple[list[Doc], list[Query]]:
    rng = random.Random(SEED)  # noqa: S311 - reproducible corpus, never a secret
    docs: list[Doc] = []
    n = 0

    def add(prefix, title, text, tenant, lang, layer, facts, topics, **kw):
        nonlocal n
        n += 1
        docs.append(Doc(doc_id=f"{prefix}{n:04d}", title=title, text=text, tenant=tenant,
                        language=lang, layer=layer, facts=tuple(facts),
                        topics=frozenset(topics), **kw))
        return docs[-1]

    # -- Layer A/B: runbooks across services, languages and tenants ----------
    for svc in SERVICES:
        for lang in ("en", "pt", "es"):
            for tenant in ("acme", "globex"):
                for region in REGIONS[:3]:
                    owner = rng.choice(PEOPLE)
                    deputy = rng.choice([p for p in PEOPLE if p != owner])
                    tier = rng.choice(TIERS)
                    concept = rng.choice(CONCEPTS)
                    value = rng.choice(CONCEPT_VALUES[concept[0]])
                    text, facts, topics = _runbook(rng, svc, owner, deputy, region, tier,
                                                   concept, value, lang)
                    add("D", f"{svc[0]} runbook {region} {lang}", text, tenant, lang,
                        "semi-realistic", facts, topics)

    # -- policies -----------------------------------------------------------
    for concept in CONCEPTS:
        for lang in ("en", "pt", "es"):
            for scope in ("payments", "ledger", "hr", "audit"):
                value = rng.choice(CONCEPT_VALUES[concept[0]])
                text, facts, topics = _policy(rng, concept, value, scope, lang)
                add("D", f"policy {concept[0]} {scope} {lang}", text, "acme", lang,
                    "semi-realistic", facts, topics)

    # -- quarterly reports --------------------------------------------------
    for svc in SERVICES:
        for quarter in ("Q1", "Q2", "Q3", "Q4"):
            region = rng.choice(REGIONS)
            text, facts, topics = _report(rng, svc, region, quarter, "en")
            add("D", f"{svc[0]} report {quarter}", text, "acme", "en",
                "semi-realistic", facts, topics)

    # -- adversarial noise --------------------------------------------------
    for i in range(60):
        text, facts, topics = _noise(rng, i, "en")
        add("N", f"working notes {i}", text, "acme", "en", "synthetic", facts, topics)

    # -- CONFLICT pairs: same subject+predicate, incompatible objects --------
    conflict_pairs = []
    for i, concept in enumerate(CONCEPTS[:6]):
        cname = concept[0]
        v1, v2 = CONCEPT_VALUES[cname][0], CONCEPT_VALUES[cname][-1]
        scope = f"conflict-scope-{i}"
        a = add("C", f"conflict A {cname} {i}",
                f"# Standard {cname} (revision A)\n\nFor {scope} the {cname} is {v1}.\n",
                "acme", "en", "synthetic", ((scope, cname.replace(" ", "_"), v1),),
                {cname, scope})
        b = add("C", f"conflict B {cname} {i}",
                f"# Standard {cname} (revision B)\n\nFor {scope} the {cname} is {v2}.\n",
                "acme", "en", "synthetic", ((scope, cname.replace(" ", "_"), v2),),
                {cname, scope}, conflicts_with=a.doc_id)
        conflict_pairs.append((a, b, cname, scope))

    # -- TEMPORAL: current / historical / superseded / expired ---------------
    temporal_sets = []
    for i, concept in enumerate(CONCEPTS[:5]):
        cname = concept[0]
        vals = CONCEPT_VALUES[cname]
        scope = f"temporal-scope-{i}"
        old = add("T", f"temporal old {cname} {i}",
                  f"# {cname} schedule (historical)\n\n"
                  f"Between 2025-01-01 and 2026-03-01 the {cname} for {scope} was {vals[0]}.\n",
                  "acme", "en", "synthetic", ((scope, cname.replace(" ", "_"), vals[0]),),
                  {cname, scope}, valid_from="2025-01-01", valid_to="2026-03-01")
        new = add("T", f"temporal current {cname} {i}",
                  f"# {cname} schedule (current)\n\n"
                  f"From 2026-03-01 the {cname} for {scope} is {vals[-1]}.\n",
                  "acme", "en", "synthetic", ((scope, cname.replace(" ", "_"), vals[-1]),),
                  {cname, scope}, valid_from="2026-03-01")
        temporal_sets.append((old, new, cname, scope))

    # -- CROSS-REFERENCE: answer only reachable via a named dependency -------
    xref = []
    for i, svc in enumerate(SERVICES[:5]):
        upstream = svc[0]
        downstream = f"consumer-{i}"
        d = add("X", f"crossref {downstream}",
                f"---\nService: {downstream}\nDepends on: {upstream}\n---\n"
                f"The {downstream} service consumes the stream produced by {upstream}.\n"
                f"Escalation for {downstream} follows the {upstream} runbook.\n",
                "acme", "en", "synthetic", ((downstream, "depends_on", upstream),),
                {downstream, upstream})
        xref.append((d, upstream, downstream))

    # -- SYNONYM / PARAPHRASE targets: one term, stated only one way ---------
    synonym_targets = []
    for i, concept in enumerate(CONCEPTS):
        cname, _cpt, _ces, syns, paras = concept
        value = CONCEPT_VALUES[cname][0]
        scope = f"unique-scope-{i}"
        d = add("S", f"unique {cname} {i}",
                f"# Reference sheet {i}\n\nFor {scope}, the {cname} is {value}.\n"
                f"This value applies to every environment without exception.\n",
                "acme", "en", "synthetic", ((scope, cname.replace(" ", "_"), value),),
                {cname, scope})
        synonym_targets.append((d, cname, syns, paras))

    # -- pad to the target size with further runbooks -----------------------
    while len(docs) < N_TARGET:
        svc = rng.choice(SERVICES)
        owner = rng.choice(PEOPLE)
        deputy = rng.choice([p for p in PEOPLE if p != owner])
        concept = rng.choice(CONCEPTS)
        text, facts, topics = _runbook(rng, svc, owner, deputy, rng.choice(REGIONS),
                                       rng.choice(TIERS), concept,
                                       rng.choice(CONCEPT_VALUES[concept[0]]), "en")
        add("D", f"{svc[0]} runbook extra", text, "acme", "en", "semi-realistic", facts, topics)

    # =======================================================================
    # Queries. Every expected set is taken from the generation record above.
    queries: list[Query] = []
    q = 0

    def addq(text, expected, category, lang="en", tenant="acme", grade=1,
             temporal=None, note=""):
        nonlocal q
        q += 1
        queries.append(Query(query_id=f"Q{q:03d}", query=text,
                             expected_documents=frozenset(expected), category=category,
                             language=lang, tenant=tenant, relevance_grade=grade,
                             temporal_constraint=temporal, note=note))

    by_topic: dict[str, list[Doc]] = {}
    for d in docs:
        for t in d.topics:
            by_topic.setdefault(t, []).append(d)

    # EXACT (>=15): a literal service name, restricted to one tenant.
    for svc in SERVICES:
        name = svc[0]
        hits = [d.doc_id for d in by_topic.get(name, []) if d.tenant == "acme"]
        if hits:
            addq(name, hits, "exact")
    for person in PEOPLE[:8]:
        hits = [d.doc_id for d in by_topic.get(person, []) if d.tenant == "acme"]
        if hits:
            addq(person, hits, "exact")

    # MORPHOLOGICAL (>=15): inflected forms of terms that occur in the corpus.
    # Surfaces are inflections of terms that DO occur in the corpus; the topic key is what the
    # generator actually recorded, so a miss here is a corpus bug, not a retrieval result.
    morph = [("retentions", "retention window"), ("retained", "retention window"),
             ("holidays", "holiday policy"), ("escalating", "escalation path"),
             ("escalations", "escalation path"), ("restarting", "restart procedure"),
             ("restarts", "restart procedure"), ("limiting", "rate limit"),
             ("limits", "rate limit"), ("encrypting", "encryption standard"),
             ("encrypted", "encryption standard"), ("auditing", "audit frequency"),
             ("audits", "audit frequency"), ("approving", "access approval"),
             ("approvals", "access approval"), ("payments", "payments"),
             ("ledgers", "ledger"), ("frauds", "fraud")]
    for surface, topic in morph:
        hits = [d.doc_id for d in by_topic.get(topic, []) if d.tenant == "acme"]
        if hits:
            addq(surface, hits, "morphology", note=f"inflection of '{topic}'")
        else:  # pragma: no cover - guards against a silently empty category
            raise AssertionError(f"morphology topic {topic!r} has no documents")

    # SYNONYM (>=20)
    for d, cname, syns, _paras in synonym_targets:
        for s in syns:
            addq(s, [d.doc_id], "synonym",
                 note=f"document states only '{cname}'")

    # PARAPHRASE (>=25)
    for d, cname, _syns, paras in synonym_targets:
        for p in paras:
            addq(p, [d.doc_id], "paraphrase", note=f"document states only '{cname}'")
    for concept in CONCEPTS:
        cname, _cpt, _ces, _syns, paras = concept
        hits = [x.doc_id for x in by_topic.get(cname, []) if x.tenant == "acme"]
        if hits:
            for p in paras:
                addq(p, hits, "paraphrase", grade=1)

    # CROSS-LINGUAL (>=15): PT->EN, EN->PT, ES->EN, PT->ES
    for svc in SERVICES[:5]:
        _name, _dom, en, pt, es = svc
        pt_docs = [d.doc_id for d in docs if d.language == "pt" and _name in d.topics
                   and d.tenant == "acme"]
        en_docs = [d.doc_id for d in docs if d.language == "en" and _name in d.topics
                   and d.tenant == "acme"]
        es_docs = [d.doc_id for d in docs if d.language == "es" and _name in d.topics
                   and d.tenant == "acme"]
        if pt_docs:
            addq(en, pt_docs, "crosslingual", lang="en", note="EN query -> PT documents")
        if en_docs:
            addq(pt, en_docs, "crosslingual", lang="pt", note="PT query -> EN documents")
        if es_docs:
            addq(pt, es_docs, "crosslingual", lang="pt", note="PT query -> ES documents")

    # TEMPORAL (>=15)
    for old, new, cname, scope in temporal_sets:
        addq(f"{cname} {scope}", [old.doc_id, new.doc_id], "temporal",
             note="both the historical and the current statement are relevant")
        addq(f"current {cname} {scope}", [new.doc_id], "temporal", temporal="current")
        addq(f"{cname} {scope} in 2025", [old.doc_id], "temporal", temporal="historical")

    # CONFLICT (>=15)
    for a, b, cname, scope in conflict_pairs:
        addq(f"{cname} {scope}", [a.doc_id, b.doc_id], "conflict",
             note="BOTH sides must surface; silent resolution is a failure")
        addq(f"{scope}", [a.doc_id, b.doc_id], "conflict")
        addq(f"what is the {cname} for {scope}", [a.doc_id, b.doc_id], "conflict")

    # CROSS-REFERENCE (>=10)
    for d, upstream, downstream in xref:
        addq(f"what depends on {upstream}", [d.doc_id], "crossref")
        addq(f"{downstream} escalation", [d.doc_id], "crossref")

    # NOISE / ADVERSARIAL (>=20): a noise doc repeats the vocabulary but asserts nothing.
    for d, cname, _syns, _paras in synonym_targets:
        addq(f"{cname} reference sheet", [d.doc_id], "adversarial",
             note="noise documents repeat this vocabulary without asserting it")
    for concept in CONCEPTS:
        cname = concept[0]
        hits = [x.doc_id for x in by_topic.get(cname, []) if x.tenant == "acme"]
        if hits:
            addq(f"{cname} {cname} {cname}", hits, "adversarial",
                 note="term repetition must not let a placeholder outrank a real statement")
    for svc in SERVICES[:6]:
        hits = [d.doc_id for d in by_topic.get(svc[0], []) if d.tenant == "acme"]
        if hits:
            addq(f"{svc[0]} owner tier region", hits, "adversarial")

    return docs, queries


def corpus_digest(docs: list[Doc], queries: list[Query]) -> str:
    """Stable digest over the whole benchmark, so 'same corpus' is a checkable claim."""
    h = hashlib.sha256()
    for d in docs:
        h.update(f"{d.doc_id}|{d.tenant}|{d.language}|{d.content_hash}".encode())
    for qq in queries:
        h.update(f"{qq.query_id}|{qq.query}|{sorted(qq.expected_documents)}".encode())
    return h.hexdigest()


if __name__ == "__main__":
    d, q = build_corpus()
    from collections import Counter
    print(f"documents = {len(d)}   queries = {len(q)}")
    print(f"digest    = {corpus_digest(d, q)}")
    print("\nby category:", dict(sorted(Counter(x.category for x in q).items())))
    print("by language:", dict(sorted(Counter(x.language for x in d).items())))
    print("by tenant  :", dict(sorted(Counter(x.tenant for x in d).items())))
    print("by layer   :", dict(sorted(Counter(x.layer for x in d).items())))
