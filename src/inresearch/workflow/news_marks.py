"""研究员给新闻线索打「有用 / 没用」(2026-10-01 用户定口径)。

这是线索评价，不是 C3 证据采用：新闻永远只是线索，标记不进 data/research_knowledge.json、不改任何研究记录。
回传给 inews 的两个信号都只是按目标行的计数：
  - useful_by_target：近 WINDOW_DAYS 天研究员点「有用」的线索，按其 target_ids 计（快信号）；
  - adopted_by_target：线索的 url / origin_pointer 指向的原件，已经有通过 C3 的采用证据（慢信号）。
标记存在私有运行目录 data/raw/news-marks/，不经 HTTP 公开；公开的只有计数。
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from inresearch.knowledge.news_policy import TARGET_ID
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import locked, write_json
import json

MARKS = ('useful', 'not_useful')
WINDOW_DAYS = 30
MAX_MARKS = 20000


def marks_path(root):
    # 已声明的私有运行前缀(与 supply-center 同一处);不新增存储契约条目。
    return workspace_path('data/raw/news-marks/marks.json', root)


def canonical(url):
    """同一篇的不同写法算一个:小写主机、去 www、去片段与尾部斜杠。非 http(s) 返回 None。"""
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        return None
    host = parts.hostname.lower().removeprefix('www.')
    return urlunsplit(('https', host, parts.path.rstrip('/') or '/', parts.query, ''))


def _targets(item):
    ids = item.get('target_ids') if isinstance(item, dict) else None
    return sorted({t for t in ids if isinstance(t, str) and TARGET_ID.fullmatch(t)}) if isinstance(ids, list) else []


def read(root):
    path = marks_path(root)
    if not path.exists():
        return {'version': 1, 'marks': {}}
    value = json.loads(path.read_text())
    if value.get('version') != 1 or not isinstance(value.get('marks'), dict):
        raise ValueError('invalid_news_marks')
    return value


def mark(root, payload, actor, items=(), now=None):
    """payload {url, mark: useful | not_useful | clear}。目标行取自当前新闻窗口里同一 url 的线索。"""
    if not isinstance(payload, dict):
        raise ValueError('无效请求')
    key = canonical(payload.get('url'))
    if not key:
        raise ValueError('无效链接')
    value = payload.get('mark')
    if value not in MARKS + ('clear',):
        raise ValueError('标记只能是 useful / not_useful / clear')
    now = now or datetime.now(timezone.utc)
    match = next((i for i in items if isinstance(i, dict) and canonical(i.get('url')) == key), None)
    path = marks_path(root)
    with locked(path):
        data = read(root)
        if value == 'clear':
            data['marks'].pop(key, None)
        else:
            if key not in data['marks'] and len(data['marks']) >= MAX_MARKS:
                raise ValueError('标记已满')
            previous = data['marks'].get(key, {})
            data['marks'][key] = {'mark': value, 'by': str(actor or 'local')[:80], 'at': now.isoformat(),
                                  'target_ids': _targets(match) or previous.get('target_ids', []),
                                  'origin_pointer': canonical((match or {}).get('origin_pointer')) or previous.get('origin_pointer')}
        write_json(path, data)
    return {'ok': True, 'url': key, 'mark': None if value == 'clear' else value}


def mark_map(root):
    """给研究员页面:url → 标记。只在登录后读。"""
    return {k: v['mark'] for k, v in read(root)['marks'].items() if isinstance(v, dict)}


def useful_by_target(root, now=None):
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)
    counts = {}
    for row in read(root)['marks'].values():
        if not isinstance(row, dict) or row.get('mark') != 'useful':
            continue
        try:
            if datetime.fromisoformat(row['at']) < since:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        for t in _targets(row):
            counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def adopted_sources(knowledge, review_valid):
    """正式采用证据所在原件的地址(规范化)。review_valid 由 registry 传入,口径只有一处。"""
    documents = {d.get('id'): d for d in knowledge.get('documents', []) if isinstance(d, dict)}
    out = set()
    for e in knowledge.get('evidence', []):
        if isinstance(e, dict) and e.get('status') == 'adopted' and review_valid(e):
            url = canonical((documents.get(e.get('document_id')) or {}).get('source_url'))
            if url:
                out.add(url)
    return out


def adopted_by_target(root, items, knowledge, review_valid):
    """当前窗口的线索 + 打过标记的线索里,url 或原件指针落在已采用原件上的,按目标行计(同一线索只算一次)。"""
    sources = adopted_sources(knowledge, review_valid)
    if not sources:
        return {}
    leads = {}
    for item in items:
        if isinstance(item, dict) and canonical(item.get('url')):
            leads[canonical(item['url'])] = (canonical(item.get('origin_pointer')), _targets(item))
    for key, row in read(root)['marks'].items():
        if isinstance(row, dict) and key not in leads:
            leads[key] = (row.get('origin_pointer'), _targets(row))
    counts = {}
    for url, (origin, targets) in leads.items():
        if url in sources or (origin and origin in sources):
            for t in targets:
                counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
