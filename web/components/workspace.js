(() => {
  const app=document.getElementById('workspace-app'),params=new URLSearchParams(location.search);
  const node=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=String(text);return e;};
  const link=(label,href)=>{const a=node('a',label);a.href=href;return a;};
  const error=document.getElementById('workspace-error');
  const query=document.getElementById('workspace-query');query.value=params.get('q')||'';
  let controller;
  async function load(){
    controller?.abort();controller=new AbortController();app.setAttribute('aria-busy','true');error.hidden=true;
    try{
      const r=await fetch('/api/workspace?'+params,{cache:'no-store',signal:controller.signal});const d=await r.json();
      if(!r.ok||d.ok===false)throw Error(d.error||'栏目暂时无法读取');
      document.title=d.title+' — inresearch.ai';document.getElementById('workspace-title').textContent=d.title;
      document.getElementById('workspace-summary').textContent=d.summary||'';
      const crumb=document.getElementById('workspace-crumb');crumb.replaceChildren(link('地图首页','/'),node('span',d.area==='backstage'?'后台':'交付'),node('span',d.title));
      const tabs=document.getElementById('workspace-tabs');tabs.replaceChildren(...d.tabs.map(t=>{const a=link(t.label,t.href);if(t.id===d.view)a.setAttribute('aria-current','page');return a;}));
      const content=document.getElementById('workspace-content');content.replaceChildren();
      for(const block of d.blocks){
        const s=node('section');s.className='workspace-block';s.append(node('h2',block.title));
        if(block.note)s.append(node('p',block.note));
        if(!block.rows.length){const p=node('p','暂无符合条件的已登记记录。');p.className='workspace-empty';s.append(p);}
        else{
          const wrap=node('div');wrap.className='workspace-table-wrap';const table=node('table');const head=node('thead'),tr=node('tr');
          block.columns.forEach(c=>{const th=node('th',c.label);th.scope='col';tr.append(th);});head.append(tr);table.append(head);const body=node('tbody');
          for(const row of block.rows){const line=node('tr');block.columns.forEach((c,i)=>{const td=node('td');const text=row[c.key]===null||row[c.key]===undefined||row[c.key]===''?'未登记':String(row[c.key]);if(i===0&&row.href)td.append(link(text,row.href));else td.textContent=text;line.append(td);});body.append(line);}
          table.append(body);wrap.append(table);s.append(wrap);
          if(block.total>block.rows.length)s.append(node('p',`本页显示 ${block.rows.length} / ${block.total} 条，请使用筛选缩小范围。`));
        }content.append(s);
      }
      document.getElementById('workspace-links').replaceChildren(...d.links.map(x=>link(x.label,x.href)));
    }catch(e){if(e.name!=='AbortError'){error.hidden=false;error.textContent=e.message;}}
    finally{app.setAttribute('aria-busy','false');}
  }
  document.getElementById('workspace-filter').addEventListener('submit',e=>{e.preventDefault();if(query.value.trim())params.set('q',query.value.trim());else params.delete('q');history.replaceState(null,'',location.pathname+'?'+params);load();});
  load();
})();
