"""CLI help and structure tests."""

import os
import platform
import subprocess
import sys
import json
import pytest
from pathlib import Path

IS_MACOS = platform.system() == "Darwin"
_skip_sibr_on_macos = pytest.mark.skipif(IS_MACOS, reason="SIBR not supported on macOS")

_HARNESS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
_CLI_CMD = [sys.executable, "-m", "cli_anything.acloudviewer"]


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _HARNESS_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        _CLI_CMD + args,
        capture_output=True, text=True, timeout=timeout, env=env)


class TestCLIHelp:
    def test_help(self):
        r = _run(["--help"])
        assert r.returncode == 0, (
            f"CLI --help failed (rc={r.returncode}):\n"
            f"stdout: {r.stdout[:1000]}\nstderr: {r.stderr[:1000]}")
        assert "acloudviewer" in r.stdout.lower()

    @pytest.mark.parametrize("cmd", [
        "convert --help",
        "batch-convert --help",
        "formats --help",
        "info --help",
        "scene --help",
        "view --help",
        "process --help",
        "session --help",
        "reconstruct --help",
        "entity --help",
        "cloud --help",
        "mesh --help",
        "transform --help",
        "export --help",
        "clear --help",
        "methods --help",
    ])
    def test_subcommand_help(self, cmd):
        r = _run(cmd.split())
        assert r.returncode == 0, (
            f"CLI '{cmd}' failed (rc={r.returncode}):\n"
            f"stdout: {r.stdout[:1000]}\nstderr: {r.stderr[:1000]}")

    def test_process_subcommands(self):
        r = _run(["process", "--help"])
        assert r.returncode == 0
        for cmd in ["subsample", "normals", "icp", "sor",
                     "c2c-dist", "c2m-dist", "density", "curvature",
                     "roughness", "delaunay", "sample-mesh", "color-banding",
                     "set-active-sf", "remove-all-sfs", "remove-sf", "rename-sf",
                     "sf-arithmetic", "sf-op", "coord-to-sf", "sf-gradient",
                     "filter-sf", "sf-color-scale", "sf-to-rgb",
                     "octree-normals", "orient-normals", "invert-normals",
                     "clear-normals", "normals-to-dip", "normals-to-sfs",
                     "extract-cc", "approx-density", "feature", "moment",
                     "best-fit-plane", "mesh-volume", "extract-vertices",
                     "flip-triangles", "merge-clouds", "merge-meshes",
                     "remove-rgb", "remove-scan-grids", "match-centers",
                     "drop-global-shift", "closest-point-set",
                     "rasterize", "stat-test"]:
            assert cmd in r.stdout, f"Missing process subcommand: {cmd}"

    def test_scene_subcommands(self):
        r = _run(["scene", "--help"])
        assert r.returncode == 0
        for cmd in ["list", "info", "remove", "show", "hide", "select", "clear"]:
            assert cmd in r.stdout, f"Missing scene subcommand: {cmd}"

    def test_entity_subcommands(self):
        r = _run(["entity", "--help"])
        assert r.returncode == 0
        for cmd in ["rename", "set-color"]:
            assert cmd in r.stdout, f"Missing entity subcommand: {cmd}"

    def test_view_subcommands(self):
        r = _run(["view", "--help"])
        assert r.returncode == 0
        for cmd in ["screenshot", "camera", "orient", "zoom", "refresh",
                     "perspective", "pointsize"]:
            assert cmd in r.stdout, f"Missing view subcommand: {cmd}"

    def test_cloud_subcommands(self):
        r = _run(["cloud", "--help"])
        assert r.returncode == 0
        for cmd in ["paint-uniform", "paint-by-height", "paint-by-scalar-field",
                     "get-scalar-fields", "crop"]:
            assert cmd in r.stdout, f"Missing cloud subcommand: {cmd}"

    def test_mesh_subcommands(self):
        r = _run(["mesh", "--help"])
        assert r.returncode == 0
        for cmd in ["simplify", "smooth", "subdivide", "sample-points"]:
            assert cmd in r.stdout, f"Missing mesh subcommand: {cmd}"

    def test_transform_subcommands(self):
        r = _run(["transform", "--help"])
        assert r.returncode == 0
        for cmd in ["apply", "apply-file"]:
            assert cmd in r.stdout, f"Missing transform subcommand: {cmd}"

    @_skip_sibr_on_macos
    def test_sibr_subcommands(self):
        r = _run(["sibr", "--help"])
        assert r.returncode == 0
        for cmd in ["prepare-colmap", "texture-mesh", "unwrap-mesh",
                     "tonemapper", "align-meshes", "camera-converter",
                     "nvm-to-sibr", "crop-from-center", "clipping-planes",
                     "distord-crop", "tool"]:
            assert cmd in r.stdout, f"Missing sibr subcommand: {cmd}"


class TestReconstructSubcommands:
    def test_reconstruct_help(self):
        r = _run(["reconstruct", "--help"])
        assert r.returncode == 0
        for cmd in ["auto", "extract-features", "match", "sparse",
                     "undistort", "dense-stereo", "fuse", "poisson",
                     "simplify-mesh", "texture-mesh", "convert-model",
                     "analyze-model", "mesh", "delaunay-mesh"]:
            assert cmd in r.stdout, f"Missing reconstruct subcommand: {cmd}"


class TestHeadlessMode:
    def test_info(self):
        r = _run(["--json", "--mode", "headless", "info"])
        assert r.returncode == 0, (
            f"headless info failed (rc={r.returncode}):\n"
            f"stdout: {r.stdout[:1000]}\nstderr: {r.stderr[:1000]}")
        data = json.loads(r.stdout)
        assert data["mode"] == "headless"

    def test_session_status(self):
        r = _run(["--json", "--mode", "headless", "session", "status"])
        assert r.returncode == 0, (
            f"session status failed:\nstdout: {r.stdout[:500]}\nstderr: {r.stderr[:500]}")

    def test_session_history(self):
        r = _run(["--json", "--mode", "headless", "session", "history"])
        assert r.returncode == 0, (
            f"session history failed:\nstdout: {r.stdout[:500]}\nstderr: {r.stderr[:500]}")

    def test_formats(self):
        r = _run(["--json", "--mode", "headless", "formats"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert ".ply" in data["point_cloud"]
        assert ".obj" in data["mesh"]
