import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { buildFilterBar } from "../components/filters.js";
import { showModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";
import { getState } from "../state.js";

const POLL_MS = 5000;

export async function render(container) {
  container.innerHTML = `
    <h1>Scan Queue</h1>
    <div class="kpi-row" id="kpi-row"></div>
    <div class="filter-bar" style="justify-content:space-between;">
      <div id="filter-bar" class="filter-bar"></div>
      <div style="display:flex;gap:8px;align-items:center;">
        <select id="scan-scope">
          <option value="all">All scannable</option>
          <option value="down_only">Down only</option>
          <option value="unscanned_only">Unscanned only</option>
          <option value="tls12_only">TLS 1.2 only</option>
        </select>
        <button id="scan-all-btn" class="primary">Trigger scan</button>
      </div>
    </div>
    <div id="table"></div>
  `;

  let filters = {};

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: [
      { key: "id", label: "Job", sortable: false, className: "mono" },
      { key: "type", label: "Type", sortable: true },
      {
        key: "state",
        label: "State",
        sortable: true,
        render: (r) => {
          const span = document.createElement("span");
          span.className = `pill ${r.state === "done" ? "on" : r.state === "error" ? "off" : "warn"}`;
          span.textContent = r.state;
          return span;
        },
      },
      { key: "zone", label: "Zone", sortable: false },
      { key: "error", label: "Error", sortable: false, className: "wrap faint" },
      { key: "created_at", label: "Created", sortable: true, render: (r) => formatDate(r.created_at) },
      { key: "finished_at", label: "Finished", sortable: true, render: (r) => formatDate(r.finished_at) },
    ],
    defaultSort: { by: "created_at", dir: "desc" },
    fetchPage: async (page) => apiGet("/jobs", { ...filters, ...page }),
    onRowClick: (row) => openJobDetail(row),
  });

  function setupFilterBar() {
    buildFilterBar(
      document.getElementById("filter-bar"),
      [
        {
          key: "state",
          label: "State",
          type: "select",
          options: [
            { value: "", label: "Any state" },
            ...["queued", "running", "done", "error"].map((s) => ({ value: s, label: s })),
          ],
        },
        {
          key: "type",
          label: "Type",
          type: "select",
          options: [
            { value: "", label: "Any type" },
            ...["scan_record", "scan_batch", "scan_domain", "send_report", "create_tickets"].map((t) => ({
              value: t,
              label: t,
            })),
          ],
        },
      ],
      (values) => {
        filters = values;
        table.refresh({ preservePage: false });
      },
      filters
    );
  }
  setupFilterBar();

  async function loadKpis() {
    try {
      const { by_state } = await apiGet("/jobs/summary");
      const row = document.getElementById("kpi-row");
      row.innerHTML = "";
      for (const state of ["queued", "running", "done", "error"]) {
        const tile = document.createElement("div");
        tile.className = "kpi-tile clickable";
        tile.title = `Filter by ${state} jobs`;
        tile.onclick = () => {
          filters.state = filters.state === state ? "" : state;
          setupFilterBar();
          table.refresh({ preservePage: false });
        };

        const hint = document.createElement("span");
        hint.className = "kpi-drilldown-hint";
        hint.textContent = "Filter →";

        const v = document.createElement("div");
        v.className = "value";
        v.textContent = by_state[state] || 0;

        const l = document.createElement("div");
        l.className = "label";
        l.textContent = state;

        tile.append(hint, v, l);
        row.appendChild(tile);
      }
    } catch {
      /* best-effort KPI poll */
    }
  }

  document.getElementById("scan-all-btn").addEventListener("click", async () => {
    const scope = document.getElementById("scan-scope").value;
    try {
      await apiPost(`/scan?scope=${encodeURIComponent(scope)}&zone=${encodeURIComponent(getState().zone || "")}`);
      showToast("Scan triggered", "success");
      table.refresh({ preservePage: false });
      loadKpis();
    } catch (e) {
      showToast(`Failed to trigger scan: ${e.message}`, "error");
    }
  });

  await table.refresh();
  await loadKpis();

  const interval = setInterval(() => {
    loadKpis();
    table.refresh({ quiet: true });
  }, POLL_MS);

  return () => clearInterval(interval);
}

function openJobDetail(job) {
  const body = document.createElement("div");
  body.innerHTML = `
    <dl class="kv-grid">
      <dt>Job ID</dt><dd class="mono">${escapeHtml(job.id)}</dd>
      <dt>Type</dt><dd>${escapeHtml(job.type)}</dd>
      <dt>State</dt><dd><span class="pill ${job.state === "done" ? "on" : job.state === "error" ? "off" : "warn"}">${escapeHtml(job.state)}</span></dd>
      <dt>Zone</dt><dd>${escapeHtml(job.zone || "—")}</dd>
      <dt>Created</dt><dd>${formatDate(job.created_at)}</dd>
      <dt>Finished</dt><dd>${formatDate(job.finished_at)}</dd>
    </dl>
    ${job.payload ? `
      <h3 style="margin-top:14px;">Payload</h3>
      <pre style="background:var(--bg-inset);padding:10px;border-radius:6px;overflow-x:auto;font-size:12px;">${escapeHtml(JSON.stringify(job.payload, null, 2))}</pre>
    ` : ""}
    ${job.error ? `
      <h3 style="margin-top:14px;color:var(--danger);">Error</h3>
      <pre style="background:var(--danger-bg);color:var(--danger);padding:10px;border-radius:6px;overflow-x:auto;font-size:12px;">${escapeHtml(job.error)}</pre>
    ` : ""}
  `;
  showModal(`Job: ${job.type} (${job.id})`, body);
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

