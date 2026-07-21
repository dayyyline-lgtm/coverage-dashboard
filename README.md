# Coverage Dashboard — 소비재/엔터/게임/호텔 유니버스

애널리스트 신주현 · 커버리지 29종목 리서치 대시보드

- **시세·멀티플·증권사 리포트·IR 일정** → 네이버 금융에서 자동 수집
- **연간/분기 실적, 밸류에이션** → 유니버스 엑셀 모델에서 추출
- **매시간 자동 갱신** (GitHub Actions → Cloudflare Pages 자동 배포)

---

## 처음 한 번만: 웹사이트로 올리기

계정 2개(둘 다 무료)가 필요합니다. **총 15분** 정도 걸립니다.

### 1단계 — GitHub 가입하고 저장소 만들기 (5분)

1. <https://github.com/signup> 에서 가입 (이메일·비밀번호·아이디)
2. 로그인 후 우측 상단 **`+` → New repository**
3. 설정
   - Repository name: `coverage-dashboard`
   - **Private 선택** ← 리서치 자료이므로 반드시 Private
   - 나머지는 기본값, **Create repository** 클릭
4. 다음 화면에 나오는 명령어 대신, **이 폴더(`asd`)에서** 아래를 실행하세요.
   `<아이디>` 부분만 본인 GitHub 아이디로 바꾸면 됩니다.

```bash
git init
git add .
git commit -m "커버리지 대시보드 최초 배포"
git branch -M main
git remote add origin https://github.com/<아이디>/coverage-dashboard.git
git push -u origin main
```

> 비밀번호를 물으면 GitHub 비밀번호가 아니라 **Personal Access Token**이 필요합니다.
> <https://github.com/settings/tokens> → Generate new token (classic) →
> `repo` 체크 → 생성된 토큰을 비밀번호 자리에 붙여넣으세요.

### 2단계 — Cloudflare Pages 연결 (5분)

1. <https://dash.cloudflare.com/sign-up> 에서 가입
2. 좌측 메뉴 **Workers & Pages → Create → Pages → Connect to Git**
3. GitHub 계정 연결 승인 → `coverage-dashboard` 저장소 선택
4. 빌드 설정 — **아무것도 건드리지 말고 비워두세요**
   - Framework preset: `None`
   - Build command: (비움)
   - Build output directory: `/`
5. **Save and Deploy**

1~2분 뒤 `https://coverage-dashboard-xxx.pages.dev` 주소가 나옵니다. **끝입니다.**

### 3단계 — API 키 등록 + 자동 갱신 확인 (2분)

`secrets_local.py` 는 보안상 GitHub에 올라가지 않으므로,
DART 키는 저장소 설정에 따로 넣어야 합니다.

1. 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
2. Name: `DART_API_KEY` / Secret: (DART에서 받은 40자리 키) → Add secret

그다음 **Actions** 탭에서 각각 **Run workflow** 로 즉시 테스트:

| 워크플로 | 주기 | 하는 일 | 필요한 Secret |
|---|---|---|---|
| `시세 자동 갱신` | 평일 07~18시 **매시**<br>주말 4시간마다 | 주가·시총·PER/PBR·배당·리포트 | 없음 |
| `이벤트 캘린더 갱신 (DART)` | 평일 아침 07:30 | 공시·IR 일정 | `DART_API_KEY` |
| `트렌드 갱신` | 매주 월 08:00 | 네이버·구글 검색 트렌드 | `NAVER_CLIENT_ID`<br>`NAVER_CLIENT_SECRET` |

> 구글 트렌드는 서버 IP가 종종 429로 차단됩니다. 그때는 **기존 구글 값을 유지**하고
> 네이버만 갱신하므로 데이터가 사라지지 않습니다. 구글 값을 확실히 새로 받으려면
> 개인 PC에서 `python fetch_trends.py` 를 돌리고 push 하세요.

성공하면 이후로는 손댈 일이 없습니다.

> 시세를 24시간 내내 갱신하려면 `.github/workflows/refresh.yml` 의
> `cron: "0 0-9 * * 1-5"` 를 `cron: "0 * * * *"` 로 바꾸세요.

---

## 사이트를 수정하고 싶을 때

### 기본 3단계 (모든 수정에 공통)

```bash
git pull                       # ① 먼저 당겨오기 (자동갱신 봇이 올린 내용 받기)
#  ... 파일 수정 ...
git add -A
git commit -m "무엇을 바꿨는지"
git push                       # ② 올리면 1~2분 뒤 사이트 자동 반영
```

> ⚠️ **`git pull` 을 꼭 먼저 하세요.**
> 자동갱신 봇이 매시간 커밋을 올리기 때문에, 그냥 push 하면
> `rejected - remote contains work that you do not have` 에러가 납니다.
> 이미 에러가 났다면 `git pull --rebase` 후 다시 `git push`.

### 어디를 고치면 되나

| 바꾸고 싶은 것 | 파일 | 위치 |
|---|---|---|
| 화면·표·색상·섹션 | `public/index.html` | 해당 부분 직접 |
| **Top/2nd/Beta Pick 수동 지정** | `public/index.html` | `PICK_OVERRIDE` |
| **이벤트 직접 추가** | `public/index.html` | `MANUAL_EVENTS` |
| **트렌드 키워드·그룹** | `fetch_trends.py` | `GROUPS` |
| **갱신 시각** | `.github/workflows/*.yml` | `cron` |
| 커버리지 종목·추정치 | 유니버스 엑셀 | 수정 후 `rebuild_from_excel.py` |

### 예시 — 트렌드 키워드 바꾸기

`fetch_trends.py` 의 `GROUPS` 를 이렇게 고치고:
```python
GROUPS = {
    "스킨부스터":   ["리쥬란", "리투오", "셀르디엠"],
    "톡신":        ["나보타", "제오민", "보툴렉스"],   # ← 새 그룹 추가
}
```
```bash
python fetch_trends.py
git add -A && git commit -m "트렌드 키워드 추가" && git push
```

### 되돌리고 싶을 때

```bash
git log --oneline           # 커밋 목록 확인
git revert <커밋번호>        # 특정 변경만 취소 (안전)
```
또는 Cloudflare → Deployments → 예전 배포의 `⋯` → **Rollback**

---

## 평소 사용법

### 커버리지 종목을 바꿨을 때
엑셀에서 종목을 추가/삭제/수정한 뒤:

```bash
python rebuild_from_excel.py    # 엑셀 → 대시보드 재생성
git add -A && git commit -m "유니버스 변경" && git push
```

푸시하면 Cloudflare가 자동으로 재배포합니다.

### 트렌드 실데이터 채우기
구글 트렌드는 서버 IP가 차단되므로 **개인 PC에서** 실행해야 합니다.

```bash
pip install pytrends requests
python fetch_trends.py
git add -A && git commit -m "트렌드 갱신" && git push
```

네이버 데이터랩까지 쓰려면 `fetch_trends.py` 상단의
`NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` 에 키를 넣으세요.
키 발급: <https://developers.naver.com/apps/#/register> (사용 API에서 **데이터랩** 체크,
웹 서비스 URL은 `http://localhost` 로 두면 됩니다)

### 수동 갱신
```bash
python refresh_live.py     # 시세·멀티플·리포트 (30초)
python fetch_events.py     # DART 공시·IR 일정 (1분)
```

### API 키 관리
키는 `secrets_local.py` 에 있고 **.gitignore 로 커밋이 차단**되어 있습니다.
GitHub Actions에서 쓰려면 저장소 Secrets에 `DART_API_KEY` 를 등록하세요.
키가 노출됐다면 각 사이트에서 재발급하면 됩니다.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `index.html` | 대시보드 본체 (데이터가 안에 내장된 단일 파일) |
| `refresh_live.py` | 시세·멀티플·리포트 수집 → `LIVE` 블록 갱신 |
| `fetch_events.py` | DART 공시·IR 일정 → `DART_EVENTS` 블록 갱신 |
| `rebuild_from_excel.py` | 유니버스 엑셀 → `DATA`/`FIN` 블록 재생성 |
| `fetch_trends.py` | 네이버/구글 트렌드 → `TREND` 블록 갱신 |
| `secrets_local.py` | API 키 (**커밋 안 됨**) |
| `.github/workflows/` | 시세 매시간 · 이벤트 매일 자동 갱신 |

## 데이터 출처

- 시세·시가총액·PER/PBR·배당수익률·52주·외국인·컨센서스·리포트·IR일정 — 네이버 금융
- 환율 — open.er-api.com
- 연간/분기 실적, 당사 추정치, 목표주가, Pick — 자체 유니버스 모델

> 본 페이지는 리서치 참고용이며 투자 권유가 아닙니다.
