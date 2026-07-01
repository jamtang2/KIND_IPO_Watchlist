# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean IPO pre-listing review (상장예비심사) watchlist dashboard. Scrapes KIND (Korea Exchange) for companies in "청구서 접수" (application received) status and tracks their review progress over time.

**Target page**: `https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain`

Full requirements are in `PRD/KIND_예비심사_대시보드_PRD.md`.

## Architecture

- **Collector** (`collect.py`): Python script that queries KIND, diffs against stored JSON, updates state
- **Data store** (`data/companies.json`): JSON file committed to repo; contains `companies` (active) and `archived` (expired after 30 days post-result) arrays
- **Frontend** (`index.html` / `src/`): Static HTML/JS dashboard served via GitHub Pages
- **Automation** (`.github/workflows/collect.yml`): Runs collector weekly; cron `0 12 * * 4` (UTC) = Thursday 21:00 KST

## Data Collection Strategy (Priority Order)

**Try in this order — confirm actual request shape with browser DevTools before coding:**

1. **EXCEL download endpoint** — capture the HTTP request the "EXCEL" button sends; replay it with `requests`. Most stable approach.
2. **AJAX search endpoint** — capture the "검색" button's XHR call (likely `method=searchListInvstgCorpSub` pattern); parse JSON/HTML fragment response.
3. **Playwright headless browser** — fallback if session/token validation blocks the above.

M1 (Milestone 1) must confirm actual parameter names and endpoint URLs before any scraper code is written.

## Filter Parameters (to be confirmed in M1)

| Field | Expected param | Value |
|---|---|---|
| 시장구분 | `marketType` | 전체 |
| 상장유형 | `listType[]` | 신규상장, 이전상장 only |
| 심사결과 | `examResult[]` | All (classify in pipeline) |
| 청구일 | `fromDate`/`toDate` | Last N months (default 12) |

## Core Business Logic

**Status mapping** (KIND raw → display, color):
- `청구서 접수` → 진행중, neutral (no expiry)
- `심사승인` → 심사승인, green
- `심사미승인` → 심사미승인, red
- `심사철회` → 심사철회, yellow
- `공모철회` / `상장철회` / `승인효력기간만료` → display as-is, gray (treated as resolved)

**Elapsed days**: Store only `apply_date` in JSON; compute `today - apply_date` client-side at render time so the number stays accurate between weekly runs.

**30-day expiry**: When status first changes from `청구서 접수` to any resolved state, record `result_date`. When `today - result_date > 30`, move the record from `companies` to `archived`. Expiry check runs only on Thursday batch — up to 6-day lag is acceptable and documented.

## JSON Schema

```json
{
  "last_updated": "2026-07-01T21:00:00+09:00",
  "companies": [{
    "corp_name": "...",
    "market": "코스닥 | 유가증권",
    "listing_type": "신규상장 | 이전상장",
    "apply_date": "YYYY-MM-DD",
    "status_raw": "KIND 원본값",
    "status_display": "표시값",
    "status_color": "green | red | yellow | gray | neutral",
    "result_date": "YYYY-MM-DD | null",
    "expire_date": "YYYY-MM-DD | null",
    "history": [{"date": "YYYY-MM-DD", "status": "..."}]
  }],
  "archived": []
}
```

## GitHub Actions Notes

- cron `0 12 * * 4` = UTC Thursday 12:00 = KST Thursday 21:00
- Always include `workflow_dispatch:` trigger for manual runs
- No secrets needed (public data source)
- GitHub disables schedule workflows after 60 days of repo inactivity — add a comment in the workflow file noting this

## Development Commands

*(To be populated as the project is built)*

```bash
# Install dependencies
pip install -r requirements.txt

# Run collector manually
python collect.py

# Run with Playwright (if needed)
playwright install chromium
python collect.py --mode playwright
```
