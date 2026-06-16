"use strict";

/* Cross-vehicle research memo. Reads data/overview.json (built by overview.py).
 * One-page hedge-fund-style valuation sheet + memo. No heavy compute client-side. */

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7",
      LOW = "#6e7681", WARN = "#d29922", BAD = "#f85149";
let DATA = null;

const pctRaw = (x, d = 0) => (x == null ? "–" : (x >= 0 ? "+" : "") + (x * 100).toFixed(d) + "%");
const pctAbs = (x, d = 0) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
function usd(x) {
  if (x == null) return "–";
  const a = Math.abs(x);
  if (a >= 1e12) return "$" + (x / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (x / 1e9).toFixed(0) + "B";
  if (a >= 1e6) return "$" + (x / 1e6).toFixed(0) + "M";
  return "$" + x.toFixed(2);
}
const CATCOLOR = { opportunity: GOOD, clean: ACC, fair: ACC, rich: WARN, avoid: BAD };
const CATLABEL = { opportunity: "OPPORTUNITY", clean: "CLEAN", fair: "FAIR", rich: "RICH", avoid: "AVOID" };
const CONFCOLOR = { high: GOOD, med: WARN, medium: WARN, "low-med": WARN, low: BAD };

async function boot() { await load("data/overview.json"); }

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

function vof(t) { return (DATA.vehicles || []).find((v) => v.ticker === t && !v.missing); }

function render() {
  document.getElementById("disclaimer").textContent = DATA.meta.disclaimer;
  document.getElementById("gen").textContent = "Generated " + DATA.meta.generated_at;
  renderSummary(); renderTable(); renderCards(); renderCompanies(); renderMemo();
}

/* 1. summary tiles --------------------------------------------------------- */
function renderSummary() {
  const s = DATA.summary;
  const tile = (label, t, sub, color) => {
    const v = t ? vof(t) : null;
    return `<a class="sumtile" style="border-top-color:${color}" href="${v ? v.page : "#"}">
      <div class="sumlabel">${label}</div>
      <div class="sumticker">${t || "–"}</div>
      <div class="sumsub">${sub || ""}</div></a>`;
  };
  const o = s.most_overheated;
  document.getElementById("summary").innerHTML =
    tile("Best opportunity", s.best_opportunity && s.best_opportunity.ticker,
         s.best_opportunity && s.best_opportunity.why, GOOD) +
    tile("Cleanest exposure", s.cleanest_exposure && s.cleanest_exposure.ticker,
         s.cleanest_exposure && s.cleanest_exposure.why, ACC) +
    tile("Top bull upside", s.top_bull_upside && s.top_bull_upside.ticker,
         s.top_bull_upside ? pctRaw(s.top_bull_upside.ret) + " if underlying re-rates" : "", SPX) +
    tile("Most overheated", o && o.ticker,
         o ? pctAbs(o.premium_mtm) + " premium to fair NAV" : "", BAD) +
    tile("Most data uncertainty", s.most_uncertain && s.most_uncertain.ticker,
         s.most_uncertain && s.most_uncertain.why, WARN);
}

/* 2. comparison table ------------------------------------------------------ */
function renderTable() {
  const rows = (DATA.vehicles || []).filter((v) => !v.missing).map((v) => {
    const sc = v.scenarios || {};
    const ret = (c) => {
      const r = sc[c] && sc[c].return_from_price;
      if (r == null) return "<td>–</td>";
      const col = r > 0.02 ? GOOD : r < -0.02 ? BAD : MUTED;
      return `<td style="color:${col}">${pctRaw(r)}</td>`;
    };
    const priceNav = v.at_nav
      ? (v.is_etf ? "at NAV (ETF)" : (v.price ? usd(v.price) : "at NAV"))
      : usd(v.price) + " / " + usd(v.nav_mtm);
    const prem = v.at_nav ? "<span class='dim'>n/a (at NAV)</span>"
      : (v.premium_stale != null && v.premium_stale > 1.5
          ? `<b style='color:${BAD}'>${pctAbs(v.premium_stale)}</b><span class='dim'> stale / </span>${pctAbs(v.premium_mtm)}<span class='dim'> MTM</span>`
          : `${pctAbs(v.premium_mtm)}<span class='dim'> MTM</span>`);
    const cc = CATCOLOR[v.category] || MUTED;
    return `<tr>
      <td><a href="${v.page}"><b>${v.ticker}</b></a><div class="dim">${v.type}</div></td>
      <td>${v.headline}<div class="dim">${(v.lookthrough[0] && v.lookthrough[0].weight != null) ? pctAbs(v.lookthrough[0].weight, 1) + " wt" : ""}</div></td>
      <td>${priceNav}</td>
      <td>${prem}</td>
      ${ret("bear")}${ret("base")}${ret("bull")}
      <td><span class="pill ${v.data_confidence === "high" ? "high" : v.data_confidence === "med" ? "med" : "low"}">${v.data_confidence}</span></td>
      <td class="risk">${v.key_risk}</td>
      <td><span class="verdict" style="background:${cc}22;color:${cc}">${CATLABEL[v.category] || v.category}</span></td>
    </tr>`;
  }).join("");
  document.getElementById("cmp-body").innerHTML = rows;
}

/* 3. vehicle cards --------------------------------------------------------- */
function renderCards() {
  const cards = (DATA.vehicles || []).filter((v) => !v.missing).map((v) => {
    const sc = v.scenarios || {};
    const scTile = (c, label) => {
      const r = sc[c] && sc[c].return_from_price;
      const col = r == null ? MUTED : r > 0.02 ? GOOD : r < -0.02 ? BAD : MUTED;
      return `<div class="sc"><div class="sclab">${label}</div><div class="scval" style="color:${col}">${pctRaw(r)}</div></div>`;
    };
    const cc = CATCOLOR[v.category] || MUTED;
    const lt = (v.lookthrough || []).map((h) =>
      `${h.name}${h.weight != null ? " " + pctAbs(h.weight, 1) : ""}`).join(" · ") || "—";
    return `<div class="vcard" style="border-left-color:${cc}">
      <div class="vhead">
        <div><a href="${v.page}"><b>${v.ticker}</b></a> <span class="dim">${v.name}</span></div>
        <span class="verdict" style="background:${cc}22;color:${cc}">${CATLABEL[v.category]}</span>
      </div>
      <div class="vmeta">${v.type} · ${v.buyable} · fee ${v.fee}</div>
      <div class="vlt"><span class="dim">Owns:</span> ${lt}</div>
      <div class="scrow">${scTile("bear", "Bear")}${scTile("base", "Base")}${scTile("bull", "Bull")}</div>
      <div class="vrow"><span class="up">▲ Buy:</span> ${v.reason_buy}</div>
      <div class="vrow"><span class="dn">▼ Avoid:</span> ${v.reason_avoid}</div>
      <div class="vwarn">⚠ ${v.confidence_reasons}</div>
    </div>`;
  }).join("");
  document.getElementById("cards").innerHTML = cards;
}

/* 4. private-company valuation section ------------------------------------- */
function renderCompanies() {
  const rows = (DATA.companies || []).map((c) => {
    const lc = c.last_confirmed || {};
    const via = (c.exposed_via || []).map((e) => {
      const tag = e.at_nav ? "at NAV" : pctAbs(e.premium_mtm) + " prem";
      const col = e.ticker === c.cleanest_ticker ? GOOD : e.ticker === c.priciest_ticker ? BAD : MUTED;
      return `<span class="viatag" style="color:${col}">${e.ticker} <span class="dim">${pctAbs(e.weight, 1)}·${tag}</span></span>`;
    }).join(" ");
    return `<div class="ccard">
      <div class="chead"><b>${c.name}</b> <span class="dim">${c.sector}</span></div>
      <div class="crange">
        <span class="dim">bear</span> ${usd(c.bear)}
        <span class="bar"><span class="dot" style="left:${barPos(c)}%"></span></span>
        ${usd(c.bull)} <span class="dim">bull</span>
        <div class="cbase">base <b>${usd(c.base)}</b> <span class="dim">(${lc.date}, ${lc.source_type}, ${lc.confidence})</span></div>
      </div>
      <div class="crum"><span class="dim">Latest/rumored:</span> ${c.rumored_range} <a href="${c.source_url}" target="_blank" rel="noopener">↗</a></div>
      <div class="cnote">${c.notes}</div>
      <div class="cvia"><span class="dim">Exposed via:</span> ${via || "—"}
        ${c.cleanest_ticker ? `<div class="dim">cleanest: <b style="color:${GOOD}">${c.cleanest_ticker}</b> · priciest: <b style="color:${BAD}">${c.priciest_ticker}</b></div>` : ""}</div>
    </div>`;
  }).join("");
  document.getElementById("companies").innerHTML = rows;
}
function barPos(c) {
  const r = c.bull - c.bear || 1;
  return Math.max(2, Math.min(98, ((c.base - c.bear) / r) * 100));
}

/* 5. final memo ------------------------------------------------------------ */
function renderMemo() {
  const s = DATA.summary;
  const cef = (DATA.vehicles || []).filter((v) => !v.missing && !v.at_nav);
  const atnav = (DATA.vehicles || []).filter((v) => !v.missing && v.at_nav);
  const worst = cef.slice().sort((a, b) => (b.premium_stale || 0) - (a.premium_stale || 0))[0];
  document.getElementById("memo").innerHTML = `
    <p><b>The one-line take.</b> The only vehicles with clean risk/reward are the ones that trade
    <b>at NAV</b> — <b>BPTIX</b> (large SpaceX, ~28% of fund) and <b>AGIX</b> (small but verifiable, low-fee
    Anthropic). The three closed-end funds (VCX, DXYZ, RVI) trade at premiums so large that they
    <b>lose money in the bear AND base cases and barely gain in the bull</b> — you can be right on the
    underlying AI names and still lose, because the premium dominates.</p>
    <p><b>What looks most attractive.</b> ${atnav.map((v) => v.ticker).join(" and ")} give honest, at-NAV
    exposure. BPTIX additionally carries an un-realized SpaceX IPO re-rate (the $1.25T mark is stale-low),
    so its bull case (${pctRaw((vof("BPTIX").scenarios.bull || {}).return_from_price)}) is real optionality
    rather than premium hope.</p>
    <p><b>What looks too expensive.</b> ${worst ? worst.ticker : "VCX"} is the most overheated:
    ${worst ? pctAbs(worst.premium_stale) : ""} above its published NAV (${pctAbs((worst || {}).premium_mtm)}
    even after marking the underlying to current valuations). DXYZ and RVI are cheaper but still carry
    structural premiums on top of large cash balances (~46% and ~53% cash respectively) that dilute the
    very exposure you're paying up for.</p>
    <p><b>Where more research is needed.</b> (1) The SPV-codenamed look-through in VCX/DXYZ is sponsor-
    disclosed, not SEC-verifiable — those weights could be wrong. (2) Closed-end NAVs are stale; the true
    premium shifts daily with the underlying privates. (3) Anthropic's key asymmetry: its last private mark
    ($965B) is <b>above</b> the reported IPO target ($400–500B), so an IPO could re-rate it <b>down</b> —
    which would hit every Anthropic-exposed vehicle.</p>
    <p><b>What would change the conclusion.</b> A fresh NPORT (next quarter) confirming the SPV holdings; a
    premium collapse on the CEFs toward NAV (would make them buyable); or a confirmed Anthropic IPO price
    that resolves the $965B-vs-$450B gap.</p>`;
}

boot();
