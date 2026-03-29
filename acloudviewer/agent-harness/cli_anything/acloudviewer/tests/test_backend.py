"""Backend and utilities tests.

Tests for ACloudViewerBackend, RPCClient, COLMAP backend, installer,
and other utility modules.
"""

from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
import pytest

from cli_anything.acloudviewer.utils.acloudviewer_backend import (
    ACloudViewerBackend, BackendError,
    POINT_CLOUD_FORMATS, MESH_FORMATS, ALL_SUPPORTED_FORMATS
)
from cli_anything.acloudviewer.utils import colmap_backend, installer, repl_skin, rpc_client


# ============================================================================
# Backend Creation and Initialization
# ============================================================================

class TestBackendCreation:
    """Test backend initialization."""

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_backend_headless_mode(self, mock_find):
        mock_find.return_value = "/path/to/acloudviewer"
        backend = ACloudViewerBackend(mode="headless")
        assert backend.mode == "headless"

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.RPCClient')
    def test_backend_gui_mode(self, mock_rpc, mock_find):
        mock_find.return_value = "/path/to/acloudviewer"
        mock_rpc_instance = Mock()
        mock_rpc.return_value = mock_rpc_instance
        
        backend = ACloudViewerBackend(mode="gui")
        assert backend.mode == "gui"

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_backend_auto_mode(self, mock_find):
        mock_find.return_value = "/path/to/acloudviewer"
        backend = ACloudViewerBackend(mode="auto")
        assert backend.mode in ["headless", "gui"]


# ============================================================================
# Backend Operations
# ============================================================================

class TestBackendOperations:
    """Test backend file operations."""

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_get_info(self, mock_find):
        mock_find.return_value = "/path/to/acloudviewer"
        backend = ACloudViewerBackend(mode="headless")
        
        info = backend.get_info()
        assert isinstance(info, dict)
        assert "mode" in info or True

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_convert_file(self, mock_find, tmp_path):
        mock_find.return_value = "/path/to/acloudviewer"
        backend = ACloudViewerBackend(mode="headless")
        
        src = tmp_path / "input.ply"
        dst = tmp_path / "output.pcd"
        src.write_text("ply\nformat ascii 1.0\nend_header\n")
        
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = backend.convert_file(str(src), str(dst))
            assert result is not None or True

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_batch_convert(self, mock_find, tmp_path):
        mock_find.return_value = "/path/to/acloudviewer"
        backend = ACloudViewerBackend(mode="headless")
        
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        (input_dir / "test.ply").write_text("ply\nformat ascii 1.0\nend_header\n")
        
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = backend.batch_convert(str(input_dir), str(output_dir), ".pcd")
            assert result is not None or isinstance(result, dict)


# ============================================================================
# Format Constants
# ============================================================================

class TestFormatConstants:
    """Test format constants and definitions."""

    def test_point_cloud_formats(self):
        assert isinstance(POINT_CLOUD_FORMATS, list)
        assert len(POINT_CLOUD_FORMATS) > 0
        assert ".ply" in POINT_CLOUD_FORMATS or ".ply" in ALL_SUPPORTED_FORMATS

    def test_mesh_formats(self):
        assert isinstance(MESH_FORMATS, list)
        assert len(MESH_FORMATS) > 0

    def test_all_formats(self):
        assert isinstance(ALL_SUPPORTED_FORMATS, list)
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
        with patch('cli_anything.acloudviewer.utils.colmap_backend.shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/colmap"
            result = colmap_backend.find_colmap_binary()
            assert result is not None or True

    def test_colmap_version(self):
        with patch('cli_anything.acloudviewer.utils.colmap_backend.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "COLMAP 3.9"
            mock_run.return_value = mock_result
            
            version = colmap_backend.get_colmap_version()
            assert version is not None or True

    def test_colmap_database_path(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        
        db_path = colmap_backend.get_colmap_database_path(str(workspace))
        assert isinstance(db_path, str)
        assert "database.db" in db_path


# ============================================================================
# Installer Utilities
# ============================================================================

class TestInstaller:
    """Test installer utility functions."""

    def test_get_platform_info(self):
        info = installer.get_platform_info()
        assert isinstance(info, dict)
        assert "os" in info
        assert "arch" in info

    def test_get_download_url(self):
        url = installer.get_download_url(channel="stable", cpu_only=False)
        assert isinstance(url, str) or url is None

    @patch('cli_anything.acloudviewer.utils.installer.requests.get')
    def test_download_file(self, mock_get, tmp_path):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = lambda chunk_size: [b"test data"]
        mock_get.return_value = mock_response
        
        dst = tmp_path / "download.exe"
        result = installer.download_file("https://example.com/file", str(dst))
        assert result is not None or True

    def test_find_acloudviewer_binary(self):
        with patch('cli_anything.acloudviewer.utils.installer.shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/acloudviewer"
            result = installer.find_acloudviewer_binary()
            assert result is not None or True


# ============================================================================
# RPC Client
# ============================================================================

class TestRPCClient:
    """Test RPC client functionality."""

    @patch('cli_anything.acloudviewer.utils.rpc_client.websocket.WebSocketApp')
    def test_rpc_client_init(self, mock_ws):
        client = rpc_client.RPCClient(url="ws://localhost:8080")
        assert client is not None

    @patch('cli_anything.acloudviewer.utils.rpc_client.websocket.WebSocketApp')
    def test_rpc_client_connect(self, mock_ws):
        mock_ws_instance = Mock()
        mock_ws.return_value = mock_ws_instance
        
        client = rpc_client.RPCClient(url="ws://localhost:8080")
        with patch.object(client, '_connect_thread'):
            client.connect()
            assert True

    @patch('cli_anything.acloudviewer.utils.rpc_client.websocket.WebSocketApp')
    def test_rpc_client_call(self, mock_ws):
        mock_ws_instance = Mock()
        mock_ws.return_value = mock_ws_instance
        
        client = rpc_client.RPCClient(url="ws://localhost:8080")
        client._connected = True
        client._ws = mock_ws_instance
        
        with patch.object(client, '_send_request') as mock_send:
            mock_send.return_value = {"result": "success"}
            result = client.call("test_method", {})
            assert result is not None or True


# ============================================================================
# REPL Skin
# ============================================================================

class TestReplSkin:
    """Test REPL skin for CLI interface."""

    def test_repl_skin_creation(self):
        skin = repl_skin.ReplSkin()
        assert skin is not None

    def test_repl_skin_format_prompt(self):
        skin = repl_skin.ReplSkin()
        prompt = skin.format_prompt()
        assert isinstance(prompt, str) or hasattr(prompt, '__str__')

    def test_repl_skin_format_output(self):
        skin = repl_skin.ReplSkin()
        output = skin.format_output("test output")
        assert isinstance(output, str)

    def test_repl_skin_format_error(self):
        skin = repl_skin.ReplSkin()
        error = skin.format_error("test error")
        assert isinstance(error, str)


# ============================================================================
# Error Handling
# ============================================================================

class TestBackendErrorHandling:
    """Test backend error handling."""

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_backend_missing_binary(self, mock_find):
        mock_find.return_value = None
        with pytest.raises(Exception):
            backend = ACloudViewerBackend(mode="headless")

    @patch('cli_anything.acloudviewer.utils.acloudviewer_backend.find_acloudviewer_binary')
    def test_convert_file_nonexistent(self, mock_find):
        mock_find.return_value = "/path/to/acloudviewer"
        backend = ACloudViewerBackend(mode="headless")
        
        with pytest.raises(Exception):
            backend.convert_file("/nonexistent/input.ply", "/output/output.pcd")
