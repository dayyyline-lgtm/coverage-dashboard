"""아마존 뷰티 베스트셀러 트래커 (US 탑100 + 유럽 5개국 탑50).

매일 1회 실행: 수집 -> 브랜드 필터 -> history.csv 누적 -> 전일 대비 변동 -> 텔레그램 발송.

사용법:
    python main.py                    # 수집 + 기록 + 텔레그램 발송
    python main.py --no-telegram      # 텔레그램 없이 테스트 (콘솔 출력만)
    python main.py --markets US,UK    # 특정 마켓만 (테스트용)
    python main.py --no-detail        # 31~50위 상세 보강 생략 (빠른 확인용)
"""

import os
import re
import csv
import sys
import shutil
import unicodedata
import argparse
import datetime
from pathlib import Path

import yaml
import requests

from scraper import scrape_all, BlockedError

BASE = Path(__file__).parent
HISTORY_COLS = ["date", "market", "brand", "asin", "title",
                "list_cat", "list_rank",
                "bsr_main", "bsr_main_cat", "bsr_sub", "bsr_sub_cat",
                "bought", "bought_period", "bought_m", "bought_w", "src", "parent_asin",
                "price", "currency", "rating", "reviews"]

FLAGS = {"US": "🇺🇸", "UK": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
         "IT": "🇮🇹", "ES": "🇪🇸", "NL": "🇳🇱", "SE": "🇸🇪", "PL": "🇵🇱", "JP": "🇯🇵"}
SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥"}
# 마켓 코드는 데이터에 그대로 쓰고(CSV·설정), 사람이 읽는 곳에서만 한글로 바꾼다
MK_NAMES = {"US": "미국", "UK": "영국", "DE": "독일", "FR": "프랑스", "IT": "이탈리아",
            "ES": "스페인", "NL": "네덜란드", "SE": "스웨덴", "PL": "폴란드", "JP": "일본"}


def mk_name(code):
    return MK_NAMES.get(code, code)
# EUR·GBP → USD 교차환율 (inject_amazon.py 와 같은 값)
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}


def load_config() -> dict:
    with open(BASE / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["data_dir"] = str(BASE / cfg.get("data_dir", "data"))
    resolve_telegram(cfg)
    return cfg


# config.yaml 템플릿의 자리표시자 — 값이 안 채워진 것으로 취급한다
_PLACEHOLDERS = {"", "None", "여기에_봇_토큰", "여기에_chat_id"}

# secrets_local.py 를 찾아볼 위치 (coverage-dashboard 규약과 공유)
_SECRET_DIRS = [BASE, BASE.parent, BASE.parent / "coverage-dashboard"]


def _read_secret(text: str, name: str) -> str:
    m = re.search(rf'{name}\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else ""


def resolve_telegram(cfg: dict) -> None:
    """토큰·챗ID를 찾아 cfg["telegram"]에 채운다.

    우선순위: 환경변수 > secrets_local.py > config.yaml
    coverage-dashboard가 쓰는 `secrets_local.py` 규약을 그대로 따라가므로,
    **봇을 새로 만들 필요 없이 기존 봇 토큰 하나를 두 프로젝트가 공유한다.**
    (secrets_local.py 는 코드로 실행하지 않고 값만 읽어온다.)
    """
    tg = cfg.setdefault("telegram", {})
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not (token and chat):
        for d in _SECRET_DIRS:
            f = d / "secrets_local.py"
            if not f.exists():
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            token = token or _read_secret(text, "TELEGRAM_BOT_TOKEN")
            chat = chat or _read_secret(text, "TELEGRAM_CHAT_ID")
            if token and chat:
                break

    cur_token = str(tg.get("bot_token") or "").strip()
    cur_chat = str(tg.get("chat_id") or "").strip()
    tg["bot_token"] = token or (cur_token if cur_token not in _PLACEHOLDERS else "")
    tg["chat_id"] = chat or (cur_chat if cur_chat not in _PLACEHOLDERS else "")


# ------------------------------------------------------------------ 히스토리

def load_history(path: Path) -> list[dict]:
    """기존 CSV를 읽는다.

    컬럼이 늘어난 것만으로 히스토리를 날리면 안 된다 — 빈 값으로 채워 이어간다.
    (실제로 bought_m/bought_w 를 추가했다가 그날 수집분 1,900행을 통째로 백업으로
    밀어낸 적이 있다.) 진짜로 못 이어붙이는 구버전, 즉 market 컬럼이 없어
    나라 구분이 안 되고 price 가 원화로 오염된 v1 스키마일 때만 새로 시작한다.
    """
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        if "market" not in cols:
            backup = path.with_name("history_v1_backup.csv")
            shutil.copy2(path, backup)
            print(f"[이전] 구버전(단일 마켓) history.csv를 {backup.name}로 백업하고 "
                  f"새 스키마로 시작합니다. "
                  f"(구버전 price 는 통화 설정 누락으로 원화 환산값이 섞여 재사용 불가)")
            return []
        rows = list(reader)
    added = [c for c in HISTORY_COLS if c not in cols]
    if added:
        print(f"[이전] 새 컬럼 {', '.join(added)} 추가 — 기존 {len(rows)}행은 빈 값으로 이어갑니다")
        for r in rows:
            for c in added:
                r.setdefault(c, "")
    return rows


def write_history(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ------------------------------------------------------------------ 리포트

def fmt_price(p, cur) -> str:
    if p in (None, "", "None"):
        return "-"
    try:
        return f"{SYMBOLS.get(cur, '')}{float(p):,.2f}"
    except (TypeError, ValueError):
        return "-"


def fmt_int(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "?"


def _i(v):
    """CSV에서 온 문자열/빈칸을 int 또는 None으로."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def esc(s):
    """텔레그램 HTML 모드에서 깨지지 않게 이스케이프."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mono(lines):
    """표를 고정폭 블록으로. 텔레그램 기본 폰트가 가변폭이라 이게 없으면 열이 어긋난다."""
    body = "\n".join(lines) if isinstance(lines, (list, tuple)) else lines
    return "<pre>" + esc(body) + "</pre>"


def _pad(s, w):
    """CJK 문자를 2칸으로 세는 폭 맞춤 (모노스페이스 정렬용)."""
    width = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
    return s + " " * max(0, w - width)


# 아마존 제목은 검색 키워드를 욱여넣어서 길다. 사람이 읽을 제품명만 남긴다.
# (원문은 history.csv 에 그대로 보존되므로 나중에 대조할 수 있다)
_CUT_SEPARATORS = re.compile(r"\s*[|–—•‧]\s*|\s+-\s+|\s*[(\[,;:]")
_SIZE = re.compile(
    r"\s*\b\d+([.,]\d+)?\s*(fl\.?\s?oz|oz|ml|mL|g\b|kg|pcs?|ea|count|ct|pack|"
    r"매|개|장|정)\.?", re.I)
_CONNECTORS = re.compile(
    r"\s+(with|for|and|mit|für|con|para|avec|pour|per|da|de|di|com)\s+.*$", re.I)
_TRAIL_JUNK = re.compile(r"[\s\-–—|,.&/]+$")


def clean_name(title, brand=""):
    """긴 아마존 제목 → 짧은 제품명. 'medicube Toner Pads Zero Pore Pad 2.0 |
    Dual-Textured Facial Pad for Exfoliating...' → 'Toner Pads Zero Pore Pad 2.0'"""
    s = unicodedata.normalize("NFKC", title or "").replace("\xa0", " ")
    if brand:
        s = re.sub(rf"^\s*{re.escape(brand)}[\s\-–—|,:]*", "", s, flags=re.I)
    s = _CUT_SEPARATORS.split(s, 1)[0]          # 첫 구분자 앞까지만
    s = _SIZE.sub("", s)
    s = _TRAIL_JUNK.sub("", s).strip()
    if len(s) > 46:                              # 아직 길면 서술 연결어에서 한 번 더 자른다
        s = _TRAIL_JUNK.sub("", _CONNECTORS.sub("", s)).strip()
    if len(s) > 46:
        s = s[:45].rsplit(" ", 1)[0] + "…"
    return s or (title or "")[:46]


def est_revenue(rows):
    """월 매출 추정 = Σ(아마존 공개 판매량 x 가격). 통화별로 나눠 반환.

    판매량 배지는 구간 하한(100K+ 는 10만 이상)이라 이 값도 **하한**이다.
    배지가 없는 제품은 빠지므로 실제 매출은 이보다 크다.
    """
    out = {}
    for r in rows:
        u, p = _i(r.get("bought")), r.get("price")
        try:
            p = float(p)
        except (TypeError, ValueError):
            p = None
        if u and p:
            out[r.get("currency") or "?"] = out.get(r.get("currency") or "?", 0) + u * p
    return out


def fmt_rev(rev):
    """{'USD': 2100000} → '$2.1M'"""
    parts = []
    for cur, v in sorted(rev.items(), key=lambda kv: -kv[1]):
        sym = SYMBOLS.get(cur, cur + " ")
        if v >= 1_000_000:
            parts.append(f"{sym}{v/1_000_000:.1f}M")
        elif v >= 1_000:
            parts.append(f"{sym}{v/1_000:.0f}K")
        else:
            parts.append(f"{sym}{v:.0f}")
    return " ".join(parts)


def build_compact(today, rows, prev, prev_date, markets, failed, rcfg) -> str:
    """브랜드x국가 매트릭스 한 장 + 오늘 변동만. 한 화면에 들어가는 게 목표.

    제품별 상세는 history.csv 와 대시보드에 그대로 쌓이므로, 텔레그램은
    '무슨 일이 있었나'만 전한다.
    """
    codes = [m["code"] for m in markets if m.get("enabled", True)]
    thr = float(rcfg.get("move_threshold", 20))
    cap = int(rcfg.get("max_moves", 6))

    head = f"💄 아마존 K뷰티 · {today[5:]}"
    if prev_date:
        head += f" (vs {prev_date[5:]})"
    out = [head, ""]

    # ---- 매트릭스: 브랜드 x 국가 = 최고 BSR(추적 제품 수) ----
    grid, counts = {}, {}
    for r in rows:
        b, mk = r["brand"], r["market"]
        bsr = r.get("bsr_main")
        counts[(b, mk)] = counts.get((b, mk), 0) + 1
        if bsr is not None and (grid.get((b, mk)) is None or bsr < grid[(b, mk)]):
            grid[(b, mk)] = bsr

    brands = sorted({r["brand"] for r in rows},
                    key=lambda b: (-sum(1 for m in codes if (b, m) in counts),
                                   min([grid[(b, m)] for m in codes
                                        if grid.get((b, m)) is not None] or [10**9])))
    if brands:
        bw = max(9, max(len(b) for b in brands) + 1)
        out.append(_pad("브랜드", bw) + "".join(_pad(mk_name(c), 8) for c in codes))
        for b in brands:
            cells = ""
            for m in codes:
                if (b, m) not in counts:
                    cells += f"{'·':>8}"
                else:
                    v = grid.get((b, m))
                    cells += f"{(str(v) if v else '?') + '(' + str(counts[(b, m)]) + ')':>8}"
            out.append(_pad(b, bw) + cells)
        out.append("   BSR 최고순위(추적 제품수)")
    else:
        out.append("추적 중인 제품이 없습니다.")
    out.append("")

    # ---- 변동: BSR 기준 (리스트 밖에서도 잡힌다) ----
    ups, downs, news, lost = [], [], [], []
    seen = set()
    for r in rows:
        key = (r["market"], r["asin"])
        seen.add(key)
        p = prev.get(key)
        cur = r.get("bsr_main")
        if not p:
            if prev_date:
                news.append((r["market"], r["brand"], cur, r["title"]))
            continue
        old = _i(p.get("bsr_main"))
        if old and cur:
            chg = (old - cur) / old * 100          # +면 순위 상승
            if abs(chg) >= thr:
                (ups if chg > 0 else downs).append(
                    (abs(chg), r["market"], r["brand"], old, cur, r["title"]))
    for key, p in prev.items():
        if key not in seen:
            lost.append((key[0], p.get("brand", ""), p.get("bsr_main"), p.get("title", "")))

    def line(icon, m, brand, txt):
        return f"{icon} {FLAGS.get(m, '')}{mk_name(m)} {brand} {txt}"

    for tag, items in (("📈", ups), ("📉", downs)):
        for c, m, b, o, n, t in sorted(items, reverse=True)[:cap]:
            out.append(line(tag, m, b, f"BSR {fmt_int(o)}→{fmt_int(n)} ({c:.0f}%) {t[:26]}"))
    for m, b, n, t in news[:cap]:
        out.append(line("🆕", m, b, f"BSR {fmt_int(n)} {t[:30]}"))
    for m, b, n, t in lost[:cap]:
        out.append(line("⛔", m, b, f"측정 실패 {t[:30]}"))
    if not (ups or downs or news or lost):
        out.append("변동 없음" if prev_date else "첫 수집 — 내일부터 변동이 표시됩니다")
    out.append("")

    # ---- 꼬리말 ----
    per = {c: sum(1 for r in rows if r["market"] == c) for c in codes}
    inlist = sum(1 for r in rows if r.get("list_rank"))
    out.append(f"총 {len(rows)}개 추적 (리스트 내 {inlist}) · "
               + " ".join(f"{FLAGS.get(c, '')}{mk_name(c)} {per[c]}" for c in codes))
    if failed:
        out.append("⚠️ 수집 실패: " + ", ".join(c for c, _ in failed))
    return "\n".join(out).rstrip()


def bsr_score(rows):
    """가중 노출 점수 = Σ(1000/BSR).

    **BSR은 점수가 아니라 순위다** (1위가 최고, 숫자가 작을수록 좋다).
    그래서 브랜드 총합을 낼 때 그냥 더하면 뜻이 없다 — '1위 + 170위 = 171'은
    아무것도 설명하지 못한다. 역수로 환산해야 1위 하나가 100위 100개와
    같은 무게가 된다. 절대 판매량이 아니라 **추이 비교용 지수**다.
    """
    return sum(1000.0 / b for b in (_i(r.get("bsr_main")) for r in rows) if b)


def _delta(cur, old):
    """점수 변화율 문자열. 점수는 클수록 좋다."""
    if not old or not cur:
        return ""
    p = (cur - old) / old * 100
    if abs(p) < 1:
        return " (-)"
    return f" ({'▲' if p > 0 else '▼'}{abs(p):.0f}%)"


def _rank_delta(cur, old):
    """BSR 변화 표시. BSR은 작아져야 상승이다."""
    if not old or not cur:
        return "NEW" if not old else ""
    d = old - cur
    if d == 0:
        return "-"
    return f"{'▲' if d > 0 else '▼'}{abs(d):,}"


def build_detail(today, rows, prev, prev_date, markets, failed, rcfg) -> str:
    """국가별 → 브랜드별 → 제품, 그리고 하단에 브랜드 총합 점수."""
    codes = [m["code"] for m in markets if m.get("enabled", True)]
    head = f"💄 아마존 K뷰티 · {today[5:]}"
    if prev_date:
        head += f" (vs {prev_date[5:]})"
    out = [head,
           "수집: 6개국 Beauty 베스트셀러 → K뷰티 35개 브랜드 대조 → "
           f"잡힌 ASIN {len(rows)}개의 BSR 측정", ""]

    prev_rows = list(prev.values())

    # ---------------- 국가별 ----------------
    for code in codes:
        mine = [r for r in rows if r["market"] == code]
        if not mine:
            out += [f"{FLAGS.get(code, '')} {mk_name(code)} — 없음", ""]
            continue
        pm = [p for p in prev_rows if p.get("market") == code]
        sc, osc = bsr_score(mine), bsr_score(pm)
        rev = est_revenue(mine)
        out.append(f"{FLAGS.get(code, '')} {mk_name(code)} · {len(mine)}개 · "
                   f"점수 {sc:,.0f}{_delta(sc, osc)}"
                   + (f" · 월매출 {fmt_rev(rev)}+" if rev else ""))

        by_brand = {}
        for r in mine:
            by_brand.setdefault(r["brand"], []).append(r)
        for brand in sorted(by_brand, key=lambda b: -bsr_score(by_brand[b])):
            items = sorted(by_brand[brand],
                           key=lambda x: (_i(x.get("bsr_main")) or 10**9,
                                          -(_i(x.get("bought")) or 0)))
            bs = bsr_score(items)
            obs = bsr_score([p for p in pm if p.get("brand") == brand])
            bu = sum(_i(x.get("bought")) or 0 for x in items)
            brev = est_revenue(items)
            out.append(f"■ {brand} {len(items)}개 · 점수 {bs:,.0f}{_delta(bs, obs)}"
                       + (f" · {fmt_int(bu)}+개/월" if bu else "")
                       + (f" · {fmt_rev(brev)}+" if brev else ""))
            shown = int(rcfg.get("products_per_brand", 6))
            rest = len(items) - shown
            for r in items[:shown]:
                cur = _i(r.get("bsr_main"))
                old = _i((prev.get((code, r["asin"])) or {}).get("bsr_main"))
                mark = _rank_delta(cur, old)
                # 가격은 메시지에 안 넣는다(CSV에는 쌓인다). 대신 아마존이 공개하는
                # 월 판매량을 붙인다 — 매출 추정의 근거가 되는 숫자다.
                name = clean_name(r["title"], brand)
                u = _i(r.get("bought"))
                units = f"  {fmt_int(u)}+/월" if u else ""
                sr = _i(r.get("bsr_sub"))
                sub = (f"  [{r['bsr_sub_cat'][:22]} {sr}]"
                       if r.get("bsr_sub_cat") and sr and sr <= 10 else "")
                out.append(f"  {fmt_int(cur):>6} {mark:<6}{name[:42]:<42}{units:>12}{sub}")
            if rest > 0:
                out.append(f"       외 {rest}개 (전체는 history.csv)")
        out.append("")

    # ---------------- 브랜드 총합 ----------------
    out.append("━━━ 브랜드 총합 (6개국) ━━━")
    brands = {}
    for r in rows:
        brands.setdefault(r["brand"], []).append(r)
    ranked = sorted(brands.items(), key=lambda kv: -bsr_score(kv[1]))
    for brand, items in ranked:
        sc = bsr_score(items)
        osc = bsr_score([p for p in prev_rows if p.get("brand") == brand])
        bsrs = [b for b in (_i(x.get("bsr_main")) for x in items) if b]
        best = f"{min(bsrs):,}" if bsrs else "-"
        n_mk = len({x["market"] for x in items})
        u = sum(_i(x.get("bought")) or 0 for x in items)
        out.append(f"{brand:<17}{sc:>7,.0f}{_delta(sc, osc):<9}"
                   f"{len(items):>4}개 {n_mk}개국 최고{best:<7}"
                   + (f" {fmt_int(u)}+개/월" if u else ""))

    total_rev = est_revenue(rows)
    if total_rev:
        out += ["", f"■ 월매출 추정 {fmt_rev(total_rev)} 이상"]

    out += ["", "점수 = Σ(1000÷BSR) — BSR은 순위라 단순합산이 무의미해서",
            "1위=1000 / 10위=100 / 100위=10점으로 환산해 더한 값입니다.",
            "판매량은 아마존이 상품페이지에 직접 공개하는 구간값(하한)입니다.",
            "상위 구간이 100K+에서 잘려 1위가 과소평가되고, 판매량은 변형 합계인데",
            "가격은 대표 변형 기준이라 매출은 자릿수 참고용으로만 보세요."]

    if failed:
        out.append("⚠️ 수집 실패: " + ", ".join(c for c, _ in failed))
    return "\n".join(out).rstrip()


def build_daily(today, rows, prev, prev_date, markets, failed, rcfg) -> str:
    """평일 알림: 국가별 top100 진입 SKU 수 + 신규 편입/이탈만.

    매출·판매량은 여기 안 넣는다. 아마존 배지는 롤링 윈도우라 매일 더하면
    같은 판매를 반복해서 세게 되고, 일 단위로는 값이 잘 안 움직여 노이즈만 된다.
    누적 집계는 주간 리포트(build_weekly)가 맡는다.
    """
    codes = [m["code"] for m in markets if m.get("enabled", True)]
    head = f"💄 아마존 K뷰티 · {today[5:]}"
    if prev_date:
        head += f" (vs {prev_date[5:]})"
    out = [head, ""]

    inlist = [r for r in rows if _i(r.get("list_rank"))]
    pin = {(r["market"], r["asin"]): r for r in prev.values() if _i(r.get("list_rank"))}

    for code in codes:
        mine = [r for r in inlist if r["market"] == code]
        cap = next((c.get("top_n", 50) for m in markets if m["code"] == code
                    for c in (m.get("categories") or [{}])), 50)
        if not mine:
            out.append(f"{FLAGS.get(code,'')} {mk_name(code)} top{cap} — 없음")
            continue
        cnt, pcnt = {}, {}
        for r in mine:
            cnt[r["brand"]] = cnt.get(r["brand"], 0) + 1
        for (mk, _a), p in pin.items():
            if mk == code:
                pcnt[p["brand"]] = pcnt.get(p["brand"], 0) + 1
        parts = []
        for b in sorted(cnt, key=lambda x: -cnt[x]):
            d = cnt[b] - pcnt.get(b, 0)
            chg = f"({d:+d})" if (prev_date and d) else ""
            parts.append(f"{b} {cnt[b]}{chg}")
        out.append(f"{FLAGS.get(code,'')} {mk_name(code)} top{cap} · {len(mine)}개")
        out.append("   " + " · ".join(parts))
    out.append("")

    # 신규 편입 / 이탈 — 리스트 기준
    cur_keys = {(r["market"], r["asin"]) for r in inlist}
    news = [r for r in inlist if (r["market"], r["asin"]) not in pin]
    lost = [p for k, p in pin.items() if k not in cur_keys]
    if prev_date and news:
        out.append("🆕 신규 편입")
        for r in sorted(news, key=lambda x: (x["market"], _i(x["list_rank"]) or 0))[:12]:
            out.append(f"  {FLAGS.get(r['market'],'')}{mk_name(r['market'])} #{r['list_rank']} "
                       f"{r['brand']} {clean_name(r['title'], r['brand'])[:34]}")
    if prev_date and lost:
        out.append("⛔ 이탈")
        for p in sorted(lost, key=lambda x: (x["market"], _i(x.get("list_rank")) or 0))[:12]:
            out.append(f"  {FLAGS.get(p['market'],'')}{mk_name(p['market'])} (전일 #{p.get('list_rank')}) "
                       f"{p['brand']} {clean_name(p.get('title',''), p['brand'])[:34]}")
    if prev_date and not news and not lost:
        out.append("변동 없음 (신규 편입·이탈 없음)")
    if not prev_date:
        out.append("첫 수집 — 내일부터 편입·이탈이 표시됩니다")

    out += ["", f"추적 {len(rows)}개 · 리스트 내 {len(inlist)}개",
            "판매량·매출 집계는 주간 리포트(일요일)에서 보냅니다"]
    if failed:
        out.append("⚠️ 수집 실패: " + ", ".join(c for c, _ in failed))
    return "\n".join(out).rstrip()


# ------------------------------------------------------------------ 주간 집계

# units_w  = 주간 배지만 센 값. 관측창이 정확히 7일이라 **주별 합산이 성립**한다.
#            대신 주간 배지가 달린 제품이 전체의 일부라 커버리지가 낮다.
# units_wx = 주간 배지가 없으면 월간÷4.33 으로 메운 값. 커버리지는 높지만
#            관측창(30일)이 섞여 있어 합산의 엄밀함은 떨어진다.
# 모델링할 때 어느 쪽을 쓸지 고를 수 있게 둘 다 남긴다.
WEEKLY_COLS = ["week", "date", "market", "brand",
               "units_w", "rev_usd_w", "cov_w", "dp",
               "units_wx", "rev_usd_wx", "products", "in_list", "best_bsr"]


def weekly_key(d: str) -> str:
    """그 날짜가 속한 주의 월요일. 스냅샷은 주 1회라 이게 곧 관측 구간이다."""
    dt = datetime.date.fromisoformat(d)
    return (dt - datetime.timedelta(days=dt.weekday())).isoformat()


def snapshot_weekly(rows, today, path: Path) -> list[dict]:
    """주간 스냅샷을 weekly.csv 에 누적하고 전체를 반환.

    ★ 아마존 주간 배지는 '최근 7일' 롤링이다. **정확히 7일 간격으로 한 번씩만**
    읽으면 관측 구간이 안 겹쳐서 그대로 더할 수 있다. 매일 읽어 더하면 같은 판매를
    7번 세게 된다. 그래서 주 1회만 여기에 적는다.
    """
    prev = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            prev = [r for r in csv.DictReader(f)]
    wk = weekly_key(today)
    prev = [r for r in prev if r["week"] != wk]          # 같은 주 재실행은 덮어쓴다

    agg = {}
    for r in rows:
        k = (r["market"], r["brand"])
        a = agg.setdefault(k, {"units_w": 0, "rev_usd_w": 0.0, "cov_w": 0, "dp": 0,
                               "units_wx": 0, "rev_usd_wx": 0.0,
                               "products": 0, "in_list": 0, "best_bsr": None})
        a["products"] += 1
        if r.get("src") == "dp":
            a["dp"] += 1          # 주간배지를 볼 기회가 있었던 건 상세조회분뿐이다
        if _i(r.get("list_rank")):
            a["in_list"] += 1
        b = _i(r.get("bsr_main"))
        if b and (a["best_bsr"] is None or b < a["best_bsr"]):
            a["best_bsr"] = b
        try:
            p = float(r.get("price"))
        except (TypeError, ValueError):
            p = None
        fx = FX_TO_USD.get(r.get("currency"), 0)
        w, m = _i(r.get("bought_w")), _i(r.get("bought_m"))
        if w:                                   # 엄밀 집계 — 관측창이 정확히 7일
            a["units_w"] += w
            a["cov_w"] += 1
            if p:
                a["rev_usd_w"] += w * p * fx
        wx = w or (round(m / 4.33) if m else 0)  # 보정 집계 — 월간을 주로 환산해 메움
        if wx:
            a["units_wx"] += wx
            if p:
                a["rev_usd_wx"] += wx * p * fx

    for (mk, br), a in sorted(agg.items()):
        prev.append({"week": wk, "date": today, "market": mk, "brand": br,
                     "units_w": a["units_w"], "rev_usd_w": round(a["rev_usd_w"]),
                     "cov_w": a["cov_w"], "dp": a["dp"],
                     "units_wx": a["units_wx"], "rev_usd_wx": round(a["rev_usd_wx"]),
                     "products": a["products"], "in_list": a["in_list"],
                     "best_bsr": a["best_bsr"]})
    prev.sort(key=lambda r: (r["week"], r["market"], r["brand"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=WEEKLY_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(prev)
    return prev


def build_weekly(today, weekly, markets) -> str:
    """주간 리포트: 이번 주 판매량·매출 + 누적. 일간 알림 뒤에 덧붙여 보낸다."""
    wk = weekly_key(today)
    cur = [r for r in weekly if r["week"] == wk]
    if not cur:
        return ""
    weeks = sorted({r["week"] for r in weekly})
    start = (datetime.date.fromisoformat(wk)).strftime("%m/%d")
    end = (datetime.date.fromisoformat(wk) + datetime.timedelta(days=6)).strftime("%m/%d")

    out = ["", "━━━━━━━━━━━━━━━━━━",
           f"📊 주간 집계 · {start}~{end} ({len(weeks)}주차)", ""]

    by_brand, cum = {}, {}
    for r in cur:
        e = by_brand.setdefault(r["brand"], {"u": 0, "rev": 0.0, "ux": 0, "revx": 0.0})
        e["u"] += _i(r["units_w"]) or 0
        e["rev"] += float(r["rev_usd_w"] or 0)
        e["ux"] += _i(r["units_wx"]) or 0
        e["revx"] += float(r["rev_usd_wx"] or 0)
    for r in weekly:
        c = cum.setdefault(r["brand"], {"u": 0, "rev": 0.0, "ux": 0, "revx": 0.0})
        c["u"] += _i(r["units_w"]) or 0
        c["rev"] += float(r["rev_usd_w"] or 0)
        c["revx"] += float(r["rev_usd_wx"] or 0)

    def usd(v):
        return f"${v/1e6:.2f}M" if v >= 1e5 else f"${v/1e3:.0f}K"

    # 기준을 하나로 통일한다. 주간배지만 쓰면 엄밀하지만 상세조회분의 40%가 빠지고,
    # 배지 종류는 판매량과 무관하게 아마존이 제각각 정하므로(BSR 중앙값 209 vs 385)
    # 빼는 쪽이 오차가 더 크다. 그래서 보정 계열을 기본으로 쓰고 누적도 여기에 맞춘다.
    tu = sum(e["ux"] for e in by_brand.values())
    tr = sum(e["rev"] for e in by_brand.values())
    trx = sum(e["revx"] for e in by_brand.values())
    tc = sum(c["revx"] for c in cum.values())

    # 표는 2칸만. 누적은 아래 한 줄로 빼야 '이 숫자들이 무슨 관계지'가 안 생긴다.
    tbl = [_pad("브랜드", 17) + f"{'판매량':>10}{'매출':>9}"]
    for b in sorted(by_brand, key=lambda x: -by_brand[x]["revx"]):
        e = by_brand[b]
        tbl.append(_pad(b, 17) + f"{fmt_int(e['ux']):>10}{usd(e['revx']):>9}")
    tbl.append("─" * 36)
    tbl.append(_pad("합계", 17) + f"{fmt_int(tu):>10}{usd(trx):>9}")
    out.append(mono(tbl))
    out.append(f"누적 {len(weeks)}주 합계 · {usd(tc)}")
    covw = sum(_i(r["cov_w"]) or 0 for r in cur)
    covdp = sum(_i(r.get("dp")) or 0 for r in cur)
    out += ["", f"※ 아마존 공개 판매량 기준이라 <b>실제는 이보다 큽니다</b> (구간 하한).",
            f"　 주간배지 {covw}개는 창이 정확히 7일, 나머지는 월간÷4.33 보정 "
            f"(엄밀만 쓰면 {usd(tr)})."]
    return "\n".join(out)


def build_report(today, rows, prev, prev_date, markets, failed, rcfg) -> str:
    rcfg = rcfg or {}
    fn = ({"compact": build_compact, "daily": build_daily}
          .get(rcfg.get("mode"), build_detail))
    return fn(today, rows, prev, prev_date, markets, failed, rcfg)


# ------------------------------------------------------------------ 부가 기능

def is_weekly_day(cfg) -> bool:
    """오늘이 주간 집계일인지. 기본 일요일(6)."""
    return datetime.date.today().weekday() == int((cfg.get("weekly") or {}).get("weekday", 6))


def deploy_slot() -> bool:
    """지금이 Cloudflare Pages 배포 슬롯인지. 저장소 루트 CLAUDE.md 규약.

    Pages 는 푸시 1건 = 빌드 1건이고 월 500 한도라, 슬롯이 아니면 [CI Skip] 을 달아
    빌드를 건너뛴다. 데이터는 다음 배포가 같이 싣는다.
    """
    now = datetime.datetime.now()
    return now.hour in ((8, 10, 12, 14, 16, 18) if now.weekday() < 5 else (12, 20))


def inject_dashboard() -> bool:
    """history.csv → public/index.html 의 AMAZON 블록 갱신. 실패해도 죽지 않는다."""
    try:
        import inject_amazon
        return inject_amazon.main() == 0
    except Exception as e:                    # 대시보드 반영 실패가 수집을 막으면 안 된다
        print(f"[대시보드] 주입 실패 (수집 데이터는 무사): {e}", file=sys.stderr)
        return False


def git_push(today: str) -> None:
    """history.csv를 커밋하고 push. 실패해도 전체 실행은 죽이지 않는다."""
    import subprocess

    def run(*cmd):
        return subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)

    if run("git", "rev-parse", "--is-inside-work-tree").returncode != 0:
        print("[git] git 저장소가 아니라서 push 생략", file=sys.stderr)
        return
    # pathspec을 붙여 **이 두 파일만** 커밋한다. 그냥 `git commit`을 쓰면 인덱스에
    # 올라와 있던 남의 작업(대시보드 편집 등)까지 데이터 커밋에 휩쓸려 들어간다.
    files = ["data/history.csv", "data/weekly.csv", "data/asin_cache.json",
             "data/tracked_asins.json", "../public/index.html"]
    run("git", "add", *files)
    # 배포 슬롯이 아니면 [CI Skip] — Cloudflare Pages 는 푸시 1건 = 빌드 1건(월 500 한도).
    # 슬롯이면 index.html 갱신이 실제로 배포돼야 하므로 안 붙인다.
    msg = f"data: amazon beauty bestsellers {today}"
    if not deploy_slot():
        msg += " [CI Skip]"
    c = run("git", "commit", "-m", msg, "--", *files)
    if "nothing to commit" in (c.stdout + c.stderr):
        print("[git] 변경 없음, push 생략")
        return
    p = run("git", "push")
    if p.returncode != 0:
        # 이 저장소는 봇이 매시간 커밋한다. 원격이 앞서 있으면 push가 거절되므로
        # rebase 후 한 번 더 시도한다. --autostash 는 작업 중인 파일(대시보드 편집 등)이
        # 있어도 알아서 넣었다 빼주므로 남의 작업을 건드리지 않는다.
        print("[git] 원격이 앞서 있어 rebase 후 재시도", file=sys.stderr)
        r = run("git", "pull", "--rebase", "--autostash")
        if r.returncode != 0:
            print(f"[git] rebase 실패 (커밋은 로컬에 남음): {r.stderr.strip()[:300]}", file=sys.stderr)
            return
        p = run("git", "push")

    if p.returncode != 0:
        print(f"[git] push 실패 (커밋은 로컬에 저장됨): {p.stderr.strip()[:300]}", file=sys.stderr)
    else:
        print("[git] GitHub push 완료")


def send_telegram(token: str, chat_id: str, text: str) -> None:
    """텔레그램 발송. 표는 <pre> 로 감싸 고정폭으로 나가게 한다.

    텔레그램 기본 폰트는 가변폭이라 공백으로 맞춘 열이 전부 어긋난다.
    HTML 파싱이 실패하면 평문으로 한 번 더 시도한다(태그가 섞여 나가는 것보다 낫다).
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i in range(0, len(text), 3800):          # <pre> 태그 여유분
        chunk = text[i:i + 3800]
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML",
                   "disable_web_page_preview": "true"}
        r = requests.post(url, data=payload, timeout=30)
        if not r.ok:
            plain = re.sub(r"</?(pre|b|i|code)>", "", chunk)
            r = requests.post(url, data={"chat_id": chat_id, "text": plain}, timeout=30)
        r.raise_for_status()


# ------------------------------------------------------------------ 진입점

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true", help="텔레그램 발송 생략")
    ap.add_argument("--markets", help="쉼표로 구분한 마켓 코드만 수집 (예: US,UK)")
    ap.add_argument("--compact", action="store_true", help="일간 대신 매트릭스 요약")
    ap.add_argument("--detail", action="store_true", help="제품별 상세 리포트")
    ap.add_argument("--weekly", action="store_true", help="요일과 무관하게 주간 집계도 실행")
    ap.add_argument("--report-only", action="store_true",
                    help="수집 없이 history.csv 로 리포트만 만들어 발송 (테스트용)")
    ap.add_argument("--budget", type=int, help="마켓당 상세조회 상한 (기본 config)")
    args = ap.parse_args()

    cfg = load_config()
    data_dir = Path(cfg["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    history_path = data_dir / "history.csv"
    today = datetime.date.today().isoformat()

    if args.markets:
        want = {c.strip().upper() for c in args.markets.split(",")}
        for m in cfg["markets"]:
            m["enabled"] = m["code"].upper() in want
    # 주간 집계일에는 /dp/ 를 깊게 판다. 주간배지는 상세 페이지에만 있어서,
    # 이 날 확보한 만큼이 그 주 판매량 커버리지가 된다.
    weekly_today = (args.weekly or is_weekly_day(cfg)) and not args.report_only
    if weekly_today:
        deep = (cfg.get("detail") or {}).get("top_per_market_weekly")
        if deep:
            cfg["detail"]["top_per_market"] = int(deep)
            cfg["detail"]["top_per_brand"] = int(cfg["detail"].get("top_per_brand_weekly", 12))
            print(f"[주간] 집계일 — 상세조회를 마켓당 {deep}개로 늘립니다")
    # 브랜드 검색은 '새 SKU 발견'용이라 매일 할 이유가 없다.
    # 6개국 x 9브랜드 x 3페이지 = 162요청으로 한 회 요청량의 3분의 1을 차지하는데,
    # 2026-08-04 차단 때 이 검색들이 줄줄이 503 을 맞으며 차단을 키웠다.
    # 주간 집계일에만 돌리고 평일엔 이미 추적 중인 ASIN 의 BSR 만 잰다.
    if not weekly_today and (cfg.get("search") or {}).get("weekly_only", True):
        cfg.setdefault("search", {})["enabled"] = False
        print("[검색] 평일은 브랜드 검색 생략 — 주간 집계일에만 돕니다(차단 회피)")
    if args.budget:
        cfg.setdefault("tracking", {})["max_detail_per_run"] = args.budget
    rcfg = dict(cfg.get("report") or {})
    if args.compact:
        rcfg["mode"] = "compact"
    if args.detail:
        rcfg["mode"] = "detail"

    if args.report_only:
        # 이미 받아둔 오늘치로 리포트만 다시 만든다. 수집이 40분 걸려서
        # 발송 형식만 확인하고 싶을 때 매번 다시 긁을 이유가 없다.
        hist = load_history(history_path)
        last = max((r["date"] for r in hist), default=None)
        rows = [r for r in hist if r["date"] == last]
        failed = []
        if not rows:
            print("[중단] history.csv 에 데이터가 없습니다.", file=sys.stderr)
            return 1
        today = last
        print(f"[리포트전용] {today} 수집분 {len(rows)}행으로 리포트만 생성")
    else:
        # scrape_all 이 브랜드 매칭까지 끝낸 행을 돌려준다 (고정 추적 ASIN 기준)
        rows, failed = scrape_all(cfg, cfg["brands"])
    if not rows:
        print("[중단] 수집된 항목이 없습니다.", file=sys.stderr)
        return 1
    measured = sum(1 for r in rows if r.get("bsr_main") not in (None, ""))
    inlist = sum(1 for r in rows if r.get("list_rank"))
    print(f"\n[수집] 추적 {len(rows)}개 / BSR 측정 {measured}개 / 리스트 내 {inlist}개")

    history = [] if args.report_only else load_history(history_path)
    prev_dates = sorted({r["date"] for r in history if r["date"] < today})
    prev_date = prev_dates[-1] if prev_dates else None
    prev_by_key = {(r["market"], r["asin"]): r
                   for r in history if r["date"] == prev_date} if prev_date else {}

    # 같은 날 재실행 시 오늘자 행을 덮어쓴다. 단 **이번에 실제로 수집한 마켓만** 지운다.
    # (--markets US 로 부분 실행하거나 한 마켓이 실패했을 때 나머지 마켓의
    #  오늘치 데이터가 통째로 날아가는 걸 막는다)
    refreshed = {m["code"] for m in cfg["markets"] if m.get("enabled", True)}
    refreshed -= {code for code, _ in failed}
    history = [r for r in history
               if not (r["date"] == today and r["market"] in refreshed)]
    if not args.report_only:
        history += [{**r, "date": today} for r in rows]
        write_history(history_path, history)
        print(f"[기록] {len(rows)}행 추가 → {history_path}")

    report = build_report(today, rows, prev_by_key, prev_date,
                          cfg["markets"], failed, rcfg)

    # 주간 집계 — 아마존 주간 배지가 '최근 7일' 롤링이라 **주 1회만** 찍어야
    # 관측 구간이 안 겹치고 그대로 누적된다. 기본 요일은 월요일.
    if args.weekly or is_weekly_day(cfg):
        weekly = snapshot_weekly(rows, today, data_dir / "weekly.csv")
        wk_text = build_weekly(today, weekly, cfg["markets"])
        if wk_text:
            report += "\n" + wk_text
            print(f"[주간] weekly.csv 갱신 — {len({r['week'] for r in weekly})}주차")
    print("\n" + report)

    tg = cfg.get("telegram", {})
    if tg.get("enabled") and not args.no_telegram:
        if tg["bot_token"] and tg["chat_id"]:
            send_telegram(tg["bot_token"], str(tg["chat_id"]), report)
            print("\n[발송] 텔레그램 전송 완료")
        else:
            # 수집은 이미 끝났으니 발송 실패로 전체를 죽이지 않는다
            print("\n[발송] 토큰/chat_id가 없어 생략했습니다. "
                  "secrets_local.py 를 만들거나 config.yaml에 넣으세요.", file=sys.stderr)

    if not args.report_only:
        inject_dashboard()

    if cfg.get("git", {}).get("enabled") and not args.report_only:
        git_push(today)
    return 2 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BlockedError as e:
        print(f"[차단] {e}", file=sys.stderr)
        sys.exit(1)
