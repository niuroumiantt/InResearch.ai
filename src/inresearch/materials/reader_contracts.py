"""Reader states, errors and format-independent execution limits."""
import os

RECIPE_VERSION = "continuous-reader-v1"

PARTIAL_SUFFIXES = (".part", ".partial", ".tmp", ".crdownload", ".download", ".filepart")

OCR_DEFERRED_PRIORITY = 1

OCR_MAX_PAGES = int(os.environ.get("READER_OCR_MAX_PAGES", "20"))

OCR_DEFER_SECONDS = float(os.environ.get("READER_OCR_DEFER_SECONDS", "300"))

LARGE_FORMAT_POINTS = float(os.environ.get("READER_LARGE_FORMAT_POINTS", "1150"))  # short side >= A2

MAX_WORKERS = 16

# Before claiming a job the reader pauses while the hottest GPU/thermal-zone reading
# is above this limit, then re-reads after the pause. 0 disables the guard.
THERMAL_LIMIT_C = float(os.environ.get("READER_THERMAL_LIMIT_C", "85"))

THERMAL_PAUSE_SECONDS = float(os.environ.get("READER_THERMAL_PAUSE_SECONDS", "60"))

# How long a reading at or below the limit is trusted before the next claim reads again.
THERMAL_SAMPLE_SECONDS = 10.0

# Documents whose effective priority after triage is below this get a summary-depth
# reading (sampled chunks only); at or above it, every chunk is read. 1 reads all in full.
FULL_READ_MIN_PRIORITY = int(os.environ.get("READER_FULL_READ_MIN_PRIORITY", "7"))

# Error codes for documents parked by a triage decision; `retry --error-code` revives them.
# derived_artifact: reader output copied back into intake (e.g. M4 要删/reader/), not source material.
PARKED_BY_TRIAGE = "parked_l1_score_zero"
PARK_REASONS = {"l1_score_zero": PARKED_BY_TRIAGE, "derived_artifact": "parked_derived_artifact"}

MODULES = {"M%02d" % i for i in range(1, 16)}

class ReaderError(Exception):
    code = "reader_error"

class Blocked(ReaderError):
    def __init__(self, code):
        self.code = code

class Deferred(ReaderError):
    """Not a failure: the job goes back to pending without spending an attempt."""

    def __init__(self, code):
        self.code = code

class UnsafePath(ReaderError):
    code = "unsafe_path"

class IntegrityError(ReaderError):
    code = "integrity_mismatch"

class ModelError(ReaderError):
    code = "model_failure"

class ModelOutputError(ModelError):
    code = "model_output_invalid"
