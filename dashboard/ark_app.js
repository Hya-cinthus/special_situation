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
  renderAnswers(); renderRanking(); renderExposure(); renderHistory(); renderTimeline();
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
  const rows = DATA.ipo_history.map((ev) => {
    const etfs = ev.etfs.map((t) => {
      const tracked = ["ARKK", "ARKW", "ARKQ", "ARKX"].includes(t);
      return `<span class="etftag" style="color:${tracked ? ACC : MUTED}">${t}</span>`;
    }).join(" ");
    return `<tr>
      <td><b>${ev.company}</b></td>
      <td>${ev.ipo_date}</td>
      <td>${ev.first_day ? "<span style='color:" + GOOD + "'>✓ first day</span>" : "later"}</td>
      <td>${etfs}</td>
      <td>${usd(ev.alloc_usd)}</td>
      <td>${ev.arkk_initial_weight != null ? pct(ev.arkk_initial_weight, 1) : "<span class='dim'>n/a</span>"}</td>
      <td><a href="${ev.source_url}" target="_blank" rel="noopener">${pill(ev.confidence)}</a></td>
    </tr>`;
  }).join("");
  const by = DATA.ipo_stats.by_etf;
  const stat = ["ARKK", "ARKW", "ARKQ", "ARKX"].map((t) =>
    `<span class="statchip"><b>${t}</b> ${by[t]}/${DATA.ipo_stats.n_ipos}</span>`).join(" ");
  document.getElementById("history").innerHTML =
    `<div class="statrow">${stat} <span class="dim">— first-day IPO participation across ${DATA.ipo_stats.n_ipos} tracked events</span></div>
     <div class="scroll-x"><table class="data"><thead><tr>
       <th>Company</th><th>IPO date</th><th>Timing</th><th>ARK ETFs that bought</th><th>1st-day $</th><th>Init. ARKK wt</th><th>Src</th>
     </tr></thead><tbody>${rows}</tbody></table></div>
     <p class="desc" style="margin-top:8px">Pattern: ARK routes first-day IPO buys through its <b>broad</b> funds
     (ARKK always; ARKW for internet/fintech) and only adds a <b>sector</b> fund when the theme fits
     (ARKQ for robotics/aerospace, ARKG for genomics). For SpaceX, expect <b>ARKK + ARKW + ARKQ + ARKX</b>.</p>`;
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
