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

let DRIFT = null;

function render() {
  const m = DATA.meta;
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("gen").textContent = "Generated " + m.generated_at;
  renderKpis(); renderChart(); renderLegs();
  fetch("data/hedge_drift.json", { cache: "no-store" })
    .then((r) => r.ok ? r.json() : null).then((d) => { if (d) { DRIFT = d; renderDrift(); } })
    .catch(() => {});
}

function pct(x, signed) {
  if (x == null) return "–";
  return (signed && x >= 0 ? "+" : "") + (x * 100).toFixed(1) + "%";
}

function renderDrift() {
  const m = DRIFT.meta, k = DRIFT.kpis, s = DRIFT.series;
  // KPI strip — lead with the PER-SHARE drift (your real hedge); fund-level is context.
  const cards = [
    { label: "Your hedge drift (per BPTIX share)", value: pct(k.hedge_drift, true),
      cls: "b", note: "fixed short is this % too small" },
    { label: "Under-hedge gap", value: usd(k.underhedge_gap_usd),
      cls: "b", note: "short to ADD to re-neutralize" },
    { label: "SpaceX weight (net)", value: pct(k.spacex_weight_net_entry) + " → " + pct(k.spacex_weight_net_now),
      note: "the dilution driving the drift" },
    { label: "Fund public book (context)", value: pct(k.fund_public_growth, true),
      cls: "muted", note: "mostly new inflows — NOT your drift" },
  ];
  document.getElementById("drift-kpis").innerHTML = cards.map((c) =>
    `<div class="kpi"><div class="label">${c.label}</div>
      <div class="value" style="color:${c.cls === "b" ? BAD : c.cls === "muted" ? MUTED : TEXT}">${c.value}</div>
      <div class="note">${c.note}</div></div>`).join("");
  // chart: per-share drift bars (left) + fund-level line (left, muted) + Total Assets (right)
  const x = s.map((r) => r.date);
  Plotly.newPlot("drift-chart", [
    { x, y: s.map((r) => r.gross_total_assets / 1e9), name: "Total Assets ($B, gross)",
      type: "scatter", mode: "lines", line: { color: ACC, width: 2 },
      yaxis: "y2", hovertemplate: "Total Assets $%{y:.1f}B<extra></extra>" },
    { x, y: s.map((r) => r.fund_public_growth * 100), name: "Fund public book growth (context)",
      type: "scatter", mode: "lines", line: { color: MUTED, width: 1.5, dash: "dot" },
      yaxis: "y", hovertemplate: "fund-level %{y:+.1f}%<extra></extra>" },
    { x, y: s.map((r) => r.hedge_drift * 100), name: "Your hedge drift (per share)",
      type: "bar", marker: { color: s.map((r) => r.hedge_drift >= 0 ? "rgba(248,81,73,0.6)" : "rgba(63,185,80,0.6)") },
      yaxis: "y", hovertemplate: "your drift %{y:+.1f}%<extra></extra>" },
  ], {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: GRID, width: 1 } }],
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "Under-hedge (%)", color: BAD, ticksuffix: "%", gridcolor: GRID, zeroline: false },
    yaxis2: { title: "Total Assets ($B)", overlaying: "y", side: "right", color: ACC, rangemode: "tozero", showgrid: false },
    legend: { orientation: "h", y: 1.16, font: { color: TEXT } },
    margin: { t: 50, r: 60, b: 36, l: 60 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
  // table
  document.getElementById("drift-table").innerHTML =
    `<table class="data"><thead><tr><th>Date</th><th>Total Assets (gross)</th><th>Shares out</th>
      <th>Public / share</th><th>SpaceX wt (net)</th><th>Your drift (per share)</th><th>Fund growth (context)</th></tr></thead><tbody>` +
    s.map((r) => `<tr><td>${r.date}</td><td>${usd(r.gross_total_assets)}</td><td>${(r.shares_out / 1e6).toFixed(2)}M</td>
      <td>$${r.public_per_share.toFixed(2)}</td><td>${(r.spacex_weight_net * 100).toFixed(1)}%</td>
      <td style="color:${r.hedge_drift >= 0 ? BAD : GOOD}">${pct(r.hedge_drift, true)}</td>
      <td style="color:${MUTED}">${pct(r.fund_public_growth, true)}</td></tr>`).join("") +
    "</tbody></table>";
  renderComposition();
}

function renderComposition() {
  if (!document.getElementById("comp-chart")) return;
  const k = DRIFT.kpis, s = DRIFT.series, L = DRIFT.meta.leverage_ratio;
  // KPI strip
  const cards = [
    { label: "SpaceX (% of NAV)", value: pct(k.spacex_weight_net_entry) + " → " + pct(k.spacex_weight_net_now),
      cls: "spx", note: "private mark fixed → diluted down" },
    { label: "Public / other (% of NAV)", value: pct(k.public_weight_net_entry) + " → " + pct(k.public_weight_net_now),
      cls: "acc", note: "grows as the fund grows" },
    { label: "Leverage ratio", value: k.leverage_ratio.toFixed(4) + "×",
      cls: "muted", note: "gross ÷ net — assumed CONSTANT" },
    { label: "Borrowings (% of NAV)", value: pct(-(L - 1), true),
      cls: "muted", note: "= −(leverage − 1), held flat" },
  ];
  document.getElementById("comp-kpis").innerHTML = cards.map((c) =>
    `<div class="kpi"><div class="label">${c.label}</div>
      <div class="value" style="color:${c.cls === "spx" ? SPX : c.cls === "acc" ? ACC : c.cls === "muted" ? MUTED : TEXT}">${c.value}</div>
      <div class="note">${c.note}</div></div>`).join("");
  // stacked bars as % of NAV: Public + SpaceX -> total = leverage (~113.6%); 100% line = your equity
  const x = s.map((r) => r.date);
  Plotly.newPlot("comp-chart", [
    { x, y: s.map((r) => r.public_weight_net * 100), name: "Public / other holdings",
      type: "bar", marker: { color: "rgba(77,163,255,0.78)" },
      hovertemplate: "public %{y:.1f}% of NAV<extra></extra>" },
    { x, y: s.map((r) => r.spacex_weight_net * 100), name: "SpaceX (private, fixed mark)",
      type: "bar", marker: { color: "rgba(255,122,69,0.88)" },
      hovertemplate: "SpaceX %{y:.1f}% of NAV<extra></extra>" },
  ], {
    barmode: "stack",
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 100, y1: 100,
      line: { color: GOOD, width: 1.5, dash: "dash" } }],
    annotations: [{ xref: "paper", x: 0.012, y: 100, yanchor: "bottom", showarrow: false,
      text: "100% = your NAV (equity) · the stack above this = borrowings (leverage)",
      font: { color: GOOD, size: 10 } }],
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "% of NAV", ticksuffix: "%", gridcolor: GRID, color: TEXT, rangemode: "tozero" },
    legend: { orientation: "h", y: 1.13, font: { color: TEXT } },
    margin: { t: 44, r: 16, b: 36, l: 52 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
  // composition table ($ and % of NAV, with leverage)
  document.getElementById("comp-table").innerHTML =
    `<table class="data"><thead><tr><th>Date</th><th>Total Assets (gross)</th><th>Net NAV</th><th>Leverage ×</th>
      <th>SpaceX $ (% NAV)</th><th>Public/other $ (% NAV)</th></tr></thead><tbody>` +
    s.map((r) => `<tr><td>${r.date}</td><td>${usd(r.gross_total_assets)}</td><td>${usd(r.net_nav)}</td>
      <td style="color:${MUTED}">${r.leverage_ratio.toFixed(4)}</td>
      <td style="color:${SPX}">${usd(r.spacex_value)} <span style="color:${MUTED}">(${(r.spacex_weight_net * 100).toFixed(1)}%)</span></td>
      <td style="color:${ACC}">${usd(r.public_total)} <span style="color:${MUTED}">(${(r.public_weight_net * 100).toFixed(1)}%)</span></td></tr>`).join("") +
    "</tbody></table>";
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
