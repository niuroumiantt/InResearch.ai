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
# @ 只到月份曾造出一组假争议：JRC 综述转引的预测只知道年份，录入时只能统一取
# 综述本身的时点 2024-02，于是 McMaster 2018 年做的与 ITU 2020 年做的两个 2020E
# 被压成同一个 vintage、报成争议。转引材料给得出年份的比给不出月份的多，@YYYY 收。
AS_OF = re.compile(r'^\d{4}(-\d{4}|-\d{2}(-\d{2})?|-Q[1-4]E?|-H[12]E?)?(E|目标)?(@\d{4}(-\d{2})?)?$')

FACT_ID = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

# 断言者不明时的取值。**它与任何具名断言者相撞时按重复处理**（见 record）：
# 宁可拒一条真的，也不要让一个来源不明的数伪装成第二家的独立印证。
UNSTATED_ASSERTER = '未注明'

# 转载不是断言。同一原文的两次转载、两次 OCR、两个模型复述都不算独立来源
# （01_data_standards §60），所以 asserter 记的是**最初说这个数的那一家**，
# 不是我们从哪份文件读到它。花旗转述 IDC 的数，asserter 是 IDC。
ASSERTER_MAX = 40

# 冲突判定要忽略的口径维：它们记的是「这个数怎么来的」，不是「测的是什么」。
#
# 这不是新规则，是把 2026-08-17 那条已经写下的规则执行到底：metrics.json 开头
# 写着「口径维度只放『测的是什么』，不放『我们多信它』……放进 caliber 会制造假的
# 不可比」，而 basis（数值性质）恰恰是它点名的那一类，却在几乎每个指标里当着口径维。
#
# 代价已经出现：伯恩斯坦的 2022 年中国用电记「券商测算」113 TWh，信通院记「实测」
# 130 TWh，两条因 basis 不同而不在同一个键上，record 一声不响——**两家对同一年同一
# 件事差 15%，这正是最该被看见的那种分歧，却被一个「我们多信它」的维度藏住了。**
# 读表的一方只能手工声明了五组。
#
# **但不能按维度名一刀切**：basis 这个名字在菜单里是重载的。
# gas_turbine_backlog_years 的 basis 取值是「在手订单/年产能 vs 在手订单/年交付」
# ——那是分母，是测的是什么；*_lead_time 的「下单到发货 vs 下单到交付现场」、
# cowos_capacity_wpm 的「名义产能 vs 有效产出」也都是。把它们摘出去会造出真的
# 假冲突：5.00 与 6.54 本来就是一件事的两个口径，metrics.json 的文档里正是拿
# 这一对当例子。
#
# 所以由菜单逐维声明：口径维写 "nature": true 的才从「同一个问题」的键里摘出去。
# 默认不摘——漏报一个冲突可以后补，凭空造一个假冲突会让人去删真数据。


def nature_dims(metric: dict | None) -> tuple:
    """这个指标声明为「数值性质」而非「测的是什么」的那些口径维。"""
    if not metric:
        return ()
    return tuple(d['id'] for d in metric.get('caliber_dims', []) if d.get('nature'))


def _dims(fact: dict, exclude: tuple = ()) -> tuple:
    caliber = fact.get('caliber')
    if not isinstance(caliber, dict):
        return ()
    return tuple(sorted((k, str(v)) for k, v in caliber.items() if k not in exclude))


def claim_identity(fact: dict, metric: dict | None = None) -> tuple:
    """What the record is *about*: metric, entity, date, caliber, bound.

    Deliberately without the asserter.  Two houses giving different numbers for
    one thing are two records about one question - that shared question is this
    key, and it is what makes a conflict findable at all.

    Without the metric's 数值性质 dims either, for the same reason one step
    further: a conflict that hides behind 「券商测算 vs 实测」 is still a
    conflict.  Pass the metric to get that; without it nothing is dropped,
    which is the old behaviour and the safe direction.  Dedup (claim_key)
    keeps every dim regardless, so the two records still coexist - what
    changes is that the machine now says they are about one question.
    """
    return ('about', fact.get('metric_id'), (fact.get('entity') or {}).get('id'),
            str(fact.get('as_of') or ''), _dims(fact, nature_dims(metric)),
            fact.get('bound') or 'point')


def asserter_of(fact: dict) -> str:
    """Who says so, normalised to a short name.  '未注明' when unrecoverable."""
    return str(fact.get('asserter') or '').strip() or UNSTATED_ASSERTER


def claim_key(fact: dict) -> tuple:
    """What makes two records the same claim: who asserts what about which thing.

    **The asserter belongs in the key.** 工信部 says 2021 用电 94 TWh and 信通院
    says 111.6 TWh: same metric, same year, same caliber, two houses.  Keyed
    without the asserter the second one is refused as a duplicate and the
    disagreement never enters the store - which is exactly backwards: a
    disagreement between two independent houses is one of the most valuable
    things a fact layer can hold.  §60 of 01_data_standards says to keep both
    sides with their originals and mark the dispute; this key is what lets it.

    Keyed *with* the asserter, the file a number arrived in stops mattering -
    and it should stop mattering.  绿色数据中心白皮书 quotes both 416.2 TWh and
    ICTresearch's 1,103 TWh from one PDF with one sha256; IDC revises its own
    2016 figure across five editions with five different sha256.  Judging
    conflict by file identity gets both cases wrong in opposite directions.
    Who asserts a number is not where you found it.

    A revision is not a conflict: same asserter, same year, a later edition.
    That is carried by as_of's @vintage (2016@2021-03) plus `supersedes`, which
    keeps the earlier value readable instead of overwriting it.

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
    return ('claim', fact.get('metric_id'), (fact.get('entity') or {}).get('id'),
            str(fact.get('as_of') or ''), _dims(fact), fact.get('bound') or 'point',
            asserter_of(fact))


def revision_key(fact: dict) -> tuple:
    """One asserter's series for one year, with the edition stripped off.

    IDC's 2016 installed-bytes figure appears in the 2018, 2019, 2020, 2021 and
    2023 editions with different values.  They are one series revised, not five
    claims, so they share this key and each later one must name what it
    supersedes.
    """
    as_of = str(fact.get('as_of') or '')
    return ('revision', fact.get('metric_id'), (fact.get('entity') or {}).get('id'),
            as_of.split('@')[0], _dims(fact), fact.get('bound') or 'point',
            asserter_of(fact))


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
    return ('forecast', fact.get('metric_id'), (fact.get('entity') or {}).get('id'),
            as_of.split('@')[0], _dims(fact), fact.get('bound') or 'point',
            asserter_of(fact))

def index_claims(records: list[dict], metrics: dict | None = None) -> dict:
    """claim/forecast/revision key -> the fact_id already holding it.

    claim_identity maps to a *list*: that is the one key several records are
    allowed to share, and the conflict check needs all of them, not the last.
    """
    claims = {}
    for fact in records:
        index_claim(claims, fact, (metrics or {}).get(fact.get('metric_id')))
    return claims


def index_claim(claims: dict, fact: dict, metric: dict | None = None) -> None:
    """Add a validated record to every identity used by batch and stored checks.

    metric 只影响「同一个问题」那一把键（它要摘掉声明为数值性质的维）；
    去重、修订、预测三把键始终用完整口径，与菜单声明无关。
    """
    claims[claim_key(fact)] = fact.get('fact_id')
    claims.setdefault(revision_key(fact), fact.get('fact_id'))
    key = forecast_key(fact)
    if key is not None:
        claims.setdefault(key, fact.get('fact_id'))
    claims.setdefault(claim_identity(fact, metric), []).append(fact.get('fact_id'))


def same_submission(stored: dict | None, incoming: dict) -> bool:
    """Generated reverse links may grow after the original request committed."""
    return stored is not None and stored == {**incoming, **(
        {'disputed_by': stored['disputed_by']}
        if 'disputed_by' in stored and 'disputed_by' not in incoming else {})}



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

    asserter = str(fact.get('asserter') or '').strip()
    if not asserter:
        bad.append('缺 asserter——最初说这个数的那一家（IDC / 信通院 / 工信部 / IEA）；'
                   '转述者不算断言者，花旗转述 IDC 的数 asserter 写 IDC；'
                   '全文确实查不到就写「%s」' % UNSTATED_ASSERTER)
    elif len(asserter) > ASSERTER_MAX:
        bad.append('asserter 要短到能当键用（≤%d 字）：报告名、期号、发布日期写进 '
                   'evidence.originator，这里只要机构名' % ASSERTER_MAX)
    elif asserter in PLACEHOLDER_VALUES:
        bad.append('asserter = %r 是占位词不是机构名' % asserter)

    if fact.get('bound') is not None and fact['bound'] not in BOUNDS:
        bad.append('bound 必须是 %s' % ' / '.join(BOUNDS))
    if fact.get('corroboration') is not None and fact['corroboration'] not in CORROBORATION:
        bad.append('corroboration 必须是 %s' % ' / '.join(CORROBORATION))
    if fact.get('derived'):
        if not str(fact.get('notes') or fact.get('derivation') or '').strip():
            bad.append('derived 为真时必须在 notes 里写清算法与被减项（兼容历史 derivation）')
    # **derived 说的是「值是算出来的」，不是「这条里有什么东西是我们推断的」。**
    # 2026-09-13 的 C3 A 档复审发现 46 条把 derived 置 true 只为了说明 as_of 是
    # 推断的（联通企标 34 条 + 华为永州 12 条里的 7 条），而值全是照抄原表。
    # 代价有两层：一是把照抄的数说成计算值，二是对外视图按「派生值不单独对外」
    # 把它们剔掉了——挡住了，但挡的理由是假的，真正该挡它们的是分发限制。
    # 时点是推断的，就用这一维说，不要借别的字段。
    if fact.get('as_of_inferred'):
        if not str(fact.get('notes') or '').strip():
            bad.append('as_of_inferred 为真时必须在 notes 里写清推断依据'
                       '（凭哪条引用、哪个利率、哪份规范版本定的年份）')
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
        bad.extend(_collision_problems(fact, claims))
    return bad


def _collision_problems(fact: dict, claims: dict) -> list[str]:
    """Three different things look alike here, and only one is an error.

    Same asserter, same everything: a duplicate.
    Same asserter, a later edition: a revision - keep both, name what it
      supersedes, and put the edition in as_of's @vintage.
    Different asserters: a conflict - keep both sides, cross-link them, and it
      goes to C3 A 档 for the owner.  §60 forbids letting the higher grade or
      the later date silently overwrite.
    """
    bad = []
    as_of = str(fact.get('as_of') or '')
    forecast = forecast_key(fact)
    if forecast is not None and '@' not in as_of:
        prior = claims.get(forecast)
        if prior:
            return ['同一年份的预测已有一条 %s——若是同一个数，属重复录入；'
                    '若是不同时点做出的两次预测，两条都要写成 2025E@2024-04 '
                    '的形式带上做出时点，否则它们会被平均到一起。'
                    '同一家自己的再预测不构成交叉验证。' % prior]

    twin = claims.get(claim_key(fact))
    if twin:
        return ['同一断言者、同口径同时点同 bound 已有一条 %s——要么是重复录入，'
                '要么少了一个把两者区分开的口径维度；'
                '若这两个数是一个区间的两端，把它们写成 '
                'bound: upper 与 bound: lower 两条' % twin]

    # 同一家的另一版：as_of 带 @ 才算修订，且必须指明替代了谁。
    #
    # 只对实绩要求 supersedes，不对预测要求：同一家在两个时点对 2025 年做的
    # 两次预测是两个都还活着的判断（看法怎么变，本身就是要读的东西），而同一
    # 家对 2016 年实际值改口，后一版是要替代前一版的。两者都用 @ 记版本，但
    # 一个是并列，一个是接替。
    if '@' in as_of and forecast is None:
        prior = claims.get(revision_key(fact))
        if prior and prior != fact.get('supersedes'):
            bad.append('同一断言者对 %s 已有一条 %s——这是修订而不是争议：'
                       'supersedes 写 %s，旧版留在库里不覆盖'
                       % (as_of.split('@')[0], prior, prior))

    # 别人家的同一个问题：并列，但必须互相指认。
    others = [fid for fid in (claims.get(claim_identity(fact)) or [])
              if fid != fact.get('fact_id')]
    if others:
        named = asserter_of(fact) != UNSTATED_ASSERTER
        declared = set(fact.get('disputes') or [])
        undeclared = [fid for fid in others if fid not in declared]
        if undeclared and not named:
            bad.append('同一问题下已有 %s，而这一条的 asserter 是「%s」——'
                       '来源不明的数与具名来源的数并列，等于给它一个它没有的'
                       '独立印证地位。先把断言者查出来，或确认它就是那一家的转述'
                       '（这种情况不新增事实，corroboration 记「同源转述」）'
                       % ('、'.join(undeclared), UNSTATED_ASSERTER))
        elif undeclared:
            bad.append('同一问题下已有 %s（不同断言者）——按 01_data_standards §60，'
                       '两边都要留下并标明争议：把 disputes 写成 [%s]。'
                       '不要因为来源等级或发布日期更晚就覆盖对方。'
                       % ('、'.join(undeclared),
                          ', '.join('"%s"' % fid for fid in undeclared)))
    return bad


def cross_link_disputes(accepted: list[dict], stored: list[dict]) -> list[dict]:
    """Write the reverse link on the other side, and report each pair once.

    A dispute declared in one direction only is half recorded: whoever reads
    the older fact would never learn it is contested.  record writes
    disputed_by rather than asking the reader to edit two records by hand -
    the same reason supersedes does not overwrite the old edition.
    """
    by_id = {f.get('fact_id'): f for f in list(stored) + list(accepted)}
    pairs = []
    for fact in accepted:
        others = [by_id.get(fid) for fid in (fact.get('disputes') or [])]
        others = [o for o in others if o]
        if not others:
            continue
        for other in others:
            back = other.setdefault('disputed_by', [])
            if fact['fact_id'] not in back:
                back.append(fact['fact_id'])
        sides = [side_summary(f) for f in [fact] + others]
        spread = value_spread([fact] + others)
        pairs.append({'about': '%s / %s / %s' % (
            fact.get('metric_id'), (fact.get('entity') or {}).get('id') or '—',
            fact.get('as_of')),
            'spread': spread,
            'kind': dispute_kind(spread),
            'needs_owner': dispute_kind(spread) == ORDER_OF_MAGNITUDE,
            'sides': sides})
    return pairs


# 一份文献综述收录的十几个估计，两两连起来是几十对「争议」，而它们说的是一件事：
# 这个量的公开估计分布在某个范围里。把每一对都送进 A 档，A 档就被噪音淹掉——
# 而淹掉 A 档比没有 A 档更糟，因为它让真正需要人判断的那几条排在第二十位。
#
# 分界线用极差（最大/最小），因为它对「几个模型算出的离散」与「有人错了一个数量级」
# 的区分最直接，而且是可复核的：
#   ≤ 2 倍  → 方法离散。JRC 2024 综述里全球 2020 年八家给 196-380 TWh 就是这样，
#            自底向上模型对边界与机柜利用率的假设不同，差一倍是常态，不是分歧。
#   > 2 倍  → 量级分歧。同一份白皮书两页给 416.2 与 1,103（2.65 倍）、
#            法国同年 5.2 与 11.6（2.23 倍）——这种必有一方口径不同或算错，要人看。
# 界限不是真理，是分诊：所有链接照样留在库里，标记只决定谁进 A 档的队列。
METHOD_DISPERSION = '方法离散'
ORDER_OF_MAGNITUDE = '量级分歧'
SPREAD_ESCALATION = 2.0


def value_spread(facts: list[dict]) -> float | None:
    """最大值 / 最小值；有一侧未披露或为零就给不出，返回 None。"""
    values = []
    for f in facts:
        v = f.get('value')
        if v is None and f.get('value_range'):
            values.extend(f['value_range'])
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            values.append(v)
    values = [abs(v) for v in values if v]
    if len(values) < 2:
        return None
    return round(max(values) / min(values), 3)


def dispute_kind(spread: float | None) -> str:
    # 给不出极差的（有一侧未披露）按需要人看处理：看不见的差距不能假定它小。
    if spread is None or spread > SPREAD_ESCALATION:
        return ORDER_OF_MAGNITUDE
    return METHOD_DISPERSION


def side_summary(fact: dict) -> dict:
    value = fact.get('value')
    if value is None and fact.get('value_range'):
        value = '%s-%s' % tuple(fact['value_range'])
    return {'fact_id': fact.get('fact_id'), 'asserter': asserter_of(fact),
            'value': '未披露' if value is None else value,
            'unit': fact.get('unit') or '',
            'locator': (fact.get('evidence') or {}).get('locator') or ''}
