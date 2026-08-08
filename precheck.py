# -*- coding: utf-8 -*-
"""배포 전 정적 점검 — 화면이 깨진 채로 배포되는 것을 막는다.

왜 필요한가
  지금 안전망은 전부 '사후'다. alert.yml 은 워크플로가 죽어야 알고,
  watchdog.py 는 데이터가 12시간 굳어야 안다. 그 사이에 있는 사고 —
  '수집은 성공했는데 화면이 안 뜬다' — 를 보는 눈이 없었다.
  그래서 매번 사람이 브라우저를 열어 확인했다(2026-08-08 하루에 6번).

  여기서 보는 것은 전부 '실제로 한 번씩 났던 사고'다. 일반론은 넣지 않았다.

무엇을 보나 (의존성 0 · 1초 안쪽)
  1. 충돌 마커      — 리베이스가 멈춘 채 커밋된 적이 있다
  2. 필수 상수      — 수집기가 이름으로 찾는다. 사라지면 조용히 깨진다
  3. const LIVE     — 수집기 8개가 새 블록을 여기 뒤에 끼워 넣는다(삽입 앵커)
  4. JSON 파싱      — 상수 하나가 깨지면 그 뒤 코드가 통째로 안 돈다
  5. 파일 연결      — index.html 이 js/app.js 를 부르는가
  6. 크기           — 데이터가 통째로 날아가면 파일이 급격히 줄어든다
  7. .bat 인코딩    — 한글이 들어가면 cmd 가 조용히 아무 일도 안 한다
  8. asOf 신선도    — 경고만(로컬에선 오래된 게 정상이라 실패로 치지 않는다)

  python precheck.py            # 점검
  python precheck.py --stale    # 신선도까지 실패로 친다 (CI 용)

필수 상수 목록을 여기에 또 적지 않는다
  `watchdog.py` 의 LIMITS 가 이미 '데이터 블록 등록처'다(CLAUDE.md 규칙).
  같은 목록을 두 곳에 두면 반드시 갈라진다 — 그래서 거기서 읽어 온다.
"""
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
APP = "public/js/app.js"

# watchdog.LIMITS 에 없지만 없어지면 안 되는 것들.
#   LIVE  = 수집기의 삽입 앵커(fetch_steam·chzzk·twitch·youtube·appstore…)
#   DATA  = 유니버스 원본. 사람이 직접 편집하는 유일한 데이터
#   TRADE_PRELIM·TRADE_FLASH = 안에 주석이 있어 JSON 이 아닌데 fetch_trade.py 가 찾는다
#     (이 둘 때문에 '순수 JSON 인 것만 챙기면 된다'는 규칙이 틀렸다 — 실제로 밟은 함정)
#   TABS  = 없으면 탭이 하나도 안 그려진다(app.js 165줄이 즉시 죽는다)
CORE = ["LIVE", "DATA", "TABS", "TRADE_PRELIM", "TRADE_FLASH",
        "PRELIM", "DART_EVENTS", "APPRANK", "PORTFOLIO", "PICK_HISTORY"]

# 데이터가 통째로 날아간 것을 잡는 바닥값. 실측(2026-08-08) index 646KB · app 270KB 의 절반.
FLOOR = {HTML: 300 * 1024, APP: 100 * 1024}

# JSON 으로 읽히는 최상위 상수의 최소 개수. 실측 34개 — 몇 개 줄어드는 건 정상이지만
# 절반으로 떨어지면 블록이 통째로 사라졌다는 뜻이다.
MIN_JSON_BLOCKS = 25


def limits_keys():
    """watchdog.LIMITS 의 블록 이름. import 가 실패해도 점검은 계속한다."""
    try:
        import watchdog
        return list(watchdog.LIMITS.keys())
    except Exception as e:
        print(f"  · watchdog.LIMITS 를 못 읽었습니다({e}) — CORE 만 봅니다")
        return []


def defined_consts(html):
    """`<script>const DATA =` 처럼 줄 앞이 아닌 것도 잡는다(DATA 가 그렇다)."""
    return set(re.findall(r'(?:^|>|\s)const ([A-Za-z_]\w*)\s*=', html, re.M))


def conflict_markers(path, text):
    """줄 앵커로만 본다. app.js 885줄의 `/* ===== 주석 ===== */` 이 오탐이었다."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if re.match(r'^(<{7}|={7}|>{7})(\s|$)', line):
            hits.append((i, line[:60]))
    return hits


def block_body(html, name):
    """`const NAME = ...;` 의 값 부분. 없으면 None."""
    m = re.search(r'(?:^|>|\s)const %s\s*=\s*([\{\[].*?);\s*$' % re.escape(name),
                  html, re.S | re.M)
    return m.group(1) if m else None


def looks_hollow(body):
    """껍데기만 남았는가 — 있긴 한데 안이 빈 경우.

    이게 가장 잡기 어려운 고장이다. app.js 가 `typeof X !== "undefined"` 로 방어하고
    있어서 예외가 안 나고 화면만 조용히 빈다(실측: 렌더 점검이 이 고장을 못 잡았다).
    watchdog 도 못 본다 — asOf 가 없으면 그 블록을 통째로 건너뛰기 때문이다.
    """
    if body is None:
        return None
    try:
        obj = json.loads(body)
    except Exception:
        return None                       # JS 표현식이 섞인 것(TRADE_PRELIM 등)은 판정 밖
    if isinstance(obj, dict):
        meta = {"asOf", "updated", "ts", "note"}
        if not (set(obj) - meta):
            return "안이 비었습니다"
        for k in ("items", "rows", "list", "data", "stocks", "records"):
            v = obj.get(k)
            if isinstance(v, (list, dict)) and len(v) == 0:
                return f'"{k}" 가 0건입니다'
    elif isinstance(obj, list) and not obj:
        return "빈 배열입니다"
    return None


def main():
    strict_stale = "--stale" in sys.argv
    if "--root" in sys.argv:                        # 사본 점검용(경보 시험에 쓴다)
        i = sys.argv.index("--root")
        if len(sys.argv) > i + 1:
            os.chdir(sys.argv[i + 1])
    fails, warns = [], []

    # ── 파일이 있는가
    for p in (HTML, APP):
        if not os.path.exists(p):
            fails.append(f"{p} 가 없습니다")
    if fails:
        for f in fails:
            print("  ✗ " + f)
        return 1

    html = open(HTML, encoding="utf-8", errors="replace").read()
    app = open(APP, encoding="utf-8", errors="replace").read()

    # ── 1. 충돌 마커
    for p, t in ((HTML, html), (APP, app)):
        for ln, s in conflict_markers(p, t):
            fails.append(f"{p}:{ln} 리베이스 충돌 마커가 남아 있습니다 — {s}")

    # ── 2. 필수 상수
    have = defined_consts(html)
    need = list(dict.fromkeys(CORE + limits_keys()))
    gone = [n for n in need if n not in have]
    for n in gone:
        fails.append(f"상수 const {n} 이 index.html 에서 사라졌습니다 "
                     f"(수집기가 이름으로 찾습니다 — 조용히 깨집니다)")

    # ── 2b. 있긴 한데 껍데기만 남았는가
    for n in need:
        if n in gone:
            continue
        why = looks_hollow(block_body(html, n))
        if why:
            fails.append(f"상수 const {n} 이 {why} — 화면은 예외 없이 그냥 비어 보입니다")

    # ── 3. 삽입 앵커
    if not re.search(r"const LIVE\s*=\s*\{", html):
        fails.append("삽입 앵커 `const LIVE = {` 가 없습니다 — "
                     "새 블록을 넣는 수집기가 전부 죽습니다")

    # ── 4. JSON 파싱
    okn = 0
    for m in re.finditer(r'^const (\w+)\s*=\s*([\{\[].*?);\s*$', html, re.S | re.M):
        try:
            json.loads(m.group(2))
            okn += 1
        except Exception:
            pass
    if okn < MIN_JSON_BLOCKS:
        fails.append(f"JSON 으로 읽히는 데이터 상수가 {okn}개뿐입니다 "
                     f"(정상 {MIN_JSON_BLOCKS}개 이상) — 블록이 깨졌을 수 있습니다")

    # ── 5. 파일 연결
    if not re.search(r'<script[^>]+src=["\']js/app\.js', html):
        fails.append("index.html 이 js/app.js 를 부르지 않습니다 — 화면이 백지가 됩니다")

    # ── 5b. 화면의 신선도 한도가 watchdog 과 같은가
    #
    # 화면은 '수집이 멈췄다'를 배지로 알리는데, 그 한도를 app.js 가 따로 들고 있다
    # (브라우저가 파이썬을 읽을 수 없으니 어쩔 수 없다). 등록처가 둘이면 반드시 갈라지고,
    # 갈라지면 watchdog 은 조용한데 화면만 경고하거나 그 반대가 된다.
    # 그래서 '두 벌 두되 어긋나면 실패' 로 묶는다.
    m = re.search(r'const STALE_H\s*=\s*\{([^}]*)\}', app)
    if not m:
        fails.append("app.js 에 STALE_H 가 없습니다 — 화면이 수집 정지를 알릴 수 없습니다")
    else:
        front = {k: int(v) for k, v in re.findall(r'(\w+)\s*:\s*(\d+)', m.group(1))}
        back = {}
        try:
            import watchdog
            back = {k: int(v[1]) for k, v in watchdog.LIMITS.items()}
        except Exception:
            pass
        for k, v in front.items():
            if k in back and back[k] != v:
                fails.append(f"신선도 한도가 어긋납니다 — {k}: app.js {v}시간 vs "
                             f"watchdog.LIMITS {back[k]}시간. 둘을 같게 맞추세요")
            elif k not in back and back:
                fails.append(f"app.js 의 STALE_H 에 있는 {k} 가 watchdog.LIMITS 에 없습니다")

    # ── 6. 크기
    for p, floor in FLOOR.items():
        sz = os.path.getsize(p)
        if sz < floor:
            fails.append(f"{p} 가 {sz // 1024}KB 뿐입니다 "
                         f"(정상 {floor // 1024}KB 이상) — 데이터가 날아갔을 수 있습니다")

    # ── 7. .bat 검사
    #
    # 인코딩: cmd 는 .bat 을 **cp949 로 읽는다**. 그러니 문제가 되는 건 한글 자체가 아니라
    #   'UTF-8 로 저장된 한글'이다 — cp949 로 읽히며 깨지는데 종료코드는 0 이라 조용히 넘어간다.
    #   cp949 로 저장된 파일은 정상 동작한다. (여기서 한 번 오판했다: ASCII 만 허용하면
    #   멀쩡히 도는 업데이트.bat·트렌드갱신.bat 이 실패로 잡힌다.)
    #
    # 참조: .bat 이 부르는 .py 가 실재하는가. `업데이트.bat` 이 폐지된 rebuild_from_excel.py 를
    #   계속 부르고 있었다 — 눌러도 아무 일이 안 일어나는데 아무도 몰랐다.
    for fn in sorted(f for f in os.listdir(".") if f.lower().endswith(".bat")):
        raw = open(fn, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            fails.append(f"{fn} 이 UTF-8 BOM 으로 시작합니다 — cmd 가 첫 줄을 못 읽습니다")
        try:
            txt = raw.decode("utf-8")
            if any(ord(c) > 127 for c in txt):
                fails.append(f"{fn} 이 UTF-8 로 저장돼 있습니다 — cmd 는 cp949 로 읽으므로 "
                             f"한글 줄이 깨집니다(종료코드는 0 이라 조용히 넘어갑니다). "
                             f"cp949 로 다시 저장하거나 ASCII 로만 쓰세요")
        except UnicodeDecodeError:
            pass          # cp949 로 저장된 파일 — cmd 가 제대로 읽는다
        body = raw.decode("cp949", errors="replace")
        for py in re.findall(r'python\s+(?:-\w+\s+)*([\w./\\-]+\.py)', body):
            if not os.path.exists(py):
                fails.append(f"{fn} 이 없는 스크립트 {py} 를 부릅니다 — "
                             f"눌러도 아무 일이 일어나지 않습니다")

    # ── 8. 신선도 (watchdog 의 판정을 그대로 빌린다)
    try:
        import datetime
        import watchdog
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        for key, label, age, lim in watchdog.freshness(html, now):
            msg = f"{label}({key}) 가 {age:.0f}시간째 그대로입니다 (정상 {lim:.0f}시간 이내)"
            (fails if strict_stale else warns).append(msg)
    except Exception as e:
        warns.append(f"신선도 점검을 건너뛰었습니다 — {e}")

    # ── 보고
    print(f"정적 점검 · 상수 {len(have)}개 · JSON 블록 {okn}개 · "
          f"index {os.path.getsize(HTML) // 1024}KB · app {os.path.getsize(APP) // 1024}KB")
    for w in warns:
        print("  ⚠ " + w)
    for f in fails:
        print("  ✗ " + f)
    if fails:
        print(f"\n실패 {len(fails)}건 — 배포하면 안 됩니다.")
        return 1
    print("  ✓ 이상 없음" + (f" (경고 {len(warns)}건)" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
