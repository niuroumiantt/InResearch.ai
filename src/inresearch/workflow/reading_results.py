"""One current full-reading result, queried without a model or a second ledger."""
from __future__ import annotations
import os
import re
from contextlib import contextmanager
from pathlib import Path
from inresearch.materials.artifacts import safe_path
from inresearch.materials.reading_artifacts import ReadingArtifacts
from inresearch.materials.reader_contracts import IntegrityError
from inresearch.storage.catalog import Catalog


class ReadingResults:
    def __init__(self, data_root=None):
        self.data = Path(data_root or os.environ.get('READER_DATA_ROOT') or
                         Path.home()/'.local/share/inresearch.ai').expanduser().resolve()
        self.artifacts = ReadingArtifacts(self.data)

    @contextmanager
    def _snapshot(self):
        path = safe_path(self.data, 'catalog/catalog.sqlite')
        if not path.exists():
            yield None
            return
        catalog = Catalog(path, read_only=True)
        try:
            with catalog.read_snapshot():
                if catalog.conn.execute('PRAGMA user_version').fetchone()[0] != 2:
                    raise ValueError('reader_catalog_version_requires_explicit_upgrade')
                yield catalog.conn
        finally:
            catalog.close()

    def current(self, sha, *, include_text=False):
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('current reading requires a complete content SHA-256')
        result = dict(content_sha256=sha, authority='reader_catalog', acceptance='candidate_only')
        with self._snapshot() as conn:
            if conn is None:
                return dict(result, status='catalog_missing')
            row = conn.execute('SELECT * FROM current_readings WHERE sha256=?', (sha,)).fetchone()
            if row is None:
                return dict(result, status='not_registered')
            doc = dict(row)
            if not doc['current_revision_id']:
                return dict(result, status='no_current_result', execution_state=doc['state'])
            reference = dict(reading_revision_id=doc['revision_id'], report_sha256=doc['report_sha256'])
            if not doc['manifest_sha256']:
                return dict(result, **reference, status='legacy_unverified')
            try:
                report = self.artifacts.verify_seal(doc)
                text = self.artifacts.full_text(doc) if include_text else None
            except (KeyError, TypeError, IndexError) as exc:
                raise IntegrityError() from exc
            result.update(reference, status='available', report=report,
                          report_path=str(safe_path(self.data, doc['report_rel'])),
                          verification='source_coverage_artifact_integrity_not_semantic_review',
                          review=doc['review_json'])
            if include_text:
                result['text'] = text
            return result

    def status(self):
        """Catalog counts are inventory, not a fresh quality audit of every report."""
        with self._snapshot() as conn:
            if conn is None:
                return dict(status='catalog_missing', authority='reader_catalog', catalog_current_results=0)
            current, sealed = conn.execute('SELECT COUNT(*),COUNT(r.manifest_sha256) FROM documents d JOIN reading_runs r ON r.revision_id=d.current_revision_id').fetchone()
            return dict(status='available', authority='reader_catalog', catalog_current_results=current,
                        sealed_current_results=sealed, legacy_unverified_results=current-sealed,
                        acceptance='candidate_only', verification='catalog_inventory_only')
