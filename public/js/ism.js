/* ══ 종목별 분기 손익 모델 — 공통 엔진 (2026-10-24 · ISM) ═════════════════════════════════════
   사용자 "종목마다 다 IS 모델링 — 컴투스·대원처럼 열심히 된 애들 참고해서, 지표를 어디서 끌어올지 고민해 종목 하나하나 딥다이브".
   전용 모델(컴투스 C2 · 대원 DW · 카카오게임즈 KG · 디어유 DY)이 없는 종목은 이 엔진이 종목 페이지 손익 탭에 그린다.

   실적 칸 = ISM 블록(fetch_ism.py) — DART 연결 분기 손익(q) + 종목별 부문 파서가 읽은 부문 매출·영업이익(seg).
   추정 칸 = ISM_SPEC[종목] — 부문마다 동인(drv):
     "px"   지표 × 계수 — 계수 = 최근 fit 개 실적 분기의 (부문 매출 ÷ 지표) 평균. 지표가 그 분기를 다 덮지 못하면(1~2개월) 관측 월로 일할,
            하나도 없으면 전년 동기 × (1+g) 로 넘어간다(넘어간 칸은 툴팁에 적는다).
     "yoy"  전년 동기 × (1+g) — g 기본 = 최근 2개 실적 분기 전년비 평균(−30~+60% 로 자름) · 가정 칸에서 바꾼다.
     "seas" 직전 분기 × 계절 배수(그 분기의 과거 전분기비 평균) × (1+g)^(1/4).
   비용 = 부문 영업이익이 공시되면 부문 이익률(최근 4분기) · 아니면 회사 이익률(최근 4분기). 영업외 = 최근 6분기 (세전 − 영업이익) 중앙값.
   세율 = 최근 4분기 실효(10~30% 로 자름 · 적자면 0) · 지배 몫 = 최근 4분기 Σ지배 ÷ Σ순이익.
   설계(ISM_SPEC)가 없는 종목은 실적 칸 + 네이버 컨센(C 표시)만 — 우리 추정이 없는데 숫자를 지어내지 않는다.

   단위는 전부 십억원(DART · 네이버 컨센 series 와 같다). 지표의 달러는 그달 ECB 평균 환율(kbFx)로 원화. */
const ISM_SPEC={};
const ISM_COLS=["2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2","2026Q3","2026Q4","2027Q1","2027Q2","2027Q3","2027Q4"];
const ismQ=ym=>`${ym.slice(0,4)}Q${Math.floor((+ym.slice(5,7)-1)/3)+1}`;     // "2026-08" → "2026Q3"
const ismMid=q=>[1,2,3].map(i=>`${q.slice(0,4)}-${String((+q.slice(-1)-1)*3+i).padStart(2,"0")}`);   // 분기의 세 달

/* ── 지표 → 분기 합 {q:{v, n(달 수)}} ─────────────────────────────────── */
function ismFill(o){ const out={}; for(let y=2023;y<=2027;y++) for(let i=1;i<=4;i++){ const q=`${y}Q${i}`; out[q]={v:o[q]||0, n:3}; } return out; }  // 일정형 지표 — 빈 분기 = 0
function ismAgg(pairs){        // [[ym, 값], …] → 분기 합
  const o={}; pairs.forEach(([ym,v])=>{ if(v==null||!isFinite(v)) return; const q=ismQ(ym); const x=o[q]||(o[q]={v:0,n:0}); x.v+=v; x.n++; });
  return o;
}
const ISM_PX={
  // 관세청 수출(TRADE · 품목 라벨 · 나라 코드 ""=전체) → 원화 십억
  trade(label, code){ if(typeof TRADE==="undefined") return {};
    const it=(TRADE.items||[]).find(x=>x.label===label); if(!it) return {};
    const c=(it.byCountry||[]).find(x=>x.code===(code||""))||(it.byCountry||[])[0]; if(!c) return {};
    return ismAgg(TRADE.months.map((m,i)=>{ const ym=`${m.slice(0,4)}-${m.slice(4,6)}`; const v=c.exp[i];
      return [ym, v==null?null:v*(kbFx("USD",ym)||1400)/1e9]; })); },
  // 미국 B/L 선적(BL · 페이지 id) → 톤
  bl(id){ if(typeof BL==="undefined") return {}; const s=(BL.s||[]).find(x=>x.id===id); if(!s) return {};
    const upd=s.upd||"", cur=upd.slice(0,7);
    return ismAgg(BL.months.map((ym,i)=>[ym, ym===cur?null:s.w[i]])); },     // 진행 중인 달은 빼고(일할은 엔진이)
  // 써클차트 월간 앨범 판매량(CIRCLE · 종목) → 만 장
  circle(stock){ if(typeof CIRCLE==="undefined"||!CIRCLE.month) return {}; const m=CIRCLE.month, a=(m.byStock||{})[stock]; if(!a) return {};
    return ismAgg(m.periods.map((p,i)=>[`20${p.slice(0,2)}-${p.slice(3,5)}`, a[i]==null?null:a[i]/1e4])); },
  // 방한 외래관광객(TOURISM) → 만 명
  tour(){ if(typeof TOURISM==="undefined") return {};
    return ismAgg(TOURISM.months.map((m,i)=>[`${m.slice(0,4)}-${m.slice(4,6)}`, TOURISM.total[i]==null?null:TOURISM.total[i]/1e4])); },
  // 게임 한국 매출순위(GRANK · gamerscroll) → 컴투스 곡선(c2Rev · 결제액 억/일) ÷ 1.1 → 회사 매출 십억/달.
  //   달마다: 일별이 그 달을 거의 덮으면(빠진 날 3일 이하) 일별 합을 일수로 늘리고, 아니면 월평균 순위 × 일수(볼록성 때문에 조금 낮다).
  app(slugs, ids){ if(typeof GRANK==="undefined"||typeof c2Rev!=="function") return {};
    const P=C2_ASM0, yms=new Set(), extra=ISM_PX.appIds(ids||[]);
    Object.keys(extra).forEach(m=>yms.add(m));
    slugs.forEach(sl=>{ const g=GRANK.g[sl]; if(!g) return; Object.keys(g.d||{}).forEach(d=>yms.add(d.slice(0,7))); Object.keys(g.m||{}).forEach(m=>yms.add(m)); });
    const pairs=[...yms].sort().map(ym=>{ const dim=new Date(+ym.slice(0,4), +ym.slice(5,7), 0).getDate(); let tot=0, ok=true;
      slugs.forEach(sl=>{ const g=GRANK.g[sl]; if(!g){ return; }
        const ds=Object.keys(g.d||{}).filter(d=>d.startsWith(ym));
        if(ds.length>=dim-3){ tot+=ds.reduce((t,d)=>t+c2Rev(P,g.d[d][0],g.d[d][1]),0)*dim/ds.length; }
        else if(g.m&&g.m[ym]){ tot+=c2Rev(P,g.m[ym][0],g.m[ym][1])*dim; }
        else ok=false; });
      if(extra[ym]!=null){ tot+=extra[ym]; }
      return [ym, ok?tot/(P.vat||1.1)/10:null]; });
    return ismAgg(pairs); },
  // gamerscroll 에 없는 게임(신작) — APPRANK 한국 일별 순위(구글·애플)로 곡선 → 결제액 억/달.
  //   첫 관측일부터 오늘까지 날마다(빈 날은 7일까지 전날 순위) · 이번 달은 일수로 늘린다.
  //   구글 관측 전(APPRANK 구글은 9/18~)은 애플 순위 × (겹친 날들의 구글/애플 순위 비 중앙값) — 크럼블은 구글 순위가 애플의 2~4배 아래였다.
  appIds(ids){ if(!ids.length||typeof APPRANK==="undefined"||!APPRANK.apps) return {}; const P=C2_ASM0, out={};
    ids.forEach(id=>{ const by={and:{}, ios:{}};
      Object.values(APPRANK.apps).filter(a=>a.id===id&&a.cc==="KR").forEach(a=>(a.hist||[]).forEach(h=>{ if(h.gr!=null) by[a.mk==="ios"?"ios":"and"][h.d]=h.gr; }));
      const all=[...Object.keys(by.and), ...Object.keys(by.ios)].sort(); if(!all.length) return;
      const g0=Object.keys(by.and).sort()[0]||"9999", rr=Object.keys(by.and).filter(k=>by.ios[k]).map(k=>by.and[k]/by.ios[k]), R=ismMed(rr);
      const d=new Date(all[0]+"T00:00:00"), end=new Date(TODAY+"T00:00:00"); let lg=null, la=null, ng=99, na=99;
      for(; d<=end; d.setDate(d.getDate()+1)){ const kk=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
        if(by.and[kk]!=null){ lg=by.and[kk]; ng=0; } else ng++;
        if(by.ios[kk]!=null){ la=by.ios[kk]; na=0; } else na++;
        const a=na<=7?la:null, g=ng<=7?lg:(kk<g0&&a!=null&&R!=null?Math.max(1,Math.round(a*R)):null);
        if(g==null&&a==null) continue;
        const ym=kk.slice(0,7); out[ym]=(out[ym]||0)+c2Rev(P,g,a); }
      });
    const cur=TODAY.slice(0,7), dim=new Date(+cur.slice(0,4), +cur.slice(5,7), 0).getDate(), el=+TODAY.slice(8,10);
    if(out[cur]!=null&&el<dim) out[cur]*=dim/el;
    return out; },
  // 한국은행 소매업태별 판매액지수(ECOS · 경상지수) — I74B 백화점 · I74F 면세점 · I74J 편의점 · I74IA 체인슈퍼 · I74VB 홈쇼핑 등. 분기 합(지수×달)
  ecos(code){ if(typeof ECOS==="undefined"||!ECOS.s||!ECOS.s[code]) return {}; const v=ECOS.s[code].v;
    return ismAgg(Object.keys(v).map(ym=>[ym, v[ym]])); },
  // 카지노 월간 공시(CASINO · fetch_casino.py) — keys: c 카지노 · h 호텔 · d 드롭(여럿이면 더한다) → 십억원
  casino(nm, keys){ if(typeof CASINO==="undefined"||!CASINO.m||!CASINO.m[nm]) return {}; const M=CASINO.m[nm], ks=[].concat(keys||"c");
    return ismAgg(Object.keys(M).map(ym=>[ym, ks.every(k=>M[ym][k]!=null)?ks.reduce((t,k)=>t+M[ym][k],0):null])); },
  // SteamCharts 월평균 동접(STEAMM · fetch_steamm.py) → 천 명(월평균의 분기 합)
  steam(appid){ if(typeof STEAMM==="undefined"||!STEAMM.g||!STEAMM.g[appid]) return {}; const m=STEAMM.g[appid].m;
    return ismAgg(Object.keys(m).map(ym=>[ym, m[ym][0]/1000])); },
  // K-pop 투어(TOURS · fetch_tours.py) — 그 종목 투어들의 분기 그로스(보고 매출 + 미보고 회차 × 그 투어 회당 평균) × 월 환율 → 원화 십억.
  //   일정이 없는 분기도 0 으로 채운다(n 3) — 투어가 없으면 기저(a)만 남는다.
  //   매출이 하나도 보고 안 된 투어(앞으로의 일정)는 같은 아티스트 지난 투어의 회당 평균을 빌린다(스트레이키즈 Run It ← Dominate).
  kpoptour(stock){ if(typeof TOURS==="undefined"||!TOURS.t) return {}; const o={}, T=Object.values(TOURS.t);
    const artAvg=ar=>{ const r=T.filter(t=>t.ar===ar).flatMap(t=>t.s.filter(x=>x[1])); return r.length?r.reduce((a,x)=>a+x[1],0)/r.length:null; };
    T.filter(t=>t.st===stock).forEach(t=>{ const rep=t.s.filter(x=>x[1]);
      const avg=rep.length?rep.reduce((a,x)=>a+x[1],0)/rep.length:artAvg(t.ar); if(!avg) return;
      t.s.forEach(([d,usd])=>{ const q=ismQ(d.slice(0,7)); o[q]=(o[q]||0)+(usd||avg)*(kbFx("USD",d.slice(0,7))||1400)/1e9; }); });
    return ismFill(o); },
  // 게임 판매량(GAMEEST · app.js geUnits — 발표 앵커 + Steam 리뷰 증분) → 분기 판매 증분 × 순ASP → 원화 십억. 미래 분기는 최근 리뷰 페이스 그대로.
  gameest(title, asp){ if(typeof GAMEEST==="undefined"||typeof geUnits!=="function"||!GAMEEST[title]) return {}; const G=GAMEEST[title], o={};
    const A=asp||(typeof GE_DEF!=="undefined"?GE_DEF.asp:52000);
    for(let y=2025;y<=2027;y++) for(let i=1;i<=4;i++){ const a=new Date(y,(i-1)*3,1), b=new Date(y,i*3,1), ds=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;
      const U=d=>d<G.launch?0:Math.max(0,geUnits(G,d));                     // 출시 전은 0(geUnits 는 첫 앵커 앞으로 음수 외삽한다)
      try{ o[`${y}Q${i}`]=Math.max(0,U(ds(b))-U(ds(a)))*A/1e9; }catch(e){} }
    return ismFill(o); },
  // 회사 채널 모델(KBCH · kbeauty) — 회사 브랜드의 아마존 전 상품 판매액(Keepa · 나라 코드 US·CA·UK·DE·FR·IT·ES·JP) + 틱톡샵(TT:US 등) 분기 관측 → 원화 십억.
  //   나라를 골라 DART 지역 부문에 맞춘다. 진행 분기 = 회사 채널 모델의 추정(최근 30일 × 시장 계절 · e 표시). 틱톡샵은 2026-04-24 부터라 그 앞 분기는 0.
  kbch(co, codes){ if(typeof KBCH==="undefined"||typeof kbModel!=="function"||typeof kbUnits!=="function") return {};
    const key=co+"|"+codes.join(","), C=ISM_PX._kc||(ISM_PX._kc={}); if(C[key]) return C[key];
    let m=null; try{ m=kbModel(co); }catch(e){} if(!m||!m.Q) return {};
    let U=[]; try{ U=kbUnits(co, m.Q, m.nowQ, m.cur, codes); }catch(e){ return {}; }
    const o={};
    m.Q.forEach(q=>{ if(q===m.nowQ){ const p=U.reduce((t,u)=>t+(u.proj||0),0); if(p>0) o[q]={v:p/10, n:3, e:1}; return; }
      let v=0, ok=false; U.forEach(u=>{ const x=u.q[q]; if(x&&x.v!=null){ v+=x.v; if(u.src==="kp") ok=true; } }); if(ok) o[q]={v:v/10, n:3}; });
    return (C[key]=o); },
  // 네이버 월별 검색량(ISMSRCH · fetch_ismsrch.py · 검색어 묶음마다 자기 최고 = 100) → 분기 합. 국내 부문(시술·화장품·완구)에만.
  srch(kw){ if(typeof ISMSRCH==="undefined"||!ISMSRCH.s||!ISMSRCH.s[kw]) return {}; const v=ISMSRCH.s[kw].v;
    return ismAgg(ISMSRCH.months.map((ym,i)=>[ym, v[i]])); },
  // Keepa 브랜드 판매(ISMKP · ism_keepa.py — 지누스 등 화장품 밖 회사) → 그달 ECB 원/달러로 원화 십억. 진행 중인 달 = 최근 30일 한 달치.
  kp(key){ if(typeof ISMKP==="undefined"||!ISMKP.b||!ISMKP.b[key]) return {}; const o=ISMKP.b[key];
    return ismAgg(o.months.map((ym,i)=>[ym, o.v[i]!=null?o.v[i]*(kbFx("USD",ym)||1400)/1e9:null])); },
  // 공연 회수(매출 미보고 투어 — 블랙핑크) → 회
  kpopshows(stock, artist){ if(typeof TOURS==="undefined"||!TOURS.t) return {}; const o={};
    Object.values(TOURS.t).filter(t=>t.st===stock&&(!artist||String(t.ar).toLowerCase()===String(artist).toLowerCase())).forEach(t=>t.s.forEach(([d])=>{ const q=ismQ(d.slice(0,7)); o[q]=(o[q]||0)+1; }));
    return ismFill(o); },
  // 아마존(Keepa 전 지역) + 틱톡샵 브랜드 판매액(KBPH) → 원화 십억
  //   mk = 아마존 시장(all 전 지역 · us · eu 유럽5 · jp · ca · uk …) · tt = 틱톡샵 미국을 더할지(미국·전 지역만 · 기본 더함)
  kb(keys, mk, tt){ if(typeof KBPH==="undefined"||!KBPH.b) return {}; mk=mk||"all";
    const key=keys.join(",")+"|"+mk+"|"+tt, C=ISM_PX._kb||(ISM_PX._kb={}); if(C[key]) return C[key];
    const mk0=typeof cosMk!=="undefined"?cosMk:"us"; let A; try{ cosMk=mk; A=KBB(); } finally{ cosMk=mk0; }
    const M=KBPH.months, part=KBPH.partial, TT=(tt!==false&&(mk==="all"||mk==="us")&&KBPH.tt&&KBPH.tt.b)?KBPH.tt:null, pairs=[];
    M.forEach((ym,j)=>{ if(ym===part) return; let s=0, any=false;
      keys.forEach(k=>{ const b=A.b[k]; if(b&&b.v&&b.v[j]!=null){ s+=b.v[j]; any=true; }
        const t=TT&&TT.b[k], ti=TT?(TT.months||[]).indexOf(ym):-1; if(t&&ti>=0&&t.mv&&t.mv[ti]!=null&&ym!==TT.partial){ s+=t.mv[ti]; any=true; } });
      pairs.push([ym, any?s*(kbFx("USD",ym)||1400)/1e9:null]); });
    return (C[key]=ismAgg(pairs)); },
};

/* 설계(ism_spec.js)의 지표 이름 → 분기 합 · 화면 이름 */
function ismPxOf(px, name){ const p=px.params||{};
  switch(px.src){
    case "trade": case "sgg": return ISM_PX.trade(p.label, p.code);
    case "kb": return ISM_PX.kb(p.keys||[], p.mk, p.tt);
    case "ecos": return ISM_PX.ecos(p.item||p.code);
    case "circle": return ISM_PX.circle(p.stock||name);
    case "tour": return ISM_PX.tour();
    case "casino": return ISM_PX.casino(p.name||p.corp||name, p.keys||p.key||"c");
    case "app": return ISM_PX.app(p.slugs||(p.games||[]).map(g=>g.gs), p.ids);
    case "steam": return ISM_PX.steam(p.appid);
    case "kpoptour": return ISM_PX.kpoptour(p.stock||name);
    case "kpopshows": return ISM_PX.kpopshows(p.stock||name, p.artist);
    case "gameest": return ISM_PX.gameest(p.title, p.asp_krw);
    case "kbch": return ISM_PX.kbch(p.co||name, p.codes||["US"]);
    case "srch": return ISM_PX.srch(p.kw);
    case "kp": return ISM_PX.kp(p.key);
    case "bl": { const ids=[].concat(p.ids||p.id||[]), xs=ids.map(id=>ISM_PX.bl(id)), o={};
      xs.forEach(x=>Object.entries(x).forEach(([q,v])=>{ const y=o[q]||(o[q]={v:0,n:3}); y.v+=v.v; y.n=Math.min(y.n,v.n); })); return o; }
    default: return null; } }
const ISM_KB_NM={US:"미국",CA:"캐나다",UK:"영국",DE:"독일",FR:"프랑스",IT:"이탈리아",ES:"스페인",JP:"일본"};
function ismKbLab(codes){ codes=codes||[]; const eu=["UK","DE","FR","IT","ES"], am=codes.filter(c=>!/^TT:/.test(c)), tt=codes.filter(c=>/^TT:/.test(c));
  const a=eu.every(c=>am.includes(c))?[...am.filter(c=>!eu.includes(c)).map(c=>ISM_KB_NM[c]||c), "유럽5"]:am.map(c=>ISM_KB_NM[c]||c);
  return `아마존 ${a.join("·")}${tt.length?` + 틱톡샵 ${tt.map(c=>c.slice(3)).join("·")}`:""}`; }
function ismPxLab(px){ if(!px) return ""; const p=px.params||{};
  return ({trade:`관세청 ${p.label||""}${p.code?" "+p.code:""} 수출(원화)`, sgg:`관세청 ${p.label||""} 수출(원화)`, kb:`아마존${({all:"",us:" 미국",eu:" 유럽5",jp:" 일본",ca:" 캐나다",uk:" 영국"})[p.mk||"all"]??(" "+p.mk)}${(p.tt!==false&&(!p.mk||p.mk==="all"||p.mk==="us"))?"·틱톡샵":""} 판매액(${(p.keys||[]).join("·")})`,
    ecos:`${p.name||"소매"} 판매지수(ECOS)`, circle:"써클 앨범(만 장)", tour:"방한 관광객(만 명)", casino:"카지노 월 공시 매출", app:"한국 매출순위 곡선(억/일)",
    steam:`${p.title||"Steam"} 월평균 동접(천 명)`, kpoptour:"투어 그로스(십억원)", kpopshows:"공연 회수", gameest:`${p.title||"게임"} 판매 × ASP(십억원)`, kbch:`${ismKbLab(p.codes)} 판매액(십억원)`, bl:"미국 해상 선적(B/L 톤)", srch:`네이버 검색 '${p.kw||""}'(월 합)`, kp:`아마존 미국 '${p.key||""}' 판매액(십억원)`})[px.src]||px.src; }

/* ── 엔진 ─────────────────────────────────────────────────────────────── */
function ismAsmGet(name){ try{ return JSON.parse(localStorage.getItem("ism_"+name)||"{}")||{}; }catch(e){ return {}; } }
function ismAsmSave(name, a){ try{ localStorage.setItem("ism_"+name, JSON.stringify(a)); }catch(e){} }
const ismMed=a=>{ const s=a.filter(v=>v!=null&&isFinite(v)).sort((x,y)=>x-y); if(!s.length) return null; const m=s.length>>1; return s.length%2?s[m]:(s[m-1]+s[m])/2; };
const ismClip=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));

function ismBuild(name, opt){
  opt=opt||{};                                                             // opt.upto = 그 분기까지만 실적으로(실전 검산) · opt.spec = 설계 바꿔 끼우기(비교용)
  const D=(typeof ISM!=="undefined"&&ISM.s&&ISM.s[name])||null; if(!D||!D.q) return null;
  const S=opt.spec||ISM_SPEC[name]||null, A=opt.upto?{}:ismAsmGet(name);   // 검산은 가정 칸 손질 없이 자동값으로
  const act=Object.keys(D.q).filter(q=>D.q[q].rev!=null&&(!opt.upto||q<=opt.upto)).sort(), lastAct=act[act.length-1];
  const segsAll=S&&S.segs?S.segs:[];
  const segAct=(q,k)=>{ const g=(D.seg||{})[q]; if(!g) return null; const v=g[k]; return v?v:null; };
  const Q={};
  // 실적 칸
  act.forEach(q=>{ const d=D.q[q], o={q, act:true, rev:d.rev, op:d.op, pbt:d.pbt, np:d.np, npp:d.npp!=null?d.npp:d.np, seg:{},
      adj:(S&&S.oneoff&&S.oneoff[q])||0};                                   // 일회성 비용(설계 oneoff) — 이익률·세율·지배 몫을 셀 때 되더한다
    let sum=0, have=0;
    segsAll.forEach(s=>{ const of=s.of||s.k;
      const v=Array.isArray(of)?(()=>{ const xs=of.map(k=>segAct(q,k)).filter(x=>x&&x[0]!=null); if(!xs.length) return null;
        return [xs.reduce((t,x)=>t+x[0],0), xs.every(x=>x[1]!=null)?xs.reduce((t,x)=>t+x[1],0):null]; })():segAct(q,of);
      if(v&&v[0]!=null){ o.seg[s.k]={rev:v[0], op:v[1]}; sum+=v[0]; have++; } });
    if(segsAll.length&&have===segsAll.length) o.seg._rest={rev:d.rev-sum, op:null};   // 부문이 다 있는 분기만 — 일부만 있으면 빠진 부문이 '나머지'로 둔갑한다
    Q[q]=o; });
  const segStart=act.find(q=>Object.keys(Q[q].seg).some(k=>k!=="_rest"));            // 부문 자료가 처음 있는 분기(그 뒤에 생긴 부문만 '새 부문')
  // 최근 실적 기준값들
  // 일회성 분기(설계 bad — 회사 전체 · 부문별 seg.bad) — 이익률·성장률·계절·지표 계수의 표본과 전년 동기 기준에서 뺀다
  const badC=new Set((S&&S.bad)||[]), badOf=k=>{ const sg=segsAll.find(x=>x.k===k); return new Set([...badC, ...((sg&&sg.bad)||[])]); };
  const lastN=(n)=>act.filter(q=>!badC.has(q)).slice(-n).map(q=>Q[q]);
  const L4=lastN((S&&S.opmWin)||4), L6=lastN(6);
  const opmAuto=L4.reduce((t,x)=>t+(x.op||0)+x.adj,0)/Math.max(1e-9,L4.reduce((t,x)=>t+(x.rev||0),0));
  const nonopAuto=ismMed(L6.map(x=>(x.pbt!=null&&x.op!=null)?x.pbt-x.op:null))||0;
  const sPbt=L4.reduce((t,x)=>t+(x.pbt||0)+x.adj,0), sNp=L4.reduce((t,x)=>t+(x.np||0)+x.adj,0);   // 일회성은 세금 효과 없이 되더한다
  const taxAuto=sPbt>0?ismClip((sPbt-sNp)/sPbt,0.1,0.3):0.22;
  const share=A.share!=null?A.share/100:(sNp!==0?ismClip(L4.reduce((t,x)=>t+(x.npp||0)+x.adj,0)/sNp,0,1.2):1);
  const P={opm:A.opm!=null?A.opm/100:opmAuto, opmAuto, nonop:A.nonop!=null?A.nonop:nonopAuto, nonopAuto, tax:A.tax!=null?A.tax/100:taxAuto, taxAuto, share, segs:{}};
  // 고정비형(설계 opFit "lin" · 엔터 투어·게임 출시·카지노) — 영업이익 = c + d × 매출(최근 6분기 적합).
  //   매출이 뛰는 분기에 이익률이 같이 오르는 것을 잡는다. 한계이익률 d 가 0~0.9 이고 R² 0.4 이상일 때만 · 이익률을 직접 넣으면 안 쓴다.
  if(S&&S.opFit==="lin"&&A.opm==null){ const pr=L6.filter(x=>x.op!=null&&x.rev>0).map(x=>[x.rev, x.op+x.adj]);
    if(pr.length>=5){ const n=pr.length, mx=pr.reduce((t,x)=>t+x[0],0)/n, my=pr.reduce((t,x)=>t+x[1],0)/n;
      const sxx=pr.reduce((t,x)=>t+(x[0]-mx)**2,0), sxy=pr.reduce((t,x)=>t+(x[0]-mx)*(x[1]-my),0), syy=pr.reduce((t,x)=>t+(x[1]-my)**2,0);
      if(sxx>0&&syy>0){ const d=sxy/sxx, r2=sxy*sxy/(sxx*syy); if(d>0&&d<0.9&&r2>=0.4) P.lin={c:my-d*mx, d, r2, n}; } } }
  // 계절 이익률 — 그 해(1~4분기 실적이 다 있는 해) 안에서 같은 분기의 이익률 − 그 해 평균, 최근 2년 평균 × 0.7 · ±8%p.
  //   빙그레 3Q 성수기·BGF 1Q 비수기·파라다이스 4Q 성과급처럼 이익률이 분기마다 다른 회사를 연평균으로 누르지 않게.
  //   (그 분기까지 4분기 평균과 견주면 이익률이 오르는 해엔 최근 분기가 늘 '계절적으로 높게' 읽힌다 — 같은 해 안에서만 견준다)
  const seasM=(qi, f, bad)=>{ const yrs=[...new Set(act.map(q=>q.slice(0,4)))].filter(y=>[1,2,3,4].every(i=>Q[`${y}Q${i}`]&&Q[`${y}Q${i}`].act&&!bad.has(`${y}Q${i}`)));
    const xs=yrs.slice(-2).map(y=>{ const r=[1,2,3,4].map(i=>f(Q[`${y}Q${i}`])); if(r.some(v=>!v||v[1]<=0)) return null;
      const a=r.reduce((t,v)=>t+v[0],0)/r.reduce((t,v)=>t+v[1],0); return r[qi-1][0]/r[qi-1][1]-a; }).filter(v=>v!=null);
    return xs.length?ismClip(0.7*xs.reduce((t,v)=>t+v,0)/xs.length,-0.08,0.08):0; };
  P.seas=[1,2,3,4].map(i=>(A.opm!=null||P.lin||(S&&S.opmWin))?0:seasM(i, x=>x.op!=null?[x.op+(x.adj||0), x.rev]:null, badC));
  // 부문 기본값 — 성장률·이익률·지표 계수
  const segRev=(q,k)=>Q[q]&&Q[q].seg[k]?Q[q].seg[k].rev:null;
  // 재분류(옛 분류 그대로인 분기 = D.segBasis[q]==="old") — 재작성된 분기의 새/옛 비율로 옛 분기를 새 분류에 맞춘다
  const OLD=D.segOld||{}, fac={};
  segsAll.forEach(s=>{ let n=0, o=0; Object.keys(OLD).forEach(q=>{ const v=OLD[q][s.k], w=segRev(q,s.k); if(v&&v[0]>0&&w!=null){ n+=w; o+=v[0]; } }); fac[s.k]=o>0?n/o:1; });
  // 분기 겹침 없이 연간만 재작성된 경우(JYP 2026 — 유튜브 옛 기타 → 새 음반 · MD 분리) — 연간 새/옛 비율
  const FY=D.segFy||{};
  segsAll.forEach(s=>{ if(fac[s.k]!==1) return; const ks=[].concat(s.of||s.k); let n=0, o=0;
    Object.keys(FY).filter(y=>/^\d{4}$/.test(y)).forEach(y=>{ const N=FY[y], O=FY[y]._old||{};
      const nv=ks.reduce((t,k)=>t+((N[k]||[])[0]||0),0), ov=ks.reduce((t,k)=>t+((O[k]||[])[0]||0),0); if(nv>0&&ov>0){ n+=nv; o+=ov; } });
    if(o>0) fac[s.k]=n/o; });
  const isOld=q=>(D.segBasis||{})[q]==="old";
  const baseRev=(q,k)=>{ const v=segRev(q,k); return v==null?null:(isOld(q)?v*fac[k]:v); };
  segsAll.forEach(s=>{
    const bd=badOf(s.k), ok=q=>!bd.has(q);
    const l4=act.filter(q=>ok(q)&&ok(c2QAdd(q,-4))).slice(-4), a4=l4.map(q=>baseRev(q,s.k)), b4=l4.map(q=>baseRev(c2QAdd(q,-4),s.k));
    const ys=l4.slice(-2).map(q=>{ const a=baseRev(q,s.k), b=baseRev(c2QAdd(q,-4),s.k); return (a!=null&&b>0)?a/b-1:null; }).filter(v=>v!=null);
    const sb=l4.length===4&&b4.every(v=>v!=null&&v>0)&&a4.every(v=>v!=null)?b4.reduce((t,v)=>t+v,0):0;   // 분기 튐에 덜 흔들리게 4분기 합끼리
    const gAuto=sb>0?ismClip(a4.reduce((t,v)=>t+v,0)/sb-1,-0.4,0.6):(ys.length?ismClip(ys.reduce((t,v)=>t+v,0)/ys.length,-0.4,0.6):0);
    const ops=act.filter(ok).slice(-(s.mWin||4)).map(q=>Q[q].seg[s.k]).filter(x=>x&&x.op!=null&&x.rev>0);
    const mAuto=ops.length>=2?ops.reduce((t,x)=>t+x.op,0)/ops.reduce((t,x)=>t+x.rev,0):null;
    let px=null, k=null, kN=0, ia=null, ib=null, r2=null;
    if((s.drv==="px"||s.drv==="pxa")&&s.px){ try{ px=s.px(); }catch(e){ px=null; }
      if(px){ const sk=new Set(s.skip||[]); const pr=act.filter(q=>!sk.has(q)&&ok(q)).slice(-(s.fit||(s.drv==="pxa"?8:4))).map(q=>{ const a=baseRev(q,s.k), p=px[q]; return (a!=null&&p&&p.n===3&&(s.drv==="pxa"?p.v>=0:p.v>0))?[p.v,a]:null; }).filter(Boolean);   // 절편 식은 지표 0 분기(투어 없음·출시 전)도 표본
        if(s.drv==="px"&&pr.length){ k=pr.reduce((t,x)=>t+x[1]/x[0],0)/pr.length; kN=pr.length; }
        if(s.drv==="pxa"&&pr.length>=3){ const n=pr.length, mx=pr.reduce((t,x)=>t+x[0],0)/n, my=pr.reduce((t,x)=>t+x[1],0)/n;
          const sxx=pr.reduce((t,x)=>t+(x[0]-mx)**2,0), sxy=pr.reduce((t,x)=>t+(x[0]-mx)*(x[1]-my),0), syy=pr.reduce((t,x)=>t+(x[1]-my)**2,0);
          // 기울기는 양수(지표가 늘면 매출도)이고 지표가 0이 아닌 분기가 둘 이상일 때만 — 거의 0인 분기만으로 맞추면 기울기가 엉뚱하다(에스엠 −15.8)
          //   설명력(R²)이 0.3 밑이면 지표가 매출을 설명하지 못한다 — 평균값을 지표 식이라 부르지 않게 자기 이력으로 돌린다
          if(sxx>0&&sxy>0&&syy>0&&pr.filter(x=>x[0]>0).length>=2&&sxy*sxy/(sxx*syy)>=0.3){ ib=sxy/sxx; ia=my-ib*mx; r2=(sxy*sxy)/(sxx*syy); kN=n; } } } }
    const a=(A.seg||{})[s.k]||{};
    const mSeas=(a.m==null&&s.m==null&&mAuto!=null&&!s.mWin)?[1,2,3,4].map(i=>seasM(i, x=>x.seg[s.k]&&x.seg[s.k].op!=null?[x.seg[s.k].op, x.seg[s.k].rev]:null, bd)):[0,0,0,0];
    const g6=a.g!=null?a.g/100:(s.g!=null?s.g:gAuto);                  // 2027 성장률(g7) = 기본 2026 의 절반 — 성장 둔화
    P.segs[s.k]={bad:bd, g:g6, g7:a.g7!=null?a.g7/100:(s.g7!=null?s.g7:g6*0.5), gAuto, m:a.m!=null?a.m/100:(s.m!=null?s.m:mAuto), mAuto, mSeas, px, k, kN, ia, ib, r2, fac:fac[s.k]};
  });
  // 추정 칸
  const est=S?ISM_COLS.filter(q=>!Q[q]&&q>lastAct):[];                    // 설계가 없으면 추정 칸을 만들지 않는다
  est.forEach(q=>{
    const o={q, act:false, seg:{}, why:{}};
    if(segsAll.length){
      let sum=0;
      segsAll.forEach(s=>{ const p0=P.segs[s.k], p={...p0, g:q>="2027"?p0.g7:p0.g}, q4=c2QAdd(q,-4), base=(Q[q4]&&Q[q4].seg[s.k]&&!p.bad.has(q4))?baseRev(q4,s.k):null;
        // ① 지표 식(px · pxa)
        let pv=null, pw="";
        const x=p.px&&p.px[q], xv=x&&x.n>=1?x.v*3/x.n:null, xl=x?(x.n===3?`${s.pxLab||"지표"} ${fmt(x.v,1)}${x.e?"(진행 분기 추정)":""}`:`${s.pxLab||"지표"} ${x.n}개월 ${fmt(x.v,1)}×3/${x.n}`):"";
        if(s.drv==="px"&&p.k!=null&&xv!=null){ pv=p.k*xv; pw=`${xl} × ${fmt(p.k,3)}(최근 ${p.kN}분기 비율)`; }
        if(s.drv==="pxa"&&p.ib!=null&&xv!=null){ pv=p.ia+p.ib*xv; pw=`${fmt(p.ia,1)} + ${fmt(p.ib,3)} × ${xl}(최근 ${p.kN}분기 적합${p.r2!=null?` · R² ${fmt(p.r2,2)}`:""})`; }
        // ② 자기 이력 — 전년 동기 × 성장률 과 직전 분기 × 계절 의 평균(한 분기가 튀어도 덜 흔들리게) · 새 부문은 직전 분기
        const pq0=Q[c2QAdd(q,-1)], prev0=pq0&&pq0.seg[s.k]?pq0.seg[s.k].rev:null, gs=`(1${p.g>=0?"+":""}${fmt(p.g*100,0)}%)`;
        const sf=s.sf1?1:ismSeas(Q,s.seasOf||s.k,+q.slice(-1),act,p.bad), seasV=(prev0!=null&&prev0>0&&sf)?prev0*sf*Math.pow(1+p.g,0.25):null;
        const seasW=seasV!=null?`직전 분기 ${fmt(prev0,1)}${s.sf1?"":` × 계절 ${fmt(sf,3)}`} × ${gs}^¼`:"";
        const born=act.find(x=>Q[x].seg[s.k]&&Q[x].seg[s.k].rev>0.5), young=born&&born>segStart&&born>c2QAdd(q,-6)&&prev0!=null&&(base==null||base<prev0*0.5);
        let hv=null, hw="";
        if(s.drv==="seas"&&seasV!=null){ hv=seasV; hw=seasW; }
        else if(young){ hv=prev0; hw=`새 부문(${c2QLab(born)}~) — 직전 분기 ${fmt(prev0,1)} 유지`; }
        else if(base!=null){ const yv=base*(1+p.g), yw=`전년 동기 ${fmt(base,1)}${isOld(q4)&&fac[s.k]!==1?`(옛 분류 × ${fmt(fac[s.k],2)})`:""} × ${gs}`;
          if(seasV!=null&&s.blend!==false&&!s.sf1){ hv=(yv+seasV)/2; hw=`[${yw} = ${fmt(yv,1)}] 와 [${seasW} = ${fmt(seasV,1)}] 의 평균`; }
          else { hv=yv; hw=yw; } }
        else if(seasV!=null){ hv=seasV; hw=seasW+(p.bad.has(q4)?` — 전년 동기(${c2QLab(q4)})는 일회성이라 뺌`:""); }
        else if(prev0!=null){ hv=prev0; hw=`직전 분기 ${fmt(prev0,1)} 유지(전년 동기·계절 기준 없음)`; }
        // ③ 합치기 — 지표가 약한 부문(설계 pxw)은 지표 식과 자기 이력을 섞는다
        let v, why;
        if(pv!=null&&s.pxw!=null&&hv!=null){ v=s.pxw*pv+(1-s.pxw)*hv; why=`지표 ${fmt(s.pxw*100,0)}% [${pw} = ${fmt(pv,1)}] + 이력 ${fmt(100-s.pxw*100,0)}% [${hw} = ${fmt(hv,1)}]`; }
        else if(pv!=null){ v=pv; why=pw; }
        else if(hv!=null){ v=hv; why=(s.drv==="px"||s.drv==="pxa"?"지표 없음 → ":"")+hw; }
        else { const lq=act.filter(x=>x<q&&Q[x].seg[s.k]).pop();                // 기준 분기가 비었으면(공시 공백) 마지막으로 있던 값
          if(lq){ v=Q[lq].seg[s.k].rev; why=`마지막 실적 ${c2QLab(lq)} ${fmt(v,1)} 유지(기준 분기 공백)`; } else { v=0; why="기준 없음"; } }
        const b4=Q[q4]&&Q[q4].seg[s.k];
        const op=(s.mInc!=null&&b4&&b4.op!=null&&b4.rev!=null&&!p.bad.has(q4))?b4.op+(v-b4.rev)*s.mInc     // 고정비형 부문 — 전년 동기 이익 + 매출 증분 × 한계이익률
          :p.m!=null?v*(p.m+p.mSeas[+q.slice(-1)-1]):null;
        o.seg[s.k]={rev:v, op}; o.why[s.k]=why; sum+=v; });
      // 나머지(부문 밖 · 조정) = 최근 4분기 비중
      const rr=act.filter(x=>Q[x].seg._rest).slice(-4).map(x=>Q[x].rev?Q[x].seg._rest.rev/Q[x].rev:null).filter(v=>v!=null);
      const rest=rr.length?ismClip(rr.reduce((t,v)=>t+v,0)/rr.length,-0.5,0.5):0;
      o.rev=sum/(1-rest); o.seg._rest={rev:o.rev-sum, op:null};
      const segOp=segsAll.every(s=>o.seg[s.k].op!=null), sq=P.seas[+q.slice(-1)-1], om=P.opm+sq;
      const sl=Math.abs(sq)>=0.0005?` ${sq>0?"+":"−"} 계절 ${fmt(Math.abs(sq)*100,1)}%p`:"";
      o.op=segOp?segsAll.reduce((t,s)=>t+o.seg[s.k].op,0)+(o.seg._rest.rev*P.opm):P.lin?P.lin.c+P.lin.d*o.rev:o.rev*om;
      const inc=segsAll.filter(s=>s.mInc!=null).map(s=>`${s.t} = 전년 동기 이익 + 매출 증분 × ${fmt(s.mInc*100,0)}%`).join(" · ");
      o.why.op=(!segOp&&P.lin)?`고정비 ${fmt(-P.lin.c,1)} 을 빼고 매출의 ${fmt(P.lin.d*100,1)}% (최근 ${P.lin.n}분기 적합 · R² ${fmt(P.lin.r2,2)}) — 이익률 ${fmt(o.op/o.rev*100,1)}%`:segOp?`부문 영업이익 합(부문 이익률${segsAll.some(s=>P.segs[s.k].mSeas.some(v=>v))?" + 계절":""} × 매출) + 나머지 × 회사 이익률 ${fmt(P.opm*100,1)}%`
        :`매출 × 영업이익률 ${fmt(om*100,1)}%(최근 ${(S&&S.opmWin)||4}분기 ${fmt(P.opm*100,1)}%${sl})`;
      if(segOp&&inc) o.why.op+=` (${inc})`;
    }
    o.pbt=o.op+P.nonop; o.np=o.pbt>0?o.pbt*(1-P.tax):o.pbt; o.npp=o.np*P.share;
    Q[q]=o;
  });
  // 연간
  const Y={};
  ["2024","2025","2026","2027"].forEach(y=>{ const qs=[1,2,3,4].map(i=>Q[`${y}Q${i}`]); if(qs.some(x=>!x)) return;
    const sum=k=>qs.reduce((t,x)=>t+(x[k]||0),0);
    const o={q:y, yr:true, act:qs.every(x=>x.act), rev:sum("rev"), op:sum("op"), pbt:sum("pbt"), np:sum("np"), npp:sum("npp"), seg:{}};
    segsAll.concat([{k:"_rest"}]).forEach(s=>{ if(qs.every(x=>x.seg[s.k])) o.seg[s.k]={rev:qs.reduce((t,x)=>t+x.seg[s.k].rev,0),
      op:qs.every(x=>x.seg[s.k].op!=null)?qs.reduce((t,x)=>t+x.seg[s.k].op,0):null}; });
    Y[y]=o; });
  return {D, S, A, P, Q, Y, act, lastAct, est};
}
// 실전 검산 — 분기 q 를 '그 직전 분기까지 실적 + q 의 지표'로 맞혀 본다(계수·성장률·이익률을 그때 자료로 다시 맞춘다).
//   지표는 그 분기 실제 값을 쓴다 — 지표가 맞으면 매출이 맞는가(모델의 짜임)를 보는 검산이지, 지표 자체를 미리 맞히는 것은 아니다.
function ismBacktest(name, n, spec){
  const D=(typeof ISM!=="undefined"&&ISM.s&&ISM.s[name])||null; if(!D||!D.q) return [];
  const act=Object.keys(D.q).filter(q=>D.q[q].rev!=null).sort(), out=[];
  act.filter(q=>q>="2025Q2").slice(-(n||4)).forEach(q=>{ let B; try{ B=ismBuild(name,{upto:c2QAdd(q,-1), spec}); }catch(e){ return; }
    const p=B&&B.Q[q]; if(!p||p.act) return;
    const a=D.q[q], adj=((spec||ISM_SPEC[name]||{}).oneoff||{})[q]||0;
    const seg={}; (B.S&&B.S.segs||[]).forEach(s=>{ const of=[].concat(s.of||s.k), g=(D.seg||{})[q]||{};
      const xs=of.map(k=>g[k]).filter(x=>x&&x[0]!=null); if(xs.length&&p.seg[s.k]) seg[s.k]={p:p.seg[s.k].rev, a:xs.reduce((t,x)=>t+x[0],0), why:p.why[s.k]}; });
    out.push({q, rev:p.rev, revA:a.rev, op:p.op, opA:a.op!=null?a.op+adj:null, seg}); });
  return out;
}
function ismSeas(Q, k, qi, act, bad){
  // 같은 분기 지수(qi)의 '직전 분기 대비 배수' 기하평균. 네 분기 배수를 다 구하면 곱이 1이 되게 나눈다 —
  //   빠르게 크는 부문은 배수마다 성장이 섞여(앨엔씨 인체조직 분기 1.2~1.35배) 그대로 쓰면 성장률과 이중으로 붙는다.
  const st=act.find(q=>Object.keys(Q[q].seg).some(x=>x!=="_rest")), born=act.find(x=>Q[x].seg[k]&&Q[x].seg[k].rev>0.5);
  const young=q=>born&&born>st&&q<=c2QAdd(born,1);                                    // 출시·인수 직후 두 분기는 계절이 아니다(자료 시작 분기는 제외)
  const raw=i=>{ const r=act.filter(q=>+q.slice(-1)===i&&!young(q)&&!young(c2QAdd(q,-1))&&!(bad&&(bad.has(q)||bad.has(c2QAdd(q,-1))))).map(q=>{
      const a=Q[q].seg[k], b=Q[c2QAdd(q,-1)]&&Q[c2QAdd(q,-1)].seg[k]; return (a&&b&&b.rev>0&&a.rev>0)?a.rev/b.rev:null; }).filter(v=>v!=null);
    return r.length?Math.exp(r.reduce((t,v)=>t+Math.log(v),0)/r.length):null; };
  const f=[1,2,3,4].map(raw); if(f[qi-1]==null) return null;
  const nz=f.every(v=>v!=null)?Math.pow(f.reduce((t,v)=>t*v,1),0.25):1;
  return ismClip(f[qi-1]/nz,0.5,2);
}

/* ── 화면 ─────────────────────────────────────────────────────────────── */
let ismOpen=(()=>{ try{ return JSON.parse(localStorage.getItem("ismOpen")||"{}")||{}; }catch(e){ return {}; } })();
function renderIsm(name, host){
  if(!host) return;
  const B=ismBuild(name);
  if(!B){ host.innerHTML=""; return; }
  const {S, P, Q, Y, A}=B;
  const f1=v=>(v==null||!isFinite(v))?"—":fmt(v,1);
  const pc=v=>(v==null||!isFinite(v))?"—":`<span class="${cls(v)}">${sign(v*100,0)}%</span>`;
  const chg=(c,b)=>{ if(c==null||b==null) return "—"; if(b>0) return c>0||c===0?pc(c/b-1):`<span class="down">적전</span>`; return c>0?`<span class="up">흑전</span>`:`<span class="g">적지</span>`; };
  const LS=(typeof LIVE!=="undefined"&&LIVE.stocks&&LIVE.stocks[name])||{}, cn=LS.cons||{}, cons={};
  ((cn.quarter||{}).series||[]).forEach(x=>{ cons[`${x.k.slice(0,4)}Q${Math.ceil(+x.k.slice(4,6)/3)}`]=x; });
  ((cn.year||{}).series||[]).forEach(x=>{ cons[x.k.slice(0,4)]=x; });
  const segs=S&&S.segs?S.segs:[], hasSpec=!!S;
  // 설계가 없으면 추정 칸 = 네이버 컨센(분기는 컨센이 있는 것만 · 2027 은 엑셀 컨센 DATA.rev27/op27)
  const R0=(typeof byName!=="undefined"&&byName[name])||{};
  if(R0.rev27!=null&&!cons["2027"]) cons["2027"]={rev:R0.rev27, op:R0.op27, np:null, xl:1};
  const cOf=q=>{ const c=cons[q]; return c?{q, yr:q.length===4, act:false, cOnly:true, seg:{}, rev:c.rev, op:c.op, npp:c.np}:null; };
  const cols=ISM_COLS.map(q=>Q[q]||(!hasSpec&&q>B.lastAct?cOf(q):null)).filter(Boolean)
    .concat(["2025","2026","2027"].map(y=>(Y[y]&&(Y[y].act||hasSpec))?Y[y]:cOf(y)).filter(Boolean));
  const nextQ=(cols.find(o=>!o.yr&&!o.act)||{}).q;
  const lab=o=>o.yr?`${o.q}${o.act?"A":o.cOnly?"C":"E"}`:`${c2QLab(o.q)}${o.act?"":o.cOnly?"C":"E"}`;
  const prevOf=o=>o.yr?(Y[String(+o.q-1)]||null):(Q[c2QAdd(o.q,-4)]||null);
  const mc=LS.mktcapEok?LS.mktcapEok/10:null;
  const open=ismOpen[name]||{};
  const ROWS=[{k:"rev", t:"매출액", em:1, tg:segs.length?"rev":null}, {k:"rev", t:"YoY", r:"yoy"}, {k:"rev", t:"QoQ", r:"qoq"}]
    .concat(segs.map(s=>({k:s.k, t:s.t, seg:1, g:"rev"})))
    .concat(segs.length?[{k:"_rest", t:"그 밖·조정", seg:1, g:"rev", sm:1}]:[])
    .concat([{k:"op", t:"영업이익", em:1, tg:segs.some(s=>s.m!=null||(P.segs[s.k]||{}).m!=null)?"op":null}, {k:"op", t:"영업이익률", r:"opm"}, {k:"op", t:"YoY", r:"opyoy"}])
    .concat(segs.filter(s=>(P.segs[s.k]||{}).m!=null).map(s=>({k:s.k, t:s.t+" 영업이익", seg:1, sop:1, g:"op"})))
    .concat([{k:"pbt", t:"세전이익", tg:"np"}, {k:"np", t:"당기순이익", g:"np"}, {k:"npp", t:"지배주주 순이익", em:1}, {k:"per", t:"PER(현재 시총)", r:"per"}]);
  const valOf=(o,r)=>{
    if(r.r==="yoy"){ const p=prevOf(o)||cols.find(x=>x.q===(o.yr?String(+o.q-1):c2QAdd(o.q,-4))); return {h:chg(o.rev,p&&p.rev)}; }
    if(r.r==="qoq"){ if(o.yr) return {h:""}; const p=Q[c2QAdd(o.q,-1)]; return {h:chg(o.rev,p&&p.rev)}; }
    if(r.r==="opm") return {h:(o.rev&&o.op!=null)?`${fmt(o.op/o.rev*100,1)}%`:"—"};
    if(r.r==="opyoy"){ const p=prevOf(o)||cols.find(x=>x.q===(o.yr?String(+o.q-1):c2QAdd(o.q,-4))); return {h:chg(o.op,p&&p.op)}; }
    if(r.r==="per") return {h:(o.yr&&mc&&o.npp>0)?`${fmt(mc/o.npp,1)}배`:""};
    if(r.seg){ const x=o.seg&&o.seg[r.k]; if(!x) return {h:"—"}; const v=r.sop?x.op:x.rev;
      if(o.act&&!o.yr&&(B.D.segBasis||{})[o.q]==="old") return {h:f1(v)+"*", tip:"옛 분류(재분류 전) — 전년비는 새 분류로 맞춰 계산"};
      return {h:f1(v), tip:(!o.act&&o.why&&!r.sop)?o.why[r.k]:""}; }
    if(r.k==="op"&&o.adj) return {h:f1(o.op)+"*", tip:`일회성 ${fmt(-o.adj,1)}${S.oneoffNote?`(${S.oneoffNote})`:""} 포함 · 빼면 ${fmt(o.op+o.adj,1)}`};
    return {h:f1(o[r.k]), tip:(r.k==="op"&&o.why&&o.why.op)?o.why.op:""};
  };
  const yrEdge=i=>i>0&&(cols[i].yr!==cols[i-1].yr||(!cols[i].yr&&cols[i].q.slice(0,4)!==cols[i-1].q.slice(0,4)));
  const th=cols.map((o,i)=>`<th style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${o.q===nextQ?"background:color-mix(in srgb, var(--accent) 14%, transparent);":""}">${lab(o)}</th>`).join("");
  const body=ROWS.filter(r=>!r.g||open[r.g]).map(r=>{
    const tog=r.tg?`<span class="ism-tg" data-ismtg="${r.tg}" style="cursor:pointer;color:var(--muted);margin-right:4px">${open[r.tg]?"▾":"▸"}</span>`:"";
    const sub=!!r.r||r.seg;
    return `<tr${r.em?' style="font-weight:800"':""}><td class="l" style="${r.seg?"padding-left:22px;":""}${sub?"color:var(--muted);font-size:11.5px;":""}">${tog}${attr(r.t)}</td>`
      +cols.map((o,i)=>{ const v=valOf(o,r); const shade=o.q===nextQ?"background:color-mix(in srgb, var(--accent) 8%, transparent);":"";
        const est=!o.act&&!o.cOnly?"":o.cOnly?"color:var(--muted);":"";
        return `<td style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${shade}${est}${r.em?"border-top:1px solid var(--line);border-bottom:1px solid var(--line);":""}"${v.tip?` title="${attr(v.tip)}"`:""}>${v.h}</td>`; }).join("")+`</tr>`; }).join("");
  // 컨센 줄
  const consRow=!hasSpec?"":`<tr><td class="l" style="color:var(--muted);font-size:11.5px">참고: 네이버 컨센 매출 / 영업이익</td>`+cols.map((o,i)=>{ const c=cons[o.q];
    return `<td style="color:var(--muted);font-size:11px;${yrEdge(i)?"border-left:2px solid var(--line);":""}">${c&&!o.act&&!o.cOnly?`${f1(c.rev)} / ${f1(c.op)}`:""}</td>`; }).join("")+`</tr>`;
  // 머리 카드
  const card=(t,v,sub)=>`<div style="flex:1;min-width:170px;background:var(--panel);border:1px solid var(--line-soft);border-radius:var(--radius);padding:12px 14px">
    <div style="font-size:11.5px;color:var(--muted);font-weight:700">${t}</div><div style="font-size:19px;font-weight:800;margin-top:3px">${v}</div>
    <div style="font-size:11px;color:var(--muted2);margin-top:3px;line-height:1.45">${sub||""}</div></div>`;
  const vsC=(o)=>{ const c=cons[o.q]; if(!c||o.cOnly) return o.cOnly?"컨센":""; return `컨센 대비 ${pc(o.rev/c.rev-1)} / ${c.op>0?pc(o.op/c.op-1):"—"}`; };
  const nq=Q[nextQ]||cols.find(o=>o.q===nextQ), y6=cols.find(o=>o.q==="2026"), y7=cols.find(o=>o.q==="2027");
  const head=`<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
    ${nq?card(`${lab(nq)} 매출 / 영업이익`, `${f1(nq.rev)} / ${f1(nq.op)}`, vsC(nq)):""}
    ${y6?card(`${lab(y6)} 매출 / 영업이익`, `${f1(y6.rev)} / ${f1(y6.op)}`, vsC(y6)):""}
    ${y7?card(`${lab(y7)} 매출 / 영업이익`, `${f1(y7.rev)} / ${f1(y7.op)}`, vsC(y7)):""}
    ${(y6&&mc&&y6.npp>0)?card("PER(현재 시총)", `${fmt(mc/y6.npp,1)} / ${y7&&y7.npp>0?fmt(mc/y7.npp,1):"—"}배`, `2026 / 2027 지배주주 순이익 · 시총 ${fmt0(mc*10)}억`):""}
  </div>`;
  // 가정 칸
  const asm=hasSpec?`<details class="fold" data-fold="ism_asm"${(()=>{ try{ return localStorage.getItem("fold_ism_asm")==="1"?" open":""; }catch(e){ return ""; } })()}><summary>가정 바꾸기 <span class="sub">부문 성장률·이익률 · 영업외·세율 — 이 브라우저에 기억</span></summary><div class="fold-b">
    <div style="display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px">`
    +segs.map(s=>{ const p=P.segs[s.k];
      return `<label>${attr(s.t)} 성장률(전년비)${(s.drv==="px"||s.drv==="pxa")&&s.px?` <span class="g">지표 없는 분기만</span>`:""} 2026 <input data-ismg="${attr(s.k)}" type="number" step="1" value="${Math.round(p.g*100)}" style="width:56px"> % <span class="g">자동 ${fmt(p.gAuto*100,0)}%</span> · 2027 <input data-ismg7="${attr(s.k)}" type="number" step="1" value="${Math.round(p.g7*100)}" style="width:56px"> %</label>`
        +(p.m!=null?`<label>이익률 <input data-ismm="${attr(s.k)}" type="number" step="0.5" value="${fmt(p.m*100,1).replace(/,/g,"")}" style="width:62px"> % <span class="g">자동 ${p.mAuto!=null?fmt(p.mAuto*100,1)+"%":"—"}</span></label>`:""); }).join("")
    +`<label>회사 이익률${P.lin?` <span class="g">넣으면 고정비형 대신</span>`:""} <input data-isma="opm" type="number" step="0.5" value="${fmt(P.opm*100,1).replace(/,/g,"")}" style="width:62px"> %</label>
      <label>영업외 <input data-isma="nonop" type="number" step="0.5" value="${fmt(P.nonop,1).replace(/,/g,"")}" style="width:62px"> 십억/분기</label>
      <label>세율 <input data-isma="tax" type="number" step="1" value="${Math.round(P.tax*100)}" style="width:52px"> %</label>
      <button data-ismreset style="font-size:11.5px">기본값으로</button></div></div></details>`:"";
  // 식 설명 — 부문마다 한 줄(식만). 조사 메모는 이름에 마우스를 올리면 보인다
  const method=hasSpec?`<div class="note" style="margin-top:6px;line-height:1.7">${segs.map(s=>{ const p=P.segs[s.k];
      const how=s.drv==="px"?(p.k!=null?`${attr(s.pxLab||"지표")} × ${fmt(p.k,3)}`:"전년 동기 × 성장률(지표 없음)")
        :s.drv==="pxa"?(p.ib!=null?`${fmt(p.ia,1)} + ${fmt(p.ib,3)} × ${attr(s.pxLab||"지표")}${p.r2!=null?` (R² ${fmt(p.r2,2)})`:""}`:"전년 동기 × 성장률(지표 없음)")
        :s.drv==="seas"?"직전 분기 × 계절":"전년 동기 × 성장률 · 직전 분기 × 계절 평균";
      const sch=/kpop/.test(String(s.src))?" · 일정 없는 분기는 기저만":"", w=s.pxw!=null&&(s.drv==="px"||s.drv==="pxa")?` · 지표 ${fmt(s.pxw*100,0)}%만 반영`:"";
      return `<b${s.note?` title="${attr(s.note)}" style="text-decoration:underline dotted;cursor:help"`:""}>${attr(s.t)}</b> ${how}${w}${sch}`; }).join("<br>")}
      <br><b${S.note?` title="${attr(S.note)}" style="text-decoration:underline dotted;cursor:help"`:""}>영업이익</b> ${P.lin?`매출 × ${fmt(P.lin.d*100,1)}% − 고정비 ${fmt(-P.lin.c,1)} (R² ${fmt(P.lin.r2,2)})`
        :segs.length&&segs.every(s=>P.segs[s.k].m!=null)?"부문 이익률 × 매출의 합":`매출 × ${fmt(P.opm*100,1)}%${P.seas.some(v=>v)?" ± 계절":""}`}
      ${Object.keys(S.oneoff||{}).length?`<br>* 영업이익에 일회성 포함(${Object.entries(S.oneoff).map(([q,v])=>`${c2QLab(q)} ${fmt(-v,1)}`).join(" · ")}${S.oneoffNote?` ${S.oneoffNote}`:""}) — 이익률은 빼고 계산`:""}</div>`
    :`<div class="note" style="margin-top:6px">아직 추정 전 — 실적(DART)과 컨센(C)만.</div>`;
  const D=B.D;
  // 실전 검산 한 줄 — 지난 분기를 '그 직전까지 실적 + 그 분기 지표'로 맞혀 본 매출 오차(설명은 마우스)
  let btLine="";
  if(hasSpec){ let bt=[]; try{ bt=ismBacktest(name,4); }catch(e){}
    if(bt.length){ const e=bt.map(r=>r.rev/r.revA-1), m=e.reduce((t,v)=>t+Math.abs(v),0)/e.length;
      const tip=bt.map(r=>`${c2QLab(r.q)} 매출 ${fmt(r.rev,1)} vs 실제 ${fmt(r.revA,1)}`+(r.op!=null&&r.opA!=null?` · 영업이익 ${fmt(r.op,1)} vs ${fmt(r.opA,1)}`:"")).join("\n");
      btLine=`<div class="note" style="margin-top:4px"><b title="${attr("그 분기 직전까지의 실적으로 계수·성장률·이익률을 다시 맞추고, 그 분기 지표를 넣어 매출을 맞혀 본 것 — 지표가 맞으면 모델이 얼마나 맞나\n"+tip)}" style="text-decoration:underline dotted;cursor:help">지난 분기 맞히기</b> 매출 오차 ${bt.map(r=>`${c2QLab(r.q)} ${pc(r.rev/r.revA-1)}`).join(" · ")} — 평균 ${fmt(m*100,0)}%</div>`; } }
  host.innerHTML=`<div class="sub-h" style="margin:2px 0 8px">분기 손익 모델 <span class="th-sub" style="display:inline;margin-left:6px">십억원 · E 우리 추정 · C 컨센 · ▸ 세부</span></div>
    ${head}
    <div class="tbl-wrap"><table class="mini-tbl ism-t"><thead><tr><th class="l">${attr(name)}</th>${th}</tr></thead><tbody>${body}${consRow}</tbody></table></div>
    ${method}${btLine}${asm}
    <p class="note">실적 DART ${D.fs==="OFS"?"별도":"연결"}(${(Object.keys(D.src||{}).sort().pop()||"").replace("-",".")}까지)${D.segHow?` · 부문 ${attr(D.segHow)}`:""} · 칸에 마우스 = 추정 식</p>`;
  host.querySelectorAll("[data-ismtg]").forEach(el=>el.addEventListener("click",()=>{ const g=el.dataset.ismtg, o=ismOpen[name]=ismOpen[name]||{}; o[g]=!o[g];
    try{ localStorage.setItem("ismOpen",JSON.stringify(ismOpen)); }catch(e){} renderIsm(name, host); }));
  const upd=()=>{ const a={seg:{}};
    host.querySelectorAll("[data-ismg]").forEach(i=>{ const s=(a.seg[i.dataset.ismg]=a.seg[i.dataset.ismg]||{}); s.g=+i.value; });
    host.querySelectorAll("[data-ismm]").forEach(i=>{ const s=(a.seg[i.dataset.ismm]=a.seg[i.dataset.ismm]||{}); s.m=+i.value; });
    host.querySelectorAll("[data-ismg7]").forEach(i=>{ const s=(a.seg[i.dataset.ismg7]=a.seg[i.dataset.ismg7]||{}); s.g7=+i.value; });
    // 자동값과 같은 칸은 저장하지 않는다(나중에 자동값이 바뀌면 따라가게)
    Object.keys(a.seg).forEach(k=>{ const p=P.segs[k]; if(!p) return; const s=a.seg[k];
      if(s.g!=null&&Math.round(p.gAuto*100)===s.g) delete s.g;
      if(s.g7!=null&&Math.round((s.g!=null?s.g/100:p.gAuto)*50)===s.g7) delete s.g7;  if(s.m!=null&&p.mAuto!=null&&Math.abs(p.mAuto*100-s.m)<0.05) delete s.m; });
    host.querySelectorAll("[data-isma]").forEach(i=>{ const k=i.dataset.isma, v=+i.value, au={opm:P.opmAuto*100, nonop:P.nonopAuto, tax:P.taxAuto*100}[k];
      if(au==null||Math.abs(au-v)>(k==="tax"?0.5:0.05)) a[k]=v; });
    ismAsmSave(name, a); renderIsm(name, host); };
  host.querySelectorAll("[data-ismg],[data-ismm],[data-isma]").forEach(i=>i.addEventListener("change",upd));
  const rb=host.querySelector("[data-ismreset]"); if(rb) rb.addEventListener("click",()=>{ ismAsmSave(name,{}); renderIsm(name, host); });
}
