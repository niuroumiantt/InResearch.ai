#!/usr/bin/env python3
"""Source-checkout launcher; all commands live in the importable package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from inresearch.interfaces.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
