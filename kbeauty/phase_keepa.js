/* K뷰티 브랜드 국면 지도(KBPH) 수집 — keepa.com Product Finder 탭에서 javascript_tool 로 붙여 넣는다 (2026-10-21).
   keepa.com 은 CSP 로 외부 fetch 가 막혀 있어 이 파일을 받아 오지 못한다 → 내용을 그대로 붙여 넣을 것.

   0) 결과 표를 연다 — 주소 해시에 필터를 직접 넣는다(브랜드 = config 아래 BRANDS · 역대 월판매 피크 ≥ 50):
        location.hash = '#!finder/' + encodeURIComponent(JSON.stringify(KBPH_QUERY))
      (KBPH_QUERY 는 아래. BSR 로 거르지 않는다 — 지금 순위로 거르면 '예전엔 팔렸지만 지금 죽은 SKU'가 빠져 과거가 과소계상된다)
   1) 표가 차면 KBPH.run() → 33페이지 안팎을 백그라운드로 넘기며 행(상품 객체)을 모은다. KBPH.status() 로 진행 확인.
   2) KBPH.dump() → 본문 맨 앞 <article id="__dump"> 에 브랜드 × 월 집계 JSON 을 띄운다 → get_page_text 로 읽어
      kbeauty/data/phase/<날짜>.json 에 저장(형식은 2026-10-20.json) → python3 kbeauty/phase.py
   ⚠ javascript_tool 반환은 1천 자 남짓에서 잘리고 '= & ? ;' 가 든 반환은 가려진다 — 덤프는 꼭 get_page_text 로.
   ⚠ CLIO 는 동명 브랜드(요거트바·낚싯대 거치대·방수포 집게·샤워 발판)가 섞이고 카테고리(salesRankReference)로도 안 갈린다 — 제목이 'CLIO'로 시작하는 화장품만 남긴다(2026-10-21 · 110개 중 17개).
     클리오 본 상품은 브랜드 표기가 'CLIO PROFESSIONAL' 이다(킬래쉬 마스카라·프로 아이 팔레트·킬커버 쿠션 — 2025-04 부터 거의 다 이쪽) → 받아서 clio 로 합친다(제목 거르기 없이).
   ⚠ 행의 monthlySoldHistory 는 '바뀐 날만' 찍힌 계단 이력이다(마지막 값이 오늘까지 이어진다). historicalSalesRankAverages 는 36칸 순환 버퍼
     (인덱스 20 = 이번 달) — 화면에선 '최고 순위'를 안 쓰므로(CLAUDE.md) 지금은 집계하지 않는다. */
var BRANDS=["abib","anua","axis-y","beauty of joseon","belif","biodance","celimax","centellian 24","clio","clio professional","cosrx","d'alba piedmont","dr.althea","eqqualberry","equalberry","goodal","haruharu","innisfree","isntree","laneige","ma:nyo","medi-peel","medicube","missha","mixsoon","numbuzin","peripera","rejuran","rom&nd","round lab","skin1004","some by mi","sulwhasoo","tonymoly","torriden","vt cosmetics"];
var KBPH_QUERY={f:{productType:{values:["0"],filterType:"set"},brand:{filterType:"autocomplete",filter:BRANDS.join("###"),type:"isOneOf"},monthlySoldPeak:{filterType:"number",type:"greaterThanOrEqual",filter:50,filterTo:null}},s:[{colId:"monthlySold",sort:"desc"}],t:"g"};
window.KBPH=window.KBPH||{};
(function(K){
  const api=()=>document.querySelector('.ag-root-wrapper').__agComponent.gridApi;
  K.rows={}; K.done=false; K.log=[];
  K.collect=function(){ api().forEachNode(n=>{ const d=n.data; if(!d||!d.asin) return; const s=d.stats||{}, g=(a,i)=>a&&a[i]!=null?a[i]:-1;
    K.rows[d.asin]={a:d.asin,p:d.parentAsin||d.asin,rb:(d.brand||'').toLowerCase(),b:(b=>b==='equalberry'?'eqqualberry':b==='clio professional'?'clio':b)((d.brand||'').toLowerCase()),t:(d.title||'').slice(0,70),msh:d.monthlySoldHistory||[],
      bb:[g(s.current,18),g(s.avg90,18),g(s.avg365,18)],cat:d.salesRankReference||0}; }); };
  K.run=function(){ (async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); K.collect(); const tp=api().paginationGetTotalPages();
    for(let p=1;p<tp;p++){ const b=Object.keys(K.rows).length; api().paginationGoToPage(p);
      for(let w=0;w<40;w++){ await sl(500); K.collect(); if(Object.keys(K.rows).length>b+60) break; }
      await sl(1000); K.collect(); K.log.push(p+':'+Object.keys(K.rows).length); }
    K.done=true; })(); return 'started'; };
  K.status=()=>JSON.stringify({n:Object.keys(K.rows).length,done:K.done,last:K.log.slice(-2)});
  K.dump=function(){
    const KM=k=>(k+21564000)*60000, now=Date.now(), today=new Date(), months=[], ML=[];
    for(let j=35;j>=0;j--){ const d=new Date(Date.UTC(today.getUTCFullYear(),today.getUTCMonth()-j,1)); months.push([d.getTime(),Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,1)]); ML.push(d.toISOString().slice(0,7)); }
    const ms=h=>{ const pts=[]; for(let i=0;i<h.length;i+=2) pts.push([KM(h[i]),h[i+1]]);
      return months.map(([s,e])=>{ e=Math.min(e,now); if(e<=s) return 0; let a=0; for(let i=0;i<pts.length;i++){ const x=Math.max(pts[i][0],s), y=Math.min(i+1<pts.length?pts[i+1][0]:now,e); if(y>x) a+=(y-x)*Math.max(pts[i][1],0); } return Math.round(a/(e-s)); }); };
    const B={}, rows=Object.values(K.rows).filter(r=>r.b!=='clio'||r.rb==='clio professional'||(/^clio\b/i.test(r.t)&&!/yogurt|fishing|shower|kayak|grab bar|tarp|clip|foot rest|rod |hot chocolate/i.test(r.t)));
    rows.forEach(r=>{ r.m=ms(r.msh); for(let i=1;i<r.msh.length;i+=2) if(r.msh[i]>0){ r.first=KM(r.msh[i-1]); break; } });
    rows.forEach(r=>{ const o=B[r.b]=B[r.b]||{u:Array(36).fill(0),n1k:Array(36).fill(0),nw:Array(36).fill(0),pw:[0,0],nsku:0,top:null}; o.nsku++;
      const f=r.first?((new Date(r.first).getUTCFullYear()*12+new Date(r.first).getUTCMonth())-(new Date(months[0][0]).getUTCFullYear()*12+new Date(months[0][0]).getUTCMonth())):99;
      for(let j=0;j<36;j++){ const u=r.m[j]; o.u[j]+=u; if(u>=1000) o.n1k[j]++; if(f<=j&&f>=j-11) o.nw[j]+=u; }
      const w=r.m[33]+r.m[34]; if(r.bb[0]>0&&r.bb[2]>0){ o.pw[0]+=w*r.bb[0]; o.pw[1]+=w*r.bb[2]; }
      const q=r.m[32]+r.m[33]+r.m[34]; if(!o.top||q>o.top.q) o.top={asin:r.a,t:r.t.slice(0,42),u:r.m[34],q}; });
    const out={asOf:new Date().toISOString().slice(0,10),months:ML,partial:ML[35],b:{}};
    for(const k in B){ const o=B[k]; out.b[k]={u:o.u,n1k:o.n1k,nw:o.nw,pi:o.pw[1]?Math.round(o.pw[0]/o.pw[1]*1000)/1000:null,nsku:o.nsku,top1:o.top?{asin:o.top.asin,t:o.top.t,u:o.top.u}:null}; }
    let el=document.getElementById('__dump'); if(!el){ el=document.createElement('article'); el.id='__dump'; el.style.cssText='position:fixed;top:0;left:0;width:10px;height:10px;overflow:hidden;opacity:0.01;z-index:-1'; document.body.appendChild(el); }
    el.textContent='DUMPSTART'+JSON.stringify(out)+'DUMPEND'; return el.textContent.length; };
})(window.KBPH);
/* 이퀄베리는 아마존 브랜드 표기가 둘(EQQUALBERRY · 새 제품 EQUALBERRY)이라 수집 때 하나로 합친다(2026-10-21).
   덤프의 b[브랜드] 에는 ko(한글 이름)·co(상장사)가 없다 — 저장할 때 직전 kbeauty/data/phase/*.json 에서 옮겨 붙일 것(새 브랜드면 손으로). */
