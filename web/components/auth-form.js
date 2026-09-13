/* Authentication forms share validation, pending state and recoverable errors. */
document.addEventListener('submit', async event => {
  const form = event.target.closest('[data-auth-form]');
  if (!form) return;
  event.preventDefault();
  const message = form.querySelector('[role=status]');
  const button = form.querySelector('button');
  if (button.disabled) return;
  const payload = Object.fromEntries(new FormData(form));
  message.className = 'msg err';
  if ('confirm_password' in payload && payload.confirm_password !== payload.new_password) {
    message.textContent = '两次输入的新密码不一致';
    return;
  }
  delete payload.confirm_password;
  if (payload.username) payload.username = payload.username.trim();
  button.disabled = true;
  message.textContent = '正在提交…';
  try {
    const response = await fetch(form.action, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok || !result.ok) throw Error(result.error || '提交失败，请重试');
    if (new URL(form.action).pathname === '/api/login') location.assign('/');
    else { message.className = 'msg ok'; message.textContent = '已修改。下次登录用新密码。'; form.reset(); }
  } catch (error) {
    message.textContent = error instanceof TypeError ? '连接中断，请重试' : error.message;
  } finally {
    button.disabled = false;
  }
});
