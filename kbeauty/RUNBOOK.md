# K뷰티 채널 모델 — 수집 절차 (Keepa · FastMoss · 2026-10-20 신설)

왜 이렇게 생겼는지는 루트 `CLAUDE.md` 의 'K뷰티 채널 모델' 절. 여기는 크롬 도구가 붙은 세션(또는 사람)이 따라 하는 순서다.

## 언제

- **주 1회** — 아마존 아침 수집 사슬(05:30 · `amazon-beauty-tracker/subcat/RUNBOOK.md` '아침 수집 — 이 세션' 6번)이 세부 카테고리·7개국을 올린 뒤
  같은 윈도우 크롬에서 돈다. 조건: `python3 kbeauty/ingest.py --due` 가 종료코드 0(마지막 Keepa 회차가 6일 넘게 지남) · 지금이 06:30 KST 전 ·
  05:30 회차(13:20 회차는 건너뛴다 — 사용자가 PC 를 쓰는 시간에 Keepa 탭이 앞으로 나온다).
  첫 회차 2026-10-20(화) → 다음 차례 10/26(월). 하루 빠져도 다음 날 아침 사슬이 이어받는다(`--due` 는 날짜만 본다).
- 주 1회면 충분한 이유: Keepa 는 과거 월 값을 Keepa 서버가 들고 있고(배지 이력 · 36개월 월평균 순위), FastMoss Pro 는 최근 180일 일별을 준다 —
  일주일에 한 번 받아도 빈 달·빈 날이 안 생긴다.
- 신선도 한도 192시간(`watchdog.LIMITS`·`STALE_H`·`FRESH_LIMITS` 의 KBCH) — 8일 넘게 안 돌면 알림.
- 실적 발표 2주 전부터는 손으로 더 돌려도 된다(Keepa 사이트 쪽 한 회차 = 약 1만 상품).

## 모드 — `--due` 가 알려 준다

| 모드 | 언제 | A 줄(브랜드·나라 월별) | 덤프 |
|---|---|---|---|
| `full` | 전체 회차가 84일 넘었거나 · 과제 목록(`keepa_tasks.json`)이 그때와 다를 때(새 브랜드 · 제목 조건) | 36개월 + 최근 30일 | 약 9만 자 · 4덩어리 |
| `recent` | 그 밖 | 최근 2개 완결 월 + 최근 30일만(옛 달은 저장된 값 그대로) | 약 5만 자 · 2~3덩어리 |

T 줄(상위 묶음 13개월)은 두 모드가 같다. 2026-10-21 기준 다음 회차는 `full`(10/20 회차 뒤 vdl 에 제목 조건을 붙여 과제가 바뀌었다).

## 1-c-1. Keepa (keepa.com 탭 · 사용자 Pro 로그인 세션 · API 키 안 씀)

1. 크롬(윈도우 PC)에서 새 탭 → `https://keepa.com/#!finder`. 오른쪽 위에 `PRO`·계정 이름이 보이면 로그인된 것. **로그인돼 있지 않으면 멈춘다** — 대신 로그인하지 않는다.
2. `javascript_tool`: `localStorage.getItem('kbk_v')`
   - `kbeauty/keepa.js` 맨 위 `const V`(지금 7)와 같으면 → `new Function(localStorage.getItem('kbk_code'))()` → `kbk v7 ready · timer worker`.
   - 다르거나 없으면(새 브라우저 · keepa.js 를 고친 뒤) → 클론의 `kbeauty/keepa.js` 를 그대로 읽어
     `const SRC = (function(){ <keepa.js 전체> });` 로 감싸 붙여 넣고 `localStorage.setItem('kbk_code','('+SRC.toString()+')()'); localStorage.setItem('kbk_v','7'); SRC()`.
     ⚠ keepa.com 은 CSP 로 다른 사이트(raw.githubusercontent)를 못 부른다 — 그래서 fetch 하지 않고 붙여 넣는다. 10/20 집 PC 크롬(keepa.com)에 v7 이 저장돼 있다.
3. `window.__KBK.start(<kbeauty/keepa_tasks.json 내용>, {mode:'<--due 의 모드>'})` → `started · 158`.
4. 60초마다 `window.__KBK.status()` — `done · 158/158 · …`(10/20 실측 1,079초 · 과제당 3~13초). **탭을 앞에 둘 것**(뒤로 가면 표가 늦게 찬다).
   - 결과 0개(`n 0`)는 한 번 2.5초 쉬고 더 오래(40회) 기다려 다시 묻는다(v7). 그래도 0 인데 지난 회차엔 있던 큰 브랜드면 끝난 뒤
     `await window.__KBK.rerun('1:medicube,2:missha', 40)`('도메인:브랜드키' 쉼표) — 그 자리만 바꿔 다시 만든다.
     10/20 첫 회차에 영국·프랑스 메디큐브 · 영국 미샤 · 미국 바이오던스가 그렇게 거짓 0 으로 나왔다(표가 늦게 찬 것).
   - `X|` 줄(실패)이 많으면 `window.__KBK.log` 를 본다. 같은 실패를 되풀이해 돌리지 않는다.
5. `window.__KBK.plan()` → `0-120,120-260 · lines … · chars …` → 덩어리마다 `window.__KBK.dump(a,b)` → `get_page_text` →
   본문을 한 글자도 바꾸지 말고 `/tmp/kbk/part_N.txt`. 덤프하면 본문이 바뀌니 끝나면 탭을 닫는다(수집기는 탭 안 메모리에만 있다 — 닫기 전에 1-c-3 의 `--check` 를 통과시킬 것).
   - ⚠ `javascript_tool` 반환값은 1천 자 남짓에서 잘리고, `= & ? ;` 가 섞인 반환은 크롬 도구가 쿼리 문자열로 보고 가린다 — 수집기 반환은 그 글자 없이 짧게 만들어 뒀다. 우회하지 말 것.

## 1-c-2. FastMoss (fastmoss.com 탭 · 사용자 Pro 로그인 세션)

⚠ **로그인된 브라우저에서만.** 10/21 기준 사용자 노트북 크롬(윈도우)에만 로그인돼 있고 사슬이 도는 집 PC 크롬은 아니다 — 거기 로그인되면 매주 같이 돈다.
로그인 여부: `https://www.fastmoss.com/ko/dashboard` 를 열어 로그인 창이 뜨면 이 단계는 건너뛴다(대신 로그인하지 않는다).
⚠ 화면 데이터 API 를 직접 부르지 않는다(10/20 오후 직접 여러 번 부르다 슬라이드 캡차). 샵 상세 페이지를 열고 '최근 180일'을 눌러 화면이 부른 응답만 받는다.
⚠ **구독이 미국만** — 미국 밖 샵 상세는 흐림 처리되고 API 가 다른 지역 견본을 준다(`grab` 이 `locked` 로 버린다). 그 샵들은 2번(스냅샷)으로.
Pro 한도: 상세 500회/일 · 검색 300회/일 · 이력 180일 — 한 회차 = 상세 18 + 검색 5 안팎.

0. 불러오기 — fastmoss.com 은 CSP 가 `eval`·`new Function` 을 막고 인라인 스크립트와 raw.githubusercontent fetch 는 연다:
   ```js
   if(localStorage.getItem('fmx_v')!=='3'){ localStorage.setItem('fmx_code', await (await fetch('https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/kbeauty/fastmoss.js')).text()); localStorage.setItem('fmx_v','3'); }
   const s=document.createElement('script'); s.textContent=localStorage.getItem('fmx_code'); document.head.appendChild(s); window.__FMX.status()
   ```
   → `shops 0 · err 0 · -`(새 회차면 `window.__FMX.reset()` 먼저). 페이지를 옮길 때마다(navigate) 다시 붙인다 — 버퍼는 localStorage(`fmx_buf`)라 남는다.
1. 미국 샵마다(`kbeauty/config.json` 의 `tt` · 18곳): `navigate https://www.fastmoss.com/ko/shop-marketing/detail/<s>` → 4초 → 불러오기 → `await window.__FMX.grab('<s>','<r>','<k>')`
   → `ok … days 180 from … gmv …k`. 샵 사이 5~10초 쉰다(`browser_batch` 로 navigate·wait·javascript_tool 을 묶는다).
   - 캡차(슬라이드)가 뜨면 **풀지 말고 멈춘다** — 사용자가 풀어야 한다. 받은 데까지만 넘긴다.
   - `locked …` = 구독 밖 지역 · `stale …` = 마지막 날이 10일 넘게 지남 · `no response` = 화면이 안 불렀다(한 번 더 navigate).
2. 미국 밖 샵(`tw` · 14곳) 스냅샷: `navigate https://www.fastmoss.com/ko/shop-marketing/search?region=<r>&words=<w>` → 검색 결과가 그려지면 불러오기 →
   `window.__FMX.snapRow('<s>','<r>','<k>')` → `snap … u7 … v7 $… total $…`. 같은 검색 화면에 샵이 여럿이면(영국 메디큐브·달바·코스알엑스…) 그 화면에서 차례로.
   - `no row` = 목록에 없다(검색어 · 지역 확인 · 첫 화면 20개 안에 없으면 브랜드명을 더 좁게).
3. 다 돌면 `window.__FMX.plan()` → `dump(a,b)` → `get_page_text` → `/tmp/kfm/part_N.txt`. 끝나면 `window.__FMX.reset()`(버퍼 비우기).
4. 새 샵 찾기: 검색 화면 → `await window.__FMX.find()`(훅을 건 뒤 검색 버튼을 누른 경우) 또는 `window.__FMX.findDom()`(이미 그려진 목록) →
   운영사가 회사 법인이거나 '브랜드' 표시가 붙은 공식 샵만 `config.json` `tt`(미국) 또는 `tw`(그 밖 · `w` = 검색어)에 한 줄(맨 뒤에).

ingest 가 하는 일(손댈 것 없음): 받은 날(FH 날짜)과 그 뒤는 버린다(미국 시각으로 진행 중) · `w0` = 받은 날 − 179일을 샵마다 기록 ·
블록을 만들 때 판매량은 평소인데 단가가 2.5배 넘게 뛴 날을 직전 28일 중앙 단가 × 판매량으로 바꾼다(7/21~27 · 10/13~19 메디큐브·바이오던스 미국).

## 1-c-3. 저장 → 올리기

```
python3 kbeauty/ingest.py --check /tmp/kbk/*.txt [/tmp/kfm/*.txt]    # CRC · END 확인
python3 kbeauty/ingest.py         /tmp/kbk/*.txt [/tmp/kfm/*.txt]    # data/ 저장 + KBCH 블록
python3 kbeauty/push.py                                              # 배포 생략 표시(봇의 다음 배포가 싣는다)
```
- CRC 가 틀린 줄이 있으면 ingest 가 `redo('A|1|medicube|,…')` 를 알려 준다 → 브라우저에서 `window.__KBK.redo(…)` → get_page_text → `/tmp/kbk/fix_1.txt` → 같이 다시 `--check`.
  (10/20: 9만 자 중 한 줄 — 제품명의 'Real' 한 단어를 빠뜨렸다.)
- `[KEEPA] END 불일치` = 덩어리가 빠졌거나 순서가 틀렸다 → plan() 의 덩어리를 다시 확인.
- 환율(`data/fx_month.csv`)은 러너가 매일 아침(events.yml · `kbeauty/fx.py` · ECB 월평균)에 갱신하고 블록을 다시 만든다 — 크롬 세션은 손대지 않는다.
- 보고 한 줄: `[KEEPA] 저장 … · 실패 …` + `[KBCH] …` + 거짓 0 을 rerun 했으면 그 목록.

## 사람이 고칠 것

| 일 | 어디 |
|---|---|
| 새 브랜드 | `config.json` `brands` 맨 뒤에 `{"k":키,"co":회사,"ko":한글,"kp":[Keepa 브랜드 문자열…],"d":"all"/"few"/[도메인],"tf":제목 조건(선택)}` → `python3 kbeauty/ingest.py --tasks` (과제가 바뀌어 다음 회차가 저절로 full) |
| Keepa 브랜드 문자열 | Product Finder 의 Brand 칸에 앞글자를 넣으면 '(상품 수)'와 함께 뜬다. d'Alba = `d'alba piedmont` + `d'alba` 처럼 둘 이상일 수 있다 |
| 이름이 겹치는 브랜드 | `tf`(제목 정규식 · 대소문자 무시) — 미국 'VDL' 은 전기자전거라 vdl 에 화장품 단어 조건을 붙였다. ts 는 샴푸 단어 |
| 새 회사·지역 | `config.json` `companies` — 지역 이름은 `ir.json` 의 공시 줄 이름과 같아야 계수가 붙는다 |
| 공시 지역 매출 | `ir.json` — 분기 실적이 나오면 한 칸(출처 URL 같이). 반기만 나오면 '1H26', 연간이면 'FY25' 키 |
| 틱톡샵 샵 | `config.json` `tt` |
