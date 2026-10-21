/* K뷰티 국면 지도 — 유럽 아마존(영·독·프·이·스) Keepa Product Finder 수집기 (2026-10-21 · 사용자 "유럽도 아마존 좀 해 주라")
   미국판(phase_keepa.js)과 같은 조건 · 같은 가격 식(바이박스 → 신품 최저가 → 아마존가 · 30·90·180·365일 평균을 달 나이에 맞춰).
   다른 점: 브랜드마다 판매량(u)·판매액(v = 현지 통화 · 파운드/유로)만 · 36진수 압축 · 검산값(H) · n1k·nw·pi·top1 은 안 받는다.

   쓰는 법 (keepa.com 탭 · 사용자 Pro 웹 로그인 · 미국판 필터와 같은 쿼리 · 브랜드 목록에 d'alba · centellian24 를 더 넣는다):
     1) 위 메뉴 나라 버튼(button.knav-mk · United Kingdom / Germany / France / Italy / Spain)을 눌러 도메인을 바꾼다
     2) 쿼리를 sessionStorage 'kbeu_q' 에 두고 location.hash = '#!finder/' + encodeURIComponent(q) → 새로 고침
        ⚠ Keepa 는 새로 고침 때 남의 localStorage 키를 지운다 — 코드·쿼리·결과는 sessionStorage 에 둔다
     3) 이 파일을 javascript_tool 로 붙여 넣고 KBPH.run() → KBPH.status() 를 done:true 까지(45초 넘는 호출은 끊기니 시작과 확인을 나눈다)
     4) KBPH.save('uk') → sessionStorage 'kbeu_uk' · 다섯 나라 다 받으면 본문 <pre> 에 띄워 get_page_text
     5) kbeauty/data/phase/eu/<날짜>.txt 로 옮겨 적고 python3 kbeauty/phase.py (나라마다 H 검산이 틀리면 멈춘다)
   결과 표가 늦게 차서 페이지 수보다 행이 적게 오는 일이 있다(10/21 이·스 2% 모자람) — 다시 받아도 같으면 그대로 둔다. */
window.KBPH={};
(function(K){
  const api=()=>document.querySelector('.ag-root-wrapper').__agComponent.gridApi;
  const MAP={"equalberry":"eqqualberry","clio professional":"clio","d'alba":"d'alba piedmont","centellian24":"centellian 24"};
  K.rows={}; K.done=false; K.log=[];
  K.prices=function(st){ const w=k=>{ if(!st||!st[k]) return -1; for(const i of [18,1,0]){ const v=st[k][i]; if(v>0) return v; } return -1; };
    const p30=w('avg30'),p90=w('avg90'),p180=w('avg180'),p365=w('avg365'),cur=w('current'), ok=(x,r)=>x>0&&r>0&&x<r*3&&x>r/3, a=p30>0?p30:cur;
    let s2=(p90>0&&p30>0)?(90*p90-30*p30)/60:p90; if(!ok(s2,p90)) s2=p90>0?p90:a;
    let s3=(p180>0&&p90>0)?(180*p180-90*p90)/90:p180; if(!ok(s3,p180)) s3=p180>0?p180:s2;
    let s4=(p365>0&&p180>0)?(365*p365-180*p180)/185:p365; if(!ok(s4,p365)) s4=p365>0?p365:s3;
    return [a,s2,s3,s4]; };
  K.collect=function(){ api().forEachNode(n=>{ const d=n.data; if(!d||!d.asin) return; const s=d.stats||{}; const rb=(d.brand||'').toLowerCase();
    K.rows[d.asin]={a:d.asin,rb,b:MAP[rb]||rb,t:(d.title||'').slice(0,70),msh:d.monthlySoldHistory||[],pr:K.prices(s)}; }); };
  K.run=function(){ (async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); K.collect(); const tp=api().paginationGetTotalPages(); K.tp=tp;
    for(let p=1;p<tp;p++){ const b=Object.keys(K.rows).length; api().paginationGoToPage(p);
      for(let w=0;w<40;w++){ await sl(500); K.collect(); if(Object.keys(K.rows).length>b+60) break; }
      await sl(1000); K.collect(); K.log.push(p+':'+Object.keys(K.rows).length); }
    K.done=true; })(); return 'started'; };
  K.px=function(r,j,months){ const p=r.pr||[]; if(!(p[0]>0)) return 0; const age=(Date.now()-(months[j][0]+14*86400000))/86400000;
    const v=j===35||age<=45?p[0]:age<=105?p[1]:age<=195?p[2]:p[3]; return v>0?v:p[0]; };
  K.status=()=>JSON.stringify({n:Object.keys(K.rows).length,tp:K.tp,done:K.done,last:K.log.slice(-2)});
  // 압축 덤프 — 브랜드마다 판매량(u)·판매액(v, 현지 통화 단위)만 · 36진수
  K.save=function(d){
    const KM=k=>(k+21564000)*60000, now=Date.now(), today=new Date(), months=[], ML=[];
    for(let j=35;j>=0;j--){ const x=new Date(Date.UTC(today.getUTCFullYear(),today.getUTCMonth()-j,1)); months.push([x.getTime(),Date.UTC(x.getUTCFullYear(),x.getUTCMonth()+1,1)]); ML.push(x.toISOString().slice(0,7)); }
    const ms=h=>{ const pts=[]; for(let i=0;i<h.length;i+=2) pts.push([KM(h[i]),h[i+1]]);
      return months.map(([s,e])=>{ e=Math.min(e,now); if(e<=s) return 0; let a=0; for(let i=0;i<pts.length;i++){ const x=Math.max(pts[i][0],s), y=Math.min(i+1<pts.length?pts[i+1][0]:now,e); if(y>x) a+=(y-x)*Math.max(pts[i][1],0); } return Math.round(a/(e-s)); }); };
    const B={}, rows=Object.values(K.rows).filter(r=>r.b!=='clio'||r.rb==='clio professional'||(/^clio\b/i.test(r.t)&&!/yogurt|fishing|shower|kayak|grab bar|tarp|clip|foot rest|rod |hot chocolate/i.test(r.t)));
    rows.forEach(r=>{ const m=ms(r.msh), o=B[r.b]=B[r.b]||{u:Array(36).fill(0),v:Array(36).fill(0),n:0}; o.n++;
      for(let j=0;j<36;j++){ o.u[j]+=m[j]; o.v[j]+=m[j]*K.px(r,j,months); } });
    const L=['D|'+d+'|'+new Date().toISOString().slice(0,10)+'|'+ML[0]+'|'+rows.length];
    let h=0;
    Object.keys(B).sort().forEach(k=>{ const o=B[k], v=o.v.map(x=>Math.round(x/100));
      o.u.forEach((x,i)=>{ h=(h+x*(i+1))%1000003; }); v.forEach((x,i)=>{ h=(h+x*(i+7))%1000003; });
      L.push(k+'|'+o.n+'|'+o.u.map(x=>x.toString(36)).join(',')+'|'+v.map(x=>x.toString(36)).join(',')); });
    L.push('H|'+h);
    const t=L.join('\n'); sessionStorage.setItem('kbeu_'+d,t); return d+' brands '+Object.keys(B).length+' rows '+rows.length+' len '+t.length+' h '+h; };
})(window.KBPH);
'ok'
