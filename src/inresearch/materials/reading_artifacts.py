"""Source-bound reading artifacts, shared by execution and read-only consumers."""
from __future__ import annotations
import re
from pathlib import Path
from inresearch.materials.artifacts import safe_path, digest_file, digest_bytes, read_json, atomic_json
from inresearch.materials.reader_contracts import UnsafePath, IntegrityError


class ReadingArtifacts:
    def __init__(self, data):
        self.data = Path(data)

    def artifact_path(self, doc, name):
        doc_id = doc["doc_id"]
        if not re.fullmatch(r"doc-[0-9a-f]{64}", doc_id):
            raise UnsafePath()
        prefix = 'artifacts/' + doc_id
        if doc['artifact_rel'] != prefix and not doc['artifact_rel'].startswith(prefix + '/'):
            raise UnsafePath()
        return safe_path(self.data, doc["artifact_rel"] + "/" + name)

    def _cached(self, doc, relative, marker):
        p = self.artifact_path(doc, relative)
        if not p.exists():
            return None
        value = read_json(p)
        if (not isinstance(value,dict) or value.get("_recipe") != doc["recipe"] or value.get("_marker") != marker
                or value.get("doc_id") != doc["doc_id"] or value.get('content_sha256') != doc['sha256']):
            raise IntegrityError()
        if value.get('reading_revision_id') != doc['revision_id'] and doc['artifact_rel'] != 'artifacts/' + doc['doc_id']:
            raise IntegrityError()
        return value

    def validate_report(self, doc):
        """Mechanical completeness and source binding; not semantic or C3 review."""
        if digest_file(safe_path(self.data, doc['original_rel'])) != doc['sha256']:
            raise IntegrityError()
        recipe = read_json(self.artifact_path(doc, 'recipe.json'))
        if recipe['recipe'] != doc['recipe']:
            raise IntegrityError()
        report = self._cached(doc, 'report.json', 'report')
        extraction = self._cached(doc, 'extraction.json', 'extract')
        if not report or not extraction or not extraction['chunks']:
            raise IntegrityError()
        chunks = []
        for i, item in enumerate(extraction['chunks']):
            if item['index'] != i or not 1 <= item['page_index'] <= extraction['pages_total']:
                raise IntegrityError()
            chunk = self._cached(doc, 'chunks/%06d.json' % i, 'read:%d' % i)
            text = self._chunk_text(item)
            if (not chunk or chunk['chunk_sha256'] != item['sha256'] or chunk['page_index'] != item['page_index']
                    or chunk['characters'] != len(text)):
                raise IntegrityError()
            chunks.append(chunk)
        coverage = report['coverage']
        pages = {c['page_index'] for c in chunks} | {p['page_index'] for p in extraction['pages'] if p.get('blank') or p.get('gap')}
        gaps = sorted(p['page_index'] for p in extraction['pages'] if p.get('gap'))
        if report['coverage'].get('gap_pages', []) != gaps:
            raise IntegrityError()
        counts = {'pages_total': extraction['pages_total'], 'pages_read': len(pages),
                  'chunks_total': len(chunks), 'chunks_read': len(chunks),
                  'characters_total': extraction['characters_total'],
                  'characters_read': sum(c['characters'] for c in chunks)}
        if (coverage.get('complete') is not True or any(coverage.get(k) != v for k,v in counts.items())
                or counts['pages_total'] != counts['pages_read'] or counts['characters_total'] != counts['characters_read']
                or report['evidence'] != [e for c in chunks for e in c['evidence']]
                or report['claims'] != [c for chunk in chunks for c in chunk['claims']]):
            raise IntegrityError()
        return report

    def seal(self, doc):
        """Bind the checked candidate to immutable artifact bytes before DB commit."""
        self.validate_report(doc)
        manifest_path = self.artifact_path(doc, 'manifest.json')
        files = {}
        for prefix in (doc['artifact_rel'], doc['extracted_rel']):
            for path in sorted(safe_path(self.data, prefix).rglob('*')):
                if path == manifest_path:
                    continue
                if path.is_symlink():
                    raise UnsafePath()
                if path.is_file():
                    files[path.relative_to(self.data).as_posix()] = digest_file(path)
        manifest = {'revision_id': doc['revision_id'], 'content_sha256': doc['sha256'], 'files': files}
        if manifest_path.exists():
            if read_json(manifest_path) != manifest:
                raise IntegrityError()
        else:
            atomic_json(manifest_path, manifest)
        return {'report_rel': self.artifact_path(doc, 'report.json').relative_to(self.data).as_posix(),
                'report_sha256': digest_file(self.artifact_path(doc, 'report.json')),
                'manifest_sha256': digest_file(manifest_path)}

    def verify_seal(self, doc):
        if safe_path(self.data, doc['report_rel']) != self.artifact_path(doc, 'report.json'):
            raise IntegrityError()
        manifest_path = self.artifact_path(doc, 'manifest.json')
        if not doc['manifest_sha256'] or digest_file(manifest_path) != doc['manifest_sha256']:
            raise IntegrityError()
        manifest = read_json(manifest_path)
        if manifest['revision_id'] != doc['revision_id'] or manifest['content_sha256'] != doc['sha256']:
            raise IntegrityError()
        if digest_file(self.artifact_path(doc, 'report.json')) != doc['report_sha256']:
            raise IntegrityError()
        for relative, sha in manifest['files'].items():
            if not any(relative.startswith(prefix + '/') for prefix in (doc['artifact_rel'], doc['extracted_rel'])):
                raise IntegrityError()
            if digest_file(safe_path(self.data, relative)) != sha:
                raise IntegrityError()
        return self.validate_report(doc)

    def _chunk_text(self, chunk):
        text = safe_path(self.data, chunk["text_rel"]).read_text(encoding="utf-8")
        if digest_bytes(text.encode()) != chunk["sha256"]:
            raise IntegrityError()
        return text


    def full_text(self, doc):
        """Reuse verified page chunks, preserving page labels for terminal locators."""
        extraction = self._cached(doc, 'extraction.json', 'extract')
        pages = {}
        for chunk in extraction['chunks']:
            pages.setdefault(chunk['page_index'], []).append(self._chunk_text(chunk))
        if extraction['pages_total'] == 1:
            return ''.join(pages.get(1, []))
        return '\n\n'.join('[第 %d 页]\n%s' % (page, ''.join(pages.get(page, [])))
                           for page in range(1, extraction['pages_total'] + 1))
