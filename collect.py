#!/usr/bin/env python3
"""
KIND 상장예비심사 현황 수집기
매주 목요일 21:00 KST (UTC 12:00)에 GitHub Actions로 자동 실행
수동 실행: python collect.py
"""
import json
import logging
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────────────────────
DATA_FILE = Path(__file__).parent / "data" / "companies.json"
BASE_URL = "https://kind.krx.co.kr/listinvstg/listinvstgcom.do"
KST = timezone(timedelta(hours=9))
LOOKBACK_MONTHS = 14   # 12개월 + 여유분 (장기 미결 건 포함)
EXPIRE_DAYS = 30       # 결과 확정 후 리스트 유지 기간
PAGE_SIZE = 100        # 최대 페이지 크기

# 상장유형 코드 (신규상장, 이전상장만)
LIST_TYPE_CODES = ["01", "02"]
# 심사결과 코드 (전체 — 파이프라인에서 분류)
INVSTG_RSLT_CODES = ["01", "02", "03", "04", "05", "06", "07", "08"]

# KIND 원본값 → (표시명, 색상)
STATUS_MAP: dict[str, tuple[str, str]] = {
    "청구서접수":   ("진행중",             "neutral"),
    "심사승인":     ("심사승인",           "green"),
    "심사미승인":   ("심사미승인",         "red"),
    "심사철회":     ("심사철회",           "yellow"),
    "공모철회":     ("공모철회",           "gray"),
    "상장철회":     ("상장철회",           "gray"),
    "승인효력기간만료": ("승인효력기간만료", "gray"),
    "상장승인":     ("상장승인",           "green"),
}
RESOLVED_STATUSES = frozenset(STATUS_MAP) - {"청구서접수"}


# ── 날짜 헬퍼 ─────────────────────────────────────────────────────────────────
def today_kst() -> date:
    return datetime.now(KST).date()


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


# ── 데이터 로드/저장 ──────────────────────────────────────────────────────────
def load_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"last_updated": None, "companies": [], "archived": []}


def save_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(exist_ok=True)
    data["last_updated"] = datetime.now(KST).isoformat()
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"저장: companies={len(data['companies'])}, archived={len(data['archived'])}")


# ── KIND API 호출 ──────────────────────────────────────────────────────────────
def _build_payload(page_index: int, from_date: str, to_date: str) -> list[tuple]:
    base = [
        ("method", "searchListInvstgCorpSub"),
        ("currentPageSize", str(PAGE_SIZE)),
        ("pageIndex", str(page_index)),
        ("orderMode", "2"),
        ("orderStat", "A"),   # 청구일 오름차순
        ("forward", "listinvstgcom_sub"),
        ("bizProcNo", ""), ("listClssCd", ""), ("comAbbrv", ""),
        ("listTypeArrStr", "|".join(LIST_TYPE_CODES) + "|"),
        ("invstgRsltArrStr", "|".join(INVSTG_RSLT_CODES) + "|"),
        ("seq", "0"), ("searchMode", ""), ("searchCodeType", ""),
        ("searchCorpName", ""), ("isurCd", ""), ("repIsuSrtCd", ""),
        ("marketType", ""), ("searchCorpNameTmp", ""),
        ("fromDate", from_date), ("toDate", to_date),
    ]
    for code in LIST_TYPE_CODES:
        base.append(("listTypeArr", code))
    for code in INVSTG_RSLT_CODES:
        base.append(("invstgRsltArr", code))
    return base


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"{BASE_URL}?method=searchListInvstgCorpMain",
        "Origin": "https://kind.krx.co.kr",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })
    # 세션 쿠키 획득
    session.get(f"{BASE_URL}?method=searchListInvstgCorpMain", timeout=15)
    return session


def scrape_kind() -> list[dict]:
    """KIND 예비심사기업 전체 목록을 가져와 파싱된 행 리스트 반환"""
    today = today_kst()
    from_date = (today - timedelta(days=LOOKBACK_MONTHS * 31)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    log.info(f"KIND 조회: {from_date} ~ {to_date}")
    session = _make_session()
    all_rows: list[dict] = []

    for page in range(1, 50):  # 최대 50페이지(5,000건) 안전 상한
        payload = _build_payload(page, from_date, to_date)
        resp = session.post(BASE_URL, data=payload, timeout=30)
        resp.raise_for_status()
        resp.encoding = "UTF-8"

        rows = _parse_page(resp.text)
        log.info(f"  페이지 {page}: {len(rows)}개 행")
        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE:
            break

    log.info(f"총 {len(all_rows)}개 기업 수집")
    return all_rows


def _parse_page(html: str) -> list[dict]:
    """HTML 응답에서 기업 행 파싱"""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_=lambda c: c and "list" in c)
    if not table:
        log.warning("결과 테이블을 찾지 못했습니다")
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    rows = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        # 시장구분: 첫 번째 td의 <img alt="...">
        img = tds[0].find("img")
        market = img.get("alt", "").strip() if img else ""

        # 회사명: td의 title 속성 (또는 텍스트)
        corp_name = tds[0].get("title", "").strip()
        if not corp_name:
            corp_name = tds[0].get_text(strip=True)

        listing_type = tds[1].get_text(strip=True)
        apply_date   = tds[2].get_text(strip=True)
        result_date  = tds[3].get_text(strip=True) or None
        # "상장 승인" → "상장승인" (공백 제거)
        status_raw   = tds[4].get_text(strip=True).replace(" ", "")

        if not corp_name or not apply_date:
            continue

        rows.append({
            "market": market,
            "corp_name": corp_name,
            "listing_type": listing_type,
            "apply_date": apply_date,
            "result_date_raw": result_date,
            "status_raw": status_raw,
        })

    return rows


# ── 상태 매핑 ──────────────────────────────────────────────────────────────────
def _map_status(status_raw: str) -> tuple[str, str, str]:
    """(status_raw, display, color) 반환"""
    info = STATUS_MAP.get(status_raw)
    if info:
        return status_raw, info[0], info[1]
    log.warning(f"알 수 없는 심사결과: '{status_raw}' — gray 처리")
    return status_raw, status_raw, "gray"


# ── diff / 업데이트 ────────────────────────────────────────────────────────────
def _key(row: dict) -> str:
    """(회사명, 청구일) 복합키"""
    return f"{row['corp_name']}|{row['apply_date']}"


def diff_and_update(stored: dict, fresh_rows: list[dict]) -> dict:
    """기존 데이터와 새 스크래핑 결과를 병합"""
    today = today_kst()
    today_str = today.isoformat()

    # 기존 companies를 복합키로 인덱싱
    existing: dict[str, dict] = {_key(c): c for c in stored["companies"]}
    fresh_index: dict[str, dict] = {_key(r): r for r in fresh_rows}

    updated_companies: list[dict] = []

    # ① 신규 기업 추가
    for key, row in fresh_index.items():
        if key not in existing:
            raw, display, color = _map_status(row["status_raw"])
            is_resolved = raw in RESOLVED_STATUSES
            if is_resolved:
                result_date = row.get("result_date_raw") or today_str
            else:
                result_date = None
            expire_date = (
                iso(date.fromisoformat(result_date) + timedelta(days=EXPIRE_DAYS))
                if result_date else None
            )
            company = {
                "corp_name":    row["corp_name"],
                "market":       row["market"],
                "listing_type": row["listing_type"],
                "apply_date":   row["apply_date"],
                "status_raw":   raw,
                "status_display": display,
                "status_color": color,
                "result_date":  result_date,
                "expire_date":  expire_date,
                "history": [
                    {"date": today_str, "status": raw},
                ],
            }
            log.info(f"[신규] {row['corp_name']} ({raw})")
            updated_companies.append(company)

    # ② 기존 기업 업데이트
    for key, company in existing.items():
        fresh = fresh_index.get(key)

        if fresh:
            new_raw = fresh["status_raw"].replace(" ", "")
            if new_raw != company["status_raw"]:
                # 상태 변경
                _, display, color = _map_status(new_raw)
                company["status_raw"]     = new_raw
                company["status_display"] = display
                company["status_color"]   = color
                company["history"].append({"date": today_str, "status": new_raw})
                log.info(f"[변경] {company['corp_name']}: {company['status_raw']} → {new_raw}")

            # 결과 확정일 기록 (최초 1회) — KIND에 날짜가 없으면 감지일(today) 사용
            if company["status_raw"] in RESOLVED_STATUSES and not company.get("result_date"):
                rd = (fresh.get("result_date_raw") or "") if fresh else ""
                rd = rd or today_str
                company["result_date"] = rd
                company["expire_date"] = iso(
                    date.fromisoformat(rd) + timedelta(days=EXPIRE_DAYS)
                )

            # 시장구분/상장유형 갱신 (최신값 유지)
            company["market"]       = fresh["market"]
            company["listing_type"] = fresh["listing_type"]

        updated_companies.append(company)

    stored["companies"] = updated_companies
    return stored


def expire_companies(data: dict) -> dict:
    """결과 확정 후 30일 초과 기업을 archived로 이동"""
    today = today_kst()
    active, archived = [], list(data.get("archived", []))

    for company in data["companies"]:
        if company.get("expire_date"):
            try:
                if date.fromisoformat(company["expire_date"]) < today:
                    log.info(f"[만료] {company['corp_name']} → archived")
                    archived.append(company)
                    continue
            except ValueError:
                pass
        active.append(company)

    data["companies"] = active
    data["archived"]  = archived
    return data


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("=== KIND 예비심사 수집 시작 ===")

    stored = load_data()
    log.info(f"기존: companies={len(stored['companies'])}, archived={len(stored['archived'])}")

    fresh_rows = scrape_kind()
    if not fresh_rows:
        log.error("스크래핑 결과 없음 — 저장 생략")
        sys.exit(1)

    stored = diff_and_update(stored, fresh_rows)
    stored = expire_companies(stored)
    save_data(stored)

    log.info("=== 수집 완료 ===")


if __name__ == "__main__":
    main()
