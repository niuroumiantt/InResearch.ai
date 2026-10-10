"""Versioned requests derived from target identities; no collection or adoption."""

COMMON = ['target_id', 'source_url', 'publisher', 'observed_at', 'access_scope', 'missing_fields']
PROFILES = {
    'vendor_spec': {'fields': COMMON + ['product_id', 'configuration', 'source_sha256', 'locator', 'native_parameter', 'value', 'unit', 'condition'],
        'acceptance': '原厂型号与配置可定位；原文参数、单位、脚注与条件保留。没有规格的目录条目只交身份与缺口。',
        'does_not_prove': '在售状态、现场安装、运行实耗、正式研究采用'},
    'vendor_operation': {'fields': COMMON + ['product_id', 'configuration', 'source_sha256', 'locator', 'rated_or_tested', 'value', 'unit', 'test_condition'],
        'acceptance': '区分额定、峰值与测试值；效率曲线保留负载点，可靠性保留测试口径。',
        'does_not_prove': '设施 PUE 贡献、现场利用率、真实项目寿命'},
    'event_lead': {'fields': COMMON + ['event_id', 'event_date', 'object_ids', 'origin_pointer'],
        'acceptance': '可追溯事件线索；发布时间与事件时间分开，转载与最初断言者分开。',
        'does_not_prove': '原件已归档、事实已核验、项目容量增加或研究采用'},
    'observation': {'fields': COMMON + ['source_sha256', 'locator', 'metric', 'entity', 'value', 'unit', 'as_of', 'caliber', 'conditions'],
        'acceptance': '价格区分挂牌/报价/成交；交期区分起止点；统计保留分母、范围与修订版本。',
        'does_not_prove': '适用于所有地区/型号/时点或可直接替代模型假设'},
    'research_material': {'fields': COMMON + ['source_sha256', 'locator', 'subject', 'period', 'coverage'],
        'acceptance': '交付原件与来源范围；定向提取和全文阅读分别声明覆盖，冲突及未披露保留。',
        'does_not_prove': '完成全文、独立来源印证、C3 采用或正式答案'},
}


def target_node(row):
    if row.get('part_id'):
        return 'part:' + row['part_id']
    if row.get('site_right_id'):
        return 'site:' + row['site_right_id']
    return 'root'


def attach_contracts(targets, questions):
    by_cell = {}
    for question in questions:
        by_cell.setdefault((question.get('node'), question.get('variable_class')), []).append(question['id'])
    for row in targets:
        profile = ('event_lead' if row['team'] == 'inews' else
                   'vendor_operation' if row['team'] == 'fetchspec' and row['id'].endswith('.operation') else
                   'vendor_spec' if row['team'] == 'fetchspec' else
                   'observation' if row['data_class'] == 'observation' else 'research_material')
        row['request'] = {'version': 1, 'profile': profile, 'node': target_node(row),
                          'question_ids': sorted(by_cell.get((target_node(row), row['variable_class']), [])),
                          'scope_required': True}
