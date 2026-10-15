#!/usr/bin/env python3
"""m5: explicitly isolated local handoff acceptance; never production intake."""
import argparse
import json
import errno
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from inresearch.materials.collector_receive import receive, lookup_receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', nargs='?')
    parser.add_argument('--lookup-provider')
    parser.add_argument('--lookup-delivery')
    parser.add_argument('--sandbox-root', required=True)
    args = parser.parse_args()
    if bool(args.lookup_provider) != bool(args.lookup_delivery) or bool(args.package) == bool(args.lookup_provider):
        parser.error('provide either a package or both lookup identifiers')
    try:
        if args.lookup_provider:
            receipt = lookup_receipt(args.sandbox_root,args.lookup_provider,args.lookup_delivery)
            result = {'local_only':True,'found':receipt is not None,'receipt':receipt}
        else:
            result = receive(args.package,args.sandbox_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        print(json.dumps({'local_only': True, 'received': False, 'error_type': type(error).__name__,
                          'error_category': ('busy' if getattr(error,'errno',None) in (errno.EAGAIN,errno.EWOULDBLOCK) else 'local_storage' if isinstance(error,(OSError,sqlite3.Error)) else 'integrity_conflict'),
                          'next_action': 'inspect package; originals and previous receipts retained'}), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
