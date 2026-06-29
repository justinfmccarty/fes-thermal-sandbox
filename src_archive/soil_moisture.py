"""
Soil Moisture Model

1-layer bucket model for root zone soil moisture dynamics.
Enhanced with SoilMoistureBucket class for CEB model integration.

Features:
- Root-zone water balance (precipitation, ET, drainage)
- Stomatal stress function (REW-based)
- Dynamic stomatal resistance for CEB model

Configuration:
    Parameters are loaded from config.yaml via config_locator.
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

from config_locator import get_config


@dataclass
class SoilMoistureState:
    """Container for soil moisture state and derived variables."""
    theta: float           # Volumetric water content [m3/m3]
    REW: float             # Relative extractable water [0-1]
    f_SM: float            # Soil moisture stress factor [0-1]
    r_sto: float           # Stomatal resistance [s/m]
    drainage: float        # Drainage rate [m/h]
    ET: float              # Evapotranspiration [m/h]


class SoilMoistureBucket:
    """
    Root-zone soil moisture bucket model with stomatal stress coupling.
    
    Water balance:
        θ(t+1) = θ(t) + (P - ET - D) / Z_r
    
    Stomatal stress:
        REW = (θ - θ_wilt) / (θ_fc - θ_wilt)
        f_SM = min(1.0, REW / REW_crit)
        r_sto = r_sto_min / f_SM
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize soil moisture bucket model.
        
        Args:
            config_path: Optional path to config.yaml
        """
        self._config = get_config(config_path)
        
        # Cache soil parameters
        soil = self._config.model.soil
        self._theta_fc = soil.theta_fc
        self._theta_wilt = soil.theta_wilt
        self._theta_sat = soil.theta_sat
        self._theta_init = soil.theta_init
        self._Z_r = soil.Z_r
        self._k_drain_default = soil.k_drain_default
        self._REW_crit = soil.REW_crit
        self._r_sto_min = soil.r_sto_min
        
        # Cache physical constants
        self._lambda_v = self._config.physical_constants.lambda_v
    
    def initialize(self, theta: Optional[float] = None) -> float:
        """
        Initialize soil moisture.
        
        Args:
            theta: Initial soil moisture [m3/m3] (uses config default if None)
            
        Returns:
            Initial theta
        """
        return theta if theta is not None else self._theta_init
    
    def calculate_REW(self, theta: float) -> float:
        """
        Calculate relative extractable water.
        
        REW = (θ - θ_wilt) / (θ_fc - θ_wilt)
        
        Args:
            theta: Volumetric water content [m3/m3]
            
        Returns:
            REW [0-1], clamped
        """
        if self._theta_fc <= self._theta_wilt:
            return 0.0
        
        REW = (theta - self._theta_wilt) / (self._theta_fc - self._theta_wilt)
        return max(0.0, min(1.0, REW))
    
    def calculate_stress_factor(self, theta: float) -> float:
        """
        Calculate soil moisture stress factor.
        
        f_SM = 1.0 when REW >= REW_crit
        f_SM = REW / REW_crit when REW < REW_crit
        
        Args:
            theta: Volumetric water content [m3/m3]
            
        Returns:
            f_SM [0-1], where 1.0 = no stress
        """
        REW = self.calculate_REW(theta)
        
        if REW >= self._REW_crit:
            return 1.0
        elif REW <= 0:
            return 0.01  # Minimum to avoid division by zero
        else:
            return max(0.01, REW / self._REW_crit)
    
    def calculate_stomatal_resistance(
        self,
        theta: float,
        r_sto_min: Optional[float] = None
    ) -> float:
        """
        Calculate stomatal resistance based on soil moisture.
        
        r_sto = r_sto_min / f_SM
        
        As soil dries (f_SM decreases), stomata close (r_sto increases).
        
        Args:
            theta: Volumetric water content [m3/m3]
            r_sto_min: Minimum stomatal resistance [s/m] (uses config if None)
            
        Returns:
            Stomatal resistance [s/m]
        """
        r_min = r_sto_min if r_sto_min is not None else self._r_sto_min
        f_SM = self.calculate_stress_factor(theta)
        
        # r_sto increases as f_SM decreases (stomata close when dry)
        r_sto = r_min / f_SM
        
        # Cap at reasonable maximum (fully closed stomata)
        return min(10000.0, r_sto)
    
    def calculate_drainage(
        self,
        theta: float,
        k_drain: Optional[float] = None
    ) -> float:
        """
        Calculate drainage when soil exceeds field capacity.
        
        D = k_drain * (θ - θ_fc) when θ > θ_fc
        D = 0 otherwise
        
        Args:
            theta: Volumetric water content [m3/m3]
            k_drain: Drainage coefficient [1/day] (uses default if None)
            
        Returns:
            Drainage rate [m/h]
        """
        k = k_drain if k_drain is not None else self._k_drain_default
        
        if theta > self._theta_fc:
            # Convert k_drain from 1/day to 1/h
            k_hourly = k / 24.0
            excess = theta - self._theta_fc
            drainage = k_hourly * excess * self._Z_r  # [m/h]
        else:
            drainage = 0.0
        
        return drainage
    
    def et_from_le(self, LE: float) -> float:
        """
        Convert latent heat flux to evapotranspiration depth.
        
        Args:
            LE: Latent heat flux [W/m2]
            
        Returns:
            ET [m/h]
        """
        RHO_WATER = 1000.0  # [kg/m3]
        ET_ms = LE / (RHO_WATER * self._lambda_v)  # [m/s]
        return ET_ms * 3600.0  # [m/h]
    
    def step(
        self,
        theta_prev: float,
        LE: float,
        precip_mm: float = 0.0,
        dt: float = 3600.0,
        k_drain: Optional[float] = None,
        r_sto_min: Optional[float] = None
    ) -> SoilMoistureState:
        """
        Advance soil moisture by one timestep.
        
        Args:
            theta_prev: Previous soil moisture [m3/m3]
            LE: Latent heat flux from tree [W/m2]
            precip_mm: Precipitation [mm] during timestep
            dt: Timestep [s]
            k_drain: Drainage coefficient [1/day]
            r_sto_min: Minimum stomatal resistance [s/m]
            
        Returns:
            SoilMoistureState with updated values
        """
        # Convert precipitation to meters
        P = precip_mm / 1000.0  # [m]
        
        # Calculate ET from latent heat (hourly rate)
        ET_mh = self.et_from_le(LE)
        ET = ET_mh * (dt / 3600.0)  # Scale to timestep
        
        # Calculate drainage
        D_mh = self.calculate_drainage(theta_prev, k_drain)
        D = D_mh * (dt / 3600.0)  # Scale to timestep
        
        # Water balance
        dtheta = (P - ET - D) / self._Z_r
        theta_new = theta_prev + dtheta
        
        # Clamp to physical bounds
        theta_new = max(self._theta_wilt * 0.5, min(self._theta_sat, theta_new))
        
        # Calculate derived variables for new state
        REW = self.calculate_REW(theta_new)
        f_SM = self.calculate_stress_factor(theta_new)
        r_sto = self.calculate_stomatal_resistance(theta_new, r_sto_min)
        
        return SoilMoistureState(
            theta=theta_new,
            REW=REW,
            f_SM=f_SM,
            r_sto=r_sto,
            drainage=D_mh,
            ET=ET_mh
        )
    
    def get_state(
        self,
        theta: float,
        r_sto_min: Optional[float] = None
    ) -> SoilMoistureState:
        """
        Get current state without updating (diagnostic).
        
        Args:
            theta: Current soil moisture [m3/m3]
            r_sto_min: Minimum stomatal resistance [s/m]
            
        Returns:
            SoilMoistureState
        """
        REW = self.calculate_REW(theta)
        f_SM = self.calculate_stress_factor(theta)
        r_sto = self.calculate_stomatal_resistance(theta, r_sto_min)
        drainage = self.calculate_drainage(theta)
        
        return SoilMoistureState(
            theta=theta,
            REW=REW,
            f_SM=f_SM,
            r_sto=r_sto,
            drainage=drainage,
            ET=0.0  # No ET without LE
        )


# =============================================================================
# Legacy functions (kept for backward compatibility)
# =============================================================================

def update_soil_moisture(
    theta: float,
    P: float,
    Irr: float,
    ET: float,
    Drain: float,
    Zr: float,
    dt: float = 3600.0,
    theta_sat: float = 0.4,
    theta_wilt: float = 0.1
) -> float:
    """
    Update soil moisture using bucket model.
    
    dtheta/dt = (P + Irr - ET - Drain) / Zr
    
    Args:
        theta: Current volumetric water content [m3/m3]
        P: Precipitation [m] (depth)
        Irr: Irrigation [m] (depth)
        ET: Evapotranspiration [m] (depth)
        Drain: Drainage [m] (depth)
        Zr: Root zone depth [m]
        dt: Time step [s]
        theta_sat: Saturated water content [m3/m3]
        theta_wilt: Wilting point [m3/m3]
        
    Returns:
        Updated volumetric water content [m3/m3]
    """
    # Calculate change in water content
    dtheta = (P + Irr - ET - Drain) / Zr
    
    # Update theta
    theta_new = theta + dtheta * (dt / 3600.0)  # Convert dt to hours
    
    # Clamp to physical bounds
    theta_new = max(theta_wilt, min(theta_sat, theta_new))
    
    return theta_new


def calculate_fSM(
    theta: float,
    theta_crit: float = 0.3,
    theta_wilt: float = 0.1
) -> float:
    """
    Calculate soil moisture stress factor.
    
    fSM declines linearly between theta_crit and theta_wilt.
    
    Args:
        theta: Volumetric water content [m3/m3]
        theta_crit: Critical soil moisture (stress begins) [m3/m3]
        theta_wilt: Wilting point [m3/m3]
        
    Returns:
        Stress factor (0.0-1.0), where 1.0 = no stress
    """
    if theta >= theta_crit:
        return 1.0
    elif theta <= theta_wilt:
        return 0.0
    else:
        # Linear decline
        return (theta - theta_wilt) / (theta_crit - theta_wilt)


def calculate_drainage(
    theta: float,
    theta_sat: float = 0.4,
    k_drain: float = 0.01
) -> float:
    """
    Calculate drainage rate.
    
    Drainage occurs when theta > field capacity.
    Simplified: linear drainage above field capacity.
    
    Args:
        theta: Volumetric water content [m3/m3]
        theta_sat: Saturated water content [m3/m3]
        k_drain: Drainage coefficient [m/h]
        
    Returns:
        Drainage rate [m/h]
    """
    theta_fc = 0.3  # Field capacity (simplified)
    
    if theta > theta_fc:
        # Drainage proportional to excess water
        excess = (theta - theta_fc) / (theta_sat - theta_fc)
        drain = k_drain * excess
    else:
        drain = 0.0
    
    return drain


def et_from_le(LE: float) -> float:
    """
    Convert latent heat flux to evapotranspiration depth.
    
    ET = LE / (rho_water * Lv)
    
    Args:
        LE: Latent heat flux [W/m2]
        
    Returns:
        Evapotranspiration [m/h]
    """
    RHO_WATER = 1000.0  # Water density [kg/m3]
    LAMBDA_V = 2.45e6  # Latent heat [J/kg]
    
    # Convert W/m2 to m/h
    # LE [W/m2] = LE [J/m2/s]
    # ET [m] = LE [J/m2] / (rho_water [kg/m3] * Lv [J/kg])
    # ET [m/h] = ET [m/s] * 3600
    
    ET_ms = LE / (RHO_WATER * LAMBDA_V)  # m/s
    ET_mh = ET_ms * 3600.0  # m/h
    
    return ET_mh

