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
   일본(data-domain 5)·캐나다(6)도 같은 수집기 — 일본은 브랜드 표기에 가타카나가 붙어 쿼리에 그 표기를 더하고 K.collect 에서 라틴 키로 바꾼다(CLAUDE.md '일본·캐나다').
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
    // 일본 표기 'コースアールエックス(cosrx)' 처럼 괄호 안 라틴 이름이 있으면 그걸 키로 · センテリアン24 는 괄호가 없다(2026-10-22)
    const pm=rb.match(/\(([^)]+)\)\s*$/), key=/センテリアン/.test(rb)?'centellian 24':pm?(MAP[pm[1]]||pm[1]):(MAP[rb]||rb);
    K.rows[d.asin]={a:d.asin,p:d.parentAsin||d.asin,rb,b:key,t:(d.title||'').slice(0,70),msh:d.monthlySoldHistory||[],pr:K.prices(s),hr:d.historicalSalesRankAverages||[],r30:(s.avg30&&s.avg30[3])||-1,rc:(s.current&&s.current[3])||-1}; }); };
  K.run=function(){ (async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); K.collect(); const tp=api().paginationGetTotalPages(); K.tp=tp;
    for(let p=1;p<tp;p++){ const b=Object.keys(K.rows).length; api().paginationGoToPage(p);
      for(let w=0;w<40;w++){ await sl(500); K.collect(); if(Object.keys(K.rows).length>b+60) break; }
      await sl(1000); K.collect(); K.log.push(p+':'+Object.keys(K.rows).length); }
    K.done=true; })(); return 'started'; };
  K.px=function(r,j,months){ const p=r.pr||[]; if(!(p[0]>0)) return 0; const age=(Date.now()-(months[j][0]+14*86400000))/86400000;
    const v=j===35||age<=45?p[0]:age<=105?p[1]:age<=195?p[2]:p[3]; return v>0?v:p[0]; };
  K.status=()=>JSON.stringify({n:Object.keys(K.rows).length,tp:K.tp,done:K.done,last:K.log.slice(-2)});
  // 배지 구간 안의 위치를 순위로 정한다(2026-10-22 · 미국판 phase_keepa.js 와 같은 식 — 설명은 그쪽 주석). 나라마다 그 나라 행으로 곡선을 맞춘다.
  K.refine=function(rows,months){ const hiOf=v=>v<100?100:v<1000?v+100:v<10000?v+1000:v<100000?v+10000:v*2, X0=Math.log(1000), XL=Math.log(20), XH=Math.log(30000);
    const rkOf=(r,j)=>{ let x; if(j<35){ const d=new Date(months[j][0]); const M=d.getUTCFullYear()*12+d.getUTCMonth(); x=(r.hr||[])[((M%36)+36)%36]; } else x=r.r30>0?r.r30:r.rc; return x>0?x:0; };
    rows.forEach(r=>{ r.rk=[]; for(let j=0;j<36;j++) r.rk.push(rkOf(r,j)); });
    const G=[]; for(let j=0;j<36;j++){ const g={}; rows.forEach(r=>{ const rk=r.rk[j]; if(!(rk>0)||!(r.mf[j]>0)) return; const k=r.p+'|'+Math.round(rk); const o=g[k]=g[k]||{p:r.p,rk,lo:0,hi:0,kids:[]}; o.lo+=r.mf[j]; o.hi+=hiOf(r.mf[j]); o.kids.push(r); }); G.push(Object.values(g)); }
    const bins={}; for(let j=23;j<35;j++) G[j].forEach(g=>{ if(g.lo<50||g.rk<20||g.rk>30000) return; const b=Math.floor(Math.log(g.rk)/0.25); (bins[b]=bins[b]||[]).push(Math.log(Math.sqrt(g.lo*g.hi))); });
    const pts=[]; for(const b in bins){ const ys=bins[b].sort((p,q)=>p-q); if(ys.length<6) continue; pts.push([(+b+0.5)*0.25,ys[ys.length>>1],Math.sqrt(ys.length)]); }
    if(pts.length<6) return null;
    const S=[[0,0,0],[0,0,0],[0,0,0]],T=[0,0,0]; pts.forEach(([x,y,w])=>{ const z=[1,Math.min(x,X0),Math.max(0,x-X0)]; for(let i=0;i<3;i++){ T[i]+=w*z[i]*y; for(let k=0;k<3;k++) S[i][k]+=w*z[i]*z[k]; } });
    const det3=m=>m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
    const D=det3(S); if(Math.abs(D)<1e-9) return null; const C=[0,1,2].map(k=>det3(S.map((row,i)=>row.map((v,q)=>q===k?T[i]:v)))/D);
    const f=x=>Math.exp(C[0]+C[1]*Math.min(x,X0)+C[2]*Math.max(0,x-X0)), cur=r=>{ const x=Math.log(r); return x<XL?f(XL)*Math.pow(20/r,0.35):x>XH?f(XH)*Math.pow(30000/r,1.4):f(x); };
    const off={}; for(let j=0;j<35;j++) G[j].forEach(g=>{ if(g.lo<50) return; (off[g.p]=off[g.p]||[]).push(Math.log(Math.sqrt(g.lo*g.hi)/cur(g.rk))); });
    const ko={}; for(const p in off){ const a=off[p].sort((x,y)=>x-y); ko[p]=a.length>=4?a[a.length>>1]:0; }
    let nIn=0,nAll=0; for(let j=0;j<36;j++) G[j].forEach(g=>{ const e=Math.min(Math.max(Math.exp(ko[g.p]||0)*cur(g.rk),g.lo),g.hi*0.999); nAll++; if(e>g.lo&&e<g.hi*0.999) nIn++; g.kids.forEach(r=>{ r.m[j]=Math.round(e*r.mf[j]/g.lo); }); });
    // 배지 없는 달 채우기(2026-10-22 · 사용자 '월판매량 추정 방식에 문제 있는 거 아니냐' — 네오팜) — 순위는 있는데 그 묶음에 배지가 하나도 없는 달(= 옵션마다 50개 미만)은
    //   0 이 아니라 곡선값(상품 수준 보정 포함) · 단 순위 있는 옵션당 49개 상한(KBCH keepa.js 와 같은 규칙). 0 으로 두면 작은 SKU 가 50개를 넘는 순간 '성장'으로 잡혔다 —
    //   KBCH 곡선식 대비 3Q26 전년비: 제로이드 +223% vs +138% · 리얼베리어 +16% vs −27% · 셀리맥스 +275% vs +201%(큰 브랜드는 ±5%p).
    { let nF=0; for(let j=0;j<36;j++){ const P={}; rows.forEach(r=>{ const rk=r.rk[j]; if(!(rk>0)) return; const k=r.p+'|'+Math.round(rk); const o=P[k]=P[k]||{p:r.p,rk,bad:0,kids:[]}; if(r.mf[j]>0) o.bad=1; o.kids.push(r); });
      Object.values(P).forEach(g=>{ if(g.bad) return; const e=Math.min(Math.exp(ko[g.p]||0)*cur(g.rk),49*g.kids.length); if(!(e>=1)) return; g.kids.forEach(r=>{ r.m[j]=Math.round(e/g.kids.length); }); nF++; }); } K.nFill=nF; }
    return {a:+C[0].toFixed(3),b1:+C[1].toFixed(3),b2:+C[2].toFixed(3),bins:pts.length,inb:+(nIn/nAll).toFixed(3),fill:K.nFill}; };
  // 압축 덤프 — 브랜드마다 판매량(u)·판매액(v, 현지 통화 단위)만 · 36진수
  K.save=function(d){
    const KM=k=>(k+21564000)*60000, now=Date.now(), today=new Date(), months=[], ML=[];
    for(let j=35;j>=0;j--){ const x=new Date(Date.UTC(today.getUTCFullYear(),today.getUTCMonth()-j,1)); months.push([x.getTime(),Date.UTC(x.getUTCFullYear(),x.getUTCMonth()+1,1)]); ML.push(x.toISOString().slice(0,7)); }
    // 그달 판매량 = 그달 마지막 7일 배지의 중앙값(2026-10-22) — 배지는 '지난 30일 구매'라 월말 값이 곧 그달 한 달치다(kbeauty/keepa.js 와 같은 식).
    //   예전엔 그달 동안의 배지를 시간 평균했는데, 그러면 반 달 밀려 6월 하순 프라임데이가 7월로 넘어갔다(라네즈 2026-06 14.6만 → 7월 38.7만 · 월말식 42.1만 → 12.0만).
    //   진행 중인 달 = 지금까지 마지막 7일(= 최근 30일 한 달치).
    const ms=h=>{ const pts=[]; for(let i=0;i<h.length;i+=2) pts.push([KM(h[i]),h[i+1]]);
      const at=t=>{ let v=0; for(let i=0;i<pts.length&&pts[i][0]<=t;i++) v=Math.max(pts[i][1],0); return v; };
      return months.map(([s,e])=>{ e=Math.min(e,now); if(e<=s) return 0; const a=[]; for(let k=0;k<7;k++){ const t=e-1-k*86400000; if(t<s) break; a.push(at(t)); }
        a.sort((x,y)=>x-y); const n=a.length; return n?Math.round(n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2):0; }); };
    const B={}, rows=Object.values(K.rows).filter(r=>r.b!=='clio'||r.rb==='clio professional'||(/^clio\b/i.test(r.t)&&!/yogurt|fishing|shower|kayak|grab bar|tarp|clip|foot rest|rod |hot chocolate/i.test(r.t)));
    rows.forEach(r=>{ r.mf=ms(r.msh); r.m=r.mf.slice(); });
    K.fit=K.refine(rows,months);
    rows.forEach(r=>{ const m=r.m, o=B[r.b]=B[r.b]||{u:Array(36).fill(0),v:Array(36).fill(0),n:0}; o.n++;
      for(let j=0;j<36;j++){ o.u[j]+=m[j]; o.v[j]+=m[j]*K.px(r,j,months); } });
    // 최근 30일 창(2026-10-24 · 미국판과 같은 식) — 브랜드 줄 다섯째 칸 = [오늘 · 30일 전 · 365일 전 · 395일 전] 배지 아랫값 합(36진수 · 검산값엔 안 넣는다)
    const atK=(h,t)=>{ let v=0; for(let i=0;i<h.length;i+=2){ if(KM(h[i])>t) break; v=Math.max(h[i+1],0); } return v; };
    const R30=[0,30,365,395].map(x=>now-x*86400000);
    rows.forEach(r=>{ const o=B[r.b]; o.r=o.r||[0,0,0,0]; R30.forEach((t,i)=>{ o.r[i]+=atK(r.msh,t); }); });
    // 3달·1달 창(2026-10-27 · 미국판과 같은 식) — 브랜드 줄 여섯째 칸 = 기준점 7개(14일 간격) × [0·30·60·90·120·150·365·395·425일 전] 배지 아랫값 합 63개(36진수 · 검산값엔 안 넣는다)
    const RWO=[0,30,60,90,120,150,365,395,425], RWN=7, RWS=14;
    rows.forEach(r=>{ const o=B[r.b]; o.w=o.w||Array(RWN*RWO.length).fill(0); for(let a=0;a<RWN;a++) RWO.forEach((x,i)=>{ o.w[a*RWO.length+i]+=atK(r.msh,now-(a*RWS+x)*86400000); }); });
    const L=['D|'+d+'|'+new Date().toISOString().slice(0,10)+'|'+ML[0]+'|'+rows.length+(K.fit?'|r':'')];   // 'r' = 배지 구간을 순위로 보정한 덤프(phase.py 가 보정 안 된 나라만 수준을 맞춘다)
    let h=0;
    Object.keys(B).sort().forEach(k=>{ const o=B[k], v=o.v.map(x=>Math.round(x/100));
      o.u.forEach((x,i)=>{ h=(h+x*(i+1))%1000003; }); v.forEach((x,i)=>{ h=(h+x*(i+7))%1000003; });
      L.push(k+'|'+o.n+'|'+o.u.map(x=>x.toString(36)).join(',')+'|'+v.map(x=>x.toString(36)).join(',')+'|'+(o.r||[0,0,0,0]).map(x=>x.toString(36)).join(',')+'|'+(o.w||[]).map(x=>x.toString(36)).join(',')); });
    L.push('H|'+h);
    const t=L.join('\n'); sessionStorage.setItem('kbeu_'+d,t); return d+' brands '+Object.keys(B).length+' rows '+rows.length+' len '+t.length+' h '+h; };
})(window.KBPH);
'ok'
