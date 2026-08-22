import { apiGet } from "../api.js";
import { getState, onStateChange } from "../state.js";
import { showToast } from "../components/toast.js";

const GRADE_ORDER = ["A+", "A", "B", "C", "F", "T"];

export async function render(container) {
  container.innerHTML = `
    <h1>Executive Dashboard</h1>
    <div class="kpi-row" id="kpi-row"></div>
    <div class="card" style="margin-bottom:16px;">
      <h2>Grade distribution <span class="faint" style="font-weight:normal;font-size:12px;">(click a grade to drill down)</span></h2>
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
      { label: "Total records", value: k.total_records, route: "#/records" },
      { label: "Scannable", value: k.scannable_records, route: "#/records" },
      { label: "Up", value: k.up_count, route: "#/records?state=up" },
      { label: "Down", value: k.down_count, route: "#/records?state=down" },
      { label: "PQC-ready", value: k.pqc_count, route: "#/records?pqc=true" },
      { label: "Weak cipher", value: k.weak_cipher_count, route: "#/records?weak_cipher=true" },
      { label: "Cleanup candidates", value: k.cleanup_count, route: "#/cleanup" },
      { label: "Certs expiring <30d", value: k.expiring_cert_count, route: "#/records" },
    ];
    const row = document.getElementById("kpi-row");
    row.innerHTML = "";
    for (const item of tiles) {
      const tile = document.createElement("div");
      tile.className = "kpi-tile clickable";
      tile.title = `View records for ${item.label}`;
      tile.onclick = () => {
        window.location.hash = item.route;
      };

      const hint = document.createElement("span");
      hint.className = "kpi-drilldown-hint";
      hint.textContent = "View →";

      const v = document.createElement("div");
      v.className = "value";
      v.textContent = item.value ?? 0;

      const l = document.createElement("div");
      l.className = "label";
      l.textContent = item.label;

      tile.append(hint, v, l);
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
      row.className = "grade-bar-row";
      row.title = `View all grade ${g} records (${n})`;
      row.onclick = () => {
        window.location.hash = `#/records?grade=${encodeURIComponent(g)}`;
      };

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
      count.style.cssText = "width:48px;text-align:right;font-weight:600;";
      count.textContent = `${n} →`;

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

    // Add dots for points
    points.forEach(([x, y], i) => {
      const circle = document.createElementNS(svgNs, "circle");
      circle.setAttribute("cx", x);
      circle.setAttribute("cy", y);
      circle.setAttribute("r", "3.5");
      circle.setAttribute("fill", "var(--accent)");
      const title = document.createElementNS(svgNs, "title");
      title.textContent = `${rows[i].snapshot_date}: ${rows[i].up_count || 0} up / ${rows[i].total_records || 0} total`;
      circle.appendChild(title);
      svg.appendChild(circle);
    });

    el.appendChild(svg);

    const caption = document.createElement("div");
    caption.className = "faint";
    caption.textContent = `${rows.length} snapshot day(s) · hover data points for snapshot details`;
    el.appendChild(caption);
  }

  const unsub = onStateChange(load);
  await load();
  return () => unsub();
}

