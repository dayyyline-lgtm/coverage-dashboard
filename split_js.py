# -*- coding: utf-8 -*-
"""index.html 의 화면 코드를 public/js/app.js 로 떼어낸다. (데이터는 그대로 둔다)

무엇을 얻나
  지금은 한 파일(823KB·5,071줄)에 데이터와 화면 코드가 섞여 있어서,
  내가 화면을 고칠 때와 봇이 데이터를 쓸 때가 같은 파일에서 부딪힌다.
  2026-08-08 하루에만 두 번 충돌했다.

  코드를 밖으로 빼면 그 충돌이 사라진다 — 봇은 index.html, 사람은 js/app.js.

무엇을 남기나 (중요)
  수집기 23개가 `const NAME = ...` 를 정규식으로 찾아 바꾼다. 그래서 다음은
  반드시 index.html 에 남겨야 한다:

    ① 순수 JSON 상수 (json.loads 가 되는 것)
    ② 수집기·봇이 이름으로 찾는 상수  ← ①에 안 잡히는 것이 있다
       TRADE_FLASH·TRADE_PRELIM 은 안에 주석이 있어 JSON 이 아니지만
       fetch_trade.py 가 찾는다. 이걸 옮기면 조용히 깨진다.
    ③ 새 상수를 끼워 넣는 앵커 `const LIVE` (수집기들이 이 뒤에 삽입한다)

왜 모듈(type="module")이 아니라 보통 스크립트인가
  모듈은 strict mode 라 기존 코드가 거기서 깨질 수 있다(선언 없는 대입 등).
  1단계는 '파일만 분리' 로 의미를 하나도 안 바꾸고 간다.
  모듈·탭별 분할은 그다음 단계에서 하나씩.

  ⚠ 검증은 file:// 로 하면 안 된다 — 외부 스크립트가 CORS 로 막힌다.
    `python -m http.server` 로 띄우고 볼 것.

    python split_js.py --dry     # 무엇이 어디로 갈지만 출력
    python split_js.py --to DIR  # DIR 에 사본을 만들어 적용(검증용)
    python split_js.py           # 실제 적용
"""
import json
import os
import re
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"


def collector_constants():
    """수집기·봇이 index.html 에서 이름으로 찾는 상수."""
    import glob
    need = set()
    for f in glob.glob("*.py") + glob.glob("amazon-beauty-tracker/*.py"):
        try:
            t = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if "index.html" not in t:
            continue
        need |= set(re.findall(r'_put\([^,]+,\s*[\'"](\w+)[\'"]', t))
        need |= set(re.findall(r'_const\(html,\s*[\'"](\w+)[\'"]', t))
        need |= set(re.findall(r'const\s+([A-Z][A-Z0-9_]*)\s', t))
    return {n for n in need if re.fullmatch(r'[A-Z][A-Z0-9_]*', n)}


def plan(html):
    m = re.search(r'(<script[^>]*>)(.*?)(</script>)', html, re.S)
    if not m:
        raise SystemExit("<script> 블록을 못 찾았습니다")
    body = m.group(2)

    keep_names = set(collector_constants())
    spans = []          # (시작, 끝, 이름, 남길것인가)
    for mm in re.finditer(r'^const (\w+)\s*=\s*(.*?);\s*$', body, re.S | re.M):
        name, raw = mm.group(1), mm.group(2)
        if not raw.lstrip().startswith(("{", "[")):
            continue
        try:
            json.loads(raw)
            pure = True
        except Exception:
            pure = False
        if pure or name in keep_names:
            spans.append((mm.start(), mm.end(), name, pure))
    spans.sort()
    return m, body, spans


def main():
    dry = "--dry" in sys.argv
    to = None
    if "--to" in sys.argv:
        to = sys.argv[sys.argv.index("--to") + 1]

    html = open(HTML, encoding="utf-8", errors="replace").read()
    m, body, spans = plan(html)

    keep_parts, code_parts, last = [], [], 0
    for a, b, name, pure in spans:
        code_parts.append(body[last:a])
        keep_parts.append(body[a:b])
        last = b
    code_parts.append(body[last:])

    keep = "\n".join(keep_parts)
    code = "".join(code_parts)

    print(f"{'상수':<18}{'JSON':>6}   남김")
    for _, _, name, pure in spans:
        print(f"  {name:<16}{'예' if pure else '아니오':>6}   index.html")
    print(f"\n  index.html 에 남는 데이터 {len(spans)}개 · {len(keep)//1024}KB")
    print(f"  js/app.js 로 나가는 코드      {len(code)//1024}KB · {code.count(chr(10)):,}줄")

    if dry:
        return 0

    root = to or "."
    if to:
        os.makedirs(to, exist_ok=True)
        shutil.copytree("public", os.path.join(to, "public"), dirs_exist_ok=True)

    js_dir = os.path.join(root, "public", "js")
    os.makedirs(js_dir, exist_ok=True)
    with open(os.path.join(js_dir, "app.js"), "w", encoding="utf-8", newline="") as f:
        f.write("/* 화면 코드. 데이터 상수는 index.html 에 남아 있고 여기서 전역으로 읽는다.\n"
                "   (보통 스크립트끼리라 그냥 보인다 — 실측 확인함)\n"
                "   ⚠ 이 파일은 봇이 안 건드린다. 화면 수정은 여기서 할 것. */\n")
        f.write(code)

    new_html = (html[:m.start()]
                + m.group(1) + keep + m.group(3)
                + '\n<script src="js/app.js"></script>'
                + html[m.end():])
    with open(os.path.join(root, HTML), "w", encoding="utf-8", newline="") as f:
        f.write(new_html)

    print(f"\n  → {os.path.join(root, HTML)}  ({len(new_html)//1024}KB)")
    print(f"  → {os.path.join(js_dir, 'app.js')}")
    if to:
        print(f"\n  검증: cd {to} && python -m http.server 8732  → 브라우저로 확인")
    return 0


if __name__ == "__main__":
    sys.exit(main())
