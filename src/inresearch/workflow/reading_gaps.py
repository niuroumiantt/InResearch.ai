"""One metric-gap ledger: stable proposals, atomic batches and replayable filling."""
import hashlib
import json
from pathlib import Path
from inresearch.storage.files import atomic_write
from inresearch.storage.jsonl import JsonlStore, read_rows


class ReadingGaps:
    def __init__(self, path):
        self.path = Path(path)

    def current(self):
        return {r['gap_id']: r for r in read_rows(self.path) if r.get('gap_id')}

    def open(self):
        return [r for r in self.current().values() if not r.get('filled')]

    def _append_batch(self, rows):
        # The caller holds the existing ledger lock and has replayed its contents.
        # Preserve historical rows; one replacement commits the entire new batch.
        if rows:
            old = self.path.read_bytes() if self.path.exists() else b''
            addition = ''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in rows)
            atomic_write(self.path, old + addition.encode('utf-8'))

    def propose(self, document, texts, at):
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError('缺口须为非空文本')
        with JsonlStore(self.path).locked():
            known = self.current()
            proposed = {}
            for text in texts:
                gap_id = hashlib.sha256(('%s|%s' % (document['sha256'], text)).encode()).hexdigest()[:12]
                row = dict(gap_id=gap_id, at=at, sha256=document['sha256'],
                           rel=document.get('rel'), module=document.get('category'), gap=text)
                if gap_id in known and (known[gap_id].get('sha256'), known[gap_id].get('gap')) != (row['sha256'], text):
                    raise ValueError('gap_identity_conflict')
                proposed[gap_id] = row
            fresh = [r for key, r in proposed.items() if key not in known]
            self._append_batch(fresh)
            return dict(gap_ids=list(proposed), gaps_recorded=len(fresh),
                        replayed=len(proposed)-len(fresh))

    def fill(self, identifiers, at):
        identifiers = list(dict.fromkeys(identifiers))
        with JsonlStore(self.path).locked():
            known = self.current()
            unknown = [key for key in identifiers if key not in known]
            if unknown:
                raise ValueError('这些 gap_id 不在缺口台账里：' + ' '.join(unknown))
            fresh = [{**known[key], 'filled': at} for key in identifiers if not known[key].get('filled')]
            self._append_batch(fresh)
            return dict(filled=identifiers, replayed=len(identifiers)-len(fresh), remaining=len(self.open()))
