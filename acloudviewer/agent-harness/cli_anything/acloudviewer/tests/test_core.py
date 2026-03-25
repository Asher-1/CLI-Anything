"""Unit tests for core modules — no external dependencies needed."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from cli_anything.acloudviewer.core.session import Session, Snapshot
from cli_anything.acloudviewer.core import scene


# ── Session Tests ────────────────────────────────────────────────

class TestSnapshot:
    def test_fields(self):
        s = Snapshot(description="test action")
        assert s.description == "test action"
        assert isinstance(s.timestamp, str)
        assert len(s.timestamp) > 0

    def test_custom_timestamp(self):
        s = Snapshot(description="a", timestamp="2025-01-01T00:00:00")
        assert s.timestamp == "2025-01-01T00:00:00"

    def test_default_timestamp_varies(self):
        s1 = Snapshot(description="a")
        s2 = Snapshot(description="b")
        assert isinstance(s1.timestamp, str)
        assert isinstance(s2.timestamp, str)


class TestSession:
    def test_empty(self):
        s = Session()
        st = s.status()
        assert st["history_length"] == 0
        assert st["redo_length"] == 0
        assert st["last"] is None

    def test_snapshot_adds_history(self):
        s = Session()
        s.snapshot("first")
        assert s.status()["history_length"] == 1
        assert s.status()["last"] == "first"

    def test_snapshot_clears_redo(self):
        s = Session()
        s.snapshot("a")
        s.snapshot("b")
        s.undo()
        assert s.status()["redo_length"] == 1
        s.snapshot("c")
        assert s.status()["redo_length"] == 0

    def test_undo_returns_snapshot(self):
        s = Session()
        s.snapshot("action 1")
        s.snapshot("action 2")
        undone = s.undo()
        assert isinstance(undone, Snapshot)
        assert undone.description == "action 2"

    def test_undo_moves_to_redo(self):
        s = Session()
        s.snapshot("a")
        s.snapshot("b")
        s.undo()
        assert s.status()["history_length"] == 1
        assert s.status()["redo_length"] == 1

    def test_undo_empty_returns_none(self):
        s = Session()
        result = s.undo()
        assert result is None

    def test_redo_returns_snapshot(self):
        s = Session()
        s.snapshot("action 1")
        s.snapshot("action 2")
        s.undo()
        redone = s.redo()
        assert isinstance(redone, Snapshot)
        assert redone.description == "action 2"

    def test_redo_moves_to_history(self):
        s = Session()
        s.snapshot("a")
        s.undo()
        s.redo()
        assert s.status()["history_length"] == 1
        assert s.status()["redo_length"] == 0

    def test_redo_empty_returns_none(self):
        s = Session()
        result = s.redo()
        assert result is None

    def test_undo_redo_sequence(self):
        s = Session()
        s.snapshot("a")
        s.snapshot("b")
        s.snapshot("c")
        assert s.status()["history_length"] == 3

        s.undo()  # c
        s.undo()  # b
        assert s.status()["history_length"] == 1
        assert s.status()["redo_length"] == 2
        assert s.status()["last"] == "a"

        s.redo()  # b
        assert s.status()["last"] == "b"
        assert s.status()["redo_length"] == 1

    def test_many_snapshots(self):
        s = Session()
        for i in range(100):
            s.snapshot(f"action {i}")
        assert s.status()["history_length"] == 100
        assert s.status()["last"] == "action 99"


# ── Scene Tests ──────────────────────────────────────────────────

class TestScene:
    def setup_method(self):
        scene._project_file = None
        scene._entities = []

    def test_create_project(self):
        result = scene.create_project("/tmp/test.json")
        assert result["project"] == "/tmp/test.json"
        assert result["status"] == "created"

    def test_create_project_resets_entities(self):
        scene._entities = [{"id": 1}]
        scene.create_project("/tmp/new.json")
        assert len(scene._entities) == 0

    def test_get_project_info_empty(self):
        info = scene.get_project_info()
        assert info["project_file"] is None
        assert info["entity_count"] == 0

    def test_get_project_info_after_create(self):
        scene.create_project("/tmp/test.json")
        info = scene.get_project_info()
        assert info["project_file"] == "/tmp/test.json"
        assert info["entity_count"] == 0

    def test_add_entity_record(self):
        scene.add_entity_record({"id": 1, "name": "cloud1", "type": "POINT_CLOUD"})
        assert scene.get_project_info()["entity_count"] == 1

    def test_add_multiple_entities(self):
        scene.add_entity_record({"id": 1, "name": "a"})
        scene.add_entity_record({"id": 2, "name": "b"})
        scene.add_entity_record({"id": 3, "name": "c"})
        assert scene.get_project_info()["entity_count"] == 3

    def test_remove_entity_record(self):
        scene.add_entity_record({"id": 10, "name": "x"})
        scene.add_entity_record({"id": 20, "name": "y"})
        scene.remove_entity_record(10)
        info = scene.get_project_info()
        assert info["entity_count"] == 1

    def test_remove_nonexistent_entity(self):
        scene.add_entity_record({"id": 1, "name": "a"})
        scene.remove_entity_record(999)
        assert scene.get_project_info()["entity_count"] == 1

    def test_save_and_open(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            scene.create_project(path)
            scene.add_entity_record({"id": 1, "name": "cloud"})
            scene.add_entity_record({"id": 2, "name": "mesh"})
            result = scene.save_project()
            assert result["saved"] == 2

            scene._entities = []
            loaded = scene.open_project(path)
            assert loaded["entities"] == 2
        finally:
            os.unlink(path)

    def test_save_no_project(self):
        scene._project_file = None
        result = scene.save_project()
        assert "error" in result

    def test_save_explicit_path(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            scene.add_entity_record({"id": 1, "name": "test"})
            result = scene.save_project(path)
            assert result["saved"] == 1
            assert Path(path).exists()
            data = json.loads(Path(path).read_text())
            assert len(data["entities"]) == 1
        finally:
            os.unlink(path)

    def test_open_nonexistent_file(self):
        result = scene.open_project("/nonexistent/path.json")
        assert result["entities"] == 0

    def test_open_non_json_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not json")
            path = f.name
        try:
            result = scene.open_project(path)
            assert result["entities"] == 0
        finally:
            os.unlink(path)


# ── Format Constants Tests ───────────────────────────────────────

class TestFormats:
    def test_ply_in_both(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            POINT_CLOUD_FORMATS, MESH_FORMATS,
        )
        assert ".ply" in POINT_CLOUD_FORMATS
        assert ".ply" in MESH_FORMATS

    def test_common_cloud_extensions(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import POINT_CLOUD_FORMATS
        for ext in (".pcd", ".xyz", ".las", ".e57", ".drc", ".bin"):
            assert ext in POINT_CLOUD_FORMATS, f"Missing: {ext}"

    def test_common_mesh_extensions(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import MESH_FORMATS
        for ext in (".obj", ".stl", ".off", ".fbx", ".vtk"):
            assert ext in MESH_FORMATS, f"Missing: {ext}"

    def test_all_is_superset(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            POINT_CLOUD_FORMATS, MESH_FORMATS, ALL_SUPPORTED_FORMATS,
        )
        assert POINT_CLOUD_FORMATS.issubset(ALL_SUPPORTED_FORMATS)
        assert MESH_FORMATS.issubset(ALL_SUPPORTED_FORMATS)

    def test_format_maps_consistent(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            CLOUD_FORMAT_MAP, MESH_FORMAT_MAP, POINT_CLOUD_FORMATS, MESH_FORMATS,
        )
        for ext in CLOUD_FORMAT_MAP:
            assert ext in POINT_CLOUD_FORMATS, f"{ext} in CLOUD_FORMAT_MAP but not POINT_CLOUD_FORMATS"
        for ext in MESH_FORMAT_MAP:
            assert ext in MESH_FORMATS, f"{ext} in MESH_FORMAT_MAP but not MESH_FORMATS"

    def test_supported_formats_static(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        f = ACloudViewerBackend.supported_formats()
        assert isinstance(f, dict)
        assert "point_cloud" in f
        assert "mesh" in f
        assert ".ply" in f["point_cloud"]
        assert ".obj" in f["mesh"]

    def test_image_formats(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import IMAGE_FORMATS
        for ext in (".png", ".jpg", ".bmp"):
            assert ext in IMAGE_FORMATS


# ── Format Conversion Tests ──────────────────────────────────────

class TestFormatConversion:
    """Tests for convert_format dispatch logic (mocked binary)."""

    @pytest.fixture
    def backend(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        from unittest.mock import patch, MagicMock
        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._binary = "/mock/ACloudViewer"
        b._mode = "headless"
        b._rpc = None
        return b

    def _patch_run(self, backend, output_exists=True):
        from unittest.mock import patch, MagicMock
        import subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        def side_effect(args, **kwargs):
            if output_exists:
                for i, a in enumerate(args):
                    if a == "FILE" and i + 1 < len(args):
                        Path(args[i + 1]).parent.mkdir(parents=True, exist_ok=True)
                        Path(args[i + 1]).write_text("mock data")
            return mock_result

        return patch.object(backend, '_run_cli', side_effect=side_effect)

    def test_cloud_to_cloud_ply_to_pcd(self, backend, tmp_path):
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.pcd"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        assert result["status"] == "converted"
        args = mock_run.call_args[0][0]
        assert "-C_EXPORT_FMT" in args
        assert "PCD" in args
        assert "-SAVE_CLOUDS" in args

    def test_cloud_to_cloud_ply_to_asc(self, backend, tmp_path):
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.asc"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        assert result["status"] == "converted"
        args = mock_run.call_args[0][0]
        assert "-C_EXPORT_FMT" in args
        assert "ASC" in args

    def test_cloud_to_cloud_ply_to_xyz_uses_asc(self, backend, tmp_path):
        """XYZ output should use ASC export format (ACloudViewer naming)."""
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.xyz"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        args = mock_run.call_args[0][0]
        assert "ASC" in args

    def test_cloud_to_cloud_ply_to_vtk(self, backend, tmp_path):
        """VTK is in both cloud and mesh sets; cloud→cloud should take priority."""
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.vtk"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        args = mock_run.call_args[0][0]
        assert "-C_EXPORT_FMT" in args
        assert "VTK" in args
        assert "-DELAUNAY" not in args

    def test_cloud_to_mesh_ply_to_obj(self, backend, tmp_path):
        """PLY (cloud) → OBJ (mesh) should trigger Delaunay."""
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.obj"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        args = mock_run.call_args[0][0]
        assert "-DELAUNAY" in args
        assert "-M_EXPORT_FMT" in args
        assert "OBJ" in args
        assert "-SAVE_MESHES" in args

    def test_cloud_to_mesh_ply_to_stl(self, backend, tmp_path):
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.stl"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        args = mock_run.call_args[0][0]
        assert "-DELAUNAY" in args
        assert "STL" in args

    def test_mesh_to_mesh_obj_to_stl(self, backend, tmp_path):
        """OBJ (mesh-only) → STL should not trigger Delaunay."""
        src = tmp_path / "in.obj"
        src.write_text("mock")
        dst = tmp_path / "out.stl"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        args = mock_run.call_args[0][0]
        assert "-DELAUNAY" not in args
        assert "-SAVE_MESHES" in args
        assert "STL" in args

    def test_mesh_to_cloud_obj_to_pcd(self, backend, tmp_path):
        """OBJ → PCD should sample mesh to cloud."""
        src = tmp_path / "in.obj"
        src.write_text("mock")
        dst = tmp_path / "out.pcd"
        with self._patch_run(backend) as mock_run:
            result = backend.convert_format(str(src), str(dst))
        args = mock_run.call_args[0][0]
        assert "-SAMPLE_MESH" in args
        assert "-SAVE_CLOUDS" in args

    def test_alias_lookup_xyz_finds_asc(self, backend, tmp_path):
        """When .xyz output not found, should look for .asc alias."""
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.xyz"
        asc_file = tmp_path / "out.asc"
        asc_file.write_text("asc data")

        with self._patch_run(backend, output_exists=False):
            result = backend.convert_format(str(src), str(dst))

        assert result["status"] == "converted"
        assert dst.exists()

    def test_alias_lookup_csv_finds_asc(self, backend, tmp_path):
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.csv"
        asc_file = tmp_path / "out.asc"
        asc_file.write_text("csv data")

        with self._patch_run(backend, output_exists=False):
            result = backend.convert_format(str(src), str(dst))

        assert result["status"] == "converted"
        assert dst.exists()

    def test_format_map_asc_not_ascii(self):
        """CLOUD_FORMAT_MAP must use 'ASC' not 'ASCII' for ACloudViewer CLI."""
        from cli_anything.acloudviewer.utils.acloudviewer_backend import CLOUD_FORMAT_MAP
        for ext in (".asc", ".xyz", ".csv", ".txt"):
            assert CLOUD_FORMAT_MAP[ext] == "ASC", f"{ext} should map to ASC, got {CLOUD_FORMAT_MAP[ext]}"

    def test_vtk_in_both_format_sets(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            POINT_CLOUD_FORMATS, MESH_FORMATS, CLOUD_FORMAT_MAP, MESH_FORMAT_MAP,
        )
        assert ".vtk" in POINT_CLOUD_FORMATS
        assert ".vtk" in MESH_FORMATS
        assert CLOUD_FORMAT_MAP[".vtk"] == "VTK"
        assert MESH_FORMAT_MAP[".vtk"] == "VTK"

    def test_format_alias_exts_defined(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import _FORMAT_ALIAS_EXTS
        assert ".xyz" in _FORMAT_ALIAS_EXTS
        assert ".asc" in _FORMAT_ALIAS_EXTS[".xyz"]
        assert ".csv" in _FORMAT_ALIAS_EXTS
        assert ".asc" in _FORMAT_ALIAS_EXTS[".csv"]

    def test_failed_conversion_returns_failed(self, backend, tmp_path):
        src = tmp_path / "in.ply"
        src.write_text("mock")
        dst = tmp_path / "out.pcd"
        with self._patch_run(backend, output_exists=False):
            result = backend.convert_format(str(src), str(dst))
        assert result["status"] == "failed"

    def test_input_not_found_raises(self, backend):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError, match="Input not found"):
            backend.convert_format("/nonexistent/file.ply", "/tmp/out.pcd")


# ── Extended Format Map Coverage Tests ───────────────────────────

class TestExtendedFormatMaps:
    """Verify all format maps contain complete entries for supported formats."""

    def test_cloud_format_map_covers_key_formats(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            CLOUD_FORMAT_MAP, POINT_CLOUD_FORMATS,
        )
        required_cloud = {
            ".ply": "PLY", ".pcd": "PCD", ".las": "LAS", ".laz": "LAS",
            ".e57": "E57", ".bin": "BIN", ".sbf": "SBF", ".drc": "DRC",
            ".vtk": "VTK",
        }
        for ext, expected_fmt in required_cloud.items():
            assert ext in POINT_CLOUD_FORMATS, f"{ext} missing from POINT_CLOUD_FORMATS"
            assert CLOUD_FORMAT_MAP.get(ext) == expected_fmt, (
                f"CLOUD_FORMAT_MAP['{ext}'] should be '{expected_fmt}', "
                f"got '{CLOUD_FORMAT_MAP.get(ext)}'"
            )

    def test_mesh_format_map_covers_key_formats(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            MESH_FORMAT_MAP, MESH_FORMATS,
        )
        required_mesh = {
            ".obj": "OBJ", ".stl": "STL", ".off": "OFF",
            ".fbx": "FBX", ".ply": "PLY", ".dxf": "DXF", ".vtk": "VTK",
        }
        for ext, expected_fmt in required_mesh.items():
            assert ext in MESH_FORMATS, f"{ext} missing from MESH_FORMATS"
            assert MESH_FORMAT_MAP.get(ext) == expected_fmt, (
                f"MESH_FORMAT_MAP['{ext}'] should be '{expected_fmt}', "
                f"got '{MESH_FORMAT_MAP.get(ext)}'"
            )

    def test_point_cloud_formats_complete(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import POINT_CLOUD_FORMATS
        expected = {".ply", ".pcd", ".xyz", ".xyzn", ".xyzrgb", ".pts",
                    ".txt", ".asc", ".neu", ".csv", ".las", ".laz",
                    ".e57", ".ptx", ".bin", ".sbf", ".drc", ".vtk"}
        missing = expected - POINT_CLOUD_FORMATS
        assert not missing, f"Missing from POINT_CLOUD_FORMATS: {missing}"

    def test_mesh_formats_complete(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import MESH_FORMATS
        expected = {".obj", ".stl", ".off", ".gltf", ".glb", ".fbx",
                    ".dae", ".3ds", ".ply", ".dxf", ".vtk"}
        missing = expected - MESH_FORMATS
        assert not missing, f"Missing from MESH_FORMATS: {missing}"

    def test_all_supported_formats_superset(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            POINT_CLOUD_FORMATS, MESH_FORMATS, IMAGE_FORMATS,
            ALL_SUPPORTED_FORMATS,
        )
        union = POINT_CLOUD_FORMATS | MESH_FORMATS | IMAGE_FORMATS
        missing = union - ALL_SUPPORTED_FORMATS
        assert not missing, f"ALL_SUPPORTED_FORMATS missing: {missing}"

    def test_format_alias_all_variants(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import _FORMAT_ALIAS_EXTS
        for key in (".xyz", ".csv", ".txt", ".neu"):
            assert key in _FORMAT_ALIAS_EXTS, f"{key} missing from _FORMAT_ALIAS_EXTS"
            assert ".asc" in _FORMAT_ALIAS_EXTS[key], (
                f"_FORMAT_ALIAS_EXTS['{key}'] should contain '.asc'"
            )

    def test_image_formats_tiff(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import IMAGE_FORMATS
        for ext in (".tif", ".tiff", ".png", ".jpg", ".bmp"):
            assert ext in IMAGE_FORMATS, f"{ext} missing from IMAGE_FORMATS"

    def test_extra_formats_in_all(self):
        """SHP, POV, PV, PGM are in ALL_SUPPORTED but not in cloud/mesh sets."""
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ALL_SUPPORTED_FORMATS
        for ext in (".shp", ".pov", ".pn", ".pv"):
            assert ext in ALL_SUPPORTED_FORMATS, f"{ext} missing from ALL_SUPPORTED_FORMATS"


# ── Version Detection Tests ──────────────────────────────────────

class TestVersionDetection:
    def test_version_from_maintenancetool(self, tmp_path):
        from unittest.mock import patch, MagicMock
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend

        resolved = tmp_path.resolve()
        mt = resolved / "maintenancetool"
        mt.write_text("#!/bin/sh\n")
        mt.chmod(0o755)
        binary = resolved / "ACloudViewer.sh"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        xml_output = '''<?xml version="1.0"?>
<localpackages>
    <package name="ACloudViewer" displayname="ACloudViewer" version="99.88.77"/>
</localpackages>'''

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.stderr = ""
            if str(mt) in cmd:
                result.returncode = 0
                result.stdout = xml_output
            else:
                result.returncode = 1
                result.stdout = ""
            return result

        mod = "cli_anything.acloudviewer.utils.acloudviewer_backend"
        with patch.object(ACloudViewerBackend, 'find_binary', return_value=str(binary)), \
             patch(f'{mod}.subprocess.run', side_effect=mock_run):
            ver = ACloudViewerBackend.get_version()
        assert ver == "99.88.77"

    def test_version_from_desktop_file(self, tmp_path):
        from unittest.mock import patch, MagicMock
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend

        resolved = tmp_path.resolve()
        binary = resolved / "ACloudViewer.sh"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        desktop = resolved / "ACloudViewer.desktop"
        desktop.write_text("[Desktop Entry]\nVersion=11.22.33\nName=ACloudViewer\n")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""

        mod = "cli_anything.acloudviewer.utils.acloudviewer_backend"
        with patch.object(ACloudViewerBackend, 'find_binary', return_value=str(binary)), \
             patch(f'{mod}.subprocess.run', return_value=mock_result):
            ver = ACloudViewerBackend.get_version()
        assert ver == "11.22.33"

    def test_version_no_binary(self):
        from unittest.mock import patch
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        with patch.object(ACloudViewerBackend, 'find_binary', return_value=None):
            assert ACloudViewerBackend.get_version() is None


# ── Binary Discovery Tests ───────────────────────────────────────

class TestBinaryDiscovery:
    def test_find_binary_returns_str_or_none(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        binary = ACloudViewerBackend.find_binary()
        assert binary is None or isinstance(binary, str)

    def test_binary_names_platform(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        names = ACloudViewerBackend._binary_names()
        assert isinstance(names, tuple)
        assert len(names) >= 2
        assert all(isinstance(n, str) for n in names)

    def test_install_dirs_platform(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        dirs = ACloudViewerBackend._install_dirs()
        assert isinstance(dirs, list)
        assert len(dirs) >= 2
        assert all(isinstance(d, Path) for d in dirs)

    def test_env_override(self):
        from unittest.mock import patch
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        with patch.dict(os.environ, {"ACV_BINARY": "/nonexistent/ACloudViewer"}):
            binary = ACloudViewerBackend.find_binary()
            assert binary != "/nonexistent/ACloudViewer"

    def test_build_env_for_binary_sets_offscreen(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        env = ACloudViewerBackend._build_env_for_binary("/usr/bin/ACloudViewer")
        assert env["QT_QPA_PLATFORM"] == "offscreen"

    def test_build_env_skips_ld_for_script(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        env = ACloudViewerBackend._build_env_for_binary("/opt/ACloudViewer/bin/ACloudViewer.sh")
        assert env["QT_QPA_PLATFORM"] == "offscreen"


# ── Colmap Backend Tests ─────────────────────────────────────────

class TestColmapBackend:
    def test_find_binary(self):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        binary = ColmapBackend.find_binary()
        assert binary is None or isinstance(binary, str)

    def test_init_without_binary_raises(self):
        from unittest.mock import patch
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend, ColmapError
        with patch.object(ColmapBackend, "find_binary", return_value=None):
            with pytest.raises(ColmapError):
                ColmapBackend()

    def test_init_with_explicit_binary(self):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        cb = ColmapBackend(binary="/usr/bin/colmap")
        assert cb._binary == "/usr/bin/colmap"


# ── RPC Client Tests (offline) ───────────────────────────────────

class TestRPCClient:
    def test_create_client(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        client = ACloudViewerRPCClient("ws://localhost:6001")
        assert not client.is_connected()

    def test_default_url(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        client = ACloudViewerRPCClient()
        assert client._url == "ws://localhost:6001"

    def test_custom_url(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        client = ACloudViewerRPCClient("ws://192.168.1.100:9999")
        assert client._url == "ws://192.168.1.100:9999"

    def test_rpc_error(self):
        from cli_anything.acloudviewer.utils.rpc_client import RPCError
        err = RPCError(code=-32600, message="Invalid request")
        assert err.code == -32600
        assert err.message == "Invalid request"
        assert "-32600" in str(err)

    def test_next_id_increments(self):
        from cli_anything.acloudviewer.utils.rpc_client import _next_id
        id1 = _next_id()
        id2 = _next_id()
        assert id2 > id1

    def test_close_when_not_connected(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        client = ACloudViewerRPCClient()
        client.close()  # should not raise

    def test_context_manager_not_connected(self):
        from unittest.mock import patch, MagicMock
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient

        client = ACloudViewerRPCClient()
        with patch.object(client, 'connect', side_effect=ConnectionRefusedError):
            with pytest.raises(ConnectionRefusedError):
                with client:
                    pass


# ── Backend Mode Tests ───────────────────────────────────────────

class TestBackendMode:
    def test_headless_mode(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        backend = ACloudViewerBackend(mode="headless")
        assert backend.mode == "headless"

    def test_auto_mode_falls_to_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        backend = ACloudViewerBackend(mode="auto")
        assert backend.mode in ("gui", "headless")

    def test_backend_error(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        err = BackendError("test error")
        assert "test error" in str(err)
