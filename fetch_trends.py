# -*- coding: utf-8 -*-
"""
트렌드 수집 -> 대시보드(index.html)의 TREND 데이터 갱신
--------------------------------------------------------
사용법:
    pip install pytrends requests
    python fetch_trends.py

네이버 데이터랩(권장, 국내 검색은 훨씬 정확)을 쓰려면
https://developers.naver.com/apps/#/register 에서
  - 애플리케이션 이름: 아무거나
  - 사용 API: "데이터랩(검색어트렌드)" 체크
등록 후 나오는 Client ID / Secret 을 아래 두 줄에 붙여넣으세요.
키가 없으면 구글 트렌드 값으로 양쪽을 채웁니다.

주의: 구글 트렌드는 요청이 잦은 IP를 429로 막습니다.
      회사망/VPN에서 막히면 개인 네트워크에서 실행해 보세요.
"""
import json, re, time, sys, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"

# ── 네이버 데이터랩 키 ─────────────────────────────────────
# 우선순위: 환경변수(GitHub Actions) > secrets_local.py(로컬)
import os
try:
    from secrets_local import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
except ImportError:
    NAVER_CLIENT_ID = NAVER_CLIENT_SECRET = ""
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", NAVER_CLIENT_ID)
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET)

# ── 비교 그룹 ──────────────────────────────────────────────
# 네이버(국내)는 한글, 구글(전세계)은 영문 키워드를 쓴다.
# 국내 브랜드는 한글 검색량이 구글에선 거의 안 잡히기 때문.
# freq = date(일별) / week(주별) / month(월별) · n = 표시 구간 수 (기본: 주52)
GROUPS = {
    # 리투오 = re2o, 셀르디엠 = CellREDM (한스바이오메드 ECM 스킨부스터)
    "스킨부스터": {
        "naver":  ["리쥬란", "리투오", "셀르디엠"],
        "google": ["Rejuran", "re2o", "CellREDM"],
        "freq":   "week",
    },
    # 달바 구글 키워드는 d'Alba(정식 표기). 'dalba' 로 조회하면 이탈리아 Alba 지역·성씨와
    # 섞인다 — 두 표기의 상관이 0.28 로 사실상 다른 것을 잡고 있었다.
    "K-뷰티 브랜드": {
        "naver":  ["메디큐브", "달바", "코스알엑스", "셀리맥스"],
        "google": ["medicube", "d'Alba", "COSRX", "Celimax"],
        "freq":   "week",
    },
    # 국산 변신로봇 완구 IP 3파전 — 헬로카봇·메탈카드봇(초이락) vs 또봇(영실업).
    # 국내 검색이라 네이버가 실신호, 구글 글로벌은 거의 0(영문명은 참고용).
    # 구글은 '영문명 전세계'가 잡음이었던 것이지 구글 자체가 문제는 아니었다.
    # 한글 키워드 + geo=KR 로 보면 네이버와 상관 0.45 로 서로 다른 신호를 준다
    # (예전 '메탈카드봇 국가별'의 한국 계열이 이 조합이었다 — 그걸 여기로 합쳤다).
    "변신로봇 IP": {
        "naver":  ["헬로카봇", "메탈카드봇", "또봇"],
        "google": ["헬로카봇", "메탈카드봇", "또봇"],
        "geo":    "KR",
        "freq":   "week",
    },
    # 같은 3파전을 러시아에서. 얀덱스는 절대 검색수를 주므로 세 IP 의 크기를
    # 진짜로 비교할 수 있다(구글 트렌드는 상대값이라 불가).
    # 현지 표기: 또봇=Тобот, 헬로카봇=Карбот(러시아 방영명 «Карбот»)
    # 메탈카드봇은 플랫폼마다 정규화가 다르다 —
    #   얀덱스는 띄어쓴 «Метал Кард Бот» 만 잡고(붙여쓰면 52주 중 1주),
    #   와일드베리즈는 반대로 붙여쓴 «Металкардбот» 이 더 많이 잡힌다.
    "변신로봇 IP 러시아": {
        "yandex": ["Тобот", "Карбот", "Метал Кард Бот"],
        "labels": ["또봇", "헬로카봇", "메탈카드봇"],
        "freq":   "week",
    },
    # '메탈카드봇 국가별' 은 없앴다.
    #   러시아 계열은 '변신로봇 IP 러시아'(얀덱스 3파전)와 상관 1.00 으로 완전 중복이었다.
    #   한국 계열(구글 geo=KR)은 네이버와 상관 0.45 로 다른 신호였지만,
    #   경쟁사 없이 혼자 보는 것보다 '변신로봇 IP' 의 구글 쪽으로 합치는 편이 낫다.
    # 신제품 단독 추이 — 출시 직후라 최근 30일을 '일별'로 자세히 (대형 키워드와 섞으면 0으로 눌림)
    # 구글은 전세계로 보면 검색량 부족으로 비니 한국(KR)으로 좁히고, 키워드도 '쿨로아'로 넓혀 신호 확보
    # 구글은 뺐다 — 30일 중 8일만 값이 잡혀 0 이 줄줄이 찍혔다.
    # 출시 직후 국내 신제품이라 구글 검색량 자체가 임계 미만이다. 네이버만 본다.
    "쿨로아600": {
        "naver":  ["쿨로아600"],
        "freq":   "date",
        "n":      30,
    },
    # 티니핑 국가별 관심도 — 나라마다 현지 명칭+현지 geo 로 따로 조회(구글만).
    # 각국 자체 0~100 스케일이라 '추이(언제 떴나)' 비교용, 절대 크기 비교는 불가.
    # 중국은 구글이 차단돼 데이터가 거의 없음(참고). 유럽은 데이터가 가장 많은 영국 기준.
    "티니핑 국가별": {
        "geos": [
            # 한국은 홈마켓 — 네이버 데이터랩(국내 검색 실신호). 각국 자체 0~100이라 추이 비교용.
            {"label": "한국",      "geo": "KR", "kw": "티니핑", "src": "naver"},
            {"label": "미국",      "geo": "US", "kw": "Teenieping"},
            # ティーニーピン(장음 표기)은 검색량 0. 현지에선 ティニピン 으로 줄여 쓴다.
            {"label": "일본",      "geo": "JP", "kw": "ティニピン"},
            # 중국은 뺐다 — 구글이 차단된 시장이라 52주 중 2주만 잡혔다(사실상 0).
            # 본토 검색은 바이두 지수뿐인데 공식 API 가 없어 수집 경로가 없다.
            # 억지로 두면 '중국 관심도 0' 으로 오독된다. 중국은 수출 데이터로 볼 것.
            # 구글 러시아로는 52주 중 8주만 잡혔다. 얀덱스가 러시아 점유가 높아 신호가 진하다.
            {"label": "러시아",    "geo": "RU", "kw": "Тинипин", "src": "yandex"},
            {"label": "유럽(영국)", "geo": "GB", "kw": "Teenieping"},
        ],
        "freq": "week",
    },
    # ── 게임 ──────────────────────────────────────────────
    # 신작 출시가 주가에 직결되는 섹터라 검색 스파이크가 곧 이벤트다.
    "배틀그라운드(크래프톤)": {
        "naver":  ["배틀그라운드"],
        "google": ["PUBG"],
        "freq":   "week",
    },
    # 검은사막=서비스 중, 붉은사막=미출시 신작이라 뉴스 때만 튄다.
    "펄어비스 IP": {
        "naver":  ["검은사막", "붉은사막"],
        "google": ["Black Desert", "Crimson Desert"],
        "freq":   "week",
    },
    # '니케'는 나이키(한글로는 나이키라 충돌은 적지만)와 섞일 수 있어 결과를 봐야 한다.
    "시프트업 IP": {
        "naver":  ["니케", "스텔라블레이드"],
        "google": ["NIKKE", "Stellar Blade"],
        "freq":   "week",
    },
    # 아이온2(NC) 국가별 — 한국·대만 2025-11-19 출시, 북미·남미·유럽·일본은 2026-09 예정.
    # 표기: 한국은 한글, 그 외는 라틴. 기간은 출시 직후부터(아래 AION_WEEKS 자동 계산)
    "아이온2 국가별": {
        "geos": [
            {"label": "한국(출시)",  "geo": "KR", "kw": "아이온2"},
            {"label": "대만(출시)",  "geo": "TW", "kw": "AION2"},
            {"label": "일본",       "geo": "JP", "kw": "AION2"},
            {"label": "미국",       "geo": "US", "kw": "AION 2"},
            {"label": "독일",       "geo": "DE", "kw": "AION 2"},
            {"label": "브라질",     "geo": "BR", "kw": "AION 2"},
        ],
        "freq": "week",
        "n": 13,        # 최근 3개월(13주)
    },
    # 아스트라에 오라티오(NC) — 디나미스 원 개발, 「블루아카이브」 원 개발진(박병림)이 세운 스튜디오.
    # 2026-04-30 정식명 공개(옛 Project AT), 6/23 신규 PV, 8월 테스터 모집, 8/15~16 코믹마켓 108 출전.
    # 배경이 1889년 도쿄인 서브컬처 RPG 라 실질 타깃은 일본이다. 한국 검색만 보면 규모를 놓친다.
    #
    # 커뮤니티(트위터·루리웹·디시)를 긁는 방법도 있으나 택하지 않았다.
    #   트위터 API 는 유료(월 $200~)이고, 루리웹·디시는 공식 API 가 없어
    #   HTML 구조가 바뀔 때마다 조용히 0 이 된다. 게시글 수는 이벤트일에만 튀어
    #   '관심의 크기'가 아니라 '글 쓴 사람 수'를 재는 것에 가깝다.
    # 검색량은 무료·안정적이고 다른 그룹과 같은 잣대라 우선 이걸로 간다.
    #
    # 일본은 뺐다 — 표기 문제가 아니라 검색량이 구글 트렌드 임계에 못 미친다.
    #   26주 중 0 아닌 주:  アスオラ 2 · アストラエ・オラティオ 6 · アストラエオラティオ 6
    #                      Astrae Oratio 1 · ディナミス・ワン 1
    #   다섯 표기를 다 재 봤고 전부 바닥이다. 미출시라 절대량 자체가 없다.
    #   억지로 두면 '일본 관심 0' 으로 오독된다. 출시일이 잡히면 그때 다시 넣을 것.
    #   (네이버 데이터랩은 임계가 낮아 국내는 26주 중 14주가 잡힌다.)
    # 기간: 정식명 공개(2026-04-30) 전은 전부 0 이라 26주만 본다.
    "아스트라에 오라티오": {
        "naver": ["아스트라에 오라티오"],
        "freq": "week",
        "n": 26,
    },
}
GOOGLE_GEO = ""   # "" = 전세계, "KR" = 한국, "US" = 미국

# 시리즈 색 (최대 8개 — 국가별 그룹이 6개까지 늘어남). Rose Pine 계열의 구분 잘 되는 색
COLORS = ["#c4a7e7", "#f6c177", "#9ccfd8", "#eb6f92", "#a6da95", "#3e8fb0", "#ea9a97", "#c9a227"]


def month_labels(n=12):
    today = datetime.date.today().replace(day=1)
    out = []
    for i in range(n - 1, -1, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12; y -= 1
        out.append(f"{m}월")
    return out


def norm(series):
    """여러 시계열을 그룹 전체 최댓값 기준 0~100으로 정규화"""
    mx = max((max(s) for s in series if s), default=0) or 1
    return [[round(v / mx * 100) for v in s] for s in series]


# 표시 단위: date=일별, week=주별, month=월별
GTF = {"date": "today 3-m", "week": "today 12-m", "month": "today 12-m"}

# trendspy 공유 인스턴스 — request_delay 로 요청 간격을 벌려 429(자가 rate-limit) 방지
_GT = None
def _gt():
    global _GT
    if _GT is None:
        from trendspy import Trends
        _GT = Trends(request_delay=3.5)   # 요청 간격 — 낮추면 429 발생
    return _GT


def _google_df(keywords, geo, freq):
    """구글 트렌드 원자료(DataFrame) — 429 시 백오프 재시도."""
    for attempt in range(3):
        try:
            return _gt().interest_over_time(
                keywords, timeframe=GTF.get(freq, "today 12-m"), geo=geo)
        except Exception:
            if attempt < 2:
                time.sleep(20 * (attempt + 1)); continue
            raise


def fetch_google(keywords, geo=None, freq="week", n=52):
    """구글 트렌드. trendspy 사용 — pytrends 는 구글의 2025 봇차단(429)에 낡아서 깨지므로 교체함."""
    df = _google_df(keywords, GOOGLE_GEO if geo is None else geo, freq)
    if df is None or df.empty:
        raise RuntimeError("응답이 비어있음 (검색량이 너무 적은 키워드일 수 있음)")
    if "isPartial" in df.columns:                 # 진행 중인 구간 제외
        df = df[~df["isPartial"].astype(bool)]
    df = df[keywords]
    if freq == "month":
        df = df.resample("MS").mean()
    df = df.tail(n)
    labels = [f"{d.month}월" if freq == "month" else f"{d.month}/{d.day}" for d in df.index]
    return norm([df[k].tolist() for k in keywords]), labels


YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
WORDSTAT_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/dynamics"


def _period_end(freq, today=None):
    """Wordstat 은 toDate 가 '해당 기간의 마지막 날'이어야 한다.
       주별이면 직전 일요일, 월별이면 지난달 말일 (진행 중인 구간은 빼는 셈)."""
    d = today or datetime.date.today()
    if freq == "month":
        return d.replace(day=1) - datetime.timedelta(days=1)
    if freq == "week":
        return d - datetime.timedelta(days=d.weekday() + 1)      # 월=0 … 직전 일요일
    return d - datetime.timedelta(days=1)


def fetch_yandex(phrase, freq="week", n=52, raw=False):
    """얀덱스 Wordstat 시계열 (Yandex Cloud Search API v2).
       러시아는 얀덱스 점유가 구글보다 높아 같은 키워드도 신호가 훨씬 진하다.
       키가 없으면 None -> 호출한 쪽에서 그 국가만 건너뛴다.
       반환값은 구글 계열과 섞어 그리므로 0~100 으로 맞춰 돌려준다."""
    if not (YANDEX_API_KEY and YANDEX_FOLDER_ID):
        return None, None
    import requests
    period = {"date": "PERIOD_DAILY", "week": "PERIOD_WEEKLY",
              "month": "PERIOD_MONTHLY"}.get(freq, "PERIOD_WEEKLY")
    end = _period_end(freq)
    # 시작일도 기간 경계에 맞아야 한다. 주별은 반드시 월요일이어야 하고
    # (아니면 400 "The from field value should be Monday"), 월별은 1일이어야 한다.
    # end 가 일요일이므로 7의 배수를 빼면 또 일요일이 된다 -> 하루를 덜 빼서 월요일로 맞춘다.
    if freq == "week":
        start = end - datetime.timedelta(days=n * 7 - 1)
    elif freq == "month":
        y, mth = end.year, end.month - (n - 1)
        while mth <= 0:
            y -= 1; mth += 12
        start = datetime.date(y, mth, 1)
    else:
        start = end - datetime.timedelta(days=n - 1)
    # fromDate/toDate 는 protobuf Timestamp 라 RFC3339 여야 한다.
    # 'YYYY-MM-DD' 로 보내면 400 (Invalid time format) 이 떨어진다.
    ts = lambda d: d.strftime("%Y-%m-%dT00:00:00Z")
    body = {"folderId": YANDEX_FOLDER_ID, "phrase": phrase, "period": period,
            "fromDate": ts(start), "toDate": ts(end)}
    r = requests.post(WORDSTAT_URL, json=body, timeout=30,
                      headers={"Authorization": f"Api-Key {YANDEX_API_KEY}"})
    if r.status_code != 200:
        # 오류 본문이 여러 줄 JSON 이라 그대로 찍으면 로그에서 잘린다 -> 한 줄로 눌러 남긴다
        raise RuntimeError(f"Wordstat {r.status_code}: "
                           + " ".join(r.text.split())[:300])
    d = r.json()
    # 실제 응답 키는 results — [{"date":"2025-07-21T00:00:00Z","count":"4124","share":0.00017}, ...]
    rows = d.get("results") or d.get("dynamics") or d.get("items") or []
    pairs = []
    for it in rows:
        # 카운트는 protobuf int64 라 문자열로 온다
        v = it.get("count", it.get("value", it.get("count7", 0)))
        dt = it.get("date") or it.get("period") or ""
        try:
            pairs.append((str(dt), float(v)))
        except (TypeError, ValueError):
            continue
    if not pairs:
        raise RuntimeError(f"Wordstat 응답에 시계열이 없음: {str(d)[:200]}")
    pairs = pairs[-n:]
    labels = []
    for dt, _ in pairs:
        p = dt[:10].split("-")
        labels.append(f"{int(p[1])}월" if freq == "month" else f"{int(p[1])}/{int(p[2])}")
    # raw=True 면 절대 검색수를 그대로 준다.
    # 여러 키워드를 견줄 땐 각자 0~100 으로 눌러버리면 크기 비교가 사라지므로,
    # 호출한 쪽에서 다 모은 뒤 공통 최대값으로 한 번에 정규화해야 한다.
    if raw:
        return [v for _, v in pairs], labels
    top = max(v for _, v in pairs) or 1
    return [round(v / top * 100) for _, v in pairs], labels


def fetch_yandex_group(keywords, freq="week", n=52):
    """얀덱스로 여러 키워드를 한 번에 견준다.

       얀덱스는 절대 검색수를 주므로, 구글과 달리 '누가 더 큰가'를 진짜로 비교할 수 있다.
       단 키워드마다 따로 0~100 으로 눌러버리면 그 장점이 사라진다.
       그래서 전부 원본으로 받아 두고 공통 최대값 하나로 같이 정규화한다."""
    raws, labels = [], None
    for kw in keywords:
        try:
            v, lb = fetch_yandex(kw, freq, n, raw=True)
        except Exception as e:
            print(f"    {kw}: 얀덱스 실패({str(e)[:80]})")
            raws.append(None); continue
        if not v:
            raws.append(None); continue
        raws.append(v)
        if labels is None:
            labels = lb
    if labels is None:
        raise RuntimeError("모든 키워드 조회 실패")
    L = min([len(labels)] + [len(v) for v in raws if v])
    labels = labels[-L:]
    top = max((max(v[-L:]) for v in raws if v), default=0) or 1
    peak = int(top)
    series = [([round(x / top * 100) for x in v[-L:]] if v else [0] * L) for v in raws]
    return series, labels, peak


def fetch_google_geos(geos, freq="week", n=52):
    """같은 대상을 나라마다 '현지 명칭 + 현지 geo'로 따로 조회.
       각국은 자체 0~100 으로 정규화되므로 국가 간 절대 비교는 불가, 추이(모양)만 비교.
       spec 에 "src":"yandex" 가 있으면 그 나라만 얀덱스 Wordstat 으로 받는다."""
    series, labels = [], None
    for spec in geos:
        if spec.get("src") == "yandex":
            try:
                s, lb = fetch_yandex(spec["kw"], freq, n)
                if s:
                    series.append(s)
                    if labels is None:
                        labels = lb
                    continue
                print(f"    {spec['label']}: 얀덱스 키 없음 - 건너뜀")
            except Exception as e:
                print(f"    {spec['label']}: 얀덱스 실패({e}) - 건너뜀")
            series.append(None)
            continue
        if spec.get("src") == "naver":       # 한국은 네이버 데이터랩(국내 검색 실신호)
            try:
                nv, lb = fetch_naver([spec["kw"]], freq, n)
                if nv and nv[0]:
                    series.append(nv[0])
                    if labels is None:
                        labels = lb
                    continue
                print(f"    {spec['label']}: 네이버 값 없음 - 건너뜀")
            except Exception as e:
                print(f"    {spec['label']}: 네이버 실패({str(e)[:60]}) - 건너뜀")
            series.append(None)
            continue
        try:
            df = _google_df([spec["kw"]], spec["geo"], freq)
        except Exception as e:
            print(f"    {spec['label']}: 구글 실패({str(e)[:60]}) - 건너뜀")
            series.append(None); continue
        # 검색량이 너무 적으면 구글이 그 키워드 컬럼을 아예 빼고 준다.
        # 그대로 df[kw] 하면 KeyError 로 그룹 전체가 죽으므로 여기서 걸러낸다.
        if df is None or df.empty or spec["kw"] not in df.columns:
            print(f"    {spec['label']}: 검색량 부족 - 건너뜀")
            s = None
        else:
            if "isPartial" in df.columns:
                df = df[~df["isPartial"].astype(bool)]
            col = df[spec["kw"]]
            if freq == "month":
                col = col.resample("MS").mean()
            col = col.tail(n)
            if labels is None:
                labels = [f"{d.month}월" if freq == "month" else f"{d.month}/{d.day}"
                          for d in col.index]
            s = [round(v) for v in col.tolist()]     # 구글 원본 0~100 유지(재정규화 안 함)
        series.append(s)
    if labels is None:
        raise RuntimeError("모든 국가 조회 실패")
    # 실패(None)한 국가는 0 으로, 길이는 공통으로 맞춘다
    L = min([len(labels)] + [len(s) for s in series if s])
    labels = labels[-L:]
    series = [(s[-L:] if s else [0] * L) for s in series]
    return series, labels


def fetch_naver(keywords, freq="week", n=52):
    """네이버 데이터랩. freq = date(일)/week(주)/month(월). 최근 n구간(진행 중 구간 제외)."""
    import requests
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        return None, None
    end = datetime.date.today()
    span = {"date": n + 5, "week": n * 7 + 14, "month": 400}.get(freq, 400)
    start = end - datetime.timedelta(days=span)
    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": freq,
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords],
    }
    r = requests.post(
        "https://openapi.naver.com/v1/datalab/search",
        headers={"X-Naver-Client-Id": NAVER_CLIENT_ID,
                 "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                 "Content-Type": "application/json"},
        data=json.dumps(body), timeout=20)
    r.raise_for_status()
    results = r.json()["results"]
    per_kw = [{d["period"]: d["ratio"] for d in g["data"]} for g in results]

    if freq == "month":
        # 고정 n개월 축(진행 중인 달 제외)
        first = end.replace(day=1)
        axis = []
        for i in range(n, 0, -1):
            y, m = first.year, first.month - i
            while m <= 0:
                m += 12; y -= 1
            axis.append(f"{y:04d}-{m:02d}")
        per_kw = [{k[:7]: v for k, v in m.items()} for m in per_kw]
        labels = [f"{int(p.split('-')[1])}월" for p in axis]
    else:
        # 키워드 합집합 축에서 진행 중 구간 제외 후 최근 n개
        axis = sorted({p for m in per_kw for p in m})
        today = end.strftime("%Y-%m-%d")
        if freq == "date":
            axis = [p for p in axis if p < today]                       # 오늘 제외
        else:  # week — 시작일이 최근 7일 이내면 진행 중인 주로 보고 제외
            cut = (end - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            axis = [p for p in axis if p <= cut]
        axis = axis[-n:]
        labels = [f"{int(p[5:7])}/{int(p[8:10])}" for p in axis]

    series = [[m.get(p, 0) for p in axis] for m in per_kw]
    return norm(series), labels


def load_existing():
    """index.html 에 이미 들어있는 TREND 를 읽어온다 (실패한 출처의 값을 보존하기 위함)"""
    try:
        html = open(HTML_PATH, encoding="utf-8").read()
        m = re.search(r"const TREND=(\{.*?\});", html, re.S)
        return json.loads(m.group(1)) if m else None
    except Exception:
        return None


def main():
    groups_out = {}
    labels = month_labels(12)
    have = {"naver": False, "google": False}
    prev = load_existing()
    prev_groups = (prev or {}).get("groups", {})

    FREQ_KO = {"date": "일별", "week": "주별", "month": "월별"}
    for gname, spec in GROUPS.items():
        freq = spec.get("freq", "week")
        n = spec.get("n", {"date": 30, "week": 52, "month": 12}[freq])

        # ── 얀덱스 비교 그룹 (러시아, 절대 검색수라 크기 비교 가능) ──────
        if "yandex" in spec:
            kws = spec["yandex"]; labs = spec.get("labels", kws)
            print(f"\n[{gname}]  얀덱스{kws}  ({FREQ_KO[freq]} {n})")
            g = {"products": labs, "productsGoogle": labs, "freq": freq,
                 "geo": "RU", "months": [], "only": "google",
                 "srcOf": ["얀덱스"] * len(kws)}
            try:
                g["google"], g["months"], peak = fetch_yandex_group(kws, freq=freq, n=n)
                g["naver"] = g["google"]      # 렌더 호환용(화면은 only 를 보고 구글칸만 쓴다)
                g["peak"] = peak              # 100 이 실제 몇 건인지 — 각주로 띄운다
                have["google"] = True
                nz = [sum(1 for v in s if v > 0) for s in g["google"]]
                print(f"  얀덱스 OK · 0아닌값 {nz} · 최대 {peak:,}건/주")
            except Exception as e:
                print("  얀덱스 실패:", str(e)[:120])
                old = prev_groups.get(gname) or {}
                if old.get("google"):
                    g["google"] = old["google"]; g["naver"] = old["google"]
                    g["months"] = old.get("months", []); g["peak"] = old.get("peak")
                    print("  기존 값 유지")
                else:
                    print("  !! 건너뜀"); continue
            groups_out[gname] = g
            continue

        # ── 국가별 그룹 (구글만, 나라마다 현지명+현지 geo) ──────────────
        if "geos" in spec:
            labs = [x["label"] for x in spec["geos"]]
            print(f"\n[{gname}]  국가별 {[x['geo'] for x in spec['geos']]}  ({FREQ_KO[freq]} {n})")
            g = {"products": labs, "productsGoogle": labs, "freq": freq,
                 "geo": "multi", "multi": True, "months": [],
                 # 해외 검색이라 네이버 데이터가 없다. 예전엔 구글 값을 네이버 자리에
                 # 복사해 둬서 화면에서 '네이버'를 눌러도 구글 값이 나왔다.
                 # only 를 달아 두면 화면에서 출처 전환 버튼 자체를 감춘다.
                 "only": "google",
                 # 계열별 실제 출처 — 러시아=얀덱스, 한국=네이버. '구글'로 뭉뚱그리면 거짓말이 된다
                 "srcOf": [{"yandex": "얀덱스", "naver": "네이버"}.get(x.get("src"), "구글")
                           for x in spec["geos"]]}
            try:
                g["google"], g["months"] = fetch_google_geos(spec["geos"], freq=freq, n=n)
                g["naver"] = g["google"]          # 렌더 호환용(화면은 only 를 보고 구글만 쓴다)
                have["google"] = True
                nz = [sum(1 for v in s if v > 0) for s in g["google"]]
                print(f"  국가별 OK · 0아닌값 {nz} · 출처 {g['srcOf']}")
            except Exception as e:
                print("  구글 국가별 실패:", str(e)[:80])
                old = prev_groups.get(gname, {})
                if old.get("google"):
                    g.update({k: old[k] for k in ("google", "naver", "months") if k in old})
                    print("  기존 값 유지")
                else:
                    continue
            groups_out[gname] = g
            time.sleep(6)
            continue

        # 출처를 한쪽만 쓰는 그룹이 있다.
        #   naver 키 없음  = 해외 전용(현지어 키워드)
        #   google 키 없음 = 국내 전용(구글에선 잡음만 잡히는 국내 브랜드)
        kws_nv = spec.get("naver") or spec.get("google")
        kws_gg = spec.get("google") or spec.get("naver")
        # 어느 출처가 진짜인지는 스펙이 정한다.
        # 수집 결과로 판단하면, 아래 '기존 값 유지' 폴백이 지난번에 복사해 둔
        # 가짜 구글 계열을 되살려 놓아 단일 출처인 걸 놓친다(only 가 안 붙는다).
        spec_only = ("naver" if "google" not in spec
                     else "google" if "naver" not in spec else None)
        print(f"\n[{gname}]  네이버{kws_nv}  구글{kws_gg}  ({FREQ_KO[freq]} {n})")
        g = {"products": kws_nv, "productsGoogle": kws_gg, "freq": freq, "months": []}
        geo = spec.get("geo", GOOGLE_GEO)
        g["geo"] = geo
        gg_labels = None
        try:
            # google 키가 없는 국내 전용 그룹은 구글을 조회하지 않는다.
            # 국내 브랜드를 영문·전세계로 조회하면 무관한 검색이 섞여 잡음만 남는다.
            if "google" in spec:
                g["google"], gg_labels = fetch_google(kws_gg, geo=geo, freq=freq, n=n)
                print(f"  구글 트렌드 OK (geo={geo or '전세계'})")
                have["google"] = True
            else:
                g["google"] = None
        except Exception as e:
            print("  구글 실패:", str(e)[:80])
            g["google"] = None
        try:
            # naver 키가 없는 해외 전용 그룹은 국내 검색을 조회하지 않는다.
            # 일본어·키릴 키워드를 데이터랩에 넣으면 엉뚱한 값이 잡힐 수 있다.
            nv, lb = fetch_naver(kws_nv, freq=freq, n=n) if "naver" in spec else (None, None)
            if nv:
                g["naver"] = nv
                if lb: g["months"] = lb           # 그룹 자체 축(네이버 우선)
                have["naver"] = True
                print("  네이버 데이터랩 OK")
            else:
                g["naver"] = None
                print("  네이버 키 미설정 -> 건너뜀")
        except Exception as e:
            g["naver"] = None
            print("  네이버 실패:", str(e)[:80])
        if not g["months"] and gg_labels:
            g["months"] = gg_labels               # 네이버 실패 시 구글 라벨 사용

        # 실패한 출처는 기존에 있던 값을 그대로 보존 (구글이 429로 막혀도 데이터가 사라지지 않음)
        old = prev_groups.get(gname, {})
        if not g["google"] and old.get("google") and old.get("productsGoogle") == kws_gg \
                and old.get("freq") == freq:
            g["google"] = old["google"]
            if not g["months"]: g["months"] = old.get("months", [])
            print("  구글: 기존 값 유지")
        if not g["naver"] and old.get("naver") and old.get("products") == kws_nv \
                and old.get("freq") == freq:
            g["naver"] = old["naver"]
            print("  네이버: 기존 값 유지")

        if not g["google"] and not g["naver"]:
            print("  !! 이 그룹 수집 실패 & 기존 값 없음 -> 건너뜀")
            continue
        # 한쪽 출처가 없으면 다른 쪽 값으로 채우되, 어느 쪽이 진짜인지 only 에 남긴다.
        # 그래야 화면에서 없는 출처 버튼을 눌러 같은 그래프를 보는 일이 없다.
        if not g["google"]:
            g["google"] = g["naver"]
            g["productsGoogle"] = kws_nv
            g["only"] = "naver"
        elif not g["naver"]:
            g["naver"] = g["google"]
            g["only"] = "google"
        if spec_only:
            g["only"] = spec_only          # 스펙이 단일 출처면 그게 최종
            if spec_only == "naver":
                g["productsGoogle"] = kws_nv

        # 축 길이 정합 — 출처마다 길이가 다르면 뒤에서 잘라 공통 길이로 맞춘다
        L = min([len(g["months"] or [999])] +
                [len(s) for s in g["naver"]] + [len(s) for s in g["google"]])
        g["months"] = (g["months"] or [])[-L:]
        g["naver"] = [s[-L:] for s in g["naver"]]
        g["google"] = [s[-L:] for s in g["google"]]

        groups_out[gname] = g
        time.sleep(6)      # 그룹 간 간격 — 구글 rate limit 완화

    if not groups_out:
        print("\n수집된 그룹이 없습니다. index.html 은 그대로 둡니다.")
        return

    trend = {"months": labels, "colors": COLORS,
             "sources": have, "groups": groups_out}

    # 값이 그대로면 파일을 건드리지 않는다 (불필요한 커밋·배포 방지)
    if prev is not None and prev.get("groups") == groups_out and prev.get("months") == labels:
        print("\n[SKIP] 트렌드 변동 없음 - index.html 그대로 둠")
        return

    js = "const TREND=" + json.dumps(trend, ensure_ascii=False) + ";"
    html = open(HTML_PATH, encoding="utf-8").read()
    new, n = re.subn(r"const TREND=\{.*?\};", js, html, count=1, flags=re.S)
    if not n:
        print("\n[!] TREND 블록을 찾지 못했습니다. 아래를 직접 붙여넣으세요:\n")
        print(js)
        return
    open(HTML_PATH, "w", encoding="utf-8").write(new)
    print(f"\n[OK] index.html 갱신 완료 - 그룹 {len(groups_out)}개 "
          f"(네이버 {'O' if have['naver'] else 'X'} / 구글 {'O' if have['google'] else 'X'})")


if __name__ == "__main__":
    main()
