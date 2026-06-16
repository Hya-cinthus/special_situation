"""
One-command build: ingest -> reconstruct -> emit JSON for all situations.

    py build.py                 # build every situation in config.SITUATIONS
    py build.py spacex_baron    # build just one
    py build.py --no-fetch      # skip network ingest, rebuild JSON from cached CSVs

Uses only the Python standard library. Network pulls (SEC EDGAR, Yahoo) are
cached under each situation's data/raw/, so re-runs are fast and offline-capable.
"""

import os
import sys
import time

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from config import SITUATIONS


def build_spacex_baron(do_fetch: bool = True):
    from situations.spacex_baron.ingest import edgar, nav
    from situations.spacex_baron import emit

    if do_fetch:
        print("[spacex_baron] Ingesting EDGAR NPORT-P anchors...")
        anchors = edgar.fetch_anchors(verbose=True)
        edgar.write_anchors_csv(anchors)
        print(f"[spacex_baron]   {len(anchors)} quarterly anchors.")

        print("[spacex_baron] Ingesting daily NAV (Yahoo)...")
        rows = nav.fetch_nav()
        nav.write_nav_csv(rows)
        print(f"[spacex_baron]   {len(rows)} daily NAV rows.")
    else:
        print("[spacex_baron] --no-fetch: rebuilding JSON from cached CSVs.")

    path = emit.write_json()
    print(f"[spacex_baron] Wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")


def build_vcx_fundrise(do_fetch: bool = True):
    from situations.vcx_fundrise.ingest import price, edgar
    from situations.vcx_fundrise import emit

    if do_fetch:
        print("[vcx_fundrise] Ingesting VCX daily price (Yahoo)...")
        rows = price.fetch_price()
        price.write_price_csv(rows)
        print(f"[vcx_fundrise]   {len(rows)} price rows.")

        print("[vcx_fundrise] Ingesting EDGAR NPORT-P (net assets + holdings)...")
        anchors = edgar.fetch_anchors(verbose=False)
        edgar.write_anchors(anchors)
        print(f"[vcx_fundrise]   {len(anchors)} NPORT anchors.")
    else:
        print("[vcx_fundrise] --no-fetch: rebuilding JSON from cached data.")

    path = emit.write_json()
    print(f"[vcx_fundrise] Wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")


def build_dxyz_destiny(do_fetch: bool = True):
    from situations.dxyz_destiny.ingest import price, edgar
    from situations.dxyz_destiny import emit

    if do_fetch:
        print("[dxyz_destiny] Ingesting DXYZ daily price (Yahoo)...")
        rows = price.fetch_price(); price.write_price_csv(rows)
        print(f"[dxyz_destiny]   {len(rows)} price rows.")
        print("[dxyz_destiny] Ingesting EDGAR NPORT-P...")
        anchors = edgar.fetch_anchors(verbose=False); edgar.write_anchors(anchors)
        print(f"[dxyz_destiny]   {len(anchors)} NPORT anchors.")
    else:
        print("[dxyz_destiny] --no-fetch: rebuilding JSON from cached data.")

    path = emit.write_json()
    print(f"[dxyz_destiny] Wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")


def build_rvi_robinhood(do_fetch: bool = True):
    from situations.rvi_robinhood.ingest import price, edgar
    from situations.rvi_robinhood import emit
    if do_fetch:
        print("[rvi_robinhood] Ingesting RVI daily price (Yahoo)...")
        rows = price.fetch_price(); price.write_price_csv(rows)
        print(f"[rvi_robinhood]   {len(rows)} price rows.")
        print("[rvi_robinhood] Ingesting EDGAR NPORT-P...")
        anchors = edgar.fetch_anchors(verbose=False); edgar.write_anchors(anchors)
        print(f"[rvi_robinhood]   {len(anchors)} NPORT anchors.")
    else:
        print("[rvi_robinhood] --no-fetch: rebuilding JSON from cached data.")
    path = emit.write_json()
    print(f"[rvi_robinhood] Wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")


def build_agix_kraneshares(do_fetch: bool = True):
    from situations.agix_kraneshares.ingest import price, edgar
    from situations.agix_kraneshares import emit
    if do_fetch:
        print("[agix_kraneshares] Ingesting AGIX daily price (Yahoo)...")
        rows = price.fetch_price(); price.write_price_csv(rows)
        print(f"[agix_kraneshares]   {len(rows)} price rows.")
        print("[agix_kraneshares] Ingesting EDGAR NPORT-P (seriesId-filtered)...")
        anchors = edgar.fetch_anchors(verbose=False); edgar.write_anchors(anchors)
        print(f"[agix_kraneshares]   {len(anchors)} AGIX NPORT anchors.")
    else:
        print("[agix_kraneshares] --no-fetch: rebuilding JSON from cached data.")
    path = emit.write_json()
    print(f"[agix_kraneshares] Wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")


def build_arkvx_arkventure(do_fetch: bool = True):
    from situations.arkvx_arkventure.ingest import price, edgar
    from situations.arkvx_arkventure import emit
    if do_fetch:
        print("[arkvx_arkventure] Ingesting ARKVX daily NAV (Yahoo)...")
        rows = price.fetch_price(); price.write_price_csv(rows)
        print(f"[arkvx_arkventure]   {len(rows)} price rows.")
        print("[arkvx_arkventure] Ingesting EDGAR NPORT-P (directly-named holdings)...")
        anchors = edgar.fetch_anchors(verbose=False); edgar.write_anchors(anchors)
        print(f"[arkvx_arkventure]   {len(anchors)} ARKVX NPORT anchors.")
    else:
        print("[arkvx_arkventure] --no-fetch: rebuilding JSON from cached data.")
    path = emit.write_json()
    print(f"[arkvx_arkventure] Wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")


BUILDERS = {"spacex_baron": build_spacex_baron, "vcx_fundrise": build_vcx_fundrise,
            "dxyz_destiny": build_dxyz_destiny, "rvi_robinhood": build_rvi_robinhood,
            "agix_kraneshares": build_agix_kraneshares, "arkvx_arkventure": build_arkvx_arkventure}


def main(argv):
    do_fetch = "--no-fetch" not in argv
    wanted = [a for a in argv if not a.startswith("--")] or SITUATIONS
    t0 = time.time()
    for key in wanted:
        if key not in BUILDERS:
            print(f"!! unknown situation '{key}' (known: {list(BUILDERS)})")
            continue
        BUILDERS[key](do_fetch=do_fetch)
    # Cross-vehicle overview memo (reads the per-vehicle JSONs just written).
    try:
        import overview
        p = overview.write_json()
        print(f"[overview] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[overview] skipped: {e}")
    # ARK / SpaceX-IPO tracker (curated model; independent of the per-vehicle JSONs).
    try:
        import ark_tracker
        p = ark_tracker.write_json()
        print(f"[ark_tracker] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
        if do_fetch:
            import ark_ipo_impact
            ark_ipo_impact.merge_into_tracker()
            print("[ark_tracker] merged IPO-day impact analytics (real price data).")
    except Exception as e:
        print(f"[ark_tracker] skipped: {e}")
    # ARKK options scenario (curated, screen-calibrated; no network needed).
    try:
        import ark_options
        p = ark_options.write_json()
        print(f"[ark_options] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[ark_options] skipped: {e}")
    # Hedged BPTIX-vs-public-holdings book (needs network for prices).
    try:
        import hedge_book
        p = hedge_book.write_json()
        print(f"[hedge_book] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[hedge_book] skipped: {e}")
    # Hedge-drift (reads the BPTIX override series; no network).
    try:
        import hedge_drift
        p = hedge_drift.write_json()
        print(f"[hedge_drift] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[hedge_drift] skipped: {e}")
    # SpaceX 6/4 re-mark multi-scenario reconciliation (documented inputs; no network).
    try:
        import spacex_remark
        p = spacex_remark.write_json()
        print(f"[spacex_remark] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[spacex_remark] skipped: {e}")
    # 3/31 NPORT holdings detail + full SpaceX valuation reconciliation (no network).
    try:
        import nport_holdings
        p = nport_holdings.write_json()
        print(f"[nport_holdings] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[nport_holdings] skipped: {e}")
    # Hedge basket vs fund holdings composition mismatch (no network).
    try:
        import basket_mismatch
        p = basket_mismatch.write_json()
        print(f"[basket_mismatch] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[basket_mismatch] skipped: {e}")
    # Minimum-variance optimal-hedge research (needs prices; out-of-sample validated).
    try:
        import optimal_hedge
        p = optimal_hedge.write_json()
        print(f"[optimal_hedge] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[optimal_hedge] skipped: {e}")
    # SpaceX across the Baron fund family — NPORT-P cross-fund scan (network; cached).
    try:
        import baron_spacex_funds
        p = baron_spacex_funds.write_json()
        print(f"[baron_spacex_funds] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[baron_spacex_funds] skipped: {e}")
    # IPO-day AUM reconciliation (SpaceX first trade): marks vs reported AUM (needs prices).
    try:
        import ipo_day_recon
        p = ipo_day_recon.write_json()
        print(f"[ipo_day_recon] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[ipo_day_recon] skipped: {e}")
    # Daily NAV-estimate log (user-pasted closes; per-basket prediction vs actual; no network).
    try:
        import daily_nav_log
        p = daily_nav_log.write_json()
        print(f"[daily_nav_log] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[daily_nav_log] skipped: {e}")
    # Daily SpaceX-weight recalibration ledger (inverts actual NAV+AUM -> weight/buy/flow; no network).
    try:
        import recalibrate
        p = recalibrate.write_json()
        print(f"[recalibrate] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
    except Exception as e:
        print(f"[recalibrate] skipped: {e}")
    # Long-horizon (3yr) public-book replication (reads cached prices; network-free).
    try:
        import long_replication
        if long_replication.build_payload() is not None:
            p = long_replication.write_json()
            print(f"[long_replication] Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
        else:
            print("[long_replication] skipped: no price cache (run `py long_replication.py --refresh`)")
    except Exception as e:
        print(f"[long_replication] skipped: {e}")
    print(f"\nDone in {time.time()-t0:.1f}s. Open dashboard/index.html "
          f"(or `cd dashboard && py -m http.server 8000`).")


if __name__ == "__main__":
    main(sys.argv[1:])
