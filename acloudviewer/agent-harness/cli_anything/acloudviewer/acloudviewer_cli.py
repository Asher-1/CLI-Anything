"""ACloudViewer CLI — controls ACloudViewer via RPC (GUI) or binary subprocess (headless).

Usage:
    # One-shot commands
    cli-anything-acloudviewer info
    cli-anything-acloudviewer --json --mode headless convert input.ply output.pcd
    cli-anything-acloudviewer process subsample input.ply -o sub.ply --voxel-size 0.05

    # Interactive REPL
    cli-anything-acloudviewer repl
    cli-anything-acloudviewer                          # also enters REPL (no subcommand)
"""

from __future__ import annotations

import functools
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Optional

import click

from cli_anything.acloudviewer.core.session import Session
from cli_anything.acloudviewer.core.scene import (
    create_project, open_project, save_project,
    add_entity_record, remove_entity_record, get_project_info,
)
from cli_anything.acloudviewer.utils.acloudviewer_backend import (
    ACloudViewerBackend, BackendError,
    POINT_CLOUD_FORMATS, MESH_FORMATS, IMAGE_FORMATS,
)
from cli_anything.acloudviewer.utils.installer import (
    detect_platform, fetch_releases, get_latest_release,
    find_matching_wheel, find_matching_app,
    install_wheel, install_app,
    check_installation, format_check_report,
    InstallError, HOMEPAGE,
)
from cli_anything.acloudviewer.utils.repl_skin import ReplSkin

# ── Global state ─────────────────────────────────────────────────────────

_session: Optional[Session] = None
_backend: Optional[ACloudViewerBackend] = None
_json_output: bool = False
_repl_mode: bool = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def get_backend() -> ACloudViewerBackend:
    global _backend
    if _backend is None:
        _backend = ACloudViewerBackend(mode="auto")
    return _backend


# ── Output helpers ───────────────────────────────────────────────────────

def output(data: Any, message: str = "") -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0) -> None:
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0) -> None:
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


# ── Error handler ────────────────────────────────────────────────────────

def handle_error(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BackendError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "backend_error"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except FileNotFoundError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_not_found"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except (ValueError, IndexError, RuntimeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {type(e).__name__}: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    return wrapper


# ── Interactive install prompt ────────────────────────────────────────────

def _prompt_install_if_missing(skin: ReplSkin) -> str | None:
    """If binary not found, interactively offer to install. Returns binary path or None."""
    binary = ACloudViewerBackend.find_binary()
    if binary:
        return binary

    skin.warning("ACloudViewer binary not found!")
    skin.info("")

    if not click.confirm("  Would you like to install ACloudViewer now?", default=True):
        skin.hint("You can install later with: cli-anything-acloudviewer install app")
        skin.hint(f"Or download manually from: {HOMEPAGE}")
        return None

    channel_choices = {"1": "stable", "2": "beta"}
    skin.info("")
    skin.info("  Choose release channel:")
    skin.info("    [1] stable  — Latest stable release (recommended)")
    skin.info("    [2] beta    — Latest development build")
    channel_input = click.prompt("  Select", type=click.Choice(["1", "2"]), default="1")
    channel = channel_choices[channel_input]

    plat = detect_platform()
    gpu_choices = {"1": False, "2": True}
    if plat.has_nvidia_gpu:
        skin.info("")
        skin.info("  NVIDIA GPU detected. Choose variant:")
        skin.info("    [1] CUDA  — GPU-accelerated (larger download)")
        skin.info("    [2] CPU   — CPU-only (smaller download)")
        gpu_input = click.prompt("  Select", type=click.Choice(["1", "2"]), default="1")
        cpu_only = gpu_choices[gpu_input]
    else:
        cpu_only = True

    skin.info("")
    try:
        release = get_latest_release(channel=channel)
        skin.info(f"  Release: {release.label}")

        asset = find_matching_app(release, plat, cpu_only=cpu_only)
        if not asset:
            skin.error(f"  No matching installer for this platform.")
            skin.hint(f"  Download manually from: {HOMEPAGE}")
            return None

        skin.info(f"  Package: {asset.name} ({asset.size_mb:.0f} MB)")

        if not click.confirm("  Proceed with download and install?", default=True):
            return None

        result = install_app(asset)

        if result.get("status") == "installed" and result.get("binary"):
            skin.info("")
            skin.info(f"  Installed! Binary: {result['binary']}")
            skin.hint(f"  Tip: export ACV_BINARY={result['binary']}")
            return result["binary"]

        if result.get("status") == "downloaded":
            skin.info("")
            skin.info(f"  {result.get('message', 'Downloaded.')}")
            return None

        skin.warning(f"  Install result: {result.get('status', 'unknown')}")
        return None

    except InstallError as e:
        skin.error(f"  Install failed: {e}")
        skin.hint(f"  Download manually from: {HOMEPAGE}")
        return None
    except Exception as e:
        skin.error(f"  Unexpected error: {e}")
        return None


# ── Main CLI group ───────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--mode", type=click.Choice(["auto", "gui", "headless"]),
              default="auto", help="Backend mode")
@click.option("--rpc-url", default="ws://localhost:6001",
              help="WebSocket URL for GUI mode")
@click.pass_context
def cli(ctx, use_json, mode, rpc_url):
    """cli-anything-acloudviewer — ACloudViewer 3D point cloud and mesh processing.

    GUI mode: controls a running ACloudViewer via JSON-RPC.
    Headless mode: invokes ACloudViewer binary in silent CLI mode.
    """
    global _json_output, _backend
    _json_output = use_json
    _backend = ACloudViewerBackend(mode=mode, rpc_url=rpc_url)

    if ctx.invoked_subcommand is None:
        skin = ReplSkin("acloudviewer", version="3.0.0")
        skin.info(f"Mode: {_backend.mode}")
        if _backend.mode == "gui":
            skin.info(f"RPC: {rpc_url}")

        binary = ACloudViewerBackend.find_binary()
        if binary:
            skin.info(f"Binary: {binary}")
        elif not use_json:
            installed = _prompt_install_if_missing(skin)
            if installed:
                _backend._binary = installed
                skin.info(f"Binary: {installed}")
        else:
            skin.warning("Binary: not found")

        ctx.invoke(repl)


# ── Info ─────────────────────────────────────────────────────────────────

@cli.command("info")
@handle_error
def cmd_info():
    """Show backend info and supported formats."""
    b = get_backend()
    fmts = ACloudViewerBackend.supported_formats()
    total = sum(len(v) for v in fmts.values())
    info = {
        "mode": b.mode,
        "binary": ACloudViewerBackend.find_binary() or "not found",
        "supported_formats": total,
    }
    get_session().snapshot("info")
    output(info)


# ── Check & Install ──────────────────────────────────────────────────────

@cli.command("check")
@handle_error
def cmd_check():
    """Check ACloudViewer installation status and suggest fixes."""
    status = check_installation()
    if _json_output:
        output(status)
    else:
        click.echo(format_check_report(status))


@cli.group("install")
def install_group():
    """Install ACloudViewer components (binary app or Python wheel)."""
    pass


@install_group.command("wheel")
@click.option("--channel", type=click.Choice(["stable", "beta", "any"]),
              default="stable", help="Release channel")
@click.option("--cpu-only", is_flag=True, help="Install CPU-only variant")
@click.option("--pip-args", default="", help="Extra args passed to pip install")
@handle_error
def install_wheel_cmd(channel, cpu_only, pip_args):
    """Download and install the cloudViewer Python wheel."""
    skin = ReplSkin("acloudviewer", version="3.0.0")
    plat = detect_platform()

    skin.info(f"Platform: {plat.os_id} {plat.os_version}, "
              f"Python {plat.python_version[0]}.{plat.python_version[1]}, "
              f"arch={plat.arch}")

    try:
        release = get_latest_release(channel=channel)
    except InstallError as e:
        skin.error(str(e))
        return
    skin.info(f"Release: {release.label}")

    asset = find_matching_wheel(release, plat, cpu_only=cpu_only)
    if not asset:
        skin.error(
            f"No matching wheel found for {plat.python_tag} / {plat.manylinux_tag}.\n"
            f"  Visit {HOMEPAGE} to download manually."
        )
        return

    skin.info(f"Package: {asset.name} ({asset.size_mb:.0f} MB)")

    extra_args = pip_args.split() if pip_args else None
    try:
        result = install_wheel(asset, pip_args=extra_args)
    except InstallError as e:
        skin.error(str(e))
        return

    output(result, message="cloudViewer Python wheel installed successfully.")


@install_group.command("app")
@click.option("--channel", type=click.Choice(["stable", "beta", "any"]),
              default="stable", help="Release channel")
@click.option("--cpu-only", is_flag=True, help="CPU-only variant (smaller download)")
@click.option("--install-dir", type=click.Path(), default=None,
              help="Install location (default: ~/.local/share/ACloudViewer)")
@click.option("--from-file", "local_file", type=click.Path(exists=True), default=None,
              help="Install from a local .run/.dmg/.exe file instead of downloading")
@handle_error
def install_app_cmd(channel, cpu_only, install_dir, local_file):
    """Download and install the ACloudViewer desktop application binary."""
    skin = ReplSkin("acloudviewer", version="3.0.0")

    if local_file:
        from cli_anything.acloudviewer.utils.installer import install_app_from_file
        from pathlib import Path as P
        target = P(install_dir) if install_dir else None
        try:
            result = install_app_from_file(P(local_file), install_dir=target)
        except InstallError as e:
            skin.error(str(e))
            return
        output(result)
        if result.get("binary"):
            skin.info(f"export ACV_BINARY={result['binary']}")
        return

    plat = detect_platform()

    skin.info(f"Platform: {plat.os_id} {plat.os_version}, arch={plat.arch}, "
              f"NVIDIA GPU: {'yes' if plat.has_nvidia_gpu else 'no'}")

    try:
        release = get_latest_release(channel=channel)
    except InstallError as e:
        skin.error(str(e))
        return
    skin.info(f"Release: {release.label}")

    asset = find_matching_app(release, plat, cpu_only=cpu_only)
    if not asset:
        skin.error(
            f"No matching installer found for this platform.\n"
            f"  Visit {HOMEPAGE} to download manually."
        )
        return

    skin.info(f"Installer: {asset.name} ({asset.size_mb:.0f} MB)")

    from pathlib import Path as P
    target = P(install_dir) if install_dir else None
    try:
        result = install_app(asset, install_dir=target)
    except InstallError as e:
        skin.error(str(e))
        return

    output(result)

    if result.get("binary"):
        skin.info("Add to your shell profile for permanent use:")
        skin.info(f"  export ACV_BINARY={result['binary']}")


@install_group.command("auto")
@click.option("--channel", type=click.Choice(["stable", "beta", "any"]),
              default="stable", help="Release channel")
@click.option("--cpu-only", is_flag=True, help="CPU-only variant")
@handle_error
def install_auto_cmd(channel, cpu_only):
    """Auto-detect missing components and install them."""
    skin = ReplSkin("acloudviewer", version="3.0.0")
    plat = detect_platform()
    status = check_installation()

    if status["ready"] and status["python_package"]["found"]:
        skin.info("Everything is already installed!")
        output(status)
        return

    try:
        release = get_latest_release(channel=channel)
    except InstallError as e:
        skin.error(str(e))
        return
    skin.info(f"Using release: {release.label}")

    if not status["binary"]["found"]:
        skin.section("Installing ACloudViewer binary...")
        asset = find_matching_app(release, plat, cpu_only=cpu_only)
        if asset:
            try:
                result = install_app(asset)
                output(result)
                if result.get("binary"):
                    skin.info(f"Binary installed: {result['binary']}")
                    skin.info(f"  export ACV_BINARY={result['binary']}")
            except InstallError as e:
                skin.error(f"App install failed: {e}")
        else:
            skin.warning(f"No matching app found. Visit {HOMEPAGE}")

    if not status["python_package"]["found"]:
        skin.section("Installing cloudViewer Python wheel...")
        asset = find_matching_wheel(release, plat, cpu_only=cpu_only)
        if asset:
            try:
                result = install_wheel(asset)
                output(result)
            except InstallError as e:
                skin.error(f"Wheel install failed: {e}")
        else:
            skin.warning(f"No matching wheel found. Visit {HOMEPAGE}")


# ── File operations ──────────────────────────────────────────────────────

@cli.command("open")
@click.argument("file_path", type=click.Path(exists=True))
@handle_error
def cmd_open(file_path):
    """Open a file in ACloudViewer."""
    result = get_backend().open_file(file_path)
    get_session().snapshot(f"open {file_path}")
    output(result)


@cli.command("convert")
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@handle_error
def cmd_convert(input_file, output_file):
    """Convert between file formats using ACloudViewer binary."""
    result = get_backend().convert_format(input_file, output_file)
    get_session().snapshot(f"convert {input_file} → {output_file}")
    output(result)


@cli.command("batch-convert")
@click.argument("input_dir", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path())
@click.option("--format", "-f", "output_format", default=".ply")
@click.option("--filter-ext", multiple=True, default=None)
@handle_error
def cmd_batch_convert(input_dir, output_dir, output_format, filter_ext):
    """Convert all files in a directory to a target format."""
    exts = list(filter_ext) if filter_ext else None
    result = get_backend().batch_convert(
        input_dir, output_dir,
        output_format=output_format,
        input_extensions=exts)
    get_session().snapshot(f"batch-convert {input_dir} → {output_dir}")
    output(result)


@cli.command("formats")
@handle_error
def cmd_formats():
    """List all supported file formats."""
    skin = ReplSkin("acloudviewer", version="3.0.0")
    if _json_output:
        output(ACloudViewerBackend.supported_formats())
    else:
        skin.section("Point Cloud")
        skin.info(", ".join(sorted(POINT_CLOUD_FORMATS)))
        skin.section("Mesh")
        skin.info(", ".join(sorted(MESH_FORMATS)))
        skin.section("Image")
        skin.info(", ".join(sorted(IMAGE_FORMATS)))


# ── Scene (GUI) ──────────────────────────────────────────────────────────

@cli.group("scene")
def scene_group():
    """Scene tree operations (GUI mode)."""
    pass


@scene_group.command("list")
@click.option("--recursive/--no-recursive", default=True)
@handle_error
def scene_list(recursive):
    """List all entities in the scene."""
    result = get_backend().scene_list(recursive=recursive)
    output(result)


@scene_group.command("info")
@click.argument("entity_id", type=int)
@handle_error
def scene_info(entity_id):
    """Show entity details."""
    result = get_backend().scene_info(entity_id)
    output(result)


# ── View (GUI) ───────────────────────────────────────────────────────────

@cli.group("view")
def view_group():
    """View control (GUI mode)."""
    pass


@view_group.command("screenshot")
@click.argument("filename", type=click.Path())
@handle_error
def view_screenshot(filename):
    """Capture viewport screenshot."""
    result = get_backend().screenshot_gui(filename)
    get_session().snapshot(f"screenshot {filename}")
    output(result)


@view_group.command("camera")
@handle_error
def view_camera():
    """Get camera parameters."""
    result = get_backend().get_camera()
    output(result)


# ── Processing ───────────────────────────────────────────────────────────

@cli.group("process")
def process_group():
    """Point cloud and mesh processing commands."""
    pass


@process_group.command("subsample")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--method", type=click.Choice(["SPATIAL", "RANDOM", "OCTREE"]),
              default="SPATIAL")
@click.option("--voxel-size", type=float, default=0.05,
              help="Spatial step or parameter")
@handle_error
def process_subsample(input_file, output_file, method, voxel_size):
    """Subsample a point cloud."""
    result = get_backend().subsample(input_file, output_file,
                                     method=method, parameter=voxel_size)
    get_session().snapshot(f"subsample {input_file}")
    output(result)


@process_group.command("normals")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--radius", type=float, default=0.0, help="Search radius (0=auto)")
@handle_error
def process_normals(input_file, output_file, radius):
    """Compute normals for a point cloud."""
    result = get_backend().compute_normals(input_file, output_file, radius=radius)
    get_session().snapshot(f"normals {input_file}")
    output(result)


@process_group.command("icp")
@click.argument("data_file", type=click.Path(exists=True))
@click.argument("reference_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path())
@click.option("--iterations", type=int, default=100)
@handle_error
def process_icp(data_file, reference_file, output_file, iterations):
    """ICP registration between two point clouds."""
    result = get_backend().icp_registration(
        data_file, reference_file,
        output_path=output_file, iterations=iterations)
    get_session().snapshot(f"icp {data_file} ↔ {reference_file}")
    output(result)


@process_group.command("sor")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--knn", type=int, default=6)
@click.option("--sigma", type=float, default=1.0)
@handle_error
def process_sor(input_file, output_file, knn, sigma):
    """Statistical outlier removal."""
    result = get_backend().sor_filter(input_file, output_file, knn=knn, sigma=sigma)
    get_session().snapshot(f"sor {input_file}")
    output(result)


@process_group.command("c2c-dist")
@click.argument("compared_file", type=click.Path(exists=True))
@click.argument("reference_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path())
@click.option("--max-dist", type=float, default=0.0)
@handle_error
def process_c2c_dist(compared_file, reference_file, output_file, max_dist):
    """Compute cloud-to-cloud distances."""
    result = get_backend().c2c_distance(
        compared_file, reference_file,
        output_path=output_file, max_dist=max_dist)
    get_session().snapshot(f"c2c-dist {compared_file} ↔ {reference_file}")
    output(result)


@process_group.command("c2m-dist")
@click.argument("cloud_file", type=click.Path(exists=True))
@click.argument("mesh_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path())
@click.option("--max-dist", type=float, default=0.0)
@handle_error
def process_c2m_dist(cloud_file, mesh_file, output_file, max_dist):
    """Compute cloud-to-mesh distances."""
    result = get_backend().c2m_distance(
        cloud_file, mesh_file,
        output_path=output_file, max_dist=max_dist)
    get_session().snapshot(f"c2m-dist {cloud_file} ↔ {mesh_file}")
    output(result)


@process_group.command("density")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--radius", type=float, default=0.5)
@handle_error
def process_density(input_file, output_file, radius):
    """Compute local density."""
    result = get_backend().density(input_file, output_file, radius=radius)
    get_session().snapshot(f"density {input_file}")
    output(result)


@process_group.command("curvature")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--type", "curv_type", type=click.Choice(["MEAN", "GAUSS"]),
              default="MEAN")
@click.option("--radius", type=float, default=0.5)
@handle_error
def process_curvature(input_file, output_file, curv_type, radius):
    """Compute curvature."""
    result = get_backend().curvature(input_file, output_file,
                                     curvature_type=curv_type, radius=radius)
    get_session().snapshot(f"curvature {input_file}")
    output(result)


@process_group.command("roughness")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--radius", type=float, default=0.5)
@handle_error
def process_roughness(input_file, output_file, radius):
    """Compute roughness."""
    result = get_backend().roughness(input_file, output_file, radius=radius)
    get_session().snapshot(f"roughness {input_file}")
    output(result)


@process_group.command("delaunay")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--max-edge-length", type=float, default=0.0)
@handle_error
def process_delaunay(input_file, output_file, max_edge_length):
    """Delaunay triangulation (mesh reconstruction)."""
    result = get_backend().delaunay(input_file, output_file,
                                    max_edge_length=max_edge_length)
    get_session().snapshot(f"delaunay {input_file}")
    output(result)


@process_group.command("sample-mesh")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--points", type=int, default=100000)
@handle_error
def process_sample_mesh(input_file, output_file, points):
    """Sample points from a mesh surface."""
    result = get_backend().sample_mesh(input_file, output_file, points=points)
    get_session().snapshot(f"sample-mesh {input_file}")
    output(result)


@process_group.command("color-banding")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--axis", type=click.Choice(["X", "Y", "Z"]), default="Z")
@click.option("--frequency", type=float, default=10.0)
@handle_error
def process_color_banding(input_file, output_file, axis, frequency):
    """Apply color banding along an axis."""
    result = get_backend().color_banding(input_file, output_file,
                                          axis=axis, frequency=frequency)
    get_session().snapshot(f"color-banding {input_file}")
    output(result)


# ── Reconstruct ──────────────────────────────────────────────────────────

@cli.group("reconstruct")
def reconstruct_group():
    """3D reconstruction commands (uses Colmap binary for SfM/MVS)."""
    pass


@reconstruct_group.command("mesh")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--max-edge-length", type=float, default=0.0)
@handle_error
def reconstruct_mesh(input_file, output_file, max_edge_length):
    """Reconstruct mesh from point cloud (Delaunay via ACloudViewer)."""
    result = get_backend().delaunay(input_file, output_file,
                                    max_edge_length=max_edge_length)
    get_session().snapshot(f"reconstruct mesh {input_file}")
    output(result)


def _get_colmap():
    from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
    return ColmapBackend()


@reconstruct_group.command("auto")
@click.argument("image_path", type=click.Path(exists=True))
@click.option("--workspace", "-w", "workspace_path", type=click.Path(), required=True)
@click.option("--quality", type=click.Choice(["low", "medium", "high", "extreme"],
              case_sensitive=False), default="high")
@click.option("--data-type", type=click.Choice(["individual", "video", "internet"],
              case_sensitive=False), default="individual")
@click.option("--mesher", type=click.Choice(["poisson", "delaunay"],
              case_sensitive=False), default="poisson")
@click.option("--camera-model", default="", help="Camera model (e.g. SIMPLE_RADIAL)")
@click.option("--single-camera", is_flag=True, help="All images from one camera")
@click.option("--no-sparse", is_flag=True, help="Skip sparse reconstruction")
@click.option("--no-dense", is_flag=True, help="Skip dense reconstruction")
@click.option("--no-gpu", is_flag=True, help="Disable GPU acceleration")
@click.option("--import/--no-import", "import_results", default=None,
              help="Import results into ACloudViewer (default: gui=on, headless=off)")
@handle_error
def reconstruct_auto(image_path, workspace_path, quality, data_type,
                     mesher, camera_model, single_camera,
                     no_sparse, no_dense, no_gpu, import_results):
    """Automatic end-to-end reconstruction from images (Colmap)."""
    result = _get_colmap().automatic_reconstruct(
        workspace_path, image_path,
        quality=quality, data_type=data_type,
        mesher=mesher, camera_model=camera_model,
        single_camera=single_camera,
        sparse=not no_sparse, dense=not no_dense,
        use_gpu=not no_gpu)
    get_session().snapshot("reconstruct auto")

    backend = get_backend()
    if import_results is None:
        import_results = (backend.mode == "gui")

    if import_results and result.get("outputs"):
        imported = []
        for category in ("textured_mesh", "mesh", "fused_ply"):
            for path in result["outputs"].get(category, []):
                try:
                    backend.open_file(path, silent=True)
                    imported.append(path)
                except Exception:
                    pass
        result["imported"] = imported

    output(result)


@reconstruct_group.command("extract-features")
@click.argument("image_path", type=click.Path(exists=True))
@click.option("--database", "-d", "database_path", type=click.Path(), required=True)
@click.option("--camera-model", default="SIMPLE_RADIAL")
@click.option("--single-camera", is_flag=True)
@click.option("--no-gpu", is_flag=True)
@click.option("--max-features", type=int, default=8192)
@handle_error
def reconstruct_extract_features(image_path, database_path, camera_model,
                                 single_camera, no_gpu, max_features):
    """Extract features from images (Colmap feature_extractor)."""
    result = _get_colmap().feature_extractor(
        database_path, image_path,
        camera_model=camera_model, single_camera=single_camera,
        use_gpu=not no_gpu, max_num_features=max_features)
    output(result)


@reconstruct_group.command("match")
@click.argument("database_path", type=click.Path(exists=True))
@click.option("--method", type=click.Choice(["exhaustive", "sequential", "vocab_tree", "spatial"]),
              default="exhaustive")
@click.option("--overlap", type=int, default=10, help="Sequence overlap (sequential only)")
@click.option("--vocab-tree", type=click.Path(), default="", help="Vocab tree path (vocab_tree only)")
@click.option("--no-gpu", is_flag=True)
@handle_error
def reconstruct_match(database_path, method, overlap, vocab_tree, no_gpu):
    """Match features between images (Colmap matcher)."""
    colmap = _get_colmap()
    if method == "exhaustive":
        result = colmap.exhaustive_matcher(database_path, use_gpu=not no_gpu)
    elif method == "sequential":
        result = colmap.sequential_matcher(database_path, overlap=overlap, use_gpu=not no_gpu)
    elif method == "vocab_tree":
        if not vocab_tree:
            raise click.BadParameter("--vocab-tree required for vocab_tree method")
        result = colmap.vocab_tree_matcher(database_path, vocab_tree, use_gpu=not no_gpu)
    else:
        result = colmap.spatial_matcher(database_path, use_gpu=not no_gpu)
    output(result)


@reconstruct_group.command("sparse")
@click.option("--database", "-d", "database_path", type=click.Path(exists=True), required=True)
@click.option("--image-path", type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--method", type=click.Choice(["incremental", "hierarchical"]),
              default="incremental")
@handle_error
def reconstruct_sparse(database_path, image_path, output_path, method):
    """Run sparse reconstruction / SfM (Colmap mapper)."""
    colmap = _get_colmap()
    if method == "hierarchical":
        result = colmap.hierarchical_mapper(database_path, image_path, output_path)
    else:
        result = colmap.mapper(database_path, image_path, output_path)
    output(result)


@reconstruct_group.command("undistort")
@click.option("--image-path", type=click.Path(exists=True), required=True)
@click.option("--input", "-i", "input_path", type=click.Path(exists=True), required=True,
              help="Sparse model path (e.g. sparse/0)")
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--max-image-size", type=int, default=0)
@handle_error
def reconstruct_undistort(image_path, input_path, output_path, max_image_size):
    """Undistort images and prepare dense workspace (Colmap)."""
    result = _get_colmap().image_undistorter(
        image_path, input_path, output_path, max_image_size=max_image_size)
    output(result)


@reconstruct_group.command("dense-stereo")
@click.argument("workspace_path", type=click.Path(exists=True))
@click.option("--no-geom-consistency", is_flag=True)
@handle_error
def reconstruct_dense_stereo(workspace_path, no_geom_consistency):
    """Run PatchMatch multi-view stereo (Colmap)."""
    result = _get_colmap().patch_match_stereo(
        workspace_path, geom_consistency=not no_geom_consistency)
    output(result)


@reconstruct_group.command("fuse")
@click.argument("workspace_path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@handle_error
def reconstruct_fuse(workspace_path, output_path):
    """Fuse depth maps into a dense point cloud (Colmap stereo_fusion)."""
    result = _get_colmap().stereo_fusion(workspace_path, output_path)
    output(result)


@reconstruct_group.command("poisson")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@handle_error
def reconstruct_poisson(input_path, output_path):
    """Poisson surface reconstruction from dense point cloud (Colmap)."""
    result = _get_colmap().poisson_mesher(input_path, output_path)
    output(result)


@reconstruct_group.command("delaunay-mesh")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@handle_error
def reconstruct_delaunay_mesh(input_path, output_path):
    """Delaunay meshing with visibility constraints (Colmap)."""
    result = _get_colmap().delaunay_mesher(input_path, output_path)
    output(result)


@reconstruct_group.command("simplify-mesh")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--face-ratio", type=float, default=0.5, help="Target face ratio (0-1)")
@handle_error
def reconstruct_simplify_mesh(input_path, output_path, face_ratio):
    """Simplify mesh (Colmap mesh_simplifier)."""
    result = _get_colmap().mesh_simplifier(input_path, output_path,
                                           target_face_ratio=face_ratio)
    output(result)


@reconstruct_group.command("texture-mesh")
@click.argument("input_path", type=click.Path(exists=True),
                metavar="RECONSTRUCTION_PATH")
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--mesh", "mesh_path", type=click.Path(exists=True),
              default="", help="Path to mesh file (auto-detected if omitted)")
@handle_error
def reconstruct_texture_mesh(input_path, output_path, mesh_path):
    """Texture a mesh from multi-view images (Colmap image_texturer)."""
    result = _get_colmap().image_texturer(input_path, output_path,
                                          mesh_path=mesh_path)
    output(result)


@reconstruct_group.command("convert-model")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--output-type", type=click.Choice(["BIN", "TXT", "NVM", "Bundler",
              "VRML", "PLY", "R3D", "CAM"]), default="PLY")
@handle_error
def reconstruct_convert_model(input_path, output_path, output_type):
    """Convert Colmap model to other formats."""
    result = _get_colmap().model_converter(input_path, output_path,
                                           output_type=output_type)
    output(result)


@reconstruct_group.command("analyze-model")
@click.argument("input_path", type=click.Path(exists=True))
@handle_error
def reconstruct_analyze_model(input_path):
    """Analyze a sparse reconstruction model (Colmap)."""
    result = _get_colmap().model_analyzer(input_path)
    output(result)


# ── SIBR Dataset Tools ────────────────────────────────────────────────────

@cli.group("sibr")
def sibr_group():
    """SIBR dataset preprocessing tools (requires ACloudViewer with SIBR plugin)."""
    pass


@sibr_group.command("tool")
@click.argument("tool_name")
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_tool(tool_name, extra_args):
    """Run any SIBR tool by name with passthrough arguments.

    Available tools: prepareColmap4Sibr, tonemapper, unwrapMesh, textureMesh,
    clippingPlanes, cropFromCenter, nvmToSIBR, distordCrop, cameraConverter,
    alignMeshes.
    """
    result = get_backend().sibr_tool(tool_name, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("prepare-colmap")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option("--fix-metadata", is_flag=True, help="Fix metadata issues in the dataset")
@handle_error
def sibr_prepare_colmap(dataset_path, fix_metadata):
    """Prepare Colmap output for SIBR rendering."""
    result = get_backend().sibr_prepare_colmap(dataset_path, fix_metadata)
    output(result)


@sibr_group.command("texture-mesh")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_texture_mesh(dataset_path, extra_args):
    """Generate textured mesh from SIBR dataset."""
    result = get_backend().sibr_texture_mesh(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("unwrap-mesh")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_unwrap_mesh(dataset_path, extra_args):
    """UV-unwrap a mesh for texturing."""
    result = get_backend().sibr_unwrap_mesh(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("tonemapper")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_tonemap(dataset_path, extra_args):
    """Apply tonemapping to HDR images in a dataset."""
    result = get_backend().sibr_tonemap(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("align-meshes")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_align_meshes(dataset_path, extra_args):
    """Align meshes in the dataset."""
    result = get_backend().sibr_align_meshes(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("camera-converter")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_camera_converter(dataset_path, extra_args):
    """Convert camera formats for SIBR."""
    result = get_backend().sibr_camera_converter(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("nvm-to-sibr")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_nvm_to_sibr(dataset_path, extra_args):
    """Convert NVM format to SIBR dataset layout."""
    result = get_backend().sibr_nvm_to_sibr(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("crop-from-center")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_crop_from_center(dataset_path, extra_args):
    """Crop dataset from center coordinates."""
    result = get_backend().sibr_crop_from_center(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("clipping-planes")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_clipping_planes(dataset_path, extra_args):
    """Compute or apply clipping planes for a dataset."""
    result = get_backend().sibr_clipping_planes(dataset_path, list(extra_args) if extra_args else None)
    output(result)


@sibr_group.command("distord-crop")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("extra_args", nargs=-1)
@handle_error
def sibr_distord_crop(dataset_path, extra_args):
    """Apply distortion-aware cropping to images."""
    result = get_backend().sibr_distord_crop(dataset_path, list(extra_args) if extra_args else None)
    output(result)


# ── Session ──────────────────────────────────────────────────────────────

@cli.group("session")
def session_group():
    """Session management."""
    pass


@session_group.command("status")
@handle_error
def session_status():
    """Show session status."""
    output(get_session().status())


@session_group.command("undo")
@handle_error
def session_undo():
    """Undo last operation."""
    s = get_session().undo()
    output({"undone": s.description if s else None})


@session_group.command("redo")
@handle_error
def session_redo():
    """Redo last undone operation."""
    s = get_session().redo()
    output({"redone": s.description if s else None})


# ── REPL ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--project", "project_path", type=str, default=None)
@handle_error
def repl(project_path):
    """Start interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("acloudviewer", version="3.0.0")

    if project_path:
        sess = get_session()
        proj = open_project(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "info":        "show backend info",
        "check":       "check installation status",
        "install":     "auto|app|wheel — install missing components",
        "open":        "open <file>",
        "convert":     "convert <in> <out>",
        "batch-convert": "batch-convert <dir-in> <dir-out> [-f .ply]",
        "formats":     "list supported formats",
        "process":     "subsample|normals|icp|sor|c2c-dist|c2m-dist|density|curvature|roughness|delaunay|sample-mesh|color-banding",
        "reconstruct": "mesh|auto|extract-features|match|sparse|undistort|dense-stereo|fuse|poisson",
        "scene":       "list|info (GUI mode)",
        "view":        "screenshot|camera (GUI mode)",
        "session":     "status|undo|redo",
        "help":        "show this help",
        "quit":        "exit REPL",
    }

    while True:
        try:
            sess = get_session()
            project_name = ""
            modified = False
            if hasattr(sess, "project_path") and sess.project_path:
                project_name = os.path.basename(sess.project_path)
            if hasattr(sess, "_modified"):
                modified = sess._modified

            line = skin.get_input(
                pt_session, project_name=project_name, modified=modified
            ).strip()
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            try:
                args = shlex.split(line, posix=(os.name != "nt"))
            except ValueError:
                args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.warning(f"Usage error: {e}")
            except Exception as e:
                skin.error(str(e))

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
