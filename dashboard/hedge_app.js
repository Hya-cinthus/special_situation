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
  renderKpis(); renderChart(); renderShortBreakdown(); renderLegs(); renderImpliedLev();
  const tog = document.getElementById("ex-remark-toggle");
  if (tog) tog.addEventListener("change", (e) => { EX_REMARK = e.target.checked; renderChart(); });
  const note = document.getElementById("pnl-note");
  const mm = (DATA.meta.manual_marks || []);
  if (note && mm.length) note.innerHTML = "⚠ Manual mark: " +
    mm.map((x) => `<b>${x.ticker} ${x.date}</b> = $${x.value.toFixed(2)} (${x.source})`).join("; ") +
    " — superseded automatically once the data provider posts the same date.";
  fetch("data/hedge_drift.json", { cache: "no-store" })
    .then((r) => r.ok ? r.json() : null).then((d) => { if (d) { DRIFT = d; renderDrift(); } })
    .catch(() => {});
  fetch("data/spacex_remark.json", { cache: "no-store" })
    .then((r) => r.ok ? r.json() : null).then((d) => { if (d) { REMARK = d; renderRemark(); } })
    .catch(() => {});
  fetch("data/basket_mismatch.json", { cache: "no-store" })
    .then((r) => r.ok ? r.json() : null).then((d) => { if (d) renderMismatch(d); })
    .catch(() => {});
}

function renderMismatch(MM) {
  if (!document.getElementById("mismatch-table")) return;
  const m = MM.meta, rows = MM.rows;
  const t = rows.find((r) => r.ticker === "TSLA") || rows[0];
  const relWt = Math.abs(t.diff_pp) / (t.our_weight * 100);   // 4.4pp on a 26% base = +17%
  document.getElementById("mismatch-intro").innerHTML =
    `Why does "Δ to full hedge" look so much bigger than the 4.4pp gap? Because it stacks <b>two</b> fixes. ` +
    `Walk Tesla: you hold <b>${t.our_shares.toLocaleString()}</b> → ` +
    `<b>(1) weight fix</b> <b style="color:${BAD}">+${t.delta_weight.toLocaleString()}</b> → ${t.target_shares.toLocaleString()} ` +
    `(the −${Math.abs(t.diff_pp)}pp gap is only 4.4 <i>points of the basket</i>, but that's <b>+${(relWt * 100).toFixed(0)}%</b> of ` +
    `Tesla's own 26% slice) → <b>(2) leverage fix</b> <b style="color:${BAD}">+${t.delta_leverage.toLocaleString()}</b> ` +
    `(scale the whole basket ×${m.leverage_factor} to cover the <i>gross</i>/levered public book) → ` +
    `<b style="color:${SPX}">${t.perfect_full_shares.toLocaleString()}</b> (total Δ +${t.delta_full_shares.toLocaleString()}). ` +
    `So the big number = <b>+${(relWt * 100).toFixed(0)}% (weight) compounded with +${((m.leverage_factor - 1) * 100).toFixed(0)}% (leverage)</b>, not 4%. ` +
    `<span style="color:${MUTED}">Hover any column header for its source &amp; meaning.</span>`;
  const cards = [
    { label: "TSLA weight gap", value: t.diff_pp + "pp → +" + t.delta_weight.toLocaleString() + " sh", cls: "b",
      note: "4.4pp = +" + (relWt * 100).toFixed(0) + "% of TSLA's count (fund " + pct(t.fund_weight) + " vs you " + pct(t.our_weight) + ")" },
    { label: "TSLA leverage scale", value: "×" + m.leverage_factor + " → +" + t.delta_leverage.toLocaleString() + " sh", cls: "b",
      note: "whole basket up to cover gross (levered) public" },
    { label: "TSLA full hedge", value: t.perfect_full_shares.toLocaleString() + " sh", cls: "spx",
      note: "Δ +" + t.delta_full_shares.toLocaleString() + " = +" + t.delta_weight.toLocaleString() + " + +" + t.delta_leverage.toLocaleString() },
    { label: "Leverage slice un-hedged", value: usd(m.leverage_slice_usd), cls: "b",
      note: "short ≈ net public; gross needs ×" + m.leverage_factor },
  ];
  document.getElementById("mismatch-kpis").innerHTML = cards.map((c) =>
    `<div class="kpi"><div class="label">${c.label}</div>
      <div class="value" style="color:${c.cls === "b" ? BAD : c.cls === "spx" ? SPX : c.cls === "muted" ? MUTED : TEXT}">${c.value}</div>
      <div class="note">${c.note}</div></div>`).join("");
  // header with hover tooltip (native title)
  const TH = (label, tip) => tip
    ? `<th title="${tip}" style="border-bottom:1px dotted #5a6573;cursor:help">${label}</th>`
    : `<th>${label}</th>`;
  const head = "<tr>" +
    TH("Ticker", "") +
    TH("Fund wt<br>(target)", "Target weight = this name's market value ÷ total public common ($7.89B), 3/31 NPORT Portfolio of Investments (authoritative filed holdings). = what % of your short the name SHOULD be. Leverage does NOT enter — it scales the total, not the split.") +
    TH("Our<br>shares", "Your hedge book's FIXED short, entered 2026-05-20 and held constant since.") +
    TH("Our wt", "Your short value ÷ total short, valued at the SAME 3/31 prices — so the gap is purely the proportion choice, not price drift.") +
    TH("Gap<br>(pp / $)", "Our weight − fund weight. Negative = UNDER-shorted vs the fund. The $ = that gap × your total short.") +
    TH("①&nbsp;Δ weight", "STEP 1 (allocation): shares to add/trim to bring this name to the fund weight, at your CURRENT short total. For TSLA the −4.4pp gap is small in points but +17% of its own share count.") +
    TH("②&nbsp;Δ leverage", "STEP 2 (scale): multiply the (weight-fixed) basket by ×" + m.leverage_factor + " so it covers the GROSS/levered public book, not just the net one your short ≈ today. = the leverage slice.") +
    TH("Full target<br>shares", "After both fixes: target_shares × ×" + m.leverage_factor + ". The shares for a complete hedge.") +
    TH("Δ full<br>(①+②)", "Full target − your shares = Δ weight + Δ leverage. + = add; − = trim.") +
    "</tr>";
  const body = rows.map((r) => {
    const u = r.diff_pp < -0.2, o = r.diff_pp > 0.2;
    const col = u ? BAD : (o ? ACC : MUTED);
    const sg = (x) => (x > 0 ? "+" : "") + x.toLocaleString();
    const dF = r.delta_full_shares;
    return `<tr${r.ticker === "TSLA" ? ` style="background:rgba(248,81,73,0.08)"` : ""}>
      <td><b>${r.ticker}</b></td><td>${(r.fund_weight * 100).toFixed(1)}%</td>
      <td>${r.our_shares.toLocaleString()}</td><td>${(r.our_weight * 100).toFixed(1)}%</td>
      <td style="color:${col}"><b>${r.diff_pp > 0 ? "+" : ""}${r.diff_pp}pp</b> <span style="color:${MUTED}">${usd(r.diff_usd)}</span></td>
      <td style="color:${r.delta_weight >= 0 ? BAD : ACC}">${sg(r.delta_weight)}</td>
      <td style="color:${MUTED}">${sg(r.delta_leverage)}</td>
      <td style="color:${SPX}">${r.perfect_full_shares.toLocaleString()}</td>
      <td style="color:${dF >= 0 ? BAD : ACC}"><b>${sg(dF)}</b></td></tr>`;
  }).join("");
  document.getElementById("mismatch-table").innerHTML =
    `<table class="data"><thead>${head}</thead><tbody>${body}</tbody></table>`;
  document.getElementById("mismatch-src").innerHTML =
    `<b>Target source:</b> ${m.target_source}<br><b>Our short:</b> ${m.short_source}<br>` +
    `<b>Pricing:</b> ${m.pricing_note}<br><b>Scale (leverage):</b> ${m.scale_note}`;
}

let REMARK = null;

function renderRemark() {
  if (!document.getElementById("remark-table")) return;
  const m = REMARK.meta, o = m.observables, sc = REMARK.scenarios;
  const obs = document.getElementById("remark-obs");
  if (obs) obs.innerHTML =
    `Observed (6/4): BPTRX NAV <b>${o.bptrx_nav_prev}→${o.bptrx_nav_now}</b> (<b style="color:${GOOD}">+${(o.nav_return * 100).toFixed(1)}%</b>) · ` +
    `public basket <b>+${(o.public_basket_return * 100).toFixed(2)}%</b> · Total Assets <b>$${(o.total_assets_prev_usd / 1e9).toFixed(1)}B → $${(o.total_assets_now_usd / 1e9).toFixed(1)}B</b> · ` +
    `base val $${(m.base_valuation_usd / 1e12).toFixed(2)}T · IPO $${(m.ipo_valuation_usd / 1e12).toFixed(2)}T`;
  const rows = sc.map((s) => {
    let result;
    if (s.solved_for === "leverage")
      result = `implied leverage <b style="color:${BAD}">${s.implied_leverage.toFixed(2)}×</b>`;
    else
      result = `SpaceX <b>$${(s.spacex_value_usd / 1e9).toFixed(2)}B</b> → val <b style="color:${ACC}">$${(s.spacex_valuation_usd / 1e12).toFixed(2)}T</b> <span style="color:${MUTED}">(${(s.spacex_return * 100).toFixed(1)}%)</span>`;
    const vc = s.verdict === "impossible" ? BAD : GOOD;
    return `<tr>
      <td><b>${s.key}</b><br><span style="color:${MUTED};font-size:11px">${s.name}</span></td>
      <td style="font-size:12px">${s.fixed}</td>
      <td style="font-size:12px">${s.solved_for === "leverage" ? "solve leverage" : "solve SpaceX mark"}</td>
      <td>${result}<br><span style="color:${vc};font-size:11px">[${s.verdict}] ${s.note}</span></td>
    </tr>`;
  }).join("");
  document.getElementById("remark-table").innerHTML =
    `<table class="data"><thead><tr><th>Scenario</th><th>Fixed assumption</th><th>Solve for</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table>`;
  const con = document.getElementById("remark-conclusion");
  if (con) {
    const cf = m.confirmed;
    let html = "";
    if (cf) html =
      `<p style="border-left:3px solid ${GOOD};padding-left:10px"><b style="color:${GOOD}">✓ Confirmed (Baron S-1):</b> ` +
      `SpaceX 6/4 reprice <b>$${cf.per_share_old_split_adj} → $${cf.per_share_new}/share</b> ` +
      `(<b>+${(cf.per_share_remark_pct * 100).toFixed(1)}%</b>), holding <b>$3.89B → $${(cf.spacex_value_usd / 1e9).toFixed(2)}B</b>. ` +
      `The $${(cf.valuation_post_money_usd / 1e12).toFixed(2)}T whole-company figure is post-money — <b>do not</b> apply it to the holding (double-counts IPO dilution).</p>`;
    con.innerHTML = html + `<p><b>Conclusion:</b> ${m.conclusion}</p>`;
  }
  const disc = document.getElementById("remark-disc");
  if (disc) disc.textContent = m.disclaimer;
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
  renderPerfectHedge();
}

function renderPerfectHedge() {
  const el = document.getElementById("perfect-table");
  if (!el || !DRIFT.perfect_hedge) return;
  const ph = DRIFT.perfect_hedge;
  const dshort = (d) => d.slice(5);                 // MM-DD
  const lastI = ph.dates.length - 1;
  // summary line
  const sum = document.getElementById("perfect-summary");
  if (sum) sum.innerHTML =
    `As of <b>${ph.as_of}</b>, a perfect hedge is <b style="color:${BAD}">${pct(ph.scale_now - 1, true)}</b> ` +
    `bigger than your fixed short — you'd <b>add ~${ph.total_delta_shares.toLocaleString()} shares</b> in total ` +
    `across the ${ph.legs.length} names (every name scales by the same factor under the pro-rata assumption).`;
  // matrix: rows = ticker, columns = Current + each date's perfect shares + delta-to-add
  const head = `<tr><th>Ticker</th><th>Current<br>(fixed)</th>` +
    ph.dates.map((d, i) => `<th${i === lastI ? ` style="color:${TEXT}"` : ""}>${dshort(d)}</th>`).join("") +
    `<th>Δ to add<br>(as of ${dshort(ph.as_of)})</th></tr>`;
  const body = ph.legs.map((l) => {
    const cells = l.perfect_shares.map((s, i) =>
      `<td style="color:${i === lastI ? ACC : MUTED}">${s.toLocaleString()}</td>`).join("");
    return `<tr><td><b>${l.ticker}</b></td><td>${l.current_shares.toLocaleString()}</td>${cells}` +
      `<td style="color:${BAD}">+${l.delta_now.toLocaleString()}</td></tr>`;
  }).join("");
  el.innerHTML = `<table class="data"><thead>${head}</thead><tbody>${body}</tbody></table>`;
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

let EX_REMARK = false;   // toggle: strip the 6/4 SpaceX re-mark from long/total

function renderChart() {
  const s = DATA.series;
  const x = s.map((r) => r.date);
  const longKey = EX_REMARK ? "long_pnl_ex_remark" : "long_pnl";
  const totalKey = EX_REMARK ? "total_pnl_ex_remark" : "total_pnl";
  const mk = (key, name, color, width) => ({
    x, y: s.map((r) => r[key]), name, type: "scatter", mode: "lines+markers",
    line: { color, width: width || 2 }, marker: { size: 5 },
    hovertemplate: name + " %{y:($,.0f}<extra></extra>",
  });
  const suffix = EX_REMARK ? " — ex SpaceX re-mark" : "";
  Plotly.newPlot("chart", [
    mk(longKey, "Long (BPTIX)" + suffix, GOOD),
    mk("short_pnl", "Short (public holdings)", BAD),
    mk(totalKey, "Total (≈ SpaceX/private)" + suffix, SPX, 3),
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

function renderImpliedLev() {
  const el = document.getElementById("impl-lev-chart");
  if (!el) return;
  const s = DATA.series.filter((r) => r.implied_leverage != null);
  const x = s.map((r) => r.date);
  const La = DATA.meta.assumed_leverage;
  // KPIs
  const last = s[s.length - 1] || {};
  const cards = [
    { label: "Implied leverage (now)", value: last.implied_leverage.toFixed(4) + "×",
      cls: "spx", note: "leverage that would make the fixed short a PERFECT hedge" },
    { label: "Assumed leverage", value: La.toFixed(4) + "×",
      cls: "muted", note: "fund's actual gross÷net (3/31 NPORT)" },
    { label: "Gap (implied − assumed)", value: pct(last.implied_leverage - La, true),
      cls: "b", note: "implied < assumed → fund carries MORE public beta than the short → under-hedged" },
  ];
  document.getElementById("impl-lev-kpis").innerHTML = cards.map((c) =>
    `<div class="kpi"><div class="label">${c.label}</div>
      <div class="value" style="color:${c.cls === "spx" ? SPX : c.cls === "b" ? BAD : MUTED}">${c.value}</div>
      <div class="note">${c.note}</div></div>`).join("");
  Plotly.newPlot("impl-lev-chart", [
    { x, y: s.map((r) => r.implied_leverage), name: "Implied perfect-hedge leverage",
      type: "scatter", mode: "lines+markers", line: { color: SPX, width: 2.5 }, marker: { size: 5 },
      hovertemplate: "implied %{y:.4f}×<extra></extra>" },
    { x, y: x.map(() => La), name: "Assumed leverage (" + La.toFixed(4) + "×)",
      type: "scatter", mode: "lines", line: { color: MUTED, width: 1.5, dash: "dash" },
      hovertemplate: "assumed " + La.toFixed(4) + "×<extra></extra>" },
    { x, y: x.map(() => 1.0), name: "Unlevered (1.00×)",
      type: "scatter", mode: "lines", line: { color: GRID, width: 1, dash: "dot" }, hoverinfo: "skip" },
  ], {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "Leverage (×)", gridcolor: GRID, color: TEXT, zeroline: false },
    legend: { orientation: "h", y: 1.14, font: { color: TEXT } },
    margin: { t: 40, r: 16, b: 36, l: 52 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderShortBreakdown() {
  const el = document.getElementById("short-chart");
  if (!el || !DATA.short_legs_pnl) return;
  const dates = DATA.series.map((r) => r.date);
  const legs = DATA.short_legs_pnl;          // already alphabetical by ticker
  const n = legs.length;
  // one line per short ticker; distinct hues; traces in alphabetical order so the
  // unified hover lists them A->Z (legend traceorder 'normal' keeps that order).
  const traces = legs.map((lg, i) => {
    const cum = lg.pnl;
    // true daily P&L = change vs the prior listed (trading) day; entry day = 0
    const daily = cum.map((v, j) => (j === 0 ? 0 : v - cum[j - 1]));
    return {
      x: dates, y: cum, customdata: daily, name: lg.ticker, type: "scatter", mode: "lines",
      line: { width: 1.4, color: `hsl(${Math.round((360 * i) / n)},65%,62%)` },
      hovertemplate: lg.ticker + "  day %{customdata:($,.0f} · cum %{y:($,.0f}<extra></extra>",
    };
  });
  Plotly.newPlot("short-chart", traces, {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID, font: { size: 10 } },
    shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: GRID, width: 1 } }],
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "Short-leg P&L ($)", gridcolor: GRID, color: TEXT, tickformat: "$,.0s", zeroline: false },
    legend: { traceorder: "normal", orientation: "h", y: -0.16, font: { color: TEXT, size: 9 } },
    margin: { t: 16, r: 16, b: 70, l: 64 },
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
