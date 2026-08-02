# CLAUDE.md — 아마존 뷰티 베스트셀러 트래커

> 이 파일은 클로드 코드가 이 프로젝트를 다룰 때 읽는 컨텍스트다.
> 설계 배경과 **실측으로 확인한 사실**을 담고 있으니, 코드를 수정하기 전에 이 문서를 기준으로 판단할 것.

## 목적

매일 아침 아마존 **US 탑100 + UK/DE/FR/IT/ES 탑50**에서 사용자 관심 브랜드(K뷰티 위주) 제품의
순위·가격·평점·리뷰 수·하위 BSR을 수집 → `data/history.csv` 누적 → 전일 대비 변동을 텔레그램 발송.
최종 목표는 **coverage dashboard**에 브랜드별 추이 데이터 소스로 통합하는 것.

## 핵심 설계 결정과 이유

### 1. Playwright를 버리고 curl_cffi로 (2026-08-02 전환)

브라우저를 띄우지 않는다. `curl_cffi`의 `impersonate="chrome"`이 TLS/JA3 + HTTP2 지문을 크롬으로
위장하므로 아마존 WAF를 통과한다. 실측 비교:

| | 베스트셀러 리스트 | 상품 상세(/dp/) |
|---|---|---|
| 일반 `curl` / `requests` | 200, 113KB (통과) | **CAPTCHA 차단** |
| `curl_cffi` (chrome) | 200, 410KB | **200, 통과** |

리스트 수집은 6개 마켓 7회 요청에 30초. Playwright의 브라우저 기동·스크롤·대기가 전부 사라졌다.

### 2. `data-client-recs-list`가 파싱의 1차 앵커 ★ 가장 중요

베스트셀러 페이지 HTML에 이 속성이 박혀 있고, **그 페이지 50개 전부의 `{순위, ASIN}`**이
JSON으로 들어있다.

```html
<div class="p13n-desktop-grid" data-client-recs-list="[{&quot;id&quot;:&quot;B09V7Z4TJG&quot;,
   &quot;metadataMap&quot;:{&quot;render.zg.rank&quot;:&quot;1&quot;...
```

`#gridItemRoot` / `.zg-bdg-text` / `p13n-sc-price` 같은 클래스명은 아마존이 수시로 바꾸지만
이 속성은 안 바뀐다. **순위와 ASIN은 항상 여기서 가져오고, CSS 셀렉터는 제목/가격/평점 보조용으로만
쓸 것.** 이 속성을 못 찾으면 `BlockedError`를 던지고 debug HTML을 저장한다 (조용히 0개 반환 금지).

### 3. 31~50위는 지연 로딩 → /dp/ 개별 조회로 보강

아마존은 페이지당 **30개만 서버 렌더**한다. 31~50위(US는 81~100위도)는 상세가 비어 있다.

- 지연 로딩 엔드포인트 `/acp/p13n-zg-list-grid-desktop/...`는 **GET·POST 모두 404**로 확인됨.
  `data-acp-path` / `data-acp-params`를 그대로 써도 안 된다. **다시 시도하지 말 것.**
- 대신 `/dp/{ASIN}`을 개별 조회한다. 실측 40/40 성공.
- 요청 수 폭증을 막는 장치가 `data/asin_cache.json`(ASIN→제목)이다. 브랜드가 아닌 걸로 이미
  판명된 ASIN은 다시 조회하지 않는다. `detail.mode: tracked`가 기본이며, 이 캐시가 전제다.

### 4. 상품 상세는 "워밍된 세션"으로만 열린다 ★ 함정

`/dp/{ASIN}`을 **새 세션으로 바로 치면 CAPTCHA(3.7KB 응답)**가 나온다. 반드시 같은 세션으로
베스트셀러 리스트를 먼저 연 뒤에 요청해야 200이 온다. `_fill_details()`가 `scrape_market()`의
세션을 그대로 재사용하는 게 이 때문이다. **세션을 새로 만드는 리팩터링을 하지 말 것.**
디버깅 스크립트를 따로 짤 때도 워밍을 넣어야 한다.

### 5. `i18n-prefs` 쿠키로 통화 고정 ★ 과거 버그

아마존은 로케일이 아니라 **쿠키**로 통화를 정한다. 한국 IP에서 쿠키 없이 amazon.com을 열면
가격이 원화로 환산돼 내려온다.

```
쿠키 없음        -> ['KRW 30,261', 'KRW 3,201', 'KRW 27,392']
i18n-prefs=USD  -> ['$20.99', '$2.22', '$19.00']
```

구버전(Playwright)은 `locale="en-US"`만 설정하고 이 쿠키가 없어서 **price 컬럼에 원화 환산값이
쌓이고 있었다.** 그래서 `main.py`가 구스키마 CSV를 발견하면 `history_v1_backup.csv`로 백업하고
새로 시작한다. 구 데이터의 price는 신뢰하지 말 것.

### 6. 하위 카테고리 BSR 파싱은 마켓마다 접두사가 다르다

```
US/UK   #31 in Beauty ( See Top 100 in Beauty )   /  #2 in Facial Masks
DE      Nr. 7 in Kosmetik ( Siehe Top 100 ... )   /  Nr. 1 in Gesichtsseren
FR/IT/ES  n° / n. / nº
```

그래서 `#숫자`로 찾으면 DE/FR/IT/ES에서 전부 실패한다. **링크 텍스트가 곧 카테고리명**이라는
점을 이용해, 카테고리명 앞부분에서 마지막 숫자를 뽑는다(`_parse_sub_bsr`). 최상위 줄만
'Top 100 보기'를 **괄호**로 달고 있어 괄호 유무로 걸러낸다.
`#1 Best Seller` 오렌지 뱃지(`#zeitgeistBadge_feature_div`)를 잘못 집지 않으려면 반드시
`_BSR_CONTAINERS` 안으로 범위를 좁혀야 한다.

### 7. 로컬 실행 고정 (클라우드 금지)

데이터센터 IP에서는 아마존이 차단한다. 가정용 IP + 하루 1회면 안정적으로 통과한다.
**GitHub Actions로 수집을 옮기자는 요청이 오면 거절하고 이유를 설명할 것.** Actions는 push된
데이터를 소비하는 용도로만 쓴다.

### 8. 판매량은 랭킹으로 프록시

아마존은 판매량 비공개. Sales Rank 변동이 업계 표준 프록시이고 리뷰 수 증가 속도가 보조 지표.
**대시보드에 "판매량"이라 표기하지 말고 "랭킹 추이"로 표기할 것.**

### 9. 같은 날 재실행은 덮어쓰기

`main.py`가 오늘 날짜 행을 지우고 다시 쓴다. 히스토리 무결성 유지 목적.

## 파일 구조

- `config.yaml` — 브랜드, 마켓 목록, 상세 조회 정책, 텔레그램 토큰. **커밋 금지** (.gitignore).
  커밋용 템플릿은 `config.example.yaml`.
- `scraper.py` — curl_cffi 수집 + 파싱. `scrape_all(cfg, brands)` 이 진입점.
  실패 시 `BlockedError`. 마켓 하나가 실패해도 나머지는 계속 수집한다.
- `main.py` — 오케스트레이션: 수집 → 브랜드 필터(타이틀 부분일치) → CSV → 전일 diff → 텔레그램.
- `data/history.csv` — `date, market, rank, asin, brand, title, price, currency, rating, reviews,
  sub_bsr_rank, sub_bsr_cat`. 관심 브랜드만 저장. **커밋 대상**(대시보드 데이터 소스).
- `data/asin_cache.json` — ASIN→제목 캐시. 요청 수 억제의 핵심. 커밋 대상.

## 현황 메모 (2026-08-02 실측)

- **medicube이 유럽 5개국을 전부 장악.** IT #1·#2·#4·#5, ES #1·#3·#4·#7, UK #1·#3·#4·#5·#6,
  DE #2·#7, FR #4·#15. US는 #1 + 탑100 내 10개.
- **COSRX·SKIN1004는 6개 마켓 전체 Beauty 리스트 어디에도 안 잡힘.** Anua는 US #88·#100,
  Beauty of Joseon은 UK #28만.
- → 이 브랜드들을 추적하려면 `category`를 **Skin Care 하위 노드**로 내려야 한다.
  전체 Beauty는 샴푸·기저귀·면도기까지 섞여 있어 스킨케어 브랜드가 밀린다.

## 유지보수 가이드

- **파싱 깨짐**: 먼저 `data/debug_*.html`을 확인. `data-client-recs-list`가 살아있으면 순위/ASIN은
  멀쩡한 것이니 상세 셀렉터만 고치면 된다. 이 속성 자체가 사라졌으면 페이지 구조 대개편이므로
  `p13n-desktop-grid` 근처의 새 데이터 속성을 찾을 것.
- **차단 발생**: 실행 시각 ±30분 이동 → `page_delay`/`detail.delay` 증가 → `impersonate`를
  `chrome131` 등으로 고정 → 그래도 안 되면 유료 폴백 제안.
- **유료 폴백(무료가 막혔을 때만)**: Apify 무료 크레딧 월 $5로 월 18,000건이 약 $1.8이라 사실상
  무료. 백필까지 필요해지면 Keepa API(€49/월, `bestsellers` + `product` 엔드포인트, 과거 이력 소급).
  Amazon PA-API는 2026-05-15 폐기되어 대안이 아니다.
- **호출 예절**: 하루 1~2회. 재시도에는 백오프 필수(구현되어 있음). robots.txt는 `/gp/bestsellers`,
  `/zgbs/`, `/dp/<ASIN>`을 막고 있지 않지만, 저빈도 개인 모니터링 전제를 지킬 것.

## 로드맵 (coverage dashboard 통합)

- `history.csv` → 마켓별·브랜드별 순위 추이 라인차트(y축 반전), 가격 변동, 리뷰 수 일간 Δ,
  신규 진입/이탈 마커, 국가별 침투도 히트맵.
- 통화가 섞여 있으므로 가격 비교 시 반드시 환산할 것 (`currency` 컬럼).
- 며칠치 쌓인 뒤 통합할 것 (1일치로는 추이가 없음).

## 히스토리

- 2026-08-01: 최초 설계. 로컬 Playwright 방식 채택.
- 2026-08-02: 유럽 확장 검토 중 **전면 재작성**. Playwright → curl_cffi 전환,
  `data-client-recs-list` 앵커 도입, 6개 마켓 확장, 통화 버그 수정, ASIN 캐시 + 하위 BSR 추가.
  US/UK/DE/FR/IT/ES 전 마켓 실행 검증 완료.
