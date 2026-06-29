"""
Ground Temperature Model

Implements a 1-layer surface energy balance for ground temperature (Tg).
This module provides physically-based ground temperature that responds to:
- Albedo (solar absorption)
- Emissivity (radiative cooling)
- Thermal mass (heat capacity)
- Evaporative cooling (for pervious/vegetated surfaces)

The ground temperature feeds into the Li et al. CEB model via:
    R_lw_up = epsilon_g * sigma * Tg^4

Configuration:
    All parameters are loaded from config.yaml via config_locator.
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from config_locator import get_config


@dataclass
class GroundState:
    """Container for ground temperature state."""
    Tg: float              # Ground temperature [C]
    R_net: float           # Net radiation [W/m2]
    H_g: float             # Sensible heat flux [W/m2]
    LE_g: float            # Latent heat flux [W/m2]
    G: float               # Ground heat flux (storage) [W/m2]


class GroundEnergyBalance:
    """
    1-Layer Ground Surface Energy Balance Model.
    
    Solves:
        C_g * dTg/dt = (1-α_g)*K↓ + L↓ - ε_g*σ*Tg⁴ - H_g - LE_g
    
    Using explicit timestep:
        Tg(t+1) = Tg(t) + dt * R_net / C_g
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ground energy balance model.
        
        Args:
            config_path: Optional path to config.yaml
        """
        self._config = get_config(config_path)
        
        # Cache physical constants
        self._sigma = self._config.physical_constants.sigma
        self._rho_air = self._config.physical_constants.rho_air
        self._cp_air = self._config.physical_constants.cp_air
        self._lambda_v = self._config.physical_constants.lambda_v
        
        # Cache ground model parameters
        self._ground = self._config.model.ground
        self._r_a_ground = self._ground.r_a_ground
        self._ET_pot_ref = self._ground.ET_pot_ref
        
        # Load ground type properties
        self._ground_types = {}
        for type_name in ['impervious', 'pervious', 'vegetated']:
            type_config = getattr(self._ground.types, type_name)
            self._ground_types[type_name] = {
                'heat_capacity': type_config.heat_capacity,
                'evap_factor': type_config.evap_factor,
                'k_drain': type_config.k_drain
            }
    
    def get_ground_properties(
        self,
        ground_type: str,
        albedo: Optional[float] = None,
        emissivity: Optional[float] = None,
        heat_capacity: Optional[float] = None,
        evap_factor: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Get ground properties for a surface type.
        
        Args:
            ground_type: One of 'impervious', 'pervious', 'vegetated'
            albedo: Override albedo (from material database)
            emissivity: Override emissivity (from material database)
            heat_capacity: Override heat capacity
            evap_factor: Override evaporation factor
            
        Returns:
            Dict with heat_capacity, evap_factor, albedo, emissivity
        """
        if ground_type not in self._ground_types:
            ground_type = 'impervious'  # Default fallback
        
        props = self._ground_types[ground_type].copy()
        
        # Use material-specific albedo/emissivity if provided
        if albedo is not None:
            props['albedo'] = albedo
        if emissivity is not None:
            props['emissivity'] = emissivity
        
        # Allow property overrides
        if heat_capacity is not None:
            props['heat_capacity'] = heat_capacity
        if evap_factor is not None:
            props['evap_factor'] = evap_factor
        
        return props
    
    def calculate_longwave_sky(self, Ta: float, RH: float = 0.5) -> float:
        """
        Calculate downwelling longwave radiation from sky.
        
        Uses Prata (1996) clear-sky emissivity formula.
        
        Args:
            Ta: Air temperature [C]
            RH: Relative humidity [fraction, 0-1]
            
        Returns:
            L_sky: Downwelling longwave [W/m2]
        """
        Ta_K = Ta + 273.15
        
        # Saturation vapor pressure (Tetens formula)
        e_sat = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))  # [kPa]
        e_a = RH * e_sat  # Actual vapor pressure [kPa]
        
        # Atmospheric emissivity (Prata 1996)
        w = 46.5 * e_a / Ta_K  # Precipitable water [mm]
        epsilon_atm = 1.0 - (1.0 + w) * np.exp(-np.sqrt(1.2 + 3.0 * w))
        
        L_sky = epsilon_atm * self._sigma * Ta_K**4
        
        return L_sky
    
    def calculate_sensible_heat(self, Tg: float, Ta: float) -> float:
        """
        Calculate sensible heat flux from ground to air.
        
        Args:
            Tg: Ground temperature [C]
            Ta: Air temperature [C]
            
        Returns:
            H_g: Sensible heat flux [W/m2] (positive = upward)
        """
        H_g = self._rho_air * self._cp_air * (Tg - Ta) / self._r_a_ground
        return H_g
    
    def calculate_latent_heat(
        self,
        Tg: float,
        Ta: float,
        RH: float,
        evap_factor: float,
        theta: Optional[float] = None,
        theta_fc: Optional[float] = None
    ) -> float:
        """
        Calculate latent heat flux (evaporative cooling).
        
        For impervious surfaces, LE_g = 0.
        For pervious/vegetated, LE_g scales with evap_factor and soil moisture.
        
        Args:
            Tg: Ground temperature [C]
            Ta: Air temperature [C]
            RH: Relative humidity [fraction]
            evap_factor: Surface evaporation factor (0-1)
            theta: Soil moisture [m3/m3] (optional, for moisture limitation)
            theta_fc: Field capacity [m3/m3] (optional)
            
        Returns:
            LE_g: Latent heat flux [W/m2] (positive = upward)
        """
        if evap_factor <= 0:
            return 0.0
        
        # Potential evaporation based on vapor pressure deficit
        Tg_K = Tg + 273.15
        Ta_K = Ta + 273.15
        
        # Saturation vapor pressure at surface and air
        e_sat_g = 0.6108 * np.exp(17.27 * Tg / (Tg + 237.3))  # [kPa]
        e_sat_a = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))
        e_a = RH * e_sat_a
        
        # Vapor pressure deficit [kPa]
        VPD = max(0, e_sat_g - e_a)
        
        # Reference potential evaporation [mm/day -> kg/m2/s]
        ET_pot = self._ET_pot_ref / 86400.0 * 1000.0  # mm/day -> kg/m2/day -> g/m2/s
        
        # Scale by VPD relative to typical daytime VPD (~1 kPa)
        vpd_scale = min(2.0, VPD / 1.0)
        
        # Moisture limitation (if soil moisture provided)
        moisture_factor = 1.0
        if theta is not None and theta_fc is not None and theta_fc > 0:
            moisture_factor = min(1.0, theta / theta_fc)
        
        # Latent heat flux [W/m2]
        LE_g = evap_factor * moisture_factor * vpd_scale * ET_pot * self._lambda_v / 1000.0
        
        return LE_g
    
    def step(
        self,
        Tg_prev: float,
        K_down: float,
        Ta: float,
        RH: float,
        albedo: float,
        emissivity: float,
        heat_capacity: float,
        evap_factor: float,
        dt: float = 3600.0,
        theta: Optional[float] = None,
        theta_fc: Optional[float] = None
    ) -> GroundState:
        """
        Advance ground temperature by one timestep.
        
        Solves: C_g * dTg/dt = R_net - H_g - LE_g
        Using explicit Euler: Tg(t+1) = Tg(t) + dt * (R_net - H_g - LE_g) / C_g
        
        Args:
            Tg_prev: Previous ground temperature [C]
            K_down: Downwelling shortwave [W/m2]
            Ta: Air temperature [C]
            RH: Relative humidity [fraction]
            albedo: Ground albedo
            emissivity: Ground emissivity
            heat_capacity: Ground heat capacity [J/m2/K]
            evap_factor: Evaporation factor (0-1)
            dt: Timestep [s] (default 3600 = 1 hour)
            theta: Soil moisture [m3/m3] (optional)
            theta_fc: Field capacity [m3/m3] (optional)
            
        Returns:
            GroundState with new temperature and fluxes
        """
        Tg_K = Tg_prev + 273.15
        
        # Incoming radiation
        K_abs = (1.0 - albedo) * K_down  # Absorbed shortwave
        L_sky = self.calculate_longwave_sky(Ta, RH)  # Downwelling longwave
        L_up = emissivity * self._sigma * Tg_K**4  # Outgoing longwave
        
        # Net radiation
        R_net = K_abs + L_sky - L_up
        
        # Turbulent fluxes
        H_g = self.calculate_sensible_heat(Tg_prev, Ta)
        LE_g = self.calculate_latent_heat(Tg_prev, Ta, RH, evap_factor, theta, theta_fc)
        
        # Ground heat flux (storage term)
        G = R_net - H_g - LE_g
        
        # Update temperature (explicit Euler)
        dTg = G * dt / heat_capacity
        Tg_new = Tg_prev + dTg
        
        # Clamp to reasonable range
        Tg_new = max(-40.0, min(80.0, Tg_new))
        
        return GroundState(
            Tg=Tg_new,
            R_net=R_net,
            H_g=H_g,
            LE_g=LE_g,
            G=G
        )
    
    def equilibrium_temperature(
        self,
        K_down: float,
        Ta: float,
        RH: float,
        albedo: float,
        emissivity: float,
        evap_factor: float,
        theta: Optional[float] = None,
        theta_fc: Optional[float] = None,
        max_iter: int = 50,
        tol: float = 0.1
    ) -> float:
        """
        Calculate equilibrium ground temperature (steady-state).
        
        Iteratively solves for Tg where R_net = H_g + LE_g.
        
        Args:
            K_down: Downwelling shortwave [W/m2]
            Ta: Air temperature [C]
            RH: Relative humidity [fraction]
            albedo: Ground albedo
            emissivity: Ground emissivity
            evap_factor: Evaporation factor
            theta: Soil moisture [m3/m3]
            theta_fc: Field capacity [m3/m3]
            max_iter: Maximum iterations
            tol: Convergence tolerance [C]
            
        Returns:
            Equilibrium ground temperature [C]
        """
        # Initial guess
        Tg = Ta + 5.0  # Start slightly warmer than air
        
        L_sky = self.calculate_longwave_sky(Ta, RH)
        K_abs = (1.0 - albedo) * K_down
        
        for _ in range(max_iter):
            Tg_K = Tg + 273.15
            
            # Radiative balance
            L_up = emissivity * self._sigma * Tg_K**4
            R_net = K_abs + L_sky - L_up
            
            # Turbulent fluxes
            H_g = self.calculate_sensible_heat(Tg, Ta)
            LE_g = self.calculate_latent_heat(Tg, Ta, RH, evap_factor, theta, theta_fc)
            
            # Imbalance
            imbalance = R_net - H_g - LE_g
            
            # Update using linearization
            # dR_net/dTg ≈ -4*ε*σ*Tg^3
            # dH_g/dTg = ρ*cp/r_a
            dR_dT = -4.0 * emissivity * self._sigma * Tg_K**3
            dH_dT = self._rho_air * self._cp_air / self._r_a_ground
            
            # Newton step
            dTg = imbalance / (dH_dT - dR_dT)
            Tg_new = Tg + dTg
            
            if abs(dTg) < tol:
                return Tg_new
            
            Tg = Tg_new
        
        return Tg


def get_ground_type_from_material(
    material_name: str,
    material_db_row: Optional[dict] = None
) -> str:
    """
    Determine ground type from material name or database row.
    
    Args:
        material_name: Material name
        material_db_row: Optional row from material database with ground_type column
        
    Returns:
        Ground type: 'impervious', 'pervious', or 'vegetated'
    """
    # Check database row first
    if material_db_row is not None and 'ground_type' in material_db_row:
        gt = material_db_row.get('ground_type', '')
        if gt in ['impervious', 'pervious', 'vegetated']:
            return gt
    
    # Fallback: infer from material name
    name_lower = material_name.lower()
    
    if any(v in name_lower for v in ['grass', 'vegetation', 'soil', 'turf', 'living']):
        return 'vegetated'
    elif any(p in name_lower for p in ['paver', 'aggregate', 'gravel', 'permeable', 'limestone']):
        return 'pervious'
    else:
        return 'impervious'
