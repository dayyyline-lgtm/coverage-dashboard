# 호텔 ADR — 아침 수집 절차 (Google 호텔 선행 판매가 · 2026-10-29 ~)

대시보드 `ADR` 블록(호텔신라 · GS피앤엘 · 서부T&D 종목 페이지 손익 탭 '호텔 ADR 추적')의 **일별** 재료.
리츠 IR 월별·회사 IR 분기·증권사 언급은 손으로 넣는다(아래 '사람이 넣는 것').

## 누가 · 언제

- **아마존 아침 수집 세션**(크롬 도구가 붙은 대화 세션 · `amazon-beauty-tracker/subcat/RUNBOOK.md` '아침 수집 — 이 세션' 8번)이
  아마존(1·2·1-b·3단계)과 6번(Keepa · 주 1회)을 마친 뒤 **같은 윈도우 크롬**에서 한다. 예약 작업으로 새로 뜨는 세션엔 크롬 도구가 없다.
- 하루 한 번. 먼저 `python3 hotel_adr/build.py --today` — 종료코드 0 이면 오늘 관측이 이미 있으니 건너뛴다.
- 13곳 × 숙박일 4개 = 52건 · 5분 안팎. 아마존과 무관하니 여기서 멈추거나 실패해도 아마존 쪽엔 영향이 없다.

## 1. 크롬

1. `tabs_create_mcp` → `navigate` 로 `https://www.google.com/travel/hotels?hl=ko&gl=kr&curr=KRW` (사용자가 열어 둔 탭은 건드리지 않는다).
2. `javascript_tool` 에 그대로:
   ```js
   const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/hotel_adr/';
   const code=await (await fetch(R+'ota.js',{cache:'no-store'})).text();
   const p=trustedTypes.createPolicy('adrota'+Date.now(),{createScript:s=>s});
   const s=document.createElement('script'); s.nonce=[...document.querySelectorAll('script')].find(x=>x.nonce).nonce;
   s.textContent=p.createScript(code); document.head.appendChild(s); window.__HOTELOTA.status()
   ```
   → `run · 0/52 · …` 가 정상. ⚠ google.com 은 `new Function`·`eval` 이 막혀 있고(CSP 에 'unsafe-eval' 없음) Trusted Types 를 강제한다 —
   아마존처럼 `new Function(…)()` 로 부르면 안 돈다. 위처럼 TrustedScript + 페이지 nonce 로 `<script>` 를 붙인다(2026-10-29 확인).
3. 60초 간격으로 `window.__HOTELOTA.status()` — `done · 52/52 · ok N · …` 까지. 15분이 지나도 `run` 이면 멈추고 보고.
   `ok` 가 30 미만이면 구글 화면이 바뀌었거나 막힌 것 — 그래도 받은 만큼 넣고 보고에 적는다.
4. `window.__HOTELOTA.dump()` → `get_page_text` → 본문을 **한 글자도 바꾸지 말고** `/tmp/adr/ota.txt`.
   (머리 줄 Title:·URL: 은 있어도 된다 — `O|`·`END|` 줄만 읽는다)
5. 만든 탭을 닫는다.

## 2. 넣기 · 올리기

```
python3 hotel_adr/build.py --check /tmp/adr/ota.txt     # END 줄 수 일치 → 종료코드 0
python3 hotel_adr/build.py --ota /tmp/adr/ota.txt       # ota.csv 에 더하고 ADR 블록 다시 만들기
python3 hotel_adr/push.py                               # hotel_adr/data · index.html 만 커밋 · 배포 생략 표시(다음 봇 배포가 싣는다)
```

보고 한 줄: build.py 의 `[ADR] OTA … 선행 판매가 …` 줄(실패면 멈춘 곳).

## 수집기가 하는 일 (`ota.js`)

- 호텔 13곳(`HOTELS`)을 Google 호텔에서 찾아(같은 출처 iframe) 호텔 상세 주소의 `ts`(protobuf)에서 체크인·아웃 날짜만 바꿔 다시 연다.
- 숙박일 = 관측일(KST) +14일 뒤 첫 수·토, +45일 뒤 첫 수·토 — `build.py rule_dates` 와 같은 규칙이라야 지수에 들어간다.
- 한 줄 = `O|관측일|호텔키|숙박일|최저가(세금 포함 원)|보통 범위 하단|상단|판정(보통·높음·낮음)|특가 %|대체 날짜:가격|상태(ok·soldout·noprice·noentity·nots·err)`.
- 지수(`build.py ota_block`) = 숙박일 4개 최저가 ÷ 1.1(부가세) 평균(천원) · 평일(수)·주말(토) 따로. 보통 범위 상단의 1.5배 또는
  같은 관측일 다른 숙박일 중앙값의 2배를 넘는 값(일반 객실 매진으로 스위트만 잡힌 날 등)은 지수에서 뺀다(표엔 '이상치').
- 드래곤시티 = 4개 브랜드 객실 수 가중(그랜드 머큐어 202 · 노보텔 스위트 286 · 노보텔 621 · 이비스 스타일 591).
- ⚠ 공개 최저가라 법인·단체 할인이 섞인 실제 ADR 보다 높다(10/29 드래곤시티 31만원 vs 증권사 2Q26 ADR 21만원). **수준이 아니라 추이**를 본다.

## 사람이 넣는 것 (`hotel_adr/data/`)

| 파일 | 언제 | 어디서 |
|---|---|---|
| `reit_monthly.json` | 신한서부티엔디리츠 IR 자료가 새로 나올 때(분기마다 2~3번) | IRGO `m.irgo.co.kr/IR-COMP/404990` → PDF '호텔 자산 실적' 쪽(2026.10 판은 p.8) — 차트 좌표를 pdf.js 로 읽어 축 눈금 기울기 + 이미 있는 2024·2025 값으로 위치를 맞춘다(잔차 ±0.2) · 차트의 2026 숫자 라벨로 검산. 새 달만 `src` 키(예 `r2610`)와 함께 더한다 |
| `ir_quarterly.json` | 분기 실적 IR 이 나올 때 | 호텔신라 IR 경영실적 '호텔&레저' 쪽(사업장별 매출·투숙률) · GS피앤엘 IR 사업장별 매출·OCC · 서부T&D 분기보고서 객실·식음 매출 |
| `broker.json` | 실적 리뷰·프리뷰가 ADR 을 말할 때 | 원문 표현 그대로(레벨은 만원) · `q` 대상 분기 · `d` 리포트 날짜 · 추정이면 `est:true` |
| `market.json` | 가끔 | 한국호텔업협회 연간 · STR 월(기사) — 정의가 달라 표로만 |

넣은 뒤 `python3 hotel_adr/build.py` → `python3 hotel_adr/push.py --deploy`.

- 나인트리 동대문은 리츠가 2026-04 매각 — 리츠 월별은 2026-02 까지로 끝난다(이후 GS피앤엘 쪽 월별은 선행 판매가뿐).
- GS피앤엘 웨스틴은 2025 1~3Q 재개관 공사 — `ir_quarterly.json` 의 `gs.skip` 이 그 분기 기준 전년비를 막는다.
