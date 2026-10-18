"""리베이스가 public/index.html 에서 막혔을 때 '상수 블록 단위'로 합친다 (2026-09-30).

index.html 의 데이터 상수는 한 줄에 하나씩 붙어 있어서(AMAZON 1114행 · LIVE 1115행),
서로 다른 상수를 고쳐도 git 은 '인접 변경'으로 보고 충돌을 낸다. 그러면 워크플로가
'이번 회차 커밋 포기'로 그 시간 수집분(시세·KOBIS·뉴스…)을 통째로 버렸다.
2026-09-30 08시: 아마존 트래커가 08:03 에 push → 시세 회차 커밋이 사라지고 영화 예매가 멈췄다.

규칙 — 파일을 `const 이름 =` 으로 시작하는 줄마다 조각으로 나누고:
  · 내 커밋이 바꾼 조각이면 내 것, 아니면 원격 것
  · 양쪽이 같은 조각을 다르게 바꿨으면 **그 조각만** asOf(수집 시각)가 늦은 쪽을 쓴다. asOf 가 없거나 같으면 원격 것.
    (2026-10-18 전엔 여기서 전체를 포기했다 — 10/17 아침 수집이 06:06 에 끝났는데 이 PC 의 한국 IP 수집이 06:00 에
     BEAUTY 를 먼저 올려, BEAUTY 하나 때문에 공시·트렌드·앱순위 등 18개 블록이 통째로 버려졌다.
     이제는 겹친 조각 하나만 잃고 나머지는 산다 — 잃는 조각은 어차피 다음 회차가 다시 받는다.)
  · 조각 구성(상수 목록·순서)이 달라졌으면 실패(종료코드 1) → 호출 쪽이 기존대로 포기

리베이스 충돌 중에 인자 없이 부른다. 인덱스 단계: 1 = 공통 조상, 2 = upstream(원격), 3 = 내 커밋.
"""
import re
import subprocess
import sys

PATH = "public/index.html"
HEAD = re.compile(r"^const ([A-Za-z_$][\w$]*)\s*=")
ASOF = re.compile(r'"(?:asOf|fetched|updated)"\s*:\s*"([^"]+)"')


def stamp(part):
    """조각의 수집 시각 — 숫자만 이어 붙여 비교한다('2026-10-17 06:06 KST' → '202610170606'). 없으면 ''."""
    m = ASOF.search(part[:400])
    return re.sub(r"\D", "", m.group(1))[:12] if m else ""


def stage(n):
    return subprocess.run(["git", "show", f":{n}:{PATH}"], capture_output=True, check=True).stdout.decode("utf-8")


def split(text):
    keys, parts, cur, key = [], [], [], "#preamble"
    for line in text.splitlines(keepends=True):
        m = HEAD.match(line)
        if m:
            keys.append(key); parts.append("".join(cur))
            key, cur = m.group(1), []
        cur.append(line)
    keys.append(key); parts.append("".join(cur))
    return keys, parts


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    base, theirs, mine = (split(stage(n)) for n in (1, 2, 3))
    if not (base[0] == theirs[0] == mine[0]) or len(set(base[0])) != len(base[0]):
        print("merge_blocks: 상수 구성이 달라 자동 병합 불가")
        return 1
    out, taken, both = [], [], []
    for k, b, t, m in zip(base[0], base[1], theirs[1], mine[1]):
        if m == b:
            out.append(t)
        elif t == b or t == m:
            out.append(m); taken.append(k)
        else:                                   # 양쪽이 같은 조각을 다르게 — 늦게 수집한 쪽, 모르면 원격
            sm, st = stamp(m), stamp(t)
            if sm and sm > st:
                out.append(m); taken.append(k); both.append(f"{k}(내 쪽 {sm} > 원격 {st})")
            else:
                out.append(t); both.append(f"{k}(원격 {st or '시각 없음'} ≥ 내 쪽 {sm or '시각 없음'})")
    with open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write("".join(out))
    print("merge_blocks: 블록 단위 병합, 내 쪽:", ", ".join(taken) or "(없음)")
    if both:
        print("merge_blocks: 양쪽이 같은 블록을 바꿔 한쪽만 남김 —", " · ".join(both))
    return 0


if __name__ == "__main__":
    sys.exit(main())
