"""
Reconstruction engine — daily estimated SpaceX weight in Baron Partners Fund.

PURE PYTHON, NO I/O. Everything is passed in and returned as plain dicts/lists so
the math can be unit-tested against the quarterly filing anchors.

True daily SpaceX weight is NOT directly observable. Between quarterly NPORT-P
anchors we *reconstruct* it. The honest core identity each day t:

    spacex_value_t   = (held flat from last filing; steps at each filing/mark)
    total_nav_t      = nav_per_share_t (observed)  ×  shares_outstanding_t
    public_value_t   = total_nav_t − spacex_value_t        (cash folded in, v1)
    spacex_weight_t  = spacex_value_t / total_nav_t

where shares_outstanding_t is interpolated between filing anchors (the main
source of between-anchor error; see data_gaps.md #2), and at every filing date
the reconstruction is pinned to the *measured* filing values — so by
construction the reconstructed weight at an anchor equals the filed weight.

Two regimes:
  • Pre-first-filing (2017 → ~2019-Q3): no NPORT-P. Weight is interpolated
    directly between the low-confidence 2017 narrative anchor and the first
    measured filing. No AUM/decomposition is fabricated here.
  • Anchored era (~2019-Q3 → today): full reconstruction + daily attribution of
    the weight change into (mark / public-drift / flow) channels.

Every output point carries: value, source (measured|interpolated|proxy_drift|
scenario), and confidence (high|med|low).
"""

from datetime import date, timedelta


# ---------------------------------------------------------------------------
# small date / lookup helpers
# ---------------------------------------------------------------------------

def _d(s: str) -> date:
    return date.fromisoformat(s)


def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _build_nav_lookup(nav_daily: list[dict]) -> dict[str, float]:
    return {r["date"]: r["nav"] for r in nav_daily if r.get("nav") is not None}


def _nearest_prior_nav(navmap: dict[str, float], sorted_dates: list[str], iso: str):
    """NAV on `iso`, else the most recent trading day before it."""
    if iso in navmap:
        return navmap[iso]
    import bisect
    idx = bisect.bisect_right(sorted_dates, iso) - 1
    if idx >= 0:
        return navmap[sorted_dates[idx]]
    return None


def _confidence_for(iso: str, density_eras) -> str:
    for start, end, _label, conf in density_eras:
        if iso >= start and (end is None or iso <= end):
            return conf
    return "med"


# ---------------------------------------------------------------------------
# main reconstruction
# ---------------------------------------------------------------------------

def reconstruct_daily(anchors: list[dict],
                      nav_daily: list[dict],
                      external_marks: list[dict],
                      density_eras,
                      window_start: str,
                      entry_date: str,
                      aum_overrides: list[dict] | None = None) -> dict:
    """Return the full reconstructed daily series + anchor/quality metadata.

    anchors: measured quarterly rows from NPORT-P (edgar.fetch_anchors), each with
        report_date, net_assets_usd, spacex_value_usd, spacex_pct_of_net_assets,
        spacex_balance_units.
    nav_daily: [{date, nav}, ...] measured NAV/share.
    external_marks: rows from spacex_marks.csv (used for the 2017 narrative anchor).
    """
    navmap = _build_nav_lookup(nav_daily)
    nav_dates = sorted(navmap)
    if not nav_dates:
        raise ValueError("no NAV data")

    anchors = sorted(anchors, key=lambda a: a["report_date"])
    last_data_day = _d(nav_dates[-1])
    start = _d(window_start)

    # Derive shares-outstanding at each filing anchor: shares = net_assets / NAV.
    enriched = []
    for a in anchors:
        nav_at = _nearest_prior_nav(navmap, nav_dates, a["report_date"])
        if not nav_at or not a.get("net_assets_usd"):
            continue
        shares = a["net_assets_usd"] / nav_at
        enriched.append({
            **a,
            "nav_at_report": nav_at,
            "shares_outstanding": shares,
            "spacex_weight_measured": a["spacex_value_usd"] / a["net_assets_usd"],
        })
    if not enriched:
        raise ValueError("no usable anchors")

    first_anchor = enriched[0]
    first_anchor_date = _d(first_anchor["report_date"])

    # 2017 narrative anchor (low confidence) for the pre-filing era.
    narrative_2017 = next((m for m in external_marks
                           if m["date"][:4] == "2017"), None)
    # Approx initiation weight ~4% (Baron's stated initial position size).
    init_weight = 0.04

    series = []

    # ---- regime 1: pre-first-filing — interpolate weight only ----
    if start < first_anchor_date:
        span_days = (first_anchor_date - start).days or 1
        w0, w1 = init_weight, first_anchor["spacex_weight_measured"]
        for cur in _daterange(start, first_anchor_date - timedelta(days=1)):
            frac = (cur - start).days / span_days
            w = w0 + (w1 - w0) * frac
            iso = cur.isoformat()
            series.append({
                "date": iso,
                "spacex_weight": round(w, 6),
                "spacex_value_usd": None,
                "public_value_usd": None,
                "total_nav_usd": None,
                "nav_per_share": navmap.get(iso),
                "source": "interpolated",
                "confidence": "low",
                "mark_contrib": None, "drift_contrib": None, "flow_contrib": None,
            })

    # ---- AUM true-up anchors (post-filing, manually-sourced) ----
    # No public holdings filing exists after the last NPORT-P, but reported total
    # net assets (e.g. Bloomberg / aggregators) move with net flows. Each override
    # becomes a pseudo-anchor: AUM is the sourced figure; SpaceX $ is CARRIED
    # FORWARD from the last filing (no new mark; private shares can't be added).
    # These are NOT measured filings — tagged source="external_aum" — so they
    # never enter the NPORT anchor table, residuals, or measured markers.
    override_anchors = []
    for ov in sorted(aum_overrides or [], key=lambda o: o["date"]):
        if ov["date"] <= enriched[-1]["report_date"]:
            continue  # only forward-fill strictly after the last filing
        nav_at = _nearest_prior_nav(navmap, nav_dates, ov["date"])
        if not nav_at or not ov.get("total_net_assets_usd"):
            continue
        carried = (override_anchors[-1] if override_anchors else enriched[-1])["spacex_value_usd"]
        na = float(ov["total_net_assets_usd"])
        override_anchors.append({
            "report_date": ov["date"], "filing_date": None, "accession": None,
            "net_assets_usd": na, "spacex_value_usd": carried,
            "spacex_pct_of_net_assets": carried / na * 100,
            "spacex_balance_units": enriched[-1].get("spacex_balance_units"),
            "nav_at_report": nav_at, "shares_outstanding": na / nav_at,
            "spacex_weight_measured": carried / na,
            "is_override": True, "source": "external_aum",
            "confidence": ov.get("confidence", "med"),
            "ov_source": ov.get("source", ""), "ov_source_url": ov.get("source_url", ""),
        })

    # ---- regime 2: anchored era — full reconstruction ----
    # Walk segment by segment between consecutive anchors; the final open segment
    # runs to the last NAV day with shares held flat (flows unobservable beyond
    # the last anchor — whether that anchor is an NPORT filing or an AUM true-up).
    seg_anchors = enriched + override_anchors
    segments = []
    for i in range(len(seg_anchors)):
        seg_start = _d(seg_anchors[i]["report_date"])
        if i + 1 < len(seg_anchors):
            seg_end = _d(seg_anchors[i + 1]["report_date"])
            nxt = seg_anchors[i + 1]
        else:
            seg_end = last_data_day
            nxt = None
        segments.append((seg_anchors[i], nxt, seg_start, seg_end))

    prev_point = None
    for cur_anchor, nxt_anchor, seg_start, seg_end in segments:
        spacex_value = cur_anchor["spacex_value_usd"]   # held flat across segment
        shares0 = cur_anchor["shares_outstanding"]
        if nxt_anchor:
            shares1 = nxt_anchor["shares_outstanding"]
            seg_days = (seg_end - seg_start).days or 1
        else:
            shares1 = shares0  # open segment: hold flat
            seg_days = (seg_end - seg_start).days or 1

        # iterate days; include seg_end only for the final open segment
        # (interior anchor dates are emitted as the *next* segment's start to
        #  carry the measured step cleanly)
        last_inclusive = nxt_anchor is None
        day_iter = list(_daterange(seg_start, seg_end if last_inclusive else seg_end - timedelta(days=1)))
        for cur in day_iter:
            iso = cur.isoformat()
            nav_t = _nearest_prior_nav(navmap, nav_dates, iso)
            if nav_t is None:
                continue
            frac = (cur - seg_start).days / seg_days
            shares_t = shares0 + (shares1 - shares0) * frac
            total_nav = nav_t * shares_t
            public_value = total_nav - spacex_value
            weight = spacex_value / total_nav if total_nav else None

            is_anchor_day = (iso == cur_anchor["report_date"])
            if is_anchor_day and cur_anchor.get("is_override"):
                source, confidence = "external_aum", cur_anchor.get("confidence", "med")
            elif is_anchor_day:
                source, confidence = "measured", "high"
            else:
                source, confidence = "interpolated", _confidence_for(iso, density_eras)

            pt = {
                "date": iso,
                "spacex_weight": round(weight, 6) if weight else None,
                "spacex_value_usd": round(spacex_value, 2),
                "public_value_usd": round(public_value, 2),
                "total_nav_usd": round(total_nav, 2),
                "nav_per_share": nav_t,
                "shares_outstanding": round(shares_t, 2),
                "source": source,
                "confidence": confidence,
            }

            # daily first-order attribution of weight change
            if prev_point and prev_point.get("total_nav_usd") and weight is not None:
                Vp = prev_point["total_nav_usd"]; Sp = prev_point["spacex_value_usd"]
                wp = prev_point["spacex_weight"]
                dS = spacex_value - Sp
                dnav = nav_t - prev_point["nav_per_share"]
                dshares = shares_t - prev_point["shares_outstanding"]
                V = total_nav
                pt["mark_contrib"] = round((1 - wp) / V * dS, 8)
                pt["drift_contrib"] = round(-wp / V * (prev_point["shares_outstanding"] * dnav), 8)
                pt["flow_contrib"] = round(-wp / V * (prev_point["nav_per_share"] * dshares), 8)
            else:
                pt["mark_contrib"] = pt["drift_contrib"] = pt["flow_contrib"] = None

            series.append(pt)
            prev_point = pt

    # ---- model-quality metric: anchor-to-anchor prediction residual ----
    # Carry SpaceX value flat from anchor i to anchor i+1's date and compare the
    # predicted weight to the measured weight there. Captures how much we miss by
    # holding marks/shares flat between filings.
    residuals = []
    for i in range(len(enriched) - 1):
        a, b = enriched[i], enriched[i + 1]
        nav_b = b["nav_at_report"]
        predicted_total = nav_b * b["shares_outstanding"]  # = net_assets_b
        predicted_weight = a["spacex_value_usd"] / predicted_total
        measured_weight = b["spacex_weight_measured"]
        residuals.append({
            "report_date": b["report_date"],
            "predicted_weight": round(predicted_weight, 6),
            "measured_weight": round(measured_weight, 6),
            "residual": round(predicted_weight - measured_weight, 6),
        })

    return {
        "series": series,
        "anchors": enriched,
        "residuals": residuals,
        "aum_overrides": override_anchors,
        "last_data_day": nav_dates[-1],
    }


def current_state(recon: dict, entry_date: str) -> dict:
    """Snapshot used for KPIs and as the base for client-side scenarios."""
    series = recon["series"]
    # latest point with a full reconstruction (has total_nav)
    latest = next((p for p in reversed(series) if p.get("total_nav_usd")), None)
    entry = next((p for p in series if p["date"] == entry_date), None)
    if entry is None:  # nearest on/after entry
        entry = next((p for p in series if p["date"] >= entry_date and p.get("total_nav_usd")), latest)
    return {
        "as_of": latest["date"] if latest else None,
        "spacex_weight": latest["spacex_weight"] if latest else None,
        "spacex_value_usd": latest["spacex_value_usd"] if latest else None,
        "public_value_usd": latest["public_value_usd"] if latest else None,
        "total_nav_usd": latest["total_nav_usd"] if latest else None,
        "entry_date": entry_date,
        "entry_weight": entry["spacex_weight"] if entry else None,
        "entry_total_nav_usd": entry.get("total_nav_usd") if entry else None,
    }
