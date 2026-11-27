# -*- coding: utf-8 -*-
"""틱톡샵 미국 밖 나라의 한국 브랜드 공식 샵 찾기 (2026-11-27)

EchoTik '나라별 뷰티 샵 순위'(로컬·크로스보더 · 월간 상위 500)에서 받은 샵 이름을 브랜드 사전에 맞춘다.
입력 = JSON {"kind|나라": {seller_id: [이름, 판매량, 판매액, 나라, 쪽, 카테고리]}} (echotik 화면에서 받은 것)
출력 = 후보 줄 — seller_id · 나라 · FastMoss 키(phase.TT_MAP 의 키) · 이름 · 월 판매량 · clean(브랜드 말고 다른 낱말이 없나)

사전 = 미국 공식 샵 키(phase.TT_MAP) + 아마존 바구니 브랜드 일부(구달·페리페라·설화수·메디필·아토팜·리얼베리어 …).
흔한 낱말 브랜드(VT·헤라·라카·아뮤즈·라곰·리더스·Dr.G …)는 이름이 '브랜드 + 나라/공식/스토어' 꼴일 때만(clean) 받는다 — 사람이 마지막에 본다.
"""
import json
import re
import sys

# FastMoss 키 → 이름 패턴(정규화한 이름 = 소문자 · 영숫자 말고는 빈칸)
PAT = {
    "medicube": [r"\bmedicube\b", "メディキューブ"], "cosrx": [r"\bcosrx\b", "コスアールエックス"], "anua": [r"\banua\b", "アヌア"],
    "skin1004": [r"\bskin ?1004\b", "スキン1004"], "boj": [r"\bbeauty of joseon\b", "朝鮮美女"], "biodance": [r"\bbiodance\b", "バイオダンス"],
    "dalba": [r"\bd ?alba\b", "ダルバ"], "torriden": [r"\btorriden\b", "トリデン"], "numbuzin": [r"\bnumbuzin\b", "ナンバーズイン"],
    "roundlab": [r"\bround ?lab\b", "ラウンドラボ"], "mixsoon": [r"\bmixsoon\b", "ミクスン"], "laneige": [r"\blaneige\b", "ラネージュ"],
    "tirtir": [r"\btirtir\b", "ティルティル"], "axisy": [r"\baxis ?y\b"], "abib": [r"\babib\b", "アビブ"], "somebymi": [r"\bsome ?by ?mi\b", "サムバイミー"],
    "haruharu": [r"\bharuharu\b"], "celimax": [r"\bcelimax\b", "セリマックス"], "isntree": [r"\bisntree\b", "イズントゥリー"],
    "innisfree": [r"\binnisfree\b", "イニスフリー"], "etude": [r"\betude\b", "エチュード"], "missha": [r"\bmissha\b", "ミシャ"],
    "tonymoly": [r"\btony ?moly\b", "トニーモリー"], "holika": [r"\bholika\b"], "klairs": [r"\bklairs\b"], "purito": [r"\bpurito\b"],
    "benton": [r"\bbenton\b"], "neogen": [r"\bneogen\b"], "dralthea": [r"\bdr ?althea\b", "ドクターエルシア"], "drjart": [r"\bdr ?jart\b", "ドクタージャルト"],
    "drg": [r"\bdr ?g\b"], "mediheal": [r"\bmediheal\b", "メディヒール"], "manyo": [r"\bma ?nyo\b", "魔女工場"], "heimish": [r"\bheimish\b"],
    "imfrom": [r"\bi ?m ?from\b"], "rovectin": [r"\brovectin\b"], "jumiso": [r"\bjumiso\b"], "clio": [r"\bclio\b", "クリオ"],
    "romand": [r"\brom ?n ?d\b", r"\bromand\b", "ロムアンド"], "amuse": [r"\bamuse\b", "アミューズ"], "hince": [r"\bhince\b", "ヒンス"],
    "laka": [r"\blaka\b", "ラカ"], "espoir": [r"\bespoir\b", "エスポア"], "hera": [r"\bhera\b", "ヘラ"], "illiyoon": [r"\billiyoon\b"],
    "aprilskin": [r"\bapril ?skin\b"], "aromatica": [r"\baromatica\b"], "centellian": [r"\bcentellian", "センテリアン"],
    "vt": [r"\bvt\b", "ブイティー"], "equalberry": [r"\be ?qq?ualberry\b"], "zeroid": [r"\bzeroid\b"], "rejuran": [r"\brejuran\b", "リジュラン"],
    "jmsolution": [r"\bjm ?solution\b"], "mizon": [r"\bmizon\b"], "skinfood": [r"\bskin ?food\b", "スキンフード"],
    "naturerepublic": [r"\bnature ?republic\b"], "tfs": [r"\bthe ?face ?shop\b"], "banilaco": [r"\bbanila ?co\b", "バニラコ"], "tocobo": [r"\btocobo\b"],
    "kahi": [r"\bkahi\b"], "biohealboh": [r"\bbio ?heal ?boh\b"], "sungboon": [r"\bsung ?boon\b"], "arencia": [r"\barencia\b"],
    "colorgram": [r"\bcolorgram\b"], "oganacell": [r"\boganacell\b"], "ongredients": [r"\bongredients\b"], "beplain": [r"\bbeplain\b"],
    "melaxin": [r"\bmelaxin\b"], "ohora": [r"\bohora\b"], "meditherapy": [r"\bmeditherapy\b"], "aplb": [r"\baplb\b"], "2an": [r"\b2an\b"],
    "age20s": [r"\bage ?20 ?s\b"], "beaund": [r"\bbeaund\b"], "bonajour": [r"\bbonajour\b"], "cellfusionc": [r"\bcell ?fusion ?c\b"],
    "cosnori": [r"\bcosnori\b"], "dashu": [r"\bdashu\b"], "deardahlia": [r"\bdear ?dahlia\b"], "demaf": [r"\bdemaf\b"], "dermafirm": [r"\bdermafirm\b"],
    "drceuracle": [r"\bceuracle\b"], "drdifferent": [r"\bdr ?different\b"], "drforhair": [r"\bdr ?for ?hair\b"], "drgroot": [r"\bdr ?groot\b"],
    "drpepti": [r"\bdr ?pepti\b"], "drrejuall": [r"\breju ?all\b"], "easydew": [r"\beasydew\b"], "elroel": [r"\belroel\b"], "frudia": [r"\bfrudia\b"],
    "growus": [r"\bgrowus\b"], "hanskin": [r"\bhanskin\b"], "hetras": [r"\bhetras\b"], "ilso": [r"\bilso\b"], "iunik": [r"\biunik\b"],
    "jayjun": [r"\bjayjun\b"], "jsm": [r"\bjungsaemmool\b"], "klavuu": [r"\bklavuu\b"], "kocostar": [r"\bkocostar\b"], "koelf": [r"\bkoelf\b"],
    "kundal": [r"\bkundal\b"], "lactomedi": [r"\blactomedi\b"], "lagom": [r"\blagom\b"], "leaders": [r"\bleaders cosmetics\b"],
    "makeprem": [r"\bmake ?p ?rem\b"], "marymay": [r"\bmary ?may\b"], "mise": [r"\bmise ?en ?scene\b"], "needly": [r"\bneedly\b"],
    "nooni": [r"\bnooni\b"], "obge": [r"\bobge\b"], "paparecipe": [r"\bpapa ?recipe\b"], "purcell": [r"\bpurcell\b"], "pyunkangyul": [r"\bpyunkang ?yul\b"],
    "siot": [r"\bsiot\b"], "terezhonor": [r"\bterez ?honor\b"], "tfit": [r"\btfit\b"], "thome": [r"\bthome\b"], "touchinsol": [r"\btouch ?in ?sol\b"],
    "tsshampoo": [r"\bts ?shampoo\b"], "unove": [r"\bunove\b"], "wellage": [r"\bwellage\b"], "wishtrend": [r"\bwishtrend\b"], "wonjin": [r"\bwonjin\b"],
    "barber501": [r"\bbarber ?501\b"], "belif": [r"\bbelif\b"], "tcfs": [r"\btoo ?cool ?for ?school\b"], "zeroid2": [],
    # 아마존 바구니에만 있던 브랜드(미국 틱톡샵 공식 샵은 없음) — 키 = 바구니 키
    "goodal": [r"\bgoodal\b", "グーダル"], "peripera": [r"\bperipera\b", "ペリペラ"], "sulwhasoo": [r"\bsulwhasoo\b", "雪花秀"],
    "medi-peel": [r"\bmedi ?peel\b", "メディピール"], "atopalm": [r"\batopalm\b"], "real barrier": [r"\breal ?barrier\b"],
    "iope": [r"\biope\b"], "primera": [r"\bprimera\b"], "a'pieu": [r"\ba ?pieu\b"], "cnp": [r"\bcnp\b"], "su:m37": [r"\bsu ?m ?37\b"],
    "whoo": [r"\bwhoo\b"], "o hui": [r"\bo ?hui\b"], "vdl": [r"\bvdl\b"], "aestura": [r"\baestura\b"], "ryo": [r"\bryo hair\b"],
    "hotomi": [r"\bhotomi\b"],
}
# 이름에서 지울 낱말(나라·공식·스토어) — 이걸 지우고 브랜드 말고 남는 게 없으면 clean
GEN = set("""official store shop shops mall global flagship uk gb us de deutschland germany france fr italia italy it espana spain es eu europe
japan jp indonesia id malaysia my philippines ph thailand th vietnam vn viet nam singapore sg mexico mx brasil brazil br ireland ie netherlands nl
belgium be austria at poland pl portugal pt czech cz hungary hu greece gr korea korean seoul kbeauty k beauty cosmetics cosmetic skincare skin care
beauty co inc ltd llc limited the by official1 offical officials store1 lab labs and plus kr global1 international intl house factory brand
hair makeup make up""".split())
JP_GEN = ("公式", "ショップ", "ストア", "オフィシャル", "店", "日本", "ジャパン")


def norm(s):
    s = (s or "").lower().replace("’", "'").replace("&", " ")
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]+", " ", s).strip()


def match(name):
    n = norm(name)
    hits = []
    for k, pats in PAT.items():
        for p in pats:
            if (p.startswith("\\b") and re.search(p, n)) or (not p.startswith("\\b") and p in (name or "")):
                hits.append((k, p))
                break
    return n, hits


def cleanness(n, k, p, name):
    rest = re.sub(p, " ", n) if p.startswith("\\b") else n
    if not p.startswith("\\b"):
        rest = name or ""
        rest = rest.replace(p, " ")
        for g in JP_GEN:
            rest = rest.replace(g, " ")
        rest = norm(rest)
    left = [w for w in rest.split() if w not in GEN and not re.fullmatch(r"\d{1,3}", w)]
    return left


def num(s):
    s = str(s or "").replace(",", "").replace("$", "").strip()
    m = re.match(r"([\d.]+)\s*([KMB]?)", s)
    if not m:
        return 0
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]


def main(path):
    rows = json.load(open(path, encoding="utf-8"))
    out = []
    for key, R in rows.items():
        kind, rg = key.split("|")
        for sid, r in R.items():
            name = r[0]
            n, hits = match(name)
            if not hits:
                continue
            k, p = hits[0]
            left = cleanness(n, k, p, name)
            out.append({"s": sid, "r": rg, "kind": kind[:5], "k": k, "name": name, "u": num(r[1]), "gmv": num(r[2]),
                        "clean": not left, "left": " ".join(left)[:30], "multi": len(hits) > 1})
    out.sort(key=lambda x: (x["r"], -x["u"]))
    json.dump(out, open(path.replace(".json", "_cand.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for x in out:
        print(f"{x['r']} {x['kind']} {x['k']:<12} {'OK ' if x['clean'] else '?? '}{x['u']:>9.0f} {x['gmv']:>11.0f}  {x['s']}  {x['name'][:40]}  [{x['left']}]")


if __name__ == "__main__":
    main(sys.argv[1])
