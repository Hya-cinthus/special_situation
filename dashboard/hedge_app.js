"use strict";

/* Hedged SpaceX-isolation book. Reads data/hedge_book.json.
 * 3 daily P&L lines: Long (BPTIX) / Short (public holdings) / Total. */

const ACC = "#4da3ff", GOOD = "#3fb950", BAD = "#f85149", SPX = "#ff7a45",
      MUTED = "#8b97a7";
const PLOT_BG = "#161b22", GRID = "#2a3343", TEXT = "#e6edf3";
let DATA = null;

function usd(x) {
  if (x == null) return "–";
  const a = Math.abs(x), s = x < 0 ? "-$" : "$";
  if (a >= 1e6) return s + (a / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return s + (a / 1e3).toFixed(0) + "K";
  return s + a.toFixed(0);
}

async function boot() { await load("data/hedge_book.json"); }

async function load(file) {
  const L = document.getElementById("loading"), C = document.getElementById("content"),
        E = document.getElementById("error");
  L.style.display = "block"; C.style.display = "none"; E.style.display = "none";
  try {
    const res = await fetch(file, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status + " " + res.statusText);
    DATA = await res.json();
    render();
    L.style.display = "none"; C.style.display = "block";
  } catch (e) {
    L.style.display = "none"; E.style.display = "block";
    E.innerHTML = "Failed to load <code>" + file + "</code>: " + e.message;
  }
}

function render() {
  const m = DATA.meta;
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("gen").textContent = "Generated " + m.generated_at;
  renderKpis(); renderChart(); renderLegs();
}

function renderKpis() {
  const k = DATA.kpis, m = DATA.meta;
  const cards = [
    { label: "Total P&L (since 5/20)", value: usd(k.total_pnl), cls: k.total_pnl >= 0 ? "g" : "b",
      note: "long + short · as of " + k.as_of },
    { label: "Long leg (BPTIX)", value: usd(k.long_pnl), cls: k.long_pnl >= 0 ? "g" : "b",
      note: usd(m.long_notional) + " notional" },
    { label: "Short leg (public holdings)", value: usd(k.short_pnl), cls: k.short_pnl >= 0 ? "g" : "b",
      note: m.n_shorts + " names · " + usd(m.short_notional) + " notional" },
    { label: "Net long exposure", value: usd(m.long_notional - m.short_notional),
      note: "the unhedged (≈ private/SpaceX + leverage) slice" },
  ];
  document.getElementById("kpis").innerHTML = cards.map((c) =>
    `<div class="kpi"><div class="label">${c.label}</div>
      <div class="value" style="color:${c.cls === "g" ? GOOD : c.cls === "b" ? BAD : TEXT}">${c.value}</div>
      <div class="note">${c.note}</div></div>`).join("");
}

function renderChart() {
  const s = DATA.series;
  const x = s.map((r) => r.date);
  const mk = (key, name, color, width) => ({
    x, y: s.map((r) => r[key]), name, type: "scatter", mode: "lines+markers",
    line: { color, width: width || 2 }, marker: { size: 5 },
    hovertemplate: name + " %{y:$,.0f}<extra></extra>",
  });
  Plotly.newPlot("chart", [
    mk("long_pnl", "Long (BPTIX)", GOOD),
    mk("short_pnl", "Short (public holdings)", BAD),
    mk("total_pnl", "Total (≈ SpaceX/private)", SPX, 3),
  ], {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: GRID, width: 1 } }],
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "P&L ($)", gridcolor: GRID, color: TEXT, tickformat: "$,.0s", zeroline: false },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT } },
    margin: { t: 40, r: 16, b: 36, l: 64 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderLegs() {
  const rows = DATA.legs.map((l) =>
    `<tr>
      <td><b>${l.ticker}</b></td>
      <td><span style="color:${l.side === "long" ? GOOD : BAD}">${l.side}</span></td>
      <td>${l.shares.toLocaleString()}</td>
      <td>$${l.entry_px.toFixed(2)}</td>
      <td>${usd(l.notional)}</td>
    </tr>`).join("");
  document.getElementById("legs").innerHTML =
    `<table class="data"><thead><tr><th>Ticker</th><th>Side</th><th>Shares</th><th>Entry px (5/20)</th><th>Notional</th></tr></thead>
     <tbody>${rows}</tbody></table>`;
}

boot();
