#!/usr/bin/env python3
"""Full SHA-256 inventory of the M4 raw-materials tree.

Read-only.  Writes one JSON line per file to inventory.jsonl (append, resumable:
files already present with the same size+mtime are skipped).  The SHA-256 is the
join key between M4's mapping table and Spark's catalog.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import m4_paths

SOURCE = m4_paths.source()
OUT = Path.home() / '.local/share/inresearch.ai/m4-triage/inventory.jsonl'

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--workers', type=int, default=4); a = ap.parse_args()
    done = {}
    if OUT.exists():
        for line in OUT.open(encoding='utf-8'):
            try: r = json.loads(line); done[r['rel']] = (r['size'], r['mtime'])
            except ValueError: pass
    todo = []
    for root, dirs, files in os.walk(SOURCE):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in files:
            if name.startswith('.'): continue
            p = Path(root) / name
            try: st = p.stat()
            except OSError: continue
            rel = str(p.relative_to(SOURCE))
            if done.get(rel) == (st.st_size, int(st.st_mtime)): continue
            todo.append((p, rel, st))
    print(json.dumps({'already': len(done), 'todo': len(todo)}), flush=True)
    t0 = time.time(); n = 0; nbytes = 0
    def work(item):
        p, rel, st = item
        try: return {'rel': rel, 'size': st.st_size, 'mtime': int(st.st_mtime), 'suffix': p.suffix.lower(), 'sha256': sha256(p)}
        except OSError as e: return {'rel': rel, 'size': st.st_size, 'mtime': int(st.st_mtime), 'suffix': p.suffix.lower(), 'error': str(e)[:120]}
    with OUT.open('a', encoding='utf-8') as out, ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(work, todo, chunksize=16):
            out.write(json.dumps(r, ensure_ascii=False) + '\n'); n += 1; nbytes += r['size']
            if n % 2000 == 0:
                out.flush(); print(json.dumps({'done': n, 'gb': round(nbytes/1e9,1), 'sec': int(time.time()-t0)}), flush=True)
    print(json.dumps({'finished': n, 'gb': round(nbytes/1e9,1), 'sec': int(time.time()-t0)}), flush=True)

if __name__ == '__main__': main()
