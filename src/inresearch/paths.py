"""Explicit repository boundary; runtime roots remain independently configured."""
import os
from pathlib import Path


def project_root():
    return Path(os.environ.get('INRESEARCH_PROJECT_ROOT', Path(__file__).resolve().parents[2])).expanduser().resolve()
