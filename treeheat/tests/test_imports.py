"""Import smoke tests — base install must stay light."""

from __future__ import annotations

import sys


def test_import_treeheat_without_heavy_deps() -> None:
    for module in ("scipy", "pyradiance", "geopandas"):
        sys.modules.pop(module, None)

    import treeheat  # noqa: F401

    assert "scipy" not in sys.modules
    assert "pyradiance" not in sys.modules
    assert "geopandas" not in sys.modules


def test_import_engine_registry_without_heavy_deps() -> None:
    for module in ("scipy", "pyradiance", "geopandas"):
        sys.modules.pop(module, None)

    from treeheat.physics.engines import get_engine, registered_engine_names

    assert "li2023_ceb" in registered_engine_names()
    assert "legacy_leaf" in registered_engine_names()
    assert "scipy" not in sys.modules

    engine = get_engine("li2023_ceb")
    assert engine.name == "li2023_ceb"
