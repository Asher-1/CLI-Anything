"""Dual-mode backend for ACloudViewer.

GUI mode:  controls a running ACloudViewer instance via JSON-RPC WebSocket.
Headless:  invokes the ACloudViewer binary in CLI (-SILENT) mode via subprocess.

The headless mode does NOT depend on any Python bindings — it calls the same
ACloudViewer binary with CloudCompare-compatible flags like:
    ACloudViewer -SILENT -O input.ply -SS SPATIAL 0.05 -SAVE_CLOUDS

Cross-platform support:
    Linux:   ACloudViewer.sh launcher (preferred) or bare ACloudViewer binary
    macOS:   ACloudViewer inside .app bundle or standalone binary
    Windows: ACloudViewer.bat launcher (preferred) or ACloudViewer.exe
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

from .rpc_client import ACloudViewerRPCClient, RPCError

POINT_CLOUD_FORMATS = {
    ".ply", ".pcd", ".xyz", ".xyzn", ".xyzrgb", ".pts", ".txt", ".asc",
    ".csv", ".las", ".laz", ".e57", ".ptx", ".bin", ".sbf", ".drc",
}

MESH_FORMATS = {
    ".obj", ".stl", ".off", ".gltf", ".glb", ".fbx", ".dae", ".3ds",
    ".ply", ".dxf", ".vtk",
}

IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

ALL_SUPPORTED_FORMATS = POINT_CLOUD_FORMATS | MESH_FORMATS | IMAGE_FORMATS | {
    ".shp", ".pov", ".pn", ".pv", ".poly", ".sx",
}

CLOUD_FORMAT_MAP = {
    ".ply": "PLY", ".pcd": "PCD", ".xyz": "ASCII", ".pts": "PTS",
    ".las": "LAS", ".laz": "LAS", ".e57": "E57", ".bin": "BIN",
    ".sbf": "SBF", ".asc": "ASCII", ".csv": "ASCII", ".txt": "ASCII",
    ".drc": "DRC",
}

MESH_FORMAT_MAP = {
    ".obj": "OBJ", ".stl": "STL", ".off": "OFF", ".fbx": "FBX",
    ".ply": "PLY", ".dxf": "DXF", ".vtk": "VTK",
}


class BackendError(Exception):
    pass


class ACloudViewerBackend:
    """Unified backend: auto-selects GUI (RPC) or headless (binary CLI) mode."""

    def __init__(self, mode: str = "auto", rpc_url: str = "ws://localhost:6001"):
        self._mode = mode
        self._rpc_url = rpc_url
        self._rpc: ACloudViewerRPCClient | None = None
        self._binary: str | None = None

        if mode == "auto":
            self._mode = self._detect_mode()
        if self._mode == "gui":
            self._rpc = ACloudViewerRPCClient(rpc_url)
        self._binary = self.find_binary()

    @property
    def mode(self) -> str:
        return self._mode

    def _detect_mode(self) -> str:
        try:
            client = ACloudViewerRPCClient(self._rpc_url)
            client.connect()
            client.ping()
            client.close()
            return "gui"
        except Exception:
            return "headless"

    # =====================================================================
    # Binary discovery & invocation
    # =====================================================================

    @staticmethod
    def _binary_names() -> tuple[str, ...]:
        """Platform-specific binary/launcher names, preferred first.

        Linux:   ACloudViewer.sh (sets LD_LIBRARY_PATH), ACloudViewer
        macOS:   ACloudViewer (standalone or inside .app bundle)
        Windows: ACloudViewer.bat (sets PATH/env), ACloudViewer.exe
        """
        if IS_WINDOWS:
            return ("ACloudViewer.bat", "ACloudViewer.exe")
        if IS_MACOS:
            return ("ACloudViewer", "ACloudViewer.sh")
        return ("ACloudViewer.sh", "ACloudViewer")

    @staticmethod
    def _install_dirs() -> list[Path]:
        """Standard install locations per platform."""
        if IS_WINDOWS:
            dirs: list[Path] = []
            for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                         os.environ.get("LOCALAPPDATA", ""),
                         str(Path.home())):
                if base:
                    dirs.append(Path(base) / "ACloudViewer")
                    dirs.append(Path(base) / "ACloudViewer" / "bin")
            return dirs
        if IS_MACOS:
            return [
                Path("/Applications/ACloudViewer.app/Contents/MacOS"),
                Path.home() / "Applications" / "ACloudViewer.app" / "Contents" / "MacOS",
                Path.home() / "ACloudViewer.app" / "Contents" / "MacOS",
                # Install-prefix layout: ~/ACloudViewer/bin/ACloudViewer.app/Contents/MacOS
                Path.home() / "ACloudViewer" / "bin" / "ACloudViewer.app" / "Contents" / "MacOS",
                Path.home() / "ACloudViewer" / "ACloudViewer.app" / "Contents" / "MacOS",
                Path.home() / "ACloudViewer",
                Path("/usr/local/bin"),
            ]
        return [
            Path("/usr/local/bin"),
            Path("/opt/ACloudViewer/bin"),
            Path("/usr/share/ACloudViewer"),
            Path.home() / ".local" / "share" / "ACloudViewer" / "bin",
            Path.home() / "ACloudViewer",
        ]

    @staticmethod
    def _resolve_app_bundle(directory: Path) -> str | None:
        """On macOS, resolve ACloudViewer.app bundle inside a directory."""
        if not IS_MACOS:
            return None
        exe = directory / "ACloudViewer.app" / "Contents" / "MacOS" / "ACloudViewer"
        if exe.is_file():
            return str(exe)
        return None

    @staticmethod
    def find_binary() -> str | None:
        """Find the ACloudViewer executable or launcher script.

        Search order:
          1. ACV_BINARY environment variable (explicit override)
          2. Platform-appropriate names on PATH
          3. Standard install locations per OS (including macOS .app bundles)
        """
        env_binary = os.environ.get("ACV_BINARY")
        if env_binary and Path(env_binary).exists():
            return env_binary

        names = ACloudViewerBackend._binary_names()
        for name in names:
            path = shutil.which(name)
            if path:
                return path

        for d in ACloudViewerBackend._install_dirs():
            for name in names:
                p = d / name
                if p.is_file():
                    return str(p)
            resolved = ACloudViewerBackend._resolve_app_bundle(d)
            if resolved:
                return resolved
        return None

    @staticmethod
    def _build_env_for_binary(binary_path: str) -> dict[str, str]:
        """Set up library search paths for the ACloudViewer binary.

        Platform-specific env setup when invoking the bare binary:
          Linux:   LD_LIBRARY_PATH = <bin_dir>:<bin_dir>/lib
          macOS:   DYLD_LIBRARY_PATH (with SIP caveats; .app bundles
                   embed their own rpath so this is usually a no-op)
          Windows: PATH prepended with <bin_dir> (DLL search)

        All platforms: QT_QPA_PLATFORM=offscreen for headless CLI.
        """
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"

        if binary_path.endswith((".sh", ".bat")):
            return env

        bin_dir = str(Path(binary_path).parent)
        lib_dir = str(Path(bin_dir) / "lib")
        plugin_python_dir = str(Path(bin_dir) / "plugins" / "Python")
        path_sep = ";" if IS_WINDOWS else ":"

        if IS_WINDOWS:
            existing_path = env.get("PATH", "")
            env["PATH"] = path_sep.join(
                filter(None, [bin_dir, lib_dir, existing_path]))
        elif IS_MACOS:
            existing_dyld = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = path_sep.join(
                filter(None, [bin_dir, lib_dir, existing_dyld]))
        else:
            existing_ld = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = path_sep.join(
                filter(None, [bin_dir, lib_dir, existing_ld]))

        existing_pypath = env.get("PYTHONPATH", "")
        if Path(plugin_python_dir).is_dir():
            env["PYTHONPATH"] = path_sep.join(
                filter(None, [plugin_python_dir, existing_pypath]))

        return env

    @staticmethod
    def get_version() -> str | None:
        binary = ACloudViewerBackend.find_binary()
        if not binary:
            return None
        try:
            env = ACloudViewerBackend._build_env_for_binary(binary)
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True, text=True, timeout=10, env=env)
            return result.stdout.strip() or result.stderr.strip()
        except Exception:
            return None

    def _ensure_binary(self) -> str:
        if self._binary:
            return self._binary
        self._binary = self.find_binary()
        if not self._binary:
            raise BackendError(
                "ACloudViewer binary not found. Set ACV_BINARY env var or add to PATH.")
        return self._binary

    def _run_cli(self, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run ACloudViewer in CLI mode with -SILENT prefix."""
        binary = self._ensure_binary()
        cmd = [binary, "-SILENT"] + args
        env = self._build_env_for_binary(binary)
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, env=env)
        if result.returncode != 0:
            combined = (result.stderr + result.stdout).strip()
            error_keywords = ("error:", "fatal:", "exception:", "segfault",
                              "cannot open", "not found", "no such file")
            has_real_error = any(
                kw in combined.lower() for kw in error_keywords
            )
            if has_real_error:
                raise BackendError(
                    f"CLI failed (exit {result.returncode}): {combined[:500]}")
        return result

    # =====================================================================
    # File I/O
    # =====================================================================

    def open_file(self, path: str, silent: bool = True) -> dict:
        if self._mode == "gui":
            return self._rpc.open_file(path, silent=silent)
        if not Path(path).exists():
            raise BackendError(f"File not found: {path}")
        return {"path": path, "mode": "headless", "status": "loaded"}

    def export_file(self, entity_id: int, path: str) -> dict:
        if self._mode == "gui":
            return self._rpc.export_entity(entity_id, path)
        raise BackendError("export_file requires GUI mode (entity_id is a GUI concept)")

    def convert_format(self, input_path: str, output_path: str,
                       sample_points: int = 100000) -> dict:
        """Convert between formats using ACloudViewer binary CLI."""
        if not Path(input_path).exists():
            raise BackendError(f"Input not found: {input_path}")

        in_ext = Path(input_path).suffix.lower()
        out_ext = Path(output_path).suffix.lower()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if self._mode == "gui":
            try:
                return self._rpc.file_convert(input_path, output_path)
            except RPCError:
                pass  # fall through to binary CLI

        is_cloud_in = in_ext in POINT_CLOUD_FORMATS
        is_mesh_in = in_ext in MESH_FORMATS
        is_cloud_out = out_ext in POINT_CLOUD_FORMATS
        is_mesh_out = out_ext in MESH_FORMATS

        with tempfile.TemporaryDirectory() as tmpdir:
            args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]

            out_fmt_key = CLOUD_FORMAT_MAP.get(out_ext) or MESH_FORMAT_MAP.get(out_ext)

            if is_cloud_in and is_cloud_out:
                if out_fmt_key:
                    args += ["-C_EXPORT_FMT", out_fmt_key]
                args += ["-SAVE_CLOUDS", "FILE", output_path]
            elif is_mesh_in and is_mesh_out:
                if out_fmt_key:
                    args += ["-M_EXPORT_FMT", out_fmt_key]
                args += ["-SAVE_MESHES", "FILE", output_path]
            elif is_mesh_in and is_cloud_out:
                args += ["-SAMPLE_MESH", "POINTS", str(sample_points)]
                if out_fmt_key:
                    args += ["-C_EXPORT_FMT", out_fmt_key]
                args += ["-SAVE_CLOUDS", "FILE", output_path]
            elif is_cloud_in and is_mesh_out:
                args += ["-DELAUNAY"]
                if out_fmt_key:
                    args += ["-M_EXPORT_FMT", out_fmt_key]
                args += ["-SAVE_MESHES", "FILE", output_path]
            else:
                args += ["-SAVE_CLOUDS", "FILE", output_path]

            self._run_cli(args)

        if not Path(output_path).exists():
            out_dir = Path(output_path).parent
            out_stem = Path(output_path).stem
            in_stem = Path(input_path).stem
            candidates = (
                list(out_dir.glob(f"{out_stem}*{out_ext}"))
                + list(out_dir.glob(f"{in_stem}*{out_ext}"))
            )
            seen = set()
            unique = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    unique.append(c)
            if unique:
                unique[0].rename(output_path)

        return {
            "input": input_path, "output": output_path,
            "input_format": in_ext, "output_format": out_ext,
            "status": "converted" if Path(output_path).exists() else "failed",
        }

    def batch_convert(self, input_dir: str, output_dir: str,
                      output_format: str = ".ply",
                      input_extensions: list[str] | None = None,
                      sample_points: int = 100000) -> dict:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        if not output_format.startswith("."):
            output_format = "." + output_format

        if input_extensions is None:
            input_extensions = list(ALL_SUPPORTED_FORMATS)
        else:
            input_extensions = ["." + e.lstrip(".") for e in input_extensions]

        results, errors = [], []
        for f in sorted(Path(input_dir).iterdir()):
            if not f.is_file() or f.suffix.lower() not in input_extensions:
                continue
            out_path = str(Path(output_dir) / (f.stem + output_format))
            try:
                r = self.convert_format(str(f), out_path, sample_points=sample_points)
                results.append(r)
            except Exception as e:
                errors.append({"file": str(f), "error": str(e)})

        return {
            "input_dir": input_dir, "output_dir": output_dir,
            "output_format": output_format,
            "converted": len(results), "errors": len(errors),
            "files": results, "error_details": errors or None,
        }

    @staticmethod
    def supported_formats() -> dict:
        return {
            "point_cloud": sorted(POINT_CLOUD_FORMATS),
            "mesh": sorted(MESH_FORMATS),
            "image": sorted(IMAGE_FORMATS),
            "all": sorted(ALL_SUPPORTED_FORMATS),
        }

    # =====================================================================
    # Scene management (GUI only)
    # =====================================================================

    def scene_list(self, recursive: bool = True) -> list[dict]:
        if self._mode != "gui":
            raise BackendError("scene_list requires GUI mode")
        return self._rpc.scene_list(recursive=recursive)

    def scene_info(self, entity_id: int) -> dict:
        if self._mode != "gui":
            raise BackendError("scene_info requires GUI mode")
        return self._rpc.scene_info(entity_id)

    def scene_remove(self, entity_id: int) -> None:
        if self._mode != "gui":
            raise BackendError("scene_remove requires GUI mode")
        self._rpc.call("scene.remove", {"entity_id": entity_id})

    # =====================================================================
    # Processing — headless via ACloudViewer CLI, GUI via RPC
    # =====================================================================

    def subsample(self, input_path: str, output_path: str,
                  method: str = "SPATIAL", parameter: float = 0.05,
                  entity_id: int | None = None) -> dict:
        if self._mode == "gui" and entity_id is not None:
            return self._rpc.call("cloud.subsample", {
                "entity_id": entity_id, "method": method.lower(),
                "step": parameter,
            })
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SS", method.upper(), str(parameter),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "method": method, "parameter": parameter,
            "status": "completed",
        }

    def compute_normals(self, input_path: str, output_path: str,
                        radius: float = 0.0,
                        entity_id: int | None = None) -> dict:
        if self._mode == "gui" and entity_id is not None:
            return self._rpc.call("cloud.computeNormals", {
                "entity_id": entity_id, "radius": radius,
            })
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]
        if radius > 0:
            args += ["-OCTREE_NORMALS", str(radius)]
        else:
            args += ["-OCTREE_NORMALS", "AUTO"]
        args += ["-SAVE_CLOUDS", "FILE", output_path]
        self._run_cli(args)
        return {
            "input": input_path, "output": output_path,
            "has_normals": True, "status": "completed",
        }

    def icp_registration(self, data_path: str, reference_path: str,
                         output_path: str | None = None,
                         iterations: int = 100,
                         overlap: float = 100.0) -> dict:
        out = output_path or str(
            Path(data_path).parent / f"{Path(data_path).stem}_registered.ply")
        self._run_cli([
            "-O", reference_path, "-O", data_path,
            "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-ICP", "-ITER", str(iterations),
            "-OVERLAP", str(overlap),
            "-SAVE_CLOUDS", "FILE", out,
        ])
        return {
            "data": data_path, "reference": reference_path,
            "output": out, "iterations": iterations,
            "status": "completed",
        }

    def sor_filter(self, input_path: str, output_path: str,
                   knn: int = 6, sigma: float = 1.0) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SOR", str(knn), str(sigma),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "knn": knn, "sigma": sigma, "status": "completed",
        }

    def crop(self, input_path: str, output_path: str,
             min_x: float = 0, min_y: float = 0, min_z: float = 0,
             max_x: float = 1, max_y: float = 1, max_z: float = 1,
             entity_id: int | None = None) -> dict:
        if self._mode == "gui" and entity_id is not None:
            return self._rpc.call("cloud.crop", {
                "entity_id": entity_id,
                "min_x": min_x, "min_y": min_y, "min_z": min_z,
                "max_x": max_x, "max_y": max_y, "max_z": max_z,
            })
        bbox = f"{min_x}:{max_x}:{min_y}:{max_y}:{min_z}:{max_z}"
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CROP", bbox,
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "status": "completed",
        }

    def c2c_distance(self, compared_path: str, reference_path: str,
                     output_path: str | None = None,
                     max_dist: float = 0.0) -> dict:
        """Cloud-to-cloud distance computation."""
        out = output_path or str(
            Path(compared_path).parent / f"{Path(compared_path).stem}_C2C_DIST.ply")
        args = [
            "-O", reference_path, "-O", compared_path,
            "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-C2C_DIST",
        ]
        if max_dist > 0:
            args += ["-MAX_DIST", str(max_dist)]
        args += ["-SAVE_CLOUDS", "FILE", out]
        self._run_cli(args)
        return {
            "compared": compared_path, "reference": reference_path,
            "output": out, "status": "completed",
        }

    def c2m_distance(self, cloud_path: str, mesh_path: str,
                     output_path: str | None = None,
                     max_dist: float = 0.0) -> dict:
        """Cloud-to-mesh distance computation."""
        out = output_path or str(
            Path(cloud_path).parent / f"{Path(cloud_path).stem}_C2M_DIST.ply")
        args = [
            "-O", mesh_path, "-O", cloud_path,
            "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-C2M_DIST",
        ]
        if max_dist > 0:
            args += ["-MAX_DIST", str(max_dist)]
        args += ["-SAVE_CLOUDS", "FILE", out]
        self._run_cli(args)
        return {
            "cloud": cloud_path, "mesh": mesh_path,
            "output": out, "status": "completed",
        }

    def delaunay(self, input_path: str, output_path: str,
                 max_edge_length: float = 0.0) -> dict:
        args = [
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-DELAUNAY",
        ]
        if max_edge_length > 0:
            args += ["-MAX_EDGE_LENGTH", str(max_edge_length)]
        args += ["-SAVE_MESHES", "FILE", output_path]
        self._run_cli(args)
        return {
            "input": input_path, "output": output_path,
            "status": "completed",
        }

    def density(self, input_path: str, output_path: str,
                radius: float = 0.5) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-DENSITY", str(radius),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "radius": radius, "status": "completed",
        }

    def curvature(self, input_path: str, output_path: str,
                  curvature_type: str = "MEAN", radius: float = 0.5) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CURV", curvature_type.upper(), str(radius),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "type": curvature_type, "radius": radius,
            "status": "completed",
        }

    def roughness(self, input_path: str, output_path: str,
                  radius: float = 0.5) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-ROUGH", str(radius),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "radius": radius, "status": "completed",
        }

    def sample_mesh(self, input_path: str, output_path: str,
                    points: int = 100000) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SAMPLE_MESH", "POINTS", str(points),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "points": points, "status": "completed",
        }

    def apply_transformation(self, input_path: str, output_path: str,
                             matrix_file: str) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-APPLY_TRANS", matrix_file,
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "matrix_file": matrix_file, "status": "completed",
        }

    def color_banding(self, input_path: str, output_path: str,
                      axis: str = "Z", frequency: float = 10.0) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CBANDING", axis.upper(), str(frequency),
            "-SAVE_CLOUDS", "FILE", output_path,
        ])
        return {
            "input": input_path, "output": output_path,
            "axis": axis, "frequency": frequency, "status": "completed",
        }

    # =====================================================================
    # Cloud colorization (GUI RPC)
    # =====================================================================

    def cloud_paint_uniform_gui(self, entity_id: int,
                                r: int = 255, g: int = 255, b: int = 255) -> dict:
        if self._mode != "gui":
            raise BackendError("Requires GUI mode")
        return self._rpc.call("cloud.paintUniform",
                              {"entity_id": entity_id, "r": r, "g": g, "b": b})

    def cloud_paint_by_height_gui(self, entity_id: int,
                                   axis: str = "z") -> dict:
        if self._mode != "gui":
            raise BackendError("Requires GUI mode")
        return self._rpc.call("cloud.paintByHeight",
                              {"entity_id": entity_id, "axis": axis})

    def cloud_paint_by_scalar_field_gui(self, entity_id: int,
                                         field_name: str = "") -> dict:
        if self._mode != "gui":
            raise BackendError("Requires GUI mode")
        return self._rpc.call("cloud.paintByScalarField",
                              {"entity_id": entity_id, "field_name": field_name})

    # =====================================================================
    # View control (GUI only)
    # =====================================================================

    def screenshot_gui(self, filename: str) -> dict:
        if self._mode != "gui":
            raise BackendError("Requires GUI mode")
        return self._rpc.call("view.screenshot", {"filename": filename})

    def get_camera(self) -> dict:
        if self._mode != "gui":
            raise BackendError("Requires GUI mode")
        return self._rpc.call("view.getCamera")

    def entity_rename(self, entity_id: int, name: str) -> None:
        if self._mode != "gui":
            raise BackendError("Requires GUI mode")
        self._rpc.call("entity.rename", {"entity_id": entity_id, "name": name})

    # =====================================================================
    # SIBR dataset tools (headless -SIBR_TOOL dispatch)
    # =====================================================================

    SIBR_TOOLS = (
        "prepareColmap4Sibr", "tonemapper", "unwrapMesh", "textureMesh",
        "clippingPlanes", "cropFromCenter", "nvmToSIBR", "distordCrop",
        "cameraConverter", "alignMeshes",
    )

    def sibr_tool(self, tool_name: str, extra_args: list[str] | None = None) -> dict:
        """Run any SIBR dataset tool by name.

        Dispatches to ACloudViewer: -SIBR_TOOL <tool_name> [extra_args...]
        """
        if tool_name not in self.SIBR_TOOLS:
            raise BackendError(
                f"Unknown SIBR tool '{tool_name}'. "
                f"Available: {', '.join(self.SIBR_TOOLS)}")
        args = ["-SIBR_TOOL", tool_name] + (extra_args or [])
        output = self._run_cli(args)
        return {"tool": tool_name, "output": output, "status": "completed"}

    def sibr_prepare_colmap(self, dataset_path: str,
                            fix_metadata: bool = False) -> dict:
        """Prepare Colmap output for SIBR rendering."""
        args = ["-path", dataset_path]
        if fix_metadata:
            args.append("-fix_metadata")
        return self.sibr_tool("prepareColmap4Sibr", args)

    def sibr_texture_mesh(self, dataset_path: str,
                          extra_args: list[str] | None = None) -> dict:
        """Generate textured mesh from SIBR dataset."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("textureMesh", args)

    def sibr_unwrap_mesh(self, dataset_path: str,
                         extra_args: list[str] | None = None) -> dict:
        """UV-unwrap a mesh for texturing."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("unwrapMesh", args)

    def sibr_tonemap(self, dataset_path: str,
                     extra_args: list[str] | None = None) -> dict:
        """Apply tonemapping to HDR images in a dataset."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("tonemapper", args)

    def sibr_align_meshes(self, dataset_path: str,
                          extra_args: list[str] | None = None) -> dict:
        """Align meshes in the dataset."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("alignMeshes", args)

    def sibr_camera_converter(self, dataset_path: str,
                              extra_args: list[str] | None = None) -> dict:
        """Convert camera formats for SIBR."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("cameraConverter", args)

    def sibr_nvm_to_sibr(self, dataset_path: str,
                         extra_args: list[str] | None = None) -> dict:
        """Convert NVM format to SIBR dataset layout."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("nvmToSIBR", args)

    def sibr_crop_from_center(self, dataset_path: str,
                              extra_args: list[str] | None = None) -> dict:
        """Crop dataset from center coordinates."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("cropFromCenter", args)

    def sibr_clipping_planes(self, dataset_path: str,
                             extra_args: list[str] | None = None) -> dict:
        """Compute or apply clipping planes for a dataset."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("clippingPlanes", args)

    def sibr_distord_crop(self, dataset_path: str,
                          extra_args: list[str] | None = None) -> dict:
        """Apply distortion-aware cropping to images."""
        args = ["-path", dataset_path] + (extra_args or [])
        return self.sibr_tool("distordCrop", args)
