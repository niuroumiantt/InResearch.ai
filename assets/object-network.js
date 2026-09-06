/* One-hop, object-centred research graph. Exploration links are not BOM facts. */
export function objectNetwork(graph, centerId, mode = 'all') {
  const objects = new Map((graph.objects || []).filter(o=>!o.navigation_hidden).map(o => [o.id, o]));
  const center = objects.get(centerId);
  if (!center) return {center:null,nodes:[],edges:[]};
  if (mode === 'topics') {
    const nodes = (graph.research_topics || []).map(t => ({id:centerId+'@'+t.id,name:t.name,kind:'research_topic',topic_id:t.id}));
    return {center,nodes,edges:nodes.map(n => ({id:'topic:'+n.id,source:centerId,target:n.id,label:'研究角度',category:'topic',status:'outline',evidence_ids:[]}))};
  }
  const edges=[];
  if (mode !== 'registered') for (const o of objects.values()) for (const [i, section] of (o.research_sections || []).entries()) {
    for (const target of section.object_ids || []) if (o.id === centerId || target === centerId) {
      if (target !== o.id && objects.has(target)) edges.push({id:`explore:${o.id}:${i}:${target}`,source:o.id,target,label:section.title,category:'explore',status:'research_navigation',evidence_ids:[]});
    }
  }
  if (mode !== 'explore') for (const r of graph.relations || []) {
    if (r.source !== r.target && (r.source === centerId || r.target === centerId) && objects.has(r.source) && objects.has(r.target))
      edges.push({...r,label:r.type,category:'registered',status:r.status || r.representation || 'unknown',evidence_ids:r.evidence_ids || (r.evidence_id ? [r.evidence_id] : [])});
  }
  const ids = [...new Set(edges.flatMap(e => [e.source,e.target]))].filter(id => id !== centerId);
  return {center,nodes:ids.map(id => objects.get(id)),edges};
}

const NS='http://www.w3.org/2000/svg';
const svgEl=(tag,attrs={},text)=>{const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;};
function download(blob,name) {const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const button=(name,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=name;b.addEventListener('click',fn);return b;};
const short=(s,n)=>Array.from(s).slice(0,n).join('')+(Array.from(s).length>n?'…':'');

export function mountObjectNetwork(host,{graph,centerId,onNavigate,onTopic,onBack,canBack,labelRelation=s=>s}) {
  let mode='all',page=0,zoom=1;
  const tools=document.createElement('div');tools.className='rg-node-actions';
  const select=document.createElement('select');select.setAttribute('aria-label','图谱关系筛选');
  for(const [value,text] of [['all','对象关系与研究外延'],['explore','研究外延'],['registered','已登记关系'],['topics','九个研究角度']]){const o=document.createElement('option');o.value=value;o.textContent=text;select.append(o);}
  const back=button('后退一步',onBack);back.disabled=!canBack;
  tools.append(back,select,button('缩小',()=>resize(.8)),button('放大',()=>resize(1.25)),button('适应画布',()=>{zoom=1;applyZoom();}));
  const status=document.createElement('p');status.className='rg-caption';status.setAttribute('aria-live','polite');
  const canvas=document.createElement('div');canvas.className='rg-network-canvas';canvas.tabIndex=0;canvas.setAttribute('aria-label','可滚动的研究图谱画布');
  const pager=document.createElement('div');pager.className='rg-node-actions';
  const facts=document.createElement('details');facts.className='rg-network-edges';const summary=document.createElement('summary');summary.textContent='本图关系与出处';facts.append(summary);const edgeList=document.createElement('ul');facts.append(edgeList);
  const legend=document.createElement('p');legend.className='rg-caption';legend.textContent='箭头表示记录方向。虚线为研究外延；实线为已登记关系，登记不等于已核实。点击对象切换中心；点击研究角度查看对应问题。';
  host.append(tools,status,canvas,pager,legend,facts);
  let svg,visibleEdges=[],visibleNodes=[],network;
  const baseName=()=>new Date().toISOString().slice(0,10)+'_'+centerId.replace(/[^\p{L}\p{N}._-]/gu,'-')+'_研究图谱';
  function exportSVG(){
    const copy=svg.cloneNode(true);copy.setAttribute('width','1000');copy.setAttribute('height','700');copy.removeAttribute('style');
    // Resolve active Attio/folk colours for a self-contained shareable image.
    const originals=[svg,...svg.querySelectorAll('*')],clones=[copy,...copy.querySelectorAll('*')];
    originals.forEach((el,i)=>{const cs=getComputedStyle(el);for(const key of ['fill','stroke','stroke-width','stroke-dasharray','font-family','font-size','font-weight','rx'])clones[i].style.setProperty(key,cs.getPropertyValue(key));});
    const meta=svgEl('metadata',{},JSON.stringify({graph_version:graph.version,center_id:centerId,mode,page:page+1,partial:visibleNodes.length<network.nodes.length,generated_at:new Date().toISOString(),nodes:visibleNodes,edges:visibleEdges}));copy.prepend(meta);
    download(new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml'}),baseName()+'.svg');
  }
  tools.append(button('导出本页 SVG',exportSVG),button('导出关系 JSON',()=>download(new Blob([JSON.stringify({graph_version:graph.version,center_id:centerId,mode,generated_at:new Date().toISOString(),...network},null,2)],{type:'application/json'}),baseName()+'.json')));
  function applyZoom(){if(svg){svg.style.width=(zoom*100)+'%';svg.style.minWidth=(zoom*760)+'px';}}
  function resize(f){zoom=Math.max(.5,Math.min(3,zoom*f));applyZoom();}
  function draw(){
    network=objectNetwork(graph,centerId,mode);const {center,nodes,edges}=network;if(!center)return;
    const pages=Math.max(1,Math.ceil(nodes.length/12));page=Math.min(page,pages-1);
    visibleNodes=nodes.slice(page*12,page*12+12);const visible=new Set([centerId,...visibleNodes.map(n=>n.id)]);visibleEdges=edges.filter(e=>visible.has(e.source)&&visible.has(e.target));
    status.textContent=`中心：${center.name} · ${nodes.length} 个相邻对象/主题 · 第 ${page+1}/${pages} 页（每页最多 12 个）`;
    svg=svgEl('svg',{viewBox:'0 0 1000 700',role:'group','aria-label':center.name+' 研究关系图','data-center-id':centerId});
    svg.append(svgEl('title',{},center.name+'：点击相邻对象重新居中'));
    const defs=svgEl('defs');const marker=svgEl('marker',{id:'network-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',class:'rg-network-arrow'}));defs.append(marker);svg.append(defs,svgEl('rect',{width:1000,height:700,class:'rg-network-background'}));
    svg.append(svgEl('text',{x:24,y:28,class:'rg-network-caption'},short(center.name,35)+' · 研究图谱 · '+graph.version));
    svg.append(svgEl('text',{x:24,y:675,class:'rg-network-caption'},`第 ${page+1}/${pages} 页 · 虚线：研究外延；实线：登记关系（非核验结论）`));
    const positions=new Map([[centerId,{x:500,y:340}]]);
    visibleNodes.forEach((n,i)=>{const angle=-Math.PI/2+2*Math.PI*i/Math.max(visibleNodes.length,1);positions.set(n.id,{x:500+355*Math.cos(angle),y:340+255*Math.sin(angle)});});
    // One visual link per neighbour; full directed edge records remain in the details/export.
    for(const n of visibleNodes){
      const pos=positions.get(n.id),es=visibleEdges.filter(e=>e.source===n.id||e.target===n.id),first=es[0];
      const dx=pos.x-500,dy=pos.y-340,len=Math.hypot(dx,dy);const ux=dx/len,uy=dy/len,ct=Math.min(105/Math.abs(ux),34/Math.abs(uy))+5,nt=Math.min(84/Math.abs(ux),34/Math.abs(uy))+5;const from={x:500+ux*ct,y:340+uy*ct},to={x:pos.x-ux*nt,y:pos.y-uy*nt};
      const outward=es.some(e=>e.source===centerId),inward=es.some(e=>e.target===centerId);
      const line=svgEl('line',{x1:from.x,y1:from.y,x2:to.x,y2:to.y,class:'rg-network-edge'+(es.every(e=>e.category!=='registered')?' rg-network-explore':''),...(outward?{'marker-end':'url(#network-arrow)'}:{}),...(inward?{'marker-start':'url(#network-arrow)'}:{})});
      line.append(svgEl('title',{},es.map(e=>(e.category==='registered'?labelRelation(e.label):e.label)+' · '+e.status).join('\n')));svg.append(line);
      const tx=500+dx*.54,ty=340+dy*.54;
      const label=short(first.category==='registered'?labelRelation(first.label):first.label,13)+(es.length>1?' +'+(es.length-1):'');
      svg.append(svgEl('rect',{x:tx-72,y:ty-12,width:144,height:21,rx:3,class:'rg-network-label-bg'}),svgEl('text',{x:tx,y:ty+3,'text-anchor':'middle',class:'rg-network-label'},label));
    }
    const addNode=(n,centerNode=false)=>{
      const pos=positions.get(n.id),group=svgEl('g',{transform:`translate(${pos.x},${pos.y})`,class:'rg-network-node'+(centerNode?' rg-network-center':''),tabindex:0,role:'button','aria-label':centerNode?'当前中心：'+n.name:n.topic_id?'研究角度：'+n.name:'以 '+n.name+' 为中心','data-node-id':n.id});
      group.append(svgEl('title',{},n.name+'\n'+n.id),svgEl('rect',{x:centerNode?-105:-84,y:-34,width:centerNode?210:168,height:68,style:'rx:var(--ui-radius,10px)'}));
      const chars=Array.from(n.name),cut=Math.ceil(Math.min(chars.length,24)/2),lines=chars.length>11?[chars.slice(0,cut).join(''),short(chars.slice(cut).join(''),12)]:[n.name];
      lines.forEach((line,i)=>group.append(svgEl('text',{x:0,y:(lines.length>1?-5:2)+i*19,'text-anchor':'middle',class:'rg-network-node-name'},line)));
      const activate=()=>{if(centerNode)return;if(n.topic_id)onTopic(n.topic_id);else onNavigate(n.id);};group.addEventListener('click',activate);group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate();}});svg.append(group);
    };
    visibleNodes.forEach(n=>addNode(n));addNode(center,true);canvas.replaceChildren(svg);applyZoom();
    pager.replaceChildren();if(pages>1){const prev=button('上一页',()=>{page--;draw();});prev.disabled=page===0;const next=button('下一页',()=>{page++;draw();});next.disabled=page===pages-1;pager.append(prev,next);}
    edgeList.replaceChildren();for(const e of visibleEdges){const li=document.createElement('li');const names=new Map([[centerId,center],...nodes.map(n=>[n.id,n])]);li.textContent=`${names.get(e.source)?.name||e.source} → ${names.get(e.target)?.name||e.target}：${e.category==='registered'?labelRelation(e.label):e.label}；${e.category==='registered'?'已登记 / '+e.status:'研究导览，非装配事实'}；证据 ID：${e.evidence_ids.length?e.evidence_ids.join('、'):'未登记'}；关系 ID：${e.id}`;edgeList.append(li);}
    if(!nodes.length){const empty=document.createElement('p');empty.className='rg-caption';empty.textContent='尚无相邻对象记录。可切换到“九个研究角度”；无连线不代表无关系。';pager.append(empty);}
  }
  select.addEventListener('change',()=>{mode=select.value;page=0;draw();});draw();
  return ()=>{};
}
