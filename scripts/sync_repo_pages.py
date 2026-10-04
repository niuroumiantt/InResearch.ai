#!/usr/bin/env python3
"""Publish deterministic, provenance-labelled repository architecture snapshots.

Run on the development machine, from the InResearch checkout:
  python3 scripts/sync_repo_pages.py --workspace /workspace
  python3 scripts/sync_repo_pages.py --workspace /workspace --check
No remote access, production database, credentials, or runtime counters are read.
"""
from __future__ import annotations

import argparse
from datetime import date
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
         'fetchspec': 'Fetchspec', 'infra': 'infra'}
DESCRIPTIONS = {'inresearch': '研究框架、证据采用、经济模型与成果展示',
                'inews': '新闻发现、编辑、事件卡供给与研究反馈',
                'fetchspec': '官方规格采集、参数整理与可核验交付',
                'infra': '主机、网络、部署与运行职责'}


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


def shell(title, body):
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
.repo-card h2{margin:0 0 8px}.repo-scroll{overflow-x:auto}.repo-wrap table{border-collapse:collapse;width:100%;font-size:13px}
.repo-ecosystem{max-width:760px;margin:28px auto;text-align:center}.repo-upstream{display:grid;grid-template-columns:1fr 1fr;gap:18px}.repo-ecosystem .repo-card{margin-bottom:12px}
.repo-wrap th,.repo-wrap td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--line)}
.repo-flow{display:flex;flex-wrap:wrap;gap:12px;list-style:none;padding:0}.repo-flow li{flex:1;min-width:150px}
.repo-flow li:not(:last-child)::after{content:' →';color:var(--accent)}
.repo-frame{width:100%;height:76vh;min-height:480px;border:1px solid var(--line);border-radius:var(--ui-radius);background:var(--card)}
.repo-provenance{margin:18px 0;font-size:12px}.repo-provenance code{overflow-wrap:anywhere}
@media(max-width:600px){.repo-wrap{padding:18px 12px 40px}.repo-wrap h1{font-size:23px}.repo-flow{display:block}.repo-flow li{margin:8px 0}.repo-frame{height:80vh}}
</style></head><body><inresearch-shell data-section="admin"></inresearch-shell>
<main class="repo-wrap"><nav class="repo-nav" aria-label="仓库架构">
<a href="/admin/repos.html">仓库总览</a>''' + ''.join(
        f'<a href="/admin/{key}repo.html">{escape(name)}</a>' for key, name in NAMES.items()
    ) + f'</nav><h1>{escape(title)}</h1>{body}</main></body></html>\n'


def provenance(files, synced_at):
    return {'synced_at': synced_at, 'kind': 'architecture_snapshot', 'sources': [
        {'repository': repo, 'path': relative,
         'sha256': hashlib.sha256((root / relative).read_bytes()).hexdigest()}
        for repo, root, relative in files]}


def source_note(meta):
    return (f'<p class="repo-note">同步日期：{meta["synced_at"]} · 架构快照；运行状态以原页所标观察时间为准。</p>'
            '<details class="repo-provenance"><summary>来源文件与内容校验</summary>' +
            table(['仓库', '文件', 'SHA-256'], [(s['repository'], s['path'], s['sha256'])
                                               for s in meta['sources']]) + '</details>')


def build(workspace, synced_at):
    roots = {'inresearch': ROOT, 'inews': workspace / 'inews.today',
             'fetchspec': workspace / 'fetchspec', 'infra': workspace / 'infra'}
    raw = subprocess.check_output(['node', '--no-warnings', 'scripts/export-reporg.mjs'],
                                  cwd=roots['inews'], text=True)
    news = json.loads(raw)
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'fetchspec.html'
        subprocess.run([sys.executable, 'scripts/reporg.py', '--upstream', str(ROOT),
                        '--output', str(out)], cwd=roots['fetchspec'], check=True, capture_output=True)
        fetch_html = out.read_text()
    files = {
        'inresearch': [('inresearch', ROOT, 'src/inresearch/README.md')],
        'inews': [('inews', roots['inews'], p) for p in
                  ('scripts/export-reporg.mjs', 'src/lib/pipeline-map.js')],
        'infra': [('infra', roots['infra'], 'docs/infra-org-chart.html')],
        'fetchspec': [('fetchspec', roots['fetchspec'], p) for p in
                     ['scripts/reporg.py', 'src/fetchspec/pipeline.py', 'docs/architecture.svg'] +
                     sorted(str(p.relative_to(roots['fetchspec'])) for folder in ('profiles', 'rules')
                            for p in (roots['fetchspec'] / folder).glob('*.json'))] +
                    [('inresearch', ROOT, 'framework/tco_targets.json')],
    }
    metadata = {key: provenance(value, synced_at) for key, value in files.items()}
    outputs = {'repo-content/infra.html': roots['infra'].joinpath('docs/infra-org-chart.html').read_text(),
               'repo-content/fetchspec.html': fetch_html}
    for key in ('infra', 'fetchspec'):
        outputs[key + 'repo.html'] = shell(NAMES[key], '<p>' + DESCRIPTIONS[key] + '</p>' +
            source_note(metadata[key]) + f'<p><a href="/admin/repo-content/{key}.html">展开完整架构图</a></p>' +
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
    readme = (ROOT / 'src/inresearch/README.md').read_text()
    rows = [[p.strip().replace('`', '') for p in line.strip('|').split('|')]
            for line in readme.splitlines() if line.startswith('| ')][1:]
    outputs['inresearchrepo.html'] = shell('InResearch.ai',
        '<p>研究框架与目标 → 接收原件和事件 → 阅读与审阅 → 证据采用 → 模型与报告。</p>' +
        source_note(metadata['inresearch']) + flow(['目标与资料接收', '阅读与证据审阅', '事实与经济模型', '网站与研究成果']) +
        '<h2>程序职责</h2>' + table(['模块', '责任与主要实现'], rows) +
        '<h2>运行边界与未完成</h2>' + ''.join(f'<p>{escape(line)}</p>' for line in readme.splitlines()
            if line and not line.startswith(('#', '|'))))
    outputs['repos.html'] = shell('为研究站协作的仓库',
        '<p>集中查看各仓库的职责、流程、交付接口与未完成事项。仅研究站管理员可见。</p>' +
        '<div class="repo-ecosystem" aria-label="仓库协作关系"><div class="repo-upstream">'
        '<div><div class="repo-card">inews.today · 新闻发现与编辑</div><p>↓ 事件卡与原件指针</p></div>'
        '<div><div class="repo-card">Fetchspec · 官方产品资料</div><p>↓ 原表与规格参数</p></div></div>'
        '<div class="repo-card"><strong>InResearch.ai · 接收、审阅、采用与研究成果</strong></div>'
        '<p>↑ 主机、网络与发布支持</p><div class="repo-card">infra · 基础设施</div></div>' +
        '<p class="repo-note">infra 为各仓库提供主机、网络和发布支持。架构由各仓库维护，研究站发布有来源校验的快照。</p>' +
        '<div class="repo-grid">' + ''.join(f'<article class="repo-card"><h2><a href="/admin/{key}repo.html">{name}</a></h2>'
            f'<p>{DESCRIPTIONS[key]}</p><p class="repo-note">同步日期：{synced_at}</p></article>' for key, name in NAMES.items()) + '</div>')
    outputs['repo-content/manifest.json'] = json.dumps(metadata, ensure_ascii=False, indent=2) + '\n'
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=ROOT.parent)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = DEST / 'repo-content/manifest.json'
    synced_at = (json.loads(manifest.read_text())['infra']['synced_at']
                 if args.check and manifest.exists() else date.today().isoformat())
    outputs = build(args.workspace.resolve(), synced_at)
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
