"""MCP server coverage tests to boost mcp_server.py coverage."""

import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
import pytest

from cli_anything.acloudviewer import mcp_server


class TestMCPServerModule:
    """Test MCP server functions."""

    def test_module_imports(self):
        assert hasattr(mcp_server, 'app')
        assert hasattr(mcp_server, '_get_backend')
        assert hasattr(mcp_server, '_result')
        assert hasattr(mcp_server, '_error')

    def test_get_backend(self):
        with patch('cli_anything.acloudviewer.mcp_server.ACloudViewerBackend') as mock:
            backend_mock = Mock()
            mock.return_value = backend_mock
            
            result = mcp_server._get_backend()
            assert result is not None
            
            result2 = mcp_server._get_backend()
            assert result is result2

    def test_result_with_string(self):
        result = mcp_server._result("test string")
        assert len(result) == 1
        assert result[0].type == "text"
        assert result[0].text == "test string"

    def test_result_with_dict(self):
        result = mcp_server._result({"key": "value"})
        assert len(result) == 1
        assert result[0].type == "text"
        assert "key" in result[0].text
        assert "value" in result[0].text

    def test_result_with_list(self):
        result = mcp_server._result([1, 2, 3])
        assert len(result) == 1
        assert result[0].type == "text"

    def test_error(self):
        result = mcp_server._error("test error")
        assert len(result) == 1
        assert result[0].type == "text"
        assert "error" in result[0].text
        assert "test error" in result[0].text

    @pytest.mark.asyncio
    async def test_list_tools(self):
        tools = await mcp_server.list_tools()
        assert len(tools) > 0
        assert any(t.name == "open_file" for t in tools)
        assert any(t.name == "convert_format" for t in tools)
        assert any(t.name == "subsample" for t in tools)

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_open_file(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.open_file.return_value = {"entity_id": 123}
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("open_file", {"path": "/test/file.ply"})
        assert backend_mock.open_file.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_convert_format(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.convert_file.return_value = {"status": "converted"}
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("convert_format", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.pcd"
        })
        assert backend_mock.convert_file.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_batch_convert(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.batch_convert.return_value = {"converted": 5}
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("batch_convert", {
            "input_dir": "/test/in",
            "output_dir": "/test/out",
            "output_format": ".ply"
        })
        assert backend_mock.batch_convert.called
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_call_list_formats(self):
        result = await mcp_server.call_tool("list_formats", {})
        assert len(result) > 0
        text = result[0].text
        assert ".ply" in text or "point_cloud" in text

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_subsample(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.subsample.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("subsample", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "method": "RANDOM",
            "count": 1000
        })
        assert backend_mock.subsample.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_compute_normals(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.compute_normals.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("compute_normals", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply"
        })
        assert backend_mock.compute_normals.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_density(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.compute_density.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("compute_density", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "radius": 0.5
        })
        assert backend_mock.compute_density.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_curvature(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.compute_curvature.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("compute_curvature", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "radius": 0.3
        })
        assert backend_mock.compute_curvature.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_roughness(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.compute_roughness.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("compute_roughness", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "radius": 0.3
        })
        assert backend_mock.compute_roughness.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_c2c_distance(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.c2c_dist.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("cloud_to_cloud_distance", {
            "cloud1_path": "/test/c1.ply",
            "cloud2_path": "/test/c2.ply",
            "output_path": "/test/out.ply"
        })
        assert backend_mock.c2c_dist.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_c2m_distance(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.c2m_dist.return_value = "/test/out.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("cloud_to_mesh_distance", {
            "cloud_path": "/test/cloud.ply",
            "mesh_path": "/test/mesh.obj",
            "output_path": "/test/out.ply"
        })
        assert backend_mock.c2m_dist.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_icp(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.icp.return_value = "/test/aligned.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("icp_registration", {
            "data_path": "/test/data.ply",
            "reference_path": "/test/ref.ply",
            "output_path": "/test/aligned.ply"
        })
        assert backend_mock.icp.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sor_filter(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sor_filter.return_value = "/test/filtered.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("sor_filter", {
            "input_path": "/test/in.ply",
            "output_path": "/test/filtered.ply",
            "knn": 6,
            "sigma": 1.0
        })
        assert backend_mock.sor_filter.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_delaunay(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.delaunay.return_value = "/test/mesh.obj"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("delaunay_triangulation", {
            "input_path": "/test/in.ply",
            "output_path": "/test/mesh.obj"
        })
        assert backend_mock.delaunay.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_sample(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_sample_points.return_value = "/test/sampled.ply"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("sample_mesh", {
            "mesh_path": "/test/mesh.obj",
            "output_path": "/test/sampled.ply",
            "point_count": 10000
        })
        assert backend_mock.mesh_sample_points.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_scene_list(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.scene_list.return_value = [{"id": 1, "name": "Cloud"}]
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("scene_list", {})
        assert backend_mock.scene_list.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_scene_info(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.scene_info.return_value = {"entities": []}
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("scene_info", {})
        assert backend_mock.scene_info.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_clear_scene(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.clear.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("clear_scene", {})
        assert backend_mock.clear.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_screenshot(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_screenshot.return_value = "/test/screenshot.png"
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("take_screenshot", {
            "output_path": "/test/screenshot.png"
        })
        assert backend_mock.view_screenshot.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_zoom_fit(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_zoom_fit.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("zoom_fit", {})
        assert backend_mock.view_zoom_fit.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_set_perspective(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_set_perspective.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("set_perspective", {"enabled": True})
        assert backend_mock.view_set_perspective.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_paint_uniform(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_paint_uniform.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("paint_uniform", {
            "entity_id": 123,
            "r": 255,
            "g": 0,
            "b": 0
        })
        assert backend_mock.cloud_paint_uniform.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_paint_by_height(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_paint_by_height.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("paint_by_height", {"entity_id": 123})
        assert backend_mock.cloud_paint_by_height.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_get_scalar_fields(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_get_scalar_fields.return_value = {"scalar_fields": []}
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("get_scalar_fields", {"entity_id": 123})
        assert backend_mock.cloud_get_scalar_fields.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_simplify(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_simplify.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("mesh_simplify", {
            "entity_id": 123,
            "target_triangles": 1000
        })
        assert backend_mock.mesh_simplify.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_smooth(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_smooth.return_value = None
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("mesh_smooth", {
            "entity_id": 123,
            "iterations": 5
        })
        assert backend_mock.mesh_smooth.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_error_handling(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.open_file.side_effect = Exception("Test error")
        mock_get_backend.return_value = backend_mock
        
        result = await mcp_server.call_tool("open_file", {"path": "/invalid"})
        assert len(result) > 0
        assert "error" in result[0].text.lower() or "Error" in result[0].text


class TestMCPServerMain:
    """Test MCP server main function."""

    def test_main_function_exists(self):
        assert hasattr(mcp_server, 'main')
        assert callable(mcp_server.main)

    @patch('cli_anything.acloudviewer.mcp_server.stdio_server')
    @patch('cli_anything.acloudviewer.mcp_server.argparse.ArgumentParser')
    def test_main_can_be_called(self, mock_argparse, mock_stdio):
        mock_args = Mock()
        mock_args.mode = "headless"
        mock_parser = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_argparse.return_value = mock_parser
        
        async def mock_serve():
            pass
        
        mock_stdio.return_value.__aenter__ = AsyncMock()
        mock_stdio.return_value.__aexit__ = AsyncMock()
        
        try:
            mcp_server.main()
        except (SystemExit, RuntimeError, asyncio.TimeoutError):
            pass
