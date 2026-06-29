"""
Tree Species Parameter Management

Manages species-specific physiological parameters for tree stress modeling.
All default values are loaded from config.yaml via config_locator.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Optional

from config_locator import get_config


class TreeSpecies:
    """Represents a tree species with physiological parameters."""
    
    def __init__(self, species_name: str, params_dict: Dict, config_path: Optional[str] = None):
        """
        Initialize tree species with parameters.
        
        Args:
            species_name: Name of species
            params_dict: Dictionary with species parameters (all MUST be provided)
            config_path: Optional path to config.yaml (for testing)
        """
        self.species_name = species_name
        
        # Load config for defaults
        config = get_config(config_path)
        defaults = config.model.species_defaults
        
        # Set parameters - use config defaults for any missing values
        self.alpha_leaf = params_dict.get('alpha_leaf', defaults.alpha_leaf)
        self.epsilon_leaf = params_dict.get('epsilon_leaf', defaults.epsilon_leaf)
        self.gc_max = params_dict.get('gc_max', defaults.gc_max)  # mol/m2/s
        self.vpd_sensitivity = params_dict.get('vpd_sensitivity', defaults.vpd_sensitivity)  # kPa
        self.T_opt = params_dict.get('T_opt', defaults.T_opt)  # C
        self.T_crit = params_dict.get('T_crit', defaults.T_crit)  # C
        self.beta_above = params_dict.get('beta_above', defaults.beta_above)
        self.beta_below = params_dict.get('beta_below', defaults.beta_below)
        self.ra_scale = params_dict.get('ra_scale', defaults.ra_scale)
        self.shelter_factor = params_dict.get('shelter_factor', defaults.shelter_factor)
        self.SVF = params_dict.get('SVF', defaults.SVF)
        
        # Li2023 CEB model parameters
        self.r_sto = params_dict.get('r_sto', defaults.r_sto)  # Stomatal resistance [s/m]
        self.leaf_char_size = params_dict.get('leaf_char_size', defaults.leaf_char_size)  # Leaf size [m]
        
        # Additional parameters
        self.light_extinction_coefficient = params_dict.get(
            'light_extinction_coefficient', defaults.light_extinction_coefficient
        )
    
    def fRad(self, Kabs: float) -> float:
        """
        Radiation response function for stomatal conductance.
        
        Args:
            Kabs: Absorbed shortwave radiation [W/m2]
            
        Returns:
            Radiation response factor (0.0-1.0)
        """
        # Simple linear response with saturation
        K_sat = 800.0  # Saturation irradiance [W/m2]
        return min(1.0, max(0.0, Kabs / K_sat))
    
    def fVPD(self, VPD: float) -> float:
        """
        VPD response function for stomatal conductance.
        
        Args:
            VPD: Vapor pressure deficit [kPa]
            
        Returns:
            VPD response factor (0.0-1.0)
        """
        # Exponential decline with VPD
        if VPD <= 0:
            return 1.0
        
        # Stomatal closure increases with VPD
        # fVPD = exp(-VPD / vpd_sensitivity)
        fvpd = np.exp(-VPD / self.vpd_sensitivity)
        return max(0.0, min(1.0, fvpd))
    
    def fSM(self, theta: float, theta_crit: Optional[float] = None, 
            theta_wilt: Optional[float] = None) -> float:
        """
        Soil moisture response function for stomatal conductance.
        
        Args:
            theta: Volumetric water content [m3/m3]
            theta_crit: Critical soil moisture (stress begins) [m3/m3]
            theta_wilt: Wilting point [m3/m3]
            
        Returns:
            Soil moisture response factor (0.0-1.0)
        """
        # Get thresholds from config if not provided
        if theta_crit is None or theta_wilt is None:
            config = get_config()
            if theta_crit is None:
                theta_crit = config.model.risk.theta_crit
            if theta_wilt is None:
                theta_wilt = config.model.risk.theta_wilt
        
        if theta >= theta_crit:
            return 1.0
        elif theta <= theta_wilt:
            return 0.0
        else:
            # Linear decline between critical and wilting point
            return (theta - theta_wilt) / (theta_crit - theta_wilt)
    
    def fT(self, T_leaf: float) -> float:
        """
        Temperature response function for stomatal conductance.
        
        Args:
            T_leaf: Leaf temperature [C]
            
        Returns:
            Temperature response factor (0.0-1.0)
        """
        # Optimal temperature response (bell curve)
        T_min = self.T_opt - 15.0  # Minimum temperature
        T_max = self.T_opt + 15.0  # Maximum temperature
        
        if T_leaf < T_min or T_leaf > T_max:
            return 0.0
        elif T_leaf == self.T_opt:
            return 1.0
        else:
            # Parabolic response around optimum
            if T_leaf < self.T_opt:
                return (T_leaf - T_min) / (self.T_opt - T_min)
            else:
                return (T_max - T_leaf) / (T_max - self.T_opt)


class TreeSpeciesDatabase:
    """Manages database of tree species parameters."""
    
    def __init__(self, csv_path: Optional[str] = None, config_path: Optional[str] = None):
        """
        Initialize species database.
        
        Args:
            csv_path: Path to tree_species_database.csv
            config_path: Optional path to config.yaml
        """
        self.species_dict = {}
        self._config_path = config_path
        self._config = get_config(config_path)
        
        if csv_path and os.path.exists(csv_path):
            self.load_from_csv(csv_path)
    
    def load_from_csv(self, csv_path: str):
        """
        Load species parameters from CSV file.
        
        Expected CSV columns:
        - species: Species name
        - leaf_shortwave_albedo: Leaf albedo
        - leaf_emissivity: Leaf emissivity
        - max_stomatal_conductance: Maximum stomatal conductance [mol/m2/s]
        - vpd_sensitivity: VPD sensitivity [kPa]
        - optimal_leaf_temperature: Optimal temperature [C]
        - critical_leaf_temperature: Critical temperature [C]
        - light_extinction_coefficient: Light extinction coefficient
        - r_sto_min: Stomatal resistance [s/m] (for Li2023 CEB model)
        - leaf_char_size: Characteristic leaf dimension [m] (for Li2023 CEB model)
        """
        defaults = self._config.model.species_defaults
        
        try:
            df = pd.read_csv(csv_path)
            
            for _, row in df.iterrows():
                species_name = row.get('species', 'default')
                
                # Also support lookup by common_name
                common_name = row.get('common_name', species_name)
                
                # Handle column name variations
                gc_max = row.get('max_stomatal_conductance') or row.get('max_stomatal_conductance_mol_m2_s')
                vpd_sens = row.get('vpd_sensitivity') or row.get('vpd_sensitivity_g1_kpa_sqrt')
                T_opt = row.get('optimal_leaf_temperature') or row.get('optimal_leaf_temperature_c')
                T_crit = row.get('critical_leaf_temperature') or row.get('critical_leaf_temperature_c')
                
                # Li2023 CEB model parameters
                r_sto = row.get('r_sto_min')
                leaf_char_size = row.get('leaf_char_size')
                
                params = {
                    'alpha_leaf': row.get('leaf_shortwave_albedo', defaults.alpha_leaf),
                    'epsilon_leaf': row.get('leaf_emissivity', defaults.epsilon_leaf),
                    'gc_max': float(gc_max) if pd.notna(gc_max) else defaults.gc_max,
                    'vpd_sensitivity': float(vpd_sens) if pd.notna(vpd_sens) else defaults.vpd_sensitivity,
                    'T_opt': float(T_opt) if pd.notna(T_opt) else defaults.T_opt,
                    'T_crit': float(T_crit) if pd.notna(T_crit) else defaults.T_crit,
                    'light_extinction_coefficient': row.get(
                        'light_extinction_coefficient', defaults.light_extinction_coefficient
                    ),
                    # Li2023 CEB model parameters
                    'r_sto': float(r_sto) if pd.notna(r_sto) else defaults.r_sto,
                    'leaf_char_size': float(leaf_char_size) if pd.notna(leaf_char_size) else defaults.leaf_char_size,
                    # Use config defaults for parameters not in CSV
                    'beta_above': defaults.beta_above,
                    'beta_below': defaults.beta_below,
                    'ra_scale': defaults.ra_scale,
                    'shelter_factor': defaults.shelter_factor,
                    'SVF': defaults.SVF
                }
                
                species = TreeSpecies(species_name, params, self._config_path)
                self.species_dict[species_name] = species
                # Also add by common name for easier lookup
                if common_name and common_name != species_name:
                    self.species_dict[common_name] = species
        except Exception as e:
            print(f"Warning: Could not load species database from {csv_path}: {e}")
            print("Using config default species parameters.")
    
    def get_species(self, species_name: str) -> TreeSpecies:
        """
        Get species parameters.
        
        Args:
            species_name: Name of species
            
        Returns:
            TreeSpecies object, or default from config if not found
        """
        if species_name in self.species_dict:
            return self.species_dict[species_name]
        else:
            # Return default species with config values
            defaults = self._config.model.species_defaults
            default_params = {
                'alpha_leaf': defaults.alpha_leaf,
                'epsilon_leaf': defaults.epsilon_leaf,
                'gc_max': defaults.gc_max,
                'vpd_sensitivity': defaults.vpd_sensitivity,
                'T_opt': defaults.T_opt,
                'T_crit': defaults.T_crit,
                'beta_above': defaults.beta_above,
                'beta_below': defaults.beta_below,
                'ra_scale': defaults.ra_scale,
                'shelter_factor': defaults.shelter_factor,
                'SVF': defaults.SVF,
                # Li2023 CEB model parameters
                'r_sto': defaults.r_sto,
                'leaf_char_size': defaults.leaf_char_size,
                'light_extinction_coefficient': defaults.light_extinction_coefficient
            }
            return TreeSpecies('default', default_params, self._config_path)
    
    def add_species(self, species: TreeSpecies):
        """Add a species to the database."""
        self.species_dict[species.species_name] = species
