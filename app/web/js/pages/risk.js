import { apiGet } from "../api.js";
import { showToast } from "../components/toast.js";
import { getState, onStateChange, setZone } from "../state.js";

const ISSUE_META = {
  dangling: { label: "Dangling DNS assets / cleanup candidates", route: "#/cleanup" },
  down: { label: "Down / unreachable scan targets", route: "#/records?state=down" },
  weak_cipher: { label: "Weak or deprecated cipher suites", route: "#/records?weak_cipher=true" },
  expired_or_bad_cert: { label: "Expired or invalid certificates", route: "#/records?grade=F" },
  no_pqc: { label: "No Post-Quantum (PQC) support", route: "#/records?pqc=false" },
  missing_hsts: { label: "Missing Strict-Transport-Security (HSTS)", route: "#/records?hsts_missing=true" },
  legacy_tls: { label: "Legacy protocols (TLS 1.0, 1.1, SSLv3)", route: "#/records?protocol=TLSv1" },
};

export async function render(container) {
  container.innerHTML = `
    <h1>Risk View</h1>
    <div class="filter-bar">
      <div class="filter-group">
        <label>Group by</label>
        <select id="group-by">
          <option value="issue">Issue</option>
          <option value="asset">Asset (zone)</option>
        </select>
      </div>
    </div>
    <div id="risk-table"></div>
  `;

  async function load() {
    const groupBy = document.getElementById("group-by").value;
    const zone = getState().zone;
    try {
      const { rows } = await apiGet("/risk", { group_by: groupBy, zone });
      renderTable(groupBy, rows);
    } catch (e) {
      showToast(`Failed to load risk view: ${e.message}`, "error");
    }
  }

  function renderTable(groupBy, rows) {
    const el = document.getElementById("risk-table");
    if (groupBy === "issue") {
      el.innerHTML = `
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>Issue</th><th style="width:120px;text-align:right;">Count</th><th style="width:100px;">Action</th></tr></thead>
          <tbody></tbody>
        </table></div>`;
      const tbody = el.querySelector("tbody");
      for (const r of rows) {
        const meta = ISSUE_META[r.issue] || { label: r.issue, route: "#/records" };
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.title = `Drill down into ${meta.label}`;
        tr.innerHTML = `
          <td><strong>${escapeHtml(meta.label)}</strong> <span class="mono faint">(${escapeHtml(r.issue)})</span></td>
          <td style="text-align:right;font-weight:700;">${r.count}</td>
          <td><span class="clickable-link">View records →</span></td>
        `;
        tr.onclick = () => {
          window.location.hash = meta.route;
        };
        tbody.appendChild(tr);
      }
    } else {
      el.innerHTML = `
        <div class="table-wrap"><table class="data-table">
          <thead><tr>
            <th>Zone</th>
            <th style="text-align:right;">Total</th>
            <th style="text-align:right;">Cleanup</th>
            <th style="text-align:right;">Down</th>
            <th style="text-align:right;">Weak cipher</th>
            <th style="text-align:right;">F / T grade</th>
          </tr></thead>
          <tbody></tbody>
        </table></div>`;
      const tbody = el.querySelector("tbody");
      for (const r of rows) {
        const z = r.hosted_zone || "";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="clickable-link"><strong>${escapeHtml(z || "All")}</strong></span></td>
          <td style="text-align:right;"><a class="clickable-link" href="#/records?search=${encodeURIComponent(z)}">${r.total}</a></td>
          <td style="text-align:right;"><a class="clickable-link" href="#/cleanup?action=">${r.cleanup_count > 0 ? `<strong>${r.cleanup_count}</strong>` : "0"}</a></td>
          <td style="text-align:right;"><a class="clickable-link" href="#/records?state=down">${r.down_count > 0 ? `<span class="state-down"><strong>${r.down_count}</strong></span>` : "0"}</a></td>
          <td style="text-align:right;"><a class="clickable-link" href="#/records?weak_cipher=true">${r.weak_cipher_count > 0 ? `<span class="pill off">${r.weak_cipher_count}</span>` : "0"}</a></td>
          <td style="text-align:right;"><a class="clickable-link" href="#/records?grade=F">${r.f_or_t_count > 0 ? `<span class="badge grade-F">${r.f_or_t_count}</span>` : "0"}</a></td>
        `;
        tr.querySelector("td span.clickable-link").onclick = () => {
          if (z) {
            setZone(z);
            showToast(`Filtered to zone ${z}`, "success");
            window.location.hash = "#/records";
          }
        };
        tbody.appendChild(tr);
      }
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s ?? "";
    return div.innerHTML;
  }

  document.getElementById("group-by").addEventListener("change", load);
  const unsub = onStateChange(load);
  await load();
  return () => unsub();
}

