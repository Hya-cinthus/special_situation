"""
Daily BPTIX NAV-estimate log -> dashboard/data/daily_nav_log.json

Each trading day the user pastes that day's public-holding closes + the SPCX close.
For every basket-weighting mechanism we've tried (actual hedge, fund 3/31, 4/30,
5/31, blend, optimal), we predict the day's BPTIX NAV and record it; when the real
NAV is known it goes in the last column and we score each basket's error. Append a
new dict to ENTRIES each day — that's the whole workflow.

Prediction (chained off the prior day's ACTUAL NAV where known):
    NAV_t = NAV_{t-1} x (1 + w_spx x spcx_return + (1 - w_spx) x basket_return)
SpaceX is marked to the live SPCX close (re-marks daily now it's public). w_spx is
carried from the reconstruction and updated each day (SpaceX value x SPCX move /
AUM grown by the NAV move; no-flows approx until the Morningstar AUM is supplied).
Public weights drop the SPY residual and renormalize over the 23 real names (per
the user's preference). Pure stdlib; the 6/12 base closes are read from hedge_book.
"""

import json
import os

import fund_snapshots as fs

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# Base = last fully-known day BEFORE the backtest window (6/5 Fri close, the Friday
# before the IPO week). spcx here is the $135 IPO-price mark (SpaceX was still PRIVATE
# 6/5-6/11, held flat at the 6/4 re-mark), and spacex_value is that $135 mark off the
# 3/31 disclosed share count. The window then walks 6/8 -> 6/22 (the IPO week + after);
# the IPO first trade (6/12) and the Friday buy are injected on 6/12 below, NOT here.
BASE = {"date": "2026-06-05", "nav": 276.32, "spcx": 135.0, "aum": 18.6e9,
        "spacex_value": 3.89026788e9 * (135.0 / 105.32)}   # ~$4.987B, the 6/4 IPO-price mark

# Days backfilled from contemporaneous records (git commits + the Morningstar AUM log),
# NOT real-time daily-log vintages. Public closes are reconstructed from hedge_book.json
# (entry_px + the day's short-leg PnL/shares — EXACT, validated against the 6/15 paste);
# BPTIX NAV from nav_daily.csv; AUM from the Morningstar log. These get an as-of seed
# (below) so as-of vs revised diverge correctly on 6/12.
BACKFILL_DATES = {"2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"}

# NEW ASSUMPTION (2026-06-16): 6/15's actual NAV cleared every no-buy basket AND the
# perfect-fit band, so 6/12 (Friday) DID add SpaceX. The recalibration back-solves
# ~$262M (band $259-344M). It is injected ON 6/12 (the day it happened) via that entry's
# `spacex_buy_usd`, lifting end-of-day SpaceX shares ~36.9M -> ~38.6M and the carried
# weight 29.1% (no buy) -> 30.4% into 6/15. The as-of seed books NO buy (we didn't know
# until 6/16), so 6/12 as-of vs revised differ. Adjust this as the calibration tightens.
FRIDAY_SPACEX_BUY = 0.262e9

# START-OF-DAY leverage assumption = gross holdings / net assets entering the day
# (BEFORE that day's redemptions, which are forward-priced at the close and don't
# touch the day's return). Public sleeve weight of net = LEVERAGE - w_spx; the
# remainder (1 - LEVERAGE) is net cash earning ~0.
# Leverage is a SINGLE fund-level number (gross/net) applied to EVERY basket weighting on a
# given day. It is TIME-VARYING, and the STABLE quantity is the BORROWINGS $ (the debt), not L:
# a redemption met by SELLING holdings drops gross and net by the same $, so borrowings are
# unchanged and L = 1 + Borrowings/Net DRIFTS UP as redemptions shrink net.
#   <=6/15   : 0.968 — the 5/31-disclosed ~3.2% net-cash buffer (~$0.65B).
#   6/16-6/25: 1.00  — the first redemption (6/15 ~$0.94B) exhausted the buffer (6/17 confirmed).
#   >=6/26   : 1 + BORROWINGS/net — the fund RE-LEVERED (drew ~$1.15B debt) back toward its
#             ~1.13 mandate. BORROWINGS pinned two ways that agree: (a) 6/30 gross-net =
#             SpaceX$/0.329 - net ~$1.08B; (b) an OLS of NAV returns on [SPCX ret, 6/30-basket
#             ret] => L 1.068 over recent net ~$17.8B => ~$1.2B. Central ~$1.15B (band $1.0-1.4B).
BORROWINGS_USD = 1.15e9
def LEVERAGE_FOR(date, net_aum=None):
    if date <= "2026-06-15":
        return 0.968
    if date <= "2026-06-25":
        return 1.00
    if net_aum:
        return 1.0 + BORROWINGS_USD / net_aum   # drifts up as redemptions shrink net
    return 1.06                                  # fallback if net unknown

# Append-only AS-OF (vintage) log: each day's estimate frozen as first reported, so
# revising an assumption (Friday buy, leverage, ...) never erases what we estimated
# that day. Seeded with 6/15 (no-buy) + 6/16 (pre-leverage); future days auto-freeze.
_VINTAGE_PATH = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "daily_nav_vintage.jsonl")

# Append one dict per trading day. closes = {ticker: close} for the 23 public names
# (Yahoo-style tickers, HEI/A -> HEI-A). spcx = SPCX close. actual_nav = BPTIX NAV
# (None until known). aum = Morningstar Total Assets (optional; improves w_spx).
# note = the day's "what's new" (information added / what changed in the assumptions).
ENTRIES = [
    # ---- BACKFILL: the IPO week (6/8-6/12). Pre-IPO (6/8-6/11) SpaceX is PRIVATE, held
    # flat at the $135 IPO-price mark -> SPCX "price" = 135 (0% SpaceX return), so these
    # days test the PUBLIC basket alone. 6/12 = IPO first trade (SPCX $160.95) + the
    # Friday buy. Closes reconstructed from hedge_book.json; NAV from nav_daily.csv (BPTIX);
    # AUM from the Morningstar log. -----------------------------------------------------
    {"date": "2026-06-08", "spcx": 135.0, "actual_nav": 276.38, "aum": 18.6e9,
     "closes": {"ACGL": 89.61, "BIRK": 43.66, "CHH": 105.42, "CSGP": 33.39, "FDS": 246.38,
                "FIG": 21.10, "GLPI": 46.55, "GWRE": 127.19, "H": 193.72, "HEI": 323.50,
                "HEI-A": 239.50, "IDXX": 561.17, "IT": 160.35, "KNSL": 299.07, "MSCI": 602.94,
                "MTN": 137.21, "ONON": 37.11, "RRR": 58.09, "SCHW": 88.08, "SHOP": 110.78,
                "SPOT": 503.13, "TSLA": 408.95, "VRSK": 178.97},
     "note": "BACKFILL (pre-IPO). SpaceX still PRIVATE, held flat at the $135 IPO-price mark "
             "(first public trade is 6/12) -> this day tests the PUBLIC basket alone. NAV +0.02% "
             "(~flat: TSLA +4.6% offset by others). AUM 18.6B (NET). What we knew then: SpaceX wt "
             "~26.8%, leverage 0.968 (the 5/31 disclosure)."},
    {"date": "2026-06-09", "spcx": 135.0, "actual_nav": 275.97, "aum": 18.8e9,
     "closes": {"ACGL": 90.41, "BIRK": 45.20, "CHH": 108.58, "CSGP": 33.93, "FDS": 246.07,
                "FIG": 20.49, "GLPI": 47.82, "GWRE": 124.51, "H": 194.08, "HEI": 326.42,
                "HEI-A": 241.83, "IDXX": 578.89, "IT": 157.40, "KNSL": 303.25, "MSCI": 607.54,
                "MTN": 131.26, "ONON": 38.25, "RRR": 59.77, "SCHW": 88.77, "SHOP": 110.42,
                "SPOT": 496.22, "TSLA": 396.68, "VRSK": 182.55},
     "note": "BACKFILL (pre-IPO). SpaceX flat at $135. NAV -0.15%. AUM 18.6B->18.8B (inflows "
             "continuing). Public basket alone."},
    {"date": "2026-06-10", "spcx": 135.0, "actual_nav": 273.78, "aum": 18.7e9,
     "closes": {"ACGL": 91.31, "BIRK": 43.95, "CHH": 104.23, "CSGP": 34.23, "FDS": 249.08,
                "FIG": 19.79, "GLPI": 48.41, "GWRE": 116.59, "H": 190.63, "HEI": 320.88,
                "HEI-A": 237.45, "IDXX": 556.94, "IT": 154.91, "KNSL": 313.57, "MSCI": 608.52,
                "MTN": 135.89, "ONON": 38.00, "RRR": 62.08, "SCHW": 89.27, "SHOP": 108.20,
                "SPOT": 503.10, "TSLA": 381.59, "VRSK": 183.13},
     "note": "BACKFILL (pre-IPO). SpaceX flat at $135. NAV -0.79% (TSLA -3.7% led it down). "
             "AUM 18.8B->18.7B. Public basket alone."},
    {"date": "2026-06-11", "spcx": 135.0, "actual_nav": 274.89, "aum": 19.0e9,
     "closes": {"ACGL": 91.13, "BIRK": 46.21, "CHH": 107.41, "CSGP": 32.65, "FDS": 236.64,
                "FIG": 19.34, "GLPI": 47.87, "GWRE": 118.52, "H": 197.86, "HEI": 339.22,
                "HEI-A": 251.05, "IDXX": 557.91, "IT": 148.81, "KNSL": 310.66, "MSCI": 594.31,
                "MTN": 136.34, "ONON": 39.21, "RRR": 62.32, "SCHW": 88.70, "SHOP": 110.47,
                "SPOT": 486.00, "TSLA": 399.15, "VRSK": 182.00},
     "note": "BACKFILL (pre-IPO). SpaceX flat at $135 — the LAST private day (first trade is "
             "tomorrow). NAV +0.41%. AUM 18.7B->19.0B (inflows). Carried SpaceX wt ~26.25%."},
    {"date": "2026-06-12", "spcx": 160.95, "actual_nav": 289.98, "aum": 20.4e9,
     "spacex_buy_usd": FRIDAY_SPACEX_BUY,
     "closes": {"ACGL": 91.66, "BIRK": 48.75, "CHH": 109.56, "CSGP": 32.84, "FDS": 241.16,
                "FIG": 18.54, "GLPI": 47.47, "GWRE": 122.56, "H": 199.36, "HEI": 331.61,
                "HEI-A": 247.09, "IDXX": 560.88, "IT": 148.17, "KNSL": 311.38, "MSCI": 599.12,
                "MTN": 133.31, "ONON": 38.58, "RRR": 63.11, "SCHW": 91.10, "SHOP": 108.24,
                "SPOT": 482.00, "TSLA": 406.43, "VRSK": 183.80},
     "note": "BACKFILL — IPO FRIDAY. SpaceX (SPCX) first public trade, closed $160.95 (+19.2% vs "
             "the $135 IPO) -> the SpaceX leg now marks to the live market. NAV +5.49%, almost all "
             "the SpaceX re-mark; AUM 19.0B->20.4B. AS-OF vs REVISED DIVERGE HERE: at the time we "
             "booked NO IPO add; the 6/16 recalibration later back-solved a ~$262M Friday SpaceX "
             "buy. Revised folds it in (end-of-day shares 36.9M->38.6M; carried weight 29.1%->30.4% "
             "into 6/15); as-of leaves it out. The day's ENTERING weight (26.25%) is the same either "
             "way — the buy executes at the close, so it only changes shares-out and the carry."},
    {"date": "2026-06-15", "spcx": 192.50, "actual_nav": 307.55, "aum": 20.7e9,
     "closes": {"ACGL": 91.50, "BIRK": 47.93, "CHH": 112.00, "CSGP": 32.04, "FDS": 235.86,
                "FIG": 18.51, "GLPI": 46.74, "GWRE": 120.03, "H": 198.95, "HEI": 336.18,
                "HEI-A": 248.73, "IDXX": 570.00, "IT": 142.77, "KNSL": 311.83, "MSCI": 611.17,
                "MTN": 134.40, "ONON": 38.69, "RRR": 61.13, "SCHW": 90.95, "SHOP": 112.49,
                "SPOT": 479.85, "TSLA": 411.15, "VRSK": 180.46},
     "note": "Actual NAV 307.55 + AUM 20.7B in. NEW: it cleared every no-buy basket AND the perfect-fit band "
             "-> Friday DID buy SpaceX (~$262M); w_spx raised 29.1%->30.4%. Implied ~$0.9B Monday outflow."},
    {"date": "2026-06-16", "spcx": 201.80, "actual_nav": 312.60, "aum": 20.6e9,
     "closes": {"ACGL": 92.58, "BIRK": 48.97, "CHH": 116.07, "CSGP": 31.97, "FDS": 237.56,
                "FIG": 17.98, "GLPI": 46.73, "GWRE": 117.46, "H": 197.03, "HEI": 335.53,
                "HEI-A": 248.11, "IDXX": 573.00, "IT": 142.24, "KNSL": 312.69, "MSCI": 608.16,
                "MTN": 136.68, "ONON": 38.06, "RRR": 60.92, "SCHW": 93.67, "SHOP": 113.23,
                "SPOT": 469.81, "TSLA": 404.66, "VRSK": 179.61},
     "note": "Actual NAV 312.60 in (our estimate was 312.5 — nailed it). SPCX +4.8% = Bloomberg $201.80; "
             "Yahoo's $192.50 is STALE (the +1.64% NAV on a ~flat public basket can only come from SpaceX rising). "
             "AUM 20.7B->20.6B vs NAV +1.64% => ~$0.44B outflow (redemptions continue; public trimmed)."},
    {"date": "2026-06-17", "spcx": 191.82, "actual_nav": 302.28, "aum": 19.6e9,
     "closes": {"ACGL": 92.37, "BIRK": 46.95, "CHH": 113.79, "CSGP": 30.46, "FDS": 228.30,
                "FIG": 18.65, "GLPI": 45.26, "GWRE": 111.17, "H": 201.88, "HEI": 337.33,
                "HEI-A": 248.14, "IDXX": 546.09, "IT": 133.58, "KNSL": 309.22, "MSCI": 596.89,
                "MTN": 129.93, "ONON": 37.72, "RRR": 59.13, "SCHW": 94.51, "SHOP": 108.09,
                "SPOT": 455.60, "TSLA": 396.38, "VRSK": 175.35},
     "note": "Actual NAV 302.28 in. LEVERAGE PINNED: on this first big-down-basket day the actual matched the "
             "L=1.0 estimate (302.3), NOT L=0.968 (302.5) -> implied L=1.009, so leverage is now ~1.0 (net-cash "
             "buffer consumed by redemptions). AUM 20.6B->19.6B vs NAV -3.30% => ~$0.32B more outflow "
             "(cumulative ~$1.7B since 6/12). w_spx now ~38%."},
    {"date": "2026-06-18", "spcx": 185.00, "actual_nav": 298.47, "aum": 19.1e9,
     "closes": {"ACGL": 91.18, "BIRK": 46.11, "CHH": 115.00, "CSGP": 30.12, "FDS": 221.29,
                "FIG": 18.88, "GLPI": 44.59, "GWRE": 107.86, "H": 202.09, "HEI": 337.10,
                "HEI-A": 247.58, "IDXX": 562.09, "IT": 127.49, "KNSL": 308.85, "MSCI": 581.19,
                "MTN": 144.78, "ONON": 38.88, "RRR": 61.33, "SCHW": 91.70, "SHOP": 108.85,
                "SPOT": 468.08, "TSLA": 400.49, "VRSK": 173.80},
     "note": "Actual NAV 298.47 (our estimate 298.36, err +0.11). AUM 19.6B->19.1B vs NAV -1.26% => ~$0.25B "
             "more outflow (cumulative ~$1.95B since 6/12; redemptions continue). SPCX -3.6% (185.00). RONB "
             "cross-check agreed. 6/19 = Juneteenth holiday (no trading)."},
    {"date": "2026-06-22", "spcx": 154.60, "actual_nav": 277.76, "aum": 17.7e9,
     "closes": {"ACGL": 92.04, "BIRK": 43.30, "CHH": 109.88, "CSGP": 29.22, "FDS": 218.62,
                "FIG": 19.08, "GLPI": 44.19, "GWRE": 102.69, "H": 196.33, "HEI": 331.15,
                "HEI-A": 242.12, "IDXX": 545.73, "IT": 125.79, "KNSL": 295.05, "MSCI": 580.85,
                "MTN": 141.67, "ONON": 36.21, "RRR": 60.45, "SCHW": 92.03, "SHOP": 107.98,
                "SPOT": 459.34, "TSLA": 405.05, "VRSK": 168.99},
     "note": "Actuals in: BPTIX NAV 277.76 (our estimate ~277.8 — nailed it; fund 5/31 exact, optimal +0.03), "
             "AUM 17.7B. BIG DOWN day: SPCX -16.4% (185.00->154.60, SpaceX cratered after the Juneteenth break) + "
             "public basket broadly down (BIRK -7.8%, GWRE/KNSL -4.5%, IDXX/VRSK/CHH ~-3%; TSLA/SPOT/MSCI ~flat). "
             "AUM 19.1B->17.7B vs NAV -6.94% => only ~$0.08B net OUTFLOW (redemptions SLOWING; cumulative ~$2.0B "
             "since 6/12). Leverage holds ~1.0: this big-down day matched the L=1.0 estimate (had the fund levered "
             "UP to meet redemptions, the actual would print BELOW it). Ignored 7 non-BPTIX tickers in the paste "
             "(AAPL/AMZN/AVGO/GOOG/MU/NVDA/ORCL — not fund holdings)."},
    {"date": "2026-06-23", "spcx": 156.11, "actual_nav": 277.81, "aum": 17.5e9,
     "closes": {"ACGL": 93.71, "BIRK": 42.35, "CHH": 111.60, "CSGP": 30.26, "FDS": 218.15,
                "FIG": 18.99, "GLPI": 44.71, "GWRE": 109.63, "H": 198.05, "HEI": 334.17,
                "HEI-A": 246.24, "IDXX": 541.31, "IT": 129.18, "KNSL": 304.48, "MSCI": 581.51,
                "MTN": 142.39, "ONON": 35.14, "RRR": 61.02, "SCHW": 93.17, "SHOP": 107.68,
                "SPOT": 455.50, "TSLA": 381.61, "VRSK": 174.76},
     "note": "Actuals in: BPTIX NAV 277.81 (our estimate ~277.4, within the perfect-fit band; ~flat as predicted), "
             "AUM 17.5B. SPCX +0.98% (154.60->156.11, SpaceX steadied after the 6/22 crater) = +0.33% contribution, "
             "roughly offsetting the public basket ~-0.7%: TSLA -5.8% (the ~28% weight) cushioned by GWRE +6.8%, "
             "VRSK +3.4%, KNSL +3.2%, IT +2.7%, ACGL +1.8%; ONON -3.0%, BIRK -2.2% the other way. AUM 17.7B->17.5B "
             "vs NAV +0.02% => ~$0.2B net OUTFLOW (redemptions continue, modest; cumulative ~$2.2B since 6/12). "
             "Leverage holds ~1.0 (flat-NAV day isn't a strong test, but the estimate matched)."},
    {"date": "2026-06-24", "spcx": 154.54, "actual_nav": 277.73, "aum": 17.4e9,
     "closes": {"ACGL": 94.92, "BIRK": 45.09, "CHH": 112.04, "CSGP": 29.81, "FDS": 216.45,
                "FIG": 18.64, "GLPI": 45.37, "GWRE": 110.33, "H": 197.32, "HEI": 335.30,
                "HEI-A": 245.97, "IDXX": 549.16, "IT": 130.47, "KNSL": 310.39, "MSCI": 577.29,
                "MTN": 144.24, "ONON": 36.92, "RRR": 62.50, "SCHW": 91.39, "SHOP": 114.17,
                "SPOT": 455.01, "TSLA": 375.53, "VRSK": 180.06},
     "note": "Actuals in: BPTIX NAV 277.73 (-0.03%, ~flat; our estimate ~277.3, fund-5/31 closest), AUM 17.4B. "
             "SPCX -1.01% (156.11->154.54) = -0.35% contribution, ~offset by a slightly POSITIVE public basket "
             "(BIRK +6.5%, SHOP +6.0%, ONON +5.1%, VRSK/RRR/KNSL/IDXX up vs TSLA -1.6%, SCHW -1.9%). AUM 17.5B->"
             "17.4B vs flat NAV => ~$0.1B net OUTFLOW (modest; cumulative ~$2.3B since 6/12). Leverage holds ~1.0."},
    {"date": "2026-06-25", "spcx": 153.00, "actual_nav": 273.22, "aum": 17.0e9,
     "closes": {"ACGL": 94.33, "BIRK": 44.52, "CHH": 111.18, "CSGP": 28.64, "FDS": 208.84,
                "FIG": 16.84, "GLPI": 45.06, "GWRE": 110.10, "H": 197.01, "HEI": 342.45,
                "HEI-A": 257.47, "IDXX": 554.94, "IT": 126.63, "KNSL": 308.43, "MSCI": 544.56,
                "MTN": 133.34, "ONON": 36.58, "RRR": 63.57, "SCHW": 89.44, "SHOP": 111.62,
                "SPOT": 441.21, "TSLA": 375.12, "VRSK": 177.04},
     "note": "Actuals in: BPTIX NAV 273.22 (-1.62%), AUM 17.0B. NOTABLE — first clearly one-directional miss: actual "
             "came in ~0.8 BELOW our L=1.0 median (274.0) and just under the perfect-fit floor (273.4); EVERY basket "
             "overestimated. On this high-dispersion down day (MSCI -5.7%, MTN -7.6%, FIG -9.7%) the likeliest cause "
             "is the fund being tilted toward the day's big LOSERS more than the stale 3/31-5/31 NPORT snapshots "
             "capture (basket drift) — for L=1.0 the true public sleeve would need ~-1.9% vs our snapshots' -1.3/-1.6% "
             "— with a possible small leverage uptick; one high-dispersion day can't separate the two. Keeping L=1.0 "
             "(won't refit on one ambiguous day); watch the next down-basket day. AUM 17.4B->17.0B vs NAV -1.62% => "
             "~$0.12B net outflow (cumulative ~$2.4B since 6/12)."},
    {"date": "2026-06-26", "spcx": 153.23, "actual_nav": 279.94, "aum": 17.4e9,
     "closes": {"ACGL": 97.54, "BIRK": 44.42, "CHH": 112.72, "CSGP": 30.25, "FDS": 231.74,
                "FIG": 18.62, "GLPI": 45.88, "GWRE": 121.48, "H": 197.68, "HEI": 345.21,
                "HEI-A": 254.74, "IDXX": 551.50, "IT": 134.96, "KNSL": 328.43, "MSCI": 554.85,
                "MTN": 137.94, "ONON": 37.07, "RRR": 67.26, "SCHW": 90.67, "SHOP": 116.86,
                "SPOT": 460.02, "TSLA": 379.71, "VRSK": 182.18},
     "note": "Actuals in: BPTIX NAV 279.94 (+2.46%; our estimate ~278.9, +1.07 LOW — every basket underestimated), "
             "AUM 17.4B. MIRROR TEST CONFIRMS BASKET DRIFT, NOT LEVERAGE: today every basket was too LOW, the exact "
             "mirror of 6/25 (every basket too HIGH), and the SAME names drove both — FDS/FIG/GWRE/IT/KNSL cratered "
             "6/25 and rebounded 6/26 — so the fund is OVERWEIGHT these vs our stale 3/31-5/31 snapshots. It is NOT "
             "leverage: 6/25+6/26 in isolation imply L~1.15, but if L were really ~1.15 the 6/17/6/18 down-basket "
             "days would have missed too — they matched L=1.0 exactly. So leverage stays ~1.0; the 6/25/6/26 misses "
             "are weight drift toward the high-dispersion names (which only show up on days they move a lot). "
             "AUM 17.0B->17.4B vs NAV +2.46% => ~FLAT flow (-$18M; redemptions essentially STOPPED on the rebound; "
             "cumulative ~$2.4B since 6/12)."},
    {"date": "2026-06-29", "spcx": 164.19, "actual_nav": 288.69, "aum": 17.9e9,
     "closes": {"ACGL": 98.06, "BIRK": 43.41, "CHH": 111.97, "CSGP": 29.32, "FDS": 233.62,
                "FIG": 19.08, "GLPI": 45.91, "GWRE": 120.87, "H": 196.77, "HEI": 350.44,
                "HEI-A": 254.48, "IDXX": 535.93, "IT": 132.79, "KNSL": 332.02, "MSCI": 558.00,
                "MTN": 135.20, "ONON": 35.42, "RRR": 65.89, "SCHW": 90.55, "SHOP": 114.21,
                "SPOT": 462.29, "TSLA": 411.84, "VRSK": 179.21},
     "note": "Actuals in: BPTIX NAV 288.69 (+3.13%; our estimate ~289.6, -0.93 — every NPORT-snapshot basket "
             "OVERestimated again), AUM 17.9B. BUT RONB (Baron's daily-transparent ETF, current weights) NAILED it "
             "(288.74, err -0.05) = best basket. This SHARPENS the basket-drift picture: on a day SpaceX +7.15% AND "
             "TSLA +8.5% both led, the stale 3/31-5/31 snapshots (TSLA 23-30%) OVERSHOT while RONB's fresher, "
             "lower-TSLA book tracked -> the fund is UNDERWEIGHT TSLA vs our snapshots (Baron's documented 'less "
             "Tesla' trim) and/or our SpaceX weight (33.96%) is a touch high. My estimate-day 'should track well' "
             "call was INCOMPLETE — I treated only FDS/FIG/GWRE as drift names, but TSLA itself is drifted "
             "(underweight). Takeaway: RONB is now the best LIVE proxy; the NPORT snapshots lag. AUM 17.4B->17.9B "
             "vs NAV +3.13% => ~flat flow (-$44M; redemptions still stopped; cumulative ~$2.45B). The 6/30 NPORT "
             "(~Aug 27) gives the true current weights."},
    {"date": "2026-06-30", "spcx": 170.86, "actual_nav": 292.60, "aum": 18.1e9,
     "closes": {"ACGL": 97.06, "BIRK": 43.03, "CHH": 110.27, "CSGP": 28.32, "FDS": 230.08,
                "FIG": 18.09, "GLPI": 44.53, "GWRE": 123.05, "H": 193.84, "HEI": 356.19,
                "HEI-A": 257.91, "IDXX": 526.44, "IT": 129.62, "KNSL": 329.81, "MSCI": 560.04,
                "MTN": 136.15, "ONON": 35.42, "RRR": 65.06, "SCHW": 92.27, "SHOP": 114.18,
                "SPOT": 459.13, "TSLA": 420.60, "VRSK": 179.53},
     "note": "Actuals in: BPTIX NAV 292.60 (+1.35%; our estimate ~293.0, -0.36 — a small overestimate, all in a "
             "tight band), AUM 18.1B. Best basket = optimal (292.67, +0.07); RONB OVERSHOT most today (+0.73) — the "
             "reverse of 6/29. On this ~flat public day the fund's public sleeve slightly UNDERperformed our baskets, "
             "consistent with an overweight in the day's LOSERS (FIG -5.2%, CSGP -3.4%, IT -2.4% — FIG a suspected "
             "drift name). So RONB isn't universally best — it tracks when the drift helps it (TSLA-led days) and "
             "lags when the fund's mid-cap overweights fall; the through-line is still that the fund's true weights "
             "sit between our snapshots, settled by the 6/30 NPORT (~Aug 27, whose snapshot IS today). AUM 17.9B->"
             "18.1B vs NAV +1.35% => ~flat flow (-$42M; redemptions still stopped; cumulative ~$2.49B)."},
    {"date": "2026-07-01", "spcx": 157.54, "actual_nav": 289.36, "aum": 17.8e9,
     "closes": {"ACGL": 98.55, "BIRK": 44.03, "CHH": 109.27, "CSGP": 29.36, "FDS": 245.55,
                "FIG": 19.49, "GLPI": 43.69, "GWRE": 127.65, "H": 190.86, "HEI": 359.70,
                "HEI-A": 261.65, "IDXX": 537.58, "IT": 133.76, "KNSL": 345.27, "MSCI": 582.03,
                "MTN": 136.35, "ONON": 35.56, "RRR": 64.19, "SCHW": 95.78, "SHOP": 121.63,
                "SPOT": 472.48, "TSLA": 425.30, "VRSK": 183.72},
     "note": "Actuals in: BPTIX NAV 289.36 (-1.11%; our estimate ~288.2, +1.20 — actual came in ABOVE EVERY basket), "
             "AUM 17.8B. DRIFT TEST CONFIRMED: the fund fell LESS than predicted, exactly as called — the mid-cap "
             "'drift' names (FDS/FIG/GWRE/KNSL) that ripped today are overweight vs our stale snapshots, so the "
             "implied public sleeve did ~+2.7% vs our +2.0-2.3% baskets. Best fund_5/31 (-0.74); all underestimated; "
             "RONB worst (-1.49, understated the winners most). CAVEAT — a 2nd reading fits equally: our SpaceX "
             "weight (36.4%) may be a few % HIGH. On a SpaceX-DOWN day a lower true weight = less drag = higher NAV; "
             "that also explains 6/29 (SpaceX UP -> we overshot -> actual below) and today (SpaceX DOWN -> actual "
             "above). Both readings (mid-cap overweight + SpaceX-weight-slightly-high) say the SAME thing: our "
             "weights are stale — settled by the 6/30 NPORT (~Aug 27). AUM 18.1B->17.8B vs NAV -1.11% => ~$0.10B "
             "net outflow (modest; redemptions ticked back up; cumulative ~$2.59B)."},
    {"date": "2026-07-02", "spcx": 162.00, "actual_nav": 292.78, "aum": 18.0e9,
     "closes": {"ACGL": 102.20, "BIRK": 45.99, "CHH": 112.37, "CSGP": 30.00, "FDS": 250.09,
                "FIG": 21.34, "GLPI": 43.95, "GWRE": 134.47, "H": 191.28, "HEI": 362.09,
                "HEI-A": 261.70, "IDXX": 557.80, "IT": 136.32, "KNSL": 354.85, "MSCI": 603.11,
                "MTN": 140.68, "ONON": 36.83, "RRR": 65.60, "SCHW": 97.00, "SHOP": 119.46,
                "SPOT": 485.97, "TSLA": 393.45, "VRSK": 188.35},
     "note": "Actuals in (after the 7/3 holiday): BPTIX NAV 292.78 (+1.18%; model median 291.94, +0.84 ABOVE — every "
             "basket UNDERestimated), AUM 18.0B. DRIFT DIAGNOSIS CONFIRMED OUT-OF-SAMPLE: on this clean test (TSLA "
             "-7.5% DOWN, mid-caps RIPPING) the errors ordered EXACTLY by TSLA weight — fund_3/31 (30% TSLA) "
             "underestimated MOST (-1.71), the low-TSLA baskets were closest (optimal -0.09 BEST, RONB -0.34) — "
             "precisely as the 7/2 diagnosis predicted (fund UNDERWEIGHT TSLA + OVERWEIGHT mid-caps -> both legs push "
             "actual ABOVE the snapshots). Strongest confirmation yet: both drift legs aligned, no confounds. AUM "
             "17.8B->18.0B vs NAV +1.18% => ~flat flow (-$10M; redemptions ~stopped; cumulative ~$2.6B). Next full "
             "weights: the 6/30 NPORT (~Aug 27)."},
    {"date": "2026-07-06", "spcx": 160.42, "actual_nav": 295.04, "aum": 18.1e9,
     "closes": {"ACGL": 101.81, "BIRK": 46.16, "CHH": 107.67, "CSGP": 28.70, "FDS": 252.20,
                "FIG": 21.08, "GLPI": 43.54, "GWRE": 137.59, "H": 193.48, "HEI": 365.31,
                "HEI-A": 262.63, "IDXX": 564.98, "IT": 135.11, "KNSL": 347.23, "MSCI": 614.04,
                "MTN": 142.12, "ONON": 36.87, "RRR": 65.04, "SCHW": 100.62, "SHOP": 120.14,
                "SPOT": 483.01, "TSLA": 419.77, "VRSK": 187.79},
     "note": "Actuals in: BPTIX NAV 295.04 (+0.77%; model median 295.39, -0.35 BELOW — as the drift-adjusted guess "
             "called), AUM 18.1B. MIRROR OF 7/2 CONFIRMED: on this TSLA-UP day (+6.7%) the high-TSLA baskets "
             "OVERestimated most (fund_3/31 +0.97) and the low-TSLA were closest (optimal -0.24 BEST, fund_5/31 "
             "+0.25) — the EXACT OPPOSITE ordering of 7/2 (TSLA down, high-TSLA underestimated most). So the "
             "UNDERWEIGHT-TSLA drift is now confirmed on BOTH a TSLA-down (7/2) AND a TSLA-up (7/6) day: the error "
             "ordering flips with TSLA's direction, exactly as the thesis requires. Best optimal (-0.24). AUM 18.0B->"
             "18.1B vs NAV +0.77% => ~flat flow (-$39M; redemptions ~minimal; cumulative ~$2.64B). 6/30 NPORT "
             "(~Aug 27) quantifies the true TSLA/mid-cap weights."},
    {"date": "2026-07-07", "spcx": 149.47, "actual_nav": 288.70, "aum": 17.7e9,
     "closes": {"ACGL": 102.85, "BIRK": 45.56, "CHH": 110.95, "CSGP": 29.87, "FDS": 258.30,
                "FIG": 22.19, "GLPI": 44.07, "GWRE": 137.06, "H": 193.16, "HEI": 358.02,
                "HEI-A": 257.57, "IDXX": 570.25, "IT": 140.80, "KNSL": 348.73, "MSCI": 608.09,
                "MTN": 143.16, "ONON": 36.62, "RRR": 66.16, "SCHW": 101.93, "SHOP": 121.88,
                "SPOT": 493.95, "TSLA": 402.90, "VRSK": 192.25},
     "note": "Actuals in: BPTIX NAV 288.70 (-2.15%; model median 287.85, +0.85 ABOVE — every basket UNDERestimated), "
             "AUM 17.7B. DRIFT CONFIRMED AGAIN (TSLA-down/mid-up): errors ordered by TSLA weight (fund_3/31 -1.18 "
             "worst, optimal -0.29 best). BIG WIN for the v1 mark basket: built 7/6, it valued 7/7 to 288.64 vs "
             "actual 288.70 = proxy error only -0.06 (-0.02%) — a near-exact out-of-sample hit, so the basket is "
             "validated for P&L. It also isolates the drift cleanly: the v1 basket carries the SAME SpaceX (~34%) as "
             "the snapshots but TSLA trimmed to 22%, and it nailed the NAV while the high-TSLA snapshots missed +0.84 "
             "-> the entire miss is the TSLA overweight, NOT SpaceX (re-confirmed on this big -6.8% SPCX day). AUM "
             "18.1B->17.7B vs NAV -2.15% => ~flat flow (-$11M; redemptions ~stopped; cumulative ~$2.65B)."},
    {"date": "2026-07-08", "spcx": 148.30, "actual_nav": 283.37, "aum": 17.3e9,
     "closes": {"ACGL": 102.01, "BIRK": 44.24, "CHH": 106.39, "CSGP": 29.34, "FDS": 247.82,
                "FIG": 21.67, "GLPI": 42.91, "GWRE": 135.74, "H": 187.40, "HEI": 347.78,
                "HEI-A": 251.03, "IDXX": 555.67, "IT": 134.68, "KNSL": 345.96, "MSCI": 604.23,
                "MTN": 143.63, "ONON": 36.38, "RRR": 63.32, "SCHW": 101.70, "SHOP": 119.22,
                "SPOT": 485.22, "TSLA": 394.06, "VRSK": 189.67,
                "AMZN": 243.62, "GOOGL": 361.92, "GOOG": 358.71, "LLY": 1215.83, "MRNA": 73.80, "MORN": 165.03},
     "note": "Actuals in: BPTIX NAV 283.37 (-1.85%; model median 283.96, -0.59 — every basket slightly "
             "OVERestimated), AUM 17.3B. The drift ~cancelled as called (tight consensus, small miss), but the "
             "mid-cap-DOWN effect edged out the TSLA-DOWN help: the overweight mid-caps fell HARDER (IT/RRR/FDS/CHH "
             "~-4%) than TSLA (-2.2%), so the fund fell a touch more than the snapshots. Errors were UNIFORM "
             "(~+0.55-0.72, NOT TSLA-ordered) -> a mid-cap effect, not a TSLA one. v1 mark basket 283.87 vs actual "
             "283.37 = +0.50 (0.18%): v1 also overestimated, exposing its ONE known weakness — the TSLA trim is "
             "spread PRO-RATA, so it under-captures the CONCENTRATED overweight in the specific mid-caps (IT/FDS/RRR) "
             "that fell hardest (the deliberate no-overfit tradeoff; the 6/30 NPORT fixes it). AUM 17.7B->17.3B vs "
             "NAV -1.85% => ~$0.07B net outflow (ticked up; cumulative ~$2.72B)."},
    {"date": "2026-07-09", "spcx": 152.16, "actual_nav": None, "aum": None,
     "closes": {"ACGL": 101.70, "BIRK": 45.32, "CHH": 109.61, "CSGP": 29.19, "FDS": 241.90,
                "FIG": 22.26, "GLPI": 43.04, "GWRE": 135.05, "H": 189.95, "HEI": 352.13,
                "HEI-A": 253.27, "IDXX": 558.60, "IT": 132.69, "KNSL": 338.58, "MSCI": 603.35,
                "MTN": 147.49, "ONON": 36.77, "RRR": 63.49, "SCHW": 101.91, "SHOP": 123.17,
                "SPOT": 485.88, "TSLA": 406.55, "VRSK": 187.01,
                "AMZN": 247.04, "GOOGL": 358.89, "GOOG": 356.24, "LLY": 1216.95, "MRNA": 76.56, "MORN": 165.55},
     "note": "Estimate only (BPTIX NAV + AUM tomorrow). FIRST day with the full 29-name book — the 6 new "
             "names (AMZN/GOOGL/GOOG/LLY/MRNA/MORN) are now in the paste, so fund_6/30 uses the COMPLETE 6/30 book. "
             "SPCX +2.60% (148.30->152.16) = ~+0.9% contribution; TSLA +3.17% (394.06->406.55) UP too. Public mixed "
             "(MTN +2.7%, SHOP/FIG +2.7%, H +1.4% up; FDS -2.4%, KNSL -2.1%, IT -1.5% down). Both SpaceX & TSLA up "
             "-> NAV up; TSLA-up means the high-TSLA snapshots overestimate, so watch fund_6/30 (real weights) to "
             "track best."},
]

METHOD_LABELS = {"actual": "actual hedge", "fund_3_31": "fund 3/31", "fund_4_30": "fund 4/30",
                 "fund_5_31": "fund 5/31", "fund_6_30": "fund 6/30 (latest)", "blend": "blend 4/30+5/31",
                 "optimal": "optimal (min-var)", "ronb": "RONB ETF (daily)"}


def _nospy(W):
    w = {k: v for k, v in W.items() if k != "SPY"}
    s = sum(w.values()) or 1
    return {k: v / s for k, v in w.items()}


def _ronb_weights():
    """RONB's public-book weights (ex SpaceX, ex cash) from the daily holdings cache
    -> the one DAILY-fresh basket weighting (the others are static NPORT snapshots).
    Names RONB holds but we lack closes for (IBKR/MORN/ABNB/LYV) drop out in the
    basket sum; the shared names renormalize. Empty if the cache is missing."""
    try:
        h = json.load(open(os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "ronb.json"),
                           encoding="utf-8"))["holdings"]["holdings"]
        return {x["ticker"]: x["weight"] for x in h if not x.get("private") and not x.get("cash")}
    except Exception:
        return {}


def _weightings():
    H = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "hedge_book.json"), encoding="utf-8"))
    comps = {m: {r["ticker"].replace("/", "-"): r["weight"] for r in rows if r["ticker"] != "SPY"}
             for m, rows in H["meta"]["basket_compositions"].items()}

    def renorm(w):
        s = sum(w.values()) or 1
        return {k: v / s for k, v in w.items()}

    blend = {t: 0.5 * (fs.WEIGHTS_4_30.get(t, 0) + fs.WEIGHTS_5_31.get(t, 0))
             for t in set(fs.WEIGHTS_4_30) | set(fs.WEIGHTS_5_31)}
    return {
        "actual": renorm(comps.get("actual", {})),
        "fund_3_31": _nospy(fs.WEIGHTS_3_31), "fund_4_30": _nospy(fs.WEIGHTS_4_30),
        "fund_5_31": _nospy(fs.WEIGHTS_5_31), "fund_6_30": _nospy(fs.WEIGHTS_6_30), "blend": _nospy(blend),
        "optimal": renorm(comps.get("optimal", {})), "ronb": renorm(_ronb_weights()),
    }, H


def _base_closes(H):
    legs = {l["ticker"].replace("/", "-"): l for l in H["legs"] if l["side"] == "short"}
    spnl = {p["ticker"].replace("/", "-"): p for p in H["short_legs_pnl"]}
    sd = [r["date"] for r in H["series"]]
    li = sd.index(BASE["date"])
    return {t: legs[t]["entry_px"] + spnl[t]["pnl"][li] / legs[t]["shares"]
            for t in legs if legs[t].get("shares")}


def _ensemble():
    """Perfect-fit ensemble (normalized weights) from ipo_day_recon, for a NAV band."""
    try:
        e = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "ipo_day_recon.json"), encoding="utf-8"))["best_fit"]["ensemble"]
        return e["tickers"], e["fits"]
    except Exception:
        return [], []


def _build_rows(WS, H, methods, ens_tk, ens_fits, apply_buy=True):
    """One forward chain BASE(6/5) -> 6/22. apply_buy=True is the REVISED view (the
    $262M Friday buy is booked on 6/12); apply_buy=False is the AS-OF view (no buy —
    what we knew before the 6/16 recalibration), used to seed the 6/8-6/12 vintage."""
    prev = {"nav": BASE["nav"], "spcx": BASE["spcx"], "aum": BASE["aum"],
            "spx_value": BASE["spacex_value"], "closes": _base_closes(H)}
    rows = []
    for e in ENTRIES:
        buy = (e.get("spacex_buy_usd", 0.0) or 0.0) if apply_buy else 0.0
        spx_ret = e["spcx"] / prev["spcx"] - 1
        w_spx = prev["spx_value"] / prev["aum"]
        lev = LEVERAGE_FOR(e["date"], prev["aum"])   # start-of-day net; >=6/26 = 1 + borrowings/net
        preds = {}
        for m in methods:
            W = WS[m]
            num = den = 0.0
            for t, w in W.items():
                a, b = prev["closes"].get(t), e["closes"].get(t)
                if a and b and w:
                    num += w * (b / a - 1)
                    den += w
            br = num / den if den else 0.0
            navret = w_spx * spx_ret + (lev - w_spx) * br
            preds[m] = {"basket_ret_pct": round(br * 100, 3),
                        "nav_return_pct": round(navret * 100, 3),
                        "pred_nav": round(prev["nav"] * (1 + navret), 2)}
        # perfect-fit ensemble band: apply each fit's (normalized) weights -> NAV range
        ens_navs = []
        for fw in ens_fits:
            num = den = 0.0
            for ti, t in enumerate(ens_tk):
                a, b, w = prev["closes"].get(t), e["closes"].get(t), fw[ti]
                if a and b and w:
                    num += w * (b / a - 1)
                    den += w
            br = num / den if den else 0.0
            ens_navs.append(prev["nav"] * (1 + w_spx * spx_ret + (lev - w_spx) * br))
        pf_range = [round(min(ens_navs), 2), round(max(ens_navs), 2)] if ens_navs else None
        actual = e.get("actual_nav")
        errs = ({m: round(preds[m]["pred_nav"] - actual, 2) for m in methods} if actual else {})
        best = min(errs, key=lambda m: abs(errs[m])) if errs else None
        # SpaceX shares behind one BPTIX share = fund SpaceX shares / BPTIX shares out
        #   = (SpaceX_$/SPCX) / (AUM/NAV) = shares x NAV / AUM.  Use END-of-day AUM so a
        #   big SPCX move doesn't distort it (the holding's share count is ~constant).
        nav_used = actual if actual else sorted(preds[m]["pred_nav"] for m in methods)[len(methods) // 2]
        spx_shares_enter = prev["spx_value"] / prev["spcx"]         # shares entering the day (pre-buy)
        bought_shares = (buy / e["spcx"]) if (buy and e["spcx"]) else 0.0
        spx_shares_end = spx_shares_enter + bought_shares          # end-of-day count (a Friday buy ADDS shares)
        aum_end = float(e["aum"]) if e.get("aum") else prev["aum"] * (nav_used / prev["nav"])
        spx_sh_per_bptix = round(spx_shares_end * nav_used / aum_end, 4) if aum_end else None
        # driver of the day-over-day change in spx_sh_per_bptix: SpaceX share count is
        # ~constant, so it moves with BPTIX shares outstanding = AUM/NAV (net flows).
        bptix_shares_out = aum_end / nav_used if nav_used else None
        flow_b = round((aum_end - prev["aum"] * (nav_used / prev["nav"])) / 1e9, 3) if e.get("aum") else None
        rows.append({"date": e["date"], "spcx": e["spcx"], "spcx_ret_pct": round(spx_ret * 100, 2),
                     "spacex_weight_pct": round(w_spx * 100, 2), "leverage": lev,
                     "spx_shares_per_bptix": spx_sh_per_bptix,
                     "spx_shares_held_m": round(spx_shares_end / 1e6, 2),
                     "spacex_buy_usd": (buy or None), "backfilled": e["date"] in BACKFILL_DATES,
                     "bptix_shares_out_m": round(bptix_shares_out / 1e6, 2) if bptix_shares_out else None,
                     "aum_used_b": round(aum_end / 1e9, 2), "flow_b": flow_b,
                     # borrowings ($B) = (leverage - 1) x net assets. The STABLE quantity; leverage
                     # drifts because net shrinks with redemptions while borrowings stay ~constant.
                     "borrowings_b": round((lev - 1) * aum_end / 1e9, 3),
                     # SpaceX-side NAV contribution = w_spx x SPCX return. IDENTICAL for every
                     # basket method -> the per-method NAV spread is purely the PUBLIC basket.
                     "spx_contrib_pct": round(w_spx * spx_ret * 100, 3),
                     "prior_nav": prev["nav"], "preds": preds, "perfect_fit_range": pf_range,
                     "actual_nav": actual, "errors": errs, "best_method": best,
                     "note": e.get("note", "")})
        # chain to next day: base off ACTUAL nav if known, else the median prediction
        base_nav = nav_used
        spx_value = prev["spx_value"] * (e["spcx"] / prev["spcx"]) + buy   # mark move + any Friday buy (at close)
        aum = float(e["aum"]) if e.get("aum") else prev["aum"] * (base_nav / prev["nav"])
        prev = {"nav": base_nav, "spcx": e["spcx"], "aum": aum, "spx_value": spx_value, "closes": e["closes"]}
    return rows


SPX_SHARES_DISCLOSED = 3.89026788e9 / 105.32   # 3/31 NPORT SpaceX share count (~36.94M, split-adj)


def _lookthrough(rows, w6):
    """Current best per-BPTIX-share LOOK-THROUGH: what 1 BPTIX share owns = shares of each holding
    + a borrowing line. The SLOW layer (holdings weights) updates only at a disclosure (6/30, then
    ~9/30); the FAST layer (per-BPTIX share counts, leverage, borrow) drifts DAILY off AUM/NAV. Uses
    the freshest disclosed weights (6/30) for the public split, the disclosed SpaceX count, and the
    borrowings-leverage. Mark 1 BPTIX share = sum(sh_i x price_i) - borrow_per_bptix."""
    r = rows[-1]
    if r.get("actual_nav"):
        nav = r["actual_nav"]
    else:
        pn = sorted(p["pred_nav"] for p in r["preds"].values())
        nav = pn[len(pn) // 2]
    N = (r.get("bptix_shares_out_m") or 0) * 1e6
    L = r.get("leverage") or 1.0
    aum = (r.get("aum_used_b") or 0) * 1e9
    prices = ENTRIES[-1]["closes"]
    spx_sh = (SPX_SHARES_DISCLOSED / N) if N else 0.0
    spx_val = spx_sh * r["spcx"]
    pub_val = L * nav - spx_val
    borrow_pb = (L - 1) * nav
    holdings = [{"ticker": "SpaceX (SPCX)", "sh_per_bptix": round(spx_sh, 4), "price": r["spcx"],
                 "pct_nav": round(spx_val / nav * 100, 2)}]
    for t, w in sorted(w6.items(), key=lambda x: -x[1]):
        px = prices.get(t)
        if not px or not w:
            continue
        val = w * pub_val
        holdings.append({"ticker": t, "sh_per_bptix": round(val / px, 6), "price": px,
                         "pct_nav": round(val / nav * 100, 2)})
    holdings.append({"ticker": "Cash (borrow)", "sh_per_bptix": None, "price": None,
                     "usd_per_bptix": round(-borrow_pb, 2), "pct_nav": round(-borrow_pb / nav * 100, 2)})
    return {"date": r["date"], "is_estimate": r.get("actual_nav") is None, "nav": round(nav, 2),
            "aum_b": round(aum / 1e9, 2), "bptix_shares_out_m": round(N / 1e6, 2), "leverage": round(L, 4),
            "borrowings_b": round((L - 1) * aum / 1e9, 3), "borrow_per_bptix": round(borrow_pb, 2),
            "position_shares": 130000, "holdings": holdings}


def build_payload():
    WS, H = _weightings()
    methods = list(METHOD_LABELS)
    ens_tk, ens_fits = _ensemble()
    rows = _build_rows(WS, H, methods, ens_tk, ens_fits, apply_buy=True)             # REVISED (buy on)
    # AS-OF seed for the IPO-week backfill: rebuild with the buy OFF and freeze 6/8-6/12
    # so as-of vs revised diverge on 6/12 (we didn't know about the buy until 6/16).
    asof_seed = [r for r in _build_rows(WS, H, methods, ens_tk, ens_fits, apply_buy=False)
                 if r["date"] in BACKFILL_DATES]
    vintage_rows = _freeze_vintage(rows, seed=asof_seed)
    # full per-method holdings weights (the renormalized ex-SPY weights the model uses)
    # for the basket-composition + fixed-basket-drift table.
    compositions = {m: sorted([{"ticker": t, "weight_pct": round(w * 100, 2)}
                               for t, w in WS[m].items() if w], key=lambda x: -x["weight_pct"])
                    for m in methods}
    lookthrough = _lookthrough(rows, WS.get("fund_6_30", {}))
    return {
        "meta": {
            "title": "Daily BPTIX NAV estimate — per basket-weighting vs actual",
            "method_labels": METHOD_LABELS, "methods": methods, "base": BASE,
            "window_start": BASE["date"], "backfill_dates": sorted(BACKFILL_DATES),
            "compositions": compositions, "lookthrough": lookthrough,
            # latest day's public closes -> lets the composition panel convert a basket's
            # weights into shares / shares-per-BPTIX / $ / total-share allocations.
            "ref_closes": {"date": ENTRIES[-1]["date"], "closes": ENTRIES[-1]["closes"]},
            # 6/5 base closes + base leverage -> the composition "difference" view sizes a
            # held-fixed (never-adjusted-since-6/5) basket and compares it to today's target.
            "base_closes": _base_closes(H), "base_leverage": LEVERAGE_FOR(BASE["date"]),
            "friday_spacex_buy_usd": FRIDAY_SPACEX_BUY, "leverage_schedule": "0.968 thru 6/15, 1.00 (6/16-6/25), 1.06 from 6/26 (re-levered; 6/30 disclosure + regression)",
            "note": ("Each day's predicted BPTIX NAV under every basket weighting we've tested, vs the actual — now "
                     "walked back through the IPO week (6/8 onward). NAV_t = NAV_{t-1} x (1 + w_spx x SPCX_return + "
                     "(LEVERAGE - w_spx) x basket_return); SpaceX marked to live SPCX once public, held flat at the "
                     "$135 IPO-price mark before (6/8-6/11 are pure PUBLIC-basket tests). Public weights drop SPY and "
                     "renormalize over the 23 names. The ~$%.0fM Friday SpaceX buy is booked on 6/12 (the day it "
                     "happened); LEVERAGE is the start-of-day gross/net: 0.968 (the 5/31-disclosed ~3.2%% net-cash "
                     "buffer) thru 6/15, then 1.00 from 6/16 once the first redemption consumed it. Chained off the "
                     "prior ACTUAL NAV where known. 6/8-6/12 are BACKFILLED from contemporaneous records (git commits "
                     "+ the Morningstar AUM log + hedge-book-reconstructed closes), not real-time daily-log vintages."
                     % (FRIDAY_SPACEX_BUY / 1e6,)),
            "two_views_note": ("AS-OF (vintage): each day's estimate FROZEN as first reported (the IPO week is the "
                               "as-of we reconstructed from the day's own records). REVISED: recomputed with the "
                               "current assumptions. The two differ ONLY where an assumption changed AFTER a day was "
                               "frozen: 6/12 (the ~$262M Friday buy, found on 6/16 — revised lifts end-of-day SpaceX "
                               "shares 36.9M->38.6M; the day's entering weight is unchanged), 6/15 (that buy carried "
                               "in moves the WEIGHT 29.1%->30.4%), and 6/17 (the LEVERAGE pin 0.968->1.0, which moves "
                               "NAV but not weight/shares). Every other day is identical across the two views."),
            "disclaimer": "Estimate, not the fund's record. Excludes fees, intraday timing, mid-day flows.",
        },
        "rows": rows,                 # REVISED (current assumptions)
        "vintage_rows": vintage_rows, # AS-OF (frozen as first reported)
    }


def _freeze_vintage(rows, seed=None):
    """Append-only: freeze each day's estimate the first time it is built; never revise
    a frozen day. `seed` rows (the as-of IPO-week backfill, built with the buy OFF) are
    considered FIRST so they win for 6/8-6/12 over the revised rows. Idempotent."""
    frozen, order = {}, []
    if os.path.exists(_VINTAGE_PATH):
        for line in open(_VINTAGE_PATH, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                frozen[r["date"]] = r
                order.append(r["date"])
    added = []
    for r in (list(seed or []) + list(rows)):   # seed (as-of backfill) before revised
        if r["date"] not in frozen:
            frozen[r["date"]] = r
            order.append(r["date"])
            added.append(r)
    if added:
        with open(_VINTAGE_PATH, "a", encoding="utf-8") as f:
            for r in added:
                f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")
    return [frozen[d] for d in sorted(set(order))]


def write_json():
    payload = build_payload()
    out = os.path.join(_REPO_ROOT, "dashboard", "data", "daily_nav_log.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return out


if __name__ == "__main__":
    pl = build_payload()
    print(pl["meta"]["title"])
    for r in pl["rows"]:
        ps = " ".join("%s=%.2f" % (m, r["preds"][m]["pred_nav"]) for m in pl["meta"]["methods"])
        print(r["date"], "SPCX", r["spcx"], "w_spx %.1f%%" % r["spacex_weight_pct"], "| actual", r["actual_nav"])
        print("  ", ps)
    print("wrote", write_json())
