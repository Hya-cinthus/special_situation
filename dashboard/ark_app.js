"use strict";

/* ARK / SpaceX-IPO Tracker. Reads data/ark_tracker.json.
 * Empirical (historical IPO behavior) -> allocation ranking + dollar exposure.
 * No charts library needed; pure DOM. */

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7",
      LOW = "#6e7681", WARN = "#d29922", BAD = "#f85149", PURPLE = "#bb86fc";
let DATA = null;

function usd(x) {
  if (x == null) return "<span class='dim'>n/a</span>";
  const a = Math.abs(x);
  if (a >= 1e9) return "$" + (x / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return "$" + (x / 1e6).toFixed(0) + "M";
  return "$" + x.toFixed(0);
}
const pct = (x, d = 0) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
function pill(c) { return `<span class="pill ${c}">${c}</span>`; }

async function boot() { await load("data/ark_tracker.json"); }

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
      "<br>Run <code>py build.py</code> then serve <code>dashboard/</code>.";
  }
}

function render() {
  document.getElementById("disclaimer").textContent = DATA.meta.disclaimer;
  document.getElementById("gen").textContent = "Generated " + DATA.meta.generated_at;
  renderAnswers(); renderRanking(); renderExposure(); renderHistory();
  renderImpact(); initScenario(); renderTimeline();
}

/* 1. the 6 key answers up top */
function renderAnswers() {
  const a = DATA.key_answers;
  const tiles = [
    { label: "Most likely to get SpaceX shares", v: a.most_likely_shares.etf, sub: a.most_likely_shares.why, c: GOOD },
    { label: "Largest $ dollar exposure", v: a.largest_dollar.etf, sub: a.largest_dollar.why, c: ACC },
    { label: "Highest portfolio weight", v: a.highest_weight.etf, sub: a.highest_weight.why, c: SPX },
    { label: "Est. ARK buying pressure (base)", v: usd(a.buying_pressure_base_usd), sub: "broad funds × ~5% target weight", c: WARN },
  ];
  document.getElementById("answers").innerHTML = tiles.map((t) =>
    `<div class="sumtile" style="border-top-color:${t.c}">
      <div class="sumlabel">${t.label}</div>
      <div class="sumticker">${t.v}</div>
      <div class="sumsub">${t.sub}</div></div>`).join("");
}

/* 2. allocation ranking — fit scores + empirical history */
function renderRanking() {
  const rows = DATA.etfs.map((e, i) => {
    const f = e.fit;
    const bar = `<div class="fitbar"><span style="width:${f.score}%;background:${i === 0 ? GOOD : ACC}"></span></div>`;
    return `<div class="arkrow">
      <div class="arkrank">#${i + 1}</div>
      <div class="arkmain">
        <div class="arkhead"><b>${e.ticker}</b> <span class="dim">${e.name}</span>
          <span class="dim">· ${e.theme}</span></div>
        <div class="arkmeta">AUM ${usd(e.aum_usd)} · bought <b>${e.ipo_participation}/${DATA.ipo_stats.n_ipos}</b> past IPOs first-day
          · fit <b>${f.score}</b>/100 <span class="dim">(${f.empirical})</span></div>
        ${bar}
        <ul class="arkreasons">${f.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
      </div>
    </div>`;
  }).join("");
  document.getElementById("ranking").innerHTML = rows;
}

/* 3. weight vs dollar-exposure matrix (the key distinction) */
function renderExposure() {
  const sizes = DATA.meta.position_sizes;
  const head = "<th>ETF</th><th>AUM</th>" + sizes.map((w) => `<th>${pct(w)} weight</th>`).join("");
  const rows = DATA.etfs.map((e) => {
    const cells = e.exposure.map((x) => `<td>${usd(x.dollar)}</td>`).join("");
    return `<tr><td><b>${e.ticker}</b></td><td>${usd(e.aum_usd)}</td>${cells}</tr>`;
  }).join("");
  document.getElementById("exposure").innerHTML =
    `<table class="data cmp"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>
     <p class="desc" style="margin-top:8px"><b>Portfolio weight ≠ dollar exposure.</b> At the same target weight,
     ARKK's $7.26B fund buys far more SpaceX in dollars than ARKX's $1.11B — but the same dollar buy is a much
     bigger <em>weight</em> in tiny ARKX. So ARKK = biggest $ impact; ARKX = biggest weight impact.
     Dollar exposure = target weight × AUM (SpaceX valuation sets the share count, not the $ ARK commits).</p>`;
}

/* 4. historical IPO database */
function renderHistory() {
  const cols = ["ARKK", "ARKW", "ARKQ", "ARKX", "ARKF", "ARKG"];
  const wcell = (ev, t) => {
    if (!ev.etfs.includes(t)) return "<td class='dim'>—</td>";
    const w = (ev.weights || {})[t];
    return `<td>${w != null ? "<b>" + pct(w, 1) + "</b>" : "<span class='dim'>bought</span>"}</td>`;
  };
  const rows = DATA.ipo_history.map((ev) => `<tr>
      <td><b>${ev.company}</b><div class="dim">${ev.ipo_date}${ev.offer_price ? " · offer $" + ev.offer_price : ""}</div></td>
      ${cols.map((t) => wcell(ev, t)).join("")}
      <td>${usd(ev.alloc_usd)}</td>
      <td><a href="${ev.source_url}" target="_blank" rel="noopener">${pill(ev.confidence)}</a></td>
    </tr>`).join("");
  const by = DATA.ipo_stats.by_etf;
  const stat = ["ARKK", "ARKW", "ARKQ", "ARKX"].map((t) =>
    `<span class="statchip"><b>${t}</b> ${by[t] || 0}/${DATA.ipo_stats.n_ipos}</span>`).join(" ");
  const r = DATA.sizing_rubric || {};
  document.getElementById("history").innerHTML =
    `<div class="statrow">${stat} <span class="dim">— first-day IPO participation across ${DATA.ipo_stats.n_ipos} tracked events</span></div>
     <div class="scroll-x"><table class="data"><thead><tr>
       <th>Company</th>${cols.map((t) => "<th>" + t + " wt</th>").join("")}<th>1st-day $</th><th>Src</th>
     </tr></thead><tbody>${rows}</tbody></table></div>
     <p class="desc" style="margin-top:8px">Initial weight ARK assigned <b>in each ETF</b> (blank = not held;
     "bought" = participated, weight not disclosed). Pattern: broad funds (ARKK always; ARKW internet/fintech;
     ARKF fintech; ARKG genomics) + a sector fund only on theme fit. For SpaceX: expect <b>ARKK + ARKW + ARKQ + ARKX</b>.</p>
     <div class="mark-callout" style="border-left-color:${SPX}">
       <b>Sizing guidance (ARK's own rubric).</b> Median position ~<b>${pct(r.median, 0)}</b>, typical min
       ~${pct(r.typical_min, 0)}, <b>max ~${pct(r.max, 0)}</b>; top-10 ≈ ${pct(r.top10_share, 0)} of the fund.
       High-conviction NEW IPOs (Circle, Tempus) entered at <b>~4.4–5%</b> — the best empirical guide for a
       <b>SpaceX day-1 weight</b> in ARKK/ARKW. ARKX (tiny, pure-theme) could start higher relative to its size.
       <a href="${r.source_url}" target="_blank" rel="noopener">source ↗</a></div>`;
}

/* 4b. IPO-day price impact (measured) */
function signp(x, d = 1) { return x == null ? "–" : (x >= 0 ? "+" : "") + (x * 100).toFixed(d) + "%"; }
function renderImpact() {
  const imp = DATA.ipo_impact;
  if (!imp) { document.getElementById("impact").innerHTML = "<p class='dim'>run a full build to populate</p>"; return; }
  const rows = imp.events.map((e) => {
    const z = e.arkk_z_score;
    const zcol = z == null ? MUTED : Math.abs(z) > 1 ? BAD : Math.abs(z) > 0.5 ? WARN : GOOD;
    const v = e.arkk_prevol || {};
    const stockcol = (e.stock_day1_open_close || 0) >= 0 ? GOOD : BAD;
    const arkcol = (e.arkk_ipo_day_return || 0) >= 0 ? GOOD : BAD;
    const contrib = e.ipo_contribution, resid = e.arkk_residual;
    const ccol = contrib == null ? MUTED : contrib >= 0 ? GOOD : BAD;
    return `<tr>
      <td><b>${e.company}</b><div class="dim">${e.ticker} · ${e.ipo_date}</div></td>
      <td style="color:${stockcol}">${signp(e.stock_day1_open_close)}<div class="dim">day-1 o→c</div></td>
      <td style="color:${arkcol}">${signp(e.arkk_ipo_day_return, 2)}<div class="dim">ARKK that day</div></td>
      <td style="color:${ccol}">${signp(contrib, 2)}<div class="dim">${e.arkk_weight != null ? pct(e.arkk_weight, 1) + " × stock" : "wt n/a"}</div></td>
      <td>${signp(resid, 2)}<div class="dim">rest of fund</div></td>
      <td>${v.d21 != null ? (v.d21 * 100).toFixed(0) + "%" : "–"}<div class="dim">ARKK RV 21d ann.</div></td>
      <td style="color:${zcol}"><b>${z == null ? "–" : (z >= 0 ? "+" : "") + z.toFixed(2) + "σ"}</b><div class="dim">excess move</div></td>
    </tr>`;
  }).join("");
  document.getElementById("impact").innerHTML =
    `<table class="data"><thead><tr>
      <th>IPO</th><th>IPO stock day-1</th><th>ARKK same day</th><th>from IPO stock</th><th>from rest of fund</th><th>ARKK vol</th><th>z-score</th>
    </tr></thead><tbody>${rows}</tbody></table>
     <p class="desc" style="margin-top:8px"><b>Decomposition:</b> "from IPO stock" = the IPO's weight × its day-1
     move (its mechanical contribution to ARKK's NAV); "from rest of fund" = ARKK's total move minus that.
     <b>Circle is the key example:</b> the IPO <em>added</em> +0.91% to ARKK, yet ARKK fell −2.79% — because the
     <b>rest of the portfolio dropped −3.70%</b> on broad-market weakness that day. The IPO helped; the market
     dragged ARKK down anyway.</p>`;
  const s = imp.summary;
  document.getElementById("impact-takeaway").innerHTML =
    `<div class="mark-callout" style="border-left-color:${ACC}">
      <b>Takeaway (measured).</b> The IPO stocks moved a lot (±8–21% on day 1), but <b>ARKK barely
      reacted</b>: average absolute excess move was <b>${s.avg_abs_z != null ? s.avg_abs_z.toFixed(2) : "–"}σ</b>,
      and only <b>${s.n_gt_1sigma}/${s.n_events}</b> IPO days were even a &gt;1σ move for ARKK — and that one
      (Circle) was a market-driven <em>down</em> day, not an IPO pop. Why: any single new IPO position is only
      ~1–4% of ARKK, so weight × pop is tiny next to ARKK's ~${DATA.ipo_impact.arkk_current_vol.d21 != null ? (DATA.ipo_impact.arkk_current_vol.d21 * 100).toFixed(0) : "32"}% annualized vol.
      <b>Implication for SpaceX: a single IPO is mathematically too small to move ARKK much</b> unless ARK
      makes it an unusually large position — which the scenario below lets you test.</div>`;
}

/* interactive SpaceX scenario */
function initScenario() {
  const imp = DATA.ipo_impact || {};
  const dailyVol = imp.arkk_current_vol_daily_21 || 0.02;   // ARKK current daily RV (21d)
  const cv = imp.arkk_current_vol || {};
  const w = document.getElementById("w-slider"), pop = document.getElementById("pop-slider");
  if (!w || !pop) return;
  // make the assumed vol level explicit, up front
  const volNote = document.getElementById("vol-note");
  if (volNote) {
    volNote.innerHTML = `Baseline = ARKK's <b>current realized volatility</b> (last ~3 months of daily closes): `
      + `<b>${pct(cv.d10, 0)}</b> (10d) · <b>${pct(cv.d21, 0)}</b> (21d) · <b>${pct(cv.d63, 0)}</b> (63d), `
      + `annualized. The σ figures below use the 21-day = <b>${pct(cv.d21, 0)}/yr ≈ ${pct(dailyVol, 2)}/day</b>. `
      + `<span class="dim">(Realized vol, not implied — ARKK options IV isn't in our free data feed.)</span>`;
  }
  const update = () => {
    const wv = +w.value, pv = +pop.value;
    document.getElementById("w-txt").textContent = pct(wv, 1);
    document.getElementById("pop-txt").textContent = signp(pv, 0);
    const navImpact = wv * pv;                 // mechanical ARKK NAV move from the new position
    const sigma = dailyVol ? navImpact / dailyVol : null;
    const arkkAum = (DATA.etfs.find((e) => e.ticker === "ARKK") || {}).aum_usd || 7.26e9;
    const dollar = wv * arkkAum;
    const out = [
      { label: "ARKK NAV impact (day 1)", value: signp(navImpact, 2),
        col: navImpact >= 0 ? GOOD : BAD, note: "= weight × pop" },
      { label: "vs ARKK normal day", value: sigma == null ? "–" : (sigma >= 0 ? "+" : "") + sigma.toFixed(2) + "σ",
        col: Math.abs(sigma) > 1 ? BAD : Math.abs(sigma) > 0.5 ? WARN : MUTED,
        note: Math.abs(sigma) > 1 ? "bigger-than-normal day" : "within normal noise" },
      { label: "$ SpaceX in ARKK", value: usd(dollar), col: ACC, note: "weight × $7.26B AUM" },
      { label: "ARKK daily vol (21d RV)", value: pct(dailyVol, 2), col: MUTED, note: "current baseline" },
    ];
    document.getElementById("scenario-out").innerHTML = out.map((c) =>
      `<div class="kpi"><div class="label">${c.label}</div>
        <div class="value" style="color:${c.col}">${c.value}</div>
        <div class="note">${c.note}</div></div>`).join("");
    const big = Math.abs(sigma) > 1;
    document.getElementById("scenario-explain").innerHTML =
      `At a <b>${pct(wv, 1)}</b> weight and a <b>${signp(pv, 0)}</b> day-1 SpaceX pop, ARKK's NAV moves about
       <b>${signp(navImpact, 2)}</b> — ${big ? "a <b>" + Math.abs(sigma).toFixed(1) + "σ</b> day, materially "
       + "bigger than ARKK's normal move." : "<b>within</b> ARKK's normal daily noise (" + pct(dailyVol, 2)
       + "), i.e. hard to even notice."} ${wv >= 0.10
       ? "Note: a 10%+ SpaceX weight would be aggressive for a single IPO vs ARK's history (typically 1–5%)."
       : ""}`;
  };
  w.oninput = update; pop.oninput = update;
  document.querySelectorAll("#scenario-card .btn-row button[data-pop]").forEach((b) => {
    b.onclick = () => { pop.value = b.dataset.pop; update(); };
  });
  update();
}

/* 5. monitoring timeline */
function renderTimeline() {
  const CATC = { SpaceX: SPX, ARK: ACC, "Cathie Wood": PURPLE };
  const rows = DATA.timeline.map((t) =>
    `<div class="tlrow">
      <div class="tldate">${t.date}</div>
      <div class="tlcat" style="color:${CATC[t.cat] || MUTED}">${t.cat}</div>
      <div class="tltext">${t.text} <a href="${t.source_url}" target="_blank" rel="noopener">↗</a>
        <span class="dim">${t.kind} · ${t.confidence}</span></div>
    </div>`).join("");
  document.getElementById("timeline").innerHTML = rows;
}

boot();
