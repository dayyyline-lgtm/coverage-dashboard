/* 손익 모델(ISM)용 Keepa 브랜드 판매 수집 — keepa.com Product Finder 탭(Pro 로그인 · 오른쪽 위 마켓 .com)에서 javascript_tool 로 붙여 넣는다 (2026-10-25 · 지누스).
   keepa.com 은 CSP 로 외부 fetch 가 막혀 이 파일을 받아 오지 못한다 → 내용을 그대로 붙여 넣을 것. K뷰티(kbeauty/phase_keepa.js)와 같은 판매량 식(배지 아랫값 · 순위 보정 없이).
   ⚠ 데이터 한도는 새 탭에서 볼 것(열어 둔 탭의 Quota 표시는 안 바뀐다 · CLAUDE.md). 하루에 Finder 를 여러 번 통째로 돌리지 말 것.

   0) 브랜드를 정하고 표를 연다:
        window.ZQ={f:{productType:{values:["0"],filterType:"set"},brand:{filterType:"autocomplete",filter:"zinus",type:"isOneOf"},
          monthlySoldPeak:{filterType:"number",type:"greaterThanOrEqual",filter:50,filterTo:null}},s:[{colId:"monthlySold",sort:"desc"}],t:"g"};
        location.hash='#!finder/'+encodeURIComponent(JSON.stringify(window.ZQ));      (2026-10-24 지누스 910개 · 10페이지)
   1) 아래 전체를 붙여 넣으면 ZK.run() 이 페이지를 넘기며 모은다 → ZK.status() 로 done 확인(1분 안팎).
   2) ZK.dump() → 본문 맨 앞 <article id="__dump"> → get_page_text 로 읽어 ism_keepa/<키>.json 에 저장(DUMPSTART·DUMPEND 사이 JSON · 'src' 한 줄 붙임)
      → 합계 대조(브라우저 u·v 합 = 파일 합) → python ism_keepa.py → 화면 '지난 분기 맞히기'로 검산. */
window.ZK={rows:{},done:false,log:[]};
(function(K){
  const api=()=>document.querySelector('.ag-root-wrapper').__agComponent.gridApi;
  K.prices=function(st){ const w=k=>{ if(!st||!st[k]) return -1; for(const i of [18,1,0]){ const v=st[k][i]; if(v>0) return v; } return -1; };
    const p30=w('avg30'),p90=w('avg90'),p180=w('avg180'),p365=w('avg365'),cur=w('current'), ok=(x,r)=>x>0&&r>0&&x<r*3&&x>r/3, a=p30>0?p30:cur;
    let s2=(p90>0&&p30>0)?(90*p90-30*p30)/60:p90; if(!ok(s2,p90)) s2=p90>0?p90:a;
    let s3=(p180>0&&p90>0)?(180*p180-90*p90)/90:p180; if(!ok(s3,p180)) s3=p180>0?p180:s2;
    let s4=(p365>0&&p180>0)?(365*p365-180*p180)/185:p365; if(!ok(s4,p365)) s4=p365>0?p365:s3;
    return [a,s2,s3,s4]; };
  K.collect=function(){ api().forEachNode(n=>{ const d=n.data; if(!d||!d.asin||d.domainId!==1) return; const s=d.stats||{};
    K.rows[d.asin]={a:d.asin,p:d.parentAsin||d.asin,b:(d.brand||'').toLowerCase(),t:(d.title||'').slice(0,60),msh:d.monthlySoldHistory||[],pr:K.prices(s),cat:d.salesRankReference||0,rc:(s.current&&s.current[3])||-1}; }); };
  K.run=function(){ (async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); K.collect(); const tp=api().paginationGetTotalPages();
    for(let p=1;p<tp;p++){ const b=Object.keys(K.rows).length; api().paginationGoToPage(p);
      for(let w=0;w<40;w++){ await sl(500); K.collect(); if(Object.keys(K.rows).length>b+60) break; }
      await sl(1000); K.collect(); K.log.push(p+':'+Object.keys(K.rows).length); }
    K.done=true; })(); return 'started'; };
  K.px=function(r,j,months){ const p=r.pr||[]; if(!(p[0]>0)) return 0; const age=(Date.now()-(months[j][0]+14*86400000))/86400000;
    const v=j===35||age<=45?p[0]:age<=105?p[1]:age<=195?p[2]:p[3]; return v>0?v:p[0]; };
  K.status=()=>JSON.stringify({n:Object.keys(K.rows).length,done:K.done,last:K.log.slice(-2)});
  // 그달 판매량 = 그달 마지막 7일 배지 중앙값(아랫값) · 판매액 = × 그달 가격(센트 → 달러는 /100) · pc = 가격이 잡힌 판매량 몫(옛 달은 낮다 — 단종 상품 가격 이력 없음)
  K.dump=function(){
    const KM=k=>(k+21564000)*60000, now=Date.now(), today=new Date(), months=[], ML=[];
    for(let j=35;j>=0;j--){ const d=new Date(Date.UTC(today.getUTCFullYear(),today.getUTCMonth()-j,1)); months.push([d.getTime(),Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,1)]); ML.push(d.toISOString().slice(0,7)); }
    const ms=h=>{ const pts=[]; for(let i=0;i<h.length;i+=2) pts.push([KM(h[i]),h[i+1]]);
      const at=t=>{ let v=0; for(let i=0;i<pts.length&&pts[i][0]<=t;i++) v=Math.max(pts[i][1],0); return v; };
      return months.map(([s,e])=>{ e=Math.min(e,now); if(e<=s) return 0; const a=[]; for(let k=0;k<7;k++){ const t=e-1-k*86400000; if(t<s) break; a.push(at(t)); }
        a.sort((x,y)=>x-y); const n=a.length; return n?Math.round(n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2):0; }); };
    const rows=Object.values(K.rows), u=Array(36).fill(0), v=Array(36).fill(0), up=Array(36).fill(0), cat={}, br={};
    rows.forEach(r=>{ r.m=ms(r.msh); br[r.b]=(br[r.b]||0)+1;
      for(let j=0;j<36;j++){ const x=r.m[j]; u[j]+=x; const p=K.px(r,j,months); v[j]+=x*p; if(p>0) up[j]+=x; const c=cat[r.cat]=cat[r.cat]||Array(36).fill(0); c[j]+=x*p; } });
    const top=rows.map(r=>({a:r.a,t:r.t.slice(0,44),q:r.m[32]+r.m[33]+r.m[34],u:r.m[34],p:Math.round((r.pr[0]||0))})).sort((a,b)=>b.q-a.q).slice(0,12);
    const atK=(h,t)=>{ let x=0; for(let i=0;i<h.length;i+=2){ if(KM(h[i])>t) break; x=Math.max(h[i+1],0); } return x; };
    const r30=[0,30,365,395].map(d=>rows.reduce((s,r)=>s+atK(r.msh,now-d*86400000),0));
    const catv={}; Object.entries(cat).forEach(([k,a])=>{ const q=a[32]+a[33]+a[34]; if(q>0) catv[k]=a.map(x=>Math.round(x/100)); });
    const out={asOf:new Date().toISOString().slice(0,10),months:ML,partial:ML[35],nsku:rows.length,brands:br,u,v:v.map(x=>Math.round(x/100)),pc:u.map((x,j)=>x?Math.round(up[j]/x*1000)/1000:null),r30,cat:catv,top};
    let el=document.getElementById('__dump'); if(!el){ el=document.createElement('article'); el.id='__dump'; el.style.cssText='position:fixed;top:0;left:0;width:10px;height:10px;overflow:hidden;opacity:0.01;z-index:-1'; document.body.prepend(el); }
    el.textContent='DUMPSTART'+JSON.stringify(out)+'DUMPEND'; return el.textContent.length; };
})(window.ZK);
ZK.run();
