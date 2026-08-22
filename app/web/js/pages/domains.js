import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { buildFilterBar } from "../components/filters.js";
import { showModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";
import { getState, onStateChange, setZone } from "../state.js";

export async function render(container, queryParams = new URLSearchParams()) {
  container.innerHTML = `
    <h1>Domains</h1>
    <div id="filter-bar"></div>
    <div id="table"></div>
  `;

  const initialSearch = queryParams.get("search") || "";
  let filters = { zone: getState().zone, search: initialSearch };

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: [
      {
        key: "domain",
        label: "Domain",
        sortable: true,
        className: "mono",
        render: (r) => {
          const link = document.createElement("span");
          link.className = "clickable-link mono";
          link.textContent = r.domain;
          link.title = `View details for ${r.domain}`;
          link.onclick = (e) => {
            e.stopPropagation();
            openDomainModal(r);
          };
          return link;
        },
      },
      {
        key: "hosted_zone",
        label: "Hosted zone",
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
      {
        key: "record_count",
        label: "Records",
        sortable: true,
        render: (r) => {
          const a = document.createElement("a");
          a.href = `#/records?search=${encodeURIComponent(r.domain)}`;
          a.className = "clickable-link";
          a.textContent = `${r.record_count || 0} record${r.record_count === 1 ? "" : "s"}`;
          a.title = `View all records under ${r.domain}`;
          a.onclick = (e) => e.stopPropagation();
          return a;
        },
      },
      {
        key: "dnssec_status",
        label: "DNSSEC",
        sortable: true,
        render: (r) => {
          const status = r.dnssec_status || "unknown";
          const span = document.createElement("span");
          span.className = `dnssec-badge dnssec-${status.toLowerCase()}`;
          span.textContent = status;
          return span;
        },
      },
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
    onRowClick: (row) => openDomainModal(row),
  });

  buildFilterBar(
    document.getElementById("filter-bar"),
    [{ key: "search", label: "Search", type: "search", placeholder: "domain…" }],
    (values) => {
      filters = { ...values, zone: getState().zone };
      table.refresh({ preservePage: false });
    },
    { search: initialSearch }
  );

  const unsub = onStateChange((s) => {
    filters = { ...filters, zone: s.zone };
    table.refresh({ preservePage: false });
  });

  await table.refresh();
  return () => unsub();
}

function openDomainModal(d) {
  const body = document.createElement("div");
  body.innerHTML = `
    <dl class="kv-grid">
      <dt>Domain</dt><dd class="mono"><strong>${escapeHtml(d.domain)}</strong></dd>
      <dt>Hosted Zone</dt><dd>${escapeHtml(d.hosted_zone || "—")}</dd>
      <dt>Total Records</dt><dd>${d.record_count || 0}</dd>
      <dt>DNSSEC Status</dt><dd><span class="dnssec-badge dnssec-${String(d.dnssec_status || "unknown").toLowerCase()}">${escapeHtml(d.dnssec_status || "unknown")}</span></dd>
      <dt>Source</dt><dd>${escapeHtml(d.source || "manual")}</dd>
      <dt>Last Scanned</dt><dd>${formatDate(d.last_scan_at)}</dd>
      <dt>Created</dt><dd>${formatDate(d.created_at)}</dd>
    </dl>
  `;

  const viewRecordsBtn = document.createElement("button");
  viewRecordsBtn.className = "primary";
  viewRecordsBtn.textContent = `View Records (${d.record_count || 0})`;

  const scanBtn = document.createElement("button");
  scanBtn.textContent = "Scan Zone Now";

  const { close } = showModal(`Domain: ${d.domain}`, body, {
    footerButtons: [scanBtn, viewRecordsBtn],
  });

  viewRecordsBtn.onclick = () => {
    close();
    window.location.hash = `#/records?search=${encodeURIComponent(d.domain)}`;
  };

  scanBtn.onclick = async () => {
    scanBtn.disabled = true;
    try {
      await apiPost(`/domains/${d.id}/scan`);
      showToast(`Scan initiated for ${d.domain}`, "success");
      close();
    } catch (e) {
      showToast(`Scan trigger failed: ${e.message}`, "error");
      scanBtn.disabled = false;
    }
  };
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

