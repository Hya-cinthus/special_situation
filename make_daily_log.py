"""
Append-only daily research journal -> daily_log/YYYY-MM-DD.md (one file per trading day).

WHY: a trace trail that preserves the AS-OF information. Each day gets its OWN file so
nothing earlier is ever edited — to see what we believed on a given day, open that day's
file. Numbers (the as-of estimate, the frozen vintage, the actual + scoring) are pulled
from the committed records, so they are genuinely as-of; the narrative may fold in slightly
later analysis for days compiled in a batch (flagged in the header).

HOW: assembles each day from daily_nav_log.json (revised rows + frozen vintage_rows),
the Morningstar AUM log, and that day's git commits. Pure stdlib. Run it after each daily
update: `py make_daily_log.py`. It ONLY writes files that don't exist yet (append-only,
idempotent) — it never overwrites a day already on disk.
"""

import datetime
import json
import os
import subprocess

_ROOT = os.path.abspath(os.path.dirname(__file__))
_OUT_DIR = os.path.join(_ROOT, "daily_log")
_NAVLOG = os.path.join(_ROOT, "dashboard", "data", "daily_nav_log.json")
_MSLOG = os.path.join(_ROOT, "situations", "spacex_baron", "data", "morningstar_aum_log.jsonl")


def _commits_by_date():
    """{date: [(hash, subject), ...]} from git, excluding the auto-rebuild commits."""
    out = {}
    try:
        raw = subprocess.run(["git", "log", "--date=short", "--pretty=format:%cd|%h|%s"],
                             cwd=_ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30).stdout
    except Exception:
        return out
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        d, h, subj = parts
        if subj.startswith("auto: rebuild"):
            continue
        out.setdefault(d, []).append((h, subj))
    return out


def _ms_by_date():
    out = {}
    if os.path.exists(_MSLOG):
        for line in open(_MSLOG, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                out[r["as_of_date_iso"]] = r
    return out


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def _est(row, methods):
    """As-of estimate from a row's preds: (median, lo, hi)."""
    navs = [row["preds"][m]["pred_nav"] for m in methods if row.get("preds", {}).get(m)]
    if not navs:
        return None, None, None
    return _median(navs), min(navs), max(navs)


def render(date, rev, aso, ms, commits, methods, lbl, compiled):
    wd = datetime.date.fromisoformat(date).strftime("%a")
    backfilled = rev.get("backfilled")
    L = rev.get("leverage")
    lines = []
    lines.append("# Daily log — %s (%s)%s" % (date, wd, "  · BACKFILL" if backfilled else ""))
    lines.append("")
    lines.append("_Compiled %s from the committed records (daily_nav_vintage.jsonl, morningstar_aum_log, "
                 "daily_nav_log, git). Append-only: this file is never edited after creation. The numbers "
                 "(as-of estimate, frozen vintage, actual + scoring) are genuinely as-of; for days compiled "
                 "in a batch the narrative may fold in slightly later analysis._" % compiled)
    lines.append("")

    # --- inputs ---
    spx_ret = rev.get("spcx_ret_pct")
    lines.append("## Inputs")
    lines.append("- **SPCX** $%.2f (%s%.2f%%); 23 public closes in." % (
        rev["spcx"], "+" if (spx_ret or 0) >= 0 else "", spx_ret or 0))
    if rev.get("actual_nav") is not None:
        aum = ("$%.1fB" % rev["aum_used_b"]) if rev.get("aum_used_b") is not None else "n/a"
        lines.append("- **BPTIX NAV** %.2f (actual); **Morningstar AUM** %s." % (rev["actual_nav"], aum))
    else:
        lines.append("- Actual NAV + AUM: _pending next morning_ (estimate-only day).")
    lines.append("")

    # --- as-of estimate ---
    med, lo, hi = _est(aso, methods)
    lines.append("## As-of estimate (frozen)")
    if med is not None:
        lines.append("- Median **%.2f**, per-basket range %.2f–%.2f." % (med, lo, hi))
    if rev.get("perfect_fit_range"):
        pf = rev["perfect_fit_range"]
        lines.append("- Perfect-fit band: %.2f–%.2f." % (pf[0], pf[1]))
    lines.append("- Entering SpaceX weight %.2f%% · leverage %s · SpaceX contribution %s%.3f%%." % (
        aso.get("spacex_weight_pct", 0),
        ("%.2f" % L) if L is not None else "—",
        "+" if (rev.get("spx_contrib_pct") or 0) >= 0 else "", rev.get("spx_contrib_pct") or 0))
    lines.append("")

    # --- outcome ---
    if rev.get("actual_nav") is not None and rev.get("errors"):
        lines.append("## Outcome vs estimate")
        errs = rev["errors"]
        best = rev.get("best_method")
        errstr = ", ".join("%s %s%.2f" % (lbl[m], "+" if errs[m] >= 0 else "", errs[m]) for m in methods if m in errs)
        lines.append("- Actual **%.2f**. Per-basket error: %s." % (rev["actual_nav"], errstr))
        if best:
            lines.append("- Best basket: **%s** (%s%.2f)." % (lbl[best], "+" if errs.get(best, 0) >= 0 else "", errs.get(best, 0)))
        lines.append("")

    # --- flow & leverage ---
    fb = rev.get("flow_b")
    if fb is not None:
        kind = "net redemption" if fb < 0 else "net subscription"
        amt = ("$%.2fB" % abs(fb)) if abs(fb) >= 1 else ("$%dM" % round(abs(fb) * 1000))
        lines.append("## Flow & leverage")
        lines.append("- Net flow: **%s%s** (%s) — = AUM_end − AUM_prev × NAV_end/NAV_prev." % (
            "−" if fb < 0 else "+", amt, kind))
        lines.append("- Leverage (start-of-day, modeled): %s." % (("%.2f" % L) if L is not None else "—"))
        lines.append("")

    # --- narrative ---
    if rev.get("note"):
        lines.append("## Notes")
        lines.append(rev["note"])
        lines.append("")

    # --- morningstar source line ---
    if ms:
        lines.append("## Source (Morningstar log)")
        lines.append("- %s" % ms.get("source", ""))
        if ms.get("notes"):
            lines.append("- %s" % ms["notes"])
        lines.append("")

    # --- commits ---
    if commits:
        lines.append("## Commits this day")
        for h, subj in commits:
            lines.append("- `%s` %s" % (h, subj))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    os.makedirs(_OUT_DIR, exist_ok=True)
    d = json.load(open(_NAVLOG, encoding="utf-8"))
    methods = d["meta"]["methods"]
    lbl = d["meta"]["method_labels"]
    rev_by = {r["date"]: r for r in d["rows"]}
    aso_by = {r["date"]: r for r in d["vintage_rows"]}
    ms_by = _ms_by_date()
    commits = _commits_by_date()
    compiled = datetime.date.today().isoformat()

    written, skipped = [], []
    for date in sorted(rev_by):
        path = os.path.join(_OUT_DIR, date + ".md")
        if os.path.exists(path):
            skipped.append(date)
            continue
        rev = rev_by[date]
        aso = aso_by.get(date, rev)
        md = render(date, rev, aso, ms_by.get(date), commits.get(date, []), methods, lbl, compiled)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        written.append(date)
    print("daily_log: wrote %d (%s), skipped %d existing" % (len(written), ", ".join(written) or "none", len(skipped)))


if __name__ == "__main__":
    main()
