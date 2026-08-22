const listeners = new Set();

let state = {
  zone: localStorage.getItem("zg_zone") || "",
  user: null,
};

export function getState() {
  return state;
}

export function setZone(zone) {
  state = { ...state, zone: zone || "" };
  localStorage.setItem("zg_zone", state.zone);
  listeners.forEach((fn) => fn(state));
}

export function setUser(user) {
  state = { ...state, user };
  listeners.forEach((fn) => fn(state));
}

export function onStateChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
