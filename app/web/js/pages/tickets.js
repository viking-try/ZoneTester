import { apiGet, apiPost } from "../api.js";
import { showToast } from "../components/toast.js";
import { getState } from "../state.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Tickets</h1>
    <div class="card" style="max-width:480px;margin-bottom:16px;">
      <h2>Integration status</h2>
      <div id="status" class="muted">Loading…</div>
    </div>
    <div class="card" style="max-width:480px;">
      <h2>Create tickets for new dangling records</h2>
      <form id="ticket-form" style="display:flex;flex-direction:column;gap:8px;">
        <label>Window
          <select id="tf-window">
            <option value="day">Last day</option>
            <option value="week" selected>Last week</option>
            <option value="month">Last month</option>
          </select>
        </label>
        <label>Provider
          <select id="tf-provider">
            <option value="jira">Jira</option>
            <option value="servicenow">ServiceNow</option>
          </select>
        </label>
        <label>Mode
          <select id="tf-mode">
            <option value="summary">One summary ticket</option>
            <option value="per_resource">One ticket per resource</option>
          </select>
        </label>
        <input type="text" id="tf-assignee" placeholder="Assignee (optional)">
        <button type="submit" class="primary">Create tickets</button>
      </form>
    </div>
  `;

  try {
    const s = await apiGet("/settings/integrations");
    document.getElementById("status").innerHTML = `
      Jira: ${s.jira.enabled ? "enabled" : "disabled"}<br>
      ServiceNow: ${s.servicenow.enabled ? "enabled" : "disabled"}
    `;
  } catch {
    document.getElementById("status").textContent = "Could not load status.";
  }

  document.getElementById("ticket-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      window: document.getElementById("tf-window").value,
      provider: document.getElementById("tf-provider").value,
      mode: document.getElementById("tf-mode").value,
      assignee: document.getElementById("tf-assignee").value || null,
      zone: getState().zone || null,
    };
    try {
      await apiPost("/tickets", payload);
      showToast("Ticket creation queued", "success");
    } catch (err) {
      showToast(`Failed: ${err.message}`, "error");
    }
  });
}
