# Daily update protocol — Baron / SpaceX dashboard

The single source of truth for what to touch each day so **nothing goes stale**. Past
mistake this prevents: filling the daily NAV log but leaving the *early* charts
(estimated SpaceX weight / reconstructed AUM / SpaceX fair value / what moved the
weight) frozen at the prior day.

Interpreter on this machine is **`py`** (Python 3.14), NOT `python`.

---

## What the user provides

- **At/after close (day T):** the 23 public-holding closes + the **SPCX** close.
- **Next morning (T+1):** **BPTIX actual NAV** and **Morningstar Total Assets (AUM)** for day T.
  (Yahoo posts BPTIX NAV with a ~1-day lag, so the user's reported NAV is the stop-gap — see step 4.)

The whole stack is on **BPTIX** (the class the user holds): `NAV_TICKER = "BPTIX"`, all NAVs, labels, charts.

---

## The five files to edit each day  (in this order)

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
- `FRIDAY_SPACEX_BUY` — assumed 6/12 SpaceX add ($262M) folded into the predicted SpaceX weight.
- `LEVERAGE_ASSUMPTION` — **start-of-day** gross/net (now **1.00**, data-confirmed 6/17: the first big-down
  basket day's actual NAV matched L=1.0 not the 5/31-disclosed 0.968 → the net-cash buffer was consumed by
  redemptions). Public sleeve weight = LEVERAGE − w_spx, remainder net cash. To re-test: a big-basket day where
  the actual NAV sits above the L=current estimate ⇒ leverage fell; below ⇒ rose. Revisit on fresh disclosures.

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
