/* Reusable inline-SVG chart primitives — no external charting library, consistent with the
rest of the SPA. Colors are pulled from CSS custom properties via element.style so both the
OS-preference dark mode and the manual data-theme toggle repaint charts automatically. */
const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

/** data: [{label, value, colorVar}] where colorVar is a CSS custom property name like
 * "--success". Renders a ring; an all-zero dataset renders a neutral empty ring rather than
 * nothing, so the chart never looks like a rendering failure. */
export function donutChart({ data, size = 132, thickness = 20, centerLabel, centerSub }) {
  const total = data.reduce((s, d) => s + Math.max(0, d.value), 0);
  const svg = svgEl("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: "img" });
  svg.setAttribute("aria-label", centerLabel ? `${centerLabel} ${centerSub || ""}`.trim() : "Distribution chart");

  const r = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;

  if (total === 0) {
    const track = svgEl("circle", { cx, cy, r, fill: "none", "stroke-width": thickness });
    track.style.stroke = "var(--bg-inset)";
    svg.appendChild(track);
  } else {
    let offset = 0;
    for (const d of data) {
      if (d.value <= 0) continue;
      const frac = d.value / total;
      const dash = frac * circumference;
      const circle = svgEl("circle", {
        cx,
        cy,
        r,
        fill: "none",
        "stroke-width": thickness,
        "stroke-dasharray": `${dash} ${circumference - dash}`,
        "stroke-dashoffset": String(-offset),
        transform: `rotate(-90 ${cx} ${cy})`,
      });
      circle.style.stroke = `var(${d.colorVar})`;
      circle.style.transition = "stroke-dasharray 0.4s ease";
      const title = svgEl("title");
      title.textContent = `${d.label}: ${d.value} (${Math.round(frac * 100)}%)`;
      circle.appendChild(title);
      svg.appendChild(circle);
      offset += dash;
    }
  }

  if (centerLabel !== undefined) {
    const wrap = document.createElement("div");
    wrap.className = "donut-wrap";
    wrap.appendChild(svg);
    const center = document.createElement("div");
    center.className = "donut-center";
    const valueEl = document.createElement("div");
    valueEl.className = "donut-center-value";
    valueEl.textContent = centerLabel;
    center.appendChild(valueEl);
    if (centerSub) {
      const subEl = document.createElement("div");
      subEl.className = "donut-center-sub";
      subEl.textContent = centerSub;
      center.appendChild(subEl);
    }
    wrap.appendChild(center);
    return wrap;
  }

  return svg;
}

export function chartLegend(data, { onClick } = {}) {
  const total = data.reduce((s, d) => s + Math.max(0, d.value), 0);
  const wrap = document.createElement("div");
  wrap.className = "chart-legend";
  for (const d of data) {
    const row = document.createElement(onClick ? "button" : "div");
    row.className = "chart-legend-item";
    if (onClick) {
      row.type = "button";
      row.addEventListener("click", () => onClick(d));
    }
    const swatch = document.createElement("span");
    swatch.className = "chart-legend-swatch";
    swatch.style.background = `var(${d.colorVar})`;
    const label = document.createElement("span");
    label.className = "chart-legend-label";
    label.textContent = d.label;
    const value = document.createElement("span");
    value.className = "chart-legend-value";
    const pct = total > 0 ? Math.round((d.value / total) * 100) : 0;
    value.textContent = total > 0 ? `${d.value} (${pct}%)` : "0";
    row.append(swatch, label, value);
    wrap.appendChild(row);
  }
  return wrap;
}

/** points: array of numbers, oldest first. Renders a minimal line + last-point dot. Fewer
 * than 2 points renders a flat centered dash rather than a degenerate/invisible path, so a
 * brand-new deployment with 0-1 snapshots doesn't look broken. */
export function sparkline({ points, width = 100, height = 28, colorVar = "--accent" }) {
  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    preserveAspectRatio: "none",
    role: "img",
  });
  svg.setAttribute("aria-label", points.length ? `Trend: ${points.join(", ")}` : "No trend data yet");

  if (points.length < 2) {
    const y = height / 2;
    const line = svgEl("line", { x1: width * 0.2, y1: y, x2: width * 0.8, y2: y, "stroke-width": 1.5, "stroke-dasharray": "3,3" });
    line.style.stroke = "var(--text-faint)";
    svg.appendChild(line);
    return svg;
  }

  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const stepX = width / (points.length - 1);
  const pad = 3;
  const coords = points.map((p, i) => [i * stepX, pad + (1 - (p - min) / range) * (height - pad * 2)]);
  const path = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

  const pathEl = svgEl("path", { d: path, fill: "none", "stroke-width": 1.5, "stroke-linecap": "round", "stroke-linejoin": "round" });
  pathEl.style.stroke = `var(${colorVar})`;
  svg.appendChild(pathEl);

  const [lx, ly] = coords[coords.length - 1];
  const dot = svgEl("circle", { cx: lx, cy: ly, r: 2.2 });
  dot.style.fill = `var(${colorVar})`;
  svg.appendChild(dot);

  return svg;
}

/** Small labeled card combining a value, a sparkline, and a trend delta — the reusable
 * "trend option" dropped into KPI rows across pages. */
export function trendCard({ label, value, points, colorVar = "--accent" }) {
  const card = document.createElement("div");
  card.className = "trend-card";

  const top = document.createElement("div");
  top.className = "trend-card-top";
  const valueEl = document.createElement("div");
  valueEl.className = "trend-card-value";
  valueEl.textContent = value;
  const labelEl = document.createElement("div");
  labelEl.className = "trend-card-label";
  labelEl.textContent = label;
  top.append(valueEl, labelEl);

  const sparkWrap = document.createElement("div");
  sparkWrap.className = "trend-card-spark";
  sparkWrap.appendChild(sparkline({ points, width: 96, height: 28, colorVar }));

  if (points.length >= 2) {
    const delta = points[points.length - 1] - points[0];
    if (delta !== 0) {
      const deltaEl = document.createElement("span");
      deltaEl.className = `trend-delta ${delta > 0 ? "up" : "down"}`;
      deltaEl.textContent = `${delta > 0 ? "↑" : "↓"} ${Math.abs(delta)}`;
      sparkWrap.appendChild(deltaEl);
    }
  }

  card.append(top, sparkWrap);
  return card;
}
