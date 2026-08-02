# 아마존 뷰티 베스트셀러 트래커 (US 탑100 + 유럽 5개국 탑50)

매일 1회, 아마존 6개국(US·UK·DE·FR·IT·ES)의 **Beauty + Skin Care** 베스트셀러에서
K뷰티 브랜드를 찾아, 그 제품들의 **BSR(판매순위)·가격·평점·리뷰 수**를 `data/history.csv`에
누적하고 전일 대비 변동을 **텔레그램**으로 보냅니다.

**핵심은 ASIN 고정 추적입니다.** 한 번이라도 잡힌 제품은 베스트셀러 100위 밖으로 밀려나도
매일 BSR을 재기 때문에 추이가 끊기지 않습니다. 리스트만 긁으면 순위권 이탈 = 데이터 소실인데,
정작 중요한 하락 국면이 그때 생깁니다.

> 판매량 자체는 아마존이 비공개라, 업계 표준대로 **랭킹 변동을 판매 추이의 프록시**로 씁니다.
> 리뷰 수 증가 속도도 보조 지표가 됩니다.

**브라우저를 쓰지 않습니다.** Playwright 대신 `curl_cffi`가 TLS 지문만 크롬으로 위장해서
HTTP 요청을 보냅니다. 6개 마켓 리스트 수집이 **7회 요청, 30초**면 끝나고 비용은 0원입니다.

## 1. 설치 (최초 1회)

```bash
cd amazon-beauty-tracker
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

`playwright install` 은 이제 필요 없습니다.

## 2. 설정

`config.example.yaml`을 `config.yaml`로 복사한 뒤:

- `brands:` 추적할 브랜드 나열 (제품 타이틀에 포함되는 표기 그대로)
- `markets:` 수집할 마켓. 안 쓸 마켓은 `enabled: false`
- `telegram.bot_token` / `telegram.chat_id` 입력 — chat_id를 모르면 봇에게 아무 메시지나
  보낸 뒤 `https://api.telegram.org/bot<토큰>/getUpdates` 를 열면 `"chat":{"id":123456789}` 가 보입니다.

### 하위 카테고리로 좁히기

전체 Beauty 리스트에 관심 브랜드가 안 잡히면 `category`를 하위 노드로 바꾸세요.

```yaml
  - code: DE
    category: beauty/64257031     # ← 전체 대신 특정 하위 카테고리
```

해당 국가 아마존에서 원하는 카테고리의 베스트셀러 페이지를 연 뒤, 주소창의
`/gp/bestsellers/` 또는 `/zgbs/` 뒷부분을 그대로 복사해 넣으면 됩니다.
**노드ID는 마켓마다 다릅니다** — US 것을 DE에 그대로 쓰면 엉뚱한 카테고리가 나옵니다.

## 3. 테스트 실행

```bash
python main.py --no-telegram --markets US --budget 20
```

빠르게 도는 조합입니다. 정상이면 마켓별로 `순위+ASIN 100개 / 페이지 렌더 60개` 같은 줄이 뜹니다.
그다음 전체로:

```bash
python main.py --no-telegram
```

| 플래그 | 용도 |
|---|---|
| `--no-telegram` | 텔레그램 발송 생략 (콘솔 출력만) |
| `--markets US,UK` | 특정 마켓만 수집 |
| `--full` | 압축 대신 제품별 상세 리포트 |
| `--budget 30` | 마켓당 상세조회 상한 (빠른 확인용) |

## 4. 매일 아침 자동 실행 등록

스크립트는 클로드 없이 혼자 돕니다. OS 스케줄러에 등록하세요.

**Windows (작업 스케줄러)**

```
schtasks /create /tn "AmazonBeautyTracker" /sc daily /st 07:30 ^
  /tr "C:\path\to\amazon-beauty-tracker\.venv\Scripts\python.exe C:\path\to\amazon-beauty-tracker\main.py"
```

작업 속성에서 **"작업을 실행하기 위해 절전 모드 해제"**를 켜두면 자리를 비워도 돕니다.

**macOS / Linux (cron)**

```bash
crontab -e
# 30 7 * * * cd /path/to/amazon-beauty-tracker && .venv/bin/python main.py >> data/run.log 2>&1
```

## 5. GitHub 자동 push

`config.yaml`의 `git.enabled: true`(기본값)이면 매 실행 후 `data/history.csv`와
`data/asin_cache.json`을 커밋·push합니다. 이 폴더가 git 저장소(또는 대시보드 저장소의 하위
폴더)이고 push 권한이 설정되어 있어야 합니다.

> ⚠️ **GitHub Actions에서 직접 돌리지 마세요.** Actions 러너는 데이터센터 IP라 아마존이
> 차단합니다. 수집은 반드시 이 컴퓨터(가정용 IP)에서 하고, Actions는 push된 데이터를
> 쓰기만 해야 합니다.

## 6. 데이터 구조

`data/history.csv`:

| 컬럼 | 뜻 |
|---|---|
| `date` `market` `brand` `asin` `title` | 식별자 |
| `list_cat` `list_rank` | 그날 베스트셀러 리스트에서의 위치. **비어 있으면 순위권 밖** |
| `bsr_main` `bsr_main_cat` | 전체 카테고리 BSR — **추이 추적의 기준. 순위권 밖에서도 존재** |
| `bsr_sub` `bsr_sub_cat` | 하위 카테고리 BSR (예: `Facial Masks #2`) — 가장 예리한 신호 |
| `price` `currency` `rating` `reviews` | 가격은 마켓별 통화 |

날짜×마켓×제품 단위로 한 행씩 쌓입니다. 같은 날 재실행하면 **그날 수집한 마켓의 행만**
덮어씁니다 (`--markets US` 로 부분 실행해도 다른 나라 데이터가 안 날아갑니다).

- `price`는 `currency` 컬럼의 통화 기준입니다. 마켓별 통화가 다르니 **합산·비교 전에 반드시
  환산**하세요.
- **`bsr_main` 이 대시보드에 그릴 값입니다.** `list_rank` 는 100에서 잘리므로 추이가 끊깁니다.
- 가격은 마켓별 통화가 다르니 비교·합산 전에 반드시 환산하세요.

`data/tracked_asins.json` — **고정 추적 목록. 이 파일이 순위권 밖 추적의 근거입니다. 지우면
그동안 쌓은 추적 대상이 사라지고 리스트에 다시 잡힐 때까지 데이터가 빕니다.**
30일 내내 BSR도 안 잡히는 제품은 자동으로 정리됩니다(단종 대응).

`data/asin_cache.json` — ASIN→제목 캐시. 이미 K뷰티가 아닌 걸로 판명된 ASIN을 매일 다시
조회하지 않게 해줍니다. 지워도 오류는 아니고 다음 실행이 느려집니다.

## 문제가 생기면

- **`data-client-recs-list를 못 찾았습니다`** — 아마존이 페이지 구조를 바꾼 경우입니다.
  `data/debug_<마켓>_p<번호>.html`이 자동 저장되니, 그 파일을 클로드 코드에 주고
  "파서 고쳐줘"라고 하면 됩니다.
- **CAPTCHA에 걸림** — 실행 시간을 30분쯤 옮기고, `config.yaml`의 `page_delay` /
  `detail.delay`를 늘리세요. 반복되면 `impersonate`를 `chrome131` 등 특정 버전으로 고정해봅니다.
- **상세 조회가 계속 실패** — 상품 상세 페이지는 **베스트셀러 리스트를 먼저 연 세션**으로만
  열립니다. 이 동작은 코드에 이미 들어있으니, 직접 스크립트를 짤 때만 주의하세요.
- **하루 1~2회를 넘기지 마세요.** 개인용 저빈도 모니터링 전제로 만든 코드입니다.
