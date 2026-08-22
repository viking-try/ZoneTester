import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { buildFilterBar } from "../components/filters.js";
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
      { key: "id", label: "Job", sortable: false },
      { key: "type", label: "Type", sortable: true },
      { key: "state", label: "State", sortable: true },
      { key: "zone", label: "Zone", sortable: false },
      { key: "error", label: "Error", sortable: false, className: "wrap" },
      { key: "created_at", label: "Created", sortable: true, render: (r) => formatDate(r.created_at) },
      { key: "finished_at", label: "Finished", sortable: true, render: (r) => formatDate(r.finished_at) },
    ],
    defaultSort: { by: "created_at", dir: "desc" },
    fetchPage: async (page) => apiGet("/jobs", { ...filters, ...page }),
  });

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
    }
  );

  async function loadKpis() {
    try {
      const { by_state } = await apiGet("/jobs/summary");
      const row = document.getElementById("kpi-row");
      row.innerHTML = "";
      for (const state of ["queued", "running", "done", "error"]) {
        const tile = document.createElement("div");
        tile.className = "kpi-tile";
        const v = document.createElement("div");
        v.className = "value";
        v.textContent = by_state[state] || 0;
        const l = document.createElement("div");
        l.className = "label";
        l.textContent = state;
        tile.append(v, l);
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
