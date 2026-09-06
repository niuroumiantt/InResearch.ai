"""Validate browse groups without treating them as physical/ownership relations."""
from collections import Counter


def validate_navigation(graph):
    # Older external fixtures need not declare a UI; repository tests require it.
    if 'navigation' not in graph:
        return []
    errors = []
    navigation = graph['navigation']
    if not isinstance(navigation, dict):
        return ['navigation must be an object keyed by view']
    views = {v['id'] for v in graph.get('views', [])}
    objects = {o['id']: o for o in graph.get('objects', [])}
    if set(navigation) != views:
        errors.append('navigation views must exactly match declared views')
    if not graph.get('navigation_version') or not graph.get('navigation_note'):
        errors.append('navigation requires its version and semantics note')
    for view, roots in navigation.items():
        seen_groups, occurrences = set(), Counter()

        def descendant_refs(groups, depth=0):
            if not isinstance(groups, list) or depth > 12:
                return set()
            found = set()
            for row in groups:
                if isinstance(row, dict):
                    refs = row.get('object_ids', [])
                    if isinstance(refs, list):
                        found.update(x for x in refs if isinstance(x, str))
                    found.update(descendant_refs(row.get('children', []), depth + 1))
            return found

        def walk(groups, depth=0):
            if depth > 12:
                errors.append(f'navigation {view}: excessive depth or cycle')
                return
            if not isinstance(groups, list):
                errors.append(f'navigation {view}: groups must be a list')
                return
            for group in groups:
                if not isinstance(group, dict):
                    errors.append(f'navigation {view}: group must be an object')
                    continue
                gid = group.get('id')
                if not isinstance(gid, str) or not gid or gid in seen_groups:
                    errors.append(f'navigation {view}: invalid or duplicate group ID {gid}')
                else:
                    seen_groups.add(gid)
                if not isinstance(group.get('label'), str) or not group['label'].strip():
                    errors.append(f'navigation {view}: group label required')
                refs = group.get('object_ids', [])
                if not isinstance(refs, list):
                    errors.append(f'navigation {view}: object_ids must be a list')
                    refs = []
                for oid in refs:
                    if not isinstance(oid, str) or oid not in objects:
                        errors.append(f'navigation {view}: unknown object {oid}')
                        continue
                    occurrences[oid] += 1
                    if view not in objects[oid].get('views', []):
                        errors.append(f'navigation {view}: object outside declared view {oid}')
                if 'system_id' in group:
                    sid = group['system_id']
                    expected_members = {r['source'] for r in graph.get('relations', [])
                                        if r.get('type') == 'member_of_system' and r.get('target') == sid}
                    if (view != 'F' or not isinstance(sid, str) or sid not in objects
                            or objects[sid].get('kind') != 'functional_system' or refs != [sid]
                            or descendant_refs(group.get('children', [])) != expected_members):
                        errors.append(f'navigation {view}: system members must match registered relations {sid}')
                walk(group.get('children', []), depth + 1)

        walk(roots)
        expected = {oid for oid, o in objects.items() if view in o.get('views', [])}
        missing = expected - set(occurrences)
        if missing:
            errors.append(f'navigation {view}: unplaced objects {sorted(missing)}')
        # F is a multi-system traversal. Other views have a single browse address.
        duplicates = sorted(oid for oid, n in occurrences.items() if n > 1)
        if view != 'F' and duplicates:
            errors.append(f'navigation {view}: duplicate browse locations {duplicates}')
    if 'hardware_domains' in graph:
        domains = graph['hardware_domains']
        occurrences = Counter()
        for domain in domains:
            if domain.get('node_id') not in objects:
                errors.append('hardware domain has unknown root')
            for oid in domain.get('object_ids', []):
                occurrences[oid] += 1
                if oid not in objects:
                    errors.append('hardware domain has unknown object ' + oid)
        expected = {o['id'] for o in objects.values() if o['id'].startswith('part:')}
        if expected - occurrences.keys():
            errors.append('hardware domains omit hardware objects')
        if any(n > 1 for n in occurrences.values()):
            errors.append('hardware domains have duplicate primary membership')
        for obj in objects.values():
            for section in obj.get('research_sections', []):
                if not set(section.get('object_ids', [])) <= objects.keys():
                    errors.append('research section has unknown target')
        for mapping in graph.get('catalog_topic_mappings', []):
            if not set(mapping.get('object_ids', [])) <= objects.keys():
                errors.append('catalog topic mapping has unknown target')
    return errors
