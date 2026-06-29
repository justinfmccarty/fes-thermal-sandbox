"""
Weather Data Loader for EPW Files

Loads EPW weather files and extracts meteorological variables needed for
tree stress modeling: air temperature, humidity, wind speed, pressure,
solar radiation, and longwave radiation.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta
import os
# from pvlib import io as pvlib_io


def load_epw(epw_path: str) -> pd.DataFrame:
    """
    Load EPW weather file and extract meteorological variables.
    
    EPW file format (EnergyPlus Weather):
    - Lines 1-8: Header information
    - Line 9: Column headers
    - Lines 10+: Hourly data (8760 rows)
    
    Standard EPW columns:
    0: Year
    1: Month
    2: Day
    3: Hour
    4: Minute
    5: Data Source and Uncertainty Flags
    6: Dry Bulb Temperature [C]
    7: Dew Point Temperature [C]
    8: Relative Humidity [%]
    9: Atmospheric Station Pressure [Pa]
    10: Extraterrestrial Horizontal Radiation [Wh/m2]
    11: Extraterrestrial Direct Normal Radiation [Wh/m2]
    12: Horizontal Infrared Radiation Intensity [Wh/m2]
    13: Global Horizontal Radiation [Wh/m2]
    14: Direct Normal Radiation [Wh/m2]
    15: Diffuse Horizontal Radiation [Wh/m2]
    16: Global Horizontal Illuminance [lux]
    17: Direct Normal Illuminance [lux]
    18: Diffuse Horizontal Illuminance [lux]
    19: Zenith Luminance [Cd/m2]
    20: Wind Direction [deg]
    21: Wind Speed [m/s]
    22: Total Sky Cover [tenths]
    23: Opaque Sky Cover [tenths]
    24: Visibility [km]
    25: Ceiling Height [m]
    26: Present Weather Observation
    27: Present Weather Codes
    28: Precipitable Water [mm]
    29: Aerosol Optical Depth [thousandths]
    30: Snow Depth [cm]
    31: Days Since Last Snow
    32: Albedo []
    33: Liquid Precipitation Depth [mm]
    34: Liquid Precipitation Quantity [hr]
    
    Args:
        epw_path: Path to EPW file
        
    Returns:
        DataFrame with columns:
        - hour_of_year: 0-8759
        - Ta: Air temperature [C]
        - RH: Relative humidity [%]
        - U: Wind speed [m/s]
        - P: Atmospheric pressure [kPa]
        - K_down: Global horizontal radiation [W/m2] (converted from Wh/m2)
        - L_sky: Downwelling longwave radiation [W/m2]
        - qa: Specific humidity [kg/kg]
        - VPD: Vapor pressure deficit [kPa]
        - qsat: Saturation specific humidity [kg/kg]
    """
    # Read EPW file (skip header lines 1-8, line 9 is column names)
    with open(epw_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Skip header lines (first 8 lines)
    # Line 9 should be column headers, but EPW format doesn't always have them
    # So we'll parse manually based on known column positions
    
    # Find where data starts (after header lines)
    data_lines = []
    for i, line in enumerate(lines):
        if i < 8:
            continue  # Skip header
        if line.strip() and not line.startswith('LOCATION'):
            # Try to parse as data line
            parts = line.strip().split(',')
            if len(parts) >= 22 and parts[0].isdigit():
                data_lines.append(parts)
    
    if not data_lines:
        raise ValueError(f"Could not parse EPW file: {epw_path}. No data lines found.")
    
    # Extract relevant columns
    data = []
    for parts in data_lines:
        try:
            # Extract key variables (0-indexed)
            year = 2025
            month = int(parts[1])
            day = int(parts[2])
            hour = int(parts[3])
            Ta = float(parts[6])  # Dry bulb temperature [C]
            Td = float(parts[7])  # Dew point temperature [C]
            RH = float(parts[8])  # Relative humidity [%]
            P_pa = float(parts[9])  # Pressure [Pa]
            L_sky_wh = float(parts[12])  # Horizontal IR radiation [Wh/m2]
            K_down_wh = float(parts[13])  # Global horizontal radiation [Wh/m2]
            U = float(parts[21])  # Wind speed [m/s]
            
            # Convert units
            P_kpa = P_pa / 1000.0  # Pa to kPa
            K_down = K_down_wh  # Wh/m2 to W/m2 (hourly average)
            L_sky = L_sky_wh  # Wh/m2 to W/m2 (hourly average)
            
            # Calculate hour of year (0-8759)
            # Create datetime to calculate day of year
            from datetime import datetime
            dt = datetime(year, month, day, hour - 1)  # EPW hour is 1-24, convert to 0-23
            day_of_year = dt.timetuple().tm_yday
            hour_of_year = (day_of_year - 1) * 24 + dt.hour
            
            # Calculate derived variables
            VPD = calculate_vpd(Ta, RH)
            qsat = calculate_qsat(Ta, P_kpa)
            qa = calculate_specific_humidity(Ta, RH, P_kpa)
            
            data.append({
                'hour_of_year': hour_of_year,
                'year': year,
                'month': month,
                'day': day,
                'hour': hour,
                'Ta': Ta,
                'Td': Td,
                'RH': RH,
                'U': U,
                'P': P_kpa,
                'K_down': K_down,
                'L_sky': L_sky,
                'qa': qa,
                'VPD': VPD,
                'qsat': qsat
            })
        except (ValueError, IndexError) as e:
            # Skip malformed lines
            continue
    
    df = pd.DataFrame(data)
    
    # Sort by hour_of_year to ensure correct order
    df = df.sort_values('hour_of_year').reset_index(drop=True)
    
    # Ensure we have 8760 hours (fill missing with NaN if needed)
    if len(df) < 8760:
        # Create full year index
        full_hours = pd.DataFrame({'hour_of_year': range(8760)})
        df = full_hours.merge(df, on='hour_of_year', how='left')
    
    
    return df


def calculate_vpd(Ta: float, RH: float) -> float:
    """
    Calculate vapor pressure deficit (VPD) from air temperature and relative humidity.
    
    Args:
        Ta: Air temperature [C]
        RH: Relative humidity [%]
        
    Returns:
        VPD [kPa]
    """
    # Saturation vapor pressure (Tetens equation)
    esat = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))  # kPa
    
    # Actual vapor pressure
    ea = esat * (RH / 100.0)  # kPa
    
    # Vapor pressure deficit
    VPD = esat - ea  # kPa
    
    return max(0.0, VPD)  # Ensure non-negative


def calculate_qsat(T: float, P: float) -> float:
    """
    Calculate saturation specific humidity.
    
    Args:
        T: Temperature [C]
        P: Pressure [kPa]
        
    Returns:
        Saturation specific humidity [kg/kg]
    """
    # Saturation vapor pressure
    esat = 0.6108 * np.exp(17.27 * T / (T + 237.3))  # kPa
    
    # Saturation specific humidity
    # qsat = 0.622 * esat / (P - 0.378 * esat)
    qsat = 0.622 * esat / P  # Simplified (0.378*esat << P)
    
    return qsat


def calculate_specific_humidity(Ta: float, RH: float, P: float) -> float:
    """
    Calculate specific humidity from air temperature, relative humidity, and pressure.
    
    Args:
        Ta: Air temperature [C]
        RH: Relative humidity [%]
        P: Pressure [kPa]
        
    Returns:
        Specific humidity [kg/kg]
    """
    # Saturation vapor pressure
    esat = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))  # kPa
    
    # Actual vapor pressure
    ea = esat * (RH / 100.0)  # kPa
    
    # Specific humidity
    qa = 0.622 * ea / P  # kg/kg
    
    return qa


def get_weather_at_hour(weather_df: pd.DataFrame, hour_of_year: int) -> dict:
    """
    Extract weather variables for a specific hour of year.
    
    Args:
        weather_df: DataFrame from load_epw()
        hour_of_year: Hour of year (0-8759)
        
    Returns:
        Dictionary with weather variables
    """
    row = weather_df[weather_df['hour_of_year'] == hour_of_year]
    if len(row) == 0:
        raise ValueError(f"No data found for hour_of_year={hour_of_year}")
    
    return row.iloc[0].to_dict()


def find_warmest_day(epw_path: str) -> Tuple[int, int, datetime]:
    """
    Find the warmest day of the year in an EPW file.
    
    Args:
        epw_path: Path to EPW file
        
    Returns:
        Tuple of (day_of_year, hour_of_year, date) for the warmest day
    """
    weather_df = load_epw(epw_path)
    
    # Find hour with maximum temperature
    max_temp_idx = weather_df['Ta'].idxmax()
    max_temp_row = weather_df.loc[max_temp_idx]
    
    month = int(max_temp_row['month'])
    day = int(max_temp_row['day'])
    hour_of_year = int(max_temp_row['hour_of_year'])
    
    # Calculate day of year (0-364)
    date = datetime(2023, month, day)  # Use any non-leap year
    day_of_year = date.timetuple().tm_yday - 1  # 0-indexed
    
    print(f"   Warmest day: {date.strftime('%B %d')} (day {day_of_year+1})")
    print(f"   Peak temperature: {max_temp_row['Ta']:.1f}°C at hour {hour_of_year}")
    
    return day_of_year, hour_of_year, date


def get_week_around_day(day_of_year: int, total_days: int = 365) -> Tuple[int, int]:
    """
    Get the start and end day indices for a week centered on a given day.
    
    Args:
        day_of_year: Day of year (0-364)
        total_days: Total days in year (365 or 366)
        
    Returns:
        Tuple of (start_day, end_day) inclusive, both 0-indexed
    """
    # Center the week on the given day (3 days before, 3 days after)
    start_day = max(0, day_of_year - 3)
    end_day = min(total_days - 1, day_of_year + 3)
    
    return start_day, end_day


def create_subset_epw(
    input_epw: str,
    output_epw: str,
    start_day: int,
    end_day: int
) -> str:
    """
    Create a subset EPW file for a specified date range.
    
    Args:
        input_epw: Path to input EPW file
        output_epw: Path to output EPW file
        start_day: Start day of year (0-indexed, 0 = Jan 1)
        end_day: End day of year (0-indexed, inclusive)
        
    Returns:
        Path to created EPW file
    """
    # Read the full EPW file
    with open(input_epw, 'r') as f:
        lines = f.readlines()
    
    # Header is first 8 lines
    header = lines[:8]
    data_lines = lines[8:]
    
    # Calculate hour ranges (each day has 24 hours)
    start_hour = start_day * 24
    end_hour = (end_day + 1) * 24  # +1 because end_day is inclusive
    
    # Extract subset of data lines (hours 0-8759)
    subset_data = data_lines[start_hour:end_hour]
    
    # Write output file
    with open(output_epw, 'w') as f:
        f.writelines(header)
        f.writelines(subset_data)
    
    num_hours = len(subset_data)
    num_days = num_hours / 24
    print(f"   Created subset EPW: {num_days:.1f} days ({num_hours} hours)")
    print(f"   Days {start_day+1} to {end_day+1} (inclusive)")
    
    return output_epw


def get_simulation_period_epw(
    input_epw: str,
    period_type: str = 'annual',
    start_date: Optional[Tuple[int, int]] = None,
    end_date: Optional[Tuple[int, int]] = None,
    output_dir: Optional[str] = None
) -> Tuple[str, int, int]:
    """
    Get or create an EPW file for the specified simulation period.
    
    Args:
        input_epw: Path to full annual EPW file
        period_type: One of 'annual', 'warmest_week', or 'manual'
        start_date: For 'manual' mode: (month, day) tuple (1-indexed)
        end_date: For 'manual' mode: (month, day) tuple (1-indexed, inclusive)
        output_dir: Directory for subset EPW files (defaults to same as input)
        
    Returns:
        Tuple of (epw_path, num_hours, start_hour_offset) where:
            - epw_path: Path to EPW file to use
            - num_hours: Number of hours in the period
            - start_hour_offset: Starting hour index (0 for annual, dynamically calculated for subsets)
    """
    if period_type == 'annual':
        # Use full annual file - starts at hour 0
        return input_epw, 8760, 0
    
    if output_dir is None:
        output_dir = os.path.dirname(input_epw)
    
    if period_type == 'warmest_week':
        # Find warmest day and create week around it
        day_of_year, _, date = find_warmest_day(input_epw)
        start_day, end_day = get_week_around_day(day_of_year)
        
        # Calculate starting hour offset (dynamically from weather file)
        start_hour_offset = start_day * 24
        
        # Create subset EPW
        subset_name = f"subset_warmest_week_{date.strftime('%b%d')}.epw"
        output_epw = os.path.join(output_dir, subset_name)
        
        if not os.path.exists(output_epw):
            create_subset_epw(input_epw, output_epw, start_day, end_day)
        
        num_hours = (end_day - start_day + 1) * 24
        return output_epw, num_hours, start_hour_offset
    
    elif period_type == 'manual':
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date required for 'manual' period_type")
        
        # Convert (month, day) to day_of_year
        start_dt = datetime(2023, start_date[0], start_date[1])
        end_dt = datetime(2023, end_date[0], end_date[1])
        start_day = start_dt.timetuple().tm_yday - 1  # 0-indexed
        end_day = end_dt.timetuple().tm_yday - 1
        
        # Calculate starting hour offset
        start_hour_offset = start_day * 24
        
        # Create subset EPW
        subset_name = f"subset_{start_dt.strftime('%b%d')}_{end_dt.strftime('%b%d')}.epw"
        output_epw = os.path.join(output_dir, subset_name)
        
        if not os.path.exists(output_epw):
            create_subset_epw(input_epw, output_epw, start_day, end_day)
        
        num_hours = (end_day - start_day + 1) * 24
        return output_epw, num_hours, start_hour_offset
    
    else:
        raise ValueError(f"Invalid period_type: {period_type}. Must be 'annual', 'warmest_week', or 'manual'")

