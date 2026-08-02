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
                "price", "currency", "rating", "reviews"]

FLAGS = {"US": "🇺🇸", "UK": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
         "IT": "🇮🇹", "ES": "🇪🇸", "NL": "🇳🇱", "SE": "🇸🇪", "PL": "🇵🇱", "JP": "🇯🇵"}
SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥"}


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
    """기존 CSV를 읽는다. 구버전(단일 마켓) 스키마면 백업하고 새로 시작."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and "bsr_main" not in reader.fieldnames:
            backup = path.with_name("history_v1_backup.csv")
            shutil.copy2(path, backup)
            print(f"[이전] 구버전 history.csv를 {backup.name}로 백업하고 새 스키마로 시작합니다.\n"
                  f"       (구버전 price 컬럼은 통화 설정 누락으로 원화 환산값이 섞여 있어 재사용하지 않습니다)")
            return []
        return list(reader)


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


def _pad(s, w):
    """CJK 문자를 2칸으로 세는 폭 맞춤 (모노스페이스 정렬용)."""
    width = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
    return s + " " * max(0, w - width)


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
        out.append(_pad("브랜드", bw) + "".join(f"{c:>8}" for c in codes))
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
        return f"{icon} {FLAGS.get(m, '')}{m} {brand} {txt}"

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
               + " ".join(f"{FLAGS.get(c, '')}{per[c]}" for c in codes))
    if failed:
        out.append("⚠️ 수집 실패: " + ", ".join(c for c, _ in failed))
    return "\n".join(out).rstrip()


def build_full(today, rows, prev, prev_date, markets, failed, rcfg) -> str:
    """제품별 전부 나열하는 상세판 (report.mode: full)."""
    out = [f"💄 아마존 K뷰티 · {today}"]
    if prev_date:
        out.append(f"(전일 비교: {prev_date})")
    out.append("")
    for m in markets:
        code = m["code"]
        if not m.get("enabled", True):
            continue
        mine = [r for r in rows if r["market"] == code]
        if not mine:
            out += [f"{FLAGS.get(code, '')} {code} — 없음", ""]
            continue
        out.append(f"{FLAGS.get(code, '')} {code}")
        by_brand = {}
        for r in mine:
            by_brand.setdefault(r["brand"], []).append(r)
        for brand in sorted(by_brand, key=lambda b: min(
                (x.get("bsr_main") or 10**9) for x in by_brand[b])):
            out.append(f"  ■ {brand} ({len(by_brand[brand])}개)")
            for r in sorted(by_brand[brand], key=lambda x: x.get("bsr_main") or 10**9):
                p = prev.get((code, r["asin"]))
                old = _i(p.get("bsr_main")) if p else None
                cur = r.get("bsr_main")
                arrow = ""
                if old and cur:
                    d = old - cur
                    arrow = f" ({'▲' if d > 0 else '▼' if d < 0 else '-'}{abs(d) or ''})"
                lr = f"리스트 #{r['list_rank']} · " if r.get("list_rank") else ""
                out.append(f"   {r['title'][:50]}")
                out.append(f"      {lr}BSR #{fmt_int(cur)}{arrow}"
                           + (f" · {r['bsr_sub_cat']} #{fmt_int(r['bsr_sub'])}"
                              if r.get("bsr_sub_cat") else "")
                           + f" · {fmt_price(r.get('price'), r.get('currency'))}"
                           + (f" · ★{r['rating']}({fmt_int(r.get('reviews'))})"
                              if r.get("rating") else ""))
        out.append("")
    if failed:
        out.append("⚠️ 수집 실패: " + ", ".join(c for c, _ in failed))
    return "\n".join(out).rstrip()


def build_report(today, rows, prev, prev_date, markets, failed, rcfg) -> str:
    fn = build_full if (rcfg or {}).get("mode") == "full" else build_compact
    return fn(today, rows, prev, prev_date, markets, failed, rcfg or {})


# ------------------------------------------------------------------ 부가 기능

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
    files = ["data/history.csv", "data/asin_cache.json"]
    run("git", "add", *files)
    c = run("git", "commit", "-m", f"data: amazon beauty bestsellers {today}", "--", *files)
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
    # 텔레그램 메시지는 4096자 제한 → 분할 발송
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i in range(0, len(text), 4000):
        r = requests.post(url, data={"chat_id": chat_id, "text": text[i:i + 4000]}, timeout=30)
        r.raise_for_status()


# ------------------------------------------------------------------ 진입점

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true", help="텔레그램 발송 생략")
    ap.add_argument("--markets", help="쉼표로 구분한 마켓 코드만 수집 (예: US,UK)")
    ap.add_argument("--full", action="store_true", help="압축 대신 제품별 상세 리포트")
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
    if args.budget:
        cfg.setdefault("tracking", {})["max_detail_per_run"] = args.budget
    rcfg = dict(cfg.get("report") or {})
    if args.full:
        rcfg["mode"] = "full"

    # scrape_all 이 브랜드 매칭까지 끝낸 행을 돌려준다 (고정 추적 ASIN 기준)
    rows, failed = scrape_all(cfg, cfg["brands"])
    if not rows:
        print("[중단] 수집된 항목이 없습니다.", file=sys.stderr)
        return 1
    measured = sum(1 for r in rows if r.get("bsr_main") is not None)
    inlist = sum(1 for r in rows if r.get("list_rank"))
    print(f"\n[수집] 추적 {len(rows)}개 / BSR 측정 {measured}개 / 리스트 내 {inlist}개")

    history = load_history(history_path)
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
    history += [{**r, "date": today} for r in rows]
    write_history(history_path, history)
    print(f"[기록] {len(rows)}행 추가 → {history_path}")

    report = build_report(today, rows, prev_by_key, prev_date,
                          cfg["markets"], failed, rcfg)
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

    if cfg.get("git", {}).get("enabled"):
        git_push(today)
    return 2 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BlockedError as e:
        print(f"[차단] {e}", file=sys.stderr)
        sys.exit(1)
