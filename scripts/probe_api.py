"""
KIND API 엔드포인트 직접 탐색 (headless, 자동화)
Playwright로 네트워크 요청을 인터셉트하여 실제 API 스펙을 출력
"""
import json
from playwright.sync_api import sync_playwright
from datetime import date, timedelta

KIND_URL = "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain"

def main():
    search_requests = []
    excel_requests = []

    def on_request(request):
        if request.method == "POST":
            search_requests.append({
                "url": request.url,
                "method": request.method,
                "post_data": request.post_data,
            })

    def on_excel_request(request):
        if request.method == "POST":
            excel_requests.append({
                "url": request.url,
                "method": request.method,
                "post_data": request.post_data,
            })

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            extra_http_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": "https://kind.krx.co.kr/",
            },
        )
        page = context.new_page()

        print("KIND 페이지 로딩...")
        page.goto(KIND_URL, wait_until="networkidle", timeout=30000)
        print(f"제목: {page.title()}")

        # ── 폼 필드 구조 탐색 ────────────────────────────────────
        print("\n=== INPUT 필드 ===")
        inputs = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input')).map(el => {
                let label = '';
                if (el.id) {
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl) label = lbl.innerText.trim();
                }
                if (!label) {
                    const parent = el.closest('label');
                    if (parent) label = parent.innerText.trim();
                }
                return {
                    type: el.type,
                    name: el.name,
                    id: el.id,
                    value: el.value,
                    checked: el.type === 'checkbox' || el.type === 'radio' ? el.checked : undefined,
                    label: label
                };
            });
        }""")
        print(json.dumps(inputs, ensure_ascii=False, indent=2))

        print("\n=== SELECT 필드 ===")
        selects = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('select')).map(el => {
                return {
                    name: el.name,
                    id: el.id,
                    selectedValue: el.value,
                    options: Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}))
                };
            });
        }""")
        print(json.dumps(selects, ensure_ascii=False, indent=2))

        # ── 검색 클릭 → 요청 캡처 ────────────────────────────────
        print("\n=== 검색 실행 ===")
        page.on("request", on_request)

        # 날짜 범위: 최근 12개월
        from_date = (date.today() - timedelta(days=365)).strftime("%Y.%m.%d")
        to_date = date.today().strftime("%Y.%m.%d")
        print(f"청구일 범위: {from_date} ~ {to_date}")

        # 검색 버튼 클릭
        search_btn = page.locator("#blaSearch").first
        if not search_btn.is_visible():
            search_btn = page.get_by_text("검색").first
        search_btn.click()
        page.wait_for_load_state("networkidle", timeout=20000)

        print("\n=== 검색 시 POST 요청 ===")
        for r in search_requests:
            print(json.dumps(r, ensure_ascii=False, indent=2))

        # ── 결과 테이블 헤더/샘플 ────────────────────────────────
        print("\n=== 테이블 구조 ===")
        table_info = page.evaluate("""() => {
            const table = document.querySelector('table');
            if (!table) return null;
            const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
            const firstRow = Array.from(table.querySelectorAll('tbody tr:first-child td')).map(td => td.innerText.trim());
            const totalRows = table.querySelectorAll('tbody tr').length;
            return { headers, firstRow, totalRows };
        }""")
        print(json.dumps(table_info, ensure_ascii=False, indent=2))

        # ── EXCEL 버튼 탐색 ──────────────────────────────────────
        print("\n=== EXCEL 버튼 ===")
        excel_btn = page.locator("#blaExcel")
        if excel_btn.count() > 0:
            print(f"EXCEL 버튼 발견: href={excel_btn.get_attribute('href')}, onclick={excel_btn.get_attribute('onclick')}")
            page.remove_listener("request", on_request)
            page.on("request", on_excel_request)
            try:
                with page.expect_download(timeout=8000) as dl_info:
                    excel_btn.click()
                dl = dl_info.value
                path = dl.save_as(f"data/KIND_sample.xlsx")
                print(f"EXCEL 다운로드 성공: {dl.suggested_filename}")
            except Exception as e:
                print(f"EXCEL 다운로드 실패: {e}")

            print("\n=== EXCEL POST 요청 ===")
            for r in excel_requests:
                print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print("EXCEL 버튼을 찾지 못했습니다.")

        browser.close()

if __name__ == "__main__":
    main()
