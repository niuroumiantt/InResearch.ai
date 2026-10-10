#!/usr/bin/env python3
"""Conservative Git-tree CI selection and its always-reported acceptance gate."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

FULL_SUITES = ['core_a', 'core_b', 'core_c', 'server_assembly', 'rack_assembly',
               'rack_exploded', 'scene_atlas', 'campus_overview:views',
               'campus_overview:geometry', 'campus_overview:navigation',
               'campus_overview:lifecycle', 'campus_exploded:views',
               'campus_exploded:geometry', 'campus_exploded:whole',
               'campus_exploded:navigation', 'campus_exploded:lifecycle', 'model_assets']
IMAGES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg'}
DERIVED = {'framework/repository_manifest.json', 'docs/REPOSITORY_REGISTER.md'}
# A page absent here needs a full run, even if only its visible text changed.
PAGES = {'index': 'industry', 'company': 'company_page', 'company-home': 'company_window',
         'company-products': 'company_catalog_map', 'product-catalog': 'product_catalog',
         'compute-catalog': 'compute_catalog', 'supply': 'supply', 'ops': 'ops_dashboard',
         'rack-exploded': 'rack_exploded', 'rack-atlas': 'rack_atlas',
         'chip-atlas': 'chip_atlas', 'server-plan': 'server_plan',
         'campus-plan': 'campus_plan', 'cross-scale-atlas': 'scale_atlas'}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def blob(root, revision, path):
    return git(root, 'show', revision+':'+path)


class Structure(HTMLParser):
    """Only visible text may vary; attributes, scripts, styles and comments stay exact."""
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.tokens, self.active = [], []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tokens.append(('open', self.get_starttag_text()))
        if tag in {'script', 'style', 'template'}:
            self.active.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tokens.append(('empty', self.get_starttag_text()))

    def handle_endtag(self, tag):
        self.tokens.append(('close', tag))
        if self.active and tag == self.active[-1]:
            self.active.pop()

    def handle_data(self, data):
        if self.active:
            self.tokens.append(('code', data))

    def handle_comment(self, data):
        self.tokens.append(('comment', data))

    def handle_decl(self, data):
        self.tokens.append(('decl', data))

    def handle_entityref(self, name):
        self.handle_data('&'+name+';')

    def handle_charref(self, name):
        self.handle_data('&#'+name+';')


def metadata_only(path, before, after, changed):
    a, b = json.loads(before), json.loads(after)
    if path.endswith('current_state.json'):
        for item in (a, b):
            for key in ('version', 'updated', 'effective_at'):
                item.pop(key, None)
    else:
        for item in (a, b):
            for key in ('version', 'reviewed_at'):
                item.pop(key, None)
        old, new = a.pop('reviewed_files'), b.pop('reviewed_files')
        if old.keys() != new.keys():
            return False
        if any(old[p] != new[p] and p not in changed for p in old):
            return False
    return a == b


def select(root, base, head, event='pull_request', force=False):
    def full(reason, changes=()):
        return {'mode': 'full', 'reason': reason, 'base': base, 'head': head,
                'files': list(changes), 'suites': FULL_SUITES, 'storage': True}
    if force or event in {'schedule', 'workflow_dispatch'}:
        return full('scheduled or explicitly requested full regression')
    try:
        if not re.fullmatch('[0-9a-f]{40}', base) or not re.fullmatch('[0-9a-f]{40}', head):
            return full('missing or invalid comparison SHA')
        git(root, 'cat-file', '-e', base+'^{commit}')
        git(root, 'cat-file', '-e', head+'^{commit}')
        raw = git(root, 'diff', '--name-status', '--no-renames', '-z', base, head).decode().split('\0')
        changes = [{'status': raw[i], 'path': raw[i+1]} for i in range(0, len(raw)-1, 2)]
        if not changes:
            return full('empty comparison cannot prove a content-only change')
        state = json.loads(blob(root, base, 'framework/current_state.json'))
        protected = {p['source'] for p in state['policies'] if p['status'] == 'current'}
        protected.update(state.get('operational_guides', []))
        protected.update(state['entrypoints'])
        suites, changed = set(), {r['path'] for r in changes}
        for row in changes:
            path, status = row['path'], row['status']
            if status not in {'A', 'M'}:
                return full('deletion or unsupported change: '+path, changes)
            # Symlinks/submodules are never treated as ordinary content.
            mode = git(root, 'ls-tree', head, '--', path).decode().split()[0]
            if mode != '100644':
                return full('non-regular content: '+path, changes)
            if path in DERIVED:
                continue  # Always revalidated by governance --check, never trusted as proof.
            if path in {'framework/current_state.json', 'framework/verification_contract.json'}:
                if status == 'M' and metadata_only(path, blob(root, base, path), blob(root, head, path), changed):
                    continue
                return full('rules or acceptance contract changed: '+path, changes)
            if path in protected or path in {'AGENTS.md', 'CLAUDE.md', 'framework/CURRENT.md'}:
                return full('normative instructions changed: '+path, changes)
            suffix = Path(path).suffix.lower()
            if suffix == '.md' and (path.startswith(('docs/', 'research/', 'outputs/')) or path == 'README.md'):
                continue
            if suffix in IMAGES and path.startswith(('docs/', 'research/', 'outputs/', 'web/assets/')):
                if path.startswith('web/assets/technical-atlas/'):
                    suites.add('technical_atlas')
                elif path.startswith(('web/assets/models/', 'web/assets/textures/')):
                    suites.add('model_assets')
                elif path.startswith('web/'):
                    consumers = git(root, 'ls-tree', '-r', '--name-only', head, '--', 'web').decode().splitlines()
                    found = False
                    for consumer in consumers:
                        if Path(consumer).suffix not in {'.js', '.css', '.html', '.json'}:
                            continue
                        if Path(path).name.encode() not in blob(root, head, consumer):
                            continue
                        suite = PAGES.get(Path(consumer).stem) if Path(consumer).parent == Path('web/pages') else None
                        if not suite:
                            return full('shared or unmapped image consumer: '+consumer, changes)
                        found = True
                        suites.add(suite)
                    if not found:
                        return full('cannot establish web image consumers: '+path, changes)
                continue
            if status == 'M' and Path(path).parent == Path('web/pages') and suffix == '.html':
                suite = PAGES.get(Path(path).stem)
                if suite and Structure(blob(root, base, path).decode()).tokens == Structure(blob(root, head, path).decode()).tokens:
                    suites.add(suite)
                    continue
            return full('implementation, structure, data, dependency or unknown path: '+path, changes)
        return {'mode': 'targeted' if suites else 'content', 'reason': 'all changed paths have bounded content impact',
                'base': base, 'head': head, 'files': changes, 'suites': sorted(suites), 'storage': False}
    except (subprocess.CalledProcessError, UnicodeError, ValueError, KeyError, IndexError, TypeError):
        return full('comparison or classification failed; full regression required')


def links(text):
    text = re.sub(r'```.*?```|~~~.*?~~~', '', text, flags=re.S)
    return set(re.findall(r'!?\[[^\]\n]*\]\(<?([^\s)>]+)>?(?:\s+[^)]*)?\)', text))


def check_content(root, plan):
    from PIL import Image
    from xml.etree import ElementTree as ET
    checked = []
    for row in plan['files']:
        path = row['path']
        if row['status'] not in {'A', 'M'} or (root/path).is_symlink():
            continue
        if Path(path).suffix.lower() not in IMAGES | {'.md', '.html'}:
            continue
        if path in DERIVED or path.startswith('framework/'):
            continue
        raw = (root/path).read_bytes()
        suffix = Path(path).suffix.lower()
        if suffix == '.svg':
            tree = ET.fromstring(raw)
            if tree.tag.split('}')[-1] != 'svg':
                raise ValueError('invalid SVG: '+path)
            for e in tree.iter():
                if e.tag.split('}')[-1].lower() in {'script', 'foreignobject'} or any(k.lower().startswith('on') for k in e.attrib):
                    raise ValueError('active SVG requires code review/full CI: '+path)
        elif suffix in IMAGES:
            with Image.open(root/path) as image:
                image.verify()
            with Image.open(root/path) as image:
                for frame in range(getattr(image, 'n_frames', 1)):
                    image.seek(frame)
                    image.load()
        elif suffix in {'.md', '.html'}:
            text = raw.decode('utf-8')
            if '\0' in text:
                raise ValueError('NUL in text: '+path)
            if suffix == '.md':
                old = blob(root, plan['base'], path).decode('utf-8') if row['status'] == 'M' else ''
                for link in links(text)-links(old):
                    url = urlsplit(link)
                    if url.scheme or url.netloc or not url.path or url.path.startswith('/'):
                        continue
                    target = ((root/path).parent/unquote(url.path)).resolve()
                    if not target.is_relative_to(root.resolve()) or not target.exists():
                        raise ValueError('new local reference missing: '+path+' -> '+link)
        checked.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    return checked


def gate(plan, results):
    expected = {'scope': 'success', 'validate': 'success',
                'browser': 'success' if plan['suites'] else 'skipped',
                'storage-container': 'success' if plan['storage'] else 'skipped'}
    if plan['mode'] not in {'full', 'targeted', 'content'}:
        return False
    if plan['mode'] == 'full' and (plan['suites'] != FULL_SUITES or not plan['storage']):
        return False
    if plan['mode'] == 'targeted' and (not plan['suites'] or plan['storage']):
        return False
    if plan['mode'] == 'content' and (plan['suites'] or plan['storage']):
        return False
    return all(results.get(k, {}).get('result') == v for k, v in expected.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'check', 'gate'])
    parser.add_argument('--base', default='')
    parser.add_argument('--head', default='')
    parser.add_argument('--event', default='pull_request')
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == 'plan':
        plan = select(root, args.base, args.head, args.event, args.full)
        encoded = json.dumps(plan, ensure_ascii=True, separators=(',', ':'))
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write('plan='+encoded+'\n')
                out.write('suites='+json.dumps(plan['suites'])+'\n')
                out.write('browser='+str(bool(plan['suites'])).lower()+'\n')
                out.write('full='+str(plan['mode'] == 'full').lower()+'\n')
        print(encoded)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
                out.write('CI scope: **'+plan['mode']+'**; '+str(len(plan['files']))+' changed paths; '+str(len(plan['suites']))+' browser suites.\n\n'+plan['reason']+'\n')
    else:
        plan = json.loads(os.environ['CI_PLAN'])
        if args.command == 'check':
            print(json.dumps(check_content(root, plan), ensure_ascii=False))
        elif not gate(plan, json.loads(os.environ['CI_RESULTS'])):
            raise SystemExit('Selected CI checks did not all succeed; merge blocked')
        else:
            print('All checks selected by the impact plan succeeded')


if __name__ == '__main__':
    main()
