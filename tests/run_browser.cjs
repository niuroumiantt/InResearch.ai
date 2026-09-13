/* All browser checks share one isolated, ephemeral local application server. */
const {spawn} = require('node:child_process');
const {mkdtempSync, rmSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join, resolve} = require('node:path');
const {createInterface} = require('node:readline');
const root = resolve(__dirname, '..');
const directory = mkdtempSync(join(tmpdir(), 'inresearch-browser-'));
const suites = process.argv.slice(2);
const defaults = ['ui_skin', 'datacenter_news', 'hardware_ecosystems', 'object_network',
  'product_node_hover', 'url_rendering', 'research_delivery', 'auth_appearance', 'research_summary', 'part_dossier', 'scene_bootstrap', 'model_assets'];
const environment = {...process.env, INRESEARCH_INTAKE_ROOT: directory};
const server = spawn(process.env.PYTHON || 'python3', ['-u', '-c',
  "import sys; sys.path.insert(0,'src'); from inresearch.interfaces import http as serve; s=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler); print(s.server_port,flush=True); s.serve_forever()"],
  {cwd:root, env:environment, stdio:['ignore','pipe','inherit']});
const lines = createInterface({input:server.stdout});
const ready = new Promise((resolve, reject) => {
  lines.once('line', line => /^\d+$/.test(line) ? resolve(line) : reject(Error('Invalid test server port')));
  server.once('error', reject);
  server.once('exit', code => reject(Error('Test server exited: ' + code)));
});
(async () => {
  try {
    const port = await ready;
    for (const suite of suites.length ? suites : defaults) {
      if (!defaults.includes(suite)) throw Error('Unknown suite: ' + suite);
      await new Promise((resolve, reject) => {
        const child = spawn(process.execPath, [join(__dirname, suite + '.cjs')], {
          timeout:300000, cwd:root, env:{...environment, UI_BASE_URL:'http://127.0.0.1:' + port}, stdio:'inherit'});
        child.once('error', reject);
        child.once('exit', (code, signal) => code === 0 ? resolve() : reject(Error(suite + ' failed: ' + (signal || code))));
      });
    }
  } finally {
    server.kill(); lines.close(); rmSync(directory, {recursive:true, force:true});
  }
})().catch(error => {console.error(error); process.exitCode=1;});
