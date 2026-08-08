# -*- coding: utf-8 -*-
"""배포 전 렌더 점검 — 진짜 브라우저로 열어 탭을 전부 눌러 본다.

왜 정적 점검만으로는 부족한가
  화면 코드를 js/app.js 로 뗀 뒤로, app.js 는 index.html 의 상수를 **이름으로만**
  참조한다. 그 연결이 끊겨도 파일 둘 다 문법은 멀쩡하다 — 브라우저에서 열어야
  ReferenceError 로 터진다. 정적 분석으로 잡으려 해 봤지만 오탐이 122건 나왔다
  (hex 색상·함수 내부 변수가 전부 '정의 없는 대문자 이름'으로 잡힌다).
  실행이 유일한 판별법이다.

무엇을 보나
  1. 첫 화면에서 잡히지 않은 JS 예외가 있는가
  2. 탭 11개를 하나씩 눌렀을 때 각각 예외가 나는가
     (탭 전환은 그때그때 renderX() 를 부른다 — 안 눌러 보면 절반이 실행조차 안 된다)
  3. 각 탭에 실제로 내용이 그려졌는가 (예외 없이 백지인 경우가 있다)

  python check_render.py            # 점검
  python check_render.py --shot DIR # 탭별 스크린샷도 남긴다

주의
  file:// 로 열면 안 된다 — 외부 스크립트가 CORS 로 막힌다(CLAUDE.md 규칙).
  그래서 여기서 임시 HTTP 서버를 띄운다.

준비물
  pip install playwright && python -m playwright install chromium
  없으면 점검을 건너뛰고 종료코드 0 을 낸다 — 정적 점검까지 같이 죽이지 않기 위해서다.
"""
import functools
import http.server
import os
import socket
import sys
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = "public"
TABS = ["overview", "coverage", "valuation", "preview", "calendar", "news",
        "reports", "trends", "boxoffice", "altdata", "amazon"]

# 로고·폰트 같은 외부 리소스가 못 뜨는 것은 화면 고장이 아니다.
# 토스 CDN 은 커버리지 밖 종목에서 404 를 내는 게 정상이고(이니셜 배지로 폴백),
# CI 러너에서는 외부 도메인이 통째로 막히기도 한다. 우리가 보려는 건 '우리 코드의 예외'다.
NOISE = ("Failed to load resource", "net::ERR", "favicon",
         "static.toss.im", "ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION")


def serve(root):
    """빈 포트에 조용한 정적 서버를 띄우고 (포트, 종료함수) 를 준다."""
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):      # 요청 로그를 끈다 — 점검 결과만 보이게
            pass
    handler = functools.partial(Quiet, directory=root)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return port, httpd.shutdown


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("렌더 점검 건너뜀 — playwright 가 없습니다 "
              "(pip install playwright && python -m playwright install chromium)")
        return 0

    def opt(flag, default=None):
        if flag in sys.argv:
            i = sys.argv.index(flag)
            return sys.argv[i + 1] if len(sys.argv) > i + 1 else default
        return None

    root = opt("--root") or ROOT      # 사본을 점검할 때 쓴다(경보가 실제로 울리는지 시험)
    shot_dir = opt("--shot", "shots")
    if not os.path.isdir(root):
        print(f"  ✗ {root}/ 가 없습니다")
        return 1
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)

    port, stop = serve(root)
    errs = []          # (탭, 종류, 메시지)
    empty = []
    seen = set()       # 같은 예외가 탭마다 되풀이되면 한 번만 센다

    def note(tab, kind, msg):
        msg = " ".join(str(msg).split())[:300]
        if any(n in msg for n in NOISE):
            return
        if msg in seen:
            return
        seen.add(msg)
        errs.append((tab, kind, msg))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            cur = {"tab": "(로딩)"}
            page.on("pageerror", lambda e: note(cur["tab"], "예외", e))
            page.on("console", lambda m: note(cur["tab"], "콘솔", m.text)
                    if m.type == "error" else None)

            page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=60000)
            page.wait_for_timeout(1500)

            n = page.locator("nav.tabs button").count()
            if n != len(TABS):
                errs.append(("(로딩)", "구조",
                             f"탭 버튼이 {n}개입니다 (TABS 는 {len(TABS)}개) — "
                             f"app.js 가 TABS 를 못 읽었을 수 있습니다"))
            if shot_dir:
                page.screenshot(path=os.path.join(shot_dir, "00-load.png"), full_page=False)

            for i, k in enumerate(TABS, 1):
                cur["tab"] = k
                btn = page.locator(f'nav.tabs button[data-k="{k}"]')
                if not btn.count():
                    errs.append((k, "구조", "탭 버튼이 없습니다"))
                    continue
                btn.click()
                page.wait_for_timeout(900)          # 차트·비동기 렌더가 끝날 틈

                view = page.locator(f'section.view[data-view="{k}"]')
                if not view.count():
                    errs.append((k, "구조", "이 탭의 화면(section.view)이 없습니다"))
                    continue
                txt = (view.inner_text() or "").strip()
                if len(txt) < 40:
                    empty.append((k, len(txt)))
                if shot_dir:
                    page.screenshot(path=os.path.join(shot_dir, f"{i:02d}-{k}.png"))

            browser.close()
    finally:
        stop()

    print(f"렌더 점검 · 탭 {len(TABS)}개 확인" + (f" · 스크린샷 {shot_dir}/" if shot_dir else ""))
    for k, cnt in empty:
        print(f"  ⚠ [{k}] 화면이 거의 비어 있습니다 (글자 {cnt}자) — 예외는 없지만 확인하세요")
    for tab, kind, msg in errs:
        print(f"  ✗ [{tab}] {kind}: {msg}")
    if errs:
        print(f"\n실패 {len(errs)}건 — 배포하면 화면이 깨집니다.")
        return 1
    print("  ✓ JS 예외 0건" + (f" (빈 화면 경고 {len(empty)}건)" if empty else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
