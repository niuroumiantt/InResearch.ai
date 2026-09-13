#!/usr/bin/env python3
"""Read the Spark collection projection; do not run remote collection on the web host."""
import json
import sys
from inresearch.knowledge import registry as research

def main():
    reader=research.build_snapshot()['reader']
    acquisition=reader.get('acquisition',{'status':'not_connected','sources':{}})
    source=sys.argv[1] if len(sys.argv)>1 else None
    print(json.dumps({'reader_status':reader.get('status'),'stale':reader.get('stale',False),
        'acquisition':acquisition.get('sources',{}).get(source) if source else acquisition},ensure_ascii=False,indent=2))
    print('第一阶段：Spark 有界采集与原件台账；本按钮只查状态。周期调度、全文翻译和采用仍分步实施。')
    print('现行规范：framework/06_acquisition.md')
    return 0 if reader.get('status')!='not_connected' and not reader.get('stale') else 1
if __name__=='__main__':raise SystemExit(main())
