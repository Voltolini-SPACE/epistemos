// API client + SSE connection manager. The browser sends only its session cookie (set server-side);
// it never chooses tenant/capability/visibility. Every response is already authorized (ADR-030/032).

async function req(path, { method = "GET", body } = {}) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json().catch(() => ({})) : await r.text();
  if (!r.ok) {
    const err = new Error((data && data.message) || r.statusText);
    err.status = r.status; err.kind = (data && data.error) || "Error";
    throw err;
  }
  return data;
}

export const api = {
  // auth
  session: (token) => req("/api/session", { method: "POST", body: { token } }),
  whoami: () => req("/api/whoami"),
  demoIdentities: () => req("/api/demo/identities"),
  // views
  overview: () => req("/api/overview"),
  counts: () => req("/api/counts"),
  graph: (q = {}) => req("/api/graph?" + new URLSearchParams(q)),
  expand: (node) => req("/api/graph/expand?" + new URLSearchParams({ node })),
  list: (kind, limit = 100, offset = 0) => req("/api/list?" + new URLSearchParams({ kind, limit, offset })),
  claim: (id) => req("/api/claim?" + new URLSearchParams({ id })),
  belief: (id) => req("/api/belief?" + new URLSearchParams({ id })),
  evidence: (id) => req("/api/evidence?" + new URLSearchParams({ id })),
  explain: (id) => req("/api/explain?" + new URLSearchParams({ id })),
  activity: (since = 0, limit = 200) => req("/api/activity?" + new URLSearchParams({ since, limit })),
  asof: (at, kinds) => req("/api/asof?" + new URLSearchParams(kinds ? { at, kinds } : { at })),
  spaces: () => req("/api/spaces"),
  agents: () => req("/api/agents"),
  sources: () => req("/api/sources"),
  health: () => req("/api/health"),
  search: (text, opts = {}) => req("/api/search", { method: "POST", body: { text, ...opts } }),
};

// -- SSE stream manager: LIVE / RECONNECTING / OFFLINE / STALE, auto-reconnect, resume by seq. -----
export class Stream extends EventTarget {
  constructor({ staleMs = 40000 } = {}) {
    super();
    this.state = "offline";
    this.lastSeq = 0;
    this._staleMs = staleMs;
    this._es = null;
    this._staleTimer = null;
    this._lastBeat = 0;
  }
  _set(state) { if (state !== this.state) { this.state = state; this.dispatchEvent(new CustomEvent("state", { detail: state })); } }
  _touch() {
    this._lastBeat = Date.now();
    clearTimeout(this._staleTimer);
    this._staleTimer = setTimeout(() => { if (this.state === "live") this._set("stale"); }, this._staleMs);
  }
  connect() {
    if (this._es) this._es.close();
    // EventSource carries the session cookie same-origin; no token in the URL (§35).
    const es = new EventSource("/api/stream", { withCredentials: true });
    this._es = es;
    this._set("reconnecting");
    es.onopen = () => { this._set("live"); this._touch(); };
    es.onerror = () => {
      // EventSource auto-reconnects; reflect the transient state honestly.
      this._set(navigator.onLine === false ? "offline" : "reconnecting");
    };
    es.onmessage = (e) => this._handle(e);
    // typed events all funnel through the same handler
    for (const t of ["claim.created","claim.retracted","claim.superseded","evidence.created",
      "evidence.attached","review.created","knowledge.accepted","knowledge.rejected","fact.asserted",
      "fact.confirmed","contradiction.recorded","relation.created","entity.created","decision.created",
      "source.added"]) es.addEventListener(t, (e) => this._handle(e));
  }
  _handle(e) {
    this._set("live"); this._touch();
    let data; try { data = JSON.parse(e.data); } catch { return; }
    if (data.seq) this.lastSeq = Math.max(this.lastSeq, data.seq);
    this.dispatchEvent(new CustomEvent("event", { detail: data }));
  }
  close() { if (this._es) this._es.close(); clearTimeout(this._staleTimer); this._set("offline"); }
}
