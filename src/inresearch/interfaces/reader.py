"""Reader command arguments. The workflow has no CLI parsing dependency."""
from __future__ import annotations
import os
import argparse, sqlite3, sys
from inresearch.materials.reader_contracts import ReaderError, MAX_WORKERS, FULL_READ_MIN_PRIORITY, CLAIM_MIN_PRIORITY, PARK_REASONS
from inresearch.materials.artifacts import encoded
from inresearch.workflow.reading_results import ReadingResults

def main(argv=None):
    os.umask(0o077)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", default=os.environ.get("READER_DATA_ROOT"))
    ap.add_argument("--state-root", default=os.environ.get("READER_STATE_ROOT"))
    ap.add_argument("--repo-root", default=os.environ.get("READER_REPO_ROOT"))
    ap.add_argument("--backend", choices=["ollama", "gateway", "claude_cli", "codex_cli"], default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--ocr-model", default=None)
    ap.add_argument('--pdf-mode', choices=['full_visual', 'native_text_only'],
                    default=os.environ.get('READER_PDF_MODE', 'native_text_only'))
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--context", type=int)
    ap.add_argument("--max-output-tokens", type=int)
    ap.add_argument("--request-model", help="provider route; actual identity still must match --model")
    ap.add_argument("--stable-seconds", type=float, default=float(os.environ.get("READER_STABLE_SECONDS", "60")))
    sub = ap.add_subparsers(dest="command", required=True)
    for command in ("init", "scan", "status"):
        sub.add_parser(command)
    current = sub.add_parser('current', help='read the current full-reading result without creating or upgrading a catalog')
    current.add_argument('--sha', required=True)
    run = sub.add_parser("run")
    run.add_argument("--once", action="store_true", help="drain eligible jobs; future retries remain pending")
    run.add_argument("--max-jobs", type=int)
    run.add_argument("--workers", type=int, default=int(os.environ.get("READER_WORKERS", "1")),
                     help="worker threads in this process (1..%d); the Ollama server must be "
                          "configured for parallel requests for more than one to help" % MAX_WORKERS)
    retry = sub.add_parser("retry")
    retry.add_argument("--doc-id")
    retry.add_argument("--revision-id")
    retry.add_argument("--error-code",
                       help="only this block reason; a parser fix retires one class, not all")
    retry_job = sub.add_parser('retry-job', help='CAS retry one failed read job online; preserve attempts and source artifacts')
    for name in ('doc-id','revision-id','stage','expected-error','expected-recipe','expected-recipe-sha256','request-id','by','reason'):
        retry_job.add_argument('--' + name, required=True)
    retry_job.add_argument('--chunk-index', type=int, required=True)
    retry_job.add_argument('--expected-attempts', type=int, required=True)
    retry_job.add_argument('--dry-run', action='store_true')
    reread = sub.add_parser('reread', help='create a separately reviewed reading candidate')
    for name in ('doc-id','expected-current','request-id','reason'):
        reread.add_argument('--' + name, required=True)
    restart = sub.add_parser('restart-unfinished',help='retain unfinished attempts and explicitly freeze a new execution model')
    for name in ('doc-id','expected-revision','request-id','reason'):
        restart.add_argument('--'+name,required=True)
    revisions = sub.add_parser('revisions')
    revisions.add_argument('--doc-id', required=True)
    inspect = sub.add_parser('inspect-revision')
    inspect.add_argument('--revision-id', required=True)
    activate = sub.add_parser('activate-revision', help='switch current reading, never C3 adoption')
    for name in ('revision-id','expected-current','expected-report-sha256','reviewer','reason'):
        activate.add_argument('--' + name, required=True)
    reject = sub.add_parser('reject-revision')
    for name in ('revision-id','reviewer','reason'):
        reject.add_argument('--' + name, required=True)
    deepen = sub.add_parser('deepen', help='continue summary-depth readings to full coverage')
    deepen.add_argument('--doc-id', action='append', required=True)
    park = sub.add_parser('park', help='park documents triage ruled out of reading; plans unless --commit')
    park.add_argument('--sha256-file', required=True, help='one full SHA-256 per line')
    park.add_argument('--reason', choices=sorted(PARK_REASONS), required=True)
    park.add_argument('--commit', action='store_true')
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--doc-id", required=True)
    triage = sub.add_parser('apply-triage', help="adopt another machine's filing; plans unless --commit")
    triage.add_argument('--mapping', required=True)
    triage.add_argument('--commit', action='store_true',
                        help='place the links and set priorities; without it nothing is written')
    for command in ("export", "backup"):
        parser = sub.add_parser(command)
        parser.add_argument("--dest", required=True)
        if command == "export":
            parser.add_argument("--doc-id", action="append",
                                help="include only this complete document in a scoped candidate export; repeat as needed")
    args = ap.parse_args(argv)
    if args.command == 'retry-job':
        from inresearch.workflow.reader_retry_job import retry_job
        try:
            result = retry_job(args.data_root, doc_id=args.doc_id, revision_id=args.revision_id,
                               stage=args.stage, chunk_index=args.chunk_index,
                               error_code=args.expected_error, expected_attempts=args.expected_attempts,
                               expected_recipe=args.expected_recipe, expected_recipe_sha256=args.expected_recipe_sha256,
                               request_id=args.request_id,
                               by=args.by, reason=args.reason, dry_run=args.dry_run)
            print(encoded(result))
            return 0
        except (ReaderError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            print(encoded({'error': exc.code if isinstance(exc, ReaderError) else type(exc).__name__}), file=sys.stderr)
            return 1
    if args.command == 'current':
        try:
            print(encoded(ReadingResults(args.data_root).current(args.sha)))
            return 0
        except (ReaderError, OSError, ValueError, sqlite3.Error) as exc:
            print(encoded({'error': exc.code if isinstance(exc, ReaderError) else str(exc)}), file=sys.stderr)
            return 1
    if args.command == 'apply-triage':
        # Checked before the Reader exists, because constructing it migrates a
        # v1 catalog -- which a plan must never do as a side effect.
        from inresearch.workflow.apply_triage import refuse_unless_current
        refusal = refuse_unless_current(args.data_root)
        if refusal:
            print(encoded({'error': refusal}), file=sys.stderr)
            return 1
    if args.stable_seconds < 0 or (args.timeout is not None and args.timeout <= 0):
        ap.error("stability must be >= 0 and timeout > 0")
    from inresearch.adapters import models
    from inresearch.adapters.reader_model import ModelClient
    from inresearch.workflow.reader import Reader
    try:
        model = ModelClient(args.backend, args.url, args.model, args.timeout, args.ocr_model,
                            args.context, args.max_output_tokens, args.request_model)
    except (ValueError, TypeError, OSError, models.InferenceError) as exc:
        ap.error(str(exc))
    # Only the long-running worker reads machine sensors; one-off commands never wait on them.
    temperature = None
    if args.command == "run" and not (model.backend=='codex_cli' and model.url):
        from inresearch.adapters.thermal import read_celsius as temperature
    reader = Reader(args.data_root, args.state_root, args.repo_root, model, args.stable_seconds,
                    temperature=temperature, full_read_min_priority=FULL_READ_MIN_PRIORITY,
                    claim_min_priority=CLAIM_MIN_PRIORITY, pdf_mode=args.pdf_mode)
    try:
        reader.initialize()
        if args.command == "run":
            result = reader.run(args.once, args.max_jobs, workers=args.workers)
        elif args.command == "scan":
            with reader.worker_session():
                result = reader.scan()
            reader.write_status()
        elif args.command in {"status", "init"}:
            result = reader.write_status()
        elif args.command == "retry":
            with reader.worker_session():
                result = reader.retry(args.doc_id, args.revision_id, args.error_code)
            reader.write_status()
        elif args.command == 'deepen':
            with reader.worker_session():
                result = reader.deepen(args.doc_id)
            reader.write_status()
        elif args.command == 'park':
            import re as _re
            from pathlib import Path as _Path
            shas = [line.strip().lower() for line in _Path(args.sha256_file).read_text(encoding='utf-8').splitlines() if line.strip()]
            if any(not _re.fullmatch(r'[0-9a-f]{64}', sha) for sha in shas):
                ap.error('sha256 file must hold one full SHA-256 per line')
            with reader.worker_session():
                result = reader.park(shas, args.commit, PARK_REASONS[args.reason])
            reader.write_status()
        elif args.command == 'reread':
            result = reader.revisions.request(args.doc_id,args.expected_current,args.request_id,args.reason)
        elif args.command == 'restart-unfinished':
            with reader.worker_session():
                result = reader.revisions.restart_unfinished(args.doc_id,args.expected_revision,args.request_id,args.reason)
            reader.write_status()
        elif args.command == 'revisions':
            result = reader.revisions.list(args.doc_id)
        elif args.command == 'inspect-revision':
            result = reader.revisions.inspect(args.revision_id)
        elif args.command == 'activate-revision':
            result = reader.revisions.activate(args.revision_id,args.expected_current,args.expected_report_sha256,args.reviewer,args.reason)
        elif args.command == 'reject-revision':
            result = reader.revisions.reject(args.revision_id,args.reviewer,args.reason)
        elif args.command == "rollback":
            with reader.worker_session():
                result = reader.rollback(args.doc_id)
        elif args.command == 'apply-triage':
            from pathlib import Path as _Path
            from inresearch.materials.mapping import load_mapping
            from inresearch.workflow import apply_triage
            header, rows = load_mapping(_Path(args.mapping))
            # The worker lock is held for the plan too: a plan made while the
            # reader is filing documents describes a catalog that no longer
            # exists by the time anyone reads it.
            with reader.worker_session():
                actions, counts = apply_triage.plan(reader.conn, rows)
                result = {'mapping': header.get('generated'), 'dataset': header.get('dataset'),
                          'plan': counts, 'actions': len(actions), 'committed': bool(args.commit)}
                if args.commit:
                    done, failures = apply_triage.commit(reader, actions)
                    result.update(done)
                    if failures:
                        result['failures'] = failures[:20]
                        result['failed_total'] = len(failures)
            reader.write_status()
        elif args.command == "export":
            result = reader.export(args.dest, doc_ids=args.doc_id)
        else:
            result = reader.backup(args.dest)
        print(encoded(result))
        return 0
    except BlockingIOError:
        print(encoded({"error": "another_worker_owns_queue"}), file=sys.stderr)
        return 2
    except (ReaderError, OSError, ValueError, sqlite3.Error) as exc:
        print(encoded({"error": exc.code if isinstance(exc, ReaderError) else type(exc).__name__}), file=sys.stderr)
        return 1
    finally:
        reader.close()
