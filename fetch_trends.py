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
GROUPS = {
    # 리투오 = re2o, 셀르디엠 = CellREDM (한스바이오메드 ECM 스킨부스터)
    "스킨부스터": {
        "naver":  ["리쥬란", "리투오", "셀르디엠"],
        "google": ["Rejuran", "re2o", "CellREDM"],
    },
    "K-뷰티 브랜드": {
        "naver":  ["메디큐브", "달바", "코스알엑스", "셀리맥스"],
        "google": ["medicube", "dalba", "COSRX", "Celimax"],
    },
    # 신제품 단독 추이 — 출시 직후라 최근 1개월을 '일별'로 자세히 (대형 키워드와 섞으면 0으로 눌림)
    # 구글은 전세계로 보면 검색량 부족으로 비니 한국(KR)으로 좁히고, 키워드도 '쿨로아'로 넓혀 신호 확보
    "쿨로아600": {
        "naver":  ["쿨로아600"],
        "google": ["쿨로아"],
        "geo":    "KR",
        "daily":  True,
        "days":   30,
    },
}
GOOGLE_GEO = ""   # "" = 전세계, "KR" = 한국, "US" = 미국

COLORS = ["#5b8def", "#ef4b56", "#22c55e", "#f59e0b", "#8b5cf6"]


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


def fetch_google(keywords, geo=None, n=12, daily=False):
    from pytrends.request import TrendReq
    py = TrendReq(hl="en-US", tz=540)
    py.build_payload(keywords, timeframe=("today 1-m" if daily else "today 12-m"),
                     geo=(GOOGLE_GEO if geo is None else geo))
    df = py.interest_over_time()
    if df.empty:
        raise RuntimeError("응답이 비어있음 (검색량이 너무 적은 키워드일 수 있음)")
    df = df[keywords].tail(n) if daily else df[keywords].resample("MS").mean().tail(n)
    return norm([df[k].tolist() for k in keywords])


def fetch_naver(keywords, n=12, daily=False):
    """네이버 데이터랩. daily=True 면 일 단위(최근 n일), 아니면 월 단위(최근 n개월).
       축을 고정 길이로 맞춰(전역 축을 덮지 않게) 빠진 구간은 0 으로 채운다."""
    import requests
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        return None, None
    end = datetime.date.today()
    start = end - datetime.timedelta(days=(n + 5) if daily else 400)
    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": "date" if daily else "month",
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

    if daily:
        # 최근 n일(오늘 제외). period = YYYY-MM-DD
        axis = [(end - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(n, 0, -1)]
        per_kw = [{d["period"]: d["ratio"] for d in g["data"]} for g in results]
        labels = [f"{int(p[5:7])}/{int(p[8:10])}" for p in axis]
    else:
        # 고정 n개월 축(진행 중인 달 제외). period = YYYY-MM
        first = end.replace(day=1)
        axis = []
        for i in range(n, 0, -1):
            y, m = first.year, first.month - i
            while m <= 0:
                m += 12; y -= 1
            axis.append(f"{y:04d}-{m:02d}")
        per_kw = [{d["period"][:7]: d["ratio"] for d in g["data"]} for g in results]
        labels = [f"{int(p.split('-')[1])}월" for p in axis]

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

    for gname, spec in GROUPS.items():
        kws_nv = spec["naver"]
        kws_gg = spec["google"]
        daily = spec.get("daily", False)
        n = spec.get("days", 30) if daily else spec.get("months", 12)
        print(f"\n[{gname}]  네이버{kws_nv}  구글{kws_gg}  ({n}{'일 일별' if daily else '개월'})")
        g = {"products": kws_nv, "productsGoogle": kws_gg, "daily": daily,
             "months": month_labels(n if not daily else 12)}
        geo = spec.get("geo", GOOGLE_GEO)
        g["geo"] = geo
        try:
            g["google"] = fetch_google(kws_gg, geo=geo, n=n, daily=daily)
            print(f"  구글 트렌드 OK (geo={geo or '전세계'})")
            have["google"] = True
        except Exception as e:
            print("  구글 실패:", str(e)[:80])
            g["google"] = None
        try:
            nv, lb = fetch_naver(kws_nv, n=n, daily=daily)
            if nv:
                g["naver"] = nv
                if lb: g["months"] = lb           # 그룹 자체 축(전역 축을 덮지 않음)
                have["naver"] = True
                print("  네이버 데이터랩 OK")
            else:
                g["naver"] = None
                print("  네이버 키 미설정 -> 건너뜀")
        except Exception as e:
            g["naver"] = None
            print("  네이버 실패:", str(e)[:80])

        # 실패한 출처는 기존에 있던 값을 그대로 보존 (구글이 429로 막혀도 데이터가 사라지지 않음)
        # 단, 표시 기간(길이)이 바뀌었으면 옛 값을 쓰지 않는다(길이 불일치 방지)
        old = prev_groups.get(gname, {})
        old_ok = old.get("months") and len(old["months"]) == n
        if not g["google"] and old_ok and old.get("google") and old.get("productsGoogle") == kws_gg:
            g["google"] = old["google"]
            print("  구글: 기존 값 유지")
        if not g["naver"] and old_ok and old.get("naver") and old.get("products") == kws_nv:
            g["naver"] = old["naver"]
            print("  네이버: 기존 값 유지")

        if not g["google"] and not g["naver"]:
            print("  !! 이 그룹 수집 실패 & 기존 값 없음 -> 건너뜀")
            continue
        # 구글 값이 없으면 네이버 값으로 대체하되, 라벨도 한글로 맞춰 오해를 막는다
        if not g["google"]:
            g["google"] = g["naver"]
            g["productsGoogle"] = kws_nv
        if not g["naver"]:
            g["naver"] = g["google"]
        groups_out[gname] = g
        time.sleep(2)

    if not groups_out:
        print("\n수집된 그룹이 없습니다. index.html 은 그대로 둡니다.")
        return

    trend = {"months": labels, "colors": COLORS[:5],
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
