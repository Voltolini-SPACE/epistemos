// Knowledge Graph Explorer — Canvas 2D, hand-written force layout (no d3/three; nothing external).
// Scales via a spatial grid for repulsion + viewport culling + level-of-detail. Motion is meaningful
// (new nodes pulse in, settle, then quiet) and fully honours prefers-reduced-motion.
import { prefersReducedMotion } from "./dom.js";

const KIND_VAR = {
  entity: "--n-entity", fact: "--n-fact", claim: "--n-claim", evidence: "--n-evidence",
  review: "--n-review", source: "--n-source", decision: "--n-decision", agent: "--n-agent",
  space: "--n-space",
};
const REL_COLOR = {
  SUPPORTS: "#4ADE80", CONTRADICTS: "#FF6B6B", WEAKENS: "#FF8A5B", DERIVED_FROM: "#8B93FF",
  SUPERSEDES: "#C58BFF", REFERENCES: "#7E8AA0", REVIEWED_BY: "#C58BFF", DECIDED_FROM: "#FF8A5B",
};

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#8B93FF";
}

export class GraphCanvas {
  constructor(container, { onSelect, onExpand } = {}) {
    this.container = container;
    this.onSelect = onSelect || (() => {});
    this.onExpand = onExpand || (() => {});
    this.canvas = document.createElement("canvas");
    this.canvas.tabIndex = 0;
    this.canvas.setAttribute("role", "application");
    this.canvas.setAttribute("aria-label",
      "Knowledge graph. Use arrow keys to move between nodes, Enter to open, plus and minus to zoom, f to fit.");
    container.append(this.canvas);
    this.ctx = this.canvas.getContext("2d");
    this.nodes = []; this.edges = []; this.byId = new Map();
    this.cam = { x: 0, y: 0, z: 1 };
    this.alpha = 0; this.selected = null; this.hover = null; this.pinned = new Set();
    this.filter = new Set(); // hidden kinds
    this._raf = null; this._colors = {};
    this._resize = this._resize.bind(this);
    this._loop = this._loop.bind(this);
    this._fitted = false;
    this._bind();
    window.addEventListener("resize", this._resize);
    // The container is often 0×0 at construction (not yet laid out). A ResizeObserver re-sizes the
    // canvas and performs the first fit once real dimensions arrive, so the graph is never blank.
    this._ro = new ResizeObserver(() => {
      this._resize();
      if (!this._fitted && this.container.clientWidth > 0 && this.nodes.length) {
        this._fitted = true; this.fit();
      }
    });
    this._ro.observe(this.container);
    this._resize();
  }

  destroy() {
    cancelAnimationFrame(this._raf);
    window.removeEventListener("resize", this._resize);
    if (this._ro) this._ro.disconnect();
    this.canvas.remove();
  }

  setData(nodes, edges, { preservePositions = false } = {}) {
    this._colors = Object.fromEntries(Object.entries(KIND_VAR).map(([k, v]) => [k, cssVar(v)]));
    const prev = this.byId;
    const w = this.canvas.clientWidth || 800, h = this.canvas.clientHeight || 600;
    this.nodes = nodes.map((n) => {
      const old = preservePositions && prev.get(n.id);
      return {
        ...n,
        x: old ? old.x : (w / 2 + (Math.random() - 0.5) * w * 0.6),
        y: old ? old.y : (h / 2 + (Math.random() - 0.5) * h * 0.6),
        vx: 0, vy: 0, deg: 0, _new: !prev.has(n.id) && prev.size > 0, _t: 0,
      };
    });
    this.byId = new Map(this.nodes.map((n) => [n.id, n]));
    this.edges = edges.filter((e) => this.byId.has(e.source) && this.byId.has(e.target));
    for (const e of this.edges) { this.byId.get(e.source).deg++; this.byId.get(e.target).deg++; }
    if (this.selected && !this.byId.has(this.selected)) this.selected = null;
    if (!preservePositions) this._fitted = false;
    this._reheat();
    // resize+fit after layout settles (rAF), plus the ResizeObserver covers any later size change
    requestAnimationFrame(() => this._resize());
  }

  _reheat() {
    this.alpha = 1;
    if (prefersReducedMotion()) {
      // no animation: settle synchronously in a bounded number of ticks, render once
      for (let i = 0; i < 140 && this.alpha > 0.02; i++) this._tick();
      this.alpha = 0; this._render();
    } else if (!this._raf) {
      this._raf = requestAnimationFrame(this._loop);
    }
  }

  visibleNodes() { return this.nodes.filter((n) => !this.filter.has(n.kind)); }

  // ---- physics (spatial-grid repulsion → ~O(n); springs; gravity) ----
  _tick() {
    const nodes = this.visibleNodes();
    const n = nodes.length; if (!n) return;
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    const cell = 60, grid = new Map();
    const key = (x, y) => `${Math.floor(x / cell)},${Math.floor(y / cell)}`;
    for (const nd of nodes) { const k = key(nd.x, nd.y); (grid.get(k) || grid.set(k, []).get(k)).push(nd); }
    const rep = 900 * this.alpha + 200;
    for (const nd of nodes) {
      const cx = Math.floor(nd.x / cell), cy = Math.floor(nd.y / cell);
      for (let gx = cx - 1; gx <= cx + 1; gx++) for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const bucket = grid.get(`${gx},${gy}`); if (!bucket) continue;
        for (const o of bucket) {
          if (o === nd) continue;
          let dx = nd.x - o.x, dy = nd.y - o.y, d2 = dx * dx + dy * dy || 0.01;
          if (d2 > cell * cell * 4) continue;
          const f = rep / d2; nd.vx += dx * f * 0.02; nd.vy += dy * f * 0.02;
        }
      }
    }
    for (const e of this.edges) {
      const a = this.byId.get(e.source), b = this.byId.get(e.target);
      if (this.filter.has(a.kind) || this.filter.has(b.kind)) continue;
      let dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01;
      const target = 110, f = (d - target) / d * 0.04 * this.alpha;
      a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
    }
    const cxw = w / 2, cyw = h / 2;
    for (const nd of nodes) {
      nd.vx += (cxw - nd.x) * 0.002 * this.alpha; nd.vy += (cyw - nd.y) * 0.002 * this.alpha;
      if (this.pinned.has(nd.id) || nd === this._dragging) { nd.vx = nd.vy = 0; continue; }
      nd.vx *= 0.86; nd.vy *= 0.86;
      nd.x += Math.max(-20, Math.min(20, nd.vx)); nd.y += Math.max(-20, Math.min(20, nd.vy));
      if (nd._new && nd._t < 1) nd._t = Math.min(1, nd._t + 0.05);
    }
    this.alpha *= 0.985;
    if (this.alpha < 0.02) this.alpha = 0;
  }

  _loop() {
    if (this.alpha > 0) this._tick();
    this._render();
    // keep animating new-node pulses briefly even after cooling
    const pulsing = this.nodes.some((n) => n._new && n._t < 1);
    if (this.alpha > 0 || pulsing || this._dragging) this._raf = requestAnimationFrame(this._loop);
    else { this._raf = null; this.nodes.forEach((n) => { n._new = false; }); }
  }

  // ---- rendering ----
  _resize() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (w === 0 || h === 0) return; // container not laid out yet — keep last good size, don't zero it
    this.canvas.width = w * dpr; this.canvas.height = h * dpr;
    this.canvas.style.width = w + "px"; this.canvas.style.height = h + "px";
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!this._fitted && this.nodes.length) { this._fitted = true; this.fit(); }
    else this._render();
  }

  _toScreen(x, y) { return [(x - this.cam.x) * this.cam.z, (y - this.cam.y) * this.cam.z]; }
  _toWorld(sx, sy) { return [sx / this.cam.z + this.cam.x, sy / this.cam.z + this.cam.y]; }
  _radius(nd) { return Math.min(16, 4 + Math.sqrt(nd.deg + 1) * 2.2) * (0.7 + 0.3 * (nd._t || 1)); }

  _render() {
    const ctx = this.ctx, z = this.cam.z;
    const W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    ctx.clearRect(0, 0, W, H);
    const showLabels = z > 0.85; // LOD: labels only when zoomed in enough
    const showEdges = z > 0.35;
    const hi = this._highlightSet();
    if (showEdges) {
      for (const e of this.edges) {
        const a = this.byId.get(e.source), b = this.byId.get(e.target);
        if (this.filter.has(a.kind) || this.filter.has(b.kind)) continue;
        const [ax, ay] = this._toScreen(a.x, a.y), [bx, by] = this._toScreen(b.x, b.y);
        if (Math.max(ax, bx) < 0 || Math.min(ax, bx) > W || Math.max(ay, by) < 0 || Math.min(ay, by) > H) continue;
        const active = hi && (hi.has(a.id) && hi.has(b.id));
        ctx.strokeStyle = REL_COLOR[e.rel] || "#3a4056";
        ctx.globalAlpha = hi ? (active ? 0.9 : 0.08) : (e.rel === "CONTRADICTS" ? 0.7 : 0.32);
        ctx.lineWidth = (e.rel === "CONTRADICTS" ? 1.6 : 1) * (active ? 1.8 : 1);
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
        if (active && showLabels) this._edgeLabel(ctx, ax, ay, bx, by, e.rel);
      }
      ctx.globalAlpha = 1;
    }
    for (const nd of this.visibleNodes()) {
      const [sx, sy] = this._toScreen(nd.x, nd.y);
      const r = this._radius(nd) * z;
      if (sx < -30 || sx > W + 30 || sy < -30 || sy > H + 30) continue; // viewport culling
      const dim = hi && !hi.has(nd.id);
      ctx.globalAlpha = dim ? 0.15 : 1;
      const color = this._colors[nd.kind] || "#8B93FF";
      if (nd._new && nd._t < 1) { // meaningful entrance pulse
        ctx.beginPath(); ctx.arc(sx, sy, r + (1 - nd._t) * 18, 0, 7); ctx.fillStyle = color;
        ctx.globalAlpha = (1 - nd._t) * 0.25; ctx.fill(); ctx.globalAlpha = dim ? 0.15 : 1;
      }
      if (nd.id === this.selected) { ctx.beginPath(); ctx.arc(sx, sy, r + 5, 0, 7);
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke(); }
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, 7); ctx.fillStyle = color; ctx.fill();
      if (this.pinned.has(nd.id)) { ctx.strokeStyle = "#F0B54A"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(sx, sy, r + 2.5, 0, 7); ctx.stroke(); }
      // status ring for claims (belief-ish shape, not color-only: disputed gets a dashed ring)
      if (nd.kind === "claim" && nd.status && nd.status !== "open") {
        ctx.strokeStyle = "#6E7488"; ctx.setLineDash([2, 2]); ctx.beginPath();
        ctx.arc(sx, sy, r + 3, 0, 7); ctx.stroke(); ctx.setLineDash([]);
      }
      if (showLabels && (!dim || nd.id === this.hover)) {
        ctx.globalAlpha = dim ? 0.4 : 0.92; ctx.fillStyle = "#E8EAF2";
        ctx.font = "11px ui-sans-serif, system-ui"; ctx.textAlign = "center";
        const lbl = (nd.label || nd.id).slice(0, 26);
        ctx.fillText(lbl, sx, sy + r + 13);
      }
      ctx.globalAlpha = 1;
    }
  }
  _edgeLabel(ctx, ax, ay, bx, by, rel) {
    ctx.save(); ctx.globalAlpha = 0.9; ctx.fillStyle = "#A9AFC4";
    ctx.font = "9px ui-monospace, monospace"; ctx.textAlign = "center";
    ctx.fillText(rel, (ax + bx) / 2, (ay + by) / 2 - 3); ctx.restore();
  }
  _highlightSet() {
    const id = this.hover || this.selected; if (!id) return null;
    const set = new Set([id]);
    for (const e of this.edges) { if (e.source === id) set.add(e.target); if (e.target === id) set.add(e.source); }
    return set;
  }

  // ---- interaction ----
  _bind() {
    const c = this.canvas;
    c.addEventListener("wheel", (e) => {
      e.preventDefault();
      const [wx, wy] = this._toWorld(e.offsetX, e.offsetY);
      this.cam.z = Math.max(0.15, Math.min(4, this.cam.z * (e.deltaY < 0 ? 1.1 : 0.9)));
      const [nx, ny] = this._toWorld(e.offsetX, e.offsetY);
      this.cam.x += wx - nx; this.cam.y += wy - ny; this._render();
    }, { passive: false });
    let down = null, moved = false;
    c.addEventListener("pointerdown", (e) => {
      c.setPointerCapture(e.pointerId); moved = false;
      const nd = this._pick(e.offsetX, e.offsetY);
      down = { sx: e.offsetX, sy: e.offsetY, cam: { ...this.cam }, nd };
      if (nd) { this._dragging = nd; this.pinned.add(nd.id); this._reheat(); }
    });
    c.addEventListener("pointermove", (e) => {
      const nd = this._pick(e.offsetX, e.offsetY);
      if (nd?.id !== this.hover) { this.hover = nd?.id || null; c.style.cursor = nd ? "pointer" : "grab"; this._render(); this._emitHover(nd); }
      if (!down) return;
      if (Math.abs(e.offsetX - down.sx) + Math.abs(e.offsetY - down.sy) > 3) moved = true;
      if (this._dragging) {
        const [wx, wy] = this._toWorld(e.offsetX, e.offsetY);
        this._dragging.x = wx; this._dragging.y = wy; this._dragging.vx = this._dragging.vy = 0;
        if (!this._raf && !prefersReducedMotion()) this._raf = requestAnimationFrame(this._loop); else this._render();
      } else {
        this.cam.x = down.cam.x - (e.offsetX - down.sx) / this.cam.z;
        this.cam.y = down.cam.y - (e.offsetY - down.sy) / this.cam.z; this._render();
      }
    });
    const up = (e) => {
      if (down && !moved && down.nd) this.select(down.nd.id);
      this._dragging = null; down = null;
    };
    c.addEventListener("pointerup", up);
    c.addEventListener("pointercancel", up);
    c.addEventListener("dblclick", (e) => { const nd = this._pick(e.offsetX, e.offsetY); if (nd) this.onExpand(nd.id); });
    c.addEventListener("keydown", (e) => this._key(e));
  }

  _emitHover(nd) { this.container.dispatchEvent(new CustomEvent("nodehover", { detail: nd || null })); }

  _pick(sx, sy) {
    let best = null, bestD = 18;
    for (const nd of this.visibleNodes()) {
      const [x, y] = this._toScreen(nd.x, nd.y);
      const d = Math.hypot(x - sx, y - sy);
      if (d < Math.max(bestD, this._radius(nd) * this.cam.z + 4)) { best = nd; bestD = d; }
    }
    return best;
  }

  _key(e) {
    if (e.key === "+" || e.key === "=") { this.zoomBy(1.15); e.preventDefault(); }
    else if (e.key === "-") { this.zoomBy(0.87); e.preventDefault(); }
    else if (e.key === "f") { this.fit(); e.preventDefault(); }
    else if (e.key === "Enter" && this.selected) { this.onExpand(this.selected); e.preventDefault(); }
    else if (e.key.startsWith("Arrow")) {
      e.preventDefault(); this._arrowNav(e.key);
    }
  }
  _arrowNav(key) {
    const vis = this.visibleNodes(); if (!vis.length) return;
    if (!this.selected) { this.select(vis[0].id); return; }
    const cur = this.byId.get(this.selected);
    const dir = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] }[key];
    let best = null, bestScore = Infinity;
    for (const nd of vis) {
      if (nd === cur) continue;
      const dx = nd.x - cur.x, dy = nd.y - cur.y;
      const along = dx * dir[0] + dy * dir[1]; if (along <= 0) continue;
      const off = Math.abs(dx * dir[1] - dy * dir[0]);
      const score = off * 2 + along * 0.5;
      if (score < bestScore) { bestScore = score; best = nd; }
    }
    if (best) this.select(best.id);
  }

  select(id) {
    this.selected = id; const nd = this.byId.get(id);
    if (nd) { // ensure it's on screen
      const [sx, sy] = this._toScreen(nd.x, nd.y);
      const W = this.canvas.clientWidth, H = this.canvas.clientHeight;
      if (sx < 40 || sx > W - 40 || sy < 40 || sy > H - 40) { this.cam.x = nd.x - W / 2 / this.cam.z; this.cam.y = nd.y - H / 2 / this.cam.z; }
    }
    this._render(); this.onSelect(id, nd);
  }
  zoomBy(f) { this.cam.z = Math.max(0.15, Math.min(4, this.cam.z * f)); this._render(); }
  togglePin(id) { if (this.pinned.has(id)) this.pinned.delete(id); else this.pinned.add(id); this._render(); }
  setFilter(kinds) { this.filter = new Set(kinds); this._reheat(); }
  focus(id) { const nd = this.byId.get(id); if (nd) { this.cam.z = 1.3; this.select(id); } }

  fit() {
    const vis = this.visibleNodes(); if (!vis.length) { this._render(); return; }
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    for (const nd of vis) { minx = Math.min(minx, nd.x); miny = Math.min(miny, nd.y); maxx = Math.max(maxx, nd.x); maxy = Math.max(maxy, nd.y); }
    const W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    const pad = 80, gw = Math.max(1, maxx - minx), gh = Math.max(1, maxy - miny);
    this.cam.z = Math.max(0.2, Math.min(2, Math.min((W - pad) / gw, (H - pad) / gh)));
    this.cam.x = (minx + maxx) / 2 - W / 2 / this.cam.z;
    this.cam.y = (miny + maxy) / 2 - H / 2 / this.cam.z;
    this._render();
  }
}

export { REL_COLOR, KIND_VAR };
