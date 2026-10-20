/* kbeauty/keepa.js — Keepa Product Finder 수집기 (2026-10-20)
   keepa.com 탭 안에서 돈다 — 사용자 Pro 로그인 세션의 웹 기능(Product Finder)만 쓴다. API 키·토큰은 안 쓴다.
   (Product Finder 결과 표가 행마다 Keepa 상품 객체를 통째로 들고 있다: monthlySoldHistory · historicalSalesRankAverages · stats)

   불러오기(사슬 세션):
     const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/kbeauty/';
     new Function(await (await fetch(R+'keepa.js',{cache:'no-store'})).text())();
     window.__KBK.start(await (await fetch(R+'keepa_tasks.json',{cache:'no-store'})).json(), {mode:'full'});
   → window.__KBK.status() 가 'done · …' 일 때까지 → plan() → dump(a,b) → get_page_text → 파일 → kbeauty/ingest.py

   방법 (상품 = ASIN, 묶음 = 부모 ASIN 이 같은 옵션들):
   · 월판매 배지 = 'Bought in past month' — 구간의 아랫값(50+ · 100+ … 1K+ · 10K+ · 100K+). 월말 7일 중앙값을 그달 값으로, 구간 가운데값으로 바꿔 쓴다.
     100K+ 는 위가 막힌 값이라(메디큐브 제로모공패드 같은 1위권) 순위 곡선 값과 큰 쪽을 쓴다.
   · 순위 = 그달 뷰티 전체 순위 평균(historicalSalesRankAverages · 36개월). 옵션들이 순위를 공유하면(부모 단위 순위) 묶음 하나로 센다.
   · 순위 → 판매량 곡선은 나라마다 이 회차 데이터로 맞춘다: log 판매 = a + b1·min(x, ln1000) + b2·max(0, x − ln1000), x = ln 순위.
     맞추는 점 = 배지가 있고(100K+ 아님) 순위가 하나인 묶음의 (그달 평균 순위, 그달 배지 가운데값 합) · 20~3만 위.
     3만 위 밖(배지 없는 꼬리)은 기울기 −1.4 로 꺾는다(v6 · 미국 실측 1만→7.7만 위 −1.38). 배지 없는 묶음은 옵션당 49개를 넘지 않는다.
   · 가격 = 바이박스(없으면 신품 최저가 → 아마존가) 30·90·180·365일 평균을 구간으로 풀어 그달 나이에 맞는 값.
   · 판매액(현지 통화) = Σ 묶음[판매량 × 가격]. 이번 달(MC)은 '최근 30일'(배지 = 지난 30일, 순위 = 30일 평균)이다 — 달력 월이 아니다.

   덤프 줄(마지막 칸은 CRC32(앞부분) 36진수):
     H|v|날짜|MS|MC|과제 수|모드
     F|도메인|점 수|구간 수|a|b1|b2           ← 곡선(소수 4자리 · 맞출 점이 모자라면 미국 곡선을 빌려 'us')
     A|도메인|브랜드키|상품 수|묶음 수|U…|V…|R  ← 월별 판매량·판매액(36진수 · MS..MC · 빈칸 = 0) · R = 순위 곡선에서 온 판매량 비중(%)
     T|도메인|브랜드키|순서|묶음키|옵션 수|제목|현재가||V…   ← 판매액 상위 묶음(최근 13개월 판매액 · 판매량 칸은 v6 부터 비움 · 미국·일본 6개 · 그 밖 4개)
     X|도메인|브랜드키|사유                   ← 실패
     END|줄 수|crc
*/
(function () {
  'use strict';
  const V = 7;
  if (window.__KBK && window.__KBK.v === V && window.__KBK.state === 'run') return 'already running';
  const K = window.__KBK = {v: V, state: 'idle', tasks: [], i: 0, raw: [], log: [], err: '', t0: 0, t1: 0, L: null, opt: {}};
  // 탭이 뒤로 가면 크롬이 setTimeout 을 1분 단위로 묶는다(집중 제한) — 워커 타이머는 그 제한을 안 받는다. 워커가 막히면(CSP) 그냥 setTimeout.
  let wk = null; const pend = {}; let seq = 0;
  try { wk = new Worker(URL.createObjectURL(new Blob(['onmessage=e=>setTimeout(()=>postMessage(e.data[0]),e.data[1])'], {type: 'text/javascript'}))); wk.onmessage = e => { const f = pend[e.data]; delete pend[e.data]; if (f) f(); }; } catch (e) { wk = null; }
  const sleep = ms => wk ? new Promise(r => { const id = ++seq; pend[id] = r; wk.postMessage([id, ms]); }) : new Promise(r => setTimeout(r, ms));
  const NAMES = {1: 'United States', 2: 'United Kingdom', 3: 'Germany', 4: 'France', 5: 'Japan', 6: 'Canada', 8: 'Italy', 9: 'Spain'};
  const KT = 21564000, DAY = 864e5, X0 = Math.log(1000);
  const b36 = n => (n == null || !(n > 0)) ? '' : Math.round(n).toString(36);
  const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; } return t; })();
  const crc32 = str => { const b = new TextEncoder().encode(str); let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC_T[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return ((c ^ 0xFFFFFFFF) >>> 0).toString(36); };
  const clean = (s, n) => String(s || '')
    .replace(/[\u2010-\u2015\u2212]/g, '-').replace(/[\u2018\u2019\u201a\u2032]/g, "'").replace(/[\u201c\u201d\u201e\u2033]/g, '"')
    .replace(/[\u2122\u00ae\u00a9\u200b-\u200f\u2060\ufeff]/g, '').replace(/[\u2502\u3163\uff5c]/g, '/')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^\x20-\x7e]/g, '')
    .replace(/[|\r\n\t=&?;,]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n || 40).trim();
  const ym = t => { const d = new Date(t); return d.getUTCFullYear() * 12 + d.getUTCMonth(); };
  let NOW = Date.now(), MC = ym(NOW), MS = MC - 36;
  const N = () => MC - MS + 1;
  const nextB = v => v < 100 ? 100 : v < 1000 ? v + 100 : v < 10000 ? v + 1000 : v < 100000 ? v + 10000 : v * 2;
  const mid = v => v >= 100000 ? 125000 : (v + nextB(v)) / 2;

  K.domain = () => (typeof getDomainByTld === 'function') ? getDomainByTld(window.tld || 'com') : 0;
  K.grid = () => { const c = document.querySelector('.ag-root-wrapper'); return (c && c.__agComponent && c.__agComponent.gridApi) || null; };
  K.setDomain = async d => {
    if (K.domain() === d) return true;
    const b = [...document.querySelectorAll('button.knav-mk')].find(x => x.textContent.includes(NAMES[d]));
    if (!b) return false;
    b.click();
    for (let i = 0; i < 30; i++) { await sleep(300); if (K.domain() === d) { await sleep(800); return true; } }
    return false;
  };

  // 한 브랜드·한 나라 — 상품 객체를 다 받을 때까지 쪽을 넘긴다
  K.query = async (d, brands, zw) => {
    const q = {f: {productType: {values: ['0'], filterType: 'set'}, brand: {filterType: 'autocomplete', filter: brands.join('###'), type: 'isOneOf'}},
      s: [{colId: 'SALES_current', sort: 'asc'}], t: 'g'};
    const want = brands.map(b => b.toLowerCase());
    const mine = r => { if (!r || !r.data || !r.data.asin || r.data.domainId !== d) return false; const bl = String(r.data.brand || '').toLowerCase();
      return want.some(w => bl === w || bl.includes(w) || (bl.length > 2 && w.includes(bl))); };
    location.hash = '#!finder/' + encodeURIComponent(JSON.stringify(q));
    let g = null, n = 0, zero = 0;
    for (let i = 0; i < 60; i++) {
      await sleep(500);
      g = K.grid(); if (!g) continue;
      n = g.getDisplayedRowCount();
      const r = n > 0 ? g.getDisplayedRowAtIndex(0) : null;
      if (mine(r)) break;
      zero = n === 0 ? zero + 1 : 0;
      if (zero >= (zw || 12)) return {n: 0, rows: []};
      if (i === 59) return {n: -1, rows: []};
    }
    const rows = [], pages = Math.max(1, g.paginationGetTotalPages ? g.paginationGetTotalPages() : 1);
    for (let p = 0; p < pages; p++) {
      if (p > 0) g.paginationGoToPage(p);
      const st = p * 100, en = Math.min(st + 100, g.getDisplayedRowCount());
      for (let k = 0; k < 40; k++) {
        let got = 0; for (let i = st; i < en; i++) { const r = g.getDisplayedRowAtIndex(i); if (r && r.data && r.data.asin) got++; }
        if (got >= en - st) break;
        await sleep(400);
      }
      for (let i = st; i < en; i++) { const r = g.getDisplayedRowAtIndex(i); if (r && r.data && r.data.asin) rows.push(r.data); }
    }
    if (pages > 1) g.paginationGoToPage(0);
    return {n: g.getDisplayedRowCount(), rows};
  };

  // 상품 객체 → 37개월 배지·순위·가격
  const prices = st => {
    const w = k => { if (!st || !st[k]) return -1; for (const i of [18, 1, 0]) { const v = st[k][i]; if (v > 0) return v; } return -1; };
    const p30 = w('avg30'), p90 = w('avg90'), p180 = w('avg180'), p365 = w('avg365'), cur = w('current');
    const ok = (x, ref) => x > 0 && ref > 0 && x < ref * 3 && x > ref / 3;
    const a = p30 > 0 ? p30 : cur;
    let s2 = (p90 > 0 && p30 > 0) ? (90 * p90 - 30 * p30) / 60 : p90; if (!ok(s2, p90)) s2 = p90 > 0 ? p90 : a;
    let s3 = (p180 > 0 && p90 > 0) ? (180 * p180 - 90 * p90) / 90 : p180; if (!ok(s3, p180)) s3 = p180 > 0 ? p180 : s2;
    let s4 = (p365 > 0 && p180 > 0) ? (365 * p365 - 180 * p180) / 185 : p365; if (!ok(s4, p365)) s4 = p365 > 0 ? p365 : s3;
    return {cur: cur > 0 ? cur : a, seg: [a, s2, s3, s4]};
  };
  const prod = d => {
    const h = d.monthlySoldHistory || [], pts = [];
    for (let i = 0; i + 1 < h.length; i += 2) pts.push([(h[i] + KT) * 60000, h[i + 1]]);
    const at = t => { let lo = 0, hi = pts.length - 1, v = 0; while (lo <= hi) { const m = (lo + hi) >> 1; if (pts[m][0] <= t) { v = pts[m][1]; lo = m + 1; } else hi = m - 1; } return v > 0 ? v : 0; };
    const st = d.stats || {}, hr = d.historicalSalesRankAverages || [], pr = prices(st);
    const ms = [], rk = [], pc = [];
    for (let M = MS; M <= MC; M++) {
      const y = Math.floor(M / 12), mo = M % 12;
      const end = Math.min(Date.UTC(y, mo + 1, 1) - 1, NOW), vs = [];
      for (let k = 0; k < 7; k++) vs.push(at(end - k * DAY));
      vs.sort((a, b) => a - b); const v = vs[3];
      ms.push(v > 0 ? v : 0);
      let r = 0;
      if (M < MC) { const x = hr[((M % 36) + 36) % 36]; r = x > 0 ? x : 0; }
      else { const a30 = st.avg30 && st.avg30[3], c = st.current && st.current[3]; r = a30 > 0 ? a30 : (c > 0 ? c : 0); }
      rk.push(r);
      const age = (NOW - (Date.UTC(y, mo, 15))) / DAY;
      pc.push(M === MC ? pr.seg[0] : age <= 45 ? pr.seg[0] : age <= 105 ? pr.seg[1] : age <= 195 ? pr.seg[2] : pr.seg[3]);
    }
    return {a: d.asin, g: d.parentAsin || d.asin, t: clean(d.title, 40), ms, rk, pc, p: pr.cur};
  };

  // 순위 → 판매량 곡선 (나라별)
  // 맞추는 구간은 20~3만 위 — 20위 안은 묶음이 몇 개 안 되고(100K+ 막힘 · 일부 옵션만 잡힌 묶음이 섞인다), 3만 위 밖은 배지 없는 상품이 빠져 위로 쏠린다.
  const XLO = Math.log(20), XHI = Math.log(30000), TOP = 0.35, TAIL = 1.4;
  const fitCurve = pairs => {
    pairs = pairs.filter(([x]) => x >= XLO && x <= XHI);
    if (pairs.length < 30) return null;
    const bins = {};
    for (const [x, y] of pairs) { const b = Math.floor(x / 0.25); (bins[b] = bins[b] || []).push(y); }
    const pts = [];
    for (const b in bins) { const ys = bins[b].sort((p, q) => p - q); if (ys.length < 6) continue; pts.push([(+b + 0.5) * 0.25, ys[Math.floor(ys.length / 2)], Math.sqrt(ys.length)]); }
    if (pts.length < 6) return null;
    // 가중 최소제곱: y = a + b1·z1 + b2·z2
    const S = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], T = [0, 0, 0];
    for (const [x, y, w] of pts) { const z = [1, Math.min(x, X0), Math.max(0, x - X0)]; for (let i = 0; i < 3; i++) { T[i] += w * z[i] * y; for (let j = 0; j < 3; j++) S[i][j] += w * z[i] * z[j]; } }
    const det3 = m => m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
    const D = det3(S); if (Math.abs(D) < 1e-9) return null;
    const sol = [0, 1, 2].map(k => det3(S.map((row, i) => row.map((v, j) => j === k ? T[i] : v))) / D);
    if (!(sol[1] < 0 && sol[2] < 0)) return null;
    return {a: sol[0], b1: sol[1], b2: sol[2], n: pairs.length, bins: pts.length};
  };
  // 20위 안은 곡선을 그대로 늘이지 않고 완만하게(지수 0.35) — 상위권은 멱함수보다 평평하다(AMZSUB 보정 때도 같았다)
  const ucurve = (c, x) => Math.exp(c.a + c.b1 * Math.min(x, X0) + c.b2 * Math.max(0, x - X0));
  // 3만 위 밖은 곡선을 그대로 늘이면 너무 높다(맞춘 점이 배지 있는 상품뿐이라 위로 쏠린다) — 미국 실측 1만→7.7만 위 기울기 −1.38 로 꺾는다(TAIL).
  const units = (c, r) => { if (!(r > 0)) return 0; const x = Math.log(r);
    if (x < XLO) return ucurve(c, XLO) * Math.pow(20 / r, TOP);
    if (x > XHI) return ucurve(c, XHI) * Math.pow(30000 / r, TAIL);
    return ucurve(c, x); };

  const groupsOf = ps => { const G = {}; for (const p of ps) (G[p.g] = G[p.g] || []).push(p); return G; };
  const shared = (kids, j) => { const rs = kids.map(k => k.rk[j]).filter(r => r > 0); if (!rs.length) return 0; const mn = Math.min(...rs), mx = Math.max(...rs); return (mx - mn) <= Math.max(2, mn * 0.02) ? mn : -1; };

  K.status = () => {
    const el = K.t0 ? Math.round(((K.t1 || Date.now()) - K.t0) / 1000) : 0;
    const last = K.log.slice(-1)[0] || '';
    return K.state + ' · ' + K.i + '/' + K.tasks.length + ' · ' + el + 's · ' + last + (K.err ? ' · ERR ' + K.err : '');
  };

  K.start = (tasks, opt) => { K.run(tasks, opt).catch(e => { K.err = clean(e && e.message, 80); K.state = 'done'; K.t1 = Date.now(); }); return 'started · ' + tasks.length; };
  K.run = async (tasks, opt) => {
    K.opt = opt || {}; K.tasks = tasks; K.i = 0; K.raw = []; K.log = []; K.err = ''; K.L = null;
    NOW = Date.now(); MC = ym(NOW); MS = MC - 36;
    K.state = 'run'; K.t0 = Date.now(); K.t1 = 0;
    const order = tasks.map((t, i) => i).sort((p, q) => tasks[p].d - tasks[q].d || p - q);
    for (const idx of order) {
      const t = tasks[idx], t0 = Date.now();
      try {
        if (!(await K.setDomain(t.d))) { K.raw.push({t, fail: 'domain'}); K.log.push(t.d + ' ' + t.k + ' domain-fail'); K.i++; continue; }
        let r = await K.query(t.d, t.b);
        if (r.n === 0) { await sleep(2500); r = await K.query(t.d, t.b, 40); }   // 큰 브랜드는 6초 안에 표가 안 찰 때가 있다(10/20 메디큐브 영국·프랑스·바이오던스 미국이 0 으로 잡혔다)
        if (r.n < 0) { K.raw.push({t, fail: 'timeout'}); K.log.push(t.d + ' ' + t.k + ' timeout'); }
        else {
          // 이름이 흔한 브랜드(TS 등)는 제목 조건(tf)으로 한 번 더 거른다
          let rows = r.rows; if (t.tf) { const re = new RegExp(t.tf, 'i'); rows = rows.filter(x => re.test(x.title || '')); }
          K.raw.push({t, n: rows.length, ps: rows.map(prod)}); K.log.push(t.d + ' ' + t.k + ' ' + rows.length + ' ' + Math.round((Date.now() - t0) / 1000) + 's');
        }
      } catch (e) { K.raw.push({t, fail: clean(e && e.message, 40)}); K.log.push(t.d + ' ' + t.k + ' err'); }
      K.i++;
      await sleep(600 + Math.random() * 600);
    }
    K.build();
    K.state = 'done'; K.t1 = Date.now();
    return K.status();
  };

  // 몇 과제만 다시(0 으로 잡힌 것 등) — 'd:k' 쉼표 목록. 받은 묶음을 그 자리에 갈아 끼우고 다시 짓는다.
  K.rerun = async (keys, zw) => {
    const ks = String(keys || '').split(',').filter(Boolean);
    K.state = 'run'; K.err = '';
    for (const key of ks) {
      const [d, k] = key.split(':'); const ix = K.raw.findIndex(R => String(R.t.d) === d && R.t.k === k);
      if (ix < 0) { K.log.push(key + ' no-task'); continue; }
      const t = K.raw[ix].t, t0 = Date.now();
      try {
        if (!(await K.setDomain(t.d))) { K.log.push(key + ' domain-fail'); continue; }
        const r = await K.query(t.d, t.b, zw || 40);
        if (r.n < 0) { K.log.push(key + ' timeout'); continue; }
        let rows = r.rows; if (t.tf) { const re = new RegExp(t.tf, 'i'); rows = rows.filter(x => re.test(x.title || '')); }
        K.raw[ix] = {t, n: rows.length, ps: rows.map(prod)}; K.log.push(key + ' ' + rows.length + ' ' + Math.round((Date.now() - t0) / 1000) + 's');
      } catch (e) { K.log.push(key + ' err'); }
      await sleep(600 + Math.random() * 600);
    }
    K.build(); K.state = 'done';
    return K.status();
  };

  K.build = () => {
    const L = [], push = a => { const s = a.join('|'); L.push(s + '|' + crc32(s)); };
    const dt = new Date(NOW).toISOString().slice(0, 10);
    push(['H', V, dt, MS, MC, K.tasks.length, K.opt.mode || 'full']);
    // 나라별 곡선
    const byD = {};
    for (const R of K.raw) if (R.ps) (byD[R.t.d] = byD[R.t.d] || []).push(...R.ps);
    const curves = {};
    for (const d in byD) {
      const pairs = [], G = groupsOf(byD[d]);
      for (const g in G) {
        const kids = G[g];
        for (let j = 0; j < N() - 1; j++) {
          const r = shared(kids, j); if (!(r > 0)) continue;
          let s = 0, cap = false; for (const k of kids) { const v = k.ms[j]; if (v > 0) { s += mid(v); if (v >= 100000) cap = true; } }
          if (s > 0 && !cap) pairs.push([Math.log(r), Math.log(s)]);
        }
      }
      curves[d] = fitCurve(pairs);
      if (curves[d]) curves[d].pairs = pairs.length;
    }
    const us = curves[1];
    for (const d in byD) {
      let c = curves[d], tag = 'own';
      if (!c) { c = us; tag = 'us'; curves[d] = us ? Object.assign({}, us, {borrowed: 1}) : null; }
      push(['F', d, c ? (c.pairs || c.n) : 0, c ? c.bins : 0, c ? c.a.toFixed(4) : '', c ? c.b1.toFixed(4) : '', c ? c.b2.toFixed(4) : '', tag]);
    }
    // 브랜드·나라별 집계 + 상위 묶음
    const mode = K.opt.mode || 'full', topMin = K.opt.topMin || 30000;
    const topOf = d => (d === 1 || d === 5) ? (K.opt.top || 6) : (K.opt.topEU || 4);
    for (const R of K.raw) {
      const t = R.t;
      if (!R.ps) { push(['X', t.d, t.k, R.fail || '?']); continue; }
      const c = curves[t.d];
      const G = groupsOf(R.ps), U = new Array(N()).fill(0), Vv = new Array(N()).fill(0);
      let fromRank = 0, tot = 0;
      const gs = [];
      for (const g in G) {
        const kids = G[g], gu = new Array(N()).fill(0), gv = new Array(N()).fill(0);
        for (let j = 0; j < N(); j++) {
          const ps = kids.map(k => k.pc[j]).filter(p => p > 0).sort((a, b) => a - b), pm = ps.length ? ps[Math.floor(ps.length / 2)] : 0;
          let bs = 0, bv = 0, cap = false;
          for (const k of kids) { const v = k.ms[j]; if (v > 0) { const m = mid(v); bs += m; bv += m * (k.pc[j] > 0 ? k.pc[j] : pm); if (v >= 100000) cap = true; } }
          const r = shared(kids, j);
          let ru = 0;
          if (c) { if (r > 0) ru = units(c, r); else if (r === -1) for (const k of kids) ru += units(c, k.rk[j]); }
          let u = 0, v = 0;
          if (bs > 0) { if (cap && ru > bs) { u = ru; v = (bv > 0 ? bv / bs : pm) * ru; fromRank += ru - bs; } else { u = bs; v = bv > 0 ? bv : bs * pm; } }
          else if (ru > 0) { const nk = kids.filter(k => k.rk[j] > 0).length || 1; u = Math.min(ru, 49 * nk); v = u * pm; fromRank += u; }
          gu[j] = u; gv[j] = v; U[j] += u; Vv[j] += v; tot += u;
        }
        const best = kids.slice().sort((a, b) => (b.ms[N() - 2] || 0) - (a.ms[N() - 2] || 0) || ((a.rk[N() - 2] || 9e9) - (b.rk[N() - 2] || 9e9)))[0];
        const recent = gv.slice(N() - 4, N() - 1).reduce((s, x) => s + x, 0);
        gs.push({g, kids: kids.length, t: best.t, p: best.p, gu, gv, recent});
      }
      const pct = tot > 0 ? Math.round(fromRank / tot * 100) : 0;
      const div = (t.d === 5) ? 1 : 100;   // 일본만 엔 단위(나머지 센트)
      const cut = mode === 'recent' ? N() - 3 : 0;
      push(['A', t.d, t.k, R.n, Object.keys(G).length, U.slice(cut).map(b36).join(','), Vv.slice(cut).map(x => b36(x / div)).join(','), pct]);
      gs.sort((a, b) => b.recent - a.recent);
      gs.slice(0, topOf(t.d)).forEach((x, i) => {
        if (x.recent / div < topMin) return;
        push(['T', t.d, t.k, i + 1, x.g, x.kids, x.t, b36(x.p), '', x.gv.slice(N() - 13).map(v => b36(v / div)).join(',')]);
      });
    }
    L.push(['END', L.length + 1, crc32(L.join('\n'))].join('|'));
    K.L = L;
    return L.length;
  };

  // 빠른 확인용 — 브랜드·나라마다 최근 4개월 판매량(천 개)·판매액(백만, 현지 통화) 한 줄씩
  K.peek = () => {
    if (!K.L) return 'not built';
    const p = x => x ? parseInt(x, 36) : 0;
    return K.L.filter(l => l[0] === 'A' || l[0] === 'F' || l[0] === 'X').map(l => {
      const f = l.split('|'); if (f[0] !== 'A') return f.slice(0, 8).join(' ');
      const U = f[5].split(',').map(p), Vv = f[6].split(',').map(p), dv = f[1] === '5' ? 1 : 1;
      return f[1] + ' ' + f[2] + ' n' + f[3] + ' rank' + f[7] + ' U ' + U.slice(-4).map(x => (x / 1e3).toFixed(1)).join(' ') + ' V ' + Vv.slice(-4).map(x => (x / 1e6 * dv).toFixed(2)).join(' ');
    }).join(' / ');
  };

  K.plan = max => {
    if (!K.L) return 'not built · ' + K.status();
    const lim = max || 24000, out = []; let a = 0, c = 0;
    K.L.forEach((l, i) => { if (c + l.length + 1 > lim && i > a) { out.push(a + '-' + i); a = i; c = 0; } c += l.length + 1; });
    out.push(a + '-' + K.L.length);
    return out.join(',') + ' · lines ' + K.L.length + ' · chars ' + K.L.join('\n').length;
  };
  const show = txt => {
    let pre = document.getElementById('kbkdump');
    if (!pre) { document.body.innerHTML = ''; pre = document.createElement('pre'); pre.id = 'kbkdump'; pre.style.whiteSpace = 'pre-wrap'; document.body.appendChild(pre); }
    pre.textContent = txt; document.title = 'kbk dump';
  };
  K.dump = (from, to) => {
    if (!K.L) return 'not built';
    const a = from || 0, b = Math.min(K.L.length, to || K.L.length);
    show(K.L.slice(a, b).join('\n'));
    return 'dumped · lines ' + a + '-' + (b - 1) + ' of ' + K.L.length;
  };
  K.redo = keys => {
    if (!K.L) return 'not built';
    const ks = String(keys || '').split(',').filter(Boolean), pick = K.L.filter(l => ks.some(k => l.startsWith(k)));
    show(pick.join('\n'));
    return 'redo · lines ' + pick.length;
  };
  return 'kbk v' + V + ' ready · timer ' + (wk ? 'worker' : 'page');
})();
