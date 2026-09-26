# -*- coding: utf-8 -*-
"""
어닝 리비전 트래커 → 커버리지 대시보드 (REVISION) — 두 대시보드에 겹치는 종목만.

리비전 트래커(revision-tracker-5xv.pages.dev)는 증권사 리포트 PDF 에서 추정치를 뽑아
'발표 직전 ↔ 직후' 컨센 이동·증권사별 리비전·부문별 서프라이즈를 계산해 둔다.
네이버 컨센(LIVE)은 평균 하나뿐이라 이런 게 없다. 그래서 겹치는 종목은 그 계산 결과를
그대로 가져와 상세 패널에 붙인다(2026-09-26 · 사용자 요청: 링크만이 아니라 데이터를 가져올 것).

  GET https://revision-tracker-5xv.pages.dev/data.js   → window.RT_DATA = {stocks:[...]}
  공개 정적 파일이라 키가 필요 없다(저장소는 비공개지만 사이트 파일은 열려 있다).

무엇을 가져오나 — 리비전 트래커의 compute.py 가 이미 계산한 값(computed[])만.
  원자료(reports[] 의 추정치·메모)는 안 가져온다. 계산 규칙(PRE/POST 판정·120일 신선도 창·
  부호 가드)은 저쪽 CLAUDE.md 가 원본이고, 여기서 다시 계산하면 두 곳이 어긋난다.

  done  가장 최근 '발표된' 분기 — 실적 vs 증권사 컨센 · 발표 후 영업익 컨센 이동 ·
        증권사별 목표가·리비전 · 부문별 서프라이즈
  next  다가오는 분기 — 증권사 컨센 레벨(화면이 네이버 컨센과 나란히 놓는다) · 부문 컨센

매칭은 종목명, 안 맞으면 종목코드. 겹치는 종목이 0개면 구조가 바뀐 것으로 보고 실패 처리한다.
값이 그대로면 파일을 안 건드린다(Cloudflare 빌드 절약).

⚠ watchdog.LIMITS 에 넣지 않는다 — 리비전 트래커는 사용자가 리포트를 올려야 움직이므로
  몇 주씩 안 바뀌는 게 정상이다. 수집 실패는 runstep 의 health.json 이 잡는다.

  python fetch_revision.py            # 수집·기록
  python fetch_revision.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request

from collector_health import ua, note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
SITE = "https://revision-tracker-5xv.pages.dev"
URL = SITE + "/data.js"
SRC = "리비전 트래커"


def _fetch():
    req = urllib.request.Request(URL, headers=ua(referer=SITE + "/"))
    with urllib.request.urlopen(req, timeout=40) as r:
        s = r.read().decode("utf-8")
    i = s.find("=")
    if not s.lstrip().startswith("window.RT_DATA") or i < 0:
        raise RuntimeError("data.js 형식이 바뀜(window.RT_DATA 없음)")
    return json.loads(s[i + 1:].strip().rstrip(";"))


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});\n" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("REVISION 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def _r(v, nd=4):
    """숫자만 반올림. 부호 가드 라벨('흑전'·'적전'·'N/M')은 문자열 그대로 둔다."""
    return round(v, nd) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def _has_actual(c):
    return any(x.get("actual") is not None for x in c.get("sec3") or [])


def _depth(seg, parents):
    d, p = 0, parents.get(seg)
    while p and d < 5:
        d, p = d + 1, parents.get(p)
    return d


def _done(st, c):
    parents = st.get("segment_parents") or {}
    s2 = c.get("sec2") or {}
    # note(검수 메모)는 안 가져온다 — 종목마다 '실적 요약'이기도 하고 '데이터 검증 기록'이기도 해서
    # 상세 패널에 붙이면 뜻이 들쭉날쭉하다.
    return {
        "q": c["quarter"], "d": c.get("announced"),
        "cnt": {k: (c.get("counts") or {}).get(k) for k in ("pre", "post_brokers", "rev_brokers")},
        "sur": [{"m": x["metric"], "c": _r(x.get("cons"), 3), "a": _r(x.get("actual"), 3),
                 "n": x.get("n"), "s": _r(x.get("surp"))} for x in c.get("sec3") or []],
        "opm": {k: _r((c.get("sec3_opm") or {}).get(v)) for k, v in (("c", "cons"), ("a", "actual"), ("d", "diff"))},
        "rev": [{"p": x["period"], "pre": _r(x.get("pre"), 3), "post": _r(x.get("post"), 3),
                 "r": _r(x.get("rev")), "np": x.get("n_pre"), "nq": x.get("n_post"), "n": x.get("n")}
                for x in c.get("sec1") or []],
        # 증권사별 — 목표가순(리비전 트래커 정렬 그대로). o = 당해·차년 영업익 리비전
        "brk": [{"b": x["broker"], "tp": _r(x.get("tp"), 0), "tc": _r(x.get("tp_chg")),
                 "o": [_r(v) for v in (x.get("op") or [None] * 4)[2:4]]}
                for x in s2.get("rows") or [] if x.get("tp") is not None or x.get("avg") is not None],
        "brkMean": {"tp": _r((s2.get("mean") or {}).get("tp"), 0), "tc": _r((s2.get("mean") or {}).get("tp_chg")),
                    "o": [_r(v) for v in ((s2.get("mean") or {}).get("op") or [None] * 4)[2:4]]},
        # 부문 — 주 축(sec4)만. 보조 축(axes4[1:])은 리비전 트래커 화면에서 본다.
        # e = 실적이 회사 공시가 아니라 발표 후 리뷰 평균(†) — 임시값이지 확정치가 아니다.
        "seg": [{"s": x["seg"], "lv": _depth(x["seg"], parents),
                 "sa": _r(x.get("sales_act"), 3), "ss": _r(x.get("sales_surp")),
                 "oa": _r(x.get("op_act"), 3), "os": _r(x.get("op_surp")),
                 "e": 1 if (x.get("sales_act_est") or x.get("op_act_est")) else 0, "n": x.get("n")}
                for x in c.get("sec4") or []
                if x.get("sales_act") is not None or x.get("op_act") is not None],
    }


def _next(st, c):
    parents = st.get("segment_parents") or {}
    yoy = {x["seg"]: x.get("yoy_cons") for x in c.get("sec5") or []}
    return {
        "q": c["quarter"], "d": c.get("announced"),
        "cnt": {k: (c.get("counts") or {}).get(k) for k in ("pre", "stale")},
        "cons": [{"m": x["metric"], "c": _r(x.get("cons"), 3), "n": x.get("n")} for x in c.get("sec3") or []],
        "seg": [{"s": x["seg"], "lv": _depth(x["seg"], parents),
                 "sc": _r(x.get("sales_cons"), 3), "oc": _r(x.get("op_cons"), 3),
                 "y": _r(yoy.get(x["seg"])), "n": x.get("n")}
                for x in c.get("sec4") or []
                if x.get("sales_cons") is not None or x.get("op_cons") is not None],
    }


def summarize(st, today):
    comps = sorted(st.get("computed") or [], key=lambda c: c.get("announced") or "")
    done = [c for c in comps if _has_actual(c)]
    upc = [c for c in comps if not _has_actual(c) and (c.get("announced") or "") >= today]
    reps = st.get("reports") or []
    out = {
        "code": st.get("code"),
        # 축 이름만(설명 꼬리는 리비전 트래커 화면 몫) — "지역별 — 국내는 두 기준…" → "지역별"
        "axis": re.split(r"\s+—\s+|\s*\(", st.get("segment_axis") or "")[0][:24],
        "nRep": len(reps),
        "nBrk": len({r.get("broker") for r in reps}),
        "last": max((r.get("date") or "" for r in reps), default=""),
    }
    if done:
        out["done"] = _done(st, done[-1])
    if upc:
        out["next"] = _next(st, upc[0])
    return out


def main():
    html = open(HTML, encoding="utf-8").read()
    data = _const(html, "DATA") or {}
    names = {r["name"] for r in data.get("records") or []}
    live = _const(html, "LIVE") or {}
    code2name = {v.get("code"): k for k, v in (live.get("stocks") or {}).items() if v.get("code")}

    try:
        rt = _fetch()
    except Exception as e:
        msg = f"data.js 수집 실패: {str(e)[:120]}"
        print(f"[리비전] {msg} — 기존 데이터 보존")
        note_health(SRC, msg)
        sys.exit(1)

    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    stocks = {}
    for st in rt.get("stocks") or []:
        nm = st.get("name") if st.get("name") in names else code2name.get(st.get("code"))
        if not nm or nm not in names:
            continue
        stocks[nm] = summarize(st, today)

    if not stocks:
        msg = f"겹치는 종목 0개(리비전 {len(rt.get('stocks') or [])}종목) — 이름·코드 구조가 바뀐 듯"
        print(f"[리비전] {msg}")
        note_health(SRC, msg)
        sys.exit(1)
    note_health(SRC, None)

    for nm, s in stocks.items():
        d = s.get("done") or {}
        op = next((x for x in d.get("sur") or [] if x["m"] == "영업이익"), {})
        print(f"  {nm:<8} 리포트 {s['nRep']:>2}건·{s['nBrk']:>2}사 · 최신 {s['last']} · "
              f"{d.get('q', '-')} 영업익 서프 {op.get('s')} · 다음 {(s.get('next') or {}).get('q', '-')}")

    old = _const(html, "REVISION") or {}
    if old.get("stocks") == stocks:
        print(f"[리비전] 변동 없음({len(stocks)}종목) — 파일 유지")
        return

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
           "site": SITE, "stocks": stocks}
    if "--dry-run" in sys.argv:
        print(f"(dry-run · {len(stocks)}종목 · {len(json.dumps(out, ensure_ascii=False)):,}자)")
        return
    open(HTML, "w", encoding="utf-8").write(_put(html, "REVISION", out))
    print(f"[OK] REVISION 갱신 · {len(stocks)}종목")


if __name__ == "__main__":
    main()
