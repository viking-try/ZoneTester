import { apiGet } from "../api.js";
import { getState, onStateChange } from "../state.js";
import { showToast } from "../components/toast.js";

const GRADE_ORDER = ["A+", "A", "B", "C", "F", "T"];

export async function render(container) {
  container.innerHTML = `
    <h1>Executive Dashboard</h1>
    <div class="kpi-row" id="kpi-row"></div>
    <div class="card" style="margin-bottom:16px;">
      <h2>Grade distribution</h2>
      <div id="grade-bars"></div>
    </div>
    <div class="card">
      <h2>Trend (up-host count, last 90 days)</h2>
      <div id="trend-chart"></div>
    </div>
  `;

  async function load() {
    const zone = getState().zone;
    try {
      const [dash, trends] = await Promise.all([
        apiGet("/dashboard", { zone }),
        apiGet("/dashboard/trends", { zone, days: 90 }),
      ]);
      renderKpis(dash.kpis);
      renderGradeBars(dash.grade_distribution);
      renderTrend(trends.rows);
    } catch (e) {
      showToast(`Failed to load dashboard: ${e.message}`, "error");
    }
  }

  function renderKpis(k) {
    const tiles = [
      ["Total records", k.total_records],
      ["Scannable", k.scannable_records],
      ["Up", k.up_count],
      ["Down", k.down_count],
      ["PQC-ready", k.pqc_count],
      ["Weak cipher", k.weak_cipher_count],
      ["Cleanup candidates", k.cleanup_count],
      ["Certs expiring <30d", k.expiring_cert_count],
    ];
    const row = document.getElementById("kpi-row");
    row.innerHTML = "";
    for (const [label, value] of tiles) {
      const tile = document.createElement("div");
      tile.className = "kpi-tile";
      const v = document.createElement("div");
      v.className = "value";
      v.textContent = value ?? 0;
      const l = document.createElement("div");
      l.className = "label";
      l.textContent = label;
      tile.append(v, l);
      row.appendChild(tile);
    }
  }

  function renderGradeBars(dist) {
    const el = document.getElementById("grade-bars");
    const max = Math.max(1, ...GRADE_ORDER.map((g) => dist[g] || 0));
    el.innerHTML = "";
    for (const g of GRADE_ORDER) {
      const n = dist[g] || 0;
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:6px;";

      const badge = document.createElement("span");
      badge.className = `badge grade-${g}`;
      badge.style.cssText = "width:34px;justify-content:center;";
      badge.textContent = g;

      const track = document.createElement("div");
      track.style.cssText = "flex:1;background:var(--bg-inset);border-radius:4px;overflow:hidden;height:16px;";
      const fill = document.createElement("div");
      fill.style.cssText = `width:${(n / max) * 100}%;background:var(--accent);height:100%;`;
      track.appendChild(fill);

      const count = document.createElement("span");
      count.className = "faint";
      count.style.cssText = "width:36px;text-align:right;";
      count.textContent = n;

      row.append(badge, track, count);
      el.appendChild(row);
    }
  }

  function renderTrend(rows) {
    const el = document.getElementById("trend-chart");
    el.innerHTML = "";
    if (!rows.length) {
      el.innerHTML = `<div class="empty-state">No snapshot history yet — snapshots are captured daily by the beat scheduler.</div>`;
      return;
    }
    const width = 720;
    const height = 160;
    const pad = 24;
    const maxTotal = Math.max(1, ...rows.map((r) => r.total_records || 0));
    const points = rows.map((r, i) => {
      const x = pad + (i / Math.max(1, rows.length - 1)) * (width - pad * 2);
      const y = height - pad - ((r.up_count || 0) / maxTotal) * (height - pad * 2);
      return [x, y];
    });
    const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

    const svgNs = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    const pathEl = document.createElementNS(svgNs, "path");
    pathEl.setAttribute("d", path);
    pathEl.setAttribute("fill", "none");
    pathEl.setAttribute("stroke-width", "2");
    pathEl.style.stroke = "var(--accent)";
    svg.appendChild(pathEl);
    el.appendChild(svg);

    const caption = document.createElement("div");
    caption.className = "faint";
    caption.textContent = `${rows.length} snapshot day(s)`;
    el.appendChild(caption);
  }

  const unsub = onStateChange(load);
  await load();
  return () => unsub();
}
