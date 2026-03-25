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
    ".neu", ".csv", ".las", ".laz", ".e57", ".ptx", ".bin", ".sbf", ".drc",
    ".vtk",
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
    ".ply": "PLY", ".pcd": "PCD", ".pts": "ASC",
    ".las": "LAS", ".laz": "LAS", ".e57": "E57", ".bin": "BIN",
    ".sbf": "SBF", ".drc": "DRC", ".vtk": "VTK",
    ".asc": "ASC", ".xyz": "ASC", ".txt": "ASC", ".csv": "ASC",
    ".xyzrgb": "ASC", ".xyzn": "ASC", ".neu": "ASC",
}

_FORMAT_ALIAS_EXTS: dict[str, list[str]] = {
    ".xyz": [".xyz", ".asc"],
    ".csv": [".csv", ".asc"],
    ".txt": [".txt", ".asc"],
    ".pts": [".pts", ".asc"],
    ".xyzrgb": [".xyzrgb", ".asc"],
    ".xyzn": [".xyzn", ".asc"],
    ".neu": [".neu", ".asc"],
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
        Windows: ACloudViewer.exe (preferred), ACloudViewer.bat (GUI wrapper)
        """
        if IS_WINDOWS:
            return ("ACloudViewer.exe", "ACloudViewer.bat")
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
          Linux:   LD_LIBRARY_PATH + QT_QPA_PLATFORM=offscreen
          macOS:   DYLD_LIBRARY_PATH; QT_QPA_PLATFORM left unset so
                   main.cpp can probe for offscreen/minimal/cocoa
          Windows: PATH prepended + QT_QPA_PLATFORM=offscreen
        """
        env = os.environ.copy()
        if IS_MACOS:
            env.pop("QT_QPA_PLATFORM", None)
        else:
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
        """Detect ACloudViewer version.

        Priority: --version / -v flag > maintenancetool > .desktop > CHANGELOG.
        """
        binary = ACloudViewerBackend.find_binary()
        if not binary:
            return None
        binary = ACloudViewerBackend._resolve_exe(binary)

        import re as _re
        env = ACloudViewerBackend._build_env_for_binary(binary)

        for flag in ("--version", "-v"):
            try:
                result = subprocess.run(
                    [binary, flag],
                    capture_output=True, text=True, timeout=10, env=env,
                )
                if result.returncode == 0:
                    out = result.stdout.strip()
                    m = _re.search(r"(\d+\.\d+\.\d+\S*)", out)
                    if m:
                        return m.group(1)
                    if out:
                        return out
            except Exception:
                pass

        binary_dir = Path(binary).resolve().parent

        mt = binary_dir / "maintenancetool"
        if mt.exists():
            try:
                result = subprocess.run(
                    [str(mt), "li"],
                    capture_output=True, text=True, timeout=10,
                )
                m = _re.search(
                    r'name="ACloudViewer"[^>]*version="([^"]+)"',
                    result.stdout,
                )
                if m:
                    return m.group(1)
            except Exception:
                pass

        desktop = binary_dir / "ACloudViewer.desktop"
        if desktop.exists():
            try:
                for line in desktop.read_text().splitlines():
                    if line.startswith("Version="):
                        return line.split("=", 1)[1].strip()
            except Exception:
                pass

        for name in ("CHANGELOG.txt", "CHANGELOG.md"):
            changelog = binary_dir / name
            if changelog.exists():
                try:
                    text = changelog.read_text(errors="replace")[:2000]
                    m = _re.search(r"v?(\d+\.\d+\.\d+)", text)
                    if m:
                        return m.group(1)
                except Exception:
                    pass

        return None

    def _require_gui(self, method_name: str) -> None:
        if self._mode != "gui":
            raise BackendError(f"{method_name} requires GUI mode")

    def _ensure_binary(self) -> str:
        if self._binary:
            return self._binary
        self._binary = self.find_binary()
        if self._binary:
            return self._binary

        import sys
        if sys.stdin.isatty() and sys.stdout.isatty():
            self._binary = self._interactive_install()
            if self._binary:
                return self._binary

        raise BackendError(
            "ACloudViewer binary not found.\n"
            "\n"
            "Quick fix options:\n"
            "  1. Auto-install:  cli-anything-acloudviewer install app\n"
            "  2. Manual:        Download from https://asher-1.github.io/ACloudViewer/\n"
            "  3. Already have it? Set: export ACV_BINARY=/path/to/ACloudViewer\n"
            "\n"
            "Run 'cli-anything-acloudviewer check' for full diagnostics."
        )

    def _interactive_install(self) -> str | None:
        """Prompt user to install ACloudViewer when running interactively."""
        from .installer import (
            detect_platform, get_latest_release, find_matching_app,
            install_app, InstallError, HOMEPAGE,
        )

        print("\n  ACloudViewer binary not found.")
        try:
            answer = input("  Install now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if answer and answer not in ("y", "yes"):
            return None

        print("  Release channel:  [1] stable (recommended)  [2] beta")
        try:
            ch = input("  Select [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        channel = "beta" if ch == "2" else "stable"

        plat = detect_platform()
        cpu_only = True
        if plat.has_nvidia_gpu:
            print("  NVIDIA GPU detected:  [1] CUDA (larger)  [2] CPU-only (smaller)")
            try:
                gv = input("  Select [1]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            cpu_only = (gv == "2")

        try:
            print("  Querying GitHub releases ...")
            release = get_latest_release(channel=channel)
            asset = find_matching_app(release, plat, cpu_only=cpu_only)
            if not asset:
                print(f"  No matching installer found for your platform.")
                print(f"  Download manually from: {HOMEPAGE}")
                return None

            print(f"\n  Package: {asset.name} ({asset.size_mb:.0f} MB)")
            print(f"  Release: {release.label}")
            try:
                confirm = input("  Download and install? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return None
            if confirm and confirm not in ("y", "yes"):
                return None

            result = install_app(asset)
            status = result.get("status", "")
            if result.get("binary"):
                binary = result["binary"]
                print(f"\n  Installed successfully!")
                print(f"  Binary: {binary}")
                if result.get("hint"):
                    print(f"  Hint:   {result['hint']}")
                return binary
            if result.get("message"):
                print(f"  {result['message']}")

        except InstallError as e:
            print(f"\n  Install failed: {e}")
            print(f"  Download manually from: {HOMEPAGE}")
        except Exception as e:
            print(f"\n  Error: {e}")

        return None

    def _run_cli(self, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run ACloudViewer in CLI mode with -SILENT prefix."""
        binary = self._ensure_binary()
        binary = self._resolve_exe(binary)
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

    @staticmethod
    def _resolve_exe(binary_path: str) -> str:
        """On Windows, resolve .bat wrappers to the underlying .exe.

        The .bat wrapper (``start /b ... >nul``) is designed for GUI launch:
        it backgrounds the process and discards output, which is incompatible
        with headless CLI mode.  Using the .exe directly keeps subprocess.run
        synchronous so we can capture output and wait for completion.
        """
        if not IS_WINDOWS:
            return binary_path
        p = Path(binary_path)
        if p.suffix.lower() == ".bat":
            exe = p.with_suffix(".exe")
            if exe.exists():
                return str(exe)
        return binary_path

    @staticmethod
    def _save_args(output_path: str, entity_type: str = "cloud") -> list[str]:
        """Build CLI args to save with the correct export format for *output_path*.

        Inspects the file extension, looks up the format keyword in
        CLOUD_FORMAT_MAP / MESH_FORMAT_MAP, and returns a list such as
        ["-C_EXPORT_FMT", "PCD", "-SAVE_CLOUDS", "FILE", "/path/to/out.pcd"].
        """
        ext = Path(output_path).suffix.lower()
        args: list[str] = []
        if entity_type == "cloud":
            fmt = CLOUD_FORMAT_MAP.get(ext)
            if fmt:
                args += ["-C_EXPORT_FMT", fmt]
            args += ["-SAVE_CLOUDS", "FILE", output_path]
        else:
            fmt = MESH_FORMAT_MAP.get(ext)
            if fmt:
                args += ["-M_EXPORT_FMT", fmt]
            args += ["-SAVE_MESHES", "FILE", output_path]
        return args

    @staticmethod
    def _check_status(output_path: str) -> str:
        """Return 'completed' if *output_path* exists and has nonzero size, else 'failed'."""
        p = Path(output_path)
        if p.exists() and p.stat().st_size > 0:
            return "completed"
        return "failed"

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

        can_cloud_in = in_ext in POINT_CLOUD_FORMATS
        can_mesh_in = in_ext in MESH_FORMATS
        can_cloud_out = out_ext in POINT_CLOUD_FORMATS
        can_mesh_out = out_ext in MESH_FORMATS

        cloud_fmt = CLOUD_FORMAT_MAP.get(out_ext)
        mesh_fmt = MESH_FORMAT_MAP.get(out_ext)

        with tempfile.TemporaryDirectory() as tmpdir:
            args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]

            if can_cloud_in and can_cloud_out:
                if cloud_fmt:
                    args += ["-C_EXPORT_FMT", cloud_fmt]
                args += ["-SAVE_CLOUDS", "FILE", output_path]
            elif can_mesh_in and can_mesh_out and not can_cloud_in:
                if mesh_fmt:
                    args += ["-M_EXPORT_FMT", mesh_fmt]
                args += ["-SAVE_MESHES", "FILE", output_path]
            elif can_cloud_in and can_mesh_out:
                args += ["-DELAUNAY"]
                fmt = mesh_fmt or cloud_fmt
                if fmt:
                    args += ["-M_EXPORT_FMT", fmt]
                args += ["-SAVE_MESHES", "FILE", output_path]
            elif can_mesh_in and can_cloud_out:
                args += ["-SAMPLE_MESH", "POINTS", str(sample_points)]
                if cloud_fmt:
                    args += ["-C_EXPORT_FMT", cloud_fmt]
                args += ["-SAVE_CLOUDS", "FILE", output_path]
            elif can_mesh_in and can_mesh_out:
                if mesh_fmt:
                    args += ["-M_EXPORT_FMT", mesh_fmt]
                args += ["-SAVE_MESHES", "FILE", output_path]
            else:
                args += ["-SAVE_CLOUDS", "FILE", output_path]

            self._run_cli(args)

        if not Path(output_path).exists():
            out_dir = Path(output_path).parent
            out_stem = Path(output_path).stem
            in_stem = Path(input_path).stem

            search_exts = _FORMAT_ALIAS_EXTS.get(out_ext, [out_ext])
            candidates = []
            for ext in search_exts:
                candidates += list(out_dir.glob(f"{out_stem}*{ext}"))
                candidates += list(out_dir.glob(f"{in_stem}*{ext}"))

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

        total_errors = len(errors) + sum(1 for r in results if r.get("status") == "failed")
        return {
            "input_dir": input_dir, "output_dir": output_dir,
            "output_format": output_format,
            "converted": len(results), "errors": total_errors,
            "files": results, "error_details": errors or None,
            "status": "failed" if total_errors > 0 or not results else "completed",
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
        self._rpc.scene_remove(entity_id)

    def scene_set_visible(self, entity_id: int, visible: bool) -> None:
        if self._mode != "gui":
            raise BackendError("scene_set_visible requires GUI mode")
        self._rpc.scene_set_visible(entity_id, visible)

    def scene_select(self, entity_ids: list[int]) -> None:
        if self._mode != "gui":
            raise BackendError("scene_select requires GUI mode")
        self._rpc.scene_select(entity_ids)

    def scene_clear(self) -> None:
        if self._mode != "gui":
            raise BackendError("scene_clear requires GUI mode")
        self._rpc.clear()

    def entity_set_color(self, entity_id: int,
                         r: int = 255, g: int = 255, b: int = 255) -> int:
        if self._mode != "gui":
            raise BackendError("entity_set_color requires GUI mode")
        return self._rpc.entity_set_color(entity_id, r, g, b)

    def cloud_get_scalar_fields(self, entity_id: int) -> list[dict]:
        if self._mode != "gui":
            raise BackendError("cloud_get_scalar_fields requires GUI mode")
        return self._rpc.cloud_get_scalar_fields(entity_id)

    # =====================================================================
    # Mesh operations (GUI only via RPC)
    # =====================================================================

    def mesh_simplify_gui(self, entity_id: int, method: str = "quadric",
                          target_triangles: int = 10000,
                          voxel_size: float = 0.05) -> dict:
        if self._mode != "gui":
            raise BackendError("mesh_simplify requires GUI mode")
        return self._rpc.mesh_simplify(entity_id, method=method,
                                       target_triangles=target_triangles,
                                       voxel_size=voxel_size)

    def mesh_smooth_gui(self, entity_id: int, method: str = "laplacian",
                        iterations: int = 5, lambda_val: float = 0.5,
                        mu: float = -0.53) -> dict:
        if self._mode != "gui":
            raise BackendError("mesh_smooth requires GUI mode")
        return self._rpc.mesh_smooth(entity_id, method=method,
                                     iterations=iterations,
                                     lambda_val=lambda_val, mu=mu)

    def mesh_subdivide_gui(self, entity_id: int, method: str = "midpoint",
                           iterations: int = 1) -> dict:
        if self._mode != "gui":
            raise BackendError("mesh_subdivide requires GUI mode")
        return self._rpc.mesh_subdivide(entity_id, method=method,
                                        iterations=iterations)

    def mesh_sample_points_gui(self, entity_id: int, method: str = "uniform",
                               count: int = 100000) -> dict:
        if self._mode != "gui":
            raise BackendError("mesh_sample_points requires GUI mode")
        return self._rpc.mesh_sample_points(entity_id, method=method,
                                            count=count)

    # =====================================================================
    # View control (GUI only via RPC)
    # =====================================================================

    def view_set_orientation(self, orientation: str) -> int:
        if self._mode != "gui":
            raise BackendError("view_set_orientation requires GUI mode")
        return self._rpc.set_view(orientation)

    def view_zoom_fit(self, entity_id: int | None = None) -> int:
        if self._mode != "gui":
            raise BackendError("view_zoom_fit requires GUI mode")
        return self._rpc.zoom_fit(entity_id)

    def view_refresh(self) -> int:
        if self._mode != "gui":
            raise BackendError("view_refresh requires GUI mode")
        return self._rpc.view_refresh()

    def view_set_perspective(self, mode: str = "object") -> int:
        if self._mode != "gui":
            raise BackendError("view_set_perspective requires GUI mode")
        return self._rpc.view_set_perspective(mode)

    def view_set_point_size(self, action: str = "increase") -> int:
        if self._mode != "gui":
            raise BackendError("view_set_point_size requires GUI mode")
        return self._rpc.view_set_point_size(action)

    def transform_apply_gui(self, entity_id: int,
                            matrix: list[float]) -> int:
        if self._mode != "gui":
            raise BackendError("transform_apply requires GUI mode")
        return self._rpc.transform_apply(entity_id, matrix)

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
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "method": method, "parameter": parameter,
            "status": self._check_status(output_path),
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
        args += self._save_args(output_path)
        self._run_cli(args)
        return {
            "input": input_path, "output": output_path,
            "has_normals": True, "status": self._check_status(output_path),
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
        ] + self._save_args(out))
        return {
            "data": data_path, "reference": reference_path,
            "output": out, "iterations": iterations,
            "status": self._check_status(out),
        }

    def sor_filter(self, input_path: str, output_path: str,
                   knn: int = 6, sigma: float = 1.0) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SOR", str(knn), str(sigma),
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "knn": knn, "sigma": sigma, "status": self._check_status(output_path),
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
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "status": self._check_status(output_path),
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
        args += self._save_args(out)
        self._run_cli(args)
        return {
            "compared": compared_path, "reference": reference_path,
            "output": out, "status": self._check_status(out),
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
        args += self._save_args(out)
        self._run_cli(args)
        return {
            "cloud": cloud_path, "mesh": mesh_path,
            "output": out, "status": self._check_status(out),
        }

    def delaunay(self, input_path: str, output_path: str,
                 max_edge_length: float = 0.0) -> dict:
        args = [
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-DELAUNAY",
        ]
        if max_edge_length > 0:
            args += ["-MAX_EDGE_LENGTH", str(max_edge_length)]
        args += self._save_args(output_path, "mesh")
        self._run_cli(args)
        return {
            "input": input_path, "output": output_path,
            "status": self._check_status(output_path),
        }

    def density(self, input_path: str, output_path: str,
                radius: float = 0.5) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-DENSITY", str(radius),
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "radius": radius, "status": self._check_status(output_path),
        }

    def curvature(self, input_path: str, output_path: str,
                  curvature_type: str = "MEAN", radius: float = 0.5) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CURV", curvature_type.upper(), str(radius),
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "type": curvature_type, "radius": radius,
            "status": self._check_status(output_path),
        }

    def roughness(self, input_path: str, output_path: str,
                  radius: float = 0.5) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-ROUGH", str(radius),
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "radius": radius, "status": self._check_status(output_path),
        }

    def sample_mesh(self, input_path: str, output_path: str,
                    points: int = 100000) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SAMPLE_MESH", "POINTS", str(points),
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "points": points, "status": self._check_status(output_path),
        }

    def apply_transformation(self, input_path: str, output_path: str,
                             matrix_file: str) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-APPLY_TRANS", matrix_file,
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "matrix_file": matrix_file, "status": self._check_status(output_path),
        }

    def color_banding(self, input_path: str, output_path: str,
                      axis: str = "Z", frequency: float = 10.0) -> dict:
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CBANDING", axis.upper(), str(frequency),
        ] + self._save_args(output_path))
        return {
            "input": input_path, "output": output_path,
            "axis": axis, "frequency": frequency, "status": self._check_status(output_path),
        }

    # =====================================================================
    # Scalar field operations (headless)
    # =====================================================================

    def set_active_sf(self, input_path: str, output_path: str,
                      sf_index: int | str = 0) -> dict:
        """Set the active scalar field (-SET_ACTIVE_SF)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SET_ACTIVE_SF", str(sf_index),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "sf_index": sf_index, "status": self._check_status(output_path)}

    def remove_all_sfs(self, input_path: str, output_path: str) -> dict:
        """Remove all scalar fields (-REMOVE_ALL_SFS)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-REMOVE_ALL_SFS",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def remove_sf(self, input_path: str, output_path: str,
                  sf_index: int = 0) -> dict:
        """Remove a specific scalar field by index (-REMOVE_SF)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-REMOVE_SF", str(sf_index),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "sf_index": sf_index, "status": self._check_status(output_path)}

    def rename_sf(self, input_path: str, output_path: str,
                  sf_index: int | str = 0, new_name: str = "") -> dict:
        """Rename a scalar field (-RENAME_SF)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-RENAME_SF", str(sf_index), new_name,
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "new_name": new_name, "status": self._check_status(output_path)}

    def sf_arithmetic(self, input_path: str, output_path: str,
                      sf_index: int | str = 0, operation: str = "SQRT") -> dict:
        """Apply SF arithmetic operation (-SF_ARITHMETIC)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SF_ARITHMETIC", str(sf_index), operation,
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "operation": operation, "status": self._check_status(output_path)}

    def sf_operation(self, input_path: str, output_path: str,
                     sf_index: int | str = 0, operation: str = "ADD",
                     value: float = 0.0) -> dict:
        """Apply SF arithmetic operation with scalar value (-SF_OP)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SF_OP", str(sf_index), operation, str(value),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "operation": operation, "value": value,
                "status": self._check_status(output_path)}

    def coord_to_sf(self, input_path: str, output_path: str,
                    dimension: str = "Z") -> dict:
        """Export coordinate as scalar field (-COORD_TO_SF)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-COORD_TO_SF", dimension.upper(),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "dimension": dimension, "status": self._check_status(output_path)}

    def sf_gradient(self, input_path: str, output_path: str,
                    euclidean: bool = False) -> dict:
        """Compute scalar field gradient (-SF_GRAD)."""
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-SF_GRAD"]
        if euclidean:
            args.append("EUCLIDEAN")
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "euclidean": euclidean, "status": self._check_status(output_path)}

    def filter_sf(self, input_path: str, output_path: str,
                  min_val: float | str = "MIN", max_val: float | str = "MAX") -> dict:
        """Filter points by scalar field value (-FILTER_SF)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-FILTER_SF", str(min_val), str(max_val),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "min": min_val, "max": max_val,
                "status": self._check_status(output_path)}

    def sf_color_scale(self, input_path: str, output_path: str,
                       scale_file: str = "") -> dict:
        """Apply a color scale to active SF (-SF_COLOR_SCALE)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SF_COLOR_SCALE", scale_file,
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "scale_file": scale_file, "status": self._check_status(output_path)}

    def sf_convert_to_rgb(self, input_path: str, output_path: str) -> dict:
        """Convert active SF to RGB colors (-SF_CONVERT_TO_RGB)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-SF_CONVERT_TO_RGB",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    # =====================================================================
    # Normals (advanced headless operations)
    # =====================================================================

    def octree_normals(self, input_path: str, output_path: str,
                       radius: float | str = "AUTO",
                       orient: str = "", model: str = "") -> dict:
        """Compute normals with octree method (-OCTREE_NORMALS)."""
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-OCTREE_NORMALS", str(radius)]
        if orient:
            args += ["-ORIENT", orient]
        if model:
            args += ["-MODEL", model]
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "radius": radius, "status": self._check_status(output_path)}

    def orient_normals_mst(self, input_path: str, output_path: str,
                           knn: int = 6) -> dict:
        """Orient normals via MST (-ORIENT_NORMS_MST)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-ORIENT_NORMS_MST", str(knn),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "knn": knn, "status": self._check_status(output_path)}

    def invert_normals(self, input_path: str, output_path: str) -> dict:
        """Invert point cloud normals (-INVERT_NORMALS)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-INVERT_NORMALS",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def clear_normals(self, input_path: str, output_path: str) -> dict:
        """Remove all normals (-CLEAR_NORMALS)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CLEAR_NORMALS",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def normals_to_dip(self, input_path: str, output_path: str) -> dict:
        """Convert normals to dip/dip direction (-NORMALS_TO_DIP)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-NORMALS_TO_DIP",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def normals_to_sfs(self, input_path: str, output_path: str) -> dict:
        """Convert normals to scalar fields (-NORMALS_TO_SFS)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-NORMALS_TO_SFS",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    # =====================================================================
    # Geometry / analysis (headless)
    # =====================================================================

    def extract_connected_components(self, input_path: str, output_path: str,
                                     octree_level: int = 8,
                                     min_points: int = 100) -> dict:
        """Extract connected components (-EXTRACT_CC)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-EXTRACT_CC", str(octree_level), str(min_points),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "octree_level": octree_level, "min_points": min_points,
                "status": self._check_status(output_path)}

    def approx_density(self, input_path: str, output_path: str,
                       density_type: str = "") -> dict:
        """Compute approximate point density (-APPROX_DENSITY)."""
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-APPROX_DENSITY"]
        if density_type:
            args += ["-TYPE", density_type]
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def feature(self, input_path: str, output_path: str,
                feature_type: str = "ROUGHNESS",
                kernel_size: float = 0.1) -> dict:
        """Compute geometric feature (-FEATURE)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-FEATURE", feature_type.upper(), str(kernel_size),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "feature_type": feature_type, "kernel_size": kernel_size,
                "status": self._check_status(output_path)}

    def moment(self, input_path: str, output_path: str,
               kernel_size: float = 0.1) -> dict:
        """Compute 1st order moment (-MOMENT)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-MOMENT", str(kernel_size),
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "kernel_size": kernel_size, "status": self._check_status(output_path)}

    def best_fit_plane(self, input_path: str, output_path: str,
                       make_horiz: bool = False,
                       keep_loaded: bool = False) -> dict:
        """Compute best fit plane (-BEST_FIT_PLANE)."""
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-BEST_FIT_PLANE"]
        if make_horiz:
            args.append("-MAKE_HORIZ")
        if keep_loaded:
            args.append("-KEEP_LOADED")
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "make_horiz": make_horiz, "status": self._check_status(output_path)}

    def mesh_volume(self, input_path: str,
                    output_file: str = "") -> dict:
        """Compute mesh volume (-MESH_VOLUME)."""
        args = ["-O", input_path, "-MESH_VOLUME"]
        if output_file:
            args += ["-TO_FILE", output_file]
        result = self._run_cli(args)
        return {"input": input_path, "output_file": output_file,
                "status": "completed"}

    def extract_vertices(self, input_path: str, output_path: str) -> dict:
        """Extract mesh vertices to a point cloud (-EXTRACT_VERTICES)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-EXTRACT_VERTICES",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def flip_triangles(self, input_path: str, output_path: str) -> dict:
        """Flip mesh triangle normals (-FLIP_TRI)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-FLIP_TRI",
        ] + self._save_args(output_path, entity_type="mesh"))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    # =====================================================================
    # Merge operations (headless)
    # =====================================================================

    def merge_clouds(self, input_paths: list[str], output_path: str) -> dict:
        """Merge multiple clouds into one (-MERGE_CLOUDS)."""
        args = ["-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]
        for p in input_paths:
            args += ["-O", p]
        args.append("-MERGE_CLOUDS")
        self._run_cli(args + self._save_args(output_path))
        return {"inputs": input_paths, "output": output_path,
                "status": self._check_status(output_path)}

    def merge_meshes(self, input_paths: list[str], output_path: str) -> dict:
        """Merge multiple meshes into one (-MERGE_MESHES)."""
        args = ["-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]
        for p in input_paths:
            args += ["-O", p]
        args.append("-MERGE_MESHES")
        self._run_cli(args + self._save_args(output_path, entity_type="mesh"))
        return {"inputs": input_paths, "output": output_path,
                "status": self._check_status(output_path)}

    # =====================================================================
    # Cleanup operations (headless)
    # =====================================================================

    def remove_rgb(self, input_path: str, output_path: str) -> dict:
        """Remove RGB colors from point cloud (-REMOVE_RGB)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-REMOVE_RGB",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def remove_scan_grids(self, input_path: str, output_path: str) -> dict:
        """Remove scan grid info (-REMOVE_SCAN_GRIDS)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-REMOVE_SCAN_GRIDS",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def match_centers(self, input_paths: list[str], output_path: str) -> dict:
        """Match bounding-box centers (-MATCH_CENTERS)."""
        args = ["-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]
        for p in input_paths:
            args += ["-O", p]
        args.append("-MATCH_CENTERS")
        self._run_cli(args + self._save_args(output_path))
        return {"inputs": input_paths, "output": output_path,
                "status": self._check_status(output_path)}

    def drop_global_shift(self, input_path: str, output_path: str) -> dict:
        """Drop the global shift of a cloud (-DROP_GLOBAL_SHIFT)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-DROP_GLOBAL_SHIFT",
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def closest_point_set(self, input_paths: list[str],
                          output_path: str) -> dict:
        """Compute closest point set between clouds (-CLOSEST_POINT_SET)."""
        args = ["-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]
        for p in input_paths:
            args += ["-O", p]
        args.append("-CLOSEST_POINT_SET")
        self._run_cli(args + self._save_args(output_path))
        return {"inputs": input_paths, "output": output_path,
                "status": self._check_status(output_path)}

    # =====================================================================
    # Rasterize / Volume (headless)
    # =====================================================================

    def rasterize(self, input_path: str, output_path: str,
                  grid_step: float = 1.0, vert_dir: int = 2,
                  output_cloud: bool = True, output_mesh: bool = False,
                  proj: str = "AVG", empty_fill: str = "MIN_H") -> dict:
        """2.5D rasterization (-RASTERIZE)."""
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-RASTERIZE", "-GRID_STEP", str(grid_step),
                "-VERT_DIR", str(vert_dir)]
        if output_cloud:
            args.append("-OUTPUT_CLOUD")
        if output_mesh:
            args.append("-OUTPUT_MESH")
        args += ["-PROJ", proj, "-EMPTY_FILL", empty_fill]
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "grid_step": grid_step, "status": self._check_status(output_path)}

    def volume_25d(self, input_paths: list[str], output_path: str,
                   grid_step: float = 1.0, vert_dir: int = 2,
                   const_height: float | None = None) -> dict:
        """Compute 2.5D volume (-VOLUME)."""
        args = ["-AUTO_SAVE", "OFF", "-NO_TIMESTAMP"]
        for p in input_paths:
            args += ["-O", p]
        args += ["-VOLUME", "-GRID_STEP", str(grid_step),
                 "-VERT_DIR", str(vert_dir)]
        if const_height is not None:
            args += ["-CONST_HEIGHT", str(const_height)]
        args.append("-OUTPUT_MESH")
        self._run_cli(args + self._save_args(output_path, entity_type="mesh"))
        return {"inputs": input_paths, "output": output_path,
                "grid_step": grid_step, "status": self._check_status(output_path)}

    # =====================================================================
    # Crop operations (headless)
    # =====================================================================

    def crop_2d(self, input_path: str, output_path: str,
                orthogonal_dim: str = "Z",
                polygon: list[tuple[float, float]] | None = None) -> dict:
        """2D polygon crop (-CROP2D)."""
        dim = orthogonal_dim.upper()
        pts = polygon or []
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-CROP2D", dim, str(len(pts))]
        for x, y in pts:
            args += [str(x), str(y)]
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "status": self._check_status(output_path)}

    def cross_section(self, input_path: str, output_path: str,
                      polyline_file: str = "") -> dict:
        """Cross-section extraction (-CROSS_SECTION)."""
        self._run_cli([
            "-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
            "-CROSS_SECTION", polyline_file,
        ] + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "polyline_file": polyline_file,
                "status": self._check_status(output_path)}

    # =====================================================================
    # Statistical test (headless)
    # =====================================================================

    def stat_test(self, input_path: str, output_path: str,
                  distribution: str = "GAUSS", params: list[float] | None = None,
                  p_value: float = 0.0001, knn: int = 16) -> dict:
        """Statistical outlier test (-STAT_TEST)."""
        dist_params = params or [0.0, 1.0]
        args = ["-O", input_path, "-AUTO_SAVE", "OFF", "-NO_TIMESTAMP",
                "-STAT_TEST", distribution.upper()]
        for p in dist_params:
            args.append(str(p))
        args += [str(p_value), str(knn)]
        self._run_cli(args + self._save_args(output_path))
        return {"input": input_path, "output": output_path,
                "distribution": distribution, "p_value": p_value,
                "status": self._check_status(output_path)}

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

    # ── Cloud scalar-field management (GUI mode) ────────────────────────

    def cloud_set_active_sf_gui(self, entity_id: int,
                                field_index: int = -1,
                                field_name: str = "") -> dict:
        """Set the active scalar field on a point cloud (GUI mode)."""
        self._require_gui("cloud_set_active_sf_gui")
        return self._rpc.cloud_set_active_sf(entity_id, field_index, field_name)

    def cloud_remove_sf_gui(self, entity_id: int,
                            field_index: int = -1,
                            field_name: str = "") -> dict:
        """Remove a scalar field from a point cloud (GUI mode)."""
        self._require_gui("cloud_remove_sf_gui")
        return self._rpc.cloud_remove_sf(entity_id, field_index, field_name)

    def cloud_remove_all_sfs_gui(self, entity_id: int) -> dict:
        """Remove all scalar fields from a point cloud (GUI mode)."""
        self._require_gui("cloud_remove_all_sfs_gui")
        return self._rpc.cloud_remove_all_sfs(entity_id)

    def cloud_rename_sf_gui(self, entity_id: int, new_name: str,
                            field_index: int = -1,
                            old_name: str = "") -> dict:
        """Rename a scalar field on a point cloud (GUI mode)."""
        self._require_gui("cloud_rename_sf_gui")
        return self._rpc.cloud_rename_sf(entity_id, new_name, field_index, old_name)

    def cloud_filter_sf_gui(self, entity_id: int,
                            min_val: float = 0, max_val: float = 1,
                            field_index: int = -1,
                            field_name: str = "") -> dict:
        """Filter cloud by scalar field range (GUI mode)."""
        self._require_gui("cloud_filter_sf_gui")
        return self._rpc.cloud_filter_sf(entity_id, min_val, max_val,
                                         field_index, field_name)

    def cloud_coord_to_sf_gui(self, entity_id: int,
                              dimension: str = "z") -> dict:
        """Create scalar field from coordinate dimension (GUI mode)."""
        self._require_gui("cloud_coord_to_sf_gui")
        return self._rpc.cloud_coord_to_sf(entity_id, dimension)

    # ── Cloud geometry (GUI mode) ───────────────────────────────────────

    def cloud_remove_rgb_gui(self, entity_id: int) -> dict:
        """Remove color data from point cloud (GUI mode)."""
        self._require_gui("cloud_remove_rgb_gui")
        return self._rpc.cloud_remove_rgb(entity_id)

    def cloud_remove_normals_gui(self, entity_id: int) -> dict:
        """Remove normals from point cloud (GUI mode)."""
        self._require_gui("cloud_remove_normals_gui")
        return self._rpc.cloud_remove_normals(entity_id)

    def cloud_invert_normals_gui(self, entity_id: int) -> dict:
        """Invert normal directions on point cloud (GUI mode)."""
        self._require_gui("cloud_invert_normals_gui")
        return self._rpc.cloud_invert_normals(entity_id)

    def cloud_merge_gui(self, entity_ids: list[int]) -> dict:
        """Merge multiple point clouds (GUI mode)."""
        self._require_gui("cloud_merge_gui")
        return self._rpc.cloud_merge(entity_ids)

    # ── Mesh extended (GUI mode) ────────────────────────────────────────

    def mesh_extract_vertices_gui(self, entity_id: int) -> dict:
        """Extract mesh vertices as point cloud (GUI mode)."""
        self._require_gui("mesh_extract_vertices_gui")
        return self._rpc.mesh_extract_vertices(entity_id)

    def mesh_flip_triangles_gui(self, entity_id: int) -> dict:
        """Flip triangle winding order on mesh (GUI mode)."""
        self._require_gui("mesh_flip_triangles_gui")
        return self._rpc.mesh_flip_triangles(entity_id)

    def mesh_volume_gui(self, entity_id: int) -> dict:
        """Compute mesh volume (GUI mode)."""
        self._require_gui("mesh_volume_gui")
        return self._rpc.mesh_volume(entity_id)

    def mesh_merge_gui(self, entity_ids: list[int]) -> dict:
        """Merge multiple meshes (GUI mode)."""
        self._require_gui("mesh_merge_gui")
        return self._rpc.mesh_merge(entity_ids)

    # ── COLMAP generic (GUI mode) ──────────────────────────────────────

    def colmap_run_gui(self, command: str,
                       args: list[str] | None = None,
                       kwargs_: dict[str, str] | None = None,
                       colmap_binary: str = "colmap",
                       timeout_ms: int = 3600000) -> dict:
        """Run any COLMAP subcommand via the RPC plugin (GUI mode)."""
        self._require_gui("colmap_run_gui")
        return self._rpc.colmap_run(command, args, kwargs_,
                                    colmap_binary, timeout_ms)
