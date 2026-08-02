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
import argparse
import datetime
from pathlib import Path

import yaml
import requests

from scraper import scrape_all, match_brand, BlockedError

BASE = Path(__file__).parent
HISTORY_COLS = ["date", "market", "rank", "asin", "brand", "title",
                "price", "currency", "rating", "reviews",
                "sub_bsr_rank", "sub_bsr_cat"]

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
        if reader.fieldnames and "market" not in reader.fieldnames:
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


def build_report(today, tracked, prev_by_key, prev_date, markets, failed) -> str:
    lines = [f"💄 아마존 뷰티 베스트셀러 — {today}"]
    if prev_date:
        lines.append(f"(전일 비교 기준: {prev_date})")
    lines.append("")

    by_market: dict[str, list[dict]] = {}
    for it in tracked:
        by_market.setdefault(it["market"], []).append(it)

    for m in markets:
        code, top_n = m["code"], m.get("top_n", 50)
        if not m.get("enabled", True):
            continue
        flag = FLAGS.get(code, "")
        items = by_market.get(code, [])
        if not items:
            lines.append(f"{flag} {code} 탑{top_n} — 해당 브랜드 없음")
            lines.append("")
            continue

        lines.append(f"{flag} {code} 탑{top_n}")
        by_brand: dict[str, list[dict]] = {}
        for it in items:
            by_brand.setdefault(it["brand"], []).append(it)

        for brand in sorted(by_brand, key=lambda b: min(x["rank"] for x in by_brand[b])):
            ranks = sorted(by_brand[brand], key=lambda x: x["rank"])
            lines.append(f"  ■ {brand} ({len(ranks)}개)")
            for it in ranks:
                prev = prev_by_key.get((code, it["asin"]))
                if prev:
                    d = int(prev["rank"]) - it["rank"]
                    arrow = f"▲{d}" if d > 0 else (f"▼{-d}" if d < 0 else "-")
                elif prev_date:
                    arrow = "NEW"
                else:
                    arrow = "-"
                title = it["title"][:52] + ("…" if len(it["title"]) > 52 else "")
                lines.append(f"   #{it['rank']:<3} ({arrow}) {title}")

                bits = [fmt_price(it["price"], it["currency"])]
                if it.get("rating"):
                    bits.append(f"★{it['rating']}({fmt_int(it.get('reviews'))})")
                if it.get("sub_bsr_cat") and it.get("sub_bsr_rank"):
                    bits.append(f"{it['sub_bsr_cat']} #{fmt_int(it['sub_bsr_rank'])}")
                lines.append(f"        {' · '.join(bits)}")
        lines.append("")

    # 어제는 있었는데 오늘 빠진 제품
    cur_keys = {(it["market"], it["asin"]) for it in tracked}
    dropped = [p for k, p in prev_by_key.items() if k not in cur_keys]
    if dropped:
        lines.append("⛔ 랭킹 이탈")
        for p in sorted(dropped, key=lambda x: (x["market"], int(x["rank"]))):
            lines.append(f"  {FLAGS.get(p['market'], '')} {p['market']} "
                         f"(전일 #{p['rank']}) {p['title'][:44]}")
        lines.append("")

    if failed:
        lines.append("⚠️ 수집 실패: " + ", ".join(c for c, _ in failed))
    return "\n".join(lines).rstrip()


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
        print(f"[git] push 실패 (커밋은 로컬에 저장됨): {p.stderr.strip()}", file=sys.stderr)
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
    ap.add_argument("--no-detail", action="store_true", help="31~50위 상세 보강 생략")
    ap.add_argument("--markets", help="쉼표로 구분한 마켓 코드만 수집 (예: US,UK)")
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
    if args.no_detail:
        cfg.setdefault("detail", {})["mode"] = "off"

    brands = cfg["brands"]
    items, failed = scrape_all(cfg, brands)
    if not items:
        print("[중단] 수집된 항목이 없습니다.", file=sys.stderr)
        return 1

    tracked = []
    for it in items:
        b = match_brand(it["title"], brands)
        if b:
            tracked.append({**it, "brand": b})
    unknown = sum(1 for it in items if not it["title"])
    print(f"\n[수집] 총 {len(items)}개 / 관심 브랜드 {len(tracked)}개"
          + (f" / 제목 미확인 {unknown}개" if unknown else ""))

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
    history += [{**it, "date": today} for it in tracked]
    write_history(history_path, history)
    print(f"[기록] {len(tracked)}행 추가 → {history_path}")

    report = build_report(today, tracked, prev_by_key, prev_date, cfg["markets"], failed)
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
