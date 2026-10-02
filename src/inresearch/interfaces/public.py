"""公开只读（reader）：不登录即可 GET 的行业总览与研究目录项、它们读的数据，以及服务端按角色过滤的字段。

05 界面规范「目录」：reader 不登录即可看数据中心、爆炸图、成果三项与账本的基准预设；不能改输入、
不能见地区预设、不能见采集页与目标行来源。这里是白名单（默认拒绝）：不在表里的路径，未登录
一律回登录页或 401；写接口永远不公开。过滤在服务端做，页面只是照着渲染。
"""
from urllib.parse import urlsplit

from inresearch.workflow.product_catalog import COMPANIES

# 目录三项 + 账本，及它们的子页（爆炸图的 3D、芯片级镜头与规格库入口）。
READER_PAGES = ('/', '/industry.html', '/projects.html', '/project.html', '/market.html', '/index.html', '/node.html', '/ledger.html', '/bom.html', '/bom3d.html', '/rack3d.html',
                '/product-catalog.html', '/compute-catalog.html', '/report.html')
# 这些页面读的登记与生成物。目标表的行不含来源 URL（来源登记在 part_fetch.json，不公开）。
READER_DATA = ('/data/dashboard.json', '/data/dashboard_rules.json', '/data/tco_targets.json', '/data/tco_factors.json',
               '/data/datacenter_model.json', '/data/prices.json', '/data/companies.json',
               '/framework/bom.json', '/framework/site_rights.json', '/framework/indicators.json', '/framework/modules.json',
               '/framework/tco_factors.json', '/framework/tco_targets.json')
# 只读接口。写接口、任务板、供应台账、用户管理不在内。规格库每家登记公司一条（GET 只读；POST 接收端仍要机器凭证）。
READER_API = ('/api/industry', '/api/whoami', '/api/report', '/api/news', '/api/targets/backflow', '/api/model-assets',
              *('/api/product-catalog/' + company for company in COMPANIES))
# 外观、组件脚本、字体、模型资产与渲染图：公开页面离不开，且都是代码或登记过的资产。
READER_PREFIXES = ('/assets/', '/favicon')
READER_AUTH = ('/login', '/logout')
# 探针与爬虫协议：不 stat 任何运行文件，不带任何数据。/healthz 是 compose、Dockerfile 与 apps.json 三处探针的唯一目标。
READER_PROBE = ('/healthz', '/robots.txt')


def allowed(path):
    """path 已解码归一（见 http.Handler._norm_path）。只判断 GET/HEAD 可否匿名放行。"""
    path = urlsplit(path).path
    return (path in READER_PAGES or path in READER_DATA or path in READER_API or path in READER_AUTH or path in READER_PROBE
            or any(path.startswith(p) for p in READER_PREFIXES))


def public_model(spec):
    """账本的公开视图：只留基准预设与校准锚引用的预设，地区表只留这些预设用到的地区。

    其余键原样保留——输入、证据、口径与公式是模型的可信边界，本来就要公开；地区预设与情景预设
    是我们的研究工作，登录后才有。"""
    presets = spec.get('presets') or {}
    keep = {'baseline'} | {c.get('preset') for c in (spec.get('calibration') or {}).values() if c.get('preset') in presets}
    kept = {k: v for k, v in presets.items() if k in keep}
    sites = {spec.get('assumptions', {}).get('site')} | {(p.get('changes') or {}).get('site') for p in kept.values()}
    regions = {k: v for k, v in (spec.get('regions') or {}).items() if k in sites}
    return {**spec, 'presets': kept, 'regions': regions, 'public_view': 'reader'}
