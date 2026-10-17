(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let state, selected, busy = false;
  async function send(payload) {
    const response = await fetch('/api/project-access',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'project-access'},body:JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok || !data.ok) throw Error(data.error || '保存失败');
    return data;
  }
  function renderUser() {
    selected = state.users.find(u=>u.name === $('project-user').value);
    if (!selected) return;
    const form = $('project-grant'), grant = selected.grant || {};
    form.elements.display_name.value = selected.display_name;
    form.elements.disabled.checked = selected.disabled;
    form.elements.enabled.checked = Boolean(grant.enabled);
    form.elements.frontend.checked = Boolean(grant.frontend);
    form.elements.expires.value = grant.expires_at ? new Date(new Date(grant.expires_at).getTime()+8*3600000).toISOString().slice(0,10) : '';
    $('project-name').textContent = `项目：${state.project.title}`;
    $('project-package-grants').innerHTML = state.packages.map(p=>`<div class="project-grant-row"><span>${esc(p.title)}</span><label><input type="checkbox" data-submit="${esc(p.id)}"${grant.submit_packages?.includes(p.id) ? ' checked' : ''}> 提交</label><label><input type="checkbox" data-approve="${esc(p.id)}"${grant.approve_packages?.includes(p.id) ? ' checked' : ''}> 审批</label></div>`).join('');
  }
  async function load(preferred) {
    const response = await fetch('/api/project-access',{cache:'no-store'});
    if (!response.ok) throw Error('仅项目所有者可以管理授权，请确认登录账号。');
    state = await response.json();
    const people = state.users.filter(u=>u.role === 'collaborator');
    $('project-user').innerHTML = people.map(u=>`<option value="${esc(u.name)}">${esc(u.display_name)} · ${esc(u.name)}</option>`).join('');
    if (people.some(u=>u.name === preferred)) $('project-user').value = preferred;
    $('project-grant').hidden = !people.length;
    $('project-access-status').textContent = people.length ? `${people.length} 个协作者账号。保存权限后，旧会话失效，成员需重新登录。` : '先添加协作者，再设置项目权限。新账号默认没有项目权限。';
    renderUser();
  }
  $('project-user').addEventListener('change',()=>{renderUser();$('project-save-status').textContent='';});
  $('project-reload').addEventListener('click',()=>load(selected?.name).catch(e=>$('project-access-status').textContent=e.message));
  $('project-create').addEventListener('submit',async event=>{
    event.preventDefault();if (busy) return;busy=true;const button=event.currentTarget.querySelector('button');button.disabled=true;
    try {
      const username = event.currentTarget.elements.username.value.trim();
      const data = await send({action:'create',username});
      $('project-created').textContent = `账号：${username}\n初始密码（仅显示这一次）：${data.password}\n请单独交给本人；首次登录须修改密码。接下来设置项目权限。`;
      await load(username);
    } catch(error) {$('project-created').textContent=error.message;}
    finally {busy=false;button.disabled=false;}
  });
  $('project-grant').addEventListener('submit',async event=>{
    event.preventDefault();if (busy || !selected) return;busy=true;const form=event.currentTarget,button=form.querySelector('button[type=submit]');button.disabled=true;
    try {
      const payload={username:selected.name,expected_revision:selected.revision,project_id:state.project.id,
        display_name:form.elements.display_name.value.trim(),disabled:form.elements.disabled.checked,
        grant:{enabled:form.elements.enabled.checked,frontend:form.elements.frontend.checked,
          expires_at:form.elements.expires.value ? form.elements.expires.value+'T23:59:59+08:00' : null,
          submit_packages:[...form.querySelectorAll('[data-submit]:checked')].map(el=>el.dataset.submit),
          approve_packages:[...form.querySelectorAll('[data-approve]:checked')].map(el=>el.dataset.approve)}};
      await send(payload);await load(selected.name);$('project-save-status').textContent='授权已保存。';
    } catch(error) {$('project-save-status').textContent=error.message;}
    finally {busy=false;button.disabled=false;}
  });
  load().catch(error=>$('project-access-status').textContent=error.message);
})();
