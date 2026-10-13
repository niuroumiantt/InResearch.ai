(() => {
  const params=new URLSearchParams(location.search),view=params.get('view')||'help';
  const section=Array.from(document.querySelectorAll('[data-guide]')).find(s=>s.dataset.guide===view);
  if(!section){const e=document.getElementById('guide-error');e.hidden=false;e.textContent='未找到该说明页面';return;}
  section.classList.add('is-current');document.title=section.querySelector('h1').textContent+' — inresearch.ai';
  const form=document.getElementById('feedback-form');
  if(view==='feedback'){
    const from=params.get('from');if(from&&from.startsWith('/')&&!from.startsWith('//'))form.elements.context.value=from;
    form.addEventListener('submit',async e=>{e.preventDefault();const status=document.getElementById('feedback-status'),button=form.querySelector('button');button.disabled=true;status.textContent='正在提交';
      try{const r=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});const d=await r.json();if(!r.ok)throw Error(d.error||'提交失败');status.textContent=d.message+' 记录号：'+d.id;form.reset();}catch(error){status.textContent=error.message;}finally{button.disabled=false;}
    });
  }
  if(view==='updates'){
    const box=document.getElementById('product-updates');
    fetch('/api/navigation?page='+encodeURIComponent(location.pathname+location.search),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>{const rows=d.footer?.updates||[];box.replaceChildren();if(!rows.length){box.textContent='尚无已登记的产品发布记录。';return;}for(const row of rows){const article=document.createElement('article'),h=document.createElement('h2'),p=document.createElement('p');h.textContent=row.title;p.textContent=[row.version,row.published_at,row.description].filter(Boolean).join(' · ');article.append(h,p);box.append(article);}}).catch(()=>{box.textContent='产品更新暂不可读取，请稍后重试。';});
  }
})();
