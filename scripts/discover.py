"""
M1 도구: KIND 예비심사기업 페이지의 실제 HTTP 요청 구조 탐색
실행 방법: python scripts/discover.py
"""
import json
from playwright.sync_api import sync_playwright

KIND_URL = "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain"

captured_requests = []


def on_request(request):
    if request.method == "POST" or "listinvstg" in request.url:
        captured_requests.append({
            "url": request.url,
            "method": request.method,
            "post_data": request.post_data,
            "headers": dict(request.headers),
        })


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 화면 보이게 실행
        context = browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = context.new_page()
        page.on("request", on_request)

        print("=" * 60)
        print("KIND 페이지 로딩 중...")
        page.goto(KIND_URL, wait_until="networkidle", timeout=30000)

        # ── 폼 구조 출력 ──────────────────────────────────────────
        print("\n[INPUT 필드]")
        for el in page.locator("input").all():
            info = {
                "type": el.get_attribute("type"),
                "name": el.get_attribute("name"),
                "id": el.get_attribute("id"),
                "value": el.get_attribute("value"),
                "checked": el.is_checked() if el.get_attribute("type") in ("checkbox", "radio") else None,
            }
            label_text = page.evaluate(
                """el => {
                    if (el.id) {
                        const lbl = document.querySelector('label[for="' + el.id + '"]');
                        if (lbl) return lbl.innerText.trim();
                    }
                    return el.closest('label')?.innerText?.trim() || '';
                }""",
                el.element_handle(),
            )
            info["label"] = label_text
            print(json.dumps(info, ensure_ascii=False))

        print("\n[SELECT 필드]")
        for el in page.locator("select").all():
            name = el.get_attribute("name")
            opts = page.evaluate(
                "el => Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}))",
                el.element_handle(),
            )
            print(json.dumps({"name": name, "options": opts}, ensure_ascii=False))

        # ── 검색 버튼 클릭 후 요청 캡처 ──────────────────────────
        print("\n[검색 버튼 클릭]")
        captured_requests.clear()
        search_btn = page.locator("#blaSearch").first
        if search_btn.count() == 0:
            search_btn = page.get_by_text("검색", exact=True).first
        search_btn.click()
        page.wait_for_load_state("networkidle", timeout=20000)

        print("\n[검색 시 캡처된 요청]")
        for r in captured_requests:
            print(json.dumps(r, ensure_ascii=False, indent=2))

        # ── 테이블 헤더 확인 ──────────────────────────────────────
        print("\n[테이블 헤더]")
        headers = [th.inner_text().strip() for th in page.locator("table th").all()]
        print(headers)

        print("\n[첫 번째 행 샘플]")
        first_row = [td.inner_text().strip() for td in page.locator("table tbody tr:first-child td").all()]
        print(first_row)

        # ── EXCEL 버튼 클릭 후 요청 캡처 ─────────────────────────
        print("\n[EXCEL 버튼 클릭]")
        captured_requests.clear()
        excel_btn = page.locator("#blaExcel").first
        if excel_btn.count() > 0:
            with page.expect_download(timeout=10000) as dl_info:
                excel_btn.click()
            dl = dl_info.value
            print(f"다운로드 파일명: {dl.suggested_filename}")

        print("\n[EXCEL 시 캡처된 요청]")
        for r in captured_requests:
            print(json.dumps(r, ensure_ascii=False, indent=2))

        input("\nEnter를 누르면 종료합니다...")
        browser.close()


if __name__ == "__main__":
    main()
