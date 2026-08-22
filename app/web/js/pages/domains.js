import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { buildFilterBar } from "../components/filters.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";
import { getState, onStateChange } from "../state.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Domains</h1>
    <div id="filter-bar"></div>
    <div id="table"></div>
  `;

  let filters = { zone: getState().zone };

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: [
      { key: "domain", label: "Domain", sortable: true, className: "mono" },
      { key: "hosted_zone", label: "Hosted zone", sortable: true },
      { key: "record_count", label: "Records", sortable: true },
      { key: "dnssec_status", label: "DNSSEC", sortable: true, render: (r) => r.dnssec_status || "unknown" },
      { key: "last_scan_at", label: "Last scan", sortable: true, render: (r) => formatDate(r.last_scan_at) },
      {
        key: "actions",
        label: "",
        render: (r) => {
          const btn = document.createElement("button");
          btn.textContent = "Scan zone";
          btn.onclick = async (e) => {
            e.stopPropagation();
            btn.disabled = true;
            try {
              await apiPost(`/domains/${r.id}/scan`);
              showToast(`Queued scan for ${r.domain}`, "success");
            } catch (err) {
              showToast(`Failed: ${err.message}`, "error");
            } finally {
              btn.disabled = false;
            }
          };
          return btn;
        },
      },
    ],
    defaultSort: { by: "domain", dir: "asc" },
    fetchPage: async (page) => apiGet("/domains", { ...filters, ...page }),
  });

  buildFilterBar(
    document.getElementById("filter-bar"),
    [{ key: "search", label: "Search", type: "search", placeholder: "domain…" }],
    (values) => {
      filters = { ...values, zone: getState().zone };
      table.refresh({ preservePage: false });
    }
  );

  const unsub = onStateChange((s) => {
    filters = { ...filters, zone: s.zone };
    table.refresh({ preservePage: false });
  });

  await table.refresh();
  return () => unsub();
}
