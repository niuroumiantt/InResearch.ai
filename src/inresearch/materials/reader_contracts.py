"""Reader states, errors and format-independent execution limits."""
import os

RECIPE_VERSION = "continuous-reader-v1"

PARTIAL_SUFFIXES = (".part", ".partial", ".tmp", ".crdownload", ".download", ".filepart")

OCR_DEFERRED_PRIORITY = 1

OCR_MAX_PAGES = int(os.environ.get("READER_OCR_MAX_PAGES", "20"))

OCR_DEFER_SECONDS = float(os.environ.get("READER_OCR_DEFER_SECONDS", "300"))

LARGE_FORMAT_POINTS = float(os.environ.get("READER_LARGE_FORMAT_POINTS", "1150"))  # short side >= A2

MAX_WORKERS = 16

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
