#!/usr/bin/env python3
"""M4 triage, level L1: preview-based scoring with the configured research model.

Task definition: docs/M4_TRIAGE_TASK.md.
This script never renames, moves or deletes anything.  It reads the SHA-256
inventory, extracts a bounded text preview per file, asks the model for a
structured judgement, and appends one JSON line per file to l1_results.jsonl.
Moving/renaming is a separate, later step driven by the mapping table.

Modes:
  preview  --limit N        extract previews only, no API call (free dry run)
  sample   --limit N        synchronous API calls for N files, prints a summary
  run      [--limit N]      score pending files through the shared model
  collect                   drain previously submitted Anthropic batches
"""
from __future__ import annotations
from inresearch.materials import triage as L1
from inresearch.storage.jsonl import append_record
from inresearch.materials.records import commit_result, result_revision, current_results
import argparse, json, os, random, sys
from pathlib import Path

from inresearch.storage.jsonl import read_rows as read_rows

from inresearch.adapters import models as models

# iWork and MS Project: still no stdlib reader, so still judged on the name.

# Derived artifacts of the previous pipeline run: text caches, batch spools and
# reader state.  User decision 2026-09-09: these never go to the model; they are
# still inventoried and still get a row in the mapping table.


def load_env():
    if os.environ.get('ANTHROPIC_API_KEY'):
        return
    for p in (Path.home() / '.config/inresearch.ai/anthropic.env', Path.home() / '.config/anthropic/api_key'):
        if p.is_file():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip().strip('"'))
                else:
                    os.environ.setdefault('ANTHROPIC_API_KEY', line)
            return


_moved: tuple | None = None


def cmd_preview(args):
    items = L1.load_inventory(); random.Random(args.seed).shuffle(items)
    n = 0
    for it in items:
        if n >= args.limit: break
        rec = L1.prepare(it)
        if args.text_only and rec['level'] != 'p': continue
        n += 1
        print(json.dumps({'rel': rec['rel'], 'level': rec['level'], 'category': rec['category'], 'needs_model': rec['needs_model'], 'preview_chars': len(rec['preview']), 'meta': rec['meta'], 'head': rec['preview'][:160]}, ensure_ascii=False))


def legacy_batch_client():
    load_env()
    import anthropic
    if not os.environ.get('ANTHROPIC_API_KEY'):
        sys.exit('ANTHROPIC_API_KEY not set: put it in ~/.config/inresearch.ai/anthropic.env as ANTHROPIC_API_KEY=... (chmod 600)')
    return anthropic.Anthropic(max_retries=3)


def cmd_sample(args):
    model = models.configured_client()
    system = L1.task_card()
    items = L1.load_inventory(); random.Random(args.seed).shuffle(items)
    base = current_results(L1.RESULTS)
    done = L1.done_keys(); count = errors = conflicts = 0
    L1.DATA.mkdir(parents=True, exist_ok=True)
    for item in items:
        if count >= args.limit:
            break
        if item['sha256'] in done:
            continue
        try:
            rec = L1.prepare(item)
        except (OSError, ValueError) as exc:
            errors += 1
            print(json.dumps({'sha256': item['sha256'], 'error': str(exc)[:160]}))
            continue
        if not rec['needs_model'] or (args.text_only and rec['level'] != 'p'):
            continue
        try:
            value = model.generate(system, L1.user_message(rec, rec['preview'], rec['meta'], rec['level']))
            out = L1.finalize(rec, L1.validate_judgement(value), None, None)
        except (models.InferenceError, ValueError) as exc:
            out = L1.finalize(rec, None, None, str(exc))
            errors += 1
        out['proposed_name'] = L1.proposed_name(out)
        try:
            commit_result(L1.RESULTS, out, result_revision(base.get(out['sha256'])))
        except ValueError as exc:
            if str(exc) != 'result_revision_conflict': raise
            conflicts += 1
            continue
        count += 1
    print(json.dumps({'files': count, 'errors': errors, 'conflicts': conflicts}))


def cmd_run(args):
    # Keep one implementation of the pending-file loop and its concurrency.
    from inresearch.workflow import score as m4_triage_local
    m4_triage_local.cmd_run(args)


def cmd_collect(args):
    c = legacy_batch_client(); pending = L1.DATA / 'l1_pending'
    seen = set(); rows = []
    for line in L1.BATCHES.open(encoding='utf-8'):
        r = json.loads(line)
        if r['id'] in seen: continue
        seen.add(r['id']); rows.append(r)
    base = current_results(L1.RESULTS)
    done = L1.done_keys(); n = 0
    for r in rows:
        if r.get('collected'): continue
        b = c.messages.batches.retrieve(r['id'])
        print(json.dumps({'batch': b.id, 'status': b.processing_status, 'counts': b.request_counts.model_dump()}))
        if b.processing_status != 'ended': continue
        for res in c.messages.batches.results(b.id):
            sha = res.custom_id
            if sha in done: continue
            p = pending / (sha + '.json')
            if not p.exists(): continue
            rec = json.loads(p.read_text())
            if res.result.type == 'succeeded':
                msg = res.result.message
                if msg.stop_reason == 'refusal':
                    out = L1.finalize(rec, None, None, 'refusal')
                else:
                    text = next(bk.text for bk in msg.content if bk.type == 'text'); u = msg.usage
                    out = L1.finalize(rec, {**L1.validate_judgement(json.loads(text)), '_model': {'actual': msg.model, 'backend': 'anthropic_legacy_batch'}}, {'in': u.input_tokens, 'out': u.output_tokens, 'cache_read': getattr(u, 'cache_read_input_tokens', 0) or 0}, None)
            else:
                out = L1.finalize(rec, None, None, 'batch_' + res.result.type)
            out['proposed_name'] = L1.proposed_name(out); out['batch'] = b.id
            commit_result(L1.RESULTS, out, result_revision(base.get(sha))); n += 1; p.unlink()
        append_record(L1.BATCHES, {**r, 'collected': True})
    print(json.dumps({'collected': n}))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('preview'); p.add_argument('--limit', type=int, default=20); p.add_argument('--seed', type=int, default=7); p.add_argument('--text-only', action='store_true')
    s = sub.add_parser('sample'); s.add_argument('--limit', type=int, default=50); s.add_argument('--seed', type=int, default=7); s.add_argument('--text-only', action='store_true')
    r = sub.add_parser('run'); r.add_argument('--limit', type=int, default=0); r.add_argument('--workers', type=int, default=1)
    sub.add_parser('collect')
    a = ap.parse_args()
    {'preview': cmd_preview, 'sample': cmd_sample, 'run': cmd_run, 'collect': cmd_collect}[a.cmd](a)

if __name__ == '__main__':
    main()
