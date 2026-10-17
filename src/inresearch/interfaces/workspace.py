"""Role-filtered navigation and small views over the existing authoritative stores.

These projections never adopt research, run deployment commands or duplicate the
ordinary source ledger. Unknown observations remain unknown.
"""
from __future__ import annotations

import copy
from collections import Counter
from datetime import datetime, timezone
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

from inresearch.storage.layout import workspace_path
from inresearch.storage.jsonl import append_record, read_rows


def _read(root, path):
    return json.loads((Path(root) / path).read_text(encoding='utf-8'))


def manifest(root):
    return _read(root, 'framework/site_navigation.json')


def _one(query, key, default=''):
    value = query.get(key, default)
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError('duplicate ' + key)
        value = value[0]
    if not isinstance(value, str):
        raise ValueError('invalid ' + key)
    return value


def permitted(root, role):
    result = {'delivery': [], 'backstage': []}
    for area, entries in manifest(root)['navigation'].items():
        for entry in entries:
            if role not in entry['roles']:
                continue
            item = copy.deepcopy(entry)
            item['children'] = [c for c in item['children'] if role in c.get('roles', entry['roles'])]
            for child in item['children']:
                child['href'] = child.get('role_hrefs', {}).get(role, child['href'])
            if entry['children'] and not item['children']:
                continue
            if item['children'] and item['href'] not in [c['href'] for c in item['children']]:
                item['href'] = item['children'][0]['href']
            result[area].append(item)
    return result


def resolve(root, page):
    doc = manifest(root)
    parts = urlsplit(page)
    query = parse_qs(parts.query)
    if parts.path == '/workspace.html':
        section = _one(query, 'section')
        view_id = _one(query, 'view')
        for area, entries in doc['navigation'].items():
            for entry in entries:
                if entry['id'] == section:
                    return {'area': area, 'section': section, 'view': view_id or None}
    if parts.path == '/industry.html' and any(query.get(k) for k in ('c','region','country','province','city','address','stage','relation','role','scope','q')):
        return {'area': 'delivery', 'section': 'campuses', 'view': 'directory'}
    if parts.path == '/tasks.html' and parts.fragment == 'work-packages':
        return {'area': 'backstage', 'section': 'production', 'view': 'tasks'}
    if parts.path == '/ops.html':
        view_id = {'ops-history': 'logs', 'users-drawer': 'accounts', 'prices-drawer': 'statistics', 'ops-quality': 'quality'}.get(parts.fragment, 'health')
        return {'area': 'backstage', 'section': 'content' if view_id in ('statistics', 'quality') else 'operations', 'view': view_id}
    for rule in doc['page_rules']:
        if parts.path in rule['paths'] and all(query.get(k) == [v] for k, v in rule.get('query', {}).items()):
            return {k: rule[k] for k in ('area', 'section', 'view')}
    if parts.path.startswith('/admin/'):
        return {'area': 'backstage', 'section': 'architecture', 'view': 'repositories'}
    return {'area': 'delivery' if parts.path in ('/guide.html','/search.html') else 'authenticated', 'section': None, 'view': None}


def navigation(root, role, user, page='/'):
    doc = manifest(root)
    if role == 'collaborator':
        from inresearch.interfaces import project_access
        value = {'member':project_access.member(user, root),
                 'frontend':bool(project_access.grant(user, root).get('frontend')),
                 'can_approve':project_access.can_review(user, root=root)}
        children = [{'id':'tasks','label':'我的工作与团队进展','href':'/tasks.html'}]
        if value['can_approve']:
            children.append({'id':'reviews','label':'待我审批','href':'/task-reviews.html'})
        delivery = [{'id':'campuses','label':'全球园区','href':'/projects.html','children':[]}] if value['frontend'] else []
        backstage = [{'id':'production','label':'项目工作','href':'/tasks.html','children':children}] if value['member'] else []
        requested_page = _one(parse_qs(urlsplit(page).query), 'page', '/') if urlsplit(page).path == '/api/navigation' else page
        return {'ok':True, 'version':doc['version'], 'identity':{'kind':'collaborator','name':user,'role':role},
                'navigation':{'delivery':delivery,'backstage':backstage},
                'active':resolve(root, requested_page),
                'public_navigation':doc['public_navigation'], 'delivery_pages':[],
                'footer':{'groups':[],'legal':[],'updates':[],'runtime':None},
                'search':{'enabled':False,'scopes':[],'default_scope':None}}
    # HTTP supplies a query in /api/navigation?page=...; standalone callers can
    # pass the page itself. Hash is useful for resolving existing in-page tools.
    if urlsplit(page).path == '/api/navigation':
        page = _one(parse_qs(urlsplit(page).query), 'page', '/')
    active = resolve(root, page)
    nav = permitted(root, role)
    if active == {'area': 'public', 'section': 'home', 'view': None} and nav['delivery']:
        active = {'area': 'delivery', 'section': 'campuses', 'view': 'directory'}
    if role == 'customer' and urlsplit(page).path == '/tasks.html':
        active = {'area': 'public', 'section': 'tasks', 'view': None}
    kind = 'anonymous' if role == 'reader' else 'customer' if role == 'customer' else 'team'
    scopes = ['delivery'] if role == 'customer' else (['delivery', 'backstage', 'all'] if role in ('admin', 'member') else ['backstage'] if role == 'intern' else [])
    default = 'backstage' if active['area'] == 'backstage' and 'backstage' in scopes else (scopes[0] if scopes else None)
    footer = copy.deepcopy(doc['footer']) if kind != 'anonymous' else {'groups': [], 'legal': []}
    footer['updates'] = [{k: r.get(k) for k in ('title', 'version', 'description', 'published_at')} for r in _plan(root)['releases'] if r.get('status') == 'published']
    footer['runtime'] = ({'version': os.environ.get('INRESEARCH_SOURCE_REVISION') or None,
                          'observed_at': None, 'status': 'unknown', 'deployed_at': None,
                          'environment': os.environ.get('INRESEARCH_ENVIRONMENT') or None}
                         if role in ('admin', 'member') else None)
    return {'ok': True, 'version': doc['version'],
            'identity': {'kind': kind, 'name': user or None, 'role': role},
            'navigation': nav, 'active': active, 'public_navigation': doc['public_navigation'],
            'delivery_pages': list(doc['access']['customer']['pages']) if kind != 'anonymous' else [],
            'footer': footer, 'search': {'enabled': bool(scopes), 'scopes': scopes, 'default_scope': default}}


def _section(root, role, section_id, view_id):
    for area, entries in permitted(root, role).items():
        for item in entries:
            if item['id'] == section_id:
                children = item['children']
                if children:
                    selected = next((c for c in children if c['id'] == view_id), None)
                    if not selected:
                        raise PermissionError('该栏目或视图不在当前账号权限内')
                else:
                    if view_id and not (section_id == 'overview' and view_id in ('current', 'analysis')):
                        raise ValueError('unknown view')
                    selected = item
                return area, item, selected
    raise PermissionError('该栏目不在当前账号权限内')


def _table(title, columns, rows, note=''):
    return {'title': title, 'columns': [{'key': k, 'label': l} for k, l in columns], 'rows': rows, 'note': note}


def _link(label, href):
    return {'label': label, 'href': href}


def _companies(root):
    from inresearch.delivery.source_publication import companies
    return companies(root)['records']


def _industry(root):
    from inresearch.knowledge.industry import cached_snapshot
    return cached_snapshot(root, {'overview': '1'})


def _reports():
    return [
        {'id': 'data-centers-2026', 'title': '全球数据中心容量与项目研究', 'kind': '专题报告', 'date': '2026-10-11',
         'region': '美国、东南亚、中国', 'href': '/research/data-centers-2026.html',
         'description': '报告正文及地区、项目附录组成一个报告包。项目记载是截止日快照，不计作当前全球园区总量。'},
        {'id': 'registry-snapshot', 'title': '数据中心研究快照', 'kind': '动态快照', 'date': None,
         'region': '综合', 'href': '/report.html', 'description': '随当前研究登记生成；生成日期不代表全部来源已更新。'},
]


def _atlas(view_id):
    pairs = ([('设施系统', 'facility-atlas'), ('电力系统', 'power-atlas'), ('水与散热', 'thermal-atlas'),
              ('计算系统', 'compute-atlas'), ('内存系统', 'memory-atlas'), ('持久存储', 'storage-atlas'),
              ('网络系统', 'network-atlas'), ('控制与软件', 'control-atlas')]
             if view_id == 'systems' else
             [('跨尺度结构', 'cross-scale-atlas'), ('整柜结构', 'rack-atlas'), ('整柜分层', 'rack-exploded'),
              ('服务器平面', 'server-plan'), ('芯片与封装', 'chip-atlas'), ('园区平面', 'campus-plan')])
    rows = [{'name': label, 'href': '/' + path + '.html', 'view': '图解'} for label, path in pairs]
    if view_id == 'systems':
        rows.insert(0, {'name': '系统与部件总览', 'href': '/bom.html', 'view': '总览'})
    else:
        rows += [{'name': '部件3D场景', 'href': '/bom3d.html', 'view': '3D'}, {'name': '整柜3D场景', 'href': '/rack3d.html', 'view': '3D'}]
    return rows


def _tasks(root, user, role):
    from inresearch.workflow.research_tasks import read
    rows = read(root)['packages']
    if role == 'intern':
        rows = [r for r in rows if r.get('assignee') == user]
    return [{'id': r['id'], 'name': r['title'], 'status': r['status'], 'region': r.get('region'),
             'assignee': r.get('assignee'), 'href': '/tasks.html#work-packages'} for r in rows]


def _plan(root):
    path = Path(root) / 'framework/site_implementation.json'
    return _read(root, str(path.relative_to(root))) if path.exists() else {'milestones': [], 'releases': []}


def view(root, role, user, query):
    root = Path(root)
    section_id, view_id = _one(query, 'section'), _one(query, 'view')
    if not view_id:
        choices = [e for entries in permitted(root, role).values() for e in entries if e['id'] == section_id]
        if choices and choices[0]['children']:
            view_id = choices[0]['children'][0]['id']
    area, item, selected = _section(root, role, section_id, view_id)
    result = {'ok': True, 'area': area, 'section': section_id, 'view': view_id,
              'title': selected['label'], 'summary': '', 'blocks': [], 'links': [],
              'tabs': item['children'], 'generated_at': datetime.now(timezone.utc).isoformat()}
    blocks = result['blocks']
    if section_id == 'companies':
        records = _companies(root)
        from inresearch.workflow import product_catalog
        rows = [{'name': c.get('name_cn') or c['name'], 'id': c['company_id'],
                 'roles': '、'.join(c.get('roles') or []),
                 'catalog': '已登记目录入口' if c['company_id'] in product_catalog.COMPANIES else '未登记产品目录',
                 'href': '/product-catalog.html?' + urlencode({'c': c['company_id'], **({'view': 'products'} if view_id == 'products' else {})})}
                for c in records]
        blocks.append(_table('企业与目录入口', [('name', '企业'), ('roles', '业务角色'), ('catalog', '产品目录')], rows,
                             '目录入口登记不等于产品资料已交付；实际收录与来源在公司页面查看。'))
        result['links'] = [_link('计算产品跨公司筛选', '/compute-catalog.html')]
    elif section_id == 'atlas':
        blocks.append(_table(selected['label'], [('name', '图册'), ('view', '视图')], _atlas(view_id),
                             '2D与3D是阅读视图，下载随具体图册提供；示意图不自动代表同一厂商或现场完整配置。'))
    elif section_id == 'reports':
        blocks.append(_table('统一报告库', [('title', '报告'), ('kind', '类型'), ('date', '报告日期'), ('region', '范围'), ('description', '说明')], _reports()))
        result['summary'] = '按标题、类型和地区筛选报告；附录、版本与导出保留在报告详情。'
    elif section_id == 'industry':
        from inresearch.knowledge.registry import cached_news
        from inresearch.interfaces.public import customer_news
        published = customer_news(cached_news(root, limit=80, overview=True))
        feed = published.get('feed') or {}
        headlines = []
        for row in feed.get('items', []):
            parts = urlsplit(row.get('url') or '')
            if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
                continue
            headlines.append({'name': row.get('title_zh') or row.get('title'), 'time': row.get('published_at'),
                              'source': row.get('domain') or parts.hostname, 'href': row['url']})
        blocks.append(_table('近期行业报道', [('name', '报道'), ('time', '原文时间'), ('source', '来源')], headlines,
                             '报道是外部信息线索，不代表本站已核实或正式采用；没有原文时间的记录保持未知。'))
        data = _industry(root)
        rows = data.get('research_updates', [])
        if isinstance(rows, dict):
            rows = rows.get('changes', rows.get('items', rows.get('rows', [])))
        safe = [{'name': r.get('title') or r.get('text') or r.get('name') or (r.get('object') or {}).get('name') or r.get('site_id') or r.get('object_id'),
                 'recorded_at': r.get('recorded_at') or r.get('published_at'), 'effective_at': r.get('effective_at') or r.get('as_of'),
                 'kind': r.get('kind') or r.get('type') or '资料补充',
                 'href': '/project.html?' + urlencode({'site': r['site_id']}) if r.get('site_id') else '/product-catalog.html?' + urlencode({'c': r['object']['identity']['company_id']}) if (r.get('object') or {}).get('type') == 'company' else '/industry.html'} for r in rows[:200]]
        blocks.append(_table('最近登记与补充', [('name', '内容'), ('kind', '类别'), ('recorded_at', '本站补充时间'), ('effective_at', '信息有效时间')], safe,
                             '补录时间不代表事件刚刚发生；未知有效时间留空。'))
        result['links'] = [_link('项目动态与建设计划', '/projects.html?view=pipeline'), _link('地图新闻与更新', '/')]
    elif section_id == 'overview':
        tasks = _tasks(root, user, role)
        geographic = _industry(root).get('geographic_analysis', {})
        blocks.append(_table('园区登记与覆盖', [('name', '独立计量'), ('value', '记录数')], [
            {'name': label, 'value': geographic.get(key)} for key, label in
            [('place_records','地点登记（非全球唯一园区总数）'),('cluster_records','跨园区集群'),
             ('portfolio_records','组合计划'),('unlocated_records','地点未定位')]],
            '登记、工作包、阅读和研究采用分别计数，不能相加成完成率。'))
        plan = _plan(root)
        if view_id == 'analysis':
            rows = [{'name': key, 'count': count} for key, count in Counter(r['status'] for r in tasks).items()]
            blocks.append(_table('团队任务状态汇总', [('name', '协调状态'), ('count', '工作包数')], rows,
                                 '协调状态不等于资料阅读、研究采用或网站上线；当前没有完整历史趋势序列。'))
        else:
            blocks.append(_table('当前团队任务', [('name', '工作包'), ('status', '协调状态'), ('assignee', '负责人'), ('region', '范围')], tasks))
        blocks.append(_table('产品建设里程碑', [('title', '里程碑'), ('status', '建设状态'), ('acceptance', '验收')], plan['milestones']))
        result['tabs'] = [{'id': v, 'label': l, 'href': '/workspace.html?' + urlencode({'section': 'overview', 'view': v})}
                          for v, l in [('current', '当前总览'), ('analysis', '分析与总结')]]
        result['links'] = [_link('服务观测与阅读状态', '/ops.html#ops-health'), _link('研究生产', '/supply.html')]
    elif section_id == 'construction':
        plan = _plan(root)
        if view_id == 'plans':
            blocks.append(_table('需求与里程碑', [('title', '需求'), ('status', '实施状态'), ('acceptance', '验收')], plan['milestones']))
        elif view_id == 'releases':
            blocks.append(_table('验收与发布记录', [('title', '版本'), ('status', '状态'), ('tested_at', '验收时间'), ('deployed_at', '部署时间')], plan['releases'],
                                 '没有实际回执的验收与部署留空；源码版本不代表环境已安装。'))
        else:
            rows = [{'title': r['title'], 'status': r['status'], 'href': '/workspace.html?' + urlencode({'section': 'construction', 'view': 'features', 'q': r['id']}), 'id': r['id']} for r in _read(root, 'framework/visual_atlas_migration.json')['items']]
            blocks.append(_table('图册建设登记', [('id', '功能记录'), ('title', '功能'), ('status', '登记状态')], rows,
                                 '这一清单仅覆盖现有图册建设范围，不代表全站功能完成度。'))
            result['links'] = [_link('全站页面地图', '/workspace.html?section=architecture&view=pages'), _link('图册资产检查', '/compare.html')]
    elif section_id == 'architecture':
        if view_id == 'pages':
            rows = []
            paths = _read(root, 'framework/interface_manifest.json')['static_pages']
            for path in paths:
                href = '/workspace.html?section=overview' if path == 'workspace.html' else '/' + path
                active = resolve(root, href)
                from inresearch.interfaces.repository_pages import protected
                administrator = protected(href) or href.lower() == '/admin/company.html'
                row = {'name': path, 'area': active['area'], 'section': active['section'],
                       'access': '管理员' if administrator else '按账号权限'}
                if not administrator or role == 'admin':
                    row['href'] = href
                rows.append(row)
            blocks.append(_table('已登记页面', [('name', '网址'), ('area', '导航域'), ('section', '所属栏目'), ('access', '访问范围')], rows,
                                 '结构归属不代表功能已验收；页面、功能和数据接口分别登记。'))
        else:
            blocks.append(_table('现行数据与服务职责', [('name', '环节'), ('description', '职责')], [
                {'name': '资料采集与接收', 'description': '来源、原件和接收回执进入研究生产；接收不等于阅读。'},
                {'name': '普通来源登记', 'description': '稳定对象身份、来源、结构与历史进入持续登记；独立数据发布不授予研究支持。'},
                {'name': '研究阅读与采用', 'description': '阅读、提取、审核和正式采用分别留痕，保留当前审核要求。'},
                {'name': '交付投影', 'description': '网页、搜索和下载按账号权限及字段分发资格读取同一正式记录。'},
                {'name': '通用数据中心', 'description': '类型分类树、3账／4问／5变量／6来源；解释结构、运行与情景。'},
                {'name': '全球真实园区', 'description': '稳定地点身份、分期、地理与现场角色；普通登记及地区统计独立于模型目标。'},
                {'name': '两者连接', 'description': '有范围／时点／来源的实际配置与指标关联；尚未实现自动现场配置或模型填参。'},
                {'name': '运行与部署', 'description': '应用代码部署与普通数据发布分别核对；实际环境回执进入运行管理。'}]))
            result['links'] = [_link('数据与服务运行观测', '/ops.html#ops-health')]
            if role == 'admin':
                result['links'].append(_link('主站详细架构', '/admin/inresearchrepo.html'))
    elif section_id == 'content':
        if view_id == 'projects':
            data = _industry(root)
            rows = [{'name': r['name'], 'country': r.get('country'), 'status': r.get('stage_label') or r.get('status'),
                     'site_id': r['site_id'], 'scope': (r.get('geography') or {}).get('identity_scope'),
                     'province': (r.get('geography') or {}).get('province'), 'city': (r.get('geography') or {}).get('city'),
                     'location': '已定位' if r.get('coordinates') else '缺坐标',
                     'registration': r.get('registration_status'),
                     'href': '/project.html?' + urlencode({'site': r['site_id']})} for r in data['rows']]
            blocks.append(_table('园区与项目登记', [('name', '对象'), ('site_id', '稳定ID'), ('scope', '登记范围'), ('country', '国家'), ('province', '省州'), ('city', '城市'), ('status', '阶段'), ('location', '定位'), ('registration', '来源登记')], rows,
                                 '读取同一运行登记；集群、组合与地点范围分开，不按名称或近似坐标自动合并。补录绑定具体对象并保留来源及历史。'))
            result['links'] = [_link('园区名录', '/projects.html'), _link('地区分析', '/regions.html'), _link('普查团队任务', '/tasks.html#work-packages')]
        elif view_id == 'statistics':
            rows = json.loads(workspace_path('data/prices.json', root).read_text())['records']
            blocks.append(_table('已登记报价系列', [('series_id', '系列'), ('as_of', '信息日期'), ('value', '值'), ('unit', '单位'), ('source_url', '来源')], rows))
            from inresearch.delivery.source_publication import objects
            ledger = objects(root, _read(root, 'data/object_observations.json'))
            identities = ledger['objects']
            observations = []
            for record in ledger['records']:
                identity = identities.get(record.get('object_id'), {})
                if identity.get('type') not in ('statistic', 'quote'):
                    continue
                observations.append({'name': identity.get('name'), 'object_id': record.get('object_id'),
                                     'metric': record.get('metric'), 'value': record.get('value'), 'unit': record.get('unit'),
                                     'scope': record.get('scope'), 'effective_at': record.get('effective_at'),
                                     'status': (record.get('registration') or {}).get('status') or (record.get('review') or {}).get('decision'),
                                     'source_url': (record.get('source') or {}).get('url')})
            blocks.append(_table('统计与报价观测历史', [('name', '系列'), ('metric', '字段'), ('value', '值或区间'),
                                 ('unit', '单位'), ('scope', '范围'), ('effective_at', '信息时间'), ('status', '登记／审核状态'), ('source_url', '来源')],
                                 observations, '包含普通登记与研究观测的历史版本；未核实登记不冒充研究采用，范围与时间不同的数值不直接相加。'))
            result['links'] = [_link('录入报价', '/ops.html#prices-drawer')]
        elif view_id == 'sources':
            from inresearch.delivery.source_publication import state
            runtime = state(root)
            records = _read(root, 'data/object_observations.json')['records'] + runtime['records']
            rows = [{'name': r.get('id'), 'object': r.get('object_id') or r.get('site_id'), 'metric': r.get('metric'),
                     'time': r.get('effective_at') or r.get('recorded_at'), 'status': (r.get('registration') or {}).get('status') or (r.get('review') or {}).get('decision') or (r.get('review') or {}).get('status')}
                    for r in records]
            blocks.append(_table('对象来源记录', [('name', '记录'), ('object', '对象'), ('metric', '字段'), ('time', '时间'), ('status', '登记／审核状态')], rows,
                                 '来源登记与正式研究支持分别表达；原件及私有定位不经客户搜索分发。'))
        else:
            data = _industry(root)
            gaps = [{'name': p['name'], 'site_id': p['site_id'],
                     'gap': '；'.join(label for missing, label in [
                         (not p.get('coordinates'), '缺坐标／地理精度'),
                         (not p.get('capacity_known') and not p.get('capacity_ranged'), 'IT容量未披露'),
                         (not p.get('participants'), '主体角色待补'),
                         (not p.get('verified_date'), '人工核实日期未登记'),
                         ((p.get('geography') or {}).get('identity_scope') == 'cluster', '集群尚未拆到物理园区')] if missing),
                     'href': '/project.html?' + urlencode({'site': p['site_id']})} for p in data['rows']]
            blocks.append(_table('园区身份与数据缺口', [('name','对象'),('site_id','稳定ID'),('gap','已知缺口')],
                                 [r for r in gaps if r['gap']], '缺项不等于信息为零或不存在；普通登记不强制研究审核。'))
            records = list(read_rows(workspace_path('data/raw/site-feedback/requests.jsonl', root)))
            blocks.append(_table('反馈与待处理问题', [('title', '反馈'), ('created_at', '收到时间'), ('context', '页面'), ('status', '状态')], records))
            result['links'] = [_link('现行数据质量检查', '/ops.html#ops-quality')]
    elif section_id == 'production':
        if view_id == 'tasks':
            blocks.append(_table('团队任务', [('name', '工作包'), ('status', '协调状态'), ('assignee', '负责人')], _tasks(root, user, role)))
        else:
            from inresearch.workflow import operations
            observed = operations.snapshot(root, {}, set())
            reader = observed.get('reader') or {}
            rows = [{'name': key, 'value': value} for key, value in reader.items() if isinstance(value, (str, int, float, bool)) or value is None]
            blocks.append(_table('阅读快照观测', [('name', '字段'), ('value', '观测值')], rows,
                                 '读取快照不启动或重启Reader；缺少、过期、失败与完成分别表达。'))
            result['links'] = [_link('节点研究工作台', '/research-workbench.html?col=4'), _link('材料与结果匹配', '/supply.html#matching'), _link('执行与日志', '/ops.html#ops-history')]
            if view_id == 'adoption':
                result['links'].append(_link('历史兼容研究结论', '/report.html?legacy=1'))
            result['summary'] = '阅读与提取结果按原件和版本追溯。' if view_id == 'reading' else '园区普通登记不经过研究审核；用于结论或模型时分别核对象、主体、分期、时间与来源支持范围。'
    elif section_id == 'operations':
        blocks.append(_table('当前部署观测', [('name', '字段'), ('value', '值')], [
            {'name': '运行环境', 'value': os.environ.get('INRESEARCH_ENVIRONMENT')},
            {'name': '实际安装源码版本', 'value': os.environ.get('INRESEARCH_SOURCE_REVISION')},
            {'name': '部署时间', 'value': None}, {'name': '现行规范版本', 'value': _read(root, 'framework/current_state.json')['version']}],
            '未收到的实际部署及恢复回执保持未知；规范版本不是安装版本。'))
        result['links'] = [_link('服务与健康', '/ops.html#ops-health'), _link('执行记录', '/ops.html#ops-history')]
        if role == 'admin':
            result['links'].append(_link('现行部署规范', '/doc.html?f=docs/local_setup/README.md'))
    else:
        result['links'] = [_link(c['label'], c['href']) for c in item['children']]
    if role != 'admin':
        result['links'] = [link for link in result['links'] if urlsplit(link['href']).path != '/ops.html']
    if role == 'customer':
        from inresearch.interfaces.public import customer_allowed
        def readable(href):
            parts = urlsplit(href)
            if parts.scheme:
                return parts.scheme in ('https', 'http') and bool(parts.hostname) and not parts.username and not parts.password
            return customer_allowed(root, parts.path, parts.query)
        for block in blocks:
            for row in block['rows']:
                if row.get('href') and not readable(row['href']):
                    row.pop('href')
        result['links'] = [link for link in result['links'] if readable(link['href'])]
    q = _one(query, 'q').strip().casefold()
    if len(q) > 160:
        raise ValueError('搜索词过长')
    for block in blocks:
        if q:
            block['rows'] = [r for r in block['rows'] if q in ' '.join(str(v) for v in r.values() if v is not None).casefold()]
        block['total'] = len(block['rows'])
        block['rows'] = block['rows'][:300]
    return result


def search(root, role, user, query):
    q = _one(query, 'q').strip()
    scope = _one(query, 'scope', 'delivery')
    if len(q) > 160 or scope not in ('delivery', 'backstage', 'all'):
        raise ValueError('invalid search')
    if role == 'reader' or role == 'customer' and scope != 'delivery' or role == 'intern' and scope != 'backstage':
        raise PermissionError('搜索范围不在当前账号权限内')
    rows = []
    nav = permitted(root, role)
    if not q:
        return {'ok': True, 'q': q, 'scope': scope, 'rows': [], 'total': 0, 'truncated': False}
    needle = q.casefold()
    total = 0
    def append_match(row):
        nonlocal total
        total += 1
        if len(rows) < 100:
            rows.append(row)
    def add(label, text, href, kind, area):
        if needle in (label + ' ' + text).casefold():
            append_match({'title': label, 'description': text[:300], 'href': href, 'kind': kind, 'area': area})
    for area, entries in nav.items():
        if scope not in (area, 'all'):
            continue
        for item in entries:
            add(item['label'], '', item['href'], '栏目', area)
            for child in item['children']:
                add(child['label'], item['label'], child['href'], '页面', area)
    if scope in ('delivery', 'all') and nav['delivery']:
        for c in _companies(root):
            add(c.get('name_cn') or c['name'], c['name'] + ' ' + (c.get('profile') or ''), '/product-catalog.html?' + urlencode({'c': c['company_id']}), '企业', 'delivery')
        for p in _industry(root)['rows']:
            add(p['name'], ' '.join(str(p.get(k) or '') for k in ('country', 'region', 'location', 'stage_label')),
                '/project.html?' + urlencode({'site': p['site_id']}), '项目', 'delivery')
        for r in _reports():
            add(r['title'], r['region'] + ' ' + r['description'], r['href'], '报告', 'delivery')
        from inresearch.workflow import product_catalog, catalog_ownership
        # Search explicit product identity fields in the current received run.
        # Payloads, originals and specification quotes never leave this index.
        pattern = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        for cid in product_catalog.COMPANIES:
            path = product_catalog.database(Path(root), cid)
            if not path.is_file():
                continue
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
                run = db.execute('SELECT id FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
                if not run:
                    continue
                products = db.execute("SELECT json_extract(payload,'$.id'),json_extract(payload,'$.name'),json_extract(payload,'$.company_id'),json_extract(payload,'$.source_url'),json_extract(payload,'$.product_url'),json_extract(payload,'$.kind') FROM products WHERE run_id=? AND (json_extract(payload,'$.name') LIKE ? ESCAPE '\\' OR json_extract(payload,'$.id') LIKE ? ESCAPE '\\') ORDER BY json_extract(payload,'$.id')", (run[0],pattern,pattern))
                for pid, name, owner, source, url, kind in products:
                    identity = {'id': pid, 'name': name, 'company_id': owner, 'source_url': source, 'product_url': url}
                    if catalog_ownership.conflict(identity, cid):
                        continue
                    if isinstance(name, str) and pid:
                        append_match({'title': name, 'description': cid + (' · 具体型号' if kind == 'named_product' else ' · 目录条目'), 'href': '/product-catalog.html?' + urlencode({'c': cid, 'view': 'products', 'product_id': pid}), 'kind': '产品', 'area': 'delivery'})
    if scope in ('backstage', 'all') and nav['backstage']:
        for t in _tasks(root, user, role):
            add(t['name'], (t.get('region') or '') + ' ' + (t.get('assignee') or ''), t['href'], '团队任务', 'backstage')
        if role in ('admin', 'member'):
            for p in _plan(root)['milestones']:
                add(p['title'], p.get('status', ''), '/workspace.html?section=construction&view=plans', '建设计划', 'backstage')
    return {'ok': True, 'q': q, 'scope': scope, 'rows': rows, 'total': total, 'truncated': total > len(rows),
            'coverage': '栏目、企业、项目、已接收产品和报告；后台另含获准查看的任务与建设计划。私有原件与完整日志正文不进入此索引。'}


def feedback(root, role, user, payload):
    if role not in ('customer', 'admin', 'member', 'intern') or not isinstance(payload, dict):
        raise PermissionError('请登录后提交反馈')
    values = {}
    for key, limit in [('title', 160), ('description', 4000), ('context', 1000)]:
        value = payload.get(key, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('反馈字段格式或长度不正确')
        values[key] = value.strip()
    if not values['title'] or not values['description']:
        raise ValueError('请填写问题标题和具体说明')
    context = values['context']
    if context and (not context.startswith('/') or context.startswith('//') or any(c in context for c in ('\r', '\n', '\\'))):
        raise ValueError('页面地址须为本站相对网址')
    row = {'id': uuid.uuid4().hex, **values, 'actor': user, 'role': role, 'status': 'received',
           'created_at': datetime.now(timezone.utc).isoformat()}
    append_record(workspace_path('data/raw/site-feedback/requests.jsonl', root), row)
    return {'ok': True, 'id': row['id'], 'status': row['status'], 'message': '反馈已收到；正式研究与数据未被修改。'}
