const DEVICE_META = {
  "meter-main": { label: "Main meter", colorVar: "--series-meter" },
  "solar-roof": { label: "Solar inverter", colorVar: "--series-solar" },
  "battery-garage": { label: "Battery", colorVar: "--series-battery" },
  "ev-charger-driveway": { label: "EV charger", colorVar: "--series-ev" },
  "meter-subpanel": { label: "Sub-panel meter", colorVar: "--series-subpanel" },
};

const state = { rangeHours: 6, pollTimer: null };

function color(varName) {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function metaFor(deviceId) {
  return DEVICE_META[deviceId] || { label: deviceId, colorVar: "--series-meter" };
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

function fmtW(w) {
  if (Math.abs(w) >= 1000) return `${(w / 1000).toFixed(2)} kW`;
  return `${Math.round(w)} W`;
}

function fmtTime(iso) {
  const d = new Date(iso + "Z");
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ---------- Stat tiles ----------

function renderStats(summary) {
  const byId = Object.fromEntries(summary.map((r) => [r.device_id, r]));
  const solar = byId["solar-roof"]?.power_w ?? 0;
  const battery = byId["battery-garage"];
  const batteryPower = battery?.power_w ?? 0;
  const soc = battery?.extra?.state_of_charge_pct;
  const load =
    (byId["meter-main"]?.power_w ?? 0) +
    (byId["meter-subpanel"]?.power_w ?? 0) +
    (byId["ev-charger-driveway"]?.power_w ?? 0);
  const gridNet = load - solar - batteryPower;

  const tiles = [
    { label: "Solar generation", value: fmtW(solar), sub: "now" },
    { label: "Total home load", value: fmtW(load), sub: "meters + EV charger" },
    {
      label: gridNet >= 0 ? "Grid import" : "Grid export",
      value: fmtW(Math.abs(gridNet)),
      sub: gridNet >= 0 ? "drawing from grid" : "sending to grid",
    },
    {
      label: "Battery",
      value: soc != null ? `${soc.toFixed(0)}%` : "—",
      sub: batteryPower >= 0 ? `discharging ${fmtW(batteryPower)}` : `charging ${fmtW(-batteryPower)}`,
    },
  ];

  document.getElementById("stat-row").innerHTML = tiles
    .map(
      (t) => `<div class="card stat-tile">
        <div class="label">${t.label}</div>
        <div class="value">${t.value}</div>
        <div class="sub">${t.sub}</div>
      </div>`
    )
    .join("");
}

// ---------- Energy bars ----------

function renderEnergyBars(readingsByDevice) {
  document.getElementById("energy-heading").textContent = `Energy in last ${state.rangeHours}h (kWh)`;

  const totals = Object.entries(readingsByDevice)
    .map(([deviceId, rows]) => {
      if (rows.length < 2) return { deviceId, kwh: 0 };
      const kwh = (rows[rows.length - 1].energy_wh_cumulative - rows[0].energy_wh_cumulative) / 1000;
      return { deviceId, kwh: Math.max(0, kwh) };
    })
    .sort((a, b) => b.kwh - a.kwh);

  const max = Math.max(1, ...totals.map((t) => t.kwh));

  document.getElementById("energy-bars").innerHTML = totals
    .map((t) => {
      const meta = metaFor(t.deviceId);
      const pct = (t.kwh / max) * 100;
      return `<div class="bar-row">
        <div class="name">${meta.label}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:var(${meta.colorVar})"></div></div>
        <div class="amount">${t.kwh.toFixed(2)}</div>
      </div>`;
    })
    .join("");
}

// ---------- Table ----------

function renderTable(summary) {
  const rows = summary
    .slice()
    .sort((a, b) => a.device_id.localeCompare(b.device_id))
    .map((r) => {
      const meta = metaFor(r.device_id);
      return `<tr>
        <td><span class="device-name"><span class="swatch" style="background:var(${meta.colorVar})"></span>${meta.label}</span></td>
        <td>${fmtW(r.power_w)}</td>
        <td>${(r.energy_wh_cumulative / 1000).toFixed(2)} kWh</td>
        <td>${fmtTime(r.timestamp)}</td>
      </tr>`;
    })
    .join("");

  document.getElementById("table-wrap").innerHTML = `
    <table>
      <thead><tr><th>Device</th><th>Power</th><th>Cumulative energy</th><th>Updated</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ---------- Line chart (hand-drawn SVG, no chart library) ----------

const CHART = { w: 900, h: 320, padL: 48, padR: 16, padT: 16, padB: 28 };

function niceTicks(min, max, count) {
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const span = max - min;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const err = (span / count) / step;
  const mult = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
  const niceStep = step * mult;
  const start = Math.floor(min / niceStep) * niceStep;
  const ticks = [];
  for (let v = start; v <= max + niceStep * 0.001; v += niceStep) ticks.push(v);
  return ticks;
}

function renderLineChart(readingsByDevice) {
  const svg = document.getElementById("line-chart");
  const deviceIds = Object.keys(readingsByDevice).filter((id) => readingsByDevice[id].length > 0);

  if (deviceIds.length === 0) {
    svg.innerHTML = `<text x="450" y="160" text-anchor="middle" class="axis-label">no data yet</text>`;
    return;
  }

  let tMin = Infinity, tMax = -Infinity, pMin = 0, pMax = 0;
  for (const id of deviceIds) {
    for (const r of readingsByDevice[id]) {
      const t = new Date(r.timestamp + "Z").getTime();
      tMin = Math.min(tMin, t);
      tMax = Math.max(tMax, t);
      pMin = Math.min(pMin, r.power_w);
      pMax = Math.max(pMax, r.power_w);
    }
  }
  if (pMax === pMin) pMax = pMin + 1;
  pMin -= (pMax - pMin) * 0.08;
  pMax += (pMax - pMin) * 0.08;

  const xScale = (t) => CHART.padL + ((t - tMin) / (tMax - tMin)) * (CHART.w - CHART.padL - CHART.padR);
  const yScale = (p) => CHART.h - CHART.padB - ((p - pMin) / (pMax - pMin)) * (CHART.h - CHART.padT - CHART.padB);

  const yTicks = niceTicks(pMin, pMax, 5);
  const xTicks = niceTicks(tMin, tMax, 6);

  let svgParts = [];

  for (const yt of yTicks) {
    const y = yScale(yt);
    svgParts.push(`<line class="gridline" x1="${CHART.padL}" y1="${y}" x2="${CHART.w - CHART.padR}" y2="${y}" />`);
    svgParts.push(`<text class="axis-label" x="${CHART.padL - 6}" y="${y + 3}" text-anchor="end">${fmtW(yt)}</text>`);
  }
  for (const xt of xTicks) {
    const x = xScale(xt);
    svgParts.push(`<text class="axis-label" x="${x}" y="${CHART.h - 8}" text-anchor="middle">${fmtTime(new Date(xt).toISOString().slice(0, -1))}</text>`);
  }

  for (const id of deviceIds) {
    const meta = metaFor(id);
    const pts = readingsByDevice[id]
      .map((r) => `${xScale(new Date(r.timestamp + "Z").getTime())},${yScale(r.power_w)}`)
      .join(" L ");
    svgParts.push(`<path class="series-line" data-device="${id}" stroke="var(${meta.colorVar})" d="M ${pts}" />`);
  }

  svgParts.push(`<g id="hover-layer"></g>`);

  svg.setAttribute("viewBox", `0 0 ${CHART.w} ${CHART.h}`);
  svg.innerHTML = svgParts.join("\n");

  attachHover(svg, readingsByDevice, deviceIds, xScale, yScale, tMin, tMax);

  document.getElementById("line-legend").innerHTML = deviceIds
    .map((id) => {
      const meta = metaFor(id);
      return `<span><span class="swatch" style="background:var(${meta.colorVar})"></span>${meta.label}</span>`;
    })
    .join("");
}

function attachHover(svg, readingsByDevice, deviceIds, xScale, yScale, tMin, tMax) {
  const tooltip = document.getElementById("tooltip");
  const hoverLayer = document.getElementById("hover-layer");

  function nearestIndex(rows, targetTime) {
    let lo = 0, hi = rows.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (new Date(rows[mid].timestamp + "Z").getTime() < targetTime) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  function onMove(evt) {
    const rect = svg.getBoundingClientRect();
    const scaleX = CHART.w / rect.width;
    const svgX = (evt.clientX - rect.left) * scaleX;
    const targetTime = tMin + ((svgX - CHART.padL) / (CHART.w - CHART.padL - CHART.padR)) * (tMax - tMin);
    if (targetTime < tMin || targetTime > tMax) {
      hoverLayer.innerHTML = "";
      tooltip.style.display = "none";
      return;
    }

    let rowsHtml = [];
    let anchorTime = null;
    let dotsSvg = [];
    for (const id of deviceIds) {
      const rows = readingsByDevice[id];
      if (!rows.length) continue;
      const idx = nearestIndex(rows, targetTime);
      const row = rows[idx];
      anchorTime = anchorTime ?? row.timestamp;
      const meta = metaFor(id);
      const px = xScale(new Date(row.timestamp + "Z").getTime());
      const py = yScale(row.power_w);
      dotsSvg.push(`<circle class="hover-dot" cx="${px}" cy="${py}" r="4" fill="var(${meta.colorVar})"></circle>`);
      rowsHtml.push(
        `<div class="row"><span class="swatch" style="background:var(${meta.colorVar})"></span>${meta.label}: <strong>${fmtW(row.power_w)}</strong></div>`
      );
    }

    const x = xScale(new Date(anchorTime + "Z").getTime());
    hoverLayer.innerHTML =
      `<line class="crosshair" x1="${x}" y1="${CHART.padT}" x2="${x}" y2="${CHART.h - CHART.padB}"></line>` +
      dotsSvg.join("");

    tooltip.style.display = "block";
    tooltip.style.left = `${evt.clientX - rect.left + 12}px`;
    tooltip.style.top = `${evt.clientY - rect.top + 12}px`;
    tooltip.innerHTML = `<div><strong>${fmtTime(anchorTime)}</strong></div>${rowsHtml.join("")}`;
  }

  svg.addEventListener("mousemove", onMove);
  svg.addEventListener("mouseleave", () => {
    hoverLayer.innerHTML = "";
    tooltip.style.display = "none";
  });
}

// ---------- Data loading ----------

function groupByDevice(readings) {
  const out = {};
  for (const r of readings) {
    (out[r.device_id] ||= []).push(r);
  }
  return out;
}

async function loadAll() {
  try {
    const end = new Date();
    const start = new Date(end.getTime() - state.rangeHours * 3600 * 1000);
    const [summary, readings] = await Promise.all([
      fetchJSON("/api/summary"),
      fetchJSON(`/api/readings?start=${start.toISOString()}&limit=20000`),
    ]);

    renderStats(summary);
    const byDevice = groupByDevice(readings);
    renderLineChart(byDevice);
    renderEnergyBars(byDevice);
    renderTable(summary);

    const status = document.getElementById("status");
    status.textContent = `updated ${new Date().toLocaleTimeString()}`;
    status.classList.remove("stale");
  } catch (err) {
    const status = document.getElementById("status");
    status.textContent = `update failed: ${err.message}`;
    status.classList.add("stale");
  }
}

document.getElementById("range-buttons").addEventListener("click", (evt) => {
  const btn = evt.target.closest("button[data-hours]");
  if (!btn) return;
  document.querySelectorAll("#range-buttons button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.rangeHours = parseInt(btn.dataset.hours, 10);
  loadAll();
});

document.getElementById("toggle-table").addEventListener("click", (evt) => {
  const wrap = document.getElementById("table-wrap");
  wrap.classList.toggle("hidden");
  evt.target.textContent = wrap.classList.contains("hidden") ? "show table" : "hide table";
});

loadAll();
state.pollTimer = setInterval(loadAll, 15000);
