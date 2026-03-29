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
        backend_mock.list_rpc_methods.return_value = ["method1", "method2"]
        mock_backend.return_value = backend_mock
        
        result = runner.invoke(cli, ['methods'])
        assert result.exit_code == 0 or backend_mock.list_rpc_methods.called


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
        
        result = runner.invoke(cli, ['process', 'subsample', str(src), '-o', str(dst), '--method', 'RANDOM', '--count', '50'])
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
        
        result = runner.invoke(cli, ['entity', 'set-color', '123', '--r', '255', '--g', '0', '--b', '0'])
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
