# -*- coding: utf-8 -*-
"""K뷰티 국면 주간 브리핑 — KBPH 블록(public/index.html)을 읽어 텔레그램 한 통 (2026-10-22).

사용자: "주간으로 업데이트하면 브리핑 메시지 텔레로 보내 주는 것도 가능한가" → 월요일 아침 국면 수집(크롬 세션)이 KBPH 를 올리면
`.github/workflows/phase_brief.yml` 이 이걸 부른다. 화면(app.js renderCosPhase)과 같은 식을 파이썬으로 다시 푼다:
  아마존(미국·유럽 5개국·일본·캐나다) — 가로 비중 YoY(최근 3개월 vs 작년 같은 3개월) × 세로 비중 QoQ(바로 앞 3개월) → 네 칸
  틱톡샵(미국 공식 샵)              — 비중 QoQ × MoM (2026-04 부터라 전년 없음 · 4월 앞부분은 추정)
  합산(아마존 미국 + 틱톡샵)          — 브랜드마다 두 채널 판매량을 더한 비중 QoQ × MoM
비중 = 바구니(추적 브랜드 전부, 비상장 포함) 판매량 중 그 브랜드 몫. 끝 달 = 두 채널 공통 마지막 완결 달(진행 중인 달은 안 쓴다).
칸이 바뀐 브랜드는 지난번 보낸 칸(kbeauty/data/phase/brief_state.json)과 견준다.

  python3 kbeauty/phase_brief.py          # 메시지만 찍는다
  python3 kbeauty/phase_brief.py --send   # 텔레그램(TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID) — 같은 KBPH asOf 는 한 번만
  python3 kbeauty/phase_brief.py --due    # 국면 수집할 차례면 종료코드 0(이번 주 월요일 이후 원재료가 없을 때) · 아니면 1
"""
import argparse
import datetime as dt
import json
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


class Chan:
    """한 채널 — U[k] = 브랜드별 월 판매량(M 순서) · e = 끝 달 인덱스."""

    def __init__(self, M, U, e):
        self.M, self.U, self.e = M, U, e
        self.tot = [sum((U[k][j] or 0) for k in U) for j in range(len(M))]

    def cmp(self, k, w, back):
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
            b = self.cmp(k, 3, 3) if yoy else self.cmp(k, 1, 1)   # 세로
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
    # 아마존 미국
    res["us"] = Chan(M, {k: b["u"] for k, b in B.items()}, e)
    # 틱톡샵
    if TM and end in TM:
        et = TM.index(end)
        res["tt"] = Chan(TM, {k: b["mu"] for k, b in tt["b"].items()}, et)
        ai = [M.index(m) if m in M else -1 for m in TM]
        keys = set(B) | set(tt["b"])
        S = {}
        for k in keys:
            S[k] = [((B[k]["u"][ai[j]] or 0) if k in B and ai[j] >= 0 else 0) + ((tt["b"][k]["mu"][j] or 0) if k in tt["b"] else 0) for j in range(len(TM))]
        res["sum"] = Chan(TM, S, et)
        res["mest"] = tt.get("mest") or []
        res["ttEnd"] = tt.get("end")
    # 다른 아마존 시장
    mk = d.get("mk") or {}
    for code, _ in MK:
        if code in mk:
            res[code] = Chan(M, {k: x["u"] for k, x in mk[code]["b"].items()}, e)
    have = [m for m in EU if m in mk]
    if have:
        U = {}
        for m in have:
            for k, x in mk[m]["b"].items():
                a = U.setdefault(k, [0] * len(M))
                for j in range(len(M)):
                    a[j] += x["u"][j] or 0
        res["eu"] = Chan(M, U, e)
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


def section(d, title, rows, prev, xl, yl, mover="x", minshare=0.005, lim=4):
    """칸별 목록(비중 0.5% 이상) + 칸 바뀜 + 비중 크게 움직인 브랜드."""
    out = [title]
    big = {k: r for k, r in rows.items() if r["s"] >= minshare}
    for q in ORD:
        ks = sorted([k for k, r in big.items() if r["q"] == q], key=lambda k: -big[k]["s"])
        if ks:
            out.append(f" {QS[q]} {len(ks)}: " + " · ".join(name(d, k) + tag(d, k) for k in ks))
    if prev:
        ch = [(k, prev[k], r["q"]) for k, r in rows.items() if k in prev and prev[k] != r["q"] and r["s"] >= minshare]
        ch.sort(key=lambda z: -rows[z[0]]["s"])
        if ch:
            out.append(" 칸 바뀜: " + " · ".join(f"{name(d, k)} {QS[a]}→{QS[b]}" for k, a, b in ch[:8]))
    v = sorted([(k, r) for k, r in big.items() if r["sp"] >= 0.003], key=lambda z: -(z[1][mover]))
    up = [f"{name(d, k)}{tag(d, k)} {pct(r[mover])}({shp(r['s'])})" for k, r in v[:lim] if r[mover] >= 105]
    dn = [f"{name(d, k)}{tag(d, k)} {pct(r[mover])}({shp(r['s'])})" for k, r in v[::-1][:lim] if r[mover] <= 95]
    lab = xl if mover == "x" else yl
    if up:
        out.append(f" 비중↑ {lab}: " + " · ".join(up))
    if dn:
        out.append(f" 비중↓ {lab}: " + " · ".join(dn))
    return out


def companies(d, C):
    """상장사로 묶은 아마존 미국 + 틱톡샵 합산 비중(3개월)과 QoQ."""
    by = {}
    for k, b in d["b"].items():
        co = b.get("co")
        if co:
            by.setdefault(co, []).append(k)
    out = []
    for co, ks in by.items():
        U = C.U
        e = C.e
        c = sum(ssum(U[k], e - 2, e) for k in ks if k in U)
        p = sum(ssum(U[k], e - 5, e - 3) for k in ks if k in U)
        tc, tp = ssum(C.tot, e - 2, e), ssum(C.tot, e - 5, e - 3)
        if not c or not p or not tc or not tp:
            continue
        out.append((co, c / tc, 100 * (c / tc) / (p / tp)))
    out.sort(key=lambda z: -z[1])
    return " · ".join(f"{co} {shp(s)}({pct(y)})" for co, s, y in out if s >= 0.002)


def message(d, R, prev):
    M, end = R["M"], R["end"]
    e = M.index(end)
    c3, p3 = mlab(M, e, 3)
    L = [f"💄 K뷰티 국면 주간 — 완결 {int(end[5:])}월까지 · 아마존 {d['asOf'][5:].replace('-', '/')} · 틱톡샵 {(R.get('ttEnd') or '')[5:].replace('-', '/')}까지",
         f"비중 = 추적 브랜드(비상장 포함) 판매량 중 몫 · * = 상장사 · 칸은 0.5% 이상만"]
    pq = (prev or {}).get("q") or {}
    us = R["us"].rows(True)
    L += [""] + section(d, f"[아마존 미국] YoY({c3} vs 작년) × QoQ({c3} vs {p3}) · 바구니 판매 YoY {pctg(R['us'].base(True))}",
                        us, pq.get("us"), "YoY", "QoQ", mover="y")
    st = {"us": {k: r["q"] for k, r in us.items()}}
    if "tt" in R:
        t1c, t1p = mlab(R["tt"].M, R["tt"].e, 1)
        est = " · 4월 앞부분 추정" if R.get("mest") and R["mest"][0] in R["tt"].M[R["tt"].e - 5:R["tt"].e + 1] else ""
        tt = R["tt"].rows(False)
        L += [""] + section(d, f"[틱톡샵 미국] QoQ({c3} vs {p3}{est}) × MoM({t1c} vs {t1p})", tt, pq.get("tt"), "QoQ", "MoM")
        sm = R["sum"].rows(False)
        L += [""] + section(d, f"[합산 아마존+틱톡샵] QoQ × MoM · 바구니 판매 QoQ {pctg(R['sum'].base(False))}", sm, pq.get("sum"), "QoQ", "MoM")
        st["tt"] = {k: r["q"] for k, r in tt.items()}
        st["sum"] = {k: r["q"] for k, r in sm.items()}
        L += ["", "[상장사 · 합산 비중(QoQ)] " + companies(d, R["sum"])]
    # 다른 시장 — 칸 바뀜 + 비중 YoY 큰 브랜드만 짧게
    extra = []
    for code, lab in [("eu", "유럽 5개국"), ("jp", "일본"), ("ca", "캐나다")]:
        if code not in R:
            continue
        rows = R[code].rows(True)
        st[code] = {k: r["q"] for k, r in rows.items()}
        big = sorted([(k, r) for k, r in rows.items() if r["s"] >= 0.01], key=lambda z: -z[1]["s"])[:5]
        top = " · ".join(f"{name(d, k)}{tag(d, k)} {shp(r['s'])} {QS[r['q']]}" for k, r in big)
        ch = [f"{name(d, k)} {QS[a]}→{QS[r['q']]}" for k, r in rows.items() if k in (pq.get(code) or {}) and (a := pq[code][k]) != r["q"] and r["s"] >= 0.01]
        extra.append(f"[아마존 {lab}] 바구니 판매 YoY {pctg(R[code].base(True))} · 큰 순 {top}" + (f" · 칸 바뀜 {' · '.join(ch[:5])}" if ch else ""))
    if extra:
        L += [""] + extra
    if not pq:
        L += ["", "(첫 브리핑 — 다음 주부터 '칸 바뀜'이 붙는다)"]
    L += ["", SITE]
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
        data = urllib.parse.urlencode({"chat_id": chat, "text": p.rstrip(), "disable_web_page_preview": "true"}).encode()
        with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=30) as r:
            ok = ok and r.status == 200
    return ok


def due():
    """이번 주 월요일(KST) 이후 미국 국면 원재료가 없으면 차례."""
    now = kst_now().date()
    mon = now - dt.timedelta(days=now.weekday())
    files = sorted((HERE / "data" / "phase").glob("20??-??-??.json"))
    last = dt.date.fromisoformat(files[-1].name[:10]) if files else dt.date(2000, 1, 1)
    print(f"마지막 국면 원재료 {last} · 이번 주 월요일 {mon} → {'차례' if last < mon else '이미 받음'}")
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
