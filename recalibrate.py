"""
Daily SpaceX-weight RECALIBRATION -> dashboard/data/recalibration.json

The daily_nav_log answers "given an assumed weighting, what NAV do we predict?".
This module runs the inverse problem and the part the user actually cares about:
each day the ACTUAL NAV (and AUM) arrives, we BACK-SOLVE what SpaceX weight /
SpaceX buy / net flow is required to explain it, and we record how that estimate
gets REVISED as data accumulates. It is the "iterative recalibration ledger".

WHY THIS IS A SEPARATE, NARROW PROBLEM (degrees of freedom)
-----------------------------------------------------------
Per trading day we observe TWO numbers: the NAV return and (when given) the AUM.
A fully-free model has ~25 unknowns/day (23 public weights + SpaceX weight + flow)
-> hopelessly underdetermined -> the "infinite solutions" the user flagged. So we
do NOT free the public weights daily. They are pinned to the DISCLOSED path
(3/31 -> 4/30 -> 5/31 NPORT/site snapshots) and only move at the monthly
disclosure cadence, because daily NAV data cannot resolve them faster than that.

That leaves the genuinely IDENTIFIABLE quantities, which is what we solve for:
  1. w_spx  -- the SpaceX weight (SpaceX is +19.6% on 6/15 vs a flat basket, so it
                dominates the NAV move and IS pinned by the data).
  2. flow   -- net subscriptions/redemptions (pinned by the AUM print).
  3. buy    -- a SpaceX purchase shows up as the gap between the back-solved
                start-of-day SpaceX $ and the mechanically carried (no-buy) value.

VOLATILITY-AWARE TOLERANCE (the regularization principle)
---------------------------------------------------------
If we ever DO let a public weight drift to absorb residual, the danger is the
optimizer abusing a HIGH-vol name (whose weight has big leverage on the NAV) to
fake the SpaceX signal -- especially TSLA, which co-moves with SpaceX. So the
drift budget is INVERSE to realized vol: high-vol names get a TIGHT tolerance
(pinned to disclosure), low-vol names a LOOSE one (they barely move the NAV and
are unidentifiable anyway). We compute realized daily vol from the reconstructed
price series and publish the per-name tolerance so the rule is transparent.
No trend bias: tolerances are symmetric and anchored to the disclosed weight.

Pure stdlib; network-free (prices reconstructed from hedge_book). ASCII only.
"""

import json
import os

import daily_nav_log as dl

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

PRIMARY = "fund_5_31"   # most-recent disclosure = headline basket; band spans all

# Append-only "vintage" log: each day's estimate is FROZEN the first time its
# actual NAV is known and is NEVER revised afterwards. This is the honest
# real-time / out-of-sample track record. The REVISED ledger (recomputed every
# build with all current data + assumptions) lives alongside it; the two coincide
# until a later filing, a re-mark, or the long-replication smoother rewrites
# history. Lives OUTSIDE the regenerated dashboard/data set so the build can't
# overwrite it (same pattern as morningstar_aum_log.jsonl).
VINTAGE_PATH = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data",
                            "recalibration_vintage.jsonl")

# Fields snapshotted into the frozen vintage row (a subset of the ledger row).
_VINTAGE_FIELDS = ("date", "spcx", "spcx_ret_pct", "basket_ret_pct", "basket_ret_band_pct",
                   "actual_nav", "navret_pct", "implied_w_spx_pct", "implied_w_spx_band_pct",
                   "carried_w_spx_pct", "w_spx_delta_pct", "implied_buy_m", "implied_buy_band_m",
                   "buy_attributed_to", "implied_net_flow_b", "interpretation")


def _basket_ret(W, prev_closes, closes):
    num = den = 0.0
    for t, w in W.items():
        a, b = prev_closes.get(t), closes.get(t)
        if a and b and w:
            num += w * (b / a - 1)
            den += w
    return num / den if den else 0.0


def _vol_tolerance(H):
    """Realized daily-return vol per name from the reconstructed series ->
    inverse-vol drift budget (high vol -> tight, low vol -> loose)."""
    legs = {l["ticker"].replace("/", "-"): l for l in H["legs"] if l["side"] == "short"}
    spnl = {p["ticker"].replace("/", "-"): p for p in H["short_legs_pnl"]}
    n = len(H["series"])
    vols = {}
    for t, l in legs.items():
        if not l.get("shares"):
            continue
        px = [l["entry_px"] + spnl[t]["pnl"][i] / l["shares"] for i in range(n)]
        rets = [px[i] / px[i - 1] - 1 for i in range(1, n) if px[i - 1]]
        if len(rets) > 1:
            m = sum(rets) / len(rets)
            vols[t] = (sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5 * 100
    med = sorted(vols.values())[len(vols) // 2] if vols else 1.0
    disc = dl._nospy(dl.fs.WEIGHTS_5_31)
    rows = []
    for t in sorted(vols, key=lambda k: -vols[k]):
        budget = med / vols[t]              # <1 tight (high vol), >1 loose (low vol)
        rows.append({"ticker": t, "daily_vol_pct": round(vols[t], 2),
                     "disclosed_wt_pct": round(disc.get(t, 0) * 100, 2),
                     "drift_budget": round(budget, 2),
                     "pinned": budget < 0.8})   # high-vol names held to disclosure
    return {"median_vol_pct": round(med, 2), "rows": rows,
            "note": ("Realized daily vol over %s..%s (reconstructed). Drift budget = "
                     "median_vol / name_vol: <1 = tight (pinned to disclosure, can't be "
                     "used to fake the SpaceX signal), >1 = loose (low impact on NAV, "
                     "unidentifiable anyway). Symmetric, anchored to the 5/31 disclosed "
                     "weight -> no trend bias.") % (H["series"][0]["date"], H["series"][-1]["date"])}


def _freeze_vintage(ledger):
    """Append-only: freeze each day's estimate the first time its actual NAV is
    known; never touch rows already frozen. Returns (vintage_rows, vintage_series)
    in date order. Rebuilding is idempotent (a frozen date is read verbatim)."""
    frozen = {}
    order = []
    if os.path.exists(VINTAGE_PATH):
        with open(VINTAGE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                frozen[r["date"]] = r
                order.append(r["date"])
    added = []
    for row in ledger:
        if row.get("implied_w_spx_pct") is None:
            continue
        if row["date"] in frozen:
            continue
        snap = {k: row[k] for k in _VINTAGE_FIELDS if k in row}
        frozen[row["date"]] = snap
        order.append(row["date"])
        added.append(snap)
    if added:
        os.makedirs(os.path.dirname(VINTAGE_PATH), exist_ok=True)
        with open(VINTAGE_PATH, "a", encoding="utf-8") as f:
            for snap in added:
                f.write(json.dumps(snap, ensure_ascii=False, allow_nan=False) + "\n")
    rows = [frozen[d] for d in sorted(set(order))]
    series = [{"date": r["date"], "implied_w_spx_pct": r["implied_w_spx_pct"],
               "lo": r["implied_w_spx_band_pct"][0], "hi": r["implied_w_spx_band_pct"][1]}
              for r in rows]
    return rows, series


def build_payload():
    WS, H = dl._weightings()
    methods = list(dl.METHOD_LABELS)
    B = dl.BASE
    prev = {"nav": B["nav"], "spcx": B["spcx"], "aum": B["aum"],
            "spx_value": B["spacex_value"], "closes": dl._base_closes(H)}

    ledger = []
    series = [{"date": B["date"], "carried_w_spx_pct": round(B["spacex_value"] / B["aum"] * 100, 2),
               "implied_w_spx_pct": None, "lo": None, "hi": None}]

    for e in dl.ENTRIES:
        spx_ret = e["spcx"] / prev["spcx"] - 1
        carried_w = prev["spx_value"] / prev["aum"]
        # basket return under every disclosed weighting -> a band
        brs = {m: _basket_ret(WS[m], prev["closes"], e["closes"]) for m in methods}
        rb_primary = brs[PRIMARY]
        actual = e.get("actual_nav")
        row = {"date": e["date"], "spcx": e["spcx"], "spcx_ret_pct": round(spx_ret * 100, 2),
               "prior_date": _prior_label(e), "prior_nav": prev["nav"],
               "carried_w_spx_pct": round(carried_w * 100, 2),
               "basket_ret_pct": round(rb_primary * 100, 3),
               "basket_ret_band_pct": [round(min(brs.values()) * 100, 3),
                                       round(max(brs.values()) * 100, 3)],
               "actual_nav": actual}

        if actual:
            navret = actual / prev["nav"] - 1
            # back-solve w_spx that explains the actual NAV, per basket -> band
            def solve(rb):
                return (navret - rb) / (spx_ret - rb)
            w_primary = solve(rb_primary)
            ws = [solve(rb) for rb in brs.values()]
            w_lo, w_hi = min(ws), max(ws)
            # implied start-of-day SpaceX $ and the buy gap vs the carried (no-buy) value
            sv_imp = w_primary * prev["aum"]
            buy = sv_imp - prev["spx_value"]
            buy_lo = w_lo * prev["aum"] - prev["spx_value"]
            buy_hi = w_hi * prev["aum"] - prev["spx_value"]
            # AUM / flow reconciliation
            exp_aum = prev["aum"] * (1 + navret)
            obs_aum = float(e["aum"]) if e.get("aum") else None
            net_flow = (obs_aum - exp_aum) if obs_aum else None
            row.update({
                "navret_pct": round(navret * 100, 3),
                "implied_w_spx_pct": round(w_primary * 100, 2),
                "implied_w_spx_band_pct": [round(w_lo * 100, 2), round(w_hi * 100, 2)],
                "w_spx_delta_pct": round((w_primary - carried_w) * 100, 2),
                "implied_spx_value_b": round(sv_imp / 1e9, 3),
                "implied_buy_m": round(buy / 1e6, 0),
                "implied_buy_band_m": [round(min(buy_lo, buy_hi) / 1e6, 0),
                                       round(max(buy_lo, buy_hi) / 1e6, 0)],
                "buy_attributed_to": row["prior_date"],
                "expected_aum_noflow_b": round(exp_aum / 1e9, 3),
                "observed_aum_b": round(obs_aum / 1e9, 3) if obs_aum else None,
                "implied_net_flow_b": round(net_flow / 1e9, 3) if net_flow is not None else None,
            })
            row["interpretation"] = _interpret(row)
            series.append({"date": e["date"], "carried_w_spx_pct": round(carried_w * 100, 2),
                           "implied_w_spx_pct": round(w_primary * 100, 2),
                           "lo": round(w_lo * 100, 2), "hi": round(w_hi * 100, 2)})
            # chain forward on the CORRECTED state (buy folded in, marked to SPCX)
            sv_end = sv_imp * (1 + spx_ret)
            base_nav = actual
            aum = obs_aum if obs_aum else exp_aum
            prev = {"nav": base_nav, "spcx": e["spcx"], "aum": aum,
                    "spx_value": sv_end, "closes": e["closes"]}
        else:
            # no actual yet: carry mechanically (no-buy), nothing to recalibrate
            sv_end = prev["spx_value"] * (1 + spx_ret)
            prev = {"nav": prev["nav"], "spcx": e["spcx"], "aum": prev["aum"],
                    "spx_value": sv_end, "closes": e["closes"]}
        ledger.append(row)

    vintage_rows, vintage_series = _freeze_vintage(ledger)
    belief = _belief(B, ledger)
    return {
        "meta": {
            "title": "Daily SpaceX-weight recalibration ledger",
            "primary_basket": PRIMARY,
            "headline": ("Each day's ACTUAL NAV + AUM, inverted to the SpaceX weight / SpaceX buy / "
                         "net flow needed to explain it -- and how that estimate is revised as data lands."),
            "two_views_note": ("AS-OF (vintage): every day's estimate is FROZEN the morning its actual NAV "
                               "lands and is never edited -- the honest real-time track record. REVISED "
                               "(all-data): the whole history is re-estimated each build with everything known "
                               "now. The two coincide until a later NPORT filing, a SpaceX re-mark, or the "
                               "long-replication smoother rewrites past days -- then the gap between them IS "
                               "the revision."),
            "method_labels": dl.METHOD_LABELS,
            "dof_note": ("2 observations/day (NAV return + AUM) vs ~25 free unknowns -> we DON'T free the "
                         "public weights daily; they stay pinned to the disclosed 3/31->4/30->5/31 path and "
                         "move only at the monthly disclosure cadence. We back-solve only the identifiable "
                         "trio: SpaceX weight, SpaceX buy, net flow."),
            "static_vs_dynamic": ("The public basket is treated as PIECEWISE-static (steps at each disclosure), "
                                  "because ~16 daily points can't resolve faster drift without over-fitting. "
                                  "The SpaceX weight IS time-varying and IS estimable -- it re-marks daily and "
                                  "jumps on a buy -- so that is the one weight we track as a live series."),
            "disclaimer": "Estimate, not the fund's record. AUM prints are coarse (0.1B) -> flow/buy bands are wide.",
        },
        "vol_tolerance": _vol_tolerance(H),
        "ledger": ledger,                       # REVISED (recomputed every build)
        "w_spx_series": series,                 # REVISED series
        "vintage_ledger": vintage_rows,         # AS-OF (frozen, append-only)
        "w_spx_series_vintage": vintage_series, # AS-OF series
        "belief": belief,
    }


def _prior_label(e):
    # the day whose close a buy is attributed to = the prior row's date
    # (first entry -> BASE date, else the previous entry's date)
    idx = dl.ENTRIES.index(e)
    return dl.BASE["date"] if idx == 0 else dl.ENTRIES[idx - 1]["date"]


def _interpret(r):
    parts = []
    d = r.get("w_spx_delta_pct")
    if d is not None:
        if d > 0.3:
            parts.append("NAV beats the no-buy carry by %.2fpt of SpaceX weight -> consistent with a SpaceX BUY of ~$%.0fM on %s (band $%.0f-%.0fM)."
                         % (d, r["implied_buy_m"], r["buy_attributed_to"], r["implied_buy_band_m"][0], r["implied_buy_band_m"][1]))
        elif d < -0.3:
            parts.append("NAV trails the carry by %.2fpt -> implies a SpaceX SELL / mark haircut of ~$%.0fM." % (-d, -r["implied_buy_m"]))
        else:
            parts.append("NAV matches the no-buy carry within %.2fpt -> no SpaceX trade needed to explain it." % abs(d))
    f = r.get("implied_net_flow_b")
    if f is not None:
        if f < -0.1:
            parts.append("AUM print implies a net OUTFLOW of ~$%.2fB (redemptions, likely met by selling public to keep SpaceX -> weight rises)." % (-f))
        elif f > 0.1:
            parts.append("AUM print implies a net INFLOW of ~$%.2fB (dilutes the SpaceX weight)." % f)
        else:
            parts.append("AUM print implies ~flat flows.")
    return " ".join(parts)


def _belief(B, ledger):
    """Prior (pre-data) vs posterior (after the latest recalibration) on the
    headline question: did Friday buy SpaceX, and how big is the redemption?"""
    last = next((r for r in reversed(ledger) if r.get("implied_w_spx_pct") is not None), None)
    if not last:
        return None
    return {
        "as_of": last["date"],
        "question": "Did 6/12 (Friday) buy SpaceX, and how large was the 6/15 redemption?",
        "prior": {"label": "Before %s data (mechanical no-buy carry)" % last["date"],
                  "w_spx_pct": round(B["spacex_value"] / B["aum"] * 100, 2),
                  "friday_buy_m": 0, "redemption_b": None},
        "posterior": {"label": "After %s NAV+AUM" % last["date"],
                      "w_spx_pct": last["implied_w_spx_pct"],
                      "w_spx_band_pct": last["implied_w_spx_band_pct"],
                      "friday_buy_m": last["implied_buy_m"],
                      "friday_buy_band_m": last["implied_buy_band_m"],
                      "redemption_b": last["implied_net_flow_b"]},
        "takeaway": ("6/15 NAV (%.2f) clears every public basket AND the perfect-fit band, so the beat is "
                     "SpaceX-side, not public-side. It is consistent with a Friday SpaceX BUY of ~$%.0fM "
                     "(raising the start-of-Monday SpaceX weight to ~%.1f%% from %.1f%%) plus a Monday net "
                     "outflow of ~$%.2fB met by trimming public holdings. Both rest on coarse 0.1B AUM "
                     "prints, so the buy/redemption sizes carry wide bands and will tighten as more days land."
                     % (last["actual_nav"], last["implied_buy_m"], last["implied_w_spx_pct"],
                        round(B["spacex_value"] / B["aum"] * 100, 1),
                        -(last["implied_net_flow_b"] or 0))),
    }


def write_json():
    payload = build_payload()
    out = os.path.join(_REPO_ROOT, "dashboard", "data", "recalibration.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return out


if __name__ == "__main__":
    pl = build_payload()
    print(pl["meta"]["title"])
    for r in pl["ledger"]:
        if r.get("implied_w_spx_pct") is not None:
            print(r["date"], "implied w_spx %.2f%% (band %.2f-%.2f) carried %.2f%% delta %+.2fpt | buy ~$%.0fM | flow %s"
                  % (r["implied_w_spx_pct"], r["implied_w_spx_band_pct"][0], r["implied_w_spx_band_pct"][1],
                     r["carried_w_spx_pct"], r["w_spx_delta_pct"], r["implied_buy_m"],
                     ("$%.2fB" % r["implied_net_flow_b"]) if r["implied_net_flow_b"] is not None else "n/a"))
            print("   ", r["interpretation"])
    b = pl["belief"]
    if b:
        print("BELIEF:", b["takeaway"])
    print("wrote", write_json())
