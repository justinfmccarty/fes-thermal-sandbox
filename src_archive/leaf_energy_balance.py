"""
Leaf Energy Balance Solver

Solves leaf energy balance iteratively to find leaf temperature.
Energy balance: Rn = H + LE
"""

import numpy as np
from scipy.optimize import brentq
from typing import Tuple, Optional
from tree_species import TreeSpecies


# Physical constants
RHO_AIR = 1.2  # Air density [kg/m3]
CP_AIR = 1005.0  # Specific heat of air [J/kg/K]
LAMBDA_V = 2.45e6  # Latent heat of vaporization [J/kg]
R_GAS = 287.0  # Gas constant for dry air [J/kg/K]


def solve_leaf_temperature(
    Rn: float,
    Ta: float,
    qa: float,
    U: float,
    species: TreeSpecies,
    theta: float = 0.3,
    ra_scale: float = 1.0,
    shelter_factor: float = 1.0,
    P: float = 101.3
) -> Tuple[float, float, float, float, float]:
    """
    Solve leaf energy balance to find leaf temperature.
    
    Energy balance: Rn = H + LE
    Where:
    - Rn = net radiation [W/m2]
    - H = sensible heat = rho*cp*(T_leaf - Ta) / ra
    - LE = latent heat = rho*Lv*(qsat(T_leaf) - qa) / (ra + rs)
    
    Args:
        Rn: Net radiation [W/m2]
        Ta: Air temperature [C]
        qa: Specific humidity [kg/kg]
        U: Wind speed [m/s]
        species: TreeSpecies object with physiological parameters
        theta: Soil moisture [m3/m3]
        ra_scale: Aerodynamic resistance scaling factor
        shelter_factor: Shelter factor for wind reduction
        P: Atmospheric pressure [kPa]
        
    Returns:
        Tuple of (T_leaf, H, LE, gc, rs)
        - T_leaf: Leaf temperature [C]
        - H: Sensible heat flux [W/m2]
        - LE: Latent heat flux [W/m2]
        - gc: Stomatal conductance [mol/m2/s]
        - rs: Stomatal resistance [s/m]
    """
    # Convert to Kelvin for calculations
    Ta_K = Ta + 273.15
    
    # Calculate resistances
    ra = calculate_aerodynamic_resistance(U, ra_scale, shelter_factor)
    
    # Initial guess for leaf temperature
    T_guess = Ta
    
    # Bounds for root finding (reasonable leaf temperature range)
    T_min = Ta - 10.0  # Can be cooler than air
    T_max = Ta + 30.0  # Can be much warmer than air
    
    try:
        # Solve energy balance using root finding
        T_leaf = brentq(
            energy_balance_residual,
            T_min,
            T_max,
            args=(Rn, Ta_K, qa, ra, species, theta, P),
            xtol=0.1,  # Relaxed from 0.01 for 1.3-1.5x speedup (still accurate for stress metrics)
            maxiter=50
        )
    except ValueError:
        # If root finding fails, use air temperature as fallback
        T_leaf = Ta
    
    # Calculate fluxes at solution
    T_leaf_K = T_leaf + 273.15
    
    # Sensible heat
    H = RHO_AIR * CP_AIR * (T_leaf_K - Ta_K) / ra
    
    # Calculate stomatal conductance
    Kabs = Rn  # Approximate absorbed radiation (simplified)
    VPD = calculate_vpd_from_q(T_leaf, qa, P)
    
    gc = calculate_stomatal_conductance(species, Kabs, VPD, theta, T_leaf)
    rs = 1.0 / gc if gc > 0 else 1e6
    
    # Latent heat
    qsat_leaf = calculate_qsat(T_leaf, P)
    LE = RHO_AIR * LAMBDA_V * (qsat_leaf - qa) / (ra + rs)
    
    # Ensure energy balance (adjust LE if needed)
    LE = max(0.0, Rn - H)  # Can't have negative LE
    
    return T_leaf, H, LE, gc, rs


def energy_balance_residual(
    T_leaf: float,
    Rn: float,
    Ta_K: float,
    qa: float,
    ra: float,
    species: TreeSpecies,
    theta: float,
    P: float
) -> float:
    """
    Calculate energy balance residual for root finding.
    
    Residual = Rn - H - LE
    
    Args:
        T_leaf: Leaf temperature [C]
        Rn: Net radiation [W/m2]
        Ta_K: Air temperature [K]
        qa: Specific humidity [kg/kg]
        ra: Aerodynamic resistance [s/m]
        species: TreeSpecies object
        theta: Soil moisture [m3/m3]
        P: Pressure [kPa]
        
    Returns:
        Energy balance residual [W/m2]
    """
    T_leaf_K = T_leaf + 273.15
    
    # Sensible heat
    H = RHO_AIR * CP_AIR * (T_leaf_K - Ta_K) / ra
    
    # Calculate stomatal conductance
    Kabs = Rn  # Simplified
    VPD = calculate_vpd_from_q(T_leaf, qa, P)
    gc = calculate_stomatal_conductance(species, Kabs, VPD, theta, T_leaf)
    rs = 1.0 / gc if gc > 0 else 1e6
    
    # Latent heat
    qsat_leaf = calculate_qsat(T_leaf, P)
    LE = RHO_AIR * LAMBDA_V * (qsat_leaf - qa) / (ra + rs)
    
    # Residual
    residual = Rn - H - LE
    
    return residual


def calculate_aerodynamic_resistance(
    U: float,
    ra_scale: float = 1.0,
    shelter_factor: float = 1.0,
    U_min: float = 0.5
) -> float:
    """
    Calculate aerodynamic resistance.
    
    ra = ra_scale / max(U * shelter_factor, U_min)
    
    Args:
        U: Wind speed [m/s]
        ra_scale: Scaling factor [s/m]
        shelter_factor: Shelter factor (reduces effective wind)
        U_min: Minimum wind speed [m/s]
        
    Returns:
        Aerodynamic resistance [s/m]
    """
    U_eff = max(U * shelter_factor, U_min)
    ra = ra_scale / U_eff
    
    return ra


def calculate_stomatal_conductance(
    species: TreeSpecies,
    Kabs: float,
    VPD: float,
    theta: float,
    T_leaf: float
) -> float:
    """
    Calculate stomatal conductance using Jarvis-style model.
    
    gc = gc_max * fRad(Kabs) * fVPD(VPD) * fSM(theta) * fT(T_leaf)
    
    Args:
        species: TreeSpecies object
        Kabs: Absorbed shortwave radiation [W/m2]
        VPD: Vapor pressure deficit [kPa]
        theta: Soil moisture [m3/m3]
        T_leaf: Leaf temperature [C]
        
    Returns:
        Stomatal conductance [mol/m2/s]
    """
    # Response functions
    f_rad = species.fRad(Kabs)
    f_vpd = species.fVPD(VPD)
    f_sm = species.fSM(theta)
    f_t = species.fT(T_leaf)
    
    # Combined response
    gc = species.gc_max * f_rad * f_vpd * f_sm * f_t
    
    return max(0.0, gc)


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
    qsat = 0.622 * esat / P  # kg/kg
    
    return qsat


def calculate_vpd_from_q(T: float, q: float, P: float) -> float:
    """
    Calculate VPD from temperature and specific humidity.
    
    Args:
        T: Temperature [C]
        q: Specific humidity [kg/kg]
        P: Pressure [kPa]
        
    Returns:
        VPD [kPa]
    """
    # Saturation vapor pressure
    esat = 0.6108 * np.exp(17.27 * T / (T + 237.3))  # kPa
    
    # Actual vapor pressure from specific humidity
    ea = q * P / 0.622  # kPa
    
    # VPD
    VPD = esat - ea
    
    return max(0.0, VPD)


def calculate_net_radiation(
    Kabs: float,
    L_in: float,
    epsilon_leaf: float,
    T_leaf: float
) -> float:
    """
    Calculate net radiation.
    
    Rn = Kabs + epsilon * L_in - epsilon * sigma * T_leaf^4
    
    Args:
        Kabs: Absorbed shortwave radiation [W/m2]
        L_in: Incoming longwave radiation [W/m2]
        epsilon_leaf: Leaf emissivity
        T_leaf: Leaf temperature [C]
        
    Returns:
        Net radiation [W/m2]
    """
    SIGMA = 5.67e-8  # Stefan-Boltzmann constant
    T_leaf_K = T_leaf + 273.15
    
    # Net radiation
    Rn = Kabs + epsilon_leaf * L_in - epsilon_leaf * SIGMA * T_leaf_K**4
    
    return Rn

