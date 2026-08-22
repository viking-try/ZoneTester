import { apiGet, apiPost } from "./api.js";
import { checkAuth, renderLogin } from "./pages/login.js";
import { getState, onStateChange, setUser, setZone } from "./state.js";

const ROUTES = {
  dashboard: () => import("./pages/dashboard.js"),
  domains: () => import("./pages/domains.js"),
  records: () => import("./pages/records.js"),
  upload: () => import("./pages/upload.js"),
  "scan-queue": () => import("./pages/scan_queue.js"),
  cleanup: () => import("./pages/cleanup.js"),
  risk: () => import("./pages/risk.js"),
  reports: () => import("./pages/reports.js"),
  tickets: () => import("./pages/tickets.js"),
  audit: () => import("./pages/audit.js"),
  settings: () => import("./pages/settings.js"),
  users: () => import("./pages/users.js"),
};

const ICONS = {
  dashboard: `<svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>`,
  domains: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>`,
  records: `<svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9H9V9h10v2zm-4 4H9v-2h6v2zm4-8H9V5h10v2z"/></svg>`,
  upload: `<svg viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>`,
  "scan-queue": `<svg viewBox="0 0 24 24"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg>`,
  cleanup: `<svg viewBox="0 0 24 24"><path d="M19.36 10.04l-2.4-2.4c-.39-.39-1.02-.39-1.41 0l-1.84 1.84 3.81 3.81 1.84-1.84c.39-.39.39-1.02 0-1.41zM3 21.5h3.75L16.29 11.96l-3.75-3.75L3 17.75V21.5zm16.5-16.5h-4l-1-1h-5l-1 1h-4v2h15z"/></svg>`,
  risk: `<svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-1 6h2v6h-2V7zm0 8h2v2h-2v-2z"/></svg>`,
  reports: `<svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>`,
  tickets: `<svg viewBox="0 0 24 24"><path d="M22 10V6c0-1.11-.9-2-2-2H4c-1.1 0-1.99.89-1.99 2v4c1.1 0 1.99.9 1.99 2s-.89 2-2 2v4c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-4c-1.1 0-2-.9-2-2s.9-2 2-2zm-9 7.5h-2v-2h2v2zm0-4.5h-2v-2h2v2zm0-4.5h-2v-2h2v2z"/></svg>`,
  audit: `<svg viewBox="0 0 24 24"><path d="M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/></svg>`,
  settings: `<svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>`,
  users: `<svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>`,
  sidebarToggle: `<svg viewBox="0 0 24 24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>`,
};

const NAV = [
  { section: "Overview", items: [["dashboard", "Dashboard", ICONS.dashboard]] },
  {
    section: "Inventory",
    items: [
      ["domains", "Domains", ICONS.domains],
      ["records", "Records", ICONS.records],
      ["upload", "Upload", ICONS.upload],
    ],
  },
  {
    section: "Operations",
    items: [
      ["scan-queue", "Scan Queue", ICONS["scan-queue"]],
      ["cleanup", "Cleanup", ICONS.cleanup],
      ["risk", "Risk", ICONS.risk],
    ],
  },
  { section: "Reporting", items: [["reports", "Reports", ICONS.reports], ["tickets", "Tickets", ICONS.tickets]] },
  { section: "Admin", items: [["audit", "Audit Log", ICONS.audit], ["settings", "Settings", ICONS.settings], ["users", "Users", ICONS.users]] },
];

let isSidebarCollapsed = localStorage.getItem("zg_sidebar_collapsed") === "true";

export function toggleSidebar(force) {
  const shell = document.getElementById("app-shell");
  if (!shell) return;
  if (typeof force === "boolean") isSidebarCollapsed = force;
  else isSidebarCollapsed = !isSidebarCollapsed;

  shell.classList.toggle("sidebar-collapsed", isSidebarCollapsed);
  localStorage.setItem("zg_sidebar_collapsed", isSidebarCollapsed ? "true" : "false");
}

async function renderShell() {
  const shell = document.getElementById("app-shell");
  if (isSidebarCollapsed) shell.classList.add("sidebar-collapsed");

  shell.innerHTML = `
    <aside id="sidebar">
      <div class="brand">
        <span class="brand-full">Zoneguard<span class="dot">.</span></span>
        <span class="brand-mini">ZG.</span>
      </div>
      <nav id="nav"></nav>
    </aside>
    <div id="main">
      <div id="topbar">
        <button id="sidebar-toggle-btn" class="sidebar-toggle-btn" type="button" title="Toggle sidebar (Ctrl+B)">
          ${ICONS.sidebarToggle}
        </button>
        <select id="zone-select" class="zone-select"><option value="">All zones</option></select>
        <div class="spacer"></div>
        <span id="user-badge" class="muted"></span>
        <button id="logout-btn" type="button">Sign out</button>
      </div>
      <div id="content"></div>
    </div>
    <div id="toast-stack"></div>
  `;

  document.getElementById("sidebar-toggle-btn").addEventListener("click", () => toggleSidebar());

  const nav = document.getElementById("nav");
  for (const section of NAV) {
    const h = document.createElement("div");
    h.className = "nav-section";
    h.textContent = section.section;
    nav.appendChild(h);
    for (const [path, label, iconSvg] of section.items) {
      const a = document.createElement("a");
      a.href = `#/${path}`;
      a.dataset.path = path;
      a.setAttribute("data-tooltip", label);
      a.innerHTML = `
        <span class="nav-icon">${iconSvg}</span>
        <span class="nav-label">${label}</span>
      `;
      nav.appendChild(a);
    }
  }

  const zoneSelect = document.getElementById("zone-select");
  zoneSelect.addEventListener("change", (e) => setZone(e.target.value));
  onStateChange((s) => {
    if (zoneSelect.value !== s.zone) zoneSelect.value = s.zone;
  });

  const user = getState().user;
  document.getElementById("user-badge").textContent = user ? `${user.email} · ${user.role}` : "";
  document.getElementById("logout-btn").addEventListener("click", async () => {
    await apiPost("/auth/logout");
    window.location.reload();
  });

  await populateZones();
}

async function populateZones() {
  const sel = document.getElementById("zone-select");
  if (!sel) return;
  try {
    const { zones } = await apiGet("/domains/zones");
    for (const z of zones) {
      const o = document.createElement("option");
      o.value = z.hosted_zone;
      o.textContent = `${z.hosted_zone} (${z.domain_count})`;
      sel.appendChild(o);
    }
    sel.value = getState().zone;
  } catch {
    // best-effort — a page's own load will surface a real connectivity error
  }
}

let currentPageCleanup = null;

async function route() {
  const raw = window.location.hash.replace(/^#\//, "") || "dashboard";
  const [path, queryString] = raw.split("?");
  const loader = ROUTES[path] || ROUTES.dashboard;

  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.path === path));

  if (typeof currentPageCleanup === "function") {
    try {
      currentPageCleanup();
    } catch {
      /* page cleanup must never block navigation */
    }
    currentPageCleanup = null;
  }

  const content = document.getElementById("content");
  if (!content) return;
  content.innerHTML = "";
  try {
    const mod = await loader();
    const queryParams = new URLSearchParams(queryString || "");
    currentPageCleanup = await mod.render(content, queryParams);
  } catch (e) {
    console.error(e);
    content.innerHTML = `<div class="empty-state">Failed to load page: ${String(e.message || e)}</div>`;
  }
}

// Global keyboard shortcut Ctrl+B or Cmd+B to toggle sidebar
window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
    e.preventDefault();
    toggleSidebar();
  }
});

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", async () => {
  const { user, oidc_enabled } = await checkAuth();
  if (!user) {
    await renderLogin(document.getElementById("app-shell"), { oidcEnabled: oidc_enabled });
    return;
  }
  setUser(user);
  await renderShell();
  route();
});

