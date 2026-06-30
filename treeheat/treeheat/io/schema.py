"""Shared CSV schema validation for reference databases."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd


class SchemaError(Exception):
    """Raised when a reference CSV fails schema validation."""


@dataclass(frozen=True)
class ColumnSpec:
    """Specification for one CSV column."""

    dtype: str  # "str", "float", "bool", "float|null"
    nullable: bool = False
    validator: Callable[[Any], None] | None = None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _validate_unit_range(value: float, *, lo: float = 0.0, hi: float = 1.0, name: str) -> None:
    if not lo <= value <= hi:
        raise SchemaError(f"{name} must be in [{lo}, {hi}], got {value}")


def validate_dataframe(df: pd.DataFrame, schema: dict[str, ColumnSpec], *, source: str) -> None:
    """Validate column order, presence, nullability, dtypes, and custom validators."""
    expected_columns = list(schema.keys())
    actual_columns = list(df.columns)

    if actual_columns != expected_columns:
        missing = [c for c in expected_columns if c not in actual_columns]
        extra = [c for c in actual_columns if c not in expected_columns]
        parts = [f"Schema mismatch in {source}."]
        if missing:
            parts.append(f"Missing columns: {missing}")
        if extra:
            parts.append(f"Unexpected columns: {extra}")
        if not missing and not extra:
            parts.append(f"Expected order {expected_columns}, got {actual_columns}")
        raise SchemaError(" ".join(parts))

    for col, spec in schema.items():
        for idx, raw in enumerate(df[col]):
            row_num = idx + 2  # 1-based, account for header
            missing = _is_missing(raw)

            if missing:
                if not spec.nullable:
                    raise SchemaError(
                        f"{source}: null/blank value in non-nullable column '{col}' (row {row_num})"
                    )
                continue

            if spec.dtype == "str":
                if not isinstance(raw, str):
                    raise SchemaError(
                        f"{source}: column '{col}' row {row_num} expected str, got {type(raw).__name__}"
                    )
            elif spec.dtype == "float":
                try:
                    float(raw)
                except (TypeError, ValueError) as exc:
                    raise SchemaError(
                        f"{source}: column '{col}' row {row_num} expected float, got {raw!r}"
                    ) from exc
            elif spec.dtype == "float|null":
                try:
                    float(raw)
                except (TypeError, ValueError) as exc:
                    raise SchemaError(
                        f"{source}: column '{col}' row {row_num} expected float, got {raw!r}"
                    ) from exc
            elif spec.dtype == "bool":
                if isinstance(raw, bool):
                    pass
                elif isinstance(raw, str) and raw.strip().lower() in {"true", "false"}:
                    pass
                else:
                    raise SchemaError(
                        f"{source}: column '{col}' row {row_num} expected bool, got {raw!r}"
                    )
            else:
                raise SchemaError(f"Unknown dtype '{spec.dtype}' for column '{col}'")

            if spec.validator is not None:
                spec.validator(raw)


def parse_bool(value: Any) -> bool | None:
    """Parse a CSV bool cell; return None if missing."""
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise SchemaError(f"Expected bool, got {value!r}")


def parse_float(value: Any) -> float | None:
    """Parse a CSV float cell; return None if missing."""
    if _is_missing(value):
        return None
    return float(value)


def parse_str(value: Any) -> str | None:
    """Parse a CSV string cell; return None if missing."""
    if _is_missing(value):
        return None
    return str(value)
