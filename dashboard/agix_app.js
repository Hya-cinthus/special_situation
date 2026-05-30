"use strict";

/* AGIX (KraneShares AI & Technology ETF) — the control case.
 * ETF -> trades AT NAV, so NO premium play. Story = Anthropic CONCENTRATION over
 * time (and its dilution as the fund grew). Reads data/agix_kraneshares.json. */

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7",
      LOW = "#6e7681", WARN = "#d29922", BAD = "#f85149";
const PLOT_BG = "#161b22", GRID = "#2a3343", TEXT = "#e6edf3";
let DATA = null;

const pct = (x, d = 1) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
const pctRaw = (x, d = 1) => (x == null ? "–" : x.toFixed(d) + "%");
function usd(x) {
  if (x == null) return "–";
  const a = Math.abs(x);
  if (a >= 1e12) return "$" + (x / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (x / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return "$" + (x / 1e6).toFixed(0) + "M";
  return "$" + x.toFixed(2);
}
function pill(c) { return `<span class="pill ${c}">${c}</span>`; }

async function boot() { await load("data/agix_kraneshares.json"); }

async function load(file) {
  const loading = document.getElementById("loading"), content = document.getElementById("content"),
        err = document.getElementById("error");
  loading.style.display = "block"; content.style.display = "none"; err.style.display = "none";
  try {
    const res = await fetch(file, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status + " " + res.statusText);
    DATA = await res.json();
    render();
    loading.style.display = "none"; content.style.display = "block";
  } catch (e) {
    loading.style.display = "none"; err.style.display = "block";
    err.innerHTML = "Failed to load <code>" + file + "</code>: " + e.message +
      "<br><br>If you opened the file directly, run <code>py -m http.server 8000</code> in <code>dashboard/</code>.";
  }
}

function render() {
  const m = DATA.meta;
  document.getElementById("sit-title").textContent = "Anthropic via AGIX (ETF)";
  document.getElementById("sit-subtitle").textContent = "data through " + m.last_data_day + " · " + m.primary_ticker;
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("edgar-link").href =
    `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${m.edgar_cik}&type=NPORT-P`;
  document.getElementById("footer-meta").textContent =
    "Generated " + m.generated_at + " · CIK " + m.edgar_cik + " · seriesId " + m.edgar_series_id;
  renderKpis(); renderThesis(); renderConcChart(); renderPriceChart();
  renderHoldingMarks(); renderNport();
}

function renderKpis() {
  const k = DATA.kpis;
  const first = (DATA.concentration || [])[0];
  const cards = [
    { label: "Anthropic % — last FILED", value: pctRaw(k.anthropic_pct_filed, 2), cls: "spx", hl: true,
      note: k.anthropic_filed_date + " · SEC NPORT (direct holding)",
      tip: "Anthropic is a <b>DIRECT, SEC-named holding</b> (NPORT title 'ANTHROPIC, PBC SERIES E-1 "
        + "PREFERRED') — high confidence, verifiable, unlike the SPV codenames in the CEFs. "
        + usd(k.anthropic_value_usd) + " of a " + usd(k.net_assets_usd) + " fund. <span class='conf'>measured / high.</span>" },
    { label: "Anthropic % — implied NOW", value: pctRaw(k.anthropic_pct_implied_now, 2), cls: "spx", hl: true,
      note: "after Series H re-rate, est.",
      tip: "If the Anthropic sleeve re-rated " + (k.anthropic_sleeve_mult || 0).toFixed(2)
        + "× (Series G→H) and nothing else moved, its weight would be ~" + pctRaw(k.anthropic_pct_implied_now, 2)
        + " now. <span class='conf'>estimate / med — assumes other holdings flat, no creations since filing.</span>" },
    { label: "Trades at NAV?", value: "Yes — ETF",
      note: "create/redeem keeps price ≈ NAV",
      tip: "AGIX is an <b>ETF</b>: authorized participants arbitrage any gap, so it trades at/near NAV. "
        + "There is <b>no premium-to-NAV play</b> here (unlike VCX/DXYZ/RVI). This is the clean control case." },
    { label: "Expense ratio", value: pct(k.expense_ratio, 2),
      note: "low; liquid",
      tip: "0.99%/yr. The cheapest, most liquid, fully-verifiable way to own a (small) slice of Anthropic." },
    { label: "Fund net assets", value: usd(k.net_assets_usd),
      note: "as of " + k.anthropic_filed_date,
      tip: "Grew fast on inflows (" + (first ? usd(first.net_assets_usd) + " → " : "") + usd(k.net_assets_usd)
        + "). That growth is exactly what DILUTED the Anthropic weight. <span class='conf'>measured.</span>" },
    { label: "Anthropic sleeve gain", value: (k.anthropic_cost_basis_mult || 0).toFixed(0) + "×",
      note: "since AGIX entered (~$18B)",
      tip: "AGIX added Anthropic ~Feb-2025 at a ~$18B valuation; it's now ~$965B — roughly "
        + (k.anthropic_cost_basis_mult || 0).toFixed(0) + "× on that sleeve. <span class='conf'>cost basis approx.</span>" },
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
  const c = DATA.concentration || [];
  const hi = c.reduce((a, b) => (b.anthropic_pct > (a ? a.anthropic_pct : -1) ? b : a), null);
  document.getElementById("thesis-body").innerHTML = `
    <div class="mark-callout" style="border-left-color:${ACC}">
      <b>The control case.</b> VCX, DXYZ and RVI are closed-end funds where you overpay a wrapper premium.
      <b>AGIX is an ETF</b> — create/redeem keeps it at NAV, so there's <b>no premium to trap you</b>, the
      fee is low (0.99%), and <b>Anthropic is a direct, SEC-named holding</b> (not an opaque SPV).
      The trade-off is small concentration — and it's getting <b>smaller</b>: Anthropic peaked at
      <b>${hi ? pctRaw(hi.anthropic_pct, 2) : "~4.2%"}</b> (${hi ? hi.date : "12/31"}) and fell to
      <b>${pctRaw(k.anthropic_pct_filed, 2)}</b> by ${k.anthropic_filed_date} as the fund's assets ballooned
      on inflows. That's the <b>same dilution mechanism as the Baron/SpaceX case</b> — new cash buys the rest
      of the book, shrinking the headline name's weight — just in a clean, at-NAV ETF wrapper. If you want
      honest, liquid Anthropic exposure without premium games, this is the vehicle; if you want a
      concentrated bet, it isn't.
    </div>`;
}

function renderConcChart() {
  const c = DATA.concentration || [];
  const pctTrace = {
    x: c.map((p) => p.date), y: c.map((p) => p.anthropic_pct),
    name: "Anthropic % of fund", type: "scatter", mode: "lines+markers",
    line: { color: SPX, width: 2.2 }, marker: { size: 8 },
    hovertemplate: "%{x}<br>Anthropic %{y:.2f}% of fund<extra></extra>", yaxis: "y",
  };
  const aumTrace = {
    x: c.map((p) => p.date), y: c.map((p) => p.net_assets_usd / 1e6),
    name: "Fund net assets ($M)", type: "bar", marker: { color: "rgba(77,163,255,0.35)" },
    hovertemplate: "%{x}<br>net assets $%{y:.0f}M<extra></extra>", yaxis: "y2",
  };
  const k = DATA.kpis;
  const traces = [aumTrace, pctTrace];
  if (k.anthropic_pct_implied_now != null) {
    traces.push({
      x: [DATA.meta.last_data_day], y: [k.anthropic_pct_implied_now],
      name: "implied now (re-rate est.)", type: "scatter", mode: "markers",
      marker: { color: WARN, symbol: "diamond-open", size: 12, line: { width: 2 } },
      hovertemplate: "%{x}<br>implied ~%{y:.2f}% after Series H<extra></extra>", yaxis: "y",
    });
  }
  Plotly.newPlot("chart-conc", traces, {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "Anthropic % of fund", color: SPX, ticksuffix: "%", rangemode: "tozero", gridcolor: GRID },
    yaxis2: { title: "Net assets ($M)", overlaying: "y", side: "right", color: ACC, rangemode: "tozero", showgrid: false },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT } },
    margin: { t: 40, r: 56, b: 30, l: 56 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderPriceChart() {
  const s = DATA.price_series || [];
  Plotly.newPlot("chart-price", [{
    x: s.map((p) => p.date), y: s.map((p) => p.price),
    name: "AGIX price", type: "scatter", mode: "lines", line: { color: ACC, width: 1.6 },
    hovertemplate: "%{x}<br>$%{y:.2f}<extra></extra>",
  }], {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "USD / share", tickprefix: "$", gridcolor: GRID, color: TEXT },
    margin: { t: 20, r: 16, b: 30, l: 52 }, showlegend: false,
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderHoldingMarks() {
  const el = document.getElementById("holding-marks");
  if (!el) return;
  const hm = DATA.holding_marks || [];
  if (!hm.length) { el.innerHTML = "<p class='desc'>no valuation timeline</p>"; return; }
  el.innerHTML = `<table class="data">
    <thead><tr><th>Holding</th><th>% of fund (filed)</th><th>Marked at</th><th>Now</th><th>Growth</th><th>Conf.</th></tr></thead>
    <tbody>${hm.map((h) => `<tr>
      <td>${h.name}</td>
      <td>${pctRaw(DATA.kpis.anthropic_pct_filed, 2)}</td>
      <td>${usd(h.base_valuation_usd)}<br><span class="sub2">${h.base_round}</span></td>
      <td>${usd(h.cur_valuation_usd)}<br><span class="sub2">${h.cur_round}</span></td>
      <td class="${h.growth_mult >= 1.5 ? "spxcell" : ""}">${h.growth_mult.toFixed(2)}×</td>
      <td>${pill(h.confidence)}</td></tr>`).join("")}</tbody></table>`;
}

function renderNport() {
  const n = DATA.nport_latest;
  const tb = document.querySelector("#nport-table tbody");
  if (!n || !n.top_holdings) { tb.innerHTML = "<tr><td colspan='3'>no filing</td></tr>"; return; }
  tb.innerHTML = n.top_holdings.map((h) =>
    `<tr><td>${h.name}${/anthropic/i.test(h.name) ? " <span class='pill measured'>Anthropic</span>" : ""}</td>`
    + `<td>${h.pctVal.toFixed(2)}%</td><td>${usd(h.valUSD)}</td></tr>`).join("");
}

boot();
