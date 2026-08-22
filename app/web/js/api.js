const BASE = "/api";

async function toApiError(resp) {
  let detail = resp.statusText;
  try {
    const data = await resp.json();
    detail = data.detail || JSON.stringify(data);
  } catch {
    /* body wasn't JSON; keep statusText */
  }
  const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  err.status = resp.status;
  return err;
}

export async function apiGet(path, params = {}) {
  const url = new URL(BASE + path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  }
  const resp = await fetch(url, { credentials: "same-origin" });
  if (!resp.ok) throw await toApiError(resp);
  return resp.json();
}

export async function apiPost(path, body) {
  const isForm = body instanceof FormData;
  const resp = await fetch(BASE + path, {
    method: "POST",
    credentials: "same-origin",
    headers: isForm ? {} : { "Content-Type": "application/json" },
    body: isForm ? body : JSON.stringify(body ?? {}),
  });
  if (!resp.ok) throw await toApiError(resp);
  return resp.json();
}

export async function apiPut(path, body) {
  const resp = await fetch(BASE + path, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!resp.ok) throw await toApiError(resp);
  return resp.json();
}
