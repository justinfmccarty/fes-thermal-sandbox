"""Tree species parameter database.

PORT FROM: src_archive/tree_species.py + tree_species_database.csv (33 rows)

Contract:
  - Load species physiology (optical, stomatal, thermal thresholds) from CSV.
  - Carry the citation-backed schema forward unchanged.
  - Engine-facing param mapping (alpha_leaf, r_sto, etc.) deferred to Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from treeheat.config import get_path
from treeheat.io.schema import (
    ColumnSpec,
    SchemaError,
    parse_float,
    parse_str,
    validate_dataframe,
)

__all__ = [
    "SPECIES_SCHEMA",
    "SpeciesDatabase",
    "SpeciesRecord",
    "load_species_database",
]

SPECIES_SCHEMA: dict[str, ColumnSpec] = {
    "common_name": ColumnSpec(dtype="str"),
    "species": ColumnSpec(dtype="str"),
    "light_extinction_coefficient": ColumnSpec(dtype="float"),
    "leaf_shortwave_albedo": ColumnSpec(
        dtype="float",
        validator=lambda v: _validate_unit_range(float(v), name="leaf_shortwave_albedo"),
    ),
    "leaf_emissivity": ColumnSpec(
        dtype="float",
        validator=lambda v: _validate_unit_range(float(v), name="leaf_emissivity"),
    ),
    "max_stomatal_conductance_mol_m2_s": ColumnSpec(dtype="float"),
    "vpd_sensitivity_g1_kpa_sqrt": ColumnSpec(dtype="float"),
    "optimal_leaf_temperature_c": ColumnSpec(dtype="float"),
    "critical_leaf_temperature_c": ColumnSpec(dtype="float"),
    "citations": ColumnSpec(dtype="str"),
    "LeafArea_cm2": ColumnSpec(dtype="float|null", nullable=True),
    "leaf_char_size": ColumnSpec(dtype="float|null", nullable=True),
}


def _validate_unit_range(value: float, *, lo: float = 0.0, hi: float = 1.0, name: str) -> None:
    if not lo <= value <= hi:
        raise SchemaError(f"{name} must be in [{lo}, {hi}], got {value}")


@dataclass(frozen=True)
class SpeciesRecord:
    """One row from tree_species_database.csv — field names match the CSV schema."""

    common_name: str
    species: str
    light_extinction_coefficient: float
    leaf_shortwave_albedo: float
    leaf_emissivity: float
    max_stomatal_conductance_mol_m2_s: float
    vpd_sensitivity_g1_kpa_sqrt: float
    optimal_leaf_temperature_c: float
    critical_leaf_temperature_c: float
    citations: str
    LeafArea_cm2: float | None
    leaf_char_size: float | None


@dataclass
class SpeciesDatabase:
    """Validated species database with dual-key lookup."""

    records: list[SpeciesRecord]
    _by_key: dict[str, SpeciesRecord]

    def get(self, name: str) -> SpeciesRecord | None:
        """Look up by species slug or common name."""
        return self._by_key.get(name)

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)


def _row_to_record(row: pd.Series) -> SpeciesRecord:
    return SpeciesRecord(
        common_name=parse_str(row["common_name"]),  # type: ignore[arg-type]
        species=parse_str(row["species"]),  # type: ignore[arg-type]
        light_extinction_coefficient=parse_float(row["light_extinction_coefficient"]),  # type: ignore[arg-type]
        leaf_shortwave_albedo=parse_float(row["leaf_shortwave_albedo"]),  # type: ignore[arg-type]
        leaf_emissivity=parse_float(row["leaf_emissivity"]),  # type: ignore[arg-type]
        max_stomatal_conductance_mol_m2_s=parse_float(row["max_stomatal_conductance_mol_m2_s"]),  # type: ignore[arg-type]
        vpd_sensitivity_g1_kpa_sqrt=parse_float(row["vpd_sensitivity_g1_kpa_sqrt"]),  # type: ignore[arg-type]
        optimal_leaf_temperature_c=parse_float(row["optimal_leaf_temperature_c"]),  # type: ignore[arg-type]
        critical_leaf_temperature_c=parse_float(row["critical_leaf_temperature_c"]),  # type: ignore[arg-type]
        citations=parse_str(row["citations"]),  # type: ignore[arg-type]
        LeafArea_cm2=parse_float(row["LeafArea_cm2"]),
        leaf_char_size=parse_float(row["leaf_char_size"]),
    )


def load_species_database(
    path: str | Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> SpeciesDatabase:
    """Load and validate the species database CSV.

    Args:
        path: Explicit CSV path. Defaults to config.paths.species_database_file.
        cfg: Optional config dict for get_path resolution.
    """
    csv_path = Path(path) if path is not None else get_path("species_database_file", cfg)
    if not csv_path.exists():
        raise FileNotFoundError(f"Species database not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    # Restore numeric columns from string read for validation
    for col in df.columns:
        if col == "citations" or col == "common_name" or col == "species":
            continue
        df[col] = df[col].replace("", pd.NA)

    validate_dataframe(df, SPECIES_SCHEMA, source=str(csv_path))

    records = [_row_to_record(row) for _, row in df.iterrows()]
    by_key: dict[str, SpeciesRecord] = {}
    for rec in records:
        by_key[rec.species] = rec
        if rec.common_name and rec.common_name != rec.species:
            by_key[rec.common_name] = rec

    return SpeciesDatabase(records=records, _by_key=by_key)
