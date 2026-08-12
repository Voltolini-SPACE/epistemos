// Tiny DOM helpers — no framework, no dependency. Everything the panel renders goes through `el`.
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    // NOTE: no HTML-string sink by design — all content is set via `text` (textContent) or
    // appended as text-node children, so user-controlled strings can never inject markup (XSS).
    else if (k === "text") node.textContent = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k in node && k !== "list") { try { node[k] = v; } catch { node.setAttribute(k, v); } }
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const clear = (node) => { while (node.firstChild) node.removeChild(node.firstChild); return node; };
export function mount(root, ...nodes) { clear(root); for (const n of nodes.flat()) if (n) root.append(n); return root; }

// short, stable id label
export const shortId = (id) => (id || "").length > 10 ? id.slice(0, 10) + "…" : (id || "");
// relative time from an ISO string
export function rel(iso) {
  if (!iso) return "";
  const t = Date.parse(iso); if (Number.isNaN(t)) return iso;
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
export const hhmmss = (iso) => (iso || "").slice(11, 19) || "--:--:--";
export const esc = (s) => String(s == null ? "" : s);
export const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
