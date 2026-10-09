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
import time
from pathlib import Path

from inresearch.materials.artifacts import atomic_json, digest_file, encoded, now_iso, private_dir, read_json
from inresearch.storage.files import locked
from inresearch.workflow.research_review import promote


def run(argv, cwd=None, check=True, timeout=60, input=None):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                            text=True, timeout=timeout,input=input)
    if check and result.returncode:
        # Logs keep an actionable error, not authentication/configuration output.
        raise RuntimeError('command_failed: '+str(argv[0])+' '+result.stderr[-1200:])
    return result


def all_checks_pass(checks):
    required = {'validate', 'browser (core)', 'browser (model_assets)', 'storage-container'}
    return required <= {c['name'] for c in checks} and all(c.get('bucket')=='pass' for c in checks)


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
    every CI check again before it can be merged.
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


class Publisher:
    def __init__(self, config):
        self.config = config
        self.root = Path(config['repo']).resolve()
        self.state = private_dir(Path(config['state']))
        self.spark_root = config.get('spark_root','/home/spark/code/inresearch.ai')
        self.spark_data = config.get('spark_data','/home/spark/.local/share/inresearch.ai')
        self.spark_queue = self.spark_data+'/material-reviews/research-verification'

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

    def tick(self):
        # Every batch has its own durable failure. A failed verification must
        # never turn an otherwise healthy publication round into unavailable.
        blocked, waiting = [], []
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
        for pending in self.remote('ready'):
            bid = pending['batch_id']
            if not re.fullmatch('[0-9a-f]{64}', bid):
                raise ValueError('unsafe_batch_id')
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
                                checks = json.loads(run(['gh', 'pr', 'checks', str(value['pr']),
                                                         '--json', 'name,bucket,state'],
                                                        self.root, check=False).stdout or '[]')
                                if all_checks_pass(checks):
                                    value.setdefault('recoveries', []).append({
                                        'from':value['state'], 'error':value.get('error'),
                                        'reason':'exact_head_checks_recovered', 'at':now_iso()})
                                    value.update(state='pr_open', checks=checks)
                                    atomic_json(path, value)
                                    return self.advance(directory, value)
                        except Exception as error:
                            value.update(error=str(error)[-1500:], updated=now_iso())
                            atomic_json(path, value)
                    blocked.append({'batch_id':bid, 'state':value['state']})
                    continue
            result = self.advance(directory, {'state':'new', 'batch_id':bid})
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
                run(['git','push','-u','origin',journal['branch']],worktree)
                body=directory/'pr-body.txt'
                body.write_text('Append '+str(len(journal['statement_ids']))+' bounded research statements from a sealed Reader report. Each retains original quotations, question relationships, actual core_review provenance and deterministic independent 10% review. No existing conclusions, formal answers, projects or GW totals change.\n\nValidation: source seal and native quotations, immutable model audit, current-context check, governance, strict validation and registry. Publication is acknowledged only after CI and live adopted API acceptance.\n')
                existing=json.loads(run(['gh','pr','list','--head',journal['branch'],'--state','all','--json','number,url'],worktree).stdout)
                if not existing:
                    run(['gh','pr','create','--base','main','--head',journal['branch'],'--title','Adopt verified research increment '+bid[:12],'--body-file',body],worktree)
                    existing=json.loads(run(['gh','pr','list','--head',journal['branch'],'--json','number,url'],worktree).stdout)
                journal.update(pr=existing[0]['number'],pr_url=existing[0]['url'])
                save('pr_open')
            if journal['state']=='pr_open':
                pr=json.loads(run(['gh','pr','view',str(journal['pr']),'--json','state,mergeCommit,headRefOid'],self.root).stdout)
                if pr['state']=='MERGED':
                    journal['merge_commit']=pr['mergeCommit']['oid'];save('merged')
                else:
                    checks=json.loads(run(['gh','pr','checks',str(journal['pr']),'--json','name,bucket,state'],self.root,check=False).stdout or '[]')
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
                    refreshed=refresh_publication_base(journal['worktree'],journal['commit'])
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
                # Public website route applies normal publication/access rules.
                # Also read the running image, not only a release marker.
                aws=self.config.get('aws','aws'); container=self.config.get('container','inresearch-host-inresearch-1')
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
                if not all(i in rows for i in expected):save('merged');return journal
                evidence={e['id']:e for e in acceptance['knowledge']['evidence']}
                docs={d['id']:d for d in acceptance['knowledge']['documents']}
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
                atomic_json(directory/'website-proof.json',proof)
                run(['scp','-q',directory/'website-proof.json',self.config.get('spark','spark')+':'+self.spark_queue+'/'+bid+'/website-proof.json'])
                self.remote('published','--batch-id',bid,'--proof',self.spark_queue+'/'+bid+'/website-proof.json')
                save('published')
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
