/* Required scene definitions settle before any renderer is created. */
export async function loadSceneData(sources, {controls = [], timeoutMs = 12000} = {}) {
  if (!sources.length || !Number.isFinite(timeoutMs) || timeoutMs <= 0)
    throw new TypeError('Scene data requires sources and a positive timeout');
  const saved = controls.map(control => [control, control.inert]);
  saved.forEach(([control]) => { control.inert = true; });
  const panel = document.createElement('section');
  panel.className = 'rg-scene-startup'; panel.setAttribute('role', 'status');
  panel.setAttribute('aria-live', 'polite');
  const title = document.createElement('h2'), message = document.createElement('p');
  const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = '重试';
  panel.append(title, message, retry); document.body.append(panel);
  try {
    for (;;) {
      panel.dataset.state = 'loading'; panel.setAttribute('aria-busy', 'true');
      title.textContent = '正在载入场景数据'; message.textContent = '数据就绪后即可查看与操作场景。';
      retry.hidden = true; retry.disabled = true;
      const controller = new AbortController();
      let timer;
      try {
        const batch = Promise.all(sources.map(async ({url, collection, schemaVersion}) => {
          const response = await fetch(url, {cache:'no-store', signal:controller.signal});
          if (!response.ok) throw new Error('Scene data HTTP ' + response.status);
          const data = await response.json();
          if (schemaVersion !== undefined && data?.schema_version !== schemaVersion)
            throw new Error('Scene data schema version is unsupported');
          if (!Array.isArray(data?.[collection]) || data[collection].some(row =>
              row === null || typeof row !== 'object' || Array.isArray(row)))
            throw new Error('Scene data collection is invalid');
          return data;
        }));
        const deadline = new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error('Scene data timeout')), timeoutMs);
        });
        // Late completion of an abandoned batch has no UI or application writes.
        return await Promise.race([batch, deadline]);
      } catch {
        panel.dataset.state = 'error'; panel.setAttribute('aria-busy', 'false');
        title.textContent = '场景数据暂不可用'; message.textContent = '请重试，或从上方导航查看其他研究页面。';
        retry.hidden = false; retry.disabled = false;
      } finally {
        clearTimeout(timer); controller.abort();
      }
      await new Promise(resolve => {
        retry.onclick = () => { retry.disabled = true; retry.onclick = null; resolve(); };
      });
    }
  } finally {
    panel.remove(); saved.forEach(([control, inert]) => { control.inert = inert; });
  }
}
