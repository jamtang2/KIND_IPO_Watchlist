"""
KIND 검색 POST 엔드포인트 직접 탐색
- 실제 버튼 클릭 없이, Playwright로 form submit을 JS로 트리거
- 네트워크 요청 인터셉트로 정확한 URL + body 캡처
"""
import json, sys
from playwright.sync_api import sync_playwright
from datetime import date, timedelta

KIND_URL = "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain"

def main():
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ko-KR", timezone_id="Asia/Seoul",
            extra_http_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
        )
        page = context.new_page()

        def on_request(req):
            if req.method == "POST":
                captured.append({
                    "url": req.url,
                    "post_data": req.post_data,
                    "headers": {k: v for k, v in req.headers.items() if k.lower() in ("content-type", "referer")},
                })

        page.on("request", on_request)
        page.goto(KIND_URL, wait_until="networkidle", timeout=30000)

        # ── 폼 내 모든 버튼/링크 탐색 ────────────────────────────
        buttons = page.evaluate("""() => {
            const elems = [...document.querySelectorAll('a, button, input[type=submit], input[type=button]')];
            return elems.map(el => ({
                tag: el.tagName,
                id: el.id,
                href: el.href || null,
                text: el.innerText?.trim() || el.value || '',
                onclick: el.getAttribute('onclick') || null,
            })).filter(e => e.text || e.id || e.onclick);
        }""")
        print("=== 버튼/링크 목록 ===")
        print(json.dumps(buttons, ensure_ascii=False, indent=2))

        # ── 상장유형 체크박스 값 확인 ─────────────────────────────
        listing_cbs = page.evaluate("""() => {
            return [...document.querySelectorAll('input[name="listTypArr"]')].map(el => {
                let label = '';
                const lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim();
                if (!label) {
                    const p = el.closest('label');
                    if (p) label = p.innerText.trim();
                }
                return { id: el.id, value: el.value, checked: el.checked, label };
            });
        }""")
        print("\n=== 상장유형 checkboxes ===")
        print(json.dumps(listing_cbs, ensure_ascii=False, indent=2))

        # ── 심사결과 체크박스 값 확인 ─────────────────────────────
        result_cbs = page.evaluate("""() => {
            return [...document.querySelectorAll('input[name="invstgRsltArr"]')].map(el => {
                let label = '';
                const lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim();
                if (!label) {
                    const p = el.closest('label');
                    if (p) label = p.innerText.trim();
                }
                return { id: el.id, value: el.value, checked: el.checked, label };
            });
        }""")
        print("\n=== 심사결과 checkboxes ===")
        print(json.dumps(result_cbs, ensure_ascii=False, indent=2))

        # ── 시장구분 필드 탐색 ────────────────────────────────────
        mkt = page.evaluate("""() => {
            const radios = [...document.querySelectorAll('input[type=radio]')].map(el => {
                let label = '';
                const lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim();
                return { name: el.name, id: el.id, value: el.value, checked: el.checked, label };
            });
            const selects = [...document.querySelectorAll('select')].map(el => ({
                name: el.name, id: el.id,
                options: [...el.options].map(o => ({ value: o.value, text: o.text.trim() }))
            }));
            return { radios, selects };
        }""")
        print("\n=== 시장구분 (radio/select) ===")
        print(json.dumps(mkt, ensure_ascii=False, indent=2))

        # ── JS로 검색 폼 submit ───────────────────────────────────
        print("\n=== JS로 검색 버튼 클릭 ===")
        captured.clear()

        # JS로 직접 onclick 실행 또는 form submit
        result = page.evaluate("""() => {
            // blaSearch 버튼 찾기
            const btn = document.querySelector('#blaSearch') || document.querySelector('a[href*="Search"]');
            if (btn) {
                btn.click();
                return { clicked: btn.id || btn.href || btn.innerText };
            }
            // form 직접 submit
            const form = document.querySelector('form[id*="search"], form[name*="search"]');
            if (form) {
                form.submit();
                return { submitted: form.id || form.name || form.action };
            }
            return { error: 'no button or form found' };
        }""")
        print(f"클릭 결과: {result}")
        page.wait_for_load_state("networkidle", timeout=20000)

        print("\n=== 캡처된 POST 요청 ===")
        for r in captured:
            print(json.dumps(r, ensure_ascii=False, indent=2))

        # ── 결과 테이블 ──────────────────────────────────────────
        table_info = page.evaluate("""() => {
            const table = document.querySelector('table');
            if (!table) return { error: 'no table' };
            const headers = [...table.querySelectorAll('th')].map(th => th.innerText.trim());
            const rows = [...table.querySelectorAll('tbody tr')].slice(0, 3).map(tr =>
                [...tr.querySelectorAll('td')].map(td => td.innerText.trim())
            );
            return { headers, sampleRows: rows, totalRows: table.querySelectorAll('tbody tr').length };
        }""")
        print("\n=== 테이블 구조 ===")
        print(json.dumps(table_info, ensure_ascii=False, indent=2))

        browser.close()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
