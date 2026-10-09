/* The serial core entry and both CI shards use one exhaustive suite list. */
const defaults = ['ops_dashboard', 'industry', 'repository_pages', 'supply', 'nvidia_pilot', 'product_catalog', 'company_page', 'company_window', 'company_catalog_map', 'catalog_materials', 'compute_catalog', 'ui_skin', 'datacenter_cost', 'datacenter_economics', 'datacenter_tco', 'datacenter_news',
  'url_rendering', 'research_delivery', 'auth_appearance', 'research_summary', 'part_dossier', 'technical_atlas', 'dashboard', 'scene_bootstrap', 'scene_framing', 'scene_resources', 'scene_atlas', 'model_assets'];
const core = defaults.filter(s => s !== 'model_assets');
// Separate the two costly software-rendered dossiers while alternating the
// remaining cases. No case, density or per-case deadline is removed.
const first = core.filter((s, i) => s === 'scene_resources' || (i % 2 === 0 && s !== 'scene_atlas'));
const second = core.filter(s => !first.includes(s));
function selectSuites(requested) {
  return requested.length ? requested.flatMap(s => s === 'core' ? core : s === 'core_a' ? first : s === 'core_b' ? second : [s]) : defaults;
}
module.exports = {defaults, core, selectSuites};
