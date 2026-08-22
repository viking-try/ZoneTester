import { apiGet, apiPost, apiPut } from "../api.js";
import { showModal } from "../components/modal.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Users</h1>
    <div class="filter-bar" style="justify-content:flex-end;">
      <button id="new-user-btn" class="primary">New user</button>
    </div>
    <div id="table"></div>
  `;

  async function load() {
    const wrap = document.getElementById("table");
    try {
      const { users } = await apiGet("/users");
      wrap.innerHTML = `
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Auth</th><th>Active</th><th>Last login</th><th></th></tr></thead>
          <tbody></tbody>
        </table></div>`;
      const tbody = wrap.querySelector("tbody");
      for (const u of users) {
        const tr = document.createElement("tr");
        const roleSelect = document.createElement("select");
        for (const r of ["viewer", "operator", "admin"]) {
          const o = document.createElement("option");
          o.value = r;
          o.textContent = r;
          o.selected = r === u.role;
          roleSelect.appendChild(o);
        }
        roleSelect.addEventListener("change", async () => {
          try {
            await apiPut(`/users/${u.id}/role`, { role: roleSelect.value });
            showToast(`Updated ${u.email}`, "success");
          } catch (e) {
            showToast(`Failed: ${e.message}`, "error");
          }
        });

        tr.innerHTML = `
          <td>${escapeHtml(u.email)}</td>
          <td>${escapeHtml(u.display_name || "")}</td>
          <td class="role-cell"></td>
          <td>${escapeHtml(u.auth_source)}</td>
          <td>${u.is_active ? "yes" : "no"}</td>
          <td>${formatDate(u.last_login_at)}</td>
        `;
        tr.querySelector(".role-cell").appendChild(roleSelect);

        const actionsTd = document.createElement("td");
        if (u.is_active) {
          const deactivateBtn = document.createElement("button");
          deactivateBtn.textContent = "Deactivate";
          deactivateBtn.onclick = async () => {
            try {
              await apiPost(`/users/${u.id}/deactivate`);
              showToast("Deactivated", "success");
              load();
            } catch (e) {
              showToast(`Failed: ${e.message}`, "error");
            }
          };
          actionsTd.appendChild(deactivateBtn);
        }
        tr.appendChild(actionsTd);
        tbody.appendChild(tr);
      }
    } catch (e) {
      wrap.innerHTML = `<div class="empty-state">Failed to load users: ${escapeHtml(e.message)}</div>`;
    }
  }

  document.getElementById("new-user-btn").addEventListener("click", () => openUserForm(load));

  await load();
}

function openUserForm(onSaved) {
  const body = document.createElement("div");
  body.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:8px;min-width:300px;">
      <input type="email" id="uf-email" placeholder="Email" required>
      <input type="text" id="uf-name" placeholder="Display name">
      <input type="password" id="uf-password" placeholder="Password" required>
      <select id="uf-role">
        <option value="viewer">viewer</option>
        <option value="operator">operator</option>
        <option value="admin">admin</option>
      </select>
    </div>
  `;
  const saveBtn = document.createElement("button");
  saveBtn.className = "primary";
  saveBtn.textContent = "Create";
  const { close } = showModal("New user", body, { footerButtons: [saveBtn] });

  saveBtn.addEventListener("click", async () => {
    const payload = {
      email: body.querySelector("#uf-email").value,
      display_name: body.querySelector("#uf-name").value || null,
      password: body.querySelector("#uf-password").value,
      role: body.querySelector("#uf-role").value,
    };
    if (!payload.email || !payload.password) {
      showToast("Email and password are required", "error");
      return;
    }
    try {
      await apiPost("/users", payload);
      showToast("User created", "success");
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
