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
                click.echo(json.dumps({"error": str(e), "type": "backend_error", "status": "failed"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except FileNotFoundError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_not_found", "status": "failed"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except (ValueError, IndexError, RuntimeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__, "status": "failed"}))
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
        skin = ReplSkin("acloudviewer", version="3.1.0")
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
    skin = ReplSkin("acloudviewer", version="3.1.0")
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
    skin = ReplSkin("acloudviewer", version="3.1.0")

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
    skin = ReplSkin("acloudviewer", version="3.1.0")
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


# ══════════════════════════════════════════════════════════════════════════
# GUI MODE — commands requiring a running ACloudViewer with JSON-RPC
# ══════════════════════════════════════════════════════════════════════════

@cli.command("open")
@click.argument("file_path", type=click.Path(exists=True))
@handle_error
def cmd_open(file_path):
    """Open a file in ACloudViewer (GUI mode)."""
    file_path = str(Path(file_path).resolve())
    result = get_backend().open_file(file_path)
    get_session().snapshot(f"open {file_path}")
    output(result)


# ══════════════════════════════════════════════════════════════════════════
# HEADLESS MODE — commands that invoke ACloudViewer binary in -SILENT mode
# ══════════════════════════════════════════════════════════════════════════

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
    skin = ReplSkin("acloudviewer", version="3.1.0")
    if _json_output:
        output(ACloudViewerBackend.supported_formats())
    else:
        skin.section("Point Cloud")
        skin.info(", ".join(sorted(POINT_CLOUD_FORMATS)))
        skin.section("Mesh")
        skin.info(", ".join(sorted(MESH_FORMATS)))
        skin.section("Image")
        skin.info(", ".join(sorted(IMAGE_FORMATS)))


# ── Scene (GUI) ──

@cli.group("scene")
def scene_group():
    """[GUI] Scene tree operations."""
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


@scene_group.command("remove")
@click.argument("entity_id", type=int)
@handle_error
def scene_remove(entity_id):
    """Remove an entity from the scene."""
    get_backend().scene_remove(entity_id)
    get_session().snapshot(f"scene remove {entity_id}")
    output({"entity_id": entity_id, "status": "removed"})


@scene_group.command("show")
@click.argument("entity_id", type=int)
@handle_error
def scene_show(entity_id):
    """Show (unhide) an entity."""
    get_backend().scene_set_visible(entity_id, True)
    output({"entity_id": entity_id, "visible": True})


@scene_group.command("hide")
@click.argument("entity_id", type=int)
@handle_error
def scene_hide(entity_id):
    """Hide an entity."""
    get_backend().scene_set_visible(entity_id, False)
    output({"entity_id": entity_id, "visible": False})


@scene_group.command("select")
@click.argument("entity_ids", nargs=-1, type=int, required=True)
@handle_error
def scene_select(entity_ids):
    """Select one or more entities."""
    get_backend().scene_select(list(entity_ids))
    output({"selected": list(entity_ids)})


@scene_group.command("clear")
@handle_error
def scene_clear():
    """Remove all entities from the scene."""
    get_backend().scene_clear()
    get_session().snapshot("scene clear")
    output({"status": "cleared"})


# ── Entity (GUI) ──

@cli.group("entity")
def entity_group():
    """[GUI] Entity manipulation."""
    pass


@entity_group.command("rename")
@click.argument("entity_id", type=int)
@click.argument("name")
@handle_error
def entity_rename(entity_id, name):
    """Rename an entity."""
    get_backend().entity_rename(entity_id, name)
    get_session().snapshot(f"entity rename {entity_id} → {name}")
    output({"entity_id": entity_id, "name": name})


@entity_group.command("set-color")
@click.argument("entity_id", type=int)
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
@handle_error
def entity_set_color(entity_id, r, g, b):
    """Set entity display color (RGB 0-255)."""
    get_backend().entity_set_color(entity_id, r, g, b)
    output({"entity_id": entity_id, "color": [r, g, b]})


# ── Export ──

@cli.command("export")
@click.argument("entity_id", type=int)
@click.argument("output_file", type=click.Path())
@handle_error
def cmd_export(entity_id, output_file):
    """Export an entity to a file (GUI mode)."""
    output_file = str(Path(output_file).resolve())
    result = get_backend().export_file(entity_id, output_file)
    get_session().snapshot(f"export {entity_id} → {output_file}")
    output(result)


# ── Clear (deprecated alias for `scene clear`) ──

@cli.command("clear", deprecated=True)
@handle_error
def cmd_clear():
    """Clear all entities — use `scene clear` instead."""
    get_backend().scene_clear()
    get_session().snapshot("clear")
    output({"status": "cleared"})


# ── Methods ──

@cli.command("methods")
@handle_error
def cmd_methods():
    """List all available RPC methods (GUI mode)."""
    b = get_backend()
    if b.mode != "gui":
        raise BackendError("methods command requires GUI mode")
    result = b._rpc.list_methods()
    output(result)


# ── View (GUI) ──

@cli.group("view")
def view_group():
    """[GUI] View control."""
    pass


@view_group.command("screenshot")
@click.argument("filename", type=click.Path())
@handle_error
def view_screenshot(filename):
    """Capture viewport screenshot."""
    filename = str(Path(filename).resolve())
    result = get_backend().screenshot_gui(filename)
    get_session().snapshot(f"screenshot {filename}")
    output(result)


@view_group.command("camera")
@handle_error
def view_camera():
    """Get camera parameters."""
    result = get_backend().get_camera()
    output(result)


@view_group.command("orient")
@click.argument("direction", type=click.Choice(
    ["top", "bottom", "front", "back", "left", "right", "iso1", "iso2"],
    case_sensitive=False))
@handle_error
def view_orient(direction):
    """Set camera view orientation."""
    get_backend().view_set_orientation(direction.lower())
    output({"orientation": direction.lower()})


@view_group.command("zoom")
@click.option("--entity", "entity_id", type=int, default=None,
              help="Zoom to a specific entity")
@handle_error
def view_zoom(entity_id):
    """Zoom to fit all entities or a specific entity."""
    get_backend().view_zoom_fit(entity_id)
    output({"status": "zoomed", "entity_id": entity_id})


@view_group.command("refresh")
@handle_error
def view_refresh_cmd():
    """Force a display redraw."""
    get_backend().view_refresh()
    output({"status": "refreshed"})


@view_group.command("perspective")
@click.argument("mode", type=click.Choice(["object", "viewer"],
                case_sensitive=False))
@handle_error
def view_perspective(mode):
    """Set perspective projection mode."""
    get_backend().view_set_perspective(mode.lower())
    output({"perspective": mode.lower()})


@view_group.command("pointsize")
@click.argument("action", type=click.Choice(["+", "-", "increase", "decrease"]))
@handle_error
def view_pointsize(action):
    """Adjust point display size (+ or -)."""
    act = "increase" if action in ("+", "increase") else "decrease"
    get_backend().view_set_point_size(act)
    output({"point_size": act})


# ── Cloud (GUI) ──

@cli.group("cloud")
def cloud_group():
    """[GUI] Point cloud operations on scene entities."""
    pass


@cloud_group.command("paint-uniform")
@click.argument("entity_id", type=int)
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
@handle_error
def cloud_paint_uniform(entity_id, r, g, b):
    """Paint all points with a uniform color (RGB 0-255)."""
    result = get_backend().cloud_paint_uniform_gui(entity_id, r, g, b)
    output(result)


@cloud_group.command("paint-by-height")
@click.argument("entity_id", type=int)
@click.option("--axis", type=click.Choice(["x", "y", "z"]), default="z")
@handle_error
def cloud_paint_by_height(entity_id, axis):
    """Colorize a point cloud by height gradient."""
    result = get_backend().cloud_paint_by_height_gui(entity_id, axis=axis)
    output(result)


@cloud_group.command("paint-by-scalar-field")
@click.argument("entity_id", type=int)
@click.option("--field", "field_name", default="", help="Scalar field name")
@handle_error
def cloud_paint_by_scalar_field(entity_id, field_name):
    """Colorize a point cloud by a scalar field."""
    result = get_backend().cloud_paint_by_scalar_field_gui(entity_id,
                                                           field_name=field_name)
    output(result)


@cloud_group.command("get-scalar-fields")
@click.argument("entity_id", type=int)
@handle_error
def cloud_get_scalar_fields(entity_id):
    """List all scalar fields on a point cloud."""
    result = get_backend().cloud_get_scalar_fields(entity_id)
    output(result)


@cloud_group.command("crop")
@click.argument("entity_id", type=int)
@click.option("--min-x", type=float, required=True)
@click.option("--min-y", type=float, required=True)
@click.option("--min-z", type=float, required=True)
@click.option("--max-x", type=float, required=True)
@click.option("--max-y", type=float, required=True)
@click.option("--max-z", type=float, required=True)
@handle_error
def cloud_crop_gui(entity_id, min_x, min_y, min_z, max_x, max_y, max_z):
    """Crop a point cloud by bounding box (GUI mode)."""
    result = get_backend().crop(
        "", "", min_x=min_x, min_y=min_y, min_z=min_z,
        max_x=max_x, max_y=max_y, max_z=max_z, entity_id=entity_id)
    output(result)


# ── Mesh (GUI) ──

@cli.group("mesh")
def mesh_group():
    """[GUI] Mesh operations on scene entities."""
    pass


@mesh_group.command("simplify")
@click.argument("entity_id", type=int)
@click.option("--method", type=click.Choice(["quadric", "vertex_clustering"]),
              default="quadric")
@click.option("--target-triangles", type=int, default=10000)
@click.option("--voxel-size", type=float, default=0.05)
@handle_error
def mesh_simplify(entity_id, method, target_triangles, voxel_size):
    """Simplify a triangle mesh."""
    result = get_backend().mesh_simplify_gui(
        entity_id, method=method,
        target_triangles=target_triangles, voxel_size=voxel_size)
    output(result)


@mesh_group.command("smooth")
@click.argument("entity_id", type=int)
@click.option("--method", type=click.Choice(["laplacian", "taubin", "simple"]),
              default="laplacian")
@click.option("--iterations", type=int, default=5)
@click.option("--lambda", "lambda_val", type=float, default=0.5)
@click.option("--mu", type=float, default=-0.53)
@handle_error
def mesh_smooth(entity_id, method, iterations, lambda_val, mu):
    """Smooth a triangle mesh."""
    result = get_backend().mesh_smooth_gui(
        entity_id, method=method, iterations=iterations,
        lambda_val=lambda_val, mu=mu)
    output(result)


@mesh_group.command("subdivide")
@click.argument("entity_id", type=int)
@click.option("--method", type=click.Choice(["midpoint", "loop"]),
              default="midpoint")
@click.option("--iterations", type=int, default=1)
@handle_error
def mesh_subdivide(entity_id, method, iterations):
    """Subdivide a triangle mesh."""
    result = get_backend().mesh_subdivide_gui(
        entity_id, method=method, iterations=iterations)
    output(result)


@mesh_group.command("sample-points")
@click.argument("entity_id", type=int)
@click.option("--method", type=click.Choice(["uniform", "poisson_disk"]),
              default="uniform")
@click.option("--count", type=int, default=100000)
@handle_error
def mesh_sample_points(entity_id, method, count):
    """Sample points from a mesh surface."""
    result = get_backend().mesh_sample_points_gui(
        entity_id, method=method, count=count)
    output(result)


# ── Transform ──

@cli.group("transform")
def transform_group():
    """[Mixed] Transformation operations (apply=GUI, apply-file=Headless)."""
    pass


@transform_group.command("apply")
@click.argument("entity_id", type=int)
@click.argument("matrix", nargs=16, type=float)
@handle_error
def transform_apply(entity_id, matrix):
    """Apply a 4x4 transformation matrix to an entity (GUI mode).

    MATRIX: 16 floats in column-major order (OpenGL convention).
    """
    get_backend().transform_apply_gui(entity_id, list(matrix))
    get_session().snapshot(f"transform apply {entity_id}")
    output({"entity_id": entity_id, "status": "transformed"})


@transform_group.command("apply-file")
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("matrix_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def transform_apply_file(input_file, matrix_file, output_file):
    """Apply a transformation matrix from a file (headless mode)."""
    result = get_backend().apply_transformation(input_file, output_file, matrix_file)
    get_session().snapshot(f"transform apply-file {input_file}")
    output(result)


# ──Scalar Field Group (convenience wrapper for process sf-* commands) ──

@cli.group("sf")
def sf_group():
    """Scalar field shortcuts (headless). Aliases for `process sf-*` commands."""
    pass


# ── Normals Group (convenience aliases for process *-normals commands) ──

@cli.group("normals")
def normals_group():
    """Normal vector shortcuts (headless). Aliases for `process *-normals` commands."""
    pass


# ── Processing (headless) ──

@cli.group("process")
def process_group():
    """[Headless] Point cloud and mesh processing (no GUI needed)."""
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


@process_group.command("crop")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--min-x", type=float, required=True)
@click.option("--min-y", type=float, required=True)
@click.option("--min-z", type=float, required=True)
@click.option("--max-x", type=float, required=True)
@click.option("--max-y", type=float, required=True)
@click.option("--max-z", type=float, required=True)
@handle_error
def process_crop(input_file, output_file, min_x, min_y, min_z, max_x, max_y, max_z):
    """Crop a point cloud by axis-aligned bounding box (headless)."""
    result = get_backend().crop(
        input_file, output_file,
        min_x, min_y, min_z, max_x, max_y, max_z)
    get_session().snapshot(f"crop {input_file}")
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


@process_group.command("pcv")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--n-rays", type=int, default=256, help="Number of rays")
@click.option("--resolution", type=int, default=1024, help="Grid resolution")
@click.option("--180", "mode_180", is_flag=True, help="Upper hemisphere only")
@click.option("--is-closed", is_flag=True, help="Treat mesh as closed")
@handle_error
def process_pcv(input_file, output_file, n_rays, resolution, mode_180, is_closed):
    """Compute PCV (ambient occlusion / sky visibility)."""
    result = get_backend().pcv(input_file, output_file,
                               n_rays=n_rays, resolution=resolution,
                               mode_180=mode_180, is_closed=is_closed)
    get_session().snapshot(f"pcv {input_file}")
    output(result)


@process_group.command("csf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--scenes", type=click.Choice(["SLOPE", "RELIEF", "FLAT"], case_sensitive=False),
              default="RELIEF", help="Scene type: SLOPE, RELIEF, or FLAT")
@click.option("--cloth-resolution", type=float, default=2.0,
              help="Cloth grid resolution (default: 2.0)")
@click.option("--max-iteration", type=int, default=500)
@click.option("--class-threshold", type=float, default=0.5)
@click.option("--proc-slope", is_flag=True, help="Enable slope post-processing")
@click.option("--export-ground", is_flag=True, help="Export ground subset")
@click.option("--export-offground", is_flag=True, help="Export off-ground subset")
@handle_error
def process_csf(input_file, output_file, scenes, cloth_resolution, max_iteration,
                class_threshold, proc_slope, export_ground, export_offground):
    """CSF ground filtering (Cloth Simulation Filter)."""
    result = get_backend().csf(input_file, output_file,
                               scenes=scenes, cloth_resolution=cloth_resolution,
                               max_iteration=max_iteration, class_threshold=class_threshold,
                               proc_slope=proc_slope, export_ground=export_ground,
                               export_offground=export_offground)
    get_session().snapshot(f"csf {input_file}")
    output(result)


@process_group.command("ransac")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--epsilon", type=float, default=0.005, help="Absolute epsilon")
@click.option("--bitmap-epsilon", type=float, default=0.01)
@click.option("--support-points", type=int, default=500)
@click.option("--max-normal-dev", type=float, default=25.0, help="Max normal deviation (degrees)")
@click.option("--probability", type=float, default=0.01)
@click.option("--primitives", type=str, multiple=True,
              help="Primitives to detect: PLANE, SPHERE, CYLINDER, CONE, TORUS (can repeat)")
@handle_error
def process_ransac(input_file, output_file, epsilon, bitmap_epsilon, support_points,
                   max_normal_dev, probability, primitives):
    """RANSAC shape detection."""
    result = get_backend().ransac(input_file, output_file,
                                  epsilon=epsilon, bitmap_epsilon=bitmap_epsilon,
                                  support_points=support_points, max_normal_dev=max_normal_dev,
                                  probability=probability,
                                  primitives=list(primitives) if primitives else None)
    get_session().snapshot(f"ransac {input_file}")
    output(result)


@process_group.command("m3c2")
@click.argument("cloud1_file", type=click.Path(exists=True))
@click.argument("cloud2_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path())
@click.option("--params-file", type=click.Path(exists=True), help="M3C2 parameters file")
@handle_error
def process_m3c2(cloud1_file, cloud2_file, output_file, params_file):
    """Compute M3C2 distances between two point clouds."""
    result = get_backend().m3c2(cloud1_file, cloud2_file,
                                output_path=output_file, params_file=params_file)
    get_session().snapshot(f"m3c2 {cloud1_file} ↔ {cloud2_file}")
    output(result)


@process_group.command("canupo")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--classifier", type=click.Path(exists=True), required=True,
              help="CANUPO classifier file (.prm)")
@handle_error
def process_canupo(input_file, output_file, classifier):
    """Apply CANUPO classification."""
    result = get_backend().canupo(input_file, output_file, classifier_file=classifier)
    get_session().snapshot(f"canupo {input_file}")
    output(result)


@process_group.command("facets")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--algo", type=click.Choice(["KD_TREE", "FAST_MARCHING"]),
              default="KD_TREE", help="Extraction algorithm")
@click.option("--error-max", type=float, default=0.2, help="Max error per facet")
@click.option("--min-points", type=int, default=10, help="Min points per facet")
@click.option("--max-edge-length", type=float, default=1.0)
@click.option("--octree-level", type=int, default=8, help="For fast marching algo")
@click.option("--classify", is_flag=True, help="Classify facets by orientation")
@click.option("--export-shp", type=click.Path(), help="Export facets to shapefile")
@click.option("--export-csv", type=click.Path(), help="Export facets info to CSV")
@handle_error
def process_facets(input_file, output_file, algo, error_max, min_points,
                   max_edge_length, octree_level, classify, export_shp, export_csv):
    """Extract planar facets from a point cloud."""
    result = get_backend().facets(
        input_file, output_file, algo=algo, error_max=error_max,
        min_points=min_points, max_edge_length=max_edge_length,
        octree_level=octree_level, classify=classify,
        export_shp=export_shp, export_csv=export_csv)
    get_session().snapshot(f"facets {input_file}")
    output(result)


@process_group.command("hough-normals")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--k", "k_neighbors", type=int, default=100, help="Number of neighbors")
@click.option("--t", "t_accumulators", type=int, default=1000, help="Number of accumulators")
@click.option("--n-phi", type=int, default=15, help="Number of phi bins")
@click.option("--n-rot", type=int, default=5, help="Number of rotations")
@handle_error
def process_hough_normals(input_file, output_file, k_neighbors, t_accumulators, n_phi, n_rot):
    """Compute normals using Hough transform method."""
    result = get_backend().hough_normals(
        input_file, output_file, k=k_neighbors, t=t_accumulators,
        n_phi=n_phi, n_rot=n_rot)
    get_session().snapshot(f"hough-normals {input_file}")
    output(result)


@process_group.command("poisson-recon")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--depth", type=int, default=8, help="Octree depth")
@click.option("--samples-per-node", type=float, default=1.5)
@click.option("--point-weight", type=float, default=2.0)
@click.option("--boundary", type=click.Choice(["FREE", "DIRICHLET", "NEUMANN"]),
              default="NEUMANN")
@click.option("--with-colors", is_flag=True, help="Preserve colors")
@click.option("--density", is_flag=True, help="Compute density scalar field")
@handle_error
def process_poisson_recon(input_file, output_file, depth, samples_per_node,
                          point_weight, boundary, with_colors, density):
    """Poisson surface reconstruction (requires normals)."""
    result = get_backend().poisson_recon(
        input_file, output_file, depth=depth,
        samples_per_node=samples_per_node, point_weight=point_weight,
        boundary=boundary, with_colors=with_colors, density=density)
    get_session().snapshot(f"poisson-recon {input_file}")
    output(result)


@process_group.command("cork-boolean")
@click.argument("mesh1_file", type=click.Path(exists=True))
@click.argument("mesh2_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--operation", type=click.Choice(["UNION", "INTERSECT", "DIFF", "SYM_DIFF"]),
              default="UNION")
@click.option("--swap", is_flag=True, help="Swap mesh A/B order")
@handle_error
def process_cork_boolean(mesh1_file, mesh2_file, output_file, operation, swap):
    """Mesh boolean (CSG) operation using Cork library."""
    result = get_backend().cork_boolean(mesh1_file, mesh2_file, output_file,
                                        operation=operation, swap=swap)
    get_session().snapshot(f"cork-boolean {mesh1_file} ∩ {mesh2_file}")
    output(result)


@process_group.command("voxfall")
@click.argument("mesh1_file", type=click.Path(exists=True))
@click.argument("mesh2_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--voxel-size", type=float, default=0.1)
@click.option("--azimuth", type=float, default=0.0, help="Slope azimuth in degrees")
@click.option("--export-meshes", is_flag=True, help="Export per-cluster voxel meshes")
@click.option("--loss-gain", is_flag=True, help="Compute loss/gain classification")
@handle_error
def process_voxfall(mesh1_file, mesh2_file, output_file, voxel_size, azimuth, export_meshes, loss_gain):
    """VoxFall voxel-based change detection between two meshes."""
    result = get_backend().voxfall(mesh1_file, mesh2_file, output_file,
                                   voxel_size=voxel_size, azimuth=azimuth,
                                   export_meshes=export_meshes, loss_gain=loss_gain)
    get_session().snapshot(f"voxfall {mesh1_file} ↔ {mesh2_file}")
    output(result)


# ── Scalar field operations ──

@process_group.command("set-active-sf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", type=str, default="0", help="Scalar field index or name")
@handle_error
def process_set_active_sf(input_file, output_file, sf_index):
    """Set the active scalar field."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().set_active_sf(input_file, output_file, sf_index=sf_idx)
    output(result)


@process_group.command("remove-all-sfs")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_remove_all_sfs(input_file, output_file):
    """Remove all scalar fields."""
    result = get_backend().remove_all_sfs(input_file, output_file)
    output(result)


@process_group.command("remove-sf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", type=int, default=0)
@handle_error
def process_remove_sf(input_file, output_file, sf_index):
    """Remove a specific scalar field by index."""
    result = get_backend().remove_sf(input_file, output_file, sf_index=sf_index)
    output(result)


@process_group.command("rename-sf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", type=str, default="0")
@click.option("--new-name", required=True)
@handle_error
def process_rename_sf(input_file, output_file, sf_index, new_name):
    """Rename a scalar field."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().rename_sf(input_file, output_file,
                                     sf_index=sf_idx, new_name=new_name)
    output(result)


@process_group.command("sf-arithmetic")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", type=str, default="0")
@click.option("--operation", type=str, default="SQRT",
              help="SQRT, ABS, INV, EXP, LOG, LOG10, etc.")
@handle_error
def process_sf_arithmetic(input_file, output_file, sf_index, operation):
    """Apply a unary arithmetic operation to a scalar field."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().sf_arithmetic(input_file, output_file,
                                         sf_index=sf_idx, operation=operation)
    output(result)


@process_group.command("sf-op")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", type=str, default="0")
@click.option("--operation", type=click.Choice(["ADD", "SUB", "MULTIPLY", "DIVIDE"]),
              default="ADD")
@click.option("--value", type=float, required=True)
@handle_error
def process_sf_op(input_file, output_file, sf_index, operation, value):
    """Apply an arithmetic operation with a scalar value to a SF."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().sf_operation(input_file, output_file,
                                        sf_index=sf_idx, operation=operation,
                                        value=value)
    output(result)


@process_group.command("coord-to-sf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--dimension", type=click.Choice(["X", "Y", "Z"]), default="Z")
@handle_error
def process_coord_to_sf(input_file, output_file, dimension):
    """Export a coordinate dimension as a scalar field."""
    result = get_backend().coord_to_sf(input_file, output_file, dimension=dimension)
    output(result)


@process_group.command("sf-gradient")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--euclidean", is_flag=True, help="Use Euclidean gradient")
@handle_error
def process_sf_gradient(input_file, output_file, euclidean):
    """Compute scalar field gradient."""
    result = get_backend().sf_gradient(input_file, output_file, euclidean=euclidean)
    output(result)


@process_group.command("filter-sf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--min", "min_val", type=str, default="MIN")
@click.option("--max", "max_val", type=str, default="MAX")
@handle_error
def process_filter_sf(input_file, output_file, min_val, max_val):
    """Filter points by active scalar field value range."""
    result = get_backend().filter_sf(input_file, output_file,
                                     min_val=min_val, max_val=max_val)
    output(result)


@process_group.command("sf-color-scale")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--scale-file", type=click.Path(exists=True), required=True)
@handle_error
def process_sf_color_scale(input_file, output_file, scale_file):
    """Apply a color scale file to the active scalar field."""
    result = get_backend().sf_color_scale(input_file, output_file,
                                          scale_file=scale_file)
    output(result)


@process_group.command("sf-to-rgb")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_sf_to_rgb(input_file, output_file):
    """Convert the active scalar field to RGB colors."""
    result = get_backend().sf_convert_to_rgb(input_file, output_file)
    output(result)


# ── Advanced normals ──

@process_group.command("octree-normals")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--radius", type=str, default="AUTO", help="Radius or AUTO")
@click.option("--orient", type=str, default="", help="Normal orientation mode")
@click.option("--model", type=click.Choice(["", "LS", "TRI", "QUADRIC"]), default="")
@handle_error
def process_octree_normals(input_file, output_file, radius, orient, model):
    """Compute normals using octree method."""
    try:
        r = float(radius)
    except ValueError:
        r = radius
    result = get_backend().octree_normals(input_file, output_file,
                                          radius=r, orient=orient, model=model)
    output(result)


@process_group.command("orient-normals")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--knn", type=int, default=6)
@handle_error
def process_orient_normals(input_file, output_file, knn):
    """Orient normals via Minimum Spanning Tree."""
    result = get_backend().orient_normals_mst(input_file, output_file, knn=knn)
    output(result)


@process_group.command("invert-normals")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_invert_normals(input_file, output_file):
    """Invert point cloud normals."""
    result = get_backend().invert_normals(input_file, output_file)
    output(result)


@process_group.command("clear-normals")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_clear_normals(input_file, output_file):
    """Remove all normals from a point cloud."""
    result = get_backend().clear_normals(input_file, output_file)
    output(result)


@process_group.command("normals-to-dip")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_normals_to_dip(input_file, output_file):
    """Convert normals to dip/dip-direction scalar fields."""
    result = get_backend().normals_to_dip(input_file, output_file)
    output(result)


@process_group.command("normals-to-sfs")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_normals_to_sfs(input_file, output_file):
    """Convert normals to Nx/Ny/Nz scalar fields."""
    result = get_backend().normals_to_sfs(input_file, output_file)
    output(result)


# ── Geometry / analysis ──

@process_group.command("extract-cc")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--octree-level", type=int, default=8)
@click.option("--min-points", type=int, default=100)
@handle_error
def process_extract_cc(input_file, output_file, octree_level, min_points):
    """Extract connected components."""
    result = get_backend().extract_connected_components(
        input_file, output_file, octree_level=octree_level, min_points=min_points)
    output(result)


@process_group.command("approx-density")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--type", "density_type", type=str, default="",
              help="Density type filter")
@handle_error
def process_approx_density(input_file, output_file, density_type):
    """Compute approximate point density."""
    result = get_backend().approx_density(input_file, output_file,
                                          density_type=density_type)
    output(result)


@process_group.command("feature")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--type", "feature_type", type=click.Choice([
    "SUM_OF_EIGENVALUES", "OMNIVARIANCE", "EIGENTROPY", "ANISOTROPY",
    "PLANARITY", "LINEARITY", "PCA1", "PCA2", "SURFACE_VARIATION",
    "SPHERICITY", "VERTICALITY", "EIGENVALUE1", "EIGENVALUE2", "EIGENVALUE3",
]), default="SURFACE_VARIATION")
@click.option("--kernel-size", type=float, default=0.1)
@handle_error
def process_feature(input_file, output_file, feature_type, kernel_size):
    """Compute a geometric feature as a scalar field."""
    result = get_backend().feature(input_file, output_file,
                                   feature_type=feature_type,
                                   kernel_size=kernel_size)
    output(result)


@process_group.command("moment")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--kernel-size", type=float, default=0.1)
@handle_error
def process_moment(input_file, output_file, kernel_size):
    """Compute 1st order moment."""
    result = get_backend().moment(input_file, output_file,
                                  kernel_size=kernel_size)
    output(result)


@process_group.command("best-fit-plane")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--make-horiz", is_flag=True)
@click.option("--keep-loaded", is_flag=True)
@handle_error
def process_best_fit_plane(input_file, output_file, make_horiz, keep_loaded):
    """Compute best fit plane for a point cloud."""
    result = get_backend().best_fit_plane(input_file, output_file,
                                          make_horiz=make_horiz,
                                          keep_loaded=keep_loaded)
    output(result)


@process_group.command("mesh-volume")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output-file", type=click.Path(), default="",
              help="File to write volume result")
@handle_error
def process_mesh_volume(input_file, output_file):
    """Compute mesh enclosed volume."""
    result = get_backend().mesh_volume(input_file, output_file=output_file)
    output(result)


@process_group.command("extract-vertices")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_extract_vertices(input_file, output_file):
    """Extract mesh vertices as a point cloud."""
    result = get_backend().extract_vertices(input_file, output_file)
    output(result)


@process_group.command("flip-triangles")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_flip_triangles(input_file, output_file):
    """Flip mesh triangle normals."""
    result = get_backend().flip_triangles(input_file, output_file)
    output(result)


# ── Merge ──

@process_group.command("merge-clouds")
@click.argument("input_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_merge_clouds(input_files, output_file):
    """Merge multiple point clouds into one."""
    result = get_backend().merge_clouds(list(input_files), output_file)
    output(result)


@process_group.command("merge-meshes")
@click.argument("input_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_merge_meshes(input_files, output_file):
    """Merge multiple meshes into one."""
    result = get_backend().merge_meshes(list(input_files), output_file)
    output(result)


# ── Cleanup ──

@process_group.command("remove-rgb")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_remove_rgb(input_file, output_file):
    """Remove RGB colors from a point cloud."""
    result = get_backend().remove_rgb(input_file, output_file)
    output(result)


@process_group.command("remove-scan-grids")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_remove_scan_grids(input_file, output_file):
    """Remove scan grid info from a point cloud."""
    result = get_backend().remove_scan_grids(input_file, output_file)
    output(result)


@process_group.command("match-centers")
@click.argument("input_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_match_centers(input_files, output_file):
    """Match bounding-box centers of multiple entities."""
    result = get_backend().match_centers(list(input_files), output_file)
    output(result)


@process_group.command("drop-global-shift")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_drop_global_shift(input_file, output_file):
    """Remove the global coordinate shift from a cloud."""
    result = get_backend().drop_global_shift(input_file, output_file)
    output(result)


@process_group.command("closest-point-set")
@click.argument("input_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def process_closest_point_set(input_files, output_file):
    """Compute closest point set between two clouds."""
    result = get_backend().closest_point_set(list(input_files), output_file)
    output(result)


# ── Rasterize / Volume ──

@process_group.command("rasterize")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--grid-step", type=float, default=1.0)
@click.option("--vert-dir", type=int, default=2, help="0=X, 1=Y, 2=Z")
@click.option("--output-cloud", is_flag=True, default=True)
@click.option("--output-mesh", is_flag=True)
@click.option("--proj", type=click.Choice(["MIN", "MAX", "AVG"]), default="AVG")
@click.option("--empty-fill", type=click.Choice(["MIN_H", "MAX_H", "CUSTOM_H", "INTERP"]),
              default="MIN_H")
@handle_error
def process_rasterize(input_file, output_file, grid_step, vert_dir,
                      output_cloud, output_mesh, proj, empty_fill):
    """2.5D rasterization of a point cloud."""
    result = get_backend().rasterize(
        input_file, output_file, grid_step=grid_step, vert_dir=vert_dir,
        output_cloud=output_cloud, output_mesh=output_mesh,
        proj=proj, empty_fill=empty_fill)
    output(result)


@process_group.command("stat-test")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--distribution", type=click.Choice(["GAUSS", "WEIBULL"]), default="GAUSS")
@click.option("--p-value", type=float, default=0.0001)
@click.option("--knn", type=int, default=16)
@handle_error
def process_stat_test(input_file, output_file, distribution, p_value, knn):
    """Statistical outlier test."""
    result = get_backend().stat_test(
        input_file, output_file, distribution=distribution,
        p_value=p_value, knn=knn)
    output(result)


@process_group.command("cross-section")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--polyline", "polyline_file", type=click.Path(exists=True), default="",
              help="Polyline file defining the cross-section path")
@handle_error
def process_cross_section(input_file, output_file, polyline_file):
    """Extract cross-section from point cloud or mesh."""
    result = get_backend().cross_section(input_file, output_file,
                                         polyline_file=polyline_file)
    output(result)


@process_group.command("volume-25d")
@click.argument("input_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--grid-step", type=float, default=1.0)
@click.option("--vert-dir", type=int, default=2, help="0=X, 1=Y, 2=Z")
@click.option("--const-height", type=float, default=None,
              help="Constant height for ground (if only one cloud)")
@handle_error
def process_volume_25d(input_files, output_file, grid_step, vert_dir, const_height):
    """[Headless] Compute 2.5D volume between two clouds."""
    result = get_backend().volume_25d(
        list(input_files), output_file,
        grid_step=grid_step, vert_dir=vert_dir, const_height=const_height)
    output(result)


@process_group.command("crop-2d")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--dim", "orthogonal_dim", type=click.Choice(["X", "Y", "Z"]), default="Z",
              help="Dimension orthogonal to the cropping plane")
@click.option("--polygon", type=str, default="",
              help="Polygon vertices as 'x1,y1;x2,y2;...' (semicolon-separated)")
@handle_error
def process_crop_2d(input_file, output_file, orthogonal_dim, polygon):
    """[Headless] Crop by 2D polygon."""
    pts = []
    if polygon:
        for pair in polygon.split(";"):
            x, y = pair.split(",")
            pts.append((float(x.strip()), float(y.strip())))
    result = get_backend().crop_2d(
        input_file, output_file,
        orthogonal_dim=orthogonal_dim, polygon=pts)
    output(result)


# ── Reconstruct (headless, uses Colmap binary) ──

@cli.group("reconstruct")
def reconstruct_group():
    """[Headless] 3D reconstruction (Colmap SfM/MVS pipeline)."""
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


# ── SIBR Dataset Tools (headless) ──

@cli.group("sibr")
def sibr_group():
    """[Headless] SIBR dataset preprocessing (requires SIBR plugin)."""
    pass


@sibr_group.command("viewer")
@click.argument("viewer_type", type=click.Choice([
    "gaussian", "ulr", "ulrv2", "texturedmesh", 
    "pointbased", "remoteGaussian"
]))
@click.option("--path", type=click.Path(exists=True), 
              help="Dataset directory")
@click.option("--model-path", type=click.Path(exists=True), 
              help="Trained model directory (for gaussian viewer)")
@click.option("--mesh", type=click.Path(exists=True), 
              help="Mesh file (for texturedmesh viewer)")
@click.option("--width", type=int, default=1920, 
              help="Window width")
@click.option("--height", type=int, default=1080, 
              help="Window height")
@click.option("--iteration", type=int, 
              help="Specific iteration to load (gaussian viewer)")
@click.option("--device", type=int, default=0, 
              help="CUDA device ID")
@click.option("--no-interop", is_flag=True, 
              help="Disable CUDA-OpenGL interop")
@click.option("--ip", default="127.0.0.1", 
              help="IP address for remote connection (remoteGaussian)")
@click.option("--port", type=int, default=6009, 
              help="Port for remote connection (remoteGaussian)")
@handle_error
def sibr_viewer(viewer_type, path, model_path, mesh, width, height, 
                iteration, device, no_interop, ip, port):
    """Launch a SIBR viewer for novel view synthesis visualization.
    
    \b
    Available viewer types:
      gaussian       - Gaussian Splatting viewer (requires --model-path and --path)
      ulr            - Unstructured Lumigraph Rendering
      ulrv2          - ULR version 2
      texturedmesh   - Textured mesh viewer (requires --mesh and --path)
      pointbased     - Point-based rendering
      remoteGaussian - Remote Gaussian viewer (requires --ip and --port)
    
    \b
    Examples:
      cli-anything-acloudviewer sibr viewer gaussian --model-path ./output/ --path ./dataset/
      cli-anything-acloudviewer sibr viewer ulr --path ./dataset/
      cli-anything-acloudviewer sibr viewer remoteGaussian --ip 127.0.0.1 --port 6009
    """
    result = get_backend().launch_sibr_viewer(
        viewer_type,
        path=path,
        model_path=model_path,
        mesh=mesh,
        width=width,
        height=height,
        iteration=iteration,
        device=device,
        no_interop=no_interop,
        ip=ip,
        port=port
    )
    output(result)


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


@session_group.command("save")
@click.argument("project_path", type=click.Path())
@handle_error
def session_save(project_path):
    """Save session/project state."""
    from cli_anything.acloudviewer.core.scene import save_project, create_project
    sess = get_session()
    if hasattr(sess, '_project') and sess._project:
        save_project(sess._project, project_path)
    else:
        proj = create_project(project_path)
        save_project(proj, project_path)
    output({"saved": project_path})


@session_group.command("history")
@handle_error
def session_history():
    """Show full undo/redo history."""
    sess = get_session()
    status = sess.status()
    history = status.get("history", [])
    output({"history": history, "length": len(history)})


# ══════════════════════════════════════════════════════════════════════════
# SF Group Commands (convenience wrappers for process sf-* commands)
# ══════════════════════════════════════════════════════════════════════════

@sf_group.command("coord-to-sf")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--dimension", type=click.Choice(["X", "Y", "Z"]), default="Z")
@handle_error
def sf_coord_to_sf(input_file, output_file, dimension):
    """Export a coordinate dimension as a scalar field."""
    result = get_backend().coord_to_sf(input_file, output_file, dimension=dimension)
    output(result)


@sf_group.command("arithmetic")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default="0", help="Scalar field index or name")
@click.option("--operation", type=str, default="SQRT",
              help="SQRT, ABS, INV, EXP, LOG, LOG10, etc.")
@handle_error
def sf_arithmetic(input_file, output_file, sf_index, operation):
    """Apply a unary arithmetic operation to a scalar field."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().sf_arithmetic(input_file, output_file,
                                         sf_index=sf_idx, operation=operation)
    output(result)


@sf_group.command("operation")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default="0", help="Scalar field index or name")
@click.option("--operation", type=click.Choice(["ADD", "SUB", "MULTIPLY", "DIVIDE"]),
              default="ADD")
@click.option("--value", type=float, required=True)
@handle_error
def sf_operation(input_file, output_file, sf_index, operation, value):
    """Apply an arithmetic operation with a scalar value to a SF."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().sf_operation(input_file, output_file,
                                        sf_index=sf_idx, operation=operation,
                                        value=value)
    output(result)


@sf_group.command("gradient")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default=None, help="SF index/name (uses active if not specified)")
@click.option("--radius", type=float, default=0.1, help="Search radius")
@click.option("--euclidean", is_flag=True, help="Use Euclidean gradient")
@handle_error
def sf_gradient(input_file, output_file, sf_index, radius, euclidean):
    """Compute scalar field gradient."""
    # If sf_index specified, set it as active first
    if sf_index is not None:
        temp_file = output_file.replace(".ply", "_temp.ply")
        try:
            sf_idx = int(sf_index)
        except ValueError:
            sf_idx = sf_index
        get_backend().set_active_sf(input_file, temp_file, sf_index=sf_idx)
        input_file = temp_file
    
    result = get_backend().sf_gradient(input_file, output_file, euclidean=euclidean)
    output(result)


@sf_group.command("filter")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default=None, help="SF index/name (uses active if not specified)")
@click.option("--min", "min_val", type=str, default="MIN")
@click.option("--max", "max_val", type=str, default="MAX")
@handle_error
def sf_filter(input_file, output_file, sf_index, min_val, max_val):
    """Filter points by scalar field value range."""
    # If sf_index specified, set it as active first
    if sf_index is not None:
        temp_file = output_file.replace(".ply", "_temp.ply")
        try:
            sf_idx = int(sf_index)
        except ValueError:
            sf_idx = sf_index
        get_backend().set_active_sf(input_file, temp_file, sf_index=sf_idx)
        input_file = temp_file
    
    result = get_backend().filter_sf(input_file, output_file,
                                     min_val=min_val, max_val=max_val)
    output(result)


@sf_group.command("color-scale")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default=None, help="SF index/name (uses active if not specified)")
@click.option("--scale-file", type=click.Path(exists=True), required=True,
              help="Color scale XML file path")
@handle_error
def sf_color_scale(input_file, output_file, sf_index, scale_file):
    """Apply a color scale file to a scalar field."""
    # If sf_index specified, set it as active first
    if sf_index is not None:
        temp_file = output_file.replace(".ply", "_temp.ply")
        try:
            sf_idx = int(sf_index)
        except ValueError:
            sf_idx = sf_index
        get_backend().set_active_sf(input_file, temp_file, sf_index=sf_idx)
        input_file = temp_file
    
    result = get_backend().sf_color_scale(input_file, output_file,
                                          scale_file=scale_file)
    output(result)


@sf_group.command("convert-to-rgb")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default=None, help="SF index/name (uses active if not specified)")
@handle_error
def sf_convert_to_rgb(input_file, output_file, sf_index):
    """Convert a scalar field to RGB colors."""
    # If sf_index specified, set it as active first
    if sf_index is not None:
        temp_file = output_file.replace(".ply", "_temp.ply")
        try:
            sf_idx = int(sf_index)
        except ValueError:
            sf_idx = sf_index
        get_backend().set_active_sf(input_file, temp_file, sf_index=sf_idx)
        input_file = temp_file
    
    result = get_backend().sf_convert_to_rgb(input_file, output_file)
    output(result)


@sf_group.command("set-active")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default="0", help="Scalar field index or name")
@handle_error
def sf_set_active(input_file, output_file, sf_index):
    """Set the active scalar field."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().set_active_sf(input_file, output_file, sf_index=sf_idx)
    output(result)


@sf_group.command("rename")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--old", "--sf-index", type=str, default="0", help="Current SF index or name to rename")
@click.option("--new", "--new-name", "new_name", required=True, help="New name for the scalar field")
@handle_error
def sf_rename(input_file, output_file, old, new_name):
    """Rename a scalar field."""
    try:
        sf_idx = int(old)
    except ValueError:
        sf_idx = old
    result = get_backend().rename_sf(input_file, output_file,
                                     sf_index=sf_idx, new_name=new_name)
    output(result)


@sf_group.command("remove")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--sf-index", "--sf", type=str, default="0", help="Scalar field index or name to remove")
@handle_error
def sf_remove(input_file, output_file, sf_index):
    """Remove a specific scalar field."""
    try:
        sf_idx = int(sf_index)
    except ValueError:
        sf_idx = sf_index
    result = get_backend().remove_sf(input_file, output_file, sf_index=sf_idx)
    output(result)


@sf_group.command("remove-all")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def sf_remove_all(input_file, output_file):
    """Remove all scalar fields."""
    result = get_backend().remove_all_sfs(input_file, output_file)
    output(result)


# ══════════════════════════════════════════════════════════════════════════
# Normals Group Commands (convenience wrappers for process *-normals commands)
# ══════════════════════════════════════════════════════════════════════════

@normals_group.command("octree")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--radius", type=str, default="AUTO", help="Radius or AUTO")
@click.option("--orient", type=str, default="", help="Normal orientation mode")
@click.option("--model", type=click.Choice(["", "LS", "TRI", "QUADRIC"]), default="")
@handle_error
def normals_octree(input_file, output_file, radius, orient, model):
    """Compute normals using octree method."""
    try:
        r = float(radius)
    except ValueError:
        r = radius
    result = get_backend().octree_normals(input_file, output_file,
                                          radius=r, orient=orient, model=model)
    output(result)


@normals_group.command("orient-mst")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@click.option("--knn", type=int, default=6)
@handle_error
def normals_orient_mst(input_file, output_file, knn):
    """Orient normals via Minimum Spanning Tree."""
    result = get_backend().orient_normals_mst(input_file, output_file, knn=knn)
    output(result)


@normals_group.command("invert")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def normals_invert(input_file, output_file):
    """Invert point cloud normals."""
    result = get_backend().invert_normals(input_file, output_file)
    output(result)


@normals_group.command("clear")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def normals_clear(input_file, output_file):
    """Remove all normals from a point cloud."""
    result = get_backend().clear_normals(input_file, output_file)
    output(result)


@normals_group.command("to-dip")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def normals_to_dip(input_file, output_file):
    """Convert normals to dip/dip-direction scalar fields."""
    result = get_backend().normals_to_dip(input_file, output_file)
    output(result)


@normals_group.command("to-sfs")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(), required=True)
@handle_error
def normals_to_sfs(input_file, output_file):
    """Convert normals to Nx/Ny/Nz scalar fields."""
    result = get_backend().normals_to_sfs(input_file, output_file)
    output(result)


# ── REPL ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--project", "project_path", type=str, default=None)
@handle_error
def repl(project_path):
    """Start interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("acloudviewer", version="3.1.0")

    if project_path:
        sess = get_session()
        proj = open_project(project_path)
        sess.set_project(proj, project_path)

    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        # ── General (no backend required) ──
        "info":          "show backend info",
        "check":         "check installation status",
        "install":       "auto|app|wheel — install components",
        "formats":       "list supported formats",
        "session":       "status|undo|redo|save|history — session management",
        "methods":       "[GUI] list available RPC methods",
        # ── Headless (binary -SILENT mode, no GUI needed) ──
        "convert":       "[headless] convert <in> <out>",
        "batch-convert": "[headless] batch-convert <dir-in> <dir-out> [-f .ply]",
        "process":       "[headless] subsample|normals|icp|sor|c2c-dist|c2m-dist|crop|density|curvature|roughness|delaunay|sample-mesh|...",
        "sf":            "[headless] coord-to-sf|arithmetic|operation|gradient|filter|color-scale|convert-to-rgb|set-active|rename|remove|...",
        "normals":       "[headless] octree|orient-mst|invert|clear|to-dip|to-sfs",
        "reconstruct":   "[headless] mesh|auto|extract-features|match|sparse|undistort|dense-stereo|fuse|poisson|...",
        "sibr":          "[headless] viewer|tool|prepare-colmap|texture-mesh|unwrap-mesh|tonemapper|align-meshes|...",
        "transform":     "[headless/GUI] apply|apply-file — transformation",
        # ── GUI (requires running ACloudViewer with JSON-RPC) ──
        "open":          "[GUI] open <file> in ACloudViewer",
        "export":        "[GUI] export <entity_id> <output>",
        "clear":         "[GUI] clear all entities from scene",
        "scene":         "[GUI] list|info|remove|show|hide|select|clear",
        "entity":        "[GUI] rename|set-color — entity manipulation",
        "view":          "[GUI] screenshot|camera|orient|zoom|refresh|perspective|pointsize",
        "cloud":         "[GUI] paint-uniform|paint-by-height|paint-by-scalar-field|get-scalar-fields|crop",
        "mesh":          "[GUI] simplify|smooth|subdivide|sample-points",
        # ──
        "help":          "show this help",
        "quit":          "exit REPL",
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
