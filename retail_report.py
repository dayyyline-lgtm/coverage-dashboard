# -*- coding: utf-8 -*-
"""산업부 유통업체 매출동향 → 텔레그램 (2026-10-29 · 사용자 "숫자만 보내면 보기 힘드니 그래프로")

RETAIL 블록(public/index.html)에서 그래프 PNG 11장(앨범 둘) + 표 메시지 한 통을 만들어 보낸다.
  ① 표(sendRichMessage · 테두리 표): 업태별 최근 6개월 전년비 + 최신 달 품목 전년비·실액 + 자동 요약(기여 상위 품목 · 계산값)
  ② 앨범(sendMediaGroup · 사진마다 읽는 법 캡션): ① 이번 달 업태별 전년비(막대 + 전월 세로선) ② 품목별 기여(%p · 합 = 업태 전년비)
     ③ 업태별 기여 월별(품목군 4개 누적 막대 + 합계 가로줄 · '25.01~ · 사용자 "시계열 비교가 안 돼서") ④ 최근 13개월 전년비 막대
     ⑤ 업태별 '최근 3개년 같은 달' 실액 막대 4장(두 번째 앨범) — 폰에서 읽히게 글씨를 키워 그린다(DPI 200)
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
import matplotlib.patches  # noqa: F401  (범례 Patch)
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
BAND = "#f1f2f4"                           # 명절 달 배경 띠(눈금선보다 옅게)
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


def ev_bands(ax, months, xs, other=(), fs=9):
    """명절 달 = 옅은 회색 띠(이어진 달은 한 띠 · 8월 추석 선판매 + 9월 추석 → '추석' 하나) + 띠 안 위쪽에 이름.
       other = 띠 없이 이름만(휴업·편입). 눈금 아래 셋째 줄에 두면 이웃 달 글씨가 붙고 텔레그램 캡션에 가린다.
       글씨 자리가 막대와 안 겹치게 부르는 쪽이 y 위쪽 여백을 남긴다."""
    trx = _blend(ax.transData, ax.transAxes)
    runs = []
    for xi, m in zip(xs, months):
        e = ev_short(m.get("ev"))
        h = next((k for k in ("설", "추석") if e.startswith(k)), None)
        if h:
            if runs and runs[-1][0] == h and runs[-1][2] == xi - 1:
                runs[-1][2] = xi
            else:
                runs.append([h, xi, xi])
        elif e in other:
            ax.text(xi, 0.985, e, transform=trx, fontsize=fs, color=MUT, ha="center", va="top", zorder=5)
    for h, a, b in runs:
        ax.axvspan(a - 0.5, b + 0.5, color=BAND, lw=0, zorder=0)
        ax.text((a + b) / 2, 0.985, h, transform=trx, fontsize=fs, color=MUT, ha="center", va="top", zorder=5)


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


# ── ②-b 품목 기여의 월별 추이: 품목군 4개 누적 막대 + 합계 가로줄 ────────────
# 품목을 다 쌓으면 색이 8개라 폰에서 안 읽힌다 → 업태마다 4개 품목군. 색은 빨강·파랑(등락)과 겹치지 않는 한 벌(검증 통과).
MIX_COL = ["#c98500", "#199e70", "#6250d6", "#d55181"]
MIX = {
    "B": [("명품", ["명품"]), ("식품", ["식품"]), ("의류", ["여성정장", "여성캐주얼", "남성의류", "아동스포츠"]), ("잡화·가정", ["잡화", "가정용품"])],
    "M": [("식품", ["식품"]), ("가전·문화", ["가전문화"]), ("의류·잡화·스포츠", ["의류", "잡화", "스포츠"]), ("가정생활·기타", ["가정생활", "기타"])],
    "C": [("음료 등 가공", ["가공식품"]), ("즉석·신선", ["즉석신선"]), ("담배 등", ["담배등"]), ("생활용품·잡화", ["생활용품", "잡화"])],
    "S": [("농수축산", ["농수축산"]), ("신선·조리", ["신선조리"]), ("가공식품", ["가공식품"]), ("비식품", ["일상용품", "생활잡화"])],
}


def mix_series(M, ch):
    """월별 품목군 기여(%p) — 실액·비중으로 낸 계산값. 막대 합 = 실액 기준 업태 전년비."""
    rows = []
    for j in range(12, len(M)):
        base = M[j - 12]["L"][ch]
        g = [(sum((M[j]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks) -
              sum((M[j - 12]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)) / base * 100 for _, ks in MIX[ch]]
        rows.append((M[j], g))
    return rows


def fig_mix(M, ch, path):
    rows = mix_series(M, ch)
    x = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(7.6, 5.8), dpi=DPI)
    fig.patch.set_facecolor("white")
    style(ax)
    W = 0.72
    pos, neg = [0.0] * len(rows), [0.0] * len(rows)
    span0 = (max([0] + [sum(a for a in g if a > 0) for _, g in rows]) -
             min([0] + [sum(a for a in g if a < 0) for _, g in rows])) or 1
    hand = []
    for gi, ((nm, _), col) in enumerate(zip(MIX[ch], MIX_COL)):
        v = [g[gi] for _, g in rows]
        bot = [pos[i] if a >= 0 else neg[i] for i, a in enumerate(v)]
        # 축 높이의 0.6% 밑(그림에서 4px 안쪽) 조각은 그리지 않는다 — 흰 테두리 두 줄만 남아 막대가 갈라진 것처럼 보인다
        keep = [abs(a) >= span0 * 0.006 for a in v]
        ax.bar([xi for xi, k in zip(x, keep) if k], [a for a, k in zip(v, keep) if k],
               bottom=[b for b, k in zip(bot, keep) if k], width=W, color=col, edgecolor="white", linewidth=0.7, zorder=2)
        hand.append(matplotlib.patches.Patch(color=col, label=f"{nm}  {v[-1]:+.1f}"))
        for i, a in enumerate(v):
            if a >= 0:
                pos[i] += a
            else:
                neg[i] += a
    tot = [sum(g) for _, g in rows]
    # 합계 = 막대보다 넓은 검은 가로줄 — 막대 양옆으로 삐져나와 조각 경계가 아니라 '표시'로 읽힌다
    tx, ty = [], []
    for xi, t in zip(x, tot):
        tx += [xi - 0.47, xi + 0.47, float("nan")]
        ty += [t, t, float("nan")]
    # 흰 테두리는 두르지 않는다 — 두르면 막대 끝을 몇 px 가려 합계가 막대보다 높이 떠 보인다
    tl, = ax.plot(tx, ty, color=INK, lw=2.6, solid_capstyle="butt", zorder=4, label=f"합계  {tot[-1]:+.1f}")
    hand.insert(0, tl)
    ax.axhline(0, color=G2, lw=1.1, zorder=3)
    lo, hi = min(neg + tot + [0]), max(pos + tot + [0])
    sp = hi - lo or 1
    ax.set_ylim(lo - sp * 0.06, hi + sp * 0.17)          # 위 여백 = 명절 글씨 자리
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: "0" if abs(v) < 1e-9 else f"{v:+g}"))
    ax.tick_params(axis="y", labelsize=10)
    labs = []
    for m, _ in rows:
        mm = int(m["ym"][3:])
        labs.append(f"{mm}" + (f"\n'{m['ym'][:2]}" if (mm == 1 or m is rows[0][0]) else ""))
    ev_bands(ax, [m for m, _ in rows], x, other=("휴업",) if ch == "M" else ())
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=9.5, color=INK, linespacing=1.1)
    ax.set_xlim(-0.6, len(x) - 0.4)
    ax.legend(handles=hand, loc="lower left", bbox_to_anchor=(0, 1.01), ncol=5, frameon=False, fontsize=10, handlelength=1.1,
              columnspacing=1.0, handletextpad=0.4)
    last = rows[-1][0]
    mo = int(last["ym"][3:])
    fig.text(0.03, 0.975, f"{CH[ch]} — 전년비를 만든 품목, 월별", fontsize=17, color=INK, fontweight="bold", ha="left", va="top")
    fig.text(0.03, 0.915, "막대 = 품목군이 업태 전년비에 보탠 몫(%p) · 0 위 = 끌어올림, 아래 = 끌어내림\n"
                          f"검은 가로줄 = 합계(업태 전년비) · 범례 숫자 = {mo}월 값", fontsize=11, color=MUT, ha="left", va="top", linespacing=1.45)
    foot(fig, "회색 띠 = 명절 달(추석 앞 선판매 달 포함) · 실액 × 붙임 품목 비중으로 낸 계산값 — 합계는 실액 기준이라\n"
              "붙임 공식 전년비와 몇 달은 조금 다르다 · 아주 작은 조각(축의 0.6% 밑)은 그리지 않았다")
    fig.subplots_adjust(left=0.08, right=0.98, top=0.74, bottom=0.16)
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
        vv = [a for a in v if a is not None]
        lo, hi = min(0, min(vv)), max(0, max(vv))
        sp = (hi - lo) or 1
        # 0 에 아주 가까운 달(SSM '25.9 -0.2%)은 막대가 0 선에 묻혀 '빈 달'처럼 보인다 → 축의 1.5% 짜리 짧은 막대로
        ax.bar(x, [0 if not a else (a if abs(a) >= sp * 0.015 else sp * 0.015 * (1 if a > 0 else -1)) for a in v],
               width=0.7, color=[UP if (a or 0) > 0 else DN for a in v], zorder=2)
        ax.axhline(0, color=G2, lw=1, zorder=3)
        ax.set_ylim(lo - sp * (0.12 if lo < 0 else 0.04), hi + sp * (0.24 if i == 0 else 0.12))
        if i == 0:
            ev_bands(ax, Y, x, other=("휴업", "편입"), fs=9.5)
        if v[-1] is not None:
            ax.text(1.0, 1.03, f"{int(Y[-1]['ym'][3:])}월 {v[-1]:+.1f}%", transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=12.5 if i == 0 else 11.5, fontweight="bold", color=UP if v[-1] > 0 else DN if v[-1] < 0 else MUT)
        labs = []
        for m in Y:
            mm = int(m["ym"][3:])
            labs.append(f"{mm}" + (f"\n'{m['ym'][:2]}" if (mm == 1 or m is Y[0]) else ""))
        ax.set_xticks(x)
        ax.set_xticklabels(labs, fontsize=9.5 if i == 0 else 8.5, linespacing=1.1)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10]))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda val, _: "0" if abs(val) < 1e-9 else f"{val:+g}"))
        ax.tick_params(axis="y", labelsize=9)
        ax.set_title(nm, fontsize=14 if i == 0 else 12.5, color=INK, loc="left", fontweight="bold", pad=6)
    heading(fig, f"전년동월비 추이 — 최근 {len(Y)}개월",
            "막대 하나 = 한 달 (빨강 증가 · 파랑 감소) · 칸마다 자기 축\n맨 위 칸 회색 띠 = 명절 달 · 위쪽 작은 글씨 = 그 달 사정")
    foot(fig, "산업통상부 주요 유통업체 매출 동향 · 칸 오른쪽 위 = 마지막 달 전년비 · 0 에 아주 가까운 달은 짧은 막대로 표시")
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


# ── 브리핑: 업태마다 #태그 · 흐름 · 국면 · 바뀐 것 · 식품/비식품 · 건수·단가 ──────────
# 국면 = 최근 3개월 평균 전년비 vs 직전 3개월 평균(1%p 넘게 달라야 가속·둔화). 판정은 이 식 하나 — 문구만 바꿔 쓴다.
PHASE = {
    "가속": ("좋아지는 중 (가속)", "플러스 폭이 커지고 있다"),
    "둔화": ("꺾이는 중 (둔화)", "아직 플러스지만 폭이 줄고 있다"),
    "유지+": ("비슷 (플러스 유지)", "비슷한 폭의 플러스가 이어진다"),
    "플전": ("좋아지는 중 (플러스 전환)", "마이너스에서 플러스로 돌아섰다"),
    "완화": ("바닥 다지는 중 (감소 완화)", "아직 마이너스지만 폭이 줄고 있다"),
    "심화": ("나빠지는 중 (감소 심화)", "마이너스 폭이 커지고 있다"),
    "마전": ("나빠지는 중 (마이너스 전환)", "플러스에서 마이너스로 돌아섰다"),
    "유지-": ("부진 지속", "비슷한 폭의 마이너스가 이어진다"),
}
GOOD, BAD = {"가속", "플전", "완화"}, {"둔화", "심화", "마전"}
FOOD = {"B": ("식품", "비식품 계"), "M": ("식품", "비식품 계"), "C": ("식품 계", "비식품 계"), "S": ("식품 계", "비식품 계")}
O_NAMES = ["가전/전자", "도서/문구", "패션/의류", "화장품", "아동/유아", "스포츠", "식품", "생활/가구", "서비스/기타"]


def phase_of(s):
    r, p = sum(s[-3:]) / 3, sum(s[-6:-3]) / 3
    if p <= 0 < r:
        k = "플전"
    elif r <= 0 < p:
        k = "마전"
    elif r > 0:
        k = "가속" if r - p >= 1 else "둔화" if p - r >= 1 else "유지+"
    else:
        k = "완화" if r - p >= 1 else "심화" if p - r >= 1 else "유지-"
    return k, r, p


def item_contrib(M, ch, j, ks):
    base = M[j - 12]["L"][ch]
    return (sum((M[j]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks) -
            sum((M[j - 12]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)) / base * 100


def holiday_shift(M):
    """(최근 두 달에 명절 시점 차이가 있나, 머리 문구) — 올해 명절 달이 작년과 다르면 그 앞뒤 달 전년비가 부풀거나 꺼진다."""
    last = M[-1]
    shift = False
    for m in M[-2:]:
        e = m.get("ev") or ""
        h = "추석" if "추석" in e else "설" if e.startswith("설") else ""
        if h:
            ly = next((x for x in M if x["ym"] == f"{int(m['ym'][:2]) - 1:02d}.{m['ym'][3:]}"), None)
            if not ly or h not in (ly.get("ev") or ""):
                shift = True
    e = last.get("ev") or ""
    h = "추석" if "추석" in e else "설" if e.startswith("설") else ""
    note = ""
    if h and "선판매" not in e:
        y, mo = int(last["ym"][:2]), int(last["ym"][3:])
        ly = [x for x in M if x["ym"].startswith(f"{y - 1:02d}.") and h in (x.get("ev") or "") and "선판매" not in (x.get("ev") or "")]
        if ly:
            lmo = int(ly[0]["ym"][3:])
            day = re.search(r"\(([^)]+)\)", e)
            lday = re.search(r"\(([^)]+)\)", ly[0]["ev"])
            when = f"올해 {day.group(1) if day else f'{mo}월'} · 작년 {lday.group(1) if lday else f'{lmo}월'}"
            pre = M[-2] if "선판매" in (M[-2].get("ev") or "") else None
            span = f"{int(pre['ym'][3:])}~{mo}월" if pre else f"{mo}월"
            if lmo > mo:
                note = (f"{h} 시점: {when} → {span} 전년비는 명절 매출 덕에 부풀었고, "
                        f"{lmo}월은 작년 {h} 달이라 낮게 나오기 쉽다")
            elif lmo < mo:
                note = f"{h} 시점: {when} → {lmo}월은 작년 {h} 달이라 낮았고, 올해 {mo}월은 명절이 늦게 와 부풀었다"
    return shift, note


def brief(R):
    """(머리 html, 업태 섹션 html, 평문) — 업태마다 '#백화점 +8.4%' 머리 + 흐름 · 국면 · 바뀐 것 · 식품/비식품 · 건수·단가."""
    M = [m for m in R["months"] if m.get("yoy")]
    j = len(R["months"]) - 1
    MM = R["months"]
    last, prev = MM[-1], MM[-2]
    mo, pmo = int(last["ym"][3:]), int(prev["ym"][3:])
    shift, hnote = holiday_shift(MM)
    secs, plains, verdict = [], [], {}
    foodonly, tag_of = set(), CH_SHORT

    def flow(series, months):
        path = " → ".join(f"{int(m['ym'][3:])}월 {v:+.1f}" for m, v in zip(months[-4:], series[-4:]))
        st, d = 0, 0
        for a, b in zip(series[::-1][1:], series[::-1]):    # 끝에서부터 같은 방향으로 몇 달 움직였나
            dd = 1 if b > a else -1 if b < a else 0
            if st == 0:
                d = dd
            if dd != d or dd == 0:
                break
            st += 1
        tail = f" (전년비 {st}개월 연속 {'높아짐' if d > 0 else '낮아짐'})" if st >= 3 else ""
        sg = 1 if series[-1] > 0 else -1
        run = 0
        for v in series[::-1]:
            if (v > 0) == (sg > 0) and v != 0:
                run += 1
            else:
                break
        if 1 <= run <= 4 and run < len(series):
            tail += f" · {int(months[-run]['ym'][3:])}월부터 {'플러스' if sg > 0 else '마이너스'}"
        return path + tail

    def section(tag, series, months, extra):
        k, r, p = phase_of(series)
        verdict[tag] = k
        bold, why = PHASE[k]
        lines = [f"<b>#{tag} {series[-1]:+.1f}%</b> ({pmo}월 {series[-2]:+.1f})",
                 f"국면: <b>{bold}</b> — {why} · 최근 3개월 평균 {r:+.1f}% (직전 3개월 {p:+.1f}%)",
                 f"흐름: {flow(series, months)}"]
        if k in BAD and series[-1] - series[-2] >= 1.5:
            lines.append(f"→ 다만 이번 달은 반등 ({series[-2]:+.1f} → {series[-1]:+.1f})")
        if k in GOOD and series[-2] - series[-1] >= 1.5:
            lines.append(f"→ 다만 이번 달은 주춤 ({series[-2]:+.1f} → {series[-1]:+.1f})")
        lines += extra(k, series)
        secs.append("<p>" + "<br>".join(lines) + "</p>")
        plains.append("\n".join(re.sub("<[^>]+>", "", l) for l in lines))

    for c in "BMCS":
        ser = [tot_yoy(m, c) for m in M]
        ok = [(m, v) for m, v in zip(M, ser) if v is not None]
        months, series = [m for m, _ in ok], [v for _, v in ok]

        def extra(k, series, c=c):
            out = []
            jj = [MM.index(m) for m in MM[-6:]]
            leaf = [(nm, ks) for nm, ks, _ in ITEMS[c] if ks != "L" and not nm.endswith(" 계")]
            ch_ = sorted(((nm, item_contrib(MM, c, j - 1, ks), item_contrib(MM, c, j, ks)) for nm, ks in leaf),
                         key=lambda t: -abs(t[2] - t[1]))
            mv = [f"{esc(nm)} {a:+.1f} → {b:+.1f}%p" for nm, a, b in ch_[:2] if abs(b - a) >= 0.3]
            if mv:
                out.append("바뀐 것: " + " · ".join(mv) + f" (기여 {pmo}월 → {mo}월)")
            fk, nk = FOOD[c]
            fks = next(ks for nm, ks, _ in ITEMS[c] if nm == fk)
            nks = next(ks for nm, ks, _ in ITEMS[c] if nm == nk)
            f0, f1 = item_contrib(MM, c, j - 1, fks), item_contrib(MM, c, j, fks)
            n0, n1 = item_contrib(MM, c, j - 1, nks), item_contrib(MM, c, j, nks)
            out.append(f"기여: 식품 {f1:+.1f}%p · 비식품 {n1:+.1f}%p ({pmo}월 {f0:+.1f} · {n0:+.1f})")
            up_now = k in GOOD or series[-1] - series[-2] >= 1.5
            if shift and up_now:
                nr = sum(item_contrib(MM, c, x, nks) for x in jj[-2:]) / 2
                npv = sum(item_contrib(MM, c, x, nks) for x in jj[-5:-2]) / 3
                w0 = f"{int(MM[jj[-5]]['ym'][3:])}~{int(MM[jj[-3]]['ym'][3:])}월"
                w1 = f"{int(MM[jj[-2]]['ym'][3:])}~{mo}월"
                if nr - npv >= 1:
                    out.append(f"→ 명절 영향이 적은 비식품도 좋아졌다 ({w0} 평균 {npv:+.1f} → {w1} {nr:+.1f}%p) — 명절 효과만은 아니다")
                else:
                    foodonly.add(tag_of[c])
                    out.append(f"→ 좋아진 몫은 식품뿐 — 비식품은 {w0} 평균 {npv:+.1f} → {w1} {nr:+.1f}%p로 그대로. 명절 시점 효과일 수 있어 다음 달 확인")
            kp = last.get("kpi", {}).get(c) or {}
            n, u = kp.get("구매건수"), kp.get("구매단가")
            if n is not None and u is not None:
                who = "손님 수(건수)가 끌었다" if n > u else "객단가가 끌었다"
                if n < 0 and u < 0:
                    who = "건수·단가 둘 다 줄었다"
                txt = f"건수·단가: 구매건수 {n:+.1f}% · 구매단가 {u:+.1f}% → {who}"
                ps = kp.get("점포당 매출")
                if kp.get("점포 증가율") is not None:
                    txt += f" · 점포 수 {kp['점포 증가율']:+.1f}%"
                out.append(txt)
                if kp.get("점포 증가율") is None and ps is not None and series[-1] is not None:
                    implied = ((1 + series[-1] / 100) / (1 + ps / 100) - 1) * 100     # 합계 = 점포당 × 점포 수
                    if abs(implied) >= 3:
                        out.append(f"점포: 점포당 매출 {ps:+.1f}% vs 합계 {series[-1]:+.1f}% → 점포 수 약 {implied:+.0f}%"
                                   + (" — 점포가 줄었는데 합계가 플러스 = 남은 점포 매출이 크게 늘었다" if implied < 0 < series[-1] else ""))
            return out

        section(CH_SHORT[c], series, months, extra)

    # 온라인 — 품목 비중이 없어 품목 전년비로만
    on = [(m, head_yoy(m, "온라인")) for m in M if head_yoy(m, "온라인") is not None]

    def extra_on(k, series):
        out = []
        o1 = (last["yoy"].get("O") or [])[:9]
        o0 = (prev.get("yoy", {}).get("O") or [])[:9]
        if len(o1) == 9 and len(o0) == 9:
            ch_ = sorted(zip(O_NAMES, o0, o1), key=lambda t: -abs((t[2] or 0) - (t[1] or 0)))
            mv = [f"{nm} {a:+.1f} → {b:+.1f}%" for nm, a, b in ch_[:3] if a is not None and b is not None and abs(b - a) >= 3]
            if mv:
                out.append("바뀐 것: " + " · ".join(mv) + " (품목 전년비)")
            hi = sorted([(nm, v) for nm, v in zip(O_NAMES, o1) if v is not None], key=lambda t: -t[1])
            out.append(f"강한 품목: {hi[0][0]} {hi[0][1]:+.1f}% · {hi[1][0]} {hi[1][1]:+.1f}% / 약한 품목: {hi[-1][0]} {hi[-1][1]:+.1f}%")
        return out

    section("온라인", [v for _, v in on], [m for m, _ in on], extra_on)

    hd = last["yoy"]["head"]
    good = [t for t, k in verdict.items() if k in GOOD]
    bad = [t for t, k in verdict.items() if k in BAD]
    flat = [t for t, k in verdict.items() if k not in GOOD and k not in BAD]
    pe = (prev.get("yoy") or {}).get("head", {}).get("전체")
    hl = [f"<b>전체 {sgn(hd.get('전체'))}%</b> ({pmo}월 {sgn(pe)}) · 오프라인 {sgn(hd.get('오프라인'))}% · 온라인 {sgn(hd.get('온라인'))}%"]
    if good:
        hl.append("좋아지는 곳: <b>" + " · ".join(t + ("*" if t in foodonly else "") for t in good) + "</b>")
    if bad:
        hl.append("꺾이거나 나빠지는 곳: <b>" + " · ".join(bad) + "</b>")
    if flat:
        hl.append("비슷: " + " · ".join(flat))
    if any(t in foodonly for t in good):
        hl.append("* 좋아진 몫이 식품뿐 — 명절 시점 효과일 수 있다")
    if hnote:
        hl.append(esc(hnote))
    head = (f"<h2>{mo}월 유통업체 매출 브리핑</h2><p>{'<br>'.join(hl)}</p>")
    plain = (f"{mo}월 유통업체 매출 브리핑\n" + "\n".join(re.sub("<[^>]+>", "", l) for l in hl) + "\n\n" +
             "\n\n".join(plains))
    return head, "".join(secs), plain


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
    head, secs, plain = brief(R)
    html = (head + secs + t1 + t2 +
            f"<p>국면 = 최근 3개월 평균 전년비 vs 직전 3개월 평균(1%p 넘게 달라야 가속·둔화) · 기여 %p = (품목 실액 − 작년 같은 달) ÷ 작년 같은 달 업태 합계(계산값) · "
            f"* = 붙임에 품목 전년비가 없어 실액으로 환산 · 실액은 조사표본 기준 추정.<br>"
            f"출처 산업통상부 주요 유통업체 매출 동향 {esc(R.get('release', ''))} · 그래프 11장은 이어서 · 대시보드 유통 종목 페이지 손익 탭 <a href=\"{SITE}\">{SITE}</a></p>")
    return html, plain


def make_pngs(R, d):
    """[(경로, 캡션)] 묶음 둘 — ① 이번 달·기여·추이 ② 업태별 실액 3개년. 보는 순서대로.
       캡션은 한 줄 이름만 — 읽는 법은 그림 안 부제에 있다. 길게 쓰면 텔레그램 사진 보기에서 캡션이 그림 아래쪽을 덮는다."""
    os.makedirs(d, exist_ok=True)
    M = R["months"]
    mo, pmo = int(M[-1]["ym"][3:]), int(M[-2]["ym"][3:])
    a, b = [], []
    p = os.path.join(d, "1_now.png"); fig_now(M, p)
    a.append((p, f"① {mo}월 업태별 전년비"))
    p = os.path.join(d, "2_drivers.png"); fig_drivers(M, p)
    a.append((p, f"② {mo}월 품목별 기여(%p)"))
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"3{i}_{c}_mix.png"); fig_mix(M, c, p)
        a.append((p, f"③ {CH[c]} · 품목 기여 월별"))
    p = os.path.join(d, "4_trend.png"); fig_trend(M, p)
    a.append((p, "④ 최근 13개월 전년비"))
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"5{i}_{c}_years.png"); fig_years(M, c, p)
        b.append((p, f"⑤ {CH[c]} · 월별 실액 3개년"))
    return a, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png"); ap.add_argument("--send", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    R = load()
    ym = R["months"][-1]["ym"]
    if a.png:
        for grp in make_pngs(R, a.png):
            for p, c in grp:
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
    groups = make_pngs(R, "retail_png")
    pngs = [p for g in groups for p, _ in g]
    ok2 = all([tg.send_photos([p for p, _ in g], captions=[c for _, c in g]) for g in groups])
    if ok1 and ok2:
        json.dump({"sent": ym, "at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "table": tg.RICH_MODE, "photos": len(pngs)},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[retail_report] {ym} 보냄")
    else:
        sys.exit(f"[retail_report] 전송 실패 (표 {ok1} · 그래프 {ok2})")


if __name__ == "__main__":
    main()
