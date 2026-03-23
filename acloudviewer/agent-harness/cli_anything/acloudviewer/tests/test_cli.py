"""CLI help and structure tests."""

import os
import subprocess
import sys
import json
import pytest
from pathlib import Path

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
        assert r.returncode == 0
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
    ])
    def test_subcommand_help(self, cmd):
        r = _run(cmd.split())
        assert r.returncode == 0

    def test_process_subcommands(self):
        r = _run(["process", "--help"])
        assert r.returncode == 0
        for cmd in ["subsample", "normals", "icp", "sor",
                     "c2c-dist", "c2m-dist", "density", "curvature",
                     "roughness", "delaunay", "sample-mesh", "color-banding"]:
            assert cmd in r.stdout, f"Missing: {cmd}"


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
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["mode"] == "headless"

    def test_session_status(self):
        r = _run(["--json", "--mode", "headless", "session", "status"])
        assert r.returncode == 0

    def test_formats(self):
        r = _run(["--json", "--mode", "headless", "formats"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert ".ply" in data["point_cloud"]
        assert ".obj" in data["mesh"]
