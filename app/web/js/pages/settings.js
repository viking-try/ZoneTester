import { apiGet } from "../api.js";
import { showToast } from "../components/toast.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Settings</h1>
    <div class="card" style="max-width:640px;">
      <h2>Integration status</h2>
      <p class="muted" style="margin-top:0;">
        All integrations are configured via environment variables (or AWS Secrets Manager) —
        secrets are never entered or stored here.
      </p>
      <dl class="kv-grid" id="status-grid"></dl>
    </div>
  `;

  try {
    const s = await apiGet("/settings/integrations");
    const grid = document.getElementById("status-grid");
    const rows = [
      ["SMTP (reports)", s.smtp.enabled ? `enabled — ${s.smtp.host}` : "disabled"],
      ["Jira ticketing", s.jira.enabled ? `enabled — ${s.jira.base_url}` : "disabled"],
      ["ServiceNow ticketing", s.servicenow.enabled ? `enabled — ${s.servicenow.base_url}` : "disabled"],
      ["OIDC / SSO", s.oidc.enabled ? `enabled — ${s.oidc.issuer}` : "disabled (local auth active)"],
      ["Secrets backend", s.secrets_backend],
      ["DNSSEC DoH resolver", s.doh_url],
      ["RFC1918 scan targets", s.allow_rfc1918_scan_targets ? "allowed" : "blocked"],
      ["Insecure TLS fallback", s.allow_insecure_tls_fallback ? "ENABLED (opt-in)" : "disabled (default)"],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      grid.append(dt, dd);
    }
  } catch (e) {
    showToast(`Failed to load settings: ${e.message}`, "error");
  }
}
