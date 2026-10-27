# 아마존 아침 수집 — 절차 (AMZSUB 미국 세부 카테고리 + AMZL 7개국 Top100)

매일 아침 **크롬 도구(Claude in Chrome)가 붙어 있는 대화 세션**이 이 순서로 돈다. 사람이 손으로 돌릴 때도 같다.
2026-10-18 부터 7개국 뷰티 Top100(1-b)도 여기서 받는다 — PC 트래커의 순위표·아침 메시지('💄 아마존 K뷰티')를 대신한다. 트래커는 메시지 없이 상품 페이지 측정(매출 환산표 재료)으로 남는다(2026-10-18 저녁 사용자 결정).
왜 이렇게 생겼는지는 `../../CLAUDE.md` 의 '아마존 세부 카테고리' 절.

## 누가 언제 돌리나 (2026-10-11 ~)

- **예약 작업(새로 뜨는 클라우드 세션)에는 크롬 도구가 아예 안 붙는다.** 2026-10-10 05:17 정기 회차 기록("크롬 도구가 안 붙어 멈춤")과
  11:07 점검 회차(윈도우 크롬이 연결된 상태에서도 ToolSearch 가 'No matching deferred tools')로 확인했다. PC 가 꺼져서가 아니다.
- 그래서 크롬 도구가 붙어 있는 **대화 세션**(session_01MeW8UpgbB36NWfLgfCNRy5 · 윈도우 PC 데스크톱 앱에 연결)이 `send_later` 로
  매일 **05:30(KST)** 자기에게 수집을 건다 — '아침 수집' 사슬. 회차마다 내일·모레 회차가 걸려 있는지 보고 없으면 건다(하루 빠져도 안 끊기게).
- 예약 작업 '아마존 세부 카테고리 — 아침 수집 점검'(매일 07:40 · `trig_01XAb98Ng7iLe9q7YgvPWR42`)은 수집하지 않는다.
  `days.csv` 를 보고 오늘 완전한 회차가 없거나 내일 사슬 회차가 안 걸려 있으면 휴대폰 알림만 보낸다.
- 시각: 윈도우 PC 는 05:15 에 작업 스케줄러 'AmazonBeautyTracker' 가 깨워 07시 전후까지 깨어 있다
  (트래커는 끄지 않는다 — 05:15 트래커가 40~50분 돌며 PC 를 깨워 두는 덕에 이 수집이 돈다. 트래커를 짧게 만들 일이 생기면 `awake.bat`(아마존 요청 없이 110분 깨워 두기)을 같이 걸 것). 크롬 확장이 계정에 붙는 시각은 날마다 다르다
  (10/10 05:53 · 10/11 05:19) — 그래서 05:30 에 시작해 **붙을 때까지 최대 90분 기다린다**. 한 회차는 붙은 뒤 15분 안팎.
  05:30~06:20 사이에 올리면 아침 봇 배포(평일 05:35 · 주말 06:05 전후)가 싣거나 push.py 가 직접 배포한다 → 6시 반 전후 사이트 반영.
- ⚠ **이 대화를 보관·삭제하면 사슬이 끊긴다.** 07:40 점검이 알려 준다. 다시 걸 때는 크롬 도구가 붙은 세션에서 맨 아래 '사슬 메시지'를
  그대로 `send_later` 로 건다(이름 '아마존 세부 카테고리 아침 수집 (MM/DD 05:30)').

## 아침 수집 — 이 세션 (한 회차)

1. **사슬 유지(맨 먼저)** — `list_triggers` 로 이름이 '아마존 세부 카테고리 아침 수집 (' 로 시작하는 예약을 보고, 내일·모레 05:30 회차가 없으면 건다.
2. 아래 0단계(`ingest.py --today` 와 `lists.py --today` 가 둘 다 0 이면 끝 · 하나만 0 이면 빠진 쪽만).
3. **윈도우 크롬 기다리기** — `list_connected_browsers` 에 osPlatform Windows 가 없으면 `sleep 240` 하고 다시. 처음 본 때부터 최대 90분.
   붙으면 `select_browser` 로 그 브라우저를 고르고 1~3단계.
4. 90분 안에 안 붙으면 수집하지 말고 멈추고, 같은 날 13:20 에 같은 메시지로 `send_later` 를 하나 건다(13:20 회차 자신이면 더 걸지 않는다).
5. **한 번만(2026-10-18 등록 · 끝나면 이 줄을 지울 것)** — PC 셸 도구(`mcp__remote-devices__device_bash`)가 붙어 있으면 루트 CLAUDE.md
   '아마존 7개국 Top100 → 아직 남은 것'의 PC 클론 동기화를 한다(트래커 메시지 끄기 · scraper 가격 수정 반영). 수집이 끝난 뒤에 · 트래커가 다 돈 뒤(07시 이후 권장)에.
   PC 클론 경로는 PC 에서 `AmazonBeautyTracker` 작업의 실행 파일 경로(`schtasks /query /tn AmazonBeautyTracker /v /fo list`)로 확인한다.
6. **K뷰티 채널(Keepa · 주 1회 · 2026-10-21 등록)** — 3단계 push.py 까지 끝난 뒤, 이 회차가 05:30 회차이고 지금이 06:30 KST 전이며
   `python3 kbeauty/ingest.py --due` 가 종료코드 0 이면 같은 윈도우 크롬에서 `kbeauty/RUNBOOK.md` 1-c-1(Keepa) → 1-c-3(저장·올리기).
   모드(full/recent)는 `--due` 출력대로. FastMoss(1-c-2)는 그 크롬에 FastMoss 가 로그인돼 있을 때만. 세부 카테고리·7개국은 이미 올라가 있으니
   여기서 멈추거나 실패해도 그쪽엔 영향이 없다 — 보고에 `[KEEPA]`·`[KBCH]` 줄 또는 멈춘 곳만 더한다. 13:20 회차·06:30 넘으면 건너뛴다(다음 날 `--due` 가 이어받는다).
7. **K뷰티 국면 지도(KBPH) — 이 세션은 하지 않는다(2026-10-27~).** 이 PC 의 Claude 데스크톱 앱 예약 작업 `kbph-weekly`(일·월·화 06:50)가
   덤프를 PC 받기 서버로 받아 올린다(`kbeauty/RUNBOOK.md` '1-e'). 이 세션에선 10/26·10/27 아침 덤프를 옮겨 적다 안전 필터 오탐으로 멈췄고
   국면 덤프는 더 커서다. 같은 크롬을 두 세션이 동시에 몰지 않게 여기서 국면을 손대지 말 것.

## 0. 저장소

```
# 작업 폴더에 coverage-dashboard 클론이 있으면: git -C <클론> pull -q --ff-only
# 없으면: add_repo(owner=dayyyline-lgtm, repo=coverage-dashboard, access=push) → 결과가 알려 주는 clone 명령 그대로(얕은 클론이면 충분)
cd <클론>
python3 amazon-beauty-tracker/subcat/ingest.py --today     # 종료코드 0 = 오늘 미국 세부 카테고리 완전한 회차가 이미 있다
python3 amazon-beauty-tracker/subcat/lists.py --today      # 종료코드 0 = 오늘 7개국이 다 ok — 둘 다 0 이면 여기서 끝
git push --dry-run origin HEAD:main                          # 실패(403 등) = 올릴 권한이 없다
```

push 가 403 이면 Claude GitHub 앱 권한이 없는 것이다 — 수집은 해도 올릴 수 없으니 **크롬을 건드리기 전에** 멈추고 알린다.

## 1. 크롬 (사용자 PC · Claude in Chrome)

0. Claude in Chrome 도구를 ToolSearch **한 번**으로 불러온다(`tabs_context_mcp` · `tabs_create_mcp` · `navigate` · `javascript_tool` ·
   `get_page_text` · `tabs_close_mcp` · `list_connected_browsers` · `select_browser`). **도구 목록에 아예 없으면 이 세션에선 못 한다**
   (예약 작업 세션이 그렇다 — 위 '누가 언제'). 도구는 있는데 연결된 브라우저가 없으면 위 3번처럼 기다린다.
   - 브라우저가 둘 이상 연결돼 있으면 `osPlatform` 이 Windows 인 것(아마존 트래커가 도는 PC)을 `select_browser` 로 고른다 — 사용자가 정한 것.
     Windows 가 없는데 여럿이면 고르지 말고 멈춘다.
1. `tabs_context_mcp`(createIfEmpty) → `tabs_create_mcp` → `navigate` 로 `https://www.amazon.com/robots.txt` (가벼운 같은 출처 페이지).
   사용자가 열어 둔 다른 탭은 건드리지 않는다.
2. `javascript_tool` 에 그대로:
   ```js
   const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/subcat/';
   new Function(await (await fetch(R+'collector.js')).text())();
   ```
   → 반환값은 `undefined` 가 정상이다(수집기는 바로 백그라운드로 돈다). 곧바로 `window.__AMZSUB.status()` 가 `run · …` 인지 본다.
3. 60초 간격으로 `window.__AMZSUB.status()` — `done · 155/155 · fail 0 · …` 가 나올 때까지(동시 1개 기준 6~8분).
   - `BLOCKED`(캡차 연속 3번)면 거기서 멈춘 상태로 `done` 이 된다. **다시 돌리지 말 것** — 차단을 키운다. 받은 데까지 넘기면 부분 회차로 기록된다.
   - 25분이 지나도 `run` 이면 탭이 잠들었거나 끊긴 것 — 받은 데까지 넘기지 말고 멈추고 알린다.

## 2. 덤프 옮기기

1. `window.__AMZSUB.plan()` → `0-170,170-420 · lines 420 · chars 41000` 처럼 2.5만 자 안쪽 덩어리.
   평소(마스터가 쌓인 뒤)는 1.5만 자 안팎이었고, 10/11 부터 가격 줄(P · 120개씩)이 붙어 2만~2.5만 자 — 한두 덩어리다.
2. 덩어리마다 `window.__AMZSUB.dump(a,b)` → `get_page_text` → 본문을 **한 글자도 바꾸지 말고** `/tmp/amzsub/part_N.txt` 로 쓴다.
   머리 4줄(Title: · URL: · Source element: · ---)은 있어도 된다 — ingest 가 버린다.

## 1-b. 7개국 뷰티 Top100 (lists.js · AMZL — 2026-10-18 ~)

미·영·독·프·이·스·일의 'Best Sellers in Beauty' 100위. 나라당 요청 4건(1쪽·POST·2쪽·POST), 상품 페이지(/dp/)는 안 연다.
세부 카테고리 덤프를 다 옮긴(2단계) **같은 탭**에서 한다. 미국 세부 카테고리가 이미 있는 날(0단계)엔 새 탭에서 바로 여기부터.

1. 미국 — 지금 탭(amazon.com/robots.txt)에서 `javascript_tool`:
   ```js
   const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/subcat/';
   new Function(await (await fetch(R+'lists.js',{cache:'no-store'})).text())(); await window.__AMZL.run()
   ```
   → 한 줄 요약(`US · ok · read 100 · titled 100 · kpos 15 · new 0 · …`)이 돌아오고 **본문에 덤프가 뜬다** → `get_page_text` →
   본문을 한 글자도 바꾸지 말고 `/tmp/amzl/US.txt`. ⚠ javascript_tool 반환값은 1천 자 남짓에서 잘린다 — 덤프는 꼭 get_page_text 로.
2. 영·독·프·이·스·일 — 같은 탭을 `navigate` 로 그 나라 robots.txt 로 옮기며 1과 같이:
   `https://www.amazon.co.uk/robots.txt` · `www.amazon.de` · `www.amazon.fr` · `www.amazon.it` · `www.amazon.es` · `www.amazon.co.jp`
   (파일 이름은 나라 코드 UK·DE·FR·IT·ES·JP). `browser_batch` 로 나라마다 navigate → javascript_tool → get_page_text 를 묶으면 한 번에 끝난다.
3. 요약 상태가 `block`(1쪽 로봇 확인)인 나라는 **다른 나라를 다 돈 뒤 한 번만** 다시(`<나라>_2.txt`). 그래도 block 이면 그날은 넘어간다 —
   크롬은 쿠키가 남아 다음 날 이어서 들어간다(10/18 첫날: 처음 가 본 프랑스·이탈리아가 첫 요청에서 막혔고 몇 분 뒤 다시 치니 통과).
   `part`(2쪽이 막힘)도 그대로 받는다 — 50위까지만 비교된다. `norecs` 는 페이지 모양이 바뀐 것이니 보고에 적는다.
4. `python3 amazon-beauty-tracker/subcat/lists.py --check /tmp/amzl/*.txt`
   CRC 가 틀린 나라는 그 나라 robots.txt 로 다시 가서 lists.js 를 불러 `window.__AMZL.again()`(다시 받지 않고 탭 세션에 남은 덤프를 띄운다)
   → get_page_text → `/tmp/amzl/<나라>_fix.txt` 로 쓰고 원래 파일들과 같이 다시 `--check`. 같은 나라 덤프가 여럿이면 상태가 좋은 것을 쓴다.
5. 통과하면 `python3 amazon-beauty-tracker/subcat/lists.py /tmp/amzl/*.txt` — data/lists/ 저장 + `AMZL` 블록 + KMJAMZ.trk(한투 글 없는 날 잇기).
   올리기는 3단계 `push.py` 가 세부 카테고리와 **한 번에** 한다. 올라가면 워크플로 '아마존 K뷰티 아침 알림'이 텔레그램 한 통(하루 한 번).
6. 끝나면 만든 탭을 닫는다.

## 3. 검증 → 저장 → 올리기

```
python3 amazon-beauty-tracker/subcat/ingest.py --check /tmp/amzsub/part_*.txt
```
- `CRC 불일치 … → window.__AMZSUB.redo('C|53|,T|B0…|')` 가 나오면 그 줄을 그대로 브라우저에서 부르고
  `get_page_text` → `/tmp/amzsub/fix_1.txt` 로 쓴 뒤 **원래 파일들과 같이** 다시 `--check`. 맞는 줄이 틀린 줄 자리에 들어간다.
- 통과하면:
```
python3 amazon-beauty-tracker/subcat/ingest.py /tmp/amzsub/part_*.txt [/tmp/amzsub/fix_*.txt]
# → 1-b(7개국)를 돌리고 lists.py 까지 넣은 뒤
python3 amazon-beauty-tracker/subcat/unknown_check.py /tmp/amzsub/part_*.txt /tmp/amzl/*.txt   # 사전 밖 브랜드 규모 점검
python3 amazon-beauty-tracker/subcat/push.py
```
- ingest 가 가격 줄(P)을 `data/subcat/prices.csv` 에 적고(값이 바뀐 날만), 블록을 만들 때 추정 매출(model.py)을 다시 계산한다.
- push.py 는 데이터 파일(세부 카테고리 · 7개국 · config) + index.html 만 커밋한다. 배포는 push.py 가 정한다 — 평소엔 배포 생략 표시(봇의 다음 배포가 싣는다),
  아침(05~07시)엔 아침 봇 배포(이벤트/수출 갱신 · 데일리 레터)가 이미 지나갔으면 직접 배포한다. 출력의 `배포: …` 줄이 이유다.
  거절되면 원격 최신 위에 블록만 다시 주입해 최대 4번 올린다(합치지 않는다).
- `unknown_check.py` 는 그날 U 줄(제목에 Korean 이 있는데 사전에 없는 상품)을 `data/subcat/unknown_daily.csv` 에 쌓고, 사전 밖 브랜드가
  규모 기준(① 7개국 중 한 곳이라도 뷰티 전체 Top100 · ② 미국 세부 카테고리 SKU 3개 이상 · ③ 세부 카테고리 Top10 최근 7일 중 4일)을 넘으면
  `[새 브랜드 확인] …` 줄을 찍는다(2026-10-23 사용자 "사전에 없는 브랜드 일정 규모 이상 되면 나한테 물어봐"). 한 번 물은 브랜드는 `unknown_asked.json` 에 적혀 다시 안 묻는다.
  처리(묻지 않는다 · 2026-10-27 사용자 "너가 찾아보고 비한국 비상장이면 무시"): 웹으로 운영사를 찾아 → 한국 회사 아님·상장 아님 = `--decide "이름=무시(사유)"` · 한국 브랜드(비상장 포함) = config.json `brands` 맨 뒤 한 줄(상태 N · 운영사 이름) + `--decide "이름=추가(사유)"` · 상장사·상장 준비 소속 = 같은 식으로 넣고 상태 L/P · 국적이 끝내 불명이면 무시하고 보고에 한 줄.
- 끝나면 만든 탭을 닫는다(`tabs_close_mcp`).

## 4. 보고 (한 줄)

`ingest.py` 출력의 `[AMZSUB] …` 줄 + `상장사 상위` 줄 + 상장사 새 SKU(`NEW` 줄)가 있으면 그것까지 + `lists.py` 의 `[AMZL]` 7줄을
'7개국 ok 7 · 한국 자리 미15 영12 …' 처럼 한 줄로. 실패면 어디서 멈췄는지.
`unknown_check.py` 가 `[새 브랜드 확인]` 줄을 냈으면 위 처리대로 직접 정리하고(묻지 않는다) 보고에 한 줄만 — 예: "새 브랜드 3: 무시 2(미국·중국) · 사전 추가 1(○○ · 한국 비상장)". 상장사 소속을 새로 넣었으면 그 줄은 꼭 적는다.

## 사람이 고칠 것

| 일 | 어디 |
|---|---|
| 새 한국 브랜드 | `config.json` 의 `brands` **맨 뒤에** `["표시명",["패턴",…],"회사","L/P/F/N"]` 한 줄. 순서를 바꾸거나 중간에 끼우면 과거 덤프 번호가 틀어진다 |
| 브랜드의 회사·상장 상태가 바뀜(인수·상장) | 그 줄의 3·4번째 칸, `companies` 의 `st` — 과거 데이터도 새 회사로 다시 묶인다(블록은 매번 마스터+사전으로 다시 만든다) |
| 새 카테고리 | `cats` **맨 뒤에** `["카테고리 id",""]` — 이름은 다음 수집이 채운다 |
| 새 브랜드 후보 확인 | `data/subcat/unknown.csv`(처음 본 날) · `unknown_daily.csv`(날마다) — 규모가 넘으면 `unknown_check.py` 가 아침 보고로 묻는다 · 물은 기록 `unknown_asked.json` |

## 덤프 형식

`collector.js` 맨 위 주석. CRC = CRC32(줄에서 마지막 `|crc` 앞까지, UTF-8) 36진수.

## 사슬 메시지 (send_later 원문 — 끊겼을 때 이걸 그대로 건다)

```
[아마존 세부 카테고리 — 아침 수집] 매일 아침 이 세션이 ① AMZSUB(아마존 미국 뷰티 세부 카테고리 155개 Top100 · 한국 브랜드 SKU)와 ② AMZL(아마존 7개국 뷰티 Top100 — 2026-10-18 부터 순위표·아침 메시지를 맡는다)을 수집한다. 예약 작업으로 새로 뜨는 세션엔 크롬 도구가 안 붙어서(10/10 점검 두 번으로 확인) 크롬 도구가 붙어 있는 이 세션이 맡는다. 사용자는 자고 있다 — 묻지 말고 끝까지. 절차 원본: 저장소 amazon-beauty-tracker/subcat/RUNBOOK.md 의 '아침 수집 — 이 세션' 절과 1·2·1-b·3단계.
0) 사슬 유지(맨 먼저): list_triggers 로 이름이 '아마존 세부 카테고리 아침 수집 (' 로 시작하는 예약을 본다. 내일·모레 05:30(KST) 회차가 없으면 이 메시지와 똑같은 내용으로 send_later 를 건다(at = 그날 05:30 KST, 이름 '아마존 세부 카테고리 아침 수집 (MM/DD 05:30)'). 같은 날짜가 둘이면 하나만 남긴다.
1) cd /home/claude/coverage-dashboard → git status 가 깨끗하면 git pull -q --ff-only → python3 amazon-beauty-tracker/subcat/ingest.py --today 와 python3 amazon-beauty-tracker/subcat/lists.py --today. 둘 다 종료코드 0 이면 '오늘 이미 수집됨' 한 줄로 끝. 하나만 0 이면 빠진 쪽만 한다.
2) 윈도우 크롬 기다리기: mcp__claude-in-chrome__list_connected_browsers 에 osPlatform 이 Windows 인 브라우저가 없으면 Bash 로 sleep 240 하고 다시 본다 — 처음 본 때부터 최대 90분(10/10 실측: PC 는 05:15 에 깨는데 크롬 확장은 05:53 에 붙었다). 보이면 select_browser 로 그 브라우저를 고르고 RUNBOOK 순서대로: 미국 세부 카테고리 수집 → 덤프 옮기기 → ingest.py --check → ingest.py → 1-b(같은 탭에서 미국 → 영·독·프·이·스·일 lists.js · 덤프는 get_page_text 로 · block 인 나라는 끝에 한 번만 다시) → lists.py --check → lists.py → unknown_check.py(그날 덤프들) → push.py(한 번에). 아마존 /dp/ 는 열지 않고, 세부 카테고리가 BLOCKED 면 다시 돌리지 않는다. 배포 여부는 push.py 가 정한다. 사용자가 열어 둔 탭은 건드리지 않고, 만든 탭은 닫는다.
3) 90분 안에 안 보이면 수집하지 말고 멈추고, 같은 날 13:20 KST 에 이 메시지와 같은 내용으로 send_later 를 하나 건다(이름 '아마존 세부 카테고리 아침 수집 (MM/DD 13:20)' · 이미 있으면 안 건다 · 지금이 13:20 회차면 더 걸지 않는다).
3-b) 그 뒤 RUNBOOK '아침 수집 — 이 세션' 6번(K뷰티 채널 · Keepa 주 1회)과 7번(국면 지도 · 일요일 주 1회)을 조건대로.
4) 보고(반말 2~3줄): [AMZSUB] 줄 · 7개국 한 줄(lists.py 의 [AMZL] 줄 — 나라별 상태·한국 자리) · push.py 의 '배포:' 줄 · unknown_check.py 가 [새 브랜드 확인] 줄을 내면 운영사를 웹으로 찾아 묻지 말고 정리한다 — 비한국·비상장 = --decide 무시 · 한국 브랜드 = config.json brands 맨 뒤에 넣고 --decide 추가(RUNBOOK 3단계 아래 처리 규칙) · 보고엔 한 줄(무시 n · 추가 n · 상장사 소속이면 이름). 실패면 어디서 왜 멈췄는지.
```
