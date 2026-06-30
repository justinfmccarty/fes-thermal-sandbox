"""Weather / EPW loader.

PORT FROM: src_archive/weather_loader.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from treeheat.config import get_path

__all__ = [
    "calculate_qsat",
    "calculate_specific_humidity",
    "calculate_vpd",
    "find_warmest_day",
    "get_week_around_day",
    "load_epw",
]


def calculate_vpd(Ta: float, RH: float) -> float:
    """Calculate vapor pressure deficit [kPa] from air temperature and RH."""
    esat = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))
    ea = esat * (RH / 100.0)
    return max(0.0, esat - ea)


def calculate_qsat(T: float, P: float) -> float:
    """Calculate saturation specific humidity [kg/kg]."""
    esat = 0.6108 * np.exp(17.27 * T / (T + 237.3))
    return 0.622 * esat / P


def calculate_specific_humidity(Ta: float, RH: float, P: float) -> float:
    """Calculate specific humidity [kg/kg]."""
    esat = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))
    ea = esat * (RH / 100.0)
    return 0.622 * ea / P


def load_epw(epw_path: str | Path | None = None, cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    """Load EPW weather file and extract meteorological variables."""
    if epw_path is None:
        epw_path = get_path("weather_file", cfg)
    epw_path = Path(epw_path)

    with epw_path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.readlines()

    data_lines: list[list[str]] = []
    for i, line in enumerate(lines):
        if i < 8:
            continue
        if line.strip() and not line.startswith("LOCATION"):
            parts = line.strip().split(",")
            if len(parts) >= 22 and parts[0].isdigit():
                data_lines.append(parts)

    if not data_lines:
        raise ValueError(f"Could not parse EPW file: {epw_path}. No data lines found.")

    data: list[dict[str, Any]] = []
    for parts in data_lines:
        try:
            year = 2025
            month = int(parts[1])
            day = int(parts[2])
            hour = int(parts[3])
            Ta = float(parts[6])
            Td = float(parts[7])
            RH = float(parts[8])
            P_pa = float(parts[9])
            L_sky_wh = float(parts[12])
            K_down_wh = float(parts[13])
            U = float(parts[21])

            P_kpa = P_pa / 1000.0
            K_down = K_down_wh
            L_sky = L_sky_wh

            dt = datetime(year, month, day, hour - 1)
            day_of_year = dt.timetuple().tm_yday
            hour_of_year = (day_of_year - 1) * 24 + dt.hour

            VPD = calculate_vpd(Ta, RH)
            qsat = calculate_qsat(Ta, P_kpa)
            qa = calculate_specific_humidity(Ta, RH, P_kpa)

            data.append(
                {
                    "hour_of_year": hour_of_year,
                    "year": year,
                    "month": month,
                    "day": day,
                    "hour": hour,
                    "Ta": Ta,
                    "Td": Td,
                    "RH": RH,
                    "U": U,
                    "P": P_kpa,
                    "K_down": K_down,
                    "L_sky": L_sky,
                    "qa": qa,
                    "VPD": VPD,
                    "qsat": qsat,
                }
            )
        except (ValueError, IndexError):
            continue

    df = pd.DataFrame(data)
    df = df.sort_values("hour_of_year").reset_index(drop=True)

    if len(df) < 8760:
        full_hours = pd.DataFrame({"hour_of_year": range(8760)})
        df = full_hours.merge(df, on="hour_of_year", how="left")

    return df


def find_warmest_day(
    epw_path: str | Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[int, int, datetime]:
    """Find the warmest day of the year in an EPW file."""
    if epw_path is None:
        epw_path = get_path("weather_file", cfg)
    weather_df = load_epw(epw_path)
    max_temp_idx = weather_df["Ta"].idxmax()
    max_temp_row = weather_df.loc[max_temp_idx]

    month = int(max_temp_row["month"])
    day = int(max_temp_row["day"])
    hour_of_year = int(max_temp_row["hour_of_year"])

    date = datetime(2023, month, day)
    day_of_year = date.timetuple().tm_yday - 1

    return day_of_year, hour_of_year, date


def get_week_around_day(day_of_year: int, total_days: int = 365) -> tuple[int, int]:
    """Get start/end day indices (0-indexed, inclusive) for a week centered on day_of_year."""
    start_day = max(0, day_of_year - 3)
    end_day = min(total_days - 1, day_of_year + 3)
    return start_day, end_day
