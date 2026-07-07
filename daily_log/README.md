# Daily log — append-only research journal

One file per trading day (`YYYY-MM-DD.md`). **These files are append-only: a day's file is
written once and never edited.** To see what we believed/estimated on a given day, open that
day's file — the as-of estimate, the frozen vintage, the actual + scoring, the flow, the
narrative, and that day's commits are all there. This is the trace trail that preserves the
**as-of** information so we can always look back at what we knew when.

- **Numbers are genuinely as-of** (pulled from the frozen `daily_nav_vintage.jsonl`, the
  Morningstar AUM log, and `daily_nav_log`). For days compiled in a batch (everything up to
  2026-06-26 was compiled 2026-06-29) the *narrative* may fold in slightly later analysis;
  from 2026-06-29 forward each file is written contemporaneously.
- **Generator:** `py make_daily_log.py` — writes only files that don't exist yet (so it can
  never overwrite a frozen day). Run it after each daily update; it creates that day's file.
- Earlier project history (pre-IPO dashboard build, 6/5–6/8 feature work) lives in git.

## Analyses (one-off diagnostics, dated, filed here)

Named `YYYY-MM-DD-analysis-<topic>.md` (distinct from the `YYYY-MM-DD.md` daily entries), append-only.

- [2026-07-02 — drift diagnosis](2026-07-02-analysis-drift-diagnosis.md): why the daily estimate
  misses. Firm conclusion — it's **public-basket composition drift (underweight TSLA + overweight
  the mid-caps)**, NOT leverage and NOT the SpaceX weight (each ruled out by a specific day).
  Reproduce with `py analyze_drift.py`.
- [2026-07-07 — position-mark basket v1](2026-07-07-basket-mark-v1.md): the current best fixed basket
  for marking BPTIX P&L (0.60 SPCX + 23 public stocks + ~$0 cash, priced 7/6). SEC-disclosed names,
  freshest weights, one validated tilt (TSLA 24.7%→22%), no overfit. CSV:
  `situations/spacex_baron/data/position_mark_basket_2026-07-06.csv`. Rebuild as v2 at the 6/30 NPORT (~Aug 27).

## Daily-update checklist (what to touch each market day)

The authoritative, detailed version is [`../DAILY_UPDATE_PROTOCOL.md`](../DAILY_UPDATE_PROTOCOL.md).
Quick list:

**At/after close (day T)** — user pastes the 23 public closes + the SPCX close:
1. `daily_nav_log.py` `ENTRIES` — append day T (`actual_nav: None, aum: None`, closes, spcx, note).
2. `py make_daily_log.py` — write `daily_log/T.md` (the as-of journal entry).

**Next morning (T+1)** — user gives BPTIX NAV + Morningstar AUM for day T:
1. `daily_nav_log.py` — fill T's `actual_nav` + `aum`, update the note (scoring, flow, leverage read).
2. `situations/spacex_baron/data/morningstar_aum_log.jsonl` — append one line (AUM + NAV).
3. `config.py` `SpacexBaron.SPACEX_REMARKS` — append T's re-mark (SPCX close → SpaceX value).
4. `nav_overrides.csv` — only if Yahoo hasn't posted BPTIX NAV yet (usually it has by T+1).
5. `py build.py` (with fetch) — refreshes `nav_daily.csv` + all JSON.
6. `py make_daily_log.py` — the T file already exists (estimate); it stays frozen. (The T+1
   completion is captured in T's `## Outcome` only if you re-run before T.md was created;
   normally the scoring lives in the next estimate day's notes + git.)
7. **Do NOT touch** `ipo_day_recon.py` (pinned to 6/12).

Then: commit → `git pull --rebase` (on conflicts: `git checkout --theirs dashboard/data/*.json`,
`git add -A`, `GIT_EDITOR=true git rebase --continue`) → rebuild → push.

## Next milestone — the 6/30/2026 NPORT-P (basket-drift verification)

The next full public holdings filing is the **6/30/2026 NPORT-P** (Baron Partners Fund,
CIK 0001217673, series S000000588). NPORT-P is filed within 60 days of quarter-end; Baron's
historical lag is **51–61 days** (the prior-year analog 6/30/2025 → filed 2025-08-27 = 58 d;
the most recent 3/31/2026 → 2026-05-22 = 52 d). So expect it **~2026-08-27 (window Aug 20–30)**.

**What to check against it** (our current theory, to confirm or revise):
- **Basket drift** — is the fund actually OVERWEIGHT the high-dispersion names our snapshots
  under-capture (FDS, FIG, GWRE, IT, KNSL)? The 6/25 (all baskets too high) / 6/26 (all too
  low) mirror said yes. The 6/30 weights settle it.
- **SpaceX share count / weight** — does it confirm the ~36.94M disclosed shares + the ~$262M
  Friday-buy add (→ ~38.57M), and the re-marked weight?
- **Leverage** — confirm gross/net ≈ 1.0 (we've held L = 1.0 since 6/16).
- **Cash** — confirm the buffer is ~gone (consumed by the ~$2.4B of redemptions since 6/12).
