/* All browser checks share one isolated, ephemeral local application server. */
const {spawn} = require('node:child_process');
const {mkdtempSync, rmSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join, resolve} = require('node:path');
const {createInterface} = require('node:readline');
const root = resolve(__dirname, '..');
const directory = mkdtempSync(join(tmpdir(), 'inresearch-browser-'));
const suites = process.argv.slice(2);
const defaults = ['ops_dashboard', 'industry', 'repository_pages', 'supply', 'nvidia_pilot', 'product_catalog', 'company_page', 'company_window', 'company_catalog_map', 'catalog_materials', 'compute_catalog', 'ui_skin', 'datacenter_cost', 'datacenter_economics', 'datacenter_tco', 'datacenter_news',
  'url_rendering', 'research_delivery', 'auth_appearance', 'research_summary', 'part_dossier', 'technical_atlas', 'dashboard', 'scene_bootstrap', 'scene_framing', 'scene_resources', 'model_assets'];
const environment = {...process.env, INRESEARCH_INTAKE_ROOT: directory, INRESEARCH_MARKET_ENABLED: '0'};
const server = spawn(process.env.PYTHON || 'python3', ['-u', '-c',
  "import sys,os,json,secrets; from pathlib import Path; sys.path.insert(0,'src'); from inresearch.interfaces import http as serve,auth; directory=Path(os.environ['INRESEARCH_INTAKE_ROOT']); auth.USERS_FILE=directory/'browser-users.json'; auth.SECRET_FILE=directory/'.browser-secret'; auth.add_user('browser-admin',secrets.token_urlsafe(32),'admin'); s=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler); print(json.dumps({'port':s.server_port,'admin_cookie':auth.make_cookie('browser-admin').split(';')[0]}),flush=True); s.serve_forever()"],
  {cwd:root, env:environment, stdio:['ignore','pipe','inherit']});
const lines = createInterface({input:server.stdout});
const ready = new Promise((resolve, reject) => {
  lines.once('line', line => {
    try {
      const result=JSON.parse(line);
      if(!Number.isInteger(result.port) || !result.admin_cookie) throw Error('Invalid test server readiness');
      resolve(result);
    } catch(error) { reject(error); }
  });
  server.once('error', reject);
  server.once('exit', code => reject(Error('Test server exited: ' + code)));
});
(async () => {
  try {
    const {port, admin_cookie} = await ready;
    const selected=suites.length ? suites.flatMap(s=>s==='core'?defaults.filter(v=>v!=='model_assets'):[s]) : defaults;
    for (const suite of selected) {
      if (!defaults.includes(suite)) throw Error('Unknown suite: ' + suite);
      for(const scenario of suite==='model_assets'?['bom3d','rack3d','compare']:[null]) {
      const label=suite+(scenario?':'+scenario:''),started=Date.now();
      console.log('START '+label);
      await new Promise((resolve, reject) => {
        const child = spawn(process.execPath, [join(__dirname, suite + '.cjs'), ...(scenario?[scenario]:[])], {
          timeout:300000, cwd:root, env:{...environment, UI_BASE_URL:'http://127.0.0.1:' + port, UI_ADMIN_COOKIE:admin_cookie}, stdio:'inherit'});
        child.once('error', reject);
        child.once('exit', (code, signal) => code === 0 ? resolve() : reject(Error(label + ' failed after '+Math.round((Date.now()-started)/1000)+'s: ' + (signal || code))));
      });
      console.log('DONE '+label+' '+Math.round((Date.now()-started)/1000)+'s');
      }
    }
  } finally {
    server.kill(); lines.close(); rmSync(directory, {recursive:true, force:true});
  }
})().catch(error => {console.error(error); process.exitCode=1;});
