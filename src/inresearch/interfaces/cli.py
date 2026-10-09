"""One local command surface for people and terminal agents. Lazy task imports."""

from inresearch.paths import project_root
import argparse
import importlib
import json
import sys
from pathlib import Path
from inresearch.storage.files import CommitUncertain

ROOT = project_root()
JSON_COMMANDS = ('add-price', 'assign', 'receive-snapshot')
COMMANDS = {
    'editorial-sync': 'inresearch.adapters.editorial_sync',
    'pipeline': 'inresearch.workflow.project_pipeline',
    'research-match': 'inresearch.workflow.research_match',
    'daily-events': 'inresearch.materials.daily_events',
    'product-catalog': 'inresearch.workflow.product_catalog',
    'storage': 'inresearch.storage.layout',
    'models': 'inresearch.adapters.models',
    'serve': 'inresearch.interfaces.http', 'users': 'inresearch.interfaces.users', 'reader': 'inresearch.interfaces.reader',
    'inventory': 'inresearch.materials.inventory', 'triage': 'inresearch.workflow.triage', 'score': 'inresearch.workflow.score',
    'batch': 'inresearch.workflow.terminal_batch', 'deep-read': 'inresearch.interfaces.deep_read', 'organize': 'inresearch.materials.organize',
    'mapping': 'inresearch.materials.mapping', 'preflight': 'inresearch.materials.preflight',
    'attribution': 'inresearch.workflow.attribution', 'progress': 'inresearch.workflow.progress',
    'receive': 'inresearch.materials.receive', 'publish': 'inresearch.delivery.publish', 'ocr-worker': 'inresearch.adapters.ocr_worker',
    'pdf-text': 'inresearch.adapters.pdf_text',
    'acquisition': 'inresearch.adapters.acquisition', 'news-sync': 'inresearch.adapters.news_sync',
    'historical-brief': 'inresearch.adapters.historical_brief',
    'acquisition-status': 'inresearch.delivery.acquisition_status', 'reader-status': 'inresearch.delivery.reader_status',
    'reader-progress': 'inresearch.delivery.reader_progress',
    'backup': 'inresearch.delivery.backup', 'library': 'inresearch.materials.library',
    'asset-check': 'inresearch.adapters.asset_check', 'asset-compare': 'inresearch.adapters.asset_compare', 'asset-download': 'inresearch.adapters.asset_download',
    'registry': 'inresearch.knowledge.registry', 'facts': 'inresearch.knowledge.facts', 'validate': 'inresearch.knowledge.validate', 'verify': 'inresearch.knowledge.verify',
    'governance': 'inresearch.interfaces.governance', 'targets': 'inresearch.knowledge.targets', 'deliveries': 'inresearch.knowledge.deliveries', 'nodes': 'inresearch.knowledge.nodes', 'graph': 'inresearch.knowledge.graph', 'dashboard': 'inresearch.knowledge.dashboard', 'indicators': 'inresearch.knowledge.indicators', 'company-ids': 'inresearch.knowledge.company_ids',
    'coverage': 'inresearch.knowledge.coverage', 'reading-queue': 'inresearch.workflow.reading_queue', 'workorders': 'inresearch.workflow.workorders',
    'submissions': 'inresearch.workflow.submissions', 'export': 'inresearch.delivery.export', 'map': 'inresearch.delivery.map',
    'daily-receive': 'inresearch.materials.daily_bundle',
    'project-review': 'inresearch.workflow.project_review',
    'research-review': 'inresearch.workflow.research_review',
    'research-publish': 'inresearch.workflow.research_publish',
    'material-retention': 'inresearch.materials.retention',
    'fetchspec-receive': 'inresearch.materials.fetchspec_receive',
    'publish-pilot-progress': 'inresearch.delivery.publish_pilot_progress',
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path,
                    help='project root for ' + ', '.join(JSON_COMMANDS) + ' only; runtime layout still applies')
    ap.add_argument('command', choices=sorted([*COMMANDS, *JSON_COMMANDS]))
    ap.add_argument('args', nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.command in COMMANDS:
        if args.root is not None:
            ap.error('global --root applies only to ' + ', '.join(JSON_COMMANDS) +
                     '; use directory options supported by ' + args.command + ' after its command name')
        previous_argv = sys.argv
        try:
            sys.argv = [args.command, *args.args]
            module = importlib.import_module(COMMANDS[args.command])
            return module.main()
        finally:
            sys.argv = previous_argv
    root = args.root if args.root is not None else ROOT
    from inresearch.workflow import commands as commands
    command = argparse.ArgumentParser(prog='inresearch ' + args.command)
    command.add_argument('--input', type=Path, help='JSON file; otherwise read stdin')
    command.add_argument('--actor', default='local-cli')
    options = command.parse_args(args.args)
    try:
        payload = json.loads(options.input.read_text() if options.input else sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError('JSON object required')
        if args.command == 'add-price':
            reply = commands.add_price(root, payload)
        elif args.command == 'assign':
            reply = commands.assign(root, payload, by=options.actor)
        else:
            reply = commands.receive_snapshot(root, payload)
        print(json.dumps(reply, ensure_ascii=False))
        return 0
    except CommitUncertain as exc:
        print(json.dumps({'ok': False, 'status': 503, 'error': str(exc),
                          'commit_state': 'visible_durability_unconfirmed'}))
        return 1
    except (ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'ok': False, 'status': getattr(exc, 'status', 400), 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
