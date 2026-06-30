"""Schema-conformance tests for reference databases."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from treeheat.config import get_config, get_path, reload_config, validate_config
from treeheat.io import (
    MATERIAL_SCHEMA,
    SPECIES_SCHEMA,
    MaterialRecord,
    SpeciesRecord,
    load_material_database,
    load_species_database,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


@pytest.fixture(scope="module", autouse=True)
def _load_project_config() -> None:
    reload_config(CONFIG_PATH)


def test_species_csv_headers_match_schema() -> None:
    path = get_path("species_database_file")
    df = pd.read_csv(path, nrows=0)
    assert list(df.columns) == list(SPECIES_SCHEMA.keys())


def test_material_csv_headers_match_schema() -> None:
    path = get_path("material_database_file")
    df = pd.read_csv(path, nrows=0)
    assert list(df.columns) == list(MATERIAL_SCHEMA.keys())


def test_load_species_database_returns_typed_records() -> None:
    db = load_species_database()
    assert len(db) > 0
    for rec in db:
        assert isinstance(rec, SpeciesRecord)
        assert rec.species
        assert rec.common_name
        assert 0.0 <= rec.leaf_shortwave_albedo <= 1.0
        assert 0.0 <= rec.leaf_emissivity <= 1.0


def test_species_dual_key_lookup() -> None:
    db = load_species_database()
    by_species = db.get("Fraxinus_pennsylvanica")
    by_common = db.get("Green Ash")
    assert by_species is not None
    assert by_common is not None
    assert by_species is by_common


def test_species_nullable_columns_allowed() -> None:
    db = load_species_database()
    # Amur Chokecherry has blank LeafArea_cm2 and leaf_char_size in v0 CSV
    rec = db.get("Prunus_maackii")
    assert rec is not None
    assert rec.LeafArea_cm2 is None
    assert rec.leaf_char_size is None


def test_load_material_database_returns_typed_records() -> None:
    db = load_material_database()
    assert len(db) > 0
    for rec in db:
        assert isinstance(rec, MaterialRecord)
        assert rec.material_name
        assert rec.ground_type in {"vegetated", "pervious", "impervious"}
        assert 0.0 <= rec.shortwave_albedo <= 1.0
        assert 0.0 <= rec.thermal_emissivity <= 1.0
        assert 0.0 <= rec.naturalness_score <= 1.0
        assert isinstance(rec.facade_applicable, bool)
        assert isinstance(rec.ground_applicable, bool)


def test_material_thermal_placeholder_columns_null() -> None:
    db = load_material_database()
    for rec in db:
        assert rec.heat_capacity_J_m2_K is None
        assert rec.evap_factor is None
        assert rec.k_drain is None


def test_material_accessors_match_csv() -> None:
    db = load_material_database()
    rec = db.get("grey_concrete")
    assert rec is not None
    assert db.get_albedo("grey_concrete") == rec.shortwave_albedo == pytest.approx(0.35)
    assert db.get_emissivity("grey_concrete") == rec.thermal_emissivity == pytest.approx(0.90)
    assert db.get_naturalness("grey_concrete") == rec.naturalness_score == pytest.approx(0.2)


def test_material_accessor_defaults_for_unknown() -> None:
    db = load_material_database()
    assert db.get_albedo("nonexistent_material") == pytest.approx(0.3)
    assert db.get_emissivity("nonexistent_material") == pytest.approx(0.95)
    assert db.get_naturalness("nonexistent_material") == pytest.approx(0.2)


def test_row_counts_from_shipped_csvs() -> None:
    species_path = get_path("species_database_file")
    material_path = get_path("material_database_file")
    species_df = pd.read_csv(species_path)
    material_df = pd.read_csv(material_path)
    assert len(load_species_database()) == len(species_df)
    assert len(load_material_database()) == len(material_df)
    assert len(species_df) == 33
    assert len(material_df) == 15


def test_validate_config_passes_species_and_material_paths() -> None:
    cfg = get_config(CONFIG_PATH)
    # grid_records_dir may still be missing — only assert species + material paths exist
    species_path = get_path("species_database_file", cfg)
    material_path = get_path("material_database_file", cfg)
    assert species_path.is_file()
    assert material_path.is_file()
