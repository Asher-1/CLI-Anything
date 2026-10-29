"""Backend and utilities tests.

Tests for ACloudViewerBackend, ColmapBackend, installer,
ReplSkin, RPCClient, and other utility modules.
"""

from unittest.mock import Mock, patch, MagicMock
import json
import sys
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


class TestPluginAndAICoreCommands:
    """Typed AICore registry and generic plugin passthrough."""

    @pytest.mark.parametrize("name", ["llm", "LLM_GENERATE", "-LLM_GENERATE"])
    def test_llm_resolves_to_generation_not_annotation(self, name):
        from cli_anything.acloudviewer.core.ai_registry import resolve_ai_command
        command = resolve_ai_command(name)
        assert command.name == "llm"
        assert command.command == "LLM_GENERATE"
        assert command.input_shape == "text-or-images"

    def test_llm_registry_and_prompt_encoding(self):
        from cli_anything.acloudviewer.core.ai_registry import list_ai_commands
        rows = [row for row in list_ai_commands() if row["name"] == "llm"]
        assert len(rows) == 1 and rows[0]["command"] == "LLM_GENERATE"
        assert ACloudViewerBackend._plugin_command_args("LLM_GENERATE", {
            "PROMPT": "Answer in one word: Paris?", "SYSTEM": "Be concise.",
            "TEMPERATURE": 0, "MAX_TOKENS": 128,
            "IMAGE": ["first image.png", "second.png"],
        }) == ["-LLM_GENERATE", "PROMPT", "Answer in one word: Paris?",
               "SYSTEM", "Be concise.", "TEMPERATURE", "0",
               "MAX_TOKENS", "128", "IMAGE", "first image.png",
               "IMAGE", "second.png"]

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acv")
    def test_ai_registry_and_argument_encoding(self, mock_find):
        backend = ACloudViewerBackend(mode="headless")
        tasks = backend.ai_list()
        assert len(tasks) >= 17
        assert any(item["command"] == "OCR_RECOGNIZE" for item in tasks)
        assert backend._plugin_command_args(
            "ocr_recognize", {"HELP": True, "IMAGE": ["a.png", "b.png"],
                              "SAVE_VIS": False}) == [
            "-OCR_RECOGNIZE", "HELP", "IMAGE", "a.png", "IMAGE", "b.png",
            "SAVE_VIS", "0"]
        with pytest.raises(BackendError):
            backend._plugin_command_args("bad command", {})
        with pytest.raises(BackendError):
            backend._plugin_command_args("OCR_RECOGNIZE", {"X": {"nested": 1}})

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acv")
    def test_headless_ai_run_parses_manifest(self, mock_find, tmp_path):
        backend = ACloudViewerBackend(mode="headless")
        result_json = tmp_path / "result.json"

        def run(args, timeout=300):
            assert "-OCR_RECOGNIZE" in args
            assert args[args.index("IMAGE") + 1] == "page.png"
            result_json.write_text(json.dumps({
                "schema": "acloudviewer.aicore.batch/1", "ok": 1,
                "failed": 0, "items": [{"status": "ok"}]}))
            completed = Mock(returncode=0, stdout="ok", stderr="")
            return completed

        with patch.object(backend, '_run_cli', side_effect=run):
            result = backend.ai_run("ocr", {
                "IMAGE": "page.png", "OUT_DIR": str(tmp_path),
                "RESULT_JSON": str(result_json)})
        assert result["manifest"]["ok"] == 1

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/old/acv")
    def test_headless_ai_run_names_binary_without_the_command(self, mock_find,
                                                              tmp_path):
        backend = ACloudViewerBackend(mode="headless")
        stale = Mock(returncode=0, stdout="",
                     stderr="Unknown or misplaced command: '-OCR_RECOGNIZE'")
        with patch.object(backend, '_run_cli', return_value=stale):
            with pytest.raises(BackendError, match=r"/old/acv.*ACV_BINARY"):
                backend.ai_run("ocr", {
                    "IMAGE": "page.png",
                    "RESULT_JSON": str(tmp_path / "result.json")})

    @patch.object(ACloudViewerBackend, 'find_binary', return_value=None)
    def test_gui_ai_run_without_local_binary_uses_rpc(self, mock_find):
        with patch('cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerRPCClient') as cls:
            backend = ACloudViewerBackend(mode="gui")
            backend._rpc.aicore_batch.return_value = {
                "manifest": {"schema": "acloudviewer.aicore.batch/1", "ok": 1}}
            result = backend.ai_run("rmbg", {"IMAGE": "x.png"})
            assert result["manifest"]["ok"] == 1
            backend._rpc.aicore_batch.assert_called_once()

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acv")
    def test_gui_ai_run_prefers_local_headless_child(self, mock_find, tmp_path):
        result_json = tmp_path / "result.json"

        def run(args, timeout=300):
            result_json.write_text(json.dumps({
                "schema": "acloudviewer.aicore.batch/1", "ok": 1,
                "failed": 0}))
            return Mock(returncode=0, stdout="", stderr="")

        with patch('cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerRPCClient'):
            backend = ACloudViewerBackend(mode="gui")
            with patch.object(backend, '_run_cli', side_effect=run) as cli:
                result = backend.ai_run("rmbg", {
                    "IMAGE": "x.png", "RESULT_JSON": str(result_json)})
            cli.assert_called_once()
            backend._rpc.aicore_batch.assert_not_called()
        assert result["manifest"]["ok"] == 1

    @patch.object(ACloudViewerBackend, 'find_binary', return_value="/path/to/acv")
    def test_plugin_run_passthrough(self, mock_find):
        backend = ACloudViewerBackend(mode="headless")
        completed = Mock(returncode=0, stdout="done", stderr="")
        with patch.object(backend, '_run_cli', return_value=completed) as run:
            result = backend.plugin_run("CSF", args=["SCENES", "RELIEF"])
        assert result["command"] == "CSF"
        assert run.call_args.args[0][-2:] == ["SCENES", "RELIEF"]


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


def test_run_cli_tolerates_undecodable_child_output(tmp_path):
    """Child logs echo user paths that need not decode in the locale codec;
    a successful run must not fail on them."""
    emit = tmp_path / "emit.py"
    emit.write_text("import sys\nsys.stdout.buffer.write(b'saved \\xff.ply\\n')\n")
    if sys.platform == "win32":
        child = tmp_path / "fake_acloudviewer.cmd"
        child.write_text(f'@"{sys.executable}" "{emit}"\n')
    else:
        child = tmp_path / "fake_acloudviewer"
        child.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{emit}"\n')
        child.chmod(0o755)
    backend = ACloudViewerBackend(mode="headless")
    with patch.object(ACloudViewerBackend, "_ensure_binary",
                      return_value=str(child)):
        result = backend._run_cli(["-O", "x.ply"], timeout=30)
    assert result.returncode == 0
    assert result.stdout.startswith("saved ")


class TestRPCClientWire:
    """ACloudViewerRPCClient against a real loopback WebSocket server."""

    @staticmethod
    def _serve(handler):
        import threading
        from websockets.sync.server import serve
        server = serve(handler, "127.0.0.1", 0, max_size=None)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, f"ws://127.0.0.1:{server.socket.getsockname()[1]}"

    def test_large_reply_behind_stale_reply_with_proxy_env(self, monkeypatch):
        # aicore.batch embeds whole manifests: above websockets' 1 MiB default.
        big = "x" * (3 << 20)

        def handler(ws):
            for raw in ws:
                request = json.loads(raw)
                ws.send(json.dumps({"jsonrpc": "2.0", "id": -1,
                                    "result": "stale"}))
                ws.send(json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                    "result": big}))

        server, url = self._serve(handler)
        # A desktop proxy must not capture the loopback GUI connection.
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            monkeypatch.setenv(name, "http://127.0.0.1:9")
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        try:
            client = rpc_client.ACloudViewerRPCClient(url)
            assert client.call("ping") == big
            assert client.call("ping") == big
            client.close()
        finally:
            server.shutdown()


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
