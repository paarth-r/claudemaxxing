"""brain dash: a local graph view of this repo's brain.

Obsidian draws a neutral web of notes. This draws the thing Obsidian cannot: each
rule's TRACK RECORD. A rule carries evidence - satisfied, overridden, strikes left -
and lives or dies by it. So the node encodes it: an evidence ring, a strike count,
and a rule two overrides from retirement drawn as visibly dying.

Self-contained: one HTML file, no CDN, no dependencies, no network. Served from
stdlib http.server on localhost and nowhere else.
"""

from __future__ import annotations

import http.server
import json
import socket
import socketserver
import threading
import webbrowser
from pathlib import Path

from hookkit.graph import build

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>brain / __REPO__</title>
<style>
  :root {
    --ink: #0b0d0e;
    --panel: #101314;
    --line: #1d2426;
    --bone: #e8e3d9;
    --dim: #74858c;
    --learning: #c9932b;
    --enforced: #56a06b;
    --contested: #c97f3e;
    --dying: #c0503f;
    --note: #4e6773;
    --archived: #2e3436;
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--ink);
    color: var(--bone);
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.5;
    overflow: hidden;
    display: grid;
    grid-template-rows: auto 1fr;
  }

  header {
    border-bottom: 1px solid var(--line);
    padding: 14px 20px;
    display: flex;
    align-items: baseline;
    gap: 20px;
    flex-wrap: wrap;
  }
  .mast {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
  }
  .mast span { color: var(--dim); font-weight: 400; }
  .counts { color: var(--dim); letter-spacing: 0.04em; }
  .legend { margin-left: auto; display: flex; gap: 16px; color: var(--dim); flex-wrap: wrap; }
  .legend b { font-weight: 400; color: var(--bone); }
  .dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 6px; vertical-align: 1px;
  }

  main { display: grid; grid-template-columns: 280px 1fr; min-height: 0; }
  @media (max-width: 820px) { main { grid-template-columns: 1fr; } aside { display: none; } }

  aside {
    border-right: 1px solid var(--line);
    overflow-y: auto;
    padding: 16px 0;
  }
  .rail-title {
    padding: 0 20px 10px;
    color: var(--dim);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-size: 11px;
  }
  .rule {
    padding: 10px 20px;
    cursor: pointer;
    border-left: 2px solid transparent;
  }
  .rule:hover, .rule:focus-visible { background: var(--panel); outline: none; }
  .rule[aria-current="true"] { background: var(--panel); border-left-color: currentColor; }
  .rule .name { color: var(--bone); }
  .rule .meta { color: var(--dim); font-size: 11px; margin-top: 3px; }

  /* The evidence bar: what this rule has actually done. Not decoration - it is the
     reason the rule still exists, or is about to stop existing. */
  .evidence { display: flex; gap: 2px; margin-top: 6px; height: 3px; }
  .evidence i { flex: 1; background: var(--line); border-radius: 1px; }
  .evidence i.on { background: currentColor; }
  .evidence i.strike { background: var(--dying); }

  #stage { position: relative; min-height: 0; }
  canvas { display: block; width: 100%; height: 100%; }
  .hint {
    position: absolute; left: 20px; bottom: 16px; color: var(--dim); font-size: 11px;
    pointer-events: none;
  }

  #detail {
    position: absolute; top: 0; right: 0; bottom: 0; width: min(420px, 92vw);
    background: var(--panel); border-left: 1px solid var(--line);
    padding: 24px; overflow-y: auto;
    transform: translateX(100%);
    transition: transform 180ms ease;
  }
  #detail.open { transform: none; }
  @media (prefers-reduced-motion: reduce) { #detail { transition: none; } }
  #detail h2 { margin: 0 0 4px; font-size: 15px; letter-spacing: 0.04em; }
  #detail .kind { color: var(--dim); font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; }
  #detail pre {
    white-space: pre-wrap; word-break: break-word; color: var(--bone);
    background: var(--ink); border: 1px solid var(--line); padding: 12px;
    margin: 14px 0 0; font-size: 12px;
  }
  #detail dl { margin: 18px 0 0; display: grid; grid-template-columns: auto 1fr; gap: 6px 14px; }
  #detail dt { color: var(--dim); }
  #detail dd { margin: 0; word-break: break-all; }
  #close {
    position: absolute; top: 16px; right: 16px; background: none; border: 0;
    color: var(--dim); font-family: var(--mono); font-size: 16px; cursor: pointer;
  }
  #close:hover, #close:focus-visible { color: var(--bone); outline: none; }

  .verdict { margin-top: 16px; padding: 10px 12px; border: 1px solid currentColor; font-size: 12px; }
  .empty { padding: 60px 20px; text-align: center; color: var(--dim); }
</style>
</head>
<body>
<header>
  <div class="mast">brain <span>/ __REPO__</span></div>
  <div class="counts" id="counts"></div>
  <div class="legend">
    <span><i class="dot" style="background:var(--enforced)"></i><b>enforced</b> earned it</span>
    <span><i class="dot" style="background:var(--learning)"></i><b>learning</b> on probation</span>
    <span><i class="dot" style="background:var(--dying)"></i><b>dying</b> being overridden</span>
    <span><i class="dot" style="background:var(--note)"></i><b>note</b> read on demand</span>
  </div>
</header>

<main>
  <aside>
    <div class="rail-title">Rules, by track record</div>
    <div id="rail"></div>
  </aside>

  <div id="stage">
    <canvas id="c"></canvas>
    <div class="hint">Drag to move a node. Click to read it. Scroll to zoom.</div>
    <div id="detail" role="dialog" aria-label="Node detail">
      <button id="close" aria-label="Close">&times;</button>
      <div id="detail-body"></div>
    </div>
  </div>
</main>

<script>
const DATA = __DATA__;
const COLORS = {
  enforced: '#56a06b', earning: '#56a06b', learning: '#c9932b',
  contested: '#c97f3e', dying: '#c0503f', note: '#4e6773', archived: '#2e3436'
};
const colorOf = n =>
  n.kind === 'note' ? COLORS.note :
  n.kind === 'archived' ? COLORS.archived :
  COLORS[n.health] || COLORS.learning;

const rules = DATA.nodes.filter(n => n.kind === 'rule');
const notes = DATA.nodes.filter(n => n.kind === 'note');
document.getElementById('counts').textContent =
  `${rules.length} rule${rules.length === 1 ? '' : 's'} · ${notes.length} note${notes.length === 1 ? '' : 's'}`;

/* ---- the rail: rules ordered by who is in trouble ---- */
const rail = document.getElementById('rail');
const order = { dying: 0, contested: 1, learning: 2, earning: 3, enforced: 4 };
[...rules].sort((a, b) => (order[a.health] ?? 9) - (order[b.health] ?? 9)).forEach(n => {
  const el = document.createElement('div');
  el.className = 'rule';
  el.tabIndex = 0;
  el.style.color = colorOf(n);
  const strikes = Array.from({length: 3}, (_, i) =>
    i < n.overridden ? '<i class="strike"></i>' : '<i></i>').join('');
  el.innerHTML =
    `<div class="name">${esc(n.label)}</div>
     <div class="meta">${n.health} · fired ${n.fired} · satisfied ${n.satisfied}</div>
     <div class="evidence" title="${n.overridden} of 3 strikes">${strikes}</div>`;
  el.onclick = () => select(n);
  el.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(n); } };
  el.dataset.id = n.id;
  rail.appendChild(el);
});
if (!rules.length) {
  rail.innerHTML = '<div class="empty">No rules yet.<br>Correct the agent and one appears.</div>';
}

/* ---- force layout ---- */
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
let W = 0, H = 0, dpr = 1;

const nodes = DATA.nodes.map((n, i) => ({
  ...n,
  x: Math.cos(i * 2.4) * 120 + (Math.sin(i * 7.1) * 40),
  y: Math.sin(i * 2.4) * 120 + (Math.cos(i * 5.3) * 40),
  vx: 0, vy: 0,
  r: n.kind === 'rule' ? 13 : n.kind === 'archived' ? 7 : 9
}));
const index = new Map(nodes.map(n => [n.id, n]));
const links = DATA.edges.map(e => ({ s: index.get(e.source), t: index.get(e.target) }))
                        .filter(l => l.s && l.t);

let view = { x: 0, y: 0, k: 1 };
let active = null, dragging = null, hovered = null;

function resize() {
  dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  W = rect.width; H = rect.height;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
new ResizeObserver(resize).observe(document.getElementById('stage'));
resize();

function step() {
  for (const n of nodes) {
    // Pull toward centre - but a dying rule drifts out. It is on its way to the
    // archive, and the layout should say so before you read a single word.
    const pull = n.health === 'dying' ? 0.0016 : 0.006;
    n.vx += -n.x * pull;
    n.vy += -n.y * pull;
  }
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      let dx = b.x - a.x, dy = b.y - a.y;
      let d2 = dx * dx + dy * dy || 0.01;
      const push = 2600 / d2;
      const d = Math.sqrt(d2);
      const ux = dx / d, uy = dy / d;
      a.vx -= ux * push; a.vy -= uy * push;
      b.vx += ux * push; b.vy += uy * push;
    }
  }
  for (const l of links) {
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
    const d = Math.hypot(dx, dy) || 0.01;
    const f = (d - 110) * 0.012;
    const ux = dx / d, uy = dy / d;
    l.s.vx += ux * f; l.s.vy += uy * f;
    l.t.vx -= ux * f; l.t.vy -= uy * f;
  }
  for (const n of nodes) {
    if (n === dragging) { n.vx = n.vy = 0; continue; }
    n.vx *= 0.82; n.vy *= 0.82;
    n.x += n.vx; n.y += n.vy;
  }
}

function draw() {
  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.translate(W / 2 + view.x, H / 2 + view.y);
  ctx.scale(view.k, view.k);

  ctx.lineWidth = 1;
  for (const l of links) {
    ctx.strokeStyle = (active && (l.s === active || l.t === active)) ? '#3c4a4e' : '#1d2426';
    ctx.beginPath();
    ctx.moveTo(l.s.x, l.s.y);
    ctx.lineTo(l.t.x, l.t.y);
    ctx.stroke();
  }

  for (const n of nodes) {
    const c = colorOf(n);
    const focused = n === active || n === hovered;

    // A dying rule is drawn as a broken ring. You should be able to see it going,
    // without reading anything.
    if (n.kind === 'rule' && n.overridden > 0) {
      ctx.setLineDash([3, 3]);
    }
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
    ctx.fillStyle = n.kind === 'rule' && n.severity === 'block' ? c : 'rgba(0,0,0,0)';
    ctx.fill();
    ctx.strokeStyle = c;
    ctx.lineWidth = focused ? 2.5 : 1.5;
    ctx.stroke();
    ctx.setLineDash([]);

    // The evidence ring: how much of its probation this rule has served.
    if (n.kind === 'rule' && n.satisfied > 0) {
      const frac = Math.min(1, n.satisfied / 5);
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r + 5, -Math.PI / 2, -Math.PI / 2 + frac * Math.PI * 2);
      ctx.strokeStyle = c;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    if (focused || view.k > 0.85) {
      ctx.fillStyle = focused ? '#e8e3d9' : '#74858c';
      ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(n.label, n.x, n.y + n.r + 16);
    }
  }
  ctx.restore();
}

let settle = reduce ? 0 : 240;
(function loop() {
  if (settle > 0 || dragging) { step(); if (!dragging) settle--; }
  draw();
  requestAnimationFrame(loop);
})();
if (reduce) { for (let i = 0; i < 240; i++) step(); }

/* ---- interaction ---- */
const at = (mx, my) => {
  const x = (mx - W / 2 - view.x) / view.k;
  const y = (my - H / 2 - view.y) / view.k;
  return nodes.find(n => Math.hypot(n.x - x, n.y - y) <= n.r + 6);
};
const pos = e => {
  const r = canvas.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
};

canvas.onmousedown = e => {
  const [mx, my] = pos(e);
  dragging = at(mx, my);
  if (!dragging) canvas._pan = [mx - view.x, my - view.y];
};
canvas.onmousemove = e => {
  const [mx, my] = pos(e);
  if (dragging) {
    dragging.x = (mx - W / 2 - view.x) / view.k;
    dragging.y = (my - H / 2 - view.y) / view.k;
    settle = 40;
  } else if (canvas._pan) {
    view.x = mx - canvas._pan[0];
    view.y = my - canvas._pan[1];
  } else {
    const h = at(mx, my);
    if (h !== hovered) { hovered = h; canvas.style.cursor = h ? 'pointer' : 'grab'; }
  }
};
window.onmouseup = e => {
  if (!dragging && canvas._pan) { canvas._pan = null; return; }
  if (dragging) {
    const [mx, my] = pos(e);
    const moved = Math.hypot(dragging.x - (mx - W / 2 - view.x) / view.k, 0) > 3;
    if (!moved) select(dragging);
  }
  dragging = null; canvas._pan = null;
};
canvas.onclick = e => { const [mx, my] = pos(e); const n = at(mx, my); if (n) select(n); };
canvas.onwheel = e => {
  e.preventDefault();
  view.k = Math.min(3, Math.max(0.3, view.k * (e.deltaY < 0 ? 1.1 : 0.9)));
};

/* ---- detail ---- */
const detail = document.getElementById('detail');
const body = document.getElementById('detail-body');
document.getElementById('close').onclick = close;
document.onkeydown = e => { if (e.key === 'Escape') close(); };
function close() { detail.classList.remove('open'); active = null; mark(); }

function mark() {
  document.querySelectorAll('.rule').forEach(el =>
    el.setAttribute('aria-current', String(active && el.dataset.id === active.id)));
}

function select(n) {
  active = n;
  mark();
  const c = colorOf(n);
  let html = `<div class="kind" style="color:${c}">${n.kind}${n.folder ? ' / ' + esc(n.folder) : ''}</div>
              <h2>${esc(n.label)}</h2>`;

  if (n.kind === 'rule') {
    const verdict =
      n.health === 'dying' ? `Overridden ${n.overridden} times. One more and it retires itself.` :
      n.health === 'contested' ? `Overridden ${n.overridden} time${n.overridden === 1 ? '' : 's'}. ${n.strikes_left} strike${n.strikes_left === 1 ? '' : 's'} left.` :
      n.health === 'enforced' ? 'Earned the right to block. It has never been wrong.' :
      n.health === 'earning' ? 'Close to being promoted to a hard block.' :
      'On probation. It blocks nothing until it proves itself.';
    html += `<div class="verdict" style="color:${c}">${verdict}</div>
      <dl>
        <dt>fires on</dt><dd>${esc(n.trigger)}</dd>
        <dt>needs</dt><dd>${esc(n.receipt)}</dd>
        ${n.remedy ? `<dt>remedy</dt><dd>${esc(n.remedy)}</dd>` : ''}
        <dt>fired</dt><dd>${n.fired}</dd>
        <dt>satisfied</dt><dd>${n.satisfied}</dd>
        <dt>overridden</dt><dd>${n.overridden}</dd>
      </dl>`;
  } else if (n.summary) {
    html += `<dl><dt>summary</dt><dd>${esc(n.summary)}</dd></dl>`;
  }

  if (n.body) html += `<pre>${esc(n.body)}</pre>`;
  body.innerHTML = html;
  detail.classList.add('open');
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g,
    m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}
</script>
</body>
</html>
"""


def _embed(data) -> str:
    """JSON safe to place inside a <script> tag.

    Note and rule bodies are MODEL-AUTHORED. A body containing the literal text
    "</script>" would terminate the script block early and turn everything after it
    into live HTML - an injection into a page served on the user's own machine.
    Escaping "</" closes that hole at the point the payload is embedded, which is
    before any JavaScript runs and therefore before any JS-side escaping could help.
    """
    return (
        json.dumps(data)
        .replace("</", "<\\/")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def _escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render(brain, repo_name: str) -> str:
    """The whole viewer, as one self-contained HTML string."""
    data = build(brain)
    return (
        PAGE
        .replace("__DATA__", _embed(data))
        .replace("__REPO__", _escape_html(repo_name))
    )


def _free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def serve(brain, repo_name: str, port: int = 7373, open_browser: bool = True):
    """Serve the viewer on localhost. Blocks until interrupted."""
    html = render(brain, repo_name).encode()
    chosen = _free_port(port)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # Regenerate on every load so a refresh shows the current brain.
            page = render(brain, repo_name).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *args):
            pass  # a dev tool should not spam the terminal it was launched from

    server = socketserver.TCPServer(("127.0.0.1", chosen), Handler)
    url = "http://127.0.0.1:%d" % chosen

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    return server, url, len(html)
