# -*- coding: utf-8 -*-
"""K뷰티 국면 주간 브리핑 — KBPH 블록(public/index.html)을 읽어 텔레그램 한 통 (2026-10-22).

사용자: "주간으로 업데이트하면 브리핑 메시지 텔레로 보내 주는 것도 가능한가" → 일요일 아침 국면 수집(크롬 세션, 10/24 월→일)이 KBPH 를 올리면
`.github/workflows/phase_brief.yml` 이 이걸 부른다. 화면(app.js renderCosPhase)과 같은 식을 파이썬으로 다시 푼다:
  아마존(미국·유럽 5개국·일본·캐나다) — 가로 비중 YoY(최근 3개월 vs 작년 같은 3개월) × 세로 비중 QoQ(바로 앞 3개월) → 네 칸
  틱톡샵(미국 공식 샵)              — 비중 QoQ × MoM (2026-04 부터라 전년 없음 · 4월 앞부분은 추정)
  합산(아마존 미국 + 틱톡샵)          — 브랜드마다 두 채널 판매량을 더한 비중 QoQ × MoM
비중 = 바구니(추적 브랜드 전부, 비상장 포함) 판매량 중 그 브랜드 몫. 끝 달 = 두 채널 공통 마지막 완결 달(진행 중인 달은 안 쓴다).
칸이 바뀐 브랜드는 지난번 보낸 칸(kbeauty/data/phase/brief_state.json)과 견준다.

  python3 kbeauty/phase_brief.py          # 메시지만 찍는다
  python3 kbeauty/phase_brief.py --send   # 텔레그램(TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID) — 같은 KBPH asOf 는 한 번만
  python3 kbeauty/phase_brief.py --due    # 국면 수집할 차례면 종료코드 0(이번 주 일요일 이후 원재료가 없을 때) · 아니면 1
"""
import argparse
import datetime as dt
import json
import math
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
INDEX = HERE.parent / "public" / "index.html"
STATE = HERE / "data" / "phase" / "brief_state.json"
SITE = "https://coverage-dashboard.pages.dev/#amazon"
MK = [("uk", "영국"), ("de", "독일"), ("fr", "프랑스"), ("it", "이탈리아"), ("es", "스페인"), ("jp", "일본"), ("ca", "캐나다")]
EU = ["uk", "de", "fr", "it", "es"]
QS = {"성장 가속": "가속", "성장 둔화": "둔화", "반등 중": "반등", "하락 지속": "하락"}
ORD = ["성장 가속", "성장 둔화", "반등 중", "하락 지속"]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def kst_now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))


def load():
    s = INDEX.read_text(encoding="utf-8")
    m = re.search(r"^const KBPH = (.*);$", s, re.M)
    if not m:
        raise SystemExit("index.html 에 KBPH 가 없다")
    return json.loads(m.group(1))


def qn(x, y):
    return ("성장 가속" if y >= 100 else "성장 둔화") if x >= 100 else ("반등 중" if y >= 100 else "하락 지속")


def ssum(a, i0, i1):
    return sum((a[j] or 0) for j in range(max(0, i0), i1 + 1) if j < len(a))


RI = {"c": {1: [0], 3: [0, 1, 2]}, "p": {1: [1], 3: [3, 4, 5]}, "y": {1: [6], 3: [6, 7, 8]}}


class Chan:
    """한 채널 — U[k] = 브랜드별 월 판매량(M 순서) · e = 끝 달 인덱스.
    W(2026-10-27 · 화면 kbPhChan 과 같은 식) = 달력과 무관한 창 — W["b"][k][a] = 기준점 a 의 [0·30·60·90·120·150(·365·395·425)일 전에 끝나는 30일] 판매량.
    있으면 판정 = 최근 3달(90일) vs 직전 3달 · 조짐 = 최근 1달(30일) vs 직전 1달 · YoY = 작년 같은 창 — 기준점 0(수집일)만 쓴다."""

    def __init__(self, M, U, e, R=None, W=None):
        self.M, self.U, self.e = M, U, e
        self.tot = [sum((U[k][j] or 0) for k in U) for j in range(len(M))]
        # R[k] = [최근 30일, 직전 30일(, 작년 같은 30일, 작년 그 앞 30일)] — 있으면 '조짐'(세로)을 MoM 대신 이걸로(2026-10-24)
        self.R = R if R and sum(r[0] for r in R.values()) > 0 and sum(r[1] for r in R.values()) > 0 else None
        ok = bool(W and W.get("b") and all(W["b"].get(k) for k in U) and sum((W["b"][k][0] or [0])[0] for k in U) > 0)
        self.W = W if ok else None
        if self.W:
            self.R = None

    def wv(self, k, ix):
        r = self.W["b"][k][0]
        return sum((r[i] if i < len(r) else 0) or 0 for i in ix)

    def rcmp(self, k, w, back):
        """기준점 0 에서 최근 w달 비중 ÷ (back=w 직전 w달 · back=12 작년 같은 w달) × 100."""
        ok = self.W.get("ok3" if w == 3 else "ok1")
        if ok and not ok[0]:
            return None
        ci, pi = RI["c"][w], (RI["y"][w] if back == 12 else RI["p"][w])
        c, p = self.wv(k, ci), self.wv(k, pi)
        tc, tp = sum(self.wv(x, ci) for x in self.U), sum(self.wv(x, pi) for x in self.U)
        if not tc or not tp:
            return None
        sc, sp = c / tc, p / tp
        return {"sc": sc, "sp": sp, "y": 100 * sc / sp if sp > 0 and sc > 0 else None, "g": c / p - 1 if p > 0 else None, "gb": tc / tp - 1}

    def r30(self, k, back=1):
        """최근 30일 비중 ÷ 직전 30일 비중(back=1) 또는 작년 같은 30일(back=2) × 100."""
        if not self.R or k not in self.R:
            return None
        i = 1 if back == 1 else 2
        tc = sum(r[0] for r in self.R.values()); tp = sum((r[i] if len(r) > i else 0) for r in self.R.values())
        r = self.R[k]
        if len(r) <= i or not tc or not tp:
            return None
        sc, sp = r[0] / tc, r[i] / tp
        return {"sc": sc, "sp": sp, "y": 100 * sc / sp if sp > 0 and sc > 0 else None,
                "g": r[0] / r[i] - 1 if r[i] > 0 else None, "gb": tc / tp - 1}

    def cmp(self, k, w, back):
        if self.W and w in (1, 3) and back in (w, 12):
            return self.rcmp(k, w, back)
        e = self.e
        if e - back - w + 1 < 0:
            return None
        u = self.U[k]
        c, p = ssum(u, e - w + 1, e), ssum(u, e - back - w + 1, e - back)
        tc, tp = ssum(self.tot, e - w + 1, e), ssum(self.tot, e - back - w + 1, e - back)
        sc, sp = (c / tc if tc else 0), (p / tp if tp else 0)
        return {"sc": sc, "sp": sp, "y": 100 * sc / sp if sp > 0 and sc > 0 else None,
                "g": c / p - 1 if p > 0 else None, "gb": tc / tp - 1 if tp > 0 else None}

    def rows(self, yoy):
        out = {}
        for k in self.U:
            a = self.cmp(k, 3, 12 if yoy else 3)   # 가로
            b = self.cmp(k, 3, 3) if yoy else (self.r30(k) if self.R else self.cmp(k, 1, 1))   # 세로 — 30일 창이 있으면 최근 30일 vs 직전 30일
            if not a or not b or a["y"] is None or b["y"] is None:
                continue
            out[k] = {"s": a["sc"], "x": a["y"], "y": b["y"], "q": qn(a["y"], b["y"]), "g": (a["g"], b["g"]), "sp": a["sp"]}
        return out

    def base(self, yoy):
        a = self.cmp(next(iter(self.U)), 3, 12 if yoy else 3)
        return a["gb"] if a else None


def last_full(months, partial):
    return len(months) - 2 if partial and months and months[-1] == partial else len(months) - 1


def build(d):
    M = d["months"]
    B = d["b"]
    tt = d.get("tt") or {}
    TM = tt.get("months") or []
    la = M[last_full(M, d.get("partial"))]
    lt = TM[last_full(TM, tt.get("partial"))] if TM else la
    end = min(la, lt)                       # 두 채널 공통 마지막 완결 달(화면 kbPhEnd 와 같다)
    e = M.index(end)
    res = {"end": end, "M": M}
    # 3달·1달 창(2026-10-27) — 아마존 = 브랜드별 rw(기준점 0 = Keepa 수집일) · 틱톡샵 = tt rw(끝날) · 나라 수집일이 미국과 10일 넘게 어긋나면 합산에 창을 안 쓴다
    rwT = (d.get("rw") or {}).get("t")
    WA = {k: b["rw"] for k, b in B.items() if b.get("rw")} if rwT else {}
    res["rwT"] = rwT
    # 아마존 미국
    RA = {k: b["r30"] for k, b in B.items() if b.get("r30")}
    res["us"] = Chan(M, {k: b["u"] for k, b in B.items()}, e, RA or None, {"b": WA} if WA else None)
    res["r30t"] = d.get("r30t")
    # 틱톡샵
    if TM and end in TM:
        et = TM.index(end)
        RT = {k: b["r30"] for k, b in tt["b"].items() if b.get("r30")} if tt.get("r30") else {}
        TW = tt.get("rw") or {}
        WT = {k: b["rw"] for k, b in tt["b"].items() if b.get("rw")}
        res["tt"] = Chan(TM, {k: b["mu"] for k, b in tt["b"].items()}, et, RT or None, {**TW, "b": WT} if WT and TW else None)
        res["ttR30"] = tt.get("r30")
        res["ttRw"] = TW.get("t") if WT else None
        ai = [M.index(m) if m in M else -1 for m in TM]
        keys = set(B) | set(tt["b"])
        mkb = [x["b"] for x in (d.get("mk") or {}).values()]
        amzUS = lambda k, i: (B[k]["u"][i] or 0) if k in B else 0
        amzAll = lambda k, i: amzUS(k, i) + sum((mb[k]["u"][i] or 0) for mb in mkb if k in mb)
        tq = lambda k, j: (tt["b"][k]["mu"][j] or 0) if k in tt["b"] else 0
        S = {k: [(amzUS(k, ai[j]) if ai[j] >= 0 else 0) + tq(k, j) for j in range(len(TM))] for k in keys}        # 미국 합산(아마존 미국 + 틱톡샵)
        SA = {k: [(amzAll(k, ai[j]) if ai[j] >= 0 else 0) + tq(k, j) for j in range(len(TM))] for k in keys}      # 전 지역 합산(2026-10-22 · 아마존 8개국 + 틱톡샵)
        # 합산 30일 창 = 아마존(그 지역들) + 틱톡샵 — 아마존 30일 창이 있을 때만(없으면 MoM 으로 남는다)
        def rsum(withmk):
            if not RA or not RT:
                return None
            out = {}
            for k in keys:
                a = list(RA.get(k, [0, 0])[:2])
                if withmk:
                    for mb in mkb:
                        if k in mb and mb[k].get("r30"):
                            a = [a[0] + mb[k]["r30"][0], a[1] + mb[k]["r30"][1]]
                t = RT.get(k, [0, 0])
                out[k] = [a[0] + t[0], a[1] + t[1]]
            return out
        mk_r30 = all(x.get("r30") for mb in mkb for x in mb.values())

        # 합산 창 — 아마존(그 지역들) + 틱톡샵 기준점을 날짜로 짝짓는다(화면 kbRwSum 과 같게 · 14일 간격 · 7일 안)
        def wsum(withmk):
            if not WA or not WT or not TW.get("t"):
                return None
            mks = d.get("mk") or {}
            if withmk and any(not x.get("asOf") or abs((dt.date.fromisoformat(x["asOf"]) - dt.date.fromisoformat(rwT)).days) > 10 for x in mks.values()):
                return None
            dd = (dt.date.fromisoformat(rwT) - dt.date.fromisoformat(TW["t"])).days
            sh = math.ceil(dd / 14 - 0.5)   # 간격이 같으면 더 최근 짝(화면 kbRwSum 과 같게)
            if abs(dd - sh * 14) > 7:
                return None
            pr = [(a, a - sh) for a in range(7) if 0 <= a - sh < 7]
            if not pr:
                return None
            a0, b0 = pr[0]
            out = {}
            for k in keys:
                av = list((WA.get(k) or [[0] * 9] * 7)[a0][:6])
                if withmk:
                    for mb in mkb:
                        if k in mb:
                            if not mb[k].get("rw"):
                                return None
                            av = [x + y for x, y in zip(av, mb[k]["rw"][a0][:6])]
                tv = (WT.get(k) or [[0] * 6] * 7)[b0]
                out[k] = [[x + y for x, y in zip(av, tv)]]
            return {"b": out, "ok3": [TW["ok3"][b0]] if TW.get("ok3") else None, "ok1": [TW["ok1"][b0]] if TW.get("ok1") else None}
        if mkb:
            res["all"] = Chan(TM, SA, et, rsum(True) if mk_r30 else None, wsum(True))
        res["sum"] = Chan(TM, S, et, rsum(False), wsum(False))
        res["mest"] = tt.get("mest") or []
        res["ttEnd"] = tt.get("end")
    # 다른 아마존 시장
    mk = d.get("mk") or {}
    for code, _ in MK:
        if code in mk:
            mw = {k: x["rw"] for k, x in mk[code]["b"].items() if x.get("rw")}
            res[code] = Chan(M, {k: x["u"] for k, x in mk[code]["b"].items()}, e, None, {"b": mw} if mw else None)
    have = [m for m in EU if m in mk]
    if have:
        U = {}
        for m in have:
            for k, x in mk[m]["b"].items():
                a = U.setdefault(k, [0] * len(M))
                for j in range(len(M)):
                    a[j] += x["u"][j] or 0
        EW = {}
        if all(all(x.get("rw") for x in mk[m]["b"].values()) for m in have):
            for m in have:
                for k, x in mk[m]["b"].items():
                    a = EW.setdefault(k, [[0] * 9 for _ in range(7)])
                    EW[k] = [[p + q for p, q in zip(r1, r2)] for r1, r2 in zip(a, x["rw"])]
        res["eu"] = Chan(M, U, e, None, {"b": EW} if EW else None)
    return res


def name(d, k):
    b = d["b"].get(k) or {}
    return b.get("ko") or k


def tag(d, k):
    b = d["b"].get(k) or {}
    return "*" if b.get("co") else ""


def pct(v):
    return "—" if v is None else f"{'+' if v >= 100 else ''}{round(v - 100)}%"


def pctg(v):
    return "—" if v is None else f"{'+' if v >= 0 else ''}{round(v * 100)}%"


def shp(v):
    v *= 100
    return f"{v:.1f}%" if v >= 1 else f"{v:.2f}%"


def mlab(M, e, w):
    m = lambda i: int(M[i][5:])
    r = lambda a, b: f"{m(a)}월" if a == b else f"{m(a)}~{m(b)}월"
    return r(e - w + 1, e), r(e - 2 * w + 1, e - w)


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nm(d, k):
    """브랜드 이름(2026-10-24: 상장사 굵게 → 긍정 항목 굵게로 바꿈 · 굵게는 호출하는 쪽에서 B())."""
    b = d["b"].get(k) or {}
    return esc(b.get("ko") or k)


def B(t):
    return f"<b>{t}</b>"


GOOD = {"성장 가속": 3, "반등 중": 2, "성장 둔화": 1, "하락 지속": 0}   # 긍정 순서


QI = {"성장 가속": "🟢 가속", "성장 둔화": "🟡 둔화", "반등 중": "🔵 반등", "하락 지속": "🔴 하락"}


def quads(d, rows, minshare=0.005, cap=6):
    """칸마다 한 줄 — 비중 0.5% 이상 · 큰 순 · 6개 넘으면 '외 N'."""
    out = []
    big = {k: r for k, r in rows.items() if r["s"] >= minshare}
    for q in ORD:
        ks = sorted([k for k, r in big.items() if r["q"] == q], key=lambda k: -big[k]["s"])
        if ks:
            more = f" 외 {len(ks) - cap}" if len(ks) > cap else ""
            out.append(f"{QI[q]}  " + ", ".join(B(nm(d, k)) if q == "성장 가속" else nm(d, k) for k in ks[:cap]) + more)
    return out


def movers(d, rows, f, n=3, minshare=0.005):
    v = sorted([(k, r) for k, r in rows.items() if r["s"] >= minshare and r["sp"] >= 0.003], key=lambda z: -z[1][f])
    up = [B(f"{nm(d, k)} {pct(r[f])}") for k, r in v[:n] if r[f] >= 105]
    dn = [f"{nm(d, k)} {pct(r[f])}" for k, r in v[::-1][:n] if r[f] <= 95]
    return up, dn


def changes(d, rows, prev, minshare=0.005):
    if not prev:
        return []
    ch = [(k, prev[k], r["q"]) for k, r in rows.items() if k in prev and prev[k] != r["q"] and r["s"] >= minshare]
    ch.sort(key=lambda z: (-(GOOD[z[2]] - GOOD[z[1]]), -rows[z[0]]["s"]))   # 좋아진 것부터
    return [(B if GOOD[b] > GOOD[a] else str)(f"{nm(d, k)} {QS[a]}→{QS[b]}") for k, a, b in ch]


def companies(d, C, n=8):
    """상장사로 묶은 합산 비중(최근 3개월)과 QoQ — 한 줄에 하나."""
    by = {}
    for k, b in d["b"].items():
        if b.get("co"):
            by.setdefault(b["co"], []).append(k)
    e, out = C.e, []
    if C.W:   # 3달 창(2026-10-27)
        cu = lambda k: C.wv(k, RI["c"][3])
        pu = lambda k: C.wv(k, RI["p"][3])
    else:
        cu = lambda k: ssum(C.U[k], e - 2, e)
        pu = lambda k: ssum(C.U[k], e - 5, e - 3)
    tc, tp = sum(cu(k) for k in C.U), sum(pu(k) for k in C.U)
    for co, ks in by.items():
        c = sum(cu(k) for k in ks if k in C.U)
        p = sum(pu(k) for k in ks if k in C.U)
        if c and p and tc and tp:
            out.append((co, c / tc, 100 * (c / tc) / (p / tp)))
    out.sort(key=lambda z: -z[1])
    top = sorted(out[:n], key=lambda z: -z[2])            # 비중 상위 n개를 QoQ 좋은 순으로
    return [(B if y >= 100 else str)(f"{esc(co)} {shp(s)} · {pct(y)}") for co, s, y in top]


def bx_lines(d, cut=0.1):
    """바이박스 억제·품절 상품이 브랜드 최근 30일 판매량의 cut 이상인 브랜드 (KBPH.b[k].bx · phase_keepa.js · 2026-10-22)."""
    out = []
    for k, b in d["b"].items():
        x, u = b.get("bx"), b.get("u") or []
        if not x or not x.get("top") or not u or not u[-1]:
            continue
        r = ((x.get("s") or 0) + (x.get("o") or 0)) / u[-1]
        if r < cut:
            continue
        t = x["top"]
        # 억제는 수집일 기준 3일 넘게 이어진 것만(2026-10-22 — 하루짜리 억제를 경고했다가 다음 날 돌아왔다)
        if t.get("k") != "o":
            try:
                if not t.get("since") or (dt.date.fromisoformat(d["asOf"]) - dt.date.fromisoformat(t["since"])).days < 3:
                    continue
            except Exception:
                continue
        kind = "품절" if t.get("k") == "o" else "억제(재고 있음)"
        since = f" · {int(t['since'][5:7])}/{int(t['since'][8:10])}부터" if t.get("since") else ""
        out.append((r, f"• {nm(d, k)} {round(r * 100)}% — {esc(t.get('t', '').strip())}… {kind}{since}"))
    return [z[1] for z in sorted(out, key=lambda z: -z[0])]


def message(d, R, prev):
    """2026-10-24 개편: 일요일 발송 · 이모지 구획 제목 빼고 전 지역 합산 하나를 본문으로, 채널·시장은 한 줄씩."""
    M, end = R["M"], R["end"]
    e = M.index(end)
    c3, p3 = mlab(M, e, 3)
    md = lambda x: f"{int(x[5:7])}/{int(x[8:10])}" if x else "—"
    pq = (prev or {}).get("q") or {}
    st = {}
    us = R["us"].rows(True)
    st["us"] = {k: r["q"] for k, r in us.items()}
    now = kst_now()
    L = [f"<b>K뷰티 국면 주간 · {now.month}/{now.day}({'월화수목금토일'[now.weekday()]})</b>",
         None]
    # 창 설명 — 3달·1달 창(2026-10-27 · 달력 무관)이 있으면 그것 · 아니면 판정 = 완결 3개월 · 조짐 = 최근 30일(있으면) 아니면 직전 완결 달
    SAc0 = R.get("all") or R.get("sum")
    w30 = R.get("ttR30") if SAc0 is not None and SAc0.R else None
    m1, m0 = mlab(M, e, 1)
    if (SAc0 or R["us"]).W:
        t0 = R.get("rwT") or d["asOf"]
        if SAc0 is not None and SAc0.W and R.get("ttRw"):
            t0 = min(t0, R["ttRw"])
        e0 = dt.date.fromisoformat(t0)
        sp = lambda n: f"{md((e0 - dt.timedelta(days=n - 1)).isoformat())}~{md(e0.isoformat())}"
        L[1] = f"<i>판정 최근 3달({sp(90)}) vs 직전 3달 · 조짐 최근 1달({sp(30)}) vs 직전 1달 · 수집 아마존 {md(d['asOf'])} · 틱톡샵 {md(R.get('ttEnd'))}</i>"
    else:
        jz = f"조짐 최근 30일({md(w30[0])}~{md(w30[1])}) vs 직전 30일" if w30 else f"조짐 {m1} vs {m0}"
        L[1] = f"<i>판정 {c3} vs {p3} · {jz} · 수집 아마존 {md(d['asOf'])} · 틱톡샵 {md(R.get('ttEnd'))}</i>"
    has_t = "tt" in R
    SAc = R.get("all") or R.get("sum")
    S = SAc.rows(False) if has_t else us
    if has_t:
        SU = R["sum"].rows(False)
        tt = R["tt"].rows(False)
        st["tt"] = {k: r["q"] for k, r in tt.items()}
        st["sumall"] = {k: r["q"] for k, r in S.items()}
        st["sumus"] = {k: r["q"] for k, r in SU.items()}
        prev_all = pq.get("sumall") or (pq.get("sum") if pq.get("sumdef") == "all" else None)
        allch = changes(d, S, prev_all)
    else:
        allch = changes(d, us, pq.get("us"))

    # 1) 요약
    # 조짐 기준(30일 · 완결 달)이 지난번 보낸 것과 다르면 칸 바뀜을 내지 않는다 — 기준이 달라 생긴 가짜 바뀜이 된다(2026-10-24)
    basis = "rw" if (SAc.W if has_t else R["us"].W) else ("r30" if (has_t and SAc.R) else "m1")
    st["basis"] = basis
    if pq and pq.get("basis", "m1") != basis:
        allch = []
        L.append(None)   # 자리 표시 — 아래 요약에 한 줄
    up, dn = movers(d, S, "x")
    L += ["", "<b>요약</b>"]
    g30 = None
    if has_t and SAc.W:
        g30 = (SAc.rcmp(next(iter(SAc.U)), 1, 1) or {}).get("gb")
    elif has_t and SAc.R:
        any_k = next(iter(SAc.R))
        g30 = (SAc.r30(any_k) or {}).get("gb")
    n3 = "3달" if (SAc.W if has_t else R["us"].W) else "QoQ"
    L.append("판매  " + (f"전 지역 {n3} {pctg(SAc.base(False))} · " if has_t else "") + (f"{'1달' if (has_t and SAc.W) else '최근 30일'} {pctg(g30)} · " if g30 is not None else "") + f"아마존 미국 YoY {pctg(R['us'].base(True))}")
    if up:
        L.append("비중↑  " + ", ".join(up))
    if dn:
        L.append("비중↓  " + ", ".join(dn))
    if None in L:
        L.remove(None)
        L.append("<i>이번 주부터 판정·조짐을 달력과 무관한 3달·1달 창으로 본다 — 칸 바뀜은 다음 주부터</i>" if basis == "rw" else "<i>이번 주부터 조짐을 최근 30일로 본다 — 칸 바뀜은 다음 주부터</i>")
    if allch:
        L.append("칸 바뀜  " + ", ".join(allch[:6]))

    # 2) 상장사
    if has_t:
        L += ["", f"<b>상장사</b> <i>전 지역 비중 · {n3} 좋은 순</i>"] + companies(d, SAc)

    # 3) 국면 — 전 지역 합산 하나만
    L += ["", "<b>국면</b> <i>" + ("아마존 8개국 + 틱톡샵 미국 합산" if has_t else "아마존 미국") + "</i>"] + quads(d, S)

    # 4) 채널·시장 — 한 줄씩
    L += ["", "<b>채널·시장</b>"]
    if R["us"].W:   # 1달 창(2026-10-27)
        r30 = {k: {"s": x["sc"], "sp": x["sp"], "z": x["y"]} for k in R["us"].U for x in [R["us"].rcmp(k, 1, 1)] if x and x["y"] is not None}
        a_up, a_dn = movers(d, r30, "z", n=2)
        lab_a = "비중 1달"
    elif R["us"].R:   # 최근 30일 vs 직전 30일 비중(2026-10-24) — 판정(3개월)보다 먼저 움직이는 쪽
        r30 = {k: {"s": x["sc"], "sp": x["sp"], "z": x["y"]} for k in R["us"].R for x in [R["us"].r30(k)] if x and x["y"] is not None}
        a_up, a_dn = movers(d, r30, "z", n=2)
        lab_a = "비중 최근 30일"
    else:
        a_up, a_dn = movers(d, us, "y", n=2)
        lab_a = "비중 YoY"
    if a_up or a_dn:
        L.append(f"아마존 미국 <i>{lab_a}</i>  " + ", ".join(a_up + a_dn))
    if has_t:
        t_up, t_dn = movers(d, tt, "y" if (R["tt"].R or R["tt"].W) else "x", n=2)
        if t_up or t_dn:
            L.append(f"틱톡샵 미국 <i>비중 {'1달' if R['tt'].W else '최근 30일' if R['tt'].R else 'QoQ'}</i>  " + ", ".join(t_up + t_dn))
    for code, lab in [("eu", "유럽5"), ("jp", "일본"), ("ca", "캐나다")]:
        if code not in R:
            continue
        rows = R[code].rows(True)
        st[code] = {k: r["q"] for k, r in rows.items()}
        big = sorted([(k, r) for k, r in rows.items() if r["s"] >= 0.01], key=lambda z: -z[1]["s"])[:3]
        big.sort(key=lambda z: (-GOOD[z[1]["q"]], -z[1]["s"]))   # 가속·반등부터
        L.append(f"{lab} YoY {pctg(R[code].base(True))}  " + ", ".join((B if r["q"] == "성장 가속" else str)(f"{nm(d, k)} {shp(r['s'])}({QS[r['q']]})") for k, r in big))

    # 5) 경고(있을 때만)
    bx = bx_lines(d)
    if bx:
        L += ["", "<b>주의: 아마존 미국 바이박스 없음</b> <i>수요 아님 · 다음 달 판매가 꺾임</i>"] + bx

    L += ["", f"<i>가속 3{'달' if basis == 'rw' else '개월'}↑·최근↑ · 둔화 3{'달' if basis == 'rw' else '개월'}↑·최근↓ · 반등 3{'달' if basis == 'rw' else '개월'}↓·최근↑ · 하락 둘 다↓ · 굵게=긍정(비중↑·가속·좋아진 칸)</i>"]
    if not pq:
        L.append("<i>첫 회 — 다음 주부터 '칸 바뀜'이 붙는다</i>")
    L.append(f'<a href="{SITE}">대시보드</a>')
    return "\n".join(L), st


def send(text):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        print("텔레그램 토큰·챗ID 가 없다 — 보내지 않는다")
        return False
    ok = True
    parts, cur = [], ""
    for line in text.split("\n"):            # 4,096자 제한 — 줄 단위로 나눈다
        if len(cur) + len(line) + 1 > 3900:
            parts.append(cur)
            cur = ""
        cur += line + "\n"
    parts.append(cur)
    for p in parts:
        data = urllib.parse.urlencode({"chat_id": chat, "text": p.rstrip(), "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
        with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=30) as r:
            ok = ok and r.status == 200
    return ok


def due():
    """이번 주 일요일(KST, 2026-10-24부터 일요일 발송) 이후 미국 국면 원재료가 없으면 차례."""
    now = kst_now().date()
    mon = now - dt.timedelta(days=(now.weekday() + 1) % 7)   # 가장 최근 일요일(오늘이 일요일이면 오늘)
    files = sorted((HERE / "data" / "phase").glob("20??-??-??.json"))
    last = dt.date.fromisoformat(files[-1].name[:10]) if files else dt.date(2000, 1, 1)
    print(f"마지막 국면 원재료 {last} · 이번 주 일요일 {mon} → {'차례' if last < mon else '이미 받음'}")
    return last < mon


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--force", action="store_true", help="같은 asOf 라도 다시 보낸다")
    a = ap.parse_args()
    if a.due:
        return 0 if due() else 1
    d = load()
    prev = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    R = build(d)
    text, st = message(d, R, prev)
    print(text)
    print(f"\n[{len(text)}자]")
    if not a.send:
        return 0
    if prev and prev.get("asOf") == d["asOf"] and not a.force:
        print(f"KBPH {d['asOf']} 는 이미 보냈다 — 안 보낸다")
        return 0
    if send(text):
        STATE.write_text(json.dumps({"asOf": d["asOf"], "sent": kst_now().isoformat(timespec="minutes"), "end": R["end"], "q": st},
                                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("보냄")
    return 0


if __name__ == "__main__":
    sys.exit(main())
