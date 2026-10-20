/* kbeauty/fastmoss.js — FastMoss(틱톡샵) 샵 일별 판매 수집기 (2026-10-20)
   fastmoss.com 탭 안에서 돈다 — 사용자 Pro 로그인 세션의 화면이 부르는 요청을 '엿듣기'만 한다(요청을 직접 만들지 않는다).
   10/20 오후에 화면 데이터 API 를 직접 여러 번 부르다 슬라이드 캡차가 떴다 — 그래서 화면이 스스로 부르게 하고 응답만 받는다.
   Pro 한도: 상세 페이지 500회/일 · 이력 180일 · 검색 300회/일. 샵 하나 = 상세 1회.

   불러오기 — fastmoss.com 은 CSP 가 eval·new Function 을 막고 인라인 스크립트는 허용한다(unsafe-inline) · raw.githubusercontent fetch 는 열려 있다:
     처음 한 번: localStorage.setItem('fmx_code', await (await fetch('https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/<커밋>/kbeauty/fastmoss.js')).text())
     페이지마다: const s=document.createElement('script'); s.textContent=localStorage.getItem('fmx_code'); document.head.appendChild(s)
   한 샵(크롬 도구가 하는 일):
     navigate https://www.fastmoss.com/ko/shop-marketing/detail/<seller_id> → 5초 → 불러오기 → await window.__FMX.grab('<seller_id>','<지역>','<브랜드키>')
   잠긴 지역(구독 밖 · grab 이 'locked' 을 돌려준다): 검색 화면(region=<지역>&words=<브랜드>)에서 window.__FMX.snapRow('<seller_id>','<지역>','<브랜드키>')
   다 돌면: window.__FMX.plan() → dump(a,b) → get_page_text → 파일 → kbeauty/ingest.py
   샵 찾기: navigate https://www.fastmoss.com/ko/shop-marketing/search?region=US&words=<브랜드> → javascript_tool: await window.__FMX.find()

   덤프 줄(마지막 칸 CRC32 36진수):
     FH|v|날짜|샵 수
     S|seller_id|지역|브랜드키|통화|샵 이름|첫날
     D|seller_id|첫날|판매량…|판매액…     ← 일별(36진수 · 판매액은 통화 단위 반올림)
     W|seller_id|지역|브랜드키|날짜|7일 판매량|7일 판매액 USD|누적 판매액 USD|이름   ← 잠긴 지역 검색 목록 스냅샷(snapRow · 36진수)
     E|seller_id|사유
     END|줄 수|crc
*/
(function () {
  'use strict';
  const V = 3;
  const KEY = 'fmx_buf';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; } return t; })();
  const crc32 = str => { const b = new TextEncoder().encode(str); let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC_T[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return ((c ^ 0xFFFFFFFF) >>> 0).toString(36); };
  const clean = (s, n) => String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^\x20-\x7e]/g, '')
    .replace(/[|\r\n\t=&?;,]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n || 40).trim();
  const b36 = n => (n == null || !(n > 0)) ? '' : Math.round(n).toString(36);
  const F = window.__FMX = window.__FMX && window.__FMX.v === V ? window.__FMX : {v: V, cap: []};
  if (!window.__fmxHook) {
    window.__fmxHook = 1;
    const o = XMLHttpRequest.prototype.open, s = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) { this.__u = u; return o.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function () {
      this.addEventListener('load', () => { if (/\/api\/shop\//.test(this.__u || '')) F.cap.push({u: this.__u, t: this.responseText}); });
      return s.apply(this, arguments);
    };
    const f0 = window.fetch;
    window.fetch = async function (i) {
      const r = await f0.apply(this, arguments);
      try { const u = typeof i === 'string' ? i : i.url; if (/\/api\/shop\//.test(u)) r.clone().text().then(t => F.cap.push({u, t})); } catch (e) { /* 무시 */ }
      return r;
    };
  }
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const save = b => { try { localStorage.setItem(KEY, JSON.stringify(b)); } catch (e) { /* 꽉 참 */ } };

  // 지금 샵 상세 페이지에서 '최근 180일'을 눌러 일별 추이를 받는다
  F.grab = async (sid, region, key) => {
    const buf = load(); buf.shops = buf.shops || {}; buf.err = buf.err || {};
    if (!location.pathname.includes('/detail/' + sid)) { buf.err[sid] = 'not-on-page'; save(buf); return 'not on page ' + sid; }
    const btn = re => [...document.querySelectorAll('label, span, div, button')].find(e => e.childElementCount <= 1 && re.test(e.textContent || ''));
    const radio = btn(/^\s*최근\s*180일\s*$/), r7 = btn(/^\s*최근\s*7일\s*$/);
    if (!radio) { buf.err[sid] = 'no-180'; save(buf); return 'no 180 button'; }
    // 이미 180일이 골라져 있으면 다시 눌러도 화면이 안 부른다 — 7일을 먼저 눌렀다가 180일(요청 2건 · 둘 다 화면이 만든다)
    if (r7) { r7.click(); await sleep(1800); }
    F.cap = F.cap.filter(c => !/recentData/.test(c.u));
    radio.click();
    let hit = null;
    for (let i = 0; i < 40 && !hit; i++) { await sleep(300); hit = F.cap.find(c => /recentData/.test(c.u) && c.u.includes(sid) && /d_type\W*180/.test(c.u)); }
    if (!hit) { buf.err[sid] = 'no-response'; save(buf); return 'no response'; }
    let j; try { j = JSON.parse(hit.t); } catch (e) { buf.err[sid] = 'bad-json'; save(buf); return 'bad json'; }
    const L = j && j.data && j.data.list;
    const tr = (L && L.trend) || [];
    if (!tr.length) { buf.err[sid] = 'empty-' + (j && j.code); save(buf); return 'empty ' + (j && j.code); }
    tr.sort((a, b) => String(a.dt).localeCompare(String(b.dt)));
    // 구독 밖 지역은 화면이 흐림 처리되고 API 가 다른 지역의 옛 견본을 준다(10/21 영국·프랑스·말레이시아 → 인도네시아 2024-10 8일치) — 버린다
    const reg = String((L.total_info && L.total_info.region) || tr[0].region || '');
    const lastDt = String(tr[tr.length - 1].dt || '');
    if (region && reg && reg !== region) { delete buf.shops[sid]; buf.err[sid] = 'locked-' + reg; save(buf); return 'locked ' + sid + ' (sample ' + reg + ' ' + tr[0].dt + ') - use snapRow on search page'; }
    if (!(Date.now() - Date.parse(lastDt + 'T00:00:00Z') < 10 * 864e5)) { delete buf.shops[sid]; buf.err[sid] = 'stale-' + lastDt; save(buf); return 'stale ' + sid + ' last ' + lastDt; }
    const name = clean((L.total_info && L.total_info.shop_name) || (document.title || '').split(' TikTok')[0], 40);
    const cur = (L.total_info && L.total_info.currency) || (tr[0] && tr[0].currency) || '';
    const d0 = tr[0].dt, days = [];
    const t0 = Date.parse(d0 + 'T00:00:00Z');
    for (const r of tr) { const i = Math.round((Date.parse(r.dt + 'T00:00:00Z') - t0) / 864e5); days[i] = [r.inc_sold_count || 0, r.inc_sale_amount || 0]; }
    for (let i = 0; i < days.length; i++) if (!days[i]) days[i] = [0, 0];
    buf.shops[sid] = {r: region, k: key, n: name, c: clean(cur, 6) || 'USD', d0, u: days.map(x => b36(x[0])).join(','), v: days.map(x => b36(x[1])).join(',')};
    delete buf.err[sid];
    buf.date = new Date().toISOString().slice(0, 10);
    save(buf);
    const sum = days.reduce((s, x) => s + x[1], 0);
    return 'ok ' + sid + ' ' + name + ' days ' + days.length + ' from ' + d0 + ' gmv ' + Math.round(sum / 1e3) + 'k';
  };

  // 샵 검색 화면 — 화면이 받은 검색 결과를 요약(이름 · ID · 지역 · 최근 7일 판매액 · 누적)
  F.find = async () => {
    for (let i = 0; i < 20 && !F.cap.some(c => /shop\/v3\/search/.test(c.u)); i++) await sleep(300);
    const hit = F.cap.filter(c => /shop\/v3\/search/.test(c.u)).slice(-1)[0];
    if (!hit) return 'no search response — 검색 버튼을 한 번 눌러 주세요';
    const j = JSON.parse(hit.t), L = (j.data && (j.data.list || j.data.data)) || [];
    return L.map(s => [s.seller_id, clean(s.shop_info && s.shop_info.name, 30), s.region, 'd7 ' + Math.round((s.day7_sale_amount || 0) / 1e3) + 'k', 'tot ' + Math.round((s.sale_amount || 0) / 1e6) + 'M', 'type ' + s.shop_type].join(' ')).join(' / ');
  };

  // 검색 화면 — 그려진 결과에서 샵 상세 링크와 줄 글자를 읽는다(훅을 걸기 전에 화면이 이미 검색했을 때)
  F.findDom = () => {
    const seen = {}, out = [];
    document.querySelectorAll('a[href*="/shop-marketing/detail/"]').forEach(a => {
      const m = /detail\/(\d+)/.exec(a.getAttribute('href') || ''); if (!m || seen[m[1]]) return; seen[m[1]] = 1;
      let row = a; for (let i = 0; i < 8 && row.parentElement && (row.innerText || '').length < 60; i++) row = row.parentElement;
      out.push(m[1] + ' ' + clean((row.innerText || '').replace(/\s+/g, ' '), 110));
    });
    return out.length ? out.join(' / ') : 'no shop links';
  };
  // 잠긴 지역 — 검색 화면 목록 줄(최근 7일 판매량·판매액 · 누적 판매액, USD 괄호값)을 스냅샷으로 남긴다(W 줄). 주마다 쌓으면 주간 계열이 된다
  const usd = t => { const m = /\$([\d.,]+)\s*(천|만|억)?/.exec(t || ''); if (!m) return 0; return Math.round(parseFloat(m[1].replace(/,/g, '')) * ({'천': 1e3, '만': 1e4, '억': 1e8}[m[2]] || 1)); };
  const cnt = t => { const m = /^\s*([\d.,]+)\s*(천|만|억)?/.exec(t || ''); if (!m) return 0; return Math.round(parseFloat(m[1].replace(/,/g, '')) * ({'천': 1e3, '만': 1e4, '억': 1e8}[m[2]] || 1)); };
  F.snapRow = (sid, region, key) => {
    const buf = load(); buf.snap = buf.snap || {};
    const tr = [...document.querySelectorAll('tr')].find(r => { const a = r.querySelector('a[href*="/shop-marketing/detail/"]'); return a && (a.getAttribute('href') || '').includes('/detail/' + sid); });
    if (!tr) return 'no row ' + sid;
    const td = [...tr.querySelectorAll('td')].map(x => (x.innerText || '').replace(/\s+/g, ' ').trim());
    const name = clean((td[0] || '').replace(/^브랜드\s*/, ''), 40);
    buf.snap[sid] = {r: region, k: key, n: name, d: new Date().toISOString().slice(0, 10), u7: cnt(td[2]), v7: usd(td[3]), vt: usd(td[7])};
    save(buf);
    const x = buf.snap[sid];
    return 'snap ' + sid + ' ' + name + ' u7 ' + x.u7 + ' v7 $' + x.v7 + ' total $' + x.vt;
  };
  F.reset = () => { localStorage.removeItem(KEY); return 'cleared'; };
  F.lines = () => {
    const buf = load(), L = [], push = a => { const s = a.join('|'); L.push(s + '|' + crc32(s)); };
    const ids = Object.keys(buf.shops || {}).sort();
    push(['FH', V, buf.date || new Date().toISOString().slice(0, 10), ids.length]);
    for (const id of ids) { const x = buf.shops[id]; push(['S', id, x.r, x.k, x.c, x.n, x.d0]); }
    for (const id of ids) { const x = buf.shops[id]; push(['D', id, x.d0, x.u, x.v]); }
    for (const id of Object.keys(buf.snap || {}).sort()) { const x = buf.snap[id]; push(['W', id, x.r, x.k, x.d, b36(x.u7), b36(x.v7), b36(x.vt), x.n]); }
    for (const id of Object.keys(buf.err || {}).sort()) push(['E', id, clean(buf.err[id], 20)]);
    L.push(['END', L.length + 1, crc32(L.join('\n'))].join('|'));
    return L;
  };
  F.plan = max => {
    const L = F.lines(), lim = max || 24000, out = []; let a = 0, c = 0;
    L.forEach((l, i) => { if (c + l.length + 1 > lim && i > a) { out.push(a + '-' + i); a = i; c = 0; } c += l.length + 1; });
    out.push(a + '-' + L.length);
    return out.join(',') + ' · lines ' + L.length + ' · chars ' + L.join('\n').length;
  };
  F.dump = (from, to) => {
    const L = F.lines(), a = from || 0, b = Math.min(L.length, to || L.length);
    document.body.innerHTML = ''; const pre = document.createElement('pre'); pre.id = 'fmxdump'; pre.style.whiteSpace = 'pre-wrap';
    pre.textContent = L.slice(a, b).join('\n'); document.body.appendChild(pre); document.title = 'fmx dump';
    return 'dumped · lines ' + a + '-' + (b - 1) + ' of ' + L.length;
  };
  F.status = () => { const b = load(); return 'shops ' + Object.keys(b.shops || {}).length + ' · err ' + Object.keys(b.err || {}).length + ' · ' + (b.date || '-'); };
  return 'fmx v' + V + ' ready · ' + F.status();
})();
