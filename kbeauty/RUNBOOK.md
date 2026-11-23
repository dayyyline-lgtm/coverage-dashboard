# K뷰티 채널 모델 — 수집 절차 (Keepa · FastMoss · 2026-10-20 신설)

왜 이렇게 생겼는지는 루트 `CLAUDE.md` 의 'K뷰티 채널 모델' 절. 여기는 크롬 도구가 붙은 세션(또는 사람)이 따라 하는 순서다.

## Keepa 를 쓰는 곳은 일요일 한 회차뿐이다 (2026-11-03 · 사용자 "필요 없는 예약 작업을 없애고 한 번에 통합해서 사용량 관리")

Keepa 데이터 한도(Pro 웹)는 꽉 차면 약 2.6만 상품 · 1% ≈ 260개 · 시간당 5%쯤 다시 찬다(비우면 약 20시간 · 11/02 실측: 10% 남은 채 미국 2,600개에서 0%).
한도 표시(`#widget__bucket_quota` 'Quota: N%')는 **남은 양**이고 **새 탭에서만** 맞다.

| 무엇 | 언제 | Keepa |
|---|---|---|
| 일요일 통합 회차(아래 1-g) — 국면(KBPH 미국·유럽·일본·캐나다) + 회사 채널(KBCH) + 지누스(ISMKP · 28일마다) | PC 예약 작업 `kbph-weekly` 일 06:50 · 빠지면 월·화 | **유일하게 쓴다** |
| 월·화 이어받기 — 일요일에 한도가 모자라 건너뛴·끊긴 나라만 | 같은 작업 월·화 06:50 · `python kbeauty/week_recv.py --todo` 가 0 일 때 | 빠진 나라 몫만 |
| 토요일 로그인 점검 | 같은 작업 토 06:50 | 페이지만 연다(한도 거의 안 씀) |
| 월~수 회사 채널 회차(옛 1-f) · 클라우드 아침 사슬의 Keepa(옛 1-c-1) · 지누스 따로 받기 | — | **없앴다** |

- 다른 세션(클라우드 대화 포함)은 Keepa Finder 를 돌리지 않는다 — 한도를 반쯤 쓰면 일요일 회차가 중간에 끊긴다(11/01 국면 + 11/02 시험이 그랬다).
  꼭 손으로 돌려야 하면 일요일 회차 20시간 전까지 끝낼 것.
- **한도 예산(keepa_week.js v2 · 2026-11-03)**: 새 탭에서 본 남은 %를 `__KW.start(tasks, {quota: N})` 에 넘기면, 나라마다 예상 상품 수를 남은 예산과 견줘 **모자란 나라는 시작 전에 건너뛴다**
  (중간에 끊겨 반쪽이 되느니 통째로 미룬다). 나라 순서 = 미국 → 영국 → 독일 → 일본 → 프랑스 → 스페인 → 이탈리아 → 캐나다 — 모자라면 뒤에서부터 빠진다.
  질의가 0개거나 페이지가 덜 차면 그 나라는 '불완전'으로 빼고(지난 회차 값이 남는다 · KBCH 최근 30일·상위 묶음은 직전 값을 잇는다), 두 질의 연속 0개면 한도 소진으로 보고 멈춘다.
- 건너뛰거나 불완전한 나라는 **월·화 회차가 그 나라만** 받는다 — `python kbeauty/week_recv.py --todo` 가 `doms 2,3` 처럼 찍으면 `__KW.start(tasks, {quota: N, doms:[2,3]})`.
  국면 유럽·일본·캐나다는 나라마다 가장 최근 덤프를 쓰므로(phase.py build_mk) 나눠 받아도 합쳐진다.
- 회차마다 나라별 받은 행·초가 `data/keepa_usage.csv` 에 쌓인다(bundle 의 @@USE@@) — 다음 회차 예상치는 이걸로 `{exp: {1: …}}` 를 넘겨 맞춘다.

## 언제

> 2026-10-30 부터 Keepa(KBCH)는 **이 PC 예약 작업**이 한다 — 아래 '1-f'. 클라우드 아침 사슬은 Keepa 를 건너뛴다. 아래 '언제'는 옛 경로 기록이다.

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

## 1-c-2'. 틱톡샵은 EchoTik 으로 (2026-11-23~ · FastMoss 구독 끝 → EchoTik Pro · 아래 1-c-2 는 옛 경로)

사용자: "FastMoss 너무 비싸서 EchoTik 으로" → Pro 결제(샵 상세 하루 500 · 90일 · 전 지역 · Basic 은 '샵 판매 분석 불가'라 안 된다).
1. 크롬 새 탭 `https://echotik.live/board`(사용자 탭은 건드리지 않는다) → javascript_tool 로 불러오기:
   ```js
   const s=document.createElement('script'); s.textContent=await (await fetch('https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/kbeauty/echotik.js?'+Date.now())).text(); document.head.appendChild(s); __ET.reset(); __ET.status()
   ```
   → `shops 0 · err 0 · - · login yes`. **login no 면 로그인하지 말고 멈춘다**(사용자가 평소 크롬에서 로그인해 둬야 한다 · 토요일 점검이 미리 알린다).
   버퍼는 sessionStorage(`__ET`)라 같은 탭 안에선 남는다 — 페이지를 옮기면 다시 붙인다.
2. `python kbeauty/echotik_recv.py --ids` 가 찍는 샵 ID 줄(`fm_shops.csv` 전부 · 틱톡 판매자 ID = FastMoss 와 같다)을 그대로 → `await __ET.run('<그 줄>')`.
   샵당 요청 4건 · 약 15초 · 41곳 10분(javascript_tool 이 그보다 먼저 끝나면 `__ET.status()` 로 shops 가 다 찰 때까지 본다 · 탭을 앞에 둔다).
   끝나면 `ERR` 가 있는 샵만 다시 `__ET.run('<그 샵>')`(이미 받은 샵은 건너뛴다).
   API = `/api/v1/data/sellers/<ID>/analysis?tag=basic.sales.trending&dateRange=90`(+ `&indicator=total_sale_gmv_amt&start_time=&end_time=` 판매액) ·
   `tag=basic.video.trending`(새 영상·라이브) · `tag=basic.influencer.trending`(크리에이터 누적 → 하루 차이). 토큰 = localStorage 'token'(Bearer). dateRange 180 은 Pro 도 막힌다.
3. 덤프를 파일로: **이 PC 예약 작업**이면 받기 서버로 `__send('et_'+오늘, __ET.text())`(1-e 4번 함수) → `python kbeauty/phase_recv.py hash .claude/recv/et_<오늘>.txt` 의 len·h 확인.
   echotik.live 가 폼 전송을 막으면 Blob 으로 내려받기 폴더에 받는다. **클라우드 세션**이면 Blob 내려받기 → `device_stage_files` · 그것도 안 되면 `__ET.plan()`·`__ET.dump(a,b)` → get_page_text.
4. `python3 kbeauty/echotik_recv.py <파일>` — 줄 CRC·END 검산 → `data/phase/et/<날짜>.txt` 원문 → 샵마다 **FastMoss 마지막 날 다음부터** EchoTik × 이어 붙이기 배수를
   FastMoss 형식(`FH|E1|…`)으로 `data/phase/fm/<날짜>.txt` 에 쓴다. 배수 = 이어 붙이는 자리 앞 4주 FastMoss 합 ÷ EchoTik 합(판매량·판매액·영상·크리에이터 따로) ·
   처음 한 번 정해 `data/phase/et_k.json` 에 둔다(**지우지 말 것** — 다음 주부터 같은 배수).
5. `python3 kbeauty/ingest.py kbeauty/data/phase/fm/<날짜>.txt`(KBCH) → `python3 kbeauty/phase.py`(KBPH) → 커밋·push(국면 원재료 push 가 브리핑을 깨운다 ·
   같은 asOf 라도 틱톡샵이 일주일 넘게 늘면 '수정본'). 예약 작업에선 1-e 8번의 push.py 가 이 파일들까지 싣는다.
   ⚠ 받는 쪽은 샵마다 '이미 들어 있는 마지막 날'(국면 덤프 + KBCH fm_daily) 다음 날부터만 쓴다 — 같은 날을 두 번 넣지 않는다.
   EchoTik 은 90일만 주므로 **2주 넘게 건너뛰지 말 것**(빈 날은 못 메운다 · 90일 안이면 다음 회차가 저절로 메운다).

11/23 첫 회차 비교(겹친 8/25~11/13 · `echotik_recv.py --compare`): 판매량 합은 거의 같다(샵 대부분 FastMoss ÷ EchoTik 0.96~1.06 · 주별 합계 0.98~1.08 ·
날짜 어긋남 없음) · **판매액은 EchoTik 이 1.2~3배**(단가가 FastMoss 보다 높고 출렁인다 — 할인 전 가격으로 보인다. 메디큐브 FM $30 vs ET $96) → 배수로 FastMoss 수준에 맞춘다 ·
새 영상 0.9~1.2배 · 새 크리에이터는 EchoTik 누적 차이가 FastMoss 의 1/2~1/10(정의가 다르다 — 배수로 맞춘다).
haruharu·isntree 는 양쪽 다 0, MEDICUBE USA(KBCH 쪽 샵)는 FastMoss 자료가 없어 배수 1.

## 1-c-2. FastMoss (옛 경로 · 2026-11-23 까지) (fastmoss.com 탭 · 사용자 Pro 로그인 세션)

⚠ **로그인된 브라우저에서만.** 10/21 기준 사용자 노트북 크롬(윈도우)에만 로그인돼 있고 사슬이 도는 집 PC 크롬은 아니다 — 거기 로그인되면 매주 같이 돈다.
로그인 여부: `https://www.fastmoss.com/ko/dashboard` 를 열어 로그인 창이 뜨면 이 단계는 건너뛴다(대신 로그인하지 않는다).
⚠ 화면 데이터 API 를 직접 부르지 않는다(10/20 오후 직접 여러 번 부르다 슬라이드 캡차). 샵 상세 페이지를 열고 '최근 180일'을 눌러 화면이 부른 응답만 받는다.
⚠ **구독이 미국만** — 미국 밖 샵 상세는 흐림 처리되고 API 가 다른 지역 견본을 준다(`grab` 이 `locked` 로 버린다). 그 샵들은 2번(스냅샷)으로.
Pro 한도: 상세 500회/일 · 검색 300회/일 · 이력 180일 — 한 회차 = 상세 18 + 검색 5 안팎.

0. 불러오기 — fastmoss.com 은 CSP 가 `eval`·`new Function` 을 막고 인라인 스크립트와 raw.githubusercontent fetch 는 연다:
   ```js
   if(localStorage.getItem('fmx_v')!=='4'){ localStorage.setItem('fmx_code', await (await fetch('https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/kbeauty/fastmoss.js')).text()); localStorage.setItem('fmx_v','4'); }
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

## 1-d. 국면 지도 주간 회차 (KBPH · 일요일 · 2026-10-22 · 10-24 월→일)

> 2026-10-27 부터 이 회차는 **이 PC 예약 작업**이 한다 — 아래 1-e. 클라우드 아침 사슬은 국면을 건너뛴다. 이 절은 수집 단계의 원본으로 남긴다.

사용자: "주간으로 업데이트 + 텔레 브리핑". 차례 판정 = `python3 kbeauty/phase_brief.py --due`(이번 주 일요일 KST 뒤 `data/phase/<날짜>.json` 이 없으면 0).
매일 받지 않는 이유: Keepa 판매량이 '지난 30일 구매' 배지라 한 달 단위이고 판정(3개월·1개월)은 완결 달이 늘 때만 바뀐다 · FastMoss 는 180일을 한 번에 준다.

1. **Keepa 미국** — keepa.com 탭(도메인 미국 · `button.knav-mk[data-domain="1"]`) → `kbeauty/phase_keepa.js` 를 붙여 넣는다(맨 위 주석대로) →
   `location.hash='#!finder/'+encodeURIComponent(JSON.stringify(KBPH_QUERY))` → 표가 차면 `KBPH.run()` → `KBPH.status()` done → hash 를 `KBPH_QUERY_NB` 로 바꿔 표가 차면 `KBPH.runNB()`(세트·번들 · 2026-10-23) → done → `KBPH.dump()` → get_page_text →
   `kbeauty/data/phase/<오늘>.json`(ko·co·sup 는 직전 파일에서 옮긴다 — 화면이 쓰는 한글 이름·상장사 · 2026-10-24 부터 덤프에 `r30t`·브랜드별 `r30`(최근 30일 창)이, 2026-10-27 부터 `rws`·브랜드별 `rw`(3달·1달 창 재료 · 기준점 7 × 9칸)가 같이 온다 — 그대로 둘 것).
   덤프 옮기기: 이 PC 미리보기 서버(`.claude/devserver.py` 8766)가 떠 있으면 keepa.com 탭에서 폼 POST(`http://127.0.0.1:8766/recv`, 필드 name·d) → `.claude/recv/<name>.txt` 로 그대로 받는다(옮겨 적기 없음 · 길이·검산값 확인).
2. **유럽 5개국 · 일본 · 캐나다** — 같은 탭에서 `kbeauty/phase_keepa_eu.js`(맨 위 주석대로 · 나라 버튼 2·3·4·8·9 → `<오늘>.txt` · 일본 5·캐나다 6 → `<오늘>-jpca.txt`, 일본은 가타카나 표기 쿼리).
   시간이 모자라면 미국만 올리고 나머지는 지난 회차 값이 남는다(`phase.py` 는 eu 폴더의 마지막 날짜 파일을 쓴다 — 그날 `.txt`·`-jpca.txt` 둘 다 있어야 일곱 나라가 다 산다).
   일본 브랜드 목록(Product Finder 정확히 일치 · 자동완성으로 찾은 표기 · 2026-10-22): `アトパーム(atopalm)` `センテリアン24` `クリオ(clio)` `コースアールエックス(cosrx)`
   `イニスフリー(innisfree)` `ラネージュ(laneige)` `ミシャ(missha)` `雪花秀 ソルファス(sulwhasoo)` + 라틴 abib · anua · axis-y · beauty of joseon · biodance · celimax · centellian 24 · clio ·
   clio professional · d'alba piedmont · d'alba · dr.althea · goodal · haruharu · innisfree · isntree · laneige · ma:nyo · medi-peel · medicube · mixsoon · numbuzin · peripera · real barrier ·
   rejuran · rom&nd · round lab · skin1004 · some by mi · sulwhasoo · tonymoly · torriden · vt cosmetics · zeroid. ⚠ `belif`(일본엔 'belif believe in truth'만)·`dalba`·`クリオ` 단독은 넣지 말 것.
   덤프가 5만 자를 넘으면 get_page_text 가 잘린다 — 유럽 다섯 나라 · 일본+캐나다 두 번으로 나눠 띄운다(2026-10-27 부터 브랜드 줄 여섯째 칸 rw 63개가 붙어 나라당 약 1.7배 — 나라 두셋씩 나누거나 위 폼 POST 로).
   나라 바꾸기는 새로 고침이 필요 없다(2026-10-27) — 나라 버튼을 누르고 `location.hash='#!finder'` → 다시 쿼리 해시를 넣으면 표가 그 나라로 다시 차고 수집기(KBPH)가 살아 있다 → `KBPH.rows={}; KBPH.done=false; KBPH.run()`.
3. **FastMoss 미국 공식 샵** — 로그인돼 있을 때만(1-c-2 의 '로그인 여부'). `python3 kbeauty/phase.py --shops` 가 돌 샵(30곳)과 grab 호출을 찍는다.
   `__FMX.reset()` → 샵마다 상세 navigate → 4초 → 불러오기 → grab(5~10초 간격) → `plan()`·`dump(a,b)` → get_page_text → `kbeauty/data/phase/fm/<오늘>.txt`(줄마다 CRC · END 확인).
   ⚠ 캡차가 뜨면 풀지 말고 멈춘다 — 받은 데까지만. 로그인 안 돼 있으면 건너뛴다(틱톡샵 칸은 지난 덤프 값으로 남는다).
4. `python3 kbeauty/phase.py` → `[KBPH] 갱신 …` 확인 → `python3 kbeauty/phase_brief.py`(미리보기 — 숫자가 이상하면 올리지 말고 멈춘다) → `python3 kbeauty/push.py --phase`.
5. 올라가면 `phase_brief.yml` 이 텔레그램을 보낸다. 같은 asOf 는 한 번만(`data/phase/brief_state.json` — 지난번 칸과 견줘 '칸 바뀜'을 낸다 · 지우지 말 것).

## 통합 수집기 v3 고친 것 (2026-11-09 · 이 PC 크롬에서 손으로 돌리다 발견)

- **Finder 브랜드 필터는 앞 50개 표기만 먹는다.** v2 는 79개를 한 질의에 넣어 뒤쪽 29개(아누아·조선미녀·스킨1004·토리든 등 비상장 경쟁 브랜드 + 토니모리·롬앤·마녀공장…)가
  통째로 빠졌다 — 미국 국면 브랜드 45 → 26, 유럽·캐나다도 절반. 그대로 올렸으면 'K뷰티 내 비중'의 분모가 바뀌어 지도 전체가 틀어진다. v3 = 50개씩 나눠 묶음마다 A·B.
- **바로 앞 질의 표를 새 결과로 읽던 경쟁 조건.** 이탈리아 B 가 직전 A 의 301줄을 그대로 읽었다(정상 1,007). v3 = 표 서명(줄 수·첫 asin·쪽 수)이 바뀔 때까지(최대 12초) 기다린다.
  v2 의 첫 실회차가 성공했어도 B 가 가끔 비었을 것이다.
- v3 시험(11/09 · 이탈리아만): A 301+282 · B 1,007+1,086 → 국면 브랜드 31(11/01 30) · 상품 2,098. **전 나라 회차·첫 회차 비교(1-g 6번)는 아직** — 11/09 의 잘린 회차는 버렸다.
- **이 PC(윈도 dayline) 크롬에서 붙여 넣는 법**: keepa.com 은 열리고 몇 초 뒤 meta CSP 를 걸어 그 뒤엔 eval 이 막힌다. 스크립트를 127.0.0.1 받기 서버의 팝업(postMessage)으로
  탭에 넘겨 keepa.com 의 sessionStorage 에 넣어 두고 → 같은 탭을 keepa.com 으로 다시 navigate 한 **바로 다음 호출**에서 `(0,eval)(sessionStorage.getItem(…))` 로 올린다.

## 통합 수집기 v4 — 쪽 기다림 20초 → 90초 (2026-11-15)

- 11/10·11/15 두 주 연속 유럽(영·프)·캐나다가 '불완전'이거나 예산에 밀려 빠졌다. 원인: 한도를 많이 쓴 뒤엔 Keepa 가 결과 쪽을 30~60초에 채우는데(화면은 빙글빙글),
  v3 는 쪽마다 20초만 기다리고 넘어가 그 쪽 상품이 통째로 빠졌다(short) → 나라 전체를 '불완전'으로 버렸다. 11/15 저녁 같은 나라를 90초 기다림으로 다시 돌리니 short 0.
- 그래서 미·영·독·일(약 2.3만 행 · 한도 약 90%)을 일요일에 받으면 프·스·이·캐는 늘 월·화 이어받기에 기댄다. 이어받기가 안 돌면 그 나라 국면이 몇 주씩 묵는다 —
  `python kbeauty/week_recv.py --todo` 를 확인할 것. 묶음 로그에 `short a/b`(빈 쪽 수)가 찍힌다.

## 1-e. 국면 주간 회차를 이 PC 예약 작업으로 (2026-10-27~ · 1-d 를 대신한다)

> 2026-11-01 부터 Keepa 단계(아래 5·6번)는 **1-g 통합 수집**이 한다(회사 채널까지 한 번에). 1~4번(준비)·7번(틱톡샵 · 2026-11-23 부터 EchoTik)·8번(올리기)은 그대로.

사용자: "일요일 국면 수집을 이 PC 예약 작업으로 옮겨 줘 — 오늘처럼 로컬로 덤프 받는 방식으로". 클라우드 아침 사슬(05:30)은 10/26·10/27 아침
덤프를 파일로 옮겨 적다가 안전 필터 오탐으로 세션이 멈췄다(수집은 끝났는데 못 올림). 국면 덤프는 더 크다(미국 6.5만 자 · 유럽·일본·캐나다 11만 자).
그래서 **이 PC 의 Claude 데스크톱 앱 예약 작업 `kbph-weekly`('K뷰티 Keepa 주간 수집' · 2026-10-30 부터 토·일·월·화·수 06:50 · 차례는 `--due` 가 가린다 · 회사 채널·토요일 점검은 1-f)** 가 하고, 덤프는 옮겨 적지 않고 받기 서버로 받는다.
권한 모드 = 자동(사용자가 2026-10-29 앱의 작업 편집에서 '수동' → '자동' — 수동이면 첫 명령에서 승인을 기다리며 멈춘다 · 10/29 시험이 그랬다).

- 앱이 켜져 있어야 돈다(꺼져 있으면 다음에 켤 때). 06:50 = PC 트래커 재시도 작업(06:45)이 PC 를 깨운 직후 · 클라우드 사슬(05:30)·K뷰티 채널 Keepa(06:30 전 시작)와 크롬이 겹치지 않게.
- 작업 폴더 `C:\Users\user\Desktop\asd` · 파이썬은 `python`(이 PC 엔 python3 가 없다).

1. **멈출 조건부터** — `git status --porcelain` 에 `.claude/` 밖 변경이 있으면 아무것도 하지 않고 보고한다(사람이 작업 중일 수 있다 · push.py 가 index.html 을 통째로 커밋한다).
   깨끗하면 `git pull -q --ff-only` → `python kbeauty/phase_brief.py --due` 가 1 이면 '이번 주 이미 받음' 한 줄로 끝.
2. **받기 서버** — `http://127.0.0.1:8766/` 이 200 이 아니면 띄운다: 미리보기 도구가 있으면 `preview_start {name:"nocache"}`, 없으면 Bash 백그라운드 `python .claude/devserver.py 8766`.
   서버는 `public/` 을 보여 주고 `POST /recv`(필드 name·d)를 `.claude/recv/<name>.txt` 에 쓴다(127.0.0.1 만 · `.claude/` 는 커밋 안 됨).
3. **크롬** — Claude in Chrome 도구를 ToolSearch 한 번으로 → `list_connected_browsers` 에서 Windows(이 PC · isLocal 이면 그것)를 `select_browser`. 없으면 4분마다 다시, 최대 40분.
   새 탭에서 keepa.com 을 연다(사용자 탭은 건드리지 않는다). 오른쪽 위 마켓이 미국(.com)인지 · **데이터 한도(Quota)는 새 탭에서 본다**(열어 둔 탭 표시는 안 바뀐다) — 40% 밑이면 미국만.
4. **보내기 함수** — 덤프를 띄운 탭에서 javascript_tool 로:
   ```js
   window.__send=(name,t)=>{let h=0;for(let i=0;i<t.length;i++)h=(h*31+t.charCodeAt(i))%1000000007;const f=document.createElement('form');f.method='POST';f.action='http://127.0.0.1:8766/recv';const a=document.createElement('textarea');a.name='d';a.value=t;const b=document.createElement('input');b.name='name';b.value=name;f.append(a,b);document.body.appendChild(f);setTimeout(()=>f.submit(),300);return 'len '+t.length+' h '+h;};
   ```
   보내면 탭이 받기 서버 화면('saved …')으로 넘어간다 — 다음 단계는 그 탭에서 keepa.com 으로 다시 navigate(수집기는 다시 붙여 넣는다 · sessionStorage 는 남는다).
   받은 뒤 `python kbeauty/phase_recv.py hash .claude/recv/<name>.txt` 의 len·h 가 페이지가 돌려준 값과 같아야 한다(다르면 다시 보낸다).
5. **미국** — 1-d 의 1번(`phase_keepa.js` 붙여 넣기 → run → runNB → `KBPH.dump()`) → `__send('kbph_us_'+오늘, document.getElementById('__dump').textContent)` →
   `python kbeauty/phase_recv.py us .claude/recv/kbph_us_<오늘>.txt --sku <runNB 전 KBPH.status() 의 n>`(ko·co·sup·src 를 직전 파일에서 옮겨 `data/phase/<asOf>.json`).
6. **유럽 5개국 · 일본 · 캐나다** — 1-d 의 2번. 나라마다 `KBPH.save(m)` 으로 sessionStorage `kbeu_<m>` 에 모은 뒤 한 번에:
   `__send('kbph_eu_'+오늘, ['uk','de','fr','it','es'].map(m=>sessionStorage.getItem('kbeu_'+m)).join('\n')+'\n@@JPCA@@\n'+['jp','ca'].map(m=>sessionStorage.getItem('kbeu_'+m)).join('\n'))`
   (빠진 나라가 있으면 보내지 않는다 — 지난 회차 값이 남는다) → `python kbeauty/phase_recv.py eu .claude/recv/kbph_eu_<오늘>.txt`.
7. **틱톡샵 = EchoTik**(2026-11-23~ · FastMoss 구독 끝) — 1-c-2' 1~3번(로그인돼 있을 때만) → `python kbeauty/echotik_recv.py .claude/recv/et_<오늘>.txt`
   (FastMoss 형식 덤프를 `data/phase/fm/<오늘>.txt` 에 쓴다) → `python kbeauty/ingest.py kbeauty/data/phase/fm/<오늘>.txt`(KBCH 틱톡 칸).
   로그인이 풀려 있으면 이 단계만 건너뛰고 아마존은 그대로 올린다(틱톡샵·합산은 지난 값 · 보고와 알림에 적는다).
8. `python kbeauty/phase.py` → `python kbeauty/phase_brief.py`(미리보기 — 숫자가 이상하면 올리지 말고 멈춘다) → `python kbeauty/push.py --phase` → 만든 탭을 닫는다.
   올라가면 `phase_brief.yml` 이 텔레그램 '💄 K뷰티 국면 주간'을 보낸다(사용자가 정한 주간 브리핑 · 같은 asOf 는 한 번만).
9. 보고(2~3줄): `[KBPH]` 줄 · 받은 나라 · EchoTik 받았나(샵 수 · 끝날) · push.py 의 배포 줄 · 멈췄으면 어디서 왜.

## 1-f. 회사 채널(KBCH) 주간 회차 · 토요일 로그인 점검 · 멈춤 알림 — 이 PC 예약 작업 (2026-10-30~)

> 2026-11-01 부터 회사 채널은 따로 돌지 않는다 — 일요일 **1-g 통합 수집**이 같이 만든다(월·화·수 회사 채널 회차 없음). 토요일 점검·알림은 그대로.

사용자: "Keepa 는 구글 아이디로 로그인하는 거라 클로드 크롬 예약 작업으로 돌리는 게 맞다"(전용 크롬 프로필 독립 프로그램을 만들었다가 걷었다 — 구글 로그인은
프로그램이 띄운 크롬에서 막히는 일이 많고, 평소 크롬의 구글 세션을 그대로 쓰는 게 가장 오래 간다). 클라우드 사슬의 Keepa(1-c-1)는 10/26 회차가 안전 필터 오탐으로 끊겨
KBCH 가 10/20 뒤로 멈췄다 → 국면과 같은 예약 작업 `kbph-weekly` 로 옮겼다. 하루에 Keepa 하나만(국면 > 회사 채널) — 같은 날 둘 다 돌리면 데이터 한도가 바닥난다.

| 요일(KST 06:50) | 하는 일 |
|---|---|
| 토 | 로그인 점검만(아래) |
| 일 | 국면(1-e) — 빠지면 월·화가 이어받는다 |
| 월·화·수 | 국면이 차례가 아니고 `python kbeauty/ingest.py --due` 가 0 이면 회사 채널(아래) — 한도 50% 밑이면 다음 날로 |

**회사 채널 단계** (1-e 의 2~4단계 — 받기 서버·크롬·보내기 함수 — 를 먼저 한다)
1. keepa.com 새 탭(`https://keepa.com/#!finder`) — 오른쪽 위 계정 이름(`.knav-btn--user .knav-btn__name`)이 보이면 로그인된 것. 로그인 화면이면 **로그인하지 말고** 멈추고 알린다.
   데이터 한도 = 새 탭의 `#widget__bucket_quota`('Quota: N%').
2. `kbeauty/keepa.js` 를 그대로 붙여 넣는다(javascript_tool · keepa.com CSP 가 외부 fetch 를 막는다 · 1-c-1 의 2번) → `kbk v8 ready`.
3. `window.__KBK.start(<kbeauty/keepa_tasks.json 내용>, {mode:'<--due 의 모드>'})` → 60초마다 `window.__KBK.status()` 가 `done · …` 까지(230과제 · 20~40분 · 탭을 앞에).
   거짓 0(큰 브랜드가 0)은 1-c-1 의 4번대로 `rerun`.
4. `__send('kbk_'+오늘, window.__KBK.L.join('
'))` → `python kbeauty/phase_recv.py hash .claude/recv/kbk_<오늘>.txt` 의 len·h 가 같은지 →
   `python kbeauty/ingest.py --check .claude/recv/kbk_<오늘>.txt` → `python kbeauty/ingest.py .claude/recv/kbk_<오늘>.txt` → `python kbeauty/push.py`(배포 생략 표시).
5. 만든 탭을 닫는다. 틱톡샵(1-c-2')은 회사 채널에선 따로 받지 않는다(국면 회차가 미국 공식 샵을 받는다 · 회사 채널의 틱톡샵 칸은 지난 덤프).

**토요일 로그인 점검** — 크롬 새 탭에서 keepa.com 을 열어 계정 이름·한도를 보고, `https://echotik.live/board` 를 열어 javascript_tool `!!localStorage.getItem('token')` 이
true 인지 본다(2026-11-23 부터 FastMoss 대신 EchoTik · false 거나 로그인 화면이면 풀린 것).
둘 중 하나라도 풀려 있으면 알림(사용자가 그날 평소 크롬에서 로그인해 두면 일요일 회차가 그대로 돈다). 둘 다 되면 알림 없이 끝. 만든 탭은 닫는다.

**알림** — 멈추거나 일부만 받으면 끝내기 전에 `python telegram_send.py msg "⚠️ K뷰티 Keepa 주간: <어디서 왜 · 사용자가 할 일>"` 한 번(사용자가 정한 알림 · 잘 끝나면 안 보낸다).

## 1-g. Keepa 주간 통합 수집 — 국면(KBPH)과 회사 채널(KBCH)을 한 번에 (2026-11-01~ · 1-e 의 5·6번 · 1-f 의 회사 채널 단계를 대신한다)

사용자: "데이터베이스에 쌓이면 한꺼번에 되는 거 아니었나 — 깔끔하게 정리해 봐". 전엔 같은 Keepa 상품을 두 번 불렀다 — 일요일 국면(나라마다 Finder 1~2번)과
월요일 회사 채널(브랜드×나라 과제마다 Finder 1번 · 230번 · 안 팔리는 상품까지 전부 · 10/20 회차 2.1만 개). 회사 채널이 한도를 바닥낸 게 KBCH 가 10/20 에 멈춘 이유다.
이제 **나라마다 Finder 두 번**(A = 배지 한 번이라도 붙은 상품 · B = 지금 30만 위 안)만 부르고, 받은 상품 객체 하나로 세 계산(KBCH · 국면 미국 · 국면 유럽·일본·캐나다)을 다 한다.
계산식은 그대로다(`keepa.js` 의 `fromRows` · `phase_keepa*.js` 의 `fromObjs` 가 표 대신 받은 객체를 읽을 뿐). 빠지는 것 = 배지가 한 번도 없고 지금 30만 위 밖인 상품.
덤으로 KBCH 일본이 가타카나 표기 상품(コースアールエックス(cosrx) 등)까지 잡는다 — 예전 KBCH 일본 과제는 라틴 표기만 받아서 빠져 있었다(첫 회차에 일본 코스알엑스 등이 한 번 뛴다).

**언제** — 일요일 1회(`kbph-weekly` · 06:50). 빠지면 월·화가 이어받는다. 차례 = `python kbeauty/phase_brief.py --due` 가 0. KBCH 모드는 `python kbeauty/ingest.py --due` 가 찍는 `모드 full|recent`.

1. 1-e 의 1~4번(멈출 조건 · 받기 서버 · 크롬 새 탭 keepa.com · 한도 확인 · 보내기 함수). **시작 전 한도 %를 적는다**(새 탭 `#widget__bucket_quota`) — 20% 밑이면 시작하지 않고 '한도 N% — 내일로'.
2. 차례로 붙여 넣는다(javascript_tool · 주석은 지워도 된다): `kbeauty/keepa.js` → `kbeauty/phase_keepa.js` → `kbeauty/phase_keepa_eu.js` → `kbeauty/keepa_week.js`(→ `kw v4 ready` · 브랜드 50개씩 나눠 검색 — Finder 브랜드 필터는 앞 50개만 먹는다 · 2026-11-09 · v4 = 쪽마다 90초까지 기다린다 · 2026-11-15).
3. `__KW.start(<kbeauty/keepa_tasks.json 내용>, {quota: <1번의 %>})`(월·화 이어받기면 `doms:[--todo 의 번호]` 도) → 40초마다 `__KW.status()` 가 `done` 까지
   (나라마다 `A n B n 합 n` 로그 · '건너뜀'·'불완전'·'멈춤' 이 뜨면 그 나라는 월·화가 받는다). 끝나면 새 탭에서 한도 %를 다시 적는다.
4. `__KW.build('<KBCH 모드>')` → `KBCH done · 230/230 … | US A n NB n fit … | uk brands … | …` 를 확인 → `__KW.bundle()`(len · h).
5. 보내기: `__send('kw_'+오늘, __KW.text)` → `python kbeauty/phase_recv.py hash .claude/recv/kw_<오늘>.txt` 의 len·h 가 같은지.
   받기 서버가 없으면(클라우드 세션) `__KW.show(i)` 로 나눠 띄워 get_page_text — 본문 줄바꿈은 '~' · 덩어리마다 len·h 를 맞춘다.
6. **첫 회차(2026-11 첫 통합 회차)만**: `python kbeauty/week_recv.py <파일> --compare --dry` — 옛 회차(지금 `keepa_month.csv`)와 같은 달끼리 판매량 비를 본다.
   나라 합계가 최근 12개월 0.97 밑이면(빠진 꼬리 상품이 생각보다 크면) 저장하지 말고 보고 — B 의 30만 위를 넓힌다.
7. `python kbeauty/week_recv.py <파일>` → KBCH(ingest) · 국면 미국(phase_recv us) · 유럽·일본·캐나다(phase_recv eu) 저장 → 틱톡샵 EchoTik(1-e 의 7번) →
   `python kbeauty/phase.py` → `python kbeauty/phase_brief.py`(미리보기) → **7-a 이유 적기** → `python kbeauty/push.py --phase` → 만든 탭 닫기.
7-a. **브리핑 이유 한두 줄(2026-11-23 사용자 "표 끝날 때마다 한두 줄 정리 · 리서치해서 이유를")** — 미리보기의 표 넷(지역 · 판매 증감 · 비중 변화율 · 채널별 순위)과 ▸ 줄을 보고,
   크게 움직인 칸(±30% · † 행사 칸 · 1주 1위 브랜드)의 이유를 웹 검색으로 찾는다(행사 일정 · 회사 발표 기사 · 신제품·입점 소식).
   `kbeauty/data/phase/brief_note.json` 에 KBPH asOf 날짜 키로 `region`·`sales`·`share`·`ch` 한 줄씩 + `top`: {#결론 1·2·3등 브랜드 한글 이름: [왜 좋았나 한 줄 · 40자 안 · 숫자와 날짜만(예 '빅딜데이 미국 +85%(10/14 발표)')]}.
  **#결론 검토**: 미리보기(`--html`)를 돌려 `[검토]` 줄을 본다 — '제품 한글 짧은 이름 없음' 이면 brief_note.json 맨 위 `_prod`({영문 제목 조각: 한글 짧은 이름 · 열 자 안팎}) 에 넣고, '길다' 면 이유를 줄여 다시 돌린다. `[검토]` 가 없을 때 올린다.(55자 안 · 출처가 회사 발표면 '(회사 발표)').
   **확인한 것만 적는다 — 짐작은 쓰지 않는다.** 못 찾으면 그 칸은 비워 둔다(▸ 숫자 줄만 나간다). brief_note.json 도 같은 push 에 싣는다.
   **검수(2026-11-23 사용자 "간결하게 · 한 번 검수해서")** — 적은 뒤 `python kbeauty/phase_brief.py` 를 다시 돌려 ① `[검수]` 줄이 없는지(55자 넘음·표에 없는 브랜드 → 자동으로 빠진다)
   ② → 줄의 행사 날짜·회사 발표 숫자가 출처와 같은지 ③ ▸ 숫자 줄과 → 이유가 서로 어긋나지 않는지(예: ▸ 가 '틱톡샵이 끌었다'인데 → 가 아마존 얘기) 본 뒤에 올린다.
7-b. **지누스(ISMKP) — 마지막 수집(`public/index.html` 의 `const ISMKP` asOf)이 28일 넘었고 한도가 10% 이상 남았을 때만.** 같은 keepa.com 탭에서
   `ism_keepa/keepa_brand.js` 주석 0~2번대로(브랜드 zinus · 미국 · 약 900개 ≈ 한도 4%) → `ism_keepa/zinus.json` → `python ism_keepa.py` → 같은 push 에 싣는다.
8. 보고: `[한도]` 줄(week_recv.py 가 찍는다 — 나라별 행 · 건너뜀·불완전) · 한도 전후 % · `[KBCH]`·`[KBPH]` 줄 · 지누스 받았나 · 첫 회차면 비교 결과 · 남은 나라(`--todo`).

**예약 작업 원문(`kbph-weekly` · 토·일·월·화 06:50 · 수요일은 뺀다 — 2026-11-03)** — 앱의 작업 편집에서 지시문을 이걸로 바꾼다:
```
[K뷰티 Keepa 주간] 작업 폴더 C:\Users\user\Desktop\asd. 절차 원본은 kbeauty/RUNBOOK.md — 맨 위 'Keepa 를 쓰는 곳은 일요일 한 회차뿐이다' 절과 1-e(준비 1~4번 · 틱톡샵 EchoTik 7번 = 1-c-2' · 올리기 8번) · 1-g(통합 수집 · 지누스 7-b) · 1-f(토요일 로그인 점검 · 알림).
토요일 = 로그인 점검만. 일·월·화 = git pull 뒤 `python kbeauty/phase_brief.py --due` 가 0 이면 1-g 통합 수집(8개국) · 1 이면 `python kbeauty/week_recv.py --todo` 가 0 일 때 그 나라만(1-g 3번 doms) · 둘 다 아니면 한 줄로 끝.
새 탭 한도 %를 __KW.start 에 quota 로 넘긴다(모자란 나라는 저절로 건너뛰고 다음 날 이어받는다 · 20% 밑이면 시작하지 말고 '한도 N% — 내일로').
Keepa·EchoTik 에 로그인하지 않는다(풀려 있으면 알림만). 사용자 탭은 건드리지 않고 만든 탭은 닫는다. 멈추거나 일부만 받으면 python telegram_send.py msg 로 한 번 알린다.
```

## 사람이 고칠 것

| 일 | 어디 |
|---|---|
| 새 브랜드 | `config.json` `brands` 맨 뒤에 `{"k":키,"co":회사,"ko":한글,"kp":[Keepa 브랜드 문자열…],"d":"all"/"few"/[도메인],"tf":제목 조건(선택)}` → `python3 kbeauty/ingest.py --tasks` (과제가 바뀌어 다음 회차가 저절로 full) |
| Keepa 브랜드 문자열 | Product Finder 의 Brand 칸에 앞글자를 넣으면 '(상품 수)'와 함께 뜬다. d'Alba = `d'alba piedmont` + `d'alba` 처럼 둘 이상일 수 있다 |
| 이름이 겹치는 브랜드 | `tf`(제목 정규식 · 대소문자 무시) — 미국 'VDL' 은 전기자전거라 vdl 에 화장품 단어 조건을 붙였다. ts 는 샴푸 단어 |
| 새 회사·지역 | `config.json` `companies` — 지역 이름은 `ir.json` 의 공시 줄 이름과 같아야 계수가 붙는다 |
| 공시 지역 매출 | `ir.json` — 분기 실적이 나오면 한 칸(출처 URL 같이). 반기만 나오면 '1H26', 연간이면 'FY25' 키 |
| 틱톡샵 샵 | `config.json` `tt` |
| 새 브랜드를 정기 회차 전에 바로 | 'add' 회차 — 새 과제만 `__KBK.start(과제, {mode:'full', add:1, curves:{d:[a,b1,b2]…}})`(곡선 = `data/keepa_curves.csv` 마지막 회차) → 평소처럼 dump → `ingest.py`. 마지막 회차 날짜로 끼워 넣고 meta 는 안 바꾼다(2026-10-21 네오팜·클리오·동국제약·브이티·엔에프씨) |
