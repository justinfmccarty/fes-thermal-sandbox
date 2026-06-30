"""Per-scenario Radiance raytracing with material-scenario application.

PORT FROM: src_archive/material_scenario_workflow.py (run_scenario_raytracing,
RadianceProjectManager, three-tier material selection).

pyradiance is imported lazily via treeheat.radiance.runner — optional extra.
The acceptance gate adopts frozen v0 feathers; this module is for fresh runs.
"""

from __future__ import annotations

import hashlib
import os
import random
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from treeheat.config import get_config, get_path
from treeheat.io.materials import MaterialDatabase, load_material_database

__all__ = [
    "NaturalnessMaterialCatalog",
    "RadianceProjectManager",
    "raytrace_feather_paths",
    "raytrace_outputs_exist",
    "run_scenario_raytrace",
]


@dataclass
class _SurfaceMaterial:
    name: str
    naturalness: float
    radiance_def: str


class NaturalnessMaterialCatalog:
    """Naturalness-weighted material selection for scenario generation (v0 port)."""

    def __init__(self, material_db: MaterialDatabase, base_library_path: Path | None = None):
        self._landscape: list[_SurfaceMaterial] = []
        self._facade: list[_SurfaceMaterial] = []
        radiance_defs = _load_radiance_defs(base_library_path) if base_library_path else {}

        for rec in material_db.records:
            albedo = rec.shortwave_albedo
            radiance_def = radiance_defs.get(
                rec.material_name,
                f"void plastic {rec.material_name}\n0\n0\n5 {albedo} {albedo} {albedo} 0.0 0.0",
            )
            mat = _SurfaceMaterial(rec.material_name, rec.naturalness_score, radiance_def)
            if rec.ground_applicable:
                self._landscape.append(mat)
            if rec.facade_applicable:
                self._facade.append(mat)

    def _pool(self, surface_type: str) -> list[_SurfaceMaterial]:
        return self._landscape if surface_type == "landscape" else self._facade

    def get_least_natural(self, surface_type: str) -> str:
        pool = self._pool(surface_type)
        if not pool:
            raise ValueError(f"No materials for surface_type={surface_type}")
        return min(pool, key=lambda m: m.naturalness).name

    def get_material_with_naturalness(
        self, name: str, surface_type: str
    ) -> tuple[str, float]:
        for m in self._pool(surface_type):
            if m.name == name:
                return m.name, m.naturalness
        raise ValueError(f"Material {name!r} not found for {surface_type}")

    def get_most_natural(self, surface_type: str) -> tuple[str, float]:
        pool = self._pool(surface_type)
        if not pool:
            raise ValueError(f"No materials for surface_type={surface_type}")
        best = max(pool, key=lambda m: m.naturalness)
        return best.name, best.naturalness

    def get_radiance_def(self, name: str) -> str | None:
        for pool in (self._landscape, self._facade):
            for m in pool:
                if m.name == name:
                    return m.radiance_def
        return None

    def calculate_three_tier_coverage(
        self, target_naturalness: float, surface_type: str
    ) -> tuple[str, str, float]:
        """Three-tier interpolation (black_brick/short_grass/tall_grass pattern from v0)."""
        least_name = self.get_least_natural(surface_type)
        n_low = next(
            m.naturalness for m in self._pool(surface_type) if m.name == least_name
        )

        try:
            mid_name, n_mid = self.get_material_with_naturalness("short_grass", surface_type)
        except ValueError:
            pool = self._pool(surface_type)
            mid = min(pool, key=lambda m: abs(m.naturalness - 0.95))
            mid_name, n_mid = mid.name, mid.naturalness

        try:
            most_name, n_high = self.get_material_with_naturalness("tall_grass", surface_type)
        except ValueError:
            most_name, n_high = self.get_most_natural(surface_type)

        target = max(n_low, min(n_high, target_naturalness))

        if target <= n_mid:
            lower_mat, upper_mat = least_name, mid_name
            upper_coverage = (
                1.0 if n_mid == n_low else (target - n_low) / (n_mid - n_low)
            )
        else:
            lower_mat, upper_mat = mid_name, most_name
            upper_coverage = (
                1.0 if n_high == n_mid else (target - n_mid) / (n_high - n_mid)
            )

        return lower_mat, upper_mat, max(0.0, min(1.0, upper_coverage))


def _load_radiance_defs(base_library_path: Path) -> dict[str, str]:
    """Parse base_material_library.txt into material_name -> radiance definition."""
    if not base_library_path.exists():
        return {}
    radiance_defs: dict[str, str] = {}
    lines = base_library_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("void"):
            parts = line.split()
            if len(parts) >= 3:
                name = parts[2]
                def_lines = [lines[j].rstrip() for j in range(i, min(i + 4, len(lines)))]
                radiance_defs[name] = "\n".join(def_lines)
                i += 4
                continue
        i += 1
    return radiance_defs


class RadianceProjectManager:
    """Temporary working copies for scenario raytracing (baseline never modified)."""

    def __init__(
        self,
        baseline_project_dir: str | Path,
        scenario_project_dir: str | Path | None = None,
        radiance_surface_key: str = "",
        temp_work_dir: str | Path | None = None,
    ):
        self.baseline_project_dir = str(baseline_project_dir)
        self.scenario_project_dir = str(scenario_project_dir or baseline_project_dir)
        self.radiance_surface_key = radiance_surface_key
        self.baseline_scene_base = self._scene_base(self.baseline_project_dir)

        if temp_work_dir is None:
            self.temp_work_dir = tempfile.mkdtemp(prefix="radiance_scenario_")
        else:
            self.temp_work_dir = str(temp_work_dir)
            os.makedirs(self.temp_work_dir, exist_ok=True)
        self.current_work_dir: str | None = None

    def _scene_base(self, project_dir: str) -> str:
        if self.radiance_surface_key:
            return os.path.join(project_dir, self.radiance_surface_key, "model")
        model_sub = os.path.join(project_dir, "model")
        return model_sub if os.path.isdir(model_sub) else project_dir

    def _work_scene_base(self) -> str:
        if self.current_work_dir is None:
            raise RuntimeError("No working copy. Call create_working_copy() first.")
        if self.radiance_surface_key:
            return os.path.join(self.current_work_dir, self.radiance_surface_key)
        return self.current_work_dir

    def create_working_copy(self, scenario_id: str) -> str:
        self.current_work_dir = os.path.join(self.temp_work_dir, scenario_id)
        if os.path.exists(self.current_work_dir):
            shutil.rmtree(self.current_work_dir)
        shutil.copytree(self.scenario_project_dir, self.current_work_dir)
        if os.path.exists(os.path.join(self.current_work_dir, "model")):
            self.current_work_dir = os.path.join(self.current_work_dir, "model")
        return self.current_work_dir

    def cleanup_working_copy(self) -> None:
        if self.current_work_dir and os.path.exists(self.current_work_dir):
            shutil.rmtree(self.current_work_dir)
            self.current_work_dir = None

    def identify_surfaces(self) -> dict[str, list[str]]:
        surfaces: dict[str, list[str]] = {"landscape": [], "facade": []}
        geometry_file = os.path.join(self.baseline_scene_base, "scene", "envelope.rad")
        with open(geometry_file, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split()
                if len(parts) < 3 or parts[1] != "polygon":
                    continue
                surface_id = parts[2]
                sid_lower = surface_id.lower()
                if any(k in sid_lower for k in ("ground", "terrain", "pavement", "landscape", "grass")):
                    surfaces["landscape"].append(surface_id)
                elif any(k in sid_lower for k in ("wall", "facade", "building")):
                    surfaces["facade"].append(surface_id)
                else:
                    surfaces["facade"].append(surface_id)
        return surfaces

    def apply_material_scenario(
        self,
        instruction: tuple[float, float],
        catalog: NaturalnessMaterialCatalog,
        surfaces: dict[str, list[str]],
        scenario_id: str,
    ) -> None:
        if self.current_work_dir is None:
            raise RuntimeError("No working copy. Call create_working_copy() first.")

        seed = int(hashlib.md5(scenario_id.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)

        landscape_ratio, facade_ratio = instruction
        work_scene = self._work_scene_base()
        geometry_file = os.path.join(work_scene, "scene", "envelope.rad")
        material_file = os.path.join(work_scene, "scene", "envelope.mat")

        baseline_geometry = os.path.join(self.baseline_scene_base, "scene", "envelope.rad")
        with open(baseline_geometry, encoding="utf-8") as handle:
            geom_lines = handle.readlines()

        landscape_lower, landscape_upper, landscape_upper_cov = catalog.calculate_three_tier_coverage(
            landscape_ratio, "landscape"
        )
        facade_lower, facade_upper, facade_upper_cov = catalog.calculate_three_tier_coverage(
            facade_ratio, "facade"
        )

        n_landscape = len(surfaces["landscape"])
        n_facade = len(surfaces["facade"])
        n_landscape_upper = int(n_landscape * landscape_upper_cov)
        n_facade_upper = int(n_facade * facade_upper_cov)

        landscape_upper_surfaces = (
            random.sample(surfaces["landscape"], n_landscape_upper)
            if n_landscape_upper > 0
            else []
        )
        landscape_lower_surfaces = [
            s for s in surfaces["landscape"] if s not in landscape_upper_surfaces
        ]
        facade_upper_surfaces = (
            random.sample(surfaces["facade"], n_facade_upper) if n_facade_upper > 0 else []
        )
        facade_lower_surfaces = [
            s for s in surfaces["facade"] if s not in facade_upper_surfaces
        ]

        modified: list[str] = []
        for line in geom_lines:
            modified_line = line
            for surface_id in landscape_upper_surfaces:
                if surface_id in line:
                    parts = line.split()
                    parts[0] = landscape_upper
                    modified_line = " ".join(parts) + "\n"
                    break
            if modified_line == line:
                for surface_id in landscape_lower_surfaces:
                    if surface_id in line:
                        parts = line.split()
                        parts[0] = landscape_lower
                        modified_line = " ".join(parts) + "\n"
                        break
            if modified_line == line:
                for surface_id in facade_upper_surfaces:
                    if surface_id in line:
                        parts = line.split()
                        parts[0] = facade_upper
                        modified_line = " ".join(parts) + "\n"
                        break
            if modified_line == line:
                for surface_id in facade_lower_surfaces:
                    if surface_id in line:
                        parts = line.split()
                        parts[0] = facade_lower
                        modified_line = " ".join(parts) + "\n"
                        break
            modified.append(modified_line)

        with open(geometry_file, "w", encoding="utf-8") as handle:
            handle.writelines(modified)

        materials_needed = list(
            {landscape_upper, landscape_lower, facade_upper, facade_lower}
        )
        self._ensure_materials(catalog, materials_needed, material_file)

    def _ensure_materials(
        self,
        catalog: NaturalnessMaterialCatalog,
        material_names: list[str],
        material_file: str,
    ) -> None:
        with open(material_file, encoding="utf-8") as handle:
            content = handle.read()
        defined = self._defined_material_names(content)
        to_add = []
        for name in material_names:
            mat_def = catalog.get_radiance_def(name)
            if mat_def and name not in defined:
                to_add.append(mat_def)
        if to_add:
            with open(material_file, "a", encoding="utf-8") as handle:
                handle.write("\n" + "\n".join(to_add) + "\n")

    @staticmethod
    def _defined_material_names(content: str) -> set[str]:
        """Identifiers already declared in a Radiance material file.

        A primitive declaration header is ``modifier type identifier``; the
        identifier is the third token. We match against that rather than a
        substring so a material literally named ``glass`` is not mistaken for
        being defined by ``void glass conifer`` (where ``glass`` is the type).
        """
        defined: set[str] = set()
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) == 3 and not parts[0][0].isdigit():
                defined.add(parts[2])
        return defined


def raytrace_feather_paths(raytracing_dir: Path, scenario_id: str) -> tuple[Path, Path]:
    direct = raytracing_dir / f"{scenario_id}_direct.feather"
    diffuse = raytracing_dir / f"{scenario_id}_diffuse.feather"
    return direct, diffuse


def raytrace_outputs_exist(raytracing_dir: Path, scenario_id: str) -> bool:
    direct, diffuse = raytrace_feather_paths(raytracing_dir, scenario_id)
    return direct.exists() and diffuse.exists()


def run_scenario_raytrace(
    scenario_id: str,
    instruction: tuple[float, float],
    cfg: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> list[Path]:
    """Run Radiance 2-phase DDS for one scenario; save direct/diffuse feather files."""
    if cfg is None:
        cfg = get_config()

    sim = cfg.get("simulation", {})
    raytracing_dir = Path(get_path("raytracing_results_dir", cfg))
    raytracing_dir.mkdir(parents=True, exist_ok=True)

    direct_path, diffuse_path = raytrace_feather_paths(raytracing_dir, scenario_id)
    if not force and raytrace_outputs_exist(raytracing_dir, scenario_id):
        return [direct_path, diffuse_path]

    from treeheat.radiance.runner import ill_to_df, run_2phase_dds

    material_db = load_material_database(cfg=cfg)
    mat_path = get_path("material_database_file", cfg)
    base_lib = mat_path.parent / "base_material_library.txt"
    catalog = NaturalnessMaterialCatalog(material_db, base_lib)

    baseline_dir = get_path("baseline_project_dir", cfg)
    scenario_dir = get_path("scenario_project_dir", cfg)
    surface_key = sim.get("surface_key", "")
    weather_file = str(get_path("weather_file", cfg))
    start_hour_offset = 0

    project_manager = RadianceProjectManager(
        baseline_project_dir=baseline_dir,
        scenario_project_dir=scenario_dir,
        radiance_surface_key=surface_key,
    )

    work_dir = project_manager.create_working_copy(scenario_id)
    surfaces = project_manager.identify_surfaces()
    project_manager.apply_material_scenario(instruction, catalog, surfaces, scenario_id)

    run_2phase_dds(
        radiance_project_dir=work_dir,
        radiance_surface_key=surface_key,
        scenario_tmy=weather_file,
        n_workers=sim.get("n_workers"),
        use_accelerad=sim.get("use_accelerad", False),
        sky_resolution=sim.get("sky_resolution", 1),
        filter_daylight_only=True,
        hour_offset=start_hour_offset,
        rcontrib_rad_params="-ad 256 -lw 1.0e-3 -dc 1 -dt 0 -dj 0",
        rflux_rad_params="-lw 6.67e-07 -ab 5 -ad 15000",
    )

    direct_df, diffuse_df = ill_to_df(work_dir, surface_key)
    import pyarrow.feather as feather

    feather.write_feather(direct_df, str(direct_path), compression="lz4")
    feather.write_feather(diffuse_df, str(diffuse_path), compression="lz4")
    project_manager.cleanup_working_copy()
    return [direct_path, diffuse_path]
