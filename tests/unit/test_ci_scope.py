"""Behavioral regression for content routing, complete Git diffs and gate failures."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import ci_scope as ci
from inresearch.workflow import research_publish as publisher


class CiScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'ci@example.test')
        self.git('config', 'user.name', 'CI fixture')
        self.write('framework/current_state.json', json.dumps({'version':'1','entrypoints':[], 'policies':[], 'operational_guides':[]}))
        self.write('framework/verification_contract.json', json.dumps({'version':'1','reviewed_files':{'docs/a.md':'old'},'policies':[]}))
        self.write('docs/a.md', 'Old text\n')
        self.write('web/pages/index.html', '<html><body><h1>Hello</h1><script>const x=1;</script></body></html>')
        self.write('web/assets/technical-atlas/test.svg', '<svg xmlns="http://www.w3.org/2000/svg"><text>old</text></svg>')
        self.knowledge = {'version':'2.0.0', 'note':'Curated source records',
                          'documents':[{'id':'doc:old', 'metadata':{'count':1, 'enabled':False}}],
                          'evidence':[{'id':'evidence:old', 'document_id':'doc:old'}],
                          'statements':[{'id':'statement:old', 'partial_support_only':True}],
                          'answers':[]}
        self.write(ci.RESEARCH_PATH, json.dumps(self.knowledge))
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE).decode().strip()

    def write(self, path, value):
        p = self.root/path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value if isinstance(value, bytes) else value.encode())

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def plan(self):
        return ci.select(self.root, self.base, self.commit())

    def appended_research(self):
        result = copy.deepcopy(self.knowledge)
        result['documents'].append({'id':'doc:new', 'status':'candidate'})
        result['evidence'].append({'id':'evidence:new', 'document_id':'doc:new'})
        result['statements'].append({'id':'statement:new', 'partial_support_only':True,
                                     'evidence_ids':['evidence:new']})
        return result

    def test_append_only_research_runs_related_pages_without_visual_assets_or_storage(self):
        self.write(ci.RESEARCH_PATH, json.dumps(self.appended_research()))
        self.write('framework/repository_manifest.json', '{}')
        self.write('docs/REPOSITORY_REGISTER.md', 'derived')
        plan = self.plan()
        self.assertEqual((plan['mode'],plan['suites'],plan['storage'],plan['assets']),
                         ('research',['research'],False,False))
        self.assertFalse(set(plan['suites']) & {'core_a','core_b','core_c','model_assets',
                                              'rack_assembly','server_assembly','scene_atlas'})
        # Sources/evidence may be appended before a statement exists as well.
        for section in ('documents','evidence','statements'):
            changed = copy.deepcopy(self.knowledge)
            changed[section].append(self.appended_research()[section][-1])
            self.write(ci.RESEARCH_PATH, json.dumps(changed))
            self.assertEqual(self.plan()['mode'], 'research')

    def test_research_edits_deletions_reordering_answers_and_schema_are_full(self):
        edits = []
        changed=self.appended_research();changed['documents'][0]['metadata']['count']=True;edits.append(changed)
        changed=self.appended_research();changed['documents'][0]['metadata']['enabled']=0;edits.append(changed)
        changed=self.appended_research();changed['evidence'][0]['document_id']='doc:new';edits.append(changed)
        changed=self.appended_research();changed['documents'].pop(0);edits.append(changed)
        changed=self.appended_research();changed['documents'].reverse();edits.append(changed)
        changed=self.appended_research();changed['answers'].append({'id':'answer:new'});edits.append(changed)
        changed=self.appended_research();changed['version']='3.0.0';edits.append(changed)
        changed=self.appended_research();changed['note']='New rule';edits.append(changed)
        changed=self.appended_research();changed['unknown_schema']=[];edits.append(changed)
        edits.append(self.knowledge)  # Formatting/no additions is not evidence of this route.
        for changed in edits:
            self.write(ci.RESEARCH_PATH, json.dumps(changed, indent=2))
            self.assertEqual(self.plan()['mode'], 'full')

    def test_research_id_collisions_ambiguous_json_and_nonfinite_values_are_full(self):
        for section in ('documents','evidence','statements'):
            changed=self.appended_research();changed[section][-1]['id']=changed[section][0]['id']
            self.write(ci.RESEARCH_PATH, json.dumps(changed))
            self.assertEqual(self.plan()['mode'],'full')
        encoded=json.dumps(self.appended_research())
        for raw in (encoded.replace('"doc:new"','"doc:new", "id":"doc:hidden"',1),
                    encoded.replace('"partial_support_only": true','"partial_support_only": NaN',1),
                    '{invalid JSON', encoded.replace('"id": "doc:new"','"id": 12',1)):
            self.write(ci.RESEARCH_PATH, raw)
            self.assertEqual(self.plan()['mode'],'full')

    def test_research_replacements_relaxed_review_and_formal_answers_are_full(self):
        for fields in ({'partial_support_only':False}, {'question_id':'question:formal'},
                       {'replaces_record_ids':['statement:old']}, {'supersedes':['statement:old']},
                       {'relaxes_distribution':True}, {'object_mapping_review':{}},
                       {'review':{'replaces_record_ids':['statement:old']}},
                       {'review':{'relaxes_distribution':True}}, {'status':'superseded'}):
            changed=self.appended_research();changed['statements'][-1].update(fields)
            self.write(ci.RESEARCH_PATH,json.dumps(changed))
            self.assertEqual(self.plan()['mode'],'full',fields)

    def test_research_parse_failure_keeps_other_changed_content_checks(self):
        self.write(ci.RESEARCH_PATH,'{invalid JSON')
        self.write('docs/broken.png',b'not PNG')
        plan=self.plan()
        self.assertEqual(plan['mode'],'full')
        self.assertEqual({r['path'] for r in plan['files']},{ci.RESEARCH_PATH,'docs/broken.png'})
        with self.assertRaises(OSError):
            ci.check_content(self.root,plan)

    def test_research_mixed_changes_union_bounded_checks_and_code_still_wins(self):
        self.write(ci.RESEARCH_PATH,json.dumps(self.appended_research()))
        self.write('docs/a.md','New source commentary')
        self.assertEqual(self.plan()['mode'],'research')
        self.write('web/pages/index.html','<html><body><h1>New</h1><script>const x=1;</script></body></html>')
        plan=self.plan()
        self.assertEqual((plan['mode'],plan['suites'],plan['assets']),
                         ('research',['industry','research'],True))
        self.write('src/change.py','pass')
        plan=self.plan()
        self.assertEqual((plan['mode'],plan['suites'],plan['storage']),('full',ci.FULL_SUITES,True))

    def test_research_regression_selection_keeps_adoption_publication_and_http_contracts(self):
        def cases(suite):
            for test in suite:
                if isinstance(test,unittest.TestSuite):
                    yield from cases(test)
                else:
                    yield test.id()
        names=list(cases(ci.research_test_suite(Path(__file__).resolve().parents[2])))
        modules={name.split('.')[0] for name in names}
        self.assertTrue({'test_research','test_research_review','test_research_publication_group',
                         'test_research_publication_merge','test_research_protected_merge',
                         'test_research_sources','test_public_reader','test_publish_reader',
                         'test_verification_contract','test_ci_scope'} <= modules)
        self.assertFalse(any('atlas' in module or 'assembly' in module for module in modules))
        self.assertFalse(any('_FailedTest' in name for name in names),names)
        with self.assertRaisesRegex(ValueError,'missing research regression'):
            ci.research_test_suite(self.root)

    def test_document_image_and_derived_inventory_only_are_content(self):
        self.write('docs/a.md', 'New text ![diagram](picture.png)\n')
        self.write('docs/picture.png', base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=='))
        self.write('framework/repository_manifest.json', '{}')
        plan = self.plan()
        self.assertEqual((plan['mode'], plan['suites'], plan['storage']), ('content', [], False))
        self.assertEqual(len(ci.check_content(self.root, plan)), 2)

    def test_corrupt_image_and_new_broken_reference_fail_content_check(self):
        self.write('docs/a.md', '![missing](missing.png)')
        plan = self.plan()
        with self.assertRaisesRegex(ValueError, 'reference missing'):
            ci.check_content(self.root, plan)
        self.write('docs/a.md', 'text')
        self.write('docs/broken.png', b'not PNG')
        plan = self.plan()
        with self.assertRaises(OSError):
            ci.check_content(self.root, plan)

    def test_full_mixed_change_still_checks_corrupt_content(self):
        self.write('src/example.py', 'pass')
        self.write('docs/broken.png', b'not PNG')
        plan = self.plan()
        self.assertEqual(plan['mode'], 'full')
        with self.assertRaises(OSError):
            ci.check_content(self.root, plan)

    def test_text_only_html_is_targeted_but_structure_and_code_are_full(self):
        self.write('web/pages/index.html', '<html><body><h1>New words</h1><script>const x=1;</script></body></html>')
        self.assertEqual(self.plan()['suites'], ['industry'])
        for html in ['<html><body><h2>Hello</h2></body></html>',
                     '<html><body><h1>Hello</h1><script>const x=2;</script></body></html>',
                     '<html><body><h1 onclick="x()">Hello</h1></body></html>']:
            self.write('web/pages/index.html', html)
            self.assertEqual(self.plan()['mode'], 'full')

    def test_model_illustration_selects_render_and_download_suite(self):
        self.write('web/assets/technical-atlas/test.svg', '<svg xmlns="http://www.w3.org/2000/svg"><text>new</text></svg>')
        plan = self.plan()
        self.assertEqual((plan['mode'], plan['suites']), ('targeted', ['technical_atlas']))

    def test_svg_script_or_embedded_html_is_code_and_requires_full(self):
        for contents in ['<script>let x=1;</script>', '<foreignObject><p>text</p></foreignObject>',
                         '<a href="javascript:alert(1)"><text>x</text></a>']:
            self.write('docs/active.svg', '<svg xmlns="http://www.w3.org/2000/svg">'+contents+'</svg>')
            plan = self.plan()
            self.assertEqual(plan['mode'], 'full')
            self.assertEqual(len(ci.check_content(self.root, plan)), 1)

    def test_ordinary_web_image_maps_direct_page_but_shared_consumer_is_full(self):
        self.write('web/pages/index.html', '<html><body><img src="/assets/logo.png"></body></html>')
        self.write('web/assets/logo.png', b'old')
        self.base = self.commit()
        self.write('web/assets/logo.png', b'new')
        self.assertEqual(self.plan()['suites'], ['industry'])
        self.write('web/themes/shared.css', 'x {background:url(/assets/logo.png)}')
        self.base = self.commit()
        self.write('web/assets/logo.png', b'newer')
        self.assertEqual(self.plan()['mode'], 'full')

    def test_nested_admin_page_and_unmapped_image_are_full(self):
        self.write('web/pages/admin/product/index.html', '<h1>old</h1>')
        self.base = self.commit()
        self.write('web/pages/admin/product/index.html', '<h1>new</h1>')
        self.assertEqual(self.plan()['mode'], 'full')
        self.base = self.git('rev-parse', 'HEAD')
        self.write('web/assets/unknown.png', b'image')
        self.assertEqual(self.plan()['mode'], 'full')

    def test_unknown_data_dependencies_deletion_and_missing_base_are_full(self):
        for path in ['src/example.py', 'data/facts.json', 'package-lock.json', '.github/workflows/validate.yml']:
            self.write(path, '{}')
            self.assertEqual(self.plan()['mode'], 'full')
        self.assertEqual(ci.select(self.root, '0'*40, self.base)['mode'], 'full')
        (self.root/'docs/a.md').unlink()
        self.assertEqual(self.plan()['mode'], 'full')

    def test_rename_symlink_and_more_than_300_paths_cannot_hide_code(self):
        for i in range(305):
            self.write(f'docs/{i}.md', 'text')
        self.write('z/hidden.py', 'print(1)')
        self.assertEqual(self.plan()['mode'], 'full')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('mv', 'docs/a.md', 'docs/renamed.md')
        self.assertEqual(self.plan()['mode'], 'full')
        self.base = self.git('rev-parse', 'HEAD')
        (self.root/'docs/link.md').symlink_to('renamed.md')
        self.assertEqual(self.plan()['mode'], 'full')

    def test_governance_metadata_does_not_hide_rule_changes(self):
        self.write('docs/a.md', 'new')
        self.write('framework/current_state.json', json.dumps({'version':'2','entrypoints':[], 'policies':[], 'operational_guides':[]}))
        self.write('framework/verification_contract.json', json.dumps({'version':'2','reviewed_files':{'docs/a.md':'new'},'policies':[]}))
        self.assertEqual(self.plan()['mode'], 'content')
        self.write('framework/current_state.json', json.dumps({'version':'2','entrypoints':['docs/a.md'], 'policies':[], 'operational_guides':[]}))
        self.assertEqual(self.plan()['mode'], 'full')

    def test_shallow_checkout_with_exact_base_tree_keeps_complete_diff(self):
        self.write('docs/a.md', 'new words')
        head = self.commit()
        checkout = self.root.parent/(self.root.name+'-shallow')
        import shutil
        self.addCleanup(lambda: shutil.rmtree(checkout, ignore_errors=True))
        subprocess.run(['git','clone','-q','--depth=1',self.root.as_uri(),str(checkout)], check=True)
        subprocess.run(['git','-C',str(checkout),'fetch','-q','--depth=1','origin',self.base], check=True)
        plan = ci.select(checkout, self.base, head)
        self.assertEqual(plan['mode'], 'content')
        self.assertEqual(plan['files'], [{'status':'M','path':'docs/a.md'}])

    def test_scheduled_and_manual_runs_preserve_complete_full_suite(self):
        for event in ('schedule', 'workflow_dispatch'):
            plan = ci.select(self.root, '', '', event)
            self.assertEqual(plan['suites'], ci.FULL_SUITES)
            self.assertTrue(plan['storage'])

    def test_gate_rejects_failed_cancelled_missing_and_unexpected_skips(self):
        plans = [ci.select(self.root, '', '', 'schedule')]
        self.write('docs/a.md', 'new')
        plans.append(self.plan())
        self.write('web/pages/index.html', '<html><body><h1>New</h1><script>const x=1;</script></body></html>')
        plans.append(self.plan())
        self.write(ci.RESEARCH_PATH,json.dumps(self.appended_research()))
        research_plan=self.plan()
        plans.append(research_plan)
        for suites in ([],['research_delivery'],['research_summary']):
            broken=dict(research_plan,suites=suites)
            results={k:{'result':v} for k,v in {'scope':'success','validate':'success',
                     'browser':'success' if suites else 'skipped','storage-container':'skipped'}.items()}
            self.assertFalse(ci.gate(broken,results))
        for plan in plans:
            results = {k:{'result':v} for k,v in {'scope':'success','validate':'success',
                       'browser':'success' if plan['suites'] else 'skipped',
                       'storage-container':'success' if plan['storage'] else 'skipped'}.items()}
            self.assertTrue(ci.gate(plan, results))
            for job in results:
                for state in ('failure', 'cancelled', 'skipped', 'success'):
                    broken = copy.deepcopy(results)
                    broken[job]['result'] = state
                    if broken != results:
                        self.assertFalse(ci.gate(plan, broken), (plan['mode'], job, state))
                broken = copy.deepcopy(results)
                del broken[job]
                self.assertFalse(ci.gate(plan, broken))

    def test_publisher_requires_successful_gates_and_only_allows_optional_skips(self):
        checks = [{'name':name,'bucket':'pass'} for name in publisher.REQUIRED_CI_CHECKS]
        self.assertTrue(publisher.all_checks_pass(checks+[{'name':'storage-container','bucket':'skipped'}]))
        for name in publisher.REQUIRED_CI_CHECKS:
            self.assertFalse(publisher.all_checks_pass([dict(c, bucket='skipped') if c['name']==name else c for c in checks]))
        for bucket in ('pending','fail','cancel'):
            self.assertFalse(publisher.all_checks_pass(checks+[{'name':'optional','bucket':bucket}]))
        self.assertFalse(publisher.all_checks_pass([]))
