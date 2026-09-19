"""
KOBIS 일별 박스오피스 수집 스크립트
==================================

영화진흥위원회 영화관입장권통합전산망(KOBIS) 오픈API의 '일별 박스오피스'를
하루씩 호출해 TOP10 원본 행을 CSV로 누적 저장한다.

설계 메모
---------
- 원본 행을 그대로 저장한다. 합계/점유율 같은 파생 지표는 분석 단계에서 계산한다.
  (분석 중 다른 지표가 필요해져도 API를 다시 호출하지 않기 위함)
- 이어받기(resume): 이미 수집된 날짜는 건너뛴다. 중단되면 그냥 재실행하면 된다.
- 수집된 CSV는 .gitignore 로 제외된다 (KOBIS 약관 제6조 2항).

사용법
------
    python src/collect_boxoffice.py             # 전체 기간 수집
    python src/collect_boxoffice.py --probe     # 하루치만 호출해 응답 필드 확인
"""

import csv
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# 설정
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_PATH = BASE_DIR / "data" / "raw_daily_boxoffice.csv"

START_DATE = date(2024, 9, 1)
END_DATE = date(2026, 8, 31)      # 24개월 = 730일

API_URL = ("http://www.kobis.or.kr/kobisopenapi/webservice/rest"
           "/boxoffice/searchDailyBoxOfficeList.json")

SLEEP_SEC = 0.3      # 호출 간 지연 (서버 부하 방지)
MAX_RETRY = 3
TIMEOUT = 10

# API 응답에서 보존할 필드. 없는 필드는 빈 값으로 채운다.
FIELDS = [
    "targetDt",        # 기준일 (스크립트가 추가)
    "rank", "rankInten", "rankOldAndNew",
    "movieCd", "movieNm", "openDt",
    "audiCnt", "audiInten", "audiChange", "audiAcc",
    "salesAmt", "salesShare", "salesInten", "salesChange", "salesAcc",
    "scrnCnt", "showCnt",
]


# --------------------------------------------------------------------------
# 유틸
# --------------------------------------------------------------------------
def get_api_key() -> str:
    load_dotenv(BASE_DIR / ".env")
    key = os.getenv("KOBIS_API_KEY", "").strip()
    if not key or key.startswith("여기에"):
        sys.exit(
            "[중단] KOBIS_API_KEY 가 설정되지 않았습니다.\n"
            "       .env.example 을 .env 로 복사한 뒤 발급받은 키를 넣어주세요."
        )
    return key


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def load_done_dates() -> set:
    """이미 수집된 targetDt 집합을 반환 (이어받기용)."""
    if not OUT_PATH.exists():
        return set()
    with OUT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["targetDt"] for row in csv.DictReader(f) if row.get("targetDt")}


def fetch_one_day(key: str, target_dt: str) -> list:
    """하루치 TOP10 행 리스트를 반환. 실패 시 예외."""
    params = {"key": key, "targetDt": target_dt}

    for attempt in range(1, MAX_RETRY + 1):
        try:
            res = requests.get(API_URL, params=params, timeout=TIMEOUT)
            res.raise_for_status()
            payload = res.json()
        except Exception as e:
            if attempt == MAX_RETRY:
                raise RuntimeError(f"{target_dt} 요청 실패: {e}") from e
            time.sleep(2 * attempt)
            continue

        # KOBIS 는 오류도 HTTP 200 + faultInfo 로 돌려준다
        if "faultInfo" in payload:
            msg = payload["faultInfo"].get("message", payload["faultInfo"])
            raise RuntimeError(f"{target_dt} API 오류: {msg}")

        items = (payload.get("boxOfficeResult", {})
                        .get("dailyBoxOfficeList", []))
        rows = []
        for item in items:
            row = {f: item.get(f, "") for f in FIELDS}
            row["targetDt"] = target_dt
            rows.append(row)
        return rows

    return []


# --------------------------------------------------------------------------
# 모드 1: 응답 필드 확인 (--probe)
# --------------------------------------------------------------------------
def probe(key: str) -> None:
    target = START_DATE.strftime("%Y%m%d")
    print(f"[probe] {target} 하루치 호출\n")

    res = requests.get(API_URL, params={"key": key, "targetDt": target},
                       timeout=TIMEOUT)
    payload = res.json()

    if "faultInfo" in payload:
        sys.exit(f"[중단] API 오류: {payload['faultInfo']}")

    items = payload["boxOfficeResult"]["dailyBoxOfficeList"]
    print(f"반환된 행 수: {len(items)}\n")
    print("--- 실제 응답 필드 ---")
    for k, v in items[0].items():
        print(f"  {k:16} = {v}")

    actual = set(items[0].keys())
    missing = [f for f in FIELDS if f != "targetDt" and f not in actual]
    extra = sorted(actual - set(FIELDS))
    print("\n--- 대조 ---")
    print(f"  스크립트가 기대했으나 없는 필드: {missing or '없음'}")
    print(f"  응답에만 있는 필드           : {extra or '없음'}")


# --------------------------------------------------------------------------
# 모드 2: 전체 수집
# --------------------------------------------------------------------------
def collect(key: str) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    done = load_done_dates()
    targets = [d.strftime("%Y%m%d") for d in daterange(START_DATE, END_DATE)]
    todo = [t for t in targets if t not in done]

    print(f"기간      : {START_DATE} ~ {END_DATE} ({len(targets)}일)")
    print(f"수집 완료 : {len(done)}일")
    print(f"남은 작업 : {len(todo)}일\n")

    if not todo:
        print("이미 전부 수집되었습니다.")
        return

    is_new = not OUT_PATH.exists()
    failures = []

    with OUT_PATH.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()

        for i, target in enumerate(todo, 1):
            try:
                rows = fetch_one_day(key, target)
            except RuntimeError as e:
                print(f"  ! {e}")
                failures.append(target)
                if len(failures) >= 10:
                    print("\n[중단] 연속 실패가 많습니다. "
                          "호출 제한에 걸렸을 수 있으니 잠시 후 재실행하세요.")
                    break
                continue

            if not rows:
                print(f"  - {target}: 데이터 없음")
            writer.writerows(rows)

            if i % 50 == 0 or i == len(todo):
                f.flush()
                print(f"  {i}/{len(todo)} ... {target}")

            time.sleep(SLEEP_SEC)

    print(f"\n저장 위치: {OUT_PATH}")
    if failures:
        print(f"실패한 날짜 {len(failures)}건: {failures[:10]}")
        print("스크립트를 다시 실행하면 실패분만 재시도합니다.")


# --------------------------------------------------------------------------
if __name__ == "__main__":
    api_key = get_api_key()
    if "--probe" in sys.argv:
        probe(api_key)
    else:
        collect(api_key)
