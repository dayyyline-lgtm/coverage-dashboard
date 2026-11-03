/* kbeauty/keepa_week.js — Keepa 주간 통합 수집 (2026-11-01 · 사용자 "깔끔하게 정리해봐 — 한도 아끼게")
   전엔 같은 Keepa 상품을 두 번 불렀다: 국면 지도(KBPH · 나라마다 Finder 1~2번)와 회사 채널 모델(KBCH · 브랜드×나라 과제마다 Finder 1번 · 230번).
   KBCH 는 '안 팔리는 상품'까지 다 받아(10/20 회차 상품 2.1만 개 · 미국 크림샵 1,326 · 미샤 1,212) 한도를 가장 많이 먹었다.
   이제 나라마다 Finder 를 두 번만 부르고(아래 A·B) 받은 상품 객체 하나로 두 계산을 다 한다 — 계산식은 그대로(keepa.js · phase_keepa.js · phase_keepa_eu.js).
     A = 브랜드 전부 · 역대 월판매 피크 ≥ 50(배지가 한 번이라도 붙은 상품) — 옛 국면 질의와 같다
     B = 브랜드 전부 · 지금 판매 순위 30만 위 안(배지 없는 세트·번들과 꼬리 상품) — 옛 국면 runNB(15만 위)보다 넓다(KBCH 꼬리용)
     빠지는 것 = 배지가 한 번도 없고 지금 순위가 30만 위 밖인 상품(사실상 안 팔리는 상품). KBCH 의 과거 달에 그 상품들이 순위 곡선으로 조금 들어가던 몫이 빠진다
       → 첫 회차에 옛 회차(10/20)와 같은 달끼리 견줘 차이를 잰다(kbeauty/week_recv.py --compare).
   쓰는 법 (keepa.com 탭 · Pro 웹 로그인 · CSP 가 외부 fetch 를 막아 붙여 넣는다):
     1) keepa.js · phase_keepa.js · phase_keepa_eu.js · 이 파일을 차례로 붙여 넣는다(주석을 지워도 된다)
     2) __KW.start(<keepa_tasks.json 내용>) → __KW.status() 를 'done' 까지(45초 넘는 호출은 끊기니 시작과 확인을 나눈다)
     3) __KW.build('full'|'recent') → KBCH(__KBK.L) · 국면 미국(KBPH dump) · 유럽·일본·캐나다(KBPHEU.save) 를 한 번에 짓는다
     4) __KW.bundle() → 길이·검산값 · __KW.show(i) 로 나눠 띄워 get_page_text(줄바꿈은 '~') → 파일 → python3 kbeauty/week_recv.py <파일>
        (이 PC 받기 서버가 있으면 __send('kw_'+날짜, __KW.text) 로 한 번에)
   v2 (2026-11-03 · 사용자 "Keepa 사용량 관리 · 최적화"):
     - 한도 예산: __KW.start(tasks, {quota: <새 탭에서 본 남은 %>}) → 예산 = % × 260 상품(꽉 차면 약 2.6만 · 11/02 실측). 나라마다 예상 상품 수(EXP · 지난 회차 실측으로 덮어씀 opt.exp)를
       남은 예산과 견줘 모자라면 그 나라는 건너뛴다(중간에 끊겨 반쪽이 되느니 통째로 다음 회차로). 예산은 A·B 행을 따로 센다(겹친 상품도 두 번 · 보수적).
     - 끊김 감지: 질의가 0개거나 페이지가 덜 차면 그 나라를 '불완전'(W.bad)으로 두고 build 에서 뺀다(지난 회차 값이 남는다). 두 질의 연속 0개면 한도 소진으로 보고 멈춘다.
     - 나라 순서 = 중요도(미국 → 영국 → 독일 → 일본 → 프랑스 → 스페인 → 이탈리아 → 캐나다) — 한도가 모자라면 뒤에서부터 빠진다.
     - bundle 에 @@USE@@ 한 줄(나라별 A·B·합·초·불완전 · 시작 %) → week_recv.py 가 data/keepa_usage.csv 에 쌓는다 — 다음 회차 EXP 의 근거.
*/
(function () {
  'use strict';
  const W = window.__KW = {v: 2, state: 'idle', log: [], rows: {}, err: '', parts: {}};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const DOMS = [1, 2, 3, 5, 4, 9, 8, 6], MK = {1: 'us', 2: 'uk', 3: 'de', 4: 'fr', 8: 'it', 9: 'es', 5: 'jp', 6: 'ca'};
  const NAMES = {1: 'United States', 2: 'United Kingdom', 3: 'Germany', 4: 'France', 5: 'Japan', 6: 'Canada', 8: 'Italy', 9: 'Spain'};
  const RANK_B = 300000, RANK_NB = 150000;
  // 나라별 예상 행 수(A 행 + B 행) — 첫 통합 회차 전이라 옛 회사 채널 회차(10/20 · 브랜드×나라 전 상품) 크기로 넉넉히. 회차가 쌓이면 opt.exp 로 실측을 넘긴다.
  const EXP = {1: 7700, 2: 2600, 3: 2100, 5: 2600, 4: 1700, 9: 1500, 8: 1600, 6: 1700}, PER_PCT = 260;
  // 국면 브랜드 목록 — 미국 = phase_keepa.js 의 BRANDS · 유럽·캐나다 = + d'alba · centellian24 · 일본 = 가타카나 표기 포함(RUNBOOK 1-d)
  const US = (window.BRANDS || []).slice();
  const EU = US.concat(["d'alba", 'centellian24']);
  const JP = ['アトパーム(atopalm)', 'センテリアン24', 'クリオ(clio)', 'コースアールエックス(cosrx)', 'イニスフリー(innisfree)', 'ラネージュ(laneige)', 'ミシャ(missha)', '雪花秀 ソルファス(sulwhasoo)',
    'abib', 'anua', 'axis-y', 'beauty of joseon', 'biodance', 'celimax', 'centellian 24', 'clio', 'clio professional', "d'alba piedmont", "d'alba", 'dr.althea', 'goodal', 'haruharu',
    'innisfree', 'isntree', 'laneige', 'ma:nyo', 'medi-peel', 'medicube', 'mixsoon', 'numbuzin', 'peripera', 'real barrier', 'rejuran', 'rom&nd', 'round lab', 'skin1004', 'some by mi',
    'sulwhasoo', 'tonymoly', 'torriden', 'vt cosmetics', 'zeroid', 'belif'].concat(window.LG_BRANDS || []);   // + LG생활건강(2026-11-03 · phase_keepa.js LG_BRANDS)
  const phList = d => d === 1 ? US : d === 5 ? JP : EU;
  const low = a => new Set(a.map(x => String(x).toLowerCase()));

  const grid = () => { const c = document.querySelector('.ag-root-wrapper'); return (c && c.__agComponent && c.__agComponent.gridApi) || null; };
  const domain = () => { const b = document.querySelector('button.knav-mk[aria-current="true"]'); return b && b.getAttribute('data-domain') ? +b.getAttribute('data-domain') : 0; };
  const setDomain = async d => {
    if (domain() === d) return true;
    const b = document.querySelector('button.knav-mk[data-domain="' + d + '"]') || [...document.querySelectorAll('button.knav-mk')].find(x => x.textContent.includes(NAMES[d]));
    if (!b) return false;
    b.click();
    for (let i = 0; i < 30; i++) { await sleep(300); if (domain() === d) { await sleep(800); return true; } }
    return false;
  };
  // 상품 객체에서 계산에 쓰는 칸만 남긴다(메모리 · 세 계산이 읽는 칸 전부)
  const slim = o => { const s = o.stats || {}, k = {}; ['current', 'avg30', 'avg90', 'avg180', 'avg365'].forEach(x => { if (s[x]) k[x] = s[x]; });
    const bb = o.buyBoxSellerIdHistory || [];
    return {asin: o.asin, parentAsin: o.parentAsin, brand: o.brand, title: o.title, domainId: o.domainId, monthlySoldHistory: o.monthlySoldHistory || [],
      historicalSalesRankAverages: o.historicalSalesRankAverages || [], stats: k, buyBoxSellerIdHistory: bb.slice(-2), COUNT_NEW_current: o.COUNT_NEW_current, salesRankReference: o.salesRankReference}; };
  const rankOf = o => { const c = o.stats && o.stats.current; return c && c[3] > 0 ? c[3] : 0; };

  // 한 질의 — 결과 표를 끝까지 넘기며 상품 객체를 모은다. stopRank 가 있으면(순위 오름차순) 그 순위를 넘는 쪽에서 멈춘다(필터 키가 안 먹을 때 대비).
  const run1 = async (d, q, tag, stopRank) => {
    const want = low(W.brands);
    location.hash = '#!finder/' + encodeURIComponent(JSON.stringify(q));
    let g = null, zero = 0;
    for (let i = 0; ; i++) {
      await sleep(500); g = grid();
      if (i > 90) return {n: -1};
      if (!g) continue;
      const n = g.getDisplayedRowCount(), r = n > 0 ? g.getDisplayedRowAtIndex(0) : null;
      if (r && r.data && r.data.asin && r.data.domainId === d && want.has(String(r.data.brand || '').toLowerCase())) break;
      zero = n === 0 ? zero + 1 : 0; if (zero >= 40) return {n: 0};
    }
    const M = W.rows[d] = W.rows[d] || {};
    const pages = Math.max(1, g.paginationGetTotalPages ? g.paginationGetTotalPages() : 1);
    let got = 0, stop = false, short = 0;
    for (let p = 0; p < pages && !stop; p++) {
      if (p > 0) g.paginationGoToPage(p);
      const st = p * 100, en = Math.min(st + 100, g.getDisplayedRowCount());
      let c = 0;
      for (let k = 0; k < 50; k++) { c = 0; for (let i = st; i < en; i++) { const r = g.getDisplayedRowAtIndex(i); if (r && r.data && r.data.asin && r.data.domainId === d) c++; } if (c >= en - st) break; await sleep(400); }
      if (c < en - st) short++;
      for (let i = st; i < en; i++) {
        const r = g.getDisplayedRowAtIndex(i); if (!r || !r.data || !r.data.asin || r.data.domainId !== d) continue;
        const o = r.data; if (stopRank && rankOf(o) > stopRank) { stop = true; continue; }
        const e = M[o.asin] || (M[o.asin] = {o: slim(o), a: 0, b: 0}); e[tag] = 1; got++;
      }
      W.cur = MK[d] + ' ' + tag + ' ' + (p + 1) + '/' + pages;
    }
    if (pages > 1) g.paginationGoToPage(0);
    return {n: got, pages, short};
  };

  W.start = (tasks, opt) => {
    W.tasks = tasks; W.opt = opt || {}; W.rows = {}; W.log = []; W.err = ''; W.state = 'run'; W.t0 = Date.now(); W.parts = {}; W.text = '';
    W.bad = {}; W.use = {}; W.spent = 0; const exp = Object.assign({}, EXP, W.opt.exp || {});
    const budget = W.opt.quota > 0 ? W.opt.quota * PER_PCT * 0.95 : Infinity;   // 5% 여유
    const B = new Set(); tasks.forEach(t => t.b.forEach(x => B.add(x))); US.concat(EU, JP).forEach(x => B.add(x));
    W.brands = [...B];
    const doms = (W.opt.doms || DOMS);
    (async () => {
      let zeros = 0;
      for (const d of doms) {
        const t0 = Date.now();
        if (W.spent + exp[d] > budget) { W.log.push(MK[d] + ' 건너뜀(예산 ' + Math.round(budget - W.spent) + ' < 예상 ' + exp[d] + ')'); W.use[MK[d]] = {skip: 1}; continue; }
        if (!(await setDomain(d))) { W.log.push(MK[d] + ' domain-fail'); W.use[MK[d]] = {fail: 'domain'}; continue; }
        const base = {productType: {values: ['0'], filterType: 'set'}, brand: {filterType: 'autocomplete', filter: W.brands.join('###'), type: 'isOneOf'}};
        let a = await run1(d, {f: Object.assign({}, base, {monthlySoldPeak: {filterType: 'number', type: 'greaterThanOrEqual', filter: 50, filterTo: null}}), s: [{colId: 'monthlySold', sort: 'desc'}], t: 'g'}, 'a');
        if (a.n <= 0) { await sleep(3000); a = await run1(d, {f: Object.assign({}, base, {monthlySoldPeak: {filterType: 'number', type: 'greaterThanOrEqual', filter: 50, filterTo: null}}), s: [{colId: 'monthlySold', sort: 'desc'}], t: 'g'}, 'a'); }
        await sleep(1500);
        const b = await run1(d, {f: Object.assign({}, base, {SALES_current: {filterType: 'number', type: 'inRange', filter: 1, filterTo: RANK_B}}), s: [{colId: 'SALES_current', sort: 'asc'}], t: 'g'}, 'b', RANK_B);
        const M = W.rows[d] || {}, all = Object.values(M), sec = Math.round((Date.now() - t0) / 1000);
        W.spent += Math.max(0, a.n) + Math.max(0, b.n);
        const bad = a.n <= 0 || b.n <= 0 || a.short || b.short;
        if (bad) W.bad[d] = 1;
        W.use[MK[d]] = {a: a.n, b: b.n, u: all.length, s: sec, bad: bad ? 1 : 0};
        W.log.push(MK[d] + ' A ' + a.n + ' B ' + b.n + ' 합 ' + all.length + ' (B만 ' + all.filter(e => !e.a).length + ') ' + sec + 's' + (bad ? ' 불완전' : ''));
        for (const r of [a, b]) zeros = r.n <= 0 ? zeros + 1 : 0;   // 질의 연속 0개 수(나라를 넘어 이어 센다)
        if (zeros >= 2) { W.log.push('멈춤 — 두 질의 연속 0개(한도 소진 의심)'); break; }
        await sleep(1500);
      }
      W.state = 'done'; W.t1 = Date.now();
    })().catch(e => { W.err = String(e && e.message || e).slice(0, 120); W.state = 'done'; });
    return 'started · 나라 ' + doms.length + ' · 브랜드 표기 ' + W.brands.length;
  };
  W.status = () => W.state + ' · ' + Math.round(((W.t1 || Date.now()) - (W.t0 || Date.now())) / 1000) + 's · ' + (W.cur || '') + ' · ' + W.log.join(' / ') + (W.err ? ' · ERR ' + W.err : '');

  // 세 계산을 한 번에 — mode = KBCH 의 'full'(36개월) | 'recent'(최근 두 완결 월 + 30일)
  W.build = mode => {
    const out = [];
    // ① KBCH — 나라마다 A∪B 전부
    const ok = d => W.rows[d] && !W.bad[d];   // 불완전한 나라는 뺀다 — 지난 회차 값이 남는다
    if (Object.keys(W.bad).length) out.push('불완전 ' + Object.keys(W.bad).map(d => MK[d]).join(','));
    if (window.__KBK && W.tasks) {
      const byD = {}; for (const d in W.rows) if (ok(d)) byD[d] = Object.values(W.rows[d]).map(e => e.o);
      out.push('KBCH ' + window.__KBK.fromRows(W.tasks, Object.assign({}, W.opt, {mode: mode || W.opt.mode || 'full'}), byD));
      W.parts.kbch = window.__KBK.L.join('\n');
    }
    // ② 국면 미국 — A(국면 브랜드) + B 만(배지 한 번도 없음 · 15만 위 안) → 옛 질의 두 번과 같은 행
    if (window.KBPH && window.KBPH.fromObjs && ok(1)) {
      const L = low(US), es = Object.values(W.rows[1]).filter(e => L.has(String(e.o.brand || '').toLowerCase()));
      const A = es.filter(e => e.a).map(e => e.o), Bo = es.filter(e => !e.a && rankOf(e.o) > 0 && rankOf(e.o) <= RANK_NB).map(e => e.o);
      window.KBPH.fromObjs(A, Bo); window.KBPH.dump();
      W.parts.us = document.getElementById('__dump').textContent;
      out.push('US A ' + A.length + ' NB ' + Bo.length + ' fit ' + JSON.stringify(window.KBPH.fit || null));
    }
    // ③ 국면 유럽 5개국 · 일본 · 캐나다 — A(그 나라 국면 브랜드 목록)만 · 옛 질의와 같다
    if (window.KBPHEU && window.KBPHEU.fromObjs) {
      const sv = {};
      for (const d of [2, 3, 4, 8, 9, 5, 6]) {
        if (!ok(d)) continue;
        const L = low(phList(d)), A = Object.values(W.rows[d]).filter(e => e.a && L.has(String(e.o.brand || '').toLowerCase())).map(e => e.o);
        window.KBPHEU.fromObjs(A); out.push(window.KBPHEU.save(MK[d])); sv[MK[d]] = sessionStorage.getItem('kbeu_' + MK[d]) || '';
      }
      W.parts.eu = ['uk', 'de', 'fr', 'it', 'es'].map(m => sv[m]).filter(Boolean).join('\n') + '\n@@JPCA@@\n' + ['jp', 'ca'].map(m => sv[m]).filter(Boolean).join('\n');
    }
    return out.join(' | ');
  };
  // 한 덩어리 — 구획 표시 줄로 나눈다(week_recv.py 가 나눈다)
  const jh = t => { let h = 0; for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) % 1000000007; return h; };
  W.bundle = () => {
    const P = W.parts, s = [];
    if (P.kbch) s.push('@@KBCH@@\n' + P.kbch);
    if (P.us) s.push('@@US@@\n' + P.us);
    if (P.eu) s.push('@@EU@@\n' + P.eu);
    s.push('@@USE@@\n' + JSON.stringify({q: W.opt.quota || null, spent: W.spent, sec: Math.round(((W.t1 || Date.now()) - W.t0) / 1000), c: W.use}));
    W.text = s.join('\n') + '\n@@END@@';
    return 'len ' + W.text.length + ' h ' + jh(W.text) + ' · 덩어리(2.2만 자) ' + Math.ceil(W.text.length / 22000);
  };
  W.show = (i, n) => {
    const t = W.text, k = n || Math.ceil(t.length / 22000), L = Math.ceil(t.length / k), c = t.slice(i * L, (i + 1) * L);
    let el = document.getElementById('__kwdump'); if (!el) { document.body.innerHTML = ''; el = document.createElement('pre'); el.id = '__kwdump'; el.style.whiteSpace = 'pre-wrap'; document.body.appendChild(el); }
    el.textContent = 'PART' + i + '|' + c.length + '|' + jh(c) + '|' + c.replace(/\n/g, '~') + '|ENDPART';
    return 'part ' + i + '/' + k + ' len ' + c.length + ' h ' + jh(c);
  };
  // 한도 재기용 — 나라별 받은 상품 수
  W.count = () => Object.keys(W.rows).map(d => MK[d] + ' ' + Object.keys(W.rows[d]).length).join(' · ');
  return 'kw v' + W.v + ' ready';
})();
