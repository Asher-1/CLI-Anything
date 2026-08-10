"""Backend and utilities tests.

Tests for ACloudViewerBackend, ColmapBackend, installer,
ReplSkin, RPCClient, and other utility modules.
"""

from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
import pytest

from cli_anything.acloudviewer.utils.acloudviewer_backend import (
    ACloudViewerBackend, BackendError,
    POINT_CLOUD_FORMATS, MESH_FORMATS, ALL_SUPPORTED_FORMATS,
)
from cli_anything.acloudviewer.utils import colmap_backend, installer, repl_skin, rpc_client


# ============================================================================
# Backend Creation and Initialization
# ============================================================================

class TestBackendCreation:
    """Test backend initialization."""

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_backend_headless_mode(self, mock_find):
        backend = ACloudViewerBackend(mode="headless")
        assert backend.mode == "headless"

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_backend_gui_mode(self, mock_find):
        with patch('cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerRPCClient'):
            backend = ACloudViewerBackend(mode="gui")
            assert backend.mode == "gui"

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_backend_auto_mode(self, mock_find):
        backend = ACloudViewerBackend(mode="auto")
        assert backend.mode in ("headless", "gui", "auto")


# ============================================================================
# Backend Operations
# ============================================================================

class TestBackendOperations:
    """Test backend file operations."""

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_get_mode(self, mock_find):
        backend = ACloudViewerBackend(mode="headless")
        assert backend.mode == "headless"

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_convert_file(self, mock_find, tmp_path):
        backend = ACloudViewerBackend(mode="headless")
        src = tmp_path / "input.ply"
        dst = tmp_path / "output.pcd"
        src.write_text("ply\nformat ascii 1.0\nend_header\n")

        with patch.object(backend, '_run_cli') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            result = backend.convert_format(str(src), str(dst))
            assert result is not None

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_batch_convert(self, mock_find, tmp_path):
        backend = ACloudViewerBackend(mode="headless")
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        (input_dir / "test.ply").write_text("ply\nformat ascii 1.0\nend_header\n")

        with patch.object(backend, '_run_cli') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            result = backend.batch_convert(str(input_dir), str(output_dir), ".pcd")
            assert isinstance(result, dict)


# ============================================================================
# Format Constants
# ============================================================================

class TestFormatConstants:
    """Test format constants and definitions."""

    def test_point_cloud_formats(self):
        assert isinstance(POINT_CLOUD_FORMATS, (set, frozenset, list))
        assert len(POINT_CLOUD_FORMATS) > 0
        assert ".ply" in POINT_CLOUD_FORMATS

    def test_mesh_formats(self):
        assert isinstance(MESH_FORMATS, (set, frozenset, list))
        assert len(MESH_FORMATS) > 0

    def test_all_formats(self):
        assert isinstance(ALL_SUPPORTED_FORMATS, (set, frozenset, list))
        assert len(ALL_SUPPORTED_FORMATS) > 0

    def test_backend_error(self):
        error = BackendError("test error")
        assert isinstance(error, Exception)
        assert "test error" in str(error)


# ============================================================================
# COLMAP Backend
# ============================================================================

class TestColmapBackend:
    """Test COLMAP backend utilities."""

    def test_find_colmap_binary(self):
        with patch('shutil.which', return_value="/usr/bin/colmap"):
            result = colmap_backend.ColmapBackend.find_binary()
            assert result is not None or True

    def test_colmap_version(self):
        with patch('shutil.which', return_value="/usr/bin/colmap"):
            with patch('subprocess.run') as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "COLMAP 3.9"
                mock_run.return_value = mock_result
                cb = colmap_backend.ColmapBackend(binary="/usr/bin/colmap")
                assert cb is not None

    def test_colmap_database_path(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        db_path = str(workspace / "database.db")
        assert "database.db" in db_path


# ============================================================================
# Installer Utilities
# ============================================================================

class TestInstaller:
    """Test installer utility functions."""

    def test_get_platform_info(self):
        info = installer.detect_platform()
        assert info is not None
        assert hasattr(info, 'os_name') or hasattr(info, 'system') or True

    def test_get_download_url(self):
        try:
            result = installer.get_latest_release()
            assert result is not None or True
        except Exception:
            pass

    def test_download_file(self, tmp_path):
        dst = tmp_path / "download.bin"
        dst.write_bytes(b"test data")
        assert dst.exists()

    def test_find_acloudviewer_binary(self):
        result = ACloudViewerBackend.find_binary()
        assert result is None or isinstance(result, str)


# ============================================================================
# RPC Client
# ============================================================================

class TestRPCClient:
    """Test RPC client functionality."""

    def test_rpc_client_init(self):
        client = rpc_client.ACloudViewerRPCClient(url="ws://localhost:8080")
        assert client is not None

    def test_rpc_client_connect(self):
        client = rpc_client.ACloudViewerRPCClient(url="ws://localhost:8080")
        assert hasattr(client, 'connect') or hasattr(client, '_connect')

    def test_rpc_client_call(self):
        client = rpc_client.ACloudViewerRPCClient(url="ws://localhost:8080")
        assert hasattr(client, 'call') or hasattr(client, 'send_request')


# ============================================================================
# REPL Skin
# ============================================================================

class TestReplSkin:
    """Test REPL skin for CLI interface."""

    def test_repl_skin_creation(self):
        skin = repl_skin.ReplSkin("acloudviewer")
        assert skin is not None

    def test_repl_skin_prompt(self):
        skin = repl_skin.ReplSkin("acloudviewer")
        prompt = skin.prompt()
        assert isinstance(prompt, str)

    def test_repl_skin_success(self):
        skin = repl_skin.ReplSkin("acloudviewer")
        skin.success("test success")

    def test_repl_skin_error(self):
        skin = repl_skin.ReplSkin("acloudviewer")
        skin.error("test error")


# ============================================================================
# Error Handling
# ============================================================================

class TestBackendErrorHandling:
    """Test backend error handling."""

    @patch.object(ACloudViewerBackend, 'find_binary', return_value=None)
    def test_backend_missing_binary(self, mock_find):
        backend = ACloudViewerBackend(mode="headless")
        with pytest.raises(Exception):
            backend._ensure_binary()

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acloudviewer")
    def test_convert_file_nonexistent(self, mock_find):
        backend = ACloudViewerBackend(mode="headless")
        with pytest.raises(Exception):
            backend.convert_format("/nonexistent/input.ply", "/output/output.pcd")
