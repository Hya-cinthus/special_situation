"""
Hedge-drift analysis -> dashboard/data/hedge_drift.json

Your hedge is FIXED: long 130,000 BPTIX shares + a fixed-share short basket of
the fund's public holdings, both struck 2026-05-20. As the fund takes inflows and
SpaceX stays marked flat, the hedge stops being delta-neutral. This quantifies by
how much — and is careful to separate two very different numbers:

  (A) PER-SHARE drift  <-- this is YOUR hedge drift.
      You own a FIXED number of BPTIX shares. New fund inflows issue NEW shares to
      NEW investors and buy public stock with their cash; that does NOT add public
      exposure to your shares. Your per-share public exposure rises only because
      SpaceX (a fixed dollar mark) is diluted across more shares. So the public
      book embedded in *your* position, per share, is what your fixed short must
      match:
          public_per_share_t = (gross_total_assets_t - SpaceX_fixed) / shares_out_t
          hedge_drift_t       = public_per_share_t / public_per_share_entry - 1
      A +X% drift means your fixed short is X% too small -> an unintended +X% long
      public-beta tilt has crept into your book.

  (B) FUND-level public-book growth  <-- context only, NOT your drift.
      The fund's TOTAL public holdings = gross_total_assets - SpaceX_fixed. This
      grows much faster than (A) because it includes new investors' inflows you
      have no claim to. Reporting (B) as a hedge deviation overstates it ~3x.

Total assets come from the SAME reconstructed daily series the BPTRX main page
shows (no hand interpolation): the series carries total_nav_usd and
shares_outstanding for every day, and gross = total_nav_usd * leverage_ratio
reproduces the Morningstar override anchors exactly. So the 2026-05-20 entry is a
real reconstructed point, not a fabricated one.

Reads dashboard/data/spacex_baron.json (+ hedge_book.json for the live short
notional). Pure stdlib.
"""

import json
import os
import datetime

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
ENTRY = "2026-05-20"


def _load(name):
    with open(os.path.join(_REPO_ROOT, "dashboard", "data", name), encoding="utf-8") as f:
        return json.load(f)


def build_payload():
    base = _load("spacex_baron.json")
    ov = base["aum_overrides"]
    leverage = ov[0]["leverage_ratio"]                 # fund-level gross/net (~1.1358)
    spacex_fixed = ov[-1]["spacex_value_usd"]          # fixed private mark (NPORT gross LMV)

    # Daily reconstructed series (same one the main page renders). Every day has
    # net NAV and reconstructed shares outstanding -> a real 2026-05-20 point.
    srt = {r["date"]: r for r in base["series"]}
    dates = sorted(d for d in srt if d >= ENTRY)
    if ENTRY not in srt:
        raise RuntimeError("series has no %s row to anchor the entry" % ENTRY)

    def gross(d):
        return srt[d]["total_nav_usd"] * leverage      # reproduces override anchors
    def pub_total(d):
        return gross(d) - spacex_fixed                 # fund's total public holdings (gross)
    def shares(d):
        return srt[d]["shares_outstanding"]
    def pub_ps(d):
        return pub_total(d) / shares(d)                # public $ per BPTIX share

    pub_ps_entry = pub_ps(ENTRY)
    pub_total_entry = pub_total(ENTRY)

    # Actual fixed short (dollars) for the dollar-gap calc.
    try:
        short_notional = _load("hedge_book.json")["meta"]["short_notional"]
    except Exception:
        short_notional = None

    rows = []
    for d in dates:
        net = srt[d]["total_nav_usd"]
        g = gross(d)
        pub = pub_total(d)
        ps = pub_ps(d)
        hedge_drift = ps / pub_ps_entry - 1            # (A) YOUR drift
        fund_growth = pub / pub_total_entry - 1        # (B) context
        rows.append({
            "date": d,
            "gross_total_assets": round(g, 0),
            "net_nav": round(net, 0),
            "leverage_ratio": round(leverage, 4),      # assumed constant (last NPORT gross/net)
            "shares_out": round(shares(d), 0),
            "spacex_value": round(spacex_fixed, 0),    # fixed
            "public_total": round(pub, 0),
            "public_per_share": round(ps, 2),
            # composition as % of NET NAV (these three sum to 100%: public + spacex − borrowings)
            "spacex_weight_net": round(spacex_fixed / net, 4),
            "public_weight_net": round(pub / net, 4),
            "borrow_weight_net": round(-(leverage - 1), 4),
            # composition as % of GROSS total assets (spacex + public = 100%)
            "spacex_pct_gross": round(spacex_fixed / g, 4),
            "public_pct_gross": round(pub / g, 4),
            "hedge_drift": round(hedge_drift, 4),
            "fund_public_growth": round(fund_growth, 4),
            # dollars of short you'd need to ADD to re-neutralize (None if unknown)
            "underhedge_gap_usd": round(short_notional * hedge_drift, 0) if short_notional else None,
            "source": srt[d].get("source"),
        })

    # ---- Perfect-hedge share table (date x ticker) ----------------------------
    # Under the pro-rata assumption the public holdings keep their relative weights,
    # so a perfectly-sized short scales EVERY public name by the same per-share
    # drift factor: perfect_shares(tk, t) = current_shares(tk) * (1 + hedge_drift_t).
    # Your actual shares are fixed at entry, so the gap = what you'd need to add.
    perfect = None
    try:
        hb = _load("hedge_book.json")
        scale_by_date = {r["date"]: 1.0 + r["hedge_drift"] for r in rows}
        hdates = [d for d in (x["date"] for x in hb["series"]) if d in scale_by_date]
        short_legs = sorted(
            ({"ticker": l["ticker"], "shares": abs(l["shares"])}
             for l in hb["legs"] if l["side"] == "short"),
            key=lambda r: r["ticker"])
        legs_out = []
        for lg in short_legs:
            cur = lg["shares"]
            perfect_shares = [round(cur * scale_by_date[d]) for d in hdates]
            legs_out.append({
                "ticker": lg["ticker"],
                "current_shares": cur,                       # fixed since entry
                "perfect_shares": perfect_shares,            # per date in hdates
                "perfect_now": perfect_shares[-1] if perfect_shares else cur,
                "delta_now": (perfect_shares[-1] - cur) if perfect_shares else 0,
            })
        perfect = {
            "as_of": hdates[-1] if hdates else None,
            "dates": hdates,
            "scale_now": round(scale_by_date[hdates[-1]], 4) if hdates else None,
            "note": ("Perfect hedge = current shares x (1 + per-share drift). All public names scale "
                     "by the SAME factor under the pro-rata assumption; only the magnitude grows. "
                     "Delta = shares to ADD to each short to be neutral as of " + (hdates[-1] if hdates else "?") + "."),
            "legs": legs_out,
            "total_delta_shares": sum(l["delta_now"] for l in legs_out),
        }
    except Exception:
        perfect = None

    last = rows[-1] if rows else {}
    return {
        "meta": {
            "title": "Hedge drift — fixed short vs your per-share public exposure",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_date": ENTRY,
            "leverage_ratio": round(leverage, 6),
            "spacex_fixed_usd": round(spacex_fixed, 0),
            "short_notional_usd": round(short_notional, 0) if short_notional else None,
            "public_per_share_entry": round(pub_ps_entry, 2),
            "assumption": ("Every change in the fund's Total Assets is allocated PRO-RATA across the "
                           "publicly-tradable holdings; the private (SpaceX) stake stays fixed. Total "
                           "assets per day = net NAV (reconstructed daily series, same as the BPTRX main "
                           "page) x leverage ratio %.4f, which reproduces the Morningstar override anchors "
                           "exactly. So the %s entry is a real reconstructed point." % (leverage, ENTRY)),
            "method_note": ("PER-SHARE drift is YOUR hedge drift: you hold a FIXED share count, so fund "
                            "inflows (new shares to new investors) do not add public exposure to your "
                            "shares — only SpaceX dilution per share does. FUND-level public-book growth "
                            "is shown as context; it includes inflows you have no claim to and overstates "
                            "the hedge gap ~3x."),
            "disclaimer": ("Analysis, not investment advice. SpaceX held fixed at its last NPORT gross LMV "
                           "(~$%.2fB); shares outstanding are reconstructed; pro-rata public allocation is a "
                           "simplification (the manager may not rebalance exactly pro-rata). Model, not a "
                           "statement of record." % (spacex_fixed / 1e9)),
            "last_data_day": last.get("date"),
        },
        "kpis": {
            "as_of": last.get("date"),
            "hedge_drift": last.get("hedge_drift"),                 # (A) the headline
            "underhedge_gap_usd": last.get("underhedge_gap_usd"),
            "public_per_share_now": last.get("public_per_share"),
            "leverage_ratio": round(leverage, 4),
            "spacex_weight_net_now": last.get("spacex_weight_net"),
            "spacex_weight_net_entry": rows[0]["spacex_weight_net"] if rows else None,
            "public_weight_net_now": last.get("public_weight_net"),
            "public_weight_net_entry": rows[0]["public_weight_net"] if rows else None,
            "fund_public_growth": last.get("fund_public_growth"),   # (B) the context
        },
        "series": rows,
        "perfect_hedge": perfect,
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "hedge_drift.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    m, k = pl["meta"], pl["kpis"]
    print("leverage %.4f | SpaceX fixed $%.2fB | entry public/share $%.2f"
          % (m["leverage_ratio"], m["spacex_fixed_usd"] / 1e9, m["public_per_share_entry"]))
    print("%-11s %9s %8s %10s %9s %11s %11s"
          % ("date", "grossTA", "sharesM", "pub/share", "spxWt", "hedgeDrift", "fundGrowth"))
    for r in pl["series"]:
        print("%-11s $%7.1fB %8.2f $%9.2f %8.1f%% %+10.1f%% %+10.1f%%"
              % (r["date"], r["gross_total_assets"] / 1e9, r["shares_out"] / 1e6,
                 r["public_per_share"], r["spacex_weight_net"] * 100,
                 r["hedge_drift"] * 100, r["fund_public_growth"] * 100))
    print("\nHEADLINE: your fixed short is %+.1f%% too small (per-share) -> add ~$%.2fM to re-neutralize."
          % (k["hedge_drift"] * 100, (k["underhedge_gap_usd"] or 0) / 1e6))
    print("Context (fund-level public book grew %+.1f%% — mostly inflows, NOT your drift)."
          % (k["fund_public_growth"] * 100))
    p = write_json()
    print("wrote", p)
