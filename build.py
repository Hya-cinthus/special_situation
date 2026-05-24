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


BUILDERS = {"spacex_baron": build_spacex_baron}


def main(argv):
    do_fetch = "--no-fetch" not in argv
    wanted = [a for a in argv if not a.startswith("--")] or SITUATIONS
    t0 = time.time()
    for key in wanted:
        if key not in BUILDERS:
            print(f"!! unknown situation '{key}' (known: {list(BUILDERS)})")
            continue
        BUILDERS[key](do_fetch=do_fetch)
    print(f"\nDone in {time.time()-t0:.1f}s. Open dashboard/index.html "
          f"(or `cd dashboard && py -m http.server 8000`).")


if __name__ == "__main__":
    main(sys.argv[1:])
