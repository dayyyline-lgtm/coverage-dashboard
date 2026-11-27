# -*- coding: utf-8 -*-
"""K뷰티 브랜드 국면 지도(아마존 미국 · 37개 브랜드 + 유럽 5개국 `mk`) → public/index.html 의 `const KBPH` 한 줄 (2026-10-21).

KBCH(회사 채널 모델)는 상장사 브랜드만 본다. 국면 지도는 '피어 안에서 몫이 늘고 있나'를 보려는 것이라
비상장 경쟁사(아누아·스킨1004·조선미녀·셀리맥스·닥터엘시아(Dr.Althea)·토리든 …)까지 같은 바구니에 넣는다.

원재료: kbeauty/data/phase/<날짜>.json — Keepa Product Finder(웹 · 미국) 결과 표의 상품 객체를 브랜드 × 월로 합친 것.
  u   = 월 판매량(배지 'Bought in past month' 계단 이력의 그달 일수 가중 평균 · 구간 아랫값 → 하한)
  n1k = 그달 1천 개 이상 팔린 SKU 수
  nw  = 배지 첫 등장 12개월 이내 SKU 의 판매량(2024-08 부터 유효)
  pi  = 현재 바이박스가 ÷ 1년 평균가(판매량 가중)
  top1 = 7~9월 판매 1위 SKU 와 직전 완결 월 판매량
  마지막 달(partial)은 진행 중 — 화면에서 완결 월과 섞지 않는다.

점유율·두 축·칸·질 체크는 전부 화면(app.js renderKbPhase)에서 계산한다(파생값은 페이지에서 — CLAUDE.md).

  python3 kbeauty/phase.py            # 가장 최근 원재료로 블록 넣기
  python3 kbeauty/phase.py --dry      # 블록 크기만
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
INDEX = HERE.parent / "public" / "index.html"
SRC = HERE / "data" / "phase"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def latest():
    files = sorted(SRC.glob("20??-??-??.json"))
    if not files:
        raise SystemExit("kbeauty/data/phase 에 원재료가 없다")
    return files[-1]


def audit(path, d):
    """추정 검사(2026-11-24 · 바이오던스 Pack of 2 이중 계산 뒤 사용자 '이런 실수가 앞으로 없도록').
    배지 아랫값 합(uf)은 실측이고 나머지(구간 위치 보정 · 배지 없는 달 채우기 · 세트 곡선 ub)는 추정이다 — 추정이 실측을 압도하거나 회차 사이에 튀면 경고.
    ① 세트 곡선(ub)이 브랜드 판매량의 30% 초과(2만 개 이상) ② 추정 ÷ 배지 실측 > 1.8배(차이 2만 개 이상) ③ 같은 달 ub 가 직전 회차보다 3배 넘게(2만 개 이상).
    경고만 한다(값은 안 바꾼다) — 원인을 보고 수집기를 고친다. CLAUDE.md 'Keepa 추정 원칙'."""
    M = d["months"]; L = len(M) - 1; warn = []
    files = sorted(SRC.glob("20??-??-??.json")); prev = None
    older = [f for f in files if f.name < path.name]
    if older:
        try:
            prev = json.loads(older[-1].read_text(encoding="utf-8"))
        except Exception:
            prev = None
    for k, b in d["b"].items():
        u = b["u"]; uf = b.get("uf", u); ub = b.get("ub") or [0] * len(u)
        for j in (L - 1, L):
            if u[j] >= 20000 and ub[j] / u[j] > 0.30:
                warn.append(f"{k} {M[j]} 세트 곡선 {ub[j]:,} = 판매량의 {ub[j] / u[j]:.0%}")
            if uf[j] > 0 and u[j] / uf[j] > 1.8 and u[j] - uf[j] > 20000:
                warn.append(f"{k} {M[j]} 추정 {u[j]:,} = 배지 실측 {uf[j]:,} 의 {u[j] / uf[j]:.1f}배")
        if prev and k in prev.get("b", {}):
            pm = prev["months"]; pub = prev["b"][k].get("ub") or [0] * len(pm)
            for j in (L - 1, L):
                if M[j] in pm:
                    was = pub[pm.index(M[j])]
                    if ub[j] >= 20000 and ub[j] > 3 * max(was, 1000):
                        warn.append(f"{k} {M[j]} 세트 곡선 {was:,} → {ub[j]:,} (직전 회차 {older[-1].stem} 대비)")
    fit = d.get("fit") or {}
    if fit.get("nbShared"):
        print(f"[KBPH] 부모 순위를 물려받은 배지 없는 옵션 {fit['nbShared']}칸 → 49개 상한 처리됨")
    for w in warn:
        print(f"[KBPH 경고] {w}")
    return warn


def legacy_fix(d):
    """옛 코드(2026-11-24 전 · fit 에 nbShared 가 없는 원재료)의 세트 곡선(ub)을 저장된 값으로 바로잡는다.
    옛 코드는 배지 없는 옵션이 형제의 부모 순위를 달고 있으면 곡선값을 상한 없이 줬다(바이오던스 Pack of 2 · 힌스 호수 옵션 …).
    새 규칙은 그런 옵션을 옵션당 49개로 막는다 — 배지가 한 번도 없다 = 아마존 기준 월 50개 미만이라서.
    원재료엔 상품 줄이 없고 브랜드 × 월 ub 합만 있어서 옵션당 49개 몫까지는 못 되살린다 → ub 를 통째로 뺀다
    (빠지는 것 = 옵션당 월 49개 이하 · Keepa 이력이 빈 진짜 세트). 판매액·신규 SKU 몫은 같은 비율로 줄인다.
    다음 회차(새 코드)부터는 원재료에 ub 가 새 규칙으로 들어와 이 함수가 아무것도 안 한다."""
    if "nbShared" in (d.get("fit") or {}):
        return None
    tot = {}
    for k, b in d["b"].items():
        ub = b.pop("ub", None)
        if not ub or not any(ub):
            continue
        for j, x in enumerate(ub):
            u = b["u"][j]
            if not x or not u:
                continue
            f = max(u - x, 0) / u
            b["u"][j] = u - x
            b["v"][j] = round(b["v"][j] * f)
            b["nw"][j] = round(b["nw"][j] * f)
        tot[k] = sum(ub)
    big = sorted(tot.items(), key=lambda t: -t[1])[:8]
    print("[KBPH 보정] 옛 세트 곡선 제외:", " · ".join(f"{k} {v:,}" for k, v in big))
    return {"ub": sum(tot.values()), "n": len(tot)}


def build(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    warn = audit(path, d)
    fix = legacy_fix(d)
    n = len(d["months"])
    for k, b in d["b"].items():
        for f in ("u", "n1k", "nw"):
            if len(b[f]) != n:
                raise SystemExit(f"{k}.{f} 길이 {len(b[f])} ≠ 월 수 {n}")
    # 최근 30일 창(phase_keepa.js · 2026-10-24) — 배지 아랫값 합이라 월별 u(구간 안 위치 보정)와 같은 배수로 수준을 맞춘다
    L = n - 1
    su = sum(sum(b["u"][L - 12:L]) for b in d["b"].values()); sf = sum(sum(b.get("uf", b["u"])[L - 12:L]) for b in d["b"].values())
    rk = su / sf if sf else 1.0
    for b in d["b"].values():
        if b.get("r30"):
            b["r30"] = [round(y * rk) for y in b["r30"]]
        if b.get("rw"):   # 3달·1달 창(2026-10-27 · 기준점 14일 간격 7개 × 0·30·60·90·120·150·365·395·425일 전 배지 아랫값 합) — r30 과 같은 배수
            b["rw"] = [[round(y * rk) for y in a] for a in b["rw"]]
    out = {"asOf": d["asOf"], "src": d["src"], "months": d["months"], "partial": d.get("partial"), "b": d["b"]}
    if fix:
        out["fix"] = fix   # 옛 세트 곡선을 뺀 회차(legacy_fix · 2026-11-24)
    if warn:
        out["warn"] = warn[:20]   # 화면·브리핑이 '추정 경고'로 쓸 수 있게(지금은 콘솔만 · 2026-11-24)
    if d.get("r30t"):
        out["r30t"] = d["r30t"]
    if d.get("rws") and any(b.get("rw") for b in d["b"].values()):
        out["rw"] = {"t": d.get("r30t") or d["asOf"], "s": d["rws"]}   # 기준점 0 = 수집일 · s = 기준점 간격(일)
    tt = build_tt(set(d["b"]) | set(MK_META) | set(TT_META))   # 미국 아마존에 없는 브랜드(MK_META)도 틱톡샵 공식 샵이 있으면 받는다
    if tt:
        build_fmx(tt)
        out["tt"] = tt
    ttr = build_ttr(set(d["b"]) | set(MK_META) | set(TT_META))
    if ttr:
        out["ttr"] = ttr
        print("[KBPH] 틱톡샵 미국 밖:", " · ".join(f"{rg} {len(t['b'])}브랜드 {t['nShop']}샵 {t['end']}" for rg, t in ttr.items()))
    mk = build_mk(d)
    if mk:
        out["mk"] = mk
    meta = d.pop("_mkmeta", None) or {}
    if tt:   # 틱톡샵에만 있는 브랜드의 이름·주인(2026-11-27)
        meta.update({k: TT_META[k] for k in tt["b"] if k in TT_META and k not in d["b"]})
    for t in (ttr or {}).values():
        meta.update({k: TT_META[k] for k in t["b"] if k in TT_META and k not in d["b"]})
    if meta:
        out["meta"] = meta
    return out


# ── 유럽 아마존(영·독·프·이·스) — Keepa Product Finder 를 나라마다 같은 조건으로(phase_keepa_eu.js 덤프 · data/phase/eu/<날짜>.txt · 2026-10-21) ──
#   D|나라|날짜|첫 달|행 수 · 브랜드 줄 k|SKU 수|u 36개(36진수)|v 36개(현지 통화 · 36진수) · H|검산값
#   v = 판매량 × 그달 가격(바이박스 → 신품 최저가 → 아마존가 · 미국과 같은 식) — 파운드·유로. 달러·원화 환산은 화면(kbFx · ECB 월평균)에서.
#   한글 이름·회사·ODM(ko·co·sup)은 미국 바구니(d["b"])에서 가져온다 — 나라마다 바구니는 그 나라에 든 브랜드만.
# 미국 아마존 바구니에 없고 다른 나라에만 있는 브랜드(2026-11-26 · 브랜드501 의 바버501·호토미·메종드펜세는 일본 아마존에만 있다).
#   여기 없는 브랜드가 나라 덩어리에만 나오면 예전처럼 멈춘다(오타·동명 브랜드를 걸러 내려고) — 새로 넣을 땐 한 줄 더할 것.
MK_META = {"barber501": {"ko": "바버501", "op": "브랜드501"}, "hotomi": {"ko": "호토미", "op": "브랜드501"},
           "maison de p:ensee": {"ko": "메종드펜세", "op": "브랜드501"}, "series y": {"ko": "시리즈와이", "op": "브랜드501"}}
MK_CUR = {"uk": "GBP", "de": "EUR", "fr": "EUR", "it": "EUR", "es": "EUR", "jp": "JPY", "ca": "CAD"}


def _eu_hash(b):
    h = 0
    for k in sorted(b):
        for i, x in enumerate(b[k]["u"]):
            h = (h + x * (i + 1)) % 1000003
        for i, x in enumerate(b[k]["v"]):
            h = (h + x * (i + 7)) % 1000003
    return h


def build_mk(d):
    files = sorted((SRC / "eu").glob("20??-??-??*.txt"))
    if not files:
        return None
    # 나라마다 가장 최근 파일의 덩어리를 쓴다(2026-11-03 · 통합 수집이 한도로 몇 나라만 받은 날 · 월·화에 빠진 나라만 받은 날이 생긴다).
    #   예전엔 마지막 날짜 파일만 읽어, 하루에 몇 나라만 받으면 나머지 나라가 통째로 빠졌다. 파일 이름 순 = 날짜 순 · 같은 날 여럿이면 뒤 파일이 이긴다.
    # '-add' 파일(2026-11-26) = 그 나라 덩어리에 빠진 브랜드만 나중에 받은 것 — 덩어리를 갈아 끼우지 않고 브랜드 줄만 더한다(자기 검산값 따로).
    #   phase_keepa_eu.js save(나라, {now: 덩어리 수집일}) 로 창 기준일을 덩어리와 맞춰 받는다. 그 뒤 날짜의 온전한 덩어리가 오면 그쪽이 이긴다(새 덩어리엔 그 브랜드가 들어 있다).
    blocks, adds = {}, {}
    for f in files:
        cur_k, buf = None, []
        for ln in f.read_text(encoding="utf-8").splitlines() + ["D|"]:
            p = ln.strip().split("|")
            if p and p[0] == "D":
                if cur_k:
                    if "-add" in f.name:
                        adds.setdefault(cur_k, []).append((f.name, buf))
                    else:
                        blocks[cur_k] = (f.name[:10], buf)
                        adds.pop(cur_k, None)
                cur_k, buf = (p[1] if len(p) > 1 else None), [ln]
            elif cur_k:
                buf.append(ln)
    out, cur, lines = {}, None, []
    for k, (fd, buf) in blocks.items():
        p = buf[0].strip().split("|")
        if p[3] != d["months"][0]:   # 미국과 첫 달이 다르다 = 달이 바뀌기 전에 받은 옛 덩어리 → 그 나라는 다음 회차까지 뺀다
            print(f"  [mk] {k} 첫 달 {p[3]} ≠ 미국 {d['months'][0]} ({fd} 파일) — 이번엔 뺀다")
            continue
        lines += buf
    for ln in lines:
        p = ln.strip().split("|")
        if not p or not p[0]:
            continue
        if p[0] == "D":
            cur = {"cur": MK_CUR[p[1]], "asOf": p[2], "rows": int(p[4]), "b": {}, "ref": len(p) > 5 and p[5] == "r"}
            out[p[1]] = cur
        elif p[0] == "H":
            h = _eu_hash(cur["b"])
            if h != int(p[1]):
                raise SystemExit(f"유럽 덤프 검산 틀림: {h} ≠ {p[1]}")
        else:
            u = [int(x, 36) for x in p[2].split(",")]
            v = [int(x, 36) for x in p[3].split(",")]
            if len(u) != len(d["months"]) or len(v) != len(d["months"]):
                raise SystemExit(f"유럽 {p[0]} 길이 {len(u)}/{len(v)}")
            cur["b"][p[0]] = {"u": u, "v": v, "n": int(p[1])}
            if len(p) > 4 and p[4]:   # 최근 30일 창(2026-10-24 · 오늘·30일 전·365일 전·395일 전 배지 아랫값 합)
                cur["b"][p[0]]["r30"] = [int(x, 36) for x in p[4].split(",")]
            if len(p) > 5 and p[5]:   # 3달·1달 창(2026-10-27 · 기준점 7개 × 9칸 = 63개 · 미국판 rw 와 같은 모양)
                w = [int(x, 36) for x in p[5].split(",")]
                if len(w) != 63:
                    raise SystemExit(f"유럽 {p[0]} rw 길이 {len(w)} ≠ 63")
                cur["b"][p[0]]["rw"] = [w[i * 9:(i + 1) * 9] for i in range(7)]
    # 덤프의 v 는 Keepa 가격(최소 단위)을 100 으로 나눈 값 — 엔화는 최소 단위가 1엔이라 다시 100 을 곱한다
    for m, c in out.items():
        if c["cur"] == "JPY":
            for x in c["b"].values():
                x["v"] = [y * 100 for y in x["v"]]
    # 배지 구간 보정(phase_keepa_eu.js · D 줄 끝 'r')을 안 거친 나라는 수준만 맞춘다(2026-10-22 · Keepa 하루 한도로 독·프·이·스·캐나다를 못 다시 받았다).
    #   보정값 ÷ 아랫값이 시장마다 거의 같다(최근 12개 완결 달 · 미국 1.21 · 영국 1.20 · 일본 1.21) — 브랜드별 미국 배수보다 시장 상수가 영국·일본 브랜드 배수를 더 잘 맞혔다
    #   (중앙 오차 4~6% vs 7%). 상수라 그 나라 안의 비중·QoQ·YoY 는 안 바뀌고, 전 지역 합산·판매액의 나라 사이 수준만 맞는다. 다음 회차에 'r' 덤프가 오면 저절로 빠진다.
    ub = d["b"]; L = len(d["months"]) - 1
    su = sum(sum(b["u"][L - 12:L]) for b in ub.values()); sf = sum(sum(b.get("uf", b["u"])[L - 12:L]) for b in ub.values())
    k = round(su / sf, 3) if sf else 1.0
    for m, c in out.items():
        if c.pop("ref"):
            continue
        c["adj"] = k
        for x in c["b"].values():
            x["u"] = [round(y * k) for y in x["u"]]
            x["v"] = [round(y * k) for y in x["v"]]
    # 나중에 받은 브랜드 끼우기 — 검산값은 그 브랜드들만으로 · 보정('r') 안 된 덤프면 위와 같은 시장 상수 k · 이미 있는 브랜드는 덩어리 쪽이 이긴다
    for m, lst in adds.items():
        c = out.get(m)
        if not c:
            continue
        for fn, buf in lst:
            hd = buf[0].strip().split("|")
            if hd[3] != d["months"][0]:
                print(f"  [mk] {m} 추가분 {fn} 첫 달 {hd[3]} ≠ {d['months'][0]} — 뺀다")
                continue
            if abs((dt.date.fromisoformat(hd[2]) - dt.date.fromisoformat(c["asOf"])).days) > 1:
                print(f"  [mk] {m} 추가분 {fn} 기준일 {hd[2]} ≠ 덩어리 {c['asOf']} — 창이 어긋난다(그래도 넣는다)")
            ref, nb = len(hd) > 5 and hd[5] == "r", {}
            for ln in buf[1:]:
                p = ln.strip().split("|")
                if not p or not p[0]:
                    continue
                if p[0] == "H":
                    if _eu_hash(nb) != int(p[1]):
                        raise SystemExit(f"유럽 추가분 검산 틀림({fn} {m}): {_eu_hash(nb)} ≠ {p[1]}")
                    continue
                x = {"u": [int(y, 36) for y in p[2].split(",")], "v": [int(y, 36) for y in p[3].split(",")], "n": int(p[1])}
                if len(x["u"]) != len(d["months"]) or len(x["v"]) != len(d["months"]):
                    raise SystemExit(f"유럽 추가분 {p[0]} 길이 {len(x['u'])}/{len(x['v'])}")
                if len(p) > 4 and p[4]:
                    x["r30"] = [int(y, 36) for y in p[4].split(",")]
                if len(p) > 5 and p[5]:
                    w = [int(y, 36) for y in p[5].split(",")]
                    if len(w) != 63:
                        raise SystemExit(f"유럽 추가분 {p[0]} rw 길이 {len(w)} ≠ 63")
                    x["rw"] = [w[i * 9:(i + 1) * 9] for i in range(7)]
                nb[p[0]] = x
            for kk, x in nb.items():
                if kk in c["b"]:
                    continue
                if c["cur"] == "JPY":
                    x["v"] = [y * 100 for y in x["v"]]
                if not ref:
                    x["u"] = [round(y * k) for y in x["u"]]
                    x["v"] = [round(y * k) for y in x["v"]]
                c["b"][kk] = x
            c["add"] = sorted(set(c.get("add", [])) | set(nb))
            print(f"  [mk] {m} 추가분 {fn} 브랜드 {len(nb)}개 끼움{'' if ref else ' (보정 없음 → 시장 상수 ' + str(k) + ')'}")
    # 최근 30일 창은 보정 안 된 배지 아랫값이라 나라 구분 없이 같은 배수(미국 보정값 ÷ 아랫값)로 수준을 맞춘다 — 틱톡샵 주문 수량과 더해도 무게가 월별 u 와 같게
    for m, c in out.items():
        for x in c["b"].values():
            if x.get("r30"):
                x["r30"] = [round(y * k) for y in x["r30"]]
            if x.get("rw"):
                x["rw"] = [[round(y * k) for y in a] for a in x["rw"]]
    meta = {}
    for m, c in out.items():
        miss = [k for k in c["b"] if k not in d["b"] and k not in MK_META and k not in TT_META]   # 2026-11-27 틱톡샵에만 있던 한국 브랜드(TT_META)도 아마존 나라 덩어리에 나올 수 있다
        if miss:
            raise SystemExit(f"유럽 {m}: 미국 바구니에 없는 브랜드 {miss}")
        meta.update({k: MK_META.get(k) or TT_META[k] for k in c["b"] if k not in d["b"]})
    if meta:
        d["_mkmeta"] = meta   # 미국에 없는 브랜드의 한글 이름·주인 — build() 가 블록 meta 로 싣는다(화면 KBB·브리핑 nm 이 읽는다)
    return out


# ── 틱톡샵(미국) — FastMoss 샵 상세 '최근 180일' 일별(kbeauty/fastmoss.js 덤프 · data/phase/fm/<받은 날>.txt) ──
# 덤프의 브랜드키(grab 셋째 인자) → 위 아마존 바구니의 브랜드 키. 미국 공식 샵을 못 찾은 브랜드: 설화수·메디필 · 페리페라·구달은 'Clio Official USA' 한 샵에 클리오와 섞여 있어 'clio' 로 통째로 넣는다(2026-10-21)
TT_MAP = {"anua": "anua", "skin1004": "skin1004", "boj": "beauty of joseon", "celimax": "celimax", "dralthea": "dr.althea",
          "torriden": "torriden", "numbuzin": "numbuzin", "roundlab": "round lab", "vt": "vt cosmetics", "centellian": "centellian 24",
          "abib": "abib", "mixsoon": "mixsoon", "somebymi": "some by mi", "haruharu": "haruharu", "manyo": "ma:nyo", "axisy": "axis-y",
          "isntree": "isntree", "tonymoly": "tonymoly", "innisfree": "innisfree", "romand": "rom&nd", "medicube": "medicube",
          "missha": "missha", "dalba": "d'alba piedmont", "cosrx": "cosrx", "laneige": "laneige", "belif": "belif", "rejuran": "rejuran",
          "biodance": "biodance", "equalberry": "eqqualberry",
          "tfs": "the face shop", "drgroot": "dr.groot", "hince": "hince",   # LG생활건강 미국 공식 샵(2026-11-03 · 키는 KBCH fm_shops.csv 와 같다)
          "clio": "clio",
          "aromatica": "aromatica", "aprilskin": "aprilskin", "illiyoon": "illiyoon", "mise": "mise en scene",   # 2026-11-26 추가 브랜드 — KBCH fm_shops.csv 가 이미 받던 미국 공식 샵 넷
          "tirtir": "tirtir", "laka": "laka", "etude": "etude", "espoir": "espoir", "hera": "hera", "skinfood": "skinfood",   # 같은 날 EchoTik 에서 찾은 미국 공식 샵 여섯(fm_shops.csv 에 넣음 · 90일치뿐이라 build_tt 가 late 로 뺀다)
          "melaxin": "dr.melaxin", "barber501": "barber501",   # 브랜드501(2026-11-26 · 비상장) — 'Brand Dr.Melaxin'(7495830785034323995 · 미국 틱톡샵 상위권) · BARBER501 Global(7496007994044811682 · 누적 7개)
          "zeroid": "zeroid",   # ZEROID Global(네오팜 · 8653940256625430663) — 하루 몇 개라도 있는 숫자는 넣는다(2026-10-22 사용자 "어쨋든 존재하는 숫자잖아")   # Clio Official USA(Stride Leader Corporation) — 클리오·페리페라·구달이 한 샵에 섞여 있어 'clio' 칸에 통째로 넣는다(2026-10-21)
          # 2026-11-27 사용자 "한국 브랜드 빠진 게 더는 없게" — FastMoss 새 계정으로 미국 공식 샵을 훑어 찾은 한국 브랜드(샵 99곳 · mixsoon-us 는 위 mixsoon 칸에 더한다).
          #   틱톡샵에만 있는 브랜드는 키 그대로가 바구니 키(아마존 바구니에 없음 · 이름·주인 = TT_META). 안 넣은 샵: Euthymol(LG생활건강 · 영국 태생 — 피지오겔·더크렘샵과 같은 규칙) ·
          #   Svelta Seoul·Dr.ville·YOUNGPLUS(한국 브랜드인지 확인 못 함 · 덤프·KBCH 원자료엔 남아 있다)
          "sungboon": "sungboon", "drg": "drg", "biohealboh": "biohealboh", "arencia": "arencia", "colorgram": "colorgram", "drrejuall": "drrejuall",
          "beplain": "beplain", "oganacell": "oganacell", "growus": "growus", "ongredients": "ongredients", "mediheal": "mediheal",
          "banilaco": "banilaco", "elroel": "elroel", "drforhair": "drforhair", "ohora": "ohora", "nooni": "nooni", "hetras": "hetras",
          "iunik": "iunik", "ilso": "ilso", "drjart": "drjart", "klairs": "klairs", "imfrom": "imfrom", "wellage": "wellage",
          "pyunkangyul": "pyunkangyul", "terezhonor": "terezhonor", "cellfusionc": "cellfusionc", "amuse": "amuse", "tfit": "tfit",
          "purcell": "purcell", "2an": "2an", "thome": "thome", "siot": "siot", "lactomedi": "lactomedi", "beaund": "beaund", "age20s": "age20s",
          "tsshampoo": "tsshampoo", "easydew": "easydew", "purito": "purito", "benton": "benton", "jsm": "jsm", "heimish": "heimish",
          "marymay": "marymay", "holika": "holika", "naturerepublic": "naturerepublic", "drceuracle": "drceuracle", "dermafirm": "dermafirm",
          "jayjun": "jayjun", "paparecipe": "paparecipe", "unove": "unove", "drdifferent": "drdifferent", "jmsolution": "jmsolution",
          "rovectin": "rovectin", "wishtrend": "wishtrend", "tcfs": "tcfs", "meditherapy": "meditherapy", "frudia": "frudia", "drpepti": "drpepti",
          "koelf": "koelf", "touchinsol": "touchinsol", "demaf": "demaf", "leaders": "leaders", "deardahlia": "deardahlia", "makeprem": "makeprem",
          "tocobo": "tocobo", "jumiso": "jumiso", "kundal": "kundal", "needly": "needly", "skinlab": "skinlab", "mizon": "mizon", "kahi": "kahi",
          "dashu": "dashu", "cosnori": "cosnori", "wonjin": "wonjin", "lagom": "lagom", "hanskin": "hanskin", "neogen": "neogen", "obge": "obge",
          "aplb": "aplb", "kocostar": "kocostar", "klavuu": "klavuu", "bonajour": "bonajour"}
# 늦게 들어온 샵(받기 시작한 날이 바구니 첫날보다 30일 넘게 늦은 샵)은 build_tt 가 관측 전 날을 바구니 모양으로 채운다(2026-11-27 · 예전 TT_BACKFILL 의
#   '아마존 같은 브랜드 모양' 채움은 닥터멜락신 한 곳용이었다 — 새 계정 FastMoss 로 그 샵도 5/31~ 실측이 생겨 일반 규칙 하나로 합쳤다).
# 틱톡샵에만 있는 브랜드(아마존 미국 바구니 밖)의 한글 이름 · 주인(2026-11-27) — co = 상장사 · op = 비상장 운영사·모회사(확인된 것만).
#   build() 가 블록 meta 에 싣는다(화면 이름 · 브리핑 nm). 새 샵을 TT_MAP 에 넣을 때 여기에도 한 줄.
TT_META = {
    "sungboon": {"ko": "성분에디터"}, "drg": {"ko": "닥터지", "op": "고운세상코스메틱(로레알)"}, "biohealboh": {"ko": "바이오힐보", "op": "CJ올리브영"},
    "arencia": {"ko": "아렌시아"}, "colorgram": {"ko": "컬러그램", "op": "CJ올리브영"}, "drrejuall": {"ko": "닥터리쥬올"}, "beplain": {"ko": "비플레인"},
    "oganacell": {"ko": "오가나셀"}, "growus": {"ko": "그로우어스"}, "ongredients": {"ko": "온그리디언츠"}, "mediheal": {"ko": "메디힐", "op": "엘앤피코스메틱"},
    "banilaco": {"ko": "바닐라코", "op": "에프앤코"}, "elroel": {"ko": "엘로엘"}, "drforhair": {"ko": "닥터포헤어", "op": "폴리페놀팩토리"},
    "ohora": {"ko": "오호라", "op": "글루가"}, "nooni": {"ko": "누니"}, "hetras": {"ko": "헤트라스"}, "iunik": {"ko": "아이유닉"}, "ilso": {"ko": "일소"},
    "drjart": {"ko": "닥터자르트", "op": "에스티로더"}, "klairs": {"ko": "클레어스", "op": "위시컴퍼니"}, "imfrom": {"ko": "아임프롬"},
    "wellage": {"ko": "웰라쥬", "co": "휴젤"}, "pyunkangyul": {"ko": "편강율"}, "terezhonor": {"ko": "테레즈아너"}, "cellfusionc": {"ko": "셀퓨전씨"},
    "amuse": {"ko": "어뮤즈", "co": "신세계인터내셔날"}, "tfit": {"ko": "티핏"}, "purcell": {"ko": "퍼셀"}, "2an": {"ko": "투에이엔"}, "thome": {"ko": "티홈"},
    "siot": {"ko": "시옷"}, "lactomedi": {"ko": "락토메디"}, "beaund": {"ko": "뷰앤드"}, "age20s": {"ko": "에이지투웨니스", "co": "애경산업"},
    "tsshampoo": {"ko": "TS샴푸", "co": "TS트릴리온"}, "easydew": {"ko": "이지듀", "co": "대웅제약"}, "purito": {"ko": "퓨리토"}, "benton": {"ko": "벤튼"},
    "jsm": {"ko": "정샘물"}, "heimish": {"ko": "헤이미쉬"}, "marymay": {"ko": "메리메이"}, "holika": {"ko": "홀리카홀리카", "op": "엔프라니"},
    "naturerepublic": {"ko": "네이처리퍼블릭"}, "drceuracle": {"ko": "닥터수라클"}, "dermafirm": {"ko": "더마펌"}, "jayjun": {"ko": "제이준"},
    "paparecipe": {"ko": "파파레서피"}, "unove": {"ko": "어노브"}, "drdifferent": {"ko": "닥터디퍼런트"}, "jmsolution": {"ko": "JM솔루션"},
    "rovectin": {"ko": "로벡틴"}, "wishtrend": {"ko": "위시트렌드", "op": "위시컴퍼니"}, "tcfs": {"ko": "투쿨포스쿨"}, "meditherapy": {"ko": "메디테라피"},
    "frudia": {"ko": "프루디아"}, "drpepti": {"ko": "닥터펩티"}, "koelf": {"ko": "쁘띠페·코엘프"}, "touchinsol": {"ko": "터치인솔"}, "demaf": {"ko": "데마프"},
    "leaders": {"ko": "리더스", "co": "산성앨엔에스"}, "deardahlia": {"ko": "디어달리아"}, "makeprem": {"ko": "메이크프렘"}, "tocobo": {"ko": "토코보"},
    "jumiso": {"ko": "주미소"}, "kundal": {"ko": "쿤달"}, "needly": {"ko": "니들리"}, "skinlab": {"ko": "스킨랩"}, "mizon": {"ko": "미즈온"},
    "kahi": {"ko": "가히", "op": "코리아테크"}, "dashu": {"ko": "다슈"}, "cosnori": {"ko": "코스노리"}, "wonjin": {"ko": "원진이펙트"}, "lagom": {"ko": "라곰"},
    "hanskin": {"ko": "한스킨"}, "neogen": {"ko": "네오젠"}, "obge": {"ko": "오브제"}, "aplb": {"ko": "APLB"}, "kocostar": {"ko": "코코스타"},
    "klavuu": {"ko": "클라뷰"}, "bonajour": {"ko": "보나쥬르"}}
RW_N = 7              # 3달·1달 창의 기준점 수(14일 간격 · 최근 12주) — phase_keepa.js 의 RWN 과 같게
TT_MAXW = 52          # 주별 칸 최대 — '평소'를 아마존처럼 1년까지(덤프가 쌓이면 늘어난다)


def _b36(s):
    return int(s, 36) if s else 0


def _kalo():
    """Kalodata 일별(kbeauty/kalodata.py) — 소급이 끝났을 때만(아니면 None → 예전 FastMoss·EchoTik 덤프)"""
    try:
        sys.path.insert(0, str(HERE))
        import kalodata
        return kalodata.load()
    except Exception as e:
        print(f"[KBPH] Kalodata 읽기 실패 — 예전 덤프로: {e}")
        return None


FMI = HERE / "data" / "fmi"   # 틱톡샵 미국 밖 나라 공식 샵(FastMoss 샵 상세 180일 · 2026-11-27) — data/phase 밖(국면 브리핑을 안 깨운다)
TT_RG = {"GB": "uk", "DE": "de", "FR": "fr", "IT": "it", "ES": "es", "JP": "jp"}   # 아마존 시장 칸이 있는 나라 — 나머지(동남아·중남미·유럽 소국)는 '전 지역'에만 더한다
VND_PER_USD = 26300   # 베트남 동은 ECB 기준환율에 없다 — 고정값(2026-11 무렵 · 화면 판매액만 바뀌고 판매량·비중은 그대로)


def _fx_usd():
    """{통화: {ym: 그 통화 1단위 = 달러}} — fx_month.csv(USD·GBP·EUR·JPY·CAD) + fx_tt.csv(IDR·MYR·PHP·THB·SGD·MXN·BRL·PLN·CZK·HUF) · 원화 교차"""
    import csv
    krw = {}
    for name in ("fx_month.csv", "fx_tt.csv"):
        f = HERE / "data" / name
        if not f.exists():
            continue
        for r in csv.DictReader(f.open(encoding="utf-8")):
            for c, v in r.items():
                if c not in ("ym", "days") and v:
                    krw.setdefault(c, {})[r["ym"]] = float(v)
    usd = krw.get("USD", {})
    out = {c: {ym: v / usd[ym] for ym, v in m.items() if usd.get(ym)} for c, m in krw.items()}
    out["USD"] = {ym: 1.0 for ym in usd}
    out["VND"] = {ym: 1.0 / VND_PER_USD for ym in usd}
    return out


def _rate(fx, cur, ym):
    m = fx.get(cur) or {}
    if ym in m:
        return m[ym]
    if not m:
        return None
    best = min(m, key=lambda x: abs((dt.date.fromisoformat(x + "-15") - dt.date.fromisoformat(ym + "-15")).days))
    return m[best]


def _tk(fk, keys):
    """FastMoss 키 → 바구니 키 — TT_MAP 이 먼저, 없으면 키가 바구니에 그대로 있으면 그것(구달·페리페라처럼 미국 틱톡샵 공식 샵이 없던 브랜드 · 2026-11-27)"""
    k = TT_MAP.get(fk)
    return k if k else (fk if fk in keys else None)


def build_tt(keys, region=None, src=None, fx=None):
    """FastMoss 덤프를 **전부** 이어 붙인다(같은 샵·같은 날은 나중 덤프가 이긴다 · 덤프마다 받은 날과 그 뒤는 진행 중이라 버린다).
    FastMoss 는 180일만 주므로 매주 받은 덤프를 버리지 않고 이어야 '평소'·꼬리가 길어진다(2026-10-21).
    region(2026-11-27) = 그 나라 샵만(S 줄 둘째 칸) · src = 덤프 폴더(미국 밖 = data/fmi) · fx = 판매액을 달러로(나라 통화 → 그달 평균 환율)."""
    files = sorted((src or (SRC / "fm")).glob("20??-??-??*.txt" if src else "20??-??-??.txt"))
    KL = _kalo() if not region else None
    if not files and not KL:
        return None
    S, day, fhs, soc = {}, {}, [], {}
    eday = set()   # (샵, 날) 중 지금 값이 EchoTik 이어 붙이기(FH|E1)에서 온 것 — FastMoss 덤프가 나중에 덮으면 빠진다(2026-11-27 · 새 계정 FastMoss 로 EchoTik 구간을 덮음)
    for path in files:
        fh = None
        isE = False
        for l in path.read_text(encoding="utf-8").splitlines():
            f = l.split("|")
            if f[0] == "FH":
                fh = f[2]
                isE = str(f[1]).startswith("E")
            elif f[0] == "S":
                S[f[1]] = {"k": f[3], "name": f[5], "r": f[2], "c": f[4]}
            elif f[0] == "V" and fh and not isE and not region:   # 미국 밖은 소셜을 안 싣는다(블록 크기)
                # 틱톡 소셜(2026-11-27) — 그날 샵 상품이 걸린 새 영상 · 처음 그 샵을 홍보한 크리에이터 · 라이브(FastMoss 만 · EchoTik 은 정의가 달라 안 쓴다)
                d0 = dt.date.fromisoformat(f[2])
                cut = dt.date.fromisoformat(fh)
                A, C, Lv = ([_b36(x) for x in f[k].split(",")] for k in (3, 4, 5))
                sv = soc.setdefault(f[1], {})
                for i, a_ in enumerate(A):
                    t = d0 + dt.timedelta(days=i)
                    if t < cut:
                        sv[t] = (a_, C[i] if i < len(C) else 0, Lv[i] if i < len(Lv) else 0)
            elif f[0] == "D" and fh:
                d0 = dt.date.fromisoformat(f[2])
                U, V = [_b36(x) for x in f[3].split(",")], [_b36(x) for x in f[4].split(",")]
                cut = dt.date.fromisoformat(fh)
                dd = day.setdefault(f[1], {})
                for i, (u, v) in enumerate(zip(U, V)):
                    t = d0 + dt.timedelta(days=i)
                    if t < cut:
                        dd[t] = (u, v)
                        if isE:
                            eday.add((f[1], t))
                        else:
                            eday.discard((f[1], t))
        if fh:
            fhs.append(fh)
    if KL:
        # Kalodata 한 출처(2026-11-26) — 샵 목록은 지금까지 국면 덤프에 든 샵 그대로(바구니를 바꾸지 않는다) · 판매량·판매액은 전부 Kalodata.
        #   FastMoss·EchoTik 일별은 안 섞는다. 늦게 들어온 샵의 아마존 채움(late·est)도 쓸 일이 없다 — Kalodata 가 그 샵의 앞 기간도 준다.
        seen = set(day) | set(S)
        day = {sid: dict(KL["day"][sid]) for sid in seen if sid in KL["day"]}
        fhs = [(dt.date.fromisoformat(KL["meta"]["to"]) + dt.timedelta(days=1)).isoformat()]
    if region:
        day = {sid: dd for sid, dd in day.items() if S.get(sid, {}).get("r") == region}
        if fx:   # 판매액 = 현지 통화 → 달러(그달 평균 환율) — 미국 칸과 같은 단위
            for sid, dd in day.items():
                c = S[sid].get("c") or "USD"
                for t, (u, v) in list(dd.items()):
                    r_ = _rate(fx, c, t.isoformat()[:7])
                    dd[t] = (u, round(v * r_) if r_ else 0)
    if not day:
        return None
    # 끝날 = 지금 받는 샵들이 다 가진 마지막 날 — 한 샵만 하루 늦게 받으면(10/22 ZEROID 를 따로 받음) 나머지가 그날 0 으로 보여 주 칸이 밀린다
    top = max(max(dd) for dd in day.values() if dd)
    end = min(max(dd) for dd in day.values() if dd and max(dd) >= top - dt.timedelta(days=10))
    start = min(min(dd) for dd in day.values() if dd)
    nw = min(TT_MAXW, ((end - start).days + 1) // 7)
    first = end - dt.timedelta(days=7 * nw - 1)
    # 달 — 처음부터 끝까지 받은 달만 완결(첫 달은 1일부터 있어야) · 끝 달이 말일까지 안 찼으면 partial
    # 첫 달이 1일부터가 아니면(4/24~) 그 달 앞부분은 샵마다 '관측 첫 14일 평균 × 빠진 날수'로 채우고 mest 에 적는다(2026-10-21 · 잣대 통일 —
    # 3개월 비교(7~9월 ÷ 4~6월)에 4월이 필요하다. KBCH 의 kbShopQ 와 같은 채움). 그 달이 3개월 창에서 빠지면(11월~) 추정도 사라진다.
    m0 = dt.date(start.year, start.month, 1)
    if region and start.day > 15:   # 미국 밖 = 5/31~ 이라 5월이 하루뿐 — 그 달을 채우지 않고 다음 달부터 센다(주·3달 창은 첫날부터)
        m0 = dt.date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    gap = max(0, (start - m0).days)
    mest = [m0.isoformat()[:7]] if gap > 0 else []
    months, m = [], m0
    while m <= end:
        months.append(m.isoformat()[:7])
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    nxt = end + dt.timedelta(days=1)
    partial = months[-1] if months and nxt.month == end.month else None
    b, miss, late, est = {}, [], {}, {}
    # 늦게 들어온 샵 — 받기 시작한 날(fm_shops.csv w0)이 바구니 시작보다 30일 넘게 늦은 샵은 그 앞 판매를 모른다(FastMoss 180일 · EchoTik 90일).
    #   2026-11-26 엔 바구니에서 빼고 late 에 적었다(라카 = 주 5.8만 개라 넣는 달부터 분모가 튄다). 2026-11-27 부터는 관측 전 날을 바구니 모양으로 채워
    #   넣는다(아래 루프) — 채울 수 없는 샵(관측 28일 미만)만 late 로 남는다.
    w0s = {}
    shp = HERE / "data" / "fm_shops.csv"
    if shp.exists():
        import csv
        for r in csv.DictReader(shp.open(encoding="utf-8")):
            if r.get("w0"):
                w0s[r["s"]] = r["w0"]
    if KL:
        w0s = {}
    late_ = lambda sid: sid in w0s and dt.date.fromisoformat(w0s[sid]) > start + dt.timedelta(days=30)
    # 바구니 하루 판매량 모양(2026-11-27) — 처음부터 받은 샵(늦게 들어오지 않은 샵)의 합. 늦게 들어온 샵의 관측 전 날을 이 모양으로 채운다.
    base = {}
    for sid, dd in day.items():
        k = _tk(S.get(sid, {}).get("k"), keys)
        if not k or k not in keys or late_(sid):
            continue
        for t, (u, _v) in dd.items():
            base[t] = base.get(t, 0) + u
    for sid, dd in day.items():
        k = _tk(S.get(sid, {}).get("k"), keys)
        if not k or k not in keys:
            miss.append(S.get(sid, {}).get("k", sid))
            continue
        if late_(sid):
            # 늦게 들어온 샵(2026-11-27 개편 · 옛 규칙 = 바구니에서 빼고 late) — FastMoss 는 180일만 줘서 바구니 첫날(4/24)~받기 시작한 날(w0) 앞을 모른다.
            #   ① w0 뒤에 문을 연 샵(첫 자료가 w0 보다 3일 넘게 늦다) = 그 앞은 판매 0(샵이 없었다) — 채우지 않는다.
            #   ② w0 부터 팔고 있던 샵 = 관측 전 날을 [바구니 하루 판매량 × 관측 첫 30일의 이 샵 ÷ 바구니 배수] 로 채우고 est 에 적는다
            #      (판매액 = 그 판매량 × 관측 첫 30일 중앙 단가). 바구니 모양이라 행사·계절은 따라가고, 그 샵만의 출렁임은 없다.
            #   옛 규칙은 늦게 든 샵이 바구니에 들어가는 달부터 분모가 갑자기 커지는 걸 막으려고 뺐는데, 이 채움이면 분모가 처음부터 이어진다.
            o0 = min(dd) if dd else None
            w0 = dt.date.fromisoformat(w0s[sid])
            if o0 is None:
                late[k] = min(late.get(k, w0s[sid]), w0s[sid])
                continue
            if o0 <= w0 + dt.timedelta(days=3):
                obs = [t for t in sorted(dd) if t < o0 + dt.timedelta(days=30)]
                bo = sum(base.get(t, 0) for t in obs)
                if len(obs) < 28 or bo <= 0:
                    late[k] = min(late.get(k, w0s[sid]), w0s[sid])
                    continue
                r = sum(dd[t][0] for t in obs) / bo
                pr = sorted(dd[t][1] / dd[t][0] for t in obs if dd[t][0] > 0)
                p = pr[len(pr) // 2] if pr else 0
                dd = dict(dd)
                t, ne = start, 0
                while t < o0:
                    u = round(base.get(t, 0) * r)
                    dd[t] = (u, round(u * p))
                    ne += u
                    t += dt.timedelta(days=1)
                e = est.get(k)
                to, fr = (o0 - dt.timedelta(days=1)).isoformat(), o0.isoformat()
                if ne <= 0:   # 관측 첫 30일 판매가 0 이면 채움도 0 — 추정 표시를 안 단다
                    pass
                elif e:   # 같은 브랜드 샵이 여럿(홀리카홀리카 셋 · JM솔루션 다섯) — 기간을 넓히고 추정량을 더한다
                    e.update({"to": max(e["to"], to), "from": min(e["from"], fr), "u": e["u"] + ne})
                else:
                    est[k] = {"to": to, "from": fr, "r": round(r, 5), "kind": "tt", "u": ne}
        ds = sorted(dd)
        U = [dd[t][0] for t in ds]
        V = [dd[t][1] for t in ds]
        # 판매액 단가 오류 고침 — ingest.build_block 과 같은 규칙(위로 튄 날만 · 직전 28일 중앙 단가의 2.5배 초과 → 판매량 × 중앙 단가)
        fixed = []
        for i in range(len(U) if not KL else 0):           # Kalodata 는 실제 판매가 — FastMoss 단가 튐 고침을 안 쓴다(할인·묶음 판매도 그대로)
            if U[i] <= 0:
                continue
            past = sorted(V[j] / U[j] for j in range(max(0, i - 28), i) if U[j] > 0 and V[j] > 0 and j not in fixed)
            if len(past) < 10:
                continue
            med = past[len(past) // 2]
            if med > 0 and V[i] / U[i] > 2.5 * med:
                V[i] = round(U[i] * med)
                fixed.append(i)
        wu, wv = [0] * nw, [0] * nw
        mu, mv = [0] * len(months), [0] * len(months)
        fill = 0                                                    # 관측 전 날(4/1~첫날 전) 하루 채움값 — 3달 창도 같은 값을 쓴다
        if gap > 0 and ds and (ds[0] - start).days <= 3:            # 하루 이틀 늦게 받은 샵(ZEROID 10/22)도 같은 규칙으로 — 빠진 날수는 샵 자기 첫날 기준
            n14 = min(14, len(U))
            gs = (ds[0] - m0).days
            fill = sum(U[:n14]) / n14
            mu0, mv0 = fill * gs, sum(V[:n14]) / n14 * gs
        else:
            mu0 = mv0 = 0
        for t, u, v in zip(ds, U, V):
            if t > end:
                continue
            if first <= t <= end:
                w = (t - first).days // 7
                wu[w] += u
                wv[w] += v
            ym = t.isoformat()[:7]
            if ym in months:
                j = months.index(ym)
                mu[j] += u
                mv[j] += v
        mu[0] += round(mu0)
        mv[0] += round(mv0)
        o = b.setdefault(k, {"n": [], "u": [0] * nw, "v": [0] * nw, "mu": [0] * len(months), "mv": [0] * len(months), "fx": 0})
        o["n"].append(S[sid]["name"])
        o["u"] = [a + c for a, c in zip(o["u"], wu)]
        o["v"] = [a + c for a, c in zip(o["v"], wv)]
        o["mu"] = [a + c for a, c in zip(o["mu"], mu)]
        o["mv"] = [a + c for a, c in zip(o["mv"], mv)]
        o["fx"] += len(fixed)
        sv = soc.get(sid)
        if sv:
            # 주별 새 홍보 영상(sa)·새 크리에이터(sc)·라이브(sl) — 소셜 자료가 처음부터 끝까지 다 있는 주만(없는 주 = None)
            s0 = min(sv)
            for nm_, ix in (("sa", 0), ("sc", 1), ("sl", 2)):
                arr = []
                for w in range(nw):
                    a0 = first + dt.timedelta(days=7 * w)
                    arr.append(None if a0 < s0 else sum(sv.get(a0 + dt.timedelta(days=q), (0, 0, 0))[ix] for q in range(7)))
                prev = o.get(nm_)
                o[nm_] = arr if prev is None else [None if (x is None or y is None) else x + y for x, y in zip(prev, arr)]
        # 최근 30일 창(2026-10-24) — 끝날까지 30일 · 그 앞 30일(판매량)
        c30 = sum(u for t, u in zip(ds, U) if end - dt.timedelta(days=29) <= t <= end)
        p30 = sum(u for t, u in zip(ds, U) if end - dt.timedelta(days=59) <= t <= end - dt.timedelta(days=30))
        o["r30"] = [a + c for a, c in zip(o.get("r30", [0, 0]), [c30, p30])]
        # 3달·1달 창(2026-10-27 · 아마존 rw 와 같은 모양) — 기준점 = 끝날부터 14일 간격 7개 · 기준점마다 0·30·…·150일 전에 끝나는 30일 판매량 여섯 개
        #   (3달 = 앞 셋 vs 뒤 셋 · 1달 = 0 vs 1). 전년 칸은 없다(4/24~). 관측 전 날은 위 채움값 — 그 날이 든 창은 블록 rw.e3·e1 에 표시.
        daily = {t: u for t, u in zip(ds, U) if t <= end}
        if fill:
            for i in range((ds[0] - m0).days):
                daily.setdefault(m0 + dt.timedelta(days=i), fill)
        rw = [[round(sum(daily.get(end - dt.timedelta(days=14 * a + 30 * j + q), 0) for q in range(30))) for j in range(6)] for a in range(RW_N)]
        o["rw"] = [[x + y for x, y in zip(p_, q_)] for p_, q_ in zip(o.get("rw") or [[0] * 6] * RW_N, rw)]
    weeks = [(first + dt.timedelta(days=7 * w + 6)).isoformat() for w in range(nw)]   # 주 끝날
    # 3달·1달 창의 기준점별 쓸 수 있나 — ok3 = 180일 전까지 자료(관측 전 채움 포함)가 있다 · ok1 = 60일 · e3·e1 = 그 창에 채움값이 든다
    floor = m0 if gap > 0 else start
    anc = [end - dt.timedelta(days=14 * a) for a in range(RW_N)]
    rwm = {"t": end.isoformat(), "s": 14,
           "ok3": [int(a - dt.timedelta(days=179) >= floor) for a in anc], "ok1": [int(a - dt.timedelta(days=59) >= floor) for a in anc],
           "e3": [int(gap > 0 and a - dt.timedelta(days=179) < start) for a in anc], "e1": [int(gap > 0 and a - dt.timedelta(days=59) < start) for a in anc]}
    r30 = [(end - dt.timedelta(days=29)).isoformat(), end.isoformat(), (end - dt.timedelta(days=59)).isoformat(), (end - dt.timedelta(days=30)).isoformat()]
    return {"asOf": fhs[-1], "end": end.isoformat(), "r30": r30 if (end - start).days >= 59 else None, "rw": rwm, "start": start.isoformat(), "weeks": weeks, "months": months, "partial": partial, "mest": mest,
            "nShop": len(day), "nDump": len(files), "miss": sorted(set(miss)), "late": late, "est": est,
            "src": (f"틱톡샵 {region} 공식 샵 {len(day)}곳 · 샵 상세 일별 판매량({start.isoformat()}~{end.isoformat()} · FastMoss · 판매액은 그달 평균 환율로 달러)" if region else
                    f"틱톡샵 미국 공식 샵 {len(day)}곳 · Kalodata 일별 판매량·판매액({start.isoformat()}~{end.isoformat()} · 뷰티 카테고리 · 한 출처)" if KL else
                    f"틱톡샵 미국 공식 샵 {len(day)}곳 · 샵 상세 일별 판매량({start.isoformat()}~{end.isoformat()} · FastMoss" +
                    (f" · EchoTik 이어 붙인 날 {min(t for _, t in eday).isoformat()}~{max(t for _, t in eday).isoformat()}" if eday else "") + f" · 덤프 {len(files)}개)"),
            "kalo": bool(KL), "b": b, **({"rg": region} if region else {})}


def build_ttr(keys):
    """미국 밖 나라별 틱톡샵(2026-11-27 · 사용자 "틱톡은 유럽이나 다른 지역은 왜 안 채웠냐 — FastMoss 로 다 해 줘").
    data/fmi 덤프의 S 줄 나라마다 build_tt 를 따로 — {나라 코드: 블록}. 판매액은 달러(그달 평균 환율 · 동은 고정값)."""
    files = sorted(FMI.glob("20??-??-??*.txt"))
    if not files:
        return None
    rgs = set()
    for path in files:
        for l in path.read_text(encoding="utf-8").splitlines():
            f = l.split("|")
            if f[0] == "S" and f[2] != "US":
                rgs.add(f[2])
    fx = _fx_usd()
    out = {}
    for rg in sorted(rgs):
        t = build_tt(keys, region=rg, src=FMI, fx=fx)
        if t and t["b"]:
            for k_ in ("mest", "est", "late"):
                t.pop(k_, None) if not t.get(k_) else None
            out[rg] = t
    return out or None


FMX = HERE / "data" / "fmx"   # FastMoss 샵 '분석' 스냅샷 + 미국 틱톡샵 뷰티 시장 일별(fastmoss_x.js 덤프 · 2026-11-27) — data/phase 밖(국면 브리핑을 안 깨운다)


def _fmx_read():
    """fmx 덤프 전부 — 시장 일별은 나중 덤프가 이긴다 · 샵 스냅샷은 덤프 날짜별로 둔다."""
    mk, avg, snaps = {}, {}, {}
    for path in sorted(FMX.glob("20??-??-??*.txt")):
        fh = None
        for l in path.read_text(encoding="utf-8").splitlines():
            f = l.split("|")
            if f[0] == "XH":
                fh = f[2]
            elif f[0] == "M":
                try:
                    avg[f[1]] = float(f[2]) if f[2] not in ("", "null", "None") else None
                except ValueError:
                    avg[f[1]] = None
                for it in f[3].split(","):
                    q = it.split(":")
                    if len(q) >= 7 and q[0]:
                        vals = [int(float(x)) if x not in ("", "null") else 0 for x in q[1:7]]
                        if sum(vals) > 0:   # 진행 중인 주의 아직 안 온 날(값이 전부 0)은 버린다
                            mk[q[0]] = vals + [f[1]]
            elif f[0] == "X" and fh:
                try:
                    snaps.setdefault(fh, {})[f[1]] = json.loads(f[3])
                except ValueError:
                    pass
            elif f[0] == "N":
                # v2(압축) 시장 줄 — N|ISO주|평균가×100(36진수)|MMDD:판매량:판매상품:신규상품:크리에이터:영상:라이브(36진수),…
                y, w = (int(x) for x in f[1].split("-"))
                mon = dt.date.fromisocalendar(y, w, 1)
                avg[f[1]] = int(f[2], 36) / 100 if f[2] else None
                for it in f[3].split(","):
                    q = it.split(":")
                    if len(q) < 7:
                        continue
                    mm, dd = int(q[0][:2]), int(q[0][2:])
                    d_ = min((dt.date(yy, mm, dd) for yy in (mon.year - 1, mon.year, mon.year + 1)), key=lambda t: abs((t - mon).days))
                    vals = [_b36s(x) for x in q[1:7]]
                    if sum(vals) > 0:
                        mk[d_.isoformat()] = vals + [f[1]]
            elif f[0] == "Y" and fh:
                # v2(압축) 샵 줄 — 숫자 27개(36진수) · 크리에이터 상위 3 · 상품 상위 3
                n = [_b36s(x) for x in f[3].split(",")]
                if len(n) < 27:
                    continue
                ta = [[t[0], _b36s(t[1]), _b36s(t[2]), _b36s(t[3])] for t in (x.split("~") for x in f[4].split(";") if x) if len(t) >= 4]
                tg = [[t[0], t[1], t[2], f"20{t[3][:2]}-{t[3][2:4]}-{t[3][4:6]}" if len(t[3]) == 6 else "", _b36s(t[4]), _b36s(t[5]), _b36s(t[6]), _b36s(t[7]), t[8]]
                      for t in (x.split("~") for x in f[5].split(";") if x) if len(t) >= 9]
                snaps.setdefault(fh, {})[f[1]] = {
                    "k": f[2], "b": {"pc": n[0]},
                    "ch": {"u": {"product_card": n[1], "shop_account": n[2], "affiliate": n[3]}, "v": {"product_card": n[4], "shop_account": n[5], "affiliate": n[6]}},
                    "ct": {"u": {"video": n[7], "live": n[8], "card": n[9]}, "v": {"video": n[10], "live": n[11], "card": n[12]}},
                    "au": {"n": n[13], "nv": n[14], "nl": n[15], "nn": n[16], "u": n[17], "v": n[18]},
                    "va": {"all": n[19], "ad": n[20]}, "vs": {"u": n[21], "v": n[22], "p": n[23]},
                    "ls": {"total_count": n[24], "sold_count": n[25], "sale_amount": n[26]},
                    "ta": {"l": ta}, "tg": {"l": tg}}
    return mk, avg, snaps


def _b36s(x):
    x = (x or "").strip()
    if not x:
        return 0
    return -int(x[1:], 36) if x.startswith("-") else int(x, 36)


def build_fmx(tt):
    """틱톡샵 블록에 ① 미국 틱톡샵 뷰티 시장(주별 · 월별) ② 브랜드별 판매 구조 스냅샷(최근 28일)을 붙인다(2026-11-27)."""
    if not FMX.exists():
        return
    mk, avg, snaps = _fmx_read()
    weeks = tt.get("weeks") or []
    if mk and weeks:
        # ① 시장 — FastMoss '시장 개요' 뷰티 & 퍼스널 케어(미국 · 카테고리 id 14) 일별 판매량 · 그 ISO 주 평균 거래가 × 판매량 = 판매액 추정
        #    바구니 주 칸(끝날 기준 7일)에 맞춰 더한다 — 하루라도 빠진 주는 None
        dv = {}
        wk = sorted(avg)
        for d_, r in mk.items():
            a = avg.get(r[6])
            if not a:   # 진행 중인 주는 평균 거래가가 없다 — 바로 앞 주 값
                prev = [avg[w] for w in wk if w < r[6] and avg.get(w)]
                a = prev[-1] if prev else None
            dv[d_] = r[0] * a if a else None
        wu, wv, wa = [], [], []
        for w in weeks:
            e = dt.date.fromisoformat(w)
            ds = [(e - dt.timedelta(days=q)).isoformat() for q in range(7)]
            ok = all(x in mk for x in ds)
            wu.append(sum(mk[x][0] for x in ds) if ok else None)
            vv = [dv.get(x) for x in ds]
            wv.append(round(sum(vv)) if ok and all(v is not None for v in vv) else None)
            wa.append(sum(mk[x][3] for x in ds) if ok else None)   # 크리에이터 수(그날 커머스 크리에이터 · 7일 합)
        # 월별(전년비용 · 2025-01~) — 그 달을 다 받은 달만 · 끝 달이 안 찼으면 진행 중
        days = sorted(mk)
        m0 = dt.date.fromisoformat(days[0][:7] + "-01")
        last = dt.date.fromisoformat(days[-1])
        months, mu, mv, mn = [], [], [], []
        m = m0
        while m <= last:
            nxt = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
            ds = [(m + dt.timedelta(days=q)).isoformat() for q in range((nxt - m).days)]
            have = [x for x in ds if x in mk]
            months.append(m.isoformat()[:7])
            mu.append(sum(mk[x][0] for x in have) if have else None)
            vv = [dv.get(x) for x in have]
            mv.append(round(sum(v for v in vv if v is not None)) if have and all(v is not None for v in vv) else None)
            mn.append(len(have))
            m = nxt
        full = [n == ((dt.date(int(ym[:4]) + (ym[5:] == "12"), int(ym[5:]) % 12 + 1, 1) - dt.date.fromisoformat(ym + "-01")).days) for ym, n in zip(months, mn)]
        tt["mk"] = {"u": wu, "v": wv, "au": wa, "m": {"months": months, "u": mu, "v": mv, "n": mn, "full": full},
                    "d0": days[0], "d1": days[-1], "last": mk[days[-1]][:6],
                    "src": "FastMoss 시장 개요 · 미국 틱톡샵 뷰티 & 퍼스널 케어(카테고리 전체) · 일별 판매량 · 판매액 = 판매량 × 그 주 평균 거래가"}
    if snaps:
        # ② 브랜드 스냅샷 — 가장 최근 덤프 · 같은 브랜드 샵(메디큐브 둘 · JM솔루션 다섯 …)은 더한다
        sd = max(snaps)
        X = snaps[sd]
        out = {}
        for sid, r in X.items():
            k = r.get("k")
            if k not in tt["b"]:
                continue
            o = out.setdefault(k, {"n": 0, "ch": [0, 0, 0], "chv": [0, 0, 0], "ct": [0, 0, 0], "ctv": [0, 0, 0], "au": [0, 0, 0, 0, 0, 0],
                                   "fr": {}, "ta": [], "tg": [], "pc": 0, "va": [0, 0], "vs": [0, 0, 0], "ls": [0, 0, 0]})
            o["n"] += 1
            ch, ct = r.get("ch") or {}, r.get("ct") or {}
            for i, kk in enumerate(("product_card", "shop_account", "affiliate")):
                o["ch"][i] += (ch.get("u") or {}).get(kk) or 0
                o["chv"][i] += (ch.get("v") or {}).get(kk) or 0
            for i, kk in enumerate(("video", "live", "card")):
                o["ct"][i] += (ct.get("u") or {}).get(kk) or 0
                o["ctv"][i] += (ct.get("v") or {}).get(kk) or 0
            au = r.get("au") or {}
            for i, kk in enumerate(("n", "nv", "nl", "nn", "u", "v")):
                o["au"][i] += au.get(kk) or 0
            for kk, v in (r.get("fr") or {}).items():
                o["fr"][kk] = o["fr"].get(kk, 0) + (v or 0)
            o["ta"] += [x for x in ((r.get("ta") or {}).get("l") or [])]
            o["tg"] += [x for x in ((r.get("tg") or {}).get("l") or [])]
            o["pc"] += (r.get("b") or {}).get("pc") or 0
            va = r.get("va") or {}
            o["va"][0] += va.get("all") or 0
            o["va"][1] += va.get("ad") or 0
            vs = r.get("vs") or {}
            for i, kk in enumerate(("u", "v", "p")):
                o["vs"][i] += vs.get(kk) or 0
            ls = r.get("ls") or {}
            for i, kk in enumerate(("total_count", "sold_count", "sale_amount")):
                o["ls"][i] += ls.get(kk) or 0
        for k, o in out.items():
            # 크리에이터 상위 5 — 샵마다 상위 5를 모아 판매량 순 · 같은 크리에이터는 더한다 · 자체 계정(브랜드 공식 계정)은 표시만
            ta = {}
            for x in o["ta"]:
                t = ta.setdefault(x[0], [x[0], x[1] or 0, 0, 0])
                t[2] += x[2] or 0
                t[3] += x[3] or 0
            o["ta"] = sorted(ta.values(), key=lambda t: -t[2])[:5]
            o["tg"] = sorted(o["tg"], key=lambda t: -(t[4] or 0))[:5]
            o["chv"] = [round(v) for v in o["chv"]]
            o["ctv"] = [round(v) for v in o["ctv"]]
            o["au"] = [round(v) for v in o["au"]]
            o["vs"] = [round(v) for v in o["vs"]]
            o["ls"] = [round(v) for v in o["ls"]]
            o["ta"] = [[t[0], round(t[1]), round(t[2]), round(t[3])] for t in o["ta"]]
            o["tg"] = [[t[1], t[2], t[3], round(t[4] or 0), round(t[5] or 0), round(t[6] or 0), round(t[7] or 0), t[8], t[0]] for t in o["tg"]]
        hist = {}
        for d_ in sorted(snaps):   # 덤프가 쌓이면 주요 지표 이력(스냅샷 날짜마다 · 브랜드별 [28일 판매량, 인플루언서 %, 영상 %, 라이브 %, 광고 영상 %, 크리에이터, 새 크리에이터])
            agg = {}
            for sid, r in snaps[d_].items():
                k = r.get("k")
                if k not in tt["b"]:
                    continue
                a = agg.setdefault(k, [0, 0, 0, 0, 0, 0, 0, 0])
                ch, ct, au, va = r.get("ch") or {}, r.get("ct") or {}, r.get("au") or {}, r.get("va") or {}
                a[0] += sum(v or 0 for v in (ch.get("u") or {}).values())
                a[1] += (ch.get("u") or {}).get("affiliate") or 0
                a[2] += (ct.get("u") or {}).get("video") or 0
                a[3] += (ct.get("u") or {}).get("live") or 0
                a[4] += va.get("ad") or 0
                a[5] += va.get("all") or 0
                a[6] += au.get("n") or 0
                a[7] += au.get("nn") or 0
            for k, a in agg.items():
                hist.setdefault(k, []).append([d_, a[0], round(a[1] / a[0] * 1000) if a[0] else None, round(a[2] / a[0] * 1000) if a[0] else None,
                                               round(a[3] / a[0] * 1000) if a[0] else None, round(a[4] / a[5] * 1000) if a[5] else None, a[6], a[7]])
        tt["x"] = {"d": sd, "b": out, "h": hist if len(snaps) > 1 else {},
                   "src": f"FastMoss 샵 상세 '판매·인플루언서·상품·영상·라이브 분석' · 최근 28일(광고 영상은 최근 180일 게시 영상 수) · {sd} 수집"}


def inject(block):
    html = INDEX.read_text(encoding="utf-8")
    line = "const KBPH = " + json.dumps(block, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"^const KBPH = .*$", re.M)
    if pat.search(html):
        new = pat.sub(lambda _m: line, html, count=1)
    else:
        mk = re.search(r"^const KBCH = .*$", html, re.M) or re.search(r"^const AMZL = .*$", html, re.M)
        if mk:
            new = html[:mk.end()] + "\n" + line + html[mk.end():]
        else:
            at = html.index("const LIVE = ")
            new = html[:at] + line + "\n" + html[at:]
    if new == html:
        return False, len(line)
    INDEX.write_text(new, encoding="utf-8", newline="\n")
    return True, len(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--shops", action="store_true", help="주간 FastMoss 회차에 돌 샵 목록(마지막 덤프의 S 줄) — grab 호출로 찍는다")
    a = ap.parse_args()
    if a.shops:
        fm = sorted((SRC / "fm").glob("20??-??-??.txt"))
        seen = {}
        for path in fm:   # 덤프 전부 — 한 샵만 따로 받은 날(10/22 ZEROID)이 마지막 파일이어도 목록이 줄지 않게
            for l in path.read_text(encoding="utf-8").splitlines():
                f = l.split("|")
                if f[0] == "S" and f[2] == "US" and TT_MAP.get(f[3]):
                    seen[f[1]] = (f[3], f[5])
        # 회사 채널 모델(KBCH)이 이미 아는 미국 공식 샵 중 TT_MAP 에 있고 국면 덤프엔 아직 없는 것(2026-11-03 LG생활건강 — 다음 회차부터 같이 받는다)
        shp = HERE / "data" / "fm_shops.csv"
        if shp.exists():
            import csv
            for r in csv.DictReader(shp.open(encoding="utf-8")):
                if r.get("r") == "US" and r.get("k") in ("tfs", "drgroot", "hince", "aromatica", "aprilskin", "illiyoon", "mise") and r["s"] not in seen:   # LG 셋 + 2026-11-26 추가 넷만 — 다른 브랜드의 둘째 샵(메디큐브 USA 등)은 국면에 안 넣는다
                    seen[r["s"]] = (r["k"], r.get("name", ""))
        for sid, (k, nm) in seen.items():
            print(f"{sid}\tawait window.__FMX.grab('{sid}','US','{k}')\t# {nm}")
        print(f"# {len(seen)}곳 · 새 샵은 TT_MAP 에도 넣을 것")
        return
    p = latest()
    block = build(p)
    if a.dry:
        eu = ", ".join(f"{m} {len(c['b'])}" for m, c in (block.get("mk") or {}).items())
        print(f"[KBPH] {p.name} · 브랜드 {len(block['b'])} · 유럽 {eu} · {len(json.dumps(block, ensure_ascii=False)) // 1024}KB")
        return
    ch, size = inject(block)
    print(f"[KBPH] {'갱신' if ch else '변동 없음'} · {size // 1024}KB · {block['asOf']} · 브랜드 {len(block['b'])}")


if __name__ == "__main__":
    main()
