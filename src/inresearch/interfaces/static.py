"""Public URLs are stable; only their declared source files are served."""
import json
from pathlib import Path

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path, LayoutError
from inresearch.materials import model_assets


def source_path(url_path, root=None):
    root = Path(root or project_root()).resolve()
    routes = json.loads((root / 'web/routes.json').read_text())
    relative = routes.get(url_path)
    if url_path.startswith('/assets/models/') and url_path.endswith('.glb'):
        try:
            registered = model_assets.read_manifest(root)['models']
            relative = next(('web/assets/models/' + m['file'] for m in registered
                             if url_path == '/assets/models/' + m['file']), None)
        except (ValueError, TypeError, KeyError, OSError):
            return root / '.not-served'
    if relative is None:
        parts = Path(url_path.lstrip('/')).parts
        allowed = {'data', 'framework', 'docs', 'reports', 'research'}
        if (not parts or parts[0] not in allowed or any(p.startswith('.') or p == '..' for p in parts)
                or parts[-1].lower() == 'users.json' or url_path.lower() == '/data/research_runtime.json'
                or parts[:2] == ('data', 'raw')):
            return root / '.not-served'
        if Path(parts[-1]).suffix.lower() not in {'.json', '.md', '.csv', '.txt', '.pdf', '.html', '.png', '.jpg', '.svg'}:
            return root / '.not-served'
        relative = '/'.join(parts)
    try:
        return workspace_path(relative, root, public=True)
    except LayoutError:
        return root / '.not-served'
