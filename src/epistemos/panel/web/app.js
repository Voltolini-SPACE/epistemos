// EPISTEMOS Panel bootstrap: shell, hash router, command palette (⌘K), inspector drawer, and the
// SSE wiring that makes counters / feed / graph update live without a reload. The browser holds no
// authority: it only renders what the authorized API returns.
import { el, mount, clear, prefersReducedMotion } from "./dom.js";
import { api, Stream } from "./api.js";
import * as S from "./screens.js";

const NAV = [
  { g: "Explore" },
  { id: "overview", label: "Overview", ic: "◎", route: "#/overview" },
  { id: "graph", label: "Brain / Graph", ic: "◍", route: "#/graph" },
  { id: "search", label: "Search", ic: "⌕", route: "#/search" },
  { g: "Knowledge" },
  { id: "claims", label: "Claims", ic: "◇", route: "#/claims" },
  { id: "timeline", label: "Timeline", ic: "≋", route: "#/timeline" },
  { id: "spaces", label: "Spaces", ic: "▤", route: "#/spaces" },
  { g: "Observe" },
  { id: "agents", label: "Agents", ic: "◈", route: "#/agents" },
  { id: "sources", label: "Sources", ic: "❖", route: "#/sources" },
  { id: "health", label: "Health", ic: "♥", route: "#/health" },
];

const app = {
  stream: null, whoami: null, conns: new Set(), feedEl: null, graph: null,
  activeRoute: "", counts: null,
};
window.__panel = app;

// ---------- connection indicator (shared, live) ----------
function connEl() {
  const e = el("span", { class: "conn", dataset: { state: app.stream ? app.stream.state : "offline" } },
    el("span", { class: "dot" }), el("span", { class: "lbl", text: (app.stream?.state || "offline").toUpperCase() }));
  app.conns.add(e);
  return e;
}
function updateConn(state) {
  for (const e of app.conns) { if (!e.isConnected) { app.conns.delete(e); continue; }
    e.dataset.state = state; e.querySelector(".lbl").textContent = state.toUpperCase(); }
}
app.connEl = connEl;

// ---------- inspector drawer ----------
async function inspect(id, kind) {
  let drawer = document.querySelector(".inspector-drawer");
  if (!drawer) {
    drawer = el("div", { class: "overlay", onclick: (e) => { if (e.target === drawer) drawer.remove(); } });
    const panel = el("div", { class: "palette inspector-drawer", role: "dialog", "aria-label": "Details",
      style: "width:min(560px,94vw); max-height:82vh; overflow:auto; margin-top:9vh" });
    drawer._panel = panel; drawer.append(panel); document.body.append(drawer);
    document.addEventListener("keydown", function esc(ev) { if (ev.key === "Escape") { drawer.remove(); document.removeEventListener("keydown", esc); } });
  }
  const panel = drawer._panel;
  mount(panel, el("div", { style: "padding:24px" }, el("div", { class: "skeleton", style: "height:20px; width:60%" })));
  let node;
  if (kind === "claim") node = await S.claimDetail(id);
  else if (kind === "evidence") node = await S.evidenceDetail(id);
  else { const d = await api.explain(id).catch((e) => ({ __err: e })); node = d.__err ? S.errState(d.__err)
    : el("div", {}, el("h2", { text: kind || "object" }), el("pre", { class: "mono", style: "white-space:pre-wrap;font-size:12px", text: JSON.stringify(d, null, 2) })); }
  mount(panel, el("div", { style: "padding:24px" },
    el("div", { class: "row", style: "margin-bottom:8px" }, el("span", { style: "flex:1" }),
      el("button", { class: "btn ghost", text: "✕", onclick: () => drawer.remove() })), node));
}
app.inspect = inspect;
app.go = (hash) => { location.hash = hash; };
app.focusGraph = (id) => { if (app.graph) app.graph.focus(id); };

// ---------- command palette / global search (⌘K) ----------
const COMMANDS = [
  { label: "Open Overview", run: () => app.go("#/overview") },
  { label: "Open Brain / Graph", run: () => app.go("#/graph") },
  { label: "Show Claims", run: () => app.go("#/claims") },
  { label: "Show disputed claims", run: () => app.go("#/claims") },
  { label: "Go to Timeline", run: () => app.go("#/timeline") },
  { label: "Open Spaces", run: () => app.go("#/spaces") },
  { label: "Agent Observatory", run: () => app.go("#/agents") },
  { label: "Source Intelligence", run: () => app.go("#/sources") },
  { label: "System Health", run: () => app.go("#/health") },
];
let paletteOpen = false;
function openPalette() {
  if (paletteOpen) return; paletteOpen = true;
  const input = el("input", { placeholder: "Search knowledge or type a command…", "aria-label": "Command palette", autofocus: true });
  const results = el("div", { class: "results", role: "listbox" });
  const box = el("div", { class: "palette", role: "dialog", "aria-label": "Command palette" }, input, results,
    el("div", { class: "foot" }, el("span", { text: "↑↓ navigate" }), el("span", { text: "↵ open" }), el("span", { text: "esc close" })));
  const overlay = el("div", { class: "overlay", onclick: (e) => { if (e.target === overlay) close(); } }, box);
  document.body.append(overlay);
  let items = [], sel = 0, seq = 0;
  function close() { paletteOpen = false; overlay.remove(); }
  function paint() {
    clear(results); if (!items.length) { results.append(el("div", { class: "grp", text: "No matches" })); return; }
    let last = null;
    items.forEach((it, i) => {
      if (it.grp !== last) { results.append(el("div", { class: "grp", text: it.grp })); last = it.grp; }
      const r = el("div", { class: "res", role: "option", "aria-selected": i === sel ? "true" : "false",
        onclick: () => { it.run(); close(); } }, el("span", { class: "rk", text: it.rk }), el("span", { class: "rl", text: it.label }));
      results.append(r);
    });
  }
  async function query(q) {
    const my = ++seq;
    if (!q) { items = COMMANDS.map((c) => ({ grp: "Commands", rk: "cmd", label: c.label, run: c.run })); sel = 0; return paint(); }
    const cmd = COMMANDS.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()))
      .map((c) => ({ grp: "Commands", rk: "cmd", label: c.label, run: c.run }));
    let hits = [];
    try {
      const d = await api.search(q, { limit: 20 });
      if (my !== seq) return;
      hits = d.results.map((r) => ({ grp: r.kind.toUpperCase(), rk: r.kind, label: r.label,
        run: () => inspect(r.id, r.kind) }));
    } catch { /* offline / unauth — commands still work */ }
    items = [...cmd, ...hits]; sel = 0; paint();
  }
  input.addEventListener("input", () => query(input.value.trim()));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { sel = Math.min(items.length - 1, sel + 1); paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { sel = Math.max(0, sel - 1); paint(); e.preventDefault(); }
    else if (e.key === "Enter") { items[sel]?.run(); close(); }
    else if (e.key === "Escape") close();
  });
  overlay.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  query(""); setTimeout(() => input.focus(), 30);
}

// ---------- shell + router ----------
function buildShell() {
  const sidebar = el("nav", { class: "sidebar", "aria-label": "Primary" });
  for (const n of NAV) {
    if (n.g) { sidebar.append(el("div", { class: "group", text: n.g })); continue; }
    sidebar.append(el("a", { class: "navitem", href: n.route, id: "nav-" + n.id },
      el("span", { class: "ic", text: n.ic }), el("span", { text: n.label }),
      el("span", { class: "count", id: "count-" + n.id })));
  }
  const searchBtn = el("button", { class: "searchbtn", onclick: openPalette, "aria-label": "Open search" },
    el("span", { text: "⌕" }), el("span", { text: "Search knowledge…" }), el("kbd", { text: "⌘K" }));
  const main = el("main", { class: "main", id: "main", role: "main", tabindex: "-1" });
  const shell = el("div", { class: "shell" },
    el("div", { class: "brand" }, el("div", { class: "logo" }),
      el("span", { class: "name", html: "EPISTEM<b>O</b>S" })),
    el("header", { class: "topbar" }, searchBtn, el("span", { class: "spacer" }),
      connEl(), el("span", { class: "chip", id: "who", text: app.whoami?.agent || "" })),
    sidebar, main);
  document.body.append(shell);
  return main;
}

async function refreshCounts() {
  try {
    const c = await api.counts(); app.counts = c;
    const set = (id, v) => { const e = document.getElementById("count-" + id); if (e) e.textContent = v; };
    set("claims", c.claims); set("spaces", c.spaces); set("sources", c.sources); set("agents", c.agents);
  } catch { /* keep last known */ }
}

const routes = {
  "": (m) => S.overview(ctx()).then((n) => mount(m, n)),
  "overview": (m) => S.overview(ctx()).then((n) => mount(m, n)),
  "graph": (m) => S.graph(ctx()).then((n) => mount(m, n)),
  "claims": (m) => S.claims(ctx()).then((n) => mount(m, n)),
  "timeline": (m) => S.timeline(ctx()).then((n) => mount(m, n)),
  "spaces": (m) => S.spaces(ctx()).then((n) => mount(m, n)),
  "agents": (m) => S.agents(ctx()).then((n) => mount(m, n)),
  "sources": (m) => S.sources(ctx()).then((n) => mount(m, n)),
  "health": (m) => S.health(ctx()).then((n) => mount(m, n)),
};
function ctx() { return app; }

async function route() {
  const m = document.getElementById("main"); if (!m) return;
  app.feedEl = null; app.graph = null; // reset per-screen live bindings
  const hash = location.hash.replace(/^#\//, "");
  const [head, arg] = [hash.split("/")[0], decodeURIComponent(hash.split("/").slice(1).join("/") || "")];
  app.activeRoute = head || "overview";
  // nav highlight
  document.querySelectorAll(".navitem").forEach((a) => a.removeAttribute("aria-current"));
  document.getElementById("nav-" + (head || "overview"))?.setAttribute("aria-current", "page");
  mount(m, el("div", { class: "view" }, el("div", { class: "skeleton", style: "height:120px" })));
  try {
    if (head === "search") { if (arg) return mount(m, await S.searchResults(ctx(), arg)); return openPalette(), mount(m, await S.overview(ctx())); }
    if (head === "explain") return mount(m, await S.explain(ctx(), arg));
    if (head === "claim") return inspect(arg, "claim");
    const fn = routes[head] ?? routes["overview"];
    await fn(m);
  } catch (e) { mount(m, S.errState(e)); }
  m.focus();
}

// ---------- live: SSE → counters / feed / graph ----------
let graphDebounce = null;
function wireStream() {
  const s = new Stream(); app.stream = s;
  s.addEventListener("state", (e) => updateConn(e.detail));
  s.addEventListener("event", (e) => {
    const ev = e.detail;
    // prepend to a visible feed with a meaningful entrance
    if (app.feedEl) { const row = S.eventRow(ev, ctx(), true); app.feedEl.prepend(row);
      while (app.feedEl.children.length > 200) app.feedEl.lastChild.remove(); }
    // live counters
    refreshCounts();
    // graph: debounced reload so genuinely-new nodes pulse in (preserve positions)
    if (app.activeRoute === "graph" && app.graph) {
      clearTimeout(graphDebounce);
      graphDebounce = setTimeout(async () => {
        try { const g = await api.graph({ limit: 1500 }); app.graph.setData(g.nodes, g.edges, { preservePositions: true }); } catch { /* ignore */ }
      }, 1200);
    }
  });
  s.connect();
}

// ---------- login ----------
async function login() {
  const box = el("div", { class: "box" });
  const wrap = el("div", { class: "login", role: "dialog", "aria-label": "Sign in" }, box);
  const doLogin = async (token) => {
    try { await api.session(token); wrap.remove(); await boot(); }
    catch (e) { err.textContent = e.status === 401 ? "Unknown token." : (e.message || "Sign-in failed"); }
  };
  const err = el("div", { style: "color:var(--danger); font-size:12px; margin-top:8px" });
  box.append(el("div", { class: "row" }, el("div", { class: "logo", style: "width:26px;height:26px" }),
    el("h2", { html: "EPISTEM<b style='color:var(--amber)'>O</b>S" })),
    el("div", { class: "sub", style: "color:var(--fg-3); margin-bottom:12px", text: "Living Knowledge Interface" }));
  const demo = await api.demoIdentities().catch(() => ({ identities: [] }));
  if (demo.identities?.length) {
    box.append(el("div", { class: "sub", style: "color:var(--fg-2); margin-bottom:6px", text: "Demo identities (local corpus):" }));
    for (const id of demo.identities) box.append(el("button", { class: "btn idbtn", onclick: () => doLogin(id.token) },
      el("b", { text: id.agent }), el("span", { class: "sub", style: "color:var(--fg-3); font-size:11px", text: id.label })));
  }
  const tok = el("input", { placeholder: "or paste a bearer token", "aria-label": "Bearer token",
    onkeydown: (e) => { if (e.key === "Enter" && tok.value.trim()) doLogin(tok.value.trim()); } });
  box.append(el("div", { style: "margin-top:14px" }, tok,
    el("button", { class: "btn primary", style: "width:100%; margin-top:8px; justify-content:center",
      text: "Sign in", onclick: () => tok.value.trim() && doLogin(tok.value.trim()) })), err);
  document.body.append(wrap);
}

// ---------- boot ----------
async function boot() {
  try { app.whoami = await api.whoami(); }
  catch (e) { if (e.status === 401) return login(); throw e; }
  if (!document.querySelector(".shell")) {
    buildShell();
    window.addEventListener("hashchange", route);
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); }
    });
    wireStream();
  }
  const who = document.getElementById("who"); if (who) who.textContent = app.whoami.agent;
  await refreshCounts();
  if (!location.hash) location.hash = "#/overview";
  route();
}

boot();
