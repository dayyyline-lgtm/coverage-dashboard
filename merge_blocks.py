"""리베이스가 막혔을 때 '상수 블록 단위'로 합친다 (2026-09-30 · 10-18 두 번 보강).

index.html 의 데이터 상수는 한 줄에 하나씩 붙어 있어서(AMAZON 1114행 · LIVE 1115행),
서로 다른 상수를 고쳐도 git 은 '인접 변경'으로 보고 충돌을 낸다. 그러면 워크플로가
'이번 회차 커밋 포기'로 그 시간 수집분(시세·KOBIS·뉴스…)을 통째로 버렸다.
2026-09-30 08시: 아마존 트래커가 08:03 에 push → 시세 회차 커밋이 사라지고 영화 예매가 멈췄다.

규칙 — 파일을 `const 이름 =` 으로 시작하는 줄마다 조각으로 나누고:
  · 내 커밋이 바꾼 조각이면 내 것, 아니면 원격 것
  · 양쪽이 같은 조각을 다르게 바꿨으면 **그 조각만** asOf(수집 시각)가 늦은 쪽을 쓴다. asOf 가 없거나 같으면 원격 것.
    (10-18 전엔 여기서 전체를 포기했다 — 10/17·10/18 아침 수집이 이 PC 의 한국 IP 수집과 BEAUTY 로 겹쳐
     공시·트렌드·앱순위 등 18개 블록이 이틀 연속 통째로 버려졌다.)
  · **상수가 새로 생기거나 없어진 경우도 합친다**(10-18 두 번째 보강). 그 전엔 '상수 구성이 다르다'며 포기했는데,
    10/18 15:42 재수집이 그렇게 버려졌다 — 수집이 도는 44분 사이에 다른 작업이 새 상수(AMZL)를 넣었다.
      원격에만 있는 상수 = 원격이 새로 만든 것 → 그대로 둔다
      내 쪽에만 있는 상수 = 내가 새로 만든 것 → 내 쪽 순서에서 바로 앞 상수 뒤에 끼운다
      한쪽이 지웠고 다른 쪽은 안 건드렸으면 지운다 · 지운 쪽 반대편이 고쳤으면 남긴다(데이터를 잃지 않는 쪽)
  · 상태 파일(health.json · watchdog_state.json)이 같이 막히면 **키 단위**로 합친다 — 양쪽이 같은 키를 바꿨으면
    내 쪽(지금 올리는 회차 · 더 늦게 돈 쪽). 그 전엔 index.html 말고 다른 파일이 하나라도 막히면 포기했다.
  · 그 밖의 파일이 막혔으면 실패(종료코드 1) → 호출 쪽이 기존대로 포기

리베이스 충돌 중에 인자 없이 부른다. 인덱스 단계: 1 = 공통 조상, 2 = upstream(원격), 3 = 내 커밋.
합친 파일은 여기서 git add 까지 한다 — 호출 쪽은 `GIT_EDITOR=true git rebase --continue` 만 부르면 된다.
"""
import json
import re
import subprocess
import sys

PATH = "public/index.html"
JSON_STATE = ("health.json", "watchdog_state.json")
HEAD = re.compile(r"^const ([A-Za-z_$][\w$]*)\s*=")
ASOF = re.compile(r'"(?:asOf|fetched|updated)"\s*:\s*"([^"]+)"')
MISSING = object()


def stamp(part):
    """조각의 수집 시각 — 숫자만 이어 붙여 비교한다('2026-10-17 06:06 KST' → '202610170606'). 없으면 ''."""
    m = ASOF.search(part[:400])
    return re.sub(r"\D", "", m.group(1))[:12] if m else ""


def stage(n, path):
    """인덱스 단계 n 의 파일 내용. 그 단계에 파일이 없으면(한쪽이 새로 만든 파일) None."""
    r = subprocess.run(["git", "show", f":{n}:{path}"], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def split(text):
    """[(이름, 조각)] — 첫 조각은 '#preamble'(첫 상수 앞 전부)."""
    keys, parts, cur, key = [], [], [], "#preamble"
    for line in text.splitlines(keepends=True):
        m = HEAD.match(line)
        if m:
            keys.append(key); parts.append("".join(cur))
            key, cur = m.group(1), []
        cur.append(line)
    keys.append(key); parts.append("".join(cur))
    return list(zip(keys, parts))


def pick_later(k, mine, theirs, taken, both):
    """같은 조각을 양쪽이 다르게 바꿨을 때 — 늦게 수집한 쪽, 모르면 원격."""
    sm, st = stamp(mine), stamp(theirs)
    if sm and sm > st:
        taken.append(k); both.append(f"{k}(내 쪽 {sm} > 원격 {st})")
        return mine
    both.append(f"{k}(원격 {st or '시각 없음'} ≥ 내 쪽 {sm or '시각 없음'})")
    return theirs


def merge_index(base_t, theirs_t, mine_t):
    """세 판의 index.html → 합친 글. 못 합치면 None."""
    if None in (base_t, theirs_t, mine_t):
        print("merge_blocks: index.html 이 한쪽에 없다(지움·새로 만듦) — 자동 병합 불가")
        return None
    B, T, M = split(base_t), split(theirs_t), split(mine_t)
    for seq in (B, T, M):
        names = [k for k, _ in seq]
        if len(set(names)) != len(names):
            print("merge_blocks: 같은 이름의 상수가 두 번 나온다 — 자동 병합 불가")
            return None
    bd, td, md = dict(B), dict(T), dict(M)
    # 조각 끝에는 다음 상수 앞까지의 글(빈 줄 · </script> · 파일 꼬리)이 붙어 있다. 그래서
    #  · 마지막 상수가 판마다 다르면 꼬리(</script>…</html>)가 사라지거나 두 번 붙는다 → 포기
    #  · 지워진 상수가 여러 줄짜리면 딸린 글까지 같이 지워진다 → 포기(한 줄짜리만 지운다)
    if len({B[-1][0], T[-1][0], M[-1][0]}) != 1:
        print("merge_blocks: 마지막 상수가 판마다 다르다 — 자동 병합 불가")
        return None
    gone = [k for k, bp in B if (k not in td or k not in md) and bp.count("\n") > 1]
    if gone:
        print("merge_blocks: 여러 줄짜리 상수를 지운 쪽이 있다 —", ", ".join(gone), "— 자동 병합 불가")
        return None
    out, taken, both, notes = [], [], [], []
    for k, tp in T:                                  # 뼈대는 원격 순서
        if k in bd and k in md:
            bp, mp = bd[k], md[k]
            if mp == bp:
                out.append((k, tp))
            elif tp == bp or tp == mp:
                out.append((k, mp)); taken.append(k)
            else:
                out.append((k, pick_later(k, mp, tp, taken, both)))
        elif k not in bd:                            # 원격이 새로 만든 상수
            if k in md and md[k] != tp:              # 양쪽이 같은 이름을 따로 만들었다
                out.append((k, pick_later(k, md[k], tp, taken, both)))
            else:
                out.append((k, tp))
            notes.append(f"{k}(원격 새 상수)")
        elif tp == bd[k]:                            # 내 쪽이 지웠고 원격은 안 건드렸다 → 지운다
            notes.append(f"{k}(내 쪽에서 지움)")
        else:                                        # 내 쪽이 지웠는데 원격이 고쳤다 → 남긴다
            out.append((k, tp)); notes.append(f"{k}(내 쪽은 지웠지만 원격이 고쳐서 남김)")
    have = {k for k, _ in out}
    for i, (k, mp) in enumerate(M):                  # 내 쪽에만 있는 상수
        if k in have:
            continue
        if k in bd:                                  # 원격이 지운 상수
            if mp == bd[k]:
                notes.append(f"{k}(원격에서 지움)")
                continue
            notes.append(f"{k}(원격은 지웠지만 내 쪽이 고쳐서 남김)")
        else:
            notes.append(f"{k}(내 쪽 새 상수)")
        prev = next((M[j][0] for j in range(i - 1, -1, -1) if M[j][0] in have), None)
        pos = next((n + 1 for n, (kk, _) in enumerate(out) if kk == prev), len(out))
        out.insert(pos, (k, mp)); have.add(k); taken.append(k)
    print("merge_blocks: 블록 단위 병합, 내 쪽:", ", ".join(taken) or "(없음)")
    if both:
        print("merge_blocks: 양쪽이 같은 블록을 바꿔 한쪽만 남김 —", " · ".join(both))
    if notes:
        print("merge_blocks: 상수 구성 변화 —", " · ".join(notes))
    return "".join(p for _, p in out)


def merge_json(path, base_t, theirs_t, mine_t):
    """상태 파일(평평한 dict) 키 단위 3방향 병합. 못 합치면 None."""
    try:
        B, T, M = (json.loads(x) if x else {} for x in (base_t, theirs_t, mine_t))
    except ValueError:
        print(f"merge_blocks: {path} 가 JSON 이 아니다 — 자동 병합 불가")
        return None
    if not all(isinstance(x, dict) for x in (B, T, M)):
        print(f"merge_blocks: {path} 가 dict 가 아니다 — 자동 병합 불가")
        return None
    out, mine_keys = {}, []
    for k in list(T) + [k for k in M if k not in T]:
        bv, tv, mv = B.get(k, MISSING), T.get(k, MISSING), M.get(k, MISSING)
        if mv == bv:
            v = tv
        else:                                        # 내 쪽이 바꿨으면(원격도 바꿨어도) 내 쪽 — 지금 올리는 회차가 더 늦게 돌았다
            v = mv; mine_keys.append(k)
        if v is not MISSING:
            out[k] = v
    print(f"merge_blocks: {path} 키 단위 병합, 내 쪽 키 {len(mine_keys)}개")
    indent = 2 if (theirs_t or "").lstrip().startswith("{\n") else None
    return json.dumps(out, ensure_ascii=False, indent=indent) + ("\n" if (theirs_t or "").endswith("\n") else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = [f for f in subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                                       capture_output=True, text=True).stdout.split() if f]
    if not files:
        print("merge_blocks: 막힌 파일이 없다 — 리베이스가 다른 이유로 멈췄다")
        return 1
    bad = [f for f in files if f != PATH and f not in JSON_STATE]
    if bad:
        print("merge_blocks: 자동으로 못 합치는 파일이 막혔다 —", ", ".join(bad))
        return 1
    merged = {}
    for f in files:
        texts = [stage(n, f) for n in (1, 2, 3)]
        merged[f] = merge_index(*texts) if f == PATH else merge_json(f, *texts)
        if merged[f] is None:
            return 1
    for f, text in merged.items():                   # 전부 합쳐진 다음에 쓴다(반쯤 쓴 채로 남지 않게)
        with open(f, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        subprocess.run(["git", "add", f], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
