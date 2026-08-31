"""Baron Partners Fund public-book weight snapshots (from the user-provided BPTIX
back-solve workbook: 3/31 NPORT shares; 4/30 & 5/31 from Baron site top-10 + GICS
sector snapshots, residual modeled as SPY). Weights are % of the PUBLIC common book
(ex SpaceX, ex cash). Leverage de-levered: 3/31 1.134x -> 4/30 1.071x -> 5/31 0.968x
(NET CASH, no leverage). SPY is a market-proxy for the 5/31 unattributed residual."""

LEVERAGE = {"2026-03-31": 1.134, "2026-04-30": 1.071, "2026-05-31": 0.968}

WEIGHTS_3_31 = {
    'TSLA': 0.304303,
    'ACGL': 0.075166,
    'MSCI': 0.061194,
    'H': 0.061035,
    'SCHW': 0.057778,
    'FDS': 0.051343,
    'IT': 0.047638,
    'IDXX': 0.044178,
    'CSGP': 0.037088,
    'CHH': 0.032564,
    'SPOT': 0.032222,
    'GWRE': 0.032139,
    'SHOP': 0.029483,
    'MTN': 0.02929,
    'RRR': 0.021247,
    'VRSK': 0.017951,
    'KNSL': 0.015948,
    'BIRK': 0.015857,
    'ONON': 0.012721,
    'GLPI': 0.009987,
    'HEI': 0.004368,
    'FIG': 0.00337,
    'HEI-A': 0.003129,
}

WEIGHTS_4_30 = {
    'TSLA': 0.265625,
    'ACGL': 0.06392,
    'H': 0.0625,
    'MSCI': 0.06108,
    'SCHW': 0.058239,
    'FDS': 0.046875,
    'IT': 0.045455,
    'IDXX': 0.038352,
    'CSGP': 0.035511,
    'CHH': 0.035511,
    'SPOT': 0.035511,
    'GWRE': 0.035511,
    'SHOP': 0.035511,
    'MTN': 0.035511,
    'RRR': 0.029437,
    'VRSK': 0.024869,
    'KNSL': 0.022096,
    'BIRK': 0.021969,
    'ONON': 0.017624,
    'GLPI': 0.013837,
    'HEI': 0.006052,
    'FIG': 0.004669,
    'HEI-A': 0.004334,
}

WEIGHTS_5_31 = {
    'TSLA': 0.226902,
    'SPY': 0.080163,
    'MSCI': 0.063859,
    'H': 0.058424,
    'SCHW': 0.052989,
    'SHOP': 0.05163,
    'ACGL': 0.047554,
    'IT': 0.044837,
    'SPOT': 0.043478,
    'FDS': 0.039402,
    'GWRE': 0.038043,
    'CSGP': 0.035326,
    'IDXX': 0.033967,
    'CHH': 0.029891,
    'BIRK': 0.027174,
    'ONON': 0.027174,
    'VRSK': 0.025815,
    'KNSL': 0.019022,
    'MTN': 0.016984,
    'RRR': 0.016984,
    'FIG': 0.008152,
    'GLPI': 0.006793,
    'HEI': 0.002717,
    'HEI-A': 0.002717,
}

# FILED 6/30/2026 holdings, from the NPORT-P filed 2026-08-28 (accession 0001410368-26-088301,
# seriesId S000000588 Baron Partners Fund). Values are a fraction of TOTAL INVESTMENTS (gross),
# ex-SpaceX and ex-cash — the same basis the previous website-derived table used, so the `_nospy`
# renormalization downstream is unchanged. Raw book: data/nport_holdings_2026-06-30.csv.
# Replaced Baron's website approximation on 2026-08-31, once the filing landed. That website book
# scored well: mean |error| 0.072pp, max 0.61pp on the public-relative basis. Its one real mistake
# was GOOGL and GOOG swapped (site 0.149/0.597 of the public book; filed 0.759/0.148).
# Fund level 6/30: netAssets $18.0511B, totAssets $19.3104B, leverage 1.0698,
# cash (SSgA MMF) $39.0M = 0.216 pct of net (essentially gone).
# SpaceX 36938300 sh = 32.68 pct of gross — UNCHANGED from 3/31,
# which falsifies the assumed ~$262M 6/12 'Friday buy'.
WEIGHTS_6_30 = {
    "TSLA": 0.14060, "H": 0.04017, "SCHW": 0.03981, "MSCI": 0.03911, "SHOP": 0.03699,
    "ACGL": 0.03263, "SPOT": 0.03046, "FDS": 0.02561, "IT": 0.02470, "IDXX": 0.02307,
    "CSGP": 0.02303, "CHH": 0.02280, "VRSK": 0.02276, "MTN": 0.02258, "GWRE": 0.02238,
    "RRR": 0.01895, "BIRK": 0.01791, "KNSL": 0.01715, "ONON": 0.01627, "MORN": 0.01529,
    "AMZN": 0.00788, "MRNA": 0.00721, "GOOGL": 0.00509, "FIG": 0.00477, "GLPI": 0.00409,
    "HEI": 0.00326, "LLY": 0.00314, "HEI-A": 0.00156, "GOOG": 0.00099,
}

IMPLIED_SHARES_5_31 = {
    'CSGP': 13539810,
    'ONON': 8215842,
    'SCHW': 7486810,
    'BIRK': 7441107,
    'ACGL': 6569271,
    'TSLA': 6425905,
    'SHOP': 5367739,
    'H': 3975777,
    'FIG': 3945538,
    'RRR': 3590385,
    'IT': 3411601,
    'CHH': 3388205,
    'GWRE': 3075385,
    'FDS': 1981047,
    'VRSK': 1820688,
    'GLPI': 1785026,
    'MTN': 1568912,
    'SPY': 1307825,
    'MSCI': 1248252,
    'SPOT': 1078189,
    'KNSL': 770284,
    'IDXX': 743906,
    'HEI-A': 129083,
    'HEI': 96321,
}
