#!/usr/bin/env python3
"""m5: explicitly isolated local handoff acceptance; never production intake."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from inresearch.materials.collector_receive import receive

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--sandbox-root', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(receive(args.package, args.sandbox_root), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'local_only': True, 'received': False, 'error_type': type(error).__name__,
                          'next_action': 'inspect package; originals and previous receipts retained'}), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
