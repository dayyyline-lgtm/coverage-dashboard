# -*- coding: utf-8 -*-
"""index.html 안의 데이터 상수를 public/data/<이름>.json 으로 떼어낸다.

왜 필요한가
  지금은 데이터 33개가 index.html(903KB) 안에 상수로 박혀 있고, 수집기 7개가
  그 한 파일을 각자 통째로 고쳐 쓴다. 서로 다른 상수를 고쳐도 git 은 '인접 변경'
  으로 보기 때문에 충돌한다 — 2026-08-08 에 아마존 하루치가 실제로 갇혔다.

  블록마다 파일이 따로 있으면 그 충돌이 원리적으로 사라진다.

지금 단계에서 이 파일들은 '아직 아무도 안 읽는다'
  화면(index.html)은 종전대로 내장 상수를 쓴다. 이 스크립트는 사본을 하나 더
  만들어 둘 뿐이라, 돌려도 화면이 바뀌지 않는다. v2 화면이 이걸 읽기 시작하면
  그때 비로소 쓰임이 생긴다. 그래서 지금 돌려도 안전하다.

    python export_blocks.py            # 내보내기
    python export_blocks.py --check    # 내보내지 않고 검증만

⚠ 여기 나가는 것은 전부 공개된다(사이트가 공개, 저장소도 공개).
  v2 로 옮길 때 '무엇을 공개할지'를 한 번 정해야 한다 —
  DATA 의 thesis(투자 논거)·fairMktcap(견적)·score·rev27/op27/eps27(사내 엑셀 출신)이
  거기 해당한다. 지금도 이미 공개돼 있으므로 이 스크립트가 노출을 늘리지는 않는다.
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
OUT = "public/data"

# 화면 코드가 쓰는 상수 중 '데이터'만 뽑는다. 색상표·라벨맵 같은 설정은 코드에 속하므로
# 여기 넣지 않는다 — 옮겨 봐야 수집기가 안 건드리니 충돌과 무관하고, 화면만 느려진다.
SKIP = {
    "MOVIE_COLORS", "SECTOR_COLORS", "CTYPE", "CTYPE_LABEL", "BRAND_LOGO",
    "BRAND_PLATE", "BRAND_MARK", "NAME_LOGO", "AMZ_MK_NAME", "MANUAL_EVENTS",
    "MOVIE_BOOKING_REF", "MOVIE_UPCOMING", "MY_EST", "W52_MODES",
    # 아래는 '설정'이지 수집 데이터가 아니다 — 수집기가 안 건드리므로 충돌과 무관하다.
    "TABS", "PORT_PAL", "SEC_LINE_COLORS", "SECTORS", "_subsBySec",
    "CAT_OF", "CATS", "PICK_OVERRIDE",
}


def blocks(html):
    """(이름, JSON문자열) — 최상위 `const X = {...};` / `[...];` 만."""
    out = []
    for m in re.finditer(r'^const (\w+)\s*=\s*([\{\[].*?);\s*$', html, re.S | re.M):
        name, raw = m.group(1), m.group(2)
        if name in SKIP:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue          # JS 표현식이 섞인 것은 데이터가 아니다
        out.append((name, obj, len(raw)))
    return out


def main():
    check = "--check" in sys.argv
    html = open(HTML, encoding="utf-8", errors="replace").read()
    got = blocks(html)
    if not got:
        print("데이터 상수를 못 찾았습니다 — index.html 형식이 바뀌었는지 확인하세요")
        return 1

    if not check:
        os.makedirs(OUT, exist_ok=True)

    total = 0
    print(f"{'상수':<16}{'크기':>9}   상태")
    for name, obj, size in sorted(got, key=lambda x: -x[2]):
        total += size
        path = os.path.join(OUT, f"{name.lower()}.json")
        if check:
            state = "확인"
        else:
            # separators 를 좁게 — 이 파일들은 사람이 읽으라고 만드는 게 아니다.
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
            state = f"→ {path}"
        print(f"  {name:<14}{size//1024:>6}KB   {state}")

    print(f"\n  블록 {len(got)}개 · 합계 {total//1024}KB "
          f"(index.html {len(html)//1024}KB 의 {total/len(html)*100:.0f}%)")
    if not check:
        print(f"  → {OUT}/ 에 썼습니다. 화면은 아직 이 파일을 읽지 않습니다(안전).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
