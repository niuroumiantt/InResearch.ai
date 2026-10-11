"""Deterministic extraction from archived JSON selectors, never an adoption."""
import argparse
import json
from pathlib import Path
from inresearch.workflow.object_review import source, pointer, prepare


def extract(root,data,plan):
    claims=[];seen=set()
    for item in plan:
        path,_,_=source(data,item['sha256'])
        if path.suffix!='.json': raise ValueError('fixed_json_extractor_requires_json_original')
        native=json.loads(path.read_text(encoding='utf-8'))
        for field in item['fields']:
            value=pointer(native,field['pointer'])
            claim={'object':item['object'],'metric':field['metric'],'value':value,
                   'unit':field.get('unit','native'),'scope':field.get('scope',item['scope']),
                   'kind':field.get('kind','reported'),'basis':item['basis'],'effective_at':item.get('effective_at'),
                   'published_at':item.get('published_at'),
                   'evidence':{'sha256':item['sha256'],'locator':field['pointer']}}
            for k in ('period_start','period_end','assumptions'):
                if k in item: claim[k]=item[k]
            key=json.dumps(claim,sort_keys=True,ensure_ascii=False)
            if key not in seen: claims.append(claim);seen.add(key)
    prepare(root,data,claims)
    return claims


def main(argv=None):
    from inresearch.paths import project_root
    from inresearch.storage.files import write_json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv);claims=extract(project_root(),a.data,json.loads(a.plan.read_text()));write_json(a.output,claims)
    print(json.dumps({'candidates':len(claims),'model_calls':0,'adopted':0}))
