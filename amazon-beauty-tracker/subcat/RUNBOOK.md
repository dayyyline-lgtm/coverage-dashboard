# 아마존 세부 카테고리 수집 — 절차 (AMZSUB)

매일 아침 **크롬 도구(Claude in Chrome)가 붙어 있는 대화 세션**이 이 순서로 돈다. 사람이 손으로 돌릴 때도 같다.
왜 이렇게 생겼는지는 `../../CLAUDE.md` 의 '아마존 세부 카테고리' 절.

## 누가 언제 돌리나 (2026-10-11 ~)

- **예약 작업(새로 뜨는 클라우드 세션)에는 크롬 도구가 아예 안 붙는다.** 2026-10-10 05:17 정기 회차 기록("크롬 도구가 안 붙어 멈춤")과
  11:07 점검 회차(윈도우 크롬이 연결된 상태에서도 ToolSearch 가 'No matching deferred tools')로 확인했다. PC 가 꺼져서가 아니다.
- 그래서 크롬 도구가 붙어 있는 **대화 세션**(session_01MeW8UpgbB36NWfLgfCNRy5 · 윈도우 PC 데스크톱 앱에 연결)이 `send_later` 로
  매일 **05:30(KST)** 자기에게 수집을 건다 — '아침 수집' 사슬. 회차마다 내일·모레 회차가 걸려 있는지 보고 없으면 건다(하루 빠져도 안 끊기게).
- 예약 작업 '아마존 세부 카테고리 — 아침 수집 점검'(매일 07:40 · `trig_01XAb98Ng7iLe9q7YgvPWR42`)은 수집하지 않는다.
  `days.csv` 를 보고 오늘 완전한 회차가 없거나 내일 사슬 회차가 안 걸려 있으면 휴대폰 알림만 보낸다.
- 시각: 윈도우 PC 는 05:15 에 아마존 트래커 작업이 깨워 07시 전후까지 깨어 있다. 크롬 확장이 계정에 붙는 시각은 날마다 다르다
  (10/10 05:53 · 10/11 05:19) — 그래서 05:30 에 시작해 **붙을 때까지 최대 90분 기다린다**. 한 회차는 붙은 뒤 15분 안팎.
  05:30~06:20 사이에 올리면 아침 봇 배포(평일 05:35 · 주말 06:05 전후)가 싣거나 push.py 가 직접 배포한다 → 6시 반 전후 사이트 반영.
- ⚠ **이 대화를 보관·삭제하면 사슬이 끊긴다.** 07:40 점검이 알려 준다. 다시 걸 때는 크롬 도구가 붙은 세션에서 맨 아래 '사슬 메시지'를
  그대로 `send_later` 로 건다(이름 '아마존 세부 카테고리 아침 수집 (MM/DD 05:30)').

## 아침 수집 — 이 세션 (한 회차)

1. **사슬 유지(맨 먼저)** — `list_triggers` 로 이름이 '아마존 세부 카테고리 아침 수집 (' 로 시작하는 예약을 보고, 내일·모레 05:30 회차가 없으면 건다.
2. 아래 0단계(`--today` 0 이면 끝).
3. **윈도우 크롬 기다리기** — `list_connected_browsers` 에 osPlatform Windows 가 없으면 `sleep 240` 하고 다시. 처음 본 때부터 최대 90분.
   붙으면 `select_browser` 로 그 브라우저를 고르고 1~3단계.
4. 90분 안에 안 붙으면 수집하지 말고 멈추고, 같은 날 13:20 에 같은 메시지로 `send_later` 를 하나 건다(13:20 회차 자신이면 더 걸지 않는다).

## 0. 저장소

```
# 작업 폴더에 coverage-dashboard 클론이 있으면: git -C <클론> pull -q --ff-only
# 없으면: add_repo(owner=dayyyline-lgtm, repo=coverage-dashboard, access=push) → 결과가 알려 주는 clone 명령 그대로(얕은 클론이면 충분)
cd <클론>
python3 amazon-beauty-tracker/subcat/ingest.py --today     # 종료코드 0 = 오늘 완전한 회차가 이미 있다 → 여기서 끝
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

## 3. 검증 → 저장 → 올리기

```
python3 amazon-beauty-tracker/subcat/ingest.py --check /tmp/amzsub/part_*.txt
```
- `CRC 불일치 … → window.__AMZSUB.redo('C|53|,T|B0…|')` 가 나오면 그 줄을 그대로 브라우저에서 부르고
  `get_page_text` → `/tmp/amzsub/fix_1.txt` 로 쓴 뒤 **원래 파일들과 같이** 다시 `--check`. 맞는 줄이 틀린 줄 자리에 들어간다.
- 통과하면:
```
python3 amazon-beauty-tracker/subcat/ingest.py /tmp/amzsub/part_*.txt [/tmp/amzsub/fix_*.txt]
python3 amazon-beauty-tracker/subcat/push.py
```
- ingest 가 가격 줄(P)을 `data/subcat/prices.csv` 에 적고(값이 바뀐 날만), 블록을 만들 때 추정 매출(model.py)을 다시 계산한다.
- push.py 는 데이터 파일 셋만 커밋한다. 배포는 push.py 가 정한다 — 평소엔 배포 생략 표시(봇의 다음 배포가 싣는다),
  아침(05~07시)엔 아침 봇 배포(이벤트/수출 갱신 · 데일리 레터)가 이미 지나갔으면 직접 배포한다. 출력의 `배포: …` 줄이 이유다.
  거절되면 원격 최신 위에 블록만 다시 주입해 최대 4번 올린다(합치지 않는다).
- 끝나면 만든 탭을 닫는다(`tabs_close_mcp`).

## 4. 보고 (한 줄)

`ingest.py` 출력의 `[AMZSUB] …` 줄 + `상장사 상위` 줄 + 상장사 새 SKU(`NEW` 줄)가 있으면 그것까지. 실패면 어디서 멈췄는지.

## 사람이 고칠 것

| 일 | 어디 |
|---|---|
| 새 한국 브랜드 | `config.json` 의 `brands` **맨 뒤에** `["표시명",["패턴",…],"회사","L/P/F/N"]` 한 줄. 순서를 바꾸거나 중간에 끼우면 과거 덤프 번호가 틀어진다 |
| 브랜드의 회사·상장 상태가 바뀜(인수·상장) | 그 줄의 3·4번째 칸, `companies` 의 `st` — 과거 데이터도 새 회사로 다시 묶인다(블록은 매번 마스터+사전으로 다시 만든다) |
| 새 카테고리 | `cats` **맨 뒤에** `["카테고리 id",""]` — 이름은 다음 수집이 채운다 |
| 새 브랜드 후보 확인 | `data/subcat/unknown.csv`(제목에 Korean·K-beauty 가 들어갔는데 사전에 없는 상품) |

## 덤프 형식

`collector.js` 맨 위 주석. CRC = CRC32(줄에서 마지막 `|crc` 앞까지, UTF-8) 36진수.

## 사슬 메시지 (send_later 원문 — 끊겼을 때 이걸 그대로 건다)

```
[아마존 세부 카테고리 — 아침 수집] 매일 아침 이 세션이 AMZSUB(아마존 미국 뷰티 세부 카테고리 155개 Top100 · 한국 브랜드 SKU)를 수집한다. 예약 작업으로 새로 뜨는 세션엔 크롬 도구가 안 붙어서(10/10 점검 두 번으로 확인) 크롬 도구가 붙어 있는 이 세션이 맡는다. 사용자는 자고 있다 — 묻지 말고 끝까지. 절차 원본: 저장소 amazon-beauty-tracker/subcat/RUNBOOK.md 의 '아침 수집 — 이 세션' 절과 1~3단계.
0) 사슬 유지(맨 먼저): list_triggers 로 이름이 '아마존 세부 카테고리 아침 수집 (' 로 시작하는 예약을 본다. 내일·모레 05:30(KST) 회차가 없으면 이 메시지와 똑같은 내용으로 send_later 를 건다(at = 그날 05:30 KST, 이름 '아마존 세부 카테고리 아침 수집 (MM/DD 05:30)'). 같은 날짜가 둘이면 하나만 남긴다.
1) cd /home/claude/coverage-dashboard → git status 가 깨끗하면 git pull -q --ff-only → python3 amazon-beauty-tracker/subcat/ingest.py --today. 종료코드 0 이면 '오늘 이미 수집됨' 한 줄로 끝.
2) 윈도우 크롬 기다리기: mcp__claude-in-chrome__list_connected_browsers 에 osPlatform 이 Windows 인 브라우저가 없으면 Bash 로 sleep 240 하고 다시 본다 — 처음 본 때부터 최대 90분(10/10 실측: PC 는 05:15 에 깨는데 크롬 확장은 05:53 에 붙었다). 보이면 select_browser 로 그 브라우저를 고르고 RUNBOOK 1~3단계(수집 → 덤프 옮기기 → --check → ingest → push.py). 아마존 /dp/ 는 열지 않고, BLOCKED 면 다시 돌리지 않는다. 배포 여부는 push.py 가 정한다. 사용자가 열어 둔 탭은 건드리지 않고, 만든 탭은 닫는다.
3) 90분 안에 안 보이면 수집하지 말고 멈추고, 같은 날 13:20 KST 에 이 메시지와 같은 내용으로 send_later 를 하나 건다(이름 '아마존 세부 카테고리 아침 수집 (MM/DD 13:20)' · 이미 있으면 안 건다 · 지금이 13:20 회차면 더 걸지 않는다).
4) 보고(반말 2~3줄): [AMZSUB] 줄 · 상장사 상위 줄 · push.py 의 '배포:' 줄. 실패면 어디서 왜 멈췄는지.
```
