"""Engine-interface tests. Mine assertions from src_archive verify_*/test_* scripts.

Known historical bugs worth pinning as regression tests:
  - hour-indexing alignment        (src_archive/verify_hour_indexing.py)
  - sensor-count == feather rows    (src_archive/verify_scenario_materials.py)
  - scenarios must differ (no shared random seed collapsing surfaces)
"""
from __future__ import annotations

import pytest

from treeheat.physics.engines import get_engine, registered_engine_names


def test_registered_engines_present() -> None:
    assert get_engine("li2023_ceb").name == "li2023_ceb"
    assert get_engine("legacy_leaf").name == "legacy_leaf"


def test_unknown_engine_raises() -> None:
    with pytest.raises(KeyError, match="Unknown canopy engine"):
        get_engine("does_not_exist")


def test_registered_names_list() -> None:
    assert registered_engine_names() == ["legacy_leaf", "li2023_ceb"]
