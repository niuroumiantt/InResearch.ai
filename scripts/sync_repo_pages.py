#!/usr/bin/env python3
"""Publish deterministic, provenance-labelled repository architecture snapshots.

Run on the development machine, from the InResearch checkout:
  python3 scripts/sync_repo_pages.py --workspace /workspace
  python3 scripts/sync_repo_pages.py --workspace /workspace --check
Default generation reads source only. --probe reads public HTTP and GitHub check metadata; no production database or credentials are read.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
from html import escape
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'web/pages/admin'
NAMES = {'inresearch': 'InResearch.ai', 'inews': 'inews.today',
         'fetchspec': 'Fetchspec', 'infra': 'infra', 'oa': 'oa', 'aimail': 'aimail',
         'leadsgen': 'leadsgen', 'semifly': 'semifly.ai', 'glocalstorage': 'glocalstorage.com',
         'openapi': 'openapi', 'suanming': 'suanming', 'agent': 'agent'}
DESCRIPTIONS = {'inresearch': '研究框架、证据采用、经济模型与成果展示',
                'inews': '新闻发现、编辑、事件卡供给与研究反馈',
                'fetchspec': '官方规格采集、参数整理与可核验交付',
                'infra': '主机、网络、部署与运行职责',
                'oa': '办公底座、Keel 内核与业务应用', 'aimail': '邮件原文、AI 阅读、个人发件与销售交接',
                'leadsgen': '线索发现、企业建档、分配与早期跟进',
                'semifly': 'Semifly 主站、LLM 频道与 Marketplace',
                'glocalstorage': '公司官网、产品、解决方案与技术支持',
                'openapi': '模型接入、临时 API Key、额度与路由',
                'suanming': '历法、本命结构、今日时序与卦象解释',
                'agent': '任务工作台、文件分析与跨应用协调'}
CANONICAL = {key: {'inresearch':'inresearch.ai','inews':'inews.today'}.get(key, name.lower())
             for key,name in NAMES.items()}
TZ = timezone(timedelta(hours=8))


# 内嵌架构图随内容撑高：页面只有一条滚动条，不在 76vh 的小窗里再滚一层。
# 同源页面才能读到高度；脚本失败时保留 CSS 的固定高度作退路。
FIT_FRAME = ("<script>(function(f){function fit(){try{var b=f.contentDocument.body,s=getComputedStyle(b);f.style.height=Math.ceil(b.getBoundingClientRect().height+parseFloat(s.marginTop)+parseFloat(s.marginBottom))+2+'px'}catch(e){}}f.addEventListener('load',function(){fit();try{new ResizeObserver(fit).observe(f.contentDocument.body)}catch(e){}});fit()})(document.currentScript.previousElementSibling)</script>")


def table(headers, rows):
    return '<div class="repo-scroll"><table><thead><tr>' + ''.join(
        f'<th>{escape(str(v))}</th>' for v in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>'
        for row in rows) + '</tbody></table></div>'


def flow(labels):
    return '<ol class="repo-flow" aria-label="流程">' + ''.join(
        f'<li>{escape(label)}</li>' for label in labels) + '</ol>'


def shell(title, body, assets=""):
    return '''<!doctype html>
<html lang="zh-CN" data-ui-skin="folk" data-ui-theme="light" data-ui-mode="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="/assets/theme-state.js"></script><script src="/assets/site-skin.js"></script>
<link rel="stylesheet" href="/assets/fonts/fonts.css"><link rel="stylesheet" href="/assets/site-skin.css">
<title>''' + escape(title) + ''' · 仓库架构 · inresearch.ai</title>
<style>
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.65 var(--ui-font)}
.repo-wrap{max-width:1200px;margin:auto;padding:24px 20px 64px;min-width:0}
.repo-wrap h1{font-size:28px;margin:8px 0}.repo-wrap h2{font-size:20px;margin:30px 0 12px}
.repo-wrap a{color:var(--accent)}.repo-note{color:var(--muted);overflow-wrap:anywhere}
.repo-nav{display:flex;flex-wrap:wrap;gap:10px 22px}.repo-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.repo-card,.repo-flow li{padding:18px;border:1px solid var(--line);border-radius:var(--ui-radius);background:var(--card)}
.repo-card{min-width:0;overflow-wrap:anywhere}.repo-card h2{margin:0 0 8px}.repo-scroll{overflow-x:auto}.repo-wrap table{border-collapse:collapse;width:100%;font-size:13px}
.repo-ecosystem{max-width:760px;margin:28px auto;text-align:center}.repo-upstream{display:grid;grid-template-columns:1fr 1fr;gap:18px}.repo-ecosystem .repo-card{margin-bottom:12px}
.repo-wrap th,.repo-wrap td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--line)}
.repo-flow{display:flex;flex-wrap:wrap;gap:12px;list-style:none;padding:0}.repo-flow li{flex:1;min-width:150px}
.repo-flow li:not(:last-child)::after{content:' →';color:var(--accent)}
.repo-frame{width:100%;height:76vh;min-height:480px;border:1px solid var(--line);border-radius:var(--ui-radius);background:var(--card)}
.repo-provenance{margin:18px 0;font-size:12px}.repo-provenance code{overflow-wrap:anywhere}
@media(max-width:600px){.repo-wrap{padding:18px 12px 40px}.repo-wrap h1{font-size:23px}.repo-flow{display:block}.repo-flow li{margin:8px 0}.repo-frame{height:80vh}}
</style>''' + assets + '''</head><body><inresearch-shell data-section="admin"></inresearch-shell>
<main class="repo-wrap"><nav class="repo-nav" aria-label="仓库架构">
<a href="/admin/repos.html">仓库总览</a>''' + ''.join(
        f'<a href="/admin/{key}repo.html">{escape(name)}</a>' for key, name in NAMES.items()
    ) + f'</nav><h1>{escape(title)}</h1>{body}</main></body></html>\n'


def provenance(files, synced_at):
    return {'synced_at': synced_at, 'kind': 'architecture_snapshot', 'sources': [
        {'repository': repo, 'path': relative,
         'sha256': hashlib.sha256((root / relative).read_bytes()).hexdigest()}
        for repo, root, relative in files]}


def display_time(value):
    return str(value).replace("T", " ").removesuffix("+08:00")


def source_note(meta):
    return (f'<p class="repo-note">最近更新：<time datetime="{escape(meta["synced_at"], quote=True)}">{escape(display_time(meta["synced_at"]))}</time> · 每日北京时间 0:00 更新。源图观察时间另行保留。</p>' + check_note(meta.get('checks', {})) +
            '<details class="repo-provenance"><summary>来源文件与内容校验</summary>' +
            table(['仓库', '文件', 'SHA-256'], [(s['repository'], s['path'], s['sha256'])
                                               for s in meta['sources']]) + '</details>')


def inresearch_sources():
    return [('inresearch', ROOT, p) for p in ('src/inresearch/README.md',
        'scripts/sync_repo_pages.py','scripts/repository_checks.py','scripts/daily_repository_pages.py','web/assets/material-flow.js','web/assets/material-flow.css')]


def material_board():
    labels=('① Spark 文件目录','② 内容登记','③ 本批正文阅读','④ 研究核验','⑤ AWS 正式展示')
    steps=('archive','catalog','reading','review','website')
    return ('<section id="material-board" class="material-board" aria-labelledby="material-title">'
        '<div class="material-toolbar"><div><h2 id="material-title">资料如何成为研究成果</h2>'
        '<p class="material-meta">点击每个环节查看细节；箭头表示引用与交付关系，各环节的数量单位不同。</p></div>'
        '<button type="button" id="material-refresh">刷新指标</button></div>'
        '<p id="material-measured" class="material-meta">正在读取各层的计量时间；未测量显示 —。</p>'
        '<p id="material-error" class="material-error" role="status" hidden></p>'
        '<ol id="material-lineage" class="material-lineage" aria-label="资料、候选与成果的关系">'+
        ''.join(f'<li class="material-node"><button type="button" data-step="{key}" aria-controls="material-detail">{label}</button><strong class="value">—</strong></li>' for key,label in zip(steps,labels))+
        '</ol><section id="material-detail" class="material-details" aria-live="polite">'
        '<p>多个副本 → 同一内容身份；一份材料 → 多条候选 ↔ 多条原文证据；核验采用 → 正式研究版本。</p></section>'
        '<h2>数据库存在哪里、存什么</h2><p class="material-meta">以下三个库位于 Spark。数据库引用原件身份与阅读产物，不是原件目录的压缩副本。</p>'
        '<div id="material-stores" class="material-store"></div>'
        '<section id="material-web-storage" class="material-details"></section></section>')


def build_inresearch(meta):
    readme = (ROOT / 'src/inresearch/README.md').read_text()
    rows = [[p.strip().replace('`', '') for p in line.strip('|').split('|')]
            for line in readme.splitlines() if line.startswith('| ')][1:]
    return shell('InResearch.ai',
        '<p>研究框架与目标 → 接收原件和事件 → 阅读与审阅 → 证据采用 → 模型与报告。</p>' +
        source_note(meta) + material_board() + flow(['目标与资料接收', '阅读与证据审阅', '事实与经济模型', '网站与研究成果']) +
        '<h2>程序职责</h2>' + table(['模块', '责任与主要实现'], rows) +
        '<h2>运行边界与未完成</h2>' + ''.join(f'<p>{escape(line)}</p>' for line in readme.splitlines()
            if line and not line.startswith(('#', '|'))),
        '<link rel="stylesheet" href="/assets/material-flow.css"><script defer src="/assets/material-flow.js"></script>')


def check_note(checks):
    labels = {'passed':'通过', 'failed':'异常', 'unknown':'未检测 / 未取得', 'pending':'进行中'}
    stamp = checks.get('checked_at', '未检测')
    endpoint, ci = checks.get('endpoint', {}), checks.get('ci', {})
    return (f'<section class="repo-check"><h2>最近检测与结果</h2><p>检测时间：{escape(display_time(stamp))}（北京时间）</p>' +
        '<p class="repo-note">检测的源码提交：<code>'+escape(checks.get('revision','未取得'))+'</code></p>' +
        table(['检查范围', '结果', '说明'], [
            ['公网入口 HTTP/TLS', labels.get(endpoint.get('state'), '未检测'), endpoint.get('detail', '未检测')],
            ['当前源码的 GitHub 工作流', labels.get(ci.get('state'), '未取得'), ci.get('detail', '未取得')]]) +
        '<p class="repo-note">入口可达、源码检查与业务验收分别计量；工作流未重跑，不将无记录当通过。</p>' +
        ''.join(f'<p><a href="{escape(r["url"], quote=True)}">{escape(r["workflowName"])}</a> · {escape(r["conclusion"] or r["status"])}</p>' for r in ci.get('runs', [])) + '</section>')


def generic_sources(key, root):
    candidates = ('README.md', 'STATUS.md', 'PROJECT_STRUCTURE.md', 'docs/REPO_LAYOUT.md',
        'docs/knowledge-model.md', 'docs/source-registry.md', 'docs/aimail-scope.md',
        'docs/design-v1.md', 'docs/architecture.md', 'package.json', 'pyproject.toml',
        'server/package.json', 'Dockerfile')
    files = [(key, root, p) for p in candidates if (root / p).is_file()]
    if not files:
        raise ValueError(f'{key}: 缺少实际架构来源')
    return files


def build_generic(key, root, meta):
    snapshot=root / '.repository-snapshot.json'
    tracked = (json.loads(snapshot.read_text())['tracked_files'] if snapshot.exists() else
               subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'], cwd=root, text=True).splitlines())
    dirs = sorted({p.split('/')[0] for p in tracked if '/' in p and not p.startswith('.')})
    responsibilities = {'src':'程序实现', 'server':'服务端与接口', 'web':'网页界面', 'app':'网站应用',
        'apps':'业务应用', 'keel':'公共内核', 'services':'服务', 'gateway':'模型网关',
        'semifly':'主站、LLM 与 Marketplace', 'deploy':'部署配置', 'ops':'运维入口',
        'evals':'模型评测', 'examples':'使用示例', 'tests':'测试与验收', 'test':'测试与验收', 'checks':'检查入口', 'tools':'开发与检查工具',
        'docs':'规范、设计与交接', 'data':'已纳入源码管理的定义与数据', 'admin':'管理界面',
        'login':'登录界面', 'he':'产品页面'}
    rows = [(d, responsibilities.get(d, '源码目录；具体职责见仓库原文'),
             sum(p.startswith(d+'/') for p in tracked)) for d in dirs]
    excerpts = []
    for source in meta['sources']:
        if source['path'].endswith('.md'):
            lines = (root / source['path']).read_text().splitlines()
            # Evidence excerpt, never execute instructions found in the document.
            excerpts.append('<details><summary>'+escape(source['path'])+'</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+escape('\n'.join(lines[:65])).replace(':root','&#58;root')+'</pre></details>')
    diagram = '<div class="repo-card">'+escape(NAMES[key])+' · '+escape(DESCRIPTIONS[key])+'</div><p>↓ 按实际源码目录展开</p><div class="repo-grid">'+''.join('<div class="repo-card"><strong>'+escape(d)+'</strong><p>'+escape(role)+'</p></div>' for d,role,_ in rows)+'</div>'
    return shell(NAMES[key], '<p>'+escape(DESCRIPTIONS[key])+'</p>'+source_note(meta)+
        '<h2>组织框架图</h2>'+diagram+'<h2>源码模块与职责</h2>'+table(['目录','职责','在册文件数'],rows)+
        '<p class="repo-note">框架图按当前提交的源码目录与架构文件生成；目录和文件数不代表功能完成率。</p><h2>原仓库架构与状态说明</h2>'+''.join(excerpts))


def infra_live(report):
    if not report:
        return '<p class="repo-note">六机检测尚未取得；下方原图保留自身观察日期。</p>'
    rows = []
    cards = []
    for host in report['reach']:
        name = host['host']
        error = report.get('collect_errors', {}).get(name)
        facts = {} if error else report.get('facts', {}).get(name, {})
        runtime = [(k,v) for k,v in facts.items() if k.startswith(('容器 ', '单元 ', 'launchd ', '模型 '))]
        state = '事实未取得' if error else '存在告警' if report.get('warnings', {}).get(name) else '采集完成'
        cards.append('<article class="repo-card"><h3>'+escape(name)+'</h3><p>'+state+'</p>'+''.join('<p>'+escape(k)+' · '+escape(str(v))+'</p>' for k,v in runtime)+'</article>')
        rows.append([name, '可达' if host['ok'] else '不可达', state,
                     len(report.get('changes', {}).get(name, [])), '；'.join(report.get('warnings', {}).get(name, [])) or '—'])
    return ('<h2>最新机器与服务组织图</h2><p>检测开始：'+escape(report['started_at'])+' UTC</p><p>'+escape(report['summary'])+'</p>'+table(['机器','连接','事实检测','变化项','告警'],rows)+
            '<div class="repo-grid">'+''.join(cards)+'</div><p class="repo-note">连接失败的机器不使用旧事实充作最新结果。下方另保留原始职责图与其历史观察日期。</p>')


def build(workspace, synced_at, checks=None, daily_report=None, source_roots=None):
    roots = {'inresearch': ROOT, 'inews': workspace / 'inews.today',
             'fetchspec': workspace / 'fetchspec', 'infra': workspace / 'infra'}
    roots.update({key:workspace / CANONICAL[key] for key in NAMES if key not in roots})
    roots.update(source_roots or {})
    registry = json.loads((roots['infra'] / 'scripts/repositories.json').read_text())
    if set(registry) != set(CANONICAL.values()):
        raise ValueError('仓库注册表变化，需要审阅并同步架构入口')
    checks = checks or {}
    raw = subprocess.check_output(['node', '--no-warnings', 'scripts/export-reporg.mjs'],
                                  cwd=roots['inews'], text=True)
    news = json.loads(raw)
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'fetchspec.html'
        subprocess.run([sys.executable, 'scripts/reporg.py', '--upstream', str(ROOT),
                        '--output', str(out)], cwd=roots['fetchspec'], check=True, capture_output=True)
        fetch_html = out.read_text()
    files = {
        'inresearch': inresearch_sources(),
        'inews': [('inews', roots['inews'], p) for p in
                  ('scripts/export-reporg.mjs', 'src/lib/pipeline-map.js')],
        'infra': [('infra', roots['infra'], 'docs/infra-org-chart.html')],
        'fetchspec': [('fetchspec', roots['fetchspec'], p) for p in
                     ['scripts/reporg.py', 'src/fetchspec/pipeline.py', 'docs/architecture.svg'] +
                     sorted(str(p.relative_to(roots['fetchspec'])) for folder in ('profiles', 'rules')
                            for p in (roots['fetchspec'] / folder).glob('*.json'))] +
                    [('inresearch', ROOT, 'framework/tco_targets.json')],
    }
    files.update({key:generic_sources(key, root) for key,root in roots.items() if key not in files})
    metadata = {key: {**provenance(value, synced_at), 'checks':checks.get(key,{})} for key, value in files.items()}
    outputs = {'repo-content/infra.html': roots['infra'].joinpath('docs/infra-org-chart.html').read_text(),
               'repo-content/fetchspec.html': fetch_html}
    for key in ('infra', 'fetchspec'):
        outputs[key + 'repo.html'] = shell(NAMES[key], '<p>' + DESCRIPTIONS[key] + '</p>' +
            source_note(metadata[key]) + (infra_live(daily_report) if key == 'infra' else '') + f'<p><a href="/admin/repo-content/{key}.html">展开完整架构图</a></p>' +
            f'<iframe class="repo-frame" title="{NAMES[key]} 完整架构图" src="/admin/repo-content/{key}.html"></iframe>' +
            FIT_FRAME)
    body = ('<p>负责新闻发现与编辑，为研究站交付带来源、对象和目标行的事件卡。</p>' +
            source_note(metadata['inews']) +
            '<p class="repo-note">本页复用新闻仓库的架构声明；不读取生产数据库，实时计数未同步。</p>' +
            '<p><a href="https://inews.today/admin/reporg.html">新闻站实时架构与运行统计（使用新闻站账号）</a></p>' +
            '<h2>通道与执行机</h2>' + table(['通道', '职责', '执行机'],
                [(r['id'], r['what'], r['host']) for r in news['channels']]) +
            '<h2>处理流程</h2>' + flow(list(dict.fromkeys(r['phase'] for r in news['stages']))) +
            table(['环节', '职责', '进程与节奏', '实现'], [(r['title'], r['what'],
                r['process'] + ' · ' + r['cadence'], r['code']) for r in news['stages']]) +
            '<h2>与研究站的接口</h2>' + table(['接口', '方向', '载体', '状态与缺口'],
                [(r['id'], r['direction'], r['carrier'], r['status'] + '；' + r['todo']) for r in news['interfaces']]) +
            '<h2>交付与使用者</h2>' + table(['使用者', '入口', '用途'],
                [(r['title'], item[0], item[1]) for r in news['outputs'] for item in r['items']]) +
            '<h2>还没做完的</h2>' + table(['事项', '说明', '状态（源仓库声明）'],
                [(r['title'], r['detail'], r['status']) for r in news['open_items']]))
    outputs['inewsrepo.html'] = shell('inews.today', body)
    outputs['inresearchrepo.html'] = build_inresearch(metadata['inresearch'])
    for key,root in roots.items():
        if key not in ('inresearch','inews','fetchspec','infra'):
            outputs[key+'repo.html'] = build_generic(key,root,metadata[key])
    outputs['repos.html'] = shell('全部仓库组织框架',
        '<p>集中查看各仓库的职责、流程、交付接口与未完成事项。仅研究站管理员可见。</p>' +
        '<div class="repo-ecosystem" aria-label="仓库协作关系"><div class="repo-upstream">'
        '<div><div class="repo-card">inews.today · 新闻发现与编辑</div><p>↓ 事件卡与原件指针</p></div>'
        '<div><div class="repo-card">Fetchspec · 官方产品资料</div><p>↓ 原表与规格参数</p></div></div>'
        '<div class="repo-card"><strong>InResearch.ai · 接收、审阅、采用与研究成果</strong></div>'
        '<p>↑ 主机、网络与发布支持</p><div class="repo-card">infra · 基础设施</div></div>' +
        '<p class="repo-note">infra 为各仓库提供主机、网络和发布支持。架构由各仓库维护，研究站发布有来源校验的快照。</p>' +
        '<div class="repo-grid">' + ''.join(f'<article class="repo-card"><h2><a href="/admin/{key}repo.html">{name}</a></h2>'
            f'<p>{DESCRIPTIONS[key]}</p><p class="repo-note">最近更新：{display_time(synced_at)}</p>'+check_note(checks.get(key,{}))+'</article>' for key, name in NAMES.items()) + '</div>')
    outputs['repo-content/checks.json'] = json.dumps(checks, ensure_ascii=False, indent=2) + '\n'
    outputs['repo-content/infra-daily.json'] = json.dumps(daily_report or {}, ensure_ascii=False, indent=2) + '\n'
    outputs['repo-content/manifest.json'] = json.dumps(metadata, ensure_ascii=False, indent=2) + '\n'
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=ROOT.parent)
    parser.add_argument('--source-roots', type=Path, help='规范仓库名到独立工作树路径的 JSON 映射')
    parser.add_argument('--probe', action='store_true', help='只读检测公网入口与 GitHub 当前提交工作流')
    parser.add_argument('--daily-report', type=Path, help='infra daily_check 生成的六机检测 JSON')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--repo', choices=['inresearch'], help='只更新研究站页与其来源登记；不刷新邻接仓库快照')
    args = parser.parse_args()
    manifest = DEST / 'repo-content/manifest.json'
    synced_at = (json.loads(manifest.read_text())['infra']['synced_at']
                 if args.check and manifest.exists() else datetime.now(TZ).isoformat(timespec='seconds'))
    if args.repo:
        metadata=json.loads(manifest.read_text())
        synced_at=metadata['inresearch']['synced_at'] if args.check else datetime.now(TZ).isoformat(timespec='seconds')
        metadata['inresearch']={**provenance(inresearch_sources(),synced_at), 'checks':metadata['inresearch'].get('checks',{})}
        outputs={'inresearchrepo.html':build_inresearch(metadata['inresearch']),
                 'repo-content/manifest.json':json.dumps(metadata,ensure_ascii=False,indent=2)+'\n'}
    else:
        if args.check and args.probe:
            parser.error('--check 不重新发起检测')
        from repository_checks import collect
        workspace=args.workspace.resolve()
        source_roots={key:Path(path) for key,path in json.loads(args.source_roots.read_text()).items()} if args.source_roots else {}
        if args.probe:
            registry=json.loads((source_roots.get('infra',workspace/'infra')/'scripts/repositories.json').read_text())
            roots={key:ROOT if key=='inresearch' else workspace/name for key,name in CANONICAL.items()}
            roots.update(source_roots)
            checks=collect(roots,{key:registry[name] for key,name in CANONICAL.items()})
        else:
            saved=DEST/'repo-content/checks.json'
            checks=json.loads(saved.read_text()) if saved.exists() else {}
        report_path=args.daily_report or DEST/'repo-content/infra-daily.json'
        report=json.loads(report_path.read_text()) if report_path.exists() else {}
        if report:
            report={k:report[k] for k in ('started_at','summary','reach','warnings','collect_errors','changes','facts')}
            report['changes']={h:[{'key':x['key']} for x in items] for h,items in report['changes'].items()}
            report['facts']={h:{k:v for k,v in facts.items() if k.startswith(('容器 ','单元 ','launchd ','模型 '))} for h,facts in report['facts'].items()}
        outputs = build(workspace, synced_at, checks, report, source_roots)
    if args.check:
        stale = [p for p, content in outputs.items() if not (DEST / p).is_file() or (DEST / p).read_text() != content]
        if stale:
            raise SystemExit('架构快照过期：' + ', '.join(stale))
        print(f'{len(outputs)} repository page artifacts verified')
    else:
        for relative, content in outputs.items():
            path = DEST / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        print(f'{len(outputs)} repository page artifacts written')


if __name__ == '__main__':
    main()
