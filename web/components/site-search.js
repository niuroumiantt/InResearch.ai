(async()=>{
  const form=document.getElementById('site-search'),input=document.getElementById('search-query'),scope=document.getElementById('search-scope'),status=document.getElementById('search-status'),results=document.getElementById('search-results');
  const params=new URLSearchParams(location.search);input.value=params.get('q')||'';
  const labels={delivery:'交付内容',backstage:'后台工作',all:'全部授权内容'};
  const make=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
  let controller;
  async function load(){
    controller?.abort();controller=new AbortController();status.textContent='正在搜索';results.replaceChildren();
    const query=new URLSearchParams({q:input.value.trim(),scope:scope.value});history.replaceState(null,'','/search.html?'+query);window.dispatchEvent(new Event('inresearch:page-navigation'));
    try{const r=await fetch('/api/site-search?'+query,{cache:'no-store',signal:controller.signal});const d=await r.json();if(!r.ok)throw Error(d.error||'搜索暂不可用');
      status.textContent=!d.q?'输入关键词开始搜索':d.truncated?`显示前 ${d.rows.length} / ${d.total} 条结果`:`${d.total} 条结果`;
      for(const row of d.rows){const article=make('article','');article.className='search-item';const h=make('h2',''),a=make('a',row.title);a.href=row.href;h.append(a);article.append(h);const kind=make('div',`${labels[row.area]} · ${row.kind}`);kind.className='search-kind';article.append(kind,make('p',row.description));results.append(article);}
      document.getElementById('search-coverage').textContent=d.coverage||'';
    }catch(e){if(e.name!=='AbortError')status.textContent=e.message;}
  }
  try{const r=await fetch('/api/navigation?page='+encodeURIComponent(location.pathname+location.search),{cache:'no-store'});const d=await r.json();if(!r.ok||!d.search.enabled)throw Error('当前身份未开放全站搜索');
    scope.replaceChildren(...d.search.scopes.map(value=>{const o=make('option',labels[value]);o.value=value;return o;}));scope.value=d.search.scopes.includes(params.get('scope'))?params.get('scope'):d.search.default_scope;
    form.addEventListener('submit',e=>{e.preventDefault();load();});if(input.value.trim())await load();else status.textContent='输入关键词开始搜索';
  }catch(e){status.textContent=e.message;form.hidden=true;}
})();
