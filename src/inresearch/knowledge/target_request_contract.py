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


def attach_contracts(targets, questions, review=None, providers=None):
    review = review or {}
    providers = providers or {}
    definitions = {r['model_input']: r for r in review.get('requirements', [])}
    if len(definitions) != len(review.get('requirements', [])):
        raise ValueError('Duplicate parameter demand definition')
    covered = {key for row in targets for key in row.get('feeds_primary', [])}
    if set(definitions) - covered:
        raise ValueError('Parameter demand lacks a primary target')
    for definition in definitions.values():
        fields = definition['scope_fields']
        if not fields or len(fields) != len(set(fields)) or not definition['question_ids']:
            raise ValueError('Parameter demand requires distinct scope fields and reviewed questions')
    question_by_id = {q['id']: q for q in questions}
    by_cell = {}
    for question in questions:
        by_cell.setdefault((question.get('node'), question.get('variable_class')), []).append(question['id'])
    for row in targets:
        profile = ('event_lead' if row['team'] == 'inews' else
                   'vendor_operation' if row['team'] == 'fetchspec' and row['id'].endswith('.operation') else
                   'vendor_spec' if row['team'] == 'fetchspec' else
                   'observation' if row['data_class'] == 'observation' else 'research_material')
        node = target_node(row)
        candidates = sorted(by_cell.get((node, row['variable_class']), []))
        rule = review.get('question_link_rules', {}).get(row['id'].rsplit('.', 1)[-1], {})
        links = [{'question_id': q['id'], 'relation': rule['relation'], 'reason': rule['reason']}
                 for q in questions if q.get('node') == node and node != 'root'
                 and any(q['id'].endswith('-' + suffix) for suffix in rule.get('suffixes', []))]
        requirements = []
        for key in row.get('feeds_primary', []):
            if key not in definitions:
                continue
            definition = definitions[key]
            if any(qid not in question_by_id for qid in definition['question_ids']):
                raise ValueError(f'{key}: unregistered reviewed question')
            team = definition['source_team']
            if team not in providers:
                raise ValueError(f'{key}: unregistered source team {team}')
            mechanism = {'fetchstat': 'pdf_free', 'fetchfilings': 'edgar',
                         'fetchreports': 'pdf_free', 'fetchquotes': 'js_page'}[team]
            requirements.append(dict(definition, id=row['id'] + '::' + key,
                profile='observation' if team in ('fetchstat', 'fetchquotes') else 'research_material',
                required_fields=COMMON + ['requirement_id', 'source_sha256', 'locator', 'scope', 'native_value', 'unit', 'conditions', 'derivation'],
                host='macmini' if mechanism == 'js_page' else providers[team].get('host_default', 'aws'),
                mechanism=mechanism,
                team_state='not_connected' if providers[team].get('connection') == 'not_connected' else 'connected',
                evidence_status='unverified'))
            links.extend({'question_id': qid, 'relation': 'supports',
                          'reason': definition['acceptance'], 'requirement_id': row['id'] + '::' + key}
                         for qid in definition['question_ids'])
        row['request'] = {'version': 2, 'profile': profile, 'node': node,
            'candidate_question_ids': candidates, 'question_ids': sorted({x['question_id'] for x in links}),
            'question_links': links, 'requirements': requirements,
            'requirement_required': bool(requirements), 'scope_required': True,
            'mapping_review': {'owner': 'research', 'review_version': review.get('version'),
                'reviewed_at': review.get('reviewed_at'),
                'disposition': 'reviewed_support_links' if links else 'question_not_registered' if not any(q.get('node') == node for q in questions) else 'purpose_review_required',
                'reason': '支持材料或线索的用途已登记；不表示回答、采用或闭题。' if links else '尚无经审核的用途关联；保留缺口，研究端审定问题和用途后再派工。'}}


def resolve_request(target, requirement_id=None):
    """Resolve dispatch authority, never infer it from same-cell retrieval."""
    request = target.get('request', {})
    requirements = request.get('requirements', [])
    if requirements:
        selected = next((r for r in requirements if r['id'] == requirement_id), None)
        if selected is None:
            raise ValueError('该目标包含参数级需求，请选择现行 requirement_id；不能整包按旧主责队派工')
        return selected
    if requirement_id:
        raise ValueError('参数级需求不属于所选目标行')
    return {'source_team': target['team'], 'host': target['host'],
            'team_state': target.get('team_state'), 'question_ids': request.get('question_ids', []),
            'scope_fields': []}
