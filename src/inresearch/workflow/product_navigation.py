"""Versioned browsing projection; never rewrites vendor category evidence.

NVIDIA uses a reviewed display mapping (``classify``).  Other companies are
browsed by the vendor's own product path as delivered (``classify_taxonomy``);
that path is evidence, so it is projected as-is and never re-labelled here.
"""
import re
from urllib.parse import urlsplit

VERSION = '2026-09-28.1'
SOURCE = 'https://www.nvidia.com/en-us/products/'
GROUPS = [
    {'id': 'datacenter', 'label': '数据中心与网络', 'official_sections': ['Data Center', 'Networking', 'Graphics Cards, GPUs, and CPUs']},
    {'id': 'consumer', 'label': '游戏与消费产品', 'official_sections': ['Gaming and Creating', 'Laptops']},
    {'id': 'professional', 'label': '专业图形与工作站', 'official_sections': ['Professional Workstations', 'Graphics Cards, GPUs, and CPUs', 'Laptops']},
    {'id': 'embedded', 'label': '嵌入式与汽车', 'official_sections': ['Embedded Systems']},
    {'id': 'software', 'label': '软件与云服务', 'official_sections': ['Software', 'Cloud Services', 'Apps and Tools']},
]
# Ordered identity/path rules resolve cross-links without inheriting every parent
# category. Labels are navigation families, not inferred vendor SKU identities.
RULES = [
    ('embedded', 'jetson', 'Jetson', r'jetson|/embedded-systems/'),
    ('embedded', 'igx', 'IGX', r'\bigx\b|/igx/'),
    ('embedded', 'drive', 'DRIVE / 汽车计算', r'drive agx|autonomous-vehicles/|clara agx'),
    ('embedded', 'embedded-rtx', 'RTX Embedded', r'rtx-embedded/'),
    ('embedded', 'holoscan', 'Holoscan', r'holoscan'),
    ('software', 'network-software', '网络软件与工具', r'cumulus|netq|sonic|\bufm\b|doca|networking software|networking/.*(?:software|configurat|configurator|/air/)'),
    ('software', 'cloud', '云服务', r'dgx.cloud|gpu-cloud|\bngc\b|geforce.now|cloud-xr|cloud computing'),
    ('software', 'enterprise', '企业软件与管理', r'ai.enterprise|mission.control|base.command|virtual.(?:pc|gpu|workstation|solutions)|enterprise.software|dgx.ready|dgx.support|magnum.io|mlops'),
    ('software', 'ai-tools', 'AI / 开发平台', r'\bnemo\b|omniverse|workbench|metropolis|/software/$'),
    ('software', 'creative-tools', '应用与创作工具', r'/software/|broadcast|rtx.remix|studio|game.ready.drivers'),
    ('professional', 'dgx-personal', 'DGX 个人工作站', r'dgx.(?:spark|station)'),
    ('professional', 'rtx-laptops', 'RTX 专业笔记本', r'professional-laptops/'),
    ('professional', 'rtx-pro', 'RTX PRO / 专业显卡', r'/products/workstations/'),
    ('consumer', 'geforce-laptops', 'GeForce 笔记本', r'/geforce/laptops/'),
    ('consumer', 'geforce-50', 'GeForce RTX 50 系列', r'/50-series/|geforce rtx 50\d\d'),
    ('consumer', 'geforce-40', 'GeForce RTX 40 系列', r'/40-series/|geforce rtx 40\d\d'),
    ('consumer', 'geforce-legacy', 'GeForce 历代与总览', r'/geforce/(?:graphics-cards|20-series)/'),
    ('consumer', 'shield', 'SHIELD', r'/shield/'),
    ('consumer', 'gsync', 'G-SYNC', r'g-sync'),
    ('datacenter', 'networking', '网络 / DPU / 互连', r'/networking/|networking-docs\.nvidia\.com|nvlink|nvqlink|connectx|bluefield|spectrum|supernic|infiniband|ethernet switching|\bsn\d{4}\b'),
    ('datacenter', 'dgx', 'DGX 系统', r'\bdgx\b'),
    ('datacenter', 'platforms', 'HGX / MGX / 系统平台', r'\b(?:hgx|mgx|ovx|dsx|stx)\b|rtx.pro.server|certified.systems|ai-storage'),
    ('datacenter', 'accelerators', 'GPU / CPU / 超级芯片', r'/data-center/'),
]
AUXILIARY = re.compile(
    r'/(?:learn|startups|sustainability|lp|resources|technologies)/|'
    r'/(?:get-started|activate-license|get-dgx|rewards|software-update|'
    r'product-literature|colocation-partners|equinix-private-ai-with-dgx|'
    r'help-me-choose|stem-majors|virtualization/resources)/|'
    r'/solutions/(?:ai|mlops|confidential-computing)/|/max-q-technologies/|'
    r'/data-center/(?:products/)?$|/networking/(?:products/)?$|'
    r'/(?:buy-desktop|buy-gpu|features|performance|product-images|videos|reviews|specifications|compare)(?:/|$)|'
    r'/(?:tensor-cores|ai-cloud-validation)/', re.I)
PRODUCT_DOCUMENT_HOSTS = {'networking-docs.nvidia.com'}


def classify(product):
    # Components reference their parent product page; no source snapshot changes.
    path = urlsplit(product.get('product_url') or product['source_url']).path.lower()
    text = product['name'].lower() + ' ' + path
    matched = next((r for r in RULES if re.search(r[3], text)), None)
    # Holoscan is itself a product under /technologies/, unlike architecture pages.
    host = (urlsplit(product.get('product_url') or product['source_url']).hostname or '').lower()
    auxiliary = (bool(AUXILIARY.search(path)) and 'holoscan-sensor-bridge' not in path
                 and host not in PRODUCT_DOCUMENT_HOSTS)
    role = 'auxiliary' if auxiliary else ('catalog' if matched else 'unclassified')
    return {'version': VERSION, 'group': matched[0] if matched else '',
            'family': matched[1] if matched else '', 'family_label': matched[2] if matched else '待归类',
            'role': role, 'basis': 'name_and_official_product_path',
            'status': 'display_mapping_not_vendor_taxonomy', 'official_source': SOURCE}


TAXONOMY_VERSION = '2026-10-01.1'


def taxonomy_path(product):
    """The vendor's own product path, keeping only well-formed {slug, name} steps."""
    path = product.get('taxonomy') or []
    return [step for step in path if isinstance(step, dict) and step.get('slug')] if isinstance(path, list) else []


def classify_taxonomy(product, official_source=''):
    """Navigation from the vendor's own product path (same shape as ``classify``)."""
    path = taxonomy_path(product)
    if not path:
        return {'version': TAXONOMY_VERSION, 'group': '', 'family': '', 'family_label': '待归类',
                'role': 'unclassified', 'basis': 'vendor_product_path', 'status': 'vendor_taxonomy',
                'official_source': official_source}
    family = path[1] if len(path) > 1 else None
    return {'version': TAXONOMY_VERSION, 'group': str(path[0]['slug']),
            'family': str(family['slug']) if family else '',
            'family_label': str((family or path[0]).get('name') or (family or path[0])['slug']),
            'role': 'auxiliary' if product.get('listing') == 'directory' else 'catalog',
            'basis': 'vendor_product_path', 'status': 'vendor_taxonomy', 'official_source': official_source}


def taxonomy_groups(products):
    """Top-level groups present in the delivered data (id=slug, label=vendor name)."""
    groups = {}
    for product in products:
        path = taxonomy_path(product)
        if path:
            groups.setdefault(str(path[0]['slug']), str(path[0].get('name') or path[0]['slug']))
    return [{'id': slug, 'label': label} for slug, label in sorted(groups.items(), key=lambda item: item[1].casefold())]


def matches(product, group='', family='', scope='all', classifier=None):
    nav = (classifier or classify)(product)
    return ((not group or nav['group'] == group) and (not family or nav['family'] == family)
            and (scope == 'all' or (nav['role'] == 'catalog' if scope == 'catalog' else nav['role'] != 'catalog')))
