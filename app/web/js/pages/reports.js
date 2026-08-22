import { apiGet, apiPost, apiPut, apiDelete } from "../api.js";
import { showModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";
import { getState, onStateChange } from "../state.js";

/* Keyed by the REAL template keys the backend returns from GET /api/reports/templates
   (app/reporting/render.py:EVENT_TYPE_LABELS plus "full") — a mismatch here would let an
   operator pick a template in the UI that silently doesn't correspond to anything real. Any
   key the backend adds later without a curated entry here still renders, just with a plainer
   auto-generated description (see renderTemplatesTab). */
const TEMPLATE_DESCRIPTIONS = {
  full: {
    description: "Complete roll-up of all infrastructure changes, state transitions, certificate renewals/expirations, grade regressions, and new dangling assets across all monitored zones.",
    audience: "CISO, Head of Infrastructure, SecOps Leadership",
    cadence: "Weekly or Daily",
  },
  new_dangling: {
    description: "Targeted alert for DNS records pointing to deprovisioned or unclaimed third-party cloud infrastructure (S3, CloudFront, Azure, GitHub Pages, Heroku). High subdomain takeover risk.",
    audience: "Cloud Security, DevOps, Site Reliability Engineers",
    cadence: "Daily or Immediately",
  },
  newly_down: {
    description: "Endpoints that were reachable and are no longer — a first signal for outages or infrastructure that quietly disappeared.",
    audience: "Site Reliability Engineers, Infrastructure On-Call",
    cadence: "Daily",
  },
  new_weak_cipher: {
    description: "Highlights endpoints newly negotiating deprecated ciphers (RC4, 3DES, EXPORT, NULL) or legacy TLS versions (1.0, 1.1, SSLv3).",
    audience: "Compliance Officers, Security Architects",
    cadence: "Weekly / Monthly",
  },
  newly_not_pqc: {
    description: "Endpoints that lost hybrid post-quantum (ML-KEM / X25519MLKEM768) key-exchange support since the last scan — a regression signal for PQC migration tracking.",
    audience: "Enterprise Architecture, Cryptographic Modernization Team",
    cadence: "Monthly / Quarterly",
  },
  grade_regression: {
    description: "Identifies endpoints where TLS or HTTP security header posture has degraded since the last scan (e.g. from A to F).",
    audience: "Security Operations, Application Owners",
    cadence: "Daily / Incident-based",
  },
  cert_expiring_30d: {
    description: "Certificates entering their final 30 days before expiry — the window where renewal needs to be actioned.",
    audience: "Infrastructure Engineers, Web Operations",
    cadence: "Weekly / Daily",
  },
};

export async function render(container) {
  let activeTab = "viewer"; // 'viewer' | 'schedules' | 'templates'
  let templatesList = [{ key: "full", label: "Full digest" }];

  container.innerHTML = `
    <h1>Reports & Distribution</h1>
    
    <div class="tab-bar">
      <button class="tab-btn active" data-tab="viewer">Report Generator & Viewer</button>
      <button class="tab-btn" data-tab="schedules">Scheduled Distributions</button>
      <button class="tab-btn" data-tab="templates">Templates & Policy</button>
    </div>

    <div id="tab-content"></div>
  `;

  try {
    const { templates } = await apiGet("/reports/templates");
    if (templates?.length) templatesList = templates;
  } catch {
    /* fallback to default templatesList */
  }

  const tabBtns = container.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.onclick = () => {
      activeTab = btn.dataset.tab;
      tabBtns.forEach((b) => b.classList.toggle("active", b.dataset.tab === activeTab));
      renderTab();
    };
  });

  async function renderTab() {
    const tabEl = document.getElementById("tab-content");
    if (!tabEl) return;

    if (activeTab === "viewer") {
      await renderViewerTab(tabEl);
    } else if (activeTab === "schedules") {
      await renderSchedulesTab(tabEl);
    } else if (activeTab === "templates") {
      renderTemplatesTab(tabEl);
    }
  }

  /* ----------------------------------------------------
     TAB 1: REPORT GENERATOR & VIEWER
  ---------------------------------------------------- */
  async function renderViewerTab(wrap) {
    const zone = getState().zone;
    wrap.innerHTML = `
      <div class="report-header-banner">
        <div class="report-controls">
          <label style="font-weight:600;font-size:12.5px;">Template
            <select id="rpt-template" style="margin-left:4px;">
              ${templatesList.map((t) => `<option value="${escapeHtml(t.key)}">${escapeHtml(t.label)}</option>`).join("")}
            </select>
          </label>
          <button id="rpt-refresh-btn" class="primary">Generate Report</button>
        </div>
        <div class="report-controls">
          <button id="rpt-print-btn" type="button" title="Print or save as PDF">🖨️ Print / Save PDF</button>
          <a id="rpt-download-html" href="#" target="_blank"><button type="button">Download HTML</button></a>
          <a id="rpt-download-csv" href="#" target="_blank"><button type="button">Download CSV</button></a>
          <button id="rpt-copy-btn" type="button">Copy Summary</button>
        </div>
      </div>

      <div class="kpi-row" id="rpt-kpis">
        <div class="kpi-tile"><div class="value" id="rpt-stat-events">—</div><div class="label">Unreported changes</div></div>
        <div class="kpi-tile"><div class="value" id="rpt-stat-zone">${escapeHtml(zone || "All zones")}</div><div class="label">Scope</div></div>
        <div class="kpi-tile"><div class="value" id="rpt-stat-template">Full digest</div><div class="label">Selected template</div></div>
      </div>

      <div class="card" style="padding:12px;">
        <h2 style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <span>Live Report Preview</span>
          <span id="rpt-status" class="faint">Ready</span>
        </h2>
        <iframe id="rpt-iframe" class="report-preview-frame" sandbox="allow-same-origin"></iframe>
      </div>
    `;

    function updateDownloadLinks() {
      const currentZone = getState().zone;
      const tpl = document.getElementById("rpt-template").value;
      const qs = new URLSearchParams();
      if (currentZone) qs.set("zone", currentZone);
      if (tpl) qs.set("template", tpl);

      const qsStr = qs.toString() ? `?${qs.toString()}` : "";
      const csvQsStr = qs.toString() ? `?${qs.toString()}&format=csv` : "?format=csv";

      document.getElementById("rpt-download-html").href = `/api/reports/download${qsStr}`;
      document.getElementById("rpt-download-csv").href = `/api/reports/download${csvQsStr}`;
    }

    async function loadReportPreview() {
      const currentZone = getState().zone;
      const tpl = document.getElementById("rpt-template").value;
      const statusEl = document.getElementById("rpt-status");
      const statEvents = document.getElementById("rpt-stat-events");
      const statTpl = document.getElementById("rpt-stat-template");
      const iframe = document.getElementById("rpt-iframe");

      statusEl.textContent = "Loading report…";
      updateDownloadLinks();

      try {
        const result = await apiGet("/reports/preview", { zone: currentZone, template: tpl });
        iframe.srcdoc = result.html;
        statEvents.textContent = result.event_count ?? 0;
        statTpl.textContent = templatesList.find((t) => t.key === tpl)?.label || tpl;
        statusEl.textContent = `Generated with ${result.event_count} change item(s)`;
      } catch (e) {
        statusEl.textContent = "Generation failed";
        iframe.srcdoc = `<div style="padding:20px;color:#dc2626;font-family:sans-serif;">Failed to load report: ${escapeHtml(e.message)}</div>`;
        showToast(`Report generation failed: ${e.message}`, "error");
      }
    }

    document.getElementById("rpt-template").addEventListener("change", loadReportPreview);
    document.getElementById("rpt-refresh-btn").addEventListener("click", loadReportPreview);

    document.getElementById("rpt-print-btn").addEventListener("click", () => {
      const iframe = document.getElementById("rpt-iframe");
      if (iframe?.contentWindow) {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
      } else {
        window.print();
      }
    });

    document.getElementById("rpt-copy-btn").addEventListener("click", () => {
      const currentZone = getState().zone || "All Zones";
      const tpl = document.getElementById("rpt-template").value;
      const events = document.getElementById("rpt-stat-events").textContent;
      const text = `Zoneguard Report Summary\nScope: ${currentZone}\nTemplate: ${tpl}\nUnreported Changes: ${events}\nGenerated At: ${new Date().toUTCString()}`;
      navigator.clipboard.writeText(text);
      showToast("Report summary copied to clipboard", "success");
    });

    await loadReportPreview();
  }

  /* ----------------------------------------------------
     TAB 2: SCHEDULED DISTRIBUTIONS
  ---------------------------------------------------- */
  async function renderSchedulesTab(wrap) {
    wrap.innerHTML = `
      <div class="filter-bar" style="justify-content:space-between;">
        <p class="muted" style="margin:0;">Manage automated recurring report deliveries to security & operations teams.</p>
        <button id="new-schedule-btn" class="primary">+ New Schedule</button>
      </div>
      <div id="schedules-table-wrap"></div>
    `;

    document.getElementById("new-schedule-btn").addEventListener("click", () => openScheduleModal(null, () => renderSchedulesTab(wrap)));

    const tableWrap = document.getElementById("schedules-table-wrap");
    try {
      const { schedules } = await apiGet("/schedules");
      if (!schedules.length) {
        tableWrap.innerHTML = `<div class="empty-state">No automated schedules configured yet. Click <strong>+ New Schedule</strong> to create one.</div>`;
        return;
      }
      tableWrap.innerHTML = `
        <div class="table-wrap"><table class="data-table">
          <thead><tr>
            <th>Name</th>
            <th>Zone</th>
            <th>Template</th>
            <th>Cadence</th>
            <th>Recipients</th>
            <th>Status</th>
            <th>Last Sent</th>
            <th style="text-align:right;">Actions</th>
          </tr></thead>
          <tbody></tbody>
        </table></div>`;

      const tbody = tableWrap.querySelector("tbody");
      for (const s of schedules) {
        const tr = document.createElement("tr");
        const statusBadge = s.enabled
          ? `<span class="pill on">Active</span>`
          : `<span class="pill off">Paused</span>`;

        tr.innerHTML = `
          <td><strong>${escapeHtml(s.name)}</strong></td>
          <td><span class="pill">${escapeHtml(s.zone || "All zones")}</span></td>
          <td><span class="badge grade-B">${escapeHtml(s.template)}</span></td>
          <td>${escapeHtml(s.cadence)}${s.cadence === "interval" ? ` (${s.interval_minutes}m)` : ""}</td>
          <td class="wrap faint">${(s.recipients || []).map((r) => `<span class="pill" style="margin:1px;">${escapeHtml(r)}</span>`).join("")}</td>
          <td>${statusBadge}</td>
          <td>${formatDate(s.last_sent_at)}</td>
          <td style="text-align:right;white-space:nowrap;"></td>
        `;

        const actionsTd = tr.querySelector("td:last-child");

        const sendBtn = document.createElement("button");
        sendBtn.textContent = "Send now";
        sendBtn.onclick = async () => {
          sendBtn.disabled = true;
          try {
            await apiPost(`/schedules/${s.id}/send-now`);
            showToast(`Report dispatch queued for ${s.name}`, "success");
          } catch (e) {
            showToast(`Failed: ${e.message}`, "error");
          } finally {
            sendBtn.disabled = false;
          }
        };

        const editBtn = document.createElement("button");
        editBtn.textContent = "Edit";
        editBtn.style.marginLeft = "4px";
        editBtn.onclick = () => openScheduleModal(s, () => renderSchedulesTab(wrap));

        const toggleBtn = document.createElement("button");
        toggleBtn.textContent = s.enabled ? "Pause" : "Resume";
        toggleBtn.style.marginLeft = "4px";
        toggleBtn.onclick = async () => {
          try {
            await apiPut(`/schedules/${s.id}`, { ...s, enabled: !s.enabled });
            showToast(`Schedule ${s.enabled ? "paused" : "activated"}`, "success");
            renderSchedulesTab(wrap);
          } catch (e) {
            showToast(`Failed: ${e.message}`, "error");
          }
        };

        const deleteBtn = document.createElement("button");
        deleteBtn.textContent = "Delete";
        deleteBtn.className = "danger";
        deleteBtn.style.marginLeft = "4px";
        deleteBtn.onclick = () => confirmDeleteSchedule(s, () => renderSchedulesTab(wrap));

        actionsTd.append(sendBtn, editBtn, toggleBtn, deleteBtn);
        tbody.appendChild(tr);
      }
    } catch (e) {
      tableWrap.innerHTML = `<div class="empty-state">Failed to load schedules: ${escapeHtml(e.message)}</div>`;
    }
  }

  /* ----------------------------------------------------
     TAB 3: REPORT TEMPLATES & POLICY CATALOG
  ---------------------------------------------------- */
  function renderTemplatesTab(wrap) {
    wrap.innerHTML = `
      <p class="muted" style="margin-top:0;margin-bottom:16px;">
        Standardized report definitions, live from the Zoneguard reporting engine — this list
        always matches what's selectable above and in schedules.
      </p>
      <div class="template-grid">
        ${templatesList
          .map((t) => {
            const meta = TEMPLATE_DESCRIPTIONS[t.key] || {
              description: `Digest scoped to "${t.label}" events only.`,
              audience: "Security Operations",
              cadence: "As needed",
            };
            return `
          <div class="template-card">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <h3>${escapeHtml(t.label)}</h3>
                <span class="badge grade-B mono">${escapeHtml(t.key)}</span>
              </div>
              <p>${escapeHtml(meta.description)}</p>
            </div>
            <div style="border-top:1px solid var(--border);padding-top:10px;font-size:12px;" class="muted">
              <div><strong>Target Audience:</strong> ${escapeHtml(meta.audience)}</div>
              <div style="margin-top:2px;"><strong>Suggested Cadence:</strong> ${escapeHtml(meta.cadence)}</div>
            </div>
          </div>
        `;
          })
          .join("")}
      </div>
    `;
  }

  function openScheduleModal(existingSchedule, onSaved) {
    const isEdit = !!existingSchedule;
    const body = document.createElement("div");
    body.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:10px;min-width:340px;">
        <label>Schedule Name *
          <input type="text" id="sf-name" placeholder="e.g. Weekly Executive Security Digest" value="${escapeHtml(existingSchedule?.name || "")}" required style="width:100%;">
        </label>
        <label>Scope Zone (blank = all zones)
          <input type="text" id="sf-zone" placeholder="e.g. example.com" value="${escapeHtml(existingSchedule?.zone || "")}" style="width:100%;">
        </label>
        <label>Report Template
          <select id="sf-template" style="width:100%;">
            ${templatesList.map((t) => `<option value="${escapeHtml(t.key)}" ${existingSchedule?.template === t.key ? "selected" : ""}>${escapeHtml(t.label)}</option>`).join("")}
          </select>
        </label>
        <label>Cadence
          <select id="sf-cadence" style="width:100%;">
            <option value="daily" ${existingSchedule?.cadence === "daily" ? "selected" : ""}>Daily</option>
            <option value="weekly" ${existingSchedule?.cadence === "weekly" ? "selected" : ""}>Weekly</option>
            <option value="interval" ${existingSchedule?.cadence === "interval" ? "selected" : ""}>Custom Interval (minutes)</option>
          </select>
        </label>
        <div id="sf-interval-group" style="display:${existingSchedule?.cadence === "interval" ? "block" : "none"};">
          <label>Interval Minutes
            <input type="number" id="sf-interval" value="${existingSchedule?.interval_minutes || 60}" min="5" style="width:100%;">
          </label>
        </div>
        <label>Recipients * (comma-separated emails)
          <input type="text" id="sf-recipients" placeholder="secops@company.com, ciso@company.com" value="${escapeHtml((existingSchedule?.recipients || []).join(", "))}" required style="width:100%;">
        </label>
      </div>
    `;

    const cadenceSel = body.querySelector("#sf-cadence");
    cadenceSel.addEventListener("change", () => {
      body.querySelector("#sf-interval-group").style.display = cadenceSel.value === "interval" ? "block" : "none";
    });

    const saveBtn = document.createElement("button");
    saveBtn.className = "primary";
    saveBtn.textContent = isEdit ? "Save Changes" : "Create Schedule";

    const { close } = showModal(isEdit ? `Edit Schedule: ${existingSchedule.name}` : "New Report Schedule", body, {
      footerButtons: [saveBtn],
    });

    saveBtn.addEventListener("click", async () => {
      const payload = {
        name: body.querySelector("#sf-name").value.trim(),
        zone: body.querySelector("#sf-zone").value.trim() || null,
        template: body.querySelector("#sf-template").value,
        cadence: cadenceSel.value,
        interval_minutes: cadenceSel.value === "interval" ? Number(body.querySelector("#sf-interval").value) : null,
        recipients: body
          .querySelector("#sf-recipients")
          .value.split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        enabled: existingSchedule ? existingSchedule.enabled : true,
      };

      if (!payload.name || !payload.recipients.length) {
        showToast("Name and at least one recipient email are required", "error");
        return;
      }

      try {
        if (isEdit) {
          await apiPut(`/schedules/${existingSchedule.id}`, payload);
          showToast("Schedule updated", "success");
        } else {
          await apiPost("/schedules", payload);
          showToast("Schedule created", "success");
        }
        close();
        onSaved?.();
      } catch (e) {
        showToast(`Failed: ${e.message}`, "error");
      }
    });
  }

  function confirmDeleteSchedule(schedule, onDeleted) {
    const body = document.createElement("div");
    body.innerHTML = `
      <p>Are you sure you want to delete schedule <strong>${escapeHtml(schedule.name)}</strong>?</p>
      <p class="faint">This will stop recurring emails sent to ${(schedule.recipients || []).join(", ")}.</p>
    `;

    const delBtn = document.createElement("button");
    delBtn.className = "danger";
    delBtn.textContent = "Delete Schedule";

    const { close } = showModal("Delete Schedule", body, { footerButtons: [delBtn] });

    delBtn.onclick = async () => {
      delBtn.disabled = true;
      try {
        await apiDelete(`/schedules/${schedule.id}`);
        showToast("Schedule deleted", "success");
        close();
        onDeleted?.();
      } catch (e) {
        showToast(`Delete failed: ${e.message}`, "error");
        delBtn.disabled = false;
      }
    };
  }

  const unsub = onStateChange(() => {
    if (activeTab === "viewer") renderViewerTab(document.getElementById("tab-content"));
  });

  await renderTab();
  return () => unsub();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}
