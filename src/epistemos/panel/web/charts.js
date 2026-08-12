// Minimal SVG charts (no dependency). All data is real (ledger-derived); no synthetic series.
import { el } from "./dom.js";

const NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs) { const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; }

export function sparkline(values, { color = "var(--indigo)", h = 40 } = {}) {
  const s = svg("svg", { class: "spark", viewBox: `0 0 100 ${h}`, preserveAspectRatio: "none" });
  const max = Math.max(1, ...values), n = values.length;
  if (n < 2) { s.append(svg("line", { x1: 0, y1: h - 2, x2: 100, y2: h - 2, stroke: "var(--line)" })); return s; }
  const pts = values.map((v, i) => `${(i / (n - 1)) * 100},${h - 2 - (v / max) * (h - 4)}`).join(" ");
  const area = svg("polygon", { points: `0,${h} ${pts} 100,${h}`, fill: color, "fill-opacity": ".12" });
  const line = svg("polyline", { points: pts, fill: "none", stroke: color, "stroke-width": "1.6", "vector-effect": "non-scaling-stroke" });
  s.append(area, line); return s;
}

export function bars(series) {
  // series: [{label, value, color?}]
  const max = Math.max(1, ...series.map((d) => d.value));
  const wrap = el("div", { class: "bars", role: "img", "aria-label":
    "Activity per minute: " + series.map((d) => `${d.label} ${d.value}`).join(", ") });
  for (const d of series) {
    const b = el("div", { class: "bar", title: `${d.label}: ${d.value}` });
    b.style.height = `${Math.max(2, (d.value / max) * 88)}px`;
    if (d.color) b.style.background = d.color;
    wrap.append(b);
  }
  return wrap;
}

export function donut(parts, { size = 120 } = {}) {
  // parts: [{label, value, color}]
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  const s = svg("svg", { width: size, height: size, viewBox: "0 0 42 42", role: "img",
    "aria-label": "Distribution: " + parts.map((p) => `${p.label} ${p.value}`).join(", ") });
  s.append(svg("circle", { cx: 21, cy: 21, r: 15.9, fill: "none", stroke: "var(--bg-3)", "stroke-width": "5" }));
  let off = 25; // start at top
  for (const p of parts) {
    const frac = p.value / total; if (frac <= 0) continue;
    const c = svg("circle", { cx: 21, cy: 21, r: 15.9, fill: "none", stroke: p.color, "stroke-width": "5",
      "stroke-dasharray": `${frac * 100} ${100 - frac * 100}`, "stroke-dashoffset": off, transform: "rotate(-90 21 21)" });
    s.append(c); off -= frac * 100;
  }
  return s;
}
