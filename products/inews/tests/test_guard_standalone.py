from __future__ import annotations

import importlib.util
from pathlib import Path


def _guard_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "guard_standalone.py"
    spec = importlib.util.spec_from_file_location("guard_standalone_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secret_check_uses_git_tracked_files(monkeypatch, capsys):
    guard = _guard_module()
    monkeypatch.setattr(guard, "declared_dependencies", lambda: set())
    monkeypatch.setattr(guard, "imported_roots", lambda: {})
    monkeypatch.setattr(
        guard,
        "tracked_files",
        lambda: (Path("secrets/bloomberg.cookies"), Path("inews/run.py")),
    )

    assert guard.main() == 1
    assert "secrets/bloomberg.cookies" in capsys.readouterr().err


def test_ignored_runtime_secret_is_outside_guard_boundary(monkeypatch, capsys):
    guard = _guard_module()
    monkeypatch.setattr(guard, "declared_dependencies", lambda: set())
    monkeypatch.setattr(guard, "imported_roots", lambda: {})
    monkeypatch.setattr(guard, "tracked_files", lambda: (Path("inews/run.py"),))

    assert guard.main() == 0
    assert "独立性守卫通过" in capsys.readouterr().out
