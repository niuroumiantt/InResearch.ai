"""Canonical BOM system ancestry; identity is independent of hierarchy depth."""


def system_path(systems, sid):
    """Root-first IDs, rejecting missing parents and cycles."""
    path = []
    while sid is not None:
        if sid in path:
            raise ValueError('system containment cycle: ' + sid)
        path.append(sid)
        sid = systems[sid].get('parent')
    return tuple(reversed(path))


def system_key(systems, sid):
    return tuple(systems[x]['order'] for x in system_path(systems, sid))
