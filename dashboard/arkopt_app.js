"use strict";

/* ARKK JUN-18-26 options scenario. Reads data/ark_options.json.
 * Delta-neutral P&L vs spot (X) per option, with a borrow toggle (the 2nd axis).
 * Sticky-strike IV; borrow acts via the forward. Client interpolates borrow. */

const SPX = "#ff7a45", ACC = "#4da3ff", GOOD = "#3fb950", MUTED = "#8b97a7",
      WARN = "#d29922", BAD = "#f85149", PURPLE = "#bb86fc", TEAL = "#2dd4bf";
const PLOT_BG = "#161b22", GRID = "#2a3343", TEXT = "#e6edf3";
let DATA = null, SEL = {};   // selected option keys -> on/off

const OPTCOLOR = {
  "Call 78": "#ff7a45", "Put 78": "#ffb088",
  "Call 80": "#4da3ff", "Put 80": "#9ecbff",
  "Call 83": "#3fb950", "Put 83": "#86e0a0",
};
const pctp = (x, d = 0) => (x * 100).toFixed(d) + "%";

async function boot() { await load("data/ark_options.json"); }

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

/* interpolate an option's P&L curve at an arbitrary borrow between precomputed levels */
function pnlAtBorrow(opt, borrow) {
  const levels = DATA.meta.borrow_levels;        // ascending
  const key = (b) => String(Math.round(b * 10000));
  if (borrow <= levels[0]) return opt.scenarios[key(levels[0])].pnl;
  if (borrow >= levels[levels.length - 1]) return opt.scenarios[key(levels[levels.length - 1])].pnl;
  let i = 0; while (i < levels.length - 1 && levels[i + 1] < borrow) i++;
  const a = levels[i], b = levels[i + 1], w = (borrow - a) / (b - a);
  const pa = opt.scenarios[key(a)].pnl, pb = opt.scenarios[key(b)].pnl;
  return pa.map((v, j) => v + (pb[j] - v) * w);
}

function render() {
  const m = DATA.meta;
  document.getElementById("disclaimer").textContent = m.disclaimer;
  document.getElementById("gen").textContent = "Generated " + m.generated_at;
  // default selection: all six on
  DATA.options.forEach((o) => { SEL[o.label] = true; });
  renderControls();
  renderCalib();
  redraw();
}

function renderControls() {
  const m = DATA.meta;
  document.getElementById("b-txt").textContent = pctp(m.borrow0, 0);
  document.getElementById("b-slider").value = m.borrow0;
  // option toggles
  document.getElementById("opt-toggles").innerHTML = DATA.options.map((o) =>
    `<label class="optchk"><input type="checkbox" data-opt="${o.label}" checked>
       <span style="color:${OPTCOLOR[o.label]}">${o.label}</span>
       <span class="dim">Δ${o.delta0 >= 0 ? "+" : ""}${o.delta0.toFixed(2)} · iv ${pctp(o.iv, 1)}</span></label>`).join("");
  document.querySelectorAll("#opt-toggles input").forEach((c) => {
    c.onchange = () => { SEL[c.dataset.opt] = c.checked; redraw(); };
  });
  document.getElementById("b-slider").oninput = redraw;
  document.querySelectorAll("#b-presets button").forEach((b) => {
    b.onclick = () => { document.getElementById("b-slider").value = b.dataset.b; redraw(); };
  });
}

function redraw() {
  const m = DATA.meta;
  const borrow = +document.getElementById("b-slider").value;
  document.getElementById("b-txt").textContent = pctp(borrow, borrow < 0.1 ? 1 : 0);
  const fwd = m.spot0 * Math.exp((m.rate - (borrow - m.div)) * m.t_years);
  document.getElementById("fwd-readout").innerHTML =
    `Forward at <b>${pctp(borrow, borrow < 0.1 ? 1 : 0)}</b> borrow = <b>$${fwd.toFixed(2)}</b> `
    + `<span class="dim">(spot $${m.spot0}; base 2% → $${(m.spot0 * Math.exp((m.rate - (m.borrow0 - m.div)) * m.t_years)).toFixed(2)}). `
    + `Higher borrow ⇒ lower forward ⇒ puts gain, calls lose.</span>`;

  const traces = DATA.options.filter((o) => SEL[o.label]).map((o) => ({
    x: m.spot_grid, y: pnlAtBorrow(o, borrow),
    name: o.label, type: "scatter", mode: "lines",
    line: { color: OPTCOLOR[o.label], width: 2, dash: o.type === "p" ? "dot" : "solid" },
    hovertemplate: o.label + "<br>spot %{x:.2f}<br>P&L $%{y:.2f}<extra></extra>",
  }));
  const shapes = [
    { type: "line", x0: m.spot0, x1: m.spot0, yref: "paper", y0: 0, y1: 1,
      line: { color: MUTED, width: 1, dash: "dash" } },
    { type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: GRID, width: 1 } },
  ];
  Plotly.newPlot("chart", traces, {
    paper_bgcolor: PLOT_BG, plot_bgcolor: PLOT_BG, font: { color: TEXT, size: 11 },
    hovermode: "x unified", hoverlabel: { bgcolor: "#0e1117", bordercolor: GRID },
    shapes,
    annotations: [{ x: m.spot0, y: 1, yref: "paper", text: "spot " + m.spot0, showarrow: false,
                    font: { color: MUTED, size: 10 }, xanchor: "left", yanchor: "top" }],
    xaxis: { title: "ARKK spot ($)", gridcolor: GRID, color: TEXT },
    yaxis: { title: "Delta-neutral P&L ($/share)", gridcolor: GRID, color: TEXT, zeroline: false },
    legend: { orientation: "h", y: 1.12, font: { color: TEXT } },
    margin: { t: 40, r: 16, b: 44, l: 60 },
  }, { responsive: true, displayModeBar: false, displaylogo: false });
}

function renderCalib() {
  const m = DATA.meta;
  document.getElementById("calib").innerHTML = `
    <div class="calibrow">
      <span><span class="dim">Spot</span> $${m.spot0}</span>
      <span><span class="dim">Expiry</span> JUN-18-26 (${m.t_business_days} bd)</span>
      <span><span class="dim">Rate</span> ${pctp(m.rate, 2)}</span>
      <span><span class="dim">Borrow (base)</span> ${pctp(m.borrow0, 1)}</span>
      <span><span class="dim">IV skew</span> put~40 / ATM~37.7 / call~36</span>
      <span><span class="dim">IV</span> sticky-strike (fixed)</span>
    </div>`;
}

boot();
