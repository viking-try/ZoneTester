import { apiGet } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { formatDate } from "../format.js";

export async function render(container) {
  container.innerHTML = `<h1>Audit Log</h1><div id="table"></div>`;

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: [
      { key: "created_at", label: "When", sortable: true, render: (r) => formatDate(r.created_at) },
      { key: "actor", label: "Actor", sortable: true },
      { key: "method", label: "Method", sortable: true },
      { key: "path", label: "Path", sortable: false, className: "mono" },
      { key: "status_code", label: "Status", sortable: true },
      { key: "duration_ms", label: "Duration (ms)", sortable: false },
      { key: "ip", label: "IP", sortable: false },
    ],
    defaultSort: { by: "created_at", dir: "desc" },
    fetchPage: async (page) => apiGet("/audit", page),
  });

  await table.refresh();
}
