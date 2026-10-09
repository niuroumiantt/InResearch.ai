/* Serial core and CI shards share one exhaustive suite list. */
const defaults = ['ops_dashboard', 'industry', 'repository_pages', 'supply', 'nvidia_pilot', 'product_catalog', 'company_page', 'company_window', 'company_catalog_map', 'catalog_materials', 'compute_catalog', 'ui_skin', 'datacenter_cost', 'datacenter_economics', 'datacenter_tco', 'datacenter_news',
  'url_rendering', 'research_delivery', 'auth_appearance', 'research_summary', 'part_dossier', 'technical_atlas', 'system_atlas', 'scale_atlas', 'campus_overview', 'campus_exploded', 'server_assembly', 'server_plan', 'rack_assembly', 'rack_atlas', 'rack_exploded', 'rack_exploded_atlas', 'chip_package', 'chip_atlas', 'dashboard', 'scene_bootstrap', 'scene_framing', 'scene_resources', 'scene_atlas', 'model_assets'];
const core = defaults.filter(s => s !== 'model_assets');
const dossierScenes = ['/bom3d.html?p=server', '/rack3d.html?node=part:server', '/rack3d.html?node=part:gpu', '/rack3d.html?node=part:hbm', '/rack3d.html?node=part:cpu', '/rack3d.html?node=part:dram', '/rack3d.html?node=part:nic', '/rack3d.html?node=part:psu', '/rack3d.html?node=part:server-fan', '/rack3d.html?node=part:coldplate'];
// Isolate expensive software-rendered suites so their serial total cannot
// exhaust one CI job. Preserve every scene, density and per-case deadline.
const third = ['part_dossier'];
const isolated = ['server_assembly', 'rack_assembly', 'rack_exploded', 'scene_atlas'];
const remaining = core.filter(s => !third.includes(s) && !isolated.includes(s));
const first = remaining.filter((s, i) => s === 'scene_resources' || (i % 2 === 0 && s !== 'scene_atlas'));
const second = remaining.filter(s => !first.includes(s));
function selectSuites(requested) {
  return requested.length ? requested.flatMap(s => s === 'core' ? core : s === 'core_a' ? first : s === 'core_b' ? second : s === 'core_c' ? third : [s]) : defaults;
}
function suiteScenarios(suite) {
  return suite === 'part_dossier' ? dossierScenes : suite === 'model_assets' ? ['bom3d', 'rack3d', 'compare'] : suite === 'scene_atlas' ? ['1', '2'] : ['system_atlas','scale_atlas'].includes(suite) ? ['views', 'downloads'] : ['rack_exploded', 'chip_package', 'campus_overview', 'campus_exploded'].includes(suite) ? ['views', 'assembly'] : [null];
}
module.exports = {defaults, core, selectSuites, suiteScenarios, dossierScenes};
