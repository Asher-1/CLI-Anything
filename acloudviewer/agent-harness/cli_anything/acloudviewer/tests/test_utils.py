"""Unit tests for utils modules — mocked external deps, no binary needed."""

import io
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ── RPC Client Tests ─────────────────────────────────────────────

class TestRPCClientCall:
    """Test call() request/response protocol without a real server."""

    def _make_client(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        c = ACloudViewerRPCClient("ws://fake:9999")
        c._ws = MagicMock()
        return c

    def test_call_sends_jsonrpc_request(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"})

        c.call("ping")

        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["jsonrpc"] == "2.0"
        assert sent["method"] == "ping"
        assert "id" in sent
        assert sent["params"] == {}

    def test_call_sends_params(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})

        c.call("open", {"filename": "/tmp/test.ply", "silent": True})

        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["params"]["filename"] == "/tmp/test.ply"
        assert sent["params"]["silent"] is True

    def test_call_returns_result(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "result": {"count": 42}
        })

        result = c.call("scene.list")
        assert result == {"count": 42}

    def test_call_raises_on_error(self):
        from cli_anything.acloudviewer.utils.rpc_client import RPCError
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32601, "message": "Method not found"}
        })

        with pytest.raises(RPCError) as exc_info:
            c.call("nonexistent")
        assert exc_info.value.code == -32601
        assert "Method not found" in exc_info.value.message

    def test_call_raises_on_error_with_data(self):
        from cli_anything.acloudviewer.utils.rpc_client import RPCError
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "error": {
                "code": 2, "message": "Entity not found",
                "data": {"entity_id": 42, "hint": "Use scene.list"}
            }
        })

        with pytest.raises(RPCError) as exc_info:
            c.call("scene.info", {"entity_id": 42})
        err = exc_info.value
        assert err.code == 2
        assert err.data == {"entity_id": 42, "hint": "Use scene.list"}
        assert "entity_id" in str(err)

    def test_call_auto_connects(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        c = ACloudViewerRPCClient("ws://fake:9999")
        assert c._ws is None

        with patch.object(c, 'connect') as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError
            with pytest.raises(ConnectionRefusedError):
                c.call("ping")
            mock_connect.assert_called_once()


class TestRPCClientConvenience:
    """Test convenience wrappers build correct RPC calls."""

    def _make_client(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        c = ACloudViewerRPCClient()
        c._ws = MagicMock()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "pong"})
        return c

    def test_ping(self):
        c = self._make_client()
        result = c.ping()
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "ping"
        assert result == "pong"

    def test_open_file(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"loaded": 1}})
        c.open_file("/tmp/test.ply")
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "open"
        assert sent["params"]["filename"] == "/tmp/test.ply"
        assert sent["params"]["silent"] is True

    def test_open_file_not_silent(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
        c.open_file("/tmp/test.ply", silent=False)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert "silent" not in sent["params"]

    def test_clear(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": 0})
        c.clear()
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "clear"

    def test_scene_list(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": [{"id": 1}]})
        result = c.scene_list(recursive=False)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "scene.list"
        assert sent["params"]["recursive"] is False

    def test_set_view(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": None})
        c.set_view("top")
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "view.setOrientation"
        assert sent["params"]["orientation"] == "top"

    def test_file_convert(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}})
        c.file_convert("/in.ply", "/out.pcd")
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "file.convert"
        assert sent["params"]["input"] == "/in.ply"
        assert sent["params"]["output"] == "/out.pcd"

    def test_export_entity(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
        c.export_entity(42, "/tmp/out.ply")
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "export"
        assert sent["params"]["entity_id"] == 42
        assert sent["params"]["filename"] == "/tmp/out.ply"

    def test_zoom_fit(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": None})
        c.zoom_fit()
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "view.zoomFit"

    def test_list_methods(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "result": [{"method": "ping"}]
        })
        result = c.list_methods()
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "methods.list"

    def test_scene_info(self):
        c = self._make_client()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"name": "cloud"}})
        result = c.scene_info(7)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "scene.info"
        assert sent["params"]["entity_id"] == 7


class TestRPCClientNewWrappers:
    """Test convenience wrappers for newly added RPC methods."""

    def _make_client(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        c = ACloudViewerRPCClient()
        c._ws = MagicMock()
        c._ws.recv.return_value = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
        return c

    def test_cloud_set_active_sf(self):
        c = self._make_client()
        c.cloud_set_active_sf(10, field_index=2)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.setActiveSf"
        assert sent["params"]["entity_id"] == 10
        assert sent["params"]["field_index"] == 2

    def test_cloud_remove_sf(self):
        c = self._make_client()
        c.cloud_remove_sf(10, field_name="height")
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.removeSf"
        assert sent["params"]["entity_id"] == 10
        assert sent["params"]["field_name"] == "height"

    def test_cloud_remove_all_sfs(self):
        c = self._make_client()
        c.cloud_remove_all_sfs(10)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.removeAllSfs"
        assert sent["params"]["entity_id"] == 10

    def test_cloud_rename_sf(self):
        c = self._make_client()
        c.cloud_rename_sf(10, "new_sf", field_index=0)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.renameSf"
        assert sent["params"]["new_name"] == "new_sf"

    def test_cloud_filter_sf(self):
        c = self._make_client()
        c.cloud_filter_sf(10, min_val=0.0, max_val=1.0)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.filterSf"
        assert sent["params"]["min"] == 0.0
        assert sent["params"]["max"] == 1.0

    def test_cloud_coord_to_sf(self):
        c = self._make_client()
        c.cloud_coord_to_sf(10, dimension="z")
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.coordToSF"
        assert sent["params"]["dimension"] == "z"

    def test_cloud_remove_rgb(self):
        c = self._make_client()
        c.cloud_remove_rgb(10)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.removeRgb"

    def test_cloud_remove_normals(self):
        c = self._make_client()
        c.cloud_remove_normals(10)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.removeNormals"

    def test_cloud_invert_normals(self):
        c = self._make_client()
        c.cloud_invert_normals(10)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.invertNormals"

    def test_cloud_merge(self):
        c = self._make_client()
        c.cloud_merge([1, 2, 3])
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "cloud.merge"
        assert sent["params"]["entity_ids"] == [1, 2, 3]

    def test_mesh_extract_vertices(self):
        c = self._make_client()
        c.mesh_extract_vertices(20)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "mesh.extractVertices"

    def test_mesh_flip_triangles(self):
        c = self._make_client()
        c.mesh_flip_triangles(20)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "mesh.flipTriangles"

    def test_mesh_volume(self):
        c = self._make_client()
        c.mesh_volume(20)
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "mesh.volume"

    def test_mesh_merge(self):
        c = self._make_client()
        c.mesh_merge([20, 21])
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "mesh.merge"
        assert sent["params"]["entity_ids"] == [20, 21]

    def test_colmap_run(self):
        c = self._make_client()
        c.colmap_run("feature_extractor",
                     kwargs_={"database_path": "/db.db", "image_path": "/imgs/"})
        sent = json.loads(c._ws.send.call_args[0][0])
        assert sent["method"] == "colmap.run"
        assert sent["params"]["command"] == "feature_extractor"
        assert sent["params"]["kwargs"]["database_path"] == "/db.db"


class TestRPCContextManager:
    def test_enter_exit(self):
        from cli_anything.acloudviewer.utils.rpc_client import ACloudViewerRPCClient
        c = ACloudViewerRPCClient()
        with patch.object(c, 'connect') as mock_conn, \
             patch.object(c, 'close') as mock_close:
            with c as client:
                assert client is c
                mock_conn.assert_called_once()
            mock_close.assert_called_once()


# ── ACloudViewerBackend Tests ────────────────────────────────────

class TestBackendOpenFile:
    def test_headless_open_existing(self, tmp_path):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        f = tmp_path / "test.ply"
        f.write_text("ply\n")
        backend = ACloudViewerBackend(mode="headless")
        result = backend.open_file(str(f))
        assert result["mode"] == "headless"
        assert result["status"] == "loaded"

    def test_headless_open_missing_raises(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            ACloudViewerBackend, BackendError,
        )
        backend = ACloudViewerBackend(mode="headless")
        with pytest.raises(BackendError, match="File not found"):
            backend.open_file("/nonexistent/file.ply")

    def test_gui_mode_delegates_to_rpc(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        backend = ACloudViewerBackend.__new__(ACloudViewerBackend)
        backend._mode = "gui"
        backend._binary = None
        backend._rpc = MagicMock()
        backend._rpc.open_file.return_value = {"loaded": 1}

        result = backend.open_file("/tmp/test.ply")
        backend._rpc.open_file.assert_called_once_with("/tmp/test.ply", silent=True)


class TestBackendExportFile:
    def test_headless_raises(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            ACloudViewerBackend, BackendError,
        )
        backend = ACloudViewerBackend(mode="headless")
        with pytest.raises(BackendError, match="GUI mode"):
            backend.export_file(1, "/tmp/out.ply")

    def test_gui_delegates(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        backend = ACloudViewerBackend.__new__(ACloudViewerBackend)
        backend._mode = "gui"
        backend._binary = None
        backend._rpc = MagicMock()
        backend._rpc.export_entity.return_value = {"status": "ok"}

        backend.export_file(42, "/tmp/out.ply")
        backend._rpc.export_entity.assert_called_once_with(42, "/tmp/out.ply")


class TestBackendSceneOps:
    def _headless_backend(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        return ACloudViewerBackend(mode="headless")

    def test_scene_list_headless_raises(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError, match="GUI mode"):
            self._headless_backend().scene_list()

    def test_scene_info_headless_raises(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError, match="GUI mode"):
            self._headless_backend().scene_info(1)

    def test_scene_remove_headless_raises(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError, match="GUI mode"):
            self._headless_backend().scene_remove(1)


class TestBackendGUIOnly:
    """GUI-only methods should raise BackendError in headless mode."""

    def _headless_backend(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        return ACloudViewerBackend(mode="headless")

    def test_screenshot_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().screenshot_gui("/tmp/shot.png")

    def test_get_camera_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().get_camera()

    def test_entity_rename_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().entity_rename(1, "new_name")

    def test_cloud_paint_uniform_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_paint_uniform_gui(1, 255, 0, 0)

    def test_cloud_paint_by_height_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_paint_by_height_gui(1)

    def test_cloud_paint_by_sf_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_paint_by_scalar_field_gui(1)

    def test_cloud_set_active_sf_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_set_active_sf_gui(1, field_index=0)

    def test_cloud_remove_sf_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_remove_sf_gui(1, field_index=0)

    def test_cloud_remove_all_sfs_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_remove_all_sfs_gui(1)

    def test_cloud_rename_sf_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_rename_sf_gui(1, "new_name", field_index=0)

    def test_cloud_filter_sf_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_filter_sf_gui(1, min_val=0, max_val=1)

    def test_cloud_coord_to_sf_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_coord_to_sf_gui(1, dimension="z")

    def test_cloud_remove_rgb_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_remove_rgb_gui(1)

    def test_cloud_remove_normals_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_remove_normals_gui(1)

    def test_cloud_invert_normals_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_invert_normals_gui(1)

    def test_cloud_merge_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().cloud_merge_gui([1, 2])

    def test_mesh_extract_vertices_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().mesh_extract_vertices_gui(1)

    def test_mesh_flip_triangles_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().mesh_flip_triangles_gui(1)

    def test_mesh_volume_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().mesh_volume_gui(1)

    def test_mesh_merge_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().mesh_merge_gui([1, 2])

    def test_colmap_run_gui_headless(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        with pytest.raises(BackendError):
            self._headless_backend().colmap_run_gui("feature_extractor")


class TestBackendRunCLI:
    """Test _run_cli command construction with mocked subprocess."""

    def _backend_with_binary(self, binary="/usr/bin/ACloudViewer"):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = binary
        b._rpc = None
        return b

    @patch("subprocess.run")
    def test_cli_prefixes_silent(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend_with_binary()
        b._run_cli(["-O", "test.ply", "-SAVE_CLOUDS"])

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/ACloudViewer"
        assert cmd[1] == "-SILENT"
        assert "-O" in cmd
        assert "test.ply" in cmd

    @patch("subprocess.run")
    def test_cli_raises_on_real_error(self, mock_run):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: file not found")
        b = self._backend_with_binary()
        with pytest.raises(BackendError, match="CLI failed"):
            b._run_cli(["-O", "missing.ply"])

    @patch("subprocess.run")
    def test_cli_ignores_non_error_exit(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="Warning: something", stderr="")
        b = self._backend_with_binary()
        result = b._run_cli(["-O", "test.ply"])
        assert result.returncode == 1

    def test_ensure_binary_raises_when_missing(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            ACloudViewerBackend, BackendError,
        )
        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._binary = None
        with patch.object(ACloudViewerBackend, "find_binary", return_value=None):
            with pytest.raises(BackendError, match="binary not found"):
                b._ensure_binary()


class TestBackendConvertFormat:
    """Test convert_format logic with mocked binary."""

    @patch("subprocess.run")
    def test_input_not_found(self, mock_run):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import (
            ACloudViewerBackend, BackendError,
        )
        b = ACloudViewerBackend(mode="headless")
        with pytest.raises(BackendError, match="Input not found"):
            b.convert_format("/nonexistent.ply", "/out.pcd")

    @patch("subprocess.run")
    def test_cloud_to_cloud_args(self, mock_run, tmp_path):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        src = tmp_path / "in.ply"
        src.write_text("ply\n")
        dst = tmp_path / "out.pcd"

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")

        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = "/usr/bin/ACloudViewer"
        b._rpc = None

        b.convert_format(str(src), str(dst))
        cmd = mock_run.call_args[0][0]
        assert "-C_EXPORT_FMT" in cmd
        assert "PCD" in cmd
        assert "-SAVE_CLOUDS" in cmd

    @patch("subprocess.run")
    def test_convert_result_status(self, mock_run, tmp_path):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        src = tmp_path / "in.ply"
        src.write_text("ply\n")
        dst = tmp_path / "out.xyz"

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")

        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = "/usr/bin/ACloudViewer"
        b._rpc = None

        result = b.convert_format(str(src), str(dst))
        assert result["input_format"] == ".ply"
        assert result["output_format"] == ".xyz"
        assert result["status"] in ("converted", "failed")


class TestBackendBatchConvert:
    @patch("subprocess.run")
    def test_batch_creates_output_dir(self, mock_run, tmp_path):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "a.ply").write_text("ply\n")
        (in_dir / "b.ply").write_text("ply\n")
        out_dir = tmp_path / "output"

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")

        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = "/usr/bin/ACloudViewer"
        b._rpc = None

        result = b.batch_convert(str(in_dir), str(out_dir), output_format=".pcd")
        assert out_dir.exists()
        assert result["output_format"] == ".pcd"

    def test_batch_normalizes_extension(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = None
        b._rpc = None

        with tempfile.TemporaryDirectory() as tmpdir:
            result = b.batch_convert(tmpdir, tmpdir + "/out", output_format="pcd")
            assert result["output_format"] == ".pcd"


class TestBackendSupportedFormats:
    def test_static_method(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        f = ACloudViewerBackend.supported_formats()
        assert isinstance(f, dict)
        for key in ("point_cloud", "mesh", "image", "all"):
            assert key in f
            assert isinstance(f[key], list)
            assert all(ext.startswith(".") for ext in f[key])

    def test_sorted(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        f = ACloudViewerBackend.supported_formats()
        for key in f:
            assert f[key] == sorted(f[key])


class TestBackendProcessing:
    """Test processing method argument construction."""

    def _backend(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = "/usr/bin/ACloudViewer"
        b._rpc = None
        return b

    @patch("subprocess.run")
    def test_subsample_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.subsample("/in.ply", "/out.ply", method="SPATIAL", parameter=0.1)
        cmd = mock_run.call_args[0][0]
        assert "-SS" in cmd
        assert "SPATIAL" in cmd
        assert "0.1" in cmd
        assert result["method"] == "SPATIAL"

    @patch("subprocess.run")
    def test_normals_auto(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.compute_normals("/in.ply", "/out.ply")
        cmd = mock_run.call_args[0][0]
        assert "-OCTREE_NORMALS" in cmd
        assert "AUTO" in cmd

    @patch("subprocess.run")
    def test_normals_radius(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.compute_normals("/in.ply", "/out.ply", radius=0.5)
        cmd = mock_run.call_args[0][0]
        assert "-OCTREE_NORMALS" in cmd
        assert "0.5" in cmd
        assert "AUTO" not in cmd

    @patch("subprocess.run")
    def test_sor_filter_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.sor_filter("/in.ply", "/out.ply", knn=10, sigma=2.0)
        cmd = mock_run.call_args[0][0]
        assert "-SOR" in cmd
        assert "10" in cmd
        assert "2.0" in cmd
        assert result["knn"] == 10

    @patch("subprocess.run")
    def test_delaunay_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.delaunay("/in.ply", "/out.obj", max_edge_length=0.5)
        cmd = mock_run.call_args[0][0]
        assert "-DELAUNAY" in cmd
        assert "-MAX_EDGE_LENGTH" in cmd

    @patch("subprocess.run")
    def test_density_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.density("/in.ply", "/out.ply", radius=1.0)
        cmd = mock_run.call_args[0][0]
        assert "-DENSITY" in cmd
        assert "1.0" in cmd
        assert result["radius"] == 1.0

    @patch("subprocess.run")
    def test_curvature_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.curvature("/in.ply", "/out.ply", curvature_type="GAUSS", radius=0.3)
        cmd = mock_run.call_args[0][0]
        assert "-CURV" in cmd
        assert "GAUSS" in cmd
        assert "0.3" in cmd

    @patch("subprocess.run")
    def test_roughness_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.roughness("/in.ply", "/out.ply", radius=0.7)
        cmd = mock_run.call_args[0][0]
        assert "-ROUGH" in cmd
        assert "0.7" in cmd

    @patch("subprocess.run")
    def test_sample_mesh_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.sample_mesh("/in.obj", "/out.ply", points=50000)
        cmd = mock_run.call_args[0][0]
        assert "-SAMPLE_MESH" in cmd
        assert "POINTS" in cmd
        assert "50000" in cmd
        assert result["points"] == 50000

    @patch("subprocess.run")
    def test_crop_headless(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.crop("/in.ply", "/out.ply",
               min_x=-1, min_y=-1, min_z=-1, max_x=1, max_y=1, max_z=1)
        cmd = mock_run.call_args[0][0]
        assert "-CROP" in cmd
        assert "-1:-1:-1:1:1:1" in cmd

    @patch("subprocess.run")
    def test_color_banding_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.color_banding("/in.ply", "/out.ply", axis="X", frequency=5.0)
        cmd = mock_run.call_args[0][0]
        assert "-CBANDING" in cmd
        assert "X" in cmd
        assert "5.0" in cmd
        assert result["axis"] == "X"

    @patch("subprocess.run")
    def test_icp_registration_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.icp_registration("/data.ply", "/ref.ply", "/out.ply",
                                     iterations=50, overlap=80.0)
        cmd = mock_run.call_args[0][0]
        assert "-ICP" in cmd
        assert "-ITER" in cmd
        assert "50" in cmd
        assert "-OVERLAP" in cmd
        assert "80.0" in cmd

    @patch("subprocess.run")
    def test_c2c_distance_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.c2c_distance("/comp.ply", "/ref.ply", max_dist=5.0)
        cmd = mock_run.call_args[0][0]
        assert "-C2C_DIST" in cmd
        assert "-MAX_DIST" in cmd
        assert "5.0" in cmd

    @patch("subprocess.run")
    def test_c2m_distance_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.c2m_distance("/cloud.ply", "/mesh.obj", max_dist=3.0)
        cmd = mock_run.call_args[0][0]
        assert "-C2M_DIST" in cmd
        assert "-MAX_DIST" in cmd

    @patch("subprocess.run")
    def test_apply_transformation_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.apply_transformation("/in.ply", "/out.ply", "/matrix.txt")
        cmd = mock_run.call_args[0][0]
        assert "-APPLY_TRANS" in cmd
        assert "/matrix.txt" in cmd


class TestBackendSIBR:
    def _backend(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        b = ACloudViewerBackend.__new__(ACloudViewerBackend)
        b._mode = "headless"
        b._binary = "/usr/bin/ACloudViewer"
        b._rpc = None
        return b

    def test_sibr_tools_list(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import ACloudViewerBackend
        assert len(ACloudViewerBackend.SIBR_TOOLS) >= 10
        assert "prepareColmap4Sibr" in ACloudViewerBackend.SIBR_TOOLS

    def test_sibr_unknown_tool_raises(self):
        from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError
        b = self._backend()
        with pytest.raises(BackendError, match="Unknown SIBR tool"):
            b.sibr_tool("nonexistentTool")

    @patch("subprocess.run")
    def test_sibr_prepare_colmap(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.sibr_prepare_colmap("/data/set")
        cmd = mock_run.call_args[0][0]
        assert "-SIBR_TOOL" in cmd
        assert "prepareColmap4Sibr" in cmd
        assert "-path" in cmd

    @patch("subprocess.run")
    def test_sibr_texture_mesh(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.sibr_texture_mesh("/data/set")
        cmd = mock_run.call_args[0][0]
        assert "textureMesh" in cmd


# ── ColmapBackend Tests ──────────────────────────────────────────

class TestColmapRun:
    """Test _run method error handling."""

    def _backend(self, binary="/usr/bin/colmap"):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        b = ColmapBackend.__new__(ColmapBackend)
        b._binary = binary
        return b

    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="done", stderr="")
        b = self._backend()
        result = b._run(["feature_extractor", "--database_path", "/db"])
        assert result == "done"

    @patch("subprocess.run")
    def test_timeout(self, mock_run):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapError
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="colmap", timeout=7200)
        b = self._backend()
        with pytest.raises(ColmapError, match="timed out"):
            b._run(["mapper"], timeout=7200)

    @patch("subprocess.run")
    def test_signal_kill(self, mock_run):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapError
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=-9, stdout="", stderr="")
        b = self._backend()
        with pytest.raises(ColmapError, match="killed by signal"):
            b._run(["mapper"])

    @patch("subprocess.run")
    def test_error_filtering(self, mock_run):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapError
        stderr = (
            "I0324 15:00:00 something.cc:10] Info message\n"
            "W0324 15:00:01 something.cc:20] Warning message\n"
            "iter 1234: cost=0.123\n"
            "Error: actual problem here\n"
        )
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=stderr)
        b = self._backend()
        with pytest.raises(ColmapError) as exc_info:
            b._run(["mapper"])
        assert "actual problem" in str(exc_info.value)
        assert "I0324" not in str(exc_info.value)

    @patch("subprocess.run")
    def test_non_error_stderr_fallback(self, mock_run):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapError
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="W0324 something internal")
        b = self._backend()
        with pytest.raises(ColmapError):
            b._run(["mapper"])


class TestColmapBinaryDiscovery:
    def test_binary_names_platform(self):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        names = ColmapBackend._colmap_binary_names()
        assert isinstance(names, list)
        assert len(names) >= 2
        assert "colmap" in names or "colmap.exe" in names

    def test_search_dirs(self):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        dirs = ColmapBackend._colmap_search_dirs()
        assert isinstance(dirs, list)
        assert len(dirs) >= 2
        assert all(isinstance(d, Path) for d in dirs)

    def test_env_override_file(self, tmp_path):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        fake = tmp_path / "colmap"
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o755)
        with patch.dict(os.environ, {"COLMAP_PATH": str(fake)}):
            result = ColmapBackend.find_binary()
            assert result == str(fake)

    def test_env_override_dir(self, tmp_path):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        fake = tmp_path / "colmap"
        fake.write_text("#!/bin/sh\n")
        with patch.dict(os.environ, {"COLMAP_PATH": str(tmp_path)}):
            result = ColmapBackend.find_binary()
            if result:
                assert str(tmp_path) in result


class TestColmapArgConstruction:
    """Verify argument building for various COLMAP subcommands."""

    def _backend(self):
        from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend
        b = ColmapBackend.__new__(ColmapBackend)
        b._binary = "/usr/bin/colmap"
        return b

    @patch("subprocess.run")
    def test_automatic_reconstruct_args(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.automatic_reconstruct(
            str(tmp_path / "ws"), str(tmp_path / "imgs"),
            quality="high", camera_model="SIMPLE_PINHOLE",
            single_camera=True, use_gpu=False)
        cmd = mock_run.call_args[0][0]
        assert "automatic_reconstructor" in cmd
        assert "--quality" in cmd
        assert "high" in cmd
        assert "--camera_model" in cmd
        assert "SIMPLE_PINHOLE" in cmd
        assert "--single_camera" in cmd
        assert "--use_gpu" in cmd

    @patch("subprocess.run")
    def test_feature_extractor_args(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.feature_extractor(str(tmp_path / "db"), str(tmp_path / "imgs"),
                            camera_model="OPENCV", use_gpu=False)
        cmd = mock_run.call_args[0][0]
        assert "feature_extractor" in cmd
        assert "OPENCV" in cmd
        assert "--SiftExtraction.use_gpu" in cmd

    @patch("subprocess.run")
    def test_exhaustive_matcher_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.exhaustive_matcher("/tmp/db", use_gpu=False)
        cmd = mock_run.call_args[0][0]
        assert "exhaustive_matcher" in cmd
        assert "--SiftMatching.use_gpu" in cmd

    @patch("subprocess.run")
    def test_mapper_args(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.mapper("/db", "/imgs", str(tmp_path / "output"))
        cmd = mock_run.call_args[0][0]
        assert "mapper" in cmd
        assert "--database_path" in cmd
        assert "--output_path" in cmd

    @patch("subprocess.run")
    def test_poisson_mesher_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.poisson_mesher("/in.ply", "/out.ply")
        cmd = mock_run.call_args[0][0]
        assert "poisson_mesher" in cmd
        assert "--input_path" in cmd

    @patch("subprocess.run")
    def test_model_converter_args(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.model_converter("/sparse/0", str(tmp_path / "out"), output_type="TXT")
        cmd = mock_run.call_args[0][0]
        assert "model_converter" in cmd
        assert "--output_type" in cmd
        assert "TXT" in cmd
        assert result["output_type"] == "TXT"

    @patch("subprocess.run")
    def test_patch_match_stereo_args(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        b.patch_match_stereo("/ws", geom_consistency=False)
        cmd = mock_run.call_args[0][0]
        assert "patch_match_stereo" in cmd
        assert "false" in cmd

    @patch("subprocess.run")
    def test_database_creator(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        b = self._backend()
        result = b.database_creator(str(tmp_path / "db.db"))
        assert result["status"] == "created"


# ── ReplSkin Tests ───────────────────────────────────────────────

class TestReplSkinInit:
    def test_default(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer", version="2.1.0")
        assert skin.software == "acloudviewer"
        assert skin.display_name == "Acloudviewer"
        assert skin.version == "2.1.0"

    def test_accent_color(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin, _ACCENT_COLORS
        skin = ReplSkin("acloudviewer")
        assert skin.accent == _ACCENT_COLORS["acloudviewer"]

    def test_default_accent(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin, _DEFAULT_ACCENT
        skin = ReplSkin("unknown_software")
        assert skin.accent == _DEFAULT_ACCENT

    def test_history_file(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        assert "acloudviewer" in skin.history_file
        assert "history" in skin.history_file

    def test_custom_history_file(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer", history_file="/tmp/test_history")
        assert skin.history_file == "/tmp/test_history"


class TestReplSkinColorDetect:
    def test_no_color_env(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            skin = ReplSkin("acloudviewer")
            assert skin._color is False

    def test_cli_anything_no_color(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        with patch.dict(os.environ, {"CLI_ANYTHING_NO_COLOR": "1"}):
            skin = ReplSkin("acloudviewer")
            assert skin._color is False

    def test_no_tty(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            skin = ReplSkin("acloudviewer")
            assert skin._color is False


class TestReplSkinANSI:
    def test_strip_ansi(self):
        from cli_anything.acloudviewer.utils.repl_skin import _strip_ansi
        assert _strip_ansi("\033[38;5;80mhello\033[0m") == "hello"

    def test_strip_plain(self):
        from cli_anything.acloudviewer.utils.repl_skin import _strip_ansi
        assert _strip_ansi("no ansi here") == "no ansi here"

    def test_visible_len(self):
        from cli_anything.acloudviewer.utils.repl_skin import _visible_len
        assert _visible_len("\033[1mBold\033[0m") == 4

    def test_visible_len_plain(self):
        from cli_anything.acloudviewer.utils.repl_skin import _visible_len
        assert _visible_len("plain text") == 10


class TestReplSkinPrompt:
    def test_basic_prompt(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        p = skin.prompt()
        assert "acloudviewer" in p

    def test_prompt_with_project(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        p = skin.prompt(project_name="scene.ply")
        assert "scene.ply" in p

    def test_prompt_modified_star(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        p = skin.prompt(project_name="scene.ply", modified=True)
        assert "*" in p

    def test_prompt_no_modified_star(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        p = skin.prompt(project_name="scene.ply", modified=False)
        assert "scene.ply" in p


class TestReplSkinMessages:
    def test_success(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.success("done")
        assert "done" in capsys.readouterr().out

    def test_warning(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.warning("careful")
        assert "careful" in capsys.readouterr().out

    def test_error(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.error("oops")
        assert "oops" in capsys.readouterr().err

    def test_info(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.info("note")
        assert "note" in capsys.readouterr().out

    def test_hint(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.hint("try this")
        assert "try this" in capsys.readouterr().out

    def test_section(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.section("My Section")
        out = capsys.readouterr().out
        assert "My Section" in out

    def test_status(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.status("Mode", "headless")
        out = capsys.readouterr().out
        assert "Mode" in out
        assert "headless" in out

    def test_progress(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.progress(50, 100, label="processing")
        out = capsys.readouterr().out
        assert "50%" in out
        assert "processing" in out

    def test_progress_zero_total(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.progress(0, 0)
        out = capsys.readouterr().out
        assert "0%" in out


class TestReplSkinTable:
    def test_table(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.table(["Name", "Type"], [["cloud.ply", "POINT_CLOUD"], ["mesh.obj", "MESH"]])
        out = capsys.readouterr().out
        assert "Name" in out
        assert "cloud.ply" in out
        assert "mesh.obj" in out

    def test_empty_headers(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.table([], [])
        assert capsys.readouterr().out == ""

    def test_status_block(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.status_block({"Mode": "headless", "Version": "2.0"}, title="Info")
        out = capsys.readouterr().out
        assert "Info" in out
        assert "headless" in out


class TestReplSkinHelp:
    def test_help(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.help({"convert": "Convert file formats", "info": "Show info"})
        out = capsys.readouterr().out
        assert "convert" in out
        assert "Convert file formats" in out

    def test_goodbye(self, capsys):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        skin._color = False
        skin.print_goodbye()
        assert "Goodbye" in capsys.readouterr().out


class TestReplSkinPromptTokens:
    def test_tokens_basic(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        tokens = skin.prompt_tokens()
        assert isinstance(tokens, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in tokens)
        classes = [t[0] for t in tokens]
        assert "class:icon" in classes
        assert "class:software" in classes

    def test_tokens_with_project(self):
        from cli_anything.acloudviewer.utils.repl_skin import ReplSkin
        skin = ReplSkin("acloudviewer")
        tokens = skin.prompt_tokens(project_name="test.ply", modified=True)
        texts = [t[1] for t in tokens]
        combined = "".join(texts)
        assert "test.ply*" in combined
