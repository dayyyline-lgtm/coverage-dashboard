# -*- coding: utf-8 -*-
"""틱톡샵 미국 공식 샵 일별 판매량·판매액 = Kalodata 하나로 (2026-11-26 · 사용자 "단가 기준이랑 판매량이랑 데이터를 하나로 통일").

왜
  EchoTik 판매액은 표시 가격(할인 전)으로 계산되고, 품절 옵션에 걸어 둔 $3.9K·$9.88K 짜리 가짜 옵션까지 섞여 개당 판매액이 $100 넘게 나온다
  (메디큐브 30일 $120/개 · 실제 $25). 그래서 지금까지는 'EchoTik 판매량 × FastMoss 마지막 4주 단가(고정)'로 이어 붙였다 — 두 출처를 섞은 숫자라
  할인(블프 $30 → $20)도, 비싼 상품 비중 변화도 안 잡혔다. Kalodata 는 판매액 ÷ 판매량이 실제 판매가 수준이고(메디큐브 $25.11 · 바이오던스 $23.65)
  블프 할인도 일별로 잡힌다(메디큐브 11/12 $26 → 11/20 $16.6) → 판매량·판매액·단가를 한 출처에서 받는다.

어디서
  Kalodata 오픈 API(https://www.kalodata.com/open-center · 키 = 환경변수 KALODATA_API_KEY · GitHub Secrets).
  · 스토어 순위(shop/rank) — 뷰티(카테고리 601450) 매출순 100개씩 · 호출당 0.1크레딧 · 10초에 10번.
    11/24 실측: 우리 샵 49곳 중 30곳이 상위 500 안(5쪽 = 0.5크레딧).
  · 스토어 상세(shop/detail) — 순위에서 못 찾은 샵만 · 같은 카테고리로(순위 값과 같은 정의 — 11/24 메디큐브 72,308개 · $1,835,661 둘이 같다) · 호출당 0.1.
  하루 약 2.4크레딧(≈ $0.24 · 1크레딧 ≈ $0.1 · 1,000크레딧 $99.9).
  날짜는 Kalodata 일자 그대로다. 그날 값은 다음 날 UTC 오전에 들어온다(11/26 05시 UTC 에 11/25 가 있었고 저녁까지 같은 값) — 비어 있으면(1쪽이 0) 다음 회차가 받는다.

  python3 kbeauty/kalodata.py                      # 빠진 날 → 어제까지(UTC) · 기본 크레딧 30 한도
  python3 kbeauty/kalodata.py --from 2026-04-01 --max-credits 700    # 소급
  python3 kbeauty/kalodata.py --plan               # 빠진 날 수·크레딧 견적만(네트워크 없음)
  python3 kbeauty/kalodata.py --status             # 받은 범위

저장
  data/kalo/daily.csv   date,s,u,v,src       — 샵별 일별 판매량(개) · 판매액($) · src r=순위 d=상세
  data/kalo/market.csv  date,n,u,v           — 그날 뷰티 상위 500 샵 합(시장 크기 참고)
  data/kalo/meta.json   from · to · complete · asOf · bal

읽는 쪽(phase.build_tt · ingest.build_block)은 load() 가 None 이 아닐 때 — **from(KALO_FROM) 부터 to 까지 모든 샵·모든 날이 있을 때** —
틱톡샵 판매량·판매액을 이것 하나로 쓴다(FastMoss·EchoTik 일별은 안 섞는다). 소급이 덜 끝났으면 None → 예전 방식 그대로.
틱톡 소셜(새 홍보 영상·크리에이터 · fm_social.csv)은 Kalodata 에 같은 정의가 없어 EchoTik 그대로다.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DIR = HERE / "data" / "kalo"
DAILY = DIR / "daily.csv"
MARKET = DIR / "market.csv"
META = DIR / "meta.json"
SHOPS = HERE / "data" / "fm_shops.csv"

BASE = "https://www.kalodata.com/openapi/v1"
CAT = "601450"            # Beauty & Personal Care
KALO_FROM = "2026-04-01"  # 소급 시작 — 2Q26 이 통째로 실측(예전엔 4/1~23 을 첫 14일 평균으로 채웠다)
RANK_PAGES = 5            # 뷰티 상위 500 — 11/24 우리 샵 30곳이 여기 · 1,000 까지 늘려도 30곳(500~1,000위에 없다)
RANK_GAP = 1.05           # 순위 API 10초에 10번
DETAIL_GAP = 0.12         # 상세 API 10초에 100번
CR_RANK = CR_DETAIL = 0.1

sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def note(msg):
    try:
        from collector_health import note_health
        note_health("Kalodata 틱톡샵", msg)
    except Exception:
        pass


# ── 읽기(다른 스크립트가 import) ─────────────────────────────────────────────

def shops():
    if not SHOPS.exists():
        return []
    return [r for r in csv.DictReader(SHOPS.open(encoding="utf-8")) if r.get("r") == "US"]


def meta():
    try:
        return json.loads(META.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rows():
    if not DAILY.exists():
        return {}
    out = {}
    for r in csv.DictReader(DAILY.open(encoding="utf-8")):
        out[(r["s"], r["date"])] = r
    return out


def load(require_complete=True):
    """{샵ID: {date: (판매량, 판매액$ 정수)}} · meta — 소급이 끝나지 않았으면(require_complete) None."""
    m = meta()
    if require_complete and not m.get("complete"):
        return None
    day = {}
    for (s, d), r in rows().items():
        if m.get("to") and d > m["to"]:
            continue
        day.setdefault(s, {})[dt.date.fromisoformat(d)] = (int(r["u"]), int(round(float(r["v"]))))
    return {"day": day, "meta": m} if day else None


# ── 받기 ────────────────────────────────────────────────────────────────────

class Api:
    def __init__(self, key, max_credits):
        self.key, self.max, self.spent, self.calls = key, max_credits, 0.0, 0
        self._t = {"rank": 0.0, "detail": 0.0}

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method, headers={
            "secret-key": self.key, "content-type": "application/json;charset=UTF-8", "accept": "application/json",
            "user-agent": "coverage-dashboard/kalodata (+github actions)"})
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8"))

    def balance(self):
        try:
            j = self._req("GET", "/credit/balance")
            return float((j.get("data") or {}).get("totalRemain"))
        except Exception:
            return None

    def post(self, kind, path, body):
        cost = CR_RANK if kind == "rank" else CR_DETAIL
        if self.spent + cost > self.max + 1e-9:
            raise Budget()
        gap = RANK_GAP if kind == "rank" else DETAIL_GAP
        last_err = None
        for k in range(4):
            w = self._t[kind] + gap - time.time()
            if w > 0:
                time.sleep(w)
            self._t[kind] = time.time()
            try:
                j = self._req("POST", path, dict({"region": "US", "language": "en-US", "currency": "USD"}, **body))
                self.calls += 1
                self.spent += cost            # 실패 응답도 깎일 수 있다(11/26 병렬 호출 500 이 크레딧을 먹었다) — 보수적으로 센다
                if j.get("success"):
                    return j.get("data")
                last_err = f"{j.get('code')} {j.get('message')}"
                if str(j.get("code")) in ("401", "403") or "key" in str(j.get("message", "")).lower():
                    raise Fatal(f"인증 실패: {last_err}")
                if "credit" in str(j.get("message", "")).lower() or "insufficient" in str(j.get("message", "")).lower():
                    raise Fatal(f"크레딧 부족: {last_err}")
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                if e.code in (401, 403):
                    raise Fatal(f"인증 실패: HTTP {e.code}")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = f"{type(e).__name__} {e}"
            time.sleep(2 * (k + 1))
        raise RuntimeError(f"{kind} 4번 실패: {last_err}")


class Budget(Exception):
    pass


class Fatal(Exception):
    pass


def fetch_day(api, d, ids):
    """하루 — {샵: (u, v, src)} · 시장 합 · 아직 안 들어온 날이면 None"""
    want = set(ids)
    got, mk = {}, [0, 0, 0]
    for p in range(1, RANK_PAGES + 1):
        data = api.post("rank", "/tiktok/shop/rank", {"date_range": f"{d}~{d}", "category_ids": [CAT], "page_size": 100, "page_number": p,
                                                      "sort_field": {"field": "revenue", "type": "DESC"}}) or []
        if p == 1 and (not data or not float(data[0].get("revenue") or 0)):
            return None                                   # 그날 값이 아직 없다(1위 매출 0)
        for x in data:
            mk[0] += 1
            mk[1] += int(x.get("sales_volumn") or 0)
            mk[2] += float(x.get("revenue") or 0)
            s = str(x.get("shop_id"))
            if s in want:
                got[s] = (int(x.get("sales_volumn") or 0), round(float(x.get("revenue") or 0), 2), "r")
        if len(data) < 100 or want <= set(got):
            break
    for s in sorted(want - set(got)):
        x = api.post("detail", "/tiktok/shop/detail", {"date_range": f"{d}~{d}", "shop_id": s, "category_ids": [CAT]}) or {}
        got[s] = (int(x.get("sales_volumn") or 0), round(float(x.get("revenue") or 0), 2), "d")
    return got, mk


def save(day_rows, mk_rows):
    DIR.mkdir(parents=True, exist_ok=True)
    allr = rows()
    allr.update(day_rows)
    with DAILY.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "s", "u", "v", "src"])
        w.writeheader()
        w.writerows(sorted(allr.values(), key=lambda r: (r["s"], r["date"])))
    mm = {}
    if MARKET.exists():
        mm = {r["date"]: r for r in csv.DictReader(MARKET.open(encoding="utf-8"))}
    mm.update(mk_rows)
    with MARKET.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "n", "u", "v"])
        w.writeheader()
        w.writerows([mm[k] for k in sorted(mm)])


def coverage(ids, frm, upto):
    """frm ~ upto 에서 모든 샵이 다 있는 마지막 날(이어진 구간) · 빠진 날 목록"""
    have = {}
    for (s, d) in rows():
        have.setdefault(d, set()).add(s)
    need = set(ids)
    missing, last_ok, t = [], None, dt.date.fromisoformat(frm)
    end = dt.date.fromisoformat(upto)
    broken = False
    while t <= end:
        ds = t.isoformat()
        if need <= have.get(ds, set()):
            if not broken:
                last_ok = ds
        else:
            missing.append(ds)
            broken = True
        t += dt.timedelta(days=1)
    return last_ok, missing


def write_meta(ids, frm, bal, api):
    yday = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    last_ok, missing = coverage(ids, frm, yday)
    # complete = 소급 시작일부터 이어진 구간이 있다(빠진 날이 어제·그제 같은 끝쪽뿐이어도 그 앞까지는 완결)
    m = meta()
    m.update({"from": frm, "to": last_ok or "", "complete": bool(last_ok), "miss": len(missing), "missFirst": missing[0] if missing else "",
              "shops": len(ids), "asOf": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "cat": CAT, "rankPages": RANK_PAGES})
    if bal is not None:
        m["bal"] = round(bal, 2)
    if api:
        m["lastRun"] = {"calls": api.calls, "credits": round(api.spent, 1)}
    DIR.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default=None, help=f"받을 첫날(기본 {KALO_FROM} 부터 빠진 날)")
    ap.add_argument("--to", default=None, help="받을 끝날(기본 어제 UTC)")
    ap.add_argument("--max-credits", type=float, default=30.0)
    ap.add_argument("--max-min", type=float, default=50.0, help="이 분이 넘으면 받은 데까지 저장하고 끝")
    ap.add_argument("--refetch", type=int, default=0, help="마지막 N일은 있어도 다시 받는다")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    sh = shops()
    ids = [r["s"] for r in sh]
    frm = a.frm or KALO_FROM
    upto = a.to or (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    if a.status:
        m = meta()
        print(json.dumps(m, ensure_ascii=False))
        return 0
    _, missing = coverage(ids, frm, upto)
    if a.refetch:
        tail = [(dt.date.fromisoformat(upto) - dt.timedelta(days=i)).isoformat() for i in range(a.refetch)]
        missing = sorted(set(missing) | set(tail))
    est = len(missing) * (RANK_PAGES * CR_RANK + 19 * CR_DETAIL)
    print(f"[Kalodata] 샵 {len(ids)} · {frm}~{upto} 빠진 날 {len(missing)} · 견적 약 {est:.0f}크레딧(하루 ≈ {RANK_PAGES * CR_RANK + 19 * CR_DETAIL:.1f})")
    if a.plan or not missing:
        if not missing:
            write_meta(ids, KALO_FROM, None, None)
        return 0
    key = os.environ.get("KALODATA_API_KEY", "").strip()
    if not key:
        print("KALODATA_API_KEY 없음 — 건너뜀(GitHub Secrets 에 넣어야 돈다)")
        return 0
    api = Api(key, a.max_credits)
    bal = api.balance()
    print(f"[Kalodata] 남은 크레딧 {bal}")
    if bal is not None and bal < RANK_PAGES * CR_RANK + 19 * CR_DETAIL:
        note(f"크레딧 부족 {bal} — 충전 필요(하루 약 2.4)")
        write_meta(ids, KALO_FROM, bal, api)
        return 1
    if bal is not None:
        api.max = min(api.max, bal - 0.2)
    t0 = time.time()
    day_rows, mk_rows, done, waitd = {}, {}, 0, None
    stop = ""
    try:
        for d in missing:
            if time.time() - t0 > a.max_min * 60:
                stop = f"시간 {a.max_min:.0f}분"
                break
            if api.spent + RANK_PAGES * CR_RANK + len(ids) * 0.5 * CR_DETAIL > api.max:   # 하루를 다 못 받을 것 같으면 시작하지 않는다(반쯤 받은 날은 버려진다)
                stop = f"크레딧 한도 {api.max:.1f}"
                break
            r = fetch_day(api, d, ids)
            if r is None:
                waitd = d
                print(f"  {d} 아직 없음(1위 매출 0) — 다음 회차")
                continue
            got, mk = r
            for s, (u, v, src) in got.items():
                day_rows[(s, d)] = {"date": d, "s": s, "u": u, "v": v, "src": src}
            mk_rows[d] = {"date": d, "n": mk[0], "u": mk[1], "v": round(mk[2])}
            done += 1
            if done % 10 == 0:                       # 중간 저장 — 시간 초과·끊김에도 받은 날은 남게
                save(day_rows, mk_rows)
                day_rows, mk_rows = {}, {}
                print(f"  …{d} 까지 {done}일 · {api.calls}콜 · {api.spent:.1f}크레딧")
    except Budget:
        stop = f"크레딧 한도 {a.max_credits}"
    except Fatal as e:
        stop = str(e)
        note(str(e))
    except Exception as e:
        stop = f"{type(e).__name__}: {e}"
        note(f"수집 중단: {stop}"[:200])
    save(day_rows, mk_rows)
    bal2 = api.balance()
    m = write_meta(ids, KALO_FROM, bal2, api)
    print(f"[Kalodata] 받은 날 {done} · 콜 {api.calls} · 쓴 크레딧 약 {api.spent:.1f} · 남은 {bal2} · 완결 {m['from']}~{m['to']} · 빠진 날 {m['miss']}"
          + (f" · 멈춤: {stop}" if stop else "") + (f" · {waitd} 미공개" if waitd else ""))
    if not stop or stop.startswith("시간") or stop.startswith("크레딧 한도"):
        if not stop:
            note(None)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
