/** Source-linked display of retained legacy panel textures; no new hardware model. */
export function mountPanelSources({handles, button, document:doc=document}) {
  const rows=[
    {id:'TA-30',key:'server',file:'server_nvme',title:'NVMe服务器来源面板',model:'Supermicro AS-1114S-WN10RT',binding:'六个普通托盘的正面外观参考'},
    {id:'TA-31',key:'hero',file:'server_gpu',title:'计算机箱来源面板',model:'Supermicro SYS-620BT-CHASSIS',binding:'抽出的计算托盘的正面；文件名不证明GPU配置'},
    {id:'TA-32',key:'storage',file:'server_storage',title:'存储服务器来源面板',model:'Supermicro SSG-610P-ACR12N4H',binding:'最后一个托盘的正面；不证明盘型、RAID或存储阵列'},
    {id:'TA-33',key:'tor',file:'switch_tor',title:'交换机来源面板',model:'Supermicro SSE-G3648B',binding:'第一台示例交换机的正面；TOR为示意角色'},
    {id:'TA-34',key:'ib',file:'switch_ib',title:'高速交换机来源面板',model:'Mellanox SN2100',binding:'第二台示例交换机的正面；文件名ib不认证InfiniBand'},
  ];
  if (!button || !rows.every(row=>handles[row.key])) return {dispose(){}};
  const style=doc.createElement('style');style.textContent=`
  .panel-source-dialog{position:fixed;inset:0;margin:auto;width:min(960px,calc(100vw - 24px));max-height:calc(100dvh - 32px);overflow:auto;padding:16px;border:1px solid var(--line);border-radius:var(--ui-radius);background:var(--ui-surface);color:var(--text);font:13px/1.65 var(--ui-font)}
  .panel-source-dialog::backdrop{background:#0007}.panel-source-dialog h2{font-size:17px}.panel-source-dialog nav{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.panel-source-dialog button,.panel-source-dialog a{padding:6px 10px;border:1px solid var(--line);border-radius:var(--ui-radius);background:transparent;color:var(--text);font:inherit;cursor:pointer}.panel-source-dialog nav button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}
  .panel-source-dialog canvas{display:block;box-sizing:content-box;width:calc(100% - 2px);height:auto;padding:0;background:#faf8f2;border:1px solid var(--line);margin:12px 0}.panel-source-dialog .panel-source-actions{display:flex;flex-wrap:wrap;gap:8px}.panel-source-dialog p{overflow-wrap:anywhere;margin:8px 0}
  `;doc.head.append(style);
  const dialog=doc.createElement('dialog');dialog.className='panel-source-dialog';dialog.setAttribute('aria-label','保留来源面板与显示比例');
  const heading=doc.createElement('h2');heading.textContent='保留来源面板 · 外观参考';
  const close=doc.createElement('button');close.type='button';close.textContent='关闭';close.style.float='right';close.onclick=()=>dialog.close();
  const nav=doc.createElement('nav');nav.setAttribute('aria-label','五张来源面板');
  const title=doc.createElement('p'),identity=doc.createElement('p'),status=doc.createElement('p'),canvas=doc.createElement('canvas'),note=doc.createElement('p');
  note.textContent='原始PNG不裁切、不重绘；此处显示与三维正面使用同一CanvasTexture内容，按示例表面比例留白。来源型号不表示三维机箱相符，端口、盘位与标识仅保留原图信息；现场配置、数量和安装规格未知。';
  const actions=doc.createElement('div');actions.className='panel-source-actions';
  const original=doc.createElement('a');original.textContent='下载原始PNG';
  const display=doc.createElement('a');display.textContent='下载等比展示SVG';
  const upstream=doc.createElement('a');upstream.href='https://github.com/netbox-community/devicetype-library';upstream.target='_blank';upstream.rel='noopener';upstream.textContent='NetBox来源库';
  const retry=doc.createElement('button');retry.type='button';retry.textContent='重新载入来源';actions.append(original,display,upstream,retry);
  dialog.append(close,heading,nav,title,identity,status,canvas,note,actions);doc.body.append(dialog);
  let active=rows[0],disposed=false,token=0,opener=null;
  const paint=()=>{
    if(disposed)return;const handle=handles[active.key],image=handle.texture.image,meta=handle.texture.userData.sourceDisplay;
    canvas.width=image.width;canvas.height=image.height;canvas.getContext('2d').drawImage(image,0,0);
    canvas.style.aspectRatio=String(meta?.surfaceAspect||image.width/image.height);
    title.textContent=active.id+' · '+active.title+' · '+active.model;
    identity.textContent='来源文件 '+active.file+'.png · '+active.binding;
    status.textContent=handle.status()==='ready'?'来源已载入 · 等比留白显示':handle.status()==='loading'?'正在载入 · 当前暂存画布不作为来源已就绪':'程序化占位前脸 · 来源未载入，不作为真实面板';
    dialog.dataset.figureId=active.id;dialog.dataset.sourceStatus=handle.status();
    original.href='/assets/panels/'+active.file+'.png';original.download=active.file+'.png';
    display.href='/assets/panels/display/'+active.file+'-contain.svg';display.download=active.file+'-contain.svg';
    for(const b of nav.children)b.setAttribute('aria-pressed',String(b.dataset.figureId===active.id));
  };
  const select=row=>{active=row;const current=++token;paint();handles[row.key].ready().then(()=>{if(current===token)paint();});};
  for(const row of rows){const b=doc.createElement('button');b.type='button';b.dataset.figureId=row.id;b.textContent=row.id;b.onclick=()=>select(row);nav.append(b);}
  retry.onclick=()=>{const current=++token;handles[active.key].retry().then(()=>{if(current===token)paint();});paint();};
  button.hidden=false;button.onclick=()=>{opener=doc.activeElement;select(active);dialog.showModal();};
  const cancel=event=>{if(!dialog.open||event.key!=='Escape')return;event.preventDefault();event.stopImmediatePropagation();dialog.close();};
  const closed=()=>{opener?.isConnected&&opener.focus();};
  doc.addEventListener('keydown',cancel,true);dialog.addEventListener('close',closed);
  return {dispose(){if(disposed)return;disposed=true;++token;button.onclick=null;button.hidden=true;doc.removeEventListener('keydown',cancel,true);dialog.removeEventListener('close',closed);dialog.close();dialog.remove();style.remove();}};
}
