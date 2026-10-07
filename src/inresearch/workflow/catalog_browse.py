"""Read-only, hierarchical browsing of captured Supermicro product paths.

These are site browsing categories, not invented vendor taxonomy. Raw payloads,
model identities, cells and source versions are never rewritten.
"""
import hashlib
import json
import re
import sqlite3
from urllib.parse import urlsplit, unquote

from . import product_catalog, product_navigation

VERSION = '2026-10-07.1'
PLATFORMS = {'mp': '多处理器平台', 'hyper': 'Hyper', 'clouddc': 'CloudDC',
             'twin': 'Twin 多节点', 'big-twin': 'BigTwin 多节点', 'bigtwin': 'BigTwin 多节点',
             'fat-twin': 'FatTwin 多节点', 'fattwin': 'FatTwin 多节点',
             'microcloud': 'MicroCloud 多节点', 'grandtwin': 'GrandTwin 多节点',
             'blade': '刀片平台', 'superblade': 'SuperBlade 刀片', 'ultra': 'Ultra'}
FOLDERS = {'addon': '扩展卡 / 模组', 'aoc': '扩展卡', 'aom': '扩展模组',
           'powersupply': '电源', 'power-supply': '电源', 'cable': '线缆', 'cables': '线缆',
           'riser': '转接卡', 'riser-card': '转接卡', 'heatsink': '散热附件',
           'backplane': '背板', 'rack': '机柜附件', 'chassis': '机箱附件',
           'xeon': 'Intel Xeon 平台', 'amd': 'AMD 平台', 'opteron': 'AMD Opteron 平台',
           'embedded': '嵌入式平台', 'atom': 'Intel Atom 平台', 'core': 'Intel Core 平台'}
HINT_KEYS = ('cpu','cpus','processor','processors','supported cpus','form factor','socket count',
             'device support','interface','network interface','network interfaces','networking','raid levels')
PLATFORM_PATTERNS = [('intel-xeon','Intel Xeon',r'\bintel\b.*\bxeon\b|\bxeon\b'),
                     ('intel-core','Intel Core',r'\bintel\b.*\bcore\b'),('intel-atom','Intel Atom',r'\batom\b'),
                     ('amd-epyc','AMD EPYC',r'\bepyc\b'),('amd-opteron','AMD Opteron',r'\bopteron\b'),
                     ('amd-ryzen','AMD Ryzen',r'\bryzen\b')]


def hint_rows(product):
    """Same bounded original-row projection used by SQL lists and full details."""
    if 'browse_hints' in product:
        return product['browse_hints']
    result = {}
    for table in product.get('tables', []):
        for row in table.get('rows', []):
            if len(row) != 2 or any(int(c.get('colspan',1)) != 1 or int(c.get('rowspan',1)) != 1 for c in row) or row[1].get('header'):
                continue
            label, value = (c.get('text','').strip() for c in row)
            if label.casefold() in HINT_KEYS and value and len(value) <= 2000:
                key = label.casefold()
                result[key] = None if key in result else {'label':label,'value':value}
    return [entry for entry in result.values() if entry][:32]


def unique_hints(product):
    result = {}
    for entry in hint_rows(product):
        key = entry['label'].strip().casefold()
        result[key] = None if key in result else entry.get('value')
    return {k:v for k,v in result.items() if v}


def board_groups(product, add, fallback):
    hints=unique_hints(product)
    cpu=' '.join(v for k,v in hints.items() if k in HINT_KEYS[:5]).casefold()
    matches=[(slug,label) for slug,label,pattern in PLATFORM_PATTERNS if re.search(pattern,cpu)]
    if len(matches)==1:
        add(matches[0][0],matches[0][1]+' 支持平台')
    elif len(matches)>1:
        add('multiple-platforms','多平台原文 / 待核对')
    elif fallback in FOLDERS:
        add(fallback,FOLDERS[fallback])
    else:
        add('platform-pending','处理器平台待补齐')
    socket_matches = [(slug,label) for count,slug,label,pattern in (
        ('1','single-socket','单路主板',r'\bsingle\s+(?:socket|processor)'),
        ('2','dual-socket','双路主板',r'\bdual\s+(?:socket|processor)|\b2\s*(?:x\s*)?sockets?'),
        ('4','quad-socket','四路主板',r'\bquad\s+(?:socket|processor)'))
        if re.search(pattern,cpu) or hints.get('socket count') == count]
    if len(socket_matches) == 1: add(*socket_matches[0])
    factor=hints.get('form factor','').casefold().strip()
    factors={'atx':('atx','ATX'),'e-atx':('e-atx','E-ATX'),'extended atx':('e-atx','E-ATX'),
             'micro atx':('micro-atx','Micro-ATX'),'micro-atx':('micro-atx','Micro-ATX'),
             'mini-itx':('mini-itx','Mini-ITX'),'mini itx':('mini-itx','Mini-ITX'),'flex atx':('flex-atx','Flex-ATX')}
    if factor in factors: add(*factors[factor])


def category_path(product):
    """Official paths plus explicit unambiguous raw fields; never model-name guesses."""
    line = product_navigation.company_line(product, 'supermicro') or 'unmapped'
    labels = {r['id']: r['name'] for r in product_navigation.COMPANY_LINES['supermicro']}
    result = [{'id': line, 'label': labels.get(line, '其他目录路径')}]
    url = product.get('product_url') or product.get('source_url') or ''
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ''
        trusted = parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username and not parsed.password and (host == 'supermicro.com' or host.endswith('.supermicro.com'))
    except ValueError:
        trusted = False
    parts = parsed.path.casefold().strip('/').split('/') if trusted else []
    if parts and parts[0] in {'en', 'zh_cn', 'zh_tw', 'zh-cn', 'zh-tw', 'ja', 'de', 'es', 'fr'}:
        parts = parts[1:]
    if not parts or parts[0] != 'products' or len(parts) < 2:
        return result + [{'id': line+'/unknown', 'label': '目录路径待核对'}]
    tail = parts[1:]
    top = tail[0]
    family = tail[1] if len(tail) > 1 else ''
    def add(slug, label):
        result.append({'id': result[-1]['id']+'/'+slug, 'label': label})
    height = next((p for p in tail[1:3] if re.fullmatch(r'\d{1,2}u', p)), '')
    if top == 'system':
        if re.fullmatch(r'\d{1,2}u', family):
            add('rack-systems', '机架式存储系统' if line == 'storage' else '机架式服务器')
        elif family in PLATFORMS:
            add(family, PLATFORMS[family])
        elif family == 'gpu':
            add('gpu-systems', 'GPU 服务器')
        elif family == 'iot':
            add('iot', 'IoT / 边缘平台')
        elif family in {'storage', 'superstorage'}:
            add('storage-systems', '存储平台')
        else:
            add('system-path', '其他系统路径')
        if height:
            add(height, height.upper()+' 形态')
    elif top == 'chassis':
        add('chassis', '机箱')
        if height: add(height, height.upper()+' 机箱')
        elif family == 'mini-1u': add('mini-1u','Mini 1U 机箱')
        elif unquote(family) in {'tower','mid-tower','mini-tower','compact mini-tower'}:
            add('tower','塔式机箱')
    elif top == 'rack':
        add('rack-scale', '整柜 / 机架级系统')
    elif top == 'motherboard':
        board_groups(product,add,family)
    elif top == 'motherboards':
        board_directories={'server-boards':'服务器主板目录','workstation-boards':'工作站主板目录',
                           'embedded-iot-boards':'嵌入式 / IoT 主板目录','desktop-gaming-boards':'桌面 / 游戏主板目录'}
        add('directories','主板分类与选型目录')
        if family in board_directories: add(family,board_directories[family])
    elif top in {'accessories', 'addon', 'aoc'}:
        folder = family if top == 'accessories' else top
        if folder in {'addon','aoc'}:
            hints=unique_hints(product)
            text=' '.join(v for k,v in hints.items() if k not in HINT_KEYS[:7]).casefold()
            network=bool(re.search(r'ethernet|\b\d+\s*g(?:b)?e\b|infiniband',text))
            storage=bool(re.search(r'\bsata\d?\b|\bsas\b|\bnvme\b',text))
            add('addon','扩展卡 / 模组')
            if network and not storage: add('network-adapters','网络接口扩展卡')
            elif storage and not network: add('storage-adapters','存储接口扩展卡')
            else: add('other-adapters','其他扩展卡 / 接口待核对')
        elif folder in FOLDERS:
            add(folder, FOLDERS[folder])
        elif folder=='networking':
            add('network-accessories','网络附件')
        else:
            add('accessory-path', '其他附件路径')
    elif top in {'superblade','microblade'}:
        add(top,'SuperBlade' if top=='superblade' else 'MicroBlade')
        kinds={'module':'刀片计算模块','modules':'模块目录','powersupply':'电源模块',
               'enclosure':'刀片机箱','networking':'刀片网络模块','storage':'刀片存储模块',
               'management':'管理模块 / 软件','matrix':'选型矩阵'}
        if family in kinds:add(family,kinds[family])
    elif top=='gpu':
        add('gpu-platforms','GPU 平台目录')
        if family in {'air-cooled','liquid-cooled'}:add(family,'风冷平台' if family=='air-cooled' else '液冷平台')
    elif line == 'unmapped':
        # Keep unexplained paths reachable in separate buckets, never discard them.
        slug = top if re.fullmatch(r'[a-z0-9_-]{1,60}', top) else hashlib.sha256(top.encode()).hexdigest()[:12]
        add(slug, '官网路径 /'+top[:80])
    else:
        add(top, {'networking': '网络产品', 'software': '软件产品', 'embedded': '嵌入式产品',
                  'iot': 'IoT 产品', 'storage': '存储产品', 'superstorage': 'SuperStorage',
                  'supercluster':'集群平台','superworkstation':'工作站','single-processor':'单处理器服务器',
                  'dual-processor':'双处理器服务器','blade':'刀片平台','microcloud':'MicroCloud 平台',
                  'rackmount-workstations':'机架工作站','rackmount':'机架式服务器目录','aplus':'A+ 平台',
                  'mp':'多处理器平台','gold-series':'Gold Series','nvme':'NVMe 存储',
                  'nvme-edsff':'EDSFF / NVMe 存储','jbof':'JBOF','general-purpose-storage':'通用存储',
                  'edge':'边缘服务器','5g':'5G 平台','nvidia-jetson':'Jetson 边缘平台',
                  'rdhx':'后门换热设备'}.get(top, '其他产品路径'))
    return result


def parameters(product):
    """Unambiguous two-cell original values only; configuration tables stay intact."""
    pairs = {}
    for table in product.get('tables', []):
        for row in table.get('rows', []):
            if len(row) != 2 or any(int(c.get('colspan', 1)) != 1 or int(c.get('rowspan', 1)) != 1 for c in row) or row[1].get('header'):
                continue
            key, value = (c.get('text', '').strip() for c in row)
            if not key or not value: continue
            pairs[key] = None if key in pairs else value
    pattern = r'processor|\bcpu|\bgpu|memory|capacity|dimensions|form factor|power|interface|network|storage|rack|nodes|cooling'
    return [{'label': k, 'value': v} for k,v in pairs.items() if v is not None and re.search(pattern,k,re.I)][:12]


def query(root, company='supermicro', category='', line='', q='', kind='', with_specs=False, offset=0, limit=25):
    if company != 'supermicro': raise ValueError('hierarchical browse is not registered for this company')
    offset, limit = int(offset), int(limit)
    if offset < 0 or not 1 <= limit <= 50 or len(q) > 120 or kind not in {'','named_product','family_or_directory','software_service'}:
        raise ValueError('invalid browsing filter')
    path = product_catalog.database(root, company)
    empty = {'available': False, 'company_id': company, 'roots': [], 'children': [], 'breadcrumb': [], 'items': [], 'matched': 0, 'offset': 0, 'limit': limit}
    if not path.is_file(): return empty
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        run = db.execute('SELECT id,generated FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
        if not run: return empty
        hints_sql="""(SELECT json_group_array(json_object('label',label,'value',value)) FROM
            (SELECT trim(json_extract(r.value,'$[0].text')) AS label,trim(json_extract(r.value,'$[1].text')) AS value
             FROM json_each(p.payload,'$.tables') AS t,json_each(t.value,'$.rows') AS r
             WHERE json_array_length(r.value)=2 AND coalesce(json_extract(r.value,'$[0].colspan'),1)=1
               AND coalesce(json_extract(r.value,'$[1].colspan'),1)=1
               AND coalesce(json_extract(r.value,'$[0].rowspan'),1)=1 AND coalesce(json_extract(r.value,'$[1].rowspan'),1)=1
               AND NOT coalesce(json_extract(r.value,'$[1].header'),0)
               AND lower(trim(json_extract(r.value,'$[0].text'))) IN ("""+','.join('?' for _ in HINT_KEYS)+""")
               AND length(trim(json_extract(r.value,'$[1].text'))) BETWEEN 1 AND 2000 GROUP BY lower(label) HAVING count(*)=1 LIMIT 32))"""
        rows = db.execute("""SELECT id,json_extract(payload,'$.name'),json_extract(payload,'$.source_url'),
            json_extract(payload,'$.product_url'),json_extract(payload,'$.kind'),json_array_length(payload,'$.tables'),
            json_extract(payload,'$.category'),json_extract(payload,'$.part_number'),"""+hints_sql+"""
            FROM products AS p WHERE run_id=? ORDER BY id""",(*HINT_KEYS,run[0]))
        items, nodes = [], {}
        for pid,name,url,product_url,entity_kind,count,original_category,part_number,hints in rows:
            item = {'id': pid, 'name': name, 'source_url': url, 'product_url': product_url,
                    'kind': entity_kind, 'table_count': count or 0, 'category': original_category or '', 'part_number': part_number or '',
                    'browse_hints':json.loads(hints)}
            chain = category_path(item)
            item['browse_path'] = chain
            item['company_line'] = chain[0]['id']
            items.append(item)
            for step in chain:
                bucket = nodes.setdefault(step['id'],{**step,'entities':0,'named_products':0,'with_tables':0})
                bucket['entities'] += 1
                bucket['named_products'] += entity_kind == 'named_product'
                bucket['with_tables'] += bool(count)
        selected = category or line
        if selected and selected not in nodes:
            known_lines = {r['id']:r['name'] for r in product_navigation.COMPANY_LINES[company]}
            known_lines['unmapped']='其他目录路径'
            if selected in known_lines: nodes[selected]={'id':selected,'label':known_lines[selected],'entities':0,'named_products':0,'with_tables':0}
            else: raise ValueError('unknown browsing category')
        if line and category and category != line and not category.startswith(line+'/'):
            raise ValueError('category does not belong to business line')
        matching = [p for p in items if (not selected or any(s['id']==selected for s in p['browse_path']))
                    and (not kind or p['kind']==kind) and (not with_specs or p['table_count'])]
        if q.strip():
            # Search original cell text as well as names. Searching B200 can find
            # a server whose model name does not contain its supported GPU name.
            needle=q.strip().casefold()
            escaped=needle.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            found={r[0] for r in db.execute("""SELECT id FROM products WHERE run_id=? AND EXISTS
                (SELECT 1 FROM json_tree(payload,'$.tables') WHERE key='text' AND type='text' AND lower(value) LIKE ? ESCAPE '\\')""",(run[0],'%'+escaped+'%'))}
            matching=[p for p in matching if needle in (p['name']+' '+p['category']+' '+p['part_number']).casefold() or p['id'] in found]
        matching.sort(key=lambda p:(p['kind']!='named_product',not p['table_count'],p['name'].casefold()))
        total=len(matching)
        offset=min(offset,max(0,((total-1)//limit)*limit))
        page=matching[offset:offset+limit]
        for item in page:
            product=json.loads(db.execute('SELECT payload FROM products WHERE id=?',(item['id'],)).fetchone()[0])
            item['parameters']=parameters(product)
            item['source_sha256']=product['source_sha256']
            item.pop('product_url',None)
            item.pop('browse_hints',None)
        children=[n for n in nodes.values() if n['id'].rsplit('/',1)[0]==selected and '/' in n['id']] if selected else [n for n in nodes.values() if '/' not in n['id']]
        breadcrumb=[]
        if selected:
            segments=selected.split('/')
            breadcrumb=[nodes['/'.join(segments[:i])] for i in range(1,len(segments)+1)]
        roots=[n for n in nodes.values() if '/' not in n['id']]
        rank={r['id']:i for i,r in enumerate(product_navigation.COMPANY_LINES[company])}
        roots.sort(key=lambda n:(rank.get(n['id'],999),n['label']))
        children.sort(key=lambda n:(-n['entities'],n['label']))
        return {**empty,'available':True,'version':VERSION,'basis':'captured_official_path_and_explicit_spec_fields',
                'generated_at':run[1],'category':selected,'roots':roots,'children':children,'breadcrumb':breadcrumb,
                'total_entities':len(items),'total_named_products':sum(p['kind']=='named_product' for p in items),
                'items':page,'matched':total,'offset':offset}
