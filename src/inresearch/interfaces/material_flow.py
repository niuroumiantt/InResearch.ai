"""Admin-only derived material lineage; never adopts, requeues or starts work."""
import json
import os
import subprocess
import threading
import time
from datetime import datetime,timezone
from pathlib import Path

from inresearch.delivery.material_measurements import database_sizes,sanitize,sanitize_scope
from inresearch.knowledge import registry
from inresearch.knowledge.research_readiness import summarize
from inresearch.storage.layout import workspace_path

_CACHE={}
_LOCK=threading.Lock()

def website_sizes(root):
    file=workspace_path('data/research_runtime.json',root);data=file.parent
    out={'measured_at':datetime.now(timezone.utc).isoformat(),
         'candidate_snapshot_bytes':file.stat().st_size if file.exists() else None}
    try:
        result=subprocess.run(['du','-s','-B1',str(data)],check=True,text=True,capture_output=True,timeout=10)
        out['allocated_bytes']=int(result.stdout.split()[0])
    except (OSError,ValueError,subprocess.SubprocessError):out['allocated_bytes']=None
    products=data/'raw/product-catalog'
    try:
        rows=[database_sizes(p) for p in products.glob('*.sqlite3')] if products.is_dir() else None
        out['product_database_bytes']=sum(d['file_bytes'] for d in rows) if rows is not None and all(d.get('state')=='observed' for d in rows) else None
    except (OSError,KeyError):out['product_database_bytes']=None
    return out

def snapshot(root):
    file=Path(os.environ.get('INRESEARCH_READER_SNAPSHOT',workspace_path('data/research_runtime.json',root)))
    root=Path(root)
    paths=[file]+[root/'data'/name for name in ('research_knowledge.json','datacenter_model.json','projects.json','contracts.json')]
    paths += [root/'framework'/name for name in ('research_graph.json','research_questions.json','tco_targets.json','research_demand_review.json')]
    paths.append(root/'data/facts.json')
    from inresearch.delivery.runtime_summary import control_path
    paths.append(control_path(file))
    signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else (str(p),None,None) for p in paths)
    with _LOCK:
        cached=_CACHE.get(signature)
        if cached and time.monotonic()-cached[0]<60:return cached[1]
        from inresearch.delivery.runtime_summary import load as runtime_summary
        graph,questions,curated=(json.loads((root / p).read_text()) for p in (
            'framework/research_graph.json','framework/research_questions.json','data/research_knowledge.json'))
        runtime=runtime_summary(root)
        reader=registry._reader_state(runtime)
        measurements=sanitize(reader.get('material_measurements'))
        scope=sanitize_scope(reader.get('execution_scope'))
        # Actual adopted support chain; candidate queue counters cannot grant adoption.
        adopted=[s for s in curated.get('statements',[]) if registry.supported_adoption(s,curated)]
        review=registry._research_verification(reader.get('research_verification'))
        review={k:v for k,v in review.items() if k in ('state','generated','last_change','candidates','active_batches')}
        result={'schema_version':1,'generated':datetime.now(timezone.utc).isoformat(),
                'received_at':reader.get('received_at'),'stale':reader.get('stale',True),
                'measurements':measurements,'execution_scope':scope,
                'review':review,
                'website':website_sizes(root),'formal':{'statements':len(adopted)}}
        def read(name):
            return json.loads((root/name).read_text())
        result['research'] = summarize(read('framework/tco_targets.json'), questions['records'], curated,
            read('data/datacenter_model.json'), graph,
            completed_question_ids=registry.completed_questions(curated),
            supported_statement_ids=[s['id'] for s in adopted], acquisition=reader.get('acquisition'))
        from inresearch.knowledge.research_gaps import build as research_gaps
        gaps = research_gaps(root)
        result['research_gaps'] = {'counts': gaps['counts'], 'records': gaps['records']}
        for name in ('projects','contracts'):
            rows=json.loads((root/'data'/(name+'.json')).read_text())['records']
            result['formal'][name]=len(rows)
        _CACHE.clear();_CACHE[signature]=(time.monotonic(),result)
        return result
