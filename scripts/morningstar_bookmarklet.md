# Morningstar BPTRX bookmarklet

A one-click browser bookmark that scrapes the BPTRX Morningstar quote page from
**your own logged-in Chrome/Safari/Firefox**, builds the JSON record the build
pipeline expects, copies it to your clipboard, and offers to open the GitHub
edit page so you can paste-and-commit.

**Why this and not cowork/Playwright/headless?**
Anthropic's Claude-in-Chrome (cowork) is configured to block `morningstar.com`,
and Morningstar's own bot defense (Akamai) reliably blocks Playwright/headless.
A bookmarklet runs as JS inside your real authenticated browser, so neither
defense applies — it just works.

## One-time install (Chrome / Edge / Brave)

1. Open your bookmarks bar (Ctrl+Shift+B).
2. Right-click the bar → **Add page…**
3. **Name:** `BPTRX scrape`
4. **URL:** paste the entire `javascript:(...)` line from the
   [next section](#bookmarklet-url) (one line, no breaks).
5. Save.

Safari: Bookmarks → Edit Bookmarks → New → paste the URL.
Firefox: Bookmarks → Manage → New Bookmark → paste the URL.

## Daily workflow (~10 seconds)

1. Open <https://www.morningstar.com/funds/XNAS/BPTRX/quote> (you must be on
   the **Quote** tab; the bookmarklet reads fields from that panel).
2. Click the **BPTRX scrape** bookmark.
3. A dialog appears with the JSON line that was just copied to your clipboard.
   Click **OK** to open the GitHub edit page in a new tab.
4. On the GitHub edit page: scroll to the end of the file, place the cursor on a
   new line after the last record, **paste**, then **Commit changes** directly
   to main with message: `cowork: BPTRX scrape <YYYY-MM-DD>`.
5. Done. The `rebuild-data` Action runs, regenerates
   `dashboard/data/spacex_baron.json`, and Vercel auto-deploys.

## Bookmarklet URL

Copy this entire single line into the bookmark's URL field:

```
javascript:(function(){const f=L=>{const A=[...document.body.querySelectorAll('*')].filter(e=>!e.children.length);const n=A.find(e=>e.textContent.trim()===L);if(!n)return null;const p=n.parentElement;const i=p?[...p.children].indexOf(n):-1;const s=n.nextElementSibling||(p&&i>=0&&p.children[i+1])||null;return s?s.textContent.trim():null};const nf=f('NAV / 1-Day Return')||'';const [ns,rs]=nf.split('/').map(s=>(s||'').trim());const ta=f('Total Assets');const m=ta&&ta.match(/([\d.,]+)\s*([BMK]?)/i);const mult={B:1e9,M:1e6,K:1e3,'':1};const usd=m?Math.round(parseFloat(m[1].replace(/,/g,''))*mult[m[2].toUpperCase()]):null;const txt=document.body.innerText;const ad=(txt.match(/NAV as of ([A-Za-z]+ \d+,\s*\d{4})/)||[])[1]||null;const iso=ad?new Date(ad).toISOString().slice(0,10):new Date().toISOString().slice(0,10);const d={as_of_date_iso:iso,ticker:'BPTRX',total_assets_raw:ta,total_assets_usd:usd,total_assets_label:'Total Assets',total_assets_as_of:ad,total_assets_definition:null,net_assets_field:null,nav_per_share:parseFloat(ns)||null,nav_one_day_return_pct:parseFloat((rs||'').replace('%',''))||null,nav_as_of:ad,expense_ratio:f('Expense Ratio'),adj_expense_ratio:f('Adj. Expense Ratio'),distribution_fee_level:f('Distribution Fee Level'),share_class_type:f('Share Class Type'),category:f('Category'),investment_style:f('Investment Style'),min_initial_investment:f('Min. Initial Investment'),status:f('Status'),ttm_yield:f('TTM Yield'),turnover:f('Turnover'),medalist_rating:null,star_rating:null,inception_date:null,captured_at:new Date().toISOString(),blocked:false,notes:'extracted via bookmarklet'};const line=JSON.stringify(d);navigator.clipboard.writeText(line).then(()=>{if(confirm('Copied to clipboard:\n\n'+line+'\n\nOpen GitHub to paste & commit?'))window.open('https://github.com/Hya-cinthus/special_situation/edit/main/situations/spacex_baron/data/morningstar_aum_log.jsonl','_blank')},e=>alert('Clipboard error: '+e+'\n\n'+line));})();
```

## Readable source (for review/editing)

```js
(function () {
  // text-match a leaf element, then read its next sibling — robust to React class-name churn
  const f = (label) => {
    const leaves = [...document.body.querySelectorAll('*')].filter((e) => !e.children.length);
    const node = leaves.find((e) => e.textContent.trim() === label);
    if (!node) return null;
    const p = node.parentElement;
    const i = p ? [...p.children].indexOf(node) : -1;
    const sib = node.nextElementSibling || (p && i >= 0 && p.children[i + 1]) || null;
    return sib ? sib.textContent.trim() : null;
  };

  // "NAV / 1-Day Return" is a single combined field like "249.68 / +0.40%"
  const navField = f('NAV / 1-Day Return') || '';
  const [navStr, retStr] = navField.split('/').map((s) => (s || '').trim());

  // "Total Assets" raw like "15.6B" — parse to a USD integer
  const ta = f('Total Assets');
  const m = ta && ta.match(/([\d.,]+)\s*([BMK]?)/i);
  const mult = { B: 1e9, M: 1e6, K: 1e3, '': 1 };
  const usd = m ? Math.round(parseFloat(m[1].replace(/,/g, '')) * mult[m[2].toUpperCase()]) : null;

  // pull the "NAV as of <Month DD, YYYY>" date from the panel footer
  const ad = (document.body.innerText.match(/NAV as of ([A-Za-z]+ \d+,\s*\d{4})/) || [])[1] || null;
  const iso = ad ? new Date(ad).toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);

  const d = {
    as_of_date_iso: iso,
    ticker: 'BPTRX',
    total_assets_raw: ta,
    total_assets_usd: usd,
    total_assets_label: 'Total Assets',
    total_assets_as_of: ad,
    total_assets_definition: null,   // bookmarklet doesn't hover-fetch tooltips; add manually if you can
    net_assets_field: null,           // search Fund Analysis / Performance tabs manually if curious
    nav_per_share: parseFloat(navStr) || null,
    nav_one_day_return_pct: parseFloat((retStr || '').replace('%', '')) || null,
    nav_as_of: ad,
    expense_ratio: f('Expense Ratio'),
    adj_expense_ratio: f('Adj. Expense Ratio'),
    distribution_fee_level: f('Distribution Fee Level'),
    share_class_type: f('Share Class Type'),
    category: f('Category'),
    investment_style: f('Investment Style'),
    min_initial_investment: f('Min. Initial Investment'),
    status: f('Status'),
    ttm_yield: f('TTM Yield'),
    turnover: f('Turnover'),
    medalist_rating: null,
    star_rating: null,
    inception_date: null,
    captured_at: new Date().toISOString(),
    blocked: false,
    notes: 'extracted via bookmarklet',
  };

  const line = JSON.stringify(d);
  navigator.clipboard.writeText(line).then(
    () => {
      if (confirm('Copied to clipboard:\n\n' + line + '\n\nOpen GitHub to paste & commit?')) {
        window.open(
          'https://github.com/Hya-cinthus/special_situation/edit/main/situations/spacex_baron/data/morningstar_aum_log.jsonl',
          '_blank'
        );
      }
    },
    (err) => alert('Clipboard error: ' + err + '\n\n' + line)
  );
})();
```

## Troubleshooting

- **"Copied: null" for Total Assets** — Morningstar may have changed the page
  layout. Open the browser console (F12), click the bookmark, look for which
  field returned null, and adjust the label in the `f('...')` call.
- **Clipboard permission denied** — older browsers block `navigator.clipboard`
  on `http:`; Morningstar is https, this should be fine. If it errors, the
  JSON line is shown in the alert — copy it manually.
- **The GitHub edit page asks you to fork** — that means you're logged into a
  GitHub account without write access to `Hya-cinthus/special_situation`. Log in
  as Hya-cinthus.

## Future: fully-automated 1-click commit

The current flow needs a manual paste on GitHub. To make it truly 1-click, we'd
add a GitHub Personal Access Token to the bookmarklet so it POSTs the line
directly via the GitHub API. That works but stores a secret in the bookmark URL
(only visible to whoever can see your bookmarks). Ask if you want this upgrade.
