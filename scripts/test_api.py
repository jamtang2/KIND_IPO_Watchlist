"""
API 직접 호출 테스트 - 실제 데이터 컬럼 구조 확인
"""
import requests, json
from datetime import date, timedelta

BASE_URL = "https://kind.krx.co.kr/listinvstg/listinvstgcom.do"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://kind.krx.co.kr",
}

session = requests.Session()
session.headers.update(HEADERS)
# 세션 쿠키 획득
session.get("https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain", timeout=15)

from_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
to_date = date.today().strftime("%Y-%m-%d")

payload = [
    ("method", "searchListInvstgCorpSub"),
    ("currentPageSize", "100"),
    ("pageIndex", "1"),
    ("orderMode", "2"),
    ("orderStat", "A"),
    ("forward", "listinvstgcom_sub"),
    ("bizProcNo", ""), ("listClssCd", ""), ("comAbbrv", ""),
    ("listTypeArrStr", "01|02|"),
    ("invstgRsltArrStr", "01|02|03|04|05|08|07|06|"),
    ("seq", "0"), ("searchMode", ""), ("searchCodeType", ""),
    ("searchCorpName", ""), ("isurCd", ""), ("repIsuSrtCd", ""),
    ("marketType", ""), ("searchCorpNameTmp", ""),
    ("listTypeArr", "01"), ("listTypeArr", "02"),
    ("invstgRsltArr", "01"), ("invstgRsltArr", "02"), ("invstgRsltArr", "03"),
    ("invstgRsltArr", "04"), ("invstgRsltArr", "05"), ("invstgRsltArr", "08"),
    ("invstgRsltArr", "07"), ("invstgRsltArr", "06"),
    ("fromDate", from_date), ("toDate", to_date),
]

print(f"요청: POST {BASE_URL}")
print(f"날짜 범위: {from_date} ~ {to_date}")

resp = session.post(BASE_URL, data=payload, timeout=30)
print(f"응답 상태: {resp.status_code}, 인코딩: {resp.encoding}")
print(f"응답 크기: {len(resp.content)} bytes")

# HTML 저장 (분석용)
with open("data/response_sample.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("응답 HTML → data/response_sample.html 저장")

# 간단 파싱 미리보기
from html.parser import HTMLParser
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.rows = []
        self.current_row = []
        self.current_cell = ""
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.in_table = True
        elif tag in ("td", "th") and self.in_table:
            self.in_cell = True
            self.current_cell = ""
        elif tag == "tr" and self.in_table:
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.in_table = False
        elif tag in ("td", "th") and self.in_cell:
            self.current_row.append(self.current_cell.strip())
            self.in_cell = False
        elif tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
                self.current_row = []

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

parser = TableParser()
parser.feed(resp.text)

print(f"\n총 {len(parser.rows)}개 행 파싱됨")
for i, row in enumerate(parser.rows[:15]):
    print(f"  [{i}] {row}")
