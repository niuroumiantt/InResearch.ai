/* Aggregates describe different units and scopes; arrows are references, not a funnel. */
(()=>{'use strict';
 const host=document.getElementById('material-board');if(!host)return;
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const count=n=>Number.isSafeInteger(n)?n.toLocaleString('zh-CN'):'—';
 const bytes=(n,unit='GB')=>Number.isSafeInteger(n)?(n/(unit==='GB'?1e9:1e6)).toLocaleString('zh-CN',{minimumFractionDigits:unit==='GB'?2:2,maximumFractionDigits:n>0&&n<1e5?3:2})+' '+unit:'—';
 const date=v=>v&&Number.isFinite(new Date(v).getTime())?new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未测量';
 const names={queued:'等待研究核验',reviewing:'正在核验',review_ready:'已核验待发布',published:'已完成发布流程',already_adopted:'已有正式采用',needs_owner:'需负责人判断',needs_specialist:'需专项核验',needs_demand_match:'待匹配现行需求',deferred:'核验阻塞',defer:'待补充证据',background:'背景资料',duplicate:'重复主张'};
 const roles={reader:['Reader catalog','文件身份、来源版本、阅读任务与正文结果指针'],acquisition:['采集库','爬取接收、新闻线索、侧车与交付回执'],review:['研究核验库','候选分流、核验尝试、独立复核与发布状态']};
 let data,selected='archive',loading=false;
 const row=(label,value,total,unit)=>`<div class="material-row"><div>${esc(label)}</div><div class="track" aria-hidden="true"><span style="width:${Number.isSafeInteger(value)&&Number.isSafeInteger(total)&&total>0?Math.min(100,value/total*100):0}%"></span></div><div class="number">${unit?bytes(value,unit):count(value)}</div></div>`;
 const explanation={
 archive:'目录统计的是占用磁盘的文件副本、暂存件、派生件和备份。相同内容出现在多个目录时仍占空间；登记库则以 SHA-256 识别内容。两边覆盖范围不同，容量差不能解释为去重节省量。',
 catalog:'一个 SHA-256 对应一个内容身份。相同字节再次接收可以追加来源记录，复用内容身份；不同字节形成新身份。登记文件包含 PDF、HTML、文本派生、CAD 和视频，登记不代表已经阅读。',
 reading:'本批范围由 execution_scope 指定，是全库的一部分。一份完成的正文报告可产出多条候选陈述与多段原文引句；正文已读、图片跳过及缺页分别保留。',
 review:'全核验队列的候选按现行需求匹配、原文与口径核验、独立复核后进入发布。下列状态按候选陈述计数，不是文件数。引文与候选是多对多关系，证据数不能作为额外候选相加。',
 website:'候选快照由 Spark 发布到 AWS，供网页查询与展示。正式研究记录经单独核验与发布进入当前研究版本；排队或核验通过不能直接算作网页已采用，项目、合同和 IT 容量继续分别登记。'};
 function detail(){
  if(!data)return;const m=data.measurements||{},cat=m.catalog||{},archive=m.archive||{},scope=data.execution_scope||{},review=data.review?.candidates||{};
  let body='';
  if(selected==='archive'){
   const dirs=archive.directories||{};const derived=['fulltext_ocr','offload','extracted','fulltext','artifacts','pdf-text'];
   const known=derived.filter(k=>Number.isSafeInteger(dirs[k]));const derivedBytes=['observed','stale'].includes(archive.state)?known.reduce((t,k)=>t+dirs[k],0):null;
   const groups=[['raw-materials',dirs['raw-materials']],['originals',dirs.originals],['incoming',dirs.incoming],['派生文件（六类目录）',derivedBytes],['backups 目录',dirs.backups],['其他目录',archive.other_bytes]];
   body=`<h3>磁盘目录占用 <span class="material-unit">${date(archive.measured_at)} · ${archive.state==='stale'?'上次成功测量，当前采集失败':'低频采样，最多缓存一小时'}</span></h3>${groups.map(([k,v])=>row(k,v,archive.allocated_bytes,'GB')).join('')}<div class="material-example" aria-label="内容去重示意"><span>原始 PDF</span><span>incoming 副本</span><span>originals 副本</span> → <span>字节一致：同一 SHA，登记一次</span></div><p class="material-meta">此处是关系示意；未测量全库副本数量，也未测量未登记原件总量。</p>`;
  }else if(selected==='catalog'){
   body=`<h3>登记文件类型（含派生）</h3>${(cat.types||[]).map(r=>row(r.suffix||'无后缀',r.files,cat.files)).join('')}<h3>全库当前阅读状态</h3>${Object.entries(cat.states||{}).map(([k,v])=>row(({complete:'完成候选报告',queued:'队列登记',blocked:'阻塞或按规则暂缓',running:'处理中的文件',failed:'执行失败'})[k]||k,v,cat.files)).join('')}<p>派生件、CAD、视频和不支持格式保留各自用途与状态，不能全部作为待读报告。全库状态与下一个“本批阅读”范围分别计量。</p>`;
  }else if(selected==='reading'){
   body=`<h3>本批材料 → 阅读候选</h3><div class="material-example"><span>${count(scope.documents)} 份本批材料</span> → <span>${count(m.candidates?.statements)} 条候选陈述</span> ↔ <span>${count(m.candidates?.evidence)} 条原文证据</span></div><p>候选计量范围 ${count(m.candidates?.documents)} 份；PDF ${count(scope.types?.['.pdf'])} · HTML ${count(scope.types?.['.html'])}；已读正文段 ${count(scope.chunks_read)} / ${count(scope.chunks_total)}。</p><p>有缺页记录的报告 ${count(scope.complete_with_gaps)} 份，共 ${count(scope.unread_gap_pages)} 页；跳过图片 ${count(scope.skipped_image_pages)} 页、无文字层 ${count(scope.text_layer_empty_pages)} 页。候选与引文保存来源、阅读版本、页码及定位指针。</p><p><a href="/supply.html#matching">查看材料阅读交付与原文引句 →</a></p>`;
  }else if(selected==='review'){
   const total=data.review?.state==='observed'?Object.values(review).reduce((a,b)=>a+b,0):null;body=`<h3>候选状态分布 <span class="material-unit">共 ${count(total)} 条陈述；同一条只在一个当前状态内</span></h3>${Object.entries(review).map(([k,v])=>row(names[k]||k,v,total)).join('')}<p>已核验待发布仍需通过发布检查和网页验收。正式页面的采用数量在右侧独立读取，不能用本表总数推算完成率或 GW。</p>`;
  }else{
   body=`<h3>AWS 展示与正式采用</h3><p>本次读取的正式研究陈述 ${count(data.formal?.statements)} 条；项目 ${count(data.formal?.projects)} 条、合同 ${count(data.formal?.contracts)} 条，三个集合有不同身份和口径。</p><p>候选快照 ${bytes(data.website?.candidate_snapshot_bytes,'MB')}，保存网页需要的候选 JSON；不会把 Spark 原件全部复制到网站。</p><p>网站收到 Spark 快照：${date(data.received_at)}。来源数据库与正式版本分别更新，接收时间不等于研究采用时间。</p><p><a href="/node.html?id=root#evidence">查看已采用研究与证据 →</a> · <a href="/projects.html">查看正式项目 →</a></p>`;
  }
  host.querySelector('#material-detail').innerHTML=`<h2>${esc(({archive:'文件与副本',catalog:'登记与文件类型',reading:'本批与候选',review:'核验与分流',website:'接收与正式展示'})[selected])}</h2><p>${explanation[selected]}</p>${body}`;
  host.querySelectorAll('[data-step]').forEach(b=>b.closest('li').setAttribute('aria-current',b.dataset.step===selected?'step':'false'));
 }
 function render(){
  const m=data.measurements||{},cat=m.catalog||{},scope=data.execution_scope||{},review=data.review?.candidates||{};
  const total=data.review?.state==='observed'?Object.values(review).reduce((a,b)=>a+b,0):null;
  const nodes=[['archive','① Spark 文件目录',bytes(m.archive?.allocated_bytes),`副本、暂存、派生与备份`,`目录采样 ${date(m.archive?.measured_at)}`],['catalog','② 内容登记',count(cat.content_identities)+' 个',`${bytes(cat.size_bytes)} · SHA 内容身份`,'全库，包含派生与非报告格式'],['reading','③ 本批正文阅读',`${count(scope.counts?.complete)} / ${count(scope.documents)}`,`${count(m.candidates?.statements)} 条候选 · ${count(m.candidates?.evidence)} 条证据`,'一份材料 → 多条陈述与引文'],['review','④ 研究核验',count(total)+' 条',`${count(review.queued)} 等待 · ${count(review.reviewing)} 处理中`,`${count(review.review_ready)} 已核验待发布`],['website','⑤ AWS 正式展示',count(data.formal?.statements)+' 条','全库正式研究陈述，另有项目与合同',`网站接收 ${date(data.received_at)}`]];
  host.querySelector('#material-lineage').innerHTML=nodes.map(([k,title,value,sub,note])=>`<li class="material-node" aria-current="${selected===k?'step':'false'}"><button type="button" data-step="${k}" aria-controls="material-detail">${title}</button><strong class="value">${value}</strong><p>${esc(sub)}</p><p class="material-meta">${esc(note)}</p></li>`).join('');
  host.querySelector('#material-measured').textContent=`Spark 登记与数据库采样 ${date(m.measured_at)} · 网站测量 ${date(data.website?.measured_at)} · ${data.stale?'接收快照缺失或超过15分钟':'已接收快照'}；各层单位与时点分别计量。`;
  const dbs=m.databases||{};
  host.querySelector('#material-stores').innerHTML=Object.entries(roles).map(([k,[name,why]])=>{const v=dbs[k]||{};return `<article><h3>${name}</h3><strong>${bytes(v.file_bytes,'MB')}</strong><p>${why}</p><p>WAL ${bytes(v.wal_bytes,'MB')} · SHM ${bytes(v.shm_bytes,'MB')}</p><p>索引 ${bytes(v.index_bytes,'MB')}，属于库内部，勿重复相加。</p></article>`;}).join('');
  const website=data.website||{};host.querySelector('#material-web-storage').innerHTML=`<h3>网站运行目录的包含关系</h3><div class="material-example"><span>AWS 运行目录<br><b>${bytes(website.allocated_bytes,'MB')}</b></span> ⊃ <span>候选 JSON 快照<br><b>${bytes(website.candidate_snapshot_bytes,'MB')}</b></span> ＋ <span>产品 SQLite 库<br><b>${bytes(website.product_database_bytes,'MB')}</b></span> ＋ <span>其他运行文件</span></div><p>父目录按磁盘分配计量，子文件按文件大小计量；产品数据库服务规格页，与研究核验库用途不同。索引是库内部结构，WAL 是尚未归并的事务页，SHM 是 WAL 协调信息；它们不代表新增材料或新增事实。</p><p>数据库引用原件与产物身份，正文、图像和原件保存在 Spark 文件目录中。数据量变小是载体和覆盖范围变化，不能解释为研究处理完成率。</p>`;
  detail();
 }
 host.addEventListener('click',e=>{const step=e.target.closest('[data-step]');if(step){selected=step.dataset.step;detail();}if(e.target.closest('#material-refresh'))refresh();});
 async function refresh(){if(loading)return;loading=true;host.setAttribute('aria-busy','true');const error=host.querySelector('#material-error');error.hidden=true;const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);
  try{const r=await fetch('/api/admin/material-flow',{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('读取失败 '+r.status);const next=await r.json();if(next.schema_version!==1)throw Error('指标格式不符');data=next;render();}
  catch(e){error.hidden=false;error.textContent='指标暂未读到；'+(data?'保留上次结果与时间。':'未测量项目显示 —。')+'请点击刷新重试。';}
  finally{clearTimeout(timeout);loading=false;host.setAttribute('aria-busy','false');}
 }
 refresh();setInterval(()=>{if(!document.hidden)refresh();},60000);
})();
