/* Unified datacenter economic model v3 — browser mirror of src/inresearch/knowledge/economics.py.
   Engine first (same functions, same names, same output keys as the Python reference; tests/unit/test_model.py
   runs both on every preset and requires equality), then the one ledger page (web/pages/ledger.html). */
(() => {
  'use strict';
  const HOURS=8760;
  const CATS=['capex_facility','capex_it','energy','demand','water','staff','maintenance','maintenance_it','software','insurance_tax','bandwidth','other','lease','decommission'];
  const OPEX_CATS=CATS.slice(2),IT_ONLY=['capex_it','maintenance_it'];
  const REDUNDANCY={n:{electrical:0.85,mechanical:0.85},n_plus_1:{electrical:1,mechanical:1},'2n':{electrical:1.35,mechanical:1.2}};
  const TABLES=[['site','regions'],['cooling','coolings'],['it_class','it_classes'],['tenancy','tenancies'],['price_path','price_paths'],['tenant_credit','tenant_credits']];
  const OWNER_PARTS={own:['building','electrical','mechanical','fitout'],bot:['building','fitout'],lease:['fitout'],colo:[]};
  const PARTNER_PARTS={bot:['electrical','mechanical']};
  const CAPITAL_KEYS=['it_capex_per_kw','shell_capex_per_mw','btm_capex_per_mw','capex_building','capex_electrical','capex_mechanical','capex_fitout','land_per_mw'];
  const sum=xs=>xs.reduce((s,x)=>s+x,0);
  const crf=(r,n)=>r===0?1/n:r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);
  function irr(flows){
    const npv=r=>flows.reduce((s,f,t)=>s+f/Math.pow(1+r,t),0);
    let lo=-0.99,hi=10;if(npv(lo)*npv(hi)>0)return null;
    for(let i=0;i<200;i++){const mid=(lo+hi)/2;if(npv(lo)*npv(mid)<=0)hi=mid;else lo=mid;}
    return (lo+hi)/2;
  }
  function applyTable(a,key,spec){
    const table=Object.fromEntries(TABLES)[key];const rec=table&&spec[table]?spec[table][a[key]]:null;if(!rec)return a;
    for(const k in rec)if(k in a&&k!==key)a[k]=rec[k];return a;
  }
  function withPreset(spec,id){
    const a={...spec.assumptions};const p=id&&spec.presets?spec.presets[id]:null;if(!p)return a;
    const ch={...(p.changes||{})};for(const [key] of TABLES)if(key in ch){a[key]=ch[key];applyTable(a,key,spec);}
    Object.assign(a,ch);return a;
  }
  const effectiveMw=a=>{const q=a.energy_quota_mw||0;return q>0?Math.min(a.it_mw,q):a.it_mw;};
  function capex(a,spec){
    const red=((spec&&spec.redundancy_factors)||REDUNDANCY)[a.redundancy]||REDUNDANCY.n_plus_1;
    let hard,softPct,contPct;
    if(a.capex_basis==='generation'){
      const me=Math.max(0,a.shell_capex_per_mw-a.capex_building-a.capex_fitout),em=a.capex_electrical+a.capex_mechanical,eShare=em>0?a.capex_electrical/em:0.6;
      hard={building:a.capex_building,electrical:me*eShare,mechanical:me*(1-eShare),fitout:a.capex_fitout};softPct=contPct=0;
    }else{
      hard={building:a.capex_building,electrical:a.capex_electrical*red.electrical,mechanical:a.capex_mechanical*red.mechanical,fitout:a.capex_fitout};softPct=a.soft_cost_pct;contPct=a.contingency_pct;
    }
    const mode=a.facility_mode,btm=(mode==='own'||mode==='bot')?a.btm_capex_per_mw:0;
    const ownerHard=sum((OWNER_PARTS[mode]||[]).map(k=>hard[k]))+btm,soft=ownerHard*softPct,cont=ownerHard*contPct;
    const partner=sum((PARTNER_PARTS[mode]||[]).map(k=>hard[k]))*(1+softPct+contPct);
    const allHard=sum(Object.values(hard))+a.btm_capex_per_mw;
    return {hard,btm,soft,contingency:cont,owner_hard:ownerHard,facility:ownerHard+soft+cont,partner,land:(mode==='own'||mode==='bot')?a.land_per_mw:0,
      all_in:allHard*(1+softPct+contPct),it:a.it_capex_per_kw/1000,landlord:(allHard-hard.fitout)*(1+softPct+contPct)};
  }
  function opyear(a,cap,mw,ramp,util,escP,escO,priceMult,feeOn){
    const itKw=mw*1000,coloBm=a.business_model==='colo',itCapex=coloBm?0:a.it_capex_per_kw*itKw,facilityCapex=cap.facility*mw*1e6,ownerHard=cap.owner_hard*mw*1e6;
    const owned=a.facility_mode==='own'||a.facility_mode==='bot',itKwh=itKw*a.load_factor*ramp*HOURS,r={};CATS.forEach(k=>r[k]=0);
    r.it_kwh=itKwh;r.energy=itKwh*a.pue*a.power_price*escP;r.demand=itKw*a.pue*ramp*a.demand_rate*12*escP;r.water=itKwh*a.wue/1000*a.water_price*escO;
    r.staff=a.fte_per_mw*mw*a.cost_per_fte*a.labor_index*escO;r.maintenance=ownerHard*a.maint_pct_facility*escO;r.maintenance_it=itCapex*a.maint_pct_it*escO;
    r.software=a.software_per_mw*mw*1e6*escO;r.insurance_tax=facilityCapex*(a.insurance_pct+(owned?a.property_tax_rate:0))*escO;r.bandwidth=a.bandwidth_per_mw*mw*1e6*escO;r.other=a.other_opex_per_mw*mw*1e6*escO;
    const mode=a.facility_mode;
    if(mode==='lease')r.lease=a.shell_rent_per_mw*mw*1e6*escO;else if(mode==='colo')r.lease=a.colo_rate*itKw*12*escO;else if(mode==='bot'&&feeOn)r.lease=cap.partner*mw*1e6*crf(a.bot_service_rate,a.bot_term_years);
    r.gpu_hours=coloBm?0:mw*a.gpus_per_mw*HOURS*util;
    if(a.business_model==='gpu_rental')r.revenue=r.gpu_hours*a.price_gpu_hour*priceMult;else if(coloBm)r.revenue=a.price_colo_kw_month*itKw*12*ramp*priceMult;else r.revenue=0;
    r.opex=sum(OPEX_CATS.map(k=>r[k]));return r;
  }
  const roicDenominator=(a,invested)=>a.roic_basis==='avg_annual_capex'?invested/Math.max(1,a.construction_years):invested;
  function compute(a,spec){
    const cap=capex(a,spec),mw=effectiveMw(a),y=opyear(a,cap,mw,1,a.gpu_utilization,1,1,1,true),itKw=mw*1000;
    const itCapex=a.business_model==='colo'?0:a.it_capex_per_kw*itKw,facilityCapex=cap.facility*mw*1e6,land=cap.land*mw*1e6,invested=itCapex+facilityCapex+land;
    const itLife=a.it_refresh_years,shellLife=a.horizon_years,depIt=itCapex/itLife,depShell=facilityCapex/shellLife,revenue=y.revenue,opex=y.opex;
    const ebitda=revenue-opex,ebit=ebitda-depIt-depShell,nopat=ebit*(1-a.tax),denominator=roicDenominator(a,invested);
    const capitalCharge=itCapex*crf(a.wacc,itLife)+facilityCapex*crf(a.wacc,shellLife)+land*a.wacc,annualised=capitalCharge+opex,paidHours=y.gpu_hours;
    const unitCost=paidHours?annualised/paidHours:null,cash=nopat+depIt+depShell,residual=facilityCapex*Math.max(0,1-itLife/shellLife)+land;
    const debt=itCapex*a.compute_ltc,ads=debt?debt*crf(a.compute_debt_rate,itLife):0,equity=invested-debt;
    const flows=[-invested],levFlows=[-equity],revenuePath=[];let balance=debt;
    for(let t=0;t<itLife;t++){const revT=revenue*Math.pow(1+a.price_change,t);revenuePath.push(revT);const ebitT=revT-opex-depIt-depShell;flows.push(ebitT*(1-a.tax)+depIt+depShell);
      const interest=balance*a.compute_debt_rate,principal=debt?ads-interest:0;balance-=principal;levFlows.push(revT-opex-ads-Math.max(0,ebitT-interest)*a.tax);}
    flows[flows.length-1]+=residual;levFlows[levFlows.length-1]+=residual;
    const price=a.business_model==='gpu_rental'?a.price_gpu_hour:null,perMw=v=>mw?v/mw/1e6:null,opexBy={};OPEX_CATS.forEach(k=>opexBy[k]=y[k]);
    const annualCost=opex+depIt+depShell+(ebit-nopat);
    return {mw,gpus:mw*a.gpus_per_mw,paid_hours:paidHours,revenue,energy:y.energy,other:y.other,facility_cost:y.lease,opex,opex_by:opexBy,ebitda,dep_it:depIt,dep_shell:depShell,ebit,nopat,
      it_capex:itCapex,facility_capex:facilityCapex,land,invested,roic_denominator:denominator,roic:denominator?nopat/denominator:null,
      ebitda_margin:revenue?ebitda/revenue:null,ebit_margin:revenue?ebit/revenue:null,nopat_margin:revenue?nopat/revenue:null,
      capital_charge:capitalCharge,annualised,unit_cost:unitCost,surplus_per_hour:(price!=null&&unitCost!=null)?price-unitCost:null,coverage:annualised?revenue/annualised:null,
      payback:cash>0?invested/cash:null,irr:irr(flows),debt,equity,debt_service:ads,irr_levered:equity>0?irr(levFlows):null,revenue_path:revenuePath,
      capex_total:invested,annual_cost:annualCost,capex_per_mw:perMw(invested),revenue_per_mw:perMw(revenue),cost_per_mw:perMw(annualCost),nopat_per_mw:perMw(nopat),
      capex_per_gw:mw?invested/mw*1000:null,revenue_per_gw:mw?revenue/mw*1000:null,it_kwh:y.it_kwh,water_m3:y.it_kwh*a.wue/1000,
      capex_split:{it:cap.it,facility:cap.facility,land:cap.land,partner:cap.partner,hard:cap.hard,btm:cap.btm,soft:cap.soft,contingency:cap.contingency}};
  }
  function ledgers(a,spec){
    const c=compute(a,spec),mw=c.mw,cap=capex(a,spec);
    const shellCapex=cap.landlord*mw*1e6,land=a.land_per_mw*mw*1e6,invested=shellCapex+land,rent=a.shell_rent_per_mw*mw*1e6,term=a.lease_term;
    const rents=[];for(let t=0;t<term;t++)rents.push(rent*Math.pow(1+a.escalator,t));
    const nois=rents.map(r=>r*a.noi_margin),noi=rent*a.noi_margin,debt=invested*a.shell_ltc,ads=debt?debt*crf(a.debt_rate,term):0,equity=invested-debt,residual=shellCapex*a.residual_share;
    const unlev=[-invested,...nois];unlev[unlev.length-1]+=residual;const lev=[-equity,...nois.map(n=>n-ads)];lev[lev.length-1]+=residual;
    const depS=shellCapex/a.horizon_years;let bal=debt;const afterTax=[-equity];
    for(const n of nois){const interest=bal*a.debt_rate,principal=debt?ads-interest:0;bal-=principal;afterTax.push(n-ads-Math.max(0,n-depS-interest)*a.tax);}
    afterTax[afterTax.length-1]+=residual;
    const optYears=a.renewal_options*a.renewal_years,optRents=[];for(let t=0;t<optYears;t++)optRents.push(rent*Math.pow(1+a.escalator,term+t));
    const withOpt=[-invested,...nois,...optRents.map(r=>r*a.noi_margin*a.renewal_probability)];withOpt[withOpt.length-1]+=residual;
    const taxY1=Math.max(0,noi-depS-debt*a.debt_rate)*a.tax;
    const shell={invested,rent_y1:rent,noi_y1:noi,yield_on_cost:invested?noi/invested:null,contract_value:sum(rents),contract_value_with_options:sum(rents)+sum(optRents),option_years:optYears,
      debt,equity,debt_service:ads,dscr:ads?noi/ads:null,cash_on_cash:equity>0?(noi-ads)/equity:null,cash_on_cash_after_tax:equity>0?(noi-ads-taxY1)/equity:null,tax_y1:taxY1,
      payback:noi>0?invested/noi:null,irr_unlevered:irr(unlev),irr_levered:equity>0?irr(lev):null,irr_levered_after_tax:equity>0?irr(afterTax):null,irr_with_options:irr(withOpt)};
    const mHours=c.paid_hours*a.monetized_share,tokens=mHours*3600*a.tokens_per_gpu_sec,mRevenue=tokens/1e6*a.price_per_m_tokens;
    let mCost,mInvested;if(a.compute_source==='own'){mCost=c.opex+c.dep_it+c.dep_shell;mInvested=c.invested;}else{mCost=mHours*a.rent_price;mInvested=0;}
    const mEbit=mRevenue-mCost,mNopat=mEbit*(1-a.tax);
    const model={tokens,revenue:mRevenue,cost:mCost,ebit:mEbit,nopat:mNopat,nopat_margin:mRevenue?mNopat/mRevenue:null,revenue_per_gpu_hour:mHours?mRevenue/mHours:null,invested:mInvested,roic:mInvested?mNopat/mInvested:null};
    const chipGp=c.it_capex*a.accelerator_share*a.chip_gross_margin;
    const chip={accelerator_capex:c.it_capex*a.accelerator_share,gross_profit:chipGp,gross_profit_per_year:chipGp/a.it_refresh_years};
    const split={chip:chip.gross_profit_per_year,landlord:a.facility_mode==='lease'?noi:0,compute:a.compute_source==='own'?0:c.nopat,model:mNopat};
    const stack={accelerators:c.it_capex*a.accelerator_share,other_it:c.it_capex*(1-a.accelerator_share),facility:c.facility_capex,partner:cap.partner*mw*1e6,land:c.land};
    return {compute:c,shell,model,chip,split,capex_stack:stack};
  }
  function lifecycle(a,spec){
    const cap=capex(a,spec),mw=effectiveMw(a),itKw=mw*1000,C=a.construction_years,W=a.gate_wait_years,H=a.horizon_years,P=W+C;
    const itCapex=a.business_model==='colo'?0:a.it_capex_per_kw*itKw,facilityCapex=(cap.facility+cap.land)*mw*1e6,years=[];
    for(let y=0;y<P+H;y++){
      const row={};CATS.forEach(k=>row[k]=0);Object.assign(row,{year:y-P+1,it_kwh:0,gpu_hours:0,revenue:0});
      if(y<P){if(y>=W)row.capex_facility=facilityCapex/C;row.opex=0;years.push(row);continue;}
      const t=y-P,ramp=t===0?a.ramp_year1:t===1?a.ramp_year2:1,util=t===0?a.util_year1:t===1?a.util_year2:a.gpu_utilization;
      Object.assign(row,opyear(a,cap,mw,ramp,util,Math.pow(1+a.power_escalation,t),Math.pow(1+a.opex_escalation,t),Math.pow(1+a.price_change,t),t<a.bot_term_years));
      if(t===0)row.capex_it=itCapex;else if(a.it_refresh_years&&t%a.it_refresh_years===0&&t<H)row.capex_it=itCapex*a.refresh_cost_factor;
      if(t===H-1)row.decommission=cap.facility*mw*1e6*a.decommission_pct;
      years.push(row);
    }
    years.forEach(r=>{r.total=sum(CATS.map(k=>r[k]));r.capex=r.capex_facility+r.capex_it;r.opex=r.total-r.capex;r.net=r.revenue-r.total;});
    const rate=a.wacc,disc=y=>1/Math.pow(1+rate,y+1),pv={};CATS.forEach(k=>pv[k]=years.reduce((s,r,i)=>s+r[k]*disc(i),0));
    const pvTotal=sum(Object.values(pv)),nominalTotal=sum(years.map(r=>r.total)),pvItKwh=years.reduce((s,r,i)=>s+r.it_kwh*disc(i),0),pvGpuHours=years.reduce((s,r,i)=>s+r.gpu_hours*disc(i),0),pvRevenue=years.reduce((s,r,i)=>s+r.revenue*disc(i),0);
    let annuity=0;for(let t=0;t<H;t++)annuity+=disc(P+t);
    const levelised=pvTotal/annuity,lev={};CATS.forEach(k=>lev[k]=pv[k]/annuity);const facilityLevelised=levelised-sum(IT_ONLY.map(k=>lev[k]));
    const out={years,pv,pv_total:pvTotal,nominal_total:nominalTotal,pv_revenue:pvRevenue,npv:pvRevenue-pvTotal,irr:irr(years.map(r=>r.net)),annuity,levelised,lev,facility_levelised:facilityLevelised,
      lead_years:P,lead_months:P*12+a.permit_months,capex_per_mw:{...cap.hard,btm:cap.btm,soft:cap.soft,contingency:cap.contingency,land:cap.land,facility:cap.facility,partner:cap.partner,it:cap.it},
      facility_capex:facilityCapex,it_capex:itCapex,per_mw_year:levelised/mw,per_kw_month:levelised/itKw/12,per_kw_month_facility:facilityLevelised/itKw/12,
      per_it_kwh:pvItKwh?pvTotal/pvItKwh:null,per_gpu_hour:pvGpuHours?pvTotal/pvGpuHours:null,capex_share:pvTotal?(pv.capex_facility+pv.capex_it)/pvTotal:null};
    const bm=a.business_model;let market=null,cost=null,unit=null;
    if(bm==='gpu_rental'&&out.per_gpu_hour){market=a.price_gpu_hour;cost=out.per_gpu_hour;unit='$/GPU·h';}else if(bm==='colo'){market=a.price_colo_kw_month;cost=out.per_kw_month_facility;unit='$/kW·月';}
    out.benchmark={model:bm,market,cost,unit,margin:market?(market-cost)/market:null};return out;
  }
  function inverse(a,spec){
    const c=compute(a,spec),mw=c.mw,t=a.tax,target=a.target_roic,nopat=target*c.roic_denominator,ebit=nopat/(1-t),dep=c.dep_it+c.dep_shell,revenue=ebit+dep+c.opex,fullHours=c.gpus*HOURS;
    const price=c.paid_hours?revenue/c.paid_hours:null,utilization=(fullHours&&a.price_gpu_hour)?revenue/(fullHours*a.price_gpu_hour):null;
    const s=capexScaleForTarget(a,spec,target);
    return {target_roic:target,roic_basis:a.roic_basis,denominator:c.roic_denominator,required_nopat:nopat,required_ebit:ebit,required_revenue:revenue,required_revenue_per_gw:mw?revenue/mw*1000:null,
      ebit_margin:revenue?ebit/revenue:null,nopat_margin:revenue?nopat/revenue:null,required_price:price,required_utilization:utilization,capex_scale:s,capex_ceiling:s!=null?c.invested*s:null,
      capex_ceiling_per_gw:(s!=null&&mw)?c.invested*s/mw*1000:null,current_roic:c.roic,current_revenue:c.revenue,gap:revenue-c.revenue};
  }
  function scaleCapital(a,s){const b={...a};for(const k of CAPITAL_KEYS)b[k]=a[k]*s;return b;}
  function capexScaleForTarget(a,spec,target){
    const roic=s=>{const r=compute(scaleCapital(a,s),spec).roic;return r==null?-1:r;};
    let lo=1e-6,hi=1;if(roic(lo)<target)return null;while(roic(hi)>target&&hi<1e6)hi*=2;
    for(let i=0;i<80;i++){const mid=(lo+hi)/2;if(roic(mid)>=target)lo=mid;else hi=mid;}
    return (lo+hi)/2;
  }
  function scaledCapex(a,capexPerGw,spec){const c=compute(a,spec);if(!c.capex_per_gw)return {...a};return scaleCapital(a,capexPerGw*1e9/c.capex_per_gw);}
  function grid(a,spec){
    const g=(spec&&spec.grid)||{},capexAxis=g.capex_per_gw||[34,38,42.4,46,51],priceFactors=g.price_factors||[0.6,0.8,1,1.2,1.4],utilAxis=g.utilization||[0.45,0.55,0.65,0.75,0.85,0.95],cells=[];
    for(const u of utilAxis){const plane=[];for(const cpg of capexAxis){const b=scaledCapex(a,cpg,spec);plane.push(priceFactors.map(f=>compute({...b,gpu_utilization:u,price_gpu_hour:a.price_gpu_hour*f},spec).roic));}cells.push(plane);}
    return {capex_per_gw:capexAxis,price_factors:priceFactors,prices:priceFactors.map(f=>a.price_gpu_hour*f),utilization:utilAxis,roic:cells,anchors:(spec&&spec.anchors)||[]};
  }
  function sensitivity(a,spec){
    const baseC=compute(a,spec),baseL=lifecycle(a,spec),rows=[];
    for(const d of (spec&&spec.sensitivity_drivers)||[]){const lo={...a},hi={...a};
      if(d.delta_abs){lo[d.key]=Math.max(0,a[d.key]-d.delta_abs);hi[d.key]=a[d.key]+d.delta_abs;}else{lo[d.key]=a[d.key]*(1-d.delta);hi[d.key]=a[d.key]*(1+d.delta);}
      const cl=compute(lo,spec),ch=compute(hi,spec),ll=lifecycle(lo,spec),lh=lifecycle(hi,spec);
      rows.push({key:d.key,label:d.label,delta:d.delta==null?null:d.delta,delta_abs:d.delta_abs==null?null:d.delta_abs,roic_lo:(cl.roic||0)-(baseC.roic||0),roic_hi:(ch.roic||0)-(baseC.roic||0),kw_lo:ll.per_kw_month-baseL.per_kw_month,kw_hi:lh.per_kw_month-baseL.per_kw_month});}
    return rows;
  }
  const run=(a,spec)=>({inputs:a,ledgers:ledgers(a,spec),lifecycle:lifecycle(a,spec),inverse:inverse(a,spec),grid:grid(a,spec),sensitivity:sensitivity(a,spec)});
  const ENGINE={HOURS,CATS,compute,ledgers,lifecycle,inverse,grid,sensitivity,run,withPreset,applyTable,capex,crf,irr,effectiveMw};
  if(typeof module!=='undefined'&&module.exports){module.exports=ENGINE;return;}
  window.InresearchModel=ENGINE;

  /* ---------------------------------------------------------------- the ledger page ---------------------------------------------------------------- */
  const app=document.getElementById('model-app');if(!app)return;
  const byId=id=>document.getElementById(id);
  const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined&&text!==null)e.textContent=text;return e;};
  const svgEl=(tag,attrs)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const k in attrs)e.setAttribute(k,attrs[k]);return e;};
  const text=(x,y,cls,t,anchor)=>Object.assign(svgEl('text',{x,y,class:cls,'text-anchor':anchor||'start'}),{textContent:t});
  const money=n=>n==null||!isFinite(n)?'—':(n<0?'−':'')+(Math.abs(n)>=1e9?'$'+(Math.abs(n)/1e9).toFixed(2)+'B':Math.abs(n)>=1e6?'$'+(Math.abs(n)/1e6).toFixed(1)+'M':'$'+Math.round(Math.abs(n)).toLocaleString());
  const money3=n=>n==null||!isFinite(n)?'—':Math.abs(n)>=1e9?'$'+(n/1e9).toFixed(3)+'B':money(n);
  const pct=(x,d=1)=>x==null||!isFinite(x)?'—':(x*100).toFixed(d)+'%';
  const num=(x,d=1)=>x==null||!isFinite(x)?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
  const yrs=x=>x==null||!isFinite(x)?'—':x.toFixed(1)+' 年';
  const LABEL={capex_facility:'设施资本开支',capex_it:'IT 资本开支与更新',energy:'电费',demand:'需量费',water:'水费',staff:'运维人员',maintenance:'设施维护',maintenance_it:'IT 维护',software:'软件与 DCIM',insurance_tax:'保险与财产税',bandwidth:'带宽',other:'其他运营',lease:'租金 / 托管费 / BOT 服务费',decommission:'退役'};
  const COLOR={capex_facility:'var(--ui-green)',capex_it:'var(--ui-accent)',energy:'var(--ui-yellow)',demand:'color-mix(in srgb,var(--ui-yellow) 60%,var(--ui-surface))',water:'color-mix(in srgb,var(--ui-info-ink,#405879) 70%,var(--ui-surface))',staff:'var(--ui-purple)',maintenance:'color-mix(in srgb,var(--ui-green) 60%,var(--ui-surface))',maintenance_it:'color-mix(in srgb,var(--ui-accent) 55%,var(--ui-surface))',software:'color-mix(in srgb,var(--ui-purple) 55%,var(--ui-surface))',insurance_tax:'var(--ui-muted)',bandwidth:'color-mix(in srgb,var(--ui-muted) 60%,var(--ui-surface))',other:'color-mix(in srgb,var(--ui-muted) 40%,var(--ui-surface))',lease:'var(--ui-red)',decommission:'color-mix(in srgb,var(--ui-red) 50%,var(--ui-surface))'};
  const STATUS={input:['用户给定','input'],sourced:['已有来源','sourced'],assumed:['作者假设','assumed'],needed:['待获取','needed']};
  const MODE={own:'自建自持',bot:'BOT',lease:'租带电壳',colo:'托管'};
  let spec,values,prices,activePreset='',view='lifecycle';
  const region=()=>spec.regions[values.site]||{};
  const gaps=()=>new Set(region().gaps||[]);

  function applyPreset(id){values=withPreset(spec,id);activePreset=id;byId('preset-note').textContent=(spec.presets[id]&&spec.presets[id].note)||'';renderInputs();render();}
  function renderPresets(){
    const host=byId('presets');host.replaceChildren();let group='';
    for(const [id,p] of Object.entries(spec.presets)){if(p.group!==group){group=p.group;host.append(make('span','preset-group',group));}const b=make('button','',p.label);b.type='button';b.dataset.id=id;b.title=p.note||'';b.addEventListener('click',()=>applyPreset(id));host.append(b);}
  }
  function markPreset(){document.querySelectorAll('#presets button').forEach(b=>b.classList.toggle('active',b.dataset.id===activePreset));}
  function renderRegion(){
    const r=region(),g=gaps(),host=byId('region-card');host.replaceChildren();
    const gate=values.gate==='chip'?'芯片门槛':'电力门槛';
    host.append(make('b','',r.label||values.site),make('span','',`${gate} · 门槛等待 ${values.gate_wait_years} 年 · 审批 ${values.permit_months} 个月 · 建设 ${values.construction_years} 年`),
      make('span','',values.energy_quota_mw>0?`能耗配额 ${values.energy_quota_mw} MW`:'无能耗配额'),make('span','',`电价 $${num(values.power_price,4)}/kWh · 需量 $${num(values.demand_rate,1)}/kW·月 · 土地 ${num(values.land_per_mw,2)} $M/MW`),
      make('span',g.size?'gap-count':'', g.size?`缺 ${g.size} 项：${[...g].map(k=>spec.inputs[k]?spec.inputs[k].label:k).join('、')}`:'该地区每个数都有登记来源'));
    host.title=r.source||'';
  }
  function renderInputs(){
    const form=byId('model-inputs');const openState={};form.querySelectorAll('details').forEach(d=>openState[d.dataset.group]=d.open);form.replaceChildren();const g=gaps();
    spec.groups.forEach((group,gi)=>{
      const box=make('details','input-group');box.dataset.group=group.id;box.open=group.id in openState?openState[group.id]:gi<2;
      const sum=make('summary');sum.append(make('b','',group.label),make('small','',group.hint));box.append(sum);
      for(const id of group.inputs){
        const cfg=spec.inputs[id],ev=spec.evidence[id]||{status:'needed'},row=make('div','input-row'),label=make('label');label.htmlFor='input-'+id;
        const badge=make('i','badge '+STATUS[ev.status][1]);badge.title=STATUS[ev.status][0]+(ev.note?'：'+ev.note:'')+(ev.fetch_what?'｜抓取：'+ev.fetch_what:'');
        label.append(badge,make('span','',cfg.label));if(g.has(id))label.append(make('em','gap','缺'));if(cfg.note)label.append(make('small','',cfg.note));
        const holder=make('div','input-box');
        if(cfg.type==='select'){const sel=make('select');sel.id='input-'+id;const opts=cfg.options?Object.entries(spec[cfg.options]).map(([k,v])=>[k,v.label]):cfg.choices;for(const [v,l] of opts){const o=make('option','',l);o.value=v;sel.append(o);}sel.value=values[id];
          sel.addEventListener('change',()=>{values[id]=sel.value;if(cfg.options)applyTable(values,id,spec);activePreset='';byId('preset-note').textContent='';renderInputs();render();});holder.append(sel);}
        else{const input=make('input');input.type='number';input.id='input-'+id;input.min=cfg.min;input.max=cfg.max;input.step=cfg.step;input.value=cfg.display==='percent'?Math.round(values[id]*10000)/100:values[id];
          input.addEventListener('input',()=>{const raw=Number(input.value);if(!Number.isFinite(raw))return;values[id]=cfg.display==='percent'?raw/100:cfg.step===1?Math.round(raw):raw;activePreset='';byId('preset-note').textContent='';render();});holder.append(input,make('span','',cfg.unit));}
        row.append(label,holder);box.append(row);
      }
      form.append(box);
    });
  }
  function tile(id,label,val,sub){const el=byId(id);el.replaceChildren(make('small','',label),make('strong','',val));if(sub!=null)el.append(make('span','sub',sub));}
  function projectLine(r){const a=values,l=r.lifecycle;byId('project-line').textContent=`${a.it_mw} MW${l.years&&effectiveMw(a)<a.it_mw?`（配额限至 ${effectiveMw(a)} MW）`:''} · ${region().label||a.site} · ${(spec.coolings[a.cooling]||{}).label||a.cooling} · ${(spec.it_classes[a.it_class]||{}).label||a.it_class} · ${MODE[a.facility_mode]} · ${a.gate==='chip'?'芯片门槛':'电力门槛'} · 等待 ${a.gate_wait_years} + 建设 ${a.construction_years} + 运营 ${a.horizon_years} 年 · 设施 ${num(l.capex_per_mw.facility,1)} + IT ${num(l.capex_per_mw.it,1)} $M/MW`;}

  /* view 1: cost structure and levelised cost (the former TCO page) */
  function renderLifecycle(r){
    const l=r.lifecycle,a=values,mw=l.years.length?effectiveMw(a):a.it_mw;
    tile('kpi-lev','平准化年成本',money(l.levelised),`名义合计 ${money(l.nominal_total)} · TCO 现值 ${money(l.pv_total)}`);
    tile('kpi-mw','每 MW·年',money(l.per_mw_year));tile('kpi-kw','每 kW·月','$'+num(l.per_kw_month,0),`设施部分 $${num(l.per_kw_month_facility,0)}`);
    tile('kpi-kwh','每 IT kWh','$'+num(l.per_it_kwh,3));tile('kpi-gpu','每付费 GPU 小时',l.per_gpu_hour?'$'+num(l.per_gpu_hour,2):'非 GPU',`稳态账本口径 ${r.ledgers.compute.unit_cost?'$'+num(r.ledgers.compute.unit_cost,2):'—'}`);
    tile('kpi-capex','资本开支占比',pct(l.capex_share,0),`拿地到投运 ${l.lead_months} 个月 · 项目 IRR ${pct(l.irr)}`);
    // structure bar
    const host=byId('structure');host.replaceChildren();const W=760,barH=26,left=70,svg=svgEl('svg',{viewBox:`0 0 ${W} 48`,class:'chart'});let x=left;
    svg.append(text(left-8,25,'chart-label','平准化','end'));
    for(const k of CATS){const v=l.lev[k];if(v<=0)continue;const w=v/l.levelised*(W-left-8);const rect=svgEl('rect',{x,y:8,width:w,height:barH,fill:COLOR[k]});rect.append(Object.assign(svgEl('title'),{textContent:LABEL[k]+' '+money(v)+' · '+pct(v/l.levelised)}));svg.append(rect);if(w>46)svg.append(text(x+w/2,25,'chart-inbar',pct(v/l.levelised,0),'middle'));x+=w;}
    host.append(svg);
    const legend=byId('structure-legend');legend.replaceChildren();for(const k of CATS){const v=l.lev[k];if(v<=0)continue;const it=make('div','legend-row');const sw=make('i');sw.style.background=COLOR[k];it.append(sw,make('span','',LABEL[k]),make('strong','',money(v/mw)+'/MW'),make('span','muted',pct(v/l.levelised)));legend.append(it);}
    // timeline
    const th=byId('timeline');th.replaceChildren();const H=260,bottom=34,top=12,n=l.years.length,colW=(W-54-10)/n,max=Math.max(...l.years.map(y=>Math.max(y.total,y.revenue)))*1.05,scale=(H-top-bottom)/max,tl=54;
    const tsvg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,class:'chart'});
    for(let i=0;i<=4;i++){const v=max/4*i,y=H-bottom-v*scale;tsvg.append(svgEl('line',{x1:tl,y1:y,x2:W-8,y2:y,stroke:'var(--ui-line)','stroke-dasharray':i?'2 3':''}));tsvg.append(text(tl-6,y+4,'chart-label',money(v),'end'));}
    l.years.forEach((row,i)=>{let y0=H-bottom;const xx=tl+i*colW+2,w=Math.max(2,colW-4);for(const k of CATS){const v=row[k];if(v<=0)continue;const h=v*scale;const rect=svgEl('rect',{x:xx,y:y0-h,width:w,height:h,fill:COLOR[k]});rect.append(Object.assign(svgEl('title'),{textContent:`第 ${row.year} 年 · ${LABEL[k]} ${money(v)}`}));tsvg.append(rect);y0-=h;}
      if(i%Math.ceil(n/12)===0||i===n-1)tsvg.append(text(xx+w/2,H-bottom+14,'chart-label',row.year<=0?(row.year<=1-a.construction_years?'等':'建'):String(row.year),'middle'));});
    if(l.years.some(y=>y.revenue>0)){const pts=l.years.map((row,i)=>`${tl+i*colW+colW/2},${H-bottom-row.revenue*scale}`).join(' ');tsvg.append(svgEl('polyline',{points:pts,fill:'none',stroke:'var(--ui-ink)','stroke-width':1.5,'stroke-dasharray':'4 3'}));}
    tsvg.append(text(W-8,H-4,'chart-label','等 = 门槛等待；建 = 建设期；虚线 = 收入（利用率爬坡与单价路径）；名义金额','end'));th.append(tsvg);
    byId('timeline-note').textContent=`折现率 ${pct(a.wacc,1)}；负载爬坡 ${pct(a.ramp_year1,0)}/${pct(a.ramp_year2,0)}，利用率爬坡 ${pct(a.util_year1,0)}/${pct(a.util_year2,0)} → 稳态 ${pct(a.gpu_utilization,0)}；IT 每 ${a.it_refresh_years} 年更新（造价 ${pct(a.refresh_cost_factor,0)}）；电价年涨 ${pct(a.power_escalation,1)}，运营年涨 ${pct(a.opex_escalation,1)}，单价年变动 ${pct(a.price_change,0)}；收入现值 ${money(l.pv_revenue)}，NPV ${money(l.npv)}。`;
    // table
    const tb=byId('cost-table');tb.replaceChildren();const table=make('table','bi'),thead=make('thead'),tr=make('tr');for(const h of ['成本项','平准化年成本','占比','每 kW·月','TCO 现值','名义合计'])tr.append(make('th','',h));thead.append(tr);table.append(thead);const body=make('tbody');
    for(const k of CATS){const v=l.lev[k];if(v<=0)continue;const row=make('tr');const sw=make('i');sw.style.background=COLOR[k];const c1=make('td');c1.append(sw,document.createTextNode(LABEL[k]));row.append(c1,make('td','',money(v)),make('td','',pct(v/l.levelised)),make('td','','$'+num(v/(mw*1000)/12,0)),make('td','',money(l.pv[k])),make('td','',money(l.years.reduce((s,y)=>s+y[k],0))));body.append(row);}
    const tot=make('tr','total');tot.append(make('td','','合计'),make('td','',money(l.levelised)),make('td','','100%'),make('td','','$'+num(l.per_kw_month,0)),make('td','',money(l.pv_total)),make('td','',money(l.nominal_total)));body.append(tot);table.append(body);tb.append(table);
    // capex bars
    const cb=byId('capex-bars');cb.replaceChildren();const items=[['building','建筑与土建'],['electrical','电气'],['mechanical','机械'],['fitout','机房装配'],['btm','表后电力'],['land','土地'],['soft','软成本'],['contingency','不可预见费'],['partner','BOT 合作方持有的机电'],['it','IT 设备']];
    const cp=l.capex_per_mw,cmax=Math.max(...items.map(([k])=>cp[k]||0),0.1);
    for(const [k,lab] of items){const v=cp[k]||0;const row=make('div','bar-row'),track=make('div','bar-track'),fill=make('div','bar-fill');fill.style.width=(v/cmax*100)+'%';fill.style.background=k==='it'?'var(--ui-accent)':k==='partner'?'var(--ui-purple)':'var(--ui-green)';track.append(fill);row.append(make('label','',lab),track,make('output','',num(v,2)+' $M/MW'));cb.append(row);}
    byId('capex-note').textContent=a.capex_basis==='generation'?`按代际：非 IT 全包 ${num(a.shell_capex_per_mw,1)} $M/MW（建筑与装配按登记值，其余为机电），无另计软成本；运营方实付设施 ${num(cp.facility,1)} + IT ${num(cp.it,1)} $M/MW。`:`按部件：硬成本 × 冗余系数 ${spec.redundancy_factors[a.redundancy].label}，加软成本 ${pct(a.soft_cost_pct,0)} 与不可预见费 ${pct(a.contingency_pct,0)}；运营方实付设施 ${num(cp.facility,1)} + IT ${num(cp.it,1)} $M/MW${cp.partner?`；合作方持有机电 ${num(cp.partner,1)} $M/MW`:''}。`;
    // benchmark compare
    const bm=l.benchmark,bc=byId('benchmark-compare');bc.replaceChildren();
    if(!bm.market)bc.append(make('p','muted','自用口径不做市场对标，只看成本。'));else{const mx=Math.max(bm.market,bm.cost)*1.1;for(const [lab,v,c] of [['平准化单位成本',bm.cost,'var(--ui-accent)'],['市场价格',bm.market,'var(--ui-yellow)']]){const row=make('div','bar-row'),track=make('div','bar-track'),fill=make('div','bar-fill');fill.style.width=(v/mx*100)+'%';fill.style.background=c;track.append(fill);row.append(make('label','',lab),track,make('output','','$'+num(v,bm.unit==='$/GPU·h'?2:0)+' '+bm.unit));bc.append(row);}
      const m=make('p','bench-verdict '+(bm.margin>=0?'better':'worse'),bm.margin>=0?`市场价高于成本 ${pct(bm.margin,0)}：按当前假设该项目可覆盖全生命周期成本（含 ${pct(a.wacc,0)} 资本回报）。`:`市场价低于成本 ${pct(-bm.margin,0)}：按当前假设该项目无法在 ${pct(a.wacc,0)} 资本成本下收回全生命周期成本。`);bc.append(m);if(bm.model==='colo')bc.append(make('p','muted','托管口径的成本不含 IT 资本开支与 IT 维护（租户自带设备）。'));}
    // scenarios across presets
    const sh=byId('scenario-table');sh.replaceChildren();const st=make('table','bi'),sth=make('thead'),str=make('tr');for(const h of ['情景','地区','持有','设施 $M/MW','每 kW·月','每 GPU·h','ROIC','需收入 $B/GW','拿地到投运'])str.append(make('th','',h));sth.append(str);st.append(sth);const sb=make('tbody');
    const list=Object.entries(spec.presets).map(([id,p])=>[p.label,withPreset(spec,id),id===activePreset]);if(!activePreset)list.unshift(['当前假设',values,true]);
    for(const [lab,aa,cur] of list){const c=compute(aa,spec),ll=lifecycle(aa,spec),inv=inverse(aa,spec),row=make('tr');if(cur)row.className='current';for(const v of [lab,(spec.regions[aa.site]||{}).label||aa.site,MODE[aa.facility_mode],num(ll.capex_per_mw.facility,1),'$'+num(ll.per_kw_month,0),ll.per_gpu_hour?'$'+num(ll.per_gpu_hour,2):'—',pct(c.roic),inv.required_revenue_per_gw?num(inv.required_revenue_per_gw/1e9,1):'—',ll.lead_months+' 个月'])row.append(make('td','',v));sb.append(row);}
    st.append(sb);sh.append(st);
    // tornado on ROIC
    const tn=byId('tornado');tn.replaceChildren();const rows=r.sensitivity.slice().sort((x,y)=>Math.max(Math.abs(y.roic_lo),Math.abs(y.roic_hi))-Math.max(Math.abs(x.roic_lo),Math.abs(x.roic_hi)));
    const rowH=24,tleft=170,mid=tleft+(W-tleft-60)/2,span=Math.max(...rows.map(x=>Math.max(Math.abs(x.roic_lo),Math.abs(x.roic_hi))),0.01),sc=(W-tleft-60)/2/span;
    const ts=svgEl('svg',{viewBox:`0 0 ${W} ${rows.length*rowH+6}`,class:'chart'});ts.append(svgEl('line',{x1:mid,y1:0,x2:mid,y2:rows.length*rowH+6,stroke:'var(--ui-line)'}));
    rows.forEach((row,i)=>{const y=i*rowH+3;ts.append(text(tleft-8,y+14,'chart-label',row.label+(row.delta_abs?` ±${row.delta_abs}`:` ±${Math.round(row.delta*100)}%`),'end'));
      for(const v of [row.roic_lo,row.roic_hi]){const w=Math.abs(v)*sc,xx=v<0?mid-w:mid;const rect=svgEl('rect',{x:xx,y,width:Math.max(1,w),height:17,fill:v<0?'var(--ui-red)':'var(--ui-green)',opacity:.85});rect.append(Object.assign(svgEl('title'),{textContent:row.label+' → ROIC '+pct((r.ledgers.compute.roic||0)+v)}));ts.append(rect);ts.append(text(v<0?xx-4:xx+w+4,y+13,'chart-value',(v>=0?'+':'−')+pct(Math.abs(v)),v<0?'end':'start'));}});
    tn.append(ts);byId('tornado-note').textContent=`基准 ROIC ${pct(r.ledgers.compute.roic)}；左（红）为该因子变动后回报下降，右（绿）为上升；单因素，其他不变。`;
  }

  /* view 2: the four ledgers (the former economics page) */
  function renderLedgers(r){
    const a=values,c=r.ledgers.compute,s=r.ledgers.shell,m=r.ledgers.model,ch=r.ledgers.chip;
    tile('kpi-chip','芯片厂商毛利（年化）',money(ch.gross_profit_per_year),'加速器 '+money(ch.accelerator_capex)+' × '+pct(a.chip_gross_margin,0));
    tile('kpi-shell','壳层成本收益率',pct(s.yield_on_cost),`租金 ${money(s.rent_y1)}/年 ÷ 投资 ${money(s.invested)} · DSCR ${num(s.dscr,2)} · 杠杆 IRR ${pct(s.irr_levered)}`);
    tile('kpi-compute',`算力方 ROIC（${a.roic_basis==='avg_annual_capex'?'平均年资本开支':'总资本开支'}口径）`,pct(c.roic),`NOPAT ${money(c.nopat)} ÷ ${money(c.roic_denominator)} · 全成本 $${num(c.unit_cost,2)}/h · IRR ${pct(c.irr)}`);
    tile('kpi-model','模型方 NOPAT 利润率',pct(m.nopat_margin),`token 收入 ${money(m.revenue)} · 每 GPU 小时 $${num(m.revenue_per_gpu_hour,2)}`);
    // waterfall: revenue → opex → depreciation → tax → nopat
    const host=byId('waterfall');host.replaceChildren();const steps=[['收入',c.revenue,'var(--ui-yellow)'],['电费',-c.energy,'var(--ui-red)'],['其他运营与设施费',-(c.opex-c.energy),'var(--ui-red)'],['IT 折旧',-c.dep_it,'var(--ui-muted)'],['非 IT 折旧',-c.dep_shell,'var(--ui-muted)'],['所得税',-(c.ebit-c.nopat),'var(--ui-muted)'],['NOPAT',c.nopat,'var(--ui-green)']];
    const W=760,H=220,left=54,bottom=40,top=10,colW=(W-left-10)/steps.length,mx=Math.max(c.revenue,1)*1.05,sc=(H-top-bottom)/mx,svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,class:'chart'});let level=0;
    steps.forEach(([lab,v,col],i)=>{const x=left+i*colW+6,w=colW-12;let y0,y1;if(i===0||i===steps.length-1){y0=0;y1=v;level=v;}else{y0=level;y1=level+v;level=y1;}const top_=H-bottom-Math.max(y0,y1)*sc,h=Math.abs(y1-y0)*sc;const rect=svgEl('rect',{x,y:top_,width:w,height:Math.max(1,h),fill:col});rect.append(Object.assign(svgEl('title'),{textContent:lab+' '+money(v)}));svg.append(rect);svg.append(text(x+w/2,H-bottom+14,'chart-label',lab,'middle'));svg.append(text(x+w/2,top_-4,'chart-value',money(v),'middle'));});
    host.append(svg);byId('waterfall-note').textContent=`稳态一年：${money(c.paid_hours)} 付费 GPU 小时 × $${num(a.price_gpu_hour,2)} = ${money(c.revenue)}；EBITDA 利润率 ${pct(c.ebitda_margin)}，EBIT 利润率 ${pct(c.ebit_margin)}，NOPAT 利润率 ${pct(c.nopat_margin)}；ROIC ${pct(c.roic)}，回收期 ${yrs(c.payback)}。`;
    // capex stack
    const cs=byId('capex-stack');cs.replaceChildren();const st=r.ledgers.capex_stack,parts=[['accelerators','加速器','var(--ui-accent)'],['other_it','其他 IT','var(--ui-purple)'],['facility','设施（运营方实付）','var(--ui-green)'],['partner','机电（BOT 合作方）','var(--ui-yellow)'],['land','土地','var(--ui-muted)']],total=sum(parts.map(([k])=>st[k]))||1;
    const ssvg=svgEl('svg',{viewBox:`0 0 ${W} 60`,class:'chart'});let x=0;for(const [k,lab,col] of parts){const v=st[k];if(v<=0)continue;const w=v/total*(W-8);const rect=svgEl('rect',{x,y:8,width:w,height:26,fill:col});rect.append(Object.assign(svgEl('title'),{textContent:lab+' '+money(v)}));ssvg.append(rect);if(w>60)ssvg.append(text(x+w/2,25,'chart-inbar',lab+' '+pct(v/total,0),'middle'));x+=w;}
    ssvg.append(text(0,54,'chart-label',`资本开支 ${money(total)} = ${num(total/effectiveMw(a)/1e6*1000/1e3,1)} $B/GW；芯片厂商在其中的毛利 ${money(ch.gross_profit)}`));cs.append(ssvg);
    // ledger table
    const tb=byId('ledger-table');tb.replaceChildren();const table=make('table','bi'),body=make('tbody');
    const rowsL=[['芯片厂商','加速器采购 '+money(ch.accelerator_capex),'毛利 '+money(ch.gross_profit)+'（'+money(ch.gross_profit_per_year)+'/年）',''],
      ['壳层出租方','投资 '+money(s.invested)+' · 债务 '+money(s.debt)+'（'+pct(a.shell_ltc,0)+' @ '+pct(a.debt_rate)+'）','NOI '+money(s.noi_y1)+' · 合同总额 '+money(s.contract_value)+(s.option_years?'（含期权 '+money(s.contract_value_with_options)+'）':''),`成本收益率 ${pct(s.yield_on_cost)} · 现金回报 ${pct(s.cash_on_cash)}（税后 ${pct(s.cash_on_cash_after_tax)}）· IRR 无杠杆 ${pct(s.irr_unlevered)} / 杠杆 ${pct(s.irr_levered)} / 含期权 ${pct(s.irr_with_options)} · 回收 ${yrs(s.payback)}`],
      ['算力运营方','投资 '+money(c.invested)+'（IT '+money(c.it_capex)+' + 设施 '+money(c.facility_capex)+' + 土地 '+money(c.land)+'）'+(c.debt?' · GPU 债务 '+money(c.debt):''),'收入 '+money(c.revenue)+' · 运营 '+money(c.opex)+' · 折旧 '+money(c.dep_it+c.dep_shell),`ROIC ${pct(c.roic)} · IRR ${pct(c.irr)}${c.irr_levered!=null?' / 杠杆 '+pct(c.irr_levered):''} · 每 GPU 小时全成本 $${num(c.unit_cost,2)}，盈亏平衡对单价 ${c.surplus_per_hour!=null?(c.surplus_per_hour>=0?'+':'−')+'$'+num(Math.abs(c.surplus_per_hour),2):'—'}`],
      ['模型方',a.compute_source==='own'?'自有算力（投资同算力方）':'租用算力 $'+num(a.rent_price,2)+'/h','token 收入 '+money(m.revenue)+'（'+num(m.tokens/1e12,0)+' 万亿 token）· 成本 '+money(m.cost),`NOPAT ${money(m.nopat)} · 利润率 ${pct(m.nopat_margin)}${m.roic!=null?' · ROIC '+pct(m.roic):''}`]];
    for(const cells of rowsL){const tr=make('tr');cells.forEach((v,i)=>tr.append(make(i?'td':'th','',v)));body.append(tr);}table.append(body);tb.append(table);
    const sp=byId('split');sp.replaceChildren();const spl=r.ledgers.split,stot=sum(Object.values(spl).map(Math.abs))||1;for(const [k,lab,col] of [['chip','芯片厂商毛利/年','var(--ui-accent)'],['landlord','壳层 NOI','var(--ui-green)'],['compute','算力方 NOPAT','var(--ui-purple)'],['model','模型方 NOPAT','var(--ui-yellow)']]){const v=spl[k];const row=make('div','bar-row'),track=make('div','bar-track'),fill=make('div','bar-fill');fill.style.width=(Math.abs(v)/stot*100)+'%';fill.style.background=col;track.append(fill);row.append(make('label','',lab),track,make('output','',money(v)));sp.append(row);}
  }

  /* view 3: unit cost per effective device hour (the former cost page) */
  function renderUnit(r){
    const a=values,c=r.ledgers.compute;
    byId('cost-total').textContent=money3(c.annualised);byId('cost-per-hour').textContent=c.unit_cost!=null?'$'+num(c.unit_cost,2):'—';
    byId('cost-line').textContent=`年化全成本 = 资本回收（IT 按 ${a.it_refresh_years} 年、设施按 ${a.horizon_years} 年、土地按资本成本率 ${pct(a.wacc,0)} 年化）${money(c.capital_charge)} + 稳态运营 ${money(c.opex)}；÷ ${money(c.paid_hours)} 有效设备小时（${num(c.gpus,0)} 台 × 8,760 × ${pct(a.gpu_utilization,0)}）`;
    byId('metric-energy').textContent=num(c.it_kwh*a.pue/1e6,1)+' GWh';byId('metric-water').textContent=num(c.water_m3/1e3,1)+'k m³';byId('metric-capex').textContent=money3(c.invested);byId('metric-hours').textContent=num(c.paid_hours/1e6,1)+'M h';
    const tb=byId('unit-table');tb.replaceChildren();const table=make('table','bi'),thead=make('thead'),tr=make('tr');for(const h of ['成本项','年化金额','占比','每有效设备小时'])tr.append(make('th','',h));thead.append(tr);table.append(thead);const body=make('tbody');
    const rows=[['IT 资本回收',c.it_capex*crf(a.wacc,a.it_refresh_years)],['设施资本回收',c.facility_capex*crf(a.wacc,a.horizon_years)],['土地资本成本',c.land*a.wacc]].concat(OPEX_CATS.map(k=>[LABEL[k],c.opex_by[k]]));
    for(const [lab,v] of rows){if(!(v>0))continue;const row=make('tr');row.append(make('td','',lab),make('td','',money(v)),make('td','',pct(v/c.annualised)),make('td','',c.paid_hours?'$'+num(v/c.paid_hours,3):'—'));body.append(row);}
    const tot=make('tr','total');tot.append(make('td','','合计'),make('td','',money3(c.annualised)),make('td','','100%'),make('td','',c.unit_cost!=null?'$'+num(c.unit_cost,2):'—'));body.append(tot);table.append(body);tb.append(table);
    const rv=byId('return-revenue');rv.textContent=money3(c.revenue);byId('return-surplus').textContent=c.surplus_per_hour!=null?(c.surplus_per_hour>=0?'+':'−')+'$'+num(Math.abs(c.surplus_per_hour),2)+'/h':'—';byId('return-coverage').textContent=pct(c.coverage,0);
    byId('return-note').textContent=a.business_model==='gpu_rental'?`市场租金 $${num(a.price_gpu_hour,2)}/h 与同口径全成本 $${num(c.unit_cost,2)}/h 相减：全成本已含 ${pct(a.wacc,0)} 资本回收，「每小时盈余」是超过该资本成本的部分，不是会计利润。`:a.business_model==='colo'?'托管口径的收入按 kW·月计；全成本不含 IT。':'自用口径不做收益比较。';
  }

  /* view 4: inverse solve and the scenario grid (new) */
  function renderInverse(r){
    const a=values,inv=r.inverse,c=r.ledgers.compute;
    byId('inv-line').textContent=`目标 ROIC ${pct(a.target_roic,0)}（${a.roic_basis==='avg_annual_capex'?'平均年资本开支 = 总额 ÷ '+a.construction_years+' 年':'总资本开支'}口径，分母 ${money(inv.denominator)}）→ 需要 NOPAT ${money(inv.required_nopat)} → EBIT ${money(inv.required_ebit)}（税率 ${pct(a.tax,0)}）→ 加折旧 ${money(c.dep_it+c.dep_shell)} 与运营 ${money(c.opex)} = 需要收入 ${money(inv.required_revenue)}。`;
    tile('inv-revenue','每 GW 满负荷需要的收入',inv.required_revenue_per_gw!=null?'$'+num(inv.required_revenue_per_gw/1e9,2)+'B':'—',`EBIT 利润率 ${pct(inv.ebit_margin)} · NOPAT 利润率 ${pct(inv.nopat_margin)}`);
    tile('inv-price','需要的单价（利用率不变）',inv.required_price!=null?'$'+num(inv.required_price,2)+'/h':'—',`当前 $${num(a.price_gpu_hour,2)}/h`);
    tile('inv-util','需要的利用率（单价不变）',pct(inv.required_utilization),`当前稳态 ${pct(a.gpu_utilization,0)}`);
    tile('inv-capex','造价上限（收入不变）',inv.capex_ceiling_per_gw!=null?'$'+num(inv.capex_ceiling_per_gw/1e9,1)+'B/GW':'—',`当前 $${num(c.capex_per_gw/1e9,1)}B/GW · 当前 ROIC ${pct(c.roic)}`);
    byId('inv-gap').textContent=inv.gap>0?`当前收入比目标少 ${money(inv.gap)}（${pct(inv.gap/inv.required_revenue,0)}）。`:`当前收入超过目标 ${money(-inv.gap)}；当前 ROIC ${pct(c.roic)} 高于阈值 ${pct(a.target_roic,0)}。`;
    const g=r.grid,sel=byId('grid-util');const cur=sel.value;sel.replaceChildren();g.utilization.forEach((u,i)=>{const o=make('option','',pct(u,0));o.value=i;sel.append(o);});
    let ui=cur!==''&&Number(cur)<g.utilization.length?Number(cur):g.utilization.findIndex(u=>Math.abs(u-a.gpu_utilization)<0.026);if(ui<0)ui=Math.round(g.utilization.length/2);sel.value=ui;
    const host=byId('grid-table');host.replaceChildren();const table=make('table','bi grid'),thead=make('thead'),tr=make('tr');tr.append(make('th','','造价 $B/GW ＼ 单价'));g.prices.forEach((p,j)=>tr.append(make('th','','$'+num(p,2)+(g.price_factors[j]===1?'（当前）':''))));thead.append(tr);table.append(thead);const body=make('tbody');
    g.capex_per_gw.forEach((cpg,i)=>{const row=make('tr');row.append(make('th','','$'+num(cpg,1)+'B'));g.roic[ui][i].forEach((v,j)=>{const td=make('td','',pct(v,0));const hits=g.anchors.filter(an=>Math.abs(an.capex_per_gw-cpg)<0.01&&(an.price_factor==null||an.price_factor===g.price_factors[j])&&(an.utilization==null||Math.abs(an.utilization-g.utilization[ui])<0.026));
      td.className=v==null?'':v>=a.target_roic?'ok':v>=0?'mid':'bad';if(v!=null&&Math.abs(v-a.target_roic)<0.02)td.classList.add('edge');for(const an of hits){if(an.price_factor!=null||Math.abs(v-an.roic)<0.05){td.classList.add('anchor');td.title=an.label;td.append(make('small','',an.label));}}row.append(td);});body.append(row);});
    table.append(body);host.append(table);
    byId('grid-note').textContent=`每格是稳态 ROIC（${a.roic_basis==='avg_annual_capex'?'平均年资本开支':'总资本开支'}口径）；造价按比例缩放 IT、设施与土地；绿 ≥ 目标 ${pct(a.target_roic,0)}，黄 0–目标，红 < 0；标记为两家机构的锚点。`;
  }

  function renderCalibration(){
    const host=byId('calibration-table');host.replaceChildren();const table=make('table','bi'),thead=make('thead'),tr=make('tr');for(const h of ['校准锚','登记值','模型值','判定','来源'])tr.append(make('th','',h));thead.append(tr);table.append(thead);const body=make('tbody');
    const fmt=(k,v)=>k==='annualised'?money3(v):k==='unit_cost'?'$'+num(v,2)+'/h':/margin|roic/.test(k)?pct(v):'$'+num(v/1e9,2)+'B';
    for(const [cid,cal] of Object.entries(spec.calibration)){const a=withPreset(spec,cal.preset),c=compute(a,spec),inv=inverse(a,spec);const got={revenue_per_gw:c.revenue_per_gw,nopat_per_gw:c.nopat_per_mw*1000*1e6,roic:c.roic,required_revenue_per_gw:inv.required_revenue_per_gw,ebit_margin:inv.ebit_margin,nopat_margin:inv.nopat_margin,annualised:c.annualised,unit_cost:c.unit_cost};
      for(const k of Object.keys(cal)){if(k==='preset'||k==='source')continue;const want=cal[k],have=got[k],ok=have!=null&&Math.abs(have-want)<=Math.abs(want)*0.01+1e-9;const row=make('tr');row.append(make('td','',spec.presets[cal.preset].label+' · '+({revenue_per_gw:'每 GW 收入',nopat_per_gw:'每 GW NOPAT',roic:'ROIC',required_revenue_per_gw:'每 GW 满负荷需收入',ebit_margin:'EBIT 利润率',nopat_margin:'NOPAT 利润率',annualised:'年化全成本',unit_cost:'每有效设备小时'}[k]||k)),make('td','num',fmt(k,want)),make('td','num',fmt(k,have)));const td=make('td');td.append(make('span','flag '+(ok?'ok':'no'),ok?'复现':'偏离'));row.append(td,make('td','',cal.source));body.append(row);}}
    table.append(body);host.append(table);
  }
  function renderGaps(){
    const host=byId('gap-list');host.replaceChildren();const counts={input:0,sourced:0,assumed:0,needed:0},rows=[],g=gaps();
    for(const group of spec.groups)for(const id of group.inputs){const ev=spec.evidence[id]||{status:'needed'};counts[ev.status]=(counts[ev.status]||0)+1;if(ev.status==='assumed'||ev.status==='needed'||g.has(id))rows.push([group.label.replace(/^\d+ · /,''),spec.inputs[id].label,ev,g.has(id)]);}
    byId('gap-summary').textContent=`${Object.keys(spec.inputs).length} 个输入：用户给定 ${counts.input}、已有来源 ${counts.sourced}、作者假设 ${counts.assumed}、待获取 ${counts.needed}；当前地区标缺 ${g.size} 项。下面是要去找数据替换的项。`;
    const table=make('table','bi gaps'),thead=make('thead'),tr=make('tr');for(const h of ['变量类','输入','现状','抓取类型','要找什么'])tr.append(make('th','',h));thead.append(tr);table.append(thead);const body=make('tbody');const KIND={product:'产品',news:'新闻',data:'数据',report:'报告'};
    for(const [gl,l,ev,gap] of rows){const row=make('tr');const st=make('td');st.append(make('span','badge-text '+(gap?'needed':ev.status),gap?'该地区缺':STATUS[ev.status][0]));row.append(make('td','',gl),make('td','',l),st,make('td','',KIND[ev.fetch_kind]||'—'),make('td','',ev.fetch_what||ev.note||''));body.append(row);}
    table.append(body);host.append(table);
  }
  function renderBenchmarks(){
    const list=byId('benchmark-list');list.replaceChildren();const latest={};for(const rec of prices.records||[]){if(!latest[rec.series_id]||rec.as_of>latest[rec.series_id].as_of)latest[rec.series_id]=rec;}
    const GL={regulatory:'监管披露',company:'公司披露',research:'研究实测',media:'媒体转述',estimate:'估算'};let group='';const shown=[];
    for(const b of spec.benchmark_series||[]){const rec=latest[b.series_id];if(!rec)continue;shown.push(rec);if(b.group!==group){group=b.group;list.append(make('h3','benchmark-group',group));}
      const row=make('div','benchmark-row'),head=make('div');head.append(make('b','',b.label),make('small','',[rec.as_of,GL[rec.grade]||rec.grade,rec.region||''].filter(Boolean).join(' · ')));row.append(head,make('strong','',(Math.abs(rec.value)>=1000?Math.round(rec.value).toLocaleString():Number(rec.value).toLocaleString(undefined,{maximumFractionDigits:2}))+' '+rec.unit));row.title=(rec.note||'')+(rec.assumptions?'；'+rec.assumptions:'');list.append(row);}
    byId('benchmark-updated').textContent=shown.length?'价格库更新至 '+shown.map(x=>x.as_of).sort().pop():'价格库暂无对应序列';
  }
  function showView(name){view=name;document.querySelectorAll('#views button').forEach(b=>{const on=b.dataset.view===name;b.classList.toggle('on',on);b.setAttribute('aria-selected',on);});document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on',v.id==='view-'+name));history.replaceState(null,'',location.pathname+location.search+'#'+name);}
  function render(){
    const r=run(values,spec);markPreset();renderRegion();projectLine(r);renderLifecycle(r);renderLedgers(r);renderUnit(r);renderInverse(r);renderGaps();
    byId('copy-results').onclick=()=>{const c=r.ledgers.compute,l=r.lifecycle;const txt=JSON.stringify({model_id:spec.model_id,as_of:spec.as_of,preset:activePreset||null,assumptions:values,levelised:l.levelised,per_kw_month:l.per_kw_month,per_gpu_hour:l.per_gpu_hour,roic:c.roic,revenue:c.revenue,nopat:c.nopat,annualised:c.annualised,unit_cost:c.unit_cost,inverse:r.inverse},null,2);const btn=byId('copy-results');const done=()=>{btn.textContent='已复制';setTimeout(()=>btn.textContent='复制假设与结果',1500);};(navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(txt).then(done):Promise.reject()).catch(()=>{const ta=document.createElement('textarea');ta.value=txt;document.body.append(ta);ta.select();try{document.execCommand('copy');done();}catch(e){}ta.remove();});};
  }
  const getJson=url=>fetch(url,{cache:'no-store'}).then(res=>{if(!res.ok)throw Error(url+' HTTP '+res.status);return res.json()});
  const boot=([data,p])=>{spec=data;prices=p;byId('model-date').textContent='口径 '+spec.as_of;byId('model-note').textContent=spec.model_note;renderPresets();renderCalibration();renderBenchmarks();applyPreset('baseline');
    document.querySelectorAll('#views button').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));byId('grid-util').addEventListener('change',()=>renderInverse(run(values,spec)));
    byId('reset-model').addEventListener('click',()=>applyPreset('baseline'));
    const VIEWS={lifecycle:'lifecycle',ledgers:'ledgers',unit:'unit',inverse:'inverse',economics:'ledgers',tco:'lifecycle',cost:'unit'};
    const fromPath=/\/(economics|tco|cost)\.html$/.exec(location.pathname);showView(VIEWS[location.hash.slice(1)]||(fromPath?VIEWS[fromPath[1]]:'lifecycle'));app.removeAttribute('aria-busy');};
  const fail=error=>{const el=byId('model-error');el.hidden=false;el.textContent='模型加载失败：'+error.message;app.setAttribute('aria-busy','false');};
  Promise.all([getJson('/data/datacenter_model.json'),getJson('/data/prices.json').catch(()=>({records:[]}))]).then(boot).catch(fail);
})();
