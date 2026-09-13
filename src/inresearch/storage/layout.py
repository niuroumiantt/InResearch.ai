"""One explicit boundary between published research and persistent website state.

Without a runtime root, a source checkout remains an authoring workspace. A
deployed website reads its published files from the image; only declared state
and projections resolve into persistent mounts. Resolution never creates data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from inresearch.paths import project_root
from inresearch.storage.files import atomic_write, locked, make_directory, write_json


class LayoutError(ValueError):
    pass


def _relative(value):
    path = Path(value)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts):
        raise LayoutError('invalid_workspace_path')
    return path.as_posix()


def _inside(base, relative):
    path = base / _relative(relative)
    if not path.resolve().is_relative_to(base.resolve()):
        raise LayoutError('workspace_path_escapes_root')
    return path


def _configuration(root=None, runtime=None):
    root = Path(root or project_root()).resolve()
    value = runtime if runtime is not None else os.environ.get('INRESEARCH_RUNTIME_ROOT')
    if not value:
        return root, None, None
    runtime = Path(value).expanduser()
    if (not runtime.is_absolute() or root.is_relative_to(runtime.resolve())
            or runtime.resolve().is_relative_to(root)):
        raise LayoutError('runtime_root_must_be_absolute_and_separate')
    contract = json.loads((root / 'framework/storage_contract.json').read_text())
    if contract.get('version') != 1 or contract.get('runtime_environment') != 'INRESEARCH_RUNTIME_ROOT':
        raise LayoutError('unsupported_storage_contract')
    targets = set()
    for group in ('files', 'directories'):
        for path, rule in contract[group].items():
            _relative(path); _relative(rule['runtime'])
            if (rule['kind'] not in ('state', 'projection', 'private')
                    or not isinstance(rule['public'], bool)
                    or not isinstance(rule.get('seed', False), bool)
                    or rule['runtime'] in targets):
                raise LayoutError('invalid_storage_rule')
            targets.add(rule['runtime'])
    return root, runtime.resolve(), contract


def _rule(relative, contract):
    if relative in contract['files']:
        rule = contract['files'][relative]
        return rule, rule['runtime']
    for prefix, rule in sorted(contract['directories'].items(), key=lambda item: -len(item[0])):
        if relative == prefix or relative.startswith(prefix + '/'):
            return rule, rule['runtime'] + relative[len(prefix):]
    return None, relative


def workspace_path(relative, root=None, *, public=False):
    """Resolve the same logical filename for HTTP, CLI, readers and writers."""
    relative = _relative(relative)
    root, runtime, contract = _configuration(root)
    if runtime is not None:
        rule, target = _rule(relative, contract)
        if rule:
            if public and not rule['public']:
                raise LayoutError('private_runtime_path')
            return _inside(runtime, target)
    return _inside(root, relative)


def _layout_identity(contract):
    # Documentation or seed content updates do not grant a state migration.
    structural = {group: {p: {k: v for k, v in rule.items() if k != 'initial'}
                          for p, rule in contract[group].items()}
                  for group in ('files', 'directories')}
    return hashlib.sha256(json.dumps(structural, sort_keys=True).encode()).hexdigest()


def _seeds(root, contract):
    result = {}
    for relative, rule in contract['files'].items():
        if rule.get('seed'):
            result[relative] = _inside(root, relative).read_bytes()
        elif 'initial' in rule:
            result[relative] = (json.dumps(rule['initial'], ensure_ascii=False, indent=2) + '\n').encode()
    return result


def _state(runtime, contract):
    path = _inside(runtime, 'data/.storage-layout.json')
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if (value.get('version') != 1 or value.get('layout') != _layout_identity(contract)
            or value.get('state') not in ('initializing', 'ready')):
        raise LayoutError('runtime_layout_migration_required')
    return value


def check_runtime(root=None, runtime=None, *, require_auth=False):
    """Read-only release preflight. Existing state never falls back to Git."""
    root, runtime, contract = _configuration(root, runtime)
    if runtime is None:
        return {'mode': 'authoring', 'initialized': False}
    state = _state(runtime, contract)
    seeds = _seeds(root, contract)
    if state and state['state'] == 'initializing' and state.get('seed_hashes') != {
            p: hashlib.sha256(body).hexdigest() for p, body in seeds.items()}:
        raise LayoutError('resume_original_initialization_release')
    for relative, rule in contract['files'].items():
        path = _inside(runtime, rule['runtime'])
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise LayoutError('runtime_file_required: ' + relative)
        if state and state['state'] == 'ready' and rule['kind'] == 'state' and relative in seeds and not path.exists():
            raise LayoutError('runtime_state_missing: ' + relative)
    if require_auth:
        path = _inside(runtime, contract['files']['data/users.json']['runtime'])
        users = json.loads(path.read_text()).get('users', {}) if path.exists() else {}
        if not isinstance(users, dict) or not any(isinstance(u, dict) and u.get('role') == 'admin' for u in users.values()):
            raise LayoutError('existing_admin_store_required')
        secret = _inside(runtime, contract['files']['data/.hub_secret']['runtime'])
        if not secret.is_file() or len(secret.read_bytes()) != 32:
            raise LayoutError('existing_session_key_required')
    return {'mode': 'deployed', 'initialized': bool(state and state['state'] == 'ready'),
            'layout': _layout_identity(contract), 'runtime_files': len(contract['files'])}


def initialize_runtime(root=None, runtime=None):
    """Seed a new store once; resume interruptions without replacing live state."""
    root, runtime, contract = _configuration(root, runtime)
    if runtime is None:
        return {'mode': 'authoring', 'initialized': False}
    marker = _inside(runtime, 'data/.storage-layout.json')
    seeds = _seeds(root, contract)
    hashes = {p: hashlib.sha256(body).hexdigest() for p, body in seeds.items()}
    with locked(marker):
        check_runtime(root, runtime)
        state = _state(runtime, contract)
        if state and state['state'] == 'initializing' and state.get('seed_hashes') != hashes:
            raise LayoutError('resume_original_initialization_release')
        if state is None:
            state = {'version': 1, 'layout': _layout_identity(contract),
                     'state': 'initializing', 'seed_hashes': hashes}
            write_json(marker, state)
        for prefix, rule in contract['directories'].items():
            make_directory(_inside(runtime, rule['runtime']))
        for relative, body in seeds.items():
            target = _inside(runtime, contract['files'][relative]['runtime'])
            # Never hold two business locks here: the library owns INDEX → PLAN.
            # The journal serializes initializers; each target lock preserves a
            # concurrent business write without introducing another lock order.
            with locked(target):
                if not target.exists():
                    atomic_write(target, body)
        state['state'] = 'ready'
        write_json(marker, state)
        return check_runtime(root, runtime)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('check', 'initialize'))
    ap.add_argument('--runtime-root', type=Path)
    ap.add_argument('--require-auth', action='store_true')
    args = ap.parse_args()
    try:
        if args.require_auth:
            check_runtime(runtime=args.runtime_root, require_auth=True)
        result = (initialize_runtime(runtime=args.runtime_root) if args.action == 'initialize'
                  else check_runtime(runtime=args.runtime_root, require_auth=args.require_auth))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (LayoutError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
