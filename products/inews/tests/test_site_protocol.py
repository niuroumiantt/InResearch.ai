"""站点插件必须在注册时满足同一份明确契约。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from inews import sites
from inews.sites.protocol import validate


def test_every_registered_site_satisfies_the_adapter_contract():
    for site in sites.REGISTRY.values():
        validate(site)


def test_an_incomplete_site_fails_early_with_all_missing_fields():
    broken = SimpleNamespace(KEY="unfinished")
    with pytest.raises(TypeError) as caught:
        validate(broken)
    message = str(caught.value)
    assert "unfinished" in message
    assert "parse_search_results" in message
    assert "admitted_rows" in message
    assert "BODY_SELECTORS" in message
