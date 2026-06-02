"use strict";

/* ARKVX (ARK Venture Fund) — interval fund, at NAV.
 * Story: SEC-named multi-company private look-through (SpaceX/OpenAI/Anthropic)
 * + concentration over time + scenario NAV + LIQUIDITY/GATING risk (no premium).
 * Reads data/arkvx_arkventure.json. */

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7",
      LOW = "#6e7681", WARN = "#d29922", BAD = "#f85149", PURPLE = "#bb86fc";
const PLOT_BG = "#161b22", GRID = "#2a3343", TEXT = "#e6edf3";
const COMPCOLOR = { SpaceX: SPX, OpenAI: ACC, Anthropic: PURPLE };
let DATA = null;

const pctRaw = (x, d = 1) => (x == null ? "–" : (x >= 0 ? "+" : "") + (x * 100).toFixed(d) + "%");
const pctAbs = (x, d = 1) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
function usd(x) {
  if (x == null) return "–";
  const a = Math.abs(x);
  if (a >= 1e12) return "$" + (x / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (x / 1e9).toFixed(0) + "B";
  if (a >= 1e6) return "$" + (x / 1e6).toFixed(0) + "M";
  return "$" + x.toFixed(2);
}
function pill(c) { return `<span class="pill ${c}">${c}</span>`; }

async function boot() { await load("data/arkvx_arkventure.json"); }

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
    E.innerHTML = "Failed to load <code>" + file + "</code>: " + e.message +
      "<br>Run <code>py build.py arkvx_arkventure</code> then serve <code>dashboard/</code>.";
  }
}

function render() {
  const m = DATA.meta;
  document.getElementById("sit-title").textContent = "SpaceX / OpenAI / Anthropic via ARKVX";
  document.getElementById("sit-subtitle").textContent = "data through " + m.last_data_day + " · " + m.primary_ticker + " · interval fund";
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("edgar-link").href =
    `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${m.edgar_cik}&type=NPORT-P`;
  document.getElementById("footer-meta").textContent =
    "Generated " + m.generated_at + " · CIK " + m.edgar_cik + " · interval fund (gated redemptions)";
  renderKpis(); renderThesis(); renderConcChart(); renderScenario(); renderHoldingMarks(); renderNport();
}

function renderKpis() {
  const k = DATA.kpis, m = DATA.meta;
  const sx = (k.lookthrough || []).find((h) => h.name === "SpaceX") || {};
  const cards = [
    { label: "Private exposure (SEC-named)", value: pctAbs(k.total_tracked_pct / 100, 1), cls: "spx", hl: true,
      note: "SpaceX + OpenAI + Anthropic · " + k.filed_date,
      tip: "Sum of SpaceX/OpenAI/Anthropic, each a <b>directly SEC-named</b> NPORT holding (no SPV codenames "
        + "— cleanest of the set). The rest (~84%) is other privates + cash/Treasuries. "
        + "<span class='conf'>measured / high.</span>" },
    { label: "SpaceX weight", value: pctAbs(sx.weight, 1), cls: "spx", hl: true,
      note: "top holding · " + k.filed_date,
      tip: "SpaceX is the fund's largest position. NPORT 1/30 = " + pctAbs(sx.weight, 1)
        + "; ARK's own site shows ~17% at 3/31 (newer). <span class='conf'>SEC-named, high.</span>" },
    { label: "Trades at NAV?", value: "Yes — but gated",
      note: "interval fund",
      tip: "Priced daily at NAV (no wrapper premium like the CEFs), BUT redemptions are limited to "
        + "<b>quarterly tenders capped ~5%</b> of the fund. So the risk is a <b>liquidity discount</b> — "
        + "you may not get out at NAV when you want — not a premium." },
    { label: "Bull / Bear (NAV)", value: pctRaw(k.bull_return, 0) + " / " + pctRaw(k.bear_return, 0),
      note: "if privates re-rate",
      tip: "At NAV, return ≈ NAV move. Bull = SpaceX→$1.75T etc.; bear = markdown. Modest because the "
        + "private basket is only ~16% of the fund. <span class='conf'>scenario estimate.</span>" },
    { label: "Net assets", value: usd(k.net_assets_usd),
      note: "as of " + k.filed_date,
      tip: "Grew ~10× in under 2 years ($55M→$554M) on inflows. <span class='conf'>measured.</span>" },
    { label: "Expense ratio", value: pctAbs(k.expense_ratio, 2),
      note: "high (active interval fund)",
      tip: "~2.88%/yr — the priciest of the set. Active management + private sourcing. <span class='conf'>approx.</span>" },
  ];
  document.getElementById("kpis").innerHTML = cards.map((c) =>
    `<div class="kpi ${c.hl ? "hl" : ""}">
       ${c.tip ? `<span class="info">i<span class="tip">${c.tip}</span></span>` : ""}
       <div class="label">${c.label}</div>
       <div class="value ${c.cls || ""}">${c.value}</div>
       <div class="note">${c.note}</div>
     </div>`).join("");
}

function renderThesis() {
  const k = DATA.kpis;
  document.getElementById("thesis-body").innerHTML = `
    <div class="mark-callout" style="border-left-color:${SPX}">
      <b>A new structure: the interval fund.</b> ARKVX is neither a premium-laden closed-end fund nor a
      simple ETF. It's <b>actively managed</b> and transacts <b>at NAV</b> — so, like BPTRX/AGIX, there's
      <b>no wrapper premium to overpay</b>. The catch is the opposite of liquidity: redemptions are
      <b>gated</b> to quarterly tenders capped near 5%, so in a rush for the exits you may be stuck or
      forced to sell below NAV — a <b>liquidity discount</b>, not a premium. What you get for that lock-up
      is the <b>cleanest, fully SEC-named private basket</b> of the whole monitor: SpaceX
      (${pctAbs((k.lookthrough.find((h) => h.name === "SpaceX") || {}).weight, 1)}, top holding) plus
      OpenAI, Anthropic, xAI, Neuralink, Figure AI and more — no SPV codenames. Net: honest, verifiable,
      at-NAV multi-name exposure, but pricey (~2.9%) and illiquid.
    </div>`;
}

function renderConcChart() {
  const c = DATA.concentration || [];
  const comps = ["SpaceX", "OpenAI", "Anthropic"];
  const lines = comps.map((name) => ({
    x: c.map((p) => p.date), y: c.map((p) => (p.tracked_pct || {})[name] || 0),
    name: name + " %", type: "scatter", mode: "lines+markers",
    line: { color: COMPCOLOR[name], width: 2 }, marker: { size: 6 },
    hovertemplate: "%{x}<br>" + name + " %{y:.1f}% of fund<extra></extra>", yaxis: "y",
  }));
  const aum = {
    x: c.map((p) => p.date), y: c.map((p) => (p.net_assets_usd || 0) / 1e6),
    name: "Net assets ($M)", type: "bar", marker: { color: "rgba(110,118,129,0.25)" },
    hovertemplate: "%{x}<br>net assets $%{y:.0f}M<extra></extra>", yaxis: "y2",
  };
  Plotly.newPlot("chart-conc", [aum, ...lines], {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "% of fund", color: TEXT, ticksuffix: "%", rangemode: "tozero", gridcolor: GRID },
    yaxis2: { title: "Net assets ($M)", overlaying: "y", side: "right", color: MUTED, rangemode: "tozero", showgrid: false },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT } },
    margin: { t: 40, r: 56, b: 30, l: 52 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderScenario() {
  const sc = DATA.scenarios || {};
  const tile = (c, label) => {
    const r = sc[c] && sc[c].return;
    const col = r == null ? MUTED : r > 0.01 ? GOOD : r < -0.01 ? BAD : MUTED;
    const contrib = (sc[c] && sc[c].contrib || []).map((x) =>
      `${x.name} ${pctRaw(x.delta_nav, 1)}`).join(" · ");
    return `<div class="sc"><div class="sclab">${label}</div>
      <div class="scval" style="color:${col}">${pctRaw(r, 0)}</div>
      <div class="dim" style="margin-top:4px">${contrib}</div></div>`;
  };
  document.getElementById("scenario").innerHTML =
    `<div class="scrow3">${tile("bear", "Bear")}${tile("base", "Base")}${tile("bull", "Bull")}</div>
     <p class="desc" style="margin-top:10px">At NAV, return ≈ the NAV move. Each scenario re-rates the
     SEC-named private holdings from their current marks to the bear/base/bull whole-company valuations
     (see the underlying-companies section on the overview page); everything else is held flat.
     The effect is modest because the private basket is only ~${(DATA.kpis.total_tracked_pct).toFixed(0)}%
     of the fund.</p>`;
}

function renderHoldingMarks() {
  const el = document.getElementById("holding-marks");
  if (!el) return;
  const hm = DATA.holding_marks || [];
  const wt = {}; (DATA.kpis.lookthrough || []).forEach((h) => { wt[h.name] = h.weight; });
  if (!hm.length) { el.innerHTML = "<p class='desc'>no valuation timeline</p>"; return; }
  el.innerHTML = `<table class="data">
    <thead><tr><th>Holding</th><th>% of fund</th><th>Marked at</th><th>Now</th><th>Growth</th><th>Conf.</th></tr></thead>
    <tbody>${hm.map((h) => `<tr>
      <td>${h.name}</td>
      <td>${pctAbs(wt[h.name], 1)}</td>
      <td>${usd(h.base_valuation_usd)}<br><span class="sub2">${h.base_round}</span></td>
      <td>${usd(h.cur_valuation_usd)}<br><span class="sub2">${h.cur_round}</span></td>
      <td class="${h.growth_mult >= 1.5 ? "spxcell" : ""}">${h.growth_mult.toFixed(2)}×</td>
      <td>${pill(h.confidence)}</td></tr>`).join("")}</tbody></table>`;
}

function renderNport() {
  const n = DATA.nport_latest;
  const tb = document.querySelector("#nport-table tbody");
  if (!n || !n.top_holdings) { tb.innerHTML = "<tr><td colspan='3'>no filing</td></tr>"; return; }
  const track = /space exploration|openai|anthropic/i;
  tb.innerHTML = n.top_holdings.map((h) =>
    `<tr><td>${h.name}${track.test(h.name) ? " <span class='pill measured'>tracked</span>" : ""}</td>`
    + `<td>${h.pctVal.toFixed(2)}%</td><td>${usd(h.valUSD)}</td></tr>`).join("");
}

boot();
