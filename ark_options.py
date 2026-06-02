"""
ARKK JUN-18-26 options scenario model -> dashboard/data/ark_options.json

A delta-neutral vol/skew scenario tool for three strikes (78 / 80 / 83), calibrated
to the RiskView screen (2026-06-02). Two scenario axes: SPOT and BORROW (sdiv).

Mechanics (Black-Scholes with carry q = borrow − div; ARKK div ~0 so q ≈ borrow):
    F = S * exp((r - q) * T)            # forward; higher borrow -> lower forward
    call/put priced off F with each strike's CALIBRATED IV (sticky-strike: IV fixed)
    delta-neutral: P&L = option P&L − delta0 * (S - S0)   (hedge at trade delta)

So raising borrow lowers the forward -> puts gain, calls lose — exactly the
described effect — and the chart shows P&L vs spot for each option, with a borrow
toggle. All inputs are screen-calibrated; IV per strike from the user's skew read.

Pure stdlib.
"""

import json
import math
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# --- screen-calibrated constants (RiskView ARKK JUN-18-26, 2026-06-02) ---
SPOT0 = 79.80           # uBid/uAsk 79.80/79.81 -> mid ~79.805, use 79.80
T_BUS = 12 / 252        # 12 business days, 252/yr  (user: 12 bd; ~16 calendar)
R = 0.0415              # rate shown
BORROW0 = 0.02          # current sdiv ~2% (Jun-18 row 2.01%)
DIV = 0.0               # ARKK ~ no dividend; q = borrow - div = borrow

# Per the user: which option to use at each strike + its SpiderRock implied vol.
#   78 -> PUT only,   IV 38.4%  (OTM put)
#   80 -> CALL + PUT, IV 37.5%  (~ATM, both legs)
#   83 -> CALL only,  IV 37.3%  (OTM call)
# Sticky-strike: IV held fixed as spot/borrow move.
STRIKES = {
    78: {"iv": 0.384, "use": ["p"], "label": "78 put"},
    80: {"iv": 0.375, "use": ["c", "p"], "label": "80 (ATM)"},
    83: {"iv": 0.373, "use": ["c"], "label": "83 call"},
}


def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, r, q, sig, typ):
    """Black-Scholes price + spot delta (carry q)."""
    if T <= 0 or sig <= 0:
        intrinsic = max(0.0, (S - K) if typ == "c" else (K - S))
        return intrinsic, (1.0 if (typ == "c" and S > K) else (-1.0 if (typ == "p" and S < K) else 0.0))
    F = S * math.exp((r - q) * T)
    sq = sig * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sq * sq) / sq
    d2 = d1 - sq
    disc = math.exp(-r * T)
    if typ == "c":
        price = disc * (F * _ncdf(d1) - K * _ncdf(d2))
        delta = math.exp(-q * T) * _ncdf(d1)
    else:
        price = disc * (K * _ncdf(-d2) - F * _ncdf(-d1))
        delta = -math.exp(-q * T) * _ncdf(-d1)
    return price, delta


def _scenario_for(K, typ, iv, borrow, spot_grid):
    """Delta-neutral P&L vs spot at a given borrow, for one option.
    Trade is struck at SPOT0/BORROW0; delta-hedge at the trade delta."""
    q0 = BORROW0 - DIV
    price0, delta0 = bs(SPOT0, K, T_BUS, R, q0, iv, typ)
    q = borrow - DIV
    pnl = []
    for S in spot_grid:
        price, _ = bs(S, K, T_BUS, R, q, iv, typ)
        opt_pnl = price - price0
        hedge_pnl = -delta0 * (S - SPOT0)      # short delta0 shares (delta-neutral)
        pnl.append(round(opt_pnl + hedge_pnl, 4))
    return {"price0": round(price0, 4), "delta0": round(delta0, 4), "pnl": pnl}


def build_payload():
    # spot grid +-12% around spot
    lo, hi, n = SPOT0 * 0.88, SPOT0 * 1.12, 49
    spot_grid = [round(lo + (hi - lo) * i / (n - 1), 3) for i in range(n)]

    # borrow scenarios to precompute (the toggle interpolates / picks these)
    borrow_levels = [0.0, 0.02, 0.10, 0.25, 0.50, 1.00, 2.00, 3.00]

    options = []
    for K, meta in STRIKES.items():
        iv = meta["iv"]
        for typ in meta["use"]:          # only the option(s) the user specified
            scen = {f"{int(b*10000)}": _scenario_for(K, typ, iv, b, spot_grid)
                    for b in borrow_levels}
            q0 = BORROW0 - DIV
            p0, d0 = bs(SPOT0, K, T_BUS, R, q0, iv, typ)
            options.append({
                "strike": K, "type": typ, "iv": iv,
                "label": ("Call " if typ == "c" else "Put ") + str(K),
                "price0": round(p0, 4), "delta0": round(d0, 4),
                "scenarios": scen,
            })

    # forward sensitivity to borrow (illustrate the mechanism)
    fwd_by_borrow = [{"borrow": b, "forward": round(SPOT0 * math.exp((R - (b - DIV)) * T_BUS), 3)}
                     for b in borrow_levels]

    import datetime
    return {
        "meta": {
            "title": "ARKK JUN-18-26 options — delta-neutral spot × borrow scenario",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "disclaimer": ("Analysis, not investment advice. Black-Scholes calibrated to the RiskView "
                           "ARKK JUN-18-26 screen (2026-06-02): spot 79.80, 12 business days, r 4.15%, "
                           "borrow (sdiv) 2.0%. Per the chosen expressions: 78 PUT (IV 38.4%), 80 CALL + "
                           "PUT (IV 37.5%), 83 CALL (IV 37.3%). Sticky-strike: each option's IV is held "
                           "FIXED as spot/borrow move; the borrow axis acts purely through the forward "
                           "F=S·e^((r−borrow)T). P&L is delta-neutral, hedged at the trade delta. "
                           "Model output, not a quote."),
            "spot0": SPOT0, "t_business_days": 12, "t_years": round(T_BUS, 5),
            "rate": R, "borrow0": BORROW0, "div": DIV,
            "borrow_levels": borrow_levels,
            "spot_grid": spot_grid,
        },
        "options": options,
        "forward_by_borrow": fwd_by_borrow,
        "strikes": [{"strike": k, **v} for k, v in STRIKES.items()],
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "ark_options.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    print("strikes:", [o["label"] + f" Δ{o['delta0']:+.2f} px{o['price0']:.2f}" for o in pl["options"]])
    print("forward vs borrow:")
    for f in pl["forward_by_borrow"]:
        print(f"  borrow {f['borrow']*100:5.0f}% -> fwd {f['forward']}")
    p = write_json()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
