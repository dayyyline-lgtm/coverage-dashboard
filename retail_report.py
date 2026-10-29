# -*- coding: utf-8 -*-
"""산업부 유통업체 매출동향 → 텔레그램 (2026-10-29 · 사용자 "숫자만 보내면 보기 힘드니 그래프로")

RETAIL 블록(public/index.html)에서 그래프 PNG 7장 + 표 메시지 한 통을 만들어 보낸다.
  ① 표(sendRichMessage · 테두리 표): 업태별 최근 6개월 전년비 + 최신 달 품목 전년비·실액 + 자동 요약(기여 상위 품목 · 계산값)
  ② 앨범(sendMediaGroup · 사진마다 읽는 법 캡션): ① 이번 달 업태별 전년비(막대 + 전월 세로선) ② 품목별 기여(%p · 합 = 업태 전년비)
     ③ 최근 13개월 전년비 막대 ④ 업태별 '최근 3개년 같은 달' 실액 막대 4장 — 폰에서 읽히게 글씨를 키워 그린다(DPI 200)
  2026-10-29 사용자 "시각적으로 이해가 잘 안 됨" → 선 7개 겹친 헤드라인·품목 작은 차트 52칸을 이 구성으로 바꿨다.
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
plt.rcParams["axes.unicode_minus"] = False

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

# 색 — 대시보드 밝은 테마와 같은 벌(강조 골드 · 등락 빨강/파랑 · 무채색 바탕)
ACC, UP, DN = "#9a6a12", "#c0392b", "#2c64b0"
G1, G2, INK, MUT, GRID = "#cfd3d8", "#9aa3ad", "#1d2329", "#6b737c", "#eceef0"
Y_OLD, Y_MID = "#d9dce0", "#a9b0b8"        # 3개년 막대: 재작년 · 작년 (올해 = ACC)
DPI = 200                                  # 폰에서 열면 폭이 약 1/3 로 줄어든다 — 글씨를 키워 그린다

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


from matplotlib.transforms import blended_transform_factory as _blend


def tot_yoy(m, c):
    return ((m.get("yoy") or {}).get(c) or [None] * 12)[TOT[c]]


def head_yoy(m, k):
    return ((m.get("yoy") or {}).get("head") or {}).get(k)


SERIES = [("전체", lambda m: head_yoy(m, "전체")), ("오프라인", lambda m: head_yoy(m, "오프라인")),
          ("온라인", lambda m: head_yoy(m, "온라인"))] + \
         [(CH_SHORT[c], (lambda c: lambda m: tot_yoy(m, c))(c)) for c in "BMCS"]


def ev_short(ev):
    if not ev:
        return ""
    h = "추석" if "추석" in ev else "설" if ev.startswith("설") else ""
    if "선판매" in ev:
        return (h or "명절") + "전"
    if h:
        return h
    for k in ("휴업", "편입"):
        if k in ev:
            return k
    return ev[:3]


def holiday_note(M):
    """'올해 9월 추석(9/25) · 작년 추석은 10월(10/6)' — 명절이 낀 달만."""
    last = M[-1]
    ev = last.get("ev") or ""
    h = "추석" if "추석" in ev else "설" if ev.startswith("설") else ""
    if not h or "선판매" in ev:
        return ev
    y = int(last["ym"][:2])
    ly = [m for m in M if m["ym"].startswith(f"{y - 1:02d}.") and h in (m.get("ev") or "") and "선판매" not in (m.get("ev") or "")]
    if not ly:
        return ev
    l = ly[0]
    same = l["ym"][3:] == last["ym"][3:]
    return f"올해 {ev} · 작년 {h}은 {int(l['ym'][3:])}월{'(같은 달)' if same else ''}" + \
        (re.sub(r"^[^(]*", "", l["ev"]) if "(" in l["ev"] else "")


def style(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(G1)
    ax.tick_params(colors=MUT, labelsize=10, length=0)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.9)
    ax.set_axisbelow(True)


def heading(fig, title, sub=None, y=0.975):
    fig.text(0.03, y, title, fontsize=17, color=INK, fontweight="bold", ha="left", va="top")
    if sub:
        fig.text(0.03, y - 0.048, sub, fontsize=11.5, color=MUT, ha="left", va="top", linespacing=1.45)


def foot(fig, txt):
    fig.text(0.03, 0.012, txt, fontsize=9, color=MUT, ha="left", va="bottom", linespacing=1.4)


def pct(v, _=None):
    return "0" if abs(v) < 1e-9 else f"{v:+g}%"


# ── ① 이번 달 한눈에: 업태별 전년비 막대 + 전월 세로선 ─────────────────────
def fig_now(M, path):
    last, prev = M[-1], M[-2]
    mo, pmo = int(last["ym"][3:]), int(prev["ym"][3:])
    cur = [f(last) for _, f in SERIES]
    pv = [f(prev) for _, f in SERIES]
    ys = [0, 1, 2, 3.5, 4.5, 5.5, 6.5]
    vals = [v for v in cur + pv if v is not None]
    lo, hi = min(0, min(vals)), max(0, max(vals))
    pad = (hi - lo) * 0.08
    fig, ax = plt.subplots(figsize=(6.6, 5.9), dpi=DPI)
    fig.patch.set_facecolor("white")
    style(ax, grid="x")
    for y, c, p in zip(ys, cur, pv):
        if c is not None:
            ax.barh(y, c, height=0.58, color=UP if c > 0 else DN, zorder=2)
        if p is not None:
            ax.plot([p, p], [y - 0.4, y + 0.4], color=INK, lw=2.2, zorder=3, solid_capstyle="butt")
    ax.axvline(0, color=G2, lw=1.1, zorder=1)
    ax.axhline(2.75, color=G1, lw=0.9)
    ax.set_yticks(ys)
    ax.set_yticklabels([nm for nm, _ in SERIES], fontsize=13, color=INK)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_ylim(6.5 + 0.6, -0.95)
    ax.set_xlim(lo - pad, hi + pad)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(pct))
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))
    tr = _blend(ax.transAxes, ax.transData)
    ax.text(1.04, -0.75, f"{mo}월", transform=tr, fontsize=11, color=MUT, ha="left", va="center")
    ax.text(1.27, -0.75, f"{pmo}월", transform=tr, fontsize=11, color=MUT, ha="left", va="center")
    for y, c, p in zip(ys, cur, pv):
        ax.text(1.04, y, f"{c:+.1f}%" if c is not None else "—", transform=tr, fontsize=13.5, fontweight="bold",
                color=UP if (c or 0) > 0 else DN if (c or 0) < 0 else MUT, ha="left", va="center")
        ax.text(1.27, y, f"{p:+.1f}" if p is not None else "—", transform=tr, fontsize=12, color=MUT, ha="left", va="center")
    ax.text(-0.02, 3.5 - 0.62, "업태별 (오프라인 안)", transform=tr, fontsize=9.5, color=MUT, ha="right", va="center")
    # 제목 = 결론: 전체 숫자 + 크게 움직인 업태
    moves = sorted([(abs(c - p), nm, c, p) for (nm, _), c, p in zip(SERIES[1:], cur[1:], pv[1:])
                    if c is not None and p is not None and abs(c - p) >= 2], reverse=True)[:3]
    sub = " · ".join(f"{nm} {p:+.1f}→{c:+.1f}" for _, nm, c, p in moves)
    hn = holiday_note(M)
    heading(fig, f"{mo}월 유통업체 매출 전년비 {cur[0]:+.1f}%",
            (f"크게 바뀐 곳: {sub}" if sub else f"{pmo}월과 비슷") + (f"\n{hn}" if hn else ""))
    foot(fig, f"막대 = {mo}월 전년동월비(빨강 증가 · 파랑 감소) · 검은 세로선 = {pmo}월 · 오른쪽 숫자 = 그 값\n"
              "산업통상부 주요 유통업체 매출 동향 — 전체 26개사 = 오프라인 15 + 온라인 11")
    fig.subplots_adjust(left=0.2, right=0.76, top=0.80, bottom=0.13)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── ② 무엇이 움직였나: 품목이 업태 전년비에 보탠 몫(%p) ─────────────────────
def item_rows(M, ch):
    j = len(M) - 1
    base = M[j - 12]["L"][ch]
    out = []
    for nm, ks, col in ITEMS[ch]:
        if ks == "L" or nm.endswith(" 계"):
            continue
        a = sum((M[j]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)
        b = sum((M[j - 12]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)
        _, yy = yoy_series(M, ch, ks, col)
        out.append((nm, (a - b) / base * 100, yy[-1][0], yy[-1][1]))
    return sorted(out, key=lambda t: -t[1])


def fig_drivers(M, path):
    last = M[-1]
    mo = int(last["ym"][3:])
    rows = {c: item_rows(M, c) for c in "BMCS"}
    allv = [r[1] for c in rows for r in rows[c]]
    lo, hi = min(0, min(allv)), max(0, max(allv))
    span = hi - lo
    fig, axs = plt.subplots(2, 2, figsize=(7.4, 8.6), dpi=DPI)
    fig.patch.set_facecolor("white")
    for ax, c in zip(axs.flat, "BMCS"):
        R = rows[c]
        style(ax, grid="x")
        ys = list(range(len(R)))
        for y, (nm, v, iy, est) in zip(ys, R):
            ax.barh(y, v, height=0.62, color=UP if v > 0 else DN, zorder=2)
            ax.text(v + (span * 0.03 if v >= 0 else -span * 0.03), y, f"{v:+.1f}", fontsize=11, fontweight="bold",
                    color=INK, ha="left" if v >= 0 else "right", va="center")
        ax.axvline(0, color=G2, lw=1.1)
        ax.set_yticks(ys)
        ax.set_yticklabels([f"{nm}\n{'품목 ' + format(iy, '+.1f') + '%' if iy is not None else ''}{'*' if est else ''}"
                            for nm, v, iy, est in R], fontsize=10.5, color=INK, linespacing=1.15)
        for t in ax.get_yticklabels():
            t.set_multialignment("right")
        ax.set_ylim(len(R) - 0.4, -0.6)
        ax.set_xlim(lo - span * 0.32, hi + span * 0.32)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10]))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: "0" if abs(v) < 1e-9 else f"{v:+g}"))
        t = tot_yoy(last, c)
        ax.set_title(f"{CH_SHORT[c]}  {t:+.1f}%", fontsize=14, color=INK, loc="left", fontweight="bold", pad=8)
    heading(fig, f"{mo}월 무엇이 움직였나 — 품목별 기여",
            "막대 = 품목이 업태 전년비에 보탠 몫(%p) · 막대를 다 더하면 제목 숫자\n이름 아래 = 그 품목 자체의 전년비")
    foot(fig, "기여 %p = (품목 실액 - 작년 같은 달) ÷ 작년 같은 달 업태 합계 — 실액·비중으로 낸 계산값 · 칸끼리 같은 축\n"
              "* = 붙임에 품목 전년비가 없어 실액으로 환산")
    fig.subplots_adjust(left=0.2, right=0.97, top=0.815, bottom=0.085, wspace=0.62, hspace=0.3)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── ③ 최근 13개월 추이: 달마다 막대 하나 ───────────────────────────────────
def fig_trend(M, path):
    Y = [m for m in M if m.get("yoy")][-13:]
    fig = plt.figure(figsize=(7.4, 9.6), dpi=DPI)
    fig.patch.set_facecolor("white")
    gs = fig.add_gridspec(4, 2, height_ratios=[1.3, 1, 1, 1], hspace=0.62, wspace=0.28)
    slots = [gs[0, :], gs[1, 0], gs[1, 1], gs[2, 0], gs[2, 1], gs[3, 0], gs[3, 1]]
    x = list(range(len(Y)))
    for i, (sl, (nm, f)) in enumerate(zip(slots, SERIES)):
        ax = fig.add_subplot(sl)
        style(ax)
        v = [f(m) for m in Y]
        ax.bar(x, [a or 0 for a in v], width=0.7, color=[UP if (a or 0) > 0 else DN for a in v], zorder=2)
        ax.axhline(0, color=G2, lw=1)
        vv = [a for a in v if a is not None]
        lo, hi = min(0, min(vv)), max(0, max(vv))
        sp = (hi - lo) or 1
        ax.set_ylim(lo - sp * (0.12 if lo < 0 else 0.04), hi + sp * 0.12)
        if v[-1] is not None:
            ax.text(1.0, 1.03, f"{int(Y[-1]['ym'][3:])}월 {v[-1]:+.1f}%", transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=12.5 if i == 0 else 11.5, fontweight="bold", color=UP if v[-1] > 0 else DN if v[-1] < 0 else MUT)
        labs = []
        for m in Y:
            mm = int(m["ym"][3:])
            t = f"{mm}" + (f"\n'{m['ym'][:2]}" if (mm == 1 or m is Y[0]) else "")
            if i == 0 and m.get("ev"):
                t = f"{mm}\n{ev_short(m['ev'])}" if not (mm == 1 or m is Y[0]) else t + f" {ev_short(m['ev'])}"
            labs.append(t)
        ax.set_xticks(x)
        ax.set_xticklabels(labs, fontsize=9.5 if i == 0 else 8.5, linespacing=1.1)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10]))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda val, _: "0" if abs(val) < 1e-9 else f"{val:+g}"))
        ax.tick_params(axis="y", labelsize=9)
        ax.set_title(nm, fontsize=14 if i == 0 else 12.5, color=INK, loc="left", fontweight="bold", pad=6)
    heading(fig, f"전년동월비 추이 — 최근 {len(Y)}개월",
            "막대 하나 = 한 달 (빨강 증가 · 파랑 감소) · 칸마다 자기 축\n맨 위 칸 아래 글씨 = 명절·휴업 등 그 달 사정")
    foot(fig, "산업통상부 주요 유통업체 매출 동향 · 칸 오른쪽 위 = 마지막 달 전년비")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.83, bottom=0.075)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── ④ 업태별 최근 3개년 같은 달 실액 + 올해 막대 위 YoY + KPI 3개 ─────────────
def fig_years(M, ch, path):
    by = {m["ym"]: m for m in M}
    last = M[-1]["ym"]
    y2, lm = int(last[:2]), int(last[3:])
    yrs = [y2 - 2, y2 - 1, y2]
    _, yy = yoy_series(M, ch, "L", TOT[ch])
    yoy_of = {m["ym"]: yy[i] for i, m in enumerate(M)}
    fig, ax = plt.subplots(figsize=(7.6, 5.6), dpi=DPI)
    fig.patch.set_facecolor("white")
    style(ax)
    w = 0.27
    for i, (y, col) in enumerate(zip(yrs, [Y_OLD, Y_MID, ACC])):
        xs, vs, ms = [], [], []
        for mo in range(1, 13):
            k = f"{y:02d}.{mo:02d}"
            if k in by:
                xs.append(mo + (i - 1) * w)
                vs.append(by[k]["L"][ch])
                ms.append(mo)
        ax.bar(xs, vs, width=w * 0.92, color=col, label=f"20{y:02d}", zorder=2)
        if y == y2:
            for x_, v_, mo in zip(xs, vs, ms):
                yv, est = yoy_of.get(f"{y:02d}.{mo:02d}", (None, True))
                if yv is None:
                    continue
                top = max(by[k]["L"][ch] for k in (f"{yy_:02d}.{mo:02d}" for yy_ in yrs) if k in by)
                ax.text(x_, top * 1.015, f"{yv:+.0f}%" + ("*" if est else ""), ha="center", va="bottom", fontsize=10,
                        color=UP if yv > 0 else DN if yv < 0 else MUT, fontweight="bold")
    ev = {int(k[3:]): ev_short(by[k].get("ev")) for k in by if k.startswith(f"{y2:02d}.") and by[k].get("ev")}
    ev = {k: v for k, v in ev.items() if v in ("설", "추석", "추석전", "설전") or (v == "휴업" and ch == "M")}
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([f"{mo}월" + (f"\n{ev[mo]}" if mo in ev else "") for mo in range(1, 13)], fontsize=10.5, color=INK)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.tick_params(axis="y", labelsize=10)
    vmax = max(m["L"][ch] for m in M)
    ax.set_ylim(0, vmax * 1.2)
    ax.set_xlim(0.45, 12.55)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.13), frameon=False, fontsize=10.5, ncol=3, handlelength=1.2, columnspacing=1.2)
    # KPI 3개
    cur = by[last]["L"][ch]
    cy = yoy_of.get(last, (None, True))[0]
    ytd = sum(by[f"{y2:02d}.{mo:02d}"]["L"][ch] for mo in range(1, lm + 1) if f"{y2:02d}.{mo:02d}" in by)
    ytd0 = sum(by[f"{y2 - 1:02d}.{mo:02d}"]["L"][ch] for mo in range(1, lm + 1) if f"{y2 - 1:02d}.{mo:02d}" in by)
    py = [by.get(f"{y2 - 1:02d}.{mo:02d}") for mo in range(1, 13)]
    ppy = [by.get(f"{y2 - 2:02d}.{mo:02d}") for mo in range(1, 13)]
    kp = [(f"{lm}월", f"{cur:.2f}조", cy),
          (f"1~{lm}월 누계", f"{ytd:.1f}조", (ytd / ytd0 - 1) * 100 if ytd0 else None)]
    if all(py):
        a = sum(m["L"][ch] for m in py)
        b = sum(m["L"][ch] for m in ppy) if all(ppy) else None
        kp.append((f"20{y2 - 1:02d} 연간", f"{a:.1f}조", (a / b - 1) * 100 if b else None))
    for i, (t, v, g) in enumerate(kp):
        x0 = 0.03 + i * 0.25
        fig.text(x0, 0.845, t, fontsize=10.5, color=MUT, ha="left")
        fig.text(x0, 0.795, v, fontsize=18, color=INK, ha="left", fontweight="bold")
        if g is not None:
            fig.text(x0, 0.755, f"전년비 {g:+.1f}%", fontsize=10.5, color=UP if g > 0 else DN, ha="left")
    fig.text(0.03, 0.975, f"{CH[ch]} — 월별 실액(조원)", fontsize=17, color=INK, fontweight="bold", ha="left", va="top")
    fig.text(0.03, 0.912, "회색 = 재작년·작년 같은 달 · 금색 = 올해 · 막대 위 % = 올해 전년비", fontsize=11, color=MUT, ha="left", va="top")
    foot(fig, "실액 = 조사표본 기준 추정(점포당 매출×점포수, '26.08~ 작년 같은 달×(1+공식 전년비)) · 누계·연간 전년비는 계산값 · * = 실액으로 환산")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.645, bottom=0.12)
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
            f"실액은 조사표본 기준 추정. 그래프 7장(한눈에 · 품목 기여 · 추이 · 업태별 실액)은 이어서 보낸다. 대시보드: 유통 종목 페이지 손익 탭 · <a href=\"{SITE}\">{SITE}</a></p>")
    plain = (f"{mo}월 유통업체 매출 — 전체 {sgn(hd.get('전체'))}% (오프 {sgn(hd.get('오프라인'))} · 온 {sgn(hd.get('온라인'))}){ev}\n" +
             "\n".join(re.sub("<[^>]+>", "", l) for l in lines))
    return html, plain


def make_pngs(R, d):
    """(경로, 캡션) 목록 — 보는 순서: 이번 달 한눈에 → 무엇이 움직였나 → 추이 → 업태별 실액."""
    os.makedirs(d, exist_ok=True)
    M = R["months"]
    mo, pmo = int(M[-1]["ym"][3:]), int(M[-2]["ym"][3:])
    out = []
    p = os.path.join(d, "1_now.png"); fig_now(M, p)
    out.append((p, f"① {mo}월 한눈에 — 막대 = {mo}월 전년비(빨강 증가·파랑 감소), 검은 세로선 = {pmo}월"))
    p = os.path.join(d, "2_drivers.png"); fig_drivers(M, p)
    out.append((p, f"② {mo}월 무엇이 움직였나 — 품목이 업태 전년비에 보탠 몫(%p). 막대를 다 더하면 업태 전년비"))
    p = os.path.join(d, "3_trend.png"); fig_trend(M, p)
    out.append((p, "③ 최근 13개월 전년비 — 막대 하나 = 한 달"))
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"4{i}_{c}_years.png"); fig_years(M, c, p)
        out.append((p, f"④ {CH[c]} 월별 실액 — 회색 재작년·작년, 금색 올해, 막대 위 % = 올해 전년비"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png"); ap.add_argument("--send", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    R = load()
    ym = R["months"][-1]["ym"]
    if a.png:
        for p, c in make_pngs(R, a.png):
            print(p, "|", c)
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
    pics = make_pngs(R, "retail_png")
    pngs = [p for p, _ in pics]
    ok2 = tg.send_photos(pngs, captions=[c for _, c in pics])
    if ok1 and ok2:
        json.dump({"sent": ym, "at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "table": tg.RICH_MODE, "photos": len(pngs)},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[retail_report] {ym} 보냄")
    else:
        sys.exit(f"[retail_report] 전송 실패 (표 {ok1} · 그래프 {ok2})")


if __name__ == "__main__":
    main()
