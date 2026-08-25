# Daily update protocol — Baron / SpaceX dashboard

The single source of truth for what to touch each day so **nothing goes stale**. Past
mistake this prevents: filling the daily NAV log but leaving the *early* charts
(estimated SpaceX weight / reconstructed AUM / SpaceX fair value / what moved the
weight) frozen at the prior day.

Interpreter on this machine is **`py`** (Python 3.14), NOT `python`.

---

## What the user provides  (workflow changed 2026-07-13)

- **The user now provides ONLY the Morningstar Total Assets (AUM)** for day T — one number per day
  (e.g. "7/13 AUM 17.0B"), except in unusual situations.
- **Everything else I fetch myself, T+1** (the next day), from Yahoo's chart API:
  - the **29 public-holding closes** + the **SPCX** close (for the as-of NAV estimate), and
  - the **BPTIX actual NAV** (day-T close from Yahoo — no longer needs a user-reported stop-gap).

**No-look-ahead rule (critical):** when reconstructing day T's estimate T+1, use **only day-T's
closes** (and prior days' info) — never any price from after day T. The frozen as-of estimate must
equal what we could have computed at day-T close. (I *may* fetch several days at once when catching
up, but each day's estimate is built from that day's closes alone.) Then score it vs the actual NAV.
Timeliness is relaxed: we no longer need a same-day close estimate (the user self-marks off the latest
basket) — only **watch for a clearly widening deviation**, which is the trigger to re-anchor / investigate.

Fetch mechanism: the Yahoo chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/<ticker>`,
`User-Agent: Mozilla/5.0`, stdlib `urllib`) — same one `situations/spacex_baron/ingest/nav.py` uses.
Loop the 29 tickers (Yahoo style: `HEI-A`, and `SPCX`), pick the day-T close for each. Local fetch is
fine; **this is NOT part of the CI rebuild** (which stays network-free except the known nav fetch).

The whole stack is on **BPTIX** (the class the user holds): `NAV_TICKER = "BPTIX"`, all NAVs, labels, charts.

---

## Position size — ONE knob

The whole book scales off a single constant in `config.py`:

```python
POSITION_BPTIX_SHARES_ORIGINAL = 130000   # size the 5/20 hedge book was struck at (history)
POSITION_BPTIX_SHARES          = 30000    # <-- CURRENT size; change this and rebuild
POSITION_SCALE = POSITION_BPTIX_SHARES / POSITION_BPTIX_SHARES_ORIGINAL
```

Everything derives from it — do **not** hardcode a share count anywhere:
- `hedge_book.POSITIONS` = `POSITIONS_ORIGINAL x POSITION_SCALE` (BPTIX takes the exact count;
  shorts scale pro-rata, so every hedge **ratio** is preserved and only the $ P&L rescales).
  `POSITIONS_ORIGINAL` is the historical record of the 5/20 fills — never edit it to resize.
- `ipo_day_recon`, `optimal_hedge`, `daily_nav_log` (look-through `position_shares`) read the constant.
- Front-end: `hedge_book.json` `meta.long_shares` / `meta.short_notional` feed the `.pos-sh` /
  `.pos-short-notl` spans in `hedge.html` (filled by `hedge_app.render()`); `app.js` reads
  `lookthrough.position_shares`. No size is written into the HTML.
- Mark-basket CSVs carry a `shares_for_<N>` column; re-run the rescale helper if N changes.

**To resize:** edit `POSITION_BPTIX_SHARES`, run `py build.py`, and rescale the CSV column. History
keeps its shape; every $ series just scales by the same factor.

2026-08-20: cut 130,000 -> 30,000 (scale 0.23077), long and short together.

---

## The files to edit each day  (in this order)

### 1. `daily_nav_log.py` — `ENTRIES`
Append (or, next morning, complete) one dict for day T:
```python
{"date":"YYYY-MM-DD","spcx":<SPCX close>,"actual_nav":<BPTIX NAV or None>,
 "aum":<Morningstar Total Assets or None>,
 "closes":{... 23 tickers ...}}   # Yahoo tickers; HEI/A -> HEI-A; SPY intentionally dropped
```
Drives the **Daily NAV estimate** card (which has an **As-of / Revised toggle**: each day's
estimate is auto-frozen to `daily_nav_vintage.jsonl` the first build, so revising an
assumption never erases what we estimated that day). `recalibrate.py` also reads this and
freezes its own vintage when `actual_nav` first lands — so just fill `actual_nav` next morning
and rebuild. Two assumption knobs at the top of `daily_nav_log.py`, both surfaced in the table:
- `FRIDAY_SPACEX_BUY` — assumed 6/12 SpaceX add ($262M); booked ON 6/12 (the day it happened) via that
  entry's `spacex_buy_usd`, not folded into the base.
- `LEVERAGE_FOR(date)` — **start-of-day** gross/net, now a SCHEDULE not a constant: **0.968 thru 6/15**
  (the 5/31-disclosed ~3.2% net-cash buffer, ~$0.65B) then **1.00 from 6/16** (the first redemption consumed
  the buffer; 6/17 confirmed L=1.0). Public sleeve weight = LEVERAGE − w_spx, remainder net cash. To re-test:
  on a big-basket day actual NAV below the L=1.0 estimate ⇒ leverage rose (or basket drift); above ⇒ fell.
  **Basket-drift finding (6/26):** the 6/25 (every basket too HIGH) / 6/26 (every basket too LOW) mirror —
  same names (FDS/FIG/GWRE/IT/KNSL) — showed the misses are WEIGHT DRIFT (fund overweight high-dispersion
  names vs the stale NPORT snapshots), NOT leverage (6/17/6/18 matched L=1.0). So on a high-dispersion day a
  one-directional miss is drift, not a leverage signal — keep L=1.0 unless ALL basket-move days shift together.
  The 6/30 NPORT (≈ Aug 27, see below) settles it.

### 2. `situations/spacex_baron/data/morningstar_aum_log.jsonl` — append one line
```json
{"as_of_date_iso":"YYYY-MM-DD","ticker":"BPTIX","total_assets_raw":"20.7B",
 "total_assets_usd":20700000000,"nav_per_share":<BPTIX NAV>,"nav_as_of":"YYYY-MM-DD",
 "captured_at":"<approx ISO now>","source":"...","blocked":false,"notes":"..."}
```
This is the **AUM true-up** that extends the reconstructed-AUM / weight charts past the
last NPORT filing. NET assets (`ASSUME_TOTAL_ASSETS_GROSS=False`).

### 3. `config.py` — `SpacexBaron.SPACEX_REMARKS` — append one re-mark (SPCX is public now)
```python
{"date":"YYYY-MM-DD",
 "spacex_value_usd": 3.89026788e9 * (<SPCX close> / 105.32),   # 3/31 shares x live price
 "per_share_old_split_adj":105.32,"per_share_new":<SPCX close>,
 "valuation_post_money_usd":1.77e12,"basis":"...","source_url":"https://finance.yahoo.com/quote/SPCX",
 "confidence":"high"}
```
`3.89026788e9` = 3/31 NPORT SpaceX gross LMV at $105.32 split-adj (= 36.94M shares). The
re-mark marks the **disclosed 3/31 share count only**. Any estimated IPO/Friday *buy*
stays in the recalibration card as an estimate — **never** booked into this hard mark.
This step drives the **SpaceX fair value** and the daily **SpaceX weight** re-mark.

### 4. `situations/spacex_baron/data/nav_overrides.csv` — only if Yahoo hasn't posted BPTIX NAV
Yahoo lags, so the morning after day T it usually lacks BPTIX's NAV. The user already gives you
the **actual BPTIX NAV**, so just add it as a row:
```
YYYY-MM-DD,<BPTIX NAV>,"BPTIX actual (user-reported); Yahoo BPTIX pending",high
```
e.g. `2026-06-15,307.55,"BPTIX actual; Yahoo pending",high`. **Why this file:**
`emit._load_nav_csv` merges it into the NAV series, and **Yahoo always wins on shared
dates** — so once Yahoo posts the real NAV the override is ignored automatically. It lives
in `emit` (not the fetcher) so it **survives the CI rebuild**, which re-fetches and
overwrites `nav_daily.csv` from Yahoo on every push. Check first:
`py -c "import json,urllib.request;..."` or just look at `nav_daily.csv` after a build.

### 5. Do NOT touch `ipo_day_recon.py`
It is **pinned to the 6/12 IPO day** (`IPO_DAY = CFG.IPO_FIRST_TRADE_DATE`): `_two_anchor_days`
caps at IPO_DAY and the re-mark step filters `<= IPO_DAY`. Adding 6/15+ AUM/re-marks will
NOT shift it. If you ever change the IPO-day card, keep the cap.

### 6. `py make_daily_log.py` — write the append-only daily journal
Creates `daily_log/<day>.md` (one file per trading day, **never edited after creation**) — the
as-of trace trail. Run it after editing `daily_nav_log.py` (so the day's estimate/actual is in
the JSON). It skips files that already exist, so it can never overwrite a frozen day. See
[`daily_log/README.md`](daily_log/README.md).

> The daily NAV table also now carries columns the build emits automatically (no manual step):
> SpaceX sh/BPTIX, BPTIX sh out, **net flow** (daily redemption $), net cash, SpaceX contrib,
> plus the fixed-basket composition/drift card (4 unit toggles + Absolute/Difference mode).

### Next public holdings filing — the 6/30/2026 NPORT-P (≈ Aug 27, 2026)
The 6/30/2026 NPORT-P is the next full holdings disclosure. Historical filing lag is 51–61 days
(6/30/2025 → 2025-08-27 = 58d; 3/31/2026 → 2026-05-22 = 52d) → **expect ~2026-08-27 (Aug 20–30)**.
When it lands, verify our theory: basket drift (overweight FDS/FIG/GWRE/IT/KNSL?), SpaceX share
count (~36.94M + ~$262M buy ⇒ ~38.57M?), leverage ≈ 1.0, cash ~gone. (See `daily_log/README.md`.)

---

## Rebuild + verify + ship

```
py build.py                 # rebuilds ALL dashboard JSON (network-free modules + Yahoo fetch)
```
Then verify (all must be the new day T):
```
py -c "import json;d=json.load(open('dashboard/data/spacex_baron.json'));print('main last:',d['meta']['last_data_day'],'wt=%.2f%%'%(d['kpis']['spacex_weight']*100))"
py -c "import json;d=json.load(open('dashboard/data/ipo_day_recon.json'));print('IPO card still:',d['meta']['date'])   # MUST stay 2026-06-12"
py -c "import json;d=json.load(open('dashboard/data/recalibration.json'));print('recalib vintage days:',len(d['vintage_ledger']))"
```
Checklist: main `last_data_day` == T · SpaceX weight moved · IPO card still 2026-06-12 ·
daily_nav_log + recalibration show T · vintage froze the new day.

Commit + push (the auto-rebuild Action re-runs `build.py` and may race on generated JSON):
```
git add -A
git commit -m "Update to T: ..."
git pull --rebase origin main          # on conflicts (generated JSON): git checkout --theirs dashboard/data/*.json ; git add -A ; GIT_EDITOR=true git rebase --continue
git push origin main
```
Deploy is **GitHub Pages** from `dashboard/` (pages.yml). `rebuild-data.yml` re-runs
`build.py` with fetch on each push and commits refreshed JSON + `nav_daily.csv` `[skip ci]`.
Build modules must stay **network-free except the known Yahoo/EDGAR fetches** (heavy fetches
rate-limit on CI and ship blank sections).

---

## RONB cross-reference (extra daily data point)

`ronb_crossref.py` uses **RONB (Baron First Principles ETF)** — Baron's daily-transparent ETF run
alongside BPTIX (holds SpaceX directly + the same public names). Post-IPO RONB↔BPTIX daily returns
correlate **0.997** with BPTIX ≈ **1.3× RONB**, and RONB prints its close the same day **before** BPTIX's
NAV posts → a leading cross-check, plus daily holdings (new-name watch: IBKR/MORN/ABNB/LYV; BPTIX-only:
CoStar). Not identical — unlevered, diverged pre-IPO, different SpaceX weight (RONB ~31% vs BPTIX ~37%).
- **Update:** the holdings seed is `RONB_SEED` in `ronb_crossref.py` (from Baron's daily CSV, as-of dated);
  refresh prices + re-cache with `py ronb_crossref.py --refresh` (commits `situations/spacex_baron/data/ronb.json`).
  When the teammate supplies a fresher RONB holdings snapshot, update `RONB_SEED` (ticker, weight) and its as_of.
- **Use it as a sanity check:** after estimating BPTIX's NAV, confirm RONB's same-day return × ~1.3 ≈ your move.

## Weekly / occasional

- **`long_replication.py`** (3-yr public-book replication): prices are cached in
  `situations/spacex_baron/data/raw/replication_prices.json`. Refresh roughly weekly:
  `py long_replication.py --refresh` (network), then commit the cache + rebuilt JSON.
- **New NPORT filing (~quarterly):** `py build.py` auto-pulls it (EDGAR), extending anchors;
  re-check `long_replication` coverage and the name→ticker map for any new holding.

---

## Map of what each daily input feeds

| input | files touched | charts / cards refreshed |
|---|---|---|
| 23 closes + SPCX | `daily_nav_log.ENTRIES` | Daily NAV estimate; recalibration (auto) |
| BPTIX NAV (T) | `daily_nav_log` actual_nav; `nav_overrides.csv` (BPTIX actual); `morningstar_aum_log` | recalibration; main NAV/weight series |
| Morningstar AUM (T) | `morningstar_aum_log.jsonl`; `daily_nav_log` aum | reconstructed AUM; SpaceX weight; recalibration flow |
| SPCX close (T) | `config.SPACEX_REMARKS` | SpaceX fair value; SpaceX weight re-mark; what-moved-the-weight |
