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
# secrets_local.py (깃에 안 올라감)에서 읽어옵니다.
try:
    from secrets_local import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
except ImportError:
    NAVER_CLIENT_ID = NAVER_CLIENT_SECRET = ""

# ── 비교 그룹: 원하는 만큼 추가/수정 (그룹당 키워드 2~5개) ──
GROUPS = {
    "스킨부스터":     ["리쥬란", "리투오", "셀르디엠"],
    "K-뷰티 브랜드":  ["메디큐브", "달바", "코스알엑스", "셀리맥스"],
}

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


def fetch_google(keywords):
    from pytrends.request import TrendReq
    py = TrendReq(hl="ko-KR", tz=540)
    py.build_payload(keywords, timeframe="today 12-m", geo="KR")
    df = py.interest_over_time()
    if df.empty:
        raise RuntimeError("응답이 비어있음 (검색량이 너무 적은 키워드일 수 있음)")
    df = df[keywords].resample("MS").mean().tail(12)
    return norm([df[k].tolist() for k in keywords])


def fetch_naver(keywords, n_months=12):
    """네이버 데이터랩. 월 축을 공통으로 맞추고, 진행 중인 달은 제외."""
    import requests
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        return None, None
    end = datetime.date.today()
    start = end - datetime.timedelta(days=400)
    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": "month",
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

    # 키워드마다 빠진 달이 있으므로 period 기준으로 합집합 축을 만든다
    per_kw = [{d["period"][:7]: d["ratio"] for d in g["data"]} for g in results]
    axis = sorted({p for m in per_kw for p in m})
    cur = end.strftime("%Y-%m")
    axis = [p for p in axis if p != cur]          # 진행 중인 달 제외
    axis = axis[-n_months:]

    series = [[m.get(p, 0) for p in axis] for m in per_kw]
    labels = [f"{int(p.split('-')[1])}월" for p in axis]
    return norm(series), labels


def main():
    groups_out = {}
    labels = month_labels(12)
    have = {"naver": False, "google": False}

    for gname, kws in GROUPS.items():
        print(f"\n[{gname}] {kws}")
        g = {"products": kws}
        try:
            g["google"] = fetch_google(kws)
            print("  구글 트렌드 OK")
            have["google"] = True
        except Exception as e:
            print("  구글 실패:", str(e)[:80])
            g["google"] = None
        try:
            nv, lb = fetch_naver(kws)
            if nv:
                g["naver"] = nv
                if lb: labels = lb
                have["naver"] = True
                print("  네이버 데이터랩 OK")
            else:
                g["naver"] = None
                print("  네이버 키 미설정 -> 건너뜀")
        except Exception as e:
            g["naver"] = None
            print("  네이버 실패:", str(e)[:80])

        if not g["google"] and not g["naver"]:
            print("  !! 이 그룹 수집 실패 -> 건너뜀")
            continue
        # 한쪽만 성공하면 다른 쪽도 같은 값으로 채우되, sources 로 실제 출처를 표시
        g["google"] = g["google"] or g["naver"]
        g["naver"] = g["naver"] or g["google"]
        groups_out[gname] = g
        time.sleep(2)

    if not groups_out:
        print("\n수집된 그룹이 없습니다. index.html 은 그대로 둡니다.")
        return

    trend = {"months": labels, "colors": COLORS[:5],
             "sources": have, "groups": groups_out}
    js = "const TREND=" + json.dumps(trend, ensure_ascii=False) + ";"

    html = open(HTML_PATH, encoding="utf-8").read()
    new, n = re.subn(r"const TREND=\{.*?\n\};", js, html, count=1, flags=re.S)
    if not n:
        print("\n[!] TREND 블록을 찾지 못했습니다. 아래를 직접 붙여넣으세요:\n")
        print(js)
        return
    open(HTML_PATH, "w", encoding="utf-8").write(new)
    print(f"\n[OK] index.html 갱신 완료 - 그룹 {len(groups_out)}개 실데이터 반영")


if __name__ == "__main__":
    main()
