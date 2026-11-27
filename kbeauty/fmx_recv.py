"""kbeauty/fmx_recv.py — fastmoss_x.js 덤프(조각 여럿)를 검산해 kbeauty/data/fmx/<날짜>.txt 로 합친다(2026-11-27).

  python3 kbeauty/fmx_recv.py 조각1.txt 조각2.txt …        # 줄마다 CRC · 마지막 END(줄 수 · 전체 CRC)
  python3 kbeauty/phase.py                                  # KBPH 에 tt.mk(시장) · tt.x(브랜드 판매 구조)가 붙는다

같은 날짜 파일이 이미 있으면 줄 단위로 합친다(X 는 샵 · M 은 주 · 새 조각이 이긴다).
"""
import pathlib
import sys
import zlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "data" / "fmx"


def b36(n):
    s, a = "", "0123456789abcdefghijklmnopqrstuvwxyz"
    while True:
        n, r = divmod(n, 36)
        s = a[r] + s
        if not n:
            return s


def crc(s):
    return b36(zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF)


def main(paths):
    lines = []
    for p in paths:
        for l in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
            l = l.strip()
            if l:
                lines.append(l)
    body = [l for l in lines if not l.startswith("END|")]
    end = [l for l in lines if l.startswith("END|")]
    bad = []
    for l in body:
        a, _, c = l.rpartition("|")
        if crc(a) != c:
            bad.append(l[:60])
    if bad:
        print(f"[fmx] CRC 틀린 줄 {len(bad)}개 — 그 줄만 다시 받을 것:")
        for b in bad[:20]:
            print("   ", b)
        sys.exit(1)
    if end:
        _, n, c = end[-1].split("|")
        if int(n) != len(body) + 1 or crc("\n".join(body)) != c:
            print(f"[fmx] END 불일치 — 줄 {len(body) + 1} vs {n} (빠진 조각이 있나?)")
            sys.exit(1)
    else:
        print("[fmx] END 줄 없음 — 조각을 다 넣었나?")
        sys.exit(1)
    hd = [l for l in body if l.startswith("XH|")]
    date = hd[0].split("|")[2]
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{date}.txt"
    keep = {}
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            f = l.split("|")
            if f[0] in ("X", "M", "E", "Y", "N"):
                keep[(f[0], f[1])] = l
    for l in body:
        f = l.split("|")
        if f[0] in ("X", "M", "E", "Y", "N"):
            if f[0] == "E" and (("X", f[1]) in keep or ("Y", f[1]) in keep):
                continue
            keep[(f[0], f[1])] = l
            if f[0] in ("X", "Y"):
                keep.pop(("E", f[1]), None)
    rows = sorted(keep.values(), key=lambda l: ({"X": 0, "Y": 0, "M": 1, "N": 1, "E": 2}[l[0]], l))
    nx = sum(1 for l in rows if l[:2] in ("X|", "Y|"))
    nm = sum(1 for l in rows if l[:2] in ("M|", "N|"))
    ver = hd[0].split("|")[1]
    h = f"XH|{ver}|{date}|{nx}|{nm}"
    allL = [h + "|" + crc(h)] + rows
    allL.append(f"END|{len(allL) + 1}|{crc(chr(10).join(allL))}")
    out.write_text("\n".join(allL) + "\n", encoding="utf-8")
    print(f"[fmx] {out.name} · 샵 {nx} · 시장 주 {nm} · 오류 {sum(1 for l in rows if l.startswith('E|'))}")


if __name__ == "__main__":
    main(sys.argv[1:])
