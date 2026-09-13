"""Shared synthetic L2 fixtures; no production ledger is used by test services."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from inresearch.workflow.deep_read import DeepRead
from inresearch.materials import triage
from inresearch.knowledge import fact_contract as FC


def make_app():
    temporary = tempfile.TemporaryDirectory(prefix='inresearch-l2-test-service-')
    base = Path(temporary.name)
    material = SimpleNamespace(**{k:v for k,v in vars(triage).items() if not k.startswith('__')})
    material.RESULTS = base/'l1.jsonl'
    material.load_inventory = lambda: []
    app = DeepRead(state=base, packet_dir=base/'packets', materials=material)
    app._test_temporary = temporary
    return app

METRICS = {
    'dc_construction_cost_per_sqm': {
        'metric_id': 'dc_construction_cost_per_sqm', 'unit': '元/㎡', 'module': 'M10',
        'caliber_dims': [
            {'id': 'stage', 'name': '造价阶段', 'values': ['招标控制价', '竣工结算价']},
            {'id': 'scope', 'name': '包含范围', 'values': ['土建本体', '施工总包']},
        ],
    },
    'free_form_metric': {
        'metric_id': 'free_form_metric', 'unit': 'MW', 'module': 'M04',
        'caliber_dims': [{'id': 'region', 'name': '地域'}],   # no enum: any text
    },
    'noted_metric': {
        'metric_id': 'noted_metric', 'name': '带警告的指标', 'unit': '亿美元', 'module': 'M10',
        'note': '**表头单位与实际数值不符**，照表头换算会错一百万倍。',
        'caliber_dims': [{'id': 'scope', 'name': '范围', 'values': ['甲', '乙']}],
    },
}

SHA = 'a' * 64

def fact(**over):
    base = {
        'fact_id': 'luan-ct-cost-gc-2022',
        'metric_id': 'dc_construction_cost_per_sqm',
        'entity': {'type': 'project', 'id': 'cn-ah-luan-ct', 'label': '六安 CT'},
        'value': 4406.0, 'unit': '元/㎡',
        'caliber': {'stage': '招标控制价', 'scope': '施工总包'},
        'as_of': '2022-01',
        'evidence': {'sha256': SHA, 'locator': '封面限价 79,483,818.90 元', 'grade': 'S2'},
        'depth': '精读', 'bound': 'point', 'corroboration': '已交叉验证',
    }
    base.update(over)
    return base

def other(**over):
    """A fact about a different site, so it is a different claim."""
    over.setdefault('entity', {'type': 'project', 'id': 'cn-gd-gz-dc', 'label': '广州'})
    over.setdefault('fact_id', 'gz-dc-cost-gc-2022')
    return fact(**over)

def problems(f, seen=None, claims=None):
    return FC.check_fact(f, METRICS, seen if seen is not None else set(), claims)

L1_ROW = {
    'sha256': 'd' * 64, 'rel': '报告/未命名表格.xlsx', 'suffix': '.xlsx',
    'status': 'ok', 'score': 9, 'score_status': 'scored', 'level': 'p',
    'category': 'M10', 'org': '未知', 'year': '未知', 'title': '机柜功率密度测算',
    'keep_original_name': False, 'size': 4096,
}

PROVENANCE_DEBT = 38

DANGLING_SOURCE_IDS = 27

def problems_for(f):
    """跑一遍校验，只看与 corroboration 有关的那部分。"""
    return [x for x in problems(f) if 'corroboration' in x]

KNOWN_DIM_NAMES = {'spec', 'sub_trade', 'option', 'bucket', 'scenario',
                   'tier', 'customer', 'region', 'measure', 'basis'}

FILLED_THIS_BATCH = frozenset((
    '6af0f6ef29ca', 'fb2fd593a96b', '79dcfab07590',
    'c887218bba8c', 'b2b357ea5a41', '21b8800b45b4', '5647700326f0',
    'a4ceb4989ff9', 'c6eac4df9d6f', '3d289012079d', 'd6ab0f6695c7',
    '668882d117c0', '836448f119cb', 'f93ec7230288', 'dce7db166f51',
    '4881b5e1ee08', '268ef629bbc5', '8b630833198b', 'af071d00d08f',
    '0223b5b69287', '1d9cb156e7fa', '6240a391fd12', 'e860f4415f38',
    '65767b0dfd12', '9bc7abd1f421',
    '0287d488eb08', '1f84210a930d', 'cbce461c8ad4', '2749a0c3ae47',
    'f29dcf1e1431',
    '678b422a1179', 'dbaef8d19b23', '793dd357eb7b', 'd22737f33f3e',
    '2f91e8fea8b5', 'e7a7f6d9e10d', '66f3c0cb1669', '550c2c739b1b',
))

