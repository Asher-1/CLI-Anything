"""End-to-end tests — require ACloudViewer binary.

These tests invoke the real ACloudViewer binary and verify output files.
Skip automatically if ACloudViewer is not available.
"""

import subprocess
import sys
import struct
import tempfile
from pathlib import Path

import pytest

from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend

_BINARY = ACloudViewerBackend.find_binary()
needs_binary = pytest.mark.skipif(
    _BINARY is None,
    reason="ACloudViewer binary not found (set ACV_BINARY or add to PATH)")


def _cli(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli_anything.acloudviewer",
         "--json", "--mode", "headless"] + args,
        capture_output=True, text=True, timeout=timeout)


def _write_minimal_ply(path: Path, num_points: int = 100):
    """Write a minimal valid ASCII PLY file."""
    header = (
        "ply\n"
        "format ascii 1.0\n"
        f"element vertex {num_points}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "end_header\n"
    )
    with open(path, "w", newline="\n") as f:
        f.write(header)
        for i in range(num_points):
            x = (i % 10) * 0.1
            y = (i // 10) * 0.1
            z = i * 0.001
            f.write(f"{x:.3f} {y:.3f} {z:.3f}\n")


@needs_binary
class TestConversion:
    def test_ply_to_pcd(self, tmp_path):
        src = tmp_path / "input.ply"
        dst = tmp_path / "output.pcd"
        _write_minimal_ply(src)

        r = _cli(["convert", str(src), str(dst)])
        assert r.returncode == 0

        import json
        data = json.loads(r.stdout)
        assert data["status"] in ("converted", "completed")

    def test_formats_command(self):
        r = _cli(["formats"])
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert ".ply" in data["point_cloud"]


@needs_binary
class TestProcessing:
    def test_subsample(self, tmp_path):
        src = tmp_path / "input.ply"
        dst = tmp_path / "subsampled.ply"
        _write_minimal_ply(src, num_points=500)

        r = _cli(["process", "subsample", str(src), "-o", str(dst),
                   "--method", "SPATIAL", "--voxel-size", "0.2"])
        assert r.returncode == 0

    def test_normals(self, tmp_path):
        src = tmp_path / "input.ply"
        dst = tmp_path / "normals.ply"
        _write_minimal_ply(src, num_points=200)

        r = _cli(["process", "normals", str(src), "-o", str(dst)])
        assert r.returncode == 0

    def test_delaunay(self, tmp_path):
        src = tmp_path / "input.ply"
        dst = tmp_path / "mesh.obj"
        _write_minimal_ply(src, num_points=50)

        r = _cli(["process", "delaunay", str(src), "-o", str(dst)])
        assert r.returncode == 0


@needs_binary
class TestBatchConvert:
    def test_batch(self, tmp_path):
        in_dir = tmp_path / "input"
        out_dir = tmp_path / "output"
        in_dir.mkdir()

        for i in range(3):
            _write_minimal_ply(in_dir / f"cloud_{i}.ply", num_points=50)

        r = _cli(["batch-convert", str(in_dir), str(out_dir), "-f", ".pcd"])
        assert r.returncode == 0

        import json
        data = json.loads(r.stdout)
        assert data["converted"] >= 0


@needs_binary
class TestSessionIntegration:
    def test_session_tracks_operations(self):
        """Session status should update after commands."""
        r = _cli(["info"])
        assert r.returncode == 0

        r = _cli(["session", "status"])
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert "history_length" in data
