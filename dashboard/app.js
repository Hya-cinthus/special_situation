"use strict";

/* -------------------------------------------------------------------------
 * Multi-situation shell. Add a new situation by appending to this list and
 * dropping its JSON in data/. No other frontend change needed.
 * ---------------------------------------------------------------------- */
const SITUATIONS = [
  { key: "spacex_baron", file: "data/spacex_baron.json" },
];

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7", LOW = "#6e7681";
const WARN = "#d29922", BAD = "#f85149";
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
  if (document.getElementById("content")) {
    await load(SITUATIONS[0].file);   // full BPTIX situation page (index.html): main + cards
  } else {
    loadCards();                       // monitor / studies page: just the cards it contains
  }
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
  renderMarkChain();
  renderWeightAssumptions();
  renderMtmCheck();
  renderWeightChart();
  renderAumChart();
  renderMarkChart();
  renderDecompChart();
  renderResidChart();
  renderAnchorTable();
  renderMarksTable();
  renderGaps();
  initScenario();
  loadCards();
}

/* Sub-card fetches. Each render() guards its own container, so a card only paints
 * on the page that actually has its <section> — index.html keeps the structural
 * cards, monitor.html (daily & studies) keeps the rest. Runs on both pages. */
function loadCards() {
  const card = (file, fn) => fetch(file, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null)).then((d) => { if (d) fn(d); }).catch(() => {});
  card("data/nport_holdings.json", renderRecon);
  card("data/baron_spacex_funds.json", renderBaronFunds);
  card("data/spacex_position.json", renderSpacexPosition);
  card("data/ronb_crossref.json", renderRonb);
  card("data/ipo_day_recon.json", renderIpoDay);
  card("data/daily_nav_log.json", renderDailyLog);
  card("data/recalibration.json", renderRecalib);
  card("data/long_replication.json", renderLongRep);
}

/* ---- Daily NAV-estimate log: per-basket predicted NAV vs actual ---- */
let DAILYLOG_DATA = null, DAILYLOG_VIEW = "revised";   // "revised" | "asof"
function renderDailyLog(d) {
  DAILYLOG_DATA = d;
  const note = document.getElementById("dailylog-note");
  if (note) note.innerHTML = d.meta.note + (d.meta.two_views_note ? "<br><b>Two views.</b> " + d.meta.two_views_note : "");
  const tg = document.getElementById("dailylog-toggle");
  if (tg) {
    const btn = (v, label) =>
      `<button data-v="${v}" style="background:${DAILYLOG_VIEW === v ? _rgba(SPX, 0.22) : "var(--panel-2)"};` +
      `color:${DAILYLOG_VIEW === v ? TEXT : MUTED};border:1px solid ${DAILYLOG_VIEW === v ? SPX : GRID};` +
      `border-radius:7px;padding:5px 12px;font-size:.8rem;cursor:pointer;margin-right:8px">${label}</button>`;
    tg.innerHTML = btn("revised", "Revised (current assumptions)") + btn("asof", "As-of (frozen, what we estimated then)");
    tg.querySelectorAll("button").forEach((b) => (b.onclick = () => { DAILYLOG_VIEW = b.dataset.v; renderDailyLog(DAILYLOG_DATA); }));
  }
  drawDailyLogTable();
  const src = document.getElementById("dailylog-src");
  if (src) src.innerHTML = "<span class='dim'>Cells = predicted BPTIX NAV under each weighting (green = closest to actual; small number = error vs actual). " + d.meta.disclaimer + "</span>";
}
/* SpaceX shares behind one BPTIX share = fund SpaceX shares / BPTIX shares out
 * (shares × NAV / AUM, end-of-day so a big SPCX move doesn't distort it).
 * Precomputed per row in the backend (revised) and backfilled into the frozen
 * vintage rows — read directly here (no recompute; that was the start/end bug). */
function _spxShPerBptix(r) {
  return r.spx_shares_per_bptix != null ? r.spx_shares_per_bptix : null;
}
function drawDailyLogTable() {
  const d = DAILYLOG_DATA, card = document.getElementById("dailylog-table");
  if (!d || !card) return;
  const ms = d.meta.methods, lbl = d.meta.method_labels;
  const rows = DAILYLOG_VIEW === "asof" ? (d.vintage_rows || []) : d.rows;
  const shTip = "SpaceX shares behind one BPTIX share = SpaceX weight × NAV ÷ SPCX price. SpaceX-side metric — " +
    "it does NOT depend on the basket-weighting columns (those only change the public return). Uses the " +
    "with-Friday-buy weight; the BPTIX page KPI uses disclosed 3/31 shares only (~0.577), the gap being the ~$262M IPO-day add.";
  const head = "<tr><th>Date</th><th>SPCX</th><th>SpaceX wt · lev</th><th title=\"" + shTip + "\">SpaceX sh / BPTIX sh ⓘ</th>" +
    ms.map((m) => `<th>${lbl[m]}</th>`).join("") + "<th>perfect-fit range</th><th>Actual NAV</th><th>best</th><th>what's new this day</th></tr>";
  const body = rows.slice().reverse().map((r) => {
    const cells = ms.map((m) => {
      const p = r.preds[m];
      if (!p) return `<td class="dim" title="this method didn't exist when this day was frozen">—</td>`;
      const isBest = r.best_method === m;
      const err = r.errors && r.errors[m] != null ? r.errors[m] : null;
      const errTxt = err != null ? `<br><span class="dim" style="font-size:10px">${err >= 0 ? "+" : ""}${err}</span>` : "";
      return `<td style="${isBest ? `background:${_rgba(GOOD, 0.16)};font-weight:700` : ""}">${p.pred_nav.toFixed(2)}${errTxt}</td>`;
    }).join("");
    const pf = r.perfect_fit_range ? `<span style="color:${SPX}">${r.perfect_fit_range[0].toFixed(2)} – ${r.perfect_fit_range[1].toFixed(2)}</span>` : "—";
    const act = r.actual_nav != null ? `<b style="color:${SPX}">${r.actual_nav.toFixed(2)}</b>` : `<span class="dim">est. only</span>`;
    const best = r.best_method ? lbl[r.best_method] : "—";
    const noteCell = r.note ? `<td style="white-space:normal;min-width:240px;max-width:340px;text-align:left;font-size:11px" class="dim">${r.note}</td>` : "<td></td>";
    const spxShVal = _spxShPerBptix(r);
    const spxSh = spxShVal != null ? `<td style="color:${SPX}">${spxShVal.toFixed(3)}</td>` : `<td class="dim">—</td>`;
    return `<tr><td><b>${r.date}</b></td><td>$${r.spcx} <span class="dim">(${r.spcx_ret_pct >= 0 ? "+" : ""}${r.spcx_ret_pct}%)</span></td>` +
      `<td>${r.spacex_weight_pct}% <span class="dim">L${(r.leverage || 1).toFixed(2)}</span></td>${spxSh}${cells}<td>${pf}</td><td>${act}</td><td class="dim">${best}</td>${noteCell}</tr>`;
  }).join("");
  card.innerHTML = `<table class="data">${head}<tbody>${body}</tbody></table>`;
}

/* ---- IPO-day reconciliation card (SpaceX first trade: marks vs AUM) ---- */
function renderIpoDay(d) {
  const card = document.getElementById("ipoday-card");
  if (!card) return;
  card.style.display = "";
  const g = d.growth, t = d.nav_test, ad = d.aum_decomp, sp = d.spcx, sv = d.spacex_value;
  const sd = (x) => (x >= 0 ? "+" : "") + x.toFixed(2) + "%";
  const mUSD = (x) => (x >= 0 ? "+" : "−") + "$" + Math.abs(x / 1e6).toFixed(0) + "M";

  document.getElementById("ipoday-title").innerHTML =
    `IPO day (${d.meta.date}): did BPTIX buy SpaceX at the IPO? — marks vs reported AUM`;
  document.getElementById("ipoday-intro").innerHTML =
    `SpaceX (SPCX) first traded ${d.meta.date}, closing <b>$${sp.close}</b> (<b>${sd(sp.return_pct)}</b> vs the $${sp.ipo_price} IPO price). ` +
    `Assuming the fund's SpaceX position is <b>unchanged</b> and <b>no leverage</b>, can marking everything to that close reproduce the reported <b>${usd(g.aum_reported)}</b> AUM — and would a new IPO buy even show up?`;

  const ssRows = (d.split_solve && d.split_solve.rows) || [];
  const buyVals = ssRows.map((r) => r.spacex_ipo_buy_usd);
  const buyMin = buyVals.length ? Math.min(...buyVals) : t.implied_buy_lo_usd;
  const buyMax = buyVals.length ? Math.max(...buyVals) : t.implied_buy_hi_usd;
  const kpi = (label, value, note, cls) =>
    `<div class="kpi"><span class="label">${label}</span><div class="value${cls ? " " + cls : ""}">${value}</div><div class="note">${note}</div></div>`;
  document.getElementById("ipoday-kpis").innerHTML =
    kpi("SPCX first close", "$" + sp.close, sd(sp.return_pct) + " vs $" + sp.ipo_price + " IPO", "spx") +
    kpi("SpaceX weight now", sv.weight_now_pct.toFixed(1) + "%", "was " + t.spacex_weight_start_pct + "% (at $135)", "spx") +
    kpi("Implied IPO add", buyMax <= 0 ? "none" : "≈ $0", "solve: " + mUSD(buyMin) + " to " + mUSD(buyMax)) +
    kpi("Net inflows (Fri)", usd(g.inflow_usd), "AUM growth beyond marks");

  document.getElementById("ipoday-growth").innerHTML =
    `<table class="data"><thead><tr><th>Measure</th><th>Calculation</th><th>Result</th><th>What it includes</th></tr></thead><tbody>` +
    `<tr><td><b>AUM growth</b></td><td>${(g.aum_reported / 1e9).toFixed(1)}B / ${(g.aum_prior / 1e9).toFixed(1)}B − 1</td>` +
    `<td style="color:${ACC}"><b>${sd(g.aum_growth_pct)}</b></td><td class="dim">includes new money</td></tr>` +
    `<tr><td><b>NAV / share growth</b></td><td>${g.nav_current} / ${g.nav_prior} − 1</td>` +
    `<td style="color:${SPX}"><b>${sd(g.nav_growth_pct)}</b></td><td class="dim">pure market return, NO new money</td></tr>` +
    `<tr style="font-weight:700;border-top:2px solid ${GRID}"><td>Difference</td><td>${sd(g.aum_growth_pct)} − ${sd(g.nav_growth_pct)}</td>` +
    `<td>${sd(g.inflow_pct)}</td><td>= net inflows <b>${usd(g.inflow_usd)}</b></td></tr></tbody></table>` +
    `<p style="margin-top:10px"><b>AUM change ${usd(ad.total_change_usd)} decomposes as:</b> SpaceX re-mark <b style="color:${SPX}">+${(ad.spacex_remark_usd / 1e9).toFixed(2)}B</b> ` +
    `+ public holdings +${(ad.public_gain_usd / 1e9).toFixed(2)}B + net inflows +${(ad.inflow_usd / 1e9).toFixed(2)}B. ` +
    `Marking the existing book to Friday's close (no new money) gives <b>${usd(ad.marked_no_inflow_usd)}</b> — only <b>${usd(ad.gap_vs_reported_usd)}</b> short of the reported ${usd(g.aum_reported)}. ` +
    `<span class="dim">That ${usd(ad.gap_vs_reported_usd)} shortfall is inflows, not a SpaceX buy.</span></p>`;

  const scen = d.buy_scenarios.map((s) =>
    `<tr><td>buy $${(s.usd / 1e9).toFixed(2)}B at $${sp.ipo_price}</td><td>+${s.extra_nav_pct}%</td><td>${sd(s.nav_would_be_pct)}</td></tr>`).join("");
  document.getElementById("ipoday-navtest").innerHTML =
    `<p>New shares bought at the $${sp.ipo_price} IPO that close at $${sp.close} gain ${sd(sp.return_pct)} <i>intraday</i> — so a real IPO buy would push per-share NAV <b>above</b> the no-add prediction. The prediction (position unchanged):</p>` +
    `<ul>` +
    `<li>SpaceX sleeve: ${t.spacex_weight_start_pct}% × ${sd(sp.return_pct)} = <b style="color:${SPX}">+${t.spacex_contribution_pct}%</b> &nbsp;(this alone is most of the day's NAV move)</li>` +
    `<li>Public sleeve: ${(100 - t.spacex_weight_start_pct).toFixed(2)}% × public return (${t.public_return_lo_pct}% to ${t.public_return_hi_pct}%) → +${(t.predicted_nav_lo_pct - t.spacex_contribution_pct).toFixed(2)}% to +${(t.predicted_nav_hi_pct - t.spacex_contribution_pct).toFixed(2)}%</li>` +
    `<li><b>Predicted NAV band: +${t.predicted_nav_lo_pct}% to +${t.predicted_nav_hi_pct}%</b> &nbsp;(band = fund 3/31→5/31 weight versions; 5/31 central +${t.predicted_nav_central_pct}%)</li>` +
    `<li><b style="color:${GOOD}">Actual NAV: ${sd(t.actual_nav_pct)}</b> — at/below the band ⇒ the implied SpaceX add solves <b>negative</b> ⇒ no IPO buy.</li>` +
    `</ul>` +
    `<p style="margin:8px 0 4px">What a real buy <i>would</i> have done to NAV:</p>` +
    `<table class="data"><thead><tr><th>Hypothetical IPO buy</th><th>extra NAV</th><th>NAV would be</th></tr></thead><tbody>${scen}` +
    `<tr style="font-weight:700;border-top:2px solid ${GRID}"><td>Actual NAV</td><td></td><td style="color:${GOOD}">${sd(t.actual_nav_pct)}</td></tr></tbody></table>` +
    `<p class="dim" style="margin-top:8px">Reverse-solving the actual NAV across the three fund-weight versions ⇒ implied SpaceX add <b>${mUSD(buyMin)} to ${mUSD(buyMax)}</b> — negative throughout, i.e. <b>no add</b> (you can't buy negative; the small shortfall is model noise — weight drift, cash in the sleeve, preferred-vs-common tracking). A $0.65B buy would have lifted NAV to +6.2% vs the actual ${sd(t.actual_nav_pct)}.</p>`;

  // ③ solve the split (X = SpaceX bought at IPO, B = neutral subscription)
  if (d.split_solve) {
    const ss = d.split_solve;
    const rows = ss.rows.map((r) =>
      `<tr${r.is_central ? ` style="background:${_rgba ? _rgba(SPX, 0.10) : "rgba(255,122,69,0.10)"}"` : ""}>` +
      `<td>${r.label} (r_pub ${r.r_pub_pct >= 0 ? "+" : ""}${r.r_pub_pct}%)${r.is_central ? " <span class='dim'>← freshest</span>" : ""}</td>` +
      `<td style="color:${r.spacex_ipo_buy_usd > 5e6 ? SPX : MUTED}"><b>${mUSD(r.spacex_ipo_buy_usd)}</b></td>` +
      `<td>${mUSD(r.neutral_inflow_usd)}</td><td class="dim">${mUSD(r.total_in_usd)}</td></tr>`).join("");
    document.getElementById("ipoday-split").innerHTML =
      `<p>Split the new money into <b>X</b> = SpaceX bought at the $${sp.ipo_price} IPO (gains ${sd(sp.return_pct)} intraday) ` +
      `+ <b>B</b> = neutral subscription priced at NAV (no intraday P&amp;L). Two equations:</p>` +
      `<ul style="font-family:monospace;font-size:12px;line-height:1.7">` +
      `<li><b>Eq1 (NAV):</b> +${g.nav_growth_pct}% = [SpaceX_end + Public_end + ${sp.return_pct}%·X] / ${(g.aum_prior / 1e9).toFixed(1)}B − 1 &nbsp;←&nbsp;<b>B drops out</b></li>` +
      `<li><b>Eq2 (AUM):</b> ${(g.aum_reported / 1e9).toFixed(1)}B = SpaceX_end + Public_end + (1+${sp.return_pct}%)·X + B</li>` +
      `</ul>` +
      `<p>Public return is <b>known</b> (market data × the fund's weights) → 2 equations, 2 unknowns (X, B). One row per disclosed weight version:</p>` +
      `<table class="data"><thead><tr><th>fund weight version</th><th>X — SpaceX at IPO</th><th>B — neutral new money</th><th>total in</th></tr></thead><tbody>${rows}</tbody></table>` +
      `<p class="dim" style="margin-top:8px">Total new cash <b>${usd(ss.total_inflow_usd)}</b> is pinned regardless of the version. <b>X is negative in all three</b> (${mUSD(buyMin)} to ${mUSD(buyMax)}) — i.e. <b>no SpaceX added</b> at the IPO; neutral subscriptions B absorb the inflow. 5/31 (freshest) is the central estimate; the 3/31→5/31 spread is the band. A large IPO buy is firmly ruled out.</p>`;
  }

  // ④ bound a buy at an unknown price
  if (d.bounds) {
    const b = d.bounds;
    const brows = b.rows.map((r) => {
      const mb = r.max_buy_usd == null ? "<b>unbounded</b> (cash only)" : mUSD(r.max_buy_usd);
      const col = r.max_buy_usd == null ? GOOD : (r.max_buy_usd < 0 ? BAD : SPX);
      return `<tr><td>$${r.price.toFixed(2)}</td><td>${r.ret_pct >= 0 ? "+" : ""}${r.ret_pct}%</td>` +
        `<td style="color:${col}">${mb}</td><td class="dim">${r.verdict}</td></tr>`;
    }).join("");
    document.getElementById("ipoday-bounds").innerHTML =
      `<p>Now drop the assumption that any buy was at the $${b.ipo_px} IPO price — suppose they bought SpaceX ` +
      `<b>in the market at an unknown price</b>, closing $${b.close_px}. The NAV pins the trade's <b>P&amp;L</b> ` +
      `(≈ ${mUSD(b.leftover_trading_pnl_usd)}, basically zero), <b>not its size</b>. Max buy consistent with the NAV, by price:</p>` +
      `<table class="data"><thead><tr><th>buy price</th><th>intraday return</th><th>max buy vs NAV</th><th>verdict</th></tr></thead><tbody>${brows}</tbody></table>` +
      `<p style="margin-top:8px"><b>The boundary:</b></p><ul>` +
      `<li><b style="color:${BAD}">Cheap / at-IPO buy → ruled out</b> (≈$0): any buy below the close gains intraday and would push NAV <i>above</i> the actual ${sd(t.actual_nav_pct)}.</li>` +
      `<li><b style="color:${GOOD}">At-the-close buy → invisible</b>: ~0 intraday P&amp;L, identical to a cash subscription. Bounded only by the ~${usd(b.cash_funded_max_usd)} of new cash (more if funded by selling public).</li>` +
      `<li><b>Above-the-close buy → large but unlikely</b>: only if they chased the intraday high.</li>` +
      `</ul>` +
      `<p class="dim" style="margin-top:6px"><b>Mechanics:</b> ${b.mechanics}</p>` +
      `<p style="margin-top:6px">${b.summary}</p>`;
  }

  // ⑤ all-SpaceX counter-test: implied execution price
  if (d.all_spacex) {
    const a = d.all_spacex, io = a.intraday;
    const arows = a.rows.map((r) =>
      `<tr><td>${r.label} (r_pub ${r.r_pub_pct >= 0 ? "+" : ""}${r.r_pub_pct}%)</td>` +
      `<td style="color:${r.above_intraday_high ? BAD : SPX}"><b>$${r.exec_price.toFixed(2)}</b></td>` +
      `<td>+${r.premium_to_close_pct}% vs close</td>` +
      `<td style="color:${r.above_intraday_high ? BAD : MUTED}">${r.above_intraday_high ? "above the day's high — impossible" : "within range"}</td></tr>`).join("");
    document.getElementById("ipoday-allspx").innerHTML =
      `<p>Flip it around: force <b>every new dollar to be SpaceX</b> (no neutral money, no selling). Cash spent = the ${usd(a.cash_spent_usd)} inflow (pinned). What average execution price matches <b>both</b> the NAV and the AUM?</p>` +
      (io ? `<p class="dim">SPCX on ${d.meta.date}: open $${io.open}, <b>high $${io.high}</b>, low $${io.low}, close $${io.close}.</p>` : "") +
      `<table class="data"><thead><tr><th>weight version</th><th>implied avg exec price</th><th>premium</th><th>plausible?</th></tr></thead><tbody>${arows}</tbody></table>` +
      `<p style="margin-top:8px">${a.summary}</p>`;
  }

  // ⑥ funding channels & leverage
  if (d.funding) {
    const f = d.funding;
    const frows = f.channels.map((c) => {
      const visible = /invisible/i.test(c.at_market_buy);
      return `<tr><td><b>${c.funding}</b></td>` +
        `<td style="color:${BAD}">${c.cheap_buy}</td>` +
        `<td style="color:${visible ? WARN : MUTED}">${c.at_market_buy}</td></tr>`;
    }).join("");
    const lev = f.hist_leverage;
    document.getElementById("ipoday-funding").innerHTML =
      `<p>Now add <b>leverage</b>, and use the fact that Baron <b>never sells</b> (positions keep rising). Any SpaceX add must be funded by <b>subscriptions or borrowing</b>, not by selling. How visible is each?</p>` +
      `<table class="data"><thead><tr><th>funding source</th><th>cheap / IPO-price buy</th><th>at-market buy</th></tr></thead><tbody>${frows}</tbody></table>` +
      `<p class="dim" style="margin-top:8px">Net AUM <b>${usd(f.net_aum_usd)}</b>; mandate allows borrowing up to 1/3 of gross → gross up to <b>${usd(f.gross_cap_usd)}</b> (1.5×), borrow up to <b>${usd(f.borrow_cap_usd)}</b>. Historical leverage: 3/31 ${lev["2026-03-31"]}× → 4/30 ${lev["2026-04-30"]}× → 5/31 <b>${lev["2026-05-31"]}× (net cash)</b>. Plenty of room to re-lever invisibly.</p>` +
      `<p style="margin-top:6px">${f.summary}</p>`;
  }

  // ⑦ buy-size × execution-price locus (interactive, weight-version toggle)
  if (d.price_locus && document.getElementById("ipoday-locus")) {
    const pl = d.price_locus, close = pl.close_px;
    const drawLocus = (vi) => {
      const v = pl.versions[vi], lo = v.leftover_usd;
      const xs = [], ys = [];
      for (let i = 0; i <= 140; i++) {
        const C = 0.15e9 * Math.pow(8e9 / 0.15e9, i / 140);   // log-spaced $0.15B→$8B
        xs.push(C / 1e9);
        ys.push(close / (1 + lo / C));
      }
      const cmin = v.min_plausible_buy_usd / 1e9;
      // per-point NAV math for the hover: buy P&L = C×(close/P−1) = leftover (constant);
      // actual NAV = SpaceX contrib + public contrib + buy contrib.
      const A0 = pl.aum_prior_usd, buyPnlM = lo / 1e6, buyPct = lo / A0 * 100;
      const spxC = pl.spx_contrib_pct, navA = pl.actual_nav_pct, pubC = navA - spxC - buyPct;
      // post-buy fund balance sheet for the hover (look-through + cash + leverage)
      const spx0v = pl.spx_value_at_close_usd, A1 = pl.net_aum_usd, navB = pl.nav_bptix, PUB = v.pub_value_usd;
      const curve = {
        x: xs, y: ys, type: "scatter", mode: "lines", name: "implied avg exec price",
        line: { color: SPX, width: 2.2 },
        customdata: xs.map((x, i) => {
          const C = x * 1e9, P = ys[i];
          const spxNew = spx0v + C * close / P, wNew = spxNew / A1;     // SpaceX $ + weight
          const totInv = spxNew + PUB, lev = totInv / A1, netCash = A1 - totInv;
          return [(close / P - 1) * 100, C * (close / P - 1) / 1e6, wNew * 100, wNew * navB / close,
                  spxNew / close / 1e6, spxNew / 1e9, lev, netCash / 1e9];
        }),
        hovertemplate:
          "<b>buy $%{x:.2f}B</b> at avg <b>$%{y:.2f}</b> (per-$ intraday %{customdata[0]:.1f}%)<br>" +
          "buy P&L $%{customdata[1]:.0f}M = <b>" + buyPct.toFixed(2) + "% of NAV</b> (leftover)<br>" +
          "NAV: +" + spxC.toFixed(2) + "%(SpX) + " + pubC.toFixed(2) + "%(pub) " +
          buyPct.toFixed(2) + "%(buy) = <b>+" + navA.toFixed(2) + "%</b><br>" +
          "──── fund after this buy ────<br>" +
          "SpaceX: <b>$%{customdata[5]:.2f}B</b> · %{customdata[4]:.1f}M sh @ $" + close.toFixed(2) + " mark<br>" +
          "weight: <b>%{customdata[2]:.1f}% of net</b> · %{customdata[3]:.3f} SpaceX sh / BPTIX sh<br>" +
          "Net AUM $" + (A1 / 1e9).toFixed(1) + "B · cash/(borrow) <b>$%{customdata[7]:+.2f}B</b> · leverage <b>%{customdata[6]:.3f}×</b><extra></extra>",
      };
      const cminMark = {
        x: [cmin], y: [pl.intraday_high], type: "scatter", mode: "markers",
        marker: { color: BAD, size: 8, symbol: "circle" },
        hovertemplate: "min buy ≥$" + cmin.toFixed(2) + "B (else price > high)<extra></extra>",
      };
      const order = pl.order_cap_usd / 1e9, levT = pl.lev_cap_thu_usd / 1e9, levF = pl.lev_cap_fri_usd / 1e9;
      const shapes = [
        // day's trading range band (physically achievable prices)
        { type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0: pl.intraday_low, y1: pl.intraday_high,
          fillcolor: "rgba(63,185,80,0.08)", line: { width: 0 }, layer: "below" },
        // FEASIBLE box: C in [cmin, $1B order] AND price in [close, high]
        { type: "rect", xref: "x", yref: "y", x0: cmin, x1: order, y0: close, y1: pl.intraday_high,
          fillcolor: "rgba(255,122,69,0.16)", line: { color: SPX, width: 1, dash: "dot" }, layer: "below" },
        hline(close, ACC), hline(pl.intraday_high, BAD), hline(pl.intraday_low, MUTED), hline(pl.ipo_px, MUTED),
        vline(order, WARN), vline(levT, MUTED), vline(levF, MUTED),
      ];
      const ann = (x, y, t, c, ax, ay) => ({ x: x, y: y, xref: "x", yref: "y", text: t, showarrow: false,
        font: { color: c, size: 10 }, xanchor: ax || "left", yanchor: ay || "bottom" });
      Plotly.newPlot("ipoday-locus", [curve, cminMark], baseLayout({
        xaxis: { title: "SpaceX bought into BPTIX ($B, log)", type: "log", gridcolor: GRID, color: TEXT, range: [Math.log10(0.15), Math.log10(8)] },
        yaxis: { title: "implied avg execution price", tickprefix: "$", range: [130, 205], gridcolor: GRID, color: TEXT },
        shapes: shapes, showlegend: false, margin: { t: 34, r: 14, b: 44, l: 56 },
        annotations: [
          { x: 0, y: 1.04, xref: "paper", yref: "paper", xanchor: "left", showarrow: false,
            text: "<b>Net AUM $" + (A1 / 1e9).toFixed(1) + "B</b> · SpaceX mark $" + close.toFixed(2) +
                  " · baseline leverage " + pl.lev_nobuy + "× (net cash $" + (pl.cash_nobuy_usd / 1e9).toFixed(2) + "B)",
            font: { color: TEXT, size: 11 } },
          ann(0.16, pl.intraday_high, "FEASIBLE: $" + cmin.toFixed(2) + "B–$" + order.toFixed(1) + "B @ ~$" + v.price_at_order_cap + "–$" + pl.intraday_high, SPX),
          ann(order, 134, " $1B order", WARN, "left"),
          ann(levT, 198, " 1.25× lev cap", MUTED, "left"),
          ann(0.155, pl.intraday_high + 1, "day's $" + pl.intraday_low + "–$" + pl.intraday_high + " range", GOOD),
          ann(0.155, close + 0.6, "close $" + close, ACC),
        ],
      }), plotConfig());
    };
    const tog = document.getElementById("ipoday-locus-toggle");
    tog.innerHTML = pl.versions.map((v, i) =>
      `<button data-vi="${i}" style="margin-right:6px;padding:3px 9px;background:${v.is_central ? "#1d3350" : PLOT_BG};` +
      `color:${TEXT};border:1px solid ${v.is_central ? "#3a5d86" : GRID};border-radius:5px;cursor:pointer;font-size:12px">` +
      `${v.label}${v.is_central ? " ★" : ""}</button>`).join("");
    tog.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      drawLocus(+b.dataset.vi);
      tog.querySelectorAll("button").forEach((x) => { x.style.background = PLOT_BG; x.style.borderColor = GRID; });
      b.style.background = "#1d3350"; b.style.borderColor = "#3a5d86";
    }));
    const ci = pl.versions.findIndex((v) => v.is_central);
    drawLocus(ci >= 0 ? ci : 0);
    const ln = document.getElementById("ipoday-locus-note");
    if (ln) ln.innerHTML = (pl.nav_identity ? "<b>" + pl.nav_identity + "</b><br>" : "") + pl.note +
      "<br><span style='color:" + MUTED + "'><b>Baseline (no buy):</b> SpaceX <b>" + usd(pl.spx_value_at_close_usd) +
      "</b> · " + (pl.spx_shares_total_nobuy / 1e6).toFixed(1) + "M sh @ $" + pl.mark_px + " mark · <b>" +
      pl.spx_weight_nobuy_pct + "% of net</b> · " + pl.spx_shares_per_bptix_nobuy + " SpaceX sh/BPTIX sh. " +
      "Net AUM <b>" + usd(pl.net_aum_usd) + "</b> · cash <b>" + usd(pl.cash_nobuy_usd) + "</b> · leverage <b>" +
      pl.lev_nobuy + "×</b> (net cash) · BPTIX NAV $" + pl.nav_bptix + ". Hover any point for the fund's balance sheet under that buy.</span>";
  }

  // ⑧ noise check: daily NAV-prediction error per basket, two views, Friday highlighted
  if (d.noise_compare && d.noise_compare.methods.length && document.getElementById("ipoday-noise")) {
    const nc = d.noise_compare, fri = nc.fri_date;
    let curVi = nc.methods.findIndex((m) => m.is_central); if (curVi < 0) curVi = 0;
    let curMode = "dev";   // "dev" = deviation bars; "cmp" = actual vs backed-out NAV
    const drawNoise = () => {
      const m = nc.methods[curVi], sd = m.daily_sd_pct, xs = m.series.map((p) => p.date);
      let traces, shapes, yTitle;
      if (curMode === "dev") {
        const ys = m.series.map((p) => p.err_pct);
        traces = [{ x: xs, y: ys, type: "bar", marker: { color: m.series.map((p) => (p.date === fri ? BAD : ACC)) },
          hovertemplate: "%{x}<br>deviation (actual − predicted) %{y:.3f}%<extra></extra>" }];
        const band = (k, c) => ({ type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1,
          y0: -k * sd, y1: k * sd, fillcolor: c, line: { width: 0 }, layer: "below" });
        shapes = [band(2, "rgba(139,151,167,0.10)"), band(1, "rgba(139,151,167,0.16)"), hline(0, MUTED)];
        yTitle = "daily deviation (actual − predicted)";
      } else {
        const act = m.series.map((p) => p.actual_pct), prd = m.series.map((p, i) => (p.actual_pct == null ? null : p.actual_pct - p.err_pct));
        traces = [
          { x: xs, y: act, type: "scatter", mode: "lines+markers", name: "actual NAV (ex re-mark)", line: { color: SPX, width: 2 }, marker: { size: 4 },
            hovertemplate: "%{x}<br>actual %{y:.3f}%<extra></extra>" },
          { x: xs, y: prd, type: "scatter", mode: "lines+markers", name: "basket backed-out NAV", line: { color: ACC, width: 2, dash: "dot" }, marker: { size: 4 },
            hovertemplate: "%{x}<br>predicted %{y:.3f}%<extra></extra>" },
        ];
        shapes = [hline(0, MUTED)];
        yTitle = "daily NAV contribution (ex re-mark)";
      }
      const friP = m.fri_pct || 0, friS = m.fri_sigma || 0;
      Plotly.newPlot("ipoday-noise", traces, baseLayout({
        xaxis: { type: "date", gridcolor: GRID, color: TEXT },
        yaxis: { title: yTitle, ticksuffix: "%", gridcolor: GRID, color: TEXT, zeroline: true, zerolinecolor: GRID },
        shapes: shapes, showlegend: curMode === "cmp",
        legend: { orientation: "h", y: 1.12, font: { color: TEXT, size: 10 } },
        margin: { t: 32, r: 14, b: 40, l: 58 },
        annotations: [
          { x: 0, y: 1.07, xref: "paper", yref: "paper", xanchor: "left", showarrow: false,
            text: "<b>" + m.label + "</b>: daily noise ±" + sd.toFixed(3) + "% (1σ) · <b>Fri " + friP.toFixed(3) + "% = " + friS.toFixed(1) + "σ</b> " + (Math.abs(friS) <= 2 ? "→ NORMAL" : "→ (overfit)"),
            font: { color: TEXT, size: 11 } },
          { x: fri, y: curMode === "dev" ? friP : (m.series.find((p) => p.date === fri) || {}).actual_pct, xref: "x", yref: "y",
            text: "Fri −0.25%", showarrow: true, arrowcolor: BAD, font: { color: BAD, size: 10 }, ax: 0, ay: -22 },
        ],
      }), plotConfig());
    };
    const styleBtns = (box, cur, attr) => box.querySelectorAll("button").forEach((b) => {
      const on = +b.dataset[attr] === cur; b.style.background = on ? "#1d3350" : PLOT_BG; b.style.borderColor = on ? "#3a5d86" : GRID; });
    const btn = (label, attr, val) =>
      `<button data-${attr}="${val}" style="margin-right:6px;padding:3px 9px;background:${PLOT_BG};color:${TEXT};border:1px solid ${GRID};border-radius:5px;cursor:pointer;font-size:12px">${label}</button>`;
    const vbox = document.getElementById("ipoday-noise-view");
    vbox.innerHTML = btn("show deviation", "vm", 0) + btn("actual vs backed-out NAV", "vm", 1);
    vbox.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      curMode = b.dataset.vm === "1" ? "cmp" : "dev"; drawNoise();
      vbox.querySelectorAll("button").forEach((x) => { const on = (x.dataset.vm === "1") === (curMode === "cmp"); x.style.background = on ? "#1d3350" : PLOT_BG; x.style.borderColor = on ? "#3a5d86" : GRID; });
    }));
    const tn = document.getElementById("ipoday-noise-toggle");
    tn.innerHTML = nc.methods.map((m, i) =>
      `<button data-ni="${i}" style="margin-right:6px;padding:3px 9px;background:${m.is_central ? "#1d3350" : PLOT_BG};` +
      `color:${TEXT};border:1px solid ${m.is_central ? "#3a5d86" : GRID};border-radius:5px;cursor:pointer;font-size:12px">${m.label}${m.is_central ? " ★" : ""}</button>`).join("");
    tn.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      curVi = +b.dataset.ni; drawNoise(); styleBtns(tn, curVi, "ni");
    }));
    // init view-toggle highlight (deviation active)
    vbox.querySelectorAll("button").forEach((x) => { const on = x.dataset.vm === "0"; x.style.background = on ? "#1d3350" : PLOT_BG; x.style.borderColor = on ? "#3a5d86" : GRID; });
    drawNoise();
    const nn = document.getElementById("ipoday-noise-note");
    if (nn) nn.innerHTML = nc.note;
  }

  // ⑨ Friday per-holding contribution (weight × return), sorted
  if (d.friday_stocks && d.friday_stocks.stocks.length && document.getElementById("ipoday-friday")) {
    const fb = d.friday_stocks, st = fb.stocks.slice().reverse();   // smallest contrib at bottom for barh
    const bars = {
      type: "bar", orientation: "h",
      y: st.map((s) => s.ticker), x: st.map((s) => s.contrib_pct),
      marker: { color: st.map((s) => (s.contrib_pct >= 0 ? GOOD : BAD)) },
      customdata: st.map((s) => [s.weight_pct, s.ret_pct]),
      hovertemplate: "%{y}: weight %{customdata[0]:.1f}% × return %{customdata[1]:+.2f}% = <b>%{x:+.3f}pp</b><extra></extra>",
    };
    Plotly.newPlot("ipoday-friday", [bars], baseLayout({
      xaxis: { title: "contribution to Friday's public-basket return (pp)", ticksuffix: "pp", gridcolor: GRID, color: TEXT, zeroline: true, zerolinecolor: MUTED },
      yaxis: { gridcolor: GRID, color: TEXT, tickfont: { size: 9 }, automargin: true },
      showlegend: false, margin: { t: 30, r: 14, b: 42, l: 52 },
      annotations: [{ x: 0, y: 1.04, xref: "paper", yref: "paper", xanchor: "left", showarrow: false,
        text: "<b>Sum = +" + fb.basket_ret_pct + "%</b> public-basket return · TSLA alone ≈ +0.41pp · biggest drag SHOP only −0.10pp",
        font: { color: TEXT, size: 11 } }],
    }), plotConfig());
    const fn = document.getElementById("ipoday-friday-note");
    if (fn) fn.innerHTML = fb.note;
  }

  // ⑩ best-fit basket: fitted vs disclosed weights + its daily hedging residual
  if (d.best_fit && document.getElementById("ipoday-bestfit-w")) {
    const bf = d.best_fit;
    const intro = document.getElementById("ipoday-bestfit-intro");
    if (intro) intro.innerHTML =
      `Free reweight of the 23 stocks fit to <b>5/20–6/11 only</b> (Friday held out). It hits the history ` +
      `<b>perfectly</b> (in-sample RMS ${bf.in_sample_rms_pct}%). With ${bf.n_obs} days vs ${bf.n_stocks} stocks the ` +
      `perfect fit is <b>non-unique</b> — across <b>~${bf.cluster.n} perfect fits</b> the Friday public-contribution ` +
      `prediction clusters at <b>+${bf.cluster.fri_mean}%</b> (range +${bf.cluster.fri_min}% to +${bf.cluster.fri_max}%), ` +
      `and the <b>actual +${bf.cluster.fri_actual}% falls inside</b>. They agree most on <b>TSLA (~24–28%)</b>; the mid/small ` +
      `names are interchangeable. Out-of-sample this fit's Friday residual is <b>${bf.friday_resid_pct}%</b> vs the disclosed ` +
      `basket's ${bf.disclosed_friday_resid_pct}% — reweighting absorbs ~half the −0.25%, no SpaceX buy needed.`;
    // weights: ALL stocks, disclosed vs ensemble-mean with the perfect-fit range as whiskers
    const ws = (bf.weight_stats || []).slice().reverse();   // ascending -> largest at top
    const wtraces = [
      { type: "bar", orientation: "h", name: "disclosed 5/31", y: ws.map((w) => w.ticker), x: ws.map((w) => w.disclosed_pct),
        marker: { color: MUTED }, hovertemplate: "%{y} disclosed %{x:.1f}%<extra></extra>" },
      { type: "bar", orientation: "h", name: "perfect-fit (mean ± range)", y: ws.map((w) => w.ticker), x: ws.map((w) => w.ens_mean_pct),
        marker: { color: SPX },
        error_x: { type: "data", symmetric: false, array: ws.map((w) => w.ens_max_pct - w.ens_mean_pct),
          arrayminus: ws.map((w) => w.ens_mean_pct - w.ens_min_pct), color: "rgba(255,122,69,0.5)", thickness: 1.2, width: 2 },
        customdata: ws.map((w) => [w.ens_min_pct, w.ens_max_pct, w.span_pp]),
        hovertemplate: "%{y} perfect-fit mean %{x:.1f}% · range [%{customdata[0]:.1f}, %{customdata[1]:.1f}] · span %{customdata[2]:.1f}pp<extra></extra>" },
    ];
    Plotly.newPlot("ipoday-bestfit-w", wtraces, baseLayout({
      barmode: "group", xaxis: { title: "weight (% of public book)", ticksuffix: "%", gridcolor: GRID, color: TEXT },
      yaxis: { gridcolor: GRID, color: TEXT, tickfont: { size: 9 }, automargin: true },
      legend: { orientation: "h", y: 1.03, font: { color: TEXT, size: 10 } }, margin: { t: 28, r: 12, b: 42, l: 52 },
    }), plotConfig());
    // cluster: interactive X/Y scatter — each dot is one perfect fit; toggle any axis
    const cl = bf.cluster, feats = bf.ensemble_features || [], opts = bf.axis_options || [];
    if (feats.length && opts.length) {
      const getV = (f, key) => (key.indexOf("w:") === 0 ? (f.w[key.slice(2)] || 0) : f[key]);
      const optLabel = (k) => ((opts.find((o) => o.key === k) || {}).label || k);
      let xKey = "dist_5_31", yKey = "friday_resid";
      const drawScatter = () => {
        const sc = [{ type: "scatter", mode: "markers", x: feats.map((f) => getV(f, xKey)), y: feats.map((f) => getV(f, yKey)),
          marker: { size: 9, color: feats.map((f) => f.friday_resid), colorscale: [[0, BAD], [0.5, MUTED], [1, GOOD]], cmid: 0,
            showscale: true, colorbar: { title: { text: "Fri resid %", side: "right" }, thickness: 10, len: 0.7, tickfont: { size: 9, color: TEXT } },
            line: { width: 0.5, color: "#0e1117" } },
          hovertemplate: optLabel(xKey) + " %{x:.2f}<br>" + optLabel(yKey) + " %{y:.2f}<extra></extra>" }];
        Plotly.newPlot("ipoday-bestfit-cluster", sc, baseLayout({
          xaxis: { title: optLabel(xKey), gridcolor: GRID, color: TEXT },
          yaxis: { title: optLabel(yKey), gridcolor: GRID, color: TEXT },
          shapes: yKey === "friday_resid" ? [hline(0, GOOD)] : [], showlegend: false, margin: { t: 16, r: 12, b: 46, l: 60 },
        }), plotConfig());
      };
      const sel = (id, cur) => `<select id="${id}" style="background:${PLOT_BG};color:${TEXT};border:1px solid ${GRID};border-radius:4px;padding:2px 6px;font-size:12px">` +
        opts.map((o) => `<option value="${o.key}"${o.key === cur ? " selected" : ""}>${o.label}</option>`).join("") + "</select>";
      const axbox = document.getElementById("ipoday-bestfit-axes");
      if (axbox) {
        axbox.innerHTML = `<span class="dim">Y:</span> ${sel("bf-y", yKey)} &nbsp; <span class="dim">X:</span> ${sel("bf-x", xKey)} ` +
          `&nbsp;<span class="dim">color = Friday residual (red = fit over-predicts → no buy; green = under → would need a buy). ${cl.n} fits, all perfect in-sample. TSLA pinned ~24–28%; ${(cl.free || []).slice(0, 4).join("/")}… are free.</span>`;
        document.getElementById("bf-y").addEventListener("change", (e) => { yKey = e.target.value; drawScatter(); });
        document.getElementById("bf-x").addEventListener("change", (e) => { xKey = e.target.value; drawScatter(); });
      }
      drawScatter();
    }
    const rs = bf.resid_series, fri = d.noise_compare ? d.noise_compare.fri_date : "2026-06-12";
    const rtr = { type: "bar", x: rs.map((p) => p.date), y: rs.map((p) => p.resid_pct),
      marker: { color: rs.map((p) => (p.date === fri ? BAD : GOOD)) },
      hovertemplate: "%{x}<br>residual %{y:.3f}%<extra></extra>" };
    Plotly.newPlot("ipoday-bestfit-r", [rtr], baseLayout({
      xaxis: { type: "date", gridcolor: GRID, color: TEXT },
      yaxis: { title: "residual", ticksuffix: "%", gridcolor: GRID, color: TEXT, zeroline: true, zerolinecolor: GRID },
      shapes: [hline(0, MUTED)], showlegend: false, margin: { t: 16, r: 12, b: 40, l: 56 },
      annotations: [{ x: fri, y: bf.friday_resid_pct, xref: "x", yref: "y", text: "Fri (held out) " + bf.friday_resid_pct + "%", showarrow: true, arrowcolor: BAD, font: { color: BAD, size: 10 }, ax: -30, ay: -16 }],
    }), plotConfig());
    const bn = document.getElementById("ipoday-bestfit-note");
    if (bn) bn.innerHTML = bf.note + " <b>Cluster:</b> across ~" + cl.n + " perfect fits, <b>" + (cl.pinned.join(", ") || "few") +
      "</b> are pinned (all fits agree) while <b>" + (cl.free.join(", ") || "several") + "</b> are free (collinear, interchangeable); TSLA clusters ~24–28%. The common thread is they all predict Friday's public contribution near +" + cl.fri_mean + "%, with the actual inside that band.";
  }

  document.getElementById("ipoday-conclusion").innerHTML = "<b>Bottom line.</b> " + d.conclusion;
  const src = document.getElementById("ipoday-source");
  if (src) src.innerHTML = "<span class='dim'>" + d.meta.assumptions + " " + d.meta.disclaimer + "</span>";
}

function hline(y, color) {
  return { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: y, y1: y,
           line: { color: color, width: 1, dash: "dot" } };
}
function vline(x, color) {
  return { type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1,
           line: { color: color, width: 1, dash: "dash" } };
}

/* ---- SpaceX holdings detail + full valuation reconciliation (bottom) ---- */
function renderRecon(NP) {
  const m = NP.meta, sx = NP.spacex, ct = NP.captable;
  const intro = document.getElementById("recon-intro");
  if (intro) intro.innerHTML =
    `Every figure comes from the fund's <b>3/31/2026 Portfolio of Investments</b> (footnote 3: restricted securities = ` +
    `<b>${usd(m.spacex_value)} = ${pct(m.spacex_pct_of_net, 2)} of net</b> — exactly SpaceX). ` +
    `Below connects it step by step: 3/31 holdings → 6/4 IPO re-mark → the $1.77T whole-company valuation.`;
  const spxNote = document.getElementById("recon-spx-note");
  if (spxNote) spxNote.innerHTML =
    `SpaceX is held across <b>5 share classes</b>: 2 common (Cl A/C) + 3 preferred (Cl H/I/Series N). ` +
    `Common @ $526.59/sh, preferred @ $5,265.90/sh (= 10× common); 3/31 total <b>${usd(sx.value_3_31)}</b>.`;

  // (1) SpaceX classes table
  const sRows = sx.classes.map((r) =>
    `<tr><td><b>${r.name.split(", ").slice(-1)[0]}</b></td><td>${r.kind === "common" ? "common" : "preferred"}</td>
      <td>${r.shares.toLocaleString()}</td><td>$${r.px_per_share.toLocaleString()}</td>
      <td>${usd(r.value)}</td><td style="color:${SPX}">${usd(r.value_remark)}</td></tr>`).join("");
  document.getElementById("recon-spacex").innerHTML =
    `<table class="data"><thead><tr><th>Class</th><th>Type</th><th>Shares (3/31)</th><th>$/share (3/31)</th>
      <th>Value (3/31)</th><th>After 6/4 re-mark</th></tr></thead><tbody>${sRows}
      <tr style="font-weight:700;border-top:2px solid ${GRID}"><td>Total</td><td></td>
      <td>${sx.total_shares_3_31.toLocaleString()}</td><td></td>
      <td>${usd(sx.value_3_31)}</td><td style="color:${SPX}">${usd(sx.value_remark_6_4)}</td></tr></tbody></table>`;

  // (2) re-mark explanation
  document.getElementById("recon-remark").innerHTML =
    `<p>Baron S-1: after the <b>5-for-1 split</b> of SpaceX common (effective 5/4), the common re-marks on 6/4 to the IPO ` +
    `price <b>$${ct.ipo_common_px}</b>; preferred does <b>not</b> split and re-marks to <b>$${ct.ipo_preferred_px.toLocaleString()}</b> ` +
    `(= ${ct.conversion_ratio}× common, i.e. 1 preferred converts to ${ct.conversion_ratio} common).</p>` +
    `<ul>` +
    `<li>Common: ${usd(sx.value_common_3_31)} × (135/105.32) = <b>${usd(sx.classes.filter(c => c.kind === "common").reduce((a, c) => a + c.value_remark, 0))}</b></li>` +
    `<li>Preferred: ${usd(sx.value_preferred_3_31)} × (6,750/5,265.9) = <b>${usd(sx.classes.filter(c => c.kind === "preferred").reduce((a, c) => a + c.value_remark, 0))}</b></li>` +
    `<li><b>Both ×${sx.remark_factor.toFixed(4)} (+${((sx.remark_factor - 1) * 100).toFixed(1)}%)</b> → SpaceX holding ${usd(sx.value_3_31)} → <b style="color:${SPX}">${usd(sx.value_remark_6_4)}</b></li>` +
    `</ul><p class="dim">This +28.2% exactly explains the +6.6% jump in BPTIX NAV on 6/4.</p>`;

  // (3) cap-table tie-out: ONE additive bridge ($1.25T -> $1.77T) + source breakdown
  const dl = ct.dilution, M = (x) => (x / 1e6).toFixed(1) + "M";
  const dlt = (x) => x == null ? "" : (x === 0 ? "—" : (x > 0 ? "+" : "") + x.toLocaleString());
  const valT = (x) => "$" + (x / 1e12).toFixed(3) + "T";
  const tag = (t) => { const c = { reported: GOOD, derived: WARN, residual: BAD }[t] || MUTED;
    return `<span style="color:${c};font-size:10px;font-weight:700">[${(t || "").toUpperCase()}]</span>`; };
  // Table A — single running share count, all post-split common; each step sourced
  const aRows = dl.valuation_bridge.map((s, i) => {
    const last = i === dl.valuation_bridge.length - 1, head = i === 0 || last;
    const col = s.delta === 0 ? MUTED : (s.delta > 0 ? ACC : TEXT);
    return `<tr${head ? ` style="font-weight:700;border-top:2px solid ${GRID}"` : ""}>
      <td>${s.label}</td><td>${s.shares.toLocaleString()}</td>
      <td style="color:${col}">${dlt(s.delta)}</td><td>$${s.price}</td>
      <td style="color:${last ? SPX : TEXT}">${valT(s.valuation)}</td></tr>
      <tr><td colspan="5" class="dim" style="font-size:11px;padding-top:0">${tag(s.src_type)} ${s.source}</td></tr>`;
  }).join("");
  // Table B — source of the 12.52B pro-forma, with a RUNNING count + source per line
  const sb = dl.source_breakdown;
  const bRows = sb.map((r, i) => {
    const head = r.delta === null || i === sb.length - 1;
    return `<tr${head ? ` style="font-weight:700;border-top:2px solid ${GRID}"` : ""}>
      <td>${r.label}</td><td style="color:${r.delta && r.delta > 0 ? ACC : TEXT}">${r.delta === null ? "" : dlt(r.delta)}</td>
      <td>${r.cumulative.toLocaleString()}</td></tr>
      <tr><td colspan="3" class="dim" style="font-size:11px;padding-top:0">${tag(r.src_type)} ${r.source}</td></tr>`;
  }).join("");
  document.getElementById("recon-captable").innerHTML =
    `<p>The whole-company value rose <b>+41.6% ($1.25T→$1.77T)</b> but the per-share value rose only <b>+28.2%</b> — the gap is <b>more shares</b>. ` +
    `Here is one running share count (all post-split common), from the $1.25T mark to the $1.77T IPO. ` +
    `Each step is tagged ${tag("reported")} (in a filing), ${tag("derived")} (computed from reported figures), or ${tag("residual")} (a reconciliation plug):</p>` +
    `<table class="data"><thead><tr><th>Step</th><th>Shares (running)</th><th>Δ shares</th><th>$/sh</th><th>Valuation</th></tr></thead><tbody>${aRows}</tbody></table>` +
    `<p style="margin:14px 0 4px"><b>Where the 12.52B pro-forma common comes from</b> (the "True-up" row, broken out as its own running count — incl. the exact xAI figure):</p>` +
    `<table class="data"><thead><tr><th>Component</th><th>Δ shares</th><th>Running (post-split)</th></tr></thead><tbody>${bRows}</tbody></table>` +
    `<p class="dim" style="margin-top:8px"><b>Is Baron diluted?</b> Mostly no. Preferred conversion was already inside the $1.25T value (just reclassified to common); the IPO raise brings in matching $75B cash; the xAI merger added xAI's value. Baron's per-share value rose the full <b>+28.2%</b> on both its common and preferred (the "price re-mark" row — no new shares). The only genuinely dilutive piece is Musk's milestone grants (${M(dl.musk_perf_classB)} perf + ${M(dl.musk_options_classB)} option Class B), which vest only on market-cap / Mars milestones.</p>`;

  // (4) net/gross/leverage
  document.getElementById("recon-leverage").innerHTML =
    `<ul>` +
    `<li>Public holdings ${usd(m.public_value)} + SpaceX ${usd(m.spacex_value)} = <b>Total Investments ${usd(m.total_investments)}</b> (${(m.leverage * 100).toFixed(2)}% of net)</li>` +
    `<li>− liabilities net of cash ${usd(m.liabilities_less_cash)} (−${((m.leverage - 1) * 100).toFixed(2)}%) = <b>Net Assets ${usd(m.net_assets)}</b></li>` +
    `<li>So <b>leverage = Total Investments / Net = ${m.leverage.toFixed(4)}</b>. Morningstar "Total Assets" reports <b>Net</b> (confirmed by the 5/31 disclosure of SpaceX 23.2%); gross = net × ${m.leverage.toFixed(4)}.</li>` +
    `</ul>`;

  // (5) full holdings
  const cls = (s) => ({ "Common": "Common", "Private Common": "SpaceX common", "Private Preferred": "SpaceX preferred",
    "Private Convertible Preferred": "Conv. preferred" }[s] || s);
  const hRows = NP.holdings.map((r) =>
    `<tr><td>${cls(r.section)}</td><td>${r.group}</td><td>${r.name}</td>
      <td>${r.shares.toLocaleString()}</td><td>${usd(r.cost)}</td><td>${usd(r.value)}</td></tr>`).join("");
  document.getElementById("recon-holdings").innerHTML =
    `<table class="data"><thead><tr><th>Class</th><th>Sector</th><th>Holding</th><th>Shares</th><th>Cost</th><th>Value</th></tr></thead>` +
    `<tbody>${hRows}<tr style="font-weight:700;border-top:2px solid ${GRID}"><td colspan="5">Total Investments</td>` +
    `<td>${usd(NP.totals.total_value)}</td></tr></tbody></table>`;

  const src = document.getElementById("recon-source");
  if (src) src.innerHTML = "Source: " + m.source;
}

/* ---- SpaceX across the Baron fund family + IPO allocation (bottom) ---- */
const BF_PAL = ["#ff7a45", "#4da3ff", "#3fb950", "#d29922", "#a371f7", "#f778ba"];
function _rgba(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
function _cTag(level) {
  const c = { CONFIRMED: GOOD, MEASURED: GOOD, REPORTED: ACC, ESTIMATED: WARN,
              RUMORED: WARN, "NOT FOUND": BAD, UNDISCLOSED: BAD }[level] || MUTED;
  return `<span style="color:${c};font-size:10px;font-weight:700">[${level}]</span>`;
}
function renderBaronFunds(d) {
  const F = d.funds, fam = d.family_by_quarter, L = d.latest, fw = d.firm_wide,
        ipo = d.ipo, ord = d.baron_order, al = d.ipo_allocation;
  const famTot = L.total_spacex_usd, bpPub = L.baron_partners_share_pct;

  // intro
  const intro = document.getElementById("bf-intro");
  if (intro) intro.innerHTML =
    `Ron Baron has put in a <b>$1B order</b> to buy more SpaceX at the IPO. To judge how much of that reaches ` +
    `<b>Baron Partners Fund</b> (the home of the BPTIX share class you hold), this maps SpaceX across <b>every</b> ` +
    `Baron fund that holds it — straight from each fund's SEC NPORT-P filings — in dollars and as a % of the fund. ` +
    `Bottom line up front: Baron Partners is <b>~${bpPub.toFixed(0)}% of Baron's public-fund SpaceX</b> but only ` +
    `<b>~${al.baron_partners_share_of_firm_wide_pct.toFixed(0)}% of firm-wide SpaceX</b> (the private BaronX vehicles dwarf the mutual funds), ` +
    `so a filled $1B order plausibly sends <b>~$260M–$650M</b> into the fund — incremental, not transformational.`;

  // KPIs
  const kpi = (label, value, note, cls) =>
    `<div class="kpi"><span class="label">${label}</span><div class="value${cls ? " " + cls : ""}">${value}</div>` +
    `<div class="note">${note}</div></div>`;
  document.getElementById("bf-kpis").innerHTML =
    kpi("Baron funds holding SpaceX", d.meta.n_funds, "open-end mutual funds (SEC NPORT-P)") +
    kpi("Family SpaceX — public funds", usd(famTot), "across the 6 funds · 3/31/2026", "spx") +
    kpi("Baron Partners share", bpPub.toFixed(0) + "%", "of Baron's public-fund SpaceX $") +
    kpi("Firm-wide SpaceX (Baron letter)", usd(fw.stated_total_usd), "incl. private BaronX vehicles") +
    kpi("Baron's IPO order", usd(ord.amount_usd), "requested · may not fully fill", "spx");

  // ① funds table
  document.getElementById("bf-funds-note").innerHTML =
    `Every figure is the fund's own filed NPORT-P at 3/31/2026 (SpaceX = all tranches summed; % is of the fund's net assets). ` +
    `Sorted by SpaceX dollars. ${_cTag("MEASURED")} straight from SEC filings.`;
  const fRows = F.map((f, i) => {
    const isBP = f.series_id === "S000000588";
    const tick = [f.ticker_retail, f.ticker_institutional].filter(Boolean).join(" / ");
    const share = famTot ? (f.latest.spacex_value_usd / famTot * 100) : 0;
    return `<tr${isBP ? ` style="background:${_rgba(BF_PAL[0], 0.10)}"` : ""}>
      <td><span style="color:${BF_PAL[i % BF_PAL.length]}">●</span> <b>${f.name}</b></td>
      <td class="dim">${tick || "—"}</td>
      <td>${usd(f.latest.spacex_value_usd)}</td>
      <td>${f.latest.spacex_pct_of_net.toFixed(1)}%</td>
      <td>${share.toFixed(1)}%</td>
      <td class="dim">${f.first_report_date}</td></tr>`;
  }).join("");
  document.getElementById("bf-funds-table").innerHTML =
    `<table class="data"><thead><tr><th>Fund</th><th>Share classes</th><th>SpaceX $</th>
      <th>% of net</th><th>% of family</th><th>Held since</th></tr></thead><tbody>${fRows}
      <tr style="font-weight:700;border-top:2px solid ${GRID}"><td>Family total (6 funds)</td><td></td>
      <td>${usd(famTot)}</td><td></td><td>100%</td><td></td></tr></tbody></table>`;

  // ② stacked dollars chart
  const dates = fam.map((q) => q.report_date);
  const dollarTraces = F.map((f, i) => {
    const col = BF_PAL[i % BF_PAL.length];
    const yByDate = {}; f.series.forEach((p) => { yByDate[p.report_date] = p.spacex_value_usd; });
    return {
      x: dates, y: dates.map((dt) => (yByDate[dt] != null ? yByDate[dt] / 1e9 : null)),
      type: "scatter", mode: "lines", name: f.name.replace("Baron ", "").replace(" Fund", ""),
      stackgroup: "one", line: { color: col, width: 1 }, fillcolor: _rgba(col, 0.55),
      hovertemplate: "%{x}<br>" + f.name + " SpaceX $%{y:.2f}B<extra></extra>",
    };
  });
  Plotly.newPlot("bf-chart-dollars", dollarTraces, baseLayout({
    yaxis: { title: "SpaceX held (USD billions)", tickprefix: "$", ticksuffix: "B", tickformat: ".0f", gridcolor: GRID, color: TEXT, rangemode: "tozero" },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT, size: 10 } }, margin: { t: 34, r: 12, b: 30, l: 54 },
  }), plotConfig());

  // ③ % of net lines
  const pctTraces = F.map((f, i) => {
    const col = BF_PAL[i % BF_PAL.length];
    const yByDate = {}; f.series.forEach((p) => { yByDate[p.report_date] = p.spacex_pct_of_net; });
    return {
      x: dates, y: dates.map((dt) => (yByDate[dt] != null ? yByDate[dt] : null)),
      type: "scatter", mode: "lines+markers", name: f.name.replace("Baron ", "").replace(" Fund", ""),
      line: { color: col, width: 1.6 }, marker: { size: 3 }, connectgaps: false,
      hovertemplate: "%{x}<br>" + f.name + " = %{y:.1f}% of net<extra></extra>",
    };
  });
  Plotly.newPlot("bf-chart-pct", pctTraces, baseLayout({
    yaxis: { title: "SpaceX % of fund net assets", ticksuffix: "%", gridcolor: GRID, color: TEXT, rangemode: "tozero" },
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT, size: 10 } }, margin: { t: 34, r: 12, b: 30, l: 50 },
  }), plotConfig());

  // ④ firm-wide table (incl. private vehicles + residual)
  document.getElementById("bf-firm-note").innerHTML =
    `From Baron's own <b>Q1-2026 "Letter from Ron," Table I</b> (3/31/2026). The 6 open-end mutual funds tie to the SEC ` +
    `scan above to the decimal. But Baron holds far more SpaceX in <b>private</b> vehicles (BaronX is ~99% SpaceX) — so ` +
    `Baron Partners is only ~${al.baron_partners_share_of_firm_wide_pct.toFixed(0)}% of the firm-wide total. ` +
    `${_cTag("REPORTED")} Baron self-disclosure.`;
  const vRows = fw.vehicles.map((v) => {
    const isBP = v[0] === "Baron Partners Fund";
    return `<tr${isBP ? ` style="background:${_rgba(BF_PAL[0], 0.10)}"` : ""}>
      <td><b>${v[0]}</b></td><td class="dim">${v[4]}</td>
      <td>${usd(v[1])}</td><td>${v[2].toFixed(1)}%</td>
      <td style="color:${v[3] ? GOOD : MUTED}">${v[3] ? "✓ NPORT" : "private"}</td></tr>`;
  }).join("");
  const resRow = fw.residual_usd > 0
    ? `<tr><td class="dim">Other Baron accounts / SMAs (not itemized)</td><td class="dim">residual</td>
        <td class="dim">${usd(fw.residual_usd)}</td><td class="dim">—</td><td class="dim">—</td></tr>` : "";
  document.getElementById("bf-firm-table").innerHTML =
    `<table class="data"><thead><tr><th>Baron vehicle</th><th>Type</th><th>SpaceX $</th><th>% of net</th><th>SEC-visible?</th></tr></thead>` +
    `<tbody>${vRows}${resRow}<tr style="font-weight:700;border-top:2px solid ${GRID}"><td>Firm-wide total (Baron stated)</td><td></td>` +
    `<td>${usd(fw.stated_total_usd)}</td><td></td><td></td></tr></tbody></table>`;

  // ⑤ IPO facts memo
  const bn = (x) => "$" + (x / 1e9).toFixed(1) + "B";
  document.getElementById("bf-ipo").innerHTML =
    `<ul>` +
    `<li><b>${ipo.ticker}</b> on ${ipo.exchange} — first trade <b>${ipo.first_trade_date}</b> (priced ${ipo.pricing_date}). ${_cTag("CONFIRMED")}</li>` +
    `<li>Fixed offer price <b>$${ipo.offer_price_usd}</b>; ${ipo.structure}. Post-money valuation <b>${usd(ipo.post_money_valuation_usd)}</b>. ${_cTag("CONFIRMED")}</li>` +
    `<li>Stock split <b>${ipo.split}</b> → private mark $${ipo.post_split_private_mark_usd}/sh; IPO at $${ipo.offer_price_usd} is a +${(((ipo.offer_price_usd / ipo.post_split_private_mark_usd) - 1) * 100).toFixed(0)}% step. ${_cTag("CONFIRMED")}</li>` +
    `<li>Primary raise <b>${(ipo.primary_shares / 1e6).toFixed(0)}M shares × $${ipo.offer_price_usd} = ${bn(ipo.primary_raise_usd)}</b> (≈${bn(ipo.with_greenshoe_usd)} with greenshoe) — largest IPO ever. ${_cTag("CONFIRMED")}</li>` +
    `<li>Leads: ${ipo.lead_banks.join(", ")}. FY2025: revenue ${bn(ipo.fy2025_revenue_usd)}, net loss ${bn(ipo.fy2025_net_loss_usd)}. ${_cTag("REPORTED")}</li>` +
    `</ul>`;

  // ⑥ allocation analysis
  const sc = al.scenarios.map((s) =>
    `<tr><td>${s.label}<br><span class="dim" style="font-size:11px">Baron Partners = ${s.basis_pct}% of this base</span></td>
      <td>${usd(s.full_fill.to_baron_partners_usd)}<br><span class="dim">${s.full_fill.pct_of_bp_nav}% of NAV</span></td>
      <td>${usd(s.half_fill.to_baron_partners_usd)}<br><span class="dim">${s.half_fill.pct_of_bp_nav}% of NAV</span></td></tr>`).join("");
  document.getElementById("bf-alloc").innerHTML =
    `<p style="border-left:3px solid ${SPX};padding-left:10px;font-style:italic;color:${TEXT}">"${ord.quote}"<br>` +
    `<span class="dim" style="font-style:normal">— ${ord.attribution} ${_cTag("REPORTED")}</span></p>` +
    `<p><b>Why $1B?</b> ${ord.rationale} The ${al.primary_dilution_pct}% primary dilution on Baron's ~$14.9B SpaceX would take ` +
    `<b>${usd(al.anti_dilution_firmwide_usd)}</b> just to hold the firm's ownership % flat — so the $1B is anti-dilution <i>plus</i> a genuine add.</p>` +
    `<p><b>How much reaches Baron Partners (BPTIX)?</b> No source discloses the per-fund split ${_cTag("NOT FOUND")}, so we bound it two ways. ` +
    `Per-fund share of the order, by allocation basis:</p>` +
    `<table class="data"><thead><tr><th>Allocation basis</th><th>If $1B fills</th><th>If ~$0.5B fills</th></tr></thead><tbody>${sc}</tbody></table>` +
    `<p class="dim" style="margin-top:8px">${al.share_class_note}</p>` +
    `<p style="margin-top:10px"><b>Bottom line.</b> ${al.bottom_line}</p>` +
    `<p class="dim">${_cTag("MEASURED")} allocation bases (SEC + Baron letter). ${_cTag("NOT FOUND")} the actual per-fund split — treat the dollar figures as a reasoned range, not a disclosed number.</p>`;

  const src = document.getElementById("bf-source");
  if (src) src.innerHTML = "Source: " + d.meta.source + " · firm-wide & IPO/order figures per Baron's Q1-2026 letter and 2026 news (tagged inline). Generated " + (d.meta.generated_at || "").slice(0, 10) + ".";
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
const YAHOO = "https://finance.yahoo.com/quote/BPTIX";

/* Rich hover text for a measured quarterly NPORT-P anchor (used on both the
 * weight chart and the SpaceX-value step chart). Says exactly what the mark is. */
function _monthsBetween(aISO, bISO) {
  return Math.abs(Date.parse(bISO) - Date.parse(aISO)) / 2.629746e9;
}
function anchorHover(a, prev) {
  const lines = [
    "<b>" + a.report_date + " · NPORT-P (measured)</b>",
    "SpaceX fair value: <b>" + usd(a.spacex_value_usd) + "</b> · " + a.spacex_n_tranches + " tranches summed",
    "Filed weight: <b>" + pct(a.spacex_weight_measured) + "</b> of net assets",
  ];
  // nearest reported whole-company valuation, if within ~12 months
  const near = (DATA.marks || [])
    .filter((m) => m.date <= a.report_date)
    .sort((x, y) => (x.date < y.date ? 1 : -1))[0];
  if (near && _monthsBetween(near.date, a.report_date) <= 12) {
    lines.push("Carried near the ≈ " + usd(near.whole_company_valuation_usd) + " valuation"
      + (near.per_share_usd ? " ($" + near.per_share_usd + "/sh)" : "") + " — mark " + near.date);
  }
  if (prev && prev.spacex_value_usd) {
    lines.push("Δ vs prior filing (" + prev.report_date + "): value "
      + signPct(a.spacex_value_usd / prev.spacex_value_usd - 1));
  }
  lines.push("Fund: net " + usd(a.net_assets_usd)
    + (a.total_assets_usd ? " · gross " + usd(a.total_assets_usd) : ""));
  lines.push("Source: SEC NPORT-P · acc " + a.accession);
  return lines.join("<br>");
}

function renderKpis() {
  const k = DATA.kpis, ipo = DATA.meta.ipo;
  const today = new Date().toISOString().slice(0, 10);
  const dToIpo = daysBetween(today, ipo.first_trade_date);

  const la = DATA.anchors[DATA.anchors.length - 1];           // latest measured filing
  const lt = DATA.lookthrough || null;                        // per-share SpaceX look-through
  const ltX = lt && lt.per_share ? lt.per_share.BPTIX : null;
  const filingUrl = secFilingUrl(la.accession);
  const lastNavPt = [...DATA.series].reverse().find((p) => p.nav_per_share != null);
  const navTxt = lastNavPt ? "$" + lastNavPt.nav_per_share.toFixed(2) : "–";
  const mk125 = DATA.marks.find((m) => m.date === "2026-02-02") || {};
  const mkIpo = DATA.marks.find((m) => m.date === "2026-06-03") || {};
  // IPO PRICED $1.77T (6/3). Pick the priced-IPO scenario (~$1.77T).
  const ipo175 = (DATA.scenario_table || []).find(
    (r) => Math.round(r.ipo_valuation_usd / 1e10) === 177) || (DATA.scenario_table || [])[1] || {};
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

    { label: "SpaceX shares held by fund", value: lt ? (lt.spacex_shares_held / 1e6).toFixed(2) + "M" : "–", cls: "spx",
      note: lt ? "post-split · carried @ $" + lt.spacex_mark_per_share + " mark" : "",
      tip: "= SpaceX $ held " + usd(lt ? lt.spacex_value_usd : 0) + " ÷ $" + (lt ? lt.spacex_mark_per_share : 135)
        + " current per-share mark (post 5-for-1 split). Carried flat from the 3/31 filing — a private holding "
        + "can't be added with daily creation cash, and there's been no observable SpaceX transaction since. "
        + "<span class='conf'>Confidence: HIGH for the $ (measured NPORT-P); share count derived at the $135 mark.</span>",
      sources: [S_EDGAR, S_IPO] },

    { label: "SpaceX shares per BPTIX share", value: ltX ? ltX.spacex_shares.toFixed(3) : "–", cls: "spx", hl: true,
      note: lt ? "$" + (ltX ? ltX.spacex_usd.toFixed(2) : "–") + " SpaceX per share · AUM " + lt.as_of : "",
      tip: "Per <b>one BPTIX share</b> (NAV $" + (ltX ? ltX.nav.toFixed(2) : "–") + ", " + (ltX ? ltX.nav_as_of : "–")
        + "): SpaceX weight " + pct(lt ? lt.spacex_weight : 0) + " × NAV ÷ $" + (lt ? lt.spacex_mark_per_share : 135)
        + "/share mark = <b>" + (ltX ? ltX.spacex_shares.toFixed(4) : "–") + " SpaceX shares</b> (≈ $"
        + (ltX ? ltX.spacex_usd.toFixed(2) : "–") + " of SpaceX). At the reported AUM of "
        + usd(lt ? lt.fund_aum_usd : 0) + " (" + (lt ? lt.as_of : "") + "), the fund holds ~"
        + (lt ? (lt.spacex_shares_held / 1e6).toFixed(2) : "–") + "M SpaceX shares total. "
        + "<span class='conf'>Confidence: MED — SpaceX $ measured & carried at the $135 mark; AUM is the reported figure; BPTIX NAV from Yahoo.</span>",
      sources: ov ? [S_AUM, S_EDGAR, S_YAHOO] : [S_EDGAR, S_YAHOO] },

    { label: "Reconstructed fund AUM", value: usd(k.total_nav_usd),
      note: ov ? "trued-up to reported " + ov.date + " + NAV drift" : "NAV × est. shares",
      tip: "Latest filed net assets = " + usd(la.net_assets_usd) + " (" + la.report_date + ", NPORT-P). "
        + (ov ? "No public holdings filing exists after that (next is 2026-06-30), so AUM is trued-up to a "
              + "reported figure of " + usd(ov.net_assets_usd) + " (" + ov.date + ", " + ov.source + "), "
              + "then drifted daily by NAV. "
            : "")
        + "<span class='conf'>Confidence: MED — post-filing AUM is a manually-sourced datapoint, not SEC.</span>",
      sources: ov ? [S_AUM, S_EDGAR, S_YAHOO] : [S_YAHOO, S_EDGAR] },

    { label: "BPTIX NAV / share (latest)", value: navTxt,
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

    { label: "IF re-marked @ IPO $1.77T", value: pct(ipo175.spacex_weight, 0) + " / " + signPct(ipo175.nav_stepup_pct, 0),
      cls: "spx", small: true, note: "SpaceX weight / NAV step-up",
      tip: "IPO PRICED $135/sh = $1.77T (6/3). Re-marking SpaceX $1.25T → $1.77T (×1.42): weight "
        + pct(k.spacex_weight) + " → " + pct(ipo175.spacex_weight) + ", per-share NAV step-up "
        + signPct(ipo175.nav_stepup_pct) + ". The fund still carries the stale $1.25T mark; it re-marks to "
        + "the public price after first trade (6/12). <span class='conf'>IPO price confirmed; fund re-mark pending.</span>",
      sources: [S_IPO] },

    { label: "Days to IPO first trade", value: dToIpo >= 0 ? dToIpo : "traded",
      note: ipo.ticker + " · " + ipo.first_trade_date,
      tip: "Calendar days to SpaceX's first trading day (" + ipo.first_trade_date
        + ", Nasdaq: " + ipo.ticker + "). PRICED 6/3 at $135/sh ($1.77T); 555.6M shares ($75B raise). "
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

/* ----------------- how the SpaceX mark is set (explainer) -------------- */
function renderMarkChain() {
  const el = document.getElementById("mark-chain");
  if (!el) return;
  const byDate = (d) => (DATA.marks || []).find((m) => m.date === d) || {};
  const la = DATA.anchors[DATA.anchors.length - 1];
  const filingUrl = secFilingUrl(la.accession);
  const link = (m, label) => m.source_url
    ? `<a href="${m.source_url}" target="_blank" rel="noopener">${label} ↗</a>` : label;

  const steps = [
    { d: "2025-12-13", t: "Last tender before the merger", v: "$800B · $421/sh",
      note: "Insider secondary sale; sets the pre-merger per-share basis.",
      link: link(byDate("2025-12-13"), "Bloomberg / CNBC") },
    { d: "2026-02-02", t: "SpaceX × xAI merger — the standing whole-company mark",
      v: "$1.25T combined",
      note: "$1.0T SpaceX + $0.25T xAI, all-stock. This is the most recent observable transaction, so it anchors the fund's fair-value mark.",
      link: link(byDate("2026-02-02"), "CNBC / Bloomberg") },
    { d: "2026-03-31", t: "What the fund actually carries — MEASURED, in the SEC filing",
      v: "$526.59 / share", hot: true,
      note: "valUSD ÷ balance for the SpaceX line items in Baron Partners' NPORT-P. "
        + "$526.59 × ~1.9B shares ≈ $1.0T SpaceX standalone; + $0.25T xAI = the $1.25T combined mark. "
        + "This $526.59 is the price baked into today's NAV.",
      link: `<a href="${filingUrl}" target="_blank" rel="noopener">SEC NPORT-P · acc ${la.accession} ↗</a>` },
    { d: "2026-05-04", t: "5-for-1 split (cosmetic only)", v: "$526.59 → $105.32",
      note: "Per-share figure divided by 5; the fund's SpaceX dollar value and weight are unchanged.",
      link: link(byDate("2026-05-04"), "Bloomberg") },
    { d: "2026-06-03", t: "IPO PRICED — the re-rate is now confirmed", v: "$135/sh = $1.77T", forward: true,
      note: "Priced 6/3 at $135/share, 555.6M shares ($75B raise, +83.3M greenshoe), $1.77T valuation. "
        + "First trade 6/12 on Nasdaq (SPCX). The fund still carries the stale $1.25T mark and will re-mark "
        + "to the public price after it trades — a confirmed step-up, no longer a target.",
      link: link(byDate("2026-06-03"), "CNBC (6/3)") },
  ];

  const rows = steps.map((s) => `
    <div class="chain-step ${s.hot ? "hot" : ""} ${s.forward ? "fwd" : ""}">
      <div class="chain-date">${s.d}</div>
      <div class="chain-body">
        <div class="chain-head"><span class="chain-title">${s.t}</span>
          <span class="chain-val ${s.hot ? "spx" : ""}">${s.v}</span></div>
        <div class="chain-note">${s.note}</div>
        <div class="chain-src">${s.link}</div>
      </div>
    </div>`).join("");

  el.innerHTML = rows + `
    <div class="mark-callout">
      <b>Bottom line.</b> Today's NAV still embeds SpaceX at the <b>$1.25T</b> private mark
      (<b>$526.59/share</b>, verified in the 3/31 SEC filing). The IPO has now <b>PRICED at $1.77T</b>
      ($135/share, 6/3) — so the re-rate is <b>confirmed, not a hope</b>. Once SpaceX trades (6/12) the
      fund must mark to the public price: a ~<b>$0.52T</b> step-up on the SpaceX mark, multiplied by
      SpaceX's ~26% weight and the fund's leverage. That captured-vs-priced gap is precisely this
      situation's thesis — now with a known number. Adjust first-day pop in the Scenario Lab below.
    </div>`;
}

/* ------------- how the current weight estimate is built ---------------- */
function renderWeightAssumptions() {
  const el = document.getElementById("weight-assumptions-body");
  if (!el) return;
  const k = DATA.kpis, la = DATA.anchors[DATA.anchors.length - 1];
  const filingUrl = secFilingUrl(la.accession);
  const ov = (DATA.aum_overrides || [])[(DATA.aum_overrides || []).length - 1];
  const wt = document.getElementById("wa-weight");
  if (wt) wt.textContent = pct(k.spacex_weight, 0);

  const badge = (b) => `<span class="badge ${b.toLowerCase()}">${b}</span>`;
  const aumLink = ov && ov.source_url
    ? `<a href="${ov.source_url}" target="_blank" rel="noopener">Morningstar ↗</a>` : "reported source";

  const items = [
    { b: "MEASURED",
      h: "Numerator — SpaceX dollars held = " + usd(k.spacex_value_usd),
      n: "Sum of valUSD across all SpaceX line items in the 2026-03-31 NPORT-P. Hard SEC data. "
        + `<a href="${filingUrl}" target="_blank" rel="noopener">filing ↗</a>` },
    { b: "ASSUMED",
      h: "SpaceX $ held flat since the filing",
      n: "No new shares (a private holding can't be bought with daily cash) and no re-mark (no observable "
        + "SpaceX transaction since the $1.25T xAI merger). So the numerator is frozen at " + usd(k.spacex_value_usd)
        + " until the next filing, tender, or the IPO." },
    { b: "SOURCED",
      h: "Denominator — net AUM ≈ " + usd(k.total_nav_usd),
      n: "No holdings filing exists after 3/31. AUM is anchored to the latest reported figure ("
        + (ov ? aumLink + ", " + ov.date : "reported") + ") and drifted by daily NAV. "
        + "<b>Working assumption (pending the 5/31 month-end):</b> we treat Morningstar's "
        + "<b>Total Assets</b> ($15.9B at 5/27, $15.6B at 5/26, $12.0B at 4/30) as GROSS/levered and "
        + "divide by ~1.136 → net ≈ <b>" + usd(ov ? ov.net_assets_usd : 0) + "</b>, the weight denominator. "
        + "<b>Honest caveat:</b> Morningstar's glossary actually defines Total Assets as the NET assets of "
        + "all share classes — if that holds, net = $15.9B and the weight is ~24%. A fresh month-end print "
        + "should settle net-vs-gross." },
    { b: "ASSUMED", hot: true,
      h: "New inflows are deployed into PUBLIC stocks + cash — not SpaceX",
      n: "This is the key assumption. Daily creations bring cash that <b>cannot</b> buy private SpaceX shares, "
        + "so it lands in the public book (Tesla, Arch, MSCI, …) and/or pays down leverage. SpaceX dollars stay "
        + "fixed while the denominator grows → the weight gets <b>diluted</b>. Baron's filings support this: the "
        + "SpaceX share count was flat in 24 of 26 quarter-over-quarter transitions." },
    { b: "ASSUMED",
      h: "Shares outstanding interpolated between known AUM points",
      n: "Daily share creations/redemptions aren't separately observable for free, so shares are interpolated "
        + "linearly between the filing and each reported-AUM datapoint. Net flows are inferred from the change "
        + "in total net assets, not measured tick-by-tick." },
    { b: "NOTE",
      h: "Weight is % of NET assets (the per-$1 lens) — leverage already included",
      n: "Per $1 of your net capital. The fund runs ~113% long / −13% cash, so this is higher than the fact "
        + "sheet's 33% (% of gross investments): 33% × 1.136 ≈ 37.5% at the filing." },
  ];

  el.innerHTML = items.map((it) => `
    <div class="chain-step asm ${it.hot ? "hot" : ""}">
      <div class="chain-date">${badge(it.b)}</div>
      <div class="chain-body">
        <div class="chain-title">${it.h}</div>
        <div class="chain-note">${it.n}</div>
      </div>
    </div>`).join("") + `
    <div class="mark-callout">
      <b>Net result.</b> Estimated SpaceX weight = ${usd(k.spacex_value_usd)} (measured, frozen) ÷
      ${usd(k.total_nav_usd)} (sourced net AUM) ≈ <b>${pct(k.spacex_weight)}</b> of net assets today —
      down from <b>${pct(la.spacex_weight_measured)}</b> filed on ${la.report_date}, as inflows diluted it.
      <span class="conf">Confidence: MED — numerator measured; denominator is a sourced, leverage-adjusted estimate.</span>
    </div>`;
}

/* ----------------- NAV freshness / mark-to-market check ---------------- */
function renderMtmCheck() {
  const el = document.getElementById("mtm-check-body");
  if (!el) return;
  const la = DATA.anchors[DATA.anchors.length - 1];
  const today = new Date().toISOString().slice(0, 10);
  const markDate = "2026-02-02";                 // last observable SpaceX transaction (xAI merger)
  const markAge = daysBetween(markDate, today);
  const filingAge = daysBetween(la.report_date, today);
  const ipo = DATA.meta.ipo;
  const ipo175 = (DATA.scenario_table || []).find(
    (r) => Math.round(r.ipo_valuation_usd) === 1750000000000) || {};

  const rows = [
    { b: "FRESH", color: GOOD,
      h: "SpaceX is re-marked every quarter (not stale)",
      n: "Baron carries SpaceX in NPORT-P at the latest observable transaction. The 2026-03-31 filing "
        + "marks it at $526.59/share ($1.25T, the Feb xAI merger). This is genuine mark-to-market — "
        + "contrast VCX, whose sponsor NAV sat at a stale mark while its holdings re-rated." },
    { b: "GAP: " + markAge + "d", color: WARN,
      h: "No new observable SpaceX transaction since " + markDate,
      n: "The standing $1.25T mark is " + markAge + " days old. Private holdings only re-mark on a real "
        + "transaction (tender / round / merger) — none has printed since the xAI merger, so the NAV "
        + "correctly still carries $1.25T. The next mark IS the IPO." },
    { b: "GAP: filing", color: MUTED,
      h: "Holdings filing is " + filingAge + "d old (next ~2026-06-30 report)",
      n: "Between filings we true-up AUM from reported figures (see the assumptions card); the SpaceX "
        + "$ value itself is held flat because it can't be added to and hasn't re-marked." },
    { b: "PENDING", color: SPX,
      h: "The real MTM event is the IPO re-rate (not yet in NAV)",
      n: "When SpaceX trades (~" + ipo.first_trade_date + ", " + ipo.ticker + "), the mark jumps from $1.25T "
        + "to the public price. At the $1.77T IPO price that is a weight step to " + pct(ipo175.spacex_weight)
        + " and a NAV step-up of " + signPct(ipo175.nav_stepup_pct) + ". Model it in the Scenario Lab below." },
  ];
  el.innerHTML = rows.map((r) =>
    `<div class="chain-step asm"><div class="chain-date"><span class="badge" style="background:${r.color}22;color:${r.color}">${r.b}</span></div>
     <div class="chain-body"><div class="chain-title">${r.h}</div><div class="chain-note">${r.n}</div></div></div>`).join("")
    + `<div class="mark-callout">
        <b>Bottom line.</b> SpaceX's NAV mark is current-as-of-last-transaction ($1.25T) and re-marked each
        quarter — it is <b>not</b> the stale-NAV problem VCX has. The only "unmarked" upside is the pending
        IPO re-rate, which is a scenario, not a gap. <span class="conf">SpaceX mark: measured (filing).
        IPO re-rate: scenario / forward.</span>
       </div>`;
}

/* ------------------------- main weight chart --------------------------- */
function renderWeightChart() {
  const s = DATA.series;
  const x = s.map((p) => p.date);
  const y = s.map((p) => p.spacex_weight);

  // measured anchor markers (rich hover from DATA.anchors so we have prior-filing context)
  const A = DATA.anchors;
  const ax = A.map((a) => a.report_date);
  const ay = A.map((a) => a.spacex_weight_measured);
  const atext = A.map((a, i) => anchorHover(a, A[i - 1]));

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
    // customdata: [gross holdings $B (= net x leverage), leverage ratio]
    customdata: ovr.map((o) => [
      (o.net_assets_usd * (o.leverage_ratio || 1)) / 1e9,
      o.leverage_ratio || null,
    ]),
    hovertemplate:
      "%{x}<br>Morningstar Total Assets = <b>NET AUM $%{y:.2f}B</b>"
      + "<br>× %{customdata[1]:.3f} leverage = gross holdings $%{customdata[0]:.1f}B"
      + "<br><i>net is the weight denominator (Baron 5/31 confirms net)</i><extra></extra>",
  };
  // dashed extrapolation of AUM to the IPO date (trend, low confidence)
  const traces = [line, diamonds, ovDiamonds];
  const proj = DATA.aum_projection;
  if (proj && proj.points && proj.points.length) {
    const g = (proj.daily_growth_pct * 100).toFixed(2);
    traces.push({
      x: proj.points.map((p) => p.date), y: proj.points.map((p) => p.total_nav_usd / 1e9),
      type: "scatter", mode: "lines",
      name: "AUM trend → IPO (extrapolated)",
      line: { color: "#d29922", width: 1.6, dash: "dash" },
      hovertemplate: "%{x}<br>projected AUM $%{y:.2f}B<br>(trend +" + g + "%/day, SpaceX wt %{customdata:.1%})<extra></extra>",
      customdata: proj.points.map((p) => p.spacex_weight),
    });
  }
  Plotly.newPlot("chart-aum", traces, baseLayout({
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
    marker: { color: SPX, size: 7, line: { color: "#fff", width: 0.6 } },
    text: a.map((d, i) => anchorHover(d, a[i - 1])),
    hovertemplate: "%{text}<extra></extra>",
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

/* SpaceX-weight series chart: shared by the as-of (vintage) and revised views.
 * `implied` = [{date, implied_w_spx_pct, lo, hi}]; `carried` = full series with
 * carried_w_spx_pct as the mechanical no-buy baseline. */
function drawWChart(elId, implied, carried, label, color) {
  if (!document.getElementById(elId)) return;
  const base = { x: carried.map((x) => x.date), y: carried.map((x) => x.carried_w_spx_pct),
    type: "scatter", mode: "lines+markers", name: "carried (no-buy)",
    line: { color: MUTED, width: 2, dash: "dot" }, marker: { size: 6 } };
  const imp = { x: implied.map((x) => x.date), y: implied.map((x) => x.implied_w_spx_pct),
    type: "scatter", mode: "markers", name: "implied (" + label + ")",
    marker: { color: color, size: 11, symbol: "diamond" },
    error_y: { type: "data", symmetric: false, array: implied.map((x) => x.hi - x.implied_w_spx_pct),
               arrayminus: implied.map((x) => x.implied_w_spx_pct - x.lo), color: color, thickness: 1.4, width: 6 } };
  Plotly.newPlot(elId, [base, imp], baseLayout({
    margin: { l: 48, r: 16, t: 6, b: 34 }, hovermode: "closest",
    showlegend: true, legend: { orientation: "h", y: 1.14, x: 0 },
    xaxis: { gridcolor: GRID, type: "category" },
    yaxis: { gridcolor: GRID, title: "SpaceX weight (% of net)", ticksuffix: "%" },
  }), plotConfig());
}

/* Recalibration ledger table: shared by both views. */
function drawRecalibLedger(elId, rows, isVintage) {
  const L = document.getElementById(elId);
  if (!L) return;
  const sp = (x, dd = 2) => (x == null ? "—" : (x >= 0 ? "+" : "") + Number(x).toFixed(dd));
  const mUSD = (x) => (x == null ? "—" : (x >= 0 ? "+" : "−") + "$" + Math.abs(x).toFixed(0) + "M");
  const bUSD = (x) => (x == null ? "—" : (x >= 0 ? "+" : "−") + "$" + Math.abs(x).toFixed(2) + "B");
  const head = "<tr><th>Date</th><th>SPCX (ret)</th><th>basket ret</th><th>Actual NAV (ret)</th>" +
    "<th>implied SpaceX wt</th><th>carried</th><th>Δ</th><th>implied buy</th><th>net flow</th></tr>";
  const body = rows.slice().reverse().map((r) => {
    if (r.implied_w_spx_pct == null) {
      return `<tr><td><b>${r.date}</b></td><td>$${r.spcx} <span class="dim">(${sp(r.spcx_ret_pct)}%)</span></td>` +
        `<td>${sp(r.basket_ret_pct, 2)}%</td><td class="dim">pending</td><td colspan="5" class="dim">awaiting actual NAV</td></tr>`;
    }
    const dcol = r.w_spx_delta_pct > 0.3 ? SPX : (r.w_spx_delta_pct < -0.3 ? BAD : MUTED);
    const fcol = r.implied_net_flow_b == null ? MUTED : (r.implied_net_flow_b < 0 ? BAD : GOOD);
    const carriedCell = r.carried_w_spx_pct != null ? r.carried_w_spx_pct + "%" : "—";
    return `<tr><td><b>${r.date}</b></td>` +
      `<td>$${r.spcx} <span class="dim">(${sp(r.spcx_ret_pct)}%)</span></td>` +
      `<td>${sp(r.basket_ret_pct, 2)}% <span class="dim">[${sp(r.basket_ret_band_pct[0], 2)},${sp(r.basket_ret_band_pct[1], 2)}]</span></td>` +
      `<td><b style="color:${SPX}">${r.actual_nav.toFixed(2)}</b> <span class="dim">(${sp(r.navret_pct)}%)</span></td>` +
      `<td><b>${r.implied_w_spx_pct}%</b> <span class="dim">(${r.implied_w_spx_band_pct[0]}–${r.implied_w_spx_band_pct[1]})</span></td>` +
      `<td class="dim">${carriedCell}</td>` +
      `<td style="color:${dcol};font-weight:700">${sp(r.w_spx_delta_pct)}pt</td>` +
      `<td style="color:${r.implied_buy_m > 5 ? SPX : MUTED}"><b>${mUSD(r.implied_buy_m)}</b><br><span class="dim" style="font-size:10px">on ${r.buy_attributed_to}</span></td>` +
      `<td style="color:${fcol}">${bUSD(r.implied_net_flow_b)}</td></tr>`;
  }).join("");
  const cap = isVintage
    ? "Frozen the morning each actual NAV first landed — never edited. The honest real-time track record."
    : "Recomputed every build with all current data + assumptions. Inverts each day's actual NAV (and AUM) into SpaceX weight, buy (attributed to the prior close) and net flow. Bands span the 3/31→5/31 disclosed weightings.";
  L.innerHTML = `<table class="data">${head}<tbody>${body}</tbody></table>` +
    `<p class="dim" style="margin-top:6px">${cap}</p>`;
  const interp = rows.filter((r) => r.interpretation).slice().reverse()
    .map((r) => `<li><b>${r.date}:</b> ${r.interpretation}</li>`).join("");
  if (interp) L.innerHTML += `<ul style="margin-top:8px">${interp}</ul>`;
}

/* ---- Daily recalibration ledger: invert actual NAV+AUM -> weight/buy/flow ---- */
function renderRecalib(d) {
  const card = document.getElementById("recalib-card");
  if (!card) return;
  card.style.display = "";
  const m = d.meta;
  const sp = (x, dd = 2) => (x == null ? "—" : (x >= 0 ? "+" : "") + Number(x).toFixed(dd));
  const mUSD = (x) => (x == null ? "—" : (x >= 0 ? "+" : "−") + "$" + Math.abs(x).toFixed(0) + "M");
  const bUSD = (x) => (x == null ? "—" : (x >= 0 ? "+" : "−") + "$" + Math.abs(x).toFixed(2) + "B");
  document.getElementById("recalib-headline").innerHTML = m.headline;
  document.getElementById("recalib-disc").innerHTML = "<span class='dim'>" + m.disclaimer + "</span>";

  // --- belief: prior (no-buy carry) -> posterior (after latest data) ---
  const b = d.belief;
  if (b) {
    const box = (title, lines, col) =>
      `<div style="flex:1;min-width:230px;border:1px solid ${GRID};border-left:3px solid ${col};border-radius:8px;padding:12px 14px;background:${_rgba(col, 0.06)}">` +
      `<div class="dim" style="font-size:11px;margin-bottom:6px">${title}</div>${lines}</div>`;
    const prior = box("PRIOR · " + b.prior.label,
      `<div>SpaceX weight <b>${b.prior.w_spx_pct}%</b></div>` +
      `<div>Friday SpaceX buy <b>$0</b> <span class="dim">(assumed none)</span></div>` +
      `<div>Redemption <b>unknown</b></div>`, MUTED);
    const post = box("POSTERIOR · " + b.posterior.label,
      `<div>Friday (${b.posterior.friday_date}) SpaceX buy <b style="color:${SPX}">${mUSD(b.posterior.friday_buy_m)}</b> <span class="dim">(${mUSD(b.posterior.friday_buy_band_m[0])} to ${mUSD(b.posterior.friday_buy_band_m[1])})</span></div>` +
      `<div>SpaceX weight @ ${b.posterior.current_date} <b style="color:${SPX}">${b.posterior.w_spx_pct}%</b> <span class="dim">(${b.posterior.w_spx_band_pct[0]}–${b.posterior.w_spx_band_pct[1]}%)</span></div>` +
      `<div>Net flow @ ${b.posterior.current_date} <b style="color:${b.posterior.redemption_b < 0 ? BAD : GOOD}">${bUSD(b.posterior.redemption_b)}</b></div>`, SPX);
    document.getElementById("recalib-belief").innerHTML =
      `<div style="font-weight:600;margin-bottom:8px">${b.question}</div>` +
      `<div style="display:flex;gap:12px;align-items:stretch;flex-wrap:wrap">${prior}` +
      `<div style="display:flex;align-items:center;font-size:22px;color:${MUTED}">→</div>${post}</div>` +
      `<p style="margin:10px 0 0">${b.takeaway}</p>`;
  }

  // --- two views: ① as-of (vintage, frozen)  ② revised (all-data) ---
  const vn = document.getElementById("recalib-views-note");
  if (vn) vn.innerHTML = "<b>Two views.</b> " + m.two_views_note;
  const carriedSeries = d.w_spx_series;   // mechanical no-buy carry (shared baseline)
  const revisedImplied = d.w_spx_series.filter((x) => x.implied_w_spx_pct != null);
  drawWChart("recalib-wchart-vintage", d.w_spx_series_vintage, carriedSeries, "as-of (frozen)", WARN);
  drawWChart("recalib-wchart", revisedImplied, carriedSeries, "revised (all-data)", SPX);
  drawRecalibLedger("recalib-ledger-vintage", d.vintage_ledger, true);
  drawRecalibLedger("recalib-ledger", d.ledger, false);

  // --- methodology memo ---
  const meth = document.getElementById("recalib-method");
  if (meth) meth.innerHTML =
    `<p><b>Degrees of freedom.</b> ${m.dof_note}</p>` +
    `<p style="margin-top:8px"><b>Static vs time-varying.</b> ${m.static_vs_dynamic}</p>`;

  // --- vol-tolerance table ---
  const vt = d.vol_tolerance;
  document.getElementById("recalib-voltol-note").innerHTML = vt.note;
  const V = document.getElementById("recalib-voltol");
  if (V) {
    const head = "<tr><th>Ticker</th><th>daily vol</th><th>disclosed wt (5/31)</th><th>drift budget</th><th>treatment</th></tr>";
    const body = vt.rows.map((r) => {
      const col = r.pinned ? WARN : GOOD;
      return `<tr><td><b>${r.ticker}</b></td><td>${r.daily_vol_pct}%</td><td>${r.disclosed_wt_pct}%</td>` +
        `<td style="color:${col};font-weight:700">${r.drift_budget}×</td>` +
        `<td style="color:${col}">${r.pinned ? "pinned (tight)" : "loose"}</td></tr>`;
    }).join("");
    V.innerHTML = `<table class="data">${head}<tbody>${body}</tbody></table>`;
  }
}

/* ---- RONB cross-reference: Baron's daily-transparent ETF as a BPTIX proxy ---- */
function renderRonb(d) {
  const card = document.getElementById("ronb-card");
  if (!card) return;
  card.style.display = "";
  const m = d.meta, bt = d.backtest, ib = d.implied_bptix, sc = d.spacex_check, cmp = d.compare;
  const sp = (x) => (x == null ? "—" : (x >= 0 ? "+" : "") + Number(x).toFixed(2));
  document.getElementById("ronb-title").textContent = m.title;
  document.getElementById("ronb-what").innerHTML = m.what + " <span class='dim'>Holdings as of " + m.as_of + ".</span>";
  document.getElementById("ronb-caveat").innerHTML = "<span class='dim'><b>Caveat.</b> " + m.caveat + "</span>";
  const kpi = (l, v, n, cls) =>
    `<div class="kpi"><span class="label">${l}</span><div class="value${cls ? " " + cls : ""}">${v}</div><div class="note">${n}</div></div>`;
  document.getElementById("ronb-kpis").innerHTML =
    kpi("Post-IPO corr", bt.post_ipo.corr, "RONB↔BPTIX daily return (" + bt.post_ipo.n + " days)", "spx") +
    kpi("BPTIX / RONB beta", (bt.post_ipo.beta || "—") + "×", "BPTIX amplifies RONB (SpaceX wt + leverage)") +
    (ib ? kpi("RONB → implied BPTIX", sp(ib.implied_bptix_ret_pct) + "%", ib.date + ": RONB " + sp(ib.ronb_ret_pct) + "% × β (leading, same-day)", "spx") : "") +
    (sc ? kpi("RONB SpaceX wt", sc.ronb_spacex_pct + "%", "unlevered, direct shares vs BPTIX ~37% levered") : "");

  const B = document.getElementById("ronb-backtest");
  if (B) {
    const row = (lbl, s) => `<tr><td><b>${lbl}</b></td><td>${s.n}</td><td>${s.corr == null ? "—" : s.corr}</td>` +
      `<td>${s.beta == null ? "—" : s.beta + "×"}</td><td class="dim">${s.vol_ronb_pct || "—"}%</td><td class="dim">${s.vol_bptix_pct || "—"}%</td></tr>`;
    B.innerHTML = "<table class='data'><tr><th>Regime</th><th>days</th><th>corr</th><th>beta (BPTIX/RONB)</th><th>RONB vol</th><th>BPTIX vol</th></tr><tbody>" +
      row("Pre-IPO", bt.pre_ipo) + row("Post-IPO (6/12+)", bt.post_ipo) + row("All", bt.all) + "</tbody></table>" +
      `<p class="dim" style="margin-top:6px">Pre-IPO they diverged (RONB took heavy subscriptions, different SpaceX weight); post-IPO they move in near-lockstep with BPTIX ≈ ${bt.post_ipo.beta}× RONB. ${ib ? ib.note : ""}</p>`;
  }
  const cdiv = document.getElementById("ronb-compare");
  if (cdiv) {
    const tag = (t, col) => `<span class="pill" style="background:${_rgba(col, 0.18)};color:${col};margin:2px 3px">${t}</span>`;
    cdiv.innerHTML =
      `<p><b>Shared (${cmp.shared.length})</b> — RONB proxies these directly:<br>${cmp.shared.map((t) => tag(t, MUTED)).join("")}</p>` +
      `<p style="margin-top:8px"><b style="color:${SPX}">RONB-only (${cmp.ronb_only.length})</b> — ${cmp.ronb_only_note}<br>${cmp.ronb_only.map((t) => tag(t, SPX)).join("")}</p>` +
      `<p style="margin-top:8px"><b style="color:${ACC}">BPTIX-only (${cmp.bptix_only.length})</b> — ${cmp.bptix_only_note}<br>${cmp.bptix_only.map((t) => tag(t, ACC)).join("")}</p>` +
      (sc ? `<p style="margin-top:8px">${sc.note}</p>` : "");
  }
  const H = document.getElementById("ronb-holdings");
  if (H) {
    const body = d.holdings.map((h) => {
      const col = h.private ? SPX : (h.cash ? MUTED : (cmp.ronb_only.includes(h.ticker) ? SPX : TEXT));
      const note = h.private ? "SpaceX (direct)" : h.cash ? "cash" : (cmp.ronb_only.includes(h.ticker) ? "not in BPTIX 5/31" : "shared");
      return `<tr><td><b style="color:${col}">${h.ticker}</b></td><td style="text-align:left">${h.name}</td>` +
        `<td>${h.weight}%</td><td class="dim" style="text-align:left">${note}</td></tr>`;
    }).join("");
    H.innerHTML = "<table class='data'><tr><th>Ticker</th><th style='text-align:left'>Name</th><th>Weight</th><th style='text-align:left'>vs BPTIX</th></tr><tbody>" + body + "</tbody></table>";
  }
}

/* ---- SpaceX position: pre-IPO holding vs the 6/12 IPO-day buy (the $262M) ---- */
function renderSpacexPosition(d) {
  const card = document.getElementById("spacex-position-card");
  if (!card) return;
  card.style.display = "";
  const m = d.meta, fb = d.friday_buy, cur = d.current, pre = d.pre_ipo;
  const uM = (x) => "$" + (x / 1e6).toFixed(0) + "M", uB = (x) => "$" + (x / 1e9).toFixed(2) + "B";
  const sh = (x) => (x / 1e6).toFixed(2) + "M";
  document.getElementById("spxpos-title").textContent = m.title;
  document.getElementById("spxpos-headline").innerHTML = m.headline;
  const kpi = (l, v, n, cls) =>
    `<div class="kpi"><span class="label">${l}</span><div class="value${cls ? " " + cls : ""}">${v}</div><div class="note">${n}</div></div>`;
  document.getElementById("spxpos-kpis").innerHTML =
    kpi("Current SpaceX", uB(cur.total_value_usd), sh(cur.total_shares) + " sh · as of " + cur.as_of + " ($" + cur.spcx + ")", "spx") +
    kpi("Pre-IPO (disclosed)", uB(cur.pre_ipo_value_usd), sh(pre.shares) + " sh · 3/31 NPORT") +
    kpi("Friday IPO add", uM(cur.friday_value_usd), sh(fb.shares) + " sh · " + cur.friday_pct + "% of holding", "spx") +
    kpi("SpaceX shares per BPTIX share", (cur.spx_shares_per_bptix != null ? cur.spx_shares_per_bptix.toFixed(3) : "—"),
        (cur.usd_per_bptix != null ? "$" + cur.usd_per_bptix.toFixed(0) + " of SpaceX per BPTIX share · " + cur.lookthrough_basis : ""), "spx") +
    kpi("Friday cash (est)", uM(fb.cash_low_usd) + "–" + uM(fb.cash_vwap_usd), "@ $" + fb.cash_low_price + " IPO → $" + fb.cash_vwap_price + " VWAP");
  document.getElementById("spxpos-derivation").innerHTML =
    "<ol style='margin:0;padding-left:20px;line-height:1.75'>" +
    d.derivation.map((s) => `<li><b>${s.step}.</b> ${s.detail}</li>`).join("") + "</ol>";
  document.getElementById("spxpos-buy").innerHTML =
    `<p><b>Shares are pinned; the cash is a range.</b> The back-solve gives the Friday-<b>close</b> marked value ` +
    `<b style="color:${SPX}">${uM(fb.close_value_usd)}</b> (band ${uM(fb.close_value_band_usd[0])}–${uM(fb.close_value_band_usd[1])}). ` +
    `Divide by the $${fb.mark_close} close → <b>${sh(fb.shares)} shares</b> added — fixed regardless of execution price. ` +
    `Cash deployed = shares × execution price: <b>${uM(fb.cash_low_usd)}</b> if IPO-allocated at $${fb.cash_low_price}, up to ` +
    `<b>${uM(fb.cash_vwap_usd)}</b> at the ~$${fb.cash_vwap_price} VWAP. So "$${(fb.close_value_usd / 1e6).toFixed(0)}M" is the value that lands in the holding, ` +
    `not necessarily the cash spent.<br><span class="dim">${fb.ipo_intraday}</span></p>`;
  const V = document.getElementById("spxpos-table");
  if (V) {
    const head = "<tr><th>Date</th><th>SPCX</th><th>Pre-IPO $</th><th>Friday add $</th><th>Total SpaceX $</th><th>Friday % of holding</th></tr>";
    const body = d.value_path.slice().reverse().map((r) =>
      `<tr><td><b>${r.date}</b></td><td>$${r.spcx}</td><td>${uB(r.pre_ipo_usd)}</td>` +
      `<td style="color:${SPX}">${uM(r.friday_usd)}</td><td><b>${uB(r.total_usd)}</b></td><td class="dim">${r.friday_pct}%</td></tr>`).join("");
    V.innerHTML = `<table class="data">${head}<tbody>${body}</tbody></table>`;
  }
  document.getElementById("spxpos-disc").innerHTML = "<span class='dim'>" + m.disclaimer + "</span>";
}

/* ---- Long-horizon replication: actual NAV vs public book + SpaceX re-marks ---- */
function renderLongRep(d) {
  const card = document.getElementById("longrep-card");
  if (!card) return;
  card.style.display = "";
  const m = d.meta, s = d.series, st = d.stats, ev = d.events || [];
  const sp = (x, dd = 2) => (x == null ? "—" : (x >= 0 ? "+" : "") + Number(x).toFixed(dd));
  document.getElementById("longrep-headline").innerHTML = m.method;
  const kpi = (label, value, note, cls) =>
    `<div class="kpi"><span class="label">${label}</span><div class="value${cls ? " " + cls : ""}">${value}</div><div class="note">${note}</div></div>`;
  document.getElementById("longrep-kpis").innerHTML =
    kpi("Window", m.window[0] + " → " + m.window[1], m.n_days + " days · " + m.n_quarters + " quarters") +
    kpi("SpaceX weight", st.spacex_wt_start_pct + "% → " + st.spacex_wt_end_pct + "%", "NPORT-measured, of net", "spx") +
    kpi("Actual vs replicated", st.cum_actual_idx.toFixed(0) + " / " + st.cum_repl_idx.toFixed(0), "index, start=100") +
    kpi("Private share", st.private_share_of_repl_pct + "%", "of replicated growth = SpaceX", "spx") +
    kpi("Tracking error", st.resid_sd_bps.toFixed(0) + " bps/day", "gap " + st.replication_gap_pct + "% = fees+financing+conservative mark");

  // event lookups
  const cumAt = (date) => { let v = null; for (const p of s) { if (p.date <= date) v = p.cum_actual; else break; } return v; };
  const remarks = ev.filter((e) => e.type === "remark"), rebals = ev.filter((e) => e.type === "rebalance");
  const shapes = remarks.map((e) => ({ type: "line", x0: e.date, x1: e.date, yref: "paper", y0: 0, y1: 1,
      line: { color: _rgba(SPX, 0.30), width: 1 } }))
    .concat(rebals.map((e) => ({ type: "line", x0: e.date, x1: e.date, yref: "paper", y0: 0, y1: 1,
      line: { color: _rgba(MUTED, 0.22), width: 1, dash: "dot" } })));

  // ① stacked: public (floor) + private (band) = replicated; actual line overlaid
  const dts = s.map((p) => p.date);
  const cd = s.map((p) => [p.c_pub_pct, p.c_priv_pct, p.mark, p.wP_pct, p.wS_pct, p.r_nav_pct, p.r_repl_pct]);
  const pubArea = { x: dts, y: s.map((p) => p.cum_public), type: "scatter", mode: "lines", name: "public book",
    line: { color: ACC, width: 1 }, fill: "tozeroy", fillcolor: _rgba(ACC, 0.18), customdata: cd,
    hovertemplate: "<b>%{x}</b><br>public idx %{y:.1f} · public contrib %{customdata[0]:.2f}%/d<br>wP %{customdata[3]:.0f}% · wS %{customdata[4]:.0f}%<extra>public</extra>" };
  const replArea = { x: dts, y: s.map((p) => p.cum_repl), type: "scatter", mode: "lines", name: "+ SpaceX re-marks (private)",
    line: { color: SPX, width: 1 }, fill: "tonexty", fillcolor: _rgba(SPX, 0.16), customdata: cd,
    hovertemplate: "<b>%{x}</b><br>replicated idx %{y:.1f}<br>SpaceX mark $%{customdata[2]:.0f}/sh · private contrib %{customdata[1]:.2f}%/d<br>repl day %{customdata[6]:.2f}% vs actual %{customdata[5]:.2f}%<extra>private</extra>" };
  const actLine = { x: dts, y: s.map((p) => p.cum_actual), type: "scatter", mode: "lines", name: "actual NAV",
    line: { color: TEXT, width: 2 }, hovertemplate: "<b>%{x}</b><br>actual NAV idx %{y:.1f}<extra>actual</extra>" };
  const remarkMk = { x: remarks.map((e) => e.date), y: remarks.map((e) => cumAt(e.date)), type: "scatter",
    mode: "markers", name: "SpaceX re-mark", marker: { color: SPX, size: 10, symbol: "triangle-up", line: { color: "#000", width: .5 } },
    text: remarks.map((e) => `<b>SpaceX re-mark ${e.date}</b><br>mark step ${sp(e.step_pct)}% → $${e.mark}/sh`),
    hovertemplate: "%{text}<extra></extra>" };
  const rebalMk = { x: rebals.map((e) => e.date), y: rebals.map((e) => cumAt(e.date)), type: "scatter",
    mode: "markers", name: "rebalance", marker: { color: ACC, size: 8, symbol: "diamond-open" },
    text: rebals.map((e) => `<b>Rebalance ${e.date}</b><br>SpaceX ${e.wS_pct}% of net · lev ${e.leverage}×<br>`
      + `added: ${e.added.join(", ") || "—"}<br>removed: ${e.removed.join(", ") || "—"}<br>`
      + `big Δ: ${e.changed.map((c) => c.ticker + " " + sp(c.chg_pct, 0) + "%").join(", ") || "—"}`),
    hovertemplate: "%{text}<extra></extra>" };
  Plotly.newPlot("longrep-cumchart", [pubArea, replArea, actLine, remarkMk, rebalMk], baseLayout({
    margin: { l: 50, r: 14, t: 10, b: 30 }, hovermode: "closest", shapes,
    showlegend: true, legend: { orientation: "h", y: 1.12, x: 0 },
    xaxis: { gridcolor: GRID, type: "date" },
    yaxis: { gridcolor: GRID, title: "growth index (start = 100)" },
  }), plotConfig());

  // ② deviation (actual − replicated), daily, with the biggest days flagged
  const topDev = new Set((st.top_deviations || []).map((x) => x.date));
  const devBar = { x: dts, y: s.map((p) => p.resid_pct), type: "bar", name: "daily deviation",
    marker: { color: s.map((p) => topDev.has(p.date) ? SPX : _rgba(MUTED, 0.55)) },
    hovertemplate: "<b>%{x}</b><br>actual − replicated = %{y:.2f}%/day<extra></extra>" };
  Plotly.newPlot("longrep-residchart", [devBar], baseLayout({
    margin: { l: 50, r: 14, t: 8, b: 30 }, hovermode: "closest", shapes,
    xaxis: { gridcolor: GRID, type: "date" },
    yaxis: { gridcolor: GRID, title: "actual − replicated (%/day)", ticksuffix: "%", zeroline: true, zerolinecolor: GRID },
  }), plotConfig());

  // ③ SpaceX weight path (quarterly, stepped) + mapping coverage
  const q = d.quarters;
  const wt = { x: q.map((x) => x.report_date), y: q.map((x) => x.wS_pct), type: "scatter",
    mode: "lines+markers", name: "SpaceX % of net", line: { color: SPX, width: 2, shape: "hv" }, marker: { size: 6 } };
  const cov = { x: q.map((x) => x.report_date), y: q.map((x) => x.coverage_pct), type: "scatter",
    mode: "lines", name: "public mapping coverage %", line: { color: MUTED, width: 1.4, dash: "dot" }, yaxis: "y2" };
  Plotly.newPlot("longrep-wtchart", [wt, cov], baseLayout({
    margin: { l: 44, r: 44, t: 14, b: 30 }, hovermode: "x unified",
    showlegend: true, legend: { orientation: "h", y: 1.16, x: 0 },
    xaxis: { gridcolor: GRID, type: "date" },
    yaxis: { gridcolor: GRID, title: "SpaceX % of net", ticksuffix: "%" },
    yaxis2: { overlaying: "y", side: "right", range: [80, 100], ticksuffix: "%", showgrid: false },
  }), plotConfig());

  // quarters table
  const Q = document.getElementById("longrep-quarters");
  if (Q) {
    const head = "<tr><th>Quarter</th><th>Net assets</th><th>Leverage</th><th>SpaceX % net</th>" +
      "<th>SpaceX $</th><th>public % net</th><th>coverage</th></tr>";
    const body = q.slice().reverse().map((x) =>
      `<tr><td><b>${x.report_date}</b></td><td>${usd(x.net_assets)}</td><td>${x.leverage ? x.leverage.toFixed(3) + "×" : "—"}</td>` +
      `<td style="color:${SPX};font-weight:600">${x.wS_pct}%</td><td>${usd(x.spacex_value)}</td>` +
      `<td>${x.wP_pct}%</td><td class="${x.coverage_pct >= 90 ? "" : "dim"}">${x.coverage_pct}%</td></tr>`).join("");
    Q.innerHTML = `<table class="data">${head}<tbody>${body}</tbody></table>`;
  }
  document.getElementById("longrep-method").innerHTML = "<b>Method.</b> " + m.method + " <b>Coverage:</b> " + m.coverage_note;
  document.getElementById("longrep-disc").innerHTML =
    `<span class="dim"><b>Reading it:</b> the orange band is SpaceX's re-mark contribution stacked on the blue public book — together they ` +
    `track actual to ~${st.resid_sd_bps.toFixed(0)} bps/day. The steady ~${Math.abs(st.replication_gap_pct)}% the replication runs ABOVE actual is ` +
    `fees + leverage interest + the fund marking SpaceX more conservatively than headline tender prices; the deviation chart shows where each ` +
    `re-mark (▲) and rebalance (◇) lands. ${m.disclaimer} ${m.price_basis}</span>`;
}

boot();
