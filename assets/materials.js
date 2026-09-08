(() => {
  const $ = id => document.getElementById(id);
  let files = [];
  const show = () => { $('selected').textContent = files.map(f => `${f.name} (${(f.size/1048576).toFixed(1)} MiB)`).join('；'); };
  $('files').onchange = () => { files = [...$('files').files]; show(); };
  $('drop').ondragover = e => e.preventDefault();
  $('drop').ondrop = e => { e.preventDefault(); files.push(...e.dataTransfer.files); show(); };
  $('text').addEventListener('paste', e => { const images = [...e.clipboardData.files]; if(images.length){e.preventDefault();files.push(...images);show();} });
  async function refresh(){
    try {
      const response = await fetch('/api/materials'); const data = await response.json();
      if(!response.ok) throw new Error(data.error || '读取失败，请确认已登录');
      $('records').replaceChildren();
      for(const item of data.items){
        const row = document.createElement('div');row.className='row';
        const title = document.createElement('strong');title.textContent=item.name;
        const detail = document.createElement('div');detail.className='muted';
        detail.textContent=`${item.status === 'archived' ? 'Spark 已归档' : '网站已接收 · 等待 Spark'} · ${new Date(item.created*1000).toLocaleString()} · ${item.topic || '未指定话题'} · ${item.id.slice(0,8)}`;
        row.append(title,detail);$('records').append(row);
      }
      if(!data.items.length) $('records').textContent='还没有提交资料。';
    }catch(e){$('records').textContent=e.message;}
  }
  $('refresh').onclick=refresh;
  $('form').onsubmit=async e=>{
    e.preventDefault();
    const text=$('text').value;
    const pending=[...files];
    if(text.trim()) pending.unshift(new File([text], '研究笔记.txt', {type:'text/plain'}));
    if(!pending.length){$('status').textContent='请粘贴内容或添加文件。';return;}
    if(pending.some(f=>!f.size || f.size>64*1048576)){$('status').textContent='请检查：文件不能为空，每份最多 64 MiB。';return;}
    $('submit').disabled=true; let completed=0;
    try{
      for(const file of pending){
        $('status').textContent=`正在提交 ${completed+1}/${pending.length}：${file.name}`;
        const response=await fetch('/api/materials',{method:'POST',headers:{'X-Requested-With':'material-intake','Content-Type':'application/octet-stream','X-Material-Metadata':encodeURIComponent(JSON.stringify({name:file.name,topic:$('topic').value,source:$('source').value,note:$('note').value}))},body:file});
        const data=await response.json();if(!response.ok)throw new Error(data.error||'提交失败');
        completed++;
        if(file===pending[0] && text.trim()) $('text').value='';
        files=files.filter(f=>f!==file);show();
      }
      $('files').value='';$('status').textContent=`已接收 ${completed} 份资料，等待 Spark 归档。`;
    }catch(err){$('status').textContent=`已接收 ${completed} 份。${err.message}；未成功的内容已保留，可重试。`;}
    finally{$('submit').disabled=false;refresh();}
  };
  refresh();
})();
