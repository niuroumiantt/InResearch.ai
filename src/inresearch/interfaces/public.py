"""Only the homepage and its bounded rendering dependencies are anonymous.

All other pages, research files, APIs and assets require a session. The former
reader grants remain explicit intern grants; hiding navigation never authorizes
a request. URL paths are decoded/normalized by the HTTP adapter before checking.
"""
from urllib.parse import parse_qs, urlsplit

from inresearch.workflow.product_catalog import COMPANIES

# 目录三项 + 账本，及它们的子页（爆炸图的 3D、芯片级镜头与规格库入口）。
INTERN_RESEARCH_PAGES = ('/', '/industry.html', '/projects.html', '/project.html', '/market.html', '/index.html', '/node.html', '/ledger.html', '/bom.html', '/bom3d.html', '/rack3d.html', '/server-plan.html', '/campus-plan.html', '/facility-atlas.html', '/power-atlas.html', '/thermal-atlas.html', '/compute-atlas.html', '/control-atlas.html', '/cross-scale-atlas.html', '/network-atlas.html', '/storage-atlas.html', '/memory-atlas.html', '/rack-atlas.html', '/rack-exploded.html', '/chip-atlas.html',
                '/product-catalog.html', '/compute-catalog.html', '/report.html',
                '/research/data-centers-2026.html',
                '/research/data-centers-2026-us.html',
                '/research/data-centers-2026-sea.html',
                '/research/data-centers-2026-cn.html',
                '/research/data-centers-2026-projects.html')
# 这些页面读的登记与生成物。目标表的行不含来源 URL（来源登记在 part_fetch.json，不公开）。
INTERN_RESEARCH_DATA = ('/data/dashboard.json', '/data/dashboard_rules.json', '/data/tco_targets.json', '/data/tco_factors.json',
               '/data/datacenter_model.json', '/data/prices.json', '/data/companies.json',
               '/research/data-centers-2026-project-ledger.json', '/research/data-centers-2026-chart-data.json',
               '/framework/bom.json', '/framework/site_rights.json', '/framework/indicators.json', '/framework/modules.json',
               '/framework/tco_factors.json', '/framework/tco_targets.json')
# 只读接口。写接口、任务板、供应台账、用户管理不在内。规格库每家登记公司一条（GET 只读；POST 接收端仍要机器凭证）。
INTERN_RESEARCH_API = ('/api/industry', '/api/observations', '/api/whoami', '/api/report', '/api/news', '/api/company-window', '/api/company-quote', '/api/targets/backflow', '/api/model-assets',
              *('/api/product-catalog/' + company for company in COMPANIES))
# Login and homepage resources are individually declared, never all /assets/.
READER_PAGES = ('/', '/index.html')
READER_API = ('/api/whoami',)
READER_ASSETS = ('/assets/theme-state.js', '/assets/site-skin.js', '/assets/site-skin.css',
                 '/assets/auth-form.js', '/assets/auth.css', '/assets/industry.js',
                 '/assets/industry.css', '/assets/datacenter-news.js', '/assets/datacenter-news.css',
                 '/assets/world.geo.json', '/assets/world-detail.geo.json',
                 *('/assets/map-admin1-' + str(i) + '.geo.json' for i in range(12)))
READER_PREFIXES = ('/assets/fonts/',)
READER_AUTH = ('/login',)
# A health probe discloses no runtime files or research content.
READER_PROBE = ('/healthz', '/robots.txt')
HOME_DATA_API = ('/api/industry', '/api/news')


def allowed(path, query=''):
    """Allow only GET/HEAD dependencies of the homepage and login mechanism.

    The query is checked separately from the normalized path: overview must be
    the only parameter and exactly 1, so company/detail/export queries stay private.
    """
    parsed = urlsplit(path)
    path = parsed.path
    query = query or parsed.query
    if path in HOME_DATA_API:
        return parse_qs(query, keep_blank_values=True) == {'overview': ['1']}
    return (path in READER_PAGES or path in READER_API or path in READER_ASSETS
            or path in READER_AUTH or path in READER_PROBE
            or any(path.startswith(prefix) for prefix in READER_PREFIXES))


def intern_research_allowed(path):
    """Retain the logged-in intern's existing read grants after closing public pages."""
    return path in INTERN_RESEARCH_PAGES or path in INTERN_RESEARCH_DATA or path in INTERN_RESEARCH_API


def public_model(spec):
    """账本的实习生受限视图：只留基准预设与校准锚引用的预设，地区表只留这些预设用到的地区。

    其余键原样保留——输入、证据、口径与公式是模型的可信边界，保留在受限视图；地区预设与情景预设
    是我们的研究工作，member 以上才有。"""
    presets = spec.get('presets') or {}
    keep = {'baseline'} | {c.get('preset') for c in (spec.get('calibration') or {}).values() if c.get('preset') in presets}
    kept = {k: v for k, v in presets.items() if k in keep}
    sites = {spec.get('assumptions', {}).get('site')} | {(p.get('changes') or {}).get('site') for p in kept.values()}
    regions = {k: v for k, v in (spec.get('regions') or {}).items() if k in sites}
    return {**spec, 'presets': kept, 'regions': regions, 'public_view': 'reader'}
