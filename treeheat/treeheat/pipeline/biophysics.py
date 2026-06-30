"""Biophysical scenario driver — orchestrates feather inputs through the integrator.

PORT FROM: src_archive/biophysical_tree_stress.py (simulate_hourly orchestration)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

from treeheat.config import get_config, get_path
from treeheat.io.grids import get_material_properties_for_grid, load_grid_material_mapping
from treeheat.io.materials import MaterialDatabase, load_material_database
from treeheat.io.weather import find_warmest_day, get_week_around_day, load_epw
from treeheat.physics.ground import GroundEnergyBalance, get_ground_type_from_material
from treeheat.physics.integrator import solve_tree_hour
from treeheat.physics.soil_moisture import SoilMoistureBucket
from treeheat.physics.species_params import SpeciesParams, default_species_params, species_params_from_record
from treeheat.io.species import SpeciesDatabase, load_species_database
from treeheat.radiance.upwelling import calculate_upwelling, extract_grid_id_from_column

__all__ = [
    "BiophysicalScenarioRunner",
    "biophysical_output_path",
    "load_biophysical_results",
    "run_biophysical_scenario",
    "run_biophysical_scenarios",
]


def _normalize_tree_points(df: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "x_coord": "xcoord",
        "y_coord": "ycoord",
        "z_coord": "zcoord",
    }
    return df.rename(columns={k: v for k, v in rename.items() if k in df.columns})


def _normalize_sensor_points(df: pd.DataFrame) -> pd.DataFrame:
    return _normalize_tree_points(df)


class BiophysicalScenarioRunner:
    """Run hourly biophysical simulation for material scenarios."""

    def __init__(self, cfg: dict[str, Any] | None = None):
        if cfg is None:
            cfg = get_config()
        self.cfg = cfg

        weather_path = get_path("weather_file", cfg)
        self.weather_data = load_epw(weather_path)

        species_db = load_species_database(cfg=cfg)
        self.species_db = species_db
        self.material_db = load_material_database(cfg=cfg)

        tree_points_path = get_path("tree_points_file", cfg)
        self.tree_points = _normalize_tree_points(pd.read_csv(tree_points_path))

        sensor_points_path = get_path("sensor_points_file", cfg)
        self.sensor_points = _normalize_sensor_points(pd.read_csv(sensor_points_path))

        grid_material_path = get_path("grid_material_mapping_file", cfg)
        scenario_grid_path = get_path("scenario_grid_materials_file", cfg)

        # The scenario grid→material table is derived from the baseline mapping +
        # config instructions. Generate it on demand if it has no scenario rows so
        # biophysics can run without a separate manual step.
        from treeheat.pipeline.grid_materials import (
            scenario_rows_present,
            write_scenario_grid_materials,
        )

        if not scenario_rows_present(cfg):
            try:
                out = write_scenario_grid_materials(cfg)
                print(f" - Generated scenario grid materials: {out}")
            except (FileNotFoundError, ValueError) as exc:
                print(f" - Could not generate scenario grid materials: {exc}")

        self.grid_material_mapping = load_grid_material_mapping(
            baseline_csv_path=grid_material_path,
            scenario_csv_path=scenario_grid_path,
        )

        self.ground_model = GroundEnergyBalance(cfg)
        self.soil_model = SoilMoistureBucket(cfg)

        self._build_spatial_index()
        self._extract_tree_svf()

    def _get_default_svf(self) -> float:
        return float(self.cfg["model"]["species_defaults"]["SVF"])

    def _get_default_albedo_emissivity(self) -> tuple[float, float]:
        ceb = self.cfg["model"]["ceb"]
        return float(ceb["albedo_g_default"]), float(ceb["epsilon_g_default"])

    def _get_soil_params(self) -> dict[str, float]:
        soil = self.cfg["model"]["soil"]
        return {
            "theta_init": float(soil["theta_init"]),
            "theta_fc": float(soil["theta_fc"]),
        }

    def _extract_tree_svf(self) -> None:
        self.tree_svf: dict[int, float] = {}
        default_svf = self._get_default_svf()
        svf_col = None
        for col in ("SVF", "svf", "sky_view_factor"):
            if col in self.tree_points.columns:
                svf_col = col
                break

        n_trees = len(self.tree_points)
        if svf_col is not None:
            for tree_idx in range(n_trees):
                svf_val = self.tree_points.iloc[tree_idx][svf_col]
                if pd.isna(svf_val) or svf_val < 0:
                    self.tree_svf[tree_idx] = default_svf
                else:
                    self.tree_svf[tree_idx] = float(min(max(svf_val, 0.0), 1.0))
        else:
            for tree_idx in range(n_trees):
                self.tree_svf[tree_idx] = default_svf

    def _build_spatial_index(self) -> None:
        tree_coords = self.tree_points[["xcoord", "ycoord", "zcoord"]].values
        sensor_coords = self.sensor_points[["xcoord", "ycoord", "zcoord"]].values
        distances = cdist(tree_coords, sensor_coords)
        self.nearest_sensor_indices = np.argmin(distances, axis=1)

        self.sensor_grid_ids: dict[int, str] = {}
        if "grid_name" in self.sensor_points.columns:
            sensor_points_reset = self.sensor_points.reset_index(drop=True)
            for pos_idx in range(len(sensor_points_reset)):
                grid_name = sensor_points_reset.iloc[pos_idx].get("grid_name", "")
                grid_id = extract_grid_id_from_column(str(grid_name))
                if grid_id is not None:
                    self.sensor_grid_ids[pos_idx] = grid_id

    def _resolve_species(self, species_name: str | None) -> SpeciesParams:
        if species_name:
            record = self.species_db.get(species_name)
            if record is not None:
                return species_params_from_record(record, self.cfg)
        return default_species_params(self.cfg)

    def _build_material_cache(
        self,
        scenario_id: str,
        direct_df: pd.DataFrame,
    ) -> dict[int, dict[str, Any]]:
        default_albedo, default_emissivity = self._get_default_albedo_emissivity()
        material_cache: dict[int, dict[str, Any]] = {}
        n_trees = len(self.tree_points)

        for tree_idx in range(n_trees):
            sensor_idx = self.nearest_sensor_indices[tree_idx]
            grid_id = self.sensor_grid_ids.get(sensor_idx)
            if grid_id is None:
                col_name = direct_df.columns[sensor_idx]
                grid_id = extract_grid_id_from_column(str(col_name), self.sensor_points)

            material_name = "generic"
            if grid_id and len(self.grid_material_mapping) > 0:
                try:
                    albedo, emissivity = get_material_properties_for_grid(
                        grid_id,
                        scenario_id,
                        self.grid_material_mapping,
                        self.material_db,
                    )
                    scenario_materials = self.grid_material_mapping[
                        self.grid_material_mapping["scenario_id"] == scenario_id
                    ]
                    grid_mat = scenario_materials[scenario_materials["grid_id"] == grid_id]
                    if not grid_mat.empty:
                        material_name = grid_mat.iloc[0].get("material_name", "generic")
                except Exception:
                    albedo, emissivity = default_albedo, default_emissivity
            else:
                albedo, emissivity = default_albedo, default_emissivity

            ground_type = get_ground_type_from_material(material_name)
            ground_props = self.ground_model.get_ground_properties(
                ground_type, albedo=albedo, emissivity=emissivity
            )
            material_cache[tree_idx] = {
                "albedo": albedo,
                "emissivity": emissivity,
                "ground_type": ground_type,
                "heat_capacity": ground_props["heat_capacity"],
                "evap_factor": ground_props["evap_factor"],
            }
        return material_cache

    def _validate_feather_sensor_alignment(self, direct_df: pd.DataFrame) -> None:
        n_sensors_grid = len(self.sensor_points)
        n_sensors_feather = direct_df.shape[1]
        if n_sensors_grid != n_sensors_feather:
            raise ValueError(
                f"Sensor count mismatch: grid has {n_sensors_grid} sensors but "
                f"feather has {n_sensors_feather} columns. "
                "Use the grid file that matches the raytracing feather outputs."
            )

    def simulate_scenario(
        self,
        scenario_id: str,
        direct_df: pd.DataFrame,
        diffuse_df: pd.DataFrame,
        weather_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Run hourly simulation for all trees in one scenario."""
        if weather_df is None:
            weather_df = self.weather_data

        self._validate_feather_sensor_alignment(direct_df)

        K_up_dir, K_up_dif = calculate_upwelling(
            direct_df,
            diffuse_df,
            self.grid_material_mapping,
            scenario_id,
            self.material_db,
            self.sensor_points,
        )

        direct_arr = direct_df.values
        diffuse_arr = diffuse_df.values
        K_up_dir_arr = K_up_dir.values
        K_up_dif_arr = K_up_dif.values

        soil_params = self._get_soil_params()
        initial_theta = soil_params["theta_init"]
        default_svf = self._get_default_svf()

        if "tree_id" in self.tree_points.columns:
            tree_ids = self.tree_points["tree_id"].values
        elif "number" in self.tree_points.columns:
            tree_ids = self.tree_points["number"].values
        else:
            tree_ids = np.arange(len(self.tree_points))

        if "species" in self.tree_points.columns:
            tree_species = [
                self._resolve_species(name) for name in self.tree_points["species"]
            ]
        else:
            default_sp = default_species_params(self.cfg)
            tree_species = [default_sp] * len(self.tree_points)

        n_trees = len(self.tree_points)
        n_hours = len(direct_df)
        material_cache = self._build_material_cache(scenario_id, direct_df)

        results_dict: dict[str, np.ndarray] = {
            "tree_id": np.empty(n_hours * n_trees, dtype=object),
            "hour": np.empty(n_hours * n_trees, dtype=np.int32),
            "T_leaf": np.empty(n_hours * n_trees, dtype=np.float64),
            "Tg": np.empty(n_hours * n_trees, dtype=np.float64),
            "Tsurf": np.empty(n_hours * n_trees, dtype=np.float64),
            "MRT": np.empty(n_hours * n_trees, dtype=np.float64),
            "ET": np.empty(n_hours * n_trees, dtype=np.float64),
            "LE": np.empty(n_hours * n_trees, dtype=np.float64),
            "H": np.empty(n_hours * n_trees, dtype=np.float64),
            "gc": np.empty(n_hours * n_trees, dtype=np.float64),
            "rs": np.empty(n_hours * n_trees, dtype=np.float64),
            "theta": np.empty(n_hours * n_trees, dtype=np.float64),
            "REW": np.empty(n_hours * n_trees, dtype=np.float64),
            "f_SM": np.empty(n_hours * n_trees, dtype=np.float64),
            "VPD": np.empty(n_hours * n_trees, dtype=np.float64),
            "Kabs": np.empty(n_hours * n_trees, dtype=np.float64),
            "Rn": np.empty(n_hours * n_trees, dtype=np.float64),
        }

        Tg_state = np.full(n_trees, 20.0)
        theta_state = np.full(n_trees, initial_theta)
        result_idx = 0
        first_hour = True

        for row_idx in range(n_hours):
            weather = weather_df.iloc[row_idx]
            hour_of_year = int(weather["hour_of_year"])
            Ta = float(weather["Ta"])
            RH = float(weather["RH"])
            U = float(weather["U"])
            P = float(weather["P"])
            L_sky = float(weather["L_sky"])
            VPD = float(weather["VPD"])
            qa = float(weather["qa"])
            precip_mm = float(weather.get("precip", 0.0)) if "precip" in weather.index else 0.0

            if first_hour:
                Tg_state[:] = Ta + 5.0
                first_hour = False

            for tree_idx in range(n_trees):
                tree_id = tree_ids[tree_idx]
                species = tree_species[tree_idx]
                sensor_idx = self.nearest_sensor_indices[tree_idx]

                E_dir = float(direct_arr[row_idx, sensor_idx])
                E_dif = float(diffuse_arr[row_idx, sensor_idx])
                K_up_dir_val = float(K_up_dir_arr[row_idx, sensor_idx])
                K_up_dif_val = float(K_up_dif_arr[row_idx, sensor_idx])

                mat_props = material_cache[tree_idx]
                tree_svf = self.tree_svf.get(tree_idx, default_svf)

                result = solve_tree_hour(
                    tree_id=tree_id,
                    hour=hour_of_year,
                    Ta=Ta,
                    RH=RH,
                    U=U,
                    P=P,
                    qa=qa,
                    VPD=VPD,
                    L_sky=L_sky,
                    E_dir=E_dir,
                    E_dif=E_dif,
                    K_up_dir=K_up_dir_val,
                    K_up_dif=K_up_dif_val,
                    SVF=tree_svf,
                    albedo=mat_props["albedo"],
                    emissivity=mat_props["emissivity"],
                    heat_capacity=mat_props["heat_capacity"],
                    evap_factor=mat_props["evap_factor"],
                    species=species,
                    Tg_prev=Tg_state[tree_idx],
                    theta_prev=theta_state[tree_idx],
                    precip_mm=precip_mm,
                    cfg=self.cfg,
                    ground_model=self.ground_model,
                    soil_model=self.soil_model,
                )

                Tg_state[tree_idx] = result.Tg
                theta_state[tree_idx] = result.theta

                results_dict["tree_id"][result_idx] = tree_id
                results_dict["hour"][result_idx] = hour_of_year
                results_dict["T_leaf"][result_idx] = result.T_leaf
                results_dict["Tg"][result_idx] = result.Tg
                results_dict["Tsurf"][result_idx] = result.Tsurf
                results_dict["MRT"][result_idx] = result.MRT
                results_dict["ET"][result_idx] = result.ET
                results_dict["LE"][result_idx] = result.LE
                results_dict["H"][result_idx] = result.H
                results_dict["gc"][result_idx] = result.gc
                results_dict["rs"][result_idx] = result.rs
                results_dict["theta"][result_idx] = result.theta
                results_dict["REW"][result_idx] = result.REW
                results_dict["f_SM"][result_idx] = result.f_SM
                results_dict["VPD"][result_idx] = VPD
                results_dict["Kabs"][result_idx] = result.Kabs
                results_dict["Rn"][result_idx] = result.Rn
                result_idx += 1

        return pd.DataFrame(results_dict)


def _load_feather_pair(raytracing_dir: Path, scenario_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    direct_path = raytracing_dir / f"{scenario_id}_direct.feather"
    diffuse_path = raytracing_dir / f"{scenario_id}_diffuse.feather"
    if not direct_path.exists() or not diffuse_path.exists():
        raise FileNotFoundError(f"Missing feather files for {scenario_id} in {raytracing_dir}")

    direct_df = pd.read_feather(direct_path).T
    diffuse_df = pd.read_feather(diffuse_path).T
    return direct_df, diffuse_df


def _warmest_week_slice(
    cfg: dict[str, Any],
) -> tuple[int, int]:
    """Return (start_hour, n_hours) for warmest week in the annual calendar."""
    weather_path = get_path("weather_file", cfg)
    day_of_year, _, _ = find_warmest_day(weather_path)
    start_day, end_day = get_week_around_day(day_of_year)
    warmest_week_start = start_day * 24
    warmest_week_hours = (end_day - start_day + 1) * 24
    return warmest_week_start, warmest_week_hours


def biophysical_output_path(output_dir: Path, scenario_id: str) -> Path:
    return output_dir / f"biophysical_results_{scenario_id}.csv"


def load_biophysical_results(
    cfg: dict[str, Any] | None = None,
    scenario_ids: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Load biophysical CSVs from the configured output directory."""
    if cfg is None:
        cfg = get_config()
    if output_dir is None:
        output_dir = get_path("biophysical_outputs_dir", cfg)
    output_dir = Path(output_dir)

    if scenario_ids is None:
        n = int(cfg.get("simulation", {}).get("n_scenarios", 25))
        scenario_ids = [f"scenario_{i:03d}" for i in range(n)]

    results: dict[str, pd.DataFrame] = {}
    for scenario_id in scenario_ids:
        path = biophysical_output_path(output_dir, scenario_id)
        if path.exists():
            results[scenario_id] = pd.read_csv(path)
    return results


def run_biophysical_scenario(
    scenario_id: str,
    runner: BiophysicalScenarioRunner,
    cfg: dict[str, Any],
    output_dir: Path,
    *,
    raytracing_dir: Path | None = None,
) -> tuple[pd.DataFrame, Path]:
    """Run biophysical simulation for one scenario; returns (results_df, output_path)."""
    if raytracing_dir is None:
        raytracing_dir = get_path("raytracing_results_dir", cfg)

    warmest_week_start, warmest_week_hours = _warmest_week_slice(cfg)
    weather_warmest = runner.weather_data.iloc[
        warmest_week_start : warmest_week_start + warmest_week_hours
    ].copy().reset_index(drop=True)

    direct_df, diffuse_df = _load_feather_pair(raytracing_dir, scenario_id)
    direct_df = direct_df.iloc[
        warmest_week_start : warmest_week_start + warmest_week_hours
    ].copy().reset_index(drop=True)
    diffuse_df = diffuse_df.iloc[
        warmest_week_start : warmest_week_start + warmest_week_hours
    ].copy().reset_index(drop=True)

    results_df = runner.simulate_scenario(
        scenario_id,
        direct_df,
        diffuse_df,
        weather_df=weather_warmest,
    )
    out_path = biophysical_output_path(output_dir, scenario_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(out_path, index=False)
    return results_df, out_path


def run_biophysical_scenarios(
    scenario_ids: list[str] | None = None,
    cfg: dict[str, Any] | None = None,
    output_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Run biophysical simulation for all scenarios using frozen feather inputs."""
    if cfg is None:
        cfg = get_config()

    if scenario_ids is None:
        n = int(cfg.get("simulation", {}).get("n_scenarios", 25))
        scenario_ids = [f"scenario_{i:03d}" for i in range(n)]

    if output_dir is None:
        output_dir = get_path("biophysical_outputs_dir", cfg)
    output_dir = Path(output_dir)

    runner = BiophysicalScenarioRunner(cfg)
    results: dict[str, pd.DataFrame] = {}
    for scenario_id in scenario_ids:
        results_df, _ = run_biophysical_scenario(
            scenario_id, runner, cfg, output_dir
        )
        results[scenario_id] = results_df

    return results
