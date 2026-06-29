"""
Biophysical Tree Stress Calculator

Main calculator integrating all modules for tree stress modeling.
All default parameters are loaded from config.yaml via config_locator.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict
from scipy.spatial.distance import cdist

# Import config
from config_locator import get_config, get_path

# Import all modules
from weather_loader import load_epw, get_weather_at_hour
from tree_species import TreeSpeciesDatabase
from grid_material_mapping import load_grid_material_mapping, get_grid_materials_for_scenario
from upwelling_calculator import calculate_upwelling, extract_grid_id_from_column
from surface_energy_balance import calculate_surface_temperature, calculate_mrt, calculate_longwave_in
from leaf_energy_balance import solve_leaf_temperature, calculate_net_radiation
from soil_moisture import update_soil_moisture, calculate_drainage, et_from_le, SoilMoistureBucket
from risk_metrics import calculate_stress_summary

# Li2023 CEB Model for improved leaf temperature calculation
from li2023_ceb_model import Li2023CEBModel, CEBInputs

# Ground temperature model for physically-based Tg
from ground_temperature import GroundEnergyBalance, get_ground_type_from_material


class BiophysicalTreeStressCalculator:
    """Calculates tree stress using biophysical energy balance model."""
    
    def __init__(
        self,
        tree_points: pd.DataFrame,
        sensor_points: pd.DataFrame,
        species_db: TreeSpeciesDatabase,
        material_db,
        weather_data: pd.DataFrame,
        grid_material_mapping: pd.DataFrame,
        use_ceb_model: Optional[bool] = None,
        config_path: Optional[str] = None
    ):
        """
        Initialize calculator.
        
        Args:
            tree_points: DataFrame with columns ['xcoord', 'ycoord', 'zcoord', 'tree_id' or 'number', 'species']
            sensor_points: DataFrame with columns ['xcoord', 'ycoord', 'zcoord'] and index as sensor_id
            species_db: TreeSpeciesDatabase instance
            material_db: MaterialDatabase instance
            weather_data: DataFrame from load_epw()
            grid_material_mapping: DataFrame from load_grid_material_mapping()
            use_ceb_model: If True, use Li2023 CEB model; if False, use legacy model.
                          Uses config.model.ceb.enabled if None.
            config_path: Optional path to config.yaml
        """
        # Load config
        self._config = get_config(config_path)
        
        self.tree_points = tree_points
        self.sensor_points = sensor_points
        self.species_db = species_db
        self.material_db = material_db
        self.weather_data = weather_data
        self.grid_material_mapping = grid_material_mapping
        
        # Model selection from config if not explicitly provided
        if use_ceb_model is None:
            use_ceb_model = self._config.model.ceb.enabled
        
        self.use_ceb_model = use_ceb_model
        if use_ceb_model:
            self.ceb_model = Li2023CEBModel(config_path)
            print("   Using Li2023 CEB model for leaf temperature calculation")
        else:
            self.ceb_model = None
            print("   Using legacy leaf energy balance model")
        
        # Initialize ground temperature model
        self.ground_model = GroundEnergyBalance(config_path)
        print("   Initialized ground temperature model")
        
        # Initialize soil moisture bucket model
        self.soil_model = SoilMoistureBucket(config_path)
        print("   Initialized soil moisture bucket model")
        
        # Build spatial index for nearest neighbor lookup
        self._build_spatial_index()
        
        # Extract per-tree SVF values (with fallback to config default)
        self._extract_tree_svf()
        
        # Initialize soil moisture state (per tree)
        self.theta = {}  # Will be initialized in simulate_hourly
    
    def _get_default_svf(self) -> float:
        """Get default SVF from config."""
        return self._config.model.species_defaults.SVF
    
    def _get_default_albedo_emissivity(self) -> Tuple[float, float]:
        """Get default ground albedo and emissivity from config."""
        return (
            self._config.model.ceb.albedo_g_default,
            self._config.model.ceb.epsilon_g_default
        )
    
    def _get_soil_params(self) -> dict:
        """Get soil parameters from config."""
        soil = self._config.model.soil
        return {
            'theta_init': soil.theta_init,
            'theta_fc': soil.theta_fc,
            'theta_wilt': soil.theta_wilt,
            'theta_sat': soil.theta_sat,
            'Z_r': soil.Z_r,
            'k_drain_default': soil.k_drain_default,
            'REW_crit': soil.REW_crit,
            'r_sto_min': soil.r_sto_min
        }
    
    def _extract_tree_svf(self):
        """Extract per-tree SVF values from tree_points DataFrame."""
        self.tree_svf = {}
        n_trees = len(self.tree_points)
        default_svf = self._get_default_svf()
        
        # Check for SVF column (might be 'SVF', 'svf', or 'sky_view_factor')
        svf_col = None
        for col in ['SVF', 'svf', 'sky_view_factor']:
            if col in self.tree_points.columns:
                svf_col = col
                break
        
        if svf_col is not None:
            for tree_idx in range(n_trees):
                svf_val = self.tree_points.iloc[tree_idx][svf_col]
                # Handle missing values - fallback to config default
                # Note: SVF=0 is valid (completely obstructed view), only NaN is invalid
                if pd.isna(svf_val) or svf_val < 0:
                    self.tree_svf[tree_idx] = default_svf
                else:
                    # Clamp SVF to valid range [0, 1]
                    self.tree_svf[tree_idx] = float(min(max(svf_val, 0.0), 1.0))
            print(f"   Loaded per-tree SVF values: min={min(self.tree_svf.values()):.3f}, max={max(self.tree_svf.values()):.3f}, mean={np.mean(list(self.tree_svf.values())):.3f}")
        else:
            # No SVF column - use config default for all trees
            for tree_idx in range(n_trees):
                self.tree_svf[tree_idx] = default_svf
            print(f"   No SVF column in tree_points - using config default SVF={default_svf} for all trees")
    
    def _build_spatial_index(self):
        """Build spatial index for fast nearest neighbor lookup."""
        tree_coords = self.tree_points[['xcoord', 'ycoord', 'zcoord']].values
        sensor_coords = self.sensor_points[['xcoord', 'ycoord', 'zcoord']].values
        
        # Calculate distances
        distances = cdist(tree_coords, sensor_coords)
        self.nearest_sensor_indices = np.argmin(distances, axis=1)
        
        # Store grid IDs for each sensor (extract from sensor_points if available)
        # Map by position index (0, 1, 2...) not DataFrame index, since nearest_sensor_indices uses positions
        self.sensor_grid_ids = {}
        if 'grid_name' in self.sensor_points.columns:
            # Reset index to ensure we're using position-based indexing
            sensor_points_reset = self.sensor_points.reset_index(drop=True)
            for pos_idx in range(len(sensor_points_reset)):
                grid_name = sensor_points_reset.iloc[pos_idx].get('grid_name', '')
                grid_id = extract_grid_id_from_column(str(grid_name))
                if grid_id is not None:
                    self.sensor_grid_ids[pos_idx] = grid_id
    
    def calculate_upwelling_for_scenario(
        self,
        direct_df: pd.DataFrame,
        diffuse_df: pd.DataFrame,
        scenario_id: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Calculate upwelling radiation for a scenario.
        
        Args:
            direct_df: Direct downwelling SW [W/m2]
            diffuse_df: Diffuse downwelling SW [W/m2]
            scenario_id: Scenario identifier
            
        Returns:
            Tuple of (K_up_dir, K_up_dif) DataFrames
        """
        return calculate_upwelling(
            direct_df, diffuse_df, self.grid_material_mapping, scenario_id, self.material_db, self.sensor_points
        )
    
    def simulate_hourly(
        self,
        direct_df: pd.DataFrame,
        diffuse_df: pd.DataFrame,
        scenario_id: str,
        analysis_period: Optional[Tuple[int, int]] = None,
        irrigation: Optional[Dict[int, float]] = None,
        initial_theta: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Run hourly simulation for all trees.
        
        Args:
            direct_df: Direct downwelling SW [W/m2], sensors as columns, hours as rows
            diffuse_df: Diffuse downwelling SW [W/m2], sensors as columns, hours as rows
            scenario_id: Scenario identifier
            analysis_period: (start_hour, end_hour) tuple, or None for all hours
            irrigation: Dictionary mapping hour_of_year -> irrigation depth [m]
            initial_theta: Initial soil moisture [m3/m3] (uses config default if None)
            
        Returns:
            DataFrame with columns: tree_id, hour, T_leaf, ET, gc, theta, VPD, stress_flags
        """
        # Get soil params from config if not specified
        soil_params = self._get_soil_params()
        if initial_theta is None:
            initial_theta = soil_params['theta_init']
        
        # Get theta_fc for ground model evaporation limitation
        theta_fc = soil_params['theta_fc']
        
        # Get default material properties from config
        default_albedo, default_emissivity = self._get_default_albedo_emissivity()
        
        # Calculate upwelling radiation
        K_up_dir, K_up_dif = self.calculate_upwelling_for_scenario(
            direct_df, diffuse_df, scenario_id
        )
        
        # OPTIMIZATION 1: Convert DataFrames to NumPy arrays for fast indexing (5-10x speedup)
        direct_arr = direct_df.values
        diffuse_arr = diffuse_df.values
        K_up_dir_arr = K_up_dir.values
        K_up_dif_arr = K_up_dif.values
        
        # Determine analysis period
        # When None, use the actual irradiance data length (not full year weather_data)
        # This handles cases where scenario data is shorter (e.g., warmest week ~168 hours)
        # vs baseline which might be full year (8760 hours)
        data_length = len(direct_df)
        if analysis_period is None:
            start_hour = 0
            # Use actual data length - weather_data should already be trimmed to match
            # but use data_length as source of truth to handle edge cases
            end_hour = data_length - 1
        else:
            start_hour, end_hour = analysis_period
            # Ensure analysis_period doesn't exceed available data
            end_hour = min(end_hour, data_length - 1)
            # Ensure start_hour is valid
            start_hour = max(0, min(start_hour, data_length - 1))
        
        # Get tree IDs
        if 'tree_id' in self.tree_points.columns:
            tree_ids = self.tree_points['tree_id'].values
        elif 'number' in self.tree_points.columns:
            tree_ids = self.tree_points['number'].values
        else:
            tree_ids = np.arange(len(self.tree_points))
        
        # Get species for each tree
        tree_species = []
        if 'species' in self.tree_points.columns:
            for species_name in self.tree_points['species']:
                tree_species.append(self.species_db.get_species(species_name))
        else:
            # Default species
            tree_species = [self.species_db.get_species('default')] * len(self.tree_points)
        
        # Initialize soil moisture state
        n_trees = len(self.tree_points)
        theta_state = np.full(n_trees, initial_theta)
        
        # OPTIMIZATION 2: Pre-compute material properties for each tree (1.5-2x speedup)
        print(f"   Pre-computing material properties for {n_trees} trees...")
        material_cache = {}
        for tree_idx in range(n_trees):
            sensor_idx = self.nearest_sensor_indices[tree_idx]
            grid_id = self.sensor_grid_ids.get(sensor_idx, None)
            
            if grid_id is None:
                # Try to extract from column name, passing sensor_points for numeric column mapping
                col_name = direct_df.columns[sensor_idx]
                grid_id = extract_grid_id_from_column(str(col_name), self.sensor_points)
            
            # Get material properties for surface energy balance
            material_name = 'generic'  # Default
            if grid_id and len(self.grid_material_mapping) > 0:
                from grid_material_mapping import get_material_properties_for_grid
                try:
                    albedo, emissivity = get_material_properties_for_grid(
                        grid_id, scenario_id, self.grid_material_mapping, self.material_db
                    )
                    # Try to get material name for ground type lookup
                    scenario_materials = self.grid_material_mapping[
                        self.grid_material_mapping['scenario_id'] == scenario_id
                    ]
                    grid_mat = scenario_materials[scenario_materials['grid_id'] == grid_id]
                    if not grid_mat.empty:
                        material_name = grid_mat.iloc[0].get('material_name', 'generic')
                except Exception:
                    albedo, emissivity = default_albedo, default_emissivity
            else:
                print(f"No grid material mapping found for tree {tree_idx}")
                albedo, emissivity = default_albedo, default_emissivity
            
            # Get ground type for thermal properties
            ground_type = get_ground_type_from_material(material_name)
            ground_props = self.ground_model.get_ground_properties(
                ground_type, albedo=albedo, emissivity=emissivity
            )
            
            material_cache[tree_idx] = {
                'albedo': albedo,
                'emissivity': emissivity,
                'ground_type': ground_type,
                'heat_capacity': ground_props['heat_capacity'],
                'evap_factor': ground_props['evap_factor']
            }
        
        # OPTIMIZATION 4: Pre-allocate results arrays (1.3-1.5x speedup)
        n_hours = end_hour - start_hour + 1
        n_results = n_hours * n_trees
        results_dict = {
            'tree_id': np.empty(n_results, dtype=tree_ids.dtype),
            'hour': np.empty(n_results, dtype=np.int32),
            'T_leaf': np.empty(n_results, dtype=np.float64),
            'Tg': np.empty(n_results, dtype=np.float64),         # Ground temperature [C]
            'Tsurf': np.empty(n_results, dtype=np.float64),
            'MRT': np.empty(n_results, dtype=np.float64),
            'ET': np.empty(n_results, dtype=np.float64),
            'LE': np.empty(n_results, dtype=np.float64),
            'H': np.empty(n_results, dtype=np.float64),
            'gc': np.empty(n_results, dtype=np.float64),
            'rs': np.empty(n_results, dtype=np.float64),         # Stomatal resistance [s/m]
            'theta': np.empty(n_results, dtype=np.float64),
            'REW': np.empty(n_results, dtype=np.float64),        # Relative extractable water [0-1]
            'f_SM': np.empty(n_results, dtype=np.float64),       # Soil moisture stress factor [0-1]
            'VPD': np.empty(n_results, dtype=np.float64),
            'Kabs': np.empty(n_results, dtype=np.float64),
            'Rn': np.empty(n_results, dtype=np.float64)
        }
        result_idx = 0
        
        # Initialize ground temperature state for each tree (start at air temperature)
        # This will be updated hourly based on energy balance
        Tg_state = np.full(n_trees, 20.0)  # Will be set from first hour's air temp
        
        # Get default SVF for fallback
        default_svf = self._get_default_svf()
        
        # Main simulation loop over hours
        print(f"   Simulating {n_hours} hours for {n_trees} trees...")
        first_hour = True
        for row_idx in range(start_hour, end_hour + 1):
            # Get weather data using row index
            weather = self.weather_data.iloc[row_idx]
            hour_of_year = int(weather['hour_of_year'])  # Actual hour of year for irrigation lookup
            Ta = weather['Ta']
            RH = weather['RH']
            U = weather['U']
            P = weather['P']
            K_down = weather['K_down']
            L_sky = weather['L_sky']
            VPD = weather['VPD']
            qa = weather['qa']
            
            # Get precipitation from weather if available (in mm)
            precip_mm = weather.get('precip', 0.0) if 'precip' in weather.index else 0.0
            
            # RH as fraction for ground model
            RH_frac = RH / 100.0 if RH > 1.0 else RH
            
            # Initialize Tg_state from first hour's air temperature
            if first_hour:
                Tg_state[:] = Ta + 5.0  # Start slightly warmer than air
                first_hour = False
            
            # Get irrigation for this hour (uses actual hour_of_year, not row index)
            Irr = irrigation.get(hour_of_year, 0.0) if irrigation else 0.0
            
            # Process each tree
            for tree_idx in range(n_trees):
                tree_id = tree_ids[tree_idx]
                species = tree_species[tree_idx]
                sensor_idx = self.nearest_sensor_indices[tree_idx]
                
                # Get radiation at sensor location (using numpy arrays for speed)
                K_down_dir = direct_arr[row_idx, sensor_idx]
                K_down_dif = diffuse_arr[row_idx, sensor_idx]
                K_down_total = K_down_dir + K_down_dif
                
                # Get upwelling radiation (using numpy arrays for speed)
                K_up_dir_val = K_up_dir_arr[row_idx, sensor_idx]
                K_up_dif_val = K_up_dif_arr[row_idx, sensor_idx]
                K_up_total = K_up_dir_val + K_up_dif_val
                
                # Get pre-computed material properties (ground albedo, emissivity, thermal props)
                mat_props = material_cache[tree_idx]
                albedo = mat_props['albedo']
                emissivity = mat_props['emissivity']
                heat_capacity = mat_props['heat_capacity']
                evap_factor = mat_props['evap_factor']
                
                # Get per-tree SVF (from tree_points, falls back to species default then config)
                tree_svf = self.tree_svf.get(tree_idx, species.SVF if hasattr(species, 'SVF') else default_svf)
                
                # =====================================================
                # Step 1: Update ground temperature using energy balance
                # =====================================================
                Tg_prev = Tg_state[tree_idx]
                theta_prev = theta_state[tree_idx]
                
                ground_state = self.ground_model.step(
                    Tg_prev=Tg_prev,
                    K_down=K_down_total,
                    Ta=Ta,
                    RH=RH_frac,
                    albedo=albedo,
                    emissivity=emissivity,
                    heat_capacity=heat_capacity,
                    evap_factor=evap_factor,
                    dt=3600.0,  # 1 hour timestep
                    theta=theta_prev,
                    theta_fc=theta_fc
                )
                Tg = ground_state.Tg
                Tg_state[tree_idx] = Tg  # Update state for next timestep
                
                # =====================================================
                # Step 2: Get soil moisture state (REW, f_SM, r_sto)
                # Uses theta from previous step; will be updated after we get LE
                # =====================================================
                soil_state = self.soil_model.get_state(
                    theta=theta_prev,
                    r_sto_min=species.r_sto  # Use species-specific r_sto_min
                )
                r_sto_dynamic = soil_state.r_sto
                REW = soil_state.REW
                f_SM = soil_state.f_SM
                
                # Calculate surface temperature (used for MRT and legacy model)
                # Note: This is for comparison; Tg from energy balance is physically more accurate
                Tsurf = calculate_surface_temperature(
                    K_down_total, K_up_total, albedo, emissivity, Ta, L_sky, U
                )
                
                # Calculate MRT using per-tree SVF
                MRT = calculate_mrt(Tsurf, tree_svf, Ta, L_sky)
                
                if self.use_ceb_model and self.ceb_model is not None:
                    # =====================================================
                    # Li2023 CEB Model - Full canopy energy balance
                    # With dynamic Tg from ground model and r_sto from soil moisture
                    # =====================================================
                    
                    # Create CEB inputs with dynamic Tg and r_sto
                    ceb_inputs = CEBInputs(
                        Ta=Ta,
                        RH=RH_frac,
                        U=U,
                        P=P,
                        E_dir=K_down_dir,
                        E_dif=K_down_dif,
                        SVF=tree_svf,
                        albedo_g=albedo,
                        epsilon_g=emissivity,
                        alpha_sf=1.0 - species.alpha_leaf,  # Absorptivity = 1 - albedo
                        alpha_lf=species.epsilon_leaf,      # LW absorptivity ≈ emissivity
                        epsilon_lf=species.epsilon_leaf,
                        r_sto=r_sto_dynamic,                # Dynamic from soil moisture stress
                        leaf_size=species.leaf_char_size,
                        Tg=Tg                               # From ground energy balance
                    )
                    
                    # Solve CEB model
                    ceb_outputs = self.ceb_model.solve_leaf_temperature(ceb_inputs)
                    
                    T_leaf = ceb_outputs.Tf
                    H = ceb_outputs.H
                    LE = ceb_outputs.LE
                    Kabs = ceb_outputs.Q_sw
                    Rn_final = ceb_outputs.Q_sw + ceb_outputs.Q_lw_in - ceb_outputs.Q_lw_out
                    
                    # Stomatal conductance (inverted from dynamic r_sto)
                    # gc [mol/m2/s] ≈ 1 / (r_sto * Vm) where Vm is molar volume
                    T_K = Ta + 273.15
                    Vm = 8.314 * T_K / (P * 1000)  # Molar volume [m3/mol]
                    gc = 1.0 / (r_sto_dynamic * Vm) if r_sto_dynamic > 0 else 0.0
                    rs = r_sto_dynamic  # Dynamic stomatal resistance
                    
                else:
                    # =====================================================
                    # Legacy Model - Original leaf energy balance
                    # =====================================================
                    # Calculate incoming longwave using per-tree SVF
                    L_in = calculate_longwave_in(tree_svf, L_sky, Tsurf=Tsurf)
                    
                    # Calculate absorbed shortwave
                    Kabs_above = species.beta_above * (1.0 - species.alpha_leaf) * K_down_total
                    Kabs_below = species.beta_below * (1.0 - species.alpha_leaf) * K_up_total
                    Kabs = Kabs_above + Kabs_below
                    
                    # Calculate net radiation (initial estimate using air temperature)
                    Rn_initial = calculate_net_radiation(Kabs, L_in, species.epsilon_leaf, Ta)
                    
                    # Solve leaf energy balance
                    T_leaf, H, LE, gc, rs = solve_leaf_temperature(
                        Rn_initial, Ta, qa, U, species, theta_state[tree_idx],
                        species.ra_scale, species.shelter_factor, P
                    )
                    
                    # Recalculate net radiation with actual leaf temperature
                    Rn_final = calculate_net_radiation(Kabs, L_in, species.epsilon_leaf, T_leaf)
                
                # =====================================================
                # Step 3: Update soil moisture using bucket model
                # Uses LE from this timestep to calculate ET for water balance
                # =====================================================
                new_soil_state = self.soil_model.step(
                    theta_prev=theta_state[tree_idx],
                    LE=LE,
                    precip_mm=precip_mm,
                    dt=3600.0,
                    r_sto_min=species.r_sto
                )
                theta_state[tree_idx] = new_soil_state.theta
                ET_depth = new_soil_state.ET
                
                # Store results in pre-allocated arrays (fast)
                results_dict['tree_id'][result_idx] = tree_id
                results_dict['hour'][result_idx] = hour_of_year
                results_dict['T_leaf'][result_idx] = T_leaf
                results_dict['Tg'][result_idx] = Tg  # Ground temperature
                results_dict['Tsurf'][result_idx] = Tsurf
                results_dict['MRT'][result_idx] = MRT
                results_dict['ET'][result_idx] = ET_depth
                results_dict['LE'][result_idx] = LE
                results_dict['H'][result_idx] = H
                results_dict['gc'][result_idx] = gc
                results_dict['rs'][result_idx] = rs
                results_dict['theta'][result_idx] = theta_state[tree_idx]
                results_dict['REW'][result_idx] = REW
                results_dict['f_SM'][result_idx] = f_SM
                results_dict['VPD'][result_idx] = VPD
                results_dict['Kabs'][result_idx] = Kabs
                results_dict['Rn'][result_idx] = Rn_final
                result_idx += 1
        
        # Convert pre-allocated arrays to DataFrame
        df_results = pd.DataFrame(results_dict)
        
        # Use config paths for output (resolved for cross-platform compatibility)
        output_dir = get_path('biophysical_outputs_dir')
        import os
        os.makedirs(output_dir, exist_ok=True)
        df_results.to_csv(os.path.join(output_dir, f"biophysical_results_{scenario_id}.csv"))
        return df_results
    
    def calculate_stress_metrics(
        self,
        results_df: pd.DataFrame,
        T_crit: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Calculate heat stress metrics from simulation results.
        
        Focuses on leaf temperature only.
        
        Args:
            results_df: DataFrame from simulate_hourly()
            T_crit: Critical temperature [C] (uses config default if None)
            
        Returns:
            DataFrame with stress summary per tree:
            - heat_stress_hours
            - degree_hours
            - mean_Tleaf_C
            - max_Tleaf_C
        """
        if T_crit is None:
            T_crit = self._config.model.risk.T_crit
        
        return calculate_stress_summary(results_df, T_crit)
