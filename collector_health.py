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


def ua(referer=None, extra=None):
    """브라우저처럼 보이는 헤더 한 벌. referer 를 주면 같이 붙인다."""
    h = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "identity",       # 수동 gzip 해제를 피한다
        "Connection": "keep-alive",
    }
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    return h


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

    Pages 는 푸시 1건 = 빌드 1건이고 무료 한도가 월 500건이다.
    수집은 자주 하되 배포는 시세가 실제로 바뀌는 슬롯에서만 한다 —
    사이 회차 커밋은 '[CI Skip]' 을 달아 두면 다음 배포가 그 데이터까지 같이 싣는다.
    """
    now = datetime.datetime.now(KST)
    if now.weekday() >= 5:
        return now.hour in (12, 20)           # 주말은 장이 안 서니 두 번이면 충분
    return now.hour in (8, 10, 12, 14, 16, 18)


if __name__ == "__main__":
    print("UA:", _UA)
    print("배포 슬롯:", deploy_slot())
    print("차단 판정:", looks_blocked(Exception("HTTP Error 429: Too Many Requests")))
