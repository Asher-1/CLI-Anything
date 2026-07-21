"""Colmap binary backend — invokes the colmap CLI for 3D reconstruction.

Discovers the colmap binary via:
  1. COLMAP_PATH env var (file or directory)
  2. Platform-appropriate names on PATH
  3. ACloudViewer install directory (Colmap is bundled with ACloudViewer)
  4. Standard install locations (Linux, macOS, Windows)

Platform support: Linux, macOS, Windows.
Supports both the automatic_reconstructor and individual pipeline steps.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


class ColmapError(Exception):
    pass


class ColmapBackend:
    """Wrapper around the colmap CLI binary."""

    def __init__(self, binary: str | None = None):
        self._binary = binary or self.find_binary()
        if not self._binary:
            raise ColmapError(
                "colmap binary not found. Set COLMAP_PATH env var or add colmap to PATH."
            )

    @staticmethod
    def _colmap_binary_names() -> list[str]:
        if platform.system() == "Windows":
            return ["Colmap.bat", "colmap.exe", "COLMAP.bat", "colmap.bat", "Colmap.exe"]
        if platform.system() == "Darwin":
            return ["colmap", "Colmap"]
        return ["colmap", "Colmap.sh", "Colmap"]

    @staticmethod
    def _colmap_search_dirs() -> list[Path]:
        """Standard install locations per platform, including ACloudViewer-bundled Colmap."""
        system = platform.system()
        dirs: list[Path] = []

        acv_binary = os.environ.get("ACV_BINARY")
        if acv_binary:
            acv_dir = Path(acv_binary).parent
            dirs.append(acv_dir)
            dirs.append(acv_dir / "bin")
            if system == "Darwin":
                # ACloudViewer.app/Contents/MacOS/../Resources/Colmap/...
                acv_res = acv_dir.parent / "Resources"
                dirs.append(acv_res / "Colmap" / "Colmap.app" / "Contents" / "MacOS")
                # Build layout: bin/Colmap.app/Contents/MacOS
                dirs.append(acv_dir / "Colmap.app" / "Contents" / "MacOS")
                dirs.append(acv_dir / "bin" / "Colmap.app" / "Contents" / "MacOS")

        if system == "Windows":
            for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                         os.environ.get("LOCALAPPDATA", "")):
                if base:
                    dirs.append(Path(base) / "Colmap")
                    dirs.append(Path(base) / "COLMAP")
                    dirs.append(Path(base) / "ACloudViewer")
                    dirs.append(Path(base) / "ACloudViewer" / "bin")
            dirs.append(Path.home() / "ACloudViewer")
        elif system == "Darwin":
            dirs += [
                Path("/usr/local/bin"),
                Path("/opt/homebrew/bin"),
                Path.home() / ".local" / "bin",
                # Installed ACloudViewer.app bundled Colmap
                Path("/Applications/ACloudViewer.app/Contents/Resources/Colmap/Colmap.app/Contents/MacOS"),
                Path("/Applications/ACloudViewer.app/Contents/MacOS"),
                Path.home() / "ACloudViewer.app" / "Contents" / "Resources" / "Colmap" / "Colmap.app" / "Contents" / "MacOS",
                Path.home() / "ACloudViewer.app" / "Contents" / "MacOS",
                # Install-prefix layout: <prefix>/bin/Colmap/Colmap.app/Contents/MacOS
                Path.home() / "ACloudViewer" / "Colmap" / "Colmap.app" / "Contents" / "MacOS",
                Path.home() / "ACloudViewer",
            ]
        else:
            dirs += [
                Path("/usr/local/bin"),
                Path("/usr/bin"),
                Path("/opt/colmap/bin"),
                Path.home() / ".local" / "bin",
                Path.home() / "ACloudViewer",
            ]
        return dirs

    @staticmethod
    def _resolve_app_bundle(directory: Path) -> str | None:
        """On macOS, resolve Colmap.app bundle inside a directory to the actual binary."""
        if platform.system() != "Darwin":
            return None
        for app_name in ("Colmap.app", "colmap.app"):
            exe = directory / app_name / "Contents" / "MacOS" / "Colmap"
            if exe.is_file():
                return str(exe)
        return None

    @staticmethod
    def find_binary() -> str | None:
        env = os.environ.get("COLMAP_PATH")
        if env:
            p = Path(env)
            if p.is_file() and os.access(str(p), os.X_OK):
                return str(p)
            if p.is_dir():
                # Try flat names first
                for name in ColmapBackend._colmap_binary_names():
                    candidate = p / name
                    if candidate.is_file():
                        return str(candidate)
                # Try .app bundle inside directory
                resolved = ColmapBackend._resolve_app_bundle(p)
                if resolved:
                    return resolved

        for name in ColmapBackend._colmap_binary_names():
            path = shutil.which(name)
            if path:
                return path

        for d in ColmapBackend._colmap_search_dirs():
            for name in ColmapBackend._colmap_binary_names():
                p = d / name
                if p.is_file():
                    return str(p)
            resolved = ColmapBackend._resolve_app_bundle(d)
            if resolved:
                return resolved
        return None

    def _run(self, args: list[str], timeout: int = 7200) -> str:
        cmd = [self._binary] + args
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ColmapError(f"colmap timed out after {timeout}s: {' '.join(args[:3])}")

        if r.returncode != 0:
            subcmd = args[0] if args else "unknown"
            if r.returncode < 0:
                import signal
                sig = -r.returncode
                try:
                    name = signal.Signals(sig).name
                except (ValueError, AttributeError):
                    name = str(sig)
                raise ColmapError(
                    f"colmap {subcmd} killed by signal {name} (exit {r.returncode})")

            stderr_lines = (r.stderr or "").strip().splitlines()
            error_lines = [
                ln for ln in stderr_lines
                if not ln.lstrip().startswith(("I0", "W0", "iter ", "   "))
                and "trust_region_minimizer" not in ln
                and "detect_structure" not in ln
                and "block_sparse_matrix" not in ln
                and "callbacks.cc" not in ln
            ]
            if error_lines:
                msg = "\n".join(error_lines[-30:])
            elif stderr_lines:
                msg = "\n".join(stderr_lines[-10:])
            else:
                msg = r.stdout.strip()[-500:] if r.stdout else f"exit code {r.returncode}"
            raise ColmapError(f"colmap {subcmd} failed (exit {r.returncode}):\n{msg}")

        return r.stdout

    # ── Automatic Reconstruction ─────────────────────────────────────

    def automatic_reconstruct(
        self,
        workspace_path: str,
        image_path: str,
        quality: str = "high",
        data_type: str = "individual",
        mesher: str = "poisson",
        camera_model: str = "",
        single_camera: bool = False,
        sparse: bool = True,
        dense: bool = True,
        use_gpu: bool = True,
        num_threads: int = -1,
    ) -> dict:
        """Run the full automatic reconstruction pipeline.

        Quality: low, medium, high, extreme
        Data type: individual, video, internet
        Mesher: poisson, delaunay
        """
        Path(workspace_path).mkdir(parents=True, exist_ok=True)
        args = [
            "automatic_reconstructor",
            "--workspace_path", workspace_path,
            "--image_path", image_path,
            "--quality", quality.lower(),
            "--data_type", data_type.lower(),
            "--mesher", mesher.lower(),
        ]
        if camera_model:
            args += ["--camera_model", camera_model]
        if single_camera:
            args += ["--single_camera", "1"]
        if not sparse:
            args += ["--sparse", "0"]
        if not dense:
            args += ["--dense", "0"]
        if not use_gpu:
            args += ["--use_gpu", "0"]
        if num_threads > 0:
            args += ["--num_threads", str(num_threads)]

        self._run(args)
        result = {
            "workspace": workspace_path,
            "image_path": image_path,
            "quality": quality.lower(),
            "status": "completed",
            "outputs": {},
        }
        ws = Path(workspace_path)
        for idx in range(10):
            dense_dir = ws / "dense" / str(idx)
            if not dense_dir.is_dir():
                break
            fused = dense_dir / "fused.ply"
            if fused.exists():
                result["outputs"].setdefault("fused_ply", []).append(str(fused))
            for mesh_name in ("meshed-poisson.ply", "meshed-delaunay.ply"):
                mesh = dense_dir / mesh_name
                if mesh.exists():
                    result["outputs"].setdefault("mesh", []).append(str(mesh))
            textured = dense_dir / "textured.obj"
            if textured.exists():
                result["outputs"].setdefault("textured_mesh", []).append(str(textured))
        return result

    # ── Feature Extraction ───────────────────────────────────────────

    def feature_extractor(
        self,
        database_path: str,
        image_path: str,
        camera_model: str = "SIMPLE_RADIAL",
        single_camera: bool = False,
        use_gpu: bool = True,
        max_image_size: int = 0,
        max_num_features: int = 8192,
    ) -> dict:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        args = [
            "feature_extractor",
            "--database_path", database_path,
            "--image_path", image_path,
            "--ImageReader.camera_model", camera_model,
            "--SiftExtraction.max_num_features", str(max_num_features),
        ]
        if single_camera:
            args += ["--ImageReader.single_camera", "1"]
        if not use_gpu:
            args += ["--SiftExtraction.use_gpu", "0"]
        if max_image_size > 0:
            args += ["--SiftExtraction.max_image_size", str(max_image_size)]

        self._run(args)
        return {"database": database_path, "status": "completed"}

    # ── Matching ─────────────────────────────────────────────────────

    def exhaustive_matcher(
        self,
        database_path: str,
        use_gpu: bool = True,
    ) -> dict:
        args = ["exhaustive_matcher", "--database_path", database_path]
        if not use_gpu:
            args += ["--SiftMatching.use_gpu", "0"]
        self._run(args)
        return {"database": database_path, "matcher": "exhaustive", "status": "completed"}

    def sequential_matcher(
        self,
        database_path: str,
        overlap: int = 10,
        use_gpu: bool = True,
    ) -> dict:
        args = [
            "sequential_matcher",
            "--database_path", database_path,
            "--SequentialMatching.overlap", str(overlap),
        ]
        if not use_gpu:
            args += ["--SiftMatching.use_gpu", "0"]
        self._run(args)
        return {"database": database_path, "matcher": "sequential", "status": "completed"}

    def vocab_tree_matcher(
        self,
        database_path: str,
        vocab_tree_path: str,
        use_gpu: bool = True,
    ) -> dict:
        args = [
            "vocab_tree_matcher",
            "--database_path", database_path,
            "--VocabTreeMatching.vocab_tree_path", vocab_tree_path,
        ]
        if not use_gpu:
            args += ["--SiftMatching.use_gpu", "0"]
        self._run(args)
        return {"database": database_path, "matcher": "vocab_tree", "status": "completed"}

    def spatial_matcher(
        self,
        database_path: str,
        use_gpu: bool = True,
    ) -> dict:
        args = ["spatial_matcher", "--database_path", database_path]
        if not use_gpu:
            args += ["--SiftMatching.use_gpu", "0"]
        self._run(args)
        return {"database": database_path, "matcher": "spatial", "status": "completed"}

    # ── SfM (Sparse Reconstruction) ─────────────────────────────────

    def mapper(
        self,
        database_path: str,
        image_path: str,
        output_path: str,
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "mapper",
            "--database_path", database_path,
            "--image_path", image_path,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "type": "incremental", "status": "completed"}

    def hierarchical_mapper(
        self,
        database_path: str,
        image_path: str,
        output_path: str,
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "hierarchical_mapper",
            "--database_path", database_path,
            "--image_path", image_path,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "type": "hierarchical", "status": "completed"}

    def bundle_adjuster(
        self,
        input_path: str,
        output_path: str,
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "bundle_adjuster",
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    # ── Dense Reconstruction ─────────────────────────────────────────

    def image_undistorter(
        self,
        image_path: str,
        input_path: str,
        output_path: str,
        output_type: str = "COLMAP",
        max_image_size: int = 0,
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "image_undistorter",
            "--image_path", image_path,
            "--input_path", input_path,
            "--output_path", output_path,
            "--output_type", output_type,
        ]
        if max_image_size > 0:
            args += ["--max_image_size", str(max_image_size)]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    def patch_match_stereo(
        self,
        workspace_path: str,
        workspace_format: str = "COLMAP",
        geom_consistency: bool = True,
    ) -> dict:
        args = [
            "patch_match_stereo",
            "--workspace_path", workspace_path,
            "--workspace_format", workspace_format,
            "--PatchMatchStereo.geom_consistency",
            "true" if geom_consistency else "false",
        ]
        self._run(args)
        return {"workspace": workspace_path, "status": "completed"}

    def stereo_fusion(
        self,
        workspace_path: str,
        output_path: str,
        workspace_format: str = "COLMAP",
        input_type: str = "geometric",
    ) -> dict:
        args = [
            "stereo_fusion",
            "--workspace_path", workspace_path,
            "--workspace_format", workspace_format,
            "--input_type", input_type,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    # ── Meshing ──────────────────────────────────────────────────────

    def poisson_mesher(
        self,
        input_path: str,
        output_path: str,
    ) -> dict:
        args = [
            "poisson_mesher",
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    def delaunay_mesher(
        self,
        input_path: str,
        output_path: str,
    ) -> dict:
        args = [
            "delaunay_mesher",
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    def image_texturer(
        self,
        input_path: str,
        output_path: str,
        mesh_path: str = "",
    ) -> dict:
        """Texture a mesh using images from the reconstruction (Colmap image_texturer)."""
        args = [
            "image_texturer",
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        if mesh_path:
            args += ["--mesh_path", mesh_path]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    # ── Model Operations ─────────────────────────────────────────────

    def model_converter(
        self,
        input_path: str,
        output_path: str,
        output_type: str = "PLY",
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "model_converter",
            "--input_path", input_path,
            "--output_path", output_path,
            "--output_type", output_type,
        ]
        self._run(args)
        return {"output": output_path, "output_type": output_type, "status": "completed"}

    def model_analyzer(
        self,
        input_path: str,
    ) -> dict:
        output = self._run(["model_analyzer", "--path", input_path])
        return {"input": input_path, "analysis": output, "status": "completed"}

    def model_aligner(
        self,
        input_path: str,
        output_path: str,
        ref_images_path: str = "",
        alignment_type: str = "",
        database_path: str = "",
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "model_aligner",
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        if ref_images_path:
            args += ["--ref_images_path", ref_images_path]
        if alignment_type:
            args += ["--alignment_type", alignment_type]
        if database_path:
            args += ["--database_path", database_path]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    def model_cropper(
        self,
        input_path: str,
        output_path: str,
        boundary: str = "",
        gps_transform_path: str = "",
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "model_cropper",
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        if boundary:
            args += ["--boundary", boundary]
        if gps_transform_path:
            args += ["--gps_transform_path", gps_transform_path]
        self._run(args)
        return {"output": output_path, "status": "completed"}

    # ── Database Operations ──────────────────────────────────────────

    def database_creator(self, database_path: str) -> dict:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._run(["database_creator", "--database_path", database_path])
        return {"database": database_path, "status": "created"}

    # ── Color Extraction ─────────────────────────────────────────────

    def color_extractor(
        self,
        image_path: str,
        input_path: str,
        output_path: str,
    ) -> dict:
        Path(output_path).mkdir(parents=True, exist_ok=True)
        args = [
            "color_extractor",
            "--image_path", image_path,
            "--input_path", input_path,
            "--output_path", output_path,
        ]
        self._run(args)
        return {"output": output_path, "status": "completed"}
