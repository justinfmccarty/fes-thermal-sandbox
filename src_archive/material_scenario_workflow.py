"""
Material Scenario Workflow for Tree Heat Stress Analysis

This workflow:
1. Loads baseline radiance simulation results
2. Generates material scenarios based on naturalness instructions
3. Runs radiance simulations for each scenario
4. Calculates heat stress for trees
5. Compares scenarios and identifies most impactful material choices
"""

import os
import json
import random
import time
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from typing import Tuple, List, Dict, Optional
from scipy.spatial.distance import cdist
import sys
from multiprocessing import Pool, cpu_count

# Import local radiance module
import radiance as rad
from config_locator import get_config

try:
    import pyarrow.feather as feather
except ImportError:
    feather = None

# Import biophysical modules
try:
    from biophysical_tree_stress import BiophysicalTreeStressCalculator
    from weather_loader import load_epw
    from tree_species import TreeSpeciesDatabase
    from grid_material_mapping import load_grid_material_mapping
    BIOPHYSICAL_AVAILABLE = True
except ImportError:
    BIOPHYSICAL_AVAILABLE = False
    print("Warning: Biophysical modules not available. Using placeholder calculator.")


class MaterialDatabase:
    """Manages materials with naturalness weighting."""
    
    def __init__(self, root_material_db_path: str = None):
        """
        Initialize material database.
        
        Args:
            root_material_db_path: Optional path to root_material_database.csv file.
                                  If provided, loads material properties (albedo, emissivity).
        """
        # Material database: list of dicts with name, radiance_definition, naturalness_score
        # naturalness_score: 0.0 = least natural (concrete), 1.0 = most natural (vegetation)
        self.materials = []
        self.root_material_db = None
        
        # Load root material database if path provided
        if root_material_db_path and os.path.exists(root_material_db_path):
            self.load_root_material_database(root_material_db_path)
        
    def add_material(self, name: str, radiance_def: str, naturalness: float, surface_type: str):
        """
        Add a material to the database.
        
        Args:
            name: Material name identifier
            radiance_def: Radiance material definition (e.g., "void plastic ...")
            naturalness: Score from 0.0 (least natural) to 1.0 (most natural)
            surface_type: Either "landscape" or "facade"
        """
        self.materials.append({
            'name': name,
            'radiance_def': radiance_def,
            'naturalness': naturalness,
            'surface_type': surface_type
        })
    
    def get_material_by_naturalness(self, naturalness_threshold: float, surface_type: str) -> str:
        """
        Get material closest to naturalness threshold for given surface type.
        
        Args:
            naturalness_threshold: Target naturalness (0.0-1.0)
            surface_type: "landscape" or "facade"
            
        Returns:
            Material name
        """
        filtered = [m for m in self.materials if m['surface_type'] == surface_type]
        if not filtered:
            raise ValueError(f"No materials found for surface_type: {surface_type}")
        
        # Find material closest to threshold
        closest = min(filtered, key=lambda x: abs(x['naturalness'] - naturalness_threshold))
        return closest['name']
    
    def get_least_natural(self, surface_type: str) -> str:
        """Get least natural material (concrete baseline)."""
        filtered = [m for m in self.materials if m['surface_type'] == surface_type]
        if not filtered:
            raise ValueError(f"No materials found for surface_type: {surface_type}")
        return min(filtered, key=lambda x: x['naturalness'])['name']
    
    def get_most_natural(self, surface_type: str) -> Tuple[str, float]:
        """
        Get most natural material and its naturalness score.
        
        Args:
            surface_type: "landscape" or "facade"
            
        Returns:
            Tuple of (material_name, naturalness_score)
        """
        filtered = [m for m in self.materials if m['surface_type'] == surface_type]
        if not filtered:
            raise ValueError(f"No materials found for surface_type: {surface_type}")
        most = max(filtered, key=lambda x: x['naturalness'])
        return most['name'], most['naturalness']
    
    def calculate_coverage_for_target(self, target_naturalness: float, surface_type: str) -> float:
        """
        Calculate fraction of surfaces needing most-natural material to achieve target average naturalness.
        
        Uses linear interpolation between least and most natural materials:
        X = (T - N_low) / (N_high - N_low)
        
        Args:
            target_naturalness: Target average naturalness (0.0-1.0)
            surface_type: "landscape" or "facade"
            
        Returns:
            Fraction of surfaces (0.0-1.0) that should get the most natural material
        """
        # Get naturalness scores for extremes
        _, n_high = self.get_most_natural(surface_type)
        least_name = self.get_least_natural(surface_type)
        n_low = next(m['naturalness'] for m in self.materials if m['name'] == least_name and m['surface_type'] == surface_type)
        
        # Clamp target to achievable range
        target = max(n_low, min(n_high, target_naturalness))
        
        # Avoid division by zero (shouldn't happen if materials are different)
        if n_high == n_low:
            return 1.0 if target >= n_high else 0.0
        
        return (target - n_low) / (n_high - n_low)
    
    def get_material_with_naturalness(self, name: str, surface_type: str) -> Tuple[str, float]:
        """
        Get a specific material by name and its naturalness score.
        
        Args:
            name: Material name to find
            surface_type: "landscape" or "facade"
            
        Returns:
            Tuple of (material_name, naturalness_score)
            
        Raises:
            ValueError if material not found for surface type
        """
        for m in self.materials:
            if m['name'] == name and m['surface_type'] == surface_type:
                return m['name'], m['naturalness']
        raise ValueError(f"Material '{name}' not found for surface_type: {surface_type}")
    
    def calculate_three_tier_coverage(
        self, 
        target_naturalness: float, 
        surface_type: str
    ) -> Tuple[str, str, float]:
        """
        Calculate materials and coverage for three-tier interpolation.
        
        Uses three materials to achieve target average naturalness:
        - For targets <= mid_naturalness: interpolate between least and mid (black_brick + short_grass)
        - For targets > mid_naturalness: interpolate between mid and most (short_grass + tall_grass)
        
        Args:
            target_naturalness: Target average naturalness (0.0-1.0)
            surface_type: "landscape" or "facade"
            
        Returns:
            Tuple of (lower_material, upper_material, upper_coverage_fraction)
        """
        # Get the three tier materials
        # Least natural
        least_name = self.get_least_natural(surface_type)
        n_low = next(m['naturalness'] for m in self.materials 
                     if m['name'] == least_name and m['surface_type'] == surface_type)
        
        # Mid natural (short_grass - the realistic vegetation baseline)
        try:
            mid_name, n_mid = self.get_material_with_naturalness('short_grass', surface_type)
        except ValueError:
            # Fallback: if short_grass not available, find material closest to 0.95
            filtered = [m for m in self.materials if m['surface_type'] == surface_type]
            mid_mat = min(filtered, key=lambda x: abs(x['naturalness'] - 0.95))
            mid_name, n_mid = mid_mat['name'], mid_mat['naturalness']
        
        # Most natural (tall_grass)
        try:
            most_name, n_high = self.get_material_with_naturalness('tall_grass', surface_type)
        except ValueError:
            # Fallback: use actual most natural
            most_name, n_high = self.get_most_natural(surface_type)
        
        # Clamp target to achievable range
        target = max(n_low, min(n_high, target_naturalness))
        
        # Determine which tier to use
        if target <= n_mid:
            # Lower tier: interpolate between least and mid (black_brick + short_grass)
            lower_mat = least_name
            upper_mat = mid_name
            
            if n_mid == n_low:
                upper_coverage = 1.0 if target >= n_mid else 0.0
            else:
                upper_coverage = (target - n_low) / (n_mid - n_low)
        else:
            # Upper tier: interpolate between mid and most (short_grass + tall_grass)
            lower_mat = mid_name
            upper_mat = most_name
            
            if n_high == n_mid:
                upper_coverage = 1.0 if target >= n_high else 0.0
            else:
                upper_coverage = (target - n_mid) / (n_high - n_mid)
        
        # Clamp coverage to [0, 1]
        upper_coverage = max(0.0, min(1.0, upper_coverage))
        
        return lower_mat, upper_mat, upper_coverage
    
    def get_material_definition(self, name: str) -> str:
        """Get radiance definition for a material by name."""
        mat = next((m for m in self.materials if m['name'] == name), None)
        return mat['radiance_def'] if mat else None
    
    def load_root_material_database(self, csv_path: str):
        """
        Load material properties from root_material_database.csv.
        
        Args:
            csv_path: Path to root_material_database.csv
        """
        self.root_material_db = pd.read_csv(csv_path)
        # Fill missing values with defaults
        if 'shortwave_albedo' in self.root_material_db.columns:
            self.root_material_db['shortwave_albedo'] = self.root_material_db['shortwave_albedo'].fillna(0.3)
        if 'thermal_emissivity' in self.root_material_db.columns:
            self.root_material_db['thermal_emissivity'] = self.root_material_db['thermal_emissivity'].fillna(0.95)
        if 'naturalness_score' in self.root_material_db.columns:
            self.root_material_db['naturalness_score'] = self.root_material_db['naturalness_score'].fillna(0.2)
        
        # Populate self.materials list for scenario generation
        # Load Radiance definitions from base_material_library.txt
        base_lib_path = os.path.join(os.path.dirname(csv_path), 'base_material_library.txt')
        radiance_defs = {}
        if os.path.exists(base_lib_path):
            with open(base_lib_path, 'r') as f:
                content = f.read()
                # Parse material definitions (simple approach - each material starts with material name)
                for line in content.split('\n'):
                    if line.strip() and not line.startswith('#'):
                        # Just use a generic definition for now
                        pass
        
        # Add materials to self.materials list based on applicability
        for _, row in self.root_material_db.iterrows():
            mat_name = row['material_name']
            naturalness = row['naturalness_score']
            
            # Generic Radiance definition (can be improved by loading from base_material_library.txt)
            radiance_def = f"void plastic {mat_name}\n0\n0\n5 0.3 0.3 0.3 0.0 0.0"
            
            # Add as landscape material if ground_applicable
            if row.get('ground_applicable', False):
                self.add_material(mat_name, radiance_def, naturalness, 'landscape')
            
            # Add as facade material if facade_applicable  
            if row.get('facade_applicable', False):
                self.add_material(mat_name, radiance_def, naturalness, 'facade')
    
    def get_albedo(self, material_name: str) -> float:
        """
        Get shortwave albedo for a material.
        
        Args:
            material_name: Name of material
            
        Returns:
            Albedo (0.0-1.0), default 0.3 if not found
        """
        if self.root_material_db is None:
            return 0.3  # Default albedo
        
        row = self.root_material_db[self.root_material_db['material_name'] == material_name]
        if len(row) > 0 and 'shortwave_albedo' in row.columns:
            albedo = row.iloc[0]['shortwave_albedo']
            if pd.notna(albedo):
                return float(albedo)
        
        return 0.3  # Default
    
    def get_emissivity(self, material_name: str) -> float:
        """
        Get thermal emissivity for a material.
        
        Args:
            material_name: Name of material
            
        Returns:
            Emissivity (0.0-1.0), default 0.95 if not found
        """
        if self.root_material_db is None:
            return 0.95  # Default emissivity
        
        row = self.root_material_db[self.root_material_db['material_name'] == material_name]
        if len(row) > 0 and 'thermal_emissivity' in row.columns:
            emissivity = row.iloc[0]['thermal_emissivity']
            if pd.notna(emissivity):
                return float(emissivity)
        
        return 0.95  # Default
    
    def get_naturalness(self, material_name: str) -> float:
        """
        Get naturalness score for a material.
        
        Args:
            material_name: Name of material
            
        Returns:
            Naturalness score (0.0-1.0), default 0.2 if not found
        """
        if self.root_material_db is None:
            return 0.2  # Default naturalness
        
        row = self.root_material_db[self.root_material_db['material_name'] == material_name]
        if len(row) > 0 and 'naturalness_score' in row.columns:
            naturalness = row.iloc[0]['naturalness_score']
            if pd.notna(naturalness):
                return float(naturalness)
        
        return 0.2  # Default
    
    def get_permeability(self, material_name: str) -> float:
        """
        Get permeability for soil moisture calculations.
        This is a placeholder - permeability data may need to be added to database.
        
        Args:
            material_name: Name of material
            
        Returns:
            Permeability factor (0.0-1.0), default based on material type
        """
        # Default permeability estimates based on material type
        if 'grass' in material_name.lower() or 'vegetation' in material_name.lower() or 'deciduous' in material_name.lower() or 'conifer' in material_name.lower():
            return 0.8  # High permeability for vegetation
        elif 'concrete' in material_name.lower() or 'asphalt' in material_name.lower() or 'glass' in material_name.lower():
            return 0.1  # Low permeability for impervious surfaces
        elif 'pavers' in material_name.lower() or 'aggregate' in material_name.lower():
            return 0.6  # Moderate permeability for permeable pavers
        else:
            return 0.5  # Medium permeability default


class RadianceProjectManager:
    """Manages radiance project files and material modifications.
    
    This class ensures the baseline project is never modified. It creates temporary
    working copies for each scenario from scenario_project_dir (which has optimized grid files)
    and cleans them up after simulation.
    """
    
    def __init__(self, baseline_project_dir: str, scenario_project_dir: str = None, radiance_surface_key: str = '', temp_work_dir: str = None):
        """
        Initialize project manager.
        
        Args:
            baseline_project_dir: Path to immutable baseline radiance project (used for reference)
            scenario_project_dir: Path to scenario source project (with optimized grid files). 
                                  If None, uses baseline_project_dir.
            radiance_surface_key: Surface key identifier (usually empty)
            temp_work_dir: Directory for temporary working copies (defaults to temp directory)
        """
        self.baseline_project_dir = baseline_project_dir
        self.scenario_project_dir = scenario_project_dir if scenario_project_dir else baseline_project_dir
        self.radiance_surface_key = radiance_surface_key
        self.baseline_scene_base = self._get_baseline_scene_base()
        
        # Setup temporary working directory
        if temp_work_dir is None:
            import tempfile
            self.temp_work_dir = tempfile.mkdtemp(prefix='radiance_scenario_')
        else:
            self.temp_work_dir = temp_work_dir
            os.makedirs(self.temp_work_dir, exist_ok=True)
        
        self.current_work_dir = None  # Will be set when creating working copy
        
    def _get_baseline_scene_base(self) -> str:
        """Get baseline scene base directory."""
        if self.radiance_surface_key:
            return os.path.join(self.baseline_project_dir, self.radiance_surface_key, "model")
        return os.path.join(self.baseline_project_dir, "model")
    
    def _get_work_scene_base(self) -> str:
        """Get working scene base directory."""
        if self.current_work_dir is None:
            raise RuntimeError("No working copy created. Call create_working_copy() first.")
        # current_work_dir already points to the correct location (may include model/ if it exists)
        if self.radiance_surface_key:
            return os.path.join(self.current_work_dir, self.radiance_surface_key)
        return self.current_work_dir
    
    def create_working_copy(self, scenario_id: str) -> str:
        """
        Create a temporary working copy from scenario_project_dir (which has optimized grid files).
        
        Args:
            scenario_id: Unique identifier for this scenario
            
        Returns:
            Path to working copy directory
        """
        import shutil
        
        # Create scenario-specific working directory
        self.current_work_dir = os.path.join(self.temp_work_dir, scenario_id)
        
        # Remove if exists
        if os.path.exists(self.current_work_dir):
            shutil.rmtree(self.current_work_dir)
        
        # Copy entire scenario project structure (includes optimized grid files)
        shutil.copytree(self.scenario_project_dir, self.current_work_dir)
        
        # Check if model subdirectory exists and adjust work_dir accordingly
        # This handles projects with model/ subdirectory structure
        if os.path.exists(os.path.join(self.current_work_dir, 'model')):
            self.current_work_dir = os.path.join(self.current_work_dir, 'model')
        
        return self.current_work_dir
    
    def cleanup_working_copy(self):
        """Remove the current working copy."""
        if self.current_work_dir and os.path.exists(self.current_work_dir):
            import shutil
            shutil.rmtree(self.current_work_dir)
            self.current_work_dir = None
    
    def identify_surfaces(self, use_baseline: bool = True) -> Dict[str, List[str]]:
        """
        Identify landscape and facade surfaces from geometry file.
        
        Args:
            use_baseline: If True, read from baseline; if False, read from working copy
            
        Returns:
            Dict with 'landscape' and 'facade' keys, each containing list of surface IDs
        """
        surfaces = {'landscape': [], 'facade': []}
        
        if use_baseline:
            geometry_file = os.path.join(self.baseline_scene_base, "scene", "envelope.rad")
        else:
            geometry_file = os.path.join(self._get_work_scene_base(), "scene", "envelope.rad")
        
        with open(geometry_file, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            parts = stripped.split()
            if len(parts) < 2:
                continue
            
            geometry_type = parts[1] if len(parts) > 1 else None
            if geometry_type == 'polygon':
                surface_id = parts[2] if len(parts) > 2 else None
                
                # Simple heuristic: landscape surfaces typically have z=0 or low z
                # Facades are vertical (have varying z coordinates)
                # This is a placeholder - you may need to refine based on your geometry
                # For now, we'll use a simple approach: check if surface name contains keywords
                if surface_id:
                    if any(keyword in surface_id.lower() for keyword in ['ground', 'terrain', 'pavement', 'landscape', 'grass']):
                        surfaces['landscape'].append(surface_id)
                    elif any(keyword in surface_id.lower() for keyword in ['wall', 'facade', 'building']):
                        surfaces['facade'].append(surface_id)
                    else:
                        # Default: assume facade if we can't determine
                        surfaces['facade'].append(surface_id)
        
        return surfaces
    
    def apply_material_scenario(
        self, 
        instruction: Tuple[float, float], 
        material_db: MaterialDatabase,
        surfaces: Dict[str, List[str]],
        scenario_id: str = None
    ):
        """
        Apply material scenario based on instruction tuple to working copy.
        
        Args:
            instruction: (landscape_naturalness, facade_naturalness) both 0.0-1.0
            material_db: MaterialDatabase instance
            surfaces: Dict with 'landscape' and 'facade' surface IDs
            scenario_id: Unique identifier for this scenario (used for deterministic seeding)
        """
        if self.current_work_dir is None:
            raise RuntimeError("No working copy created. Call create_working_copy() first.")
        
        # Seed random number generator based on scenario_id for reproducibility
        # Each scenario gets a unique, deterministic seed
        if scenario_id:
            import hashlib
            seed = int(hashlib.md5(scenario_id.encode()).hexdigest(), 16) % (2**32)
            random.seed(seed)
        
        landscape_ratio, facade_ratio = instruction
        
        work_scene_base = self._get_work_scene_base()
        geometry_file = os.path.join(work_scene_base, "scene", "envelope.rad")
        material_file = os.path.join(work_scene_base, "scene", "envelope.mat")
        
        # Read baseline geometry file (for reference)
        baseline_geometry_file = os.path.join(self.baseline_scene_base, "scene", "envelope.rad")
        with open(baseline_geometry_file, 'r') as f:
            geom_lines = f.readlines()
        
        # Read baseline material file (for reference)
        baseline_material_file = os.path.join(self.baseline_scene_base, "scene", "envelope.mat")
        with open(baseline_material_file, 'r') as f:
            mat_lines = f.readlines()
        
        # THREE-TIER MATERIAL SELECTION
        # Uses three materials to achieve target average naturalness:
        # - For targets <= 0.95: interpolate between black_brick (0.15) + short_grass (0.95)
        # - For targets > 0.95: interpolate between short_grass (0.95) + tall_grass (1.0)
        
        # Get materials and coverage for landscape
        landscape_lower, landscape_upper, landscape_upper_coverage = \
            material_db.calculate_three_tier_coverage(landscape_ratio, 'landscape')
        
        # Get materials and coverage for facade  
        facade_lower, facade_upper, facade_upper_coverage = \
            material_db.calculate_three_tier_coverage(facade_ratio, 'facade')
        
        n_landscape = len(surfaces['landscape'])
        n_facade = len(surfaces['facade'])
        
        # Number of surfaces to get the UPPER material in each tier
        n_landscape_to_upper = int(n_landscape * landscape_upper_coverage)
        n_facade_to_upper = int(n_facade * facade_upper_coverage)
        
        # Remaining surfaces get the LOWER material
        n_landscape_to_lower = n_landscape - n_landscape_to_upper
        n_facade_to_lower = n_facade - n_facade_to_upper
        
        # Randomly select surfaces to get UPPER material
        landscape_to_upper = random.sample(
            surfaces['landscape'], 
            n_landscape_to_upper
        ) if n_landscape_to_upper > 0 else []
        
        # Remaining surfaces get LOWER material
        landscape_to_lower = [s for s in surfaces['landscape'] if s not in landscape_to_upper]
        
        # Randomly select facade surfaces to get UPPER material
        facade_to_upper = random.sample(
            surfaces['facade'],
            n_facade_to_upper
        ) if n_facade_to_upper > 0 else []
        
        # Remaining surfaces get LOWER material
        facade_to_lower = [s for s in surfaces['facade'] if s not in facade_to_upper]
        
        # For backward compatibility, use aliases
        landscape_material = landscape_upper  # Upper tier material
        facade_material = facade_upper  # Upper tier material
        least_natural_landscape = landscape_lower  # Lower tier material
        least_natural_facade = facade_lower  # Lower tier material
        landscape_to_natural = landscape_to_upper
        landscape_to_less_natural = landscape_to_lower
        facade_to_natural = facade_to_upper
        facade_to_less_natural = facade_to_lower
        
        # Modify geometry file
        modified_geom_lines = []
        for line in geom_lines:
            modified_line = line
            
            # Check if this is a landscape surface that should be changed
            for surface_id in landscape_to_natural:
                if surface_id in line:
                    # Change TO natural material (based on ratio)
                    parts = line.split()
                    if len(parts) > 0:
                        parts[0] = landscape_material
                        modified_line = ' '.join(parts) + '\n'
                    break
            
            # If not changed yet, check if it should be less natural
            if modified_line == line:
                for surface_id in landscape_to_less_natural:
                    if surface_id in line:
                        # Change TO less natural material
                        parts = line.split()
                        if len(parts) > 0:
                            parts[0] = least_natural_landscape
                            modified_line = ' '.join(parts) + '\n'
                        break
            
            # Check if this is a facade surface that should be changed
            if modified_line == line:
                for surface_id in facade_to_natural:
                    if surface_id in line:
                        # Change TO natural material (based on ratio)
                        parts = line.split()
                        if len(parts) > 0:
                            parts[0] = facade_material
                            modified_line = ' '.join(parts) + '\n'
                        break
            
            # If not changed yet, check if facade should be less natural
            if modified_line == line:
                for surface_id in facade_to_less_natural:
                    if surface_id in line:
                        # Change TO less natural material
                        parts = line.split()
                        if len(parts) > 0:
                            parts[0] = least_natural_facade
                            modified_line = ' '.join(parts) + '\n'
                        break
            
            modified_geom_lines.append(modified_line)
        
        # Write modified geometry file to working copy
        with open(geometry_file, 'w') as f:
            f.writelines(modified_geom_lines)
        
        # Ensure materials exist in material file (both natural and less natural materials)
        materials_needed = list(set([landscape_material, facade_material, least_natural_landscape, least_natural_facade]))
        self._ensure_materials_in_file(material_db, materials_needed, material_file)
    
    def _ensure_materials_in_file(self, material_db: MaterialDatabase, material_names: List[str], material_file: str):
        """Ensure required materials are defined in material file."""
        # Read current material file
        with open(material_file, 'r') as f:
            mat_content = f.read()
        
        # Add missing materials
        materials_to_add = []
        for mat_name in material_names:
            mat_def = material_db.get_material_definition(mat_name)
            if mat_def and mat_name not in mat_content:
                materials_to_add.append(mat_def)
        
        if materials_to_add:
            with open(material_file, 'a') as f:
                f.write('\n')
                f.write('\n'.join(materials_to_add))
                f.write('\n')


class TreeHeatStressCalculator:
    """Calculates heat stress for trees based on sensor data."""
    
    def __init__(self, tree_points: pd.DataFrame, sensor_points: pd.DataFrame):
        """
        Initialize calculator.
        
        Args:
            tree_points: DataFrame with columns ['xcoord', 'ycoord', 'zcoord', 'tree_id']
            sensor_points: DataFrame with columns ['xcoord', 'ycoord', 'zcoord'] and index as sensor_id
        """
        self.tree_points = tree_points
        self.sensor_points = sensor_points
        
        # Build spatial index for nearest neighbor lookup
        self._build_spatial_index()
    
    def _build_spatial_index(self):
        """Build spatial index for fast nearest neighbor lookup."""
        tree_coords = self.tree_points[['xcoord', 'ycoord', 'zcoord']].values
        sensor_coords = self.sensor_points[['xcoord', 'ycoord', 'zcoord']].values
        
        # Calculate distances
        distances = cdist(tree_coords, sensor_coords)
        self.nearest_sensor_indices = np.argmin(distances, axis=1)
    
    def calculate_heat_stress(
        self, 
        irradiance_data: pd.DataFrame,
        timestep: Optional[int] = None,
        period: Optional[Tuple[int, int]] = None
    ) -> pd.DataFrame:
        """
        Calculate heat stress for trees.
        
        Args:
            irradiance_data: DataFrame with sensors as columns, hours as rows (W/m²)
            timestep: Specific hour to calculate (0-8759), or None for period
            period: Tuple of (start_hour, end_hour) for period analysis
            
        Returns:
            DataFrame with tree_id and heat_stress columns
        """
        # Get tree_id column (could be 'tree_id', 'number', or index)
        if 'tree_id' in self.tree_points.columns:
            tree_ids = self.tree_points['tree_id'].values
        elif 'number' in self.tree_points.columns:
            tree_ids = self.tree_points['number'].values
        else:
            tree_ids = range(len(self.tree_points))
        
        if timestep is not None:
            # Single timestep
            sensor_values = irradiance_data.iloc[timestep, :].values
            tree_stress = sensor_values[self.nearest_sensor_indices]
            
            result = pd.DataFrame({
                'tree_id': tree_ids,
                'heat_stress': tree_stress
            })
        
        elif period is not None:
            # Period analysis
            start_hour, end_hour = period
            period_data = irradiance_data.iloc[start_hour:end_hour+1, :]
            
            # Calculate mean or max stress over period
            tree_stress_values = []
            for tree_idx in range(len(self.tree_points)):
                sensor_idx = self.nearest_sensor_indices[tree_idx]
                sensor_series = period_data.iloc[:, sensor_idx]
                # Use maximum stress in period
                tree_stress_values.append(sensor_series.max())
            
            result = pd.DataFrame({
                'tree_id': tree_ids,
                'heat_stress': tree_stress_values
            })
        
        else:
            raise ValueError("Must provide either timestep or period")
        
        return result


def _analyze_single_scenario(args):
    """
    Helper function to analyze a single scenario in parallel.
    
    This function is designed to be called by multiprocessing workers.
    
    Args:
        args: Tuple containing (scenario_id, scenario_info, workflow_data_dict)
    
    Returns:
        Tuple of (scenario_id, risk_analysis_df, metadata_dict, error_message)
    """
    scenario_id, scenario_info, workflow_data = args
    
    try:
        # Import modules needed for worker process
        import time as _time
        import pandas as _pd
        import os as _os
        try:
            import pyarrow.feather as _feather
        except ImportError:
            _feather = None
        
        from biophysical_tree_stress import BiophysicalTreeStressCalculator as _Calculator
        
        start_time = _time.time()
        
        # Unpack workflow data
        baseline_data = workflow_data['baseline_data']
        analysis_period_for_calc = workflow_data['analysis_period_for_calc']
        tree_points = workflow_data['tree_points']
        sensor_points = workflow_data['sensor_points']
        weather_data = workflow_data['weather_data']
        species_db = workflow_data['species_db']
        material_db = workflow_data['material_db']
        grid_material_mapping = workflow_data['grid_material_mapping']
        raytracing_results_dir = workflow_data['raytracing_results_dir']
        use_biophysical = workflow_data['use_biophysical']
        # Weather alignment for warmest_week scenarios
        warmest_week_weather_start = workflow_data.get('warmest_week_weather_start')
        warmest_week_weather_end = workflow_data.get('warmest_week_weather_end')
        
        direct_path = scenario_info['direct']
        diffuse_path = scenario_info['diffuse']
        
        if not _os.path.exists(direct_path) or not _os.path.exists(diffuse_path):
            return (scenario_id, None, None, "Feather files not found")
        
        # Calculate risk using biophysical model if available
        if use_biophysical and weather_data is not None and species_db is not None:
            # Load direct and diffuse separately from feather files
            baseline_direct_path = _os.path.join(raytracing_results_dir, 'baseline_direct.feather')
            baseline_diffuse_path = _os.path.join(raytracing_results_dir, 'baseline_diffuse.feather')
            scenario_direct_path = direct_path
            scenario_diffuse_path = diffuse_path
            
            if _feather and _os.path.exists(baseline_direct_path) and _os.path.exists(baseline_diffuse_path):
                # Transpose: feather files have sensors as rows, hours as columns
                # Code expects hours as rows, sensors as columns
                baseline_direct = _feather.read_feather(baseline_direct_path).T
                baseline_diffuse = _feather.read_feather(baseline_diffuse_path).T
            else:
                # Fallback: split total irradiance approximately
                baseline_direct = baseline_data * 0.6
                baseline_diffuse = baseline_data * 0.4
            
            if _feather and _os.path.exists(scenario_direct_path) and _os.path.exists(scenario_diffuse_path):
                # Transpose: feather files have sensors as rows, hours as columns
                # Code expects hours as rows, sensors as columns
                scenario_direct = _feather.read_feather(scenario_direct_path).T
                scenario_diffuse = _feather.read_feather(scenario_diffuse_path).T
            else:
                # Fallback: split total irradiance approximately
                scenario_direct = baseline_data * 0.6
                scenario_diffuse = baseline_data * 0.4
            
            # Create weather data subsets that match feather data lengths
            # Both baseline and scenario files now have data at correct calendar positions,
            # so we can use the same subsetting logic for both
            if warmest_week_weather_start is not None and warmest_week_weather_end is not None:
                # Warmest week: extract the same calendar range from both baseline and scenario
                warmest_week_n_hours = warmest_week_weather_end - warmest_week_weather_start + 1
                
                # Extract the correct weather data from the warmest week period
                scenario_weather = weather_data.iloc[warmest_week_weather_start:warmest_week_weather_start + warmest_week_n_hours].copy()
                scenario_weather = scenario_weather.reset_index(drop=True)
                baseline_weather = scenario_weather.copy()  # Same weather for both
                
                # Subset both baseline and scenario irradiance using same calendar range
                # Now that scenario files store data at correct positions, this is unified
                baseline_direct = baseline_direct.iloc[warmest_week_weather_start:warmest_week_weather_start + warmest_week_n_hours].copy()
                baseline_diffuse = baseline_diffuse.iloc[warmest_week_weather_start:warmest_week_weather_start + warmest_week_n_hours].copy()
                baseline_direct = baseline_direct.reset_index(drop=True)
                baseline_diffuse = baseline_diffuse.reset_index(drop=True)
                
                # Same subsetting for scenario (data now at correct calendar positions)
                scenario_direct = scenario_direct.iloc[warmest_week_weather_start:warmest_week_weather_start + warmest_week_n_hours].copy()
                scenario_diffuse = scenario_diffuse.iloc[warmest_week_weather_start:warmest_week_weather_start + warmest_week_n_hours].copy()
                scenario_direct = scenario_direct.reset_index(drop=True)
                scenario_diffuse = scenario_diffuse.reset_index(drop=True)
            else:
                # No warmest_week offset: use full data
                baseline_weather = weather_data.iloc[:len(baseline_direct)].copy()
                scenario_weather = weather_data.iloc[:len(scenario_direct)].copy()
            
            # Create biophysical calculator for baseline
            calc_baseline = _Calculator(
                tree_points,
                sensor_points,
                species_db,
                material_db,
                baseline_weather,
                grid_material_mapping if grid_material_mapping is not None else _pd.DataFrame()
            )
            
            # Run simulation for baseline
            print(f"Running simulation for baseline {scenario_id}")
            baseline_results = calc_baseline.simulate_hourly(
                baseline_direct,
                baseline_diffuse,
                'baseline',
                analysis_period_for_calc
            )
            
            # Create biophysical calculator for scenario
            print(f"Running simulation for scenario {scenario_id}")
            calc_scenario = _Calculator(
                tree_points,
                sensor_points,
                species_db,
                material_db,
                scenario_weather,
                grid_material_mapping if grid_material_mapping is not None else _pd.DataFrame()
            )
            
            # Run simulation for scenario
            scenario_results = calc_scenario.simulate_hourly(
                scenario_direct,
                scenario_diffuse,
                scenario_id,
                analysis_period_for_calc
            )
            
            # Calculate stress metrics (can use either calculator since tree points are the same)
            baseline_stress = calc_baseline.calculate_stress_metrics(baseline_results)
            scenario_stress = calc_baseline.calculate_stress_metrics(scenario_results)
            
            # Compare results
            print(f"Calculating stress metrics for baseline and {scenario_id}")
            risk_analysis = _pd.DataFrame({
                'tree_id': baseline_stress['tree_id'],
                'baseline_risk_index': baseline_stress['weighted_risk_index'],
                'scenario_risk_index': scenario_stress['weighted_risk_index'],
                'risk_reduction': baseline_stress['weighted_risk_index'] - scenario_stress['weighted_risk_index'],
                'baseline_heat_hours': baseline_stress['heat_hours_Tleaf>T_crit'],
                'scenario_heat_hours': scenario_stress['heat_hours_Tleaf>T_crit'],
                'heat_hours_reduction': baseline_stress['heat_hours_Tleaf>T_crit'] - scenario_stress['heat_hours_Tleaf>T_crit']
            })
        else:
            # Use placeholder calculator (load direct feather as proxy)
            if _feather:
                # Transpose: feather files have sensors as rows, hours as columns
                _ = _feather.read_feather(direct_path).T
            else:
                return (scenario_id, None, None, "pyarrow.feather is required")
            
            # Simple analysis without biophysical model
            # This is a placeholder - in practice you'd want to implement analyze_tree_risk
            risk_analysis = _pd.DataFrame({
                'tree_id': tree_points['tree_id'] if 'tree_id' in tree_points.columns else range(len(tree_points)),
                'baseline_risk_index': 0,
                'scenario_risk_index': 0,
                'risk_reduction': 0
            })
        
        end_time = _time.time()
        
        metadata = {
            'instruction': scenario_info.get('instruction'),
            'direct_path': direct_path,
            'diffuse_path': diffuse_path,
            'analysis_time': end_time - start_time
        }
        
        return (scenario_id, risk_analysis, metadata, None)
    
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return (scenario_id, None, None, error_msg)


class MaterialScenarioWorkflow:
    """Main workflow for material scenario analysis.
    
    This workflow operates in two phases:
    1. Raytracing Phase: Generate feather files for all scenarios (saved to raytracing_results/)
    2. Tree Risk Analysis Phase: Analyze feather files and calculate tree risk
    """
    
    def __init__(
        self,
        baseline_project_dir: str,
        scenario_project_dir: str = None,
        radiance_surface_key: str = '',
        raytracing_results_dir: str = None,
        baseline_feather_file: str = None,
        tree_points_file: str = None,
        sensor_points_file: str = None,
        weather_file: str = None,
        scenario_instructions: List[Tuple[float, float]] = None,
        baseline_period: str = 'annual',
        scenario_period: str = 'warmest_week',
        scenario_period_start: Tuple[int, int] = None,
        scenario_period_end: Tuple[int, int] = None
    ):
        """
        Initialize workflow.
        
        Args:
            baseline_project_dir: Path to immutable baseline radiance project (used for reference)
            scenario_project_dir: Path to scenario source project (with optimized grid files).
                                 If None, uses baseline_project_dir.
            radiance_surface_key: Surface key identifier (usually empty)
            raytracing_results_dir: Directory to save feather files (defaults to jodla_project/raytracing_results)
            baseline_feather_file: Path to baseline feather file if already exists
            tree_points_file: Path to tree points CSV
            sensor_points_file: Path to sensor points CSV
            weather_file: Path to weather EPW file
            scenario_instructions: Optional list of (landscape_naturalness, facade_naturalness) tuples.
                                  If provided, these explicit scenarios will be used instead of random generation.
            baseline_period: Simulation period for baseline ('annual', 'warmest_week', 'manual')
            scenario_period: Simulation period for scenarios ('annual', 'warmest_week', 'manual')
            scenario_period_start: For manual period: (month, day) tuple
            scenario_period_end: For manual period: (month, day) tuple
        """
        self.baseline_project_dir = baseline_project_dir
        self.scenario_project_dir = scenario_project_dir
        self.radiance_surface_key = radiance_surface_key
        
        # Setup raytracing results directory
        if raytracing_results_dir is None:
            project_root = os.path.dirname(os.path.abspath(__file__))
            self.raytracing_results_dir = os.path.join(project_root, 'raytracing_results')
        else:
            self.raytracing_results_dir = raytracing_results_dir
        os.makedirs(self.raytracing_results_dir, exist_ok=True)
        
        self.baseline_feather_file = baseline_feather_file
        self.tree_points_file = tree_points_file
        self.sensor_points_file = sensor_points_file
        self.weather_file = weather_file
        self.scenario_instructions = scenario_instructions  # Predefined scenario instructions
        
        # Simulation period settings
        self.baseline_period = baseline_period
        self.scenario_period = scenario_period
        self.scenario_period_start = scenario_period_start
        self.scenario_period_end = scenario_period_end
        
        self.project_manager = RadianceProjectManager(
            baseline_project_dir, 
            scenario_project_dir=scenario_project_dir,
            radiance_surface_key=radiance_surface_key
        )
        
        # Load root material database if available
        project_root = os.path.dirname(os.path.abspath(__file__))
        root_material_db_path = os.path.join(project_root, 'root_material_database.csv')
        self.material_db = MaterialDatabase(root_material_db_path=root_material_db_path)
        
        self.scenarios = []
        self.results = {}
        
        # Load weather, species, and grid mapping if available
        self.weather_data = None
        self.species_db = None
        self.grid_material_mapping = None
        
        if BIOPHYSICAL_AVAILABLE:
            if weather_file and os.path.exists(weather_file):
                try:
                    self.weather_data = load_epw(weather_file)
                except Exception as e:
                    print(f"Warning: Could not load weather file: {e}")
            
            # Load species database
            species_db_path = os.path.join(project_root, 'tree_species_database.csv')
            if os.path.exists(species_db_path):
                self.species_db = TreeSpeciesDatabase(species_db_path)
            else:
                self.species_db = TreeSpeciesDatabase()  # Empty database with defaults
            
            # Load grid-material mapping
            # Try to load from separate baseline and scenario files first
            baseline_mapping_path = os.path.join(project_root, 'grid_records', 'baseline_materials.csv')
            scenario_mapping_path = os.path.join(project_root, 'grid_records', 'scenario_grid_materials.csv')
            
            if os.path.exists(baseline_mapping_path) or os.path.exists(scenario_mapping_path):
                try:
                    self.grid_material_mapping = load_grid_material_mapping(
                        baseline_csv_path=baseline_mapping_path if os.path.exists(baseline_mapping_path) else None,
                        scenario_csv_path=scenario_mapping_path if os.path.exists(scenario_mapping_path) else None
                    )
                    print(f"   Loaded grid-material mapping: baseline={os.path.exists(baseline_mapping_path)}, scenarios={os.path.exists(scenario_mapping_path)}")
                except Exception as e:
                    print(f"Warning: Could not load grid-material mapping: {e}")
            else:
                # Fallback: try single combined file
                grid_mapping_path = os.path.join(project_root, 'grid_records', 'scenario_grid_materials.csv')
                if os.path.exists(grid_mapping_path):
                    try:
                        self.grid_material_mapping = load_grid_material_mapping(csv_path=grid_mapping_path)
                    except Exception as e:
                        print(f"Warning: Could not load grid-material mapping: {e}")
        
    def setup_material_database(self):
        """Setup material database with naturalness-weighted materials."""
        # Try to load materials from root_material_database.csv first
        if self.material_db.root_material_db is not None:
            self._load_materials_from_csv()
        else:
            # Fallback to hardcoded materials if CSV not available
            self._setup_default_materials()
    
    def _record_scenario_materials(
        self,
        scenario_id: str,
        instruction: Tuple[float, float],
        landscape_material: str,
        facade_material: str,
        surfaces: Dict[str, List[str]]
    ):
        """
        Record material assignments for a scenario.
        
        This method stores which materials were assigned to which surfaces.
        Note: Mapping surfaces to grid IDs requires additional information from Radiance outputs.
        For now, we store the instruction and materials used.
        """
        # Import here to avoid circular imports
        try:
            from grid_material_mapping import update_scenario_grid_mapping
            
            # Try to update the scenario grid mapping CSV
            if self.tree_points_file:
                project_root = os.path.dirname(os.path.dirname(self.tree_points_file))
            elif hasattr(self, 'baseline_project_dir'):
                project_root = os.path.dirname(os.path.dirname(self.baseline_project_dir))
            else:
                project_root = '.'
            
            scenario_mapping_path = os.path.join(project_root, 'grid_records', 'scenario_grid_materials.csv')
            
            if os.path.exists(scenario_mapping_path):
                try:
                    # For now, we'll update with placeholder information
                    # The actual grid-material mapping will need to be determined from Radiance outputs
                    # which requires parsing the column names in the feather files
                    update_scenario_grid_mapping(
                        scenario_id,
                        instruction,
                        landscape_material,
                        facade_material,
                        scenario_mapping_path
                    )
                except Exception as e:
                    print(f"Warning: Could not update scenario grid mapping: {e}")
        except ImportError:
            print(f"Warning: Could not import update_scenario_grid_mapping")
    
    def _load_materials_from_csv(self):
        """Load materials from root_material_database.csv."""
        if self.material_db.root_material_db is None:
            return
        
        # Read base material library for Radiance definitions
        project_root = os.path.dirname(os.path.abspath(__file__))
        base_library_path = os.path.join(project_root, 'base_material_library.txt')
        radiance_defs = {}
        
        if os.path.exists(base_library_path):
            with open(base_library_path, 'r') as f:
                lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('void'):
                    # Extract material name
                    parts = line.split()
                    if len(parts) >= 3:
                        material_name = parts[2]  # e.g., "grey_concrete" from "void plastic grey_concrete"
                        
                        # Collect the full definition (4 lines: void, 0, 0, parameters)
                        def_lines = [lines[i].rstrip()]
                        if i + 1 < len(lines):
                            def_lines.append(lines[i + 1].rstrip())  # First "0"
                        if i + 2 < len(lines):
                            def_lines.append(lines[i + 2].rstrip())  # Second "0"
                        if i + 3 < len(lines):
                            def_lines.append(lines[i + 3].rstrip())  # Parameters line
                        
                        radiance_defs[material_name] = '\n'.join(def_lines)
                        i += 4  # Skip the definition lines
                    else:
                        i += 1
                else:
                    i += 1
        
        # Load materials from CSV
        for _, row in self.material_db.root_material_db.iterrows():
            material_name = row['material_name']
            naturalness = row.get('naturalness_score', 0.2)
            
            # Determine surface type from CSV
            facade_app = row.get('facade_applicable', False)
            if isinstance(facade_app, str):
                facade_app = facade_app.lower() == 'true'
            ground_app = row.get('ground_applicable', False)
            if isinstance(ground_app, str):
                ground_app = ground_app.lower() == 'true'
            
            # Get Radiance definition
            radiance_def = radiance_defs.get(material_name, None)
            if radiance_def is None:
                # Generate default Radiance definition from albedo
                albedo = row.get('shortwave_albedo', 0.3)
                if pd.isna(albedo):
                    albedo = 0.3
                radiance_def = f'void plastic {material_name}\n0\n0\n5 {albedo} {albedo} {albedo} 0.0 0.0'
            
            # Add material for each applicable surface type
            if ground_app:
                self.material_db.add_material(
                    material_name,
                    radiance_def,
                    float(naturalness),
                    'landscape'
                )
            if facade_app:
                self.material_db.add_material(
                    material_name,
                    radiance_def,
                    float(naturalness),
                    'facade'
                )
    
    def _setup_default_materials(self):
        """Setup default materials if CSV not available."""
        # Landscape materials (from least to most natural)
        self.material_db.add_material(
            'concrete_landscape',
            'void plastic concrete_landscape\n0\n0\n5 0.3 0.3 0.3 0.0 0.0',
            0.0,
            'landscape'
        )
        
        self.material_db.add_material(
            'asphalt',
            'void plastic asphalt\n0\n0\n5 0.1 0.1 0.1 0.0 0.0',
            0.2,
            'landscape'
        )
        
        self.material_db.add_material(
            'pavement_light',
            'void plastic pavement_light\n0\n0\n5 0.5 0.5 0.5 0.0 0.0',
            0.4,
            'landscape'
        )
        
        self.material_db.add_material(
            'grass',
            'void plastic grass\n0\n0\n5 0.2 0.4 0.1 0.0 0.0',
            0.8,
            'landscape'
        )
        
        self.material_db.add_material(
            'vegetation',
            'void plastic vegetation\n0\n0\n5 0.15 0.35 0.1 0.0 0.0',
            1.0,
            'landscape'
        )
        
        # Facade materials
        self.material_db.add_material(
            'concrete_facade',
            'void plastic concrete_facade\n0\n0\n5 0.5 0.5 0.5 0.0 0.0',
            0.0,
            'facade'
        )
        
        self.material_db.add_material(
            'brick_dark',
            'void plastic brick_dark\n0\n0\n5 0.4 0.3 0.25 0.0 0.0',
            0.3,
            'facade'
        )
        
        self.material_db.add_material(
            'brick_light',
            'void plastic brick_light\n0\n0\n5 0.6 0.5 0.4 0.0 0.0',
            0.5,
            'facade'
        )
        
        self.material_db.add_material(
            'green_wall',
            'void plastic green_wall\n0\n0\n5 0.2 0.4 0.2 0.0 0.0',
            0.9,
            'facade'
        )
    
    def load_baseline(self) -> pd.DataFrame:
        """Load baseline irradiance results (total = direct + diffuse)."""
        # Check for baseline direct and diffuse feather files
        baseline_direct_path = os.path.join(self.raytracing_results_dir, 'baseline_direct.feather')
        baseline_diffuse_path = os.path.join(self.raytracing_results_dir, 'baseline_diffuse.feather')
        
        if os.path.exists(baseline_direct_path) and os.path.exists(baseline_diffuse_path):
            # Load from feather files and calculate total
            if feather:
                # Transpose: feather files have sensors as rows, hours as columns
                direct = feather.read_feather(baseline_direct_path).T
                diffuse = feather.read_feather(baseline_diffuse_path).T
                baseline = direct + diffuse
            else:
                raise ImportError("pyarrow.feather is required to read feather files")
            return baseline
        else:
            # Load from radiance project outputs
            direct, diffuse = rad.ill_to_df(
                self.baseline_project_dir,
                self.radiance_surface_key
            )
            baseline = direct + diffuse
            return baseline
    
    def generate_scenarios(self, n_scenarios: int = 10) -> List[Tuple[float, float]]:
        """
        Generate random material scenarios.
        
        Args:
            n_scenarios: Number of scenarios to generate
            
        Returns:
            List of (landscape_naturalness, facade_naturalness) tuples
        """
        scenarios = []
        for _ in range(n_scenarios):
            landscape_ratio = random.uniform(0.0, 1.0)
            facade_ratio = random.uniform(0.0, 1.0)
            scenarios.append((landscape_ratio, facade_ratio))
        
        self.scenarios = scenarios
        return scenarios
    
    def run_scenario_raytracing(
        self,
        instruction: Tuple[float, float],
        scenario_id: str,
        n_workers: int = 6,
        sky_resolution: int = 1,
        save_feather: bool = True,
        use_accelerad: bool = None,
        force_regenerate: bool = False
    ) -> Optional[str]:
        """
        Run radiance simulation for a single scenario and save feather file.
        
        Args:
            instruction: (landscape_naturalness, facade_naturalness) tuple
            scenario_id: Unique identifier for this scenario
            n_workers: Number of parallel workers
            sky_resolution: Sky resolution (1-6)
            save_feather: If True, save feather file to raytracing_results
            use_accelerad: Use GPU-accelerated Accelerad. If None, uses config.simulation.use_accelerad
            force_regenerate: If True, regenerate even if files exist
            
        Returns:
            Path to saved direct feather file, or None if save_feather=False or if skipped
        """
        # Get use_accelerad from config if not specified
        if use_accelerad is None:
            use_accelerad = get_config().simulation.use_accelerad
        # Check if scenario already exists
        direct_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_direct.feather')
        diffuse_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_diffuse.feather')
        scenario_exists = os.path.exists(direct_path) and os.path.exists(diffuse_path)
        
        if scenario_exists and not force_regenerate:
            print(f"\n✓ Scenario {scenario_id} already exists, skipping...")
            print(f"   {instruction}")
            return direct_path
        
        print(f"\nRunning scenario {scenario_id}: {instruction}")
        
        try:
            # Get appropriate weather file for simulation period
            from weather_loader import get_simulation_period_epw
            
            scenario_weather, num_hours, start_hour_offset = get_simulation_period_epw(
                input_epw=self.weather_file,
                period_type=self.scenario_period,
                start_date=self.scenario_period_start,
                end_date=self.scenario_period_end,
                output_dir=self.raytracing_results_dir
            )
            
            if self.scenario_period != 'annual':
                print(f"   Using {self.scenario_period} period: {num_hours} hours (offset={start_hour_offset})")
            
            # Create working copy
            work_dir = self.project_manager.create_working_copy(scenario_id)
            
            # Identify surfaces from baseline
            surfaces = self.project_manager.identify_surfaces(use_baseline=True)
            
            # Apply material scenario to working copy
            self.project_manager.apply_material_scenario(instruction, self.material_db, surfaces, scenario_id)
            
            # VERIFICATION: Check materials in envelope.rad before raytracing
            env_rad_path = os.path.join(work_dir, 'scene', 'envelope.rad')
            if os.path.exists(env_rad_path):
                with open(env_rad_path, 'r') as f:
                    lines = f.readlines()
                materials_in_file = {}
                for line in lines:
                    parts = line.strip().split()
                    if parts and not line.strip().startswith('#'):
                        mat = parts[0]
                        materials_in_file[mat] = materials_in_file.get(mat, 0) + 1
                print(f"   Materials in envelope.rad: {dict(sorted(materials_in_file.items()))}")
            else:
                print(f"   WARNING: envelope.rad not found at {env_rad_path}")
            
            # Run radiance simulation on working copy
            # Pass hour_offset so results are placed at correct calendar positions
            rad.run_2phase_dds(
                radiance_project_dir=work_dir,
                radiance_surface_key=self.radiance_surface_key,
                scenario_tmy=scenario_weather,
                n_workers=n_workers,
                sky_resolution=sky_resolution,
                use_accelerad=use_accelerad,
                rcontrib_rad_params="-ad 256 -lw 1.0e-3 -dc 1 -dt 0 -dj 0",
                rflux_rad_params="-lw 6.67e-07 -ab 5 -ad 15000",
                hour_offset=start_hour_offset
            )
            
            # Load results from working copy
            direct, diffuse = rad.ill_to_df(
                work_dir,
                self.radiance_surface_key
            )
            total_irradiance = direct + diffuse
            
            # Save feather files (direct, diffuse, and total)
            feather_paths = {}
            if save_feather:
                if feather:
                    # Save direct irradiance
                    direct_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_direct.feather')
                    feather.write_feather(direct, direct_path, compression="lz4")
                    feather_paths['direct'] = direct_path
                    print(f"   Saved direct irradiance: {direct_path}")
                    
                    # Save diffuse irradiance
                    diffuse_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_diffuse.feather')
                    feather.write_feather(diffuse, diffuse_path, compression="lz4")
                    feather_paths['diffuse'] = diffuse_path
                    print(f"   Saved diffuse irradiance: {diffuse_path}")
                    
                    # Note: Total irradiance not saved (can be calculated as direct + diffuse)
                else:
                    raise ImportError("pyarrow.feather is required to save feather files")
            
            # Track material assignments for this scenario
            # Get the surfaces that were changed
            surfaces = self.project_manager.identify_surfaces(use_baseline=True)
            landscape_ratio, facade_ratio = instruction
            landscape_material = self.material_db.get_material_by_naturalness(landscape_ratio, 'landscape')
            facade_material = self.material_db.get_material_by_naturalness(facade_ratio, 'facade')
            
            # Record material assignments (we'll need to map surfaces to grid IDs later)
            # For now, store the instruction and materials used
            self._record_scenario_materials(scenario_id, instruction, landscape_material, facade_material, surfaces)
            
            # Cleanup working copy
            self.project_manager.cleanup_working_copy()
            
            return feather_paths if save_feather else None
            
        except Exception as e:
            # Ensure cleanup even on error
            self.project_manager.cleanup_working_copy()
            raise e
    
    def analyze_tree_risk(
        self,
        baseline_data: pd.DataFrame,
        scenario_data: pd.DataFrame,
        analysis_period: Tuple[int, int],
        tree_points: pd.DataFrame,
        sensor_points: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Analyze tree risk comparing baseline to scenario.
        
        Args:
            baseline_data: Baseline irradiance DataFrame
            scenario_data: Scenario irradiance DataFrame
            analysis_period: (start_hour, end_hour) for analysis
            tree_points: Tree point locations
            sensor_points: Sensor point locations
            
        Returns:
            DataFrame with tree risk metrics
        """
        calculator = TreeHeatStressCalculator(tree_points, sensor_points)
        
        # Calculate heat stress for baseline
        baseline_stress = calculator.calculate_heat_stress(
            baseline_data,
            period=analysis_period
        )
        
        # Calculate heat stress for scenario
        scenario_stress = calculator.calculate_heat_stress(
            scenario_data,
            period=analysis_period
        )
        
        # Calculate difference (positive = reduced stress, negative = increased stress)
        result = pd.DataFrame({
            'tree_id': baseline_stress['tree_id'],
            'baseline_stress': baseline_stress['heat_stress'],
            'scenario_stress': scenario_stress['heat_stress'],
            'stress_reduction': baseline_stress['heat_stress'] - scenario_stress['heat_stress'],
            'percent_reduction': ((baseline_stress['heat_stress'] - scenario_stress['heat_stress']) / 
                                 baseline_stress['heat_stress'] * 100)
        })
        
        return result
    
    def analyze_tree_risk_biophysical(
        self,
        baseline_data: pd.DataFrame,
        scenario_data: pd.DataFrame,  # Kept for compatibility but not used - loads from feather
        scenario_id: str,
        analysis_period: Tuple[int, int],
        tree_points: pd.DataFrame,
        sensor_points: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Analyze tree risk using biophysical model.
        
        Args:
            baseline_data: Baseline total irradiance DataFrame  
            scenario_data: Not used - scenario feather files loaded directly
            scenario_id: Scenario identifier
            analysis_period: (start_hour, end_hour) for analysis, or None for all data
            tree_points: Tree point locations
            sensor_points: Sensor point locations
            
        Returns:
            DataFrame with tree risk metrics
        """
        if not BIOPHYSICAL_AVAILABLE:
            raise ImportError("Biophysical modules not available")
        
        # Load direct and diffuse separately from feather files
        baseline_direct_path = os.path.join(self.raytracing_results_dir, 'baseline_direct.feather')
        baseline_diffuse_path = os.path.join(self.raytracing_results_dir, 'baseline_diffuse.feather')
        scenario_direct_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_direct.feather')
        scenario_diffuse_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_diffuse.feather')
        
        if feather and os.path.exists(baseline_direct_path) and os.path.exists(baseline_diffuse_path):
            # Transpose: feather files have sensors as rows, hours as columns
            # Code expects hours as rows, sensors as columns
            baseline_direct = feather.read_feather(baseline_direct_path).T
            baseline_diffuse = feather.read_feather(baseline_diffuse_path).T
        else:
            # Fallback: split total irradiance approximately
            print(f"Warning: Direct/diffuse files not found, using 60/40 split approximation")
            baseline_direct = baseline_data * 0.6
            baseline_diffuse = baseline_data * 0.4
        
        if feather and os.path.exists(scenario_direct_path) and os.path.exists(scenario_diffuse_path):
            # Transpose: feather files have sensors as rows, hours as columns
            # Code expects hours as rows, sensors as columns
            scenario_direct = feather.read_feather(scenario_direct_path).T
            scenario_diffuse = feather.read_feather(scenario_diffuse_path).T
        else:
            # Fallback: split total irradiance approximately
            print(f"Warning: Direct/diffuse files not found for scenario, using 60/40 split approximation")
            scenario_direct = scenario_data * 0.6
            scenario_diffuse = scenario_data * 0.4
        
        # Create weather data subsets that match feather data lengths
        # Baseline: use first len(baseline_direct) rows of weather
        baseline_weather = self.weather_data.iloc[:len(baseline_direct)].copy()
        
        # Scenario: use first len(scenario_direct) rows of weather  
        scenario_weather = self.weather_data.iloc[:len(scenario_direct)].copy()
        
        # Create biophysical calculator for baseline
        calc_baseline = BiophysicalTreeStressCalculator(
            tree_points,
            sensor_points,
            self.species_db,
            self.material_db,
            baseline_weather,
            self.grid_material_mapping if self.grid_material_mapping is not None else pd.DataFrame()
        )
        
        # Run simulation for baseline
        baseline_results = calc_baseline.simulate_hourly(
            baseline_direct,
            baseline_diffuse,
            'baseline',
            analysis_period
        )
        
        # Create biophysical calculator for scenario
        calc_scenario = BiophysicalTreeStressCalculator(
            tree_points,
            sensor_points,
            self.species_db,
            self.material_db,
            scenario_weather,
            self.grid_material_mapping if self.grid_material_mapping is not None else pd.DataFrame()
        )
        
        # Run simulation for scenario
        scenario_results = calc_scenario.simulate_hourly(
            scenario_direct,
            scenario_diffuse,
            scenario_id,
            analysis_period
        )
        
        # Calculate stress metrics (can use either calculator since tree points are the same)
        baseline_stress = calc_baseline.calculate_stress_metrics(baseline_results)
        scenario_stress = calc_baseline.calculate_stress_metrics(scenario_results)
        
        # Compare results
        result = pd.DataFrame({
            'tree_id': baseline_stress['tree_id'],
            'baseline_risk_index': baseline_stress['weighted_risk_index'],
            'scenario_risk_index': scenario_stress['weighted_risk_index'],
            'risk_reduction': baseline_stress['weighted_risk_index'] - scenario_stress['weighted_risk_index'],
            'baseline_heat_hours': baseline_stress['heat_hours_Tleaf>T_crit'],
            'scenario_heat_hours': scenario_stress['heat_hours_Tleaf>T_crit'],
            'heat_hours_reduction': baseline_stress['heat_hours_Tleaf>T_crit'] - scenario_stress['heat_hours_Tleaf>T_crit']
        })
        
        return result
    
    def find_warmest_july_day(self, baseline_data: pd.DataFrame) -> int:
        """
        Find the warmest day in July (hour of year).
        
        Args:
            baseline_data: Baseline irradiance DataFrame
            
        Returns:
            Hour of year for start of warmest July day
        """
        # July is hours 4344-4631 (assuming Jan 1 = hour 0)
        july_start = 4344
        july_end = 4631
        
        july_data = baseline_data.iloc[july_start:july_end+1, :]
        
        # Find day with maximum total irradiance
        daily_totals = []
        for day_start in range(0, len(july_data), 24):
            day_data = july_data.iloc[day_start:day_start+24, :]
            daily_totals.append(day_data.sum().sum())
        
        warmest_day_idx = np.argmax(daily_totals)
        warmest_day_hour = july_start + (warmest_day_idx * 24)
        
        return warmest_day_hour
    
    def run_baseline_raytracing(
        self,
        n_workers: int = 6,
        use_accelerad: bool = None,
        force_regenerate: bool = False
    ) -> Tuple[str, str]:
        """
        Run baseline raytracing simulation and save feather files.
        
        Args:
            n_workers: Number of parallel workers for radiance
            use_accelerad: Use GPU-accelerated Accelerad. If None, uses config.simulation.use_accelerad
            force_regenerate: If True, regenerate even if files exist
            
        Returns:
            Tuple of (baseline_direct_path, baseline_diffuse_path)
        """
        # Get use_accelerad from config if not specified
        if use_accelerad is None:
            use_accelerad = get_config().simulation.use_accelerad
        print("="*70)
        print("BASELINE RAYTRACING")
        print("="*70)
        
        # Setup material database
        print("\n1. Setting up material database...")
        self.setup_material_database()
        
        # Check if baseline files already exist
        baseline_direct_path = os.path.join(self.raytracing_results_dir, 'baseline_direct.feather')
        baseline_diffuse_path = os.path.join(self.raytracing_results_dir, 'baseline_diffuse.feather')
        
        if not force_regenerate and os.path.exists(baseline_direct_path) and os.path.exists(baseline_diffuse_path):
            print("\n2. Baseline feather files already exist, skipping raytracing...")
            print(f"   Direct: {baseline_direct_path}")
            print(f"   Diffuse: {baseline_diffuse_path}")
            return baseline_direct_path, baseline_diffuse_path
        
        print("\n2. Generating baseline feather files...")
        try:
            # Create temporary working copy
            import shutil
            import tempfile
            temp_baseline_dir = tempfile.mkdtemp(prefix='baseline_temp_')
            shutil.copytree(self.baseline_project_dir, os.path.join(temp_baseline_dir, 'baseline'))
            work_dir = os.path.join(temp_baseline_dir, 'baseline')
            
            # Check if model subdirectory exists and adjust work_dir accordingly
            if os.path.exists(os.path.join(work_dir, 'model')):
                work_dir = os.path.join(work_dir, 'model')
            
            # Run radiance simulation
            print(f"   Running 2-phase DDS simulation (use_accelerad={use_accelerad})...")
            rad.run_2phase_dds(
                radiance_project_dir=work_dir,
                radiance_surface_key=self.radiance_surface_key,
                scenario_tmy=self.weather_file,
                n_workers=n_workers,
                sky_resolution=1,
                use_accelerad=use_accelerad,
                rcontrib_rad_params="-ad 256 -lw 1.0e-3 -dc 1 -dt 0 -dj 0",
                rflux_rad_params="-lw 6.67e-07 -ab 5 -ad 15000"
            )
            
            # Load and save results
            print("   Loading results...")
            direct, diffuse = rad.ill_to_df(work_dir, self.radiance_surface_key)
            total_irradiance = direct + diffuse
            
            if feather:
                # Ensure output directory exists
                os.makedirs(self.raytracing_results_dir, exist_ok=True)
                
                # Save direct irradiance
                feather.write_feather(direct, baseline_direct_path, compression="lz4")
                print(f"   ✓ Saved baseline direct irradiance: {baseline_direct_path}")
                
                # Save diffuse irradiance
                feather.write_feather(diffuse, baseline_diffuse_path, compression="lz4")
                print(f"   ✓ Saved baseline diffuse irradiance: {baseline_diffuse_path}")
                
                # Note: Total irradiance not saved (can be calculated as direct + diffuse)
            else:
                raise ImportError("pyarrow.feather is required")
            
            # Cleanup
            shutil.rmtree(temp_baseline_dir)
            
        except Exception as e:
            # Ensure cleanup even on error
            if 'temp_baseline_dir' in locals():
                shutil.rmtree(temp_baseline_dir)
            raise e
        
        print("\n" + "="*70)
        print("Baseline raytracing complete!")
        print("="*70)
        
        return baseline_direct_path, baseline_diffuse_path
    
    def run_raytracing_phase(
        self,
        n_scenarios: int = 10,
        n_workers: int = 6,
        generate_baseline_feather: bool = True,
        scenario_instructions: List[Tuple[float, float]] = None,
        use_accelerad: bool = None,
        force_regenerate: bool = False
    ):
        """
        Phase 1: Run raytracing simulations for all scenarios.
        Saves feather files to raytracing_results/ directory.
        
        Args:
            n_scenarios: Number of scenarios to generate (used only if no predefined instructions)
            n_workers: Number of parallel workers for radiance
            generate_baseline_feather: If True, generate baseline feather file
            scenario_instructions: Optional list of (landscape_naturalness, facade_naturalness) tuples.
                                  If provided, overrides self.scenario_instructions. If both are None,
                                  generates n_scenarios random scenarios.
            use_accelerad: Use GPU-accelerated Accelerad. If None, uses config.simulation.use_accelerad
            force_regenerate: If True, regenerate scenarios even if they exist
        """
        # Get use_accelerad from config if not specified
        if use_accelerad is None:
            use_accelerad = get_config().simulation.use_accelerad
        print("="*70)
        print("PHASE 1: Raytracing Simulations")
        print("="*70)
        
        # Setup
        print("\n1. Setting up material database...")
        self.setup_material_database()
        
        # Generate baseline feather file if needed
        if generate_baseline_feather:
            print("\n2. Generating baseline feather file...")
            self.run_baseline_raytracing(
                n_workers=n_workers,
                use_accelerad=use_accelerad,
                force_regenerate=False  # Don't regenerate if exists
            )
        else:
            print("\n2. Skipping baseline generation...")
        
        # Get scenarios - priority: parameter > instance variable > random generation
        if scenario_instructions is not None:
            scenarios = scenario_instructions
            print(f"\n3. Using {len(scenarios)} predefined scenario instructions (from parameter)")
            for i, instruction in enumerate(scenarios):
                print(f"   scenario_{i:03d}: landscape={instruction[0]:.2f}, facade={instruction[1]:.2f}")
        elif self.scenario_instructions:
            scenarios = self.scenario_instructions
            print(f"\n3. Using {len(scenarios)} predefined scenario instructions (from initialization)")
            for i, instruction in enumerate(scenarios):
                print(f"   scenario_{i:03d}: landscape={instruction[0]:.2f}, facade={instruction[1]:.2f}")
        else:
            print(f"\n3. Generating {n_scenarios} random scenarios...")
            scenarios = self.generate_scenarios(n_scenarios)
            print(f"   Generated {len(scenarios)} random scenarios")
        
        # Run scenarios
        print(f"\n4. Running {len(scenarios)} scenario simulations...")
        if force_regenerate:
            print(f"   Mode: FORCE REGENERATE")
        scenario_feather_files = {}
        for i, instruction in enumerate(scenarios):
            scenario_id = f"scenario_{i:03d}"
            try:
                feather_paths = self.run_scenario_raytracing(
                    instruction,
                    scenario_id,
                    n_workers=n_workers,
                    save_feather=True,
                    use_accelerad=use_accelerad,
                    force_regenerate=force_regenerate
                )
                # feather_paths is dict with 'direct' and 'diffuse' keys
                if feather_paths:
                    feather_paths['instruction'] = instruction
                    scenario_feather_files[scenario_id] = feather_paths
            except Exception as e:
                print(f"   Error in {scenario_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print("\n" + "="*70)
        print(f"Raytracing phase completed! Generated {len(scenario_feather_files)} scenario feather files")
        print(f"Results saved to: {self.raytracing_results_dir}")
        print("="*70)
        
        return scenario_feather_files
    
    def run_tree_risk_analysis_phase(
        self,
        analysis_period: Optional[Tuple[int, int]] = None,
        scenario_feather_files: Optional[Dict] = None,
        n_workers: Optional[int] = None,
        use_parallel: bool = False
    ):
        """
        Phase 2: Analyze tree risk from feather files.
        
        Args:
            analysis_period: (start_hour, end_hour) for analysis, or None to use warmest July day
            scenario_feather_files: Dict of scenario feather files (if None, loads from raytracing_results)
            n_workers: Number of parallel workers (None = use all CPU cores, 1 = sequential)
            use_parallel: Whether to use parallel processing (default True)
        """
        print("="*70)
        print("PHASE 2: Tree Risk Analysis")
        print("="*70)
        
        # Load baseline
        print("\n1. Loading baseline results...")
        baseline_data = self.load_baseline()
        
        # Determine analysis period
        # NOTE: When scenarios use warmest_week while baseline uses annual,
        # we cannot use absolute hour indices from baseline on scenario data.
        # The scenario data is already subset to the analysis period (e.g., 168 hours).
        # Pass analysis_period to limit baseline processing to match scenario data.
        # Track warmest week hour offset for weather data alignment
        warmest_week_weather_start = None
        warmest_week_weather_end = None
        
        if analysis_period is None:
            # Check scenario data length to determine appropriate period
            # If scenarios were run with warmest_week, use that same period
            if self.scenario_period == 'warmest_week' and self.weather_file:
                from weather_loader import find_warmest_day, get_week_around_day
                try:
                    day_of_year, _, _ = find_warmest_day(self.weather_file)
                    start_day, end_day = get_week_around_day(day_of_year)
                    # Calculate relative hours (scenario data starts at 0)
                    warmest_week_hours = (end_day - start_day + 1) * 24
                    analysis_period_for_calc = (0, warmest_week_hours - 1)
                    # Store the actual year hours for weather data alignment
                    warmest_week_weather_start = start_day * 24
                    warmest_week_weather_end = (end_day + 1) * 24 - 1
                    print(f"   Using warmest_week period: hours 0-{warmest_week_hours - 1} ({warmest_week_hours} hours)")
                    print(f"   Weather data alignment: year hours {warmest_week_weather_start}-{warmest_week_weather_end}")
                except Exception as e:
                    print(f"   Warning: Could not determine warmest week: {e}")
                    print(f"   Using all available data")
                    analysis_period_for_calc = None
            else:
                print(f"   Using all available data (analysis_period=None)")
                analysis_period_for_calc = None
        else:
            print(f"   Using specified period: hours {analysis_period[0]}-{analysis_period[1]}")
            analysis_period_for_calc = analysis_period
        
        # Load tree and sensor points
        print("\n2. Loading tree and sensor points...")
        tree_points = None
        sensor_points = None
        
        if self.tree_points_file and os.path.exists(self.tree_points_file):
            tree_points = pd.read_csv(self.tree_points_file)
            # Handle different column name formats
            if 'x_coord' in tree_points.columns:
                tree_points = tree_points.rename(columns={
                    'x_coord': 'xcoord',
                    'y_coord': 'ycoord',
                    'z_coord': 'zcoord'
                })
            # Filter to baseline if scenario_id column exists
            if 'scenario_id' in tree_points.columns:
                tree_points = tree_points[tree_points['scenario_id'] == 'baseline'].copy()
            if not all(col in tree_points.columns for col in ['xcoord', 'ycoord', 'zcoord']):
                raise ValueError("Tree points file must contain xcoord, ycoord, zcoord columns (or x_coord/y_coord/z_coord)")
        
        if self.sensor_points_file and os.path.exists(self.sensor_points_file):
            # Use utils.load_sensor_points which handles both CSV and .pts formats
            from utils import load_sensor_points
            sensor_points = load_sensor_points(self.sensor_points_file)
        
        if tree_points is None or sensor_points is None:
            raise ValueError("Tree points and sensor points files are required for risk analysis")
        
        print(f"   Loaded {len(tree_points)} tree points")
        print(f"   Loaded {len(sensor_points)} sensor points")
        
        # Load scenario feather files
        if scenario_feather_files is None:
            print("\n3. Loading scenario feather files...")
            scenario_feather_files = {}
            # Collect unique scenario IDs from direct feather files
            scenario_ids_found = set()
            for feather_file in os.listdir(self.raytracing_results_dir):
                if feather_file.endswith('_direct.feather') and feather_file.startswith('scenario_'):
                    scenario_id = feather_file.replace('_direct.feather', '')
                    scenario_ids_found.add(scenario_id)
            
            # Create entries for each scenario
            for scenario_id in scenario_ids_found:
                direct_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_direct.feather')
                diffuse_path = os.path.join(self.raytracing_results_dir, f'{scenario_id}_diffuse.feather')
                
                # Both direct and diffuse must exist
                if not (os.path.exists(direct_path) and os.path.exists(diffuse_path)):
                    continue
                
                scenario_feather_files[scenario_id] = {
                    'direct': direct_path,
                    'diffuse': diffuse_path,
                    'instruction': None  # Will need to be stored separately
                }
        else:
            print("\n3. Using provided scenario feather files...")
        
        # Analyze tree risk
        print("\n4. Analyzing tree risk...")
        risk_analyses = {}
        scenario_results = {}
        
        # Determine number of workers
        if n_workers is None:
            n_workers = cpu_count() - 3
        
        # Prepare workflow data that will be passed to worker processes
        workflow_data = {
            'baseline_data': baseline_data,
            'analysis_period_for_calc': analysis_period_for_calc,
            'tree_points': tree_points,
            'sensor_points': sensor_points,
            'weather_data': self.weather_data,
            'species_db': self.species_db,
            'material_db': self.material_db,
            'grid_material_mapping': self.grid_material_mapping,
            'raytracing_results_dir': self.raytracing_results_dir,
            'use_biophysical': BIOPHYSICAL_AVAILABLE and self.weather_data is not None and self.species_db is not None,
            # Weather alignment for warmest_week scenarios
            'warmest_week_weather_start': warmest_week_weather_start,
            'warmest_week_weather_end': warmest_week_weather_end
        }
        
        # Prepare arguments for each scenario
        scenario_args = []
        for scenario_id, scenario_info in scenario_feather_files.items():
            scenario_args.append((scenario_id, scenario_info, workflow_data))
        
        # Process scenarios
        if use_parallel and n_workers > 1:
            print(f"   Using parallel processing with {n_workers} workers")
            print(f"   Processing {len(scenario_args)} scenarios in parallel...")
            start_time_all = time.time()
            
            with Pool(processes=n_workers) as pool:
                results = pool.map(_analyze_single_scenario, scenario_args)
            
            # Process results
            for scenario_id, risk_analysis, metadata, error_msg in results:
                if error_msg is not None:
                    print(f"   ✗ {scenario_id}: {error_msg.split(chr(10))[0]}")  # Print first line of error
                    continue
                
                if risk_analysis is not None and metadata is not None:
                    risk_analyses[scenario_id] = risk_analysis
                    scenario_results[scenario_id] = metadata
                    print(f"   ✓ {scenario_id}: completed in {metadata['analysis_time']:.2f}s")
                else:
                    print(f"   ✗ {scenario_id}: analysis returned no results")
            
            end_time_all = time.time()
            print(f"\n   Total parallel processing time: {end_time_all - start_time_all:.2f} seconds")
            print(f"   Successfully analyzed {len(risk_analyses)}/{len(scenario_args)} scenarios")
        else:
            # Sequential processing (for debugging or single-core systems)
            print(f"   Using sequential processing")
            for args in scenario_args:
                scenario_id, scenario_info, _ = args
                print(f"\n   Analyzing {scenario_id}...")
                scenario_id, risk_analysis, metadata, error_msg = _analyze_single_scenario(args)
                
                if error_msg is not None:
                    print(f"   ✗ Error: {error_msg.split(chr(10))[0]}")
                    continue
                
                if risk_analysis is not None and metadata is not None:
                    risk_analyses[scenario_id] = risk_analysis
                    scenario_results[scenario_id] = metadata
                    print(f"   ✓ Analysis time: {metadata['analysis_time']:.2f}s")
                else:
                    print(f"   ✗ Analysis returned no results")
        
        # Identify most impactful scenarios
        print("\n5. Identifying most impactful material choices...")
        if risk_analyses:
            scenario_impacts = {}
            for scenario_id, risk_df in risk_analyses.items():
                avg_reduction = risk_df['risk_reduction'].mean()  # Fixed: was 'stress_reduction'
                scenario_impacts[scenario_id] = {
                    'avg_risk_reduction': avg_reduction,
                    'instruction': scenario_results[scenario_id].get('instruction')
                }
            
            # Sort by impact
            sorted_scenarios = sorted(
                scenario_impacts.items(),
                key=lambda x: x[1]['avg_risk_reduction'],
                reverse=True
            )
            
            print("\n   Top 5 most impactful scenarios:")
            for i, (scenario_id, impact) in enumerate(sorted_scenarios[:5]):
                print(f"   {i+1}. {scenario_id}: {impact['avg_risk_reduction']:.4f} risk index reduction")
                if impact['instruction']:
                    print(f"      Instruction: {impact['instruction']}")
        
        # Store results (exclude raw feather data - it's already saved to disk)
        # Only store the analysis results and metadata
        scenario_metadata = {}
        for scenario_id, info in scenario_results.items():
            scenario_metadata[scenario_id] = {
                'instruction': info.get('instruction'),
                'direct_path': info.get('direct_path'),
                'diffuse_path': info.get('diffuse_path')
            }
        
        self.results = {
            'risk_analyses': risk_analyses,  # The actual analysis results
            'scenario_metadata': scenario_metadata,  # Just paths and instructions
            'analysis_period': analysis_period,
            'num_trees': len(tree_points) if tree_points is not None else 0,
            'num_sensors': len(sensor_points) if sensor_points is not None else 0
        }
        
        print("\n" + "="*70)
        print("Tree risk analysis completed!")
        print("="*70)
        
        return self.results
    
    def run_full_workflow(
        self,
        n_scenarios: int = 10,
        analysis_period: Optional[Tuple[int, int]] = None,
        n_workers: int = 6,
        skip_raytracing: bool = False,
        use_accelerad: bool = None
    ):
        """
        Run complete workflow: raytracing phase -> tree risk analysis phase.
        
        Args:
            n_scenarios: Number of scenarios to generate
            analysis_period: (start_hour, end_hour) for analysis, or None to use warmest July day
            n_workers: Number of parallel workers for radiance
            skip_raytracing: If True, skip raytracing phase and use existing feather files
            use_accelerad: Use GPU-accelerated Accelerad. If None, uses config.simulation.use_accelerad
        """
        # Get use_accelerad from config if not specified
        if use_accelerad is None:
            use_accelerad = get_config().simulation.use_accelerad
        if not skip_raytracing:
            # Phase 1: Raytracing
            scenario_feather_files = self.run_raytracing_phase(
                n_scenarios=n_scenarios,
                n_workers=n_workers,
                use_accelerad=use_accelerad
            )
        else:
            print("Skipping raytracing phase, using existing feather files...")
            scenario_feather_files = None
        
        # Phase 2: Tree Risk Analysis
        results = self.run_tree_risk_analysis_phase(
            analysis_period=analysis_period,
            scenario_feather_files=scenario_feather_files
        )
        
        return results

