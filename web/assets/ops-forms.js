/* Secondary management forms load only when opened. */
// ── 当前用户与「用户与权限」区（仅 admin） ─────────────────
let ME=null;
async function initWho(){
  try{
    ME=await (await fetch("/api/whoami")).json();
    if(!ME.ok) return;
    document.getElementById("whoami").innerHTML =
      `${ME.user} · ${ME.role} &nbsp;<a href="/account">改密码</a> &nbsp;<a href="/logout">退出</a>`;
    if(ME.role==="admin"){document.getElementById("usersSec").style.display="";if(document.getElementById("users-drawer").open)loadUsers();}
  }catch(e){}
}
async function loadUsers(){
  const d=await (await fetch("/api/users")).json();
  if(!d.ok) return;
  const tb=document.querySelector("#usersTable tbody");
  tb.innerHTML=d.users.map(u=>`<tr>
    <td><b>${u.name}</b>${u.name===ME.user?' <span style="color:var(--muted);font-size:11px">(我)</span>':''}</td>
    <td><select onchange="setRole('${u.name}',this.value,this)" style="padding:3px 6px;border-radius: var(--ui-radius);border:1px solid var(--line);background:var(--card);color:var(--text)">
      ${["intern","member","admin"].map(r=>`<option value="${r}"${r===u.role?" selected":""}>${r}</option>`).join("")}
    </select></td>
    <td style="color:var(--muted)">${u.created}</td>
    <td style="text-align:right;white-space:nowrap">
      <a href="#" onclick="resetPw('${u.name}');return false">重置密码</a> ·
      <a href="#" onclick="renameU('${u.name}');return false">改名</a> ·
      <a href="#" onclick="removeU('${u.name}');return false" style="color:var(--red)">删除</a>
    </td></tr>`).join("");
}
function umsg(ok,text){const m=document.getElementById("usersMsg");
  m.style.color=ok?"var(--green)":"var(--red)";m.textContent=text;}
function showPw(name,pw){
  document.getElementById("pwUser").textContent=name;
  document.getElementById("pwText").textContent=pw;
  document.getElementById("pwCopied").textContent="";
  document.getElementById("pwReveal").style.display="";
}
function copyPw(){navigator.clipboard.writeText(document.getElementById("pwText").textContent)
  .then(()=>document.getElementById("pwCopied").textContent="✓ 已复制");}
async function uapi(body){
  const d=await (await fetch("/api/users",{method:"POST",body:JSON.stringify(body)})).json();
  umsg(d.ok,d.ok?(d.msg||"完成"):(d.error||"失败"));
  if(d.ok){loadUsers();if(d.password)showPw(body.username,d.password);}
  return d;
}
function addUser(){
  const name=document.getElementById("nuName").value.trim();
  if(!name){umsg(false,"填一个用户名");return;}
  uapi({action:"add",username:name,role:document.getElementById("nuRole").value})
    .then(d=>{if(d.ok)document.getElementById("nuName").value="";});
}
function setRole(name,role,sel){
  uapi({action:"role",username:name,role}).then(d=>{if(!d.ok)loadUsers();});
}
function resetPw(name){
  if(!confirm(`重置 ${name} 的密码？旧密码将立即失效。`))return;
  uapi({action:"reset",username:name});
}
function renameU(name){
  const nn=prompt(`把 ${name} 改成什么名字？\n（改名后其旧登录立即失效，须用新名重登）`,name);
  if(!nn||nn===name)return;
  uapi({action:"rename",username:name,new_name:nn.trim()});
}
function removeU(name){
  if(!confirm(`确定删除 ${name}？其登录立即失效。此操作不可撤销。`))return;
  uapi({action:"remove",username:name});
}
initWho();
const usersDrawer=document.getElementById('users-drawer');
usersDrawer.addEventListener('toggle',()=>{if(usersDrawer.open && ME?.role==='admin')loadUsers();});
async function loadJSON(path) {
  const r = await fetch(path + "?t=" + Date.now(), { cache: "no-store", priority: "high" });
  if (!r.ok) throw new Error(path + " → HTTP " + r.status);
  return r.json();
}
/* 生成物新鲜度：各登记表与生成物的版本、时点与条数（不做聚合，不填估值） */
async function loadFreshness() {
  document.getElementById("error").textContent="";
  try {
    const [dash, targets, graph, questions, model, prices, companies, products, bom] = await Promise.all([
      loadJSON("data/dashboard.json"), loadJSON("framework/tco_targets.json"), loadJSON("framework/research_graph.json"),
      loadJSON("framework/research_questions.json"), loadJSON("data/datacenter_model.json"), loadJSON("data/prices.json"),
      loadJSON("data/companies.json"), loadJSON("data/products.json"), loadJSON("framework/bom.json")]);
    document.getElementById("updated").textContent = `图谱 ${graph.version} · 目标表 ${targets.version} · 骨架 ${bom.version}`;
    const rows = [
      ["dashboard 快照", "data/dashboard.json", dash.version, dash.updated, `${dash.system_nodes.length} 系统 · ${Object.keys(dash.parts).length} 部件`, "python3 manage.py dashboard --refresh"],
      ["目标表", "framework/tco_targets.json", targets.version, targets.updated, `${targets.counts.total} 行（缺 ${targets.counts.by_status.needed}）`, "python3 manage.py targets --refresh"],
      ["研究图谱", "framework/research_graph.json", graph.version, graph.updated, `${graph.objects.length} 对象 · ${graph.relations.length} 关系`, "python3 manage.py graph --refresh"],
      ["问题表", "framework/research_questions.json", questions.version, questions.updated, `${questions.records.length} 条`, "python3 manage.py graph --refresh"],
      ["统一经济模型", "data/datacenter_model.json", model.schema_version, model.as_of, `${Object.keys(model.inputs).length} 输入 · ${Object.keys(model.presets).length} 预设`, "评审后手改"],
      ["骨架", "framework/bom.json", bom.version, bom.updated, `${bom.parts.length} 条目 · ${bom.stages.length} 段`, "评审后手改"],
    ];
    document.getElementById("freshness").innerHTML = '<tr><th>生成物 / 登记</th><th>文件</th><th>版本</th><th>时点</th><th>规模</th><th>重建</th></tr>' +
      rows.map(r => `<tr><td>${r[0]}</td><td><code>${r[1]}</code></td><td>${r[2] ?? "—"}</td><td>${r[3] ?? "—"}</td><td>${r[4]}</td><td><code>${r[5]}</code></td></tr>`).join("");
    const stats = [[prices.records.length, "价格点"], [companies.records.length, "主体"], [products.records.length, "产品线"], [bom.parts.length, "部件条目"], [targets.counts.total, "目标行"]];
    document.getElementById("stats").innerHTML = stats.map(([n, l]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`).join("");
  } catch (e) {
    document.getElementById("error").textContent = "生成物读取失败：" + e.message + "。关闭后重新展开可重试。";
    throw e;
  }
}

// 手动录入保留既有校验与写入接口。
// 录入表单：序列名自动补全 + 提交
async function loadPriceOptions() {
  try {
    const prices = await (await fetch("data/prices.json?t=" + Date.now())).json();
    document.getElementById("serieslist").innerHTML =
      [...new Set(prices.records.map(r => r.series_id))].map(s => `<option value="${s}">`).join("");
    const targets = await (await fetch("framework/tco_targets.json?t=" + Date.now())).json();
    document.getElementById("targetlist").innerHTML = targets.targets.filter(t => t.data_class === "observation").map(t => `<option value="${t.id}">${t.disclosure_type}</option>`).join("");
  } catch (e) { throw e; }
}
document.getElementById("psubmit").onclick = async () => {
  const f = document.getElementById("pform");
  const rec = Object.fromEntries(new FormData(f).entries());
  if (!rec.target_id) delete rec.target_id;
  const msg = document.getElementById("pmsg");
  msg.textContent = "提交中…"; msg.style.color = "var(--muted)";
  try {
    const r = await (await fetch("/api/add-price", { method: "POST", body: JSON.stringify(rec) })).json();
    msg.textContent = r.ok ? "✔ " + r.msg : "✘ " + r.error;
    msg.style.color = r.ok ? "var(--green)" : "var(--red)";
    if (r.ok) { f.reset(); clog("✔ 录入 " + rec.series_id + "@" + rec.as_of + " = " + rec.value + " " + rec.unit); }
  } catch (e) { msg.textContent = "✘ " + e.message; msg.style.color = "var(--red)"; }
};

// Optional drawers have independent reads; opening the dashboard does not load them.
function lazyDrawer(id, load) {
  const drawer=document.getElementById(id);let pending=null,done=false;
  const run=()=>{
    if(!drawer.open || done || pending)return;
    pending=load().then(()=>{done=true;}).catch(()=>{}).finally(()=>{pending=null;});
  };
  drawer.addEventListener('toggle',run);run();
}
lazyDrawer('freshness-drawer',loadFreshness);
lazyDrawer('prices-drawer',loadPriceOptions);
