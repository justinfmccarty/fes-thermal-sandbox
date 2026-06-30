"""Surface/facade material database.

PORT FROM: src_archive/root_material_database.csv (15 rows)

Contract:
  - Albedo, emissivity, naturalness score, ground/facade applicability.
  - Ground thermal columns in CSV are blank; resolved via config.model.ground.types.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from treeheat.config import get_path
from treeheat.io.schema import (
    ColumnSpec,
    SchemaError,
    parse_bool,
    parse_float,
    parse_str,
    validate_dataframe,
    _validate_unit_range,
)

__all__ = [
    "GROUND_TYPES",
    "MATERIAL_SCHEMA",
    "MaterialDatabase",
    "MaterialRecord",
    "load_material_database",
]

GroundType = Literal["vegetated", "pervious", "impervious"]
GROUND_TYPES: frozenset[str] = frozenset({"vegetated", "pervious", "impervious"})

DEFAULT_ALBEDO = 0.3
DEFAULT_EMISSIVITY = 0.95
DEFAULT_NATURALNESS = 0.2


def _validate_ground_type(value: Any) -> None:
    text = str(value).strip()
    if text not in GROUND_TYPES:
        raise SchemaError(
            f"ground_type must be one of {sorted(GROUND_TYPES)}, got {value!r}"
        )


MATERIAL_SCHEMA: dict[str, ColumnSpec] = {
    "material_name": ColumnSpec(dtype="str"),
    "facade_applicable": ColumnSpec(dtype="bool"),
    "ground_applicable": ColumnSpec(dtype="bool"),
    "naturalness_score": ColumnSpec(
        dtype="float",
        validator=lambda v: _validate_unit_range(float(v), name="naturalness_score"),
    ),
    "shortwave_albedo": ColumnSpec(
        dtype="float",
        validator=lambda v: _validate_unit_range(float(v), name="shortwave_albedo"),
    ),
    "thermal_emissivity": ColumnSpec(
        dtype="float",
        validator=lambda v: _validate_unit_range(float(v), name="thermal_emissivity"),
    ),
    "ground_type": ColumnSpec(dtype="str", validator=_validate_ground_type),
    "heat_capacity_J_m2_K": ColumnSpec(dtype="float|null", nullable=True),
    "evap_factor": ColumnSpec(dtype="float|null", nullable=True),
    "k_drain": ColumnSpec(dtype="float|null", nullable=True),
    "naturalness_score_rationale": ColumnSpec(dtype="str"),
}


@dataclass(frozen=True)
class MaterialRecord:
    """One row from root_material_database.csv — field names match the CSV schema."""

    material_name: str
    facade_applicable: bool
    ground_applicable: bool
    naturalness_score: float
    shortwave_albedo: float
    thermal_emissivity: float
    ground_type: GroundType
    heat_capacity_J_m2_K: float | None
    evap_factor: float | None
    k_drain: float | None
    naturalness_score_rationale: str


@dataclass
class MaterialDatabase:
    """Validated material database with v0-compatible accessors."""

    records: list[MaterialRecord]
    by_name: dict[str, MaterialRecord]

    def get(self, material_name: str) -> MaterialRecord | None:
        return self.by_name.get(material_name)

    def get_albedo(self, material_name: str) -> float:
        """Shortwave albedo; default 0.3 if not found (v0 semantics)."""
        rec = self.by_name.get(material_name)
        if rec is None:
            return DEFAULT_ALBEDO
        return rec.shortwave_albedo

    def get_emissivity(self, material_name: str) -> float:
        """Thermal emissivity; default 0.95 if not found (v0 semantics)."""
        rec = self.by_name.get(material_name)
        if rec is None:
            return DEFAULT_EMISSIVITY
        return rec.thermal_emissivity

    def get_naturalness(self, material_name: str) -> float:
        """Naturalness score; default 0.2 if not found (v0 semantics)."""
        rec = self.by_name.get(material_name)
        if rec is None:
            return DEFAULT_NATURALNESS
        return rec.naturalness_score

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)


def _row_to_record(row: pd.Series) -> MaterialRecord:
    ground_type = parse_str(row["ground_type"])
    assert ground_type is not None
    return MaterialRecord(
        material_name=parse_str(row["material_name"]),  # type: ignore[arg-type]
        facade_applicable=parse_bool(row["facade_applicable"]),  # type: ignore[arg-type]
        ground_applicable=parse_bool(row["ground_applicable"]),  # type: ignore[arg-type]
        naturalness_score=parse_float(row["naturalness_score"]),  # type: ignore[arg-type]
        shortwave_albedo=parse_float(row["shortwave_albedo"]),  # type: ignore[arg-type]
        thermal_emissivity=parse_float(row["thermal_emissivity"]),  # type: ignore[arg-type]
        ground_type=ground_type,  # type: ignore[assignment]
        heat_capacity_J_m2_K=parse_float(row["heat_capacity_J_m2_K"]),
        evap_factor=parse_float(row["evap_factor"]),
        k_drain=parse_float(row["k_drain"]),
        naturalness_score_rationale=parse_str(row["naturalness_score_rationale"]),  # type: ignore[arg-type]
    )


def load_material_database(
    path: str | Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> MaterialDatabase:
    """Load and validate the material database CSV.

    Args:
        path: Explicit CSV path. Defaults to config.paths.material_database_file.
        cfg: Optional config dict for get_path resolution.
    """
    csv_path = Path(path) if path is not None else get_path("material_database_file", cfg)
    if not csv_path.exists():
        raise FileNotFoundError(f"Material database not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    for col in df.columns:
        if col in {"material_name", "ground_type", "naturalness_score_rationale"}:
            continue
        df[col] = df[col].replace("", pd.NA)

    validate_dataframe(df, MATERIAL_SCHEMA, source=str(csv_path))

    records = [_row_to_record(row) for _, row in df.iterrows()]
    by_name = {rec.material_name: rec for rec in records}

    return MaterialDatabase(records=records, by_name=by_name)
