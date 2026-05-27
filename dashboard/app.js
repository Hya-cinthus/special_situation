"use strict";

/* -------------------------------------------------------------------------
 * Multi-situation shell. Add a new situation by appending to this list and
 * dropping its JSON in data/. No other frontend change needed.
 * ---------------------------------------------------------------------- */
const SITUATIONS = [
  { key: "spacex_baron", file: "data/spacex_baron.json" },
];

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7", LOW = "#6e7681";
const PLOT_BG = "#161b22", GRID = "#2a3343", TEXT = "#e6edf3";

let DATA = null;

/* ----------------------------- formatting ------------------------------ */
const pct = (x, d = 1) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
const signPct = (x, d = 1) => (x == null ? "–" : (x >= 0 ? "+" : "") + (x * 100).toFixed(d) + "%");
function usd(x) {
  if (x == null) return "–";
  const a = Math.abs(x);
  if (a >= 1e12) return "$" + (x / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (x / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return "$" + (x / 1e6).toFixed(1) + "M";
  return "$" + x.toFixed(0);
}
const fmtDate = (s) => s;
function daysBetween(aIso, bIso) {
  return Math.round((Date.parse(bIso) - Date.parse(aIso)) / 86400000);
}

/* --------------------------- scenario math ----------------------------- *
 * Mirrors situations/spacex_baron/engine/scenarios.py exactly so the
 * client-side sliders match the Python-precomputed table.                  */
function ipoRerate(spacex, pub, curVal, ipoVal) {
  const scale = ipoVal / curVal;
  const newS = spacex * scale, total = newS + pub, before = spacex + pub;
  return { spacex: newS, pub, total, weight: total ? newS / total : null,
           stepup: before ? total / before - 1 : null, scale };
}
function flowShock(spacex, pub, flow) {
  let newPub = pub + flow, forced = 0;
  if (newPub < 0) { forced = -newPub; newPub = 0; }
  const newS = Math.max(0, spacex - forced), total = newS + newPub;
  return { spacex: newS, pub: newPub, total, forced, weight: total ? newS / total : null };
}
function combined(base, ipoVal, flow) {
  const r = ipoRerate(base.spacex_value_usd, base.public_value_usd, base.current_valuation_usd, ipoVal);
  const f = flowShock(r.spacex, r.pub, flow);
  return { weight: f.weight, spacex: f.spacex, pub: f.pub, total: f.total,
           stepup: r.stepup, forced: f.forced, ipoVal, flow };
}

/* ------------------------------ bootstrap ------------------------------ */
async function boot() {
  const sel = document.getElementById("situation-select");
  SITUATIONS.forEach((s) => {
    const o = document.createElement("option");
    o.value = s.file; o.textContent = s.key; sel.appendChild(o);
  });
  sel.onchange = () => load(sel.value);
  await load(SITUATIONS[0].file);
}

async function load(file) {
  const loading = document.getElementById("loading");
  const content = document.getElementById("content");
  const errBox = document.getElementById("error");
  loading.style.display = "block"; content.style.display = "none"; errBox.style.display = "none";
  try {
    const res = await fetch(file, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status + " " + res.statusText);
    DATA = await res.json();
    render();
    loading.style.display = "none"; content.style.display = "block";
  } catch (e) {
    loading.style.display = "none";
    errBox.style.display = "block";
    errBox.innerHTML = "Failed to load <code>" + file + "</code>: " + e.message +
      "<br><br>If you opened index.html directly, the browser may be blocking local fetch(). " +
      "Run <code>py -m http.server 8000</code> in the <code>dashboard/</code> folder and open " +
      "<a href='http://localhost:8000'>http://localhost:8000</a>.";
  }
}

function render() {
  const m = DATA.meta;
  document.getElementById("sit-title").textContent = m.title;
  document.getElementById("sit-subtitle").textContent =
    "data through " + m.last_data_day + " · " + m.primary_ticker;
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("entry-date-txt").textContent = m.entry_date;
  document.getElementById("edgar-link").href =
    `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${m.edgar_cik}&type=NPORT-P`;
  document.getElementById("footer-meta").textContent =
    "Generated " + m.generated_at + " · registrant CIK " + m.edgar_cik +
    " · " + DATA.series.length + " daily points · " + DATA.anchors.length + " filing anchors.";

  renderKpis();
  renderWeightChart();
  renderAumChart();
  renderMarkChart();
  renderDecompChart();
  renderResidChart();
  renderAnchorTable();
  renderMarksTable();
  renderGaps();
  initScenario();
}

/* -------------------------------- KPIs --------------------------------- *
 * The current-situation highlights. Every card carries (a) an ⓘ tooltip that
 * states exactly how the number is derived + its confidence, and (b) clickable
 * source links that jump straight to the primary source (EDGAR filing, Yahoo,
 * the dated news mark).                                                       */
function secFilingUrl(accession) {
  const nod = (accession || "").replace(/-/g, "");
  const cik = String(parseInt(DATA.meta.edgar_cik, 10));
  return `https://www.sec.gov/Archives/edgar/data/${cik}/${nod}/`;
}
const YAHOO = "https://finance.yahoo.com/quote/BPTRX";

function renderKpis() {
  const k = DATA.kpis, ipo = DATA.meta.ipo;
  const today = new Date().toISOString().slice(0, 10);
  const dToIpo = daysBetween(today, ipo.first_trade_date);

  const la = DATA.anchors[DATA.anchors.length - 1];           // latest measured filing
  const filingUrl = secFilingUrl(la.accession);
  const lastNavPt = [...DATA.series].reverse().find((p) => p.nav_per_share != null);
  const navTxt = lastNavPt ? "$" + lastNavPt.nav_per_share.toFixed(2) : "–";
  const mk125 = DATA.marks.find((m) => m.date === "2026-02-02") || {};
  const mkIpo = DATA.marks.find((m) => m.date === "2026-06-12") || {};
  const ipo175 = (DATA.scenario_table || []).find(
    (r) => Math.round(r.ipo_valuation_usd) === 1750000000000) || {};
  const markAge = daysBetween("2026-02-02", today);
  const ov = (DATA.aum_overrides || [])[ (DATA.aum_overrides || []).length - 1 ];  // latest reported AUM
  // implied net inflows since last filing = current AUM − filed net assets grown by NAV
  const impliedInflow = (ov && lastNavPt)
    ? k.total_nav_usd - la.net_assets_usd * (lastNavPt.nav_per_share / la.nav_at_report) : null;

  const S_EDGAR = { label: "📄 NPORT-P " + la.report_date, url: filingUrl };
  const S_YAHOO = { label: "📈 Yahoo NAV", url: YAHOO };
  const S_MERGER = { label: "📰 source", url: mk125.source_url || "#" };
  const S_IPO = { label: "📰 S-1 / source", url: mkIpo.source_url || "#" };
  const S_AUM = ov ? { label: "📊 reported AUM", url: ov.source_url || "#" } : null;
  const S_FACT = { label: "📄 Baron fact sheet",
    url: "https://www.baroncapitalgroup.com/sites/default/files/2026-04/baron-partners-fund-fact-sheet-bptix-3.31.26.pdf" };

  const cards = [
    { label: "SpaceX weight — NOW (est.)", value: pct(k.spacex_weight), cls: "spx", hl: true,
      note: "as of " + k.as_of + " · vs " + pct(la.spacex_weight_measured) + " filed " + la.report_date,
      tip: "<b>Reconstructed</b>, not directly observable. = SpaceX $ ÷ total AUM. SpaceX $ is carried "
        + "from the last filing at the $1.25T mark (can't add private shares, no new mark). AUM is "
        + (ov ? "trued-up to reported " + usd(ov.net_assets_usd) + " (" + ov.date + ") then drifted by NAV"
              : "NAV × shares interpolated between filings") + ". "
        + (impliedInflow && impliedInflow > 0
            ? "It has fallen from " + pct(la.spacex_weight_measured) + " (filed " + la.report_date + ") because "
              + "~" + usd(impliedInflow) + " of net inflows since then went into <b>public holdings</b> (new cash "
              + "can't buy private SpaceX), diluting the SpaceX weight — your dilution thesis, live. "
            : "")
        + "<span class='conf'>Confidence: MED — SpaceX $ measured; AUM post-filing is a sourced estimate.</span>",
      sources: ov ? [S_EDGAR, S_AUM, S_YAHOO] : [S_EDGAR, S_YAHOO] },

    { label: "SpaceX weight — last FILED", value: pct(la.spacex_weight_measured), cls: "spx", hl: true,
      note: la.report_date + " · % of net assets",
      tip: "<b>Hard regulatory data — no reconstruction.</b> Sum of the pctVal of all "
        + la.spacex_n_tranches + " SpaceX line items in Baron Partners' NPORT-P "
        + "(seriesId S000000588, verified). <b>This is % of NET ASSETS.</b> Baron's fact sheet shows "
        + "SpaceX at 33.0% of total long investments — the gap is leverage: the fund runs ~113% long / "
        + "−13% cash, so 33.0% × 1.13 ≈ 37.5%. Both are correct under their own denominator. "
        + "<span class='conf'>Confidence: HIGH — straight from the SEC filing.</span>",
      sources: [S_EDGAR, S_FACT] },

    { label: "Fund leverage (long exposure)",
      value: la.total_assets_usd ? (la.total_assets_usd / la.net_assets_usd * 100).toFixed(0) + "% long" : "–",
      note: la.total_assets_usd
        ? "−" + ((la.total_assets_usd / la.net_assets_usd - 1) * 100).toFixed(0) + "% cash · levered, " + la.report_date : "",
      tip: "Baron Partners is a <b>levered</b>, non-diversified fund. Per the fact sheet it runs ~113% long "
        + "/ −13% cash: <b>$1 of your net capital controls ~$"
        + (la.total_assets_usd ? (la.total_assets_usd / la.net_assets_usd).toFixed(2) : "1.13")
        + " of long positions</b> (total assets " + usd(la.total_assets_usd) + " vs net assets "
        + usd(la.net_assets_usd) + ", " + la.report_date + "). This is why your SpaceX exposure per $1 "
        + "(net-assets basis, " + pct(la.spacex_weight_measured) + ") is higher than the fact sheet's 33% "
        + "(% of gross investments). All per-$1 figures here use the net-assets basis — i.e. per actual dollar invested. "
        + "<span class='conf'>Confidence: HIGH — totAssets/netAssets from NPORT-P, matches fact sheet.</span>",
      sources: [S_EDGAR, S_FACT] },

    { label: "SpaceX $ held by fund", value: usd(k.spacex_value_usd), cls: "spx",
      note: la.report_date + " · " + la.spacex_n_tranches + " tranches summed",
      tip: "Sum of valUSD across all " + la.spacex_n_tranches + " SpaceX holdings (common / preferred / "
        + "rounds) in the latest NPORT-P. SpaceX's legal name in the filing is "
        + "“Space Exploration Technologies”. "
        + "<span class='conf'>Confidence: HIGH — measured.</span>",
      sources: [S_EDGAR] },

    { label: "Reconstructed fund AUM", value: usd(k.total_nav_usd),
      note: ov ? "trued-up to reported " + ov.date + " + NAV drift" : "NAV × est. shares",
      tip: "Latest filed net assets = " + usd(la.net_assets_usd) + " (" + la.report_date + ", NPORT-P). "
        + (ov ? "No public holdings filing exists after that (next is 2026-06-30), so AUM is trued-up to a "
              + "reported figure of " + usd(ov.net_assets_usd) + " (" + ov.date + ", " + ov.source + "), "
              + "then drifted daily by NAV. "
            : "")
        + "<span class='conf'>Confidence: MED — post-filing AUM is a manually-sourced datapoint, not SEC.</span>",
      sources: ov ? [S_AUM, S_EDGAR, S_YAHOO] : [S_YAHOO, S_EDGAR] },

    { label: "BPTRX NAV / share (latest)", value: navTxt,
      note: lastNavPt ? "as of " + lastNavPt.date + " · measured close" : "",
      tip: "A mutual fund's daily closing price IS its NAV per share. Pulled from the Yahoo Finance "
        + "chart API (no key). This is the actual price basis you transact at. "
        + "<span class='conf'>Confidence: HIGH — measured.</span>",
      sources: [S_YAHOO] },

    { label: "Last private mark", value: usd(k.last_private_mark_usd),
      note: "SpaceX+xAI combined · " + markAge + " days old",
      tip: "On 2026-02-02 SpaceX merged with xAI; combined entity $1.25T ($1.0T SpaceX + $0.25T xAI). "
        + "Reconciles with Baron's 2026-03-31 filing mark of $526.59/share ($421 × 1.25). The fund's NAV "
        + "still carries SpaceX here — i.e. the <b>stale mark</b> ahead of the IPO. "
        + "<span class='conf'>Confidence: HIGH — dated primary news (Bloomberg/CNBC).</span>",
      sources: [S_MERGER, S_EDGAR] },

    { label: "Your exposure per $1 (entry)", value: "$" + (k.entry_weight || 0).toFixed(2), cls: "spx", hl: true,
      note: "bought " + k.entry_date + " · " + pct(k.entry_weight) + " of NAV",
      tip: "On your 2026-05-20 entry, SpaceX was " + pct(k.entry_weight) + " of fund NAV — so roughly "
        + "$" + (k.entry_weight || 0).toFixed(2) + " of every $1 you invested is SpaceX exposure, at the "
        + "stale $1.25T mark. "
        + "<span class='conf'>Confidence: MED — same basis as the reconstructed weight.</span>",
      sources: [S_EDGAR, S_YAHOO] },

    { label: "IF IPO @ $1.75T", value: pct(ipo175.spacex_weight, 0) + " / " + signPct(ipo175.nav_stepup_pct, 0),
      cls: "spx", small: true, note: "SpaceX weight / NAV step-up",
      tip: "Re-marking SpaceX $1.25T → $1.75T (×1.40): weight " + pct(k.spacex_weight) + " → "
        + pct(ipo175.spacex_weight) + ", per-share NAV step-up " + signPct(ipo175.nav_stepup_pct) + ". "
        + "$1.75T is the S-1 / press target, <b>not yet realized</b>. Adjust it live in the Scenario Lab below. "
        + "<span class='conf'>Confidence: scenario — forward, user-adjustable.</span>",
      sources: [S_IPO] },

    { label: "Days to projected IPO", value: dToIpo >= 0 ? dToIpo : "traded",
      note: ipo.ticker + " · " + ipo.first_trade_date,
      tip: "Calendar days from today to SpaceX's projected first trading day (" + ipo.first_trade_date
        + ", Nasdaq: " + ipo.ticker + "). Dates are S-1 / press targets and may move; re-verify. "
        + "<span class='conf'>Confidence: MED — announced target, not final.</span>",
      sources: [S_IPO] },
  ];

  document.getElementById("kpis").innerHTML = cards.map((c) => {
    const tip = c.tip ? `<span class="info">i<span class="tip">${c.tip}</span></span>` : "";
    const src = (c.sources || []).length
      ? `<div class="src">${c.sources.map((s) =>
          `<a href="${s.url}" target="_blank" rel="noopener">${s.label} ↗</a>`).join("")}</div>` : "";
    return `<div class="kpi ${c.hl ? "hl" : ""}">
       ${tip}
       <div class="label">${c.label}</div>
       <div class="value ${c.cls || ""} ${c.small ? "small" : ""}">${c.value}</div>
       <div class="note">${c.note}</div>
       ${src}
     </div>`;
  }).join("");
}

/* ------------------------- main weight chart --------------------------- */
function renderWeightChart() {
  const s = DATA.series;
  const x = s.map((p) => p.date);
  const y = s.map((p) => p.spacex_weight);

  // measured anchor markers
  const anchorDates = new Set(DATA.anchors.map((a) => a.report_date));
  const ax = [], ay = [], atext = [];
  s.forEach((p) => {
    if (p.source === "measured" && p.spacex_weight != null) {
      ax.push(p.date); ay.push(p.spacex_weight);
      atext.push("Filed " + p.date + "<br>" + pct(p.spacex_weight, 1) + " of net assets");
    }
  });

  const reconLine = {
    x, y, type: "scattergl", mode: "lines", name: "Reconstructed (interpolated)",
    line: { color: SPX, width: 1.6, dash: "dot" },
    hovertemplate: "%{x}<br>est. weight %{y:.1%}<extra></extra>",
  };
  const anchorMarkers = {
    x: ax, y: ay, type: "scattergl", mode: "markers", name: "Measured filing (NPORT-P)",
    marker: { color: SPX, size: 7, line: { color: "#fff", width: 0.7 } },
    text: atext, hovertemplate: "%{text}<extra></extra>",
  };
  // reported-AUM true-up point(s): not SEC — distinct hollow amber diamond
  const ovr = DATA.aum_overrides || [];
  const ovMarkers = {
    x: ovr.map((o) => o.date), y: ovr.map((o) => o.spacex_weight),
    type: "scatter", mode: "markers", name: "Reported-AUM true-up (not SEC)",
    marker: { color: "#d29922", symbol: "diamond-open", size: 10, line: { width: 1.6 } },
    hovertemplate: "%{x}<br>reported-AUM weight %{y:.1%}<br>(SpaceX $ carried, AUM sourced)<extra></extra>",
  };

  const shapes = [], annotations = [];
  // low-confidence era shading
  DATA.density_eras.forEach((e) => {
    if (e.confidence === "low") {
      shapes.push({ type: "rect", xref: "x", yref: "paper",
        x0: e.start, x1: e.end || DATA.meta.last_data_day, y0: 0, y1: 1,
        fillcolor: "rgba(110,118,129,0.12)", line: { width: 0 }, layer: "below" });
      annotations.push({ x: e.start, y: 1, yref: "paper", text: "soft estimate",
        showarrow: false, font: { color: LOW, size: 10 }, xanchor: "left", yanchor: "top" });
    }
  });
  // event lines
  const kindColor = { init: MUTED, mark: ACC, corporate: "#bb86fc", filing: GOOD, ipo: SPX, lockup: "#d29922" };
  DATA.events.forEach((ev, i) => {
    shapes.push({ type: "line", xref: "x", yref: "paper", x0: ev.date, x1: ev.date,
      y0: 0, y1: 1, line: { color: kindColor[ev.kind] || MUTED, width: 1, dash: "dash" } });
    annotations.push({ x: ev.date, y: (i % 2 ? 0.93 : 0.86), yref: "paper", xref: "x",
      text: ev.label, showarrow: false, font: { color: kindColor[ev.kind] || MUTED, size: 9 },
      textangle: 0, xanchor: "left", bgcolor: "rgba(14,17,23,0.7)" });
  });

  const layout = baseLayout({
    shapes, annotations,
    yaxis: { title: "SpaceX % of fund", tickformat: ".0%", gridcolor: GRID, zeroline: false,
             color: TEXT, rangemode: "tozero" },
    xaxis: {
      gridcolor: GRID, color: TEXT,
      rangeselector: {
        buttons: [
          { count: 6, label: "6M", step: "month", stepmode: "backward" },
          { count: 1, label: "1Y", step: "year", stepmode: "backward" },
          { count: 5, label: "5Y", step: "year", stepmode: "backward" },
          { step: "all", label: "All" },
        ],
        bgcolor: "#1c2330", activecolor: "#2f4a6b", font: { color: TEXT }, x: 0, y: 1.12,
      },
      rangeslider: { visible: true, bgcolor: "#10141b", thickness: 0.07 },
      type: "date",
    },
    legend: { orientation: "h", y: 1.16, x: 0.18, font: { color: TEXT } },
    margin: { t: 70, r: 16, b: 30, l: 56 },
  });
  // default view: last ~2 years (decision-relevant, not swamped by sparse era)
  const last = DATA.meta.last_data_day;
  const start2y = new Date(Date.parse(last) - 730 * 86400000).toISOString().slice(0, 10);
  layout.xaxis.range = [start2y, last];

  Plotly.newPlot("chart-weight", [reconLine, anchorMarkers, ovMarkers], layout, plotConfig());
}

/* ----------------------------- AUM chart ------------------------------- */
function renderAumChart() {
  const s = DATA.series.filter((p) => p.total_nav_usd != null);
  const line = {
    x: s.map((p) => p.date), y: s.map((p) => p.total_nav_usd / 1e9),
    type: "scattergl", mode: "lines", name: "Reconstructed AUM",
    line: { color: ACC, width: 1.4 },
    hovertemplate: "%{x}<br>AUM $%{y:.2f}B<extra></extra>",
  };
  const a = DATA.anchors;
  const diamonds = {
    x: a.map((d) => d.report_date), y: a.map((d) => d.net_assets_usd / 1e9),
    type: "scatter", mode: "markers", name: "Filed net assets (NPORT-P)",
    marker: { color: GOOD, symbol: "diamond", size: 6 },
    hovertemplate: "%{x}<br>filed net assets $%{y:.2f}B<extra></extra>",
  };
  const ovr = DATA.aum_overrides || [];
  const ovDiamonds = {
    x: ovr.map((o) => o.date), y: ovr.map((o) => o.net_assets_usd / 1e9),
    type: "scatter", mode: "markers", name: "Reported AUM (not SEC)",
    marker: { color: "#d29922", symbol: "diamond-open", size: 9, line: { width: 1.6 } },
    hovertemplate: "%{x}<br>reported AUM $%{y:.2f}B (sourced, post-filing)<extra></extra>",
  };
  Plotly.newPlot("chart-aum", [line, diamonds, ovDiamonds], baseLayout({
    yaxis: { title: "USD (billions)", tickprefix: "$", ticksuffix: "B", tickformat: ".0f", gridcolor: GRID, color: TEXT, rangemode: "tozero" },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    legend: { orientation: "h", y: 1.1, font: { color: TEXT } }, margin: { t: 30, r: 12, b: 30, l: 52 },
  }), plotConfig());
}

/* ----------------------------- mark chart ------------------------------ */
function renderMarkChart() {
  const s = DATA.series.filter((p) => p.spacex_value_usd != null);
  const step = {
    x: s.map((p) => p.date), y: s.map((p) => p.spacex_value_usd / 1e9),
    type: "scattergl", mode: "lines", name: "SpaceX $ held",
    line: { color: SPX, width: 1.6, shape: "hv" },
    hovertemplate: "%{x}<br>SpaceX value $%{y:.2f}B<extra></extra>",
  };
  const a = DATA.anchors;
  const dots = {
    x: a.map((d) => d.report_date), y: a.map((d) => d.spacex_value_usd / 1e9),
    type: "scatter", mode: "markers", name: "Filing mark",
    marker: { color: SPX, size: 6 },
    hovertemplate: "%{x}<br>filed SpaceX value $%{y:.2f}B<extra></extra>",
  };
  Plotly.newPlot("chart-mark", [step, dots], baseLayout({
    yaxis: { title: "USD (billions)", tickprefix: "$", ticksuffix: "B", tickformat: ".1f", gridcolor: GRID, color: TEXT, rangemode: "tozero" },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    legend: { orientation: "h", y: 1.1, font: { color: TEXT } }, margin: { t: 30, r: 12, b: 30, l: 52 },
  }), plotConfig());
}

/* -------------------------- decomposition ------------------------------ */
function renderDecompChart() {
  const s = DATA.series.filter((p) => p.mark_contrib != null);
  let cm = 0, cd = 0, cf = 0;
  const x = [], mark = [], drift = [], flow = [];
  s.forEach((p) => {
    cm += p.mark_contrib; cd += p.drift_contrib; cf += p.flow_contrib;
    x.push(p.date); mark.push(cm); drift.push(cd); flow.push(cf);
  });
  const mk = (y, name, color) => ({ x, y, type: "scattergl", mode: "lines", name,
    line: { color, width: 1.5 }, hovertemplate: name + " %{y:+.1%}<extra></extra>" });
  Plotly.newPlot("chart-decomp", [
    mk(mark, "mark (re-marks)", SPX),
    mk(drift, "public-drift", ACC),
    mk(flow, "flow (creations/redemptions)", GOOD),
  ], baseLayout({
    yaxis: { title: "cumulative Δ weight", tickformat: "+.0%", gridcolor: GRID, color: TEXT, zeroline: true, zerolinecolor: GRID },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT } }, margin: { t: 36, r: 12, b: 30, l: 56 },
  }), plotConfig());
}

/* ----------------------------- residuals ------------------------------- */
function renderResidChart() {
  const r = DATA.residuals;
  const bar = {
    x: r.map((d) => d.report_date), y: r.map((d) => d.residual),
    type: "bar", name: "residual",
    marker: { color: r.map((d) => (Math.abs(d.residual) > 0.1 ? "#f85149" : d.residual >= 0 ? GOOD : ACC)) },
    hovertemplate: "%{x}<br>predicted %{customdata[0]:.1%} · measured %{customdata[1]:.1%}<br>residual %{y:+.1%}<extra></extra>",
    customdata: r.map((d) => [d.predicted_weight, d.measured_weight]),
  };
  Plotly.newPlot("chart-resid", [bar], baseLayout({
    yaxis: { title: "predicted − measured", tickformat: "+.0%", gridcolor: GRID, color: TEXT, zeroline: true, zerolinecolor: "#3a4459" },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    margin: { t: 16, r: 12, b: 36, l: 56 }, showlegend: false,
  }), plotConfig());
}

/* ------------------------------- tables -------------------------------- */
function pill(conf) { return `<span class="pill ${conf}">${conf}</span>`; }

function renderAnchorTable() {
  const tb = document.querySelector("#anchor-table tbody");
  tb.innerHTML = DATA.anchors.slice().reverse().map((a) =>
    `<tr>
       <td><a href="${a.edgar_url}" target="_blank" rel="noopener">${a.report_date}</a></td>
       <td>${usd(a.spacex_value_usd)}</td>
       <td>${pct(a.spacex_weight_measured)}</td>
       <td>${usd(a.net_assets_usd)}</td>
       <td>${a.spacex_n_tranches ?? "–"}</td>
       <td>${pill(a.confidence)}</td>
     </tr>`).join("");
}

function renderMarksTable() {
  const tb = document.querySelector("#marks-table tbody");
  tb.innerHTML = DATA.marks.map((mk) =>
    `<tr>
       <td>${mk.date}</td>
       <td>${usd(mk.whole_company_valuation_usd)}</td>
       <td>${mk.per_share_usd ? "$" + mk.per_share_usd : "–"}${mk.split_adjusted === "yes" ? " <span class='pill low'>split-adj</span>" : ""}</td>
       <td>${mk.basis}</td>
       <td>${pill(mk.confidence)}</td>
       <td><a href="${mk.source_url}" target="_blank" rel="noopener" title="${mk.source_desc}">source ↗</a></td>
     </tr>`).join("");
}

/* ---------------------------- gaps markdown ---------------------------- */
function renderGaps() {
  document.getElementById("gaps").innerHTML = miniMarkdown(DATA.data_gaps_md);
}
function miniMarkdown(md) {
  const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = md.split("\n"); let html = "", inList = false;
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "<a href='$2' target='_blank' rel='noopener'>$1</a>");
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  for (let raw of lines) {
    const line = raw.replace(/\r$/, "");
    if (/^---\s*$/.test(line)) { closeList(); html += "<hr>"; continue; }
    let m;
    if ((m = line.match(/^###\s+(.*)/))) { closeList(); html += "<h3>" + inline(m[1]) + "</h3>"; }
    else if ((m = line.match(/^##\s+(.*)/))) { closeList(); html += "<h2>" + inline(m[1]) + "</h2>"; }
    else if ((m = line.match(/^#\s+(.*)/))) { closeList(); html += "<h1>" + inline(m[1]) + "</h1>"; }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (!inList) { html += "<ul>"; inList = true; } html += "<li>" + inline(m[1]) + "</li>"; }
    else if (line.trim() === "") { closeList(); }
    else { closeList(); html += "<p>" + inline(line) + "</p>"; }
  }
  closeList();
  return html;
}

/* ---------------------------- scenario lab ----------------------------- */
function initScenario() {
  const base = DATA.scenario_base;
  const ipo = document.getElementById("ipo-slider");
  const flow = document.getElementById("flow-slider");
  const LO = 1.0e12, HI = 2.6e12;
  ipo.min = LO; ipo.max = HI; ipo.step = 0.05e12; ipo.value = base.current_valuation_usd;
  document.getElementById("ipo-val-lo").textContent = usd(LO);
  document.getElementById("ipo-val-hi").textContent = usd(HI);

  const update = () => {
    const ipoVal = +ipo.value, flowVal = +flow.value;
    document.getElementById("ipo-val-txt").textContent = usd(ipoVal) +
      (Math.abs(ipoVal - base.current_valuation_usd) < 1e9 ? " (status quo)" : "");
    document.getElementById("flow-txt").textContent = (flowVal >= 0 ? "+" : "") + usd(flowVal);
    const r = combined(base, ipoVal, flowVal);
    const cur = DATA.kpis.spacex_weight;
    const out = [
      { label: "SpaceX weight", value: pct(r.weight), cls: "spx",
        note: signPct(r.weight - cur) + " vs now (" + pct(cur) + ")" },
      { label: "Exposure per $1", value: "$" + (r.weight || 0).toFixed(2), cls: "spx",
        note: "of every dollar invested" },
      { label: "Implied NAV step-up", value: signPct(r.stepup),
        note: "from the IPO re-mark" },
      { label: "Implied fund AUM", value: usd(r.total),
        note: "SpaceX " + usd(r.spacex) + " + public " + usd(r.pub) },
    ];
    if (r.forced > 0) out.push({ label: "Forced SpaceX sale", value: usd(r.forced), cls: "spx",
      note: "redemptions exhausted the public book" });
    document.getElementById("scenario-out").innerHTML = out.map((c) =>
      `<div class="kpi"><div class="label">${c.label}</div>
        <div class="value ${c.cls || ""}">${c.value}</div>
        <div class="note">${c.note}</div></div>`).join("");

    const inflow = flowVal > 0;
    document.getElementById("scenario-explain").innerHTML =
      (Math.abs(ipoVal - base.current_valuation_usd) < 1e9
        ? "Holding SpaceX at the standing $1.25T private mark. "
        : `Re-marking SpaceX to ${usd(ipoVal)} (×${r ? (ipoVal / base.current_valuation_usd).toFixed(2) : ""}) lifts both NAV and weight. `) +
      (flowVal === 0 ? "No flow shock applied."
        : inflow
          ? `A ${usd(flowVal)} net <b>inflow</b> can't buy private SpaceX shares, so it lands in the public book and <b>dilutes</b> the SpaceX weight.`
          : `A ${usd(-flowVal)} net <b>redemption</b> is met by selling liquid public holdings first, so the SpaceX weight passively <b>rises</b>` +
            (r.forced > 0 ? " — and here it's large enough to force SpaceX sales." : "."));
  };

  ipo.oninput = update; flow.oninput = update;
  document.querySelectorAll(".btn-row button[data-ipo]").forEach((b) => {
    b.onclick = () => { ipo.value = b.dataset.ipo === "status" ? base.current_valuation_usd : +b.dataset.ipo; update(); };
  });
  document.getElementById("flow-reset").onclick = () => { flow.value = 0; update(); };
  update();
}

/* ------------------------------ plot utils ----------------------------- */
function baseLayout(over) {
  return Object.assign({
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID, font: { color: TEXT } },
    hovermode: "x unified",
  }, over);
}
function plotConfig() {
  return { responsive: true, displayModeBar: false, displaylogo: false,
           modeBarButtonsToRemove: ["lasso2d", "select2d"] };
}

boot();
