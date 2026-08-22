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

const NAV = [
  { section: "Overview", items: [["dashboard", "Dashboard"]] },
  {
    section: "Inventory",
    items: [
      ["domains", "Domains"],
      ["records", "Records"],
      ["upload", "Upload"],
    ],
  },
  {
    section: "Operations",
    items: [
      ["scan-queue", "Scan Queue"],
      ["cleanup", "Cleanup"],
      ["risk", "Risk"],
    ],
  },
  { section: "Reporting", items: [["reports", "Reports"], ["tickets", "Tickets"]] },
  { section: "Admin", items: [["audit", "Audit Log"], ["settings", "Settings"], ["users", "Users"]] },
];

async function renderShell() {
  document.getElementById("app-shell").innerHTML = `
    <aside id="sidebar">
      <div class="brand">Zoneguard<span class="dot">.</span></div>
      <nav id="nav"></nav>
    </aside>
    <div id="main">
      <div id="topbar">
        <select id="zone-select" class="zone-select"><option value="">All zones</option></select>
        <div class="spacer"></div>
        <span id="user-badge" class="muted"></span>
        <button id="logout-btn" type="button">Sign out</button>
      </div>
      <div id="content"></div>
    </div>
    <div id="toast-stack"></div>
  `;

  const nav = document.getElementById("nav");
  for (const section of NAV) {
    const h = document.createElement("div");
    h.className = "nav-section";
    h.textContent = section.section;
    nav.appendChild(h);
    for (const [path, label] of section.items) {
      const a = document.createElement("a");
      a.href = `#/${path}`;
      a.textContent = label;
      a.dataset.path = path;
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
  const path = raw.split("?")[0];
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
  content.innerHTML = "";
  try {
    const mod = await loader();
    currentPageCleanup = await mod.render(content);
  } catch (e) {
    console.error(e);
    content.innerHTML = `<div class="empty-state">Failed to load page: ${String(e.message || e)}</div>`;
  }
}

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
