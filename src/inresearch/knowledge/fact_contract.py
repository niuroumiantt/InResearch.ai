"""Fact acceptance rules; no machine paths, model calls or writes."""
from __future__ import annotations
import re, math


GRADES = ('S1', 'S2', 'S3', 'S4', 'S5')

DEPTHS = ('精读', '据实生成')          # 半自动 and 目录级 never reach the fact layer

BOUNDS = ('point', 'upper', 'lower')

CORROBORATION = ('待交叉验证', '已交叉验证', '孤证已知', '同源转述')

PLACEHOLDER_VALUES = frozenset(
    ('见 notes', '见notes', '见备注', '同上', '未填', '待补', '略', '-', '—', 'N/A', 'n/a'))

# 半年与季度并列，因为渠道纪要按半年给数：寒武纪 2025 上半年已交付 4 万片、
# 下半年预计约 7 万片。拆成两个季度是我们替原文做的拆分，原文没这个拆分。
AS_OF = re.compile(r'^\d{4}(-\d{4}|-\d{2}(-\d{2})?|-Q[1-4]E?|-H[12]E?)?(E|目标)?(@\d{4}-\d{2})?$')

FACT_ID = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

def claim_key(fact: dict) -> tuple:
    """What makes two records the same claim: metric, entity, date, caliber.

    Caliber belongs in the key because it is the thing that makes two numbers
    different rather than contradictory.  The store already holds 4406 元/㎡
    and 3736.6 元/㎡ for one project in one month - 施工总包 against 土建本体 -
    and 5.00 against 6.54 backlog years in one quarter, one over capacity and
    one over deliveries.  Keyed without caliber those read as duplicates; keyed
    with it they are what they are, two calibers of one thing.

    bound belongs in the key for the same reason.  「1800-2100 万只」 is two
    records about one metric at one date in one caliber - an upper and a lower.
    Keyed without bound the second one is refused as a duplicate, the range
    collapses to whichever end was recorded first, and the other end survives
    only as prose in notes.  Ranges are the normal shape of an expert call, not
    an edge case.
    """
    caliber = fact.get('caliber')
    dims = (tuple(sorted((k, str(v)) for k, v in caliber.items()))
            if isinstance(caliber, dict) else ())
    return ('claim', fact.get('metric_id'), (fact.get('entity') or {}).get('id'),
            str(fact.get('as_of') or ''), dims, fact.get('bound') or 'point')

def forecast_key(fact: dict) -> tuple | None:
    """The same claim with the vintage stripped off - forecasts only.

    Two forecasts of one year made a year apart are two claims about the same
    future, not one claim recorded twice.  Stored as a bare 2025E they collide,
    and whoever reads them later sees one metric carrying two values and
    averages them.  The vintage is the only thing that separates them, which is
    why a forecast that collides without one is refused.
    """
    as_of = str(fact.get('as_of') or '')
    if 'E' not in as_of:
        return None
    _, metric, entity, _, dims, bound = claim_key(fact)
    return ('forecast', metric, entity, as_of.split('@')[0], dims, bound)

def index_claims(records: list[dict]) -> dict:
    """claim/forecast key -> the fact_id already holding it."""
    claims = {}
    for f in records:
        claims[claim_key(f)] = f.get('fact_id')
        key = forecast_key(f)
        if key is not None:
            claims.setdefault(key, f.get('fact_id'))
    return claims

def check_fact(fact: dict, metrics: dict, seen: set, claims: dict | None = None) -> list[str]:
    bad = []
    fid = fact.get('fact_id')
    if not fid or not FACT_ID.match(str(fid)):
        bad.append('fact_id 缺失或不是小写连字符：%r' % fid)
    elif fid in seen:
        bad.append('fact_id 重复：%s' % fid)

    metric = metrics.get(fact.get('metric_id'))
    if metric is None:
        bad.append('metric_id 不在 metrics.json 里：%r' % fact.get('metric_id'))
    else:
        if fact.get('unit') != metric.get('unit'):
            bad.append('unit 与指标声明不符：%r ≠ %r' % (fact.get('unit'), metric.get('unit')))
        caliber = fact.get('caliber')
        if not isinstance(caliber, dict):
            bad.append('caliber 必须是对象')
        else:
            for dim in metric.get('caliber_dims', []):
                got = caliber.get(dim['id'])
                if got is None:
                    bad.append('caliber 缺 %s（%s）——缺一维即无法比较' % (dim['id'], dim.get('name', '')))
                elif dim.get('free_text'):
                    # 有些口径维本来就是开放的：设备规格、调查选项、清单分项名。
                    # 拿一个占位值糊过去比不填更糟——两台不同规格的 UPS 会撞成
                    # 同一个 claim_key，后录的那台被当成重复直接拒掉。
                    text = str(got).strip()
                    if not text:
                        bad.append('caliber.%s 是自由文本维，不能留空' % dim['id'])
                    elif text in PLACEHOLDER_VALUES:
                        bad.append('caliber.%s = %r 是占位词不是取值——'
                                   '自由文本维要填原文的那一串（规格、选项、分项名），'
                                   '它是把两条数区分开的东西' % (dim['id'], got))
                elif dim.get('values') and got not in dim['values']:
                    bad.append('caliber.%s = %r 不在允许取值内：%s' % (
                        dim['id'], got, ' / '.join(dim['values'])))
            for extra in set(caliber) - {d['id'] for d in metric.get('caliber_dims', [])}:
                bad.append('caliber 多出未声明的维度：%s' % extra)

    value = fact.get('value', ...)
    if value is ...:
        bad.append('缺 value（未披露请显式写 null，不要省略）')
    elif value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        bad.append('value 必须是数字或 null：%r' % value)

    if not AS_OF.match(str(fact.get('as_of', ''))):
        bad.append('as_of 必须是 YYYY / YYYY-MM / YYYY-MM-DD / YYYY-Q1 / YYYY-H1'
                   '（可带 E 或 目标，可带 @快照）：%r' % fact.get('as_of'))

    if fact.get('depth') not in DEPTHS:
        bad.append('depth 只收 %s，半自动与目录级不进事实层' % ' / '.join(DEPTHS))

    ev = fact.get('evidence')
    if not isinstance(ev, dict):
        bad.append('缺 evidence')
    else:
        if ev.get('grade') not in GRADES:
            bad.append('evidence.grade 必须是 %s' % ' / '.join(GRADES))
        if not str(ev.get('locator') or '').strip():
            bad.append('evidence.locator 不能为空——它是别人翻回去核对的唯一依据')
        sha = str(ev.get('sha256') or '')
        if not re.fullmatch(r'[0-9a-f]{64}', sha):
            bad.append('evidence.sha256 必须是 64 位十六进制——路径会变，内容不会')

    if fact.get('bound') is not None and fact['bound'] not in BOUNDS:
        bad.append('bound 必须是 %s' % ' / '.join(BOUNDS))
    if fact.get('corroboration') is not None and fact['corroboration'] not in CORROBORATION:
        bad.append('corroboration 必须是 %s' % ' / '.join(CORROBORATION))
    if fact.get('derived'):
        if not str(fact.get('notes') or fact.get('derivation') or '').strip():
            bad.append('derived 为真时必须在 notes 里写清算法与被减项（兼容历史 derivation）')
    value_range = fact.get('value_range')
    if value_range is not None:
        if value is not None:
            bad.append('value 与 value_range 只能填一个')
        if not (isinstance(value_range, list) and len(value_range) == 2
                and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                        and math.isfinite(v) for v in value_range)
                and value_range[0] < value_range[1]):
            bad.append('value_range 必须是有限数字 [下界, 上界] 且下界小于上界')
    elif value is None and not str(fact.get('notes') or '').strip():
        bad.append('value 为 null 时必须在 notes 说明为何留白')

    if claims is not None:
        key = forecast_key(fact)
        if key is not None and '@' not in str(fact.get('as_of') or ''):
            prior = claims.get(key)
            if prior:
                bad.append('同一年份的预测已有一条 %s——若是同一个数，属重复录入；'
                           '若是不同时点做出的两次预测，两条都要写成 2025E@2024-04 '
                           '的形式带上做出时点，否则它们会被平均到一起。'
                           '同一家自己的再预测不构成交叉验证。' % prior)
        else:
            prior = claims.get(claim_key(fact))
            if prior:
                bad.append('同口径同时点同 bound 已有一条 %s——要么是重复录入，'
                           '要么少了一个把两者区分开的口径维度；'
                           '若这两个数是一个区间的两端，把它们写成 '
                           'bound: upper 与 bound: lower 两条' % prior)
    return bad
