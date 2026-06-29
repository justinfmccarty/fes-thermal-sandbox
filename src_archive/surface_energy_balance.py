"""
Surface Energy Balance Module

Calculates surface temperature and Mean Radiant Temperature (MRT) from
energy balance equations.
"""

import numpy as np
from typing import Tuple


# Stefan-Boltzmann constant [W/m2/K4]
SIGMA = 5.67e-8


def calculate_surface_temperature(
    K_down: float,
    K_up: float,
    albedo: float,
    emissivity: float,
    Ta: float,
    L_sky: float,
    U: float = 2.0,
    h_conv: float = 10.0
) -> float:
    """
    Calculate surface temperature from energy balance.
    
    Energy balance: Rn = H + LE
    Where:
    - Rn = net radiation = (1-alpha)*K_down - K_up + epsilon*(L_sky - sigma*Tsurf^4)
    - H = sensible heat = h_conv * (Tsurf - Ta)
    - LE = latent heat (assumed small for dry surfaces, simplified)
    
    Args:
        K_down: Downwelling shortwave [W/m2]
        K_up: Upwelling shortwave [W/m2]
        albedo: Surface albedo (0.0-1.0)
        emissivity: Surface emissivity (0.0-1.0)
        Ta: Air temperature [C]
        L_sky: Downwelling longwave [W/m2]
        U: Wind speed [m/s] (for convective coefficient)
        h_conv: Convective heat transfer coefficient [W/m2/K]
        
    Returns:
        Surface temperature [C]
    """
    # Convert to Kelvin
    Ta_K = Ta + 273.15
    
    # Net shortwave radiation
    K_net = (1.0 - albedo) * K_down - K_up
    
    # Net longwave radiation (simplified: assume surface emits as blackbody)
    # Rn = K_net + epsilon * (L_sky - sigma * Tsurf^4)
    # At equilibrium: Rn = H = h_conv * (Tsurf - Ta)
    
    # Solve iteratively for Tsurf
    Tsurf_K = Ta_K  # Initial guess
    
    for _ in range(20):  # Max iterations
        # Net radiation
        L_net = emissivity * (L_sky - SIGMA * Tsurf_K**4)
        Rn = K_net + L_net
        
        # Sensible heat flux
        H = h_conv * (Tsurf_K - Ta_K)
        
        # Update surface temperature
        # Rn = H (at equilibrium)
        # K_net + epsilon*L_sky - epsilon*sigma*Tsurf^4 = h_conv*(Tsurf - Ta)
        # Rearranging: epsilon*sigma*Tsurf^4 + h_conv*Tsurf = K_net + epsilon*L_sky + h_conv*Ta
        
        # Use Newton-Raphson iteration
        f = emissivity * SIGMA * Tsurf_K**4 + h_conv * Tsurf_K - (K_net + emissivity * L_sky + h_conv * Ta_K)
        df = 4.0 * emissivity * SIGMA * Tsurf_K**3 + h_conv
        
        if abs(df) < 1e-10:
            break
        
        Tsurf_K_new = Tsurf_K - f / df
        
        # Ensure reasonable bounds
        Tsurf_K_new = max(250.0, min(350.0, Tsurf_K_new))
        
        if abs(Tsurf_K_new - Tsurf_K) < 0.01:
            break
        
        Tsurf_K = Tsurf_K_new
    
    return Tsurf_K - 273.15  # Convert back to Celsius


def calculate_mrt(
    Tsurf: float,
    SVF: float,
    Ta: float,
    L_sky: float
) -> float:
    """
    Calculate Mean Radiant Temperature (MRT).
    
    MRT represents the effective temperature of surrounding surfaces
    that the leaf "sees". It combines sky and ground contributions.
    
    Args:
        Tsurf: Surface temperature [C]
        SVF: Sky view factor (0.0-1.0), fraction of hemisphere that is sky
        Ta: Air temperature [C]
        L_sky: Downwelling longwave from sky [W/m2]
        
    Returns:
        Mean Radiant Temperature [C]
    """
    # Convert to Kelvin
    Tsurf_K = Tsurf + 273.15
    Ta_K = Ta + 273.15
    
    # Longwave from ground (assuming ground at surface temperature)
    L_ground = SIGMA * Tsurf_K**4  # [W/m2]
    
    # Effective longwave radiation
    # L_effective = SVF * L_sky + (1 - SVF) * L_ground
    L_effective = SVF * L_sky + (1.0 - SVF) * L_ground
    
    # Convert back to temperature (effective blackbody temperature)
    # L = sigma * T^4, so T = (L / sigma)^0.25
    T_mrt_K = (L_effective / SIGMA) ** 0.25
    
    return T_mrt_K - 273.15  # Convert to Celsius


def calculate_longwave_in(
    SVF: float,
    L_sky: float,
    L_air: float = None,
    Tsurf: float = None
) -> float:
    """
    Calculate incoming longwave radiation.
    
    Args:
        SVF: Sky view factor (0.0-1.0)
        L_sky: Downwelling longwave from sky [W/m2]
        L_air: Longwave from air (if available) [W/m2]
        Tsurf: Surface temperature [C] (used if L_air not provided)
        
    Returns:
        Incoming longwave radiation [W/m2]
    """
    if L_air is None:
        # Estimate from surface temperature
        if Tsurf is None:
            # Default: use sky temperature
            L_air = L_sky
        else:
            Tsurf_K = Tsurf + 273.15
            L_air = SIGMA * Tsurf_K**4
    
    # Weighted average of sky and ground/air contributions
    L_in = SVF * L_sky + (1.0 - SVF) * L_air
    
    return L_in

