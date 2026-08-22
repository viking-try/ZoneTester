import { apiGet } from "../api.js";
import { getState, onStateChange } from "../state.js";
import { showToast } from "../components/toast.js";
import { donutChart, chartLegend, trendCard } from "../components/charts.js";

const GRADE_ORDER = ["A+", "A", "B", "C", "F", "T"];
const GRADE_COLOR_VAR = { "A+": "--success", A: "--success", B: "--accent", C: "--warning", F: "--danger", T: "--info" };

export async function render(container) {
  container.innerHTML = `
    <h1>Executive Dashboard</h1>
    <div class="kpi-row" id="kpi-row"></div>

    <div class="card" style="margin-bottom:16px;">
      <h2>Grade distribution <span class="faint" style="font-weight:normal;font-size:12px;">(click to drill down)</span></h2>
      <div class="chart-row">
        <div id="grade-donut"></div>
        <div id="grade-legend"></div>
        <div style="flex:1;min-width:260px;">
          <div id="grade-bars"></div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h2>Trend (up-host count, last 90 days)</h2>
      <div id="trend-chart"></div>
    </div>

    <h2 style="margin-bottom:10px;">Posture trends</h2>
    <div class="trend-row" id="trend-cards"></div>
  `;

  async function load() {
    const zone = getState().zone;
    try {
      const [dash, trends] = await Promise.all([
        apiGet("/dashboard", { zone }),
        apiGet("/dashboard/trends", { zone, days: 90 }),
      ]);
      renderKpis(dash.kpis);
      renderGradeCharts(dash.grade_distribution);
      renderTrend(trends.rows);
      renderTrendCards(trends.rows);
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

  function renderGradeCharts(dist) {
    const data = GRADE_ORDER.map((g) => ({ label: g, value: dist[g] || 0, colorVar: GRADE_COLOR_VAR[g], grade: g }));
    const total = data.reduce((s, d) => s + d.value, 0);

    const donutEl = document.getElementById("grade-donut");
    donutEl.innerHTML = "";
    donutEl.appendChild(donutChart({ data, centerLabel: String(total), centerSub: "graded" }));

    const legendEl = document.getElementById("grade-legend");
    legendEl.innerHTML = "";
    legendEl.appendChild(
      chartLegend(data, {
        onClick: (d) => {
          window.location.hash = `#/records?grade=${encodeURIComponent(d.grade)}`;
        },
      })
    );

    renderGradeBars(dist);
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

    if (rows.length === 0) {
      el.innerHTML = `
        <div class="sparse-data-note">
          <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          <span>No snapshot history yet. The <strong>beat</strong> scheduler captures one daily — check back tomorrow, or trigger <code>daily_snapshot_task</code> manually to seed today's.</span>
        </div>`;
      return;
    }

    if (rows.length < 3) {
      const latest = rows[rows.length - 1];
      el.innerHTML = `
        <div class="sparse-data-note" style="margin-bottom:12px;">
          <svg viewBox="0 0 24 24"><path d="M11 7h2v6h-2zm0 8h2v2h-2zm1-13C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/></svg>
          <span>Only ${rows.length} snapshot day${rows.length === 1 ? "" : "s"} so far — the trend line fills in as daily snapshots accumulate. Latest: <strong>${latest.up_count ?? 0}</strong> up of ${latest.total_records ?? 0} total on ${latest.snapshot_date}.</span>
        </div>`;
    }

    const width = 720;
    const height = 160;
    const pad = 24;
    const maxTotal = Math.max(1, ...rows.map((r) => r.total_records || 0));
    const points = rows.map((r, i) => {
      const x = rows.length === 1 ? width / 2 : pad + (i / Math.max(1, rows.length - 1)) * (width - pad * 2);
      const y = height - pad - ((r.up_count || 0) / maxTotal) * (height - pad * 2);
      return [x, y];
    });

    const svgNs = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

    if (points.length > 1) {
      const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
      const pathEl = document.createElementNS(svgNs, "path");
      pathEl.setAttribute("d", path);
      pathEl.setAttribute("fill", "none");
      pathEl.setAttribute("stroke-width", "2");
      pathEl.style.stroke = "var(--accent)";
      svg.appendChild(pathEl);
    }

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

  function renderTrendCards(rows) {
    const el = document.getElementById("trend-cards");
    el.innerHTML = "";
    const metrics = [
      { key: "pqc_count", label: "PQC-ready", colorVar: "--success" },
      { key: "weak_cipher_count", label: "Weak cipher", colorVar: "--danger" },
      { key: "dangling_count", label: "Dangling / cleanup", colorVar: "--warning" },
      { key: "down_count", label: "Down hosts", colorVar: "--info" },
    ];
    for (const m of metrics) {
      const points = rows.map((r) => r[m.key] ?? 0);
      const latest = points.length ? points[points.length - 1] : 0;
      el.appendChild(trendCard({ label: m.label, value: latest, points, colorVar: m.colorVar }));
    }
  }

  const unsub = onStateChange(load);
  await load();
  return () => unsub();
}
