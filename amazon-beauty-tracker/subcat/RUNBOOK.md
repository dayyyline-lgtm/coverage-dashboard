# 아마존 세부 카테고리 수집 — 예약 작업 절차 (AMZSUB)

하루 두 번(KST 09:23 · 13:23) 예약 작업이 이 순서로 돈다. 두 번째 회차는 오전이 성공했으면 바로 끝난다.
사람이 손으로 돌릴 때도 같다. 왜 이렇게 생겼는지는 `../../CLAUDE.md` 의 '아마존 세부 카테고리' 절.

## 0. 저장소

```
add_repo(dayyyline-lgtm/coverage-dashboard, access=push)
git clone --depth 1 https://github.com/dayyyline-lgtm/coverage-dashboard ~/cd   # 있으면 git -C ~/cd pull -q
cd ~/cd
python3 amazon-beauty-tracker/subcat/ingest.py --today     # 종료코드 0 = 오늘 완전한 회차가 이미 있다 → 여기서 끝
```

push 가 403 이면 Claude GitHub 앱 권한이 없는 것이다 — 수집은 해도 올릴 수 없으니 **크롬을 건드리기 전에** 멈추고 알린다.
(`git push --dry-run origin HEAD:main` 으로 미리 본다.)

## 1. 크롬 (사용자 PC · Claude in Chrome)

1. `tabs_context_mcp` → `tabs_create_mcp` → `navigate` 로 `https://www.amazon.com/robots.txt` (가벼운 같은 출처 페이지)
2. `javascript_tool` 에 그대로:
   ```js
   const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/subcat/';
   new Function(await (await fetch(R+'collector.js')).text())();
   ```
   → `started`
3. 60초 간격으로 `window.__AMZSUB.status()` — `done · 155/155 · fail 0 · …` 가 나올 때까지(동시 1개 기준 6~8분).
   - `BLOCKED`(캡차 연속 3번)면 거기서 멈춘 상태로 `done` 이 된다. **다시 돌리지 말 것** — 차단을 키운다. 받은 데까지 넘기면 부분 회차로 기록된다.
   - 25분이 지나도 `run` 이면 탭이 잠들었거나 끊긴 것 — 받은 데까지 넘기지 말고 멈추고 알린다.

## 2. 덤프 옮기기

1. `window.__AMZSUB.plan()` → `0-170,170-420 · lines 420 · chars 41000` 처럼 2.5만 자 안쪽 덩어리.
   평소(마스터가 쌓인 뒤)는 1만 자 안팎 한 덩어리다.
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
- push.py 는 데이터 파일 셋만 커밋하고 배포 생략 표시를 단다 — 사이트엔 봇의 다음 배포(평일 09~16시 매시간 · 주말 12·20시)가 싣는다.
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
