#!/usr/bin/env python3
"""Export the real ledger UI with frozen, read-only local inputs; no server or login."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from inresearch.knowledge import site_model_bridge
from inresearch.interfaces import public


def export(root, output, site_id):
    root, output = Path(root), Path(output)
    projects = json.loads((root/'data/projects.json').read_text())['records']
    bridge = site_model_bridge.project(root, projects, site_id)
    if not bridge:
        raise ValueError('site has no model bridge')
    site = next(p for p in projects if p['site_id'] == site_id)
    data = {'/api/industry?site='+site_id: {'detail': {'name': site['name'], 'model_bridge': bridge}},
            '/data/datacenter_model.json': public.customer_model(json.loads((root/'data/datacenter_model.json').read_text())),
            '/data/prices.json': public.customer_prices(json.loads((root/'data/prices.json').read_text()))}
    page = (root/'web/pages/ledger.html').read_text()
    page = re.sub(r'<script\b[^>]*src=[^>]*></script>', '', page)
    page = re.sub(r'<link\b[^>]*>', '', page)
    page = page.replace('<inresearch-shell data-section="ledger"></inresearch-shell>', '')
    css = (root/'web/themes/site-skin.css').read_text()
    css = re.sub(r'url\([^)]*\)', 'none', css)
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    # Same page and component as the app; only the transport is replaced by frozen data.
    transport = """
const frozen=%s;
window.fetch=async url=>{const key=String(url);if(!(key in frozen))throw Error('离线预览没有此资源：'+key);return {ok:true,json:async()=>structuredClone(frozen[key])};};
const local=new URL(location.href);local.searchParams.set('site',%s);local.searchParams.set('scope',%s);local.searchParams.set('view','basis');history.replaceState({},'',local);
document.addEventListener('click',e=>{const a=e.target.closest('a');if(a&&a.getAttribute('href')?.startsWith('/')&&!a.closest('#column-tabs'))e.preventDefault();});
document.querySelectorAll('a').forEach(a=>{if(!a.href.startsWith('http'))a.addEventListener('click',e=>{if(!a.closest('#column-tabs'))e.preventDefault();});});
""" % (payload, json.dumps(site_id), json.dumps(bridge['scope']['id']))
    banner = '<p style="padding:12px 18px;border-bottom:1px solid var(--ui-line)">本地离线预览 · 未上线 · 使用冻结复核版本 · 请先确认生成情景。页面与导出均不修改园区资料。</p>'
    page = page.replace('</head>', '<style>'+css+'</style></head>').replace('<body>', '<body>'+banner)
    component = (root/'web/components/datacenter-model.js').read_text().replace('</script', '<\\/script')
    page = page.replace('</body>', '<script>'+transport+'</script><script>'+component+'</script></body>')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', default='us-tx-abilene')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(export(ROOT, args.output, args.site))
