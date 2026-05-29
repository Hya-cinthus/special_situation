"use strict";

/* VCX (Fundrise Innovation Fund) — premium-to-NAV deep dive.
 * Reads data/vcx_fundrise.json; all scenario math runs client-side. */

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7",
      LOW = "#6e7681", WARN = "#d29922", BAD = "#f85149";
const PLOT_BG = "#161b22", GRID = "#2a3343", TEXT = "#e6edf3";
let DATA = null;

const pct = (x, d = 1) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
const signPct = (x, d = 1) => (x == null ? "–" : (x >= 0 ? "+" : "") + (x * 100).toFixed(d) + "%");
function usd(x) {
  if (x == null) return "–";
  const a = Math.abs(x);
  if (a >= 1e12) return "$" + (x / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (x / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return "$" + (x / 1e6).toFixed(1) + "M";
  if (a >= 1e3) return "$" + (x / 1e3).toFixed(1) + "K";
  return "$" + x.toFixed(2);
}
function daysBetween(a, b) { return Math.round((Date.parse(b) - Date.parse(a)) / 86400000); }

/* scenario math — mirrors engine/scenarios.py */
function scenarioReturn(price, nav, navChange, targetPremium) {
  const newNav = nav * (1 + navChange);
  const newPrice = newNav * (1 + targetPremium);
  return { newNav, newPrice, totalReturn: price ? newPrice / price - 1 : null };
}

async function boot() { await load("data/vcx_fundrise.json"); }

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
  document.getElementById("sit-title").textContent = "OpenAI / Anthropic via VCX";
  document.getElementById("sit-subtitle").textContent = "data through " + m.last_data_day + " · " + m.primary_ticker;
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("hn-label").textContent = m.headline_name;
  document.getElementById("edgar-link").href =
    `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${m.edgar_cik}&type=NPORT-P`;
  document.getElementById("footer-meta").textContent =
    "Generated " + m.generated_at + " · CIK " + m.edgar_cik + " · " + DATA.series.length + " trading days.";
  renderKpis(); renderThesis(); renderPremiumChart(); renderLookthrough();
  renderNport(); renderRisks(); initScenario();
}

function renderKpis() {
  const k = DATA.kpis, m = DATA.meta;
  const today = new Date().toISOString().slice(0, 10);
  const dLock = daysBetween(today, m.lockup_expiry);
  const anth = (k.lookthrough || []).find((l) => l.name === m.headline_name) || {};
  const cards = [
    { label: "Premium to NAV (now)", value: signPct(k.premium, 0), cls: "spx", hl: true,
      note: "price " + usd(k.price) + " vs NAV " + usd(k.nav),
      tip: "VCX market price ÷ NAV per share − 1. You pay <b>" + (k.price_multiple || 0).toFixed(1)
        + "×</b> the value of the underlying holdings. Closed-end funds have no redemption to close this gap. "
        + "<span class='conf'>price: measured (Yahoo). NAV: sponsor-published, " + k.nav_age_days
        + " days old (carried forward).</span>" },
    { label: "You pay per $1 of NAV", value: "$" + (k.price_multiple || 0).toFixed(2), cls: "spx", hl: true,
      note: "every $1 of holdings costs you this",
      tip: "The inverse lens on the premium: $1 of the fund's net asset value costs you $"
        + (k.price_multiple || 0).toFixed(2) + " at today's price." },
    { label: "Effective $ for $1 of " + m.headline_name + " NAV",
      value: anth.weight ? "$" + (k.price_multiple * 1).toFixed(2) : "–", cls: "spx",
      note: m.headline_name + " is " + pct(anth.weight, 1) + " of NAV (sponsor-disclosed)",
      tip: m.headline_name + " is " + pct(anth.weight) + " of NAV = " + usd(anth.nav_value_per_share)
        + "/share of value, but you pay " + usd(anth.price_paid_per_share) + "/share for it through the premium. "
        + "<span class='conf'>weight is sponsor-disclosed, not SEC-verifiable.</span>" },
    { label: "VCX price", value: usd(k.price),
      note: "as of " + k.as_of + " · measured",
      tip: "NYSE close from Yahoo Finance. <span class='conf'>measured / high.</span>" },
    { label: "NAV per share", value: usd(k.nav),
      note: k.nav_age_days + " days old · sponsor-published",
      tip: "Fundrise-published NAV, carried forward (not daily). Underlying privates are themselves "
        + "marked periodically. <span class='conf'>med confidence; " + k.nav_age_days + "d stale.</span>" },
    { label: "Days to lockup expiry", value: dLock >= 0 ? dLock : "passed",
      note: m.lockup_expiry + " · premium-compression risk",
      tip: "~6-month post-listing lockup. When restricted pre-listing holders can sell, supply jumps "
        + "and the premium can compress hard. <span class='conf'>dated catalyst.</span>" },
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
  const k = DATA.kpis, m = DATA.meta;
  document.getElementById("thesis-body").innerHTML = `
    <div class="mark-callout" style="border-left-color:${SPX}">
      <b>Baron/SpaceX:</b> an <b>open-end</b> fund priced <b>at NAV</b> carrying a <b>stale-low</b>
      private mark → you bought the underlying <em>cheap</em> before a re-rate. <br>
      <b>VCX:</b> a <b>closed-end</b> fund trading at a <b>${signPct(k.premium, 0)} premium</b> to NAV →
      even if the underlying marks are stale-low, <b>you massively overpay through the wrapper</b>.
      The edge here isn't the underlying — it's whether that premium holds or collapses. There are three
      stacked opacities: (1) the wrapper premium, (2) NAV staleness (${k.nav_age_days}d old), and
      (3) SPV look-through (OpenAI/Anthropic weights are sponsor-disclosed, not in the filings).
    </div>`;
}

function renderPremiumChart() {
  const s = DATA.series;
  const priceTrace = {
    x: s.map((p) => p.date), y: s.map((p) => p.price), name: "Market price",
    type: "scatter", mode: "lines", line: { color: ACC, width: 1.8 },
    hovertemplate: "%{x}<br>price $%{y:.2f}<extra></extra>", yaxis: "y",
  };
  const navTrace = {
    x: s.map((p) => p.date), y: s.map((p) => p.nav), name: "NAV/share (sponsor)",
    type: "scatter", mode: "lines", line: { color: GOOD, width: 1.6, shape: "hv" },
    hovertemplate: "%{x}<br>NAV $%{y:.2f}<extra></extra>", yaxis: "y",
  };
  const premTrace = {
    x: s.map((p) => p.date), y: s.map((p) => p.premium == null ? null : p.premium * 100),
    name: "Premium to NAV (%)", type: "scatter", mode: "lines",
    line: { color: SPX, width: 1.4 }, fill: "tozeroy", fillcolor: "rgba(255,122,69,0.10)",
    hovertemplate: "%{x}<br>premium %{y:.0f}%<extra></extra>", yaxis: "y2",
  };
  const shapes = [], ann = [];
  const kc = { listing: GOOD, mark: ACC, ipo: SPX, lockup: WARN, corporate: "#bb86fc" };
  (DATA.events || []).forEach((ev, i) => {
    shapes.push({ type: "line", xref: "x", yref: "paper", x0: ev.date, x1: ev.date, y0: 0, y1: 1,
      line: { color: kc[ev.kind] || MUTED, width: 1, dash: "dash" } });
    ann.push({ x: ev.date, y: (i % 2 ? 0.98 : 0.90), yref: "paper", xref: "x", text: ev.label,
      showarrow: false, font: { color: kc[ev.kind] || MUTED, size: 9 }, xanchor: "left",
      bgcolor: "rgba(14,17,23,0.7)" });
  });
  Plotly.newPlot("chart-premium", [priceTrace, navTrace, premTrace], {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    shapes, annotations: ann,
    xaxis: { gridcolor: GRID, color: TEXT, type: "date" },
    yaxis: { title: "USD / share", gridcolor: GRID, color: TEXT, rangemode: "tozero",
             tickprefix: "$", side: "left" },
    yaxis2: { title: "Premium %", overlaying: "y", side: "right", color: SPX,
              ticksuffix: "%", showgrid: false, rangemode: "tozero" },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT } },
    margin: { t: 40, r: 56, b: 30, l: 56 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderLookthrough() {
  const k = DATA.kpis;
  const rows = (k.lookthrough || []).map((l) => {
    const mult = l.price_paid_per_share / l.nav_value_per_share;
    return `<tr>
      <td>${l.name}</td>
      <td>${pct(l.weight, 1)}</td>
      <td>${usd(l.nav_value_per_share)}</td>
      <td class="spxcell">${usd(l.price_paid_per_share)}</td>
      <td>${mult.toFixed(1)}×</td>
      <td>${pill(l.confidence)}</td>
    </tr>`;
  }).join("");
  document.getElementById("lookthrough").innerHTML = `
    <table class="data">
      <thead><tr><th>Holding</th><th>% of NAV</th><th>NAV value / VCX share</th>
        <th>You pay / VCX share</th><th>Overpay</th><th>Conf.</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="desc" style="margin-top:8px">Weights are <b>sponsor-disclosed</b> (Fundrise), not SEC-verifiable — in the NPORT-P they sit inside codenamed SPVs.</p>`;
}

function pill(c) { return `<span class="pill ${c}">${c}</span>`; }

function renderNport() {
  const n = DATA.nport_latest;
  const tb = document.querySelector("#nport-table tbody");
  if (!n || !n.top_holdings) { tb.innerHTML = "<tr><td colspan='3'>no filing</td></tr>"; return; }
  tb.innerHTML = n.top_holdings.map((h) =>
    `<tr><td>${h.name}</td><td>${h.pctVal.toFixed(1)}%</td><td>${usd(h.valUSD)}</td></tr>`).join("");
}

function renderRisks() {
  const k = DATA.kpis, m = DATA.meta;
  const cards = [
    { t: "Premium compression (the big one)", b: BAD,
      n: "At " + signPct(k.premium, 0) + ", price is " + (k.price_multiple || 0).toFixed(1)
        + "× NAV. Closed-end funds historically drift toward — and often below — NAV. If the premium "
        + "normalizes, the loss can dwarf any AI upside. The scenario lab shows this directly." },
    { t: "Lockup expiry " + m.lockup_expiry, b: WARN,
      n: "~6-month post-listing lockup. Restricted holders (who came in near NAV) can then sell into the "
        + "premium — a classic supply shock that compresses CEF premiums." },
    { t: "SPV look-through opacity", b: WARN,
      n: "OpenAI/Anthropic aren't named in the SEC filing — they're inside codenamed SPVs (DBH1 LP, "
        + "Quiet OA Access LP, …). The 20.7%/9.9% weights are sponsor-disclosed and not independently "
        + "verifiable. You're trusting Fundrise's marks on top of the premium." },
    { t: "NAV staleness", b: MUTED,
      n: "NAV is published periodically (now " + k.nav_age_days + " days old) and the underlying privates "
        + "are themselves marked infrequently. The 'true' premium today could be higher or lower than shown." },
    { t: "Headline re-rate may be DOWN, not up", b: MUTED,
      n: "Anthropic's Series H (~$965B) is already ABOVE its reported $400–500B IPO target — so an IPO could "
        + "re-rate the mark DOWN, not up. Don't assume the AI leg only helps." },
  ];
  document.getElementById("risk-cards").innerHTML = cards.map((c) =>
    `<div class="chain-step asm"><div class="chain-date"><span class="badge" style="background:${c.b}22;color:${c.b}">RISK</span></div>
     <div class="chain-body"><div class="chain-title">${c.t}</div><div class="chain-note">${c.n}</div></div></div>`).join("");
}

function initScenario() {
  const b = DATA.scenario_base, k = DATA.kpis;
  const navc = document.getElementById("navc-slider"), prem = document.getElementById("prem-slider");
  const curPrem = k.premium;
  prem.min = 0; prem.max = Math.max(curPrem, 0.5); prem.step = 0.05; prem.value = curPrem;

  const update = () => {
    const nc = +navc.value, tp = +prem.value;
    document.getElementById("navc-txt").textContent = signPct(nc, 0);
    document.getElementById("prem-txt").textContent = signPct(tp, 0);
    const r = scenarioReturn(b.price, b.nav, nc, tp);
    const out = [
      { label: "Total return", value: signPct(r.totalReturn, 0), cls: r.totalReturn >= 0 ? "" : "",
        note: "from today's " + usd(b.price) },
      { label: "Implied VCX price", value: usd(r.newPrice), note: "new NAV " + usd(r.newNav) + " × (1+prem)" },
      { label: "NAV change applied", value: signPct(nc, 0), note: "the AI re-rate leg" },
      { label: "Premium assumed", value: signPct(tp, 0), note: "vs " + signPct(curPrem, 0) + " now" },
    ];
    document.getElementById("scenario-out").innerHTML = out.map((c) =>
      `<div class="kpi"><div class="label">${c.label}</div>
        <div class="value" style="color:${c.label === "Total return" ? (r.totalReturn >= 0 ? GOOD : BAD) : TEXT}">${c.value}</div>
        <div class="note">${c.note}</div></div>`).join("");
    const compressing = tp < curPrem - 1e-9;
    document.getElementById("scenario-explain").innerHTML =
      (nc > 0 ? `A ${signPct(nc, 0)} NAV gain ` : nc < 0 ? `A ${signPct(nc, 0)} NAV drop ` : "Flat NAV ")
      + (compressing
          ? `with the premium compressing from ${signPct(curPrem, 0)} to ${signPct(tp, 0)} → <b>${signPct(r.totalReturn, 0)}</b>. `
            + (nc > 0 && r.totalReturn < 0 ? "Note: you're <b>right on the AI and still lose</b> — the premium dominates." : "")
          : `with the premium held at ${signPct(tp, 0)} → <b>${signPct(r.totalReturn, 0)}</b>.`);
  };
  navc.oninput = update; prem.oninput = update;
  document.getElementById("b-hold").onclick = () => { prem.value = curPrem; update(); };
  document.getElementById("b-half").onclick = () => { prem.value = (curPrem / 2).toFixed(2); update(); };
  document.getElementById("b-zero").onclick = () => { prem.value = 0; update(); };
  update();
}

boot();
