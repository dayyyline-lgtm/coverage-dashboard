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
     (칸 = (연×12+월(0부터)) mod 36 · 2026-09 = 20번 칸 — 진행 중인 달 칸은 달이 끝나야 채워져 3년 전 값이 남아 있다.
     10/22 확인: 배지가 바뀐 달에 순위가 같은 방향으로 움직인 비율이 이 칸 매칭이면 84%, 한 칸 어긋나면 47%) — 화면에선 '최고 순위'를 안 쓰므로(CLAUDE.md) 지금은 집계하지 않는다. */
var BRANDS=["abib","anua","atopalm","axis-y","beauty of joseon","belif","biodance","celimax","centellian 24","clio","clio professional","cosrx","d'alba piedmont","dr.althea","eqqualberry","equalberry","goodal","haruharu","innisfree","isntree","laneige","ma:nyo","medi-peel","medicube","missha","mixsoon","numbuzin","peripera","real barrier","rejuran","rom&nd","round lab","skin1004","some by mi","sulwhasoo","tonymoly","torriden","vt cosmetics","zeroid"];
var KBPH_QUERY={f:{productType:{values:["0"],filterType:"set"},brand:{filterType:"autocomplete",filter:BRANDS.join("###"),type:"isOneOf"},monthlySoldPeak:{filterType:"number",type:"greaterThanOrEqual",filter:50,filterTo:null}},s:[{colId:"monthlySold",sort:"desc"}],t:"g"};
window.KBPH=window.KBPH||{};
(function(K){
  const api=()=>document.querySelector('.ag-root-wrapper').__agComponent.gridApi;
  K.rows={}; K.done=false; K.log=[];
  K.collect=function(){ api().forEachNode(n=>{ const d=n.data; if(!d||!d.asin||d.domainId!==1) return; const s=d.stats||{}, g=(a,i)=>a&&a[i]!=null?a[i]:-1;
    K.rows[d.asin]={a:d.asin,p:d.parentAsin||d.asin,rb:(d.brand||'').toLowerCase(),b:(b=>b==='equalberry'?'eqqualberry':b==='clio professional'?'clio':b)((d.brand||'').toLowerCase()),t:(d.title||'').slice(0,70),msh:d.monthlySoldHistory||[],
      bb:[g(s.current,18),g(s.avg90,18),g(s.avg365,18)],pr:K.prices(s),cat:d.salesRankReference||0,hr:d.historicalSalesRankAverages||[],r30:(s.avg30&&s.avg30[3])||-1,rc:(s.current&&s.current[3])||-1,
      bx:(h=>({s:h.length?String(h[h.length-1]):'',t:h.length>1?+h[h.length-2]:0}))(d.buyBoxSellerIdHistory||[]),no:d.COUNT_NEW_current==null?-1:d.COUNT_NEW_current}; }); };
  // 가격(센트) — 바이박스 → 신품 최저 → 아마존가 · 30·90·180·365일 평균을 구간으로 풀어 달 나이에 맞춘다(kbeauty/keepa.js 와 같은 식 · 2026-10-21 금액 환산)
  K.prices=function(st){ const w=k=>{ if(!st||!st[k]) return -1; for(const i of [18,1,0]){ const v=st[k][i]; if(v>0) return v; } return -1; };
    const p30=w('avg30'),p90=w('avg90'),p180=w('avg180'),p365=w('avg365'),cur=w('current'), ok=(x,r)=>x>0&&r>0&&x<r*3&&x>r/3, a=p30>0?p30:cur;
    let s2=(p90>0&&p30>0)?(90*p90-30*p30)/60:p90; if(!ok(s2,p90)) s2=p90>0?p90:a;
    let s3=(p180>0&&p90>0)?(180*p180-90*p90)/90:p180; if(!ok(s3,p180)) s3=p180>0?p180:s2;
    let s4=(p365>0&&p180>0)?(365*p365-180*p180)/185:p365; if(!ok(s4,p365)) s4=p365>0?p365:s3;
    return [a,s2,s3,s4]; };
  K.run=function(){ (async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); K.collect(); const tp=api().paginationGetTotalPages();
    for(let p=1;p<tp;p++){ const b=Object.keys(K.rows).length; api().paginationGoToPage(p);
      for(let w=0;w<40;w++){ await sl(500); K.collect(); if(Object.keys(K.rows).length>b+60) break; }
      await sl(1000); K.collect(); K.log.push(p+':'+Object.keys(K.rows).length); }
    K.done=true; })(); return 'started'; };
  // 그달 가격(센트) — 달 가운데가 오늘에서 며칠 전인가로 구간을 고른다 · 1년 넘은 달은 185~365일 전 평균(그 앞 가격 이력은 Finder 행에 없다) · 가격을 모르면 0
  K.px=function(r,j,months){ const p=r.pr||[]; if(!(p[0]>0)) return 0; const age=(Date.now()-(months[j][0]+14*86400000))/86400000;
    const v=j===35||age<=45?p[0]:age<=105?p[1]:age<=195?p[2]:p[3]; return v>0?v:p[0]; };
  K.status=()=>JSON.stringify({n:Object.keys(K.rows).length,done:K.done,last:K.log.slice(-2)});  // ⚠ 마켓이 .com 이 아니면(유럽·일본 수집 뒤 그대로면) 행이 하나도 안 잡힌다 — 오른쪽 위 마켓 선택을 .com 으로(2026-10-22 일본 표를 미국으로 읽을 뻔했다)
  K.dump=function(){
    const KM=k=>(k+21564000)*60000, now=Date.now(), today=new Date(), months=[], ML=[];
    for(let j=35;j>=0;j--){ const d=new Date(Date.UTC(today.getUTCFullYear(),today.getUTCMonth()-j,1)); months.push([d.getTime(),Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,1)]); ML.push(d.toISOString().slice(0,7)); }
    // 그달 판매량 = 그달 마지막 7일 배지의 중앙값(2026-10-22) — 배지는 '지난 30일 구매'라 월말 값이 곧 그달 한 달치다(kbeauty/keepa.js 와 같은 식).
    //   예전엔 그달 동안의 배지를 시간 평균했는데, 그러면 반 달 밀려 6월 하순 프라임데이가 7월로 넘어갔다(라네즈 2026-06 14.6만 → 7월 38.7만 · 월말식 42.1만 → 12.0만).
    //   진행 중인 달 = 지금까지 마지막 7일(= 최근 30일 한 달치).
    const ms=h=>{ const pts=[]; for(let i=0;i<h.length;i+=2) pts.push([KM(h[i]),h[i+1]]);
      const at=t=>{ let v=0; for(let i=0;i<pts.length&&pts[i][0]<=t;i++) v=Math.max(pts[i][1],0); return v; };
      return months.map(([s,e])=>{ e=Math.min(e,now); if(e<=s) return 0; const a=[]; for(let k=0;k<7;k++){ const t=e-1-k*86400000; if(t<s) break; a.push(at(t)); }
        a.sort((x,y)=>x-y); const n=a.length; return n?Math.round(n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2):0; }); };
    const B={}, rows=Object.values(K.rows).filter(r=>r.b!=='clio'||r.rb==='clio professional'||(/^clio\b/i.test(r.t)&&!/yogurt|fishing|shower|kayak|grab bar|tarp|clip|foot rest|rod |hot chocolate/i.test(r.t)));
    rows.forEach(r=>{ r.mf=ms(r.msh); r.m=r.mf.slice(); for(let i=1;i<r.msh.length;i+=2) if(r.msh[i]>0){ r.first=KM(r.msh[i-1]); break; } });
    // ── 배지 구간 안의 위치를 순위로 정한다(2026-10-22 · 사용자 "구간이 거칠다 — 20~30% 변화가 안 보인다") ──
    //   배지 = 구간 아랫값(50·100·200…900·1천·2천…9천·1만·2만…·10만+). 구간 안 어디쯤인지는 그달 평균 판매 순위(historicalSalesRankAverages · 이번 달 = 30일 평균)로 정한다:
    //   ① 순위 → 판매량 곡선(꺾은 멱함수 · 20~3만 위 · 최근 12개 완결 달 · 구간 가운데값에 맞춤) ② 상품(부모)마다 수준 보정(그 상품의 '가운데값 ÷ 곡선' 중앙값 —
    //   카테고리·옵션 차이를 흡수) ③ 보정한 곡선값을 그달 배지 구간 [아랫값, 윗값) 안으로 자른다. 배지가 없는 달(50개 미만)은 0 그대로.
    //   옵션(자식 ASIN)이 순위를 같이 쓰면 묶음 단위로 구간을 더해 자르고 아랫값 비율로 나눈다.
    //   검증(10/22 미국 3,544개): 이웃 달을 뺀 보정으로 그달 구간을 맞힌 비율 54%(직전 달 구간을 그대로 쓰면 37%) · 중앙 오차 17%(직전 달 26%) ·
    //   배지가 그대로인데 순위가 15% 넘게 움직인 경우 다음 달 배지가 움직인 방향이 순위 쪽 70%.
    { const hiOf=v=>v<100?100:v<1000?v+100:v<10000?v+1000:v<100000?v+10000:v*2, X0=Math.log(1000), XL=Math.log(20), XH=Math.log(30000);
      const rkOf=(r,j)=>{ let x; if(j<35){ const d=new Date(months[j][0]); const M=d.getUTCFullYear()*12+d.getUTCMonth(); x=(r.hr||[])[((M%36)+36)%36]; } else x=r.r30>0?r.r30:r.rc; return x>0?x:0; };
      rows.forEach(r=>{ r.rk=[]; for(let j=0;j<36;j++) r.rk.push(rkOf(r,j)); });
      const grp=j=>{ const g={}; rows.forEach(r=>{ const rk=r.rk[j]; if(!(rk>0)||!(r.mf[j]>0)) return; const k=r.p+'|'+Math.round(rk); const o=g[k]=g[k]||{p:r.p,rk,lo:0,hi:0,kids:[]}; o.lo+=r.mf[j]; o.hi+=hiOf(r.mf[j]); o.kids.push(r); }); return Object.values(g); };
      const G=[]; for(let j=0;j<36;j++) G.push(grp(j));
      const bins={}; for(let j=23;j<35;j++) G[j].forEach(g=>{ if(g.lo<50||g.rk<20||g.rk>30000) return; const x=Math.log(g.rk), b=Math.floor(x/0.25); (bins[b]=bins[b]||[]).push(Math.log(Math.sqrt(g.lo*g.hi))); });
      const pts=[]; for(const b in bins){ const ys=bins[b].sort((p,q)=>p-q); if(ys.length<6) continue; pts.push([(+b+0.5)*0.25,ys[ys.length>>1],Math.sqrt(ys.length)]); }
      const S=[[0,0,0],[0,0,0],[0,0,0]],T=[0,0,0]; pts.forEach(([x,y,w])=>{ const z=[1,Math.min(x,X0),Math.max(0,x-X0)]; for(let i=0;i<3;i++){ T[i]+=w*z[i]*y; for(let k=0;k<3;k++) S[i][k]+=w*z[i]*z[k]; } });
      const det3=m=>m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
      const D=det3(S), C=Math.abs(D)>1e-9?[0,1,2].map(k=>det3(S.map((row,i)=>row.map((v,q)=>q===k?T[i]:v)))/D):null;
      if(C&&pts.length>=6){ const f=x=>Math.exp(C[0]+C[1]*Math.min(x,X0)+C[2]*Math.max(0,x-X0));
        const cur=r=>{ const x=Math.log(r); return x<XL?f(XL)*Math.pow(20/r,0.35):x>XH?f(XH)*Math.pow(30000/r,1.4):f(x); };
        const off={}; for(let j=0;j<35;j++) G[j].forEach(g=>{ if(g.lo<50) return; (off[g.p]=off[g.p]||[]).push(Math.log(Math.sqrt(g.lo*g.hi)/cur(g.rk))); });
        const ko={}; for(const p in off){ const a=off[p].sort((x,y)=>x-y); ko[p]=a.length>=4?a[a.length>>1]:0; }
        let nIn=0,nAll=0; for(let j=0;j<36;j++) G[j].forEach(g=>{ const e=Math.min(Math.max(Math.exp(ko[g.p]||0)*cur(g.rk),g.lo),g.hi*0.999); nAll++; if(e>g.lo&&e<g.hi*0.999) nIn++; g.kids.forEach(r=>{ r.m[j]=Math.round(e*r.mf[j]/g.lo); }); });
        K.fit={a:+C[0].toFixed(3),b1:+C[1].toFixed(3),b2:+C[2].toFixed(3),bins:pts.length,inb:+(nIn/nAll).toFixed(3)}; }
    }
    rows.forEach(r=>{ const o=B[r.b]=B[r.b]||{u:Array(36).fill(0),uf:Array(36).fill(0),v:Array(36).fill(0),up:Array(36).fill(0),n1k:Array(36).fill(0),nw:Array(36).fill(0),pw:[0,0],nsku:0,top:null}; o.nsku++;
      const f=r.first?((new Date(r.first).getUTCFullYear()*12+new Date(r.first).getUTCMonth())-(new Date(months[0][0]).getUTCFullYear()*12+new Date(months[0][0]).getUTCMonth())):99;
      for(let j=0;j<36;j++){ const u=r.m[j]; o.u[j]+=u; o.uf[j]+=r.mf[j]; const px=K.px(r,j,months); o.v[j]+=u*px; if(px>0) o.up[j]+=u; if(u>=1000) o.n1k[j]++; if(f<=j&&f>=j-11) o.nw[j]+=u; }
      const w=r.m[33]+r.m[34]; if(r.bb[0]>0&&r.bb[2]>0){ o.pw[0]+=w*r.bb[0]; o.pw[1]+=w*r.bb[2]; }
      const q=r.m[32]+r.m[33]+r.m[34]; if(!o.top||q>o.top.q) o.top={asin:r.a,t:r.t.slice(0,42),u:r.m[34],q}; });
    // 바이박스 없음·품절(2026-10-22 · 사용자 '센텔리안24 판매량 40% 가 바이박스 없음 — 무슨 이슈냐') — 최근 30일 판매량(r.m[35]) 기준으로 센다.
    //   품절 = 신품 판매자 0 · 바이박스 없음 = 판매자는 있는데 바이박스가 비어 있다(-1·-2 · 아마존이 '장바구니'를 내린 상태 — 가격 비교 등으로 억제).
    //   둘 다 장바구니 버튼이 없어 판매가 줄어든다. 행이 수집 시점 상태라 한 번의 스냅샷이다.
    const BX={}; rows.forEach(r=>{ const u=r.m[35]; if(!(u>0)||!r.bx) return; const sup=(r.bx.s==='-1'||r.bx.s==='-2')&&r.no>0&&r.bx.t&&(now-KM(r.bx.t))>=3*86400000, oos=r.no===0; if(!sup&&!oos) return;  // 억제는 3일 넘게 이어진 것만(2026-10-22 — 센텔리안24 마데카 크림이 하루 억제됐다 돌아온 걸 '판매가 꺾인다'로 경고했다 · Keepa 30일 바이박스 통계로 억제·품절 4%뿐)
      const o=BX[r.b]=BX[r.b]||{s:0,o:0,top:null}; if(oos) o.o+=u; else o.s+=u; if(!o.top||u>o.top.u) o.top={asin:r.a,t:r.t.slice(0,42),u,k:oos?'o':'s',since:r.bx.t?new Date(KM(r.bx.t)).toISOString().slice(0,10):'',n:r.no}; });
    const out={asOf:new Date().toISOString().slice(0,10),months:ML,partial:ML[35],fit:K.fit||null,b:{}};
    for(const k in B){ const o=B[k]; out.b[k]={u:o.u,uf:o.uf,v:o.v.map(x=>Math.round(x/100)),pc:o.u[34]?Math.round(o.up[34]/o.u[34]*1000)/1000:null,n1k:o.n1k,nw:o.nw,pi:o.pw[1]?Math.round(o.pw[0]/o.pw[1]*1000)/1000:null,nsku:o.nsku,top1:o.top?{asin:o.top.asin,t:o.top.t,u:o.top.u}:null,bx:BX[k]?{s:BX[k].s,o:BX[k].o,top:BX[k].top}:null}; }
    let el=document.getElementById('__dump'); if(!el){ el=document.createElement('article'); el.id='__dump'; el.style.cssText='position:fixed;top:0;left:0;width:10px;height:10px;overflow:hidden;opacity:0.01;z-index:-1'; document.body.appendChild(el); }
    el.textContent='DUMPSTART'+JSON.stringify(out)+'DUMPEND'; return el.textContent.length; };
})(window.KBPH);
/* 이퀄베리는 아마존 브랜드 표기가 둘(EQQUALBERRY · 새 제품 EQUALBERRY)이라 수집 때 하나로 합친다(2026-10-21).
   덤프의 b[브랜드] 에는 ko(한글 이름)·co(상장사)가 없다 — 저장할 때 직전 kbeauty/data/phase/*.json 에서 옮겨 붙일 것(새 브랜드면 손으로). */
