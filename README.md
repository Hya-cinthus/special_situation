# Special Situations — research repo

A personal, reproducible research repo for analyzing one special situation at a
time. Each situation has its own data + calculation layer and renders into a
single shared, zero-dependency dashboard.

> **This is analysis, not investment advice.** Nothing here is a recommendation
> to buy or sell any security. Every number traces to a public source or is
> explicitly labeled an estimate/interpolation with a confidence level. No
> datapoint is fabricated; where data could not be obtained it is recorded as a
> gap rather than guessed.

## Situations

| Key | Title | Status |
|-----|-------|--------|
| [`spacex_baron`](situations/spacex_baron/) | SpaceX exposure via Baron Partners Fund (BPTRX), and its effective SpaceX weight over time | active |

## How to run

The pipeline uses **only the Python standard library** — no `pip install` needed.

```bash
# 1. (Re)generate the dashboard data from public sources.
py build.py                 # Windows (python3 build.py elsewhere)

# 2. Open the dashboard.
#    Easiest: just open dashboard/index.html in a browser.
#    If the browser blocks local fetch() of the JSON, serve it:
cd dashboard
py -m http.server 8000
#    then visit http://localhost:8000
```

`build.py` ingests from public sources (SEC EDGAR NPORT-P, Yahoo Finance NAV),
runs the reconstruction engine, and writes `dashboard/data/<situation>.json`.
The frontend reads only that JSON and does the interactive scenario math
client-side, so the sliders are instant and need no server round-trip.

## Architecture

Strict separation of concerns:

```
ingest/    pull raw public data  -> data/processed/*.csv   (one module per source)
engine/    pure-Python math       -> reconstructed series   (unit-tested, no I/O)
emit.py    assemble + serialize   -> dashboard/data/*.json
dashboard/ static HTML + Plotly.js (CDN) reads the JSON, renders, recomputes scenarios
```

The engine is pure Python with no I/O so it can be unit-tested against the
quarterly filing anchors (reconstructed weight at an anchor date must match the
filed weight within tolerance).

## Run the tests

```bash
py -m unittest discover -s situations/spacex_baron/tests -v
```

## Adding a new situation

1. `situations/<new_key>/` mirroring `spacex_baron/`'s layout.
2. Add `<new_key>` to `SITUATIONS` in `config.py` (plus a config block).
3. `py build.py` emits `dashboard/data/<new_key>.json`; the dashboard's
   situation selector picks it up with no frontend changes.
