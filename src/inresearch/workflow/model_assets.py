"""Import visual candidates under one manifest transaction; never adopt or overwrite."""
from inresearch.materials import model_assets as assets
from inresearch.storage.files import atomic_write, locked, write_json


def import_candidate(root, filename, data, *, page, source, license, hide_rack=False):
    """No overwrites; an unregistered complete file is safely replayable."""
    entry = dict(file=filename, page=page, source=source, license=license,
                 status='candidate', sha256=assets.validate_glb(data), hideRack=hide_rack)
    assets.validate_entry(entry)
    directory = assets.model_directory(root)
    with locked(directory / 'manifest.json'):
        manifest = assets.read_manifest(root, verify_files=True)
        existing = next((m for m in manifest['models'] if m['file'] == filename), None)
        if existing:
            if existing['sha256'] != entry['sha256'] or existing['page'] != page:
                raise ValueError('model_version_conflict_use_new_filename')
            return existing  # Retry must not revoke an existing decision or placement.
        target = directory / filename
        if target.is_symlink():
            raise ValueError('unsafe_model_destination')
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('model_version_conflict_use_new_filename')
        else:
            atomic_write(target, data, exclusive=True)
        manifest['models'].append(entry)
        write_json(directory / 'manifest.json', manifest)
        return entry
