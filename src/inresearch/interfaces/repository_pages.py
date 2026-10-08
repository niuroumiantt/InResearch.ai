"""Repository architecture pages always require an authenticated administrator."""
import os
from pathlib import Path

from inresearch.storage.layout import workspace_path, LayoutError

PAGES = {'/admin/repos.html', '/admin/inresearchrepo.html', '/admin/inewsrepo.html',
         '/admin/fetchspecrepo.html', '/admin/infrarepo.html',
         '/admin/oarepo.html', '/admin/aimailrepo.html', '/admin/leadsgenrepo.html', '/admin/semiflyrepo.html', '/admin/glocalstoragerepo.html', '/admin/openapirepo.html', '/admin/agentrepo.html'}
ALIASES = {'/admin/fetchspec/reporg.html': '/admin/fetchspecrepo.html'}
FILES = {p: p.removeprefix('/admin/') for p in PAGES}
FILES.update({'/admin/repo-content/'+p: 'repo-content/'+p for p in
              ('infra.html','fetchspec.html','manifest.json','checks.json','infra-daily.json')})


def runtime_source(path, root):
    """Private, atomic daily projection, served only after the existing admin gate."""
    if not os.environ.get('INRESEARCH_RUNTIME_ROOT'):
        return None
    relative = FILES.get(path)
    if path == '/admin/repo-content/job-status.json':
        relative = 'status.json'
    elif relative:
        relative = 'current/' + relative
    if not relative:
        return None
    try:
        source = workspace_path('data/raw/repository-pages/' + relative, root)
        if source.is_file():
            return source
    except (LayoutError, OSError):
        pass
    return None


def protected(path):
    path = path.lower()
    return (path in PAGES or path in ALIASES or path.startswith('/admin/repo-content/')
            or path == '/api/admin/material-flow')
