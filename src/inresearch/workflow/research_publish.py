"""Publish verified B increments through isolated Git, CI and live acceptance.

Runs on M5 with existing SSH/GitHub access. Every boundary is journaled outside
Git. A model result is never a website receipt; failed CI blocks only its batch.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import copy
import math
import time
from pathlib import Path

from inresearch.materials.artifacts import atomic_json, digest_file, encoded, now_iso, private_dir, read_json
from inresearch.storage.files import locked
from inresearch.knowledge import registry
from inresearch.workflow.research_review import promote, promote_group, verify_audit


def run(argv, cwd=None, check=True, timeout=60, input=None):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                            text=True, timeout=timeout,input=input)
    if check and result.returncode:
        # Logs keep an actionable error, not authentication/configuration output.
        detail = result.stderr[-1200:]
        if not detail:
            # Governance/validation report failures on stdout. Only their
            # explicit error lines may enter the journal, never arbitrary output.
            detail = '\n'.join(line for line in result.stdout.splitlines()
                               if line.startswith('ERROR:'))[-1200:]
        raise RuntimeError('command_failed: '+str(argv[0])+' exit='+str(result.returncode)+' '+detail)
    return result


def all_checks_pass(checks):
    required = {'validate', 'browser (core)', 'browser (model_assets)', 'storage-container'}
    return required <= {c['name'] for c in checks} and all(c.get('bucket')=='pass' for c in checks)


def publication_checks(root, commit):
    """Read checks on the reviewed SHA, never a PR's cached previous rollup."""
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('invalid_publication_commit')
    pages = json.loads(run(['gh', 'api',
        'repos/{owner}/{repo}/commits/'+commit+'/check-runs?per_page=100&filter=latest',
        '--paginate', '--slurp'], root).stdout)
    checks = []
    for page in pages:
        for check in page['check_runs']:
            if check['head_sha'] != commit:
                raise ValueError('ci_head_changed_requires_review')
            conclusion = check.get('conclusion')
            if check['status'] != 'completed': bucket = 'pending'
            elif conclusion == 'success': bucket = 'pass'
            elif conclusion == 'cancelled': bucket = 'cancel'
            else: bucket = 'fail'
            checks.append({'name':check['name'], 'bucket':bucket,
                           'state':(conclusion or check['status']).upper(),
                           'head_sha':commit, 'check_run_id':check['id']})
    return checks


# Fixed acceptance surface, not caller-supplied commands or a CI-success flag.
LOCAL_ACCEPTANCE_COMMANDS = (
    ('env', 'PYTHONPATH=src', sys.executable, '-B', '-m', 'unittest', 'discover',
     '-s', 'tests/unit', '-p', 'test_research*.py'),
    ('env', 'PYTHONPATH=src', sys.executable, '-B', '-m', 'unittest', 'discover',
     '-s', 'tests/unit', '-p', 'test_verification_contract.py'),
    (sys.executable, 'manage.py', 'governance', '--check'),
    (sys.executable, 'manage.py', 'validate', '--strict'),
    (sys.executable, 'manage.py', 'registry'),
)


def source_bundle(root, directory, target, base):
    """Incremental approved-main Git objects; never replace a divergent head."""
    if not all(re.fullmatch('[0-9a-f]{40}',x) for x in (target,base)):
        raise ValueError('invalid_source_commit')
    if run(['git','merge-base','--is-ancestor',base,target],root,check=False).returncode:
        raise ValueError('spark_source_not_ancestor_preserve_and_defer')
    if run(['git','rev-parse','origin/main'],root).stdout.strip()!=target:
        raise ValueError('source_target_is_not_current_main')
    path=private_dir(Path(directory))/(target+'-'+base[:12]+'.bundle')
    if not path.exists():run(['git','bundle','create',path,'origin/main','^'+base],root)
    heads=run(['git','bundle','list-heads',path],root).stdout.splitlines()
    if target+' refs/remotes/origin/main' not in heads:raise ValueError('source_bundle_head_mismatch')
    return path


def merge_appended_research(base, reviewed, upstream):
    """Union unchanged records and independent append-only additions by ID.

    A deletion, edit, ID collision or other field change requires review.
    Accepted main records never lose to the publication branch.
    """
    sections = {'documents', 'evidence', 'statements'}
    if set(base) != set(reviewed) or set(base) != set(upstream):
        raise ValueError('research_merge_requires_review')
    result = dict(base)
    for name, original in base.items():
        if name not in sections:
            if original != reviewed[name] or original != upstream[name]:
                raise ValueError('research_merge_requires_review')
            continue
        def indexed(rows):
            if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get('id') for r in rows):
                raise ValueError('research_merge_requires_review')
            values = {r['id']:r for r in rows}
            if len(values) != len(rows):raise ValueError('research_merge_requires_review')
            return values
        old = indexed(original)
        left, right = indexed(reviewed[name]), indexed(upstream[name])
        if any(left.get(k) != v or right.get(k) != v for k,v in old.items()):
            raise ValueError('research_merge_requires_review')
        union = dict(old)
        # Main ordering/records first; identical additions are idempotent.
        for row in upstream[name]+reviewed[name]:
            if row['id'] in union and union[row['id']] != row:
                raise ValueError('research_merge_requires_review')
            union[row['id']] = row
        result[name] = list(union.values())
    return result


def refresh_publication_base(worktree, expected_commit):
    """Merge current main into our exclusive, clean publication branch.

    Derived inventories are rebuilt; unchanged research records may receive
    independent additions. Edits, rules or source conflicts remain for review. A changed head must pass
    every configured acceptance check again before it can be merged.
    """
    worktree = Path(worktree)
    if (run(['git','status','--porcelain'],worktree).stdout.strip()
            or run(['git','rev-parse','HEAD'],worktree).stdout.strip()!=expected_commit):
        raise ValueError('publication_worktree_changed_requires_review')
    run(['env','GIT_TERMINAL_PROMPT=0','git','fetch','origin','main'],worktree)
    if run(['git','merge-base','--is-ancestor','origin/main','HEAD'],worktree,check=False).returncode==0:
        return expected_commit
    result=run(['git','merge','--no-commit','--no-ff','origin/main'],worktree,check=False)
    derived={'framework/repository_manifest.json','docs/REPOSITORY_REGISTER.md'}
    resolved=set()
    if result.returncode:
        conflicts=set(run(['git','diff','--name-only','--diff-filter=U'],worktree).stdout.splitlines())
        research='data/research_knowledge.json'
        if not conflicts or not conflicts <= derived | {research}:
            raise ValueError('publication_non_inventory_conflict_preserved')
        if research in conflicts:
            try:
                versions=[json.loads(run(['git','show',f':{stage}:'+research],worktree).stdout)
                          for stage in (1,2,3)]
                merged=merge_appended_research(*versions)
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError('publication_non_inventory_conflict_preserved') from error
            (worktree/research).write_text(json.dumps(merged,ensure_ascii=False,indent=2)+'\n')
            resolved.add(research)
        for name in conflicts:
            if name==research:continue
            (worktree/name).write_text(run(['git','show','origin/main:'+name],worktree).stdout)
    for args in (['governance','--refresh'],['governance','--check'],['validate','--strict'],['registry']):
        run([sys.executable,'manage.py',*args],worktree)
    run(['git','add',*sorted(derived | resolved)],worktree)
    run(['git','commit','-m','Refresh verified research publication against current main'],worktree)
    return run(['git','rev-parse','HEAD'],worktree).stdout.strip()


def protected_main_merge_receipt(root, pr, commit):
    """Allow an already tested head on protected main; never waive its CI."""
    required = {'validate', 'browser (core)', 'browser (model_assets)', 'storage-container'}
    try:
        info = json.loads(run(['gh', 'api', 'repos/{owner}/{repo}/pulls/'+str(pr)+'?fresh='+str(time.time_ns()),
                               '-H', 'Cache-Control: no-cache'], root).stdout)
        if (info['state'] != 'open' or info['head']['sha'] != commit
                or info['base']['ref'] != 'main' or info['mergeable'] is not True
                or info['mergeable_state'] != 'clean'
                or not re.fullmatch('[0-9a-f]{40}', info['base']['sha'])):
            return None
        protection = json.loads(run(['gh', 'api',
            'repos/{owner}/{repo}/branches/main/protection?fresh='+str(time.time_ns()),
            '-H', 'Cache-Control: no-cache'], root).stdout)
        checks = protection['required_status_checks']['checks']
        if (protection['required_status_checks']['strict'] is not False
                or protection['enforce_admins']['enabled'] is not True
                or not required <= {c['context'] for c in checks if c.get('app_id') == 15368}):
            return None
        return {'commit':commit, 'base':info['base']['sha'], 'pr':pr,
                'mergeable':True, 'required_checks':sorted(required),
                'protected_main':True, 'verified_at':now_iso()}
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        return None  # Unknown protection/mergeability retains the old refresh path.


class Publisher:
    def __init__(self, config):
        self.config = config
        self.publication_mode = config.get('publication_mode', 'ci')
        if self.publication_mode not in ('ci', 'local_acceptance'):
            raise ValueError('invalid_publication_mode')
        self.base_update_policy = config.get('base_update_policy', 'always_refresh')
        if (self.base_update_policy not in ('always_refresh', 'protected_merge')
                or (self.publication_mode != 'ci' and self.base_update_policy != 'always_refresh')):
            raise ValueError('invalid_publication_base_update_policy')
        self.group_wait_seconds = config.get('group_wait_seconds', 300)
        if type(self.group_wait_seconds) is not int or not 0 <= self.group_wait_seconds <= 3600:
            raise ValueError('invalid_publication_group_wait')
        self.group_max_batches = config.get('group_max_batches', 4)
        self.group_max_statements = config.get('group_max_statements', 24)
        if (type(self.group_max_batches) is not int or not 1 <= self.group_max_batches <= 12
                or type(self.group_max_statements) is not int or not 1 <= self.group_max_statements <= 72):
            raise ValueError('invalid_publication_group_limits')
        self.root = Path(config['repo']).resolve()
        self.state = private_dir(Path(config['state']))
        self.spark_root = config.get('spark_root','/home/spark/code/inresearch.ai')
        self.spark_data = config.get('spark_data','/home/spark/.local/share/inresearch.ai')
        self.spark_queue = self.spark_data+'/material-reviews/research-verification'

    def open_research_prs(self, own_branch=None):
        rows = json.loads(run(['gh', 'pr', 'list', '--state', 'open', '--limit', '1000',
                               '--json', 'number,headRefName,headRefOid'], self.root).stdout)
        # A saturated listing cannot prove absence. Fail closed rather than
        # open another publication outside the observed window.
        if len(rows) >= 1000:
            raise ValueError('open_pr_inventory_incomplete')
        return [r for r in rows if r['headRefName'].startswith('codex/research-publication-')
                and r['headRefName'] != own_branch]

    def local_source_proof(self, journal):
        if journal.get('members'):
            stale = []
            for member in journal['members']:
                proof = self.local_source_proof(member)
                if not proof['context_current']:
                    stale.append(member['batch_id'])
            return {'verified':True, 'context_current':not stale, 'stale_batches':stale}
        proof = self.remote('verify', '--batch-id', journal['batch_id'])
        if (proof.get('verified') is not True or proof.get('batch_id') != journal['batch_id']
                or proof.get('attempt') != journal['attempt']
                or proof.get('bundle_sha256') != journal['bundle_sha256']):
            raise ValueError('local_acceptance_source_binding_changed')
        if journal.get('source_identity') and journal['source_identity'] != {
                key:proof.get(key) for key in ('doc_id','source_sha256','revision_id','report_sha256')}:
            raise ValueError('local_acceptance_source_identity_changed')
        return proof

    def local_context_current(self, journal):
        proof = self.local_source_proof(journal)
        if not proof['context_current']:
            for bid in proof.get('stale_batches', [journal['batch_id']]):
                self.remote('revalidate', '--batch-id', bid)
            return False
        return True

    def local_binding(self, journal, directory):
        worktree = Path(journal['worktree'])
        head = run(['git', 'rev-parse', 'HEAD'], worktree).stdout.strip()
        base = run(['git', 'rev-parse', 'origin/main'], worktree).stdout.strip()
        if (head != journal['commit'] or not re.fullmatch('[0-9a-f]{40}', head)
                or not re.fullmatch('[0-9a-f]{40}', base)
                or run(['git', 'status', '--porcelain'], worktree).stdout.strip()):
            raise ValueError('local_acceptance_head_or_worktree_changed')
        if journal.get('members'):
            expected = self.group_manifest(journal, head, base)
            reference = journal.get('group_manifest') or {}
            path = directory/reference.get('path', '')
            if (path.resolve().parent != (directory/'manifests').resolve()
                    or digest_file(path) != reference.get('sha256') or read_json(path) != expected):
                raise ValueError('publication_group_manifest_changed')
            for member in journal['members']:
                audit = directory/'members'/member['batch_id']/member['attempt']
                bundle = read_json(audit/'bundle.json')
                if (digest_file(audit/'bundle.json') != member['bundle_sha256']
                        or bundle['attempt'] != member['attempt']
                        or bundle['packet']['batch_id'] != member['batch_id']
                        or bundle['request_sha256'] != member['request_sha256']
                        or bundle['packet']['context_sha256'] != member['context_sha256']):
                    raise ValueError('publication_group_member_changed')
                verify_audit(bundle, audit)
                expected_ids = ['adoption:review:'+hashlib.sha256(r['id'].encode()).hexdigest()[:24]
                                for r in bundle['reviews'] if r['decision']=='adopt_B']
                if member['statement_ids'] != expected_ids:
                    raise ValueError('publication_group_statement_ids_changed')
            if journal['statement_ids'] != [sid for m in journal['members'] for sid in m['statement_ids']]:
                raise ValueError('publication_group_statement_ids_changed')
            return {'commit':head, 'baseline':base, 'group_id':journal['batch_id'],
                    'manifest_sha256':reference['sha256']}
        audit = directory/journal['attempt']
        if digest_file(audit/'bundle.json') != journal['bundle_sha256']:
            raise ValueError('local_acceptance_bundle_changed')
        bundle = read_json(audit/'bundle.json')
        verify_audit(bundle, audit)
        if bundle['attempt'] != journal['attempt']:
            raise ValueError('local_acceptance_attempt_changed')
        return {'commit':head, 'baseline':base, 'batch_id':journal['batch_id'],
                'attempt':journal['attempt'], 'bundle_sha256':journal['bundle_sha256']}

    def validate_local_receipt(self, journal, directory):
        reference = journal.get('local_acceptance')
        if not isinstance(reference, dict):
            raise ValueError('local_acceptance_receipt_required')
        path = directory/reference['path']
        if path.resolve().parent != (directory/'local-acceptance').resolve():
            raise ValueError('local_acceptance_receipt_path_changed')
        if digest_file(path) != reference['sha256']:
            raise ValueError('local_acceptance_receipt_changed')
        receipt = read_json(path)
        commands = [list(c) for c in LOCAL_ACCEPTANCE_COMMANDS]
        if (receipt.get('version') != (2 if journal.get('members') else 1) or receipt.get('mode') != 'local_acceptance'
                or receipt.get('binding') != self.local_binding(journal, directory)
                or receipt.get('commands') != commands or not receipt.get('finished_at')
                or len(receipt.get('results', [])) != len(commands)
                or any(r.get('returncode') != 0 for r in receipt['results'])):
            raise ValueError('local_acceptance_receipt_binding_changed')
        for result in receipt['results']:
            log = directory/result['log_path']
            if (log.resolve().parent != (directory/'local-acceptance').resolve()
                    or digest_file(log) != result['log_sha256']):
                raise ValueError('local_acceptance_check_log_changed')
        return receipt

    def accept_local(self, journal, directory):
        if journal.get('local_acceptance'):
            return self.validate_local_receipt(journal, directory)
        binding = self.local_binding(journal, directory)
        results = []
        started = now_iso()
        folder = private_dir(directory/'local-acceptance')
        for index, command in enumerate(LOCAL_ACCEPTANCE_COMMANDS):
            outcome = run(command, journal['worktree'], timeout=900, check=False)
            log = {'command':list(command),'returncode':outcome.returncode,
                   'stdout':outcome.stdout,'stderr':outcome.stderr,'at':now_iso()}
            path = folder/('check-'+str(index)+'-'+hashlib.sha256(encoded(log).encode()).hexdigest()+'.json')
            if not path.exists():
                atomic_json(path,log)
            if outcome.returncode != 0:
                raise RuntimeError('local_acceptance_check_failed_'+str(index)+'_exit='+str(outcome.returncode))
            results.append({'returncode':outcome.returncode,
                'log_path':str(path.relative_to(directory)),'log_sha256':digest_file(path),
                'stdout_sha256':hashlib.sha256(outcome.stdout.encode()).hexdigest(),
                'stderr_sha256':hashlib.sha256(outcome.stderr.encode()).hexdigest()})
        if self.local_binding(journal, directory) != binding:
            raise ValueError('local_acceptance_head_changed_during_checks')
        receipt = {'version':2 if journal.get('members') else 1, 'mode':'local_acceptance', 'binding':binding,
                   'commands':[list(c) for c in LOCAL_ACCEPTANCE_COMMANDS],
                   'results':results, 'started_at':started, 'finished_at':now_iso()}
        folder = private_dir(directory/'local-acceptance')
        path = folder/(binding['commit']+'-'+hashlib.sha256(encoded(receipt).encode()).hexdigest()+'.json')
        atomic_json(path, receipt)
        journal['local_acceptance'] = {'path':str(path.relative_to(directory)), 'sha256':digest_file(path)}
        return self.validate_local_receipt(journal, directory)

    def invalidate_local_receipt(self, journal):
        if journal.get('local_acceptance'):
            journal.setdefault('local_acceptance_history', []).append(journal.pop('local_acceptance'))

    def ssh(self, args):
        return run(['ssh','-o','ConnectTimeout=10',self.config.get('spark','spark'),shlex.join(args)])

    def remote(self, *args):
        try:
            result = self.ssh(['python3', self.spark_root+'/manage.py', 'research-review',
                               '--root', self.spark_root, '--data', self.spark_data, *args])
        except RuntimeError as error:
            # SSH preserves the remote semantic failure as stderr, not its Python
            # exception class. Classify only explicit machine-readable codes;
            # transport/authentication failures keep their retryable stage.
            code = re.search(r'ValueError: ([a-z_]+)(?:: ([a-z_,]+))?', str(error))
            if code:
                raise ValueError(code.group(1)+((': '+code.group(2)) if code.group(2) else '')) from error
            raise
        return json.loads(result.stdout)

    def sync_source(self):
        # Preserve any unrelated active checkout changes. No reset, stash or
        # service restart is a substitute for a clean fast-forward.
        dirty=self.ssh(['git','-C',self.spark_root,'status','--porcelain']).stdout
        if dirty.strip():raise ValueError('spark_source_dirty_preserve_and_defer')
        # M5 already has GitHub access. Ship only verified incremental objects
        # over the existing SSH link, rather than blocking every publication on
        # Spark's intermittent direct GitHub TLS connection.
        run(['env','GIT_TERMINAL_PROMPT=0','git','fetch','origin','main'],self.root)
        target=run(['git','rev-parse','origin/main'],self.root).stdout.strip()
        base=self.ssh(['git','-C',self.spark_root,'rev-parse','HEAD']).stdout.strip()
        if base==target:return
        bundle=source_bundle(self.root,self.state/'source-releases',target,base)
        remote_dir=self.config.get('spark_state','/home/spark/.local/state/inresearch.ai')+'/research-source'
        self.ssh(['mkdir','-p','-m','700',remote_dir])
        remote_path=remote_dir+'/'+bundle.name
        run(['scp','-q',bundle,self.config.get('spark','spark')+':'+remote_path])
        remote_sha=self.ssh(['sha256sum',remote_path]).stdout.split()[0]
        if remote_sha!=digest_file(bundle):raise ValueError('source_bundle_transport_changed')
        self.ssh(['git','-C',self.spark_root,'bundle','verify',remote_path])
        if (self.ssh(['git','-C',self.spark_root,'status','--porcelain']).stdout.strip()
                or self.ssh(['git','-C',self.spark_root,'rev-parse','HEAD']).stdout.strip()!=base):
            raise ValueError('spark_source_changed_during_transfer')
        self.ssh(['git','-C',self.spark_root,'fetch',remote_path,
                  'refs/remotes/origin/main:refs/remotes/origin/main'])
        self.ssh(['git','-C',self.spark_root,'merge','--ff-only',target])
        actual=self.ssh(['git','-C',self.spark_root,'rev-parse','HEAD']).stdout.strip()
        if actual!=target:raise ValueError('spark_source_acceptance_mismatch')
        atomic_json(self.state/'source-releases'/(bundle.stem+'.json'),
                    {'target':target,'previous':base,'sha256':remote_sha,'bytes':bundle.stat().st_size,
                     'transport':'existing SSH, incremental Git bundle','verified_at':now_iso()})

    def local_deployment(self, merge_commit):
        """Observe exact running image plus public health, without environment data.

        Missing/old/unhealthy deployments are pending, not acceptance or an ACK.
        """
        aws = self.config.get('aws','aws')
        container = self.config.get('container','inresearch-host-inresearch-1')
        template = ('{"image":{{json .Image}},"tag":{{json .Config.Image}},'
                    '"status":{{json .State.Status}},'
                    '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}')
        try:
            outcome = run(['ssh',aws,shlex.join(['docker','inspect','--format',template,container])], check=False)
            if outcome.returncode:
                return None
            observed = json.loads(outcome.stdout)
            if not isinstance(observed,dict):
                return None
            tag = observed.get('tag')
            match = re.fullmatch('inresearch-app:([0-9a-f]{40})',tag or '')
            image = observed.get('image')
            if (not match or not re.fullmatch('sha256:[0-9a-f]{64}',image or '')
                    or observed.get('status')!='running' or observed.get('health')!='healthy'
                    or not re.fullmatch('[0-9a-f]{40}',merge_commit)):
                return None
            actual = run(['ssh',aws,shlex.join(['docker','image','inspect','--format','{{.Id}}',tag])], check=False)
            if actual.returncode or actual.stdout.strip()!=image:
                return None
            source = match.group(1)
            if run(['git','merge-base','--is-ancestor',merge_commit,source],self.root,check=False).returncode:
                return None
            url = self.config.get('website','https://inresearch.ai').rstrip('/')+'/healthz'
            script = """import json,urllib.request
with urllib.request.urlopen(URL,timeout=30) as response:
 body=json.loads(response.read().decode())
 print(json.dumps({'status':response.status,'ok':body.get('ok') is True}))
""".replace('URL',repr(url))
            result = run(['ssh',aws,shlex.join(['docker','exec','-i',container,'python3','-'])],
                         input=script,check=False)
            if result.returncode:
                return None
            health = json.loads(result.stdout)
            if not isinstance(health,dict) or health.get('status')!=200 or health.get('ok') is not True:
                return None
            return {'tag':tag,'image':image,'source_commit':source,
                    'status':'running','health':'healthy','healthz_status':200,
                    'healthz_ok':True,'verified_at':now_iso()}
        except (OSError,subprocess.SubprocessError,RuntimeError,ValueError,KeyError,TypeError):
            return None

    def accept_website(self, directory, journal):
        bid = journal['batch_id']
        aws=self.config.get('aws','aws'); container=self.config.get('container','inresearch-host-inresearch-1')
        deployment = None
        if self.publication_mode == 'local_acceptance':
            deployment = self.local_deployment(journal['merge_commit'])
            if deployment is None:
                return False
            image = deployment['tag']
        else:
            image=run(['ssh',aws,shlex.join(['docker','inspect','--format','{{.Config.Image}}',container])]).stdout.strip()
        # Mint an ephemeral signed session for the existing deployment
        # administrator inside the container. Neither session nor key
        # leaves the host; accounts and auth policy are unchanged.
        script='''import sys,os,json,urllib.request
sys.path.insert(0,"/app/src")
from inresearch.interfaces import auth
username=os.environ.get("HUB_ADMIN_USERNAME","admin")
if auth.load_users().get(username,{}).get("role")!="admin":raise ValueError("existing_deployment_admin_required")
if not auth.SECRET_FILE.exists():raise ValueError("existing_session_key_required")
cookie=auth.make_cookie(username).split(";",1)[0]
request=urllib.request.Request(URL,headers={"Cookie":cookie})
with urllib.request.urlopen(request,timeout=30) as response:
 print(response.read().decode())
'''.replace('URL',repr(self.config.get('website','https://inresearch.ai')+'/api/research-adopted?node=root'))
        acceptance=json.loads(run(['ssh',aws,shlex.join(['docker','exec','-i',container,'python3','-'])],input=script).stdout)
        rows={s['id']:s for s in acceptance['knowledge']['statements']}
        expected=journal['statement_ids']
        if not all(i in rows for i in expected):return False
        evidence={e['id']:e for e in acceptance['knowledge']['evidence']}
        docs={d['id']:d for d in acceptance['knowledge']['documents']}
        canonical_closure = None
        if self.publication_mode == 'local_acceptance':
            canonical = registry.adopted_for_node(Path(journal['worktree']), 'root')['knowledge']
            canonical_rows = {s['id']:s for s in canonical['statements']}
            canonical_evidence = {e['id']:e for e in canonical['evidence']}
            canonical_docs = {d['id']:d for d in canonical['documents']}
            # Compare the same public projection, including reviewed object
            # scope, limits, source identity and actual review attribution.
            closure = {'statements':[], 'evidence':[], 'documents':[]}
            for sid in expected:
                wanted = canonical_rows[sid]
                if rows[sid] != wanted:
                    raise ValueError('website_canonical_statement_mismatch')
                closure['statements'].append(rows[sid])
                for eid in wanted['evidence_ids']:
                    ev = canonical_evidence[eid]
                    if evidence.get(eid) != ev or docs.get(ev['document_id']) != canonical_docs[ev['document_id']]:
                        raise ValueError('website_canonical_support_mismatch')
                    if evidence[eid] not in closure['evidence']:
                        closure['evidence'].append(evidence[eid])
                    if docs[ev['document_id']] not in closure['documents']:
                        closure['documents'].append(docs[ev['document_id']])
            canonical_closure = hashlib.sha256(encoded(closure).encode()).hexdigest()
        bundle=read_json(directory/journal['attempt']/'bundle.json')
        reviewed={r['id']:r for r in bundle['reviews'] if r['decision']=='adopt_B'}
        byid={'adoption:review:'+hashlib.sha256(k.encode()).hexdigest()[:24]:v for k,v in reviewed.items()}
        for sid in expected:
            s=rows[sid]
            if s['text']!=byid[sid]['text'] or s['review']['decision']!='adopted':raise ValueError('website_adoption_mismatch')
            for eid in s['evidence_ids']:
                e=evidence[eid]
                if not e.get('quote') or not docs[e['document_id']]['coverage']['complete']:raise ValueError('website_support_closure_missing')
        proof={'batch_id':bid,'bundle_sha256':journal['bundle_sha256'],
               'website_statement_ids':expected,'website_image':image,'verified_at':now_iso(),
               'merge_commit':journal['merge_commit'],'api':'/api/research-adopted?node=root',
               'links':['https://inresearch.ai/node.html?id=root#evidence']}
        if deployment:
            proof.update(website_image_digest=deployment['image'],
                         website_source_commit=deployment['source_commit'],
                         website_health_verified_at=deployment['verified_at'],
                         website_deployment=deployment)
        if canonical_closure:
            proof['canonical_public_closure_sha256'] = canonical_closure
            proof['canonical_public_closure_encoding'] = 'artifacts.encoded-v1; expected-order lists'
        if journal.get('publication_group'):
            proof['publication_group'] = journal['publication_group']
        atomic_json(directory/'website-proof.json',proof)
        run(['scp','-q',directory/'website-proof.json',self.config.get('spark','spark')+':'+self.spark_queue+'/'+bid+'/website-proof.json'])
        self.remote('published','--batch-id',bid,'--proof',self.spark_queue+'/'+bid+'/website-proof.json')
        return True

    def group_manifest(self, journal, head, baseline):
        return {'version':1, 'group_id':journal['batch_id'], 'commit':head,
                'baseline':baseline, 'members':copy.deepcopy(journal['members'])}

    def write_group_manifest(self, journal, directory):
        if not journal.get('members'):
            return
        base = run(['git','rev-parse','origin/main'], journal['worktree']).stdout.strip()
        value = self.group_manifest(journal, journal['commit'], base)
        folder = private_dir(directory/'manifests')
        path = folder/('manifest-'+hashlib.sha256(encoded(value).encode()).hexdigest()+'.json')
        if not path.exists():
            atomic_json(path, value)
        reference = {'path':str(path.relative_to(directory)), 'sha256':digest_file(path)}
        if journal.get('group_manifest') != reference:
            if journal.get('group_manifest'):
                journal.setdefault('group_manifest_history', []).append(journal['group_manifest'])
            journal['group_manifest'] = reference

    def group_member_ids(self):
        # Blocked or partially acknowledged groups keep ownership. Another
        # cohort must never silently absorb their immutable batch attempts.
        return {member['batch_id']
                for path in (self.state/'groups').glob('*/journal.json')
                for value in [read_json(path)]
                if value.get('state') not in ('published', 'revalidation', 'superseded')
                for member in value.get('members', [])}

    def ready_group(self, ready, *, proofs_out=None):
        groups = {}
        reserved = self.group_member_ids()
        for row in ready:
            bid = row['batch_id']
            if not re.fullmatch('[0-9a-f]{64}', bid):
                raise ValueError('unsafe_batch_id')
            # Existing journals remain with their original single-batch owner.
            # Their manual consolidation needs an explicit ownership window.
            if bid in reserved or (self.state/bid/'journal.json').exists():
                continue
            try:
                proof = self.remote('verify', '--batch-id', bid)
            except Exception:
                # Single-batch dispatch below retains its normal durable error
                # journal; one unavailable source cannot block healthy groups.
                continue
            fields = ('doc_id','source_sha256','revision_id','report_sha256')
            identity = tuple(proof.get(key) for key in fields)
            count = proof.get('adopt_B_count')
            if (proof.get('batch_id') != bid or proof.get('verified') is not True or proof.get('context_current') is not True
                    or not all(isinstance(x,str) and x for x in identity)
                    or type(count) is not int or count < 1):
                continue
            if proofs_out is not None:
                proofs_out[bid] = proof
            cohort = groups.setdefault(identity, [])
            if (len(cohort) < self.group_max_batches
                    and sum(item['adopt_B_count'] for item in cohort)+count <= self.group_max_statements):
                cohort.append(proof)
        return next((members for members in groups.values() if len(members)>1), [])

    def wait_for_group(self, proof):
        """Bounded singleton collection window, private and queue-independent."""
        if self.group_wait_seconds == 0:
            return False
        binding = {key:proof[key] for key in ('batch_id','attempt','bundle_sha256',
                    'doc_id','source_sha256','revision_id','report_sha256')}
        key = hashlib.sha256(encoded(binding).encode()).hexdigest()
        path = private_dir(self.state/'group-wait')/(key+'.json')
        clock = time.time()
        if not path.exists():
            atomic_json(path,{'binding':binding,'first_seen_epoch':clock,'first_seen_at':now_iso()})
        value = read_json(path)
        first = value.get('first_seen_epoch')
        if (value.get('binding') != binding or type(first) not in (int,float)
                or not math.isfinite(first)):
            raise ValueError('publication_group_wait_state_changed')
        return clock-first < self.group_wait_seconds

    def prepare_group(self, proofs):
        if (not 2 <= len(proofs) <= self.group_max_batches
                or len({p['batch_id'] for p in proofs}) != len(proofs)
                or any(type(p.get('adopt_B_count')) is not int or p['adopt_B_count'] < 1
                       for p in proofs)
                or sum(p['adopt_B_count'] for p in proofs) > self.group_max_statements):
            raise ValueError('invalid_publication_group_members')
        identity_keys = ('doc_id','source_sha256','revision_id','report_sha256')
        identity = {key:proofs[0][key] for key in identity_keys}
        members = []
        for proof in proofs:
            if ({key:proof[key] for key in identity_keys} != identity
                    or not re.fullmatch('attempt-[0-9]{4,}', proof['attempt'])
                    or not re.fullmatch('[0-9a-f]{64}',proof['batch_id'])):
                raise ValueError('publication_group_identity_mismatch')
            members.append({'batch_id':proof['batch_id'], 'attempt':proof['attempt'],
                            'bundle_sha256':proof['bundle_sha256'], 'source_identity':identity})
        gid = hashlib.sha256(encoded(members).encode()).hexdigest()
        directory = private_dir(self.state/'groups'/gid)
        path = directory/'journal.json'
        if path.exists():
            return self.advance(directory, read_json(path))
        journal = {'state':'prepared', 'batch_id':gid, 'members':members,
                   'statement_ids':[], 'member_acks':{}, 'created':now_iso()}
        try:
            self.sync_source()
            # sync_source fetched approved main; every member is now reverified
            # against that same unmodified baseline before any promote write.
            for member in members:
                if not self.local_context_current(member):
                    raise ValueError('research_context_changed_revalidation_required')
            baseline = run(['git','rev-parse','origin/main'],self.root).stdout.strip()
            branch = 'codex/research-publication-group-'+gid[:16]
            worktree = Path.home()/'.worktrees/inresearch.ai'/('research-publication-group-'+gid[:16])
            if worktree.exists():
                raise ValueError('publication_group_worktree_exists_preserve')
            run(['git','worktree','add','-b',branch,worktree,baseline],self.root)
            journal.update(branch=branch, worktree=str(worktree), baseline=baseline)
            bundles = []
            for member in members:
                audit = private_dir(directory/'members'/member['batch_id']/member['attempt'])
                for name in ('packet.json','request.json','response.json','matching-request.json',
                             'matching-response.json','sampling-request.json','sampling-response.json','bundle.json'):
                    run(['scp','-q',self.config.get('spark','spark')+':'+self.spark_queue+'/'+
                         member['batch_id']+'/'+member['attempt']+'/'+name,audit/name])
                if digest_file(audit/'bundle.json') != member['bundle_sha256']:
                    raise ValueError('bundle_transport_changed')
                bundle = read_json(audit/'bundle.json')
                member.update(request_sha256=bundle['request_sha256'],
                              context_sha256=bundle['packet']['context_sha256'])
                bundles.append((bundle,audit))
            adoption = promote_group(worktree,bundles)
            ids = {member['batch_id']:member['statement_ids'] for member in adoption['members']}
            for member in members:
                member['statement_ids'] = ids[member['batch_id']]
            journal['statement_ids'] = adoption['statement_ids']
            if not journal['statement_ids']:
                raise ValueError('empty_adoption')
            atomic_json(path,journal)
            return self.advance(directory,journal)
        except Exception as error:
            journal.update(state='blocked', error=str(error)[-1500:], updated=now_iso())
            atomic_json(path,journal)
            return journal

    def tick(self):
        # Every batch has its own durable failure. A failed verification must
        # never turn an otherwise healthy publication round into unavailable.
        blocked, waiting = [], []
        if self.publication_mode == 'local_acceptance':
            for path in sorted((self.state/'groups').glob('*/journal.json')):
                value = read_json(path)
                if value.get('state') in ('prepared','pr_open','merged'):
                    return self.advance(path.parent,value)
                if value.get('state') == 'blocked':
                    blocked.append({'batch_id':value['batch_id'],'state':'blocked'})
        for path in sorted(self.state.glob('*/journal.json')):
            value = read_json(path)
            if value.get('state') not in ('published', 'blocked', 'revalidation'):
                before = {k:value.get(k) for k in ('state', 'commit', 'merge_commit')}
                result = self.advance(path.parent, value)
                if result.get('error') or result['state'] in ('blocked', 'revalidation'):
                    blocked.append({'batch_id':value['batch_id'], 'state':result['state']})
                    continue
                if any(result.get(k) != v for k,v in before.items()):
                    return result
                waiting.append({'batch_id':value['batch_id'], 'state':result['state']})
                # A PR still waiting for checks/deployment cannot occupy the
                # whole dispatcher. Later batches may advance independently.
        ready = self.remote('ready')
        reserved = self.group_member_ids() if self.publication_mode == 'local_acceptance' else set()
        group_proofs = {}
        if self.publication_mode == 'local_acceptance' and not self.open_research_prs():
            group = self.ready_group(ready, proofs_out=group_proofs)
            if group:
                return self.prepare_group(group)
        for pending in ready:
            bid = pending['batch_id']
            if not re.fullmatch('[0-9a-f]{64}', bid):
                raise ValueError('unsafe_batch_id')
            if bid in reserved:
                continue
            directory = private_dir(self.state/bid)
            path = directory/'journal.json'
            value = read_json(path) if path.exists() else {}
            if value.get('state') not in (None, 'blocked', 'revalidation'):
                continue  # existing durable journal was already visited
            if value.get('state') in ('blocked', 'revalidation'):
                try:
                    proof = self.remote('verify', '--batch-id', bid)
                except Exception as error:
                    value.update(error=str(error)[-1500:], updated=now_iso())
                    atomic_json(path, value)
                    blocked.append({'batch_id':bid, 'state':value['state']})
                    continue
                if value.get('bundle_sha256') == proof['bundle_sha256']:
                    # A separately authorized release may have merged this
                    # exact reviewed head while CI was blocked. Recover only
                    # the website receipt; do not merge or waive any checks.
                    if value.get('pr') and value.get('commit'):
                        try:
                            pr = json.loads(run(['gh', 'pr', 'view', str(value['pr']),
                                                 '--json', 'state,mergeCommit,headRefOid'], self.root).stdout)
                            if pr['state'] == 'MERGED':
                                if pr['headRefOid'] != value['commit']:
                                    raise ValueError('pr_head_changed_requires_review')
                                value.setdefault('recoveries', []).append({
                                    'from':value['state'], 'error':value.get('error'),
                                    'reason':'exact_reviewed_head_already_merged', 'at':now_iso()})
                                value.update(state='merged', merge_commit=pr['mergeCommit']['oid'])
                                atomic_json(path, value)
                                result = self.advance(directory, value)
                                if not result.get('error'):
                                    return result
                            elif pr['state'] == 'OPEN':
                                if pr['headRefOid'] != value['commit']:
                                    raise ValueError('pr_head_changed_requires_review')
                                if proof.get('context_current') is False:
                                    self.remote('revalidate', '--batch-id', bid)
                                    run(['gh', 'pr', 'close', str(value['pr'])], self.root)
                                    value.setdefault('recoveries', []).append({
                                        'from':value['state'], 'error':value.get('error'),
                                        'reason':'changed_context_requeued', 'at':now_iso()})
                                    value.update(state='revalidation', updated=now_iso())
                                    value.pop('error', None)
                                    atomic_json(path, value)
                                    return value
                                if self.publication_mode == 'local_acceptance':
                                    value.setdefault('recoveries', []).append({
                                        'from':value['state'], 'error':value.get('error'),
                                        'reason':'explicit_local_acceptance_recovery', 'at':now_iso()})
                                    value.update(state='pr_open')
                                    atomic_json(path, value)
                                    return self.advance(directory, value)
                                checks = publication_checks(self.root, value['commit'])
                                if all_checks_pass(checks):
                                    value.setdefault('recoveries', []).append({
                                        'from':value['state'], 'error':value.get('error'),
                                        'reason':'exact_head_checks_recovered', 'at':now_iso()})
                                    value.update(state='pr_open', checks=checks)
                                    atomic_json(path, value)
                                    return self.advance(directory, value)
                                if any(c.get('bucket') in ('fail', 'cancel') for c in checks):
                                    # An approved fix on main must reach a failed
                                    # publication branch before its tests can
                                    # recover. Source/audit, context and exact PR
                                    # head have already been checked above.
                                    refreshed = refresh_publication_base(value['worktree'], value['commit'])
                                    if refreshed != value['commit']:
                                        value.setdefault('recoveries', []).append({
                                            'from':value['state'], 'error':value.get('error'),
                                            'checks':checks, 'reason':'failed_checks_new_approved_base',
                                            'at':now_iso()})
                                        value.setdefault('base_refreshes', []).append({
                                            'from':value['commit'], 'to':refreshed, 'at':now_iso()})
                                        value.update(state='prepared', commit=refreshed, checks=[])
                                        atomic_json(path, value)
                                        return self.advance(directory, value)
                        except Exception as error:
                            value.update(error=str(error)[-1500:], updated=now_iso())
                            atomic_json(path, value)
                    blocked.append({'batch_id':bid, 'state':value['state']})
                    continue
            if self.publication_mode == 'local_acceptance':
                opened = self.open_research_prs()
                if opened:
                    waiting.append({'state':'waiting_open_research_prs',
                                    'prs':[r['number'] for r in opened]})
                    continue
                if not value and bid in group_proofs and self.wait_for_group(group_proofs[bid]):
                    waiting.append({'batch_id':bid,'state':'collecting_same_source_batches',
                                    'group_wait_seconds':self.group_wait_seconds})
                    continue
            previous = value.get('previous_attempts', [])
            if value.get('attempt'):
                if not re.fullmatch('attempt-[0-9]{4,}', value['attempt']):
                    raise ValueError('unsafe_attempt')
                digest = hashlib.sha256(encoded(value).encode()).hexdigest()
                saved = private_dir(directory/value['attempt'])/('publication-journal-'+digest+'.json')
                if not saved.exists():atomic_json(saved, value)
                previous = previous + [{'attempt':value['attempt'], 'state':value['state'],
                                        'path':str(saved.relative_to(directory)), 'sha256':digest_file(saved)}]
            result = self.advance(directory, {'state':'new', 'batch_id':bid, 'previous_attempts':previous})
            if result.get('error') or result['state'] in ('blocked', 'revalidation'):
                blocked.append({'batch_id':bid, 'state':result['state']})
                continue
            return result
        return {'state':'waiting_batches' if waiting else ('blocked_batches' if blocked else 'idle'),
                'batches':blocked, 'waiting':waiting, 'at':now_iso()}

    def advance(self, directory, journal):
        bid=journal['batch_id']
        def save(state):
            journal.update(state=state,updated=now_iso())
            atomic_json(directory/'journal.json',journal)
        journal.pop('error', None)
        try:
            if journal['state']=='new':
                self.sync_source()
                proof=self.remote('verify','--batch-id',bid)
                attempt=proof['attempt']
                if not re.fullmatch('attempt-[0-9]{4,}',attempt):raise ValueError('unsafe_attempt')
                audit=private_dir(directory/attempt)
                for name in ('packet.json','request.json','response.json','matching-request.json','matching-response.json','sampling-request.json','sampling-response.json','bundle.json'):
                    run(['scp','-q',self.config.get('spark','spark')+':'+self.spark_queue+'/'+bid+'/'+attempt+'/'+name,audit/name])
                bundle=read_json(audit/'bundle.json')
                if digest_file(audit/'bundle.json')!=proof['bundle_sha256']:raise ValueError('bundle_transport_changed')
                journal.update(bundle_sha256=proof['bundle_sha256'],attempt=attempt)
                run(['env','GIT_TERMINAL_PROMPT=0','git','fetch','origin','main'],self.root)
                branch='codex/research-publication-'+bid[:16]+'-'+hashlib.sha256(attempt.encode()).hexdigest()[:6]
                worktree=Path.home()/'.worktrees/inresearch.ai'/('research-publication-'+bid[:16]+'-'+attempt)
                if not worktree.exists():
                    run(['git','worktree','add','-b',branch,worktree,'origin/main'],self.root)
                journal.update(branch=branch,worktree=str(worktree))
                try:
                    adoption=promote(worktree,bundle,audit)
                except ValueError as error:
                    if str(error)=='research_context_changed_revalidation_required':
                        self.remote('revalidate','--batch-id',bid)
                        save('revalidation');return journal
                    raise
                journal['statement_ids']=adoption['statement_ids']
                if not journal['statement_ids']:raise ValueError('empty_adoption')
                save('prepared')
            if journal['state']=='prepared':
                worktree=Path(journal['worktree'])
                for args in (['governance','--refresh'],['governance','--check'],['validate','--strict'],['registry']):
                    run([sys.executable,'manage.py',*args],worktree)
                run(['git','add','data/research_knowledge.json','framework/repository_manifest.json','docs/REPOSITORY_REGISTER.md'],worktree)
                if run(['git','diff','--cached','--quiet'],worktree,check=False).returncode:
                    run(['git','commit','-m','Adopt source-bound C3 B research increment '+bid[:12]],worktree)
                journal['commit']=run(['git','rev-parse','HEAD'],worktree).stdout.strip()
                self.write_group_manifest(journal, directory)
                run(['git','push','-u','origin',journal['branch']],worktree)
                body=directory/'pr-body.txt'
                body.write_text('Append '+str(len(journal['statement_ids']))+' bounded research statements from a sealed Reader report. Each retains original quotations, question relationships, actual core_review provenance and deterministic independent 10% review. No existing conclusions, formal answers, projects or GW totals change.\n\nValidation: source seal and native quotations, immutable model audit, current-context check, governance, strict validation and registry. Publication is acknowledged only after CI and live adopted API acceptance.\n')
                if self.publication_mode == 'local_acceptance':
                    body.write_text(body.read_text().replace(
                        'only after CI and live adopted API acceptance.',
                        'only after fixed local acceptance on the exact reviewed head and live adopted API acceptance.'))
                existing=json.loads(run(['gh','pr','list','--head',journal['branch'],'--state','all','--json','number,url'],worktree).stdout)
                if not existing:
                    if self.publication_mode == 'local_acceptance' and self.open_research_prs(journal['branch']):
                        save('prepared');return journal
                    run(['gh','pr','create','--base','main','--head',journal['branch'],'--title','Adopt verified research increment '+bid[:12],'--body-file',body],worktree)
                    existing=json.loads(run(['gh','pr','list','--head',journal['branch'],'--json','number,url'],worktree).stdout)
                journal.update(pr=existing[0]['number'],pr_url=existing[0]['url'])
                save('pr_open')
            if journal['state']=='pr_open':
                pr=json.loads(run(['gh','pr','view',str(journal['pr']),'--json','state,mergeCommit,headRefOid'],self.root).stdout)
                if pr['state']=='MERGED':
                    if self.publication_mode == 'local_acceptance' and pr['headRefOid'] != journal['commit']:
                        raise ValueError('pr_head_changed_requires_review')
                    journal['merge_commit']=pr['mergeCommit']['oid'];save('merged')
                else:
                    if pr['headRefOid']!=journal['commit']:raise ValueError('pr_head_changed_requires_review')
                    if self.publication_mode == 'local_acceptance':
                        self.sync_source()
                        if not self.local_context_current(journal):
                            run(['gh','pr','close',str(journal['pr'])],self.root)
                            save('revalidation');return journal
                        refreshed=refresh_publication_base(journal['worktree'],journal['commit'])
                        if refreshed != journal['commit']:
                            previous=journal['commit']
                            self.invalidate_local_receipt(journal)
                            journal.update(commit=refreshed)
                            journal.setdefault('base_refreshes',[]).append({
                                'from':previous,'to':refreshed,'at':now_iso()})
                            save('prepared');return journal
                        self.accept_local(journal, directory)
                        save('pr_open')  # durable receipt before the merge boundary
                        self.sync_source()
                        if not self.local_context_current(journal):
                            run(['gh','pr','close',str(journal['pr'])],self.root)
                            save('revalidation');return journal
                        refreshed=refresh_publication_base(journal['worktree'],journal['commit'])
                        if refreshed != journal['commit']:
                            previous=journal['commit']
                            self.invalidate_local_receipt(journal)
                            journal.update(commit=refreshed)
                            journal.setdefault('base_refreshes',[]).append({
                                'from':previous,'to':refreshed,'at':now_iso()})
                            save('prepared');return journal
                        self.validate_local_receipt(journal, directory)
                        final=json.loads(run(['gh','pr','view',str(journal['pr']),
                                              '--json','state,headRefOid'],self.root).stdout)
                        if final['state'] != 'OPEN' or final['headRefOid'] != journal['commit']:
                            raise ValueError('pr_head_changed_requires_review')
                        run(['gh','pr','merge',str(journal['pr']),'--merge',
                             '--match-head-commit',journal['commit']],self.root)
                        save('pr_open');return journal
                    checks=publication_checks(self.root,journal['commit'])
                    journal['checks']=checks
                    if any(c.get('bucket') in ('fail','cancel') for c in checks):
                        raise ValueError('ci_failed_preserve_review_branch')
                    if not all_checks_pass(checks):save('pr_open');return journal
                    if pr['headRefOid']!=journal['commit']:raise ValueError('pr_head_changed_requires_review')
                    self.sync_source()
                    if not self.remote('verify','--batch-id',bid)['context_current']:
                        self.remote('revalidate','--batch-id',bid)
                        run(['gh','pr','close',str(journal['pr'])],self.root)
                        save('revalidation');return journal
                    receipt = (protected_main_merge_receipt(self.root, journal['pr'], journal['commit'])
                               if self.base_update_policy == 'protected_merge' else None)
                    if receipt:
                        journal.setdefault('protected_merges', []).append(receipt)
                        save('pr_open')  # Persist the exact head, base and protection before merge.
                    refreshed=(journal['commit'] if receipt else
                               refresh_publication_base(journal['worktree'],journal['commit']))
                    if refreshed!=journal['commit']:
                        previous=journal['commit']
                        journal.update(commit=refreshed,checks=[])
                        journal.setdefault('base_refreshes',[]).append({'from':previous,'to':refreshed,'at':now_iso()})
                        # Journal the exact new head before pushing: a failed push
                        # can be retried without accepting somebody else's edit.
                        save('prepared');return journal
                    run(['gh','pr','merge',str(journal['pr']),'--merge','--match-head-commit',journal['commit']],self.root)
                    save('pr_open');return journal
            if journal['state']=='merged':
                self.sync_source()
                if journal.get('members'):
                    for member in journal['members']:
                        bid_member = member['batch_id']
                        if bid_member in journal.get('member_acks', {}):
                            if digest_file(directory/'members'/bid_member/'website-proof.json') != journal['member_acks'][bid_member]['proof_sha256']:
                                raise ValueError('publication_group_ack_proof_changed')
                            continue
                        folder = directory/'members'/bid_member
                        item = {**member, 'worktree':journal['worktree'], 'merge_commit':journal['merge_commit'],
                                'publication_group':{'group_id':journal['batch_id'],
                                    'commit':journal['commit'],
                                    'manifest_sha256':journal['group_manifest']['sha256']}}
                        if not self.accept_website(folder, item):
                            save('merged');return journal
                        journal.setdefault('member_acks', {})[bid_member] = {
                            'proof_sha256':digest_file(folder/'website-proof.json'), 'at':now_iso()}
                        save('merged')
                    save('published')
                elif self.accept_website(directory, journal):
                    save('published')
                else:
                    save('merged')
            return journal
        except Exception as error:
            journal['error']=str(error)[-1500:]
            # Context/source/CI failures require review; transient access failures
            # leave the journal at its last durable stage for the next poll.
            if isinstance(error,ValueError):save('blocked')
            else:save(journal['state'])
            return journal


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--poll',type=int,default=60)
    args=parser.parse_args()
    if args.poll<30:raise ValueError('publisher_poll_too_short')
    publisher=Publisher(read_json(args.config))
    with locked(publisher.state/'worker'):
        while True:
            try:result=publisher.tick()
            except Exception as error:result={'state':'unavailable','error':str(error)[-1500:],'at':now_iso()}
            atomic_json(publisher.state/'status.json',result)
            print(encoded(result),flush=True)
            if args.once:return
            time.sleep(args.poll)


if __name__=='__main__':main()
