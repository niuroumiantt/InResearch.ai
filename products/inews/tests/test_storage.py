from __future__ import annotations

import stat

from inews.storage import read_json, write_json_atomic, write_text_atomic


def test_atomic_json_keeps_one_last_known_good_snapshot(tmp_path):
    path = tmp_path / "state.json"
    write_json_atomic(path, {"generation": 1})
    write_json_atomic(path, {"generation": 2})
    assert read_json(path, {}) == {"generation": 2}
    assert read_json(path.with_suffix(".json.bak"), {}, recover=False) == {
        "generation": 1
    }


def test_atomic_text_replaces_the_complete_shared_page(tmp_path):
    path = tmp_path / "DASHBOARD" / "index.html"
    write_text_atomic(path, "old complete page")
    write_text_atomic(path, "new complete page")
    assert path.read_text(encoding="utf-8") == "new complete page"
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert not list(path.parent.glob(".index.html.*"))
