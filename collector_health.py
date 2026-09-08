# -*- coding: utf-8 -*-
"""수집기 공통 — 차단을 덜 당하고, 당하면 티가 나게.

왜 따로 뺐나
  같은 코드가 fetch_screens.py 에만 있었다. 정작 요청량이 제일 많은 건
  네이버 금융(refresh_live.py)인데 거기엔 아무 보호도 없었다 —
  고정 UA `Mozilla/5.0`, 지터 없는 0.2초 간격, 실패해도 아무 기록이 안 남는다.
  막히면 화면 숫자가 옛날 값에 조용히 멈춰 있고 아무도 모른다.

무엇을 하나
  ua()          체인/사이트마다 조금씩 다른, 실제로 쓰이는 브라우저 헤더
  nap(초)       요청 간격을 ±25% 흔든다. 정확히 같은 간격이 차단 규칙에 더 잘 걸린다
  looks_blocked 403/429/캡차처럼 '막힌 것'으로 볼 실패인지 판정
  note_health   health.json 에 기록 → watchdog.py 가 읽어 별도 텔레그램 알림
  guard         위 셋을 묶은 컨텍스트 매니저(성공하면 기록을 지운다)

health.json 은 워크플로가 커밋하므로 실행 사이에 남는다.
"""
import re
import datetime
import json
import os
import random
import time

KST = datetime.timezone(datetime.timedelta(hours=9))
HEALTH = "health.json"

# 실제로 통용되는 최신 데스크톱 브라우저 UA. 'Mozilla/5.0' 만 달랑 보내면
# 봇이라고 광고하는 셈이라 차단 목록에 가장 먼저 오른다.
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
]
# 한 번 실행하는 동안은 UA 를 바꾸지 않는다. 요청마다 갈아 끼우면
# 같은 IP 에서 브라우저가 계속 바뀌는 꼴이라 오히려 더 수상하다.
_UA = random.choice(_UAS)


def ua(referer=None, extra=None, doc=False):
    """브라우저처럼 보이는 헤더 한 벌. referer 를 주면 같이 붙인다.

    doc=True 는 **HTML 페이지를 받을 때** 쓴다. 기본값은 `Accept: application/json` 이라
    XHR 처럼 보이는데, 사람이 주소창에 치면 절대 나오지 않는 조합이다 —
    WAF 가 이걸로 봇을 가른다.

    실측(2026-09-08): 올리브영 `getBestList.do` 가 기본 헤더로는 **403**,
    doc 헤더(Accept: text/html + Sec-Fetch-* + sec-ch-ua + Upgrade-Insecure-Requests)로는
    **200 · 373KB** 였다. 헤더 한 줄 차이로 열리고 닫힌다.
    새로 뚫을 사이트가 403 을 주면 이걸 먼저 시도해 볼 것."""
    h = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "identity",       # 수동 gzip 해제를 피한다
        "Connection": "keep-alive",
    }
    if doc:
        h.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                      "image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })
    if referer:
        h["Referer"] = referer
        if doc:
            h["Sec-Fetch-Site"] = "same-origin"   # referer 가 있는데 none 이면 앞뒤가 안 맞는다
    if extra:
        h.update(extra)
    return h


def due_today(const_name, after_hour=0, html_path="public/index.html"):
    """오늘치를 **아직 못 받았고** 지금이 after_hour 시(KST) 이후인가.

    왜 '슬롯'이 아니라 '조건'인가 (2026-09-08)
      게임머니 재시도를 `KST 15시` 한 시각에만 걸었더니, 하필 그날 워커가 15시 슬롯을
      걸러서(GitHub 백업 cron 은 3~12시간 밀린다) 재시도가 통째로 없었다.
      실측: 그날 refresh 회차가 08·09·10·11·12·13·14·16·18 — 15시와 17시가 빠졌다.
      CLAUDE.md 가 이미 경고한 '한쪽만 두면 그게 죽는 날 데이터가 없다' 를 그대로 밟은 것이다.

      시각으로 고정하지 말고 **'오늘 아직 없으면 그 뒤 아무 회차나 잡는다'** 로 두면,
      슬롯 하나가 빠져도 다음 회차가 이어받는다. 이미 받은 날은 조용히 건너뛴다.

      after_hour 는 '이 시각 전에는 소스가 어제치를 안 준다' 는 뜻이다.
      예: Steam 은 UTC 일자가 닫혀야 해서 KST 09시 이후여야 한다.
    """
    try:
        html = open(html_path, encoding="utf-8").read()
    except Exception:
        return True                      # 못 읽으면 일단 시도한다
    now = datetime.datetime.now(KST)
    if now.hour < after_hour:
        return False
    m = re.search(r'const %s\s*=\s*\{\s*"asOf"\s*:\s*"([^"]+)"' % re.escape(const_name), html)
    if not m:
        return True                      # 블록이 아직 없으면 받아야 한다
    return m.group(1)[:10] != now.date().isoformat()


def trend_daily_stale(html_path="public/index.html"):
    """트렌드 **일별 축의 끝이 어제가 아닌가.** (2026-09-09)

    due_today 로는 못 잡는다 — 05시 events.yml 이 TREND.asOf 를 이미 오늘 날짜로 찍어 두기
    때문이다. 문제는 '오늘 받았나'가 아니라 **'어제치까지 왔나'** 다.

    네이버 데이터랩은 전일치를 KST 05시엔 아직 안 준다(실측 2026-09-09: 05:56·07:40 둘 다
    9/7 까지 · 전날 16:53 실행은 9/7=전일까지). 게다가 fetch_naver 가 러너(UTC)의 오늘로
    '진행 중인 날'을 잘라, KST 새벽엔 어제(KST)가 '오늘(UTC)'로 버려지기까지 했다.
    그래서 05시 수집만 두면 화면은 **늘 이틀 전**에서 끝났다.

    refresh.yml 이 매 회차 이걸 보고, 축 끝이 어제가 아니면
    `fetch_trends.py --naver-only --if-stale` 을 돌린다(그쪽이 1요청으로 공개 여부를 먼저 찍는다).
    """
    try:
        html = open(html_path, encoding="utf-8").read()
    except Exception:
        return True
    m = re.search(r'^const TREND\s*=\s*(\{.*?\});?\s*$', html, re.M | re.S)
    if not m:
        return True
    try:
        groups = json.loads(m.group(1)).get("groups", {})
    except Exception:
        return True
    y = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)
    ylab = f"{y.month}/{y.day}"
    for g in groups.values():
        # 네이버가 갱신하는 일별 축만 본다 — 구글·얀덱스 전용(only=google)은 --naver-only 가 안 건드린다
        for d in (g, g.get("alt") or {}):
            if d.get("freq") == "date" and d.get("months") and d.get("only") != "google":
                return d["months"][-1] != ylab
    return True


def nap(sec):
    """요청 간격 — ±25% 흔들어 준다. 규칙적인 간격이 차단 규칙에 더 잘 걸린다."""
    time.sleep(max(0.0, sec) * (0.75 + 0.5 * random.random()))


def looks_blocked(e):
    """차단으로 볼 만한 실패인가 — 403/429/캡차/연결거부."""
    s = f"{type(e).__name__} {e}".lower()
    return any(k in s for k in ("403", "429", "captcha", "forbidden",
                                "too many", "unusual traffic", "timed out",
                                "refused", "reset"))


def note_health(src, msg):
    """차단·오류를 health.json 에 남긴다. watchdog.py 가 읽어 별도 알림을 쏜다.
       사용자가 매일 로그를 볼 수는 없으니, 막히면 봇이 먼저 말해 줘야 한다.
       msg=None 이면 그 소스의 기록을 지운다(정상 복귀)."""
    now = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    try:
        d = json.load(open(HEALTH, encoding="utf-8"))
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    if msg is None:
        d.pop(src, None)
    else:
        d[src] = {"t": now, "msg": str(msg)[:200]}
    try:
        json.dump(d, open(HEALTH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


class guard:
    """with guard("네이버 금융"): ... — 실패하면 기록하고, 성공하면 지운다.

    예외는 삼키지 않는다. 호출부의 기존 흐름(try/except, || echo 등)을 그대로 둔다.
    '조금 실패'는 기록하지 않는다 — 종목 하나가 빠진 것과 통째로 막힌 건 다르다.
    부분 실패는 fail() 로 세다가 임계치를 넘을 때만 남긴다.
    """

    def __init__(self, src, tol=0):
        self.src, self.tol, self.n = src, tol, 0

    def fail(self, e):
        """부분 실패 1건. 허용치를 넘으면 그때 기록한다."""
        self.n += 1
        if self.n > self.tol:
            note_health(self.src, f"{self.n}건 실패 · {type(e).__name__}: {e}")

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if ev is not None:
            note_health(self.src, f"{type(ev).__name__}: {ev}")
        elif self.n <= self.tol:
            note_health(self.src, None)      # 정상 — 묵은 기록을 지운다
        return False


def deploy_slot():
    """지금이 Cloudflare 를 새로 빌드시킬 시각인가.

    Pages 는 푸시 1건 = 빌드 1건이고 무료 한도가 월 500건이다(저장소를 공개해도 이 한도는 그대로 —
    공개로 무제한이 되는 건 GitHub Actions 분뿐이다).
    수집은 매시간 하되 배포는 여기 정한 시각에만 — 사이 회차 커밋은 '[CI Skip]' 을 달아 두면
    다음 배포가 그 데이터까지 같이 싣는다.

    2026-08-07: 시세를 매시간 수집으로 바꾸면서 배포도 '평일 장중 매시간(09~16시)'으로 넓혔다.
    09~16 매시간 = 8회/일 × 22일 ≈ 176건/월. 다른 수집기까지 합쳐 월 ~300건으로 500 한도 안.
    (장 개시 09:00 ~ 마감 15:30, 16시는 마감 직후 확정치까지. 08·17·18시 수집분은 [CI Skip] 후
     다음 배포에 실린다. 시세가 안 바뀌는 밤·주말을 매시간 배포하면 한도만 태운다.)
    """
    now = datetime.datetime.now(KST)
    if now.weekday() >= 5:
        return now.hour in (12, 20)           # 주말은 장이 안 서니 두 번이면 충분
    return 9 <= now.hour <= 16                 # 평일 장중 매시간 배포


if __name__ == "__main__":
    print("UA:", _UA)
    print("배포 슬롯:", deploy_slot())
    print("차단 판정:", looks_blocked(Exception("HTTP Error 429: Too Many Requests")))
