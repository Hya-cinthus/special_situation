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
    {"date": "2026-07-09", "spcx": 152.16, "actual_nav": 287.82, "aum": 17.5e9,
     "closes": {"ACGL": 101.70, "BIRK": 45.32, "CHH": 109.61, "CSGP": 29.19, "FDS": 241.90,
                "FIG": 22.26, "GLPI": 43.04, "GWRE": 135.05, "H": 189.95, "HEI": 352.13,
                "HEI-A": 253.27, "IDXX": 558.60, "IT": 132.69, "KNSL": 338.58, "MSCI": 603.35,
                "MTN": 147.49, "ONON": 36.77, "RRR": 63.49, "SCHW": 101.91, "SHOP": 123.17,
                "SPOT": 485.88, "TSLA": 406.55, "VRSK": 187.01,
                "AMZN": 247.04, "GOOGL": 358.89, "GOOG": 356.24, "LLY": 1216.95, "MRNA": 76.56, "MORN": 165.55},
     "note": "Actuals in: BPTIX NAV 287.82 (+1.57%; model median 287.83 — NAILED it, err -0.01), AUM 17.5B. First "
             "completion on the FULL 29-name book (the 6 new names now in the paste): fund_6/30 +0.16 (good), optimal "
             "best (-0.04), median exact; high-TSLA fund_3/31 +0.33 over (TSLA-up day). SPCX +2.60% (148.30->152.16) "
             "= +0.86% contribution; TSLA +3.17% UP too. AUM 17.3B->17.5B vs NAV +1.57% => ~$0.07B net outflow "
             "(cumulative ~$2.8B since 6/12). Leverage 1.067 (borrowings model on entering net $17.3B)."},
    {"date": "2026-07-10", "spcx": 145.30, "actual_nav": 283.97, "aum": 17.2e9,
     "closes": {"ACGL": 101.06, "BIRK": 45.48, "CHH": 109.72, "CSGP": 28.39, "FDS": 247.11,
                "FIG": 21.11, "GLPI": 43.18, "GWRE": 136.13, "H": 191.14, "HEI": 350.92,
                "HEI-A": 254.07, "IDXX": 563.57, "IT": 133.24, "KNSL": 340.57, "MSCI": 604.71,
                "MTN": 150.14, "ONON": 38.54, "RRR": 64.21, "SCHW": 103.12, "SHOP": 122.54,
                "SPOT": 479.77, "TSLA": 407.76, "VRSK": 185.39,
                "AMZN": 245.34, "GOOGL": 357.18, "GOOG": 355.03, "LLY": 1188.58, "MRNA": 68.27, "MORN": 165.18},
     "note": "Fri 7/10. Closes fetched T+1 (Yahoo) per new workflow (user stopped pasting daily closes on 7/13; I "
             "fetch prev-day closes myself, no look-ahead). SPCX -4.51% (152.16->145.30) => SpaceX ~$5.37B (disclosed "
             "shares). BPTIX NAV 283.97 (-1.34%), AUM 17.2B. Scoring: SpaceX-down day, estimates tightly clustered "
             "~284.1-284.2 vs actual 283.97 => most methods +0.1-0.2 over; fund_6/30 -0.15, fund_5/31 best (+0.14), "
             "ronb worst (+0.63). AUM 17.5B->17.2B vs NAV -1.34% => ~-$0.07B net outflow (cumulative ~$2.9B since "
             "6/12). Leverage 1.066 (borrowings model, entering net $17.5B)."},
    {"date": "2026-07-13", "spcx": 139.14, "actual_nav": 281.09, "aum": 17.0e9,
     "closes": {"ACGL": 103.06, "BIRK": 44.63, "CHH": 108.74, "CSGP": 28.77, "FDS": 263.11,
                "FIG": 23.65, "GLPI": 44.04, "GWRE": 140.31, "H": 184.72, "HEI": 344.11,
                "HEI-A": 249.30, "IDXX": 564.21, "IT": 141.31, "KNSL": 344.96, "MSCI": 620.23,
                "MTN": 151.47, "ONON": 37.92, "RRR": 64.41, "SCHW": 102.38, "SHOP": 124.74,
                "SPOT": 479.84, "TSLA": 394.76, "VRSK": 193.73,
                "AMZN": 247.31, "GOOGL": 352.51, "GOOG": 350.67, "LLY": 1181.87, "MRNA": 67.01, "MORN": 173.55},
     "note": "Mon 7/13. Closes fetched T+1 (Yahoo). SPCX -4.24% (145.30->139.14) => SpaceX ~$5.14B (disclosed "
             "shares). BPTIX NAV 281.09 (-1.01%), AUM 17.0B. Scoring: TSLA-down (-3.19%) + SpaceX-down day; ALL "
             "methods UNDER (actual came in above every basket): optimal -0.34 and fund_6/30 -0.35 best, high-TSLA "
             "fund_3/31 -1.00 + ronb -1.20 worst => errors ordered by TSLA weight, re-confirming underweight-TSLA "
             "drift. Best-basket miss -0.35 (-0.12% NAV), a touch wider than the ~0.1% norm but not alarming; watch "
             "if it persists. AUM 17.2B->17.0B vs NAV -1.01% => ~-$0.03B net outflow (cumulative ~$2.9B). Leverage "
             "1.067 (borrowings model, entering net $17.2B)."},
    {"date": "2026-07-14", "spcx": 136.08, "actual_nav": 277.12, "aum": 16.7e9,
     "closes": {"ACGL": 101.53, "BIRK": 44.36, "CHH": 108.32, "CSGP": 27.68, "FDS": 252.61,
                "FIG": 23.86, "GLPI": 43.84, "GWRE": 140.71, "H": 189.70, "HEI": 345.61,
                "HEI-A": 249.70, "IDXX": 540.68, "IT": 132.97, "KNSL": 337.14, "MSCI": 611.43,
                "MTN": 147.64, "ONON": 37.74, "RRR": 64.00, "SCHW": 101.10, "SHOP": 125.68,
                "SPOT": 481.06, "TSLA": 396.18, "VRSK": 190.54,
                "AMZN": 247.49, "GOOGL": 359.51, "GOOG": 357.33, "LLY": 1152.54, "MRNA": 67.44, "MORN": 170.48},
     "note": "Tue 7/14. Closes fetched T+1 (Yahoo). SPCX -2.20% (139.14->136.08) => SpaceX ~$5.03B (disclosed "
             "shares). BPTIX NAV 277.12 (-1.41%), AUM 16.7B. Scoring: estimates NAILED it - tight cluster 277.1-277.3 "
             "vs actual 277.12; fund_3/31 best (+0.01), fund_6/30 +0.19, optimal -0.15, ronb +0.86 worst. The 7/13 "
             "-0.35 under did NOT persist -> reverted to ~0. AUM 17.0B->16.7B vs NAV -1.41% => ~-$0.06B net outflow "
             "(cumulative ~$2.95B). Leverage 1.068 (borrowings model, entering net $17.0B). SpaceX weight down to "
             "31.6% (SPCX falling faster than the fund)."},
    {"date": "2026-07-15", "spcx": 135.27, "actual_nav": 276.80, "aum": 16.7e9,
     "closes": {"ACGL": 98.54, "BIRK": 42.86, "CHH": 109.10, "CSGP": 28.49, "FDS": 251.19,
                "FIG": 23.50, "GLPI": 44.03, "GWRE": 140.54, "H": 191.00, "HEI": 351.59,
                "HEI-A": 253.20, "IDXX": 557.02, "IT": 133.76, "KNSL": 319.61, "MSCI": 621.77,
                "MTN": 148.03, "ONON": 37.46, "RRR": 65.51, "SCHW": 102.79, "SHOP": 123.55,
                "SPOT": 485.38, "TSLA": 394.46, "VRSK": 191.94,
                "AMZN": 254.96, "GOOGL": 370.92, "GOOG": 370.21, "LLY": 1156.63, "MRNA": 68.28, "MORN": 169.25},
     "note": "Wed 7/15. Closes fetched T+1 (Yahoo). SPCX -0.60% (136.08->135.27) => SpaceX ~$5.00B (disclosed "
             "shares). BPTIX NAV 276.80 (-0.12%), AUM 16.7B. Scoring: model NAILED it again - all methods within "
             "+/-0.13 of actual 276.80; fund_6/30 +0.02 (best-in-class), actual -0.01, fund_5/31 -0.13. Two clean "
             "days after 7/13 confirm no drift. AUM flat 16.7B; flow ~+$0.02B (negligible inflow). Leverage 1.069 "
             "(borrowings model, entering net $16.7B). SpaceX weight 31.4%."},
    {"date": "2026-07-16", "spcx": 131.11, "actual_nav": 277.52, "aum": 16.7e9,
     "closes": {"ACGL": 100.04, "BIRK": 44.31, "CHH": 111.29, "CSGP": 30.37, "FDS": 262.46,
                "FIG": 23.41, "GLPI": 45.17, "GWRE": 148.91, "H": 188.76, "HEI": 344.03,
                "HEI-A": 250.24, "IDXX": 576.07, "IT": 142.89, "KNSL": 335.52, "MSCI": 637.24,
                "MTN": 149.13, "ONON": 38.20, "RRR": 66.73, "SCHW": 102.80, "SHOP": 125.06,
                "SPOT": 476.08, "TSLA": 391.06, "VRSK": 201.49,
                "AMZN": 249.89, "GOOGL": 354.46, "GOOG": 353.81, "LLY": 1169.17, "MRNA": 63.15, "MORN": 173.90},
     "note": "Thu 7/16. Closes fetched T+1 (Yahoo). SPCX -3.08% (135.27->131.11) => SpaceX ~$4.84B (disclosed "
             "shares). BPTIX NAV 277.52 (+0.26%), AUM 16.7B. Scoring: most methods slightly UNDER (actual above "
             "baskets); fund_5/31 NAILED it (0.00), blend -0.09, optimal +0.17, fund_6/30 -0.39, ronb -0.94 worst. "
             "HEDGE IN ACTION: SPCX -3.1% but NAV +0.26% -> public mid-caps ripped (IT +6.8%, GWRE +6.0%, CSGP +6.6%, "
             "VRSK +5.7%, FDS +4.5%) and more than offset SpaceX. AUM flat 16.7B vs NAV +0.26% => ~-$0.04B net outflow "
             "(cumulative ~$3.0B). Leverage 1.069 (borrowings model, entering net $16.7B). SpaceX weight 31.2%."},
    {"date": "2026-07-17", "spcx": 123.99, "actual_nav": 270.95, "aum": 16.3e9,
     "closes": {"ACGL": 101.35, "BIRK": 44.36, "CHH": 111.84, "CSGP": 29.78, "FDS": 258.09,
                "FIG": 23.95, "GLPI": 45.08, "GWRE": 150.02, "H": 190.65, "HEI": 342.66,
                "HEI-A": 250.07, "IDXX": 567.44, "IT": 140.19, "KNSL": 343.99, "MSCI": 628.66,
                "MTN": 147.86, "ONON": 37.20, "RRR": 64.75, "SCHW": 101.56, "SHOP": 123.56,
                "SPOT": 478.14, "TSLA": 380.84, "VRSK": 200.68,
                "AMZN": 247.23, "GOOGL": 346.77, "GOOG": 346.12, "LLY": 1179.11, "MRNA": 61.82, "MORN": 172.48},
     "note": "Fri 7/17. Closes fetched T+1 (Yahoo). SPCX -5.43% (131.11->123.99) => SpaceX ~$4.58B (disclosed "
             "shares). BPTIX NAV 270.95 (-2.37%), AUM 16.3B. Scoring: all methods slightly UNDER but modest; optimal "
             "-0.07 best, fund_6/30 -0.14, fund_3/31 -0.47 worst. Big down day: SPCX -5.4% + TSLA -2.6% "
             "(391.06->380.84) both dragged. AUM 16.7B->16.3B vs NAV -2.37% => ~-$0.01B net outflow (nearly all "
             "market; cumulative ~$3.0B). Leverage 1.069 (borrowings model, entering net $16.7B). SpaceX weight "
             "30.3%. Watch: baskets under-predicted on this week's SpaceX-down days (7/13/16/17) -> weak hint the "
             "SpaceX weight may run a touch high, but not consistent (7/14 was over) -> no action yet."},
    {"date": "2026-07-20", "spcx": 119.85, "actual_nav": 267.08, "aum": 16.3e9,
     "closes": {"ACGL": 101.83, "BIRK": 42.77, "CHH": 109.96, "CSGP": 29.68, "FDS": 255.79,
                "FIG": 24.02, "GLPI": 44.66, "GWRE": 149.19, "H": 189.55, "HEI": 340.44,
                "HEI-A": 248.18, "IDXX": 563.81, "IT": 141.06, "KNSL": 350.13, "MSCI": 625.11,
                "MTN": 146.08, "ONON": 37.65, "RRR": 64.94, "SCHW": 102.54, "SHOP": 124.48,
                "SPOT": 492.32, "TSLA": 369.57, "VRSK": 201.79,
                "AMZN": 249.99, "GOOGL": 351.99, "GOOG": 351.37, "LLY": 1146.90, "MRNA": 59.49, "MORN": 171.76},
     "note": "Mon 7/20. Closes fetched T+1 (Yahoo). SPCX -3.34% (123.99->119.85) => SpaceX ~$4.43B (disclosed "
             "shares). BPTIX NAV 267.08 (-1.43%), AUM 16.3B. Scoring: all methods slightly under; fund_6/30 best "
             "(-0.12), fund_5/31 -0.28, fund_3/31 -0.76 worst. AUM flat 16.3B vs NAV -1.43% => model reads ~+$0.23B "
             "inflow (but $0.1B AUM rounding ~+/-$0.1B noise; likely ~flat-to-small-in). Leverage 1.071 (borrowings "
             "model, entering net $16.3B). SpaceX weight 29.3%."},
    {"date": "2026-07-21", "spcx": 123.54, "actual_nav": 265.85, "aum": 15.9e9,
     "closes": {"ACGL": 100.55, "BIRK": 42.22, "CHH": 108.13, "CSGP": 28.50, "FDS": 246.95,
                "FIG": 21.93, "GLPI": 44.51, "GWRE": 142.53, "H": 189.51, "HEI": 340.40,
                "HEI-A": 247.64, "IDXX": 552.46, "IT": 134.77, "KNSL": 339.46, "MSCI": 561.74,
                "MTN": 147.41, "ONON": 37.24, "RRR": 64.22, "SCHW": 99.96, "SHOP": 123.03,
                "SPOT": 493.23, "TSLA": 378.93, "VRSK": 195.25,
                "AMZN": 247.55, "GOOGL": 347.15, "GOOG": 346.19, "LLY": 1175.41, "MRNA": 59.66, "MORN": 165.70},
     "note": "Tue 7/21. Closes fetched T+1 (Yahoo). SPCX +3.08% (119.85->123.54) => SpaceX ~$4.56B (disclosed "
             "shares). BPTIX NAV 265.85 (-0.46%), AUM 15.9B. Scoring: all methods OVER (actual below baskets); "
             "optimal +0.41 best, fund_5/31 +0.44, fund_6/30 +0.56, fund_3/31 +1.22 worst. REVERSE HEDGE: SpaceX "
             "+3.1% and TSLA +2.5% UP, yet NAV -0.46% -> public mid-caps got crushed (MSCI -10.1%, FIG -8.7%, GWRE "
             "-4.5%, IT -4.5%, FDS -3.5%) = classic mid-cap dispersion miss (fund overweight those vs snapshot), NOT "
             "SpaceX. AUM 16.3B->15.9B => ~-$0.33B net outflow. Leverage 1.071 (borrowings model, entering net "
             "$16.3B). SpaceX weight 28.4%."},
    {"date": "2026-07-22", "spcx": 115.26, "actual_nav": 257.64, "aum": 15.3e9,
     "closes": {"ACGL": 98.63, "BIRK": 42.97, "CHH": 108.00, "CSGP": 27.69, "FDS": 245.21,
                "FIG": 21.47, "GLPI": 44.71, "GWRE": 133.97, "H": 187.43, "HEI": 335.24,
                "HEI-A": 244.25, "IDXX": 545.00, "IT": 132.10, "KNSL": 325.64, "MSCI": 570.95,
                "MTN": 144.93, "ONON": 36.65, "RRR": 63.89, "SCHW": 100.80, "SHOP": 118.42,
                "SPOT": 474.16, "TSLA": 374.01, "VRSK": 192.28,
                "AMZN": 244.85, "GOOGL": 342.09, "GOOG": 341.91, "LLY": 1163.01, "MRNA": 58.07, "MORN": 166.83},
     "note": "Wed 7/22. Closes fetched T+1 (Yahoo). SPCX -6.70% (123.54->115.26) => SpaceX ~$4.26B (disclosed "
             "shares). BPTIX NAV 257.64 (-3.09%), AUM 15.3B. Scoring: fund_6/30 NAILED it (257.64 = actual, 0.00). "
             "KEY: this was the week's BIGGEST SpaceX move (-6.7%) and fund_6/30 was EXACT -> kills the 'SpaceX weight "
             "runs high' worry from last week (that would show max under here). fund_6/30 over 7/13-7/22 is UNBIASED "
             "(mean -0.03, sd 0.29, n=8); misses are mid-cap dispersion (7/16 rip, 7/21 crash), not SpaceX/leverage. "
             "Broad down day: SPCX -6.7% + public weak (GWRE -6.0%, KNSL -4.1%). AUM 15.9B->15.3B => ~-$0.11B net "
             "outflow (cumulative ~$3.2B). Leverage 1.072 (borrowings model, entering net $15.9B). SpaceX weight "
             "30.0%. Basket healthy -> no v3.1 change needed."},
    {"date": "2026-07-23", "spcx": 118.24, "actual_nav": 251.41, "aum": None,
     "closes": {"ACGL": 100.10, "BIRK": 40.61, "CHH": 108.00, "CSGP": 27.14, "FDS": 243.96,
                "FIG": 20.00, "GLPI": 44.42, "GWRE": 131.38, "H": 183.62, "HEI": 340.54,
                "HEI-A": 248.87, "IDXX": 539.37, "IT": 133.69, "KNSL": 332.28, "MSCI": 552.51,
                "MTN": 144.06, "ONON": 34.84, "RRR": 62.78, "SCHW": 101.61, "SHOP": 112.00,
                "SPOT": 468.99, "TSLA": 319.69, "VRSK": 193.17,
                "AMZN": 233.66, "GOOGL": 317.69, "GOOG": 318.34, "LLY": 1185.87, "MRNA": 57.02, "MORN": 167.57},
     "note": "Thu 7/23. Closes fetched T+1 (Yahoo). AUM NOT CAPTURED (Morningstar only shows current; the 7/23 "
             "snapshot was missed) -> aum=None, so AUM/flow are model carry-forward estimates (~$14.93B, which "
             "happens to match 7/24's reported 14.9B -> validates the carry-forward), NOT reported figures; backfill "
             "if found. SPCX +2.59% (115.26->118.24) => SpaceX ~$4.37B (disclosed shares). BPTIX NAV 251.41 (-2.42%). "
             "Scoring: TSLA-CRASH day = textbook underweight-TSLA confirmation - errors ordered by TSLA weight: "
             "fund_3/31 (high TSLA) -2.16 (huge under), fund_6/30 -0.21, optimal +0.11 best; using 6/30 weights "
             "saved ~2 pts vs 3/31. THE DRIVER: TSLA -14.5% (319.69 vs 374.01, earnings) + growth selloff (GOOGL "
             "-7.1%, AMZN -4.6%, SHOP -5.4%); SpaceX UP +2.6% couldn't offset. Leverage ~1.075 (borrowings model, "
             "entering net $15.3B). SpaceX weight 29.1%."},
    {"date": "2026-07-24", "spcx": 115.07, "actual_nav": 252.42, "aum": 14.9e9,
     "closes": {"ACGL": 103.36, "BIRK": 40.63, "CHH": 110.52, "CSGP": 27.66, "FDS": 254.36,
                "FIG": 21.12, "GLPI": 45.17, "GWRE": 138.23, "H": 187.13, "HEI": 349.61,
                "HEI-A": 253.40, "IDXX": 544.32, "IT": 140.50, "KNSL": 349.10, "MSCI": 550.79,
                "MTN": 145.72, "ONON": 35.82, "RRR": 63.92, "SCHW": 101.97, "SHOP": 113.75,
                "SPOT": 482.66, "TSLA": 313.03, "VRSK": 201.34,
                "AMZN": 232.11, "GOOGL": 319.74, "GOOG": 319.09, "LLY": 1196.03, "MRNA": 54.07, "MORN": 172.61},
     "note": "Fri 7/24. Closes fetched T+1 (Yahoo). SPCX -2.68% (118.24->115.07) => SpaceX ~$4.25B (disclosed "
             "shares). BPTIX NAV 252.42 (+0.40%), AUM 14.9B. Scoring: all methods slightly under; optimal -0.36 best, "
             "fund_6/30 -0.61, fund_3/31 -1.12 worst (still TSLA-ordered). HEDGE AGAIN: SPCX -2.7% but NAV +0.40% -> "
             "public rebounded (KNSL +5.1%, GWRE +5.2%, VRSK +4.2%, FDS +4.3%) as TSLA bled a bit more (-2.1%). AUM "
             "14.9B (flow ~-$0.09B, approx due to 7/23 gap). Leverage 1.077 (borrowings model, entering est net "
             "~$14.9B). SpaceX weight 30.5%. fund_6/30 over 7/13-7/24: mean -0.11, sd 0.31 (n=10) - still healthy; "
             "slight under-bias from the TSLA-crash-regime days."},
    {"date": "2026-07-27", "spcx": 113.50, "actual_nav": 257.38, "aum": 15.2e9,
     "closes": {"ACGL": 103.88, "BIRK": 41.55, "CHH": 113.12, "CSGP": 29.17, "FDS": 265.90,
                "FIG": 22.94, "GLPI": 45.04, "GWRE": 149.28, "H": 191.18, "HEI": 357.15,
                "HEI-A": 259.42, "IDXX": 556.20, "IT": 147.45, "KNSL": 361.55, "MSCI": 571.03,
                "MTN": 148.28, "ONON": 37.06, "RRR": 65.07, "SCHW": 104.18, "SHOP": 126.88,
                "SPOT": 494.72, "TSLA": 309.22, "VRSK": 206.66,
                "AMZN": 231.39, "GOOGL": 326.56, "GOOG": 326.57, "LLY": 1197.53, "MRNA": 55.63, "MORN": 182.43},
     "note": "Mon 7/27. Closes fetched T+1 (Yahoo). (IT close was null in Yahoo's daily bar -- a data glitch; used "
             "the meta regularMarketPrice 147.45, timestamped 7/27 16:00 ET = the actual close, not a proxy.) SPCX "
             "-1.36% (115.07->113.50) => SpaceX ~$4.19B (disclosed shares). BPTIX NAV 257.38 (+1.97%), AUM 15.2B. "
             "Scoring: ALL methods UNDER by a lot; fund_6/30 -0.80 best, fund_3/31 -2.07 worst (TSLA-ordered). HEDGE "
             "AGAIN (4th in 2 wks): SPCX -1.4% & TSLA -1.2% DOWN but NAV +1.97% -> public ripped (SHOP +11.5%, GWRE "
             "+8.0%, MORN +5.7%, IT +4.9%, FDS +4.5%). AUM 14.9B->15.2B => ~+$0.01B (flat flow; rise is ~all market). "
             "Leverage 1.077 (borrowings model, entering net $14.9B). SpaceX weight 29.8%. WATCH: fund_6/30 now UNDER "
             "3 straight & growing (7/23 -0.21, 7/24 -0.61, 7/27 -0.80; 11-day mean -0.17) -> public sleeve "
             "outperforming the 6/30 snapshot (intra-quarter drift toward the winning mid-caps), NOT SpaceX/leverage. "
             "If it persists ~5d or mean bias > -0.3, refresh public weights (lean on recalibrate-implied / optimal); "
             "else hold 6/30 until the 9/30 NPORT."},
    {"date": "2026-07-28", "spcx": 116.41, "actual_nav": 264.20, "aum": 15.5e9,
     "closes": {"ACGL": 106.48, "BIRK": 41.85, "CHH": 114.64, "CSGP": 30.33, "FDS": 283.87,
                "FIG": 24.38, "GLPI": 45.85, "GWRE": 159.40, "H": 188.83, "HEI": 363.44,
                "HEI-A": 263.25, "IDXX": 569.54, "IT": 155.84, "KNSL": 370.26, "MSCI": 579.39,
                "MTN": 157.08, "ONON": 37.89, "RRR": 66.13, "SCHW": 105.97, "SHOP": 130.28,
                "SPOT": 511.56, "TSLA": 307.44, "VRSK": 212.26,
                "AMZN": 230.86, "GOOGL": 333.71, "GOOG": 332.60, "LLY": 1220.66, "MRNA": 55.81, "MORN": 194.12},
     "note": "Tue 7/28. Closes fetched T+1 (Yahoo). SPCX +2.56% (113.50->116.41) => SpaceX ~$4.30B (disclosed "
             "shares). BPTIX NAV 264.20 (+2.65%), AUM 15.5B. Scoring: all methods UNDER again; optimal -0.56 best, "
             "fund_6/30 -0.69, fund_3/31 -1.20 worst. BROAD RALLY (both sleeves): SPCX +2.6% AND public ripped again "
             "(FDS +6.8%, GWRE +6.8%, MORN +6.4%, MTN +5.9%, IT +5.7%); only TSLA -0.6%. AUM 15.2B->15.5B vs NAV "
             "+2.65% => ~-$0.10B net outflow. Leverage 1.076 (borrowings model, entering net $15.2B). SpaceX weight "
             "28.8%. WATCH ESCALATING: fund_6/30 UNDER 4 straight (7/23 -0.21, 7/24 -0.61, 7/27 -0.80, 7/28 -0.69; "
             "12-day mean -0.21, nearing the -0.3 trigger). Fits a mid-cap rally where the fund (buy-and-hold, lets "
             "winners run) out-runs our DAILY-REBALANCED constant-6/30-weight basket. Investigating whether making "
             "fund_6/30 buy-and-hold (drift 6/30 SHARES, not re-impose weights) removes it -- same hold-shares "
             "insight as v3/Leon."},
    {"date": "2026-07-29", "spcx": 112.55, "actual_nav": 261.52, "aum": None,
     "closes": {"ACGL": 104.55, "BIRK": 41.53, "CHH": 115.65, "CSGP": 29.83, "FDS": 282.04,
                "FIG": 24.76, "GLPI": 46.01, "GWRE": 167.26, "H": 186.02, "HEI": 355.23,
                "HEI-A": 257.36, "IDXX": 569.77, "IT": 165.65, "KNSL": 376.67, "MSCI": 582.92,
                "MTN": 160.01, "ONON": 37.91, "RRR": 65.61, "SCHW": 104.47, "SHOP": 129.17,
                "SPOT": 524.01, "TSLA": 298.32, "VRSK": 213.15,
                "AMZN": 226.65, "GOOGL": 336.71, "GOOG": 335.76, "LLY": 1210.02, "MRNA": 54.49, "MORN": 198.66},
     "note": "Wed 7/29. Closes fetched T+1 (Yahoo). AUM NOT PROVIDED (user gave 7/30 not 7/29) -> aum=None; AUM/flow "
             "are carry-forward estimates (~$15.34B), NOT reported; backfill if available. SPCX -3.32% "
             "(116.41->112.55) => SpaceX ~$4.16B (disclosed shares). BPTIX NAV 261.52 (-1.01%). Scoring: all methods "
             "under; optimal -0.47 best, fund_6/30 -0.59, fund_3/31 -1.25 worst (5th straight fund_6/30 under). SPCX "
             "-3.3% + TSLA -3.0% dragged; mid-caps still up (IT +6.3%, GWRE +4.9%). Leverage 1.074 (borrowings model, "
             "entering net $15.5B). SpaceX weight 29.0%."},
    {"date": "2026-07-30", "spcx": 112.20, "actual_nav": 255.92, "aum": 15.4e9,
     "closes": {"ACGL": 101.14, "BIRK": 40.49, "CHH": 111.66, "CSGP": 29.46, "FDS": 263.03,
                "FIG": 23.76, "GLPI": 44.71, "GWRE": 153.21, "H": 176.68, "HEI": 354.17,
                "HEI-A": 256.15, "IDXX": 558.80, "IT": 152.92, "KNSL": 355.87, "MSCI": 575.74,
                "MTN": 152.82, "ONON": 37.10, "RRR": 64.93, "SCHW": 104.33, "SHOP": 122.40,
                "SPOT": 522.61, "TSLA": 308.85, "VRSK": 200.35,
                "AMZN": 235.50, "GOOGL": 333.66, "GOOG": 333.68, "LLY": 1154.97, "MRNA": 57.92, "MORN": 193.12},
     "note": "Thu 7/30. Closes fetched T+1 (Yahoo). SPCX -0.31% (112.55->112.20) => SpaceX ~$4.15B (disclosed "
             "shares). BPTIX NAV 255.92 (-2.14%), AUM 15.4B. Scoring: ALL methods massively OVER (+1.05 to +2.45); "
             "optimal +1.05 best, fund_6/30 +1.60, fund_3/31 +2.45 worst. MID-CAP WINNERS REVERSED HARD: the names "
             "that ripped all week retraced (GWRE -8.4%, IT -7.7%, FDS -6.7%, VRSK -6.0%, KNSL -5.5%, H -5.0%); TSLA "
             "+3.5% & AMZN +3.9% bounced; SPCX flat. KEY: fund_6/30 flipped -0.59 (under, rally) -> +1.60 (over, "
             "reversal) => the error is TWO-DIRECTIONAL, constant-weight mis-tracking the concentrated winners BOTH "
             "ways (under-captures the run-up AND the crash). STRENGTHENS the buy-and-hold fix (14-day SD jumped to "
             "0.59). FLOW: 7/28->7/30 AUM 15.5->15.4B while NAV fell ~3.1% => ~+$0.38B net INFLOW over 2 days (first "
             "real inflow in weeks; can't split 7/29 vs 7/30 due to the 7/29 gap). Leverage 1.075 (borrowings model, "
             "entering est net ~$15.34B). SpaceX weight 28.3%."},
    {"date": "2026-07-31", "spcx": 108.37, "actual_nav": 251.24, "aum": 14.7e9,
     "closes": {"ACGL": 100.53, "BIRK": 38.72, "CHH": 111.49, "CSGP": 28.76, "FDS": 263.20,
                "FIG": 24.32, "GLPI": 44.79, "GWRE": 151.94, "H": 174.06, "HEI": 356.36,
                "HEI-A": 257.28, "IDXX": 559.07, "IT": 151.02, "KNSL": 356.42, "MSCI": 572.24,
                "MTN": 149.38, "ONON": 36.24, "RRR": 64.44, "SCHW": 105.24, "SHOP": 117.15,
                "SPOT": 499.94, "TSLA": 311.21, "VRSK": 194.85,
                "AMZN": 271.58, "GOOGL": 356.13, "GOOG": 356.65, "LLY": 1148.84, "MRNA": 54.82, "MORN": 192.57},
     "note": "Fri 7/31. Closes fetched T+1 (Yahoo). SPCX -3.41% (112.20->108.37, under $110) => SpaceX ~$4.00B "
             "(disclosed shares). BPTIX NAV 251.24 (-1.83%), AUM 14.7B. Scoring: all methods slightly OVER; ronb "
             "+0.26 best, fund_5/31 +0.47, fund_6/30 +0.79, fund_3/31 +1.12 worst (2nd straight over -> constant-"
             "weight variance, BH fix pending). SpaceX drag + mixed public: AMZN +15.3% & GOOGL +6.7% RIPPED "
             "(earnings) but SHOP -4.3%, BIRK -4.4%, VRSK -2.7%, H -1.5% offset. FLOW: AUM 15.4B->14.7B vs NAV -1.83% "
             "=> ~-$0.42B net outflow (the 7/29-30 inflow reversed; redemptions back). Leverage 1.075 (borrowings "
             "model, entering net $15.4B). SpaceX weight 28.1%."},
    {"date": "2026-08-03", "spcx": 114.53, "actual_nav": 257.40, "aum": 15.0e9,
     "closes": {"ACGL": 101.12, "BIRK": 38.88, "CHH": 108.47, "CSGP": 30.03, "FDS": 269.68,
                "FIG": 24.92, "GLPI": 44.81, "GWRE": 157.33, "H": 171.58, "HEI": 360.44,
                "HEI-A": 261.82, "IDXX": 567.84, "IT": 151.53, "KNSL": 360.44, "MSCI": 574.43,
                "MTN": 149.23, "ONON": 37.95, "RRR": 65.61, "SCHW": 105.87, "SHOP": 117.01,
                "SPOT": 486.33, "TSLA": 322.08, "VRSK": 193.11,
                "AMZN": 284.02, "GOOGL": 373.51, "GOOG": 372.47, "LLY": 1121.36, "MRNA": 55.14, "MORN": 198.93},
     "note": "Mon 8/3. Closes fetched T+1 (Yahoo). (BPTIX NAV 257.40 from Yahoo meta, timestamped 8/3 20:08 ET = "
             "post-close NAV posting; the daily bar lagged null, same as IT 7/27 -- real close, not a proxy.) SPCX "
             "+5.68% (108.37->114.53) => SpaceX ~$4.23B (disclosed shares). BPTIX NAV 257.40 (+2.45%), AUM 15.0B. "
             "Scoring: all methods slightly over; ronb +0.14 best, optimal +0.36, fund_6/30 +0.48, fund_3/31 +0.92 "
             "worst (3rd straight over, magnitude decaying 1.60->0.79->0.48). RISK-ON: SpaceX BOUNCED +5.7% AND "
             "public up (AMZN +4.6%, GOOGL +4.9%, TSLA +3.5%, MORN +3.3%); only SPOT -2.7%, H -1.4% down. AUM "
             "14.7B->15.0B vs NAV +2.45% => ~-$0.06B net outflow (rise is market). Leverage 1.078 (borrowings model, "
             "entering net $14.7B). SpaceX weight 28.4%."},
    {"date": "2026-08-04", "spcx": 125.33, "actual_nav": 267.59, "aum": None,
     "closes": {"ACGL": 99.52, "BIRK": 37.86, "CHH": 108.61, "CSGP": 29.82, "FDS": 274.49,
                "FIG": 27.12, "GLPI": 44.41, "GWRE": 160.31, "H": 173.60, "HEI": 367.66,
                "HEI-A": 265.96, "IDXX": 588.09, "IT": 185.79, "KNSL": 362.82, "MSCI": 571.47,
                "MTN": 149.59, "ONON": 37.61, "RRR": 64.27, "SCHW": 106.35, "SHOP": 123.30,
                "SPOT": 478.17, "TSLA": 327.35, "VRSK": 192.80,
                "AMZN": 277.42, "GOOGL": 377.65, "GOOG": 375.35, "LLY": 1115.68, "MRNA": 56.99, "MORN": 200.25},
     "note": "Tue 8/4. Closes fetched T+1 (Yahoo). AUM not provided (user gave 8/10 only) -> aum=None, "
             "carry-forward est. SPCX +15.65% (108.37->125.33) => SpaceX ~$4.63B (disclosed shares). BPTIX NAV "
             "267.59 (+3.96%). fund_6/30 best +0.15; SpaceX ripped +15.7%; IT +22.7% (earnings). Leverage ~1.08. "
             "SpaceX weight ~28%. [7/31 disclosure now in hand: true L=1.10, SpaceX 24.8% gross -- see analysis.]"},
    {"date": "2026-08-05", "spcx": 108.27, "actual_nav": 259.10, "aum": None,
     "closes": {"ACGL": 99.09, "BIRK": 37.48, "CHH": 111.79, "CSGP": 30.21, "FDS": 278.03,
                "FIG": 28.15, "GLPI": 43.81, "GWRE": 160.33, "H": 178.91, "HEI": 366.80,
                "HEI-A": 266.46, "IDXX": 584.78, "IT": 186.41, "KNSL": 370.97, "MSCI": 571.87,
                "MTN": 151.26, "ONON": 38.19, "RRR": 60.97, "SCHW": 108.02, "SHOP": 144.24,
                "SPOT": 482.23, "TSLA": 321.55, "VRSK": 188.75,
                "AMZN": 272.65, "GOOGL": 362.43, "GOOG": 360.13, "LLY": 1169.86, "MRNA": 56.26, "MORN": 199.33},
     "note": "Wed 8/5. Closes fetched T+1 (Yahoo). aum=None (carry-forward est). SPCX -13.61% "
             "(125.33->108.27) => SpaceX ~$4.00B. BPTIX NAV 259.10 (-3.17%). fund_6/30 -0.96 (SpaceX -13.6% day), fund_5/31 best -0.81; SpaceX gave back the +15.7%; "
             "SHOP +17% up. Leverage ~1.08. SpaceX weight ~28%."},
    {"date": "2026-08-06", "spcx": 114.92, "actual_nav": 262.46, "aum": None,
     "closes": {"ACGL": 99.29, "BIRK": 37.20, "CHH": 109.73, "CSGP": 29.58, "FDS": 274.58,
                "FIG": 23.97, "GLPI": 43.86, "GWRE": 160.03, "H": 178.88, "HEI": 363.29,
                "HEI-A": 263.93, "IDXX": 590.00, "IT": 184.82, "KNSL": 376.37, "MSCI": 567.23,
                "MTN": 146.71, "ONON": 37.34, "RRR": 62.91, "SCHW": 107.66, "SHOP": 147.44,
                "SPOT": 475.07, "TSLA": 319.53, "VRSK": 189.75,
                "AMZN": 272.26, "GOOGL": 357.75, "GOOG": 356.62, "LLY": 1191.94, "MRNA": 53.86, "MORN": 196.57},
     "note": "Thu 8/6. Closes fetched T+1 (Yahoo). aum=None (carry-forward est). SPCX +6.14% "
             "(108.27->114.92) => SpaceX ~$4.24B. BPTIX NAV 262.46 (+1.30%). fund_6/30 -0.06 (near-exact), fund_4/30 best -0.01. Leverage 1.076. SpaceX weight "
             "~28%."},
    {"date": "2026-08-07", "spcx": 133.11, "actual_nav": 277.05, "aum": None,
     "closes": {"ACGL": 98.48, "BIRK": 38.45, "CHH": 106.66, "CSGP": 30.24, "FDS": 285.57,
                "FIG": 23.29, "GLPI": 44.14, "GWRE": 170.53, "H": 177.71, "HEI": 367.58,
                "HEI-A": 266.31, "IDXX": 586.67, "IT": 185.60, "KNSL": 373.76, "MSCI": 563.17,
                "MTN": 148.83, "ONON": 37.55, "RRR": 61.88, "SCHW": 107.60, "SHOP": 151.57,
                "SPOT": 488.14, "TSLA": 328.58, "VRSK": 191.82,
                "AMZN": 274.48, "GOOGL": 354.30, "GOOG": 353.47, "LLY": 1185.71, "MRNA": 59.17, "MORN": 200.66},
     "note": "Fri 8/7. Closes fetched T+1 (Yahoo). aum=None (carry-forward est). SPCX +15.83% "
             "(114.92->133.11) => SpaceX ~$4.92B. BPTIX NAV 277.05 (+5.56%). fund_6/30 +0.28, ronb best -0.08; SpaceX ripped again +15.8%; "
             "SHOP/GWRE strong. Leverage ~1.08. SpaceX weight ~29%."},
    {"date": "2026-08-10", "spcx": 138.74, "actual_nav": 281.53, "aum": 16.3e9,
     "closes": {"ACGL": 98.25, "BIRK": 39.72, "CHH": 102.75, "CSGP": 31.48, "FDS": 284.12,
                "FIG": 25.39, "GLPI": 42.81, "GWRE": 172.94, "H": 170.08, "HEI": 363.94,
                "HEI-A": 265.08, "IDXX": 595.76, "IT": 193.17, "KNSL": 368.60, "MSCI": 563.08,
                "MTN": 146.26, "ONON": 38.78, "RRR": 61.29, "SCHW": 107.99, "SHOP": 155.18,
                "SPOT": 511.82, "TSLA": 330.88, "VRSK": 181.18,
                "AMZN": 278.09, "GOOGL": 357.52, "GOOG": 355.84, "LLY": 1231.94, "MRNA": 59.81, "MORN": 201.03},
     "note": "Mon 8/10. Closes fetched T+1 (Yahoo). SPCX +4.23% (133.11->138.74) => SpaceX ~$5.13B "
             "(disclosed shares). BPTIX NAV 281.53 (+1.62%), AUM 16.3B. fund_6/30 +0.17, actual best -0.04. SpaceX recovered SPCX 108->139 "
             "(+28%) over the week -> NAV 257->281 (+9.4%). AUM 15.0B->16.3B (2-day-gap flow uncertain). Leverage "
             "~1.08 (engine; 7/31 disclosure says true L=1.10 -- correction pending). SpaceX weight ~29%."},
    {"date": "2026-08-11", "spcx": 133.29, "actual_nav": 276.15, "aum": 15.9e9,
     "closes": {"ACGL": 98.26, "BIRK": 37.47, "CHH": 102.63, "CSGP": 31.12, "FDS": 282.95,
                "FIG": 24.87, "GLPI": 42.64, "GWRE": 176.65, "H": 172.64, "HEI": 366.92,
                "HEI-A": 264.72, "IDXX": 586.64, "IT": 187.27, "KNSL": 374.60, "MSCI": 561.71,
                "MTN": 147.66, "ONON": 30.91, "RRR": 63.04, "SCHW": 107.70, "SHOP": 152.61,
                "SPOT": 501.00, "TSLA": 332.81, "VRSK": 180.97,
                "AMZN": 272.27, "GOOGL": 343.80, "GOOG": 343.00, "LLY": 1215.02, "MRNA": 60.57, "MORN": 195.38},
     "note": "Tue 8/11. Closes fetched T+1 (Yahoo). SPCX -3.93% (138.74->133.29) => SpaceX ~$4.92B "
             "(disclosed shares). BPTIX NAV 276.15 (-1.91%), AUM 15.9B. Scoring: fund_5/31 best -0.03, fund_6/30 +0.15, fund_3/31 +1.06 worst. SPCX -3.9% led the drop; ONON "
             "-20.3% crashed (earnings), GOOGL -3.8%, VRSK -0.1%; GWRE +2.1%, SHOP -1.7% mixed. AUM 16.3B->15.9B vs "
             "NAV -1.91% => ~-$0.09B net outflow. Leverage 1.079 (model) but the slow-var tracker reads ~1.10-1.11 "
             "(disclosure-confirmed 1.10) -> ALERT active, model leverage understated."},
    {"date": "2026-08-12", "spcx": 146.15, "actual_nav": 282.98, "aum": 16.3e9,
     "closes": {"ACGL": 97.29, "BIRK": 36.74, "CHH": 105.54, "CSGP": 30.50, "FDS": 277.99,
                "FIG": 23.75, "GLPI": 43.10, "GWRE": 173.08, "H": 178.37, "HEI": 373.10,
                "HEI-A": 272.21, "IDXX": 570.58, "IT": 179.46, "KNSL": 373.52, "MSCI": 563.01,
                "MTN": 148.36, "ONON": 31.01, "RRR": 63.09, "SCHW": 109.34, "SHOP": 150.41,
                "SPOT": 489.60, "TSLA": 327.51, "VRSK": 180.38,
                "AMZN": 267.28, "GOOGL": 343.54, "GOOG": 342.37, "LLY": 1220.28, "MRNA": 63.67, "MORN": 197.51},
     "note": "Wed 8/12. Closes fetched T+1 (Yahoo). SPCX +9.65% (133.29->146.15) => SpaceX ~$5.40B "
             "(disclosed shares). BPTIX NAV 282.98 (+2.47%), AUM 16.3B. Scoring: fund_3/31 & fund_5/31 best (+0.05), fund_6/30 +0.51, ronb +1.41 worst (big-SpaceX-up day). Mark baskets: v4 -0.12, v4.1 +0.01. SpaceX ripped +9.7% and carried the "
             "day; public mixed (H +3.3%, HEI-A +2.8%, SCHW +1.5% up; IT -4.2%, MORN +1.1%, FDS -1.8%). AUM "
             "15.9B->16.3B vs NAV +2.47% => ~-$0.01B (flat flow). Leverage 1.072 (model) vs slow-var tracker ~1.09."},
    {"date": "2026-08-13", "spcx": 141.29, "actual_nav": 285.41, "aum": 16.4e9,
     "closes": {"ACGL": 98.03, "BIRK": 41.00, "CHH": 104.57, "CSGP": 33.05, "FDS": 287.18,
                "FIG": 26.35, "GLPI": 43.65, "GWRE": 182.62, "H": 179.85, "HEI": 371.56,
                "HEI-A": 272.49, "IDXX": 566.93, "IT": 183.30, "KNSL": 376.97, "MSCI": 575.24,
                "MTN": 145.42, "ONON": 31.59, "RRR": 62.04, "SCHW": 110.06, "SHOP": 158.53,
                "SPOT": 498.24, "TSLA": 339.96, "VRSK": 185.94,
                "AMZN": 265.13, "GOOGL": 346.36, "GOOG": 343.94, "LLY": 1209.00, "MRNA": 63.65, "MORN": 206.89},
     "note": "Thu 8/13. Closes fetched T+1 (Yahoo). SPCX -3.33% (146.15->141.29) => SpaceX ~$5.22B "
             "(disclosed shares). BPTIX NAV 285.41 (+0.86%), AUM 16.4B. Scoring: blend best -0.12, fund_6/30 -0.37, ronb -0.73 worst; mark baskets v4 +0.04, v4.1 +0.15. HEDGE AGAIN: SPCX -3.3% but NAV UP "
             "+0.86% -> public ripped broadly (BIRK +11.6%, FIG +11.0%, CSGP +8.4%, GWRE +5.5%, SHOP +5.4%, MORN "
             "+4.8%, TSLA +3.8%). AUM 16.3B->16.4B vs NAV +0.86% => ~-$0.04B (flat-to-small outflow). Leverage 1.070 "
             "(model) vs slow-var tracker ~1.09."},
    {"date": "2026-08-14", "spcx": 140.00, "actual_nav": 283.98, "aum": 16.3e9,
     "closes": {"ACGL": 98.71, "BIRK": 39.35, "CHH": 104.44, "CSGP": 32.38, "FDS": 283.49,
                "FIG": 25.42, "GLPI": 43.57, "GWRE": 175.59, "H": 180.98, "HEI": 374.67,
                "HEI-A": 274.99, "IDXX": 550.96, "IT": 181.09, "KNSL": 379.19, "MSCI": 569.13,
                "MTN": 148.30, "ONON": 32.22, "RRR": 63.66, "SCHW": 111.09, "SHOP": 154.32,
                "SPOT": 512.82, "TSLA": 342.27, "VRSK": 181.67,
                "AMZN": 262.65, "GOOGL": 345.90, "GOOG": 343.54, "LLY": 1180.16, "MRNA": 63.32, "MORN": 207.41},
     "note": "Fri 8/14. Closes fetched T+1 (Yahoo). SPCX -0.91% (141.29->140.00) => SpaceX ~$5.17B "
             "(disclosed shares). BPTIX NAV 283.98 (-0.50%), AUM 16.3B. Scoring: fund_5/31 best -0.07, fund_6/30 & blend +0.11, ronb +0.55 worst; mark baskets v4 -0.18, v4.1 -0.05 (v4.1 closest today). Quiet day: SPCX -0.9%; public mixed "
             "(SPOT +2.9%, SCHW +0.9%, TSLA +0.7% up; GWRE -3.8%, BIRK -4.0%, IDXX -2.8%, FIG -3.5% down). AUM "
             "16.4B->16.3B vs NAV -0.50% => ~-$0.02B (flat). Leverage 1.070 (model) vs slow-var tracker ~1.09."},
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


# 7/31 as-of disclosure (Baron): top-10 % of GROSS (total investments), + Long Equity 110% / Cash -10%.
DISCLOSED_7_31 = {"weights_gross": {"TSLA": 12.4, "SCHW": 5.3, "MSCI": 4.7, "SHOP": 4.4, "H": 4.3,
                                    "ACGL": 4.0, "SPOT": 3.9, "FDS": 3.7, "GWRE": 3.2},
                  "spacex_gross": 24.8, "leverage": 1.10, "anchor": "2026-07-31",
                  "nav": 251.24, "aum": 14.7e9, "spcx": 108.37}


def _build_static_basket(anchor_date, w_pub, spx_gross_pct, L, disclosed=None, prior_shares=None):
    """Build a STATIC mark basket (shares per BPTIX) anchored at `anchor_date`.
    w_pub = public relative weights (any scaling; renormalized to the public sleeve).
    SpaceX uses the exact disclosed 36.94M share count / shares-out(anchor). `disclosed` overrides
    the given public names with their disclosed %-of-gross. Returns (shares_dict, borrow_per_bptix)."""
    e = next(x for x in ENTRIES if x["date"] == anchor_date)
    nav = e["actual_nav"]; px = dict(e["closes"]); px["SPCX"] = e["spcx"]
    aum = e["aum"] or None
    # anchor AUM: use the entry's if present, else infer from a neighbouring reported day
    if aum is None:
        aum = 14.7e9  # 7/31 fallback
    so = aum / nav
    gpb = nav * L; borrow = nav * (L - 1)
    spx_val = (SPX_SHARES_DISCLOSED / so) * e["spcx"]
    val = {}
    dw = (disclosed or {})
    for t in dw:
        val[t] = dw[t] / 100.0 * gpb
    tail = [t for t in w_pub if t not in dw and px.get(t)]
    rem = gpb - spx_val - sum(val.values())
    # TAIL = BUY-AND-HOLD (v4.1). Keep the tail's PRIOR SHARE structure and apply one uniform
    # haircut to fit the forced residual — do NOT re-impose the prior WEIGHTS, which would
    # "sell the winners / buy the losers" the fund never did. Verified on the 9 disclosed names
    # (we know their true 6/30 AND 7/31 weights): buy-and-hold predicts the 7/31 weights with
    # RMS 0.26 vs 1.25 for constant-weight, and wins on all 9 (TSLA is the extreme: -26% price,
    # constant-weight says 15.8% of gross, truth 12.4%, buy-and-hold 11.8%).
    if prior_shares:
        bh = {t: prior_shares[t] * px[t] for t in tail if prior_shares.get(t)}
        s_bh = sum(bh.values())
        k = (rem / s_bh) if s_bh else 0.0
        for t in bh:
            val[t] = bh[t] * k
    else:                                   # no prior book (first anchor) -> weights are all we have
        tw = sum(w_pub.get(t, 0) for t in tail) or 1.0
        for t in tail:
            val[t] = rem * (w_pub.get(t, 0) / tw)
    sh = {"SPCX": SPX_SHARES_DISCLOSED / so}
    for t in val:
        if px.get(t):
            sh[t] = val[t] / px[t]
    return sh, borrow


def _load_v3_csv():
    """v3 (6/30) mark basket from its committed CSV — the PRIOR share book (all 29 names, incl the
    6 whose 6/30 price isn't in ENTRIES). Used as the buy-and-hold anchor for v4.1's tail."""
    import csv as _csv
    sh, bor = {}, 19.31
    with open(os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data",
                           "position_mark_basket_v3_2026-06-30.csv"), encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            if r["component"].startswith("CASH"):
                bor = -float(r["value_per_bptix_6_30"]); continue
            sh["SPCX" if r["component"].startswith("SPCX") else r["component"]] = float(r["shares_per_bptix"])
    return sh, bor


def _mark_basket_accuracy():
    """v4 (7/31-anchored, L=1.10) mark basket + its live tracking accuracy vs actual NAV, plus the
    v3(6/30) comparison and clean-split date. Wrapped by the caller in try/except (never break CI)."""
    import math
    W6 = _nospy(fs.WEIGHTS_6_30)
    v3_prior, _b = _load_v3_csv()
    v4, b4 = _build_static_basket("2026-07-31", W6, DISCLOSED_7_31["spacex_gross"],
                                  DISCLOSED_7_31["leverage"], DISCLOSED_7_31["weights_gross"],
                                  prior_shares=v3_prior)
    v3, b3 = _load_v3_csv()
    def mark(s, b, e):
        p = dict(e["closes"]); p["SPCX"] = e["spcx"]
        return sum(s[t] * p[t] for t in s if p.get(t)) - b
    def rms(xs): return round(math.sqrt(sum(x * x for x in xs) / len(xs)), 3) if xs else None
    def errs(basket, bor, d0, d1):
        return [mark(basket, bor, e) - e["actual_nav"]
                for e in ENTRIES if d0 <= e["date"] <= d1 and e.get("actual_nav")]
    post = errs(v4, b4, "2026-08-03", "2026-08-11")           # v4 forward (post-anchor)
    stale = errs(v3, b3, "2026-08-03", "2026-08-11")          # stale v3 now
    e = next(x for x in ENTRIES if x["date"] == "2026-07-31")
    so = e["aum"] / e["actual_nav"]
    return {
        "version": "v4.1", "anchor": "2026-07-31", "leverage": DISCLOSED_7_31["leverage"],
        "spx_sh_per_bptix": round(SPX_SHARES_DISCLOSED / so, 4),
        "spx_pct_gross": DISCLOSED_7_31["spacex_gross"], "borrow_per_bptix": round(b4, 2),
        "rms_forward": rms(post), "rms_forward_pct_nav": (round(rms(post) / 270 * 100, 3) if post else None),
        "rms_stale_v3": rms(stale), "n_forward": len(post),
        "clean_split_date": "2026-07-13",
        "note": ("v4.1 mark basket: anchored 7/31, leverage 1.10 (long 110%% / cash -10%% of NET; stocks=110%% "
                 "of net = 100%% of gross). SpaceX = 36.94M disclosed sh / shares-out = %.4f sh/BPTIX (24.8%% of "
                 "GROSS = 27.2%% of net). Top-10 = disclosed 7/31 weights; TAIL = BUY-AND-HOLD (prior 6/30 SHARES, "
                 "one uniform -6.0%% haircut to fit the forced residual) — NOT re-imposed 6/30 weights, which would "
                 "sell winners / buy losers. Validated on the 9 disclosed names (true 6/30 AND 7/31 weights known): "
                 "buy-and-hold predicts 7/31 weights at RMS 0.26 vs 1.25 constant-weight, winning on all 9. Forward "
                 "tracking (8/3+) RMS $%.2f/BPTIX (~%.2f%% NAV) vs stale-v3 $%.2f. Clean split v3->v4.1 at 2026-07-13."
                 % (SPX_SHARES_DISCLOSED / so, rms(post) or 0, (rms(post) or 0) / 270 * 100, rms(stale) or 0)),
    }


# Disclosed leverage checkpoints (gross/net) — ground truth to score the estimator against.
LEVERAGE_DISCLOSED = {"2026-07-31": 1.10}   # Baron 7/31 as-of: long equity 110% / cash -10% of net


def _slow_vars(w_pub, window=15, alert_gap=0.02, alert_days=3):
    """Track the two SLOW variables that drive basket drift but DON'T need a disclosure:

      1. SpaceX per BPTIX  = 36.94M disclosed shares / (AUM/NAV)  -> EXACT, daily.
      2. Leverage L        = solved from returns with w_spx PINNED by (1), so it's a ONE-parameter
         fit (much tighter than the 2-param regression, which is too noisy to read):
             nav_ret - w_spx*spcx_ret = (L - w_spx) * basket_ret
         L_hat = w_spx_bar + OLS slope over a rolling window.

    Why: the fixed-$1.15B-borrowings model can only drift L passively with redemptions; it CANNOT
    see Baron actively adding borrowings (July: ~$1.15B -> ~$1.47B, L 1.07 -> 1.10). This estimator
    caught that ~2-3 weeks before the 7/31 disclosure landed (~8/11).
    Emits a series + an ALERT when the estimate diverges from the model for `alert_days` running."""
    import math
    # shares-out (= AUM/NAV) only moves with FLOWS, not with the market — so on a day whose AUM
    # wasn't captured, carrying SHARES-OUT forward is far better than carrying AUM forward.
    so_by_date, so_run = {}, None
    for e in ENTRIES:
        if e.get("aum") and e.get("actual_nav"):
            so_run = e["aum"] / e["actual_nav"]
            so_by_date[e["date"]] = (so_run, False)
        elif so_run:
            so_by_date[e["date"]] = (so_run, True)           # carried forward (estimated)
    pts = []
    for i in range(1, len(ENTRIES)):
        p, c = ENTRIES[i - 1], ENTRIES[i]
        if not (c.get("actual_nav") and p.get("actual_nav") and p["date"] in so_by_date):
            continue
        navr = c["actual_nav"] / p["actual_nav"] - 1
        sr = c["spcx"] / p["spcx"] - 1
        num = den = 0.0
        for t, w in w_pub.items():
            a, b = p["closes"].get(t), c["closes"].get(t)
            if a and b and w:
                num += w * (b / a - 1); den += w
        br = num / den if den else 0.0
        so = so_by_date[p["date"]][0]                         # ENTERING shares out (known day before)
        w_spx = (SPX_SHARES_DISCLOSED / so) * p["spcx"] / p["actual_nav"]
        pts.append({"date": c["date"], "navr": navr, "sr": sr, "br": br, "w_spx": w_spx})

    def fit(win):
        d = sum(x["br"] ** 2 for x in win)
        if d < 1e-12:
            return None, None
        k = sum((x["navr"] - x["w_spx"] * x["sr"]) * x["br"] for x in win) / d
        wbar = sum(x["w_spx"] for x in win) / len(win)
        L = k + wbar
        e = [x["navr"] - (x["w_spx"] * x["sr"] + (L - x["w_spx"]) * x["br"]) for x in win]
        return L, math.sqrt(sum(v * v for v in e) / len(e))

    series, streak = [], 0
    for i in range(len(pts)):
        d = pts[i]["date"]
        so, so_est = so_by_date.get(d, (None, True))
        L15, sd15 = fit(pts[max(0, i - window + 1):i + 1]) if i + 1 >= window else (None, None)
        L10, _ = fit(pts[max(0, i - 9):i + 1]) if i + 1 >= 10 else (None, None)
        # baseline: the engine's model leverage. On an AUM-gap day feed it the CARRIED-FORWARD net
        # (shares_out x prior NAV) so it doesn't fall back to the 1.06 default and fake a gap.
        di = [x["date"] for x in ENTRIES].index(d)
        pe = ENTRIES[di - 1] if di else None
        net_prev = pe.get("aum") if (pe and pe.get("aum")) else (
            so_by_date[pe["date"]][0] * pe["actual_nav"]
            if (pe and pe["date"] in so_by_date and pe.get("actual_nav")) else None)
        L_model = LEVERAGE_FOR(d, net_prev)
        gap = (L15 - L_model) if L15 else None
        # ALERT on the estimator's OWN move vs a trailing, NON-overlapping baseline. The level of
        # L_est carries a bias (it absorbs public-basket tracking error), but that bias cancels in a
        # difference — so a SHIFT is detectable in real time, before any disclosure exists to
        # calibrate the level against. (Comparing the biased level to L_model would misfire.)
        base = [s["L_est"] for s in series[max(0, i - 25):max(0, i - 9)] if s["L_est"]]
        shift = None
        if L15 and len(base) >= 5:
            base_sorted = sorted(base)
            med = base_sorted[len(base_sorted) // 2]
            shift = L15 - med
        streak = streak + 1 if (shift is not None and abs(shift) > alert_gap) else 0
        series.append({"date": d, "shares_out_estimated": so_est, "shift": round(shift, 4) if shift is not None else None,
                       "spx_sh_per_bptix": round(SPX_SHARES_DISCLOSED / so, 4) if so else None,
                       "L_est": round(L15, 4) if L15 else None,
                       "L_est_10d": round(L10, 4) if L10 else None,
                       "L_model": round(L_model, 4), "gap": round(gap, 4) if gap is not None else None,
                       "resid_sd_pct": round(sd15 * 100, 3) if sd15 else None,
                       "L_disclosed": LEVERAGE_DISCLOSED.get(d), "alert_streak": streak})
    # CALIBRATION: the fit absorbs public-basket tracking error as well as true leverage, so its
    # LEVEL runs high. Score it against the disclosed checkpoint(s) and carry that bias forward.
    biases = [s["L_est"] - LEVERAGE_DISCLOSED[s["date"]]
              for s in series if s["L_est"] and s["date"] in LEVERAGE_DISCLOSED]
    bias = round(sum(biases) / len(biases), 4) if biases else None
    for s in series:
        s["L_est_adj"] = round(s["L_est"] - bias, 4) if (s["L_est"] and bias is not None) else None
    live = [s for s in series if s["L_est"]]
    last = live[-1] if live else None
    alert = bool(last and last["alert_streak"] >= alert_days)
    return {"window": window, "series": series, "latest": last, "alert": alert,
            "alert_gap": alert_gap, "alert_days": alert_days, "bias_vs_disclosed": bias,
            "disclosed": LEVERAGE_DISCLOSED,
            "note": ("Two SLOW variables tracked WITHOUT waiting for a disclosure. (1) SpaceX per BPTIX = "
                     "36.94M disclosed sh / (AUM/NAV) — EXACT daily. (2) Leverage — one-parameter fit with "
                     "w_spx pinned by (1); the 2-param regression is too noisy to read. This caught July's "
                     "1.07 -> 1.10 re-levering ~2-3 weeks before the 7/31 disclosure arrived (~8/11); the "
                     "fixed-borrowings model structurally cannot (it only drifts L with redemptions). "
                     "ALERT fires when L_est SHIFTS >%.2f vs its own trailing baseline for %d straight days "
                     "(bias-immune, so it works BEFORE any disclosure exists) => re-anchor the basket."
                     % (alert_gap, alert_days))}


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
    try:
        mark_basket = _mark_basket_accuracy()
    except Exception:
        mark_basket = None
    try:
        slow_vars = _slow_vars(WS.get("fund_6_30", {}))
    except Exception:
        slow_vars = None
    return {
        "meta": {
            "title": "Daily BPTIX NAV estimate — per basket-weighting vs actual",
            "method_labels": METHOD_LABELS, "methods": methods, "base": BASE,
            "window_start": BASE["date"], "backfill_dates": sorted(BACKFILL_DATES),
            "compositions": compositions, "lookthrough": lookthrough, "mark_basket": mark_basket,
            "slow_vars": slow_vars,
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
