/* Manual dark-mode toggle, layered on top of the OS-preference default. Explicit choice
persists in localStorage; absence of a stored choice means "follow the OS", matching the CSS
in base.css which only checks prefers-color-scheme when no data-theme attribute is set. */
const STORAGE_KEY = "zg_theme";

export function getStoredTheme() {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : null;
}

export function applyStoredTheme() {
  const stored = getStoredTheme();
  if (stored) document.documentElement.setAttribute("data-theme", stored);
  else document.documentElement.removeAttribute("data-theme");
}

export function isEffectivelyDark() {
  const stored = getStoredTheme();
  if (stored) return stored === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function setTheme(theme) {
  if (theme === "light" || theme === "dark") {
    localStorage.setItem(STORAGE_KEY, theme);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
  applyStoredTheme();
}

export function toggleTheme() {
  setTheme(isEffectivelyDark() ? "light" : "dark");
}

// Applied immediately on script load (before the shell renders) so there's no flash of the
// wrong theme between page load and app.js's DOMContentLoaded handler running.
applyStoredTheme();
