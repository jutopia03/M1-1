# M1-1 — AI 데이터 분석: 데이터 기반 트렌드 분석

코디세이 미션 M1-1. 국내 일별 박스오피스 시계열(2024-09-01 ~ 2026-08-31, 730일)을
정제·분석하고 인사이트 리포트를 작성한다.

## 결과물

- [`REPORT.md`](REPORT.md) — 분석 리포트 (핵심 산출물)
- `analysis.ipynb` — 분석 코드
- `src/collect_boxoffice.py` — 데이터 수집 스크립트
- `images/` — 리포트에 삽입된 시각화

## 실행 방법

```bash
pip install -r requirements.txt

# 1) API 키 설정
#    .env.example 을 .env 로 복사한 뒤 KOBIS_API_KEY 값을 채운다
#    키 발급: https://www.kobis.or.kr/kobisopenapi/homepg/main/main.do

# 2) 데이터 수집 (약 730회 호출, 중단 시 재실행하면 이어받음)
python src/collect_boxoffice.py

# 3) 분석
jupyter notebook analysis.ipynb   # 셀을 위에서부터 순서대로 실행
```

Python 3.10 이상 필요.

## 데이터

- **출처**: 영화진흥위원회 영화관입장권통합전산망(KOBIS) 오픈API — 일별 박스오피스
- **기간**: 2024-09-01 ~ 2026-08-31 (24개월, 730일)
- **원본 데이터 미포함**: KOBIS 오픈API 이용약관 제6조 2항(결과의 복제·저장 및 재전송 제한)에
  따라 수집한 원본 데이터는 본 저장소에 포함하지 않는다.
  위 실행 방법의 2번 단계로 동일한 데이터를 재현할 수 있다.

---

본 프로젝트는 영화진흥위원회 영화관입장권통합전산망(KOBIS) 오픈API를 이용하였습니다.
