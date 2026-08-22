import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { buildFilterBar } from "../components/filters.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";
import { getState, onStateChange, setZone } from "../state.js";
import { openRecordDetail } from "./records.js";

export async function render(container, queryParams = new URLSearchParams()) {
  container.innerHTML = `
    <h1>Cleanup Candidates</h1>
    <div class="filter-bar" style="justify-content:space-between;">
      <div id="filter-bar" class="filter-bar"></div>
      <button id="reconcile-btn">Re-run reconciliation</button>
    </div>
    <div id="table"></div>
  `;

  const initialAction = queryParams.get("action") || "";
  let filters = { zone: getState().zone, action: initialAction };

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: [
      {
        key: "name",
        label: "Name",
        sortable: true,
        className: "mono",
        render: (r) => {
          const span = document.createElement("span");
          span.className = "clickable-link mono";
          span.textContent = r.name;
          span.onclick = (e) => {
            e.stopPropagation();
            openRecordDetail(r.id, () => table.refresh({ quiet: true }));
          };
          return span;
        },
      },
      { key: "rtype", label: "Type", sortable: false },
      {
        key: "hosted_zone",
        label: "Zone",
        sortable: true,
        render: (r) => {
          const span = document.createElement("span");
          span.className = "pill clickable";
          span.textContent = r.hosted_zone || "—";
          span.title = `Filter by zone ${r.hosted_zone}`;
          span.onclick = (e) => {
            e.stopPropagation();
            if (r.hosted_zone) {
              setZone(r.hosted_zone);
              showToast(`Filtered to zone ${r.hosted_zone}`, "success");
            }
          };
          return span;
        },
      },
      { key: "cleanup_action", label: "Action", sortable: true },
      { key: "cleanup_confidence", label: "Confidence", sortable: true },
      {
        key: "cleanup_reasons",
        label: "Reasons",
        className: "wrap",
        render: (r) => (r.cleanup_reasons || []).join("; "),
      },
      { key: "cleanup_ack", label: "Ack'd", sortable: false, render: (r) => (r.cleanup_ack ? "yes" : "") },
      { key: "last_scanned", label: "Last scanned", sortable: true, render: (r) => formatDate(r.last_scanned) },
      {
        key: "actions",
        label: "",
        render: (r) => {
          if (r.cleanup_ack) return "";
          const btn = document.createElement("button");
          btn.textContent = "Acknowledge & keep";
          btn.onclick = async (e) => {
            e.stopPropagation();
            btn.disabled = true;
            try {
              await apiPost(`/records/${r.id}/cleanup-ack`);
              showToast("Acknowledged", "success");
              table.refresh({ quiet: true });
            } catch (err) {
              showToast(`Failed: ${err.message}`, "error");
              btn.disabled = false;
            }
          };
          return btn;
        },
      },
    ],
    defaultSort: { by: "cleanup_confidence", dir: "desc" },
    fetchPage: async (page) => apiGet("/cleanup", { ...filters, ...page }),
    onRowClick: (row) => openRecordDetail(row.id, () => table.refresh({ quiet: true })),
  });

  buildFilterBar(
    document.getElementById("filter-bar"),
    [
      {
        key: "action",
        label: "Action",
        type: "select",
        options: [
          { value: "", label: "Any action" },
          { value: "delete", label: "Delete" },
          { value: "investigate", label: "Investigate" },
        ],
      },
      { key: "ack", label: "Unacknowledged only", type: "checkbox" },
    ],
    (values) => {
      filters = { ...values, ack: values.ack ? "false" : "", zone: getState().zone };
      table.refresh({ preservePage: false });
    },
    { action: initialAction }
  );

  document.getElementById("reconcile-btn").addEventListener("click", async () => {
    try {
      const r = await apiPost("/cleanup/reconcile");
      showToast(`Reconciled ${r.updated} records`, "success");
      table.refresh({ quiet: true });
    } catch (e) {
      showToast(`Failed: ${e.message}`, "error");
    }
  });

  const unsub = onStateChange((s) => {
    filters = { ...filters, zone: s.zone };
    table.refresh({ preservePage: false });
  });

  await table.refresh();
  return () => unsub();
}

