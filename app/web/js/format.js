/* Shared render helpers for badges/pills/dates used across every page. */

export function gradeBadge(grade) {
  // Class name is the literal grade string (e.g. "grade-A+"); components.css matches it via
  // the escaped selector .grade-A\+ — CSS escaping happens only in the selector, never here.
  const span = document.createElement("span");
  span.className = `badge ${grade ? `grade-${grade}` : "grade-none"}`;
  span.textContent = grade || "—";
  return span;
}

export function statePill(state) {
  const span = document.createElement("span");
  span.className = `pill state-${state}`;
  span.textContent = state;
  return span;
}

export function boolPill(label, value, { unknownLabel = "unknown" } = {}) {
  const span = document.createElement("span");
  if (value === true) {
    span.className = "pill on";
    span.textContent = `${label}`;
  } else if (value === false) {
    span.className = "pill off";
    span.textContent = `no ${label}`;
  } else {
    span.className = "pill";
    span.textContent = `${label}: ${unknownLabel}`;
  }
  return span;
}

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeDays(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const days = Math.round((d.getTime() - Date.now()) / 86400000);
  if (days === 0) return "today";
  return days > 0 ? `in ${days}d` : `${-days}d ago`;
}

export function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}
