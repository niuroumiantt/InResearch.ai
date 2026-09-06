#!/usr/bin/env python3
"""Spark candidate collection compatibility entry. See framework/06_acquisition.md.
No core price writes; originals and observations stay in the acquisition ledger.
"""
import sys
import acquisition

def main():
    args = sys.argv[1:]
    sys.argv = [sys.argv[0], 'gpu', *args]
    return acquisition.main()
if __name__ == '__main__':raise SystemExit(main())
