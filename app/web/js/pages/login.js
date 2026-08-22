import { apiGet, apiPost } from "../api.js";

export async function renderLogin(root, { oidcEnabled }) {
  root.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;">
      <div class="card" style="width:320px;">
        <h1 style="margin-bottom:4px;">Zoneguard<span style="color:var(--accent);">.</span></h1>
        <p class="muted" style="margin-top:0;">Sign in to continue</p>
        ${
          oidcEnabled
            ? `<button id="oidc-btn" class="primary" style="width:100%;">Sign in with SSO</button>`
            : `
          <form id="login-form" style="display:flex;flex-direction:column;gap:10px;">
            <input type="email" id="login-email" placeholder="Email" required autocomplete="username">
            <input type="password" id="login-password" placeholder="Password" required autocomplete="current-password">
            <button type="submit" class="primary">Sign in</button>
            <div id="login-error" class="faint" style="color:var(--danger);"></div>
          </form>`
        }
      </div>
    </div>
  `;

  if (oidcEnabled) {
    document.getElementById("oidc-btn").addEventListener("click", () => {
      window.location.href = "/api/auth/oidc/login";
    });
    return;
  }

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    const errEl = document.getElementById("login-error");
    errEl.textContent = "";
    try {
      await apiPost("/auth/login", { email, password });
      window.location.reload();
    } catch (err) {
      errEl.textContent = err.message || "Login failed";
    }
  });
}

export async function checkAuth() {
  try {
    return await apiGet("/auth/me");
  } catch {
    return { user: null, oidc_enabled: false };
  }
}
