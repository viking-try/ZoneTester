import { apiGet, apiPost, apiPut } from "../api.js";
import { showModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";
import { getState } from "../state.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Reports</h1>
    <div class="filter-bar" style="justify-content:space-between;">
      <div class="filter-group">
        <button id="preview-btn">Preview digest</button>
        <a id="download-html" href="#" target="_blank"><button type="button">Download HTML</button></a>
        <a id="download-csv" href="#" target="_blank"><button type="button">Download CSV</button></a>
      </div>
      <button id="new-schedule-btn" class="primary">New schedule</button>
    </div>
    <div id="schedules-wrap"></div>
  `;

  function updateDownloadLinks() {
    const zone = getState().zone;
    const qs = zone ? `?zone=${encodeURIComponent(zone)}` : "";
    document.getElementById("download-html").href = `/api/reports/download${qs}`;
    document.getElementById("download-csv").href = `/api/reports/download${qs}${qs ? "&" : "?"}format=csv`;
  }
  updateDownloadLinks();

  document.getElementById("preview-btn").addEventListener("click", async () => {
    try {
      const zone = getState().zone;
      const result = await apiGet("/reports/preview", { zone, template: "full" });
      const frame = document.createElement("iframe");
      frame.style.cssText = "width:100%;height:60vh;border:1px solid var(--border);border-radius:6px;";
      frame.srcdoc = result.html;
      const wrap = document.createElement("div");
      const caption = document.createElement("p");
      caption.className = "muted";
      caption.textContent = `${result.event_count} unreported change(s)`;
      wrap.append(caption, frame);
      showModal("Digest preview", wrap);
    } catch (e) {
      showToast(`Preview failed: ${e.message}`, "error");
    }
  });

  async function loadSchedules() {
    const wrap = document.getElementById("schedules-wrap");
    try {
      const { schedules } = await apiGet("/schedules");
      if (!schedules.length) {
        wrap.innerHTML = `<div class="empty-state">No schedules yet — create one to send recurring digest emails.</div>`;
        return;
      }
      wrap.innerHTML = `
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>Name</th><th>Zone</th><th>Template</th><th>Cadence</th><th>Recipients</th><th>Enabled</th><th>Last sent</th><th></th></tr></thead>
          <tbody></tbody>
        </table></div>`;
      const tbody = wrap.querySelector("tbody");
      for (const s of schedules) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${escapeHtml(s.name)}</td>
          <td>${escapeHtml(s.zone || "All zones")}</td>
          <td>${escapeHtml(s.template)}</td>
          <td>${escapeHtml(s.cadence)}${s.cadence === "interval" ? ` (${s.interval_minutes}m)` : ""}</td>
          <td>${escapeHtml((s.recipients || []).join(", "))}</td>
          <td>${s.enabled ? "yes" : "no"}</td>
          <td>${formatDate(s.last_sent_at)}</td>
        `;
        const actionsTd = document.createElement("td");
        const sendBtn = document.createElement("button");
        sendBtn.textContent = "Send now";
        sendBtn.onclick = async () => {
          sendBtn.disabled = true;
          try {
            await apiPost(`/schedules/${s.id}/send-now`);
            showToast("Report queued", "success");
          } catch (e) {
            showToast(`Failed: ${e.message}`, "error");
          } finally {
            sendBtn.disabled = false;
          }
        };
        const toggleBtn = document.createElement("button");
        toggleBtn.textContent = s.enabled ? "Disable" : "Enable";
        toggleBtn.style.marginLeft = "6px";
        toggleBtn.onclick = async () => {
          try {
            await apiPut(`/schedules/${s.id}`, { ...s, enabled: !s.enabled });
            loadSchedules();
          } catch (e) {
            showToast(`Failed: ${e.message}`, "error");
          }
        };
        actionsTd.append(sendBtn, toggleBtn);
        tr.appendChild(actionsTd);
        tbody.appendChild(tr);
      }
    } catch (e) {
      wrap.innerHTML = `<div class="empty-state">Failed to load schedules: ${escapeHtml(e.message)}</div>`;
    }
  }

  document.getElementById("new-schedule-btn").addEventListener("click", () => openScheduleForm(loadSchedules));

  await loadSchedules();
}

function openScheduleForm(onSaved) {
  const body = document.createElement("div");
  body.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:8px;min-width:320px;">
      <input type="text" id="sf-name" placeholder="Schedule name" required>
      <input type="text" id="sf-zone" placeholder="Zone (blank = all zones)">
      <select id="sf-template"></select>
      <select id="sf-cadence">
        <option value="daily">Daily</option>
        <option value="weekly">Weekly</option>
        <option value="interval">Interval (minutes)</option>
      </select>
      <input type="number" id="sf-interval" placeholder="Interval minutes" style="display:none;">
      <input type="text" id="sf-recipients" placeholder="Recipients, comma-separated" required>
    </div>
  `;
  apiGet("/reports/templates").then(({ templates }) => {
    const sel = body.querySelector("#sf-template");
    for (const t of templates) {
      const o = document.createElement("option");
      o.value = t.key;
      o.textContent = t.label;
      sel.appendChild(o);
    }
  });
  const cadenceSel = body.querySelector("#sf-cadence");
  cadenceSel.addEventListener("change", () => {
    body.querySelector("#sf-interval").style.display = cadenceSel.value === "interval" ? "block" : "none";
  });

  const saveBtn = document.createElement("button");
  saveBtn.className = "primary";
  saveBtn.textContent = "Create";
  const { close } = showModal("New report schedule", body, { footerButtons: [saveBtn] });

  saveBtn.addEventListener("click", async () => {
    const payload = {
      name: body.querySelector("#sf-name").value,
      zone: body.querySelector("#sf-zone").value || null,
      template: body.querySelector("#sf-template").value,
      cadence: cadenceSel.value,
      interval_minutes: cadenceSel.value === "interval" ? Number(body.querySelector("#sf-interval").value) : null,
      recipients: body
        .querySelector("#sf-recipients")
        .value.split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (!payload.name || !payload.recipients.length) {
      showToast("Name and at least one recipient are required", "error");
      return;
    }
    try {
      await apiPost("/schedules", payload);
      showToast("Schedule created", "success");
      close();
      onSaved?.();
    } catch (e) {
      showToast(`Failed: ${e.message}`, "error");
    }
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}
