/* The serial core entry and both CI shards use one exhaustive suite list. */
const defaults = ['ops_dashboard', 'industry', 'repository_pages', 'supply', 'nvidia_pilot', 'product_catalog', 'company_page', 'company_window', 'company_catalog_map', 'catalog_materials', 'compute_catalog', 'ui_skin', 'datacenter_cost', 'datacenter_economics', 'datacenter_tco', 'datacenter_news',
  'url_rendering', 'research_delivery', 'auth_appearance', 'research_summary', 'part_dossier', 'technical_atlas', 'server_assembly', 'server_plan', 'rack_assembly', 'rack_atlas', 'rack_exploded', 'rack_exploded_atlas', 'dashboard', 'scene_bootstrap', 'scene_framing', 'scene_resources', 'scene_atlas', 'model_assets'];
const core = defaults.filter(s => s !== 'model_assets');
const dossierScenes = ['/bom3d.html?p=server', '/rack3d.html?node=part:server', '/rack3d.html?node=part:gpu', '/rack3d.html?node=part:hbm', '/rack3d.html?node=part:cpu', '/rack3d.html?node=part:dram', '/rack3d.html?node=part:nic', '/rack3d.html?node=part:psu', '/rack3d.html?node=part:server-fan', '/rack3d.html?node=part:coldplate'];
// Separate the two costly software-rendered dossiers while alternating the
// remaining cases. No case, density or per-case deadline is removed.
const third = ['part_dossier'];
const remaining = core.filter(s => !third.includes(s));
const first = remaining.filter((s, i) => s === 'scene_resources' || (i % 2 === 0 && s !== 'scene_atlas'));
const second = remaining.filter(s => !first.includes(s));
function selectSuites(requested) {
  return requested.length ? requested.flatMap(s => s === 'core' ? core : s === 'core_a' ? first : s === 'core_b' ? second : s === 'core_c' ? third : [s]) : defaults;
}
function suiteScenarios(suite) {
  return suite === 'part_dossier' ? dossierScenes : suite === 'model_assets' ? ['bom3d', 'rack3d', 'compare'] : suite === 'scene_atlas' ? ['1', '2'] : suite === 'rack_exploded' ? ['views', 'assembly'] : [null];
}
module.exports = {defaults, core, selectSuites, suiteScenarios, dossierScenes};
