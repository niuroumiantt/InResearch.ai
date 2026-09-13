"""Reader command arguments. The workflow has no CLI parsing dependency."""
from __future__ import annotations
import os
import argparse, sys
from inresearch.adapters import models as models
from inresearch.workflow.reader import Reader
from inresearch.adapters.reader_model import ModelClient
from inresearch.materials.reader_contracts import ReaderError, MAX_WORKERS
from inresearch.materials.artifacts import encoded

def main(argv=None):
    os.umask(0o077)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", default=os.environ.get("READER_DATA_ROOT"))
    ap.add_argument("--state-root", default=os.environ.get("READER_STATE_ROOT"))
    ap.add_argument("--repo-root", default=os.environ.get("READER_REPO_ROOT"))
    ap.add_argument("--backend", choices=["ollama", "gateway", "claude_cli"], default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--ocr-model", default=None)
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--context", type=int)
    ap.add_argument("--max-output-tokens", type=int)
    ap.add_argument("--request-model", help="provider route; actual identity still must match --model")
    ap.add_argument("--stable-seconds", type=float, default=float(os.environ.get("READER_STABLE_SECONDS", "60")))
    sub = ap.add_subparsers(dest="command", required=True)
    for command in ("init", "scan", "status"):
        sub.add_parser(command)
    run = sub.add_parser("run")
    run.add_argument("--once", action="store_true", help="drain eligible jobs; future retries remain pending")
    run.add_argument("--max-jobs", type=int)
    run.add_argument("--workers", type=int, default=int(os.environ.get("READER_WORKERS", "1")),
                     help="worker threads in this process (1..%d); the Ollama server must be "
                          "configured for parallel requests for more than one to help" % MAX_WORKERS)
    retry = sub.add_parser("retry")
    retry.add_argument("--doc-id")
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--doc-id", required=True)
    for command in ("export", "backup"):
        parser = sub.add_parser(command)
        parser.add_argument("--dest", required=True)
    args = ap.parse_args(argv)
    if args.stable_seconds < 0 or (args.timeout is not None and args.timeout <= 0):
        ap.error("stability must be >= 0 and timeout > 0")
    try:
        model = ModelClient(args.backend, args.url, args.model, args.timeout, args.ocr_model,
                            args.context, args.max_output_tokens, args.request_model)
    except (ValueError, TypeError, OSError, models.InferenceError) as exc:
        ap.error(str(exc))
    reader = Reader(args.data_root, args.state_root, args.repo_root, model, args.stable_seconds).initialize()
    try:
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
                result = reader.retry(args.doc_id)
            reader.write_status()
        elif args.command == "rollback":
            with reader.worker_session():
                result = reader.rollback(args.doc_id)
        elif args.command == "export":
            result = reader.export(args.dest)
        else:
            result = reader.backup(args.dest)
        print(encoded(result))
        return 0
    except BlockingIOError:
        print(encoded({"error": "another_worker_owns_queue"}), file=sys.stderr)
        return 2
    except (ReaderError, OSError, ValueError) as exc:
        print(encoded({"error": exc.code if isinstance(exc, ReaderError) else type(exc).__name__}), file=sys.stderr)
        return 1
    finally:
        reader.close()
