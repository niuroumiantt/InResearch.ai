"""Repository architecture pages always require an authenticated administrator."""

PAGES = {'/admin/repos.html', '/admin/inresearchrepo.html', '/admin/inewsrepo.html',
         '/admin/fetchspecrepo.html', '/admin/infrarepo.html',
         '/admin/oarepo.html', '/admin/aimailrepo.html', '/admin/leadsgenrepo.html', '/admin/semiflyrepo.html', '/admin/glocalstoragerepo.html', '/admin/openapirepo.html', '/admin/suanmingrepo.html', '/admin/agentrepo.html'}
ALIASES = {'/admin/fetchspec/reporg.html': '/admin/fetchspecrepo.html'}


def protected(path):
    path = path.lower()
    return (path in PAGES or path in ALIASES or path.startswith('/admin/repo-content/')
            or path == '/api/admin/material-flow')
