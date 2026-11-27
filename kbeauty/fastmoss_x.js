/* kbeauty/fastmoss_x.js — FastMoss 샵 상세 '분석' 스냅샷 + 미국 틱톡샵 뷰티 시장 일별 (2026-11-27)
   fastmoss.js(일별 판매·소셜)와 같은 원칙 — 화면이 부른 응답만 엿듣는다(요청을 직접 만들지 않는다).
   한 번 하드 로드한 탭에서 Next 앱 라우터(window.next.router.push)로 샵 상세·시장 화면을 옮겨 다니며 훅을 유지한다.
   javascript_tool 로 이 파일 내용을 그대로 붙여 넣으면 window.__FX 가 생긴다.

   샵 하나(28일 창 · 데이터 갱신일 기준):
     saleAnalysis     거래 채널(상품 카드·자체 계정·인플루언서) · 판매 방식(영상·라이브·상품 카드) 판매량·판매액
     authorAnalysis   크리에이터 요약(전체·영상·라이브·새로 · 크리에이터 경유 판매량·판매액) · 팔로워 구간별 판매량
     v3/author        크리에이터 상위 5(28일 판매)
     v3/goods         상품 상위 5(28일 판매) · 등록 상품 수
     videoAnalysisSummary  영상 경유 판매·재생수
     videoAnalysis    최근 180일 영상 수(전체) → '광고 집행 중'을 눌러 광고 영상 수
     liveAnalysisSummary   라이브 요약
   시장(뷰티 & 퍼스널 케어 · 미국): market-pulse 주 보기(date_type 2) 한 번에 7일 일별 판매량·판매 상품 수·신규 상품·크리에이터·영상·라이브 + 그 주 평균 거래가.
     월 보기는 이 요금제에서 MAG_AUTH_3016(가짜 견본)이라 쓰지 않는다 — code 200 만 받는다.

   느린 이유와 고친 것(2026-11-27 첫 회차):
     · 탭이 뒤에 있으면 setTimeout 이 1분 단위로 묶인다 → 대기는 Web Worker 타이머(window.__wsleep)로.
     · 뒤에 있는 탭은 아래쪽 칸(크리에이터·상품·영상 분석)이 '화면에 보일 때' 부르는 IntersectionObserver 라 영영 안 부른다
       → IntersectionObserver 를 '바로 보인다'고 답하는 것으로 바꿔 둔다(이 탭에서만 · 새로 고치면 원래대로).
     · 칸이 늦게 오면 빠진다 → 꼭 있어야 할 응답 목록(NEED)이 다 올 때까지 세 번까지 다시 내려 본다.
     → 샵 하나 약 8초 · 148곳 약 20분 · 시장 100주 약 5분.

   덤프 줄 v2(마지막 칸 CRC32 36진수 · 숫자는 36진수 · 판매액은 달러 정수):
     XH|2|날짜|샵 수|시장 주 수
     Y|seller_id|브랜드키|숫자 27개|크리에이터 상위 3(id~팔로워~판매량~판매액;…)|상품 상위 3(id~제목40~가격~YYMMDD~판매량~판매액~크리에이터~영상~수수료;…)
        숫자 27개 = 등록 상품 · 채널 판매량(상품 카드·자체 계정·크리에이터) · 채널 판매액(같은 순) · 방식 판매량(영상·라이브·상품 카드) · 방식 판매액(같은 순)
                   · 크리에이터 수·영상 크리에이터·라이브 크리에이터·새 크리에이터·크리에이터 경유 판매량·판매액 · 180일 영상·광고 영상
                   · 영상 경유 판매량·판매액·재생 · 라이브 수·판매량·판매액
     N|ISO 주(YYYY-WW)|평균 거래가×100|MMDD:판매량:판매 상품:신규 상품:크리에이터:영상:라이브,…
     E|id|사유
     END|줄 수(END 포함)|crc32(앞 줄 전부를 \n 으로 이은 것)
   옮기기: window.__FXD(a,b) 가 본문을 그 줄들로 바꾼다 → get_page_text → 파일 → python3 kbeauty/fmx_recv.py 파일들… → python3 kbeauty/phase.py
     (v1 의 X|id|key|JSON · M 줄도 fmx_recv·phase 가 그대로 읽는다 — 다만 JSON 이라 덤프가 3배 길다)
*/
(function () {
  'use strict';
  const V = 2;
  // 뒤 탭에서도 제때 깨는 대기 — Worker 안의 타이머는 탭이 가려져도 묶이지 않는다
  if (!window.__wsleep) {
    const w = new Worker(URL.createObjectURL(new Blob(['onmessage=e=>setTimeout(()=>postMessage(e.data[0]),e.data[1])'], {type: 'text/javascript'})));
    const cb = {}; let id = 0;
    w.onmessage = e => { const f = cb[e.data]; delete cb[e.data]; if (f) f(); };
    window.__wsleep = ms => new Promise(r => { const i = ++id; cb[i] = r; w.postMessage([i, ms]); });
  }
  const sleep = ms => window.__wsleep(ms);
  // 아래쪽 칸은 화면에 들어올 때 데이터를 부른다 — 가려진 탭에서도 부르게 '바로 보인다'고 답한다
  if (!window.__ioPatched) {
    window.__ioPatched = 1;
    window.IntersectionObserver = class {
      constructor(cb) { this.cb = cb; }
      observe(el) { setTimeout(() => { try { const r = el.getBoundingClientRect(); this.cb([{target: el, isIntersecting: true, intersectionRatio: 1, boundingClientRect: r, intersectionRect: r, rootBounds: null, time: performance.now()}], this); } catch (e) { /* 무시 */ } }, 0); }
      unobserve() {} disconnect() {} takeRecords() { return []; }
    };
  }
  const NEED = ['v3/base', 'v3/saleAnalysis', 'v3/authorAnalysis', 'v3/author', 'v3/goods', 'v3/videoAnalysis', 'v3/videoAnalysisSummary', 'v3/liveAnalysisSummary'];
  const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; } return t; })();
  const crc32 = str => { const b = new TextEncoder().encode(str); let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC_T[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return ((c ^ 0xFFFFFFFF) >>> 0).toString(36); };
  const clean = (s, n) => String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^\x20-\x7e]/g, '')
    .replace(/[|\r\n\t=&?;"\\]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n || 40).trim();
  const num = x => { const v = +x; return isFinite(v) ? Math.round(v * 100) / 100 : null; };
  const X = window.__FX = window.__FX && window.__FX.v === V ? window.__FX : {v: V, res: {}, mk: {}, err: {}, done: 0, stop: false, state: 'idle'};
  if (!window.__fxHook) {
    window.__fxHook = 1; window.__cap = window.__cap || [];
    const o = XMLHttpRequest.prototype.open, s = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__u = u; return o.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function () {
      this.addEventListener('load', () => { if (/\/api\/(shop|goods|GoodCategory)/.test(this.__u || '')) window.__cap.push({u: this.__u, t: this.responseText}); });
      return s.apply(this, arguments);
    };
    const f0 = window.fetch;
    window.fetch = async function (i) {
      const r = await f0.apply(this, arguments);
      try { const u = typeof i === 'string' ? i : i.url; if (/\/api\/(shop|goods|GoodCategory)/.test(u)) r.clone().text().then(t => window.__cap.push({u, t})); } catch (e) { /* 무시 */ }
      return r;
    };
  }
  const J = c => { try { return JSON.parse(c.t); } catch (e) { return null; } };
  const path = c => c.u.split('?')[0];
  const pick = (sid, name, pred) => window.__cap.filter(c => path(c).endsWith(name) && c.u.includes(sid) && (!pred || pred(c.u))).slice(-1)[0];
  const okCode = j => j && (j.code === 200 || j.code === '200' || j.code === 0);

  const pair = (lst, keyF, vF) => { const o = {}; (lst || []).forEach(r => { o[keyF(r)] = vF(r); }); return o; };
  const srcKey = s => String(s || '').split('.').pop();   // product_card · shop_account · affiliate
  const ctKey = s => /^video/.test(s) ? 'video' : /^live/.test(s) ? 'live' : 'card';

  X.one = async (sid, key) => {
    window.__cap = [];
    window.next.router.push('/ko/shop-marketing/detail/' + sid);
    for (let i = 0; i < 40; i++) { await sleep(300); if (location.pathname.endsWith(sid) && pick(sid, 'v3/base')) break; }
    if (!pick(sid, 'v3/base')) return {e: 'no-base'};
    await sleep(1200);
    // 꼭 있어야 할 응답이 다 올 때까지 세 번까지 내려 본다
    for (let pass = 0; pass < 3; pass++) {
      const miss = () => NEED.filter(n => !pick(sid, n));
      if (!miss().length) break;
      for (let y = 0; y < 9600; y += 800) { window.scrollTo(0, y); await sleep(220); if (!miss().length) break; }
      for (let i = 0; i < 12 && miss().length; i++) await sleep(300);
      window.scrollTo(0, 0);
    }
    { const m = NEED.filter(n => !pick(sid, n)); if (m.length) return {e: 'miss-' + m.map(n => n.replace('v3/', '')).join('+').slice(0, 40)}; }
    await sleep(300);
    const bad = window.__cap.filter(c => c.u.includes(sid)).map(J).filter(j => j && !okCode(j));
    if (bad.length) return {e: 'code-' + bad[0].code};
    const out = {};
    const b = J(pick(sid, 'v3/base') || {}); if (b && b.data) { const d = b.data; out.b = {pc: num(d.product_count), tpc: num(d.total_product_count), u: num(d.sold_count), v: num(d.sale_amount)}; }
    const sa = J(pick(sid, 'v3/saleAnalysis', u => /d_type=28/.test(u)) || {});
    if (sa && sa.data) {
      const ch = sa.data.channel_distribution || {}, ct = sa.data.content_distribution || {};
      out.ch = {u: pair(ch.units_sold && ch.units_sold.list, r => srcKey(r.source), r => num(r.sold_count)), v: pair(ch.gmv && ch.gmv.list, r => srcKey(r.source), r => num(r.sale_amount))};
      out.ct = {u: pair(ct.units_sold && ct.units_sold.list, r => ctKey(r.category), r => num(r.sold_count)), v: pair(ct.gmv && ct.gmv.list, r => ctKey(r.category), r => num(r.sale_amount))};
    }
    const aa = J(pick(sid, 'v3/authorAnalysis', u => /d_type=28/.test(u)) || {});
    if (aa && aa.data) {
      const s = aa.data.summary || {};
      out.au = {n: num(s.author_count), nv: num(s.video_count), nl: num(s.live_count), u: num(s.sold_count), v: num(s.sale_amount), nn: num(s.inc_author_count)};
      const fr = aa.data.follower_range || {};
      out.fr = pair(fr.sold_count_range, r => clean(r.label, 12), r => num(r.value));
    }
    const al = J(pick(sid, 'v3/author', u => /d_type=28/.test(u) && /page=1\b/.test(u)) || {});
    if (al && al.data) out.ta = {t: num(al.data.total), l: (al.data.list || []).slice(0, 5).map(r => [clean(r.unique_id, 30), num(r.follower_count), num(r.sold_count), num(r.sale_amount)])};
    const gl = J(pick(sid, 'v3/goods', u => /d_type=28/.test(u) && /page=1\b/.test(u)) || {});
    if (gl && gl.data) out.tg = {t: num(gl.data.total), l: (gl.data.product_list || []).slice(0, 5).map(r => [String(r.product_id || r.id), clean(r.title, 70), clean(r.price, 20), String(r.ctime || '').slice(0, 10),
      num(r.sold_count), num(r.sale_amount), num(r.relate_author_count), num(r.relate_video_count), clean(r.crate, 6)])};
    const vs = J(pick(sid, 'v3/videoAnalysisSummary') || {});
    if (vs && vs.data) out.vs = {u: num(vs.data.video_count), v: num(vs.data.video_amount), p: num(vs.data.play_count)};
    const ls = J(pick(sid, 'v3/liveAnalysisSummary') || {});
    if (ls && ls.data) { const o = {}; Object.entries(ls.data).forEach(([k, v]) => { if (typeof v === 'number' && !/pop|rate/.test(k)) o[k] = num(v); }); out.ls = o; }
    const va = J(pick(sid, 'v3/videoAnalysis', u => /is_ad=-1/.test(u)) || {});
    if (va && va.data) out.va = {all: num(va.data.total)};
    // 광고 집행 중 — 영상 분석 표의 필터 버튼(화면이 is_ad=1 로 다시 부른다)
    const btn = [...document.querySelectorAll('label, span, div, button')].find(e => e.childElementCount === 0 && (e.textContent || '').trim() === '광고 집행 중');
    if (btn && out.va) {
      const n0 = window.__cap.length; btn.click();
      for (let i = 0; i < 25; i++) {
        await sleep(300);
        const c = window.__cap.slice(n0).find(c => path(c).endsWith('v3/videoAnalysis') && /is_ad=1\b/.test(c.u) && c.u.includes(sid));
        if (c) { const j = J(c); if (j && okCode(j) && j.data) { out.va.ad = num(j.data.total); out.va.ad5 = (j.data.list || []).slice(0, 5).map(r => [num(r.sold_count), num(r.sale_amount), num(r.play_cnt)]); } break; }
      }
    }
    out.k = key;
    return out;
  };

  X.run = async (list, gap) => {
    X.stop = false; X.state = 'running';
    for (const [sid, key] of list) {
      if (X.stop) break;
      if (X.res[sid]) continue;
      let r;
      try { r = await X.one(sid, key); } catch (e) { r = {e: 'ex-' + String(e && e.message).slice(0, 30)}; }
      if (r.e) { X.err[sid] = r.e; if (/^code-/.test(r.e)) { X.state = 'halted ' + sid + ' ' + r.e; return; } }
      else { X.res[sid] = r; delete X.err[sid]; }
      X.done++;
      await sleep((gap || 2500) + Math.random() * 1500);
    }
    X.state = X.stop ? 'stopped' : 'done';
  };

  // 시장 — 주 보기(date_type 2). weeks = ['2026-47', …]
  X.market = async (weeks, pcid) => {
    X.state = 'market';
    for (const w of weeks) {
      if (X.stop) break;
      if (X.mk[w]) continue;
      const n0 = window.__cap.length;
      window.next.router.push('/ko/market/market-pulse?tab=1&l1_cid=' + (pcid || 14) + '&date_type=2&date_value=' + w);
      let c = null;
      for (let i = 0; i < 30 && !c; i++) { await sleep(300); c = window.__cap.slice(n0).find(c => /marketOverview/.test(c.u) && c.u.includes('date_value=' + w)); }
      const j = c && J(c);
      if (!j) { X.err['mk' + w] = 'no-response'; continue; }
      if (!okCode(j)) { X.err['mk' + w] = 'code-' + j.code; X.state = 'halted market ' + w + ' ' + j.code; return; }
      const d = j.data || {};
      X.mk[w] = {avg: num(d.summary && d.summary.avg_sale_amount), l: (d.list || []).map(r => [r.date, r.sold_count, r.sold_product_count, r.new_product_count, r.author_cnt, r.video_cnt, r.live_cnt])};
      await sleep(2200 + Math.random() * 1200);
    }
    X.state = X.stop ? 'stopped' : 'market done';
  };

  const b36 = x => { const v = Math.round(+x || 0); return v < 0 ? '-' + (-v).toString(36) : v.toString(36); };
  const g = (o, k) => (o && o[k]) || 0;
  const ymd = t => { const m = String(t || '').match(/^20(\d\d)-(\d\d)-(\d\d)/); return m ? m[1] + m[2] + m[3] : ''; };
  const yLine = (id, r) => {
    const ch = r.ch || {}, ct = r.ct || {}, au = r.au || {}, va = r.va || {}, vs = r.vs || {}, ls = r.ls || {};
    const n = [g(r.b, 'pc'), g(ch.u, 'product_card'), g(ch.u, 'shop_account'), g(ch.u, 'affiliate'), g(ch.v, 'product_card'), g(ch.v, 'shop_account'), g(ch.v, 'affiliate'),
      g(ct.u, 'video'), g(ct.u, 'live'), g(ct.u, 'card'), g(ct.v, 'video'), g(ct.v, 'live'), g(ct.v, 'card'),
      g(au, 'n'), g(au, 'nv'), g(au, 'nl'), g(au, 'nn'), g(au, 'u'), g(au, 'v'), g(va, 'all'), g(va, 'ad'), g(vs, 'u'), g(vs, 'v'), g(vs, 'p'),
      g(ls, 'total_count'), g(ls, 'sold_count'), g(ls, 'sale_amount')].map(b36).join(',');
    const ta = ((r.ta && r.ta.l) || []).slice(0, 3).map(t => [clean(t[0], 30), b36(t[1]), b36(t[2]), b36(t[3])].join('~')).join(';');
    const tg = ((r.tg && r.tg.l) || []).slice(0, 3).map(t => [t[0], clean(t[1], 40).replace(/~/g, '-'), clean(t[2], 20), ymd(t[3]), b36(t[4]), b36(t[5]), b36(t[6]), b36(t[7]), clean(t[8], 6) || '-'].join('~')).join(';');
    return ['Y', id, r.k, n, ta, tg];
  };
  X.lines = () => {
    const L = [], push = a => { const s = a.join('|'); L.push(s + '|' + crc32(s)); };
    const ids = Object.keys(X.res).sort(), ws = Object.keys(X.mk).sort();
    push(['XH', V, new Date().toISOString().slice(0, 10), ids.length, ws.length]);
    for (const id of ids) push(yLine(id, X.res[id]));
    for (const w of ws) push(['N', w, X.mk[w].avg == null ? '' : b36(X.mk[w].avg * 100),
      X.mk[w].l.map(r => [String(r[0]).slice(5, 7) + String(r[0]).slice(8, 10)].concat(r.slice(1).map(b36)).join(':')).join(',')]);
    for (const id of Object.keys(X.err).sort()) push(['E', id, clean(X.err[id], 30)]);
    L.push(['END', L.length + 1, crc32(L.join('\n'))].join('|'));
    window.__FXLINES = L;   // 나눠 옮기는 동안 줄 번호가 안 바뀌게 고정
    return L;
  };
  X.plan = max => {
    const L = X.lines(), lim = max || 20000, out = []; let a = 0, c = 0;
    L.forEach((l, i) => { if (c + l.length + 1 > lim && i > a) { out.push(a + '-' + i); a = i; c = 0; } c += l.length + 1; });
    out.push(a + '-' + L.length);
    return out.join(',') + ' · lines ' + L.length + ' · chars ' + L.join('\n').length;
  };
  X.dump = (from, to) => {
    const L = window.__FXLINES || X.lines(), a = from || 0, b = Math.min(L.length, to || L.length);
    const pre = document.createElement('pre'); pre.style.cssText = 'white-space:pre-wrap;margin:0;font-size:11px';
    pre.textContent = L.slice(a, b).join('\n');
    document.body.replaceChildren(pre); document.title = 'fx dump';   // get_page_text 가 이 줄들만 읽게
    return 'dumped ' + a + '-' + (b - 1) + ' of ' + L.length;
  };
  window.__FXD = X.dump;
  X.status = () => X.state + ' · shops ' + Object.keys(X.res).length + ' · done ' + X.done + ' · err ' + Object.keys(X.err).length + ' · weeks ' + Object.keys(X.mk).length;
  return 'fx v' + V + ' ready · ' + X.status();
})();
