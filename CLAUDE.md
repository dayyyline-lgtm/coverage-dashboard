# 작업 규칙

신주현(캐리 펀드 리서치)의 커버리지 대시보드. 소비재·유통·미용·음식료·엔터·게임·호텔 29종목.

- 사이트: https://coverage-dashboard.pages.dev (Cloudflare Pages, **공개**)
- 사용자는 개발자가 아님. 터미널 명령을 시키지 말고, **내가 직접 수정하고 push까지 완료**할 것.
- 한국어로 응답.

## 구조

`public/index.html` **단일 파일**이 전부다. 데이터는 JS 상수로 내장:

| 상수 | 내용 | 갱신 스크립트 |
|---|---|---|
| `DATA` | 유니버스(종목·섹터·점수·견적·27E 추정·Pick) | **없음 — 직접 편집** |
| `FIN` | 연간·분기 실적 | **없음 — 직접 편집** |
| `LIVE` | 시세·컨센·리포트·섹터지수·환율 | `refresh_live.py` |
| `DART_EVENTS` | 공시·IR 일정 | `fetch_events.py` |
| `NEWS` | 종목별 뉴스 | `fetch_news.py` |
| `TREND` | 네이버·구글 검색 트렌드 | `fetch_trends.py` |
| `TRADE` / `TRADE_PRELIM` | 화장품 수출입 | `fetch_trade.py` |

각 스크립트는 **해당 블록만 정규식으로 교체**하므로 서로 덮어쓰지 않는다.
데이터 변동이 없으면 파일을 건드리지 않는다(Cloudflare 무료 빌드 500회/월 절약).

### DATA 는 엑셀에서 오지 않는다 (2026-07-26 ~)

엑셀 파이프라인(`rebuild_from_excel.py`)은 폐지했다. **`index.html` 이 원본**이고,
종목 추가·견적 변경 등은 사용자가 말로 지시하면 내가 직접 `DATA` 를 편집한다.

`DATA` 에는 **API로 못 구하는 값만** 둔다:

```
pickLabel · rank · pick2 · sector · sub · name · score · fairMktcap
rev26 · op26        (당사 26E 추정 — rev26own/op26own 로 보존돼 컨센 괴리 계산에 쓰임)
rev27 · op27 · eps27 · epsg27   (27E 당사 추정 — 무료 API에 27E 컨센이 없음)
```

**시세·시총·컨센·PER·수익률·목표주가·상승여력을 `DATA` 에 넣지 말 것.**
전부 `LIVE` 에서 매번 재계산한다. 엑셀 시절 남아 있던 고정값
(`price` `target` `upsideCons` `mktcap` `upsideOwn` `ret1w/1m/3m`
`eps26` `epsg26` `per26` `per12mf` `per27`)은 제거했다.

`upsideOwn`(당사 상승여력)이 대표적 사고 사례다. 엑셀 작성 시점 값이 그대로 박혀 있어
29종목 전부 틀린 숫자를 표시했다(평균 +31.9% vs 실제 +51.5%).
지금은 병합 블록에서 `fairMktcap ÷ (mktcapEok/10) − 1` 로 계산한다.
**단위 주의: `fairMktcap` 은 십억원, `LIVE` 의 `mktcapEok` 은 억원이다.**

`public/` 만 배포된다. 스크립트·README는 루트에 있어 공개되지 않는다.

## 하지 말 것

- **빌드 단계를 도입하지 말 것.** 파일 하나 + push하면 즉시 배포되는 단순함이 이 프로젝트의 핵심.
  React·번들러·프레임워크 제안 금지.
- `secrets_local.py` 를 커밋하지 말 것 (.gitignore로 차단됨). 토큰·키를 채팅에 노출시키지 말 것.
- 원본 엑셀(`*.xlsx`)은 사내 자료라 커밋 금지.
- **레이아웃을 크게 바꾸지 말 것.** 사이드바 개편을 시도했다가 되돌린 이력이 있다.
  구조 변경은 반드시 먼저 물어볼 것. 색·간격 조정은 자유.

## 디자인 토큰

테마는 **Rosé Pine** (다크 = main / 라이트 = dawn). `:root` 와 `:root[data-theme="light"]` 두 블록.

- 색은 **반드시 CSS 변수**로. 배지·태그의 반투명 배경은
  `color-mix(in srgb, var(--토큰) N%, transparent)` — hex 하드코딩 금지.
- **강조색(`--accent`)은 빨강·파랑을 피할 것.** 그 둘은 등락(`--up`/`--down`)에 예약된 색이라,
  파란 강조색을 쓰면 버튼·탭이 "하락"처럼 읽힌다. 현재는 라벤더 `#c4a7e7`.
- 강조색 위 글씨는 `--onacc` (흰색 아님 — 라벤더 위 흰색은 대비 부족).
- 라이트(dawn)는 원본 팔레트보다 보조색을 한 단계 어둡게 잡아 대비 4.5:1을 맞춘 상태.
  이 값들을 원본으로 되돌리면 표의 숫자가 안 읽힌다.
- 한국 관행: **상승 = 빨강, 하락 = 파랑.**

## 엑셀 내보내기

`public/index.html` 하단에 **의존성 없는 순수 JS XLSX 라이터**가 들어 있다.
ZIP(STORE) + CRC32 + inline string + styles.xml 레지스트리를 직접 구성한다.

- 원본 유니버스 엑셀의 Universe 시트 양식을 재현하는 것이 목표. 컬럼 정의는 `C[]` 배열.
- 파일명: `신주현_소비재_커버리지_YYYYMMDD.xlsx`
- 조건부 서식 데이터 막대: EPS증가율(0~200%), 낙폭(파랑, -60~0), 반등(빨강, 0~150).
- x14 확장의 **GUID는 8-4-4-4-12 자리를 지킬 것.** 어기면 엑셀이 "복구가 완료되었습니다" 오류를 낸다.
- 빈 셀도 `<c r=".." s=".."/>` 로 내보내야 테두리가 끊기지 않는다.
- 수정 후에는 브라우저에서 blob을 가로채 ZIP을 풀고 XML 파싱까지 검증할 것. 눈으로만 보지 말 것.

## 자동 갱신

GitHub 자체 cron(`schedule:`)이 이 저장소에서 **한 번도 발화하지 않았다.**
그래서 **Cloudflare Worker의 Cron Trigger**가 GitHub Actions를 대신 호출한다.

- Worker: https://coverage-cron.dayyyline.workers.dev — `?wf=refresh.yml` 로 수동 실행 가능
  (`events.yml`, `trends.yml` 도 동일). 성공 시 `{"ok":true,"status":204}`
- 소스: `cloudflare-worker/worker.js`, 설치 안내: `cloudflare-worker/설정방법.md`
- Cloudflare cron은 요일 숫자(`0-4`)를 거부한다. **`SUN-THU` 같은 이름**으로 써야 통과.
- ⚠ 워크플로가 초록불인데 커밋이 없으면, 커밋 단계의 경로가 `public/index.html` 인지부터 확인.
  (index.html을 public/로 옮긴 뒤 옛 경로를 보고 있어서 계속 "변경 없음" 처리된 이력)

## 작업 절차

```
git pull --rebase        # 봇이 매시간 커밋하므로 필수
# ... 수정 ...
git add -A && git commit -m "..." && git push
```

배포는 1~2분 걸린다. **로컬 프리뷰가 캐시된 옛 버전을 잡는 일이 잦으니**,
검증은 배포 후 실제 사이트에 캐시 무력화 쿼리를 붙여서 할 것.

되돌리기: `git revert <커밋>` 또는 Cloudflare → Deployments → Rollback.
