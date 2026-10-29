/* 호텔 OTA 판매가 수집기 — Google 호텔(google.com/travel) 최저가 · 크롬(사용자 PC)에서만.
   쓰는 법(hotel_adr/RUNBOOK.md): google.com/travel/hotels 탭에서 이 파일을 받아 <script> 로 붙인다.
     ⚠ google.com 은 'unsafe-eval' 이 없어 new Function·eval 이 막히고, Trusted Types 를 강제한다 →
       trustedTypes.createPolicy 로 TrustedScript 를 만들고, 페이지 script 의 nonce 를 빌려 <script> 를 붙여야 돈다(2026-10-29 확인).
   → window.__HOTELOTA.status() 가 done 이 될 때까지(호텔 13 × 날짜 4 ≈ 5분) → window.__HOTELOTA.dump() → get_page_text.
   방식: 같은 출처 iframe 에서 호텔 검색 → 주소의 ts(protobuf)에서 체크인·아웃 날짜만 바꿔 다시 연다 → '가격대 보기'를 눌러 구글 통상가와 판정을 읽는다.
   덤프 한 줄 = O|관측일|호텔키|숙박일|최저가(세금 포함 원)|통상가 하단|상단|판정(보통·높음·낮음)|특가 %|대체 날짜:가격|상태
   (출력에 = & ? 를 쓰지 않는다 — 크롬 도구가 쿼리 문자열로 보고 가린다) */
(() => {
  const HOTELS = [
    ['gic', 'Grand InterContinental Seoul Parnas'], ['westin', 'The Westin Seoul Parnas'], ['pjeju', 'Parnas Hotel Jeju'],
    ['nt_md2', 'Nine Tree by Parnas Seoul Myeongdong II'], ['nt_ddm', 'Nine Tree Hotel Dongdaemun'],
    ['gm_ys', 'Grand Mercure Ambassador Seoul Yongsan'], ['ns_ys', 'Novotel Suites Ambassador Seoul Yongsan'],
    ['nv_ys', 'Novotel Ambassador Seoul Yongsan'], ['is_ys', 'ibis Styles Ambassador Seoul Yongsan'],
    ['shilla_seoul', 'The Shilla Seoul hotel'], ['shilla_jeju', 'The Shilla Jeju'],
    ['stay_ghm', 'Shilla Stay Gwanghwamun'], ['stay_mapo', 'Shilla Stay Mapo'],
  ];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const kst = () => new Date(Date.now() + 9 * 3600e3);                      // KST 를 UTC 칸으로
  const ymd = d => d.toISOString().slice(0, 10);
  const addD = (d, n) => new Date(d.getTime() + n * 864e5);
  const nextDow = (d, dow) => { let x = d; while (x.getUTCDay() !== dow) x = addD(x, 1); return x; };
  function stayDates(only) {
    if (only && only.length) return only;                                   // ['2026-11-11', …] 로 고정 날짜도 된다
    const t = kst(); const a = addD(t, 14), b = addD(t, 45);
    return [nextDow(a, 3), nextDow(a, 6), nextDow(b, 3), nextDow(b, 6)].map(ymd);   // 수·토 × (2주 뒤 · 6주 반 뒤)
  }
  const kd = s => { const [y, m, d] = s.split('-').map(Number); return { y, m, d }; };
  function dateLabel(ci) {                                                  // 화면 표기 '11월 11일~12일' · '11월 30일~12월 1일'
    const a = kd(ci), o = kd(ymd(addD(new Date(ci + 'T00:00:00Z'), 1)));
    return a.m === o.m ? `${a.m}월 ${a.d}일~${o.d}일` : `${a.m}월 ${a.d}일~${o.m}월 ${o.d}일`;
  }
  function withDates(href, ci) {
    const u = new URL(href); let s = (u.searchParams.get('ts') || '').replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '=';
    const b = Uint8Array.from(atob(s), c => c.charCodeAt(0)); const o = [];
    for (let i = 0; i < b.length - 6; i++) { if (b[i] === 8 && b[i + 3] === 16 && b[i + 5] === 24) { const y = (b[i + 1] & 127) + (b[i + 2] << 7); if (y > 2020 && y < 2035) o.push(i); } }
    if (o.length < 2) return null;
    const a = kd(ci), c = kd(ymd(addD(new Date(ci + 'T00:00:00Z'), 1)));
    const st = (p, y, m, d) => { b[p + 1] = (y & 127) | 128; b[p + 2] = y >> 7; b[p + 4] = m; b[p + 6] = d; };
    st(o[0], a.y, a.m, a.d); st(o[1], c.y, c.m, c.d);
    let r = ''; b.forEach(x => r += String.fromCharCode(x)); u.searchParams.set('ts', btoa(r).replace(/=+$/, '')); return u.toString();
  }
  const S = { st: 'idle', i: 0, n: 0, rows: [], log: [], t0: 0, obs: '' };
  async function load(f, url, ok, maxMs) {
    await new Promise(res => { let done = false; f.onload = () => { if (!done) { done = true; res(); } }; f.src = url; setTimeout(() => { if (!done) { done = true; res(); } }, maxMs || 20000); });
    for (let k = 0; k < 40; k++) { let t = ''; try { t = f.contentWindow.document.body.innerText; } catch (e) {} if (ok(t)) return true; await sleep(400); }
    return false;
  }
  function parse(doc, W) {
    const t = doc.body.innerText.replace(/\n+/g, ' | ').replace(/\s+/g, ' ');
    const a = t.indexOf('모든 검색결과 목록으로 돌아가기'); if (a < 0) return { st: 'noentity' };
    const e = t.indexOf('비슷한 호텔', a); const seg = t.slice(a, e > 0 ? e : a + 6000);
    const hs = [...seg.matchAll(/₩([\d,]+) \| (?:\d{4}년 )?(\d+월 \d+일~(?:\d+월 )?\d+일)/g)].find(m => m[2] === W);
    const deal = seg.match(/₩([\d,]+) \| 일반적인 가격 대비 (\d+)% 저렴/);
    const rg = seg.match(/1박당 ₩([\d,]+)~₩([\d,]+)/);
    const lb = (seg.match(/선택한 일정의 가격이 현재 (\S+?)입니다/) || [])[1] || '';
    const alt = seg.match(/(\d+월 \d+일~(?:\d+월 )?\d+일)에 ₩([\d,]+) 가격으로 예약할 수 있습니다/);
    const num = s => s ? s.replace(/,/g, '') : '';
    const price = hs ? num(hs[1]) : deal ? num(deal[1]) : '';
    return { st: price ? 'ok' : alt ? 'soldout' : 'noprice', price, lo: rg ? num(rg[1]) : '', hi: rg ? num(rg[2]) : '', lb, deal: deal ? deal[2] : '', alt: alt ? alt[1].replace(/\s/g, '') + ':' + num(alt[2]) : '' };
  }
  async function run(opt) {
    opt = opt || {}; const dates = stayDates(opt.dates); const hs = opt.only ? HOTELS.filter(h => opt.only.includes(h[0])) : HOTELS;
    S.st = 'run'; S.i = 0; S.n = hs.length * dates.length; S.rows = []; S.log = []; S.t0 = Date.now(); S.obs = ymd(kst()); S.dates = dates;
    const f = document.createElement('iframe'); f.style.cssText = 'width:1280px;height:900px;position:fixed;left:-4000px;top:0;border:0';
    document.body.appendChild(f);
    try {
      for (const [key, q] of hs) {
        const base = '/travel/search?q=' + encodeURIComponent(q) + '&hl=ko&gl=kr&curr=KRW';
        const okE = await load(f, base, t => t.includes('모든 검색결과 목록으로 돌아가기'));
        if (!okE) { dates.forEach(d => S.rows.push([S.obs, key, d, '', '', '', '', '', '', 'noentity'])); S.i += dates.length; S.log.push(key + ' noentity'); continue; }
        for (const d of dates) {
          const url = withDates(f.contentWindow.location.href, d); const W = dateLabel(d);
          if (!url) { S.rows.push([S.obs, key, d, '', '', '', '', '', '', 'nots']); S.i++; continue; }
          await load(f, url, t => t.includes(W) || t.includes('예약할 수 있습니다'));
          await sleep(500);
          try { const btn = [...f.contentWindow.document.querySelectorAll('button')].find(x => /가격대 보기/.test(x.innerText)); if (btn) { btn.click(); await sleep(1100); } } catch (e) {}
          let r = { st: 'err' }; try { r = parse(f.contentWindow.document, W); } catch (e) { r = { st: 'err' }; }
          S.rows.push([S.obs, key, d, r.price || '', r.lo || '', r.hi || '', r.lb || '', r.deal || '', r.alt || '', r.st]); S.i++;
          await sleep(300 + Math.random() * 400);
        }
      }
      S.st = 'done';
    } catch (e) { S.st = 'done'; S.log.push('ERR ' + e.message); }
    finally { f.remove(); }
  }
  window.__HOTELOTA = {
    start: opt => { if (S.st === 'run') return 'already running'; run(opt); return 'started ' + stayDates(opt && opt.dates).join(','); },
    status: () => `${S.st} · ${S.i}/${S.n} · ok ${S.rows.filter(r => r[9] === 'ok').length} · ${Math.round((Date.now() - S.t0) / 1000)}s` + (S.log.length ? ' · ' + S.log.slice(-3).join(' ; ') : ''),
    // Google 은 Trusted Types 를 강제한다 — innerHTML 대입이 막히므로 textContent 로 쓴다
    dump: () => { const body = S.rows.map(r => 'O|' + r.join('|')).join('\n') + `\nEND|${S.obs}|${S.rows.length}`;
      const pre = document.createElement('pre'); pre.id = 'otaDump'; pre.style.whiteSpace = 'pre-wrap'; pre.textContent = body;
      document.body.replaceChildren(pre); return 'dump ' + S.rows.length + ' rows'; },
    rows: () => S.rows,
  };
  window.__HOTELOTA.start(window.__HOTELOTA_OPT);
})();
