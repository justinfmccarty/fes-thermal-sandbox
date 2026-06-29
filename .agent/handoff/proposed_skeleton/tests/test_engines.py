"""Engine-interface tests. Mine assertions from src_archive verify_*/test_* scripts.

Known historical bugs worth pinning as regression tests:
  - hour-indexing alignment        (src_archive/verify_hour_indexing.py)
  - sensor-count == feather rows    (src_archive/verify_scenario_materials.py)
  - scenarios must differ (no shared random seed collapsing surfaces)
"""
import pytest


@pytest.mark.skip(reason="placeholder — implement once engines are ported")
def test_registered_engines_present():
    from treeheat.physics.engines import get_engine
    assert get_engine("li2023_ceb").name == "li2023_ceb"
    assert get_engine("legacy_leaf").name == "legacy_leaf"
