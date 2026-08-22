import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { buildFilterBar } from "../components/filters.js";
import { showModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { gradeBadge, statePill, boolPill, formatDate } from "../format.js";
import { getState, onStateChange, setZone } from "../state.js";

const COLUMNS = [
  { key: "name", label: "Name", sortable: true, className: "mono" },
  { key: "rtype", label: "Type", sortable: true },
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
  { key: "state", label: "State", sortable: true, render: (r) => statePill(r.state) },
  { key: "protocol", label: "Protocol", sortable: false },
  { key: "grade", label: "Grade", sortable: true, render: (r) => gradeBadge(r.grade) },
  { key: "pqc_supported", label: "PQC", sortable: false, render: (r) => boolPill("PQC", r.pqc_supported) },
  {
    key: "weak_cipher_present",
    label: "Weak cipher",
    sortable: false,
    render: (r) => (r.weak_cipher_present ? boolPill("weak", true) : ""),
  },
  { key: "cleanup", label: "Cleanup", sortable: false, render: (r) => (r.cleanup ? boolPill(r.cleanup_action, true) : "") },
  { key: "last_scanned", label: "Last scanned", sortable: true, render: (r) => formatDate(r.last_scanned) },
];

export async function render(container, queryParams = new URLSearchParams()) {
  container.innerHTML = `
    <h1>Records</h1>
    <div id="quick-presets" class="quick-filters"></div>
    <div id="filter-bar"></div>
    <div id="table"></div>
  `;

  const initialFilters = {
    search: queryParams.get("search") || "",
    grade: queryParams.get("grade") || "",
    state: queryParams.get("state") || "",
    protocol: queryParams.get("protocol") || "",
    pqc: queryParams.get("pqc") || "",
    weak_cipher: queryParams.get("weak_cipher") || "",
    hsts_missing: queryParams.get("hsts_missing") || "",
    cleanup: queryParams.get("cleanup") || "",
  };

  let filters = { ...initialFilters, zone: getState().zone };

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: COLUMNS,
    defaultSort: { by: "name", dir: "asc" },
    fetchPage: async (page) => apiGet("/records", { ...filters, ...page }),
    onRowClick: (row) => openRecordDetail(row.id, () => table.refresh({ quiet: true })),
  });

  // Render quick preset filter chips
  const presetsEl = document.getElementById("quick-presets");
  const PRESETS = [
    { label: "All Records", match: (f) => !f.grade && !f.state && !f.weak_cipher && !f.hsts_missing && !f.pqc && !f.cleanup, apply: {} },
    { label: "Critical (F/T)", match: (f) => f.grade === "F" || f.grade === "T", apply: { grade: "F" } },
    { label: "Down Hosts", match: (f) => f.state === "down", apply: { state: "down" } },
    { label: "Weak Ciphers", match: (f) => f.weak_cipher === "true", apply: { weak_cipher: "true" } },
    { label: "Missing HSTS", match: (f) => f.hsts_missing === "true", apply: { hsts_missing: "true" } },
    { label: "PQC Ready", match: (f) => f.pqc === "true", apply: { pqc: "true" } },
    { label: "Cleanup Candidates", match: (f) => f.cleanup === "true", apply: { cleanup: "true" } },
  ];

  function renderPresets() {
    presetsEl.innerHTML = "";
    for (const p of PRESETS) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `quick-chip ${p.match(filters) ? "active" : ""}`;
      chip.textContent = p.label;
      chip.onclick = () => {
        filters = {
          search: filters.search,
          grade: "",
          state: "",
          protocol: "",
          pqc: "",
          weak_cipher: "",
          hsts_missing: "",
          cleanup: "",
          ...p.apply,
          zone: getState().zone,
        };
        rebuildFilterBar();
        renderPresets();
        table.refresh({ preservePage: false });
      };
      presetsEl.appendChild(chip);
    }
  }

  function rebuildFilterBar() {
    buildFilterBar(
      document.getElementById("filter-bar"),
      [
        { key: "search", label: "Search", type: "search", placeholder: "name or value…" },
        {
          key: "grade",
          label: "Grade",
          type: "select",
          options: [
            { value: "", label: "Any grade" },
            ...["A+", "A", "B", "C", "F", "T"].map((g) => ({ value: g, label: g })),
          ],
        },
        {
          key: "state",
          label: "State",
          type: "select",
          options: [
            { value: "", label: "Any state" },
            ...["up", "down", "validation", "unscanned", "error"].map((s) => ({ value: s, label: s })),
          ],
        },
        {
          key: "protocol",
          label: "Protocol",
          type: "select",
          options: [
            { value: "", label: "Any protocol" },
            ...["TLSv1.3", "TLSv1.2", "TLSv1.1", "TLSv1", "SSLv3"].map((p) => ({ value: p, label: p })),
          ],
        },
        {
          key: "pqc",
          label: "PQC",
          type: "select",
          options: [
            { value: "", label: "Any" },
            { value: "true", label: "PQC-ready" },
            { value: "false", label: "Not PQC" },
            { value: "unknown", label: "Unknown" },
          ],
        },
        { key: "weak_cipher", label: "Weak cipher only", type: "checkbox" },
        { key: "hsts_missing", label: "Missing HSTS", type: "checkbox" },
        { key: "cleanup", label: "Cleanup only", type: "checkbox" },
      ],
      (values) => {
        filters = { ...values, zone: getState().zone };
        renderPresets();
        table.refresh({ preservePage: false });
      },
      filters
    );
  }

  rebuildFilterBar();
  renderPresets();

  const unsub = onStateChange((s) => {
    filters = { ...filters, zone: s.zone };
    table.refresh({ preservePage: false });
  });

  await table.refresh();
  return () => unsub();
}

export async function openRecordDetail(recordId, onChanged) {
  const body = document.createElement("div");
  body.textContent = "Loading…";
  const { close } = showModal("Record detail", body);

  try {
    const r = await apiGet(`/records/${recordId}`);
    body.innerHTML = "";

    const dl = document.createElement("dl");
    dl.className = "kv-grid";
    const rows = [
      ["Name", r.name, true],
      ["Type / Zone", `${r.rtype} · ${r.hosted_zone || "—"}`, false],
      ["Value", r.value, true],
      ["State", r.state, false],
      ["Down reason", r.down_reason || "—", false],
      ["Protocol", r.protocol || "—", false],
      ["Negotiated cipher", r.negotiated_cipher || "—", true],
      ["Forward secrecy", r.forward_secrecy === null ? "—" : String(r.forward_secrecy), false],
      ["PQC supported", r.pqc_supported === null ? "unknown" : String(r.pqc_supported), false],
      ["Weak cipher present", String(!!r.weak_cipher_present), false],
      ["TLS grade", r.tls_grade || "—", false],
      ["Header grade", r.header_grade ?? "—", false],
      ["Overall grade", r.grade || "—", false],
      ["Cert expires", formatDate(r.cert_expires_at), false],
      ["Server header", r.server_header || "—", false],
      ["X-Powered-By", r.x_powered_by || "—", false],
      ["Cleanup action", r.cleanup_action || "keep", false],
      ["Cleanup confidence", r.cleanup_confidence ?? 0, false],
      ["Last scanned", formatDate(r.last_scanned), false],
      ["First seen", formatDate(r.first_seen), false],
    ];

    for (const [label, value, copyable] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");

      if (copyable && value && value !== "—") {
        dd.innerHTML = `<span>${escapeHtml(value)}</span> `;
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.style.cssText = "padding:2px 6px;font-size:11px;margin-left:6px;";
        copyBtn.textContent = "Copy";
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(value);
          showToast(`Copied ${label}`, "success");
        };
        dd.appendChild(copyBtn);
      } else {
        dd.textContent = value;
      }
      dl.append(dt, dd);
    }
    body.appendChild(dl);

    if (r.cleanup_reasons?.length) {
      const h = document.createElement("h3");
      h.textContent = "Cleanup reasons";
      h.style.marginTop = "14px";
      const ul = document.createElement("ul");
      ul.className = "reasons-list";
      for (const reason of r.cleanup_reasons) {
        const li = document.createElement("li");
        li.textContent = reason;
        ul.appendChild(li);
      }
      body.append(h, ul);
    }

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:8px;margin-top:16px;";

    const rescanBtn = document.createElement("button");
    rescanBtn.className = "primary";
    rescanBtn.textContent = "Rescan now";
    rescanBtn.onclick = async () => {
      rescanBtn.disabled = true;
      try {
        await apiPost(`/records/${recordId}/rescan`);
        showToast("Rescan queued", "success");
        onChanged?.();
      } catch (e) {
        showToast(`Rescan failed: ${e.message}`, "error");
      } finally {
        rescanBtn.disabled = false;
      }
    };
    actions.appendChild(rescanBtn);

    if (r.cleanup && !r.cleanup_ack) {
      const ackBtn = document.createElement("button");
      ackBtn.textContent = "Acknowledge & keep";
      ackBtn.onclick = async () => {
        ackBtn.disabled = true;
        try {
          await apiPost(`/records/${recordId}/cleanup-ack`);
          showToast("Acknowledged", "success");
          onChanged?.();
          close();
        } catch (e) {
          showToast(`Failed: ${e.message}`, "error");
        }
      };
      actions.appendChild(ackBtn);
    }
    body.appendChild(actions);
  } catch (e) {
    body.textContent = `Failed to load record: ${e.message}`;
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

