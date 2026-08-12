"""Authorized read-model for the EPISTEMOS Panel (ADR-030/032).

The panel is a *consumer*; this module is the trusted server-side boundary that turns the Engine's
authorized primitives into the views the UI renders — listings, a knowledge **graph**, aggregate
**metrics**, a **timeline**, and per-object detail (claim/evidence/belief/explain). It is built on a
single rule:

    candidate  →  Engine.is_readable(principal, obj)  →  project (redacted)

Nothing is ever serialized to a consumer that ``is_readable`` does not pass. A graph **edge** is
emitted only when **both** endpoints are readable, so the graph never renders a stub that betrays a
hidden neighbour (``PRIVATE_GRAPH_LEAK = 0``). Belief/explain pass through from the core, which
already elides unreadable evidence/reviews/genealogy. The boundary may read ``store.objects``
directly (trusted server code); the invariant — enforced by tests — is that no object becomes part
of a response without passing the firewall.

This module contains **no** epistemological rule: belief is not recomputed here, visibility is not
evaluated here (only consulted via ``is_readable``), and no mutation is offered — the UI grants
nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from ..claims import ClaimStatus
from ..core import Engine
from ..identity import Principal, require_principal
from ..spaces import Visibility, resolve_visibility

__all__ = ["PanelService", "GRAPH_KINDS", "concerned_object_id"]

# object kinds that can appear as nodes in the knowledge graph
GRAPH_KINDS = ("entity", "fact", "claim", "evidence", "review", "source", "decision")

# a defensive cap so a single request can never assemble an unbounded graph/list
_MAX_NODES = 1500
_MAX_LIST = 500
_MAX_ACTIVITY = 200


def concerned_object_id(op: str, payload: dict[str, Any]) -> str | None:
    """The id of the object a ledger event concerns, for authorization of the event (ADR-032).

    Most write ops embed the full object dict (with its ``id``); the claim-graph link/governance ops
    embed only foreign keys. We authorize an event by the readability of the object it is *about* —
    for an evidence attachment or a review or an acceptance, that is the **claim**, so a private
    claim's activity never surfaces to someone who cannot read the claim.
    """
    if not isinstance(payload, dict):
        return None
    # link / review / governance ops reference a claim (or object) by id
    for key in ("claim_id", "object_id", "obj_id", "id"):
        val = payload.get(key)
        if isinstance(val, str):
            return val
    return None


class PanelService:
    """Authorized views over an :class:`~epistemos.core.Engine` for the panel boundary."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # -- low-level authorized enumeration -----------------------------------
    def _candidates(self, principal: Principal, kind: str | None) -> Iterator[dict[str, Any]]:
        """Raw objects of ``kind`` in the principal's tenant/namespace — UNFILTERED (internal)."""
        return self._engine.store.objects(principal.tenant, principal.namespace, kind=kind)

    def _readable_of_kind(self, principal: Principal, kind: str) -> list[dict[str, Any]]:
        eng = self._engine
        return [o for o in self._candidates(principal, kind) if eng.is_readable(principal, o)]

    def _readable_by_kinds(
        self, principal: Principal, kinds: Iterable[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Authorized objects for several kinds in a SINGLE store pass (one ``objects()`` scan, one
        ``is_readable`` per object) instead of one full scan per kind. Same firewall, ~Nx less work
        for the aggregate views (counts/graph/as_of/agents/sources). Performance only — no semantic
        change: an object still appears iff ``is_readable`` passes."""
        eng = self._engine
        want = set(kinds)
        out: dict[str, list[dict[str, Any]]] = {k: [] for k in want}
        for o in self._engine.store.objects(principal.tenant, principal.namespace):
            k = o.get("kind")
            if k in want and eng.is_readable(principal, o):
                out[k].append(o)
        return out

    # -- listings -----------------------------------------------------------
    def list_objects(
        self, principal: Principal, *, kind: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """A page of authorized objects of one kind. The firewall runs BEFORE limit/offset, so a
        page size never leaks the existence of hidden objects; ``count`` is the authorized total."""
        principal = _require(principal)
        if kind not in GRAPH_KINDS and kind != "space":
            from ..errors import ValidationError

            raise ValidationError(f"unknown kind {kind!r}")
        rows = self._readable_of_kind(principal, kind)
        rows.sort(key=lambda o: o.get("created_at", ""), reverse=True)
        lo = max(0, int(offset))
        hi = min(len(rows), lo + min(int(limit), _MAX_LIST))
        return {
            "kind": kind,
            "count": len(rows),  # authorized count only
            "items": [self._project_node(principal, o) for o in rows[lo:hi]],
        }

    # -- metrics / overview -------------------------------------------------
    def counts(self, principal: Principal) -> dict[str, Any]:
        """Authorized counts across kinds + belief tallies. Every number counts only objects the
        caller may read, so a counter can never reveal a hidden object (``PRIVATE_UI_LEAK = 0``)."""
        principal = _require(principal)
        by_kind = self._readable_by_kinds(principal, GRAPH_KINDS)
        spaces = self._readable_spaces(principal)
        # belief tally over readable claims + readable reviews (single pass, derive_belief order)
        reviews_by_claim: dict[str, list[str]] = {}
        for r in by_kind["review"]:
            reviews_by_claim.setdefault(r.get("claim_id", ""), []).append(r.get("verdict", ""))
        disputed = accepted = supported = proposed = 0
        for c in by_kind["claim"]:
            state = _belief_state_of(c, reviews_by_claim.get(c["id"], []))
            disputed += state == "disputed"
            accepted += state == "accepted"
            supported += state == "supported"
            proposed += state == "proposed"
        return {
            "knowledge_objects": sum(len(v) for v in by_kind.values()),
            "entities": len(by_kind["entity"]),
            "facts": len(by_kind["fact"]),
            "claims": len(by_kind["claim"]),
            "evidence": len(by_kind["evidence"]),
            "reviews": len(by_kind["review"]),
            "sources": len(by_kind["source"]),
            "decisions": len(by_kind["decision"]),
            "spaces": len(spaces),
            "disputed": disputed,
            "accepted": accepted,
            "supported": supported,
            "proposed": proposed,
            "agents": len(self._observed_agents(principal, by_kind)),
        }

    def overview(self, principal: Principal) -> dict[str, Any]:
        """Metrics + a real activity-derived pulse (per-minute buckets) + recent authorized events.
        Every series is derived from real ledger events the caller may read — no synthetic data."""
        principal = _require(principal)
        counts = self.counts(principal)
        activity = self.activity(principal, limit=_MAX_ACTIVITY)
        pulse = _bucket_per_minute(activity["events"])
        return {"counts": counts, "pulse": pulse, "recent": activity["events"][:20],
                "health": self.health(principal)}

    # -- knowledge graph ----------------------------------------------------
    def knowledge_graph(
        self, principal: Principal, *, focus: str | None = None, hops: int = 1,
        kinds: Iterable[str] | None = None, limit: int = _MAX_NODES,
    ) -> dict[str, Any]:
        """Assemble an authorized subgraph. A node exists iff the caller can read it; an edge exists
        iff BOTH endpoints are readable (ADR-032). ``focus`` keeps a node + its N-hop neighbors."""
        principal = _require(principal)
        want = set(kinds) if kinds else set(GRAPH_KINDS)
        cap = min(int(limit), _MAX_NODES)
        # readable node set, keyed by id — one store pass across all wanted kinds
        nodes: dict[str, dict[str, Any]] = {}
        for rows in self._readable_by_kinds(principal, want).values():
            for o in rows:
                nodes[o["id"]] = o
                if len(nodes) >= cap:
                    break
            if len(nodes) >= cap:
                break
        edges = self._edges_among(principal, nodes)
        truncated = len(nodes) >= min(int(limit), _MAX_NODES)
        if focus:
            nodes, edges, truncated = _restrict_to_focus(focus, nodes, edges, hops, truncated)
        return {
            "focus": focus,
            "nodes": [self._project_node(principal, o) for o in nodes.values()],
            "edges": edges,
            "truncated": truncated,
        }

    def expand(self, principal: Principal, node_id: str, *, kinds: Iterable[str] | None = None
               ) -> dict[str, Any]:
        """Authorized 1-hop expansion around a node — the same firewall as the full graph."""
        return self.knowledge_graph(principal, focus=node_id, hops=1, kinds=kinds)

    def _edges_among(
        self, principal: Principal, nodes: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Typed edges whose BOTH endpoints are in the authorized node set. Any edge touching a
        node the caller cannot read is dropped whole — no dangling stub (PRIVATE_GRAPH_LEAK=0)."""
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        def add(src: str, dst: str, rel: str) -> None:
            if src in nodes and dst in nodes:
                key = (src, dst, rel)
                if key not in seen:
                    seen.add(key)
                    edges.append({"source": src, "target": dst, "rel": rel})

        for oid, o in nodes.items():
            kind = o.get("kind")
            for anc in o.get("derived_from", ()) or ():
                add(oid, anc, "DERIVED_FROM")
            for old in o.get("supersedes", ()) or ():
                add(oid, old, "SUPERSEDES")
            for other in o.get("contradicts", ()) or ():
                add(oid, other, "CONTRADICTS")
            src_id = o.get("source")
            if isinstance(src_id, str):
                add(oid, src_id, "REFERENCES")
            if kind == "claim":
                for link in o.get("metadata", {}).get("evidence_links", []) or ():
                    ev, rel = link.get("evidence"), link.get("relation", "supports")
                    if isinstance(ev, str):
                        add(ev, oid, rel.upper())  # evidence --SUPPORTS/CONTRADICTS--> claim
            elif kind == "review":
                cid = o.get("claim_id")
                if isinstance(cid, str):
                    add(oid, cid, "REVIEWED_BY")
            elif kind == "relation":
                add(o.get("source_entity", ""), o.get("target_entity", ""),
                    str(o.get("rel_type", "REL")).upper())
            elif kind == "decision":
                for ev in o.get("evidence", ()) or ():
                    add(oid, ev, "DECIDED_FROM")
        # entity relations live as their own objects; fold them in (both endpoints must be readable)
        for rel in self._readable_of_kind(principal, "relation"):
            add(rel.get("source_entity", ""), rel.get("target_entity", ""),
                str(rel.get("rel_type", "REL")).upper())
        return edges

    def _edges_asof(
        self, nodes: dict[str, dict[str, Any]], asof: _AsOfState
    ) -> list[dict[str, Any]]:
        """Edges reconstructed at ``at_tx``. Immutable structural links (derived_from / supersedes /
        source / review→claim / decision→evidence) come from the objects; the *mutable* evidence
        attachments are taken from the ledger's as-of link set — never the claim's CURRENT
        ``metadata.evidence_links`` (which would leak a link attached later)."""
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        def add(src: str, dst: str, rel: str) -> None:
            if src in nodes and dst in nodes and (src, dst, rel) not in seen:
                seen.add((src, dst, rel))
                edges.append({"source": src, "target": dst, "rel": rel})

        for oid, o in nodes.items():
            kind = o.get("kind")
            for anc in o.get("derived_from", ()) or ():
                add(oid, anc, "DERIVED_FROM")
            for old in o.get("supersedes", ()) or ():
                add(oid, old, "SUPERSEDES")
            src_id = o.get("source")
            if isinstance(src_id, str):
                add(oid, src_id, "REFERENCES")
            if kind == "review":
                cid = o.get("claim_id")
                if isinstance(cid, str):
                    add(oid, cid, "REVIEWED_BY")
            elif kind == "decision":
                for ev in o.get("evidence", ()) or ():
                    add(oid, ev, "DECIDED_FROM")
        # mutable evidence attachments — as-of the ledger, not the current claim metadata
        for cid, links in asof.ev_links.items():
            for ev_id, rel in links:
                add(ev_id, cid, str(rel).upper())
        return edges

    # -- object detail ------------------------------------------------------
    def claim_detail(self, principal: Principal, claim_id: str) -> dict[str, Any]:
        """Full claim view: the core's ``explain_claim`` (authorized-before-traversal) as-is."""
        principal = _require(principal)
        return self._engine.explain_claim(principal, claim_id)

    def belief(self, principal: Principal, claim_id: str) -> dict[str, Any]:
        principal = _require(principal)
        return self._engine.belief(principal, claim_id)

    def evidence_detail(self, principal: Principal, evidence_id: str) -> dict[str, Any]:
        """Evidence view. Loads only if readable (else NotFound — no oracle). Lists the claims it is
        attached to, filtered to claims the caller can read; never leaks a private claim link."""
        principal = _require(principal)
        eng = self._engine
        ev = eng.get(principal, evidence_id)
        if ev is None or getattr(ev, "kind", None) != "evidence":
            from ..errors import NotFoundError

            raise NotFoundError(f"evidence {evidence_id!r} not found")
        supports: list[dict[str, Any]] = []
        contradicts: list[dict[str, Any]] = []
        for c in self._readable_of_kind(principal, "claim"):
            for link in c.get("metadata", {}).get("evidence_links", []) or ():
                if link.get("evidence") == evidence_id:
                    rel = link.get("relation", "supports")
                    (contradicts if rel in ("contradicts", "weakens") else supports).append(
                        {"claim": c["id"], "label": _claim_label(c), "relation": rel})
        d = ev.to_dict() if hasattr(ev, "to_dict") else dict(ev)
        return {
            "id": d["id"], "evidence_kind": d.get("evidence_kind"), "title": d.get("title"),
            "uri": d.get("uri"), "content_hash": d.get("content_hash"), "origin": d.get("origin"),
            "captured_at": d.get("captured_at"), "created_at": d.get("created_at"),
            "space": (d.get("spaces") or [None])[0], "owner": d.get("owner"),
            "supports": supports, "contradicts": contradicts,
        }

    def explain(self, principal: Principal, obj_id: str) -> dict[str, Any]:
        """WHY do we know this? Route to the claim explainer for claims, else the object explainer.
        Both are authorization-aware in the core; unreadable genealogy is elided, never exposed."""
        principal = _require(principal)
        obj = self._engine.get(principal, obj_id)
        if obj is None:
            from ..errors import NotFoundError

            raise NotFoundError(f"object {obj_id!r} not found")
        if getattr(obj, "kind", None) == "claim":
            return {"kind": "claim", **self._engine.explain_claim(principal, obj_id)}
        return {"kind": getattr(obj, "kind", "object"), **self._engine.explain(principal, obj_id)}

    # -- timeline / time-travel ---------------------------------------------
    def activity(self, principal: Principal, *, limit: int = _MAX_ACTIVITY, since_seq: int = 0
                 ) -> dict[str, Any]:
        """A bounded, authorized tail of the ledger as redacted event envelopes (ADR-032)."""
        principal = _require(principal)
        from .stream import authorized_events

        events = authorized_events(self._engine, principal, since_seq=since_seq)
        return {"events": events[-int(min(limit, _MAX_ACTIVITY)):][::-1], "head_seq":
                self._engine.store.event_count()}

    def as_of(self, principal: Principal, *, at_tx: str, kinds: Iterable[str] | None = None,
              limit: int = _MAX_NODES) -> dict[str, Any]:
        """A bitemporal snapshot: the authorized graph as it was **believed at** transaction time
        ``at_tx``. State is reconstructed from the ledger using **only** events with ``ts <= at_tx``
        so a claim retracted/accepted later, an evidence link attached later, or a review cast later
        never appears (``FUTURE_KNOWLEDGE_LEAK = 0``). Objects created after ``at_tx`` are excluded
        entirely. Authorization is evaluated against LIVE grants, fail-closed."""
        principal = _require(principal)
        want = set(kinds) if kinds else set(GRAPH_KINDS)
        asof = _asof_state(self._engine.store, at_tx)
        cap = min(int(limit), _MAX_NODES)
        nodes: dict[str, dict[str, Any]] = {}
        for rows in self._readable_by_kinds(principal, want).values():
            for o in rows:
                # existence as-of at_tx: a creation event for this object must precede at_tx. Both
                # the object's tx_from and the ledger creation record are required (the ledger is
                # authoritative; tx_from is unchanged by later mutation — a safe cross-check).
                tx_from = o.get("tx_from") or o.get("created_at")
                if not (tx_from and str(tx_from) <= at_tx and o["id"] in asof.existed):
                    continue
                nodes[o["id"]] = o
                if len(nodes) >= cap:
                    break
            if len(nodes) >= cap:
                break
        edges = self._edges_asof(nodes, asof)
        return {"at_tx": at_tx,
                "nodes": [self._project_node_asof(o, asof) for o in nodes.values()],
                "edges": edges, "as_of": True}

    def _project_node_asof(self, o: dict[str, Any], asof: _AsOfState) -> dict[str, Any]:
        """Project a node with its state RECONSTRUCTED at ``at_tx`` — never the current, possibly
        later-mutated, status/belief (the fix for the time-travel future-state leak)."""
        node = self._project_node_bare(o)
        oid, kind = o["id"], o.get("kind")
        if kind == "claim":
            if oid in asof.superseded:
                node["status"] = "superseded"
            elif oid in asof.retracted:
                node["status"] = "retracted"
            else:
                node["status"] = "open"  # lifecycle transitions after at_tx are not yet known
            node["claimant"] = o.get("claimant")
        elif kind == "fact":
            node["believed"] = oid not in asof.fact_ended  # not yet ended as of at_tx
        return node

    # -- spaces / agents / sources / health ---------------------------------
    def spaces(self, principal: Principal) -> dict[str, Any]:
        principal = _require(principal)
        out = []
        for sp in self._readable_spaces(principal):
            vis = resolve_visibility(sp.get("visibility"))
            members = self._space_members(principal, sp["id"])
            out.append({
                "id": sp["id"], "name": sp.get("name"), "visibility": vis.name,
                "level": int(vis), "owner": sp.get("owner"), "members": members,
                "created_at": sp.get("created_at"),
            })
        out.sort(key=lambda s: s["level"])
        return {"spaces": out}

    def agents(self, principal: Principal) -> dict[str, Any]:
        """Agents actually observed in readable objects/events — never a fabricated integration."""
        principal = _require(principal)
        by_kind = self._readable_by_kinds(principal, GRAPH_KINDS)
        stats = self._observed_agents(principal, by_kind)
        return {"agents": sorted(stats.values(), key=lambda a: -a["objects"])}

    def sources(self, principal: Principal) -> dict[str, Any]:
        """Sources with trust + usage. Trust is source AUTHORITY, never a truth score (§21)."""
        principal = _require(principal)
        grouped = self._readable_by_kinds(principal, ("source", "fact", "claim", "evidence"))
        srcs = grouped["source"]
        usage: dict[str, int] = {}
        for k in ("fact", "claim", "evidence"):
            for o in grouped[k]:
                sid = o.get("source")
                if sid:
                    usage[sid] = usage.get(sid, 0) + 1
        out = [{
            "id": s["id"], "uri": s.get("uri"), "trust": s.get("trust"),
            "source_kind": s.get("source_kind"), "used_by": usage.get(s["id"], 0),
            "created_at": s.get("created_at"),
        } for s in srcs]
        out.sort(key=lambda s: -s["used_by"])
        return {"sources": out}

    def health(self, principal: Principal) -> dict[str, Any]:
        """Core/ledger/index/projection health + stream availability (no sensitive internals)."""
        principal = _require(principal)
        h = self._engine.health(principal)
        h["event_stream"] = "healthy"  # served from this process; SSE endpoint is live
        return h

    def search(self, principal: Principal, **kw: Any) -> dict[str, Any]:
        """Typed search — the core's ``search`` is candidate-boundary-first (only authorized hits).
        Each hit is enriched with its object's human label; a hit whose object is not readable is
        dropped defensively (it should never occur, but the boundary never trusts an id blindly)."""
        principal = _require(principal)
        out = []
        for r in self._engine.search(principal, **kw):
            obj = self._engine.store.get_object(r.get("id", ""))
            if obj is None or not self._engine.is_readable(principal, obj):
                continue  # defense-in-depth: never label/serialize an unreadable object
            out.append({"id": obj["id"], "kind": obj.get("kind"), "label": _label(obj),
                        "score": r.get("score"), "space": (obj.get("spaces") or [None])[0]})
        return {"results": out}

    # -- projection / helpers (redaction) -----------------------------------
    def _project_node_bare(self, o: dict[str, Any]) -> dict[str, Any]:
        """The redacted node WITHOUT time-varying state (status/belief) — only creation-time,
        immutable fields. Shared by the live and the as-of projections."""
        kind = o.get("kind", "object")
        node = {
            "id": o["id"], "kind": kind, "label": _label(o),
            "space": (o.get("spaces") or [None])[0], "created_at": o.get("created_at"),
        }
        if kind == "claim":
            node["claimant"] = o.get("claimant")
        elif kind == "evidence":
            node["evidence_kind"] = o.get("evidence_kind")
        elif kind == "review":
            node["verdict"] = o.get("verdict")
            node["claim_id"] = o.get("claim_id")
        elif kind == "source":
            node["trust"] = o.get("trust")
        return node

    def _project_node(self, principal: Principal, o: dict[str, Any]) -> dict[str, Any]:
        """Live projection: bare fields + the object's CURRENT state."""
        node = self._project_node_bare(o)
        kind = o.get("kind", "object")
        if kind == "claim":
            node["status"] = o.get("status")
        elif kind == "fact":
            node["believed"] = o.get("tx_to") is None
        return node

    def _readable_spaces(self, principal: Principal) -> list[dict[str, Any]]:
        """Spaces the caller may see: owner, or member, or ORGANIZATION+ (org-wide visible)."""
        eng = self._engine
        out = []
        for sp in self._candidates(principal, "space"):
            if sp.get("tenant") != principal.tenant:
                continue
            vis = resolve_visibility(sp.get("visibility"))
            if (sp.get("owner") == principal.agent
                    or eng._is_member(sp["id"], principal.agent)  # server-side grant state
                    or vis >= Visibility.ORGANIZATION
                    or "admin" in principal.capabilities):
                out.append(sp)
        return out

    def _space_members(self, principal: Principal, space_id: str) -> int:
        n = 0
        for g in self._candidates(principal, "grant"):
            if g.get("kind") == "grant" and g.get("active") and space_id in g.get("id", ""):
                n += 1
        return n

    def _observed_agents(
        self, principal: Principal, by_kind: dict[str, list[dict[str, Any]]]
    ) -> dict[str, dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}

        def touch(agent: str | None) -> dict[str, Any]:
            a = agent or "unknown"
            return stats.setdefault(a, {"agent": a, "objects": 0, "claims": 0, "evidence": 0,
                                        "reviews": 0, "last_seen": ""})

        for kind, rows in by_kind.items():
            for o in rows:
                s = touch(o.get("owner"))
                s["objects"] += 1
                if kind in ("claim", "evidence", "review"):
                    s[kind + "s" if kind != "evidence" else "evidence"] += 1
                ts = o.get("created_at", "")
                if ts > s["last_seen"]:
                    s["last_seen"] = ts
        return stats


# -- as-of (bitemporal) state reconstruction -----------------------------------
@dataclass(frozen=True)
class _AsOfState:
    """Object state derived from the ledger using only events with ``ts <= at_tx``."""
    existed: set[str]                      # ids with a creation event by at_tx
    retracted: set[str]                    # claim ids retracted by at_tx
    superseded: set[str]                   # claim ids superseded by at_tx
    fact_ended: set[str]                   # fact ids retracted/superseded by at_tx
    ev_links: dict[str, list[tuple[str, str]]]  # claim id -> [(evidence id, relation)]


def _asof_state(store: Any, at_tx: str) -> _AsOfState:
    """Single ledger scan → the lifecycle/link state as it stood at ``at_tx``. Events strictly
    after ``at_tx`` are ignored, so nothing that happened later can be reconstructed."""
    existed: set[str] = set()
    retracted: set[str] = set()
    superseded: set[str] = set()
    fact_ended: set[str] = set()
    ev_links: dict[str, list[tuple[str, str]]] = {}
    for rec in store.read_events():
        if str(rec.ts) > at_tx:
            continue
        p = rec.payload if isinstance(rec.payload, dict) else {}
        oid = p.get("id")
        if isinstance(oid, str) and "kind" in p:  # an object-creation event
            existed.add(oid)
        op = rec.op
        cid = p.get("claim_id")
        if op == "claim_retracted" and isinstance(cid, str):
            retracted.add(cid)
        elif op == "claim_superseded" and isinstance(cid, str):
            superseded.add(cid)
        elif op in ("fact_retracted", "fact_superseded"):
            fid = p.get("fact_id") or p.get("id")
            if isinstance(fid, str):
                fact_ended.add(fid)
        elif op == "evidence_attached" and isinstance(cid, str):
            ev_id, rel = p.get("evidence_id"), p.get("relation", "supports")
            if isinstance(ev_id, str):
                ev_links.setdefault(cid, []).append((ev_id, str(rel)))
    return _AsOfState(existed, retracted, superseded, fact_ended, ev_links)


# -- module-level pure helpers -------------------------------------------------
def _require(principal: Principal) -> Principal:
    return require_principal(principal)


def _label(o: dict[str, Any]) -> str:
    kind = o.get("kind")
    if kind in ("fact", "claim"):
        return _claim_label(o)
    if kind == "entity":
        return str(o.get("name") or o.get("id"))
    if kind == "evidence":
        return str(o.get("title") or o.get("uri") or o.get("id"))
    if kind == "review":
        return f"{o.get('verdict', 'review')} · {o.get('claim_id', '')[:10]}"
    if kind == "source":
        return str(o.get("uri") or o.get("id"))
    if kind == "decision":
        return str(o.get("statement") or o.get("id"))
    if kind == "space":
        return str(o.get("name") or o.get("id"))
    return str(o.get("id"))


def _claim_label(o: dict[str, Any]) -> str:
    parts = [o.get("subject"), o.get("predicate"), o.get("object")]
    return " ".join(str(p) for p in parts if p) or str(o.get("id"))


def _belief_state_of(claim: dict[str, Any], verdicts: list[str]) -> str:
    """The derive_belief precedence, computed for a counter (lifecycle → governance → reviews)."""
    status = claim.get("status")
    if status == ClaimStatus.RETRACTED.value:
        return "retracted"
    if status == ClaimStatus.SUPERSEDED.value:
        return "superseded"
    meta = claim.get("metadata", {})
    if meta.get("rejected"):
        return "rejected"
    if meta.get("accepted"):
        return "accepted"
    if any(v in ("dispute", "reject") for v in verdicts):
        return "disputed"
    if any(v == "confirm" for v in verdicts):
        return "supported"
    return "proposed"


def _bucket_per_minute(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-minute activity buckets by event kind, derived from real events (newest last)."""
    buckets: dict[str, dict[str, int]] = {}
    for e in events:
        ts = str(e.get("ts", ""))[:16]  # YYYY-MM-DDTHH:MM
        b = buckets.setdefault(ts, {})
        b[e.get("kind", "event")] = b.get(e.get("kind", "event"), 0) + 1
    return [{"t": t, **counts} for t, counts in sorted(buckets.items())]


def _restrict_to_focus(
    focus: str, nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], hops: int,
    truncated: bool,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], bool]:
    """Keep ``focus`` + nodes within ``hops`` edges of it (over the already-authorized edge set)."""
    if focus not in nodes:
        return {}, [], truncated
    keep = {focus}
    frontier = {focus}
    for _ in range(max(0, hops)):
        nxt: set[str] = set()
        for e in edges:
            if e["source"] in frontier and e["target"] in nodes:
                nxt.add(e["target"])
            if e["target"] in frontier and e["source"] in nodes:
                nxt.add(e["source"])
        nxt -= keep
        keep |= nxt
        frontier = nxt
        if not frontier:
            break
    kept_nodes = {i: n for i, n in nodes.items() if i in keep}
    kept_edges = [e for e in edges if e["source"] in keep and e["target"] in keep]
    return kept_nodes, kept_edges, truncated
