#!/usr/bin/env python3
"""Compatibility command; the sole inventory writer lives in m4_triage.py.

Old invocation: m4_inventory.py --workers N
Current invocation: m4_triage.py inventory --workers N
Both use the same dataset, schema, resume rules and source binding.
"""
import sys
from m4_triage import main as triage_main


def main(argv=None):
    return triage_main(['inventory', *(sys.argv[1:] if argv is None else argv)])


if __name__ == '__main__':
    main()
