"""
Li et al. (2023) Canopy Energy Balance (CEB) Model

Implements the steady-state canopy energy balance model from:
Li et al., Sustainable Cities and Society (2023) 99:104994
"Analyzing the impact of various factors on leaf surface temperature 
based on a new tree-scale canopy energy balance model"

This module solves for leaf temperature (Tf) from Eq. 16:
    alpha_sf*(R_sw_dir + R_sw_diff) 
    + alpha_lf*(R_lw_down + R_lw_up + R_lw_env)
    - 2*epsilon_lf*sigma*Tf^4
    - rho_a*cp*(Tf - Ta)/rb_h
    - 0.622*lambda*rho_a*[D + s*(Tf - Ta)] / [P*(rb_w + r_sto)]
    = 0

Uses a single effective leaf layer simplification for efficiency.

Configuration:
    All parameters are loaded from config.yaml via config_locator.
    No hardcoded defaults are allowed.
"""

import numpy as np
from scipy.optimize import brentq
from typing import Tuple, Optional
from dataclasses import dataclass

from config_locator import get_config


@dataclass
class CEBInputs:
    """Container for all CEB model inputs."""
    # Meteorology
    Ta: float           # Air temperature [C]
    RH: float           # Relative humidity [fraction, 0-1]
    U: float            # Wind speed [m/s]
    P: float            # Atmospheric pressure [kPa]
    
    # Irradiance (from Radiance)
    E_dir: float        # Direct irradiance at sensor [W/m2]
    E_dif: float        # Diffuse irradiance at sensor [W/m2]
    
    # Geometry
    SVF: float          # Sky view factor [0-1]
    
    # Material properties (scenario-dependent)
    albedo_g: float     # Ground albedo [0-1]
    epsilon_g: float    # Ground emissivity [0-1]
    
    # Species parameters
    alpha_sf: float     # Shortwave absorptivity (1 - leaf_albedo)
    alpha_lf: float     # Longwave absorptivity
    epsilon_lf: float   # Leaf emissivity
    r_sto: float        # Stomatal resistance [s/m] (can be dynamic from soil moisture)
    leaf_size: float    # Characteristic leaf dimension [m]
    
    # Optional: Ground temperature from ground energy balance model
    # If None, uses Ta + delta_Tg proxy (default behavior)
    Tg: Optional[float] = None


@dataclass
class CEBOutputs:
    """Container for CEB model outputs."""
    Tf: float           # Leaf temperature [C]
    H: float            # Sensible heat flux [W/m2]
    LE: float           # Latent heat flux [W/m2]
    Q_sw: float         # Absorbed shortwave [W/m2]
    Q_lw_in: float      # Absorbed longwave [W/m2]
    Q_lw_out: float     # Emitted longwave [W/m2]
    R_sw_dir: float     # Direct SW at leaf [W/m2]
    R_sw_dif: float     # Diffuse SW at leaf [W/m2]
    R_lw_down: float    # Downwelling LW at leaf [W/m2]
    R_lw_up: float      # Upwelling LW at leaf [W/m2]
    R_lw_env: float     # Environmental LW at leaf [W/m2]
    rb_h: float         # Boundary layer resistance for heat [s/m]
    rb_w: float         # Boundary layer resistance for vapor [s/m]
    D: float            # Vapor pressure deficit [kPa]
    converged: bool     # Whether solver converged
    Tg: float = 0.0     # Ground temperature used [C] (for diagnostics)


class Li2023CEBModel:
    """
    Li et al. (2023) Canopy Energy Balance Model.
    
    Solves for leaf temperature using a single effective leaf layer
    approximation of the full vertical canopy model.
    
    All parameters are loaded from config.yaml - no hardcoded defaults.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize CEB model with configuration from config.yaml.
        
        Args:
            config_path: Optional path to config.yaml (uses default search if None)
        """
        # Load configuration
        self._config = get_config(config_path)
        
        # Cache physical constants
        self._sigma = self._config.physical_constants.sigma
        self._rho_air = self._config.physical_constants.rho_air
        self._cp_air = self._config.physical_constants.cp_air
        self._lambda_v = self._config.physical_constants.lambda_v
        
        # Cache CEB model parameters
        self._ceb = self._config.model.ceb
        self._species_defaults = self._config.model.species_defaults
    
    # =========================================================================
    # Shortwave Radiation (Eq. 5-7, simplified)
    # =========================================================================
    
    def calculate_shortwave_at_leaf(
        self,
        E_dir: float,
        E_dif: float,
        albedo_g: float
    ) -> Tuple[float, float]:
        """
        Calculate shortwave radiation reaching the leaf.
        
        For single effective leaf, uses coupling factors to convert
        ground-level sensor irradiance to leaf-level irradiance.
        
        Eq. 6 simplified: R_sw_dir includes direct beam + ground reflection
        Eq. 7 simplified: R_sw_dif is diffuse reaching leaf
        
        Args:
            E_dir: Direct irradiance at sensor [W/m2]
            E_dif: Diffuse irradiance at sensor [W/m2]
            albedo_g: Ground albedo [0-1]
            
        Returns:
            Tuple of (R_sw_dir, R_sw_dif) [W/m2]
        """
        beta_dir = self._ceb.beta_dir
        beta_dif = self._ceb.beta_dif
        
        # Direct component: beam reaching leaf + ground reflection
        R_sw_dir = beta_dir * E_dir + albedo_g * E_dir * beta_dir
        
        # Diffuse component reaching leaf
        R_sw_dif = beta_dif * E_dif
        
        return R_sw_dir, R_sw_dif
    
    def calculate_absorbed_shortwave(
        self,
        R_sw_dir: float,
        R_sw_dif: float,
        alpha_sf: float
    ) -> float:
        """
        Calculate absorbed shortwave radiation (Eq. 5).
        
        Q_sw = alpha_sf * (R_sw_dir + R_sw_dif)
        
        Args:
            R_sw_dir: Direct SW at leaf [W/m2]
            R_sw_dif: Diffuse SW at leaf [W/m2]
            alpha_sf: Shortwave absorptivity
            
        Returns:
            Absorbed shortwave [W/m2]
        """
        return alpha_sf * (R_sw_dir + R_sw_dif)
    
    # =========================================================================
    # Longwave Radiation (Eq. 8-12)
    # =========================================================================
    
    def calculate_sky_longwave(self, Ta_K: float) -> float:
        """
        Calculate sky longwave radiation using Swinbank (1963) formula (Eq. 12).
        
        R_lw_sky = -170.9 + 1.195 * sigma * Ta^4
        
        Args:
            Ta_K: Air temperature [K]
            
        Returns:
            Sky longwave radiation [W/m2]
        """
        return -170.9 + 1.195 * self._sigma * Ta_K**4
    
    def calculate_longwave_components(
        self,
        Ta: float,
        SVF: float,
        epsilon_g: float,
        Tg: Optional[float] = None
    ) -> Tuple[float, float, float, float]:
        """
        Calculate longwave radiation components (Eq. 9-11, simplified).
        
        For single effective leaf layer:
        - R_lw_down: sky contribution weighted by SVF (Eq. 9 simplified)
        - R_lw_up: ground emission (Eq. 10 simplified)
        - R_lw_env: surrounding surfaces contribution (Eq. 11 simplified)
        
        Args:
            Ta: Air temperature [C]
            SVF: Sky view factor [0-1]
            epsilon_g: Ground emissivity [0-1]
            Tg: Ground temperature [C] (optional, uses Ta + delta_Tg if None)
            
        Returns:
            Tuple of (R_lw_down, R_lw_up, R_lw_env, Tg_used) [W/m2, W/m2, W/m2, C]
        """
        Ta_K = Ta + 273.15
        delta_Tw = self._ceb.delta_Tw
        epsilon_w = self._ceb.epsilon_w
        
        # Ground temperature: use provided Tg or fall back to proxy
        if Tg is not None:
            Tg_used = Tg
            Tg_K = Tg + 273.15
        else:
            delta_Tg = self._ceb.delta_Tg
            Tg_used = Ta + delta_Tg
            Tg_K = Ta_K + delta_Tg
        
        # Wall temperature (still uses proxy)
        Tw_K = Ta_K + delta_Tw
        
        # Sky longwave (Eq. 12)
        R_lw_sky = self.calculate_sky_longwave(Ta_K)
        
        # Downwelling LW from sky (Eq. 9 simplified for single layer)
        R_lw_down = SVF * R_lw_sky
        
        # Upwelling LW from ground (Eq. 10 simplified)
        R_lw_up = epsilon_g * self._sigma * Tg_K**4
        
        # Environmental LW from surrounding surfaces (Eq. 11 simplified)
        R_lw_env = (1.0 - SVF) * epsilon_w * self._sigma * Tw_K**4
        
        return R_lw_down, R_lw_up, R_lw_env, Tg_used
    
    def calculate_absorbed_longwave(
        self,
        R_lw_down: float,
        R_lw_up: float,
        R_lw_env: float,
        alpha_lf: float
    ) -> float:
        """
        Calculate absorbed longwave radiation (Eq. 8, incoming part).
        
        Q_lw_in = alpha_lf * (R_lw_down + R_lw_up + R_lw_env)
        
        Args:
            R_lw_down: Downwelling LW [W/m2]
            R_lw_up: Upwelling LW [W/m2]
            R_lw_env: Environmental LW [W/m2]
            alpha_lf: Longwave absorptivity
            
        Returns:
            Absorbed longwave [W/m2]
        """
        return alpha_lf * (R_lw_down + R_lw_up + R_lw_env)
    
    def calculate_emitted_longwave(self, Tf_K: float, epsilon_lf: float) -> float:
        """
        Calculate emitted longwave from leaf (Eq. 8, outgoing part).
        
        Q_lw_out = 2 * epsilon_lf * sigma * Tf^4
        
        Factor of 2 accounts for emission from both leaf surfaces.
        
        Args:
            Tf_K: Leaf temperature [K]
            epsilon_lf: Leaf emissivity
            
        Returns:
            Emitted longwave [W/m2]
        """
        return 2.0 * epsilon_lf * self._sigma * Tf_K**4
    
    # =========================================================================
    # Resistances (Eq. 2)
    # =========================================================================
    
    def calculate_boundary_resistances(
        self,
        U: float,
        leaf_size: float
    ) -> Tuple[float, float]:
        """
        Calculate boundary layer resistances (Eq. 2).
        
        rb_h = A * (u/d)^(-0.5)
        rb_w = rb_h / 1.08
        
        Args:
            U: Wind speed [m/s]
            leaf_size: Characteristic leaf dimension [m]
            
        Returns:
            Tuple of (rb_h, rb_w) [s/m]
        """
        A = self._ceb.A_coeff
        
        # Ensure minimum wind speed to avoid division by zero
        U_eff = max(U, 0.1)
        
        # Heat transfer resistance (Eq. 2)
        rb_h = A * (leaf_size / U_eff)**0.5
        
        # Vapor transfer resistance
        rb_w = rb_h / 1.08
        
        return rb_h, rb_w
    
    # =========================================================================
    # Vapor Terms (Eq. 15, 19)
    # =========================================================================
    
    def calculate_saturation_vapor_pressure(self, T: float) -> float:
        """
        Calculate saturation vapor pressure using Tetens equation.
        
        es(T) = 0.6108 * exp(17.27*T / (T+237.3))
        
        Args:
            T: Temperature [C]
            
        Returns:
            Saturation vapor pressure [kPa]
        """
        return 0.6108 * np.exp(17.27 * T / (T + 237.3))
    
    def calculate_vapor_pressure_slope(self, T: float) -> float:
        """
        Calculate slope of saturation vapor pressure curve (d(es)/dT).
        
        s = 4098 * es(T) / (T + 237.3)^2
        
        Args:
            T: Temperature [C]
            
        Returns:
            Slope [kPa/C]
        """
        es = self.calculate_saturation_vapor_pressure(T)
        return 4098.0 * es / (T + 237.3)**2
    
    def calculate_vpd(self, Ta: float, RH: float) -> float:
        """
        Calculate vapor pressure deficit (Eq. 15).
        
        D = es(Ta) * (1 - RH)
        
        Args:
            Ta: Air temperature [C]
            RH: Relative humidity [fraction, 0-1]
            
        Returns:
            VPD [kPa]
        """
        es_Ta = self.calculate_saturation_vapor_pressure(Ta)
        return es_Ta * (1.0 - RH)
    
    # =========================================================================
    # Sensible Heat (Eq. 13)
    # =========================================================================
    
    def calculate_sensible_heat(
        self,
        Tf: float,
        Ta: float,
        rb_h: float
    ) -> float:
        """
        Calculate sensible heat flux (Eq. 13).
        
        H = rho_a * cp * (Tf - Ta) / rb_h
        
        Args:
            Tf: Leaf temperature [C]
            Ta: Air temperature [C]
            rb_h: Boundary layer resistance for heat [s/m]
            
        Returns:
            Sensible heat flux [W/m2]
        """
        return self._rho_air * self._cp_air * (Tf - Ta) / rb_h
    
    # =========================================================================
    # Latent Heat (Eq. 14)
    # =========================================================================
    
    def calculate_latent_heat(
        self,
        Tf: float,
        Ta: float,
        D: float,
        s: float,
        P: float,
        rb_w: float,
        r_sto: float
    ) -> float:
        """
        Calculate latent heat flux (Eq. 14).
        
        LE = 0.622 * lambda * rho_a * [D + s*(Tf - Ta)] / [P * (rb_w + r_sto)]
        
        Args:
            Tf: Leaf temperature [C]
            Ta: Air temperature [C]
            D: Vapor pressure deficit [kPa]
            s: Slope of saturation vapor pressure curve [kPa/C]
            P: Atmospheric pressure [kPa]
            rb_w: Boundary layer resistance for vapor [s/m]
            r_sto: Stomatal resistance [s/m]
            
        Returns:
            Latent heat flux [W/m2]
        """
        # VPD driving term (includes temperature difference effect)
        vpd_leaf = D + s * (Tf - Ta)
        
        # Ensure non-negative VPD (prevents condensation calculation)
        vpd_leaf = max(0.0, vpd_leaf)
        
        # Latent heat flux
        LE = 0.622 * self._lambda_v * self._rho_air * vpd_leaf / (P * (rb_w + r_sto))
        
        return LE
    
    # =========================================================================
    # Energy Balance Residual (Eq. 16)
    # =========================================================================
    
    def energy_balance_residual(
        self,
        Tf: float,
        inputs: CEBInputs,
        R_sw_dir: float,
        R_sw_dif: float,
        R_lw_down: float,
        R_lw_up: float,
        R_lw_env: float,
        rb_h: float,
        rb_w: float,
        D: float,
        s: float
    ) -> float:
        """
        Calculate energy balance residual for root finding (Eq. 16).
        
        Residual = Q_sw + Q_lw_in - Q_lw_out - H - LE
        
        At solution, residual = 0.
        
        Args:
            Tf: Leaf temperature [C] (unknown to solve for)
            inputs: CEBInputs container
            R_sw_dir, R_sw_dif: Shortwave at leaf
            R_lw_down, R_lw_up, R_lw_env: Longwave components
            rb_h, rb_w: Boundary resistances
            D: VPD at air temperature
            s: Slope of es curve
            
        Returns:
            Energy balance residual [W/m2]
        """
        Tf_K = Tf + 273.15
        
        # Absorbed shortwave (Eq. 5)
        Q_sw = self.calculate_absorbed_shortwave(
            R_sw_dir, R_sw_dif, inputs.alpha_sf
        )
        
        # Absorbed longwave (Eq. 8, incoming)
        Q_lw_in = self.calculate_absorbed_longwave(
            R_lw_down, R_lw_up, R_lw_env, inputs.alpha_lf
        )
        
        # Emitted longwave (Eq. 8, outgoing)
        Q_lw_out = self.calculate_emitted_longwave(Tf_K, inputs.epsilon_lf)
        
        # Sensible heat (Eq. 13)
        H = self.calculate_sensible_heat(Tf, inputs.Ta, rb_h)
        
        # Latent heat (Eq. 14)
        LE = self.calculate_latent_heat(
            Tf, inputs.Ta, D, s, inputs.P, rb_w, inputs.r_sto
        )
        
        # Energy balance residual (Eq. 16 rearranged)
        residual = Q_sw + Q_lw_in - Q_lw_out - H - LE
        
        return residual
    
    # =========================================================================
    # Main Solver
    # =========================================================================
    
    def solve_leaf_temperature(self, inputs: CEBInputs) -> CEBOutputs:
        """
        Solve for leaf temperature using the CEB model (Eq. 16).
        
        Uses Brent's method for 1D root finding.
        
        Args:
            inputs: CEBInputs container with all required inputs
            
        Returns:
            CEBOutputs container with leaf temperature and all fluxes
        """
        # Pre-compute radiation terms (don't depend on Tf)
        R_sw_dir, R_sw_dif = self.calculate_shortwave_at_leaf(
            inputs.E_dir, inputs.E_dif, inputs.albedo_g
        )
        
        # Get Tg from inputs (may be None, in which case proxy is used)
        Tg_input = inputs.Tg if hasattr(inputs, 'Tg') else None
        
        R_lw_down, R_lw_up, R_lw_env, Tg_used = self.calculate_longwave_components(
            inputs.Ta, inputs.SVF, inputs.epsilon_g, Tg_input
        )
        
        # Pre-compute resistances
        rb_h, rb_w = self.calculate_boundary_resistances(
            inputs.U, inputs.leaf_size
        )
        
        # Pre-compute vapor terms at air temperature
        D = self.calculate_vpd(inputs.Ta, inputs.RH)
        s = self.calculate_vapor_pressure_slope(inputs.Ta)
        
        # Solver bounds from config
        T_min = inputs.Ta + self._ceb.T_min_offset
        T_max = inputs.Ta + self._ceb.T_max_offset
        
        # Solve energy balance
        converged = True
        try:
            Tf = brentq(
                self.energy_balance_residual,
                T_min,
                T_max,
                args=(inputs, R_sw_dir, R_sw_dif, R_lw_down, R_lw_up, R_lw_env,
                      rb_h, rb_w, D, s),
                xtol=self._ceb.solver_xtol,
                maxiter=self._ceb.solver_maxiter
            )
        except ValueError:
            # Root finding failed - use air temperature as fallback
            Tf = inputs.Ta
            converged = False
        
        # Calculate fluxes at solution
        Tf_K = Tf + 273.15
        
        Q_sw = self.calculate_absorbed_shortwave(
            R_sw_dir, R_sw_dif, inputs.alpha_sf
        )
        Q_lw_in = self.calculate_absorbed_longwave(
            R_lw_down, R_lw_up, R_lw_env, inputs.alpha_lf
        )
        Q_lw_out = self.calculate_emitted_longwave(Tf_K, inputs.epsilon_lf)
        H = self.calculate_sensible_heat(Tf, inputs.Ta, rb_h)
        LE = self.calculate_latent_heat(
            Tf, inputs.Ta, D, s, inputs.P, rb_w, inputs.r_sto
        )
        
        return CEBOutputs(
            Tf=Tf,
            H=H,
            LE=LE,
            Q_sw=Q_sw,
            Q_lw_in=Q_lw_in,
            Q_lw_out=Q_lw_out,
            R_sw_dir=R_sw_dir,
            R_sw_dif=R_sw_dif,
            R_lw_down=R_lw_down,
            R_lw_up=R_lw_up,
            R_lw_env=R_lw_env,
            rb_h=rb_h,
            rb_w=rb_w,
            D=D,
            converged=converged,
            Tg=Tg_used
        )
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    def solve(
        self,
        Ta: float,
        RH: float,
        U: float,
        P: float,
        E_dir: float,
        E_dif: float,
        SVF: float,
        albedo_g: float,
        epsilon_g: float,
        alpha_sf: Optional[float] = None,
        alpha_lf: Optional[float] = None,
        epsilon_lf: Optional[float] = None,
        r_sto: Optional[float] = None,
        leaf_size: Optional[float] = None
    ) -> CEBOutputs:
        """
        Convenience method to solve CEB with individual arguments.
        
        Uses species defaults from config for optional parameters.
        
        Args:
            Ta: Air temperature [C]
            RH: Relative humidity [fraction or %, auto-detected]
            U: Wind speed [m/s]
            P: Atmospheric pressure [kPa]
            E_dir: Direct irradiance [W/m2]
            E_dif: Diffuse irradiance [W/m2]
            SVF: Sky view factor [0-1]
            albedo_g: Ground albedo [0-1]
            epsilon_g: Ground emissivity [0-1]
            alpha_sf: Shortwave absorptivity (uses config default if None)
            alpha_lf: Longwave absorptivity (uses config default if None)
            epsilon_lf: Leaf emissivity (uses config default if None)
            r_sto: Stomatal resistance [s/m] (uses config default if None)
            leaf_size: Characteristic leaf size [m] (uses config default if None)
            
        Returns:
            CEBOutputs container
        """
        # Auto-detect RH format (fraction vs percentage)
        if RH > 1.0:
            RH = RH / 100.0
        
        # Use species defaults from config for optional parameters
        if alpha_sf is None:
            # Shortwave absorptivity = 1 - albedo
            alpha_sf = 1.0 - self._species_defaults.alpha_leaf
        if alpha_lf is None:
            alpha_lf = self._species_defaults.epsilon_leaf
        if epsilon_lf is None:
            epsilon_lf = self._species_defaults.epsilon_leaf
        if r_sto is None:
            r_sto = self._species_defaults.r_sto
        if leaf_size is None:
            leaf_size = self._species_defaults.leaf_char_size
        
        inputs = CEBInputs(
            Ta=Ta,
            RH=RH,
            U=U,
            P=P,
            E_dir=E_dir,
            E_dif=E_dif,
            SVF=SVF,
            albedo_g=albedo_g,
            epsilon_g=epsilon_g,
            alpha_sf=alpha_sf,
            alpha_lf=alpha_lf,
            epsilon_lf=epsilon_lf,
            r_sto=r_sto,
            leaf_size=leaf_size
        )
        
        return self.solve_leaf_temperature(inputs)


# =============================================================================
# Standalone Function Interface
# =============================================================================

def solve_leaf_temperature_ceb(
    Ta: float,
    RH: float,
    U: float,
    P: float,
    E_dir: float,
    E_dif: float,
    SVF: float,
    albedo_g: float,
    epsilon_g: float,
    alpha_sf: Optional[float] = None,
    alpha_lf: Optional[float] = None,
    epsilon_lf: Optional[float] = None,
    r_sto: Optional[float] = None,
    leaf_size: Optional[float] = None,
    config_path: Optional[str] = None
) -> Tuple[float, float, float, float, bool]:
    """
    Standalone function to solve for leaf temperature using Li2023 CEB model.
    
    This provides a simple interface similar to the original solve_leaf_temperature().
    All defaults come from config.yaml.
    
    Args:
        Ta: Air temperature [C]
        RH: Relative humidity [fraction, 0-1]
        U: Wind speed [m/s]
        P: Atmospheric pressure [kPa]
        E_dir: Direct irradiance [W/m2]
        E_dif: Diffuse irradiance [W/m2]
        SVF: Sky view factor [0-1]
        albedo_g: Ground albedo [0-1]
        epsilon_g: Ground emissivity [0-1]
        alpha_sf: Shortwave absorptivity (uses config default if None)
        alpha_lf: Longwave absorptivity (uses config default if None)
        epsilon_lf: Leaf emissivity (uses config default if None)
        r_sto: Stomatal resistance [s/m] (uses config default if None)
        leaf_size: Characteristic leaf size [m] (uses config default if None)
        config_path: Optional path to config.yaml
        
    Returns:
        Tuple of (Tf, H, LE, gc, converged)
        - Tf: Leaf temperature [C]
        - H: Sensible heat [W/m2]
        - LE: Latent heat [W/m2]
        - gc: Stomatal conductance [mol/m2/s] (inverted from r_sto)
        - converged: Whether solver converged
    """
    model = Li2023CEBModel(config_path)
    
    outputs = model.solve(
        Ta=Ta,
        RH=RH,
        U=U,
        P=P,
        E_dir=E_dir,
        E_dif=E_dif,
        SVF=SVF,
        albedo_g=albedo_g,
        epsilon_g=epsilon_g,
        alpha_sf=alpha_sf,
        alpha_lf=alpha_lf,
        epsilon_lf=epsilon_lf,
        r_sto=r_sto,
        leaf_size=leaf_size
    )
    
    # Get r_sto from config if not provided
    if r_sto is None:
        config = get_config(config_path)
        r_sto = config.model.species_defaults.r_sto
    
    # Convert stomatal resistance to conductance
    # gc [mol/m2/s] ≈ 1 / (r_sto * 0.025) for typical conditions
    # Using P and T to compute molar volume: Vm = R*T/P
    T_K = Ta + 273.15
    Vm = 8.314 * T_K / (P * 1000)  # Molar volume [m3/mol]
    gc = 1.0 / (r_sto * Vm) if r_sto > 0 else 0.0
    
    return outputs.Tf, outputs.H, outputs.LE, gc, outputs.converged
