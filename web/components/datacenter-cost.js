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
      facilityAccount:components.facility+components.land+components.energy+components.demand+components.water+a.facility_opex};
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
  function applyPreset(id){values={...spec.assumptions,...(spec.presets[id]?.changes||{})};renderInputs();setActivePreset(id);render();}
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
    renderBars(out);renderMatrix();
  }
  fetch('/data/datacenter_cost_model.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(data=>{
    spec=data;values={...spec.assumptions};baseline=calculate(values);byId('model-date').textContent='口径 '+spec.as_of;byId('model-note').textContent=spec.model_note;
    renderPresets();renderInputs();setActivePreset('baseline');render();byId('reset-model').addEventListener('click',()=>applyPreset('baseline'));app.removeAttribute('aria-busy');
  }).catch(error=>{const el=byId('cost-error');el.hidden=false;el.textContent='成本模型加载失败：'+error.message;app.setAttribute('aria-busy','false')});
})();
