# -*- coding: utf-8 -*-
"""산업부 유통업체 매출동향 → 텔레그램 (2026-10-29 · 사용자 "숫자만 보내면 보기 힘드니 그래프로")

RETAIL 블록(public/index.html)에서 그래프 PNG 9장 + 표 메시지 한 통을 만들어 보낸다.
  ① 표(sendRichMessage · 테두리 표): 업태별 최근 6개월 전년비 + 최신 달 품목 전년비·실액 + 자동 요약(기여 상위 품목 · 계산값)
  ② 앨범(sendMediaGroup): 헤드라인 전년비 1장 · 업태별 '최근 3개년 같은 달' 실액 막대 4장 · 업태별 품목 전년비 작은 차트 4장
같은 달은 한 번만 보낸다(retail_report_sent.json). 보내는 곳은 GitHub Actions(retail_report.yml) — 클라우드 세션은 텔레그램에 못 붙는다.

  python retail_report.py --png DIR        # 그림만 만든다(점검용)
  python retail_report.py --send [--force]
"""
import argparse, datetime, json, os, re, sys

import matplotlib
matplotlib.use("Agg")
try:
    import koreanize_matplotlib  # noqa: F401  (나눔고딕 등록)
except Exception:
    pass
import matplotlib.pyplot as plt
from matplotlib import font_manager

HTML = "public/index.html"
STATE = "retail_report_sent.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
SITE = "https://coverage-dashboard.pages.dev"
TRACKER = "https://claude.ai/artifact/5FBywc16SNyf6fzqZhEbJp"

CH = {"B": "백화점 3사", "M": "대형마트 4사", "C": "편의점 4사", "S": "SSM 4사"}
CH_SHORT = {"B": "백화점", "M": "대형마트", "C": "편의점", "S": "SSM"}
TOT = {"M": 8, "B": 9, "C": 7, "S": 7}
# [표시 이름, 실액 품목 키(합) | "L", 붙임 YoY 열] — 대시보드 app.js RETAIL_ITEMS 와 같게
ITEMS = {
    "B": [["합계", "L", 9], ["비식품 계", ["잡화", "여성정장", "여성캐주얼", "남성의류", "아동스포츠", "가정용품", "명품"], 7], ["해외유명(명품)", ["명품"], 6], ["식품", ["식품"], 8],
          ["여성정장", ["여성정장"], 1], ["여성캐주얼", ["여성캐주얼"], 2], ["남성의류", ["남성의류"], 3], ["아동스포츠", ["아동스포츠"], 4], ["잡화", ["잡화"], 0], ["가정용품", ["가정용품"], 5]],
    "M": [["합계", "L", 8], ["식품", ["식품"], 7], ["비식품 계", ["가전문화", "의류", "가정생활", "스포츠", "잡화", "기타"], 6], ["가전/문화", ["가전문화"], 0], ["의류", ["의류"], 1],
          ["가정/생활", ["가정생활"], 2], ["스포츠", ["스포츠"], 3], ["잡화", ["잡화"], 4], ["기타", ["기타"], 5]],
    "C": [["합계", "L", 7], ["식품 계", ["가공식품", "즉석신선"], 6], ["음료 등 가공", ["가공식품"], 4], ["즉석·신선", ["즉석신선"], 5], ["비식품 계", ["생활용품", "잡화", "담배등"], 3],
          ["담배 등", ["담배등"], 2], ["생활용품", ["생활용품"], 0], ["잡화", ["잡화"], 1]],
    "S": [["합계", "L", 7], ["식품 계", ["농수축산", "신선조리", "가공식품"], 6], ["농수축산", ["농수축산"], 3], ["신선·조리", ["신선조리"], 4], ["가공식품", ["가공식품"], 5],
          ["비식품 계", ["일상용품", "생활잡화"], 2], ["일상용품", ["일상용품"], 0], ["생활잡화", ["생활잡화"], 1]],
}
KPI = {"B": ["구매건수", "구매단가", "점포당 매출"], "M": ["구매건수", "구매단가", "점포당 매출"],
       "C": ["구매건수", "구매단가", "점포 증가율", "점포당 매출"], "S": ["구매건수", "구매단가", "점포당 매출"]}

# 색 — 대시보드 밝은 테마와 같은 벌(강조 골드 · 등락 빨강/파랑)
ACC, UP, DN = "#9a6a12", "#c0392b", "#2c64b0"
G1, G2, INK, MUT, GRID = "#cfd3d8", "#9aa3ad", "#1d2329", "#6b737c", "#e6e8eb"
LINES = ["#b8862b", "#4f8fc9", "#d0694c", "#5f9c7e", "#b5708f", "#3f9f9f", "#7d8894"]


def load():
    h = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const RETAIL = (\{.*?\});$", h, re.M | re.S)
    if not m:
        sys.exit("RETAIL 블록 없음")
    return json.loads(m.group(1))


def lab(ym):              # '26.09' → '26.09
    return "'" + ym


def sgn(v, d=1):
    return "—" if v is None else f"{v:+.{d}f}"


def lv_series(M, ch, ks):
    return [m["L"][ch] if ks == "L" else sum((m["I"].get(ch) or {}).get(k, 0) or 0 for k in ks) for m in M]


def yoy_series(M, ch, ks, col):
    """붙임 공식치 우선, 없으면 실액 12개월 전과 견준 값(est=True)."""
    lv = lv_series(M, ch, ks)
    out = []
    for j, m in enumerate(M):
        o = ((m.get("yoy") or {}).get(ch) or [None] * 12)
        o = o[col] if col is not None and col < len(o) else None
        if o is not None:
            out.append((o, False))
        elif j >= 12 and lv[j - 12]:
            out.append(((lv[j] / lv[j - 12] - 1) * 100, True))
        else:
            out.append((None, True))
    return lv, out


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(G1)
    ax.tick_params(colors=MUT, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def foot(fig, txt):
    fig.text(0.01, 0.01, txt, fontsize=8.5, color=MUT, ha="left", va="bottom")


# ── ① 헤드라인: 전체·오프·온 + 4업태 전년비 ─────────────────────────────
def end_labels(ax, items, gap):
    """오른쪽 끝 꼬리표 — 값 순으로 놓고 gap 보다 가까우면 밀어낸다."""
    items = sorted(items, key=lambda t: t[1])
    ys = [t[1] for t in items]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    for (x, y0, txt, col), y in zip(items, ys):
        ax.annotate(txt, (x, y0), xytext=(x + 0.35, y), textcoords="data", fontsize=9.5, color=col,
                    va="center", fontweight="bold")


def ticks_nice(ax):
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))


def fig_head(M, path):
    Y = [m for m in M if m.get("yoy")][-16:]
    x = list(range(len(Y)))
    fig, axs = plt.subplots(2, 1, figsize=(11, 9.2), dpi=150)
    fig.patch.set_facecolor("white")
    groups = [("헤드라인 — 전체 26개사 · 오프라인 15 · 온라인 11", [("전체", lambda m: m["yoy"]["head"].get("전체")),
                                                         ("오프라인", lambda m: m["yoy"]["head"].get("오프라인")),
                                                         ("온라인", lambda m: m["yoy"]["head"].get("온라인"))]),
              ("업태별 합계", [(CH_SHORT[c], (lambda c: lambda m: (m["yoy"].get(c) or [None] * 12)[TOT[c]])(c)) for c in "BMCS"])]
    for ax, (ttl, ser) in zip(axs, groups):
        style(ax)
        ax.axhline(0, color=G2, lw=1)
        labs, lo, hi = [], 0, 0
        for i, (nm, f) in enumerate(ser):
            v = [f(m) for m in Y]
            ax.plot(x, v, color=LINES[i], lw=2.6 if i == 0 else 1.9, label=nm)
            ok = [(k, a) for k, a in enumerate(v) if a is not None]
            if ok:
                k, a = max(ok, key=lambda t: t[1])
                ax.scatter([k], [a], s=24, color=LINES[i], zorder=3)
                lo, hi = min(lo, min(t[1] for t in ok)), max(hi, a)
                if v[-1] is not None:
                    labs.append((x[-1], v[-1], f"{nm} {v[-1]:+.1f}%", LINES[i]))
        end_labels(ax, labs, (hi - lo) * 0.065)
        ax.set_xticks(x)
        ax.set_xticklabels([lab(m["ym"]) + ("\n" + m["ev"].replace(" ", "\n") if m.get("ev") else "") for m in Y], fontsize=8)
        ax.set_xlim(-0.4, len(Y) - 1 + 2.4)
        ax.set_title(ttl, fontsize=12.5, color=INK, loc="left", fontweight="bold")
        ticks_nice(ax)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0"))
    fig.suptitle(f"유통업체 매출 전년동월비 — 최근 {len(Y)}개월", fontsize=15, color=INK, x=0.01, ha="left", fontweight="bold")
    foot(fig, "산업통상부 주요 유통업체 매출 동향(월간 보도자료) · 점 = 계열 고점 · 월 아래 글씨 = 명절·휴업 등")
    fig.tight_layout(rect=(0, 0.025, 1, 0.965), h_pad=2.5)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── ② 업태별 최근 3개년 같은 달 실액 막대 + 올해 막대 위 YoY + KPI 3개 ───
def fig_years(M, ch, path):
    by = {m["ym"]: m for m in M}
    last = M[-1]["ym"]
    y2, lm = int(last[:2]), int(last[3:])
    yrs = [y2 - 2, y2 - 1, y2]
    _, yy = yoy_series(M, ch, "L", TOT[ch])
    yoy_of = {m["ym"]: yy[i] for i, m in enumerate(M)}
    fig, ax = plt.subplots(figsize=(13, 5.6), dpi=150)
    fig.patch.set_facecolor("white")
    style(ax)
    w = 0.27
    cols = [G1, G2, ACC]
    for i, y in enumerate(yrs):
        xs, vs = [], []
        for mo in range(1, 13):
            k = f"{y:02d}.{mo:02d}"
            if k in by:
                xs.append(mo + (i - 1) * w)
                vs.append(by[k]["L"][ch])
        ax.bar(xs, vs, width=w * 0.95, color=cols[i], label=f"20{y:02d}", zorder=2)
        if y == y2:
            for x_, v_, mo in zip(xs, vs, [int(k[3:]) for k in sorted(by) if k.startswith(f"{y:02d}.")]):
                yv, est = yoy_of.get(f"{y:02d}.{mo:02d}", (None, True))
                if yv is None:
                    continue
                ax.text(x_, v_ * 1.012, f"{yv:+.1f}%" + ("*" if est else ""), ha="center", va="bottom", fontsize=8.5,
                        color=UP if yv > 0 else DN if yv < 0 else MUT, fontweight="bold")
    ax.set_xticks(range(1, 13))
    ev = {int(k[3:]): by[k].get("ev") for k in by if k.startswith(f"{y2:02d}.") and by[k].get("ev")}
    ax.set_xticklabels([f"{mo}월" + (f"\n{ev[mo]}" if mo in ev else "") for mo in range(1, 13)], fontsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.1f}"))
    ax.set_ylabel("조원", color=MUT, fontsize=9)
    vmax = max(m["L"][ch] for m in M)
    ax.set_ylim(0, vmax * 1.32)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, ncol=3)
    # KPI 3개
    cur = by[last]["L"][ch]
    cy = yoy_of.get(last, (None, True))[0]
    ytd = sum(by[f"{y2:02d}.{mo:02d}"]["L"][ch] for mo in range(1, lm + 1) if f"{y2:02d}.{mo:02d}" in by)
    ytd0 = sum(by[f"{y2 - 1:02d}.{mo:02d}"]["L"][ch] for mo in range(1, lm + 1) if f"{y2 - 1:02d}.{mo:02d}" in by)
    py = [by.get(f"{y2 - 1:02d}.{mo:02d}") for mo in range(1, 13)]
    ppy = [by.get(f"{y2 - 2:02d}.{mo:02d}") for mo in range(1, 13)]
    kp = [(f"{lm}월", f"{cur:.2f}조", f"전년비 {sgn(cy)}%"),
          (f"1~{lm}월 누계", f"{ytd:.1f}조", f"전년비 {(ytd / ytd0 - 1) * 100:+.1f}% (계산값)" if ytd0 else "")]
    if all(py):
        a = sum(m["L"][ch] for m in py)
        b = sum(m["L"][ch] for m in ppy) if all(ppy) else None
        kp.append((f"20{y2 - 1:02d} 연간", f"{a:.1f}조", f"전년비 {(a / b - 1) * 100:+.1f}% (계산값)" if b else ""))
    for i, (t, v, s) in enumerate(kp):
        x0 = 0.42 + i * 0.195
        fig.text(x0, 0.905, t, fontsize=9, color=MUT, ha="left")
        fig.text(x0, 0.865, v, fontsize=15, color=INK, ha="left", fontweight="bold")
        col = UP if "+" in s.split("%")[0] else DN if "-" in s.split("%")[0] else MUT
        fig.text(x0, 0.835, s, fontsize=8.5, color=col, ha="left")
    fig.text(0.01, 0.94, f"{CH[ch]} — 월별 실액, 최근 3개년 같은 달", fontsize=14, color=INK, fontweight="bold", ha="left")
    foot(fig, "실액 = 산업부 조사표본 기준 추정(점포당 매출×점포수 앵커, '26.08~ 전년 같은 달×(1+공식 YoY)) · 막대 위 % = 올해 전년동월비(붙임 공식치, *는 실액 환산)")
    fig.tight_layout(rect=(0, 0.03, 1, 0.82))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── ③ 업태별 품목 전년비 작은 차트 ─────────────────────────────────────
def fig_items(M, ch, path):
    i0 = 12
    Mx = M[i0:]
    panels = []
    for nm, ks, col in ITEMS[ch]:
        lv, yy = yoy_series(M, ch, ks, col)
        panels.append((nm, [v for v, _ in yy[i0:]], [e for _, e in yy[i0:]], lv[-1], ks == "L" or nm.endswith(" 계")))
    for k in KPI[ch]:
        v = [((m.get("kpi") or {}).get(ch) or {}).get(k) for m in Mx]
        panels.append((k + " 증감(%)" if not k.endswith("율") else k + "(%)", v, [False] * len(v), None, False))
    n = len(panels)
    nc = 4
    nr = (n + nc - 1) // nc
    fig, axs = plt.subplots(nr, nc, figsize=(14, 2.55 * nr + 0.9), dpi=150, squeeze=False)
    fig.patch.set_facecolor("white")
    x = list(range(len(Mx)))
    for idx, ax in enumerate(axs.flat):
        if idx >= n:
            ax.axis("off")
            continue
        nm, v, est, lvl, bold = panels[idx]
        style(ax)
        ax.axhline(0, color=G2, lw=0.9)
        for a in range(1, len(x)):                       # 공식치 실선 · 실액 환산 점선
            if v[a] is None or v[a - 1] is None:
                continue
            ax.plot([a - 1, a], [v[a - 1], v[a]], color=ACC, lw=2.0 if bold else 1.6,
                    ls=(0, (2, 2)) if est[a] else "-", alpha=0.75 if est[a] else 1)
        ok = [(k, a) for k, a in enumerate(v) if a is not None]
        if ok:
            k, a = max(ok, key=lambda t: t[1])
            ax.scatter([k], [a], s=14, color=ACC, zorder=3)
        lastv = v[-1]
        col = UP if (lastv or 0) > 0 else DN if (lastv or 0) < 0 else MUT
        ax.set_title(nm, fontsize=10, color=INK, loc="left", fontweight="bold" if bold else "normal")
        ax.text(1.0, 1.02, (f"{lastv:+.1f}%" if lastv is not None else "—") + (f"  {lvl:.2f}조" if lvl else ""),
                transform=ax.transAxes, ha="right", va="bottom", fontsize=9.5, color=col, fontweight="bold")
        ticks = [k for k, m in enumerate(Mx) if m["ym"].endswith(".01")] + [len(Mx) - 1]
        ax.set_xticks(ticks)
        ax.set_xticklabels([lab(Mx[k]["ym"]) for k in ticks], fontsize=7.5)
        ticks_nice(ax)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda val, _: f"{val:g}"))
        ax.tick_params(axis="y", labelsize=8)
    fig.suptitle(f"{CH[ch]} — 품목별 전년동월비(%) · '{Mx[0]['ym']}~'{Mx[-1]['ym']}", fontsize=14, color=INK, x=0.01, ha="left", fontweight="bold")
    foot(fig, "칸마다 자기 축 · 실선 = 붙임 공식치 · 점선 = 실액에서 환산 · 오른쪽 위 = 최신 달 전년비·실액(조원) · 점 = 고점")
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── 표·요약 ───────────────────────────────────────────────────────────
def contrib(M, ch):
    """최신 달 품목별 전년비 기여(%p, 계산값) = (품목 실액 − 작년 같은 달) ÷ 작년 같은 달 업태 합계."""
    j = len(M) - 1
    if j < 12:
        return []
    base = M[j - 12]["L"][ch]
    out = []
    for nm, ks, col in ITEMS[ch]:
        if ks == "L" or nm.endswith(" 계"):
            continue
        a = sum((M[j]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)
        b = sum((M[j - 12]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)
        out.append((nm, (a - b) / base * 100))
    return sorted(out, key=lambda t: -abs(t[1]))


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_rich(R):
    M = R["months"]
    last = M[-1]
    ym = last["ym"]
    mo = int(ym[3:])
    Y = [m for m in M if m.get("yoy")][-6:]
    hd = last["yoy"]["head"]
    td = lambda s, al="right": f'<td align="{al}">{s}</td>'
    th = lambda s, al="right": f'<th align="{al}">{s}</th>'
    rows = [("전체", lambda m: m["yoy"]["head"].get("전체")), ("오프라인", lambda m: m["yoy"]["head"].get("오프라인")),
            ("온라인", lambda m: m["yoy"]["head"].get("온라인"))] + \
           [(CH_SHORT[c], (lambda c: lambda m: (m["yoy"].get(c) or [None] * 12)[TOT[c]])(c)) for c in "BMCS"]
    t1 = "<table bordered><caption>업태별 전년동월비(%)</caption><tr>" + th("업태", "left") + \
         "".join(th(lab(m["ym"]) + (f"<br>{esc(m['ev'])}" if m.get("ev") else "")) for m in Y) + "</tr>"
    for nm, f in rows:
        t1 += "<tr>" + td(f"<b>{nm}</b>", "left") + "".join(td(sgn(f(m))) for m in Y) + "</tr>"
    t1 += "</table>"
    prev = M[-2]
    t2 = f"<table bordered><caption>{mo}월 품목 전년동월비 · 실액</caption><tr>" + th("업태", "left") + th("품목", "left") + \
         th(f"{mo}월 %") + th(f"{int(prev['ym'][3:])}월 %") + th("실액(조)") + "</tr>"
    for c in "BMCS":
        for k, (nm, ks, col) in enumerate(ITEMS[c]):
            lv, yy = yoy_series(M, c, ks, col)
            b = nm == "합계" or nm.endswith(" 계")
            name = f"<b>{nm}</b>" if b else nm
            t2 += "<tr>" + td(f"<b>{CH_SHORT[c]}</b>" if k == 0 else "", "left") + td(name, "left") + \
                  td(sgn(yy[-1][0]) + ("*" if yy[-1][1] and yy[-1][0] is not None else "")) + \
                  td(sgn(yy[-2][0]) + ("*" if yy[-2][1] and yy[-2][0] is not None else "")) + td(f"{lv[-1]:.3f}") + "</tr>"
    t2 += "</table>"
    # 요약 — 기여 상위 품목(계산값)
    lines = []
    for c in "BMCS":
        cy = (last["yoy"].get(c) or [None] * 12)[TOT[c]]
        py_ = (prev.get("yoy", {}).get(c) or [None] * 12)[TOT[c]]
        top = contrib(M, c)[:2]
        lines.append(f"<b>{CH_SHORT[c]}</b> {sgn(cy)}% (전월 {sgn(py_)}) — 기여 상위: " +
                     " · ".join(f"{esc(n)} {v:+.1f}%p" for n, v in top))
    ev = f" · {esc(last['ev'])}" if last.get("ev") else ""
    html = (f"<h2>{mo}월 유통업체 매출 — 전체 {sgn(hd.get('전체'))}%</h2>"
            f"<p>오프라인 {sgn(hd.get('오프라인'))}% · 온라인 {sgn(hd.get('온라인'))}%{ev} · {esc(R.get('release', ''))}</p>"
            f"<p>{'<br>'.join(lines)}</p>" + t1 + t2 +
            f"<p>기여 %p = (품목 실액 − 작년 같은 달) ÷ 작년 같은 달 업태 합계(계산값). * = 붙임에 품목 전년비가 없어 실액으로 환산.<br>"
            f"실액은 조사표본 기준 추정. 그래프 9장은 이어서 보낸다. 대시보드: 유통 종목 페이지 손익 탭 · <a href=\"{SITE}\">{SITE}</a></p>")
    plain = (f"{mo}월 유통업체 매출 — 전체 {sgn(hd.get('전체'))}% (오프 {sgn(hd.get('오프라인'))} · 온 {sgn(hd.get('온라인'))}){ev}\n" +
             "\n".join(re.sub("<[^>]+>", "", l) for l in lines))
    return html, plain


def make_pngs(R, d):
    os.makedirs(d, exist_ok=True)
    M = R["months"]
    out = []
    p = os.path.join(d, "00_head.png"); fig_head(M, p); out.append(p)
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"1{i}_{c}_years.png"); fig_years(M, c, p); out.append(p)
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"2{i}_{c}_items.png"); fig_items(M, c, p); out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png"); ap.add_argument("--send", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    R = load()
    ym = R["months"][-1]["ym"]
    if a.png:
        for p in make_pngs(R, a.png):
            print(p)
        html, plain = build_rich(R)
        open(os.path.join(a.png, "rich.html"), "w", encoding="utf-8").write(html)
        print(plain)
        return
    if not a.send:
        sys.exit("--png DIR 또는 --send")
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    if st.get("sent") == ym and not a.force:
        print(f"[retail_report] {ym} 이미 보냄 — 생략"); return
    import telegram_send as tg
    if not tg.configured():
        sys.exit("[retail_report] 텔레그램 토큰·챗ID 없음")
    html, plain = build_rich(R)
    ok1 = tg.send_rich(html, fallback=plain)
    pngs = make_pngs(R, "retail_png")
    cap = f"{int(ym[3:])}월 유통업체 매출동향 그래프 — ① 헤드라인 전년비 ② 업태별 최근 3개년 같은 달 실액(4장) ③ 업태별 품목 전년비(4장)"
    ok2 = tg.send_photos(pngs, caption=cap)
    if ok1 and ok2:
        json.dump({"sent": ym, "at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "table": tg.RICH_MODE, "photos": len(pngs)},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[retail_report] {ym} 보냄")
    else:
        sys.exit(f"[retail_report] 전송 실패 (표 {ok1} · 그래프 {ok2})")


if __name__ == "__main__":
    main()
