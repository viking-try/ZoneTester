import { apiGet, apiPost } from "../api.js";
import { PaginatedTable } from "../components/table.js";
import { showToast } from "../components/toast.js";
import { formatDate } from "../format.js";

export async function render(container) {
  container.innerHTML = `
    <h1>Upload</h1>
    <div class="card" style="margin-bottom:16px;max-width:640px;">
      <h2>Upload a dump</h2>
      <p class="muted" style="margin-top:0;">
        Accepts enriched CSV, bare CSV, BIND zone files, or Route&nbsp;53 JSON
        (<code>aws route53 list-resource-record-sets</code> output). Format is auto-detected.
      </p>
      <form id="upload-form">
        <input type="file" id="file-input" accept=".csv,.txt,.zone,.json" required>
        <button type="submit" class="primary" style="margin-left:8px;">Upload</button>
      </form>
    </div>

    <div class="card" style="margin-bottom:16px;max-width:640px;">
      <h2>Fetch from S3</h2>
      <p class="muted" style="margin-top:0;">
        For the Lambda&rarr;S3&rarr;Zoneguard flow: one object per hosted zone under a prefix.
        Uses this container's IAM role — no keys are entered here.
      </p>
      <form id="s3-form">
        <div style="display:flex;flex-direction:column;gap:8px;">
          <input type="text" id="s3-bucket" placeholder="bucket name" required>
          <input type="text" id="s3-prefix" placeholder="prefix (optional)">
          <select id="s3-mode">
            <option value="new">New objects only</option>
            <option value="latest">Latest object only</option>
            <option value="all">All objects</option>
          </select>
          <input type="text" id="s3-role" placeholder="assume-role ARN (optional)">
          <button type="submit" class="primary">Fetch</button>
        </div>
      </form>
    </div>

    <h2>Ingest history</h2>
    <div id="table"></div>
  `;

  const table = new PaginatedTable(document.getElementById("table"), {
    columns: [
      { key: "filename", label: "File / S3 key", sortable: true, className: "mono" },
      { key: "format", label: "Format", sortable: false },
      { key: "source", label: "Source", sortable: false },
      { key: "row_count", label: "Rows", sortable: true },
      { key: "domain_count", label: "Domains", sortable: false },
      { key: "status", label: "Status", sortable: true },
      { key: "uploaded_by", label: "By", sortable: false },
      { key: "created_at", label: "When", sortable: true, render: (r) => formatDate(r.created_at) },
    ],
    defaultSort: { by: "created_at", dir: "desc" },
    fetchPage: async (page) => apiGet("/batches", page),
  });
  await table.refresh();

  document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("file-input");
    const file = fileInput.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await apiPost("/batches", form);
      showToast(`Ingested ${result.row_count} records across ${result.domain_count} domain(s)`, "success");
      fileInput.value = "";
      table.refresh({ preservePage: false });
    } catch (err) {
      showToast(`Upload failed: ${err.message}`, "error");
    }
  });

  document.getElementById("s3-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      bucket: document.getElementById("s3-bucket").value,
      prefix: document.getElementById("s3-prefix").value,
      mode: document.getElementById("s3-mode").value,
      assume_role_arn: document.getElementById("s3-role").value || null,
    };
    try {
      const result = await apiPost("/batches/s3-fetch", body);
      showToast(`Found ${result.objects_found}, ingested ${result.objects_selected}`, "success");
      table.refresh({ preservePage: false });
    } catch (err) {
      showToast(`S3 fetch failed: ${err.message}`, "error");
    }
  });
}
