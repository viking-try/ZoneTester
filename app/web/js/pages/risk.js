import { apiGet } from "../api.js";
import { showToast } from "../components/toast.js";
import { getState, onStateChange } from "../state.js";

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
          <thead><tr><th>Issue</th><th>Count</th></tr></thead>
          <tbody>${rows
            .map((r) => `<tr><td>${escapeHtml(r.issue)}</td><td>${r.count}</td></tr>`)
            .join("")}</tbody>
        </table></div>`;
    } else {
      el.innerHTML = `
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>Zone</th><th>Total</th><th>Cleanup</th><th>Down</th><th>Weak cipher</th><th>F/T grade</th></tr></thead>
          <tbody>${rows
            .map(
              (r) =>
                `<tr><td>${escapeHtml(r.hosted_zone)}</td><td>${r.total}</td><td>${r.cleanup_count}</td><td>${r.down_count}</td><td>${r.weak_cipher_count}</td><td>${r.f_or_t_count}</td></tr>`
            )
            .join("")}</tbody>
        </table></div>`;
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
