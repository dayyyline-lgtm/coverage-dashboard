/* KAYAK 호텔 월별 평균 요금 수집기 (2026-10-29 · hotel_adr/RUNBOOK.md '2. KAYAK')
   kayak.com 탭(https://www.kayak.com/robots.txt 권장 — 가볍고 CSP 가 없다)에서:
     const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/hotel_adr/';
     new Function(await (await fetch(R+'kayak.js',{cache:'no-store'})).text())();
     await window.__KAYAKADR.start(); window.__KAYAKADR.status()
   → 'done · 26/26 · ok 26 · err 0' 이면 window.__KAYAKADR.dump() → get_page_text → build.py --kayak

   무엇을 읽나: 호텔 페이지에 박힌 JSON 의 monthlyStayPrice(1~12월) · weeklyStayPrice(월~일).
   'KAYAK 사용자들이 지난 12개월 동안 검색한 요금' 의 평균이다(전 객실 타입·세금 포함) — 수준은 ADR 보다 높고 변화만 쓴다.
   kayak.com 은 달러로 준다. 같은 자료를 kayak.co.kr 은 '오늘 환율' 하나로 곱해 원화로 보여 준다(2026-10-29 확인: 모든 달이 1,339.2배)
   → 저장된 달러를 그달 원/달러로 바꾸는 일은 build.py 가 한다(환율 보정 · 리츠 실측 3곳으로 검증).
   한 줄 = K|수집일(KST)|호텔키|KAYAK id|통화|월 12개(;)|요일 7개(;)|CRC32(36진수, 앞 부분 전체) · 끝 = END|수집일|줄 수 */
(() => {
  const H = [
    ["gic", 82365], ["westin", 1072878518], ["pjeju", 1070436092],
    ["nt_md1", 496105], ["nt_md2", 2731798], ["nt_ins", 5554595], ["nt_ddm", 6019223], ["nt_pg", 7536808], ["nt_ys", 1070670581],
    ["shilla_seoul", 76540], ["shilla_jeju", 86274],
    ["stay_ghm", 2450802], ["stay_mapo", 2330447], ["stay_yeoksam", 2154992], ["stay_seocho", 2757891], ["stay_samsung", 6080159],
    ["stay_sdm", 806452], ["stay_guro", 2450800], ["stay_dongtan", 728662], ["stay_hud", 2757890], ["stay_jeju", 2259231], ["stay_iho", 10357751],
    ["gm_ys", 2992812], ["ns_ys", 2992813], ["nv_ys", 2991340], ["is_ys", 2991349],
  ];
  const S = window.__KAYAKADR = { st: "idle", i: 0, n: H.length, rows: [], err: [] };
  const T = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t.push(c >>> 0); } return t; })();
  const crc = s => { const b = new TextEncoder().encode(s); let c = 0xFFFFFFFF; for (const x of b) c = T[(c ^ x) & 255] ^ (c >>> 8); return ((c ^ 0xFFFFFFFF) >>> 0).toString(36); };
  const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const nap = ms => new Promise(r => setTimeout(r, ms * (0.8 + Math.random() * 0.4)));
  const num = s => s.split(",").map(x => +(+x).toFixed(2));
  async function one(key, id) {
    const r = await fetch(`/Seoul-Hotels-x.${id}.ksp`, { credentials: "include" });
    const h = await r.text();
    if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
    const m = h.match(/"monthlyStayPrice":\{"values":\[([^\]]*)\]/), w = h.match(/"weeklyStayPrice":\{"values":\[([^\]]*)\]/);
    const cur = (h.match(/"priceCurrency":"([A-Z]{3})"/) || [])[1] || "";
    if (!m) throw new Error(/captcha|robot|denied/i.test(h.slice(0, 5000)) ? "막힘(captcha)" : "monthlyStayPrice 없음");
    const mv = num(m[1]);
    if (mv.length !== 12) throw new Error(`월 ${mv.length}개`);
    return { mv, wv: w ? num(w[1]) : [], cur };
  }
  S.start = async (opt = {}) => {
    const only = opt.only ? new Set(opt.only) : null, d = today();
    S.st = "run"; S.i = 0; S.rows = []; S.err = []; S.d = d;
    const list = H.filter(([k]) => !only || only.has(k)); S.n = list.length;
    for (const [k, id] of list) {
      try {
        const x = await one(k, id);
        const body = `K|${d}|${k}|${id}|${x.cur}|${x.mv.join(";")}|${x.wv.join(";")}`;
        S.rows.push(body + "|" + crc(body));
      } catch (e) { S.err.push(`${k}:${e.message}`); }
      S.i++;
      await nap(1500);
    }
    S.st = "done";
    return S.status();
  };
  S.status = () => `${S.st} · ${S.i}/${S.n} · ok ${S.rows.length} · err ${S.err.length}${S.err.length ? " (" + S.err.join(", ") + ")" : ""}`;
  S.dump = () => {
    const pre = document.createElement("pre");
    pre.id = "kayakDump";
    pre.textContent = S.rows.concat([`END|${S.d}|${S.rows.length}`]).join("\n");
    document.body.replaceChildren(pre);
    return S.rows.length;
  };
})();
