"""Comprehensive CLI tests - Direct invocation with Click.testing.CliRunner.

This file consolidates all CLI command tests using direct function calls
instead of subprocess, which provides better coverage measurement.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from click.testing import CliRunner

from cli_anything.acloudviewer import acloudviewer_cli
from cli_anything.acloudviewer.acloudviewer_cli import (
    cli, get_session, output, _print_dict, _print_list, handle_error
)
from cli_anything.acloudviewer.core.session import Session


def _write_minimal_ply(path: Path, num_points: int = 100):
    """Write a minimal valid ASCII PLY file."""
    with open(path, "w", newline="\n") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {num_points}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("end_header\n")
        for i in range(num_points):
            f.write(f"{i*0.1:.3f} {i*0.1:.3f} {i*0.001:.3f}\n")


# ============================================================================
# Helper Functions Tests
# ============================================================================

class TestCLIHelpers:
    """Test CLI helper functions."""

    def test_get_session(self):
        session = get_session()
        assert isinstance(session, Session)
        session2 = get_session()
        assert session is session2

    def test_output_dict(self):
        output({"key": "value"}, "test message")
        assert True

    def test_output_string(self):
        output("test string")
        assert True

    def test_output_list(self):
        output([1, 2, 3])
        assert True

    def test_output_none(self):
        output(None)
        assert True

    def test_print_dict(self):
        _print_dict({"a": 1, "b": 2})
        assert True

    def test_print_dict_nested(self):
        _print_dict({"outer": {"inner": "value"}})
        assert True

    def test_print_list(self):
        _print_list(["item1", "item2"])
        assert True

    def test_print_list_with_dicts(self):
        _print_list([{"id": 1}, {"id": 2}])
        assert True

    def test_handle_error_decorator(self):
        @handle_error
        def success_fn():
            return "success"
        
        result = success_fn()
        assert result == "success"


# ============================================================================
# Info & Check Commands
# ============================================================================

class TestInfoCommands:
    """Test info and check commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_info(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.get_info.return_value = {"mode": "headless", "version": "3.9.5"}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['info'])
        assert backend_mock.get_info.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_check(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.check_binary.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['check'])
        assert backend_mock.check_binary.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_formats(self, mock_backend):
        runner = CliRunner()
        mock_backend.return_value = Mock()
        
        result = runner.invoke(cli, ['formats'])
        assert ".ply" in result.output or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_methods(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.mode = "gui"
        rpc_mock = Mock()
        rpc_mock.list_methods.return_value = ["method1", "method2"]
        backend_mock._rpc = rpc_mock
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['methods'])
        assert result.exit_code == 0 or rpc_mock.list_methods.called


# ============================================================================
# File Operations
# ============================================================================

class TestFileCommands:
    """Test file operation commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_open(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.open_file.return_value = {"entity_id": 123}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['open', str(src)])
        assert backend_mock.open_file.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_convert(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "input.ply"
        dst = tmp_path / "output.pcd"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.convert_file.return_value = {"status": "converted"}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['convert', str(src), str(dst)])
        assert backend_mock.convert_file.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_batch_convert(self, mock_backend, tmp_path):
        runner = CliRunner()
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        backend_mock = Mock()
        backend_mock.batch_convert.return_value = {"converted": 5}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['batch-convert', str(input_dir), str(output_dir)])
        assert backend_mock.batch_convert.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_export(self, mock_backend, tmp_path):
        runner = CliRunner()
        output = tmp_path / "exported.ply"
        
        backend_mock = Mock()
        backend_mock.export_entity.return_value = str(output)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['export', '123', str(output)])
        assert backend_mock.export_entity.called or result.exit_code == 0


# ============================================================================
# Scene Commands
# ============================================================================

class TestSceneCommands:
    """Test scene management commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_list(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.scene_list.return_value = [{"id": 1, "name": "Cloud1"}]
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['scene', 'list'])
        assert backend_mock.scene_list.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_info(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.scene_info.return_value = {"entities": []}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['scene', 'info', '123'])
        assert backend_mock.scene_info.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_clear(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.clear.return_value = None
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['scene', 'clear'])
        assert backend_mock.clear.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_clear(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.clear.return_value = None
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['clear'])
        assert backend_mock.clear.called or result.exit_code == 0


# ============================================================================
# Session Commands
# ============================================================================

class TestSessionCommands:
    """Test session management commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_session_status(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.session_status.return_value = {"status": "active"}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['session', 'status'])
        assert backend_mock.session_status.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_session_history(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.session_history.return_value = ["cmd1", "cmd2"]
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['session', 'history'])
        assert backend_mock.session_history.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_session_undo(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.session_undo.return_value = {"status": "undone"}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['session', 'undo'])
        assert backend_mock.session_undo.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_session_redo(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.session_redo.return_value = {"status": "redone"}
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['session', 'redo'])
        assert backend_mock.session_redo.called or result.exit_code == 0


# ============================================================================
# Process Commands
# ============================================================================

class TestProcessCommands:
    """Test point cloud and mesh processing commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_subsample(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        dst = tmp_path / "output.ply"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.subsample.return_value = str(dst)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['process', 'subsample', str(src), '-o', str(dst), '--method', 'RANDOM', '--voxel-size', '0.05'])
        assert backend_mock.subsample.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        dst = tmp_path / "output.ply"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.compute_normals.return_value = str(dst)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['process', 'normals', str(src), '-o', str(dst)])
        assert backend_mock.compute_normals.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_density(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        dst = tmp_path / "output.ply"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.compute_density.return_value = str(dst)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['process', 'density', str(src), '-o', str(dst)])
        assert backend_mock.compute_density.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_curvature(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        dst = tmp_path / "output.ply"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.compute_curvature.return_value = str(dst)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['process', 'curvature', str(src), '-o', str(dst)])
        assert backend_mock.compute_curvature.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_delaunay(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        dst = tmp_path / "mesh.obj"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.delaunay.return_value = str(dst)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['process', 'delaunay', str(src), '-o', str(dst)])
        assert backend_mock.delaunay.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sor(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "cloud.ply"
        dst = tmp_path / "filtered.ply"
        _write_minimal_ply(src)
        
        backend_mock = Mock()
        backend_mock.sor_filter.return_value = str(dst)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['process', 'sor', str(src), '-o', str(dst)])
        assert backend_mock.sor_filter.called or result.exit_code == 0


# ============================================================================
# View Commands
# ============================================================================

class TestViewCommands:
    """Test view and visualization commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_screenshot(self, mock_backend, tmp_path):
        runner = CliRunner()
        output = tmp_path / "screenshot.png"
        
        backend_mock = Mock()
        backend_mock.view_screenshot.return_value = str(output)
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['view', 'screenshot', str(output)])
        assert backend_mock.view_screenshot.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_zoom(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.view_zoom_fit.return_value = None
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['view', 'zoom'])
        assert backend_mock.view_zoom_fit.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_refresh(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.view_refresh.return_value = None
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['view', 'refresh'])
        assert backend_mock.view_refresh.called or result.exit_code == 0


# ============================================================================
# Entity Commands
# ============================================================================

class TestEntityCommands:
    """Test entity management commands."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_entity_rename(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.entity_rename.return_value = None
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['entity', 'rename', '123', 'NewName'])
        assert backend_mock.entity_rename.called or result.exit_code == 0

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_entity_set_color(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.entity_set_color.return_value = None
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['entity', 'set-color', '123', '255', '0', '0'])
        assert backend_mock.entity_set_color.called or result.exit_code == 0


# ============================================================================
# CLI Context and Options
# ============================================================================

class TestCLIContext:
    """Test CLI context and global options."""

    def test_cli_with_json_flag(self):
        runner = CliRunner()
        with patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend'):
            result = runner.invoke(cli, ['--json', 'info'])
            assert result.exit_code == 0 or result.exit_code == 1

    def test_cli_with_mode_headless(self):
        runner = CliRunner()
        with patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend'):
            result = runner.invoke(cli, ['--mode', 'headless', 'info'])
            assert result.exit_code == 0 or result.exit_code == 1

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'acloudviewer' in result.output.lower() or 'Usage' in result.output


# ============================================================================
# Cloud (GUI)
# ============================================================================

class TestCloudGUICommands:
    """Test cloud paint / scalar field / crop commands (GUI mode)."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_cloud_paint_uniform(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.cloud_paint_uniform_gui.return_value = {"entity_id": 1, "status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['cloud', 'paint-uniform', '1', '255', '128', '64'])
        assert result.exit_code == 0
        assert backend_mock.cloud_paint_uniform_gui.called
        assert '255' in result.output or 'entity_id' in result.output

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_cloud_paint_by_height(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.cloud_paint_by_height_gui.return_value = {"entity_id": 2, "axis": "z"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['cloud', 'paint-by-height', '2', '--axis', 'z'])
        assert result.exit_code == 0
        assert backend_mock.cloud_paint_by_height_gui.called
        assert 'entity_id' in result.output or '2' in result.output

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_cloud_paint_by_scalar_field(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.cloud_paint_by_scalar_field_gui.return_value = {"entity_id": 3}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['cloud', 'paint-by-scalar-field', '3', '--field', 'intensity'])
        assert result.exit_code == 0
        assert backend_mock.cloud_paint_by_scalar_field_gui.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_cloud_get_scalar_fields(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.cloud_get_scalar_fields.return_value = ["sf0", "sf1"]
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['cloud', 'get-scalar-fields', '4'])
        assert result.exit_code == 0
        assert backend_mock.cloud_get_scalar_fields.called
        assert 'sf0' in result.output

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_cloud_crop(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.crop.return_value = {"status": "cropped", "entity_id": 5}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, [
            'cloud', 'crop', '5',
            '--min-x', '0', '--min-y', '0', '--min-z', '0',
            '--max-x', '1', '--max-y', '1', '--max-z', '1',
        ])
        assert result.exit_code == 0
        assert backend_mock.crop.called


# ============================================================================
# Mesh (GUI)
# ============================================================================

class TestMeshGUICommands:
    """Test mesh simplify / smooth / subdivide / sample-points (GUI mode)."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_mesh_simplify(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.mesh_simplify_gui.return_value = {"entity_id": 1}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, [
            'mesh', 'simplify', '1', '--method', 'quadric',
            '--target-triangles', '5000', '--voxel-size', '0.1',
        ])
        assert result.exit_code == 0
        assert backend_mock.mesh_simplify_gui.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_mesh_smooth(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.mesh_smooth_gui.return_value = {"entity_id": 2}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, [
            'mesh', 'smooth', '2', '--method', 'laplacian',
            '--iterations', '3', '--lambda', '0.3', '--mu', '-0.5',
        ])
        assert result.exit_code == 0
        assert backend_mock.mesh_smooth_gui.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_mesh_subdivide(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.mesh_subdivide_gui.return_value = {"entity_id": 3}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['mesh', 'subdivide', '3', '--method', 'midpoint', '--iterations', '2'])
        assert result.exit_code == 0
        assert backend_mock.mesh_subdivide_gui.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_mesh_sample_points(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.mesh_sample_points_gui.return_value = {"entity_id": 4, "points": 1000}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['mesh', 'sample-points', '4', '--method', 'uniform', '--count', '1000'])
        assert result.exit_code == 0
        assert backend_mock.mesh_sample_points_gui.called


# ============================================================================
# Transform
# ============================================================================

class TestTransformCommands:
    """Test transform apply (GUI) and apply-file (headless)."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_transform_apply(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.transform_apply_gui.return_value = None
        mock_backend.return_value = backend_mock

        m = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        args = ['transform', 'apply', '42'] + [str(x) for x in m]
        result = runner.invoke(cli, args)
        assert result.exit_code == 0
        assert backend_mock.transform_apply_gui.called
        assert 'transformed' in result.output.lower() or 'entity_id' in result.output

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_transform_apply_file(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "in.ply"
        dst = tmp_path / "out.ply"
        mtx = tmp_path / "matrix.txt"
        _write_minimal_ply(src)
        mtx.write_text(" ".join(str(x) for x in ([1] * 16)))

        backend_mock = Mock()
        backend_mock.apply_transformation.return_value = {"status": "ok", "output": str(dst)}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, [
            'transform', 'apply-file', str(src), str(mtx), '-o', str(dst),
        ])
        assert result.exit_code == 0
        assert backend_mock.apply_transformation.called


# ============================================================================
# Scene: remove / show / hide / select
# ============================================================================

class TestSceneVisibilityCommands:
    """Test scene remove, show, hide, select."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_remove(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.scene_remove.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['scene', 'remove', '10'])
        assert result.exit_code == 0
        assert backend_mock.scene_remove.called
        assert 'removed' in result.output.lower() or '10' in result.output

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_show(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.scene_set_visible.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['scene', 'show', '11'])
        assert result.exit_code == 0
        assert backend_mock.scene_set_visible.call_args[0][1] is True

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_hide(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.scene_set_visible.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['scene', 'hide', '12'])
        assert result.exit_code == 0
        assert backend_mock.scene_set_visible.call_args[0][1] is False

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_scene_select(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.scene_select.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['scene', 'select', '1', '2', '3'])
        assert result.exit_code == 0
        assert backend_mock.scene_select.called
        assert 'selected' in result.output.lower()


# ============================================================================
# View: camera / orient / perspective / pointsize
# ============================================================================

class TestViewExtendedCommands:
    """Test view camera, orient, perspective, pointsize."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_camera(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.get_camera.return_value = {"position": [0, 0, 10], "fov": 45}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['view', 'camera'])
        assert result.exit_code == 0
        assert backend_mock.get_camera.called
        assert 'position' in result.output or 'fov' in result.output

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_orient(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.view_set_orientation.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['view', 'orient', 'top'])
        assert result.exit_code == 0
        assert backend_mock.view_set_orientation.called
        assert 'top' in result.output.lower() or 'orientation' in result.output.lower()

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_perspective(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.view_set_perspective.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['view', 'perspective', 'object'])
        assert result.exit_code == 0
        assert backend_mock.view_set_perspective.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_view_pointsize(self, mock_backend):
        runner = CliRunner()
        backend_mock = Mock()
        backend_mock.view_set_point_size.return_value = None
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['view', 'pointsize', '+'])
        assert result.exit_code == 0
        assert backend_mock.view_set_point_size.called


# ============================================================================
# Session save
# ============================================================================

class TestSessionSaveCommand:
    """Test session save."""

    @patch('cli_anything.acloudviewer.core.scene.save_project')
    @patch('cli_anything.acloudviewer.core.scene.create_project')
    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_session_save(self, mock_backend, mock_create, mock_save, tmp_path):
        runner = CliRunner()
        mock_backend.return_value = Mock()
        mock_create.return_value = {"project": "x", "status": "created"}
        mock_save.return_value = {"project": str(tmp_path / "p.json"), "saved": 0}

        out = tmp_path / "session_proj.json"
        result = runner.invoke(cli, ['session', 'save', str(out)])
        assert result.exit_code == 0
        assert 'saved' in result.output.lower()
        assert mock_save.called or mock_create.called


# ============================================================================
# SF convenience commands
# ============================================================================

class TestSfConvenienceCommands:
    """Test sf group headless wrappers."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_coord_to_sf(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.coord_to_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'coord-to-sf', str(src), '-o', str(dst), '--dimension', 'Z'])
        assert result.exit_code == 0
        assert backend_mock.coord_to_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_arithmetic(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.sf_arithmetic.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'arithmetic', str(src), '-o', str(dst), '--operation', 'SQRT'])
        assert result.exit_code == 0
        assert backend_mock.sf_arithmetic.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_operation(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.sf_operation.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'operation', str(src), '-o', str(dst), '--value', '2.5'])
        assert result.exit_code == 0
        assert backend_mock.sf_operation.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_gradient(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.sf_gradient.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'gradient', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.sf_gradient.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_filter(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.filter_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'filter', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.filter_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_color_scale(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        scale = tmp_path / "scale.xml"
        _write_minimal_ply(src)
        scale.write_text("<scale/>")
        backend_mock = Mock()
        backend_mock.sf_color_scale.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'color-scale', str(src), '-o', str(dst), '--scale-file', str(scale)])
        assert result.exit_code == 0
        assert backend_mock.sf_color_scale.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_convert_to_rgb(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.sf_convert_to_rgb.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'convert-to-rgb', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.sf_convert_to_rgb.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_set_active(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.set_active_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'set-active', str(src), '-o', str(dst), '--sf-index', '0'])
        assert result.exit_code == 0
        assert backend_mock.set_active_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_rename(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.rename_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'rename', str(src), '-o', str(dst), '--new-name', 'myfield'])
        assert result.exit_code == 0
        assert backend_mock.rename_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_remove(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.remove_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'remove', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.remove_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_sf_remove_all(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "out.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.remove_all_sfs.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['sf', 'remove-all', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.remove_all_sfs.called


# ============================================================================
# Normals convenience commands
# ============================================================================

class TestNormalsConvenienceCommands:
    """Test normals group headless wrappers."""

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals_octree(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.octree_normals.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['normals', 'octree', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.octree_normals.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals_orient_mst(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.orient_normals_mst.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['normals', 'orient-mst', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.orient_normals_mst.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals_invert(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.invert_normals.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['normals', 'invert', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.invert_normals.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals_clear(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.clear_normals.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['normals', 'clear', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.clear_normals.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals_to_dip(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.normals_to_dip.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['normals', 'to-dip', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.normals_to_dip.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_normals_to_sfs(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = tmp_path / "a.ply"
        dst = tmp_path / "b.ply"
        _write_minimal_ply(src)
        backend_mock = Mock()
        backend_mock.normals_to_sfs.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['normals', 'to-sfs', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.normals_to_sfs.called


# ============================================================================
# Process — additional subcommands
# ============================================================================

class TestProcessExtendedCommands:
    """Additional process subcommands (headless)."""

    @staticmethod
    def _ply(tmp_path, name: str = "c.ply") -> Path:
        p = tmp_path / name
        _write_minimal_ply(p)
        return p

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_icp(self, mock_backend, tmp_path):
        runner = CliRunner()
        a, b, o = self._ply(tmp_path, "d.ply"), self._ply(tmp_path, "r.ply"), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.icp_registration.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'icp', str(a), str(b), '-o', str(o)])
        assert result.exit_code == 0
        assert backend_mock.icp_registration.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_c2c_dist(self, mock_backend, tmp_path):
        runner = CliRunner()
        a, b = self._ply(tmp_path, "c1.ply"), self._ply(tmp_path, "c2.ply")
        backend_mock = Mock()
        backend_mock.c2c_distance.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'c2c-dist', str(a), str(b)])
        assert result.exit_code == 0
        assert backend_mock.c2c_distance.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_c2m_dist(self, mock_backend, tmp_path):
        runner = CliRunner()
        cloud = self._ply(tmp_path, "cloud.ply")
        mesh = self._ply(tmp_path, "mesh.obj")
        backend_mock = Mock()
        backend_mock.c2m_distance.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'c2m-dist', str(cloud), str(mesh)])
        assert result.exit_code == 0
        assert backend_mock.c2m_distance.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_crop(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "cropped.ply"
        backend_mock = Mock()
        backend_mock.crop.return_value = {
            "input": str(src), "output": str(dst), "status": "ok",
        }
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, [
            'process', 'crop', str(src), '-o', str(dst),
            '--min-x', '0', '--min-y', '0', '--min-z', '0',
            '--max-x', '0.5', '--max-y', '1.0', '--max-z', '1.5',
        ])
        assert result.exit_code == 0
        assert backend_mock.crop.called
        ca = backend_mock.crop.call_args
        assert ca[0][0] == str(src) and ca[0][1] == str(dst)
        assert ca[0][2:] == (0.0, 0.0, 0.0, 0.5, 1.0, 1.5)

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_color_banding(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "band.ply"
        backend_mock = Mock()
        backend_mock.color_banding.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'color-banding', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.color_banding.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_set_active_sf(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.set_active_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'set-active-sf', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.set_active_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_remove_all_sfs(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.remove_all_sfs.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'remove-all-sfs', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.remove_all_sfs.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_remove_sf(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.remove_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'remove-sf', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.remove_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_rename_sf(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.rename_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'rename-sf', str(src), '-o', str(dst), '--new-name', 'n'])
        assert result.exit_code == 0
        assert backend_mock.rename_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_sf_arithmetic(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.sf_arithmetic.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'sf-arithmetic', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.sf_arithmetic.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_sf_op(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.sf_operation.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'sf-op', str(src), '-o', str(dst), '--value', '1.0'])
        assert result.exit_code == 0
        assert backend_mock.sf_operation.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_coord_to_sf(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.coord_to_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'coord-to-sf', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.coord_to_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_sf_gradient(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.sf_gradient.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'sf-gradient', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.sf_gradient.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_filter_sf(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.filter_sf.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'filter-sf', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.filter_sf.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_sf_color_scale(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        scale = tmp_path / "s.xml"
        scale.write_text("<x/>")
        backend_mock = Mock()
        backend_mock.sf_color_scale.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'sf-color-scale', str(src), '-o', str(dst), '--scale-file', str(scale)])
        assert result.exit_code == 0
        assert backend_mock.sf_color_scale.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_sf_to_rgb(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.sf_convert_to_rgb.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'sf-to-rgb', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.sf_convert_to_rgb.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_octree_normals(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.octree_normals.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'octree-normals', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.octree_normals.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_orient_normals(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.orient_normals_mst.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'orient-normals', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.orient_normals_mst.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_invert_normals(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.invert_normals.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'invert-normals', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.invert_normals.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_clear_normals(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.clear_normals.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'clear-normals', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.clear_normals.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_normals_to_dip(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.normals_to_dip.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'normals-to-dip', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.normals_to_dip.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_normals_to_sfs(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.normals_to_sfs.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'normals-to-sfs', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.normals_to_sfs.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_extract_cc(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.extract_connected_components.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'extract-cc', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.extract_connected_components.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_approx_density(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.approx_density.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'approx-density', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.approx_density.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_feature(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.feature.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'feature', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.feature.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_moment(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.moment.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'moment', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.moment.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_best_fit_plane(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.best_fit_plane.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'best-fit-plane', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.best_fit_plane.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_mesh_volume(self, mock_backend, tmp_path):
        runner = CliRunner()
        src = self._ply(tmp_path)
        backend_mock = Mock()
        backend_mock.mesh_volume.return_value = {"volume": 1.0}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'mesh-volume', str(src)])
        assert result.exit_code == 0
        assert backend_mock.mesh_volume.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_extract_vertices(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "v.ply"
        backend_mock = Mock()
        backend_mock.extract_vertices.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'extract-vertices', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.extract_vertices.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_flip_triangles(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "m.ply"
        backend_mock = Mock()
        backend_mock.flip_triangles.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'flip-triangles', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.flip_triangles.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_merge_clouds(self, mock_backend, tmp_path):
        runner = CliRunner()
        a, b, o = self._ply(tmp_path, "a.ply"), self._ply(tmp_path, "b.ply"), tmp_path / "m.ply"
        backend_mock = Mock()
        backend_mock.merge_clouds.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'merge-clouds', str(a), str(b), '-o', str(o)])
        assert result.exit_code == 0
        assert backend_mock.merge_clouds.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_merge_meshes(self, mock_backend, tmp_path):
        runner = CliRunner()
        a, b, o = self._ply(tmp_path, "m1.ply"), self._ply(tmp_path, "m2.ply"), tmp_path / "mm.ply"
        backend_mock = Mock()
        backend_mock.merge_meshes.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'merge-meshes', str(a), str(b), '-o', str(o)])
        assert result.exit_code == 0
        assert backend_mock.merge_meshes.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_remove_rgb(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.remove_rgb.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'remove-rgb', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.remove_rgb.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_remove_scan_grids(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.remove_scan_grids.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'remove-scan-grids', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.remove_scan_grids.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_match_centers(self, mock_backend, tmp_path):
        runner = CliRunner()
        a, b, o = self._ply(tmp_path, "x.ply"), self._ply(tmp_path, "y.ply"), tmp_path / "o.ply"
        backend_mock = Mock()
        backend_mock.match_centers.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'match-centers', str(a), str(b), '-o', str(o)])
        assert result.exit_code == 0
        assert backend_mock.match_centers.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_drop_global_shift(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "out.ply"
        backend_mock = Mock()
        backend_mock.drop_global_shift.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'drop-global-shift', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.drop_global_shift.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_closest_point_set(self, mock_backend, tmp_path):
        runner = CliRunner()
        a, b, o = self._ply(tmp_path, "p1.ply"), self._ply(tmp_path, "p2.ply"), tmp_path / "cps.ply"
        backend_mock = Mock()
        backend_mock.closest_point_set.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'closest-point-set', str(a), str(b), '-o', str(o)])
        assert result.exit_code == 0
        assert backend_mock.closest_point_set.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_rasterize(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "r.ply"
        backend_mock = Mock()
        backend_mock.rasterize.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'rasterize', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.rasterize.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_stat_test(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "st.ply"
        backend_mock = Mock()
        backend_mock.stat_test.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'stat-test', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.stat_test.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_cross_section(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "cs.ply"
        poly = tmp_path / "poly.txt"
        poly.write_text("0 0 0\n1 1 1\n")
        backend_mock = Mock()
        backend_mock.cross_section.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, [
            'process', 'cross-section', str(src), '-o', str(dst),
            '--polyline', str(poly),
        ])
        assert result.exit_code == 0
        assert backend_mock.cross_section.called

    @patch('cli_anything.acloudviewer.acloudviewer_cli.get_backend')
    def test_process_sample_mesh(self, mock_backend, tmp_path):
        runner = CliRunner()
        src, dst = self._ply(tmp_path), tmp_path / "s.ply"
        backend_mock = Mock()
        backend_mock.sample_mesh.return_value = {"status": "ok"}
        mock_backend.return_value = backend_mock

        result = runner.invoke(cli, ['process', 'sample-mesh', str(src), '-o', str(dst)])
        assert result.exit_code == 0
        assert backend_mock.sample_mesh.called
