#!/usr/bin/env python3
"""Conservative Git-tree CI selection and its always-reported acceptance gate."""
import argparse
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

FULL_SUITES = ['core_a', 'core_b', 'core_c', 'technical_atlas', 'chip_package', 'server_assembly', 'rack_assembly',
               'rack_exploded', 'scene_atlas', 'campus_overview:views',
               'campus_overview:geometry', 'campus_overview:navigation',
               'campus_overview:lifecycle', 'campus_exploded:views',
               'campus_exploded:geometry', 'campus_exploded:whole',
               'campus_exploded:navigation', 'campus_exploded:lifecycle', 'model_assets']
IMAGES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg'}
DERIVED = {'framework/repository_manifest.json', 'docs/REPOSITORY_REGISTER.md'}
RESEARCH_PATH = 'data/research_knowledge.json'
PROJECT_PATH = 'data/projects.json'
OBJECT_PATH = 'data/object_observations.json'
RESEARCH_SUITES = ['research']
RESEARCH_TEST_PATTERNS = ('test_research*.py', 'test_public_reader.py',
                          'test_publish_reader.py', 'test_verification_contract.py',
                          'test_ci_scope.py', 'test_site_*.py', 'test_project_review.py',
                          'test_targeted_research.py', 'test_industry.py',
                          'test_object_review.py', 'test_fetchspec_receive.py', 'test_source_statements.py')
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


def active_svg(raw):
    from xml.etree import ElementTree as ET
    return any(e.tag.split('}')[-1].lower() in {'script', 'foreignobject'}
               or any(k.lower().startswith('on') or str(v).strip().lower().startswith('javascript:')
                      for k, v in e.attrib.items()) for e in ET.fromstring(raw).iter())


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('non-finite JSON value: '+value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def research_append_only(before, after):
    """Only new bounded sources; preserve every old JSON value and its type.

    Shape selection is not source/adoption approval. The selected CI jobs
    continue validating the support chain and publication regression.
    """

    old, new = map(strict_json, (before, after))
    sections = {'documents', 'evidence', 'statements'}
    keys = sections | {'version', 'note', 'answers'}
    if not isinstance(old, dict) or not isinstance(new, dict) or set(old) != keys or set(new) != keys:
        return False
    if old['version'] != '2.0.0':
        return False
    if any(canonical(old[k]) != canonical(new[k]) for k in keys-sections):
        return False
    added = 0
    for name in sections:
        a, b = old[name], new[name]
        if not isinstance(a, list) or not isinstance(b, list) or len(b) < len(a):
            return False
        for rows in (a, b):
            if any(not isinstance(r, dict) or not isinstance(r.get('id'), str)
                   or not r['id'].strip() for r in rows):
                return False
            if len({r['id'] for r in rows}) != len(rows):
                return False
        if canonical(a) != canonical(b[:len(a)]):
            return False
        for row in b[len(a):]:
            if name == 'statements' and (row.get('partial_support_only') is not True
                                         or 'question_id' in row):
                return False
            if row.get('status') in {'withdrawn', 'rejected', 'superseded'} or 'object_mapping_review' in row:
                return False
            for declaration in (row, row.get('review', {})):
                if (not isinstance(declaration, dict)
                        or declaration.get('replaces_record_ids', []) != []
                        or declaration.get('supersedes', []) != []
                        or declaration.get('relaxes_distribution', False) is not False):
                    return False
        added += len(b)-len(a)
    return added > 0


def source_registration_append_valid(row, site_id):
    """Shape proof only; never a factual verdict or research-review grant."""
    if not isinstance(row, dict) or type(row.get('schema_version')) is not int or row['schema_version'] != 3:
        return False
    registration = row.get('registration') or {}
    adoption = row.get('adoption') or {}
    if not isinstance(adoption, dict):
        return False
    fields, versions, refs = row.get('fields'), row.get('source_versions'), adoption.get('document_refs')
    if (not isinstance(registration, dict) or registration.get('status') != 'unverified'
            or not isinstance(registration.get('registered_by'), str) or not registration['registered_by']
            or registration.get('at') != row.get('recorded_at')
            or adoption.get('registration_id') != row.get('id') or adoption.get('source_kind') != 'source_statement'
            or adoption.get('target_ids') != [] or 'review' in adoption
            or any(k in row for k in ('reviewed_at','revision','owner_decision','supersedes','replaces_observation_ids'))
            or not isinstance(fields, dict) or not fields
            or not isinstance(versions,list) or len(versions)!=1 or not isinstance(refs,list) or len(refs)!=1
            or not isinstance(versions[0],dict) or not isinstance(refs[0],dict)):
        return False
    binding = adoption.get('object_binding')
    if binding != {'version':1, 'site_id':site_id, 'fields':sorted(fields), 'scope':row.get('scope')}:
        return False
    sha = versions[0].get('source_sha256')
    if (not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha)
            or refs[0].get('source_sha256') != sha or adoption.get('source_id') != sha
            or not re.fullmatch('[0-9a-f]{64}',str(adoption.get('source_version','')))):
        return False
    source = {'sha256':sha, 'url':refs[0].get('source_url'), 'archive':refs[0].get('archive'),
              'first_received_at':versions[0].get('first_received_at')}
    return object_source_reference(source)


def initial_site_append_valid(project):
    identity=project.get('identity_registration')
    required={'version','site_id','name','native_name','country','region','location','basis'}
    allowed=required|{'province','city','district','street_address'}
    if (not isinstance(identity,dict) or not required <= identity.keys() or set(identity)-allowed
            or type(identity['version']) is not int or identity['version']!=1
            or any(not isinstance(v,str) or not v.strip() for k,v in identity.items() if k!='version')
            or len(identity['country'])!=2 or not identity['country'].isascii() or not identity['country'].isupper()
            or not identity['country'].isalpha() or len(identity['native_name'].strip())<4
            or project.get('duplicate_of') or project.get('identity_scope') in ('cluster','portfolio')
            or 'portfolio' in identity['site_id']
            or any(project.get(k)!=v for k,v in identity.items() if k not in ('version','native_name','basis'))
            or any(project.get(k) not in (None,{}) for k in ('capacity_it_mw','capacity_planned_it_mw','capacity_facility_mw','capacity_it_mw_by_status','capacity_assessment'))):
        return False
    observations=project.get('observations')
    if not isinstance(observations,list) or not observations or len(observations)>500:
        return False
    if all(isinstance(row,dict) and row.get('schema_version')==3 for row in observations):
        return (project.get('verified_date') is None
                and all(source_registration_append_valid(row,project['site_id']) for row in observations)
                and observations[0]['fields'].get('name')==project['name']
                and observations[0]['fields'].get('status')==project.get('status'))
    for row in observations:
        adoption=row.get('adoption',{}) if isinstance(row,dict) else {}
        if (not isinstance(row,dict) or row.get('schema_version')!=2 or not row.get('fields')
                or not row.get('source_versions') or not adoption or adoption.get('target_ids')!=[]
                or not adoption.get('object_binding') or not adoption.get('assertions')
                or adoption.get('review',{}).get('decision')!='adopted'
                or any(k in row for k in ('replaces_observation_ids','owner_decision','supersedes','revision'))):
            return False
    return (observations[0]['fields'].get('name')==project.get('name')
            and observations[0]['fields'].get('status')==project.get('status'))


def project_observations_append_only(before, after):
    """Bounded observation appends and stable initial campuses, never revisions.

    All baseline fields, source records and old observations remain byte-value
    equivalent. New campuses require a frozen identity with targetless v2
    reviewed observations or v3 unverified source registrations. Backfills and
    revisions stay full. Strict validation remains independent of CI scope;
    ordinary registrations never require or grant C3 research adoption.
    """
    old, new = map(strict_json, (before, after))
    if not isinstance(old, dict) or not isinstance(new, dict) or set(old) != set(new):
        return False
    if 'records' not in old or any(canonical(old[k]) != canonical(new[k]) for k in old if k != 'records'):
        return False
    a, b = old['records'], new['records']
    if not isinstance(a, list) or not isinstance(b, list) or not len(a) <= len(b) <= len(a)+100:
        return False
    identities = set()
    added = 0
    for previous, current in zip(a, b):
        if not isinstance(previous, dict) or not isinstance(current, dict):
            return False
        site = previous.get('site_id')
        if not isinstance(site, str) or not site or site in identities:
            return False
        identities.add(site)
        if 'observations' in previous and 'observations' not in current:
            return False
        if canonical({k:v for k,v in previous.items() if k != 'observations'}) != canonical({k:v for k,v in current.items() if k != 'observations'}):
            return False
        prior, following = previous.get('observations', []), current.get('observations', [])
        if not isinstance(prior, list) or not isinstance(following, list) or len(following) < len(prior):
            return False
        if canonical(prior) != canonical(following[:len(prior)]):
            return False
        ids = [r.get('id') for r in following if isinstance(r, dict)]
        if len(ids) != len(following) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            return False
        for observation in following[len(prior):]:
            if (type(observation.get('schema_version')) is not int or observation['schema_version'] not in (2,3) or not observation.get('fields')
                    or not observation.get('source_versions') or not observation.get('adoption')
                    or any(k in observation for k in ('replaces_observation_ids', 'owner_decision', 'supersedes', 'revision'))):
                return False
            if observation['schema_version']==3 and not source_registration_append_valid(observation,current['site_id']):
                return False
        added += len(following)-len(prior)
    names={str(name).casefold() for p in a for name in [p.get('name'),*(p.get('aliases') or [])] if name}
    for project in b[len(a):]:
        if not isinstance(project,dict) or not initial_site_append_valid(project):
            return False
        incoming_names={str(n).casefold() for n in [project['name'],*(project.get('aliases') or [])]}
        if project.get('site_id') in identities or incoming_names & names:
            return False
        identities.add(project['site_id']);names.update(incoming_names)
        added += len(project['observations'])
    return added > 0


def object_source_reference(source):
    if isinstance(source.get('url'), str) and source['url'].startswith('https://'):
        return True
    archive = source.get('archive')
    if (source.get('url') is not None or not isinstance(archive, dict)
            or set(archive) != {'kind', 'doc_id', 'receipts'}
            or archive['kind'] != 'catalog_import' or archive['doc_id'] != 'doc-'+source.get('sha256', '')
            or not isinstance(archive['receipts'], list) or not archive['receipts']):
        return False
    try:
        ids=[];dates=[]
        for row in archive['receipts']:
            if (set(row) != {'id', 'source_key_sha256', 'received_at'} or type(row['id']) != int or row['id'] <= 0
                    or not re.fullmatch('[0-9a-f]{64}', row['source_key_sha256'])): return False
            date=datetime.fromisoformat(row['received_at'].replace('Z','+00:00'))
            if date.tzinfo is None: return False
            ids.append(row['id']);dates.append((date,row['received_at']))
        return len(ids)==len(set(ids)) and source.get('first_received_at')==min(dates)[1]
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def object_observations_append_only(before, after):
    """Prove bounded append-only observations; adoption still requires source/C3."""
    old, new = map(strict_json, (before, after))
    if (not isinstance(old, dict) or not isinstance(new, dict)
            or set(old) != {'version', 'objects', 'records'} or set(new) != set(old)
            or type(old['version']) is not int or old['version'] != 1
            or canonical(old['version']) != canonical(new['version'])):
        return False
    a, b = old['records'], new['records']
    previous, following = old['objects'], new['objects']
    if (not isinstance(a, list) or not isinstance(b, list) or not 1 <= len(b)-len(a) <= 500
            or not isinstance(previous, dict) or not isinstance(following, dict)
            or any(k not in following or canonical(v) != canonical(following[k]) for k,v in previous.items())
            or canonical(a) != canonical(b[:len(a)])):
        return False
    identities = {'company': {'company_id'}, 'product': {'company_id','model','version'},
                  'statistic': {'publisher','series','geography','definition'},
                  'quote': {'company_id','configuration','market','currency','billing_basis'}}
    for key, obj in following.items():
        if (not isinstance(obj, dict) or set(obj) != {'id','type','identity','name'}
                or obj.get('type') not in identities or not isinstance(obj.get('identity'),dict)
                or set(obj['identity']) != identities[obj['type']]
                or any(not isinstance(v,str) or not v.strip() for v in obj['identity'].values())
                or not isinstance(obj.get('name'),str) or not obj['name'].strip()):
            return False
        raw=json.dumps({'type':obj['type'],'identity':obj['identity']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        if key != obj['id'] or key != obj['type']+':'+hashlib.sha256(raw).hexdigest()[:32]:
            return False
    ids=[r.get('id') for r in b if isinstance(r,dict)]
    if len(ids)!=len(b) or any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):
        return False
    added=b[len(a):]
    if set(following)-set(previous) != {r.get('object_id') for r in added}-set(previous):
        return False
    for row in added:
        source, review = row.get('source'), row.get('review')
        if (row.get('object_id') not in following or row.get('target_ids') != []
                or any(k in row for k in ('revision','replaces_record_ids','supersedes','owner_decision','relaxes_distribution'))
                or row.get('status') in {'withdrawn','superseded','rejected'}
                or not isinstance(source,dict) or not source.get('quote') or not source.get('locator')
                or any(not re.fullmatch('[0-9a-f]{64}',str(source.get(k,''))) for k in ('sha256','context_sha256'))
                or not object_source_reference(source)
                or not isinstance(review,dict) or review.get('decision') != 'adopted'
                or any(k in review for k in ('supersedes','replaces_record_ids','relaxes_distribution'))):
            return False
    return True


def research_test_suite(root):
    """Select the fixed research/adoption/HTTP/publication regression surface."""
    import sys
    import unittest
    root = Path(root)
    directory = root/'tests/unit'
    # Fail if a selected entry disappears; unittest discovery alone accepts zero.
    if any(not list(directory.glob(pattern)) for pattern in RESEARCH_TEST_PATTERNS):
        raise ValueError('missing research regression test entry')
    sys.path.insert(0, str(root))
    suite = unittest.TestSuite()
    for pattern in RESEARCH_TEST_PATTERNS:
        selected = unittest.TestLoader().discover(str(directory), pattern=pattern)
        if not selected.countTestCases():
            raise ValueError('empty research regression test entry: '+pattern)
        suite.addTests(selected)
    return suite


def select(root, base, head, event='pull_request', force=False):
    def full(reason, changes=()):
        return {'mode': 'full', 'reason': reason, 'base': base, 'head': head,
                'files': list(changes), 'suites': FULL_SUITES, 'storage': True, 'assets': True}
    if force or event in {'schedule', 'workflow_dispatch'}:
        return full('scheduled or explicitly requested full regression')
    changes = ()
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
        suites, changed, research = set(), {r['path'] for r in changes}, False
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
            if path == RESEARCH_PATH:
                if status != 'M' or not research_append_only(blob(root, base, path), blob(root, head, path)):
                    return full('research edit, schema, answer or non-additive change: '+path, changes)
                research = True
                suites.update(RESEARCH_SUITES)
                continue
            if path == PROJECT_PATH:
                if status != 'M' or not project_observations_append_only(blob(root, base, path), blob(root, head, path)):
                    return full('project identity, baseline, revision or non-additive change: '+path, changes)
                research = True
                suites.update([*RESEARCH_SUITES, 'industry'])
                continue
            if path == OBJECT_PATH:
                if status != 'M' or not object_observations_append_only(blob(root, base, path), blob(root, head, path)):
                    return full('object identity, revision, schema or non-additive change: '+path, changes)
                research = True
                suites.update([*RESEARCH_SUITES, 'industry'])
                continue
            suffix = Path(path).suffix.lower()
            if suffix == '.md' and (path.startswith(('docs/', 'research/', 'outputs/')) or path == 'README.md'):
                continue
            if suffix in IMAGES and path.startswith(('docs/', 'research/', 'outputs/', 'web/assets/')):
                if suffix == '.svg' and active_svg(blob(root, head, path)):
                    return full('SVG contains active code or embedded HTML: '+path, changes)
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
        return {'mode': 'research' if research else 'targeted' if suites else 'content',
                'reason': 'append-only bounded research with related checks' if research else 'all changed paths have bounded content impact',
                'base': base, 'head': head, 'files': changes, 'suites': sorted(suites), 'storage': False,
                'assets': bool(suites-set(RESEARCH_SUITES))}
    except (subprocess.CalledProcessError, UnicodeError, ValueError, KeyError, IndexError, TypeError,
            __import__('xml.etree.ElementTree', fromlist=['ParseError']).ParseError):
        return full('comparison or classification failed; full regression required', changes)


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
            if plan['mode'] != 'full' and active_svg(raw):
                raise ValueError('active SVG was incorrectly classified as content: '+path)
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
    if plan['mode'] not in {'full', 'targeted', 'content', 'research'}:
        return False
    if plan['mode'] == 'full' and (plan['suites'] != FULL_SUITES or not plan['storage']):
        return False
    if plan['mode'] == 'targeted' and (not plan['suites'] or plan['storage']):
        return False
    if plan['mode'] == 'content' and (plan['suites'] or plan['storage']):
        return False
    if plan['mode'] == 'research' and (not set(RESEARCH_SUITES) <= set(plan['suites']) or plan['storage']):
        return False
    if plan['mode'] == 'research' and any(r.get('path') in {PROJECT_PATH, OBJECT_PATH} for r in plan.get('files', [])) and 'industry' not in plan['suites']:
        return False
    return all(results.get(k, {}).get('result') == v for k, v in expected.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'check', 'gate', 'research-tests'])
    parser.add_argument('--base', default='')
    parser.add_argument('--head', default='')
    parser.add_argument('--event', default='pull_request')
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == 'research-tests':
        import unittest
        if not unittest.TextTestRunner().run(research_test_suite(root)).wasSuccessful():
            raise SystemExit('Research regression failed; merge blocked')
        return
    if args.command == 'plan':
        plan = select(root, args.base, args.head, args.event, args.full)
        encoded = json.dumps(plan, ensure_ascii=True, separators=(',', ':'))
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write('plan='+encoded+'\n')
                out.write('suites='+json.dumps(plan['suites'])+'\n')
                out.write('browser='+str(bool(plan['suites'])).lower()+'\n')
                out.write('full='+str(plan['mode'] == 'full').lower()+'\n')
                out.write('research='+str(plan['mode'] == 'research').lower()+'\n')
                out.write('assets='+str(plan['assets']).lower()+'\n')
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
