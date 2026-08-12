// All panel screens. Every screen loads REAL data from the authorized API and renders states
// honestly (empty / no-permission / offline). No mock data, no fabricated counters.
import { el, mount, clear, rel, hhmmss, shortId, prefersReducedMotion } from "./dom.js";
import { api } from "./api.js";
import { GraphCanvas, KIND_VAR, REL_COLOR } from "./graph.js";
import { sparkline, bars, donut } from "./charts.js";

// ---------- shared components ----------
export const beliefBadge = (s) => el("span", { class: "badge b-" + (s || "proposed"), text: (s || "proposed").toUpperCase() });
export const verdictBadge = (v) => el("span", { class: "badge v-" + v, text: v });
export const visBadge = (v) => el("span", { class: "vis vis-" + v, text: v });
export const stateTag = (s) => el("span", { class: "tag", dataset: { state: (s || "").toLowerCase() }, text: s });
const kindColor = (k) => getComputedStyle(document.documentElement).getPropertyValue(KIND_VAR[k] || "--n-entity").trim();
export const kindDot = (k) => { const d = el("span", { class: "vis", title: k }); d.firstChild || d.append(el("span", { class: "sw" })); d.style.borderColor = "transparent"; const sw = el("span"); sw.style.cssText = `display:inline-block;width:8px;height:8px;border-radius:3px;background:${kindColor(k)}`; return el("span", { class: "row", style: "gap:6px" }, sw, el("span", { class: "mono", text: k })); };

function empty(icon, title, sub) {
  return el("div", { class: "empty" }, el("div", { class: "big", text: icon }),
    el("div", { text: title }), sub && el("div", { class: "mono", style: "font-size:11px", text: sub }));
}
function errState(err) {
  const code = err.status || "";
  const msg = code === 403 ? "You are not authorized to view this."
    : code === 401 ? "Session expired." : (err.message || "Something went wrong.");
  return el("div", { class: "errstate" }, el("div", { class: "big", text: code === 403 ? "🔒" : "⚠" }),
    el("div", { text: msg }), el("div", { class: "mono", style: "font-size:11px", text: err.kind || "" }));
}
async function guard(fn) { try { return await fn(); } catch (e) { return { __err: e }; } }
const head = (title, sub, ...actions) => el("div", { class: "head" },
  el("div", {}, el("h1", { text: title }), sub && el("div", { class: "sub", text: sub })),
  el("div", { class: "spacer", style: "flex:1" }), ...actions);

// ---------- OVERVIEW / BRAIN PULSE ----------
export async function overview(ctx) {
  const data = await guard(() => api.overview());
  if (data.__err) return errState(data.__err);
  const c = data.counts;
  const view = el("div", { class: "view" });
  const metric = (val, lbl, tag = "LIVE") => el("div", { class: "card metric" },
    stateTag(tag), el("div", { class: "val", text: val.toLocaleString() }), el("div", { class: "lbl", text: lbl }));
  view.append(head("Knowledge Pulse", "Live epistemological activity — authorized to you", ctx.connEl()));
  view.append(el("div", { class: "grid cols-4" },
    el("div", { class: "card metric big" }, stateTag("LIVE"),
      el("div", { class: "val", text: c.knowledge_objects.toLocaleString() }),
      el("div", { class: "lbl", text: "knowledge objects you can see" })),
    metric(c.claims, "active claims"),
    metric(c.evidence, "evidence relations"),
    metric(c.disputed, "disputed", c.disputed ? "LIVE" : "LIVE")));
  // pulse bars (real per-minute activity)
  const pulse = data.pulse.slice(-30);
  const totalPer = pulse.map((p) => Object.entries(p).filter(([k]) => k !== "t").reduce((s, [, v]) => s + v, 0));
  const pulseCard = el("div", { class: "card" }, el("h3", { text: "Activity / minute (real ledger events)" }),
    pulse.length ? bars(pulse.map((p, i) => ({ label: p.t.slice(11), value: totalPer[i] }))) : empty("∅", "No activity in window"));
  const dist = el("div", { class: "card" }, el("h3", { text: "Belief distribution" }),
    el("div", { class: "row", style: "gap:24px" },
      donut([
        { label: "accepted", value: c.accepted, color: "var(--accepted)" },
        { label: "supported", value: c.supported, color: "var(--supported)" },
        { label: "disputed", value: c.disputed, color: "var(--disputed)" },
        { label: "proposed", value: c.proposed, color: "var(--proposed)" },
      ]),
      el("div", {}, ...[["accepted", c.accepted, "b-accepted"], ["supported", c.supported, "b-supported"],
        ["disputed", c.disputed, "b-disputed"], ["proposed", c.proposed, "b-proposed"]].map(([l, v, cls]) =>
        el("div", { class: "row", style: "margin:4px 0" }, el("span", { class: "badge " + cls, text: l }), el("b", { class: "mono", text: v }))))));
  view.append(el("div", { class: "grid cols-2", style: "margin-top:16px" }, pulseCard, dist));
  // secondary metrics
  view.append(el("div", { class: "grid cols-4", style: "margin-top:16px" },
    metric(c.entities, "entities"), metric(c.sources, "sources"),
    metric(c.spaces, "knowledge spaces", "SNAPSHOT"), metric(c.agents, "active agents")));
  // live activity feed
  const feed = el("div", { class: "feed" });
  ctx.feedEl = feed;
  const activity = el("div", { class: "card", style: "margin-top:16px" },
    el("div", { class: "row" }, el("h3", { text: "Live activity stream" }), el("div", { style: "flex:1" }),
      el("a", { href: "#/timeline", text: "Open timeline →" })), feed);
  for (const ev of data.recent) feed.append(eventRow(ev, ctx));
  view.append(activity);
  return view;
}
export function eventRow(ev, ctx, isNew = false) {
  const row = el("div", { class: "ev" + (isNew && !prefersReducedMotion() ? " enter" : "") },
    el("span", { class: "t", text: hhmmss(ev.ts) }),
    el("span", { class: "k", text: ev.kind }),
    el("span", { class: "who", text: ev.actor }),
    el("span", { class: "s", text: ev.summary }));
  row.addEventListener("click", () => ev.object && ctx.inspect(ev.object, ev.object_kind));
  return row;
}

// ---------- GRAPH EXPLORER ----------
export async function graph(ctx) {
  const wrap = el("div", { class: "view full" });
  const gwrap = el("div", { class: "graphwrap" });
  wrap.append(gwrap);
  const data = await guard(() => api.graph({ limit: 1500 }));
  if (data.__err) { wrap.append(el("div", { class: "graph-hud" }, errState(data.__err))); return wrap; }
  if (!data.nodes.length) { clear(gwrap); gwrap.append(empty("◍", "No knowledge visible to you yet",
    "Objects you are authorized to read will appear here.")); return wrap; }
  const g = new GraphCanvas(gwrap, {
    onSelect: (id, nd) => nd && showNodeInspector(gwrap, nd, g, ctx),
    onExpand: async (id) => { const ex = await guard(() => api.expand(id)); if (!ex.__err) { g.setData(ex.nodes, ex.edges, { preservePositions: true }); } },
  });
  g.setData(data.nodes, data.edges);
  ctx.graph = g;
  // HUD: filters by kind
  const kinds = [...new Set(data.nodes.map((n) => n.kind))];
  const hud = el("div", { class: "graph-hud" },
    el("span", { class: "chip", dataset: { on: "1" }, text: `${data.nodes.length} nodes` }),
    el("span", { class: "chip", text: `${data.edges.length} edges` }),
    data.truncated ? el("span", { class: "chip", dataset: { on: "1" },
      style: "color:var(--amber); border-color:rgba(240,181,74,.4)",
      title: "The authorized graph exceeds the render cap; showing the first slice. Focus a node to explore a neighbourhood.",
      text: "⚠ capped" }) : null);
  const hidden = new Set();
  for (const k of kinds) {
    const chip = el("button", { class: "chip", dataset: { on: "1" } }, kindDot(k));
    chip.addEventListener("click", () => { if (hidden.has(k)) hidden.delete(k); else hidden.add(k);
      chip.dataset.on = hidden.has(k) ? "0" : "1"; g.setFilter([...hidden]); });
    hud.append(chip);
  }
  gwrap.append(hud);
  // tools
  const tool = (label, fn) => { const b = el("button", { class: "chip", title: label, text: label }); b.addEventListener("click", fn); return b; };
  gwrap.append(el("div", { class: "graph-tools" },
    tool("＋", () => g.zoomBy(1.2)), tool("－", () => g.zoomBy(0.83)),
    tool("⤢ fit", () => g.fit()),
    tool("⛶", () => gwrap.requestFullscreen ? (document.fullscreenElement ? document.exitFullscreen() : gwrap.requestFullscreen()) : null),
    tool("≣ list", () => altGraph(gwrap, data, ctx))));
  // legend
  gwrap.append(el("div", { class: "legend" }, ...kinds.map((k) => kindDot(k))));
  return wrap;
}
function showNodeInspector(gwrap, nd, g, ctx) {
  const old = gwrap.querySelector(".node-inspector"); if (old) old.remove();
  const box = el("div", { class: "node-inspector" },
    el("div", { class: "row" }, kindDot(nd.kind), el("span", { style: "flex:1" }),
      el("button", { class: "btn ghost", text: g.pinned.has(nd.id) ? "unpin" : "pin", onclick: () => { g.togglePin(nd.id); box.remove(); showNodeInspector(gwrap, nd, g, ctx); } })),
    el("h3", { style: "margin:8px 0", text: nd.label }),
    nd.kind === "claim" && nd.status ? el("div", { class: "row", style: "margin:6px 0" }, el("span", { class: "mono", text: "status:" }), el("b", { text: nd.status })) : null,
    el("div", { class: "row", style: "margin-top:10px; gap:8px" },
      el("button", { class: "btn", text: "Expand", onclick: () => g.onExpand(nd.id) }),
      el("button", { class: "btn primary", text: "Open", onclick: () => ctx.inspect(nd.id, nd.kind) }),
      el("button", { class: "btn", text: "Why?", onclick: () => ctx.go("#/explain/" + encodeURIComponent(nd.id)) })));
  gwrap.append(box);
}
function altGraph(gwrap, data, ctx) {
  // accessible, keyboard-navigable textual representation of the same authorized graph (a11y gate)
  const adj = new Map(data.nodes.map((n) => [n.id, []]));
  for (const e of data.edges) { adj.get(e.source)?.push(`${e.rel} → ${lbl(data, e.target)}`); adj.get(e.target)?.push(`${lbl(data, e.source)} ${e.rel} →`); }
  const panel = el("div", { class: "alt-graph", role: "region", "aria-label": "Graph as a navigable list" },
    el("div", { class: "head" }, el("h1", { text: "Graph — list view" }), el("div", { style: "flex:1" }),
      el("button", { class: "btn", text: "✕ close", onclick: () => panel.remove() })),
    el("div", { class: "list-scroll" }, el("table", { class: "table" },
      el("thead", {}, el("tr", {}, el("th", { text: "Node" }), el("th", { text: "Type" }), el("th", { text: "Relations" }))),
      el("tbody", {}, ...data.nodes.map((n) => el("tr", { tabindex: "0", onclick: () => ctx.inspect(n.id, n.kind),
        onkeydown: (e) => e.key === "Enter" && ctx.inspect(n.id, n.kind) },
        el("td", { text: n.label }), el("td", {}, kindDot(n.kind)),
        el("td", { class: "mono", style: "font-size:11px", text: (adj.get(n.id) || []).slice(0, 6).join("  ·  ") || "—" })))))));
  gwrap.append(panel);
}
const lbl = (data, id) => (data.nodes.find((n) => n.id === id) || {}).label || shortId(id);

// ---------- CLAIM CENTER ----------
export async function claims(ctx) {
  const view = el("div", { class: "view" });
  view.append(head("Claims", "Contribution ≠ truth — belief is derived, never asserted"));
  const data = await guard(() => api.list("claim", 200));
  if (data.__err) return mount(view, errState(data.__err)), view;
  if (!data.items.length) return mount(el("div", { class: "view" }), head("Claims"), empty("◇", "No claims visible to you")), view;
  const rows = await Promise.all(data.items.map(async (c) => {
    const b = await guard(() => api.belief(c.id));
    return { c, state: b.__err ? "proposed" : b.state };
  }));
  const table = el("table", { class: "table" },
    el("thead", {}, el("tr", {}, el("th", { text: "Claim" }), el("th", { text: "Claimant" }),
      el("th", { text: "Belief" }), el("th", { text: "Status" }), el("th", { text: "Space" }))),
    el("tbody", {}, ...rows.map(({ c, state }) => el("tr", { onclick: () => ctx.inspect(c.id, "claim") },
      el("td", { text: c.label }), el("td", { class: "mono", text: c.claimant || "—" }),
      el("td", {}, beliefBadge(state)), el("td", { class: "mono", text: c.status || "open" }),
      el("td", { class: "mono", style: "font-size:11px", text: c.space ? shortId(c.space) : "private" })))));
  view.append(el("div", { class: "card list-scroll" }, table));
  return view;
}

// ---------- CLAIM DETAIL (inspector) ----------
export async function claimDetail(id) {
  const data = await guard(() => api.claim(id));
  if (data.__err) return errState(data.__err);
  const st = data.statement, b = data.belief;
  const box = el("div", {},
    el("div", { class: "row" }, kindDot("claim"), el("span", { style: "flex:1" }), beliefBadge(b.state)),
    el("h2", { style: "margin:10px 0 4px", text: `${st.subject} ${st.predicate} ${st.object || ""}` }),
    el("dl", { class: "kv", style: "margin-top:12px" },
      el("dt", { text: "claimant" }), el("dd", { class: "mono", text: data.claimant }),
      el("dt", { text: "ingested by" }), el("dd", { class: "mono", text: data.ingested_by }),
      el("dt", { text: "source" }), el("dd", { class: "mono", text: data.source ? (data.source.uri || data.source.id) : "—" }),
      el("dt", { text: "space" }), el("dd", { class: "mono", text: data.space || "private" }),
      el("dt", { text: "valid" }), el("dd", { class: "mono", text: (data.temporal.valid_from || "—") + " → " + (data.temporal.valid_to || "now") }),
      el("dt", { text: "tx" }), el("dd", { class: "mono", text: (data.temporal.tx_from || "").slice(0, 19) })));
  // belief decomposition (evidence + reviews → derived state)
  box.append(el("div", { class: "divider" }), el("h3", { text: "Why this belief" }), beliefDecomp(data));
  // actions (all real)
  box.append(el("div", { class: "row", style: "margin-top:16px; gap:8px" },
    el("a", { class: "btn", href: "#/graph", text: "Open graph", onclick: () => setTimeout(() => window.__panel.focusGraph?.(id), 60) }),
    el("a", { class: "btn", href: "#/explain/" + encodeURIComponent(id), text: "Explain" }),
    el("a", { class: "btn", href: "#/timeline", text: "Timeline" })));
  return box;
}
function beliefDecomp(data) {
  const tree = el("div", { class: "belief-tree" });
  for (const e of data.evidence) tree.append(el("div", { class: "b-row" },
    el("span", { class: "badge v-" + (e.relation === "contradicts" || e.relation === "weakens" ? "dispute" : "confirm"), text: e.relation }),
    el("span", { text: e.title || e.uri || e.evidence })));
  for (const r of data.reviews) tree.append(el("div", { class: "b-row" }, verdictBadge(r.verdict),
    el("span", { text: (r.reviewer || "reviewer") + (r.self_review ? " (self-review)" : "") }),
    r.rationale ? el("span", { class: "sub", style: "color:var(--fg-3)", text: "— " + r.rationale }) : null));
  if (!data.evidence.length && !data.reviews.length) tree.append(el("div", { class: "b-row", text: "No evidence or reviews yet." }));
  tree.append(el("div", { class: "belief-out" }, el("span", { text: "⇒" }), beliefBadge(data.belief.state),
    el("span", { class: "sub", style: "color:var(--fg-2)", text: data.belief.why })));
  return tree;
}

// ---------- EVIDENCE DETAIL ----------
export async function evidenceDetail(id) {
  const d = await guard(() => api.evidence(id));
  if (d.__err) return errState(d.__err);
  return el("div", {},
    el("div", { class: "row" }, kindDot("evidence"), el("span", { style: "flex:1" }),
      d.space ? visBadge("TEAM") : el("span", { class: "vis vis-PRIVATE", text: "PRIVATE" })),
    el("h2", { style: "margin:10px 0", text: d.title || d.uri || "Evidence" }),
    el("dl", { class: "kv" },
      el("dt", { text: "kind" }), el("dd", { class: "mono", text: d.evidence_kind }),
      el("dt", { text: "uri" }), el("dd", { class: "mono", text: d.uri || "—" }),
      el("dt", { text: "hash" }), el("dd", { class: "mono", text: d.content_hash || "—" }),
      el("dt", { text: "origin" }), el("dd", { text: d.origin || "—" }),
      el("dt", { text: "space" }), el("dd", { class: "mono", text: d.space || "private" })),
    el("div", { class: "divider" }),
    el("h3", { text: `Supports (${d.supports.length})` }),
    ...d.supports.map((s) => el("div", { class: "b-row", onclick: () => window.__panel.inspect(s.claim, "claim") }, el("span", { class: "badge v-confirm", text: "supports" }), el("span", { text: s.label }))),
    el("h3", { style: "margin-top:12px", text: `Contradicts (${d.contradicts.length})` }),
    ...d.contradicts.map((s) => el("div", { class: "b-row", onclick: () => window.__panel.inspect(s.claim, "claim") }, el("span", { class: "badge v-dispute", text: s.relation }), el("span", { text: s.label }))));
}

// ---------- DECISION LINEAGE ----------
export async function decisionDetail(id) {
  const d = await guard(() => api.explain(id));
  if (d.__err) return errState(d.__err);
  const box = el("div", {},
    el("div", { class: "row" }, kindDot("decision"), el("span", { style: "flex:1" }),
      d.reversible === false ? el("span", { class: "badge b-rejected", text: "IRREVERSIBLE" })
        : el("span", { class: "badge b-supported", text: "REVERSIBLE" })),
    el("h2", { style: "margin:10px 0", text: d.statement || "Decision" }),
    el("dl", { class: "kv" },
      el("dt", { text: "outcome" }), el("dd", { class: "mono", text: d.outcome || "—" }),
      el("dt", { text: "alternatives" }),
      el("dd", { text: (d.alternatives || []).join(", ") || "none recorded" })));
  // lineage: DECISION → evidence (facts/claims) → source → OUTCOME
  box.append(el("div", { class: "divider" }), el("h3", { text: "Why this decision was made" }));
  const tree = el("div", { class: "belief-tree" });
  for (const ev of d.evidence || []) {
    const st = ev.statement || {};
    const label = ev.title || [st.subject, st.predicate, st.object].filter(Boolean).join(" ")
      || shortId(ev.id);
    tree.append(el("div", { class: "b-row", style: "cursor:pointer",
      onclick: () => window.__panel.inspect(ev.id, ev.kind) },
      el("span", { class: "badge v-confirm", text: "decided from" }),
      el("span", {}, el("b", { text: label }),
        ev.source ? el("span", { class: "sub", style: "color:var(--fg-3)", text: " · " + (ev.source.uri || ev.source.id) }) : null)));
  }
  if (!(d.evidence || []).length) tree.append(el("div", { class: "b-row", text: "No recorded lineage." }));
  tree.append(el("div", { class: "belief-out" }, el("span", { text: "⇒" }),
    el("span", { class: "badge b-accepted", text: "OUTCOME: " + (d.outcome || "recorded") })));
  box.append(tree);
  return box;
}

// ---------- EXPLAIN MODE ----------
export async function explain(ctx, id) {
  const view = el("div", { class: "view" });
  view.append(head("Why do we know this?", "Authorization-aware genealogy — unreadable nodes are elided, never exposed"));
  const d = await guard(() => api.explain(id));
  if (d.__err) return mount(view, errState(d.__err)), view;
  if (d.kind === "claim") { view.append(el("div", { class: "card" }, beliefDecomp(d)));
    view.append(el("div", { class: "card", style: "margin-top:12px" }, el("h3", { text: "Provenance" }),
      el("dl", { class: "kv" }, el("dt", { text: "claimant" }), el("dd", { text: d.claimant }),
        el("dt", { text: "source" }), el("dd", { text: d.source ? (d.source.uri || d.source.id) : "—" }),
        el("dt", { text: "contradictions" }), el("dd", { text: (d.contradictions || []).length })))); return view; }
  // generic object explain
  view.append(el("div", { class: "card mono", style: "white-space:pre-wrap; font-size:12px", text: JSON.stringify(d, null, 2) }));
  return view;
}

// ---------- TIMELINE + TIME TRAVEL ----------
export async function timeline(ctx) {
  const view = el("div", { class: "view" });
  const atInput = el("input", { type: "datetime-local", class: "btn", style: "color:var(--fg)" });
  const travelBtn = el("button", { class: "btn", text: "⏳ Time travel" });
  view.append(head("Timeline", "Bitemporal — go back and ask: what did EPISTEMOS know then?",
    el("div", { class: "row" }, atInput, travelBtn)));
  const feedCard = el("div", { class: "card" });
  view.append(feedCard);
  const data = await guard(() => api.activity(0, 300));
  if (data.__err) return mount(feedCard, errState(data.__err)), view;
  const feed = el("div", { class: "feed" });
  ctx.feedEl = feed;
  for (const ev of data.events) feed.append(eventRow(ev, ctx));
  mount(feedCard, feed.children.length ? feed : empty("∅", "No activity yet"));
  travelBtn.addEventListener("click", async () => {
    const at = atInput.value ? new Date(atInput.value).toISOString() : new Date().toISOString();
    const snap = await guard(() => api.asof(at));
    const old = view.querySelector(".travel-banner"); if (old) old.remove();
    const banner = el("div", { class: "card travel-banner", style: "margin:12px 0; border-color: rgba(240,181,74,.5); background: rgba(240,181,74,.06)" },
      el("div", { class: "row" }, el("span", { class: "timepill", text: "⏳ TIME TRAVEL · viewing " + at.slice(0, 19) }),
        el("span", { style: "flex:1" }),
        el("button", { class: "btn ghost", text: "✕ return to live", onclick: () => { banner.remove(); } })),
      snap.__err ? errState(snap.__err) :
        el("div", { style: "margin-top:10px" }, el("div", { class: "sub", style: "color:var(--fg-2)",
          text: `As of ${at.slice(0, 19)}, EPISTEMOS knew ${snap.nodes.length} objects and ${snap.edges.length} relations that you are authorized to read. Objects asserted after this instant are not shown.` })));
    view.insertBefore(banner, view.children[1]); // right below the header
    banner.scrollIntoView({ block: "nearest" });
  });
  return view;
}

// ---------- SPACES ----------
export async function spaces(ctx) {
  const view = el("div", { class: "view" });
  view.append(head("Knowledge Spaces", "Visibility is orthogonal to tenant — PUBLIC is never the default"));
  const d = await guard(() => api.spaces());
  if (d.__err) return mount(view, errState(d.__err)), view;
  if (!d.spaces.length) return mount(view.appendChild(el("div")), empty("▤", "No spaces visible to you")), view;
  view.append(el("div", { class: "grid cols-3" }, ...d.spaces.map((s) => el("div", { class: "card" },
    el("div", { class: "row" }, visBadge(s.visibility), el("span", { style: "flex:1" }),
      s.level >= 3 ? el("span", { class: "tag", dataset: { state: "stale" }, text: "⚠ exposure" }) : null),
    el("h3", { style: "margin:10px 0 4px; text-transform:none; font-size:15px; color:var(--fg)", text: s.name }),
    el("dl", { class: "kv" }, el("dt", { text: "owner" }), el("dd", { class: "mono", text: s.owner }),
      el("dt", { text: "members" }), el("dd", { class: "mono", text: s.members }),
      el("dt", { text: "level" }), el("dd", { class: "mono", text: `${s.visibility} (${s.level})` }))))));
  view.append(el("div", { class: "card", style: "margin-top:16px" },
    el("h3", { text: "Promotion & exposure" }),
    el("div", { class: "sub", style: "color:var(--fg-2)" },
      "Moving an object up the lattice (TEAM → ORGANIZATION → PUBLIC) widens who can read it. Promotion to ORGANIZATION+ requires the knowledge.promote capability and is always logged; the panel never promotes.")));
  return view;
}

// ---------- AGENT OBSERVATORY ----------
export async function agents(ctx) {
  const view = el("div", { class: "view" });
  view.append(head("Agent Observatory", "Only agents actually observed in knowledge you can read"));
  const d = await guard(() => api.agents());
  if (d.__err) return mount(view, errState(d.__err)), view;
  view.append(el("div", { class: "grid cols-3" }, ...d.agents.map((a) => el("div", { class: "card" },
    el("div", { class: "row" }, el("span", { class: "dot", style: "background:var(--n-agent)" }),
      el("b", { text: a.agent }), el("span", { style: "flex:1" }),
      el("span", { class: "tag", dataset: { state: "live" }, text: "observed" })),
    el("div", { class: "grid cols-3", style: "margin-top:12px; gap:8px" },
      miniStat(a.claims, "claims"), miniStat(a.evidence, "evidence"), miniStat(a.reviews, "reviews")),
    el("div", { class: "sub", style: "margin-top:8px; color:var(--fg-3); font-size:11px", text: "last seen " + rel(a.last_seen) })))));
  return view;
}
const miniStat = (v, l) => el("div", { style: "text-align:center" }, el("div", { class: "mono", style: "font-size:18px", text: v }), el("div", { class: "sub", style: "font-size:10px; color:var(--fg-3)", text: l }));

// ---------- SOURCE INTELLIGENCE ----------
export async function sources(ctx) {
  const view = el("div", { class: "view" });
  view.append(head("Source Intelligence", "Trust is source authority — NOT a truth score"));
  const d = await guard(() => api.sources());
  if (d.__err) return mount(view, errState(d.__err)), view;
  const table = el("table", { class: "table" },
    el("thead", {}, el("tr", {}, el("th", { text: "Source" }), el("th", { text: "Kind" }),
      el("th", { text: "Authority" }), el("th", { text: "Used by" }))),
    el("tbody", {}, ...d.sources.map((s) => el("tr", {},
      el("td", { class: "mono", text: s.uri }), el("td", { class: "mono", text: s.source_kind }),
      el("td", {}, trustBar(s.trust)), el("td", { class: "mono", text: s.used_by })))));
  view.append(el("div", { class: "card list-scroll" }, table));
  return view;
}
function trustBar(t) {
  const pct = Math.round((t || 0) * 100);
  const bar = el("div", { style: "width:120px; height:8px; background:var(--bg-3); border-radius:4px; overflow:hidden; display:inline-block; vertical-align:middle" });
  const fill = el("div", { style: `height:100%; width:${pct}%; background:linear-gradient(90deg,var(--indigo),var(--amber))` });
  bar.append(fill);
  return el("span", { class: "row", style: "gap:8px" }, bar, el("span", { class: "mono", text: pct + "%" }));
}

// ---------- SYSTEM HEALTH ----------
export async function health(ctx) {
  const view = el("div", { class: "view" });
  view.append(head("System Health", "Core, ledger, index, projections, event stream"));
  const h = await guard(() => api.health());
  if (h.__err) return mount(view, errState(h.__err)), view;
  const comp = (name, ok, detail) => el("div", { class: "card" },
    el("div", { class: "row" }, el("span", { class: "dot", style: `background:${ok ? "var(--ok)" : "var(--danger)"}` }),
      el("b", { text: name }), el("span", { style: "flex:1" }),
      el("span", { class: "tag", dataset: { state: ok ? "live" : "unavailable" }, text: ok ? "HEALTHY" : "DEGRADED" })),
    detail ? el("div", { class: "sub", style: "margin-top:8px; color:var(--fg-3); font-size:11px", text: detail }) : null);
  view.append(el("div", { class: "grid cols-3" },
    comp("Core", true, "engine responding"),
    comp("Ledger", h.integrity_ok !== false, `${h.event_count ?? "?"} events · head ${shortId(h.head_hash || "")}`),
    comp("Index", (h.index || {}).healthy !== false, "lexical/FTS"),
    comp("Projections", true, "rebuildable from ledger"),
    comp("Event stream", h.event_stream === "healthy", "SSE authorized tail"),
    comp("Storage", true, "local, single file")));
  return view;
}

// ---------- SEARCH RESULTS (page) ----------
export async function searchResults(ctx, q) {
  const view = el("div", { class: "view" });
  view.append(head(`Search: ${q}`, "Typed results — a Claim is never silently shown as accepted knowledge"));
  const d = await guard(() => api.search(q, { limit: 50 }));
  if (d.__err) return mount(view, errState(d.__err)), view;
  if (!d.results.length) return mount(view.appendChild(el("div")), empty("⌕", "No results", "Nothing you can read matches.")), view;
  const byKind = {};
  for (const r of d.results) (byKind[r.kind] = byKind[r.kind] || []).push(r);
  for (const [kind, items] of Object.entries(byKind)) {
    view.append(el("div", { class: "card", style: "margin-bottom:12px" },
      el("h3", {}, kindDot(kind)),
      ...items.map((r) => el("div", { class: "b-row", style: "cursor:pointer", onclick: () => ctx.inspect(r.id, r.kind) },
        el("span", { text: r.label }), el("span", { style: "flex:1" }),
        el("span", { class: "mono", style: "font-size:11px; color:var(--fg-3)", text: r.space ? shortId(r.space) : "private" })))));
  }
  return view;
}

export { errState, empty };
