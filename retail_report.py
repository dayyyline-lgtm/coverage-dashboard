# -*- coding: utf-8 -*-
"""산업부 유통업체 매출동향 → 텔레그램 (2026-10-29 · 사용자 "숫자만 보내면 보기 힘드니 그래프로")

RETAIL 블록(public/index.html)에서 메시지 넷을 만들어 이 순서로 보낸다(2026-10-29 사용자 "표 데이터 따로 · 브리핑 따로 · 사진 깔끔하게").
  ① 브리핑(sendRichMessage) — 요약 + 업태마다 '#백화점 +8.4%' 머리, 국면(굵게)·추이·변화·구성·명절 점검·객수/객단가. 리포트식 개조식.
  ② 데이터 표(sendRichMessage · 테두리 표) — 업태 6개월 · 업태별 품목(전년비·기여·실액) · 구매 지표 · 온라인 품목.
  ③ 그래프 앨범 둘(sendMediaGroup · 캡션 없음 — 캡션은 사진 보기에서 그림 아래쪽을 덮는다): ① 이번 달 업태별 전년비 ② 품목별 기여
     ③ 최근 13개월 추이 ④ 업태별 기여 월별 × 4 / ⑤ 업태별 최근 3개년 같은 달 실액 × 4. 모든 그림이 같은 틀(frame — 금색 머리줄 · 제목 · 부제 · 각주·출처).
  글꼴은 Pretendard(retail_report.yml 이 npm 으로 받아 RETAIL_FONT_DIR 로) — 없으면 나눔고딕.
같은 달은 한 번만 보낸다(retail_report_sent.json). 보내는 곳은 GitHub Actions(retail_report.yml) — 클라우드 세션은 텔레그램에 못 붙는다.

  RETAIL_FONT_DIR=… python retail_report.py --png DIR   # 그림·브리핑·표 html 만 만든다(점검용)
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


from matplotlib.lines import Line2D


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


def item_contrib(M, ch, j, ks):
    base = M[j - 12]["L"][ch]
    return (sum((M[j]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks) -
            sum((M[j - 12]["I"].get(ch) or {}).get(k, 0) or 0 for k in ks)) / base * 100


def holiday_info(M):
    """명절 시점 — (최근 두 달에 시점 차이가 있나, 짧은 문구 '추석 시점: 올해 9/25 · 작년 10/6', 영향 문구).
       올해 명절 달이 작년과 다르면 그 앞뒤 달 전년비가 부풀거나 꺼진다."""
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
    short = impact = ""
    if h and "선판매" not in e:
        y, mo = int(last["ym"][:2]), int(last["ym"][3:])
        ly = [x for x in M if x["ym"].startswith(f"{y - 1:02d}.") and h in (x.get("ev") or "") and "선판매" not in (x.get("ev") or "")]
        if ly:
            lmo = int(ly[0]["ym"][3:])
            day, lday = re.search(r"\(([^)]+)\)", e), re.search(r"\(([^)]+)\)", ly[0]["ev"])
            short = f"{h} 시점: 올해 {day.group(1) if day else f'{mo}월'} · 작년 {lday.group(1) if lday else f'{lmo}월'}"
            pre = M[-2] if "선판매" in (M[-2].get("ev") or "") else None
            span = f"{int(pre['ym'][3:])}~{mo}월" if pre else f"{mo}월"
            if lmo > mo:
                impact = f"{span} 전년비 상향 효과, {lmo}월은 역기저 부담"
            elif lmo < mo:
                impact = f"{lmo}월 전년비 하향, {mo}월 상향 효과"
    return shift, short, impact


# ── 그림 틀 — 모든 그림이 같은 머리·여백·꼬리 (2026-10-29 사용자 "사진들 디자인적으로 깔끔하게") ──────────
#   머리: 작은 금색 줄(자료·달) → 제목(결론) → 부제(읽는 법) · 꼬리: 가는 선 + 각주 + 출처
#   위치는 인치로 잡는다 — 그림 높이가 달라도 머리·꼬리 간격이 같아 넘겨 볼 때 들쭉날쭉하지 않다.
#   캡션은 달지 않는다 — 텔레그램 사진 보기에서 캡션이 그림 아래쪽을 덮는다(그림 제목이 이름 역할).
W_IN, LM, RM = 8.0, 0.5, 0.5
KICK, SRC = "", ""                     # make_pngs 가 채운다


def _font():
    """Pretendard 가 있으면 그것(retail_report.yml 이 npm 으로 받아 RETAIL_FONT_DIR 로 알려 준다) — 없으면 나눔고딕(koreanize)."""
    import glob
    from matplotlib import font_manager as fm
    d = os.environ.get("RETAIL_FONT_DIR", "")
    fs = sorted(glob.glob(os.path.join(d, "Pretendard-*.otf"))) if d else []
    if not fs:
        return "기본"
    for f in fs:
        fm.fontManager.addfont(f)
    plt.rcParams["font.family"] = "Pretendard"
    return "Pretendard"


FONT = _font()


def frame(h, title, sub=None, foot=None):
    fig = plt.figure(figsize=(W_IN, h), dpi=DPI)
    fig.patch.set_facecolor("white")
    x = LM / W_IN
    fig.text(x, 1 - 0.30 / h, KICK, fontsize=10, color=ACC, fontweight="bold", va="top")
    fig.text(x, 1 - 0.55 / h, title, fontsize=19, color=INK, fontweight="bold", va="top")
    if sub:
        fig.text(x, 1 - 1.00 / h, sub, fontsize=11.5, color=MUT, va="top", linespacing=1.55)
    lines = ([foot] if foot else []) + ([SRC] if SRC else [])
    n = len(lines)
    if n:
        fig.add_artist(Line2D([x, 1 - RM / W_IN], [(0.32 + 0.19 * n) / h] * 2, transform=fig.transFigure, color=G1, lw=0.8))
    for i, t in enumerate(lines):
        fig.text(x, (0.17 + 0.19 * (n - 1 - i)) / h, t, fontsize=8.8, color=MUT, va="bottom")
    return fig


def place(fig, h, top, bottom, left=None, right=None):
    """인치로 축 자리 — top·bottom = 그림 위·아래 끝에서 잰 거리."""
    l = LM if left is None else left
    r = RM if right is None else right
    return fig.add_axes([l / W_IN, bottom / h, (W_IN - l - r) / W_IN, (h - top - bottom) / h])


def style(ax, grid="y"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(G1)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(colors=MUT, labelsize=10, length=0, pad=6)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def pct(v, _=None):
    return "0" if abs(v) < 1e-9 else f"{v:+g}%"


def pp(v, _=None):
    return "0" if abs(v) < 1e-9 else f"{v:+g}"


def save(fig, path):
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ── ① 이번 달 한눈에: 업태별 전년비 막대 + 전월 눈금 ─────────────────────────
def fig_now(M, path):
    last, prev = M[-1], M[-2]
    mo, pmo = int(last["ym"][3:]), int(prev["ym"][3:])
    cur = [f(last) for _, f in SERIES]
    pv = [f(prev) for _, f in SERIES]
    ys = [0, 1, 2, 3.75, 4.75, 5.75, 6.75]
    vals = [v for v in cur + pv if v is not None]
    lo, hi = min(0, min(vals)), max(0, max(vals))
    pad = (hi - lo) * 0.05
    moves = sorted([(abs(c - p), nm, c, p) for (nm, _), c, p in zip(SERIES[1:], cur[1:], pv[1:])
                    if c is not None and p is not None and abs(c - p) >= 2], reverse=True)[:3]
    sub = ("크게 바뀐 곳  " + "  ·  ".join(f"{nm} {p:+.1f} → {c:+.1f}" for _, nm, c, p in moves)) if moves else f"{pmo}월과 비슷한 흐름"
    _, hs, _ = holiday_info(M)
    if hs:
        sub += "\n" + hs
    h = 7.0
    fig = frame(h, f"{mo}월 유통업체 매출 전년비 {cur[0]:+.1f}%", sub,
                foot=f"막대 = {mo}월 전년동월비(빨강 증가 · 파랑 감소) · 검은 눈금 = {pmo}월 · 전체 26개사 = 오프라인 15 + 온라인 11")
    left, right = 1.6, 1.95
    ax = place(fig, h, top=1.95 if hs else 1.7, bottom=1.05, left=left, right=right)
    style(ax, grid="x")
    ax.spines["bottom"].set_visible(False)
    for y, c, p in zip(ys, cur, pv):
        if c is not None:
            ax.barh(y, c, height=0.5, color=UP if c > 0 else DN, zorder=2)
        if p is not None:
            ax.plot([p, p], [y - 0.34, y + 0.34], color=INK, lw=2.0, zorder=3, solid_capstyle="butt")
    ax.axvline(0, color=G2, lw=1.0, zorder=1)
    ax.set_yticks(ys)
    ax.set_yticklabels([nm for nm, _ in SERIES], fontsize=13, color=INK)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_ylim(6.75 + 0.5, -0.95)
    ax.set_xlim(lo - pad, hi + pad)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(pct))
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))
    tr = _blend(ax.transAxes, ax.transData)
    aw = W_IN - left - right
    c1, c2, c0 = 1 + 0.32 / aw, 1 + 1.28 / aw, -(left - LM) / aw
    ax.text(c1, -0.7, f"{mo}월", transform=tr, fontsize=10.5, color=MUT, ha="left", va="center")
    ax.text(c2, -0.7, f"{pmo}월", transform=tr, fontsize=10.5, color=MUT, ha="left", va="center")
    ax.text(c0, -0.7, "합계", transform=tr, fontsize=10.5, color=MUT, ha="left", va="center")
    ax.text(c0, 3.05, "오프라인 업태", transform=tr, fontsize=10.5, color=MUT, ha="left", va="center")
    ax.add_artist(Line2D([c0, 1 + (right - RM) / aw], [2.65, 2.65], transform=tr, color=G1, lw=0.8, clip_on=False))
    for y, c, p in zip(ys, cur, pv):
        ax.text(c1, y, f"{c:+.1f}%" if c is not None else "—", transform=tr, fontsize=13.5, fontweight="bold",
                color=UP if (c or 0) > 0 else DN if (c or 0) < 0 else MUT, ha="left", va="center")
        ax.text(c2, y, f"{p:+.1f}" if p is not None else "—", transform=tr, fontsize=12, color=MUT, ha="left", va="center")
    save(fig, path)


# ── ② 무엇이 움직였나: 품목이 업태 전년비에 보탠 몫(%p) ─────────────────────
SHORT = {"해외유명(명품)": "명품", "음료 등 가공": "음료·가공", "가전/문화": "가전·문화", "가정/생활": "가정·생활"}


def fig_drivers(M, path):
    last = M[-1]
    mo = int(last["ym"][3:])
    rows = {c: item_rows(M, c) for c in "BMCS"}
    allv = [r[1] for c in rows for r in rows[c]]
    lo, hi = min(0, min(allv)), max(0, max(allv))
    span = hi - lo
    h = 9.2
    fig = frame(h, f"{mo}월 품목별 기여 — 무엇이 전년비를 움직였나",
                "막대 = 품목이 업태 전년비에 보탠 몫(%p) · 막대를 다 더하면 업태 전년비",
                foot="기여 = (품목 실액 − 작년 같은 달) ÷ 작년 같은 달 업태 합계 — 실액·비중으로 낸 계산값 · 품목 자체 전년비는 표 메시지")
    top0, bot0, title_h, gap, gx = 1.42, 0.85, 0.52, 0.42, 0.6
    n_top = max(len(rows["B"]), len(rows["M"]))
    n_bot = max(len(rows["C"]), len(rows["S"]))
    unit = (h - top0 - bot0 - 2 * title_h - gap) / (n_top + n_bot)
    col_w = (W_IN - LM - RM - gx) / 2
    lab_w = 1.05
    for idx, c in enumerate("BMCS"):
        r, k = divmod(idx, 2)
        R = rows[c]
        n_row = n_top if r == 0 else n_bot
        top = top0 + title_h + (0 if r == 0 else n_top * unit + gap + title_h)
        x0 = LM + k * (col_w + gx)
        ax = fig.add_axes([(x0 + lab_w) / W_IN, 1 - (top + n_row * unit) / h, (col_w - lab_w) / W_IN, n_row * unit / h])
        style(ax, grid=None)
        ax.spines["bottom"].set_visible(False)
        ys = list(range(len(R)))
        for y, (nm, v, iy, est) in zip(ys, R):
            ax.barh(y, v, height=0.56, color=UP if v > 0 else DN, zorder=2)
            ax.text(v + (span * 0.025 if v >= 0 else -span * 0.025), y, f"{v:+.1f}", fontsize=11, fontweight="bold",
                    color=INK, ha="left" if v >= 0 else "right", va="center")
        ax.axvline(0, color=G2, lw=1.0)
        ax.set_yticks(ys)
        ax.set_yticklabels([SHORT.get(nm, nm) for nm, *_ in R], fontsize=11.5, color=INK)
        ax.set_ylim(n_row - 0.5, -0.5)
        ax.set_xlim(lo - span * 0.22, hi + span * 0.22)
        ax.set_xticks([])
        t = tot_yoy(last, c)
        ty = 1 - (top - 0.16) / h
        fig.text(x0 / W_IN, ty, CH_SHORT[c], fontsize=14, color=INK, fontweight="bold", va="bottom")
        fig.text((x0 + col_w) / W_IN, ty, f"{t:+.1f}%", fontsize=14, fontweight="bold", ha="right", va="bottom",
                 color=UP if t > 0 else DN if t < 0 else MUT)
        fig.add_artist(Line2D([x0 / W_IN, (x0 + col_w) / W_IN], [ty - 0.07 / h] * 2, transform=fig.transFigure, color=G1, lw=0.8))
    save(fig, path)


# ── ③ 품목 기여의 월별 추이: 품목군 4개 누적 막대 + 합계 가로줄 ───────────────
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


def month_ticks(ax, months, x, fs=10):
    labs = []
    for i, m in enumerate(months):
        mm = int(m["ym"][3:])
        labs.append(f"{mm}" + (f"\n'{m['ym'][:2]}" if (mm == 1 or i == 0) else ""))
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=fs, color=MUT, linespacing=1.15)


def fig_mix(M, ch, path):
    rows = mix_series(M, ch)
    x = list(range(len(rows)))
    mo = int(rows[-1][0]["ym"][3:])
    h = 6.9
    fig = frame(h, f"{CH[ch]} — 전년비를 만든 품목, 월별",
                f"막대 = 품목군이 업태 전년비에 보탠 몫(%p) · 검은 가로줄 = 합계(업태 전년비) · 범례 숫자 = {mo}월",
                foot="회색 띠 = 명절 달(추석 앞 선판매 달 포함) · 실액 × 붙임 품목 비중으로 낸 계산값 · 축의 0.6% 밑 조각은 생략")
    ax = place(fig, h, top=1.9, bottom=1.25, left=0.9)
    style(ax)
    W = 0.7
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
    # 합계 = 막대보다 넓은 검은 가로줄 — 막대 양옆으로 삐져나와 조각 경계가 아니라 '표시'로 읽힌다(흰 테두리를 두르면 막대 끝을 가려 떠 보인다)
    tx, ty = [], []
    for xi, t in zip(x, tot):
        tx += [xi - 0.46, xi + 0.46, float("nan")]
        ty += [t, t, float("nan")]
    tl, = ax.plot(tx, ty, color=INK, lw=2.6, solid_capstyle="butt", zorder=4, label=f"합계  {tot[-1]:+.1f}")
    hand.insert(0, tl)
    ax.axhline(0, color=G2, lw=1.0, zorder=3)
    lo, hi = min(neg + tot + [0]), max(pos + tot + [0])
    sp = hi - lo or 1
    ax.set_ylim(lo - sp * 0.06, hi + sp * 0.17)          # 위 여백 = 명절 글씨 자리
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(pp))
    month_ticks(ax, [m for m, _ in rows], x)
    ev_bands(ax, [m for m, _ in rows], x, other=("휴업",) if ch == "M" else ())
    ax.set_xlim(-0.6, len(x) - 0.4)
    ax.legend(handles=hand, loc="lower left", bbox_to_anchor=(0, 1.03), ncol=5, frameon=False, fontsize=10.5,
              handlelength=1.0, columnspacing=1.3, handletextpad=0.45, borderaxespad=0)
    save(fig, path)


# ── ④ 최근 13개월 추이: 달마다 막대 하나 ───────────────────────────────────
def fig_trend(M, path):
    Y = [m for m in M if m.get("yoy")][-13:]
    x = list(range(len(Y)))
    h = 11.2
    fig = frame(h, f"전년동월비 추이 — 최근 {len(Y)}개월",
                "막대 하나 = 한 달(빨강 증가 · 파랑 감소) · 칸마다 자기 축 · 맨 위 칸 회색 띠 = 명절 달",
                foot="0 에 아주 가까운 달(±축의 1.5% 안)은 짧은 막대로 표시")
    top, bot = 1.42, 0.95
    title_h, tick_h = 0.42, 0.42
    avail = h - top - bot
    small_n = 3
    big = 2.0                                                       # 맨 위 칸 높이(인치)
    sm = (avail - (big + title_h + tick_h + 0.12) - small_n * (title_h + tick_h)) / small_n
    gx = 0.75
    cw = (W_IN - LM - RM - 0.45 - gx) / 2
    slots = [(LM + 0.45, top + title_h, W_IN - LM - RM - 0.45, big)]
    y0 = top + title_h + big + tick_h + 0.12
    for r in range(small_n):
        for k in range(2):
            slots.append((LM + 0.45 + k * (cw + gx), y0 + r * (sm + title_h + tick_h) + title_h, cw, sm))
    for i, ((xl, yt, w, hh), (nm, f)) in enumerate(zip(slots, SERIES)):
        ax = fig.add_axes([xl / W_IN, 1 - (yt + hh) / h, w / W_IN, hh / h])
        style(ax)
        v = [f(m) for m in Y]
        vv = [a for a in v if a is not None]
        lo, hi = min(0, min(vv)), max(0, max(vv))
        sp = (hi - lo) or 1
        # 0 에 아주 가까운 달(SSM '25.9 -0.2%)은 막대가 0 선에 묻혀 '빈 달'처럼 보인다 → 축의 1.5% 짧은 막대로
        ax.bar(x, [0 if not a else (a if abs(a) >= sp * 0.015 else sp * 0.015 * (1 if a > 0 else -1)) for a in v],
               width=0.68, color=[UP if (a or 0) > 0 else DN for a in v], zorder=2)
        ax.axhline(0, color=G2, lw=1, zorder=3)
        ax.set_ylim(lo - sp * (0.1 if lo < 0 else 0.03), hi + sp * (0.24 if i == 0 else 0.16))
        if i == 0:
            ev_bands(ax, Y, x, other=("휴업", "편입"), fs=9.5)
        month_ticks(ax, Y, x, fs=9.5 if i == 0 else 8.8)
        ax.set_xlim(-0.6, len(x) - 0.4)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=4, steps=[1, 2, 2.5, 5, 10]))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(pp))
        ax.tick_params(axis="y", labelsize=9)
        fs = 14 if i == 0 else 12.5
        fig.text(xl / W_IN - 0.45 / W_IN, 1 - (yt - 0.1) / h, nm, fontsize=fs, color=INK, fontweight="bold", va="bottom")
        if v[-1] is not None:
            fig.text((xl + w) / W_IN, 1 - (yt - 0.1) / h, f"{int(Y[-1]['ym'][3:])}월 {v[-1]:+.1f}%", fontsize=fs - 1, fontweight="bold",
                     ha="right", va="bottom", color=UP if v[-1] > 0 else DN if v[-1] < 0 else MUT)
    save(fig, path)


# ── ⑤ 업태별 최근 3개년 같은 달 실액 + 올해 막대 위 YoY + KPI 3개 ─────────────
def fig_years(M, ch, path):
    by = {m["ym"]: m for m in M}
    last = M[-1]["ym"]
    y2, lm = int(last[:2]), int(last[3:])
    yrs = [y2 - 2, y2 - 1, y2]
    _, yy = yoy_series(M, ch, "L", TOT[ch])
    yoy_of = {m["ym"]: yy[i] for i, m in enumerate(M)}
    h = 7.2
    fig = frame(h, f"{CH[ch]} — 월별 매출(조원)", "회색 = 재작년·작년 같은 달 · 금색 = 올해 · 막대 위 % = 올해 전년동월비",
                foot="실액 = 조사표본 기준 추정('26.08~ 작년 같은 달 × (1+공식 전년비)) · 누계·연간 전년비는 계산값 · * = 실액으로 환산")
    # KPI 3개
    cur = by[last]["L"][ch]
    cy = yoy_of.get(last, (None, True))[0]
    ytd = sum(by[f"{y2:02d}.{mo:02d}"]["L"][ch] for mo in range(1, lm + 1) if f"{y2:02d}.{mo:02d}" in by)
    ytd0 = sum(by[f"{y2 - 1:02d}.{mo:02d}"]["L"][ch] for mo in range(1, lm + 1) if f"{y2 - 1:02d}.{mo:02d}" in by)
    py = [by.get(f"{y2 - 1:02d}.{mo:02d}") for mo in range(1, 13)]
    ppy = [by.get(f"{y2 - 2:02d}.{mo:02d}") for mo in range(1, 13)]
    kp = [(f"{lm}월", f"{cur:.2f}조", cy), (f"1~{lm}월 누계", f"{ytd:.1f}조", (ytd / ytd0 - 1) * 100 if ytd0 else None)]
    if all(py):
        a = sum(m["L"][ch] for m in py)
        b = sum(m["L"][ch] for m in ppy) if all(ppy) else None
        kp.append((f"20{y2 - 1:02d} 연간", f"{a:.1f}조", (a / b - 1) * 100 if b else None))
    for i, (t, v, g) in enumerate(kp):
        x0 = (LM + i * 2.3) / W_IN
        fig.text(x0, 1 - 1.38 / h, t, fontsize=10.5, color=MUT, va="top")
        fig.text(x0, 1 - 1.62 / h, v, fontsize=20, color=INK, fontweight="bold", va="top")
        if g is not None:
            fig.text(x0, 1 - 2.0 / h, f"전년비 {g:+.1f}%", fontsize=10.5, color=UP if g > 0 else DN, va="top")
    ax = place(fig, h, top=2.75, bottom=1.25, left=0.85)
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
        ax.bar(xs, vs, width=w * 0.9, color=col, label=f"20{y:02d}", zorder=2)
        if y == y2:
            for x_, v_, mo in zip(xs, vs, ms):
                yv, est = yoy_of.get(f"{y:02d}.{mo:02d}", (None, True))
                if yv is None:
                    continue
                top = max(by[k]["L"][ch] for k in (f"{yy_:02d}.{mo:02d}" for yy_ in yrs) if k in by)
                ax.text(x_, top * 1.015, (f"{yv:+.1f}%" if abs(yv) < 1 else f"{yv:+.0f}%") + ("*" if est else ""), ha="center", va="bottom", fontsize=10,
                        color=UP if yv > 0 else DN if yv < 0 else MUT, fontweight="bold")
    ev = {int(k[3:]): ev_short(by[k].get("ev")) for k in by if k.startswith(f"{y2:02d}.") and by[k].get("ev")}
    ev = {k: v for k, v in ev.items() if v in ("설", "추석", "추석전", "설전") or (v == "휴업" and ch == "M")}
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([f"{mo}월" + (f"\n{ev[mo]}" if mo in ev else "") for mo in range(1, 13)], fontsize=10.5, color=MUT, linespacing=1.2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    vmax = max(m["L"][ch] for m in M)
    ax.set_ylim(0, vmax * 1.18)
    ax.set_xlim(0.45, 12.55)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.02), frameon=False, fontsize=10.5, ncol=3, handlelength=1.0,
              columnspacing=1.2, handletextpad=0.45, borderaxespad=0)
    save(fig, path)


# ── 표·브리핑 ─────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# 국면 = 최근 3개월 평균 전년비 vs 직전 3개월 평균(1%p 넘게 달라야 가속·둔화). 판정은 이 식 하나 — 문구만 바꿔 쓴다.
PHASE = {   # 짧은 이름(굵게) · 풀이
    "가속": ("가속", "증가 폭 확대"),
    "둔화": ("둔화", "증가 폭 축소"),
    "유지+": ("유지", "비슷한 증가세"),
    "플전": ("플러스 전환", "감소 → 증가"),
    "완화": ("감소 완화", "감소 폭 축소"),
    "심화": ("감소 심화", "감소 폭 확대"),
    "마전": ("마이너스 전환", "증가 → 감소"),
    "유지-": ("부진 지속", "비슷한 감소세"),
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


def rel(R):
    """'2026-10-28 11:00 (9월호)' → '9월호(10/28 발표)'"""
    s = R.get("release", "") or ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}).*?\(([^)]+)\)", s)
    return f"{m.group(4)}({int(m.group(2))}/{int(m.group(3))} 발표)" if m else s


def brief(R):
    """브리핑 메시지(rich html, 평문) — 요약 + 업태마다 '#백화점 +8.4%' 머리와 국면·추이·변화·구성·점검·객수/객단가.
       말투는 리포트식 개조식(명사형 끝맺음). 판정·계산은 여기 한 곳(phase_of · item_contrib)."""
    M = [m for m in R["months"] if m.get("yoy")]
    MM = R["months"]
    j = len(MM) - 1
    last, prev = MM[-1], MM[-2]
    mo, pmo = int(last["ym"][3:]), int(prev["ym"][3:])
    shift, hshort, himpact = holiday_info(MM)
    secs, verdict, foodonly = [], {}, set()

    def flow(series, months):
        ms = [int(m["ym"][3:]) for m in months[-4:]]
        txt = f"{ms[0]}~{ms[-1]}월 " + " → ".join(f"{v:+.1f}" for v in series[-4:]) + "%"
        st, d = 0, 0
        for a, b in zip(series[::-1][1:], series[::-1]):    # 끝에서부터 같은 방향으로 몇 달 움직였나
            dd = 1 if b > a else -1 if b < a else 0
            if st == 0:
                d = dd
            if dd != d or dd == 0:
                break
            st += 1
        if st >= 3:
            txt += f", 전년비 {st}개월 연속 {'상승' if d > 0 else '하락'}"
        sg = 1 if series[-1] > 0 else -1
        run = 0
        for v in series[::-1]:
            if (v > 0) == (sg > 0) and v != 0:
                run += 1
            else:
                break
        if 1 <= run <= 4 and run < len(series):
            txt += f", {int(months[-run]['ym'][3:])}월부터 {'플러스' if sg > 0 else '마이너스'}"
        return txt

    def section(tag, series, months, extra):
        k, r, p = phase_of(series)
        verdict[tag] = k
        nm, why = PHASE[k]
        L = [f"국면: <b>{nm}</b>({why}) — 최근 3개월 평균 {r:+.1f}%, 직전 3개월 {p:+.1f}%",
             f"추이: {flow(series, months)}"]
        if k in BAD and series[-1] - series[-2] >= 1.5:
            L.append(f"{mo}월은 반등({series[-2]:+.1f} → {series[-1]:+.1f}%)")
        if k in GOOD and series[-2] - series[-1] >= 1.5:
            L.append(f"{mo}월은 주춤({series[-2]:+.1f} → {series[-1]:+.1f}%)")
        L += extra(k, series)
        secs.append((f"#{tag} {series[-1]:+.1f}%", f"{pmo}월 {series[-2]:+.1f}%", L))

    for c in "BMCS":
        ok = [(m, tot_yoy(m, c)) for m in M if tot_yoy(m, c) is not None]
        months, series = [m for m, _ in ok], [v for _, v in ok]

        def extra(k, series, c=c):
            out = []
            jj = list(range(len(MM) - 6, len(MM)))
            leaf = [(nm, ks) for nm, ks, _ in ITEMS[c] if ks != "L" and not nm.endswith(" 계")]
            mv = sorted(((nm, item_contrib(MM, c, j - 1, ks), item_contrib(MM, c, j, ks)) for nm, ks in leaf),
                        key=lambda t: -abs(t[2] - t[1]))
            mv = [f"{esc(SHORT.get(nm, nm))} 기여 {a:+.1f} → {b:+.1f}%p" for nm, a, b in mv[:2] if abs(b - a) >= 0.3]
            if mv:
                out.append("변화: " + ", ".join(mv))
            fk, nk = FOOD[c]
            fks = next(ks for nm, ks, _ in ITEMS[c] if nm == fk)
            nks = next(ks for nm, ks, _ in ITEMS[c] if nm == nk)
            f0, f1 = item_contrib(MM, c, j - 1, fks), item_contrib(MM, c, j, fks)
            n0, n1 = item_contrib(MM, c, j - 1, nks), item_contrib(MM, c, j, nks)
            out.append(f"구성: 식품 {f1:+.1f}%p, 비식품 {n1:+.1f}%p ({pmo}월 {f0:+.1f}, {n0:+.1f}%p)")
            if shift and (k in GOOD or series[-1] - series[-2] >= 1.5):
                nr = sum(item_contrib(MM, c, x, nks) for x in jj[-2:]) / 2
                npv = sum(item_contrib(MM, c, x, nks) for x in jj[-5:-2]) / 3
                w0 = f"{int(MM[jj[-5]]['ym'][3:])}~{int(MM[jj[-3]]['ym'][3:])}월"
                w1 = f"{int(MM[jj[-2]]['ym'][3:])}~{mo}월"
                if nr - npv >= 1:
                    out.append(f"명절 점검: 비식품도 개선({w0} 평균 {npv:+.1f} → {w1} {nr:+.1f}%p) — 명절 효과만은 아님")
                else:
                    foodonly.add(CH_SHORT[c])
                    out.append(f"명절 점검: 개선은 식품에 국한(비식품 {w0} 평균 {npv:+.1f} → {w1} {nr:+.1f}%p) — 명절 효과 가능성, 다음 달 확인 필요")
            kp = last.get("kpi", {}).get(c) or {}
            n, u = kp.get("구매건수"), kp.get("구매단가")
            if n is not None and u is not None:
                who = "둘 다 감소" if n < 0 and u < 0 else ("객수 주도" if n > u else "객단가 주도")
                txt = f"객수·객단가: 구매건수 {n:+.1f}%, 구매단가 {u:+.1f}% — {who}"
                if kp.get("점포 증가율") is not None:
                    txt += f" (점포 수 {kp['점포 증가율']:+.1f}%)"
                out.append(txt)
                ps = kp.get("점포당 매출")
                if kp.get("점포 증가율") is None and ps is not None:
                    implied = ((1 + series[-1] / 100) / (1 + ps / 100) - 1) * 100     # 합계 = 점포당 × 점포 수
                    if abs(implied) >= 3:
                        out.append(f"점포: 점포당 매출 {ps:+.1f}% vs 합계 {series[-1]:+.1f}% → 점포 수 약 {abs(implied):.0f}% {'감소' if implied < 0 else '증가'} 추정"
                                   + (", 남은 점포 매출 급증" if implied < 0 < series[-1] else ""))
            return out

        section(CH_SHORT[c], series, months, extra)

    on = [(m, head_yoy(m, "온라인")) for m in M if head_yoy(m, "온라인") is not None]

    def extra_on(k, series):
        out = []
        o1, o0 = (last["yoy"].get("O") or [])[:9], (prev.get("yoy", {}).get("O") or [])[:9]
        if len(o1) == 9 and len(o0) == 9:
            mv = sorted(zip(O_NAMES, o0, o1), key=lambda t: -abs((t[2] or 0) - (t[1] or 0)))
            mv = [f"{nm} {a:+.1f} → {b:+.1f}%" for nm, a, b in mv[:3] if a is not None and b is not None and abs(b - a) >= 3]
            if mv:
                out.append("변화: " + ", ".join(mv))
            hi = sorted([(nm, v) for nm, v in zip(O_NAMES, o1) if v is not None], key=lambda t: -t[1])
            out.append(f"강약: 강세 {hi[0][0]} {hi[0][1]:+.1f}%, {hi[1][0]} {hi[1][1]:+.1f}% / 약세 {hi[-1][0]} {hi[-1][1]:+.1f}%")
        return out

    section("온라인", [v for _, v in on], [m for m, _ in on], extra_on)

    hd = last["yoy"]["head"]
    pe = (prev.get("yoy") or {}).get("head", {}).get("전체")
    good = [t for t, k in verdict.items() if k in GOOD]
    bad = [t for t, k in verdict.items() if k in BAD]
    flat = [t for t, k in verdict.items() if k not in GOOD and k not in BAD]
    S = [f"전체 <b>{sgn(hd.get('전체'))}%</b> ({pmo}월 {sgn(pe)}%) · 오프라인 {sgn(hd.get('오프라인'))}% · 온라인 {sgn(hd.get('온라인'))}%"]
    if good:
        S.append("개선: <b>" + ", ".join(t + ("*" if t in foodonly else "") for t in good) + "</b>")
    if bad:
        S.append("둔화·악화: <b>" + ", ".join(bad) + "</b>")
    if flat:
        S.append("보합: " + ", ".join(flat))
    if hshort:
        S.append(esc(hshort) + (f" — {esc(himpact)}" if himpact else ""))
    star = "* 식품만 개선 — 명절 효과 가능성" if any(t in foodonly for t in good) else ""
    bl = lambda xs: "<br>".join("▸ " + x for x in xs)
    html = (f"<h2>{mo}월 유통업체 매출 브리핑</h2>"
            f"<p>산업통상부 「주요 유통업체 매출 동향」 {esc(rel(R))} · 전년동월비 기준</p>"
            f"<h3>요약</h3><p>{bl(S)}{'<br>' + star if star else ''}</p>"
            + "".join(f"<h3>{t}</h3><p><i>{esc(pv)}</i><br>{bl(L)}</p>" for t, pv, L in secs)
            + "<p><i>국면 = 최근 3개월 평균 전년비와 직전 3개월 평균 비교(1%p 이상 차이) · 기여 = 실액·비중으로 낸 계산값 · 데이터 표와 그래프는 이어서</i></p>")
    strip = lambda s: re.sub("<[^>]+>", "", s)
    plain = (f"{mo}월 유통업체 매출 브리핑 — {rel(R)}\n\n[요약]\n" + "\n".join("▸ " + strip(x) for x in S) + (f"\n{star}" if star else "")
             + "".join(f"\n\n{t} ({pv})\n" + "\n".join("▸ " + strip(x) for x in L) for t, pv, L in secs))
    return html, plain


def tables(R):
    """데이터 표 메시지(rich html, 평문) — 업태 6개월 · 업태별 품목(전년비·기여·실액) · 구매 지표 · 온라인 품목."""
    M = R["months"]
    last, prev = M[-1], M[-2]
    j = len(M) - 1
    mo, pmo = int(last["ym"][3:]), int(prev["ym"][3:])
    Y = [m for m in M if m.get("yoy")][-6:]
    td = lambda s, al="right": f'<td align="{al}">{s}</td>'
    th = lambda s, al="right": f'<th align="{al}">{s}</th>'
    out = [f"<h2>{mo}월 유통업체 매출 — 데이터</h2>",
           f"<p>{esc(rel(R))} · 전년동월비 % · 기여 %p · 실액 조원(조사표본 기준 추정) · * 붙임에 없어 실액으로 환산</p>"]
    rows = [("전체", lambda m: head_yoy(m, "전체")), ("오프라인", lambda m: head_yoy(m, "오프라인")),
            ("온라인", lambda m: head_yoy(m, "온라인"))] + [(CH_SHORT[c], (lambda c: lambda m: tot_yoy(m, c))(c)) for c in "BMCS"]
    t = "<table bordered><caption>업태별 전년동월비 · 최근 6개월</caption><tr>" + th("업태", "left") + \
        "".join(th(lab(m["ym"]) + (f"<br>{esc(ev_short(m['ev']))}" if m.get("ev") else "")) for m in Y) + "</tr>"
    for nm, f in rows:
        t += "<tr>" + td(f"<b>{nm}</b>", "left") + "".join(td(sgn(f(m))) for m in Y) + "</tr>"
    out.append(t + "</table>")
    for c in "BMCS":
        t = (f"<table bordered><caption>{CH[c]} · 품목</caption><tr>" + th("품목", "left") + th(f"{mo}월 %") + th(f"{pmo}월 %") +
             th(f"{mo}월 기여 %p") + th("실액(조)") + "</tr>")
        for nm, ks, col in ITEMS[c]:
            lv, yy = yoy_series(M, c, ks, col)
            b = nm == "합계" or nm.endswith(" 계")
            cb = "" if ks == "L" else f"{item_contrib(M, c, j, ks):+.1f}"
            star = lambda e: "*" if e[1] and e[0] is not None else ""
            t += "<tr>" + td(f"<b>{esc(nm)}</b>" if b else esc(nm), "left") + td(sgn(yy[-1][0]) + star(yy[-1])) + \
                td(sgn(yy[-2][0]) + star(yy[-2])) + td(cb) + td(f"{lv[-1]:.3f}") + "</tr>"
        out.append(t + "</table>")
    K = ["구매건수", "구매단가", "점포당 매출"]
    t = "<table bordered><caption>구매 지표 · 전년동월비 %</caption><tr>" + th("업태", "left") + \
        "".join(th(f"{k}<br>{mo}월") + th(f"{pmo}월") for k in K[:2]) + th(f"점포당 매출<br>{mo}월") + "</tr>"
    for c in "BMCS":
        k1, k0 = last.get("kpi", {}).get(c) or {}, prev.get("kpi", {}).get(c) or {}
        t += "<tr>" + td(f"<b>{CH_SHORT[c]}</b>", "left") + "".join(td(sgn(k1.get(k))) + td(sgn(k0.get(k))) for k in K[:2]) + \
            td(sgn(k1.get("점포당 매출"))) + "</tr>"
    out.append(t + "</table>")
    O = [m for m in M if (m.get("yoy") or {}).get("O")][-3:]
    if len(O) == 3:
        t = "<table bordered><caption>온라인 품목 · 전년동월비 %</caption><tr>" + th("품목", "left") + \
            "".join(th(f"{int(m['ym'][3:])}월") for m in O[::-1]) + "</tr>"
        for i, nm in enumerate(O_NAMES + ["합계"]):
            t += "<tr>" + td(f"<b>{nm}</b>" if nm == "합계" else nm, "left") + "".join(td(sgn((m["yoy"]["O"] + [None] * 10)[i])) for m in O[::-1]) + "</tr>"
        out.append(t + "</table>")
    out.append(f"<p><i>기여 = (품목 실액 − 작년 같은 달) ÷ 작년 같은 달 업태 합계(계산값) · 대시보드: 유통 종목 페이지 손익 탭 · <a href=\"{SITE}\">{SITE}</a></i></p>")
    html = "".join(out)
    plain = f"{mo}월 유통업체 매출 — 데이터 표는 텔레그램 리치 메시지로만 보낸다(이 기기에서 표가 안 보이면 대시보드에서): {SITE}"
    return html, plain


def make_pngs(R, d):
    """그림 묶음 둘 — ① 이번 달 · 품목 기여 · 13개월 추이 · 업태별 기여 월별 ② 업태별 실액 3개년. 보는 순서대로. 캡션 없음."""
    global KICK, SRC
    os.makedirs(d, exist_ok=True)
    M = R["months"]
    y, mo = int(M[-1]["ym"][:2]), int(M[-1]["ym"][3:])
    KICK = f"산업부 유통업체 매출동향 · 20{y:02d}년 {mo}월"
    SRC = f"자료: 산업통상부 「주요 유통업체 매출 동향」 {rel(R)} · 정리: 커버리지 대시보드"
    a, b = [], []
    p = os.path.join(d, "1_now.png"); fig_now(M, p); a.append(p)
    p = os.path.join(d, "2_drivers.png"); fig_drivers(M, p); a.append(p)
    p = os.path.join(d, "3_trend.png"); fig_trend(M, p); a.append(p)
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"4{i}_{c}_mix.png"); fig_mix(M, c, p); a.append(p)
    for i, c in enumerate("BMCS"):
        p = os.path.join(d, f"5{i}_{c}_years.png"); fig_years(M, c, p); b.append(p)
    return a, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png"); ap.add_argument("--send", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    R = load()
    ym = R["months"][-1]["ym"]
    if a.png:
        for grp in make_pngs(R, a.png):
            for p in grp:
                print(p)
        h1, p1 = brief(R)
        h2, _ = tables(R)
        open(os.path.join(a.png, "brief.html"), "w", encoding="utf-8").write(h1)
        open(os.path.join(a.png, "tables.html"), "w", encoding="utf-8").write(h2)
        print(f"[글꼴] {FONT}")
        print(p1)
        return
    if not a.send:
        sys.exit("--png DIR 또는 --send")
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    if st.get("sent") == ym and not a.force:
        print(f"[retail_report] {ym} 이미 보냄 — 생략"); return
    import telegram_send as tg
    if not tg.configured():
        sys.exit("[retail_report] 텔레그램 토큰·챗ID 없음")
    # 보내는 순서: ① 브리핑(글) ② 데이터 표 ③ 그래프 앨범 둘(캡션 없음)
    h1, p1 = brief(R)
    ok1 = tg.send_rich(h1, fallback=p1)
    m1 = tg.RICH_MODE
    h2, p2 = tables(R)
    ok2 = tg.send_rich(h2, fallback=p2)
    m2 = tg.RICH_MODE
    groups = make_pngs(R, "retail_png")
    ok3 = all([tg.send_photos(g) for g in groups])
    if ok1 and ok2 and ok3:
        json.dump({"sent": ym, "at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "brief": m1, "table": m2,
                   "photos": sum(len(g) for g in groups), "font": FONT},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[retail_report] {ym} 보냄")
    else:
        sys.exit(f"[retail_report] 전송 실패 (브리핑 {ok1} · 표 {ok2} · 그래프 {ok3})")


if __name__ == "__main__":
    main()
