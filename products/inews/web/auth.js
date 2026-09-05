// 管理处：登录状态 + 页眉右上角的下拉菜单 + 登录/注册/找回密码弹窗。
//
// 时间线是公开的，其余（Dashboard、规则演化、账号管理）都要求管理员登录。
// 所以未登录时那些入口直接隐藏 —— 让访客先点进去再吃 403 是最差的一种交互。

const $ = (s) => document.querySelector(s);

export const auth = { user: null, csrf: null, registrationOpen: false, requireLogin: false };
const listeners = [];
export const onAuthChange = (fn) => { listeners.push(fn); fn(auth); };
const emit = () => listeners.forEach((fn) => fn(auth));

/** 后端把预期状态放在 HTTP code 上，错误文案放在 body.error。 */
async function call(url, { method = 'GET', body } = {}) {
  let res;
  try {
    res = await fetch(url, {
      method,
      // Do not let a 307/308 carry a password-bearing POST body to a login
      // page (or anywhere else). The response checks below stay as defence in
      // depth for browsers/polyfills that do not honour this option correctly.
      redirect: 'error',
      headers: {
        ...(body ? { 'content-type': 'application/json' } : {}),
        ...(auth.csrf && method !== 'GET' ? { 'x-csrf-token': auth.csrf } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    const err = new Error('API 请求被重定向或网络中断，请刷新页面后重试');
    err.status = 0;
    err.cause = cause;
    throw err;
  }
  // API calls must never turn into page navigation.  During the native-auth
  // rollout the old outer login gate can redirect an expired request to an
  // HTML login page. Before redirects were forbidden above, fetch followed it
  // and reported the final page as HTTP 200. Treating that HTML as `{}` used
  // to look like a successful login and close
  // the modal even though no native session had been created.
  if (res.redirected) {
    const err = new Error('登录状态已失效，请刷新页面后重新登录');
    err.status = 401;
    throw err;
  }
  const contentType = res.headers?.get?.('content-type') || '';
  if (!/^application\/(?:json|[a-z0-9!#$&^_.+-]+\+json)(?:\s*;|$)/i.test(contentType)) {
    const err = new Error('服务返回了非 API 响应，请刷新页面后重试');
    err.status = res.status;
    throw err;
  }
  let data;
  try {
    data = await res.json();
  } catch {
    const err = new Error('服务返回了无效的 API 响应，请刷新页面后重试');
    err.status = res.status;
    throw err;
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    const err = new Error('服务返回了无效的 API 响应，请刷新页面后重试');
    err.status = res.status;
    throw err;
  }
  if (!res.ok || data.error) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const post = (url, body) => call(url, { method: 'POST', body });

export function assertSessionPayload(data) {
  const user = data?.user;
  if (!Number.isInteger(user?.id) || user.id <= 0
      || typeof user.email !== 'string' || !user.email.trim()
      || typeof user.nickname !== 'string' || !user.nickname.trim()
      || !['user', 'staff', 'admin'].includes(user.role)
      || typeof user.is_staff !== 'boolean'
      || typeof data.csrf !== 'string' || !data.csrf) {
    const err = new Error('登录响应不完整，请刷新页面后重试');
    err.status = 502;
    throw err;
  }
  return data;
}

export async function refreshAuth() {
  try {
    const data = await call('/api/auth/me');
    auth.user = data.user;
    auth.csrf = data.csrf || null;
    auth.registrationOpen = Boolean(data.registrationOpen);
    auth.requireLogin = Boolean(data.requireLogin);
  } catch {
    auth.user = null; auth.csrf = null;
  }
  emit();
  return auth;
}

/* ---------------- 弹窗 ---------------- */

const FIELD = (name, label, type = 'text', extra = '') =>
  `<label><span>${label}</span><input name="${name}" type="${type}" ${extra}></label>`;

const CODE_ROW = (label) => `<label><span>${label}</span><div class="sd-modal__row">
    <input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6">
    <button type="button" data-code>获取验证码</button></div></label>`;

const FORMS = {
  login: {
    title: '登录管理处', submit: '登录', alt: '忘记密码？',
    altMode: 'reset',
    // 登录框收**邮箱或用户名**，所以是 text 不是 email:type="email" 会让浏览器
    // 在你敲 admin 的时候弹一句英文的 "Enter an email address" 把提交拦下来。
    fields: FIELD('identifier', '邮箱或用户名', 'text', 'autocomplete="username"')
      + FIELD('password', '密码', 'password', 'autocomplete="current-password"'),
    async run(v) {
      const r = assertSessionPayload(await post('/api/auth/login', {
        identifier: v.identifier, password: v.password,
      }));
      auth.user = r.user; auth.csrf = r.csrf; emit();
      return '登录成功';
    },
  },
  register: {
    title: '注册账号', submit: '注册', alt: '已有账号？去登录', altMode: 'login',
    purpose: 'register',
    fields: FIELD('email', '邮箱', 'email', 'autocomplete="username"')
      + CODE_ROW('邮箱验证码')
      + FIELD('nickname', '昵称（选填）')
      + FIELD('password', '密码（至少 8 位）', 'password', 'autocomplete="new-password"'),
    async run(v) {
      const r = assertSessionPayload(await post('/api/auth/register', v));
      auth.user = r.user; auth.csrf = r.csrf; emit();
      return '注册成功';
    },
  },
  reset: {
    title: '重置密码', submit: '重置', alt: '返回登录', altMode: 'login',
    purpose: 'reset',
    fields: FIELD('email', '邮箱', 'email', 'autocomplete="username"')
      + CODE_ROW('邮箱验证码')
      + FIELD('password', '新密码（至少 8 位）', 'password', 'autocomplete="new-password"'),
    async run(v) {
      await post('/api/auth/password/reset', v);
      return '密码已重置，请用新密码登录';
    },
  },
  change: {
    title: '修改密码', submit: '保存', alt: '', altMode: null,
    fields: FIELD('current', '当前密码', 'password', 'autocomplete="current-password"')
      + FIELD('password', '新密码（至少 8 位）', 'password', 'autocomplete="new-password"'),
    async run(v) {
      await post('/api/auth/password/change', v);
      return '密码已更新，其它设备上的登录已失效';
    },
  },
};

let mode = 'login';
let closeTimer = null;
let modalGeneration = 0;
let submissionGeneration = 0;

function cancelScheduledClose() {
  if (closeTimer === null) return;
  clearTimeout(closeTimer);
  closeTimer = null;
}

function openModal(next = 'login') {
  cancelScheduledClose();
  modalGeneration += 1;
  mode = next;
  const form = FORMS[mode];
  $('#auth-title').textContent = form.title;
  $('#auth-submit').textContent = form.submit;
  $('#auth-fields').innerHTML = form.fields;
  $('#auth-alt').textContent = form.alt;
  $('#auth-alt').hidden = !form.alt;
  $('#auth-submit').disabled = false;
  message('');
  $('#modal').classList.remove('sd-hide');
  $('#auth-fields').querySelector('input')?.focus();
}

const closeModal = () => {
  cancelScheduledClose();
  modalGeneration += 1;
  $('#modal').classList.add('sd-hide');
};

function scheduleCloseModal(expectedGeneration) {
  cancelScheduledClose();
  closeTimer = setTimeout(() => {
    closeTimer = null;
    if (modalGeneration !== expectedGeneration) return;
    modalGeneration += 1;
    $('#modal').classList.add('sd-hide');
  }, 400);
}

function message(text, ok = false) {
  const box = $('#auth-msg');
  box.textContent = text;
  box.classList.toggle('ok', ok);
}

const values = () => Object.fromEntries(
  [...$('#auth-fields').querySelectorAll('input')].map((i) => [i.name, i.value.trim()]));

async function requestCode(btn) {
  const expectedGeneration = modalGeneration;
  const purpose = FORMS[mode].purpose;
  const email = values().email;
  if (!email) return message('请先填邮箱');
  btn.disabled = true;
  try {
    const r = await post(`/api/auth/${purpose === 'register' ? 'register' : 'password'}/code`, { email });
    if (modalGeneration !== expectedGeneration) return;
    message(r.devConsole ? '验证码已发到服务端日志（未配置 SMTP 的开发模式）' : '验证码已发送，10 分钟内有效', true);
    // 冷却是给用户看的，真正的限流在服务端（每小时 5 次）。
    let left = 60;
    btn.textContent = `${left}s`;
    const timer = setInterval(() => {
      if (--left <= 0) { clearInterval(timer); btn.disabled = false; btn.textContent = '获取验证码'; }
      else btn.textContent = `${left}s`;
    }, 1000);
  } catch (e) {
    if (modalGeneration !== expectedGeneration) return;
    btn.disabled = false;
    message(e.message);
  }
}

/* ---------------- 页眉菜单 ---------------- */

function paintMenu() {
  const signedIn = Boolean(auth.user);
  const staff = Boolean(auth.user?.is_staff);
  $('#account-btn').textContent = signedIn ? `${auth.user.nickname} ▾` : '管理 ▾';
  $('#account-btn').classList.toggle('sd-menu__btn--in', signedIn);
  $('#account-who').innerHTML = signedIn
    ? `<b>${auth.user.email}</b>${auth.user.role === 'admin' ? '管理员' : auth.user.role === 'staff' ? '运营' : '普通用户'}`
    : auth.requireLogin ? '未登录 · 本站需要账号' : '未登录 · 分析页面需要管理员';
  $('#menu-login').hidden = signedIn;
  $('#menu-register').hidden = signedIn || !auth.registrationOpen;
  $('#menu-password').hidden = !signedIn;
  $('#menu-logout').hidden = !signedIn;
  for (const n of document.querySelectorAll('[data-staff]')) n.hidden = !staff;
}

export function initAuth({ onTab, onTranslate } = {}) {
  const pop = $('#account-pop');
  const btn = $('#account-btn');
  const toggle = (open) => { pop.hidden = !open; btn.setAttribute('aria-expanded', String(open)); };

  btn.onclick = (e) => { e.stopPropagation(); toggle(pop.hidden); };
  document.addEventListener('click', (e) => { if (!$('#account').contains(e.target)) toggle(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    toggle(false);
    closeModal();
  });

  for (const item of pop.querySelectorAll('[data-tab]')) {
    item.onclick = () => { toggle(false); onTab?.(item.dataset.tab); };
  }
  $('#menu-login').onclick = () => { toggle(false); openModal('login'); };
  $('#menu-register').onclick = () => { toggle(false); openModal('register'); };
  $('#menu-password').onclick = () => { toggle(false); openModal('change'); };
  $('#menu-logout').onclick = async () => {
    toggle(false);
    await post('/api/auth/logout').catch(() => {});
    auth.user = null; auth.csrf = null; emit();
    onTab?.('timeline');
  };
  $('#menu-translate').onclick = async () => {
    toggle(false);
    onTranslate?.();
  };

  $('#auth-close').onclick = closeModal;
  $('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });
  $('#auth-alt').onclick = () => openModal(FORMS[mode].altMode || 'login');
  $('#auth-fields').addEventListener('click', (e) => {
    if (e.target.matches('[data-code]')) requestCode(e.target);
  });

  $('#auth-form').onsubmit = async (e) => {
    e.preventDefault();
    const submittedMode = mode;
    const submittedModal = modalGeneration;
    const submittedRequest = ++submissionGeneration;
    const submit = $('#auth-submit');
    submit.disabled = true;
    message('');
    try {
      const done = await FORMS[submittedMode].run(values());
      if (modalGeneration !== submittedModal || submissionGeneration !== submittedRequest) return;
      message(done, true);
      // 重置密码后停在弹窗上切到登录；其余情况直接关掉。
      if (submittedMode === 'reset') openModal('login');
      else scheduleCloseModal(submittedModal);
    } catch (err) {
      if (modalGeneration === submittedModal && submissionGeneration === submittedRequest) {
        message(err.message);
      }
    } finally {
      if (modalGeneration === submittedModal && submissionGeneration === submittedRequest) {
        submit.disabled = false;
      }
    }
  };

  onAuthChange(paintMenu);
  return refreshAuth();
}

export { openModal };
