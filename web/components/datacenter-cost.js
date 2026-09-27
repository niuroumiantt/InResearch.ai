(() => {
  'use strict';
  const COLORS=['#0877c9','#6956a8','#a86921','#aa3d72','#42657b','#d17824','#71806a','#b34b3f'];
  const money=n=>n>=1e9?'$'+(n/1e9).toFixed(3)+'B':n>=1e6?'$'+(n/1e6).toFixed(1)+'M':'$'+Math.round(n).toLocaleString();
  const number=(n,d=1)=>Number(n).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
  const crf=(r,n)=>r===0?1/n:r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);
  function calculate(a){
    const itEnergy=a.it_mw*1000*a.power_load*8760;
    const facilityEnergy=itEnergy*a.pue;
    const productiveHours=a.devices*8760*a.productive;
    const components={
      servers:a.servers*crf(a.rate,a.it_life),
      network:a.network*crf(a.rate,a.it_life),
      facility:(a.facility+a.utility)*crf(a.rate,a.facility_life),
      land:a.land*a.rate,
      energy:facilityEnergy*a.energy_price,
      demand:a.billed_kw*a.demand_rate*12,
      opex:a.fixed_opex,
      water:itEnergy*a.site_water_l/1000*a.water_price
    };
    const total=Object.values(components).reduce((x,y)=>x+y,0);
    const capital=components.servers+components.network+components.facility+components.land;
    return {itEnergy,facilityEnergy,productiveHours,components,total,capital,
      perHour:total/productiveHours,capex:a.facility+a.utility+a.land+a.servers+a.network,
      waterM3:itEnergy*a.site_water_l/1000,
      itAccount:components.servers+components.network,
      facilityAccount:components.facility+components.land+components.energy+components.demand+components.water+a.facility_opex,
      rent:a.rent_price||0,revenue:(a.rent_price||0)*productiveHours,
      surplusPerHour:(a.rent_price||0)-total/productiveHours,surplus:(a.rent_price||0)*productiveHours-total,
      coverage:(a.rent_price||0)*productiveHours/total};
  }
  window.InresearchCost={calculate,crf};
  const app=document.getElementById('cost-app'); if(!app)return;
  let spec,values,baseline;
  const byId=id=>document.getElementById(id);
  const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  function renderInputs(){
    const form=byId('cost-inputs'); form.replaceChildren();
    for(const group of spec.groups){
      const box=make('section','input-group');box.append(make('h3','',group.label));
      for(const id of group.inputs){
        const cfg=spec.inputs[id],row=make('div','input-row'),label=make('label','',cfg.label),note=make('small','',cfg.note||'');
        label.htmlFor='input-'+id;label.append(note);
        const holder=make('div','input-box'),input=make('input');input.type='number';input.id='input-'+id;input.name=id;
        input.min=cfg.min;input.max=cfg.max;input.step=cfg.step;input.value=cfg.display==='percent'?values[id]*100:cfg.display==='million'?values[id]/1e6:values[id];
        input.addEventListener('input',()=>{const raw=Number(input.value);if(!Number.isFinite(raw))return;values[id]=cfg.display==='percent'?raw/100:cfg.display==='million'?raw*1e6:raw;setActivePreset('');render();});
        holder.append(input,make('span','',cfg.unit));row.append(label,holder);box.append(row);
      }
      form.append(box);
    }
  }
  function setActivePreset(id){document.querySelectorAll('#presets button').forEach(b=>b.classList.toggle('active',b.dataset.id===id));}
  function applyPreset(id){values={...spec.assumptions,...(spec.presets[id]?.changes||{})};renderInputs();setActivePreset(id);byId('preset-note').textContent=spec.presets[id]?.note||'';render();}
  const GRADE_LABEL={regulatory:'监管披露',company:'公司披露',research:'研究实测',media:'媒体转述',estimate:'估算'};
  const REGION_LABEL={global:'全球','north-america':'北美',europe:'欧洲','asia-pacific':'亚太',CN:'中国'};
  function latestBySeries(records){const out={};for(const r of records||[]){if(!out[r.series_id]||r.as_of>out[r.series_id].as_of)out[r.series_id]=r;}return out;}
  function renderBenchmarks(prices){
    const host=byId('benchmark-list');if(!host)return;host.replaceChildren();
    const latest=latestBySeries(prices.records),shown=[];let group='';
    for(const b of spec.benchmark_series||[]){
      const r=latest[b.series_id];if(!r)continue;shown.push(r);
      if(b.group&&b.group!==group){group=b.group;host.append(make('h3','benchmark-group',group));}
      const row=make('div','benchmark-row'),head=make('div'),name=make('b','',b.label),val=make('strong','',formatValue(r.value)+' '+r.unit),
        meta=make('small','',[r.as_of,GRADE_LABEL[r.grade]||r.grade,REGION_LABEL[r.region]||r.region||''].filter(Boolean).join(' · '));
      head.append(name,meta);row.append(head,val);row.title=(r.note||'')+(r.assumptions?'；'+r.assumptions:'');host.append(row);
    }
    const stamp=byId('benchmark-updated');if(stamp)stamp.textContent=shown.length?'数据更新至 '+shown.map(r=>r.as_of).sort().pop()+'，共 '+shown.length+' 条序列的最新时点':'价格库暂无对应序列';
  }
  const formatValue=v=>Math.abs(v)>=1000?Math.round(v).toLocaleString():Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
  function renderPresets(){const host=byId('presets');host.replaceChildren();for(const [id,p] of Object.entries(spec.presets)){const b=make('button','',p.label);b.type='button';b.dataset.id=id;b.addEventListener('click',()=>applyPreset(id));host.append(b);}}
  function renderBars(out){
    const labels={servers:'服务器资本年化',network:'集群网络资本年化',facility:'设施与接入资本年化',land:'土地机会成本',energy:'电量费',demand:'计费需量费用',opex:'其他运营支出',water:'现场水费'};
    const entries=Object.entries(out.components),max=Math.max(...entries.map(x=>x[1]));
    const stack=byId('cost-stack'),bars=byId('cost-bars');stack.replaceChildren();bars.replaceChildren();
    entries.forEach(([key,val],i)=>{
      const piece=make('span');piece.style.width=(val/out.total*100)+'%';piece.style.background=COLORS[i];piece.title=labels[key]+' '+money(val);stack.append(piece);
      const row=make('div','bar-row'),lab=make('label','',labels[key]),track=make('div','bar-track'),fill=make('div','bar-fill'),output=make('output','',money(val));
      fill.style.width=Math.max(.3,val/max*100)+'%';fill.style.background=COLORS[i];track.append(fill);row.append(lab,track,output);bars.append(row);
    });
  }
  function renderMatrix(){
    const util=[.35,.45,.55,.65,.75,.85],energy=[.04,.08,.12],points=[];
    util.forEach(u=>energy.forEach(e=>points.push(calculate({...values,productive:u,energy_price:e}).perHour)));
    const lo=Math.min(...points),hi=Math.max(...points),table=make('table','matrix'),head=make('tr');head.append(make('th','','有效时间'));
    energy.forEach(e=>head.append(make('th','','$'+e.toFixed(2)+'/kWh')));const thead=make('thead');thead.append(head);table.append(thead);const body=make('tbody');
    util.forEach(u=>{const row=make('tr');row.append(make('th','',Math.round(u*100)+'%'));energy.forEach(e=>{const v=calculate({...values,productive:u,energy_price:e}).perHour,t=(v-lo)/Math.max(.001,hi-lo),cell=make('td','','$'+v.toFixed(2));cell.style.background=`color-mix(in srgb, ${t>.55?'var(--yellow)':'var(--accent)'} ${18+Math.round(t*35)}%, var(--card))`;row.append(cell)});body.append(row)});table.append(body);byId('sensitivity-matrix').replaceChildren(table);
  }
  function render(){
    const out=calculate(values),change=out.perHour/baseline.perHour-1;
    byId('cost-total').textContent=money(out.total);byId('cost-per-hour').textContent='$'+out.perHour.toFixed(2);
    byId('cost-delta').textContent=Math.abs(change)<.0005?'研究基准':(change>0?'+':'')+(change*100).toFixed(1)+'% vs 基准';
    byId('metric-capex').textContent=money(out.capex);byId('metric-energy').textContent=number(out.facilityEnergy/1e6,1)+' GWh';
    byId('metric-power').textContent='平均设施功率 '+number(out.facilityEnergy/8760/1000,1)+' MW';
    byId('metric-hours').textContent=number(out.productiveHours/1e6,1)+'M h';byId('metric-water').textContent=number(out.waterM3/1000,1)+'k m³';
    byId('account-it').textContent=money(out.itAccount);byId('account-it-share').textContent=number(out.itAccount/out.total*100,1)+'% 全项目年成本';
    byId('account-facility').textContent=money(out.facilityAccount);
    byId('formula-it-energy').textContent=number(out.itEnergy/1e6,1)+' GWh';byId('formula-facility-energy').textContent=number(out.facilityEnergy/1e6,1)+' GWh';
    byId('formula-capital').textContent=money(out.capital);byId('formula-total').textContent=money(out.total);byId('formula-unit').textContent='$'+out.perHour.toFixed(2)+'/h';
    const hasRent=out.rent>0;
    byId('return-revenue').textContent=hasRent?money(out.revenue):'—';
    byId('return-surplus-hour').textContent=hasRent?(out.surplusPerHour>=0?'+':'−')+'$'+Math.abs(out.surplusPerHour).toFixed(2)+'/h':'—';
    byId('return-surplus').textContent=hasRent?(out.surplus>=0?'+':'−')+money(Math.abs(out.surplus)):'—';
    byId('return-coverage').textContent=hasRent?number(out.coverage*100,0)+'%':'—';
    byId('return-state').textContent=hasRent?(out.surplusPerHour>=0?'租金覆盖全成本（含 '+number(values.rate*100,1)+'% 资本回收）':'租金低于全成本，资本回收不足'):'在左侧“收益参照”填入租金，或选择带租金的情景预设';
    renderBars(out);renderMatrix();
  }
  const getJson=url=>fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(url+' HTTP '+r.status);return r.json()});
  Promise.all([getJson('/data/datacenter_cost_model.json'),getJson('/data/prices.json').catch(()=>({records:[]}))]).then(([data,prices])=>{
    spec=data;values={...spec.assumptions};baseline=calculate(values);byId('model-date').textContent='口径 '+spec.as_of;byId('model-note').textContent=spec.model_note;
    renderPresets();renderBenchmarks(prices);renderInputs();applyPreset('baseline');byId('reset-model').addEventListener('click',()=>applyPreset('baseline'));app.removeAttribute('aria-busy');
  }).catch(error=>{const el=byId('cost-error');el.hidden=false;el.textContent='成本模型加载失败：'+error.message;app.setAttribute('aria-busy','false')});
})();
