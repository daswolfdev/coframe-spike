// perfmon dashboard — a pure derived view over the api read contract (#15).
// One state object, whole-section render(); no partial-DOM bookkeeping.
// ?fixture=1 serves committed sample data through the same fetch seam.

const POLL_MS = 5000;
const CONFIG_POLL_MS = 60000; // config is nearly static — spare the endpoint
const FETCH_TIMEOUT_MS = 4000; // < POLL_MS: hung requests die before the next tick
const FIXTURE = new URLSearchParams(location.search).has('fixture');

const state = {
  sites: [], site: null, pages: [], trend: [], config: null,
  error: false, updated: null,
};

let fixtureData = null;

// 404 (endpoint or site not there yet) → fallback, rendered as "no data yet",
// with a console.warn so a persistent 404 (typo, renamed route) stays findable.
// Network errors / 5xx / timeouts (api down) → throw, rendered as the banner.
// fixture.json is keyed by exact request path — no second URL grammar here.
async function get(path, fallback) {
  if (FIXTURE) {
    if (!fixtureData) fixtureData = await (await fetch('fixture.json')).json();
    return fixtureData[path] ?? fallback;
  }
  // the '/api' prefix must match the proxy mount in nginx.conf
  const r = await fetch('/api' + path, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
  if (r.status === 404) {
    console.warn(`GET ${path} → 404, rendering "no data yet"`);
    return fallback;
  }
  if (!r.ok) throw new Error(`${r.status} on ${path}`);
  return r.json();
}

// Single-flight token: a newer refresh (poll tick or site switch) supersedes
// an in-flight one, so a slow response can never overwrite fresher state.
let refreshSeq = 0;
let configFetchedAt = 0;
let configSite = null;

async function refresh() {
  const seq = ++refreshSeq;
  try {
    const sites = await get('/sites', []);
    if (seq !== refreshSeq) return;
    state.sites = sites;
    if (!state.sites.includes(state.site)) state.site = state.sites[0] ?? null;
    if (state.site) {
      const site = encodeURIComponent(state.site);
      const wantConfig = state.site !== configSite ||
        Date.now() - configFetchedAt >= CONFIG_POLL_MS;
      const [pages, trend, config] = await Promise.all([
        get(`/sites/${site}/pages`, []),
        get(`/sites/${site}/trend`, []),
        wantConfig ? get(`/config/${site}`, null) : state.config,
      ]);
      if (seq !== refreshSeq) return;
      state.pages = pages;
      state.trend = trend;
      state.config = config;
      if (wantConfig) {
        configFetchedAt = Date.now();
        configSite = state.site;
      }
    } else {
      state.pages = []; state.trend = []; state.config = null;
    }
    state.error = false;
    state.updated = new Date();
  } catch (err) {
    if (seq !== refreshSeq) return; // superseded — the newer run reports
    state.error = true; // keep last-rendered data; the banner marks it stale
    console.error('refresh failed:', err);
  }
  render();
}

const $ = (id) => document.getElementById(id);

function el(tag, text, className) {
  const e = document.createElement(tag);
  if (text != null) e.textContent = text;
  if (className) e.className = className;
  return e;
}

const fmtInt = (n) => n.toLocaleString('en-US');
const fmtMs = (ms) => `${Math.round(ms).toLocaleString('en-US')} ms`;

function ago(ms) {
  const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function render() {
  const banner = $('banner');
  banner.hidden = !state.error;
  if (state.error) {
    banner.textContent = state.updated
      ? '⚠ API unreachable — showing last loaded data, which may be stale.'
      : '⚠ API unreachable — no data loaded yet.';
  }
  $('updated').textContent =
    state.updated ? `updated ${state.updated.toLocaleTimeString()}` : '';
  renderSites();
  renderPages();
  renderTrend();
  renderExperiments();
}

function renderSites() {
  const sel = $('site');
  sel.replaceChildren(
    ...state.sites.map((s) => new Option(s, s, false, s === state.site)));
  sel.disabled = !state.sites.length;
}

function renderPages() {
  if (!state.pages.length) {
    const td = el('td', 'no data yet', 'empty');
    td.colSpan = 4;
    const tr = document.createElement('tr');
    tr.append(td);
    $('pages').replaceChildren(tr);
    return;
  }
  $('pages').replaceChildren(...state.pages.map((p) => {
    const tr = document.createElement('tr');
    tr.append(
      el('td', p.page_url),
      el('td', fmtInt(p.count), 'num'),
      el('td', fmtMs(p.p75_ms), 'num'),
      el('td', ago(p.last_seen_ms), 'num'));
    return tr;
  }));
}

function renderExperiments() {
  const host = $('experiments');
  const exps = state.config?.experiments ?? [];
  if (!exps.length) {
    host.replaceChildren(el('p', 'no data yet', 'empty'));
    return;
  }
  const rows = exps.map((x) => {
    const row = el('div', null, 'exp');
    row.append(
      el('span', null, 'swatch'),
      el('strong', x.id ?? '(unnamed)'),
      el('span', (x.variants ?? []).join(' / '), 'empty'),
      el('span', x.traffic == null ? '' : `${Math.round(x.traffic * 100)}% of traffic`, 'empty'));
    return row;
  });
  if (state.config?.sampling_rate != null) {
    rows.push(el('p', `sampling rate ${state.config.sampling_rate}`, 'muted'));
  }
  host.replaceChildren(...rows);
}

// --- trend sparkline: single series, inline SVG, crosshair + tooltip ---

const W = 640, H = 150, PAD_X = 8, PAD_TOP = 14, PAD_BOT = 22;
const svgEl = (tag, attrs) => {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};

function renderTrend() {
  const host = $('trend');
  const pts = state.trend;
  if (pts.length < 2) {
    host.replaceChildren(el('p',
      pts.length ? `${fmtMs(pts[0].p75_ms)} (one point so far)` : 'no data yet',
      'empty'));
    return;
  }
  const t0 = pts[0].bucket_start_ms, t1 = pts[pts.length - 1].bucket_start_ms;
  const vals = pts.map((p) => p.p75_ms);
  const vMin = Math.min(...vals), vMax = Math.max(...vals);
  const x = (t) => PAD_X + ((t - t0) / (t1 - t0 || 1)) * (W - 2 * PAD_X);
  const y = (v) => vMax === vMin
    ? H / 2
    : PAD_TOP + (1 - (v - vMin) / (vMax - vMin)) * (H - PAD_TOP - PAD_BOT);
  const xy = pts.map((p) => [x(p.bucket_start_ms), y(p.p75_ms)]);

  const css = getComputedStyle(document.documentElement);
  const [series, muted, baseline, surface] =
    ['--series-1', '--muted', '--baseline', '--surface'].map((v) => css.getPropertyValue(v).trim());

  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  svg.append(
    svgEl('line', { x1: PAD_X, y1: H - PAD_BOT, x2: W - PAD_X, y2: H - PAD_BOT,
                    stroke: baseline, 'stroke-width': 1 }),
    svgEl('path', { d: 'M' + xy.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join('L'),
                    fill: 'none', stroke: series, 'stroke-width': 2,
                    'stroke-linejoin': 'round', 'stroke-linecap': 'round' }),
    svgEl('circle', { cx: xy[xy.length - 1][0], cy: xy[xy.length - 1][1], r: 3,
                      fill: series, stroke: surface, 'stroke-width': 2 }));

  // axis extremes in muted ink — recessive, no grid
  const label = (text, attrs) => {
    const t = svgEl('text', { fill: muted, 'font-size': 11, ...attrs });
    t.textContent = text;
    return t;
  };
  svg.append(
    label(new Date(t0).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          { x: PAD_X, y: H - 6 }),
    label(new Date(t1).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          { x: W - PAD_X, y: H - 6, 'text-anchor': 'end' }),
    label(fmtMs(vMax), { x: W - PAD_X, y: PAD_TOP - 3, 'text-anchor': 'end' }));

  // hover layer: crosshair + dot + tooltip on nearest point
  const cross = svgEl('line', { y1: PAD_TOP, y2: H - PAD_BOT, stroke: muted,
                                'stroke-width': 1, 'stroke-dasharray': '3,3', visibility: 'hidden' });
  const dot = svgEl('circle', { r: 4, fill: series, stroke: surface,
                                'stroke-width': 2, visibility: 'hidden' });
  const tip = el('div', null, 'tooltip');
  svg.append(cross, dot);
  svg.addEventListener('pointermove', (ev) => {
    const box = svg.getBoundingClientRect();
    const mx = ((ev.clientX - box.left) / box.width) * W;
    let i = 0;
    for (let k = 1; k < xy.length; k++) {
      if (Math.abs(xy[k][0] - mx) < Math.abs(xy[i][0] - mx)) i = k;
    }
    cross.setAttribute('x1', xy[i][0]);
    cross.setAttribute('x2', xy[i][0]);
    dot.setAttribute('cx', xy[i][0]);
    dot.setAttribute('cy', xy[i][1]);
    cross.setAttribute('visibility', 'visible');
    dot.setAttribute('visibility', 'visible');
    tip.textContent =
      `${new Date(pts[i].bucket_start_ms).toLocaleTimeString()} · ${fmtMs(pts[i].p75_ms)}`;
    tip.style.display = 'block';
    tip.style.left = `${(xy[i][0] / W) * box.width}px`;
    tip.style.top = `${(xy[i][1] / H) * box.height - 8}px`;
  });
  svg.addEventListener('pointerleave', () => {
    cross.setAttribute('visibility', 'hidden');
    dot.setAttribute('visibility', 'hidden');
    tip.style.display = 'none';
  });

  host.replaceChildren(svg, tip);
}

$('site').addEventListener('change', (ev) => {
  state.site = ev.target.value;
  refresh();
});

refresh();
setInterval(refresh, POLL_MS);
