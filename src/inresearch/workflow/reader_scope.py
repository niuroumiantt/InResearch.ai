"""Explicit runtime batch scope; a broken scope never opens the entire library."""
import json
import re
from pathlib import Path
from inresearch.materials.artifacts import digest_file, read_json, safe_path
from inresearch.materials.reader_contracts import IntegrityError


def gap_counts(data, rows, cache):
    """Only sealed current reports contribute; a gap never means a read page."""
    counts=[]
    for row in rows:
        if row['state']!='complete' or not row.get('report_rel'): continue
        sha=row.get('report_sha256')
        if sha not in cache:
            path=safe_path(data,row['report_rel'])
            if digest_file(path)!=sha:raise IntegrityError()
            report=read_json(path);cache[sha]=len(report['coverage'].get('gap_pages',[]))
        counts.append(cache[sha])
    return {'complete_with_gaps':sum(n>0 for n in counts),'unread_gap_pages':sum(counts)}


class DocumentScope:
    def __init__(self, path, data):
        self.path, self.data = Path(path).expanduser(), data
        self.ids()

    def ids(self):
        if self.path.stat().st_size > 1024*1024:
            raise ValueError('reader scope is too large')
        value = json.loads(self.path.read_text(encoding='utf-8'))
        ids = value.get('doc_ids')
        if value.get('schema_version') != 1 or not isinstance(ids,list) or len(ids)>5000 or any(
                not isinstance(i,str) or not re.fullmatch(r'doc-[0-9a-f]{64}',i) for i in ids):
            raise ValueError('invalid reader document scope')
        result = set(ids)
        if value.get('include_daily_deliveries') is True:
            from inresearch.workflow.daily_dispatch import receipt_documents
            result.update('doc-'+sha for sha in receipt_documents(self.data))
        return sorted(result)
