"""Radiance 2-phase DDS annual irradiance.

PORT FROM: src_archive/radiance.py (pyradiance)

pyradiance is imported lazily — optional dependency (treeheat[radiance]).
The workflow follows these steps:

1. Part 0: Convert EPW weather file to WEA format
2. Part 1: Calculate total irradiance (sky + direct + indirect)
3. Part 2: Calculate direct irradiance only
4. Part 3: Calculate sun coefficients for direct solar contribution

The folder structure expected:
    radiance_project_dir/
        {radiance_surface_key}/
            model/
                scene/
                    envelope.mat
                    envelope.rad
                    skyglow.rad (created automatically with specified resolution)
                    suns.rad (created for Part 3)
                aperture/
                    aperture.mat (optional)
                    aperture.rad (optional)
                grid/
                    *.pts (sensor grid files)
            outputs/
                octree/
                    total.oct
                    direct.oct
                    sun.oct
                matrices/
                    total_illum.mtx
                    direct_illum.mtx
                    sun_illum.mtx
                    sky_total.smx
                    sky_direct.smx
                    sky_sun.smx
                results/
                    result_total.ill
                    result_direct.ill
                    result_sun.ill
"""

import os
import glob
import pathlib
import time
import subprocess
import shutil
from typing import Optional, Tuple
import numpy as np
import pandas as pd

_pr = None


def _get_pyradiance():
    """Lazy import of pyradiance (optional dependency)."""
    global _pr
    if _pr is None:
        try:
            import pyradiance as pr  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "pyradiance is not installed. Install with: uv sync --extra radiance"
            ) from exc
        _pr = pr
    return _pr


def find_accelerad_command(cmd_name: str) -> Optional[str]:
    """
    Find Accelerad command in system PATH or common installation locations.
    
    Args:
        cmd_name: Command name (e.g., "accelerad_rfluxmtx" or "accelerad_rcontrib")
        
    Returns:
        Full path to command if found, None otherwise
    """
    # Check common Windows installation path
    windows_paths = [
        r"C:\Program Files\Accelerad\bin",
        r"C:\Program Files (x86)\Accelerad\bin",
    ]
    
    for base_path in windows_paths:
        cmd_path = os.path.join(base_path, f"{cmd_name}.exe")
        if os.path.exists(cmd_path):
            return cmd_path
    
    # Check if command is in PATH
    cmd_path = shutil.which(cmd_name)
    if cmd_path:
        return cmd_path
    
    # Check if command is in PATH with .exe extension (Windows)
    cmd_path = shutil.which(f"{cmd_name}.exe")
    if cmd_path:
        return cmd_path
    
    return None


def accelerad_available() -> bool:
    """True only if both Accelerad commands resolve on this machine."""
    return (
        find_accelerad_command("accelerad_rfluxmtx") is not None
        and find_accelerad_command("accelerad_rcontrib") is not None
    )


def resolve_accelerad(use_accelerad: bool) -> bool:
    """Honor the request only if Accelerad is actually installed.

    Accelerad is a niche GPU build of Radiance that most users do not have.
    Rather than aborting a run when it is requested but missing, we warn once
    and fall back to the standard Radiance tools (bundled with pyradiance).
    """
    if use_accelerad and not accelerad_available():
        print(
            "   ⚠️  Accelerad requested but 'accelerad_rfluxmtx'/'accelerad_rcontrib' "
            "were not found in PATH. Falling back to standard Radiance "
            "(set simulation.use_accelerad: false to silence this)."
        )
        return False
    return use_accelerad


def get_radiance_paths(radiance_project_dir: str, radiance_surface_key: str) -> Tuple[str, str]:
    """
    Get radiance_surface_dir and scene_base paths, handling empty surface_key.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier (can be empty string)
        
    Returns:
        Tuple of (radiance_surface_dir, scene_base)
    """
    if radiance_surface_key:
        radiance_surface_dir = os.path.join(radiance_project_dir, radiance_surface_key)
        scene_base = os.path.join(radiance_surface_dir, "model")
    else:
        radiance_surface_dir = radiance_project_dir
        scene_base = radiance_surface_dir
    
    return radiance_surface_dir, scene_base


def change_plastic_material(
    og_material_fp: str, blk_material_fp: str, line_idx: int, item_idx: int, new_name: str
) -> None:
    """
    Modify a plastic material file to change a specific material property to 'black'.
    
    Args:
        og_material_fp: Path to original material file
        blk_material_fp: Path to output black material file
        line_idx: Line index to modify (0-indexed)
        item_idx: Item index within the line to modify
        new_name: New value to insert (typically 'black')
    """
    with open(og_material_fp, "r", encoding="utf-8") as fp:
        material_lines = fp.readlines()

    new_line = []
    for n, i in enumerate(material_lines[line_idx].split(" ")):
        if n == item_idx:
            new_line.append(new_name)
        else:
            new_line.append(i)
    new_line = " ".join(new_line) + "\n"
    material_lines[line_idx] = new_line

    with open(blk_material_fp, "w", encoding="utf-8") as fp:
        fp.writelines(material_lines)


def create_black_objects(input_f: str, output_f: str) -> None:
    """
    Create black version of geometry file by replacing material names with 'black'.
    This matches the approach where materials are changed to 'black' in the material file.
    
    Args:
        input_f: Path to input geometry file
        output_f: Path to output black geometry file
    """
    # Read the input file and replace material names with 'black' on geometry lines
    with open(input_f, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
    
    with open(output_f, "w", encoding="utf-8") as fp:
        for line in lines:
            stripped = line.strip()
            # Skip comments, void statements, empty lines, and lines already starting with !
            if not stripped or stripped.startswith("#") or stripped.startswith("void") or stripped.startswith("!"):
                fp.write(line)
            else:
                # Check if this is a geometry primitive line (material_name geometry_type ...)
                parts = stripped.split()
                # Geometry lines typically have: material_name geometry_type modifier_count modifier_list vertex_count vertices...
                # Common geometry types: polygon, sphere, ring, cylinder, cone, mesh, instance, etc.
                geometry_types = ["polygon", "sphere", "ring", "cylinder", "cone", "mesh", "instance", "prism", "tube", "cup"]
                if len(parts) >= 2 and parts[1] in geometry_types:
                    # Replace the material name (first part) with 'black'
                    parts[0] = "black"
                    fp.write(" ".join(parts) + "\n")
                else:
                    # Not a geometry line, write as-is
                    fp.write(line)


def create_skyglow(dst: str, resolution: int = 1) -> None:
    """
    Create a skyglow file with specified resolution on-the-fly.
    
    Args:
        dst: Path where to save the new skyglow file
        resolution: Integer from 1 to 6 determining sky subdivisions (1 = Tregenza sky)
    """
    skyglow_content = f"""#@rfluxmtx u=+Y h=u
void glow groundglow
0
0
4 1 1 1 0

groundglow source ground
0
0
4 0 0 -1 180

#@rfluxmtx u=+Y h=r{resolution}
void glow skyglow
0
0
4 1 1 1 0

skyglow source skydome
0
0
4 0 0 1 180
"""

    with open(dst, "w", encoding="utf-8") as fp:
        fp.write(skyglow_content)


def create_primitive_sun(radiance_project_dir: str, radiance_surface_key: str) -> str:
    """
    Create a primitive sun light source file.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        
    Returns:
        Path to created suns.rad file
    """
    _, scene_base = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    scene_dir = os.path.join(scene_base, "scene")
    output_file = os.path.join(scene_dir, "suns.rad")
    write_line = "void light solar 0 0 3 1e6 1e6 1e6\n"

    with open(output_file, "w", encoding="utf-8") as file:
        file.write(write_line)

    return output_file


def build_octree(
    radiance_project_dir: str,
    radiance_surface_key: str,
    step: str,
    output_octree: str
) -> None:
    """
    Build octree file using oconv for the specified step.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        step: One of 'total', 'direct', or 'sun'
        output_octree: Path to output octree file
    """
    # Handle case where radiance_surface_key is empty (model/ already in project_dir)
    if radiance_surface_key:
        radiance_surface_dir = os.path.join(radiance_project_dir, radiance_surface_key)
        scene_base = os.path.join(radiance_surface_dir, "model")
    else:
        radiance_surface_dir = radiance_project_dir
        scene_base = radiance_surface_dir
    
    object_material_file = os.path.join(
        scene_base, "scene", "envelope.mat"
    )
    black_object_material_file = os.path.join(
        scene_base, "scene", "envelope.blk"
    )
    
    object_file = os.path.join(scene_base, "scene", "envelope.rad")
    black_object_file = os.path.join(
        scene_base, "scene", "envelope_black.rad"
    )
    
    glazing_material_file = os.path.join(
        scene_base, "aperture", "aperture.mat"
    )
    
    sun_file = os.path.join(scene_base, "scene", "suns.rad")
    
    # Prepare input files list
    input_files = []
    
    if step == "total":
        # Use normal materials and objects
        if os.path.exists(glazing_material_file):
            change_plastic_material(
                object_material_file, black_object_material_file, 0, 2, "black"
            )
            create_black_objects(object_file, black_object_file)
            input_files = [
                object_material_file,
                object_file,
                glazing_material_file,
                os.path.join(scene_base, "aperture", "aperture.rad"),
            ]
        else:
            input_files = [object_material_file, object_file]
            
    elif step == "direct":
        # Use black materials for objects, normal for glazing
        change_plastic_material(
            object_material_file, black_object_material_file, 0, 2, "black"
        )
        create_black_objects(object_file, black_object_file)
        
        if os.path.exists(glazing_material_file):
            black_glazing_material_file = os.path.join(
                radiance_surface_dir, "model", "aperture", "aperture.blk"
            )
            change_plastic_material(
                glazing_material_file, black_glazing_material_file, 0, 2, "black"
            )
            glazing_file = os.path.join(
                scene_base, "aperture", "aperture.rad"
            )
            black_glazing_file = os.path.join(
                scene_base, "aperture", "aperture_black.rad"
            )
            create_black_objects(glazing_file, black_glazing_file)
            input_files = [
                black_object_material_file,
                black_object_file,
                glazing_material_file,
                glazing_file,
            ]
        else:
            input_files = [black_object_material_file, black_object_file]
            
    elif step == "sun":
        # Use black materials and include sun file
        change_plastic_material(
            object_material_file, black_object_material_file, 0, 2, "black"
        )
        create_black_objects(object_file, black_object_file)
        
        if not os.path.exists(sun_file):
            raise FileNotFoundError(
                "The file 'suns.rad' is missing. This should be created before running sun step."
            )
        
        if os.path.exists(glazing_material_file):
            input_files = [
                "-f",
                black_object_material_file,
                black_object_file,
                sun_file,
                glazing_material_file,
                os.path.join(scene_base, "aperture", "aperture.rad"),
            ]
        else:
            input_files = ["-f", black_object_material_file, black_object_file, sun_file]
    else:
        raise ValueError("Arg 'step' must be specified as 'total', 'direct', or 'sun'")
    
    # Run oconv using pyradiance - returns bytes, write to file
    octree_bytes = _get_pyradiance().oconv(*input_files)
    with open(output_octree, "wb") as fp:
        fp.write(octree_bytes)


def run_rfluxmtx(
    radiance_project_dir: str,
    radiance_surface_key: str,
    step: str,
    use_accelerad: bool = False,
    n_workers: Optional[int] = None,
    rad_params: Optional[str] = None,
    sky_resolution: int = 1,
) -> Tuple[str, str]:
    """
    Run rfluxmtx to create flux matrix for total or direct irradiance.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        step: Either 'total' or 'direct'
        use_accelerad: Whether to use accelerad_rfluxmtx instead of rfluxmtx
        n_workers: Number of parallel workers (defaults to CPU count - 1)
        rad_params: Radiance parameters as string (e.g., "-lw 0.0001 -ab 5 -ad 10000")
        sky_resolution: Integer from 1 to 6 determining sky subdivisions (1 = Tregenza sky)
        
    Returns:
        Tuple of (output_matrix_file, grid_file)
    """
    if step not in ["total", "direct"]:
        raise ValueError("Arg 'step' must be specified as 'total' or 'direct'")

    use_accelerad = resolve_accelerad(use_accelerad)

    radiance_surface_dir, scene_base = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    output_dir = os.path.join(radiance_surface_dir, "outputs", "matrices")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create skyglow file on-the-fly if it doesn't exist
    skyglow_file = os.path.join(scene_base, "scene", "skyglow.rad")
    if not os.path.exists(skyglow_file):
        create_skyglow(skyglow_file, resolution=sky_resolution)
    
    # Determine octree file
    oct_dir = os.path.join(radiance_surface_dir, "outputs", "octree")
    if step == "total":
        octree_file = os.path.join(oct_dir, "total.oct")
        output_file = os.path.join(output_dir, "total_illum.mtx")
    else:  # direct
        octree_file = os.path.join(oct_dir, "direct.oct")
        output_file = os.path.join(output_dir, "direct_illum.mtx")
    
    # Find grid file
    grid_files = glob.glob(os.path.join(scene_base, "grid", "*.pts"))
    if not grid_files:
        raise FileNotFoundError(f"No grid files found in {os.path.join(scene_base, 'grid')}/")
    grid_file = grid_files[0]
    
    # Count lines in grid file
    try:
        line_count = int(grid_file.split("_")[-1].split("s")[0])
    except ValueError:
        with open(grid_file, "r", encoding="utf-8") as fp:
            line_count = len(fp.readlines())
    
    # Set default parameters
    if n_workers is None:
        n_workers = os.cpu_count() - 1 if os.cpu_count() else 1
    
    if rad_params is None:
        rad_params = "-lw 0.0001 -ab 5 -ad 10000"
    
    # Parse rad_params
    rp_list = rad_params.split()
    
    # Modify -ab for direct step
    if step == "direct":
        for n, p in enumerate(rp_list):
            if p == "-ab":
                rp_list[n + 1] = "1"
                break
    
    # Build command for rfluxmtx using subprocess to match original implementation
    # Format: rfluxmtx -I+ -y <line_count> -n <n_workers> <rad_params> - <skyglow_file> -i <octree_file> < <grid_file> > <output_file>
    if use_accelerad:
        # Use bare command name (not full path) so Accelerad can find its RAYPATH.
        # Availability is already guaranteed by resolve_accelerad() above.
        cmd_name = "accelerad_rfluxmtx"
        cmd_path = cmd_name  # Use bare name, not full path
    else:
        cmd_name = "rfluxmtx"
        cmd_path = os.path.join(_get_pyradiance().BINPATH, cmd_name) if os.path.exists(os.path.join(_get_pyradiance().BINPATH, cmd_name)) else cmd_name
    
    cmd = [cmd_path]
    cmd.extend(["-I+", "-y", str(int(line_count)), "-n", str(int(n_workers))])
    cmd.extend(rp_list)
    cmd.extend(["-", skyglow_file, "-i", octree_file])
    
    # Verify files exist before running
    if not os.path.exists(grid_file):
        raise FileNotFoundError(f"Grid file not found: {grid_file}")
    if not os.path.exists(skyglow_file):
        raise FileNotFoundError(f"Skyglow file not found: {skyglow_file}")
    if not os.path.exists(octree_file):
        raise FileNotFoundError(f"Octree file not found: {octree_file}")
    
    # Run rfluxmtx with grid file as stdin
    # Set up environment for Accelerad if needed
    env = None
    if use_accelerad:
        # Accelerad needs RAYPATH to find PTX files
        env = os.environ.copy()
        # Try common Accelerad library locations
        accelerad_lib_paths = [
            r"C:\Program Files\Accelerad\lib",
            r"C:\Program Files (x86)\Accelerad\lib",
        ]
        # Also check relative to bin directory
        accelerad_bin = find_accelerad_command("accelerad_rfluxmtx")
        if accelerad_bin:
            bin_dir = os.path.dirname(accelerad_bin)
            parent_dir = os.path.dirname(bin_dir)
            lib_path = os.path.join(parent_dir, "lib")
            if os.path.exists(lib_path):
                accelerad_lib_paths.insert(0, lib_path)
        
        # Find first existing lib directory
        raypath_value = None
        for lib_path in accelerad_lib_paths:
            if os.path.exists(lib_path):
                raypath_value = lib_path
                break
        
        if raypath_value:
            # Debug: Check if PTX files actually exist
            ptx_files = glob.glob(os.path.join(raypath_value, "*.ptx"))
            print(f"   Debug: RAYPATH will be set to: {raypath_value}")
            print(f"   Debug: Found {len(ptx_files)} PTX files in lib directory")
            if ptx_files:
                ptx_names = [os.path.basename(f) for f in ptx_files]
                print(f"   Debug: PTX files found: {', '.join(ptx_names[:5])}{'...' if len(ptx_names) > 5 else ''}")
                # Check specifically for rcontrib.ptx
                rcontrib_ptx = os.path.join(raypath_value, "rcontrib.ptx")
                if os.path.exists(rcontrib_ptx):
                    print(f"   ✓ Found rcontrib.ptx at: {rcontrib_ptx}")
                else:
                    print(f"   ⚠️  Warning: rcontrib.ptx NOT found at expected location: {rcontrib_ptx}")
            else:
                print(f"   ⚠️  Warning: No PTX files found in {raypath_value}")
            
            # Add to existing RAYPATH or create new
            existing_raypath = env.get("RAYPATH", "")
            if existing_raypath:
                env["RAYPATH"] = f"{raypath_value}:{existing_raypath}" if os.name != 'nt' else f"{raypath_value};{existing_raypath}"
            else:
                env["RAYPATH"] = raypath_value
            
            print(f"   Debug: Final RAYPATH environment variable: {env.get('RAYPATH', 'NOT SET')}")
        else:
            print(f"   ⚠️  Warning: Could not find Accelerad lib directory for RAYPATH")
            # Still create env copy even if we can't find lib, in case system RAYPATH is set
            env = os.environ.copy()
    
    # Ensure env is set (use system environment if not using Accelerad)
    if env is None:
        env = os.environ.copy()
    
    with open(grid_file, "rb") as stdin_fp:
        with open(output_file, "wb") as stdout_fp:
            result = subprocess.run(
                cmd,
                stdin=stdin_fp,
                stdout=stdout_fp,
                stderr=subprocess.PIPE,
                env=env,  # Pass environment with RAYPATH
                check=False  # Don't raise immediately, capture error first
            )
            
            if result.returncode != 0:
                # Capture stderr for better error messages
                stderr_text = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error message available"
                # Print detailed error information
                print(f"\n❌ Accelerad/rfluxmtx failed with exit code {result.returncode}")
                print(f"   Command: {' '.join(cmd)}")
                print(f"   Grid file: {grid_file} (exists: {os.path.exists(grid_file)})")
                print(f"   Skyglow file: {skyglow_file} (exists: {os.path.exists(skyglow_file)})")
                print(f"   Octree file: {octree_file} (exists: {os.path.exists(octree_file)})")
                print(f"   Output file: {output_file}")
                if stderr_text.strip():
                    print(f"   Error output:\n{stderr_text}")
                else:
                    print(f"   No error message from Accelerad (exit code {result.returncode})")
                    print(f"   This might indicate:")
                    print(f"     - GPU/driver compatibility issue")
                    print(f"     - Invalid octree file")
                    print(f"     - File access permission issue")
                
                # Raise with detailed message
                error_msg = (
                    f"Accelerad command failed (exit code {result.returncode}). "
                    f"See details above. Error: {stderr_text[:200] if stderr_text else 'No error message'}"
                )
                raise RuntimeError(error_msg) from subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    
    return output_file, grid_file


def run_gendaymtx(
    radiance_project_dir: str,
    radiance_surface_key: str,
    wea_file: str,
    step: str,
) -> str:
    """
    Generate sky matrix using gendaymtx.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        wea_file: Path to WEA weather file
        step: One of 'total', 'direct', or 'sun'
        
    Returns:
        Path to output sky matrix file
    """
    radiance_surface_dir = os.path.join(radiance_project_dir, radiance_surface_key)
    output_dir = os.path.join(radiance_surface_dir, "outputs", "matrices")
    
    # Use subprocess for gendaymtx to match original implementation exactly
    gendaymtx_path = os.path.join(_get_pyradiance().BINPATH, "gendaymtx")
    
    if step == "total":
        output_file = os.path.join(output_dir, "sky_total.smx")
        cmd = [gendaymtx_path, "-m", "1", wea_file]
    elif step == "direct":
        output_file = os.path.join(output_dir, "sky_direct.smx")
        cmd = [gendaymtx_path, "-m", "1", "-d", wea_file]
    elif step == "sun":
        output_file = os.path.join(output_dir, "sky_sun.smx")
        cmd = [gendaymtx_path, "-5", "0.533", "-d", "-m", "6", wea_file]
    else:
        raise ValueError("Arg 'step' must be specified as 'total', 'direct', or 'sun'")
    
    # Run gendaymtx
    with open(output_file, "wb") as stdout_fp:
        subprocess.run(
            cmd,
            stdout=stdout_fp,
            stderr=subprocess.PIPE,
            check=True
        )
    
    return output_file


def run_dctimestep_rmtxop(
    radiance_project_dir: str,
    radiance_surface_key: str,
    step: str,
    daylight_mask: Optional[np.ndarray] = None,
) -> str:
    """
    Run dctimestep piped to rmtxop to combine matrices and convert to illuminance.
    If daylight_mask is provided, expands results back to 8760 timesteps with zeros for nighttime.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        step: One of 'total', 'direct', or 'sun'
        daylight_mask: Optional boolean array of shape (8760,) indicating daylight hours
        
    Returns:
        Path to output illuminance file
    """
    radiance_surface_dir = os.path.join(radiance_project_dir, radiance_surface_key)
    matrices_dir = os.path.join(radiance_surface_dir, "outputs", "matrices")
    output_dir = os.path.join(radiance_surface_dir, "outputs", "results")
    os.makedirs(output_dir, exist_ok=True)
    
    if step == "total":
        input_matrix = os.path.join(matrices_dir, "total_illum.mtx")
        input_sky = os.path.join(matrices_dir, "sky_total.smx")
        output_file = os.path.join(output_dir, "result_total.ill")
    elif step == "direct":
        input_matrix = os.path.join(matrices_dir, "direct_illum.mtx")
        input_sky = os.path.join(matrices_dir, "sky_direct.smx")
        output_file = os.path.join(output_dir, "result_direct.ill")
    elif step == "sun":
        input_matrix = os.path.join(matrices_dir, "sun_illum.mtx")
        input_sky = os.path.join(matrices_dir, "sky_sun.smx")
        output_file = os.path.join(output_dir, "result_sun.ill")
    else:
        raise ValueError("Arg 'step' must be specified as 'total', 'direct', or 'sun'")
    
    # Run dctimestep - returns bytes
    dctimestep_output_bytes = _get_pyradiance().dctimestep(input_matrix, input_sky)

    # Run rmtxop with conversion coefficients (47.4, 119.9, 11.6) for RGB to lux
    result_bytes = _get_pyradiance().rmtxop(
        inp=dctimestep_output_bytes,
        outform='a',  # -fa flag
        transpose=True,  # -t flag
        transform=[47.4, 119.9, 11.6]  # -c 47.4 119.9 11.6
    )
    
    # If daylight_mask is provided, expand results back to 8760 timesteps
    if daylight_mask is not None:
        # Parse the result to get dimensions and data
        result_str = result_bytes.decode('utf-8')
        result_lines = result_str.split('\n')
        
        # Find header info
        nrows = None
        ncols = None
        header_end = 0
        header_lines = []
        for i, line in enumerate(result_lines):
            if line.startswith("NROWS="):
                nrows = int(line.split("=")[1].strip())
                header_lines.append(line)
            elif line.startswith("NCOLS="):
                ncols = int(line.split("=")[1].strip())
                header_lines.append(line)
            elif line.startswith("#") or line.startswith("FORMAT") or "rmtxop" in line or "dctimestep" in line or "CAPDATE" in line or "GMT" in line or "Applied" in line or "Transposed" in line:
                header_lines.append(line)
            elif line.strip() == "" and nrows is not None and ncols is not None:
                header_end = i + 1
                break
        
        if nrows is not None and ncols is not None:
            # Read data
            data_lines = result_lines[header_end:]
            data = []
            for line in data_lines:
                stripped = line.strip()
                if stripped:
                    try:
                        values = [float(x) for x in stripped.split()]
                        data.extend(values)
                    except ValueError:
                        continue
            
            # Reshape to ncols x nrows (sensors x timesteps)
            data_array = np.array(data).reshape(ncols, nrows)
            
            # Expand to 8760 timesteps
            expanded_array = np.zeros((ncols, 8760), dtype=np.float32)
            expanded_array[:, daylight_mask] = data_array
            
            # Reconstruct HDR format file
            with open(output_file, "w", encoding="utf-8") as fp:
                # Write header, updating NROWS to 8760
                for line in header_lines:
                    if line.startswith("NROWS="):
                        fp.write("NROWS=8760\n")
                    else:
                        fp.write(line + "\n")
                fp.write("\n")  # Empty line before data
                
                # Write expanded data
                for row in expanded_array:
                    fp.write(" ".join([f"{val:.6e}" for val in row]) + "\n")
        else:
            # Fallback: write as-is if parsing fails
            with open(output_file, "wb") as fp:
                fp.write(result_bytes)
    else:
        # Write result to file as-is
        with open(output_file, "wb") as fp:
            fp.write(result_bytes)
    
    return output_file


def run_rcontrib(
    radiance_project_dir: str,
    radiance_surface_key: str,
    use_accelerad: bool = False,
    cal: str = "reinhart.cal",
    n_workers: Optional[int] = None,
    rad_params: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Run rcontrib to create contribution matrix for sun coefficients.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        use_accelerad: Whether to use accelerad_rcontrib instead of rcontrib
        cal: Path to calculation file (default: "reinhart.cal")
        n_workers: Number of parallel workers (defaults to CPU count - 1)
        rad_params: Radiance parameters as string
        
    Returns:
        Tuple of (output_matrix_file, grid_file)
    """
    use_accelerad = resolve_accelerad(use_accelerad)

    radiance_surface_dir, scene_base = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    output_dir = os.path.join(radiance_surface_dir, "outputs", "matrices")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "sun_illum.mtx")
    
    sun_oct = os.path.join(radiance_surface_dir, "outputs", "octree", "sun.oct")
    
    # Find grid file
    grid_files = glob.glob(os.path.join(scene_base, "grid", "*.pts"))
    if not grid_files:
        raise FileNotFoundError(f"No grid files found in {os.path.join(scene_base, 'grid')}/")
    grid_file = grid_files[0]
    
    # Count lines in grid file
    try:
        line_count = int(grid_file.split("_")[-1].split("s")[0])
    except ValueError:
        with open(grid_file, "r", encoding="utf-8") as fp:
            line_count = len(fp.readlines())
    
    # Set default parameters
    if n_workers is None:
        n_workers = os.cpu_count() - 1 if os.cpu_count() else 1
    
    if rad_params is None:
        # Default parameters for rcontrib (direct sun sources)
        # Using developer's recommended values: -ad 256 (not 10000+) for direct sun calculations
        rad_params = "-ad 256 -lw 1.0e-3 -dc 1 -dt 0 -dj 0"
    
    # Build command for rcontrib using subprocess to match original implementation
    # Format: rcontrib -I+ -ab 1 -y <line_count> -n <n_workers> <rad_params> -faf -e MF:6 -f <cal> -b rbin -bn Nrbins -m solar <octree> < <grid_file> > <output_file>
    if use_accelerad:
        # Use bare command name (not full path) so Accelerad can find its RAYPATH.
        # Availability is already guaranteed by resolve_accelerad() above.
        cmd_name = "accelerad_rcontrib"
        cmd_path = cmd_name  # Use bare name, not full path
    else:
        cmd_name = "rcontrib"
        cmd_path = os.path.join(_get_pyradiance().BINPATH, cmd_name) if os.path.exists(os.path.join(_get_pyradiance().BINPATH, cmd_name)) else cmd_name
    
    cmd = [cmd_path]
    cmd.extend(["-I+", "-ab", "1", "-y", str(int(line_count)), "-n", str(int(n_workers))])
    cmd.extend(rad_params.split())
    cmd.extend([
        "-faf",
        "-e", "MF:6",
        "-f", cal,
        "-b", "rbin",
        "-bn", "Nrbins",
        "-m", "solar",
        sun_oct
    ])
    
    # Verify files exist before running
    if not os.path.exists(grid_file):
        raise FileNotFoundError(f"Grid file not found: {grid_file}")
    if not os.path.exists(sun_oct):
        raise FileNotFoundError(f"Sun octree file not found: {sun_oct}")
    
    # Run rcontrib with grid file as stdin
    # Set up environment for Accelerad if needed
    env = None
    if use_accelerad:
        # Accelerad needs RAYPATH to find PTX files
        env = os.environ.copy()
        # Try common Accelerad library locations
        accelerad_lib_paths = [
            r"C:\Program Files\Accelerad\lib",
            r"C:\Program Files (x86)\Accelerad\lib",
        ]
        # Also check relative to bin directory
        accelerad_bin = find_accelerad_command("accelerad_rcontrib")
        if accelerad_bin:
            bin_dir = os.path.dirname(accelerad_bin)
            parent_dir = os.path.dirname(bin_dir)
            lib_path = os.path.join(parent_dir, "lib")
            if os.path.exists(lib_path):
                accelerad_lib_paths.insert(0, lib_path)
        
        # Find first existing lib directory
        raypath_value = None
        for lib_path in accelerad_lib_paths:
            if os.path.exists(lib_path):
                raypath_value = lib_path
                break
        
        if raypath_value:
            # Debug: Check if PTX files actually exist
            ptx_files = glob.glob(os.path.join(raypath_value, "*.ptx"))
            print(f"   Debug: RAYPATH will be set to: {raypath_value}")
            print(f"   Debug: Found {len(ptx_files)} PTX files in lib directory")
            if ptx_files:
                ptx_names = [os.path.basename(f) for f in ptx_files]
                print(f"   Debug: PTX files found: {', '.join(ptx_names[:5])}{'...' if len(ptx_names) > 5 else ''}")
                # Check specifically for rcontrib.ptx
                rcontrib_ptx = os.path.join(raypath_value, "rcontrib.ptx")
                if os.path.exists(rcontrib_ptx):
                    print(f"   ✓ Found rcontrib.ptx at: {rcontrib_ptx}")
                else:
                    print(f"   ⚠️  Warning: rcontrib.ptx NOT found at expected location: {rcontrib_ptx}")
            else:
                print(f"   ⚠️  Warning: No PTX files found in {raypath_value}")
            
            # Add to existing RAYPATH or create new
            existing_raypath = env.get("RAYPATH", "")
            if existing_raypath:
                env["RAYPATH"] = f"{raypath_value}:{existing_raypath}" if os.name != 'nt' else f"{raypath_value};{existing_raypath}"
            else:
                env["RAYPATH"] = raypath_value
            
            print(f"   Debug: Final RAYPATH environment variable: {env.get('RAYPATH', 'NOT SET')}")
        else:
            print(f"   ⚠️  Warning: Could not find Accelerad lib directory for RAYPATH")
            # Still create env copy even if we can't find lib, in case system RAYPATH is set
            env = os.environ.copy()
    
    # Ensure env is set (use system environment if not using Accelerad)
    if env is None:
        env = os.environ.copy()
    
    with open(grid_file, "rb") as stdin_fp:
        with open(output_file, "wb") as stdout_fp:
            result = subprocess.run(
                cmd,
                stdin=stdin_fp,
                stdout=stdout_fp,
                stderr=subprocess.PIPE,
                env=env,  # Pass environment with RAYPATH
                check=False  # Don't raise immediately, capture error first
            )
            
            if result.returncode != 0:
                # Capture stderr for better error messages
                stderr_text = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error message available"
                # Print detailed error information
                print(f"\n❌ Accelerad/rcontrib failed with exit code {result.returncode}")
                print(f"   Command: {' '.join(cmd)}")
                print(f"   Grid file: {grid_file} (exists: {os.path.exists(grid_file)})")
                print(f"   Sun octree: {sun_oct} (exists: {os.path.exists(sun_oct)})")
                print(f"   Output file: {output_file}")
                if stderr_text.strip():
                    print(f"   Error output:\n{stderr_text}")
                else:
                    print(f"   No error message from Accelerad (exit code {result.returncode})")
                
                # Raise with detailed message
                error_msg = (
                    f"Accelerad command failed (exit code {result.returncode}). "
                    f"See details above. Error: {stderr_text[:200] if stderr_text else 'No error message'}"
                )
                raise RuntimeError(error_msg) from subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    
    return output_file, grid_file


def create_sun_discs(radiance_project_dir: str, radiance_surface_key: str) -> None:
    """
    Create sun disc sources using cnt and rcalc, appending to suns.rad file.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
    """
    _, scene_base = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    sun_file = os.path.join(scene_base, "scene", "suns.rad")
    
    # Create primitive sun first
    create_primitive_sun(radiance_project_dir, radiance_surface_key)
    
    # Generate 5165 sun positions using cnt and rcalc
    # cnt 5165 | rcalc -e 'MF:6' -f reinsrc.cal -e 'Rbin=recno' -o 'solar source sun 0 0 4 ${Dx} ${Dy} ${Dz} 0.533'
    # Use subprocess for this complex pipeline
    cnt_path = os.path.join(_get_pyradiance().BINPATH, "cnt")
    rcalc_path = os.path.join(_get_pyradiance().BINPATH, "rcalc")
    
    # Run cnt 5165
    cnt_proc = subprocess.Popen(
        [cnt_path, "5165"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Run rcalc with the cnt output as input
    rcalc_proc = subprocess.Popen(
        [
            rcalc_path,
            "-e", "MF:6",
            "-f", "reinsrc.cal",
            "-e", "Rbin=recno",
            "-o", r"solar source sun 0 0 4 ${Dx} ${Dy} ${Dz} 0.533"
        ],
        stdin=cnt_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    cnt_proc.stdout.close()
    rcalc_output_bytes, rcalc_error = rcalc_proc.communicate()
    
    if rcalc_proc.returncode != 0:
        raise RuntimeError(f"rcalc failed: {rcalc_error.decode()}")
    
    # Append to sun file
    with open(sun_file, "ab") as fp:
        fp.write(rcalc_output_bytes)


def filter_wea_daylight_only(
    wea_file: str, 
    output_wea: Optional[str] = None,
    hour_offset: int = 0
) -> Tuple[str, np.ndarray]:
    """
    Filter WEA file to include only daylight hours (when global horizontal irradiance > 0).
    Also returns a boolean mask indicating which of the original 8760 hours are daylight.
    
    Args:
        wea_file: Path to input WEA file
        output_wea: Path to output filtered WEA file (if None, creates filtered version)
        hour_offset: Starting hour offset for subset EPW files (e.g., 4224 for warmest week).
                    This ensures the daylight mask marks the correct calendar positions.
        
    Returns:
        Tuple of (path to filtered WEA file, boolean array of shape (8760,) indicating daylight hours)
    """
    if output_wea is None:
        output_wea = wea_file.replace(".wea", "_filtered.wea")
    
    # Read WEA file
    with open(wea_file, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
    
    # Parse header
    header_lines = []
    data_start_idx = 0
    
    for i, line in enumerate(lines):
        if line.startswith(("place", "latitude", "longitude", "time_zone", "site_elevation", "weather_data_file_units")):
            header_lines.append(line)
        elif line.strip() and not line.startswith("#"):
            # First data line
            data_start_idx = i
            break
    
    # Parse data lines and filter
    filtered_data_lines = []
    daylight_mask = np.zeros(8760, dtype=bool)  # Track which hours are daylight
    hour_idx = 0
    
    for line in lines[data_start_idx:]:
        parts = line.strip().split()
        if len(parts) >= 5:
            direct_normal = float(parts[3])
            diffuse_horizontal = float(parts[4])
            global_horizontal = direct_normal + diffuse_horizontal
            
            # Keep line if global horizontal irradiance > 0
            if global_horizontal > 0:
                filtered_data_lines.append(line)
                # Apply hour_offset to mark correct calendar position
                calendar_hour = hour_offset + hour_idx
                if calendar_hour < 8760:  # Bounds check
                    daylight_mask[calendar_hour] = True
            
            hour_idx += 1
    
    # Write filtered WEA file
    with open(output_wea, "w", encoding="utf-8") as fp:
        fp.writelines(header_lines)
        fp.writelines(filtered_data_lines)
    
    n_daylight = np.sum(daylight_mask)
    if hour_offset > 0:
        print(f"     - Filtered WEA: {n_daylight} daylight hours (from {hour_idx} total, offset={hour_offset})")
    else:
        print(f"     - Filtered WEA: {n_daylight} daylight hours (from {hour_idx} total hours)")
    
    return output_wea, daylight_mask


def epw2wea(
    radiance_project_dir: str,
    radiance_surface_key: str,
    input_epw: str,
    filter_daylight_only: bool = False,
    hour_offset: int = 0,
) -> Tuple[str, Optional[np.ndarray]]:
    """
    Convert EPW weather file to WEA format, optionally filtering to daylight hours only.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        input_epw: Path to input EPW file
        filter_daylight_only: If True, filter WEA to only include daylight hours (GHi > 0)
        hour_offset: Starting hour offset for subset EPW files. Used to place daylight
                    mask at correct calendar positions (e.g., 4224 for warmest week).
        
    Returns:
        Tuple of (path to output WEA file, daylight_mask array if filtering, None otherwise)
    """
    input_epw = pathlib.Path(input_epw)
    _, scene_base = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    os.makedirs(scene_base, exist_ok=True)
    wea_name = input_epw.name.replace(".epw", ".wea")
    output_wea = os.path.join(scene_base, wea_name)
    
    # Run epw2wea using subprocess
    epw2wea_path = os.path.join(_get_pyradiance().BINPATH, "epw2wea")
    cmd = [epw2wea_path, str(input_epw), output_wea]
    subprocess.run(cmd, check=True)
    
    # Optionally filter to daylight hours only
    daylight_mask = None
    if filter_daylight_only:
        filtered_wea, daylight_mask = filter_wea_daylight_only(output_wea, hour_offset=hour_offset)
        # Replace original with filtered version
        os.replace(filtered_wea, output_wea)
    
    return output_wea, daylight_mask


def run_2phase_dds(
    radiance_project_dir: str,
    radiance_surface_key: str,
    scenario_tmy: str,
    n_workers: Optional[int] = None,
    rflux_rad_params: Optional[str] = None,
    rcontrib_rad_params: Optional[str] = None,
    use_accelerad: bool = False,
    sky_resolution: int = 1,
    filter_daylight_only: bool = True,
    hour_offset: int = 0,
) -> None:
    """
    Run the complete 2-Phase DDS workflow for annual irradiance simulation.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        scenario_tmy: Path to EPW or WEA weather file
        n_workers: Number of parallel workers (defaults to CPU count - 1)
        rflux_rad_params: Radiance parameters for rfluxmtx (default: "-lw 0.0001 -ab 5 -ad 10000")
        rcontrib_rad_params: Radiance parameters for rcontrib (default: "-ad 256 -lw 1.0e-3 -dc 1 -dt 0 -dj 0")
            Note: Use -ad 256 for direct sun sources. High -ad values (10000+) are for rfluxmtx (diffuse sky), not rcontrib.
        use_accelerad: Whether to use Accelerad for faster computation
        sky_resolution: Integer from 1 to 6 determining sky subdivisions (1 = Tregenza sky, default)
        filter_daylight_only: If True, filter WEA to only process daylight hours (GHi > 0), then expand results to 8760 timesteps
        hour_offset: Starting hour offset for subset EPW/WEA files. Results will be placed at 
                    correct calendar positions (e.g., 4224 for warmest week starting day 176).
        
        For params the HB medium resolution string is "-ab 5 -ad 15000 -as 2048 -c 1 -dc 0.5 -dp 256 -dr 1 -ds 0.25 -dt 0.25 -lr 6 -lw 6.67e-07 -ss 0.7 -st 0.5"

    """
    use_accelerad = resolve_accelerad(use_accelerad)

    print(f" - Running 2-Phase DDS with {n_workers or (os.cpu_count() - 1)} workers")
    print(f" - Current surface is {radiance_surface_key if radiance_surface_key else '(root)'}")
    print(f" - Accelerad: {'on' if use_accelerad else 'off (standard Radiance)'}")
    start_time = time.time()
    
    radiance_surface_dir, _ = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    
    # Create output directories
    os.makedirs(os.path.join(radiance_surface_dir, "outputs", "octree"), exist_ok=True)
    os.makedirs(os.path.join(radiance_surface_dir, "outputs", "matrices"), exist_ok=True)
    os.makedirs(os.path.join(radiance_surface_dir, "outputs", "results"), exist_ok=True)
    
    ### Part 0: Convert EPW to WEA
    step_start = time.time()
    print(" - Initializing the weather file.")
    if hour_offset > 0:
        print(f"     - Using hour offset: {hour_offset} (subset EPW at correct calendar position)")
    if pathlib.Path(scenario_tmy).suffix == ".epw":
        output_wea, daylight_mask = epw2wea(
            radiance_project_dir, 
            radiance_surface_key, 
            scenario_tmy,
            filter_daylight_only=filter_daylight_only,
            hour_offset=hour_offset
        )
    else:
        output_wea = scenario_tmy
        daylight_mask = None
        if filter_daylight_only:
            # Filter existing WEA file
            output_wea, daylight_mask = filter_wea_daylight_only(output_wea, hour_offset=hour_offset)
    print(f"     - Weather file initialized in {round(time.time() - step_start, 2)} seconds")
    
    ### Part 1 & 2: Total and Direct Irradiance
    for n, step in enumerate(["total", "direct"]):
        step_start = time.time()
        print(f" - Starting Part {n + 1} ({step}).")
        
        ## Build octree
        oct_start = time.time()
        print("     - oconv")
        oct_dir = os.path.join(radiance_surface_dir, "outputs", "octree")
        if step == "total":
            octree_file = os.path.join(oct_dir, "total.oct")
        else:
            octree_file = os.path.join(oct_dir, "direct.oct")
        
        build_octree(radiance_project_dir, radiance_surface_key, step, octree_file)
        print(f"         - oconv completed in {round(time.time() - oct_start, 2)} seconds")
        
        ## Run rfluxmtx
        rflux_start = time.time()
        print("     - rfluxmtx")
        run_rfluxmtx(
            radiance_project_dir,
            radiance_surface_key,
            step,
            use_accelerad=use_accelerad,
            n_workers=n_workers,
            rad_params=rflux_rad_params,
            sky_resolution=sky_resolution,
        )
        print(f"         - rfluxmtx completed in {round(time.time() - rflux_start, 2)} seconds")
        
        ## Run gendaymtx
        genday_start = time.time()
        print("     - gendaymtx")
        run_gendaymtx(radiance_project_dir, radiance_surface_key, output_wea, step)
        print(f"         - gendaymtx completed in {round(time.time() - genday_start, 2)} seconds")
        
        ## Run dctimestep | rmtxop
        dctimestep_start = time.time()
        print("     - dctimestep | rmtxop")
        run_dctimestep_rmtxop(radiance_project_dir, radiance_surface_key, step, daylight_mask)
        print(f"         - dctimestep | rmtxop completed in {round(time.time() - dctimestep_start, 2)} seconds")
        
        print(f"     - Part {n + 1} completed in {round(time.time() - step_start, 2)} seconds")
    
    ### Part 3: Sun Coefficients
    step = "sun"
    step_start = time.time()
    print(f" - Starting Part {3} ({step}).")
    
    ## Create sun discs
    sun_start = time.time()
    print("     - create_sun_discs")
    create_sun_discs(radiance_project_dir, radiance_surface_key)
    print(f"         - create_sun_discs completed in {round(time.time() - sun_start, 2)} seconds")
    
    ## Build octree with sun
    oct_start = time.time()
    print("     - oconv")
    oct_dir = os.path.join(radiance_surface_dir, "outputs", "octree")
    octree_file = os.path.join(oct_dir, "sun.oct")
    build_octree(radiance_project_dir, radiance_surface_key, step, octree_file)
    print(f"         - oconv completed in {round(time.time() - oct_start, 2)} seconds")
    
    ## Run rcontrib
    rcontrib_start = time.time()
    print("     - rcontrib")
    run_rcontrib(
        radiance_project_dir,
        radiance_surface_key,
        use_accelerad=use_accelerad,
        n_workers=n_workers,
        rad_params=rcontrib_rad_params,
    )
    print(f"         - rcontrib completed in {round(time.time() - rcontrib_start, 2)} seconds")
    
    ## Run gendaymtx for sun
    genday_start = time.time()
    print("     - gendaymtx")
    run_gendaymtx(radiance_project_dir, radiance_surface_key, output_wea, step)
    print(f"         - gendaymtx completed in {round(time.time() - genday_start, 2)} seconds")
    
    ## Run dctimestep | rmtxop for sun
    dctimestep_start = time.time()
    print("     - dctimestep | rmtxop")
    run_dctimestep_rmtxop(radiance_project_dir, radiance_surface_key, step, daylight_mask)
    print(f"         - dctimestep | rmtxop completed in {round(time.time() - dctimestep_start, 2)} seconds")
    
    print(f"     - Part {3} completed in {round(time.time() - step_start, 2)} seconds")
    
    total_time = round(time.time() - start_time, 2)
    print(f" - Simulation completed in {total_time} seconds")
    return None


def read_ill(filepath: str) -> pd.DataFrame:
    """
    Read illuminance file (.ill) and return as DataFrame.
    
    The .ill file is a Radiance HDR format file (ASCII) with header containing:
    NROWS=<number_of_timesteps>
    NCOLS=<number_of_sensors>
    NCOMP=1
    
    Args:
        filepath: Path to .ill file
        
    Returns:
        DataFrame with illuminance values (rows=sensors, columns=timesteps)
    """
    nrows = None
    ncols = None
    header_end = 0
    
    # Read header to get dimensions
    with open(filepath, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
        for i, line in enumerate(lines):
            if line.startswith("NROWS="):
                nrows = int(line.split("=")[1].strip())
            elif line.startswith("NCOLS="):
                ncols = int(line.split("=")[1].strip())
            elif line.strip() == "" and nrows is not None and ncols is not None:
                # Empty line after header marks start of data
                header_end = i + 1
                break
    
    if nrows is None or ncols is None:
        raise ValueError(f"Could not parse dimensions from {filepath} header")
    
    # Read data (skip header, read as ASCII floats)
    data_lines = lines[header_end:]
    # Filter out empty lines and parse floats
    data = []
    for line in data_lines:
        stripped = line.strip()
        if stripped:
            try:
                # Each line may have multiple space-separated values
                values = [float(x) for x in stripped.split()]
                data.extend(values)
            except ValueError:
                continue
    
    # Reshape: ncols (sensors) x nrows (timesteps)
    data_array = np.array(data).reshape(ncols, nrows)
    
    return pd.DataFrame(data_array)

def find_ill_skip(fp):
    """Find the skip row for the .ill file

    Args:
        fp: the .ill filepath

    Returns:
        the skip row number
    """
    break_line = None
    with open(fp, "r", encoding="utf-8") as fp_:
        for n, line in enumerate(fp_.readlines()):
            if "FORMAT=ascii" in line:
                break_line = n
                break
    return break_line + 1

def read_ill_legacy(filepath):
    """

    :param filepath: the ill filepath
    :return: a pandas dataframe where each column is a snesor point and the rows coordinate to the timeseries analysed
    """
    # this works on honeybee files
    # return pd.read_csv(filepath, delimiter=' ', header=None, dtype='float32').iloc[:, 1:].T.reset_index(drop=True)
    if pathlib.Path(filepath).suffix == ".ill":
        print(f"Reading {filepath} as .ill file")
        skiprows_n = 0#find_ill_skip(filepath)
        df = pd.read_csv(filepath, header=None, skiprows=skiprows_n, delimiter=' ', dtype='float') * 1000
        # df = df[range(1, len(df.columns))].round(2)
        df = df.round(5)
    else:
        df = pd.read_feather(filepath) * 1000
        # df = df[range(1, len(df.columns))].round(2)
        df = df.round(5)
    # df[0] = 0
    # print(df.iloc[10:14])
    return df

def ill_to_df(
    radiance_project_dir: str,
    radiance_surface_key: str,
    lux_to_wattm2: float = 0.0079,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convert illuminance files to DataFrames and calculate direct and diffuse irradiance.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        lux_to_wattm2: Conversion factor from lux to W/m² (default: 0.0079)
        
    Returns:
        Tuple of (direct_irradiance_df, diffuse_irradiance_df)
    """
    radiance_surface_dir, _ = get_radiance_paths(radiance_project_dir, radiance_surface_key)
    output_dir = os.path.join(radiance_surface_dir, "outputs", "results")
    
    filepath_total = os.path.join(output_dir, "result_total.ill")
    filepath_direct = os.path.join(output_dir, "result_direct.ill")
    filepath_sun = os.path.join(output_dir, "result_sun.ill")
    
    df_total = read_ill(filepath_total)
    df_direct = read_ill(filepath_direct)
    df_sun = read_ill(filepath_sun)
    
    indirect_illuminance = df_total - df_direct
    
    direct = df_sun * lux_to_wattm2
    direct = direct.astype("float").round(2)
    diffuse = indirect_illuminance * lux_to_wattm2
    diffuse = diffuse.astype("float").round(2)
    diffuse = pd.DataFrame(np.where(diffuse < 0, direct * 0.01, diffuse))
    
    return pd.DataFrame(direct.values), pd.DataFrame(diffuse.values)


def save_irradiance_results(
    radiance_project_dir: str,
    radiance_surface_key: str,
    direct_output_file: str,
    diffuse_output_file: str,
    lux_to_wattm2: float = 0.0079,
) -> None:
    """
    Save irradiance results to compressed feather files.
    
    Args:
        radiance_project_dir: Base directory for Radiance project
        radiance_surface_key: Surface key identifier
        direct_output_file: Path to save direct irradiance results
        diffuse_output_file: Path to save diffuse irradiance results
        lux_to_wattm2: Conversion factor from lux to W/m²
    """
    try:
        import pyarrow.feather as feather
    except ImportError as exc:
        raise ImportError("pyarrow is required for saving feather files. Install with: pip install pyarrow") from exc
    
    print(" - Saving Irradiance results")
    direct, diffuse = ill_to_df(radiance_project_dir, radiance_surface_key, lux_to_wattm2)
    
    start_time = time.time()
    feather.write_feather(direct, direct_output_file, compression="lz4")
    end_time = time.time()
    print(
        f"    - Direct sensor data saved in compressed format, time={round(end_time-start_time,0)}-seconds."
    )
    
    start_time = time.time()
    feather.write_feather(diffuse, diffuse_output_file, compression="lz4")
    end_time = time.time()
    print(
        f"    - Diffuse sensor data saved in compressed format, time={round(end_time-start_time,0)}-seconds."
    )
    
def get_hoy(timestamp):
    """
    :param timestamp: a string input should be in the form 'YYYY-MM-DD HH:MM'
    :return: int hour difference
    """

    if type(timestamp) is str:
        year = timestamp.split("-")[0]
    else:
        year = timestamp.year
    delta = np.datetime64(timestamp) - np.datetime64(f"{year}-01-01")
    return delta.astype('timedelta64[h]').astype(np.int32)