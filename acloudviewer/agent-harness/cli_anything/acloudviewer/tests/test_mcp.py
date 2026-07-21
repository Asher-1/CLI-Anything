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

            mcp_server._backend = None
            result = mcp_server._get_backend()
            assert result is not None

            result2 = mcp_server._get_backend()
            assert result is result2
            mcp_server._backend = None

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
        assert "error" in result[0].text.lower()
        assert "test error" in result[0].text

    @pytest.mark.asyncio
    async def test_list_tools(self):
        tools = await mcp_server.list_tools()
        assert len(tools) > 0
        tool_names = {t.name for t in tools}
        assert "open_file" in tool_names
        assert "convert_format" in tool_names
        assert "subsample" in tool_names

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
        backend_mock.convert_format.return_value = {"status": "converted"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("convert_format", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.pcd"
        })
        assert backend_mock.convert_format.called
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
        backend_mock.subsample.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("subsample", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "method": "RANDOM",
            "parameter": 1000
        })
        assert backend_mock.subsample.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_compute_normals(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.compute_normals.return_value = {"status": "completed"}
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
        backend_mock.density.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("density", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "radius": 0.5
        })
        assert backend_mock.density.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_curvature(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.curvature.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("curvature", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "radius": 0.3
        })
        assert backend_mock.curvature.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_roughness(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.roughness.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("roughness", {
            "input_path": "/test/in.ply",
            "output_path": "/test/out.ply",
            "radius": 0.3
        })
        assert backend_mock.roughness.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_c2c_distance(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.c2c_distance.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("c2c_distance", {
            "compared_path": "/test/c1.ply",
            "reference_path": "/test/c2.ply",
            "output_path": "/test/out.ply"
        })
        assert backend_mock.c2c_distance.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_c2m_distance(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.c2m_distance.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("c2m_distance", {
            "cloud_path": "/test/cloud.ply",
            "mesh_path": "/test/mesh.obj",
            "output_path": "/test/out.ply"
        })
        assert backend_mock.c2m_distance.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_icp(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.icp_registration.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("icp_registration", {
            "data_path": "/test/data.ply",
            "reference_path": "/test/ref.ply",
            "output_path": "/test/aligned.ply"
        })
        assert backend_mock.icp_registration.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sor_filter(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sor_filter.return_value = {"status": "completed"}
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
        backend_mock.delaunay.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("delaunay", {
            "input_path": "/test/in.ply",
            "output_path": "/test/mesh.obj"
        })
        assert backend_mock.delaunay.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_sample(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sample_mesh.return_value = {"status": "completed"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sample_mesh", {
            "input_path": "/test/mesh.obj",
            "output_path": "/test/sampled.ply",
            "points": 10000
        })
        assert backend_mock.sample_mesh.called
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

        result = await mcp_server.call_tool("scene_info", {"entity_id": 1})
        assert backend_mock.scene_info.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_clear_scene(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.scene_clear.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("scene_clear", {})
        assert backend_mock.scene_clear.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_screenshot(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.screenshot_gui.return_value = "/test/screenshot.png"
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("screenshot", {
            "filename": "/test/screenshot.png"
        })
        assert backend_mock.screenshot_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_zoom_fit(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_zoom_fit.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("view_zoom_fit", {})
        assert backend_mock.view_zoom_fit.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_set_perspective(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_set_perspective.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("view_set_perspective", {"mode": "perspective"})
        assert backend_mock.view_set_perspective.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_paint_uniform(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_paint_uniform_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_paint_uniform", {
            "entity_id": 123,
            "r": 255,
            "g": 0,
            "b": 0
        })
        assert backend_mock.cloud_paint_uniform_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_paint_by_height(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_paint_by_height_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_paint_by_height", {"entity_id": 123})
        assert backend_mock.cloud_paint_by_height_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_get_scalar_fields(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_get_scalar_fields.return_value = {"scalar_fields": []}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_get_scalar_fields", {"entity_id": 123})
        assert backend_mock.cloud_get_scalar_fields.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_simplify(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_simplify_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_simplify", {
            "entity_id": 123,
            "target_triangles": 1000
        })
        assert backend_mock.mesh_simplify_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_smooth(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_smooth_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_smooth", {
            "entity_id": 123,
            "iterations": 5
        })
        assert backend_mock.mesh_smooth_gui.called
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


# ── Additional MCP tool coverage (headless processing, GUI, COLMAP, SIBR) ──


class TestMCPHeadlessProcessing:
    """Group 1 — Headless processing: crop, SF ops, normals, geometry, merge, rasterize."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_crop(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.crop.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("crop", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "min_x": 0.0, "min_y": 0.0, "min_z": 0.0,
            "max_x": 1.0, "max_y": 1.0, "max_z": 1.0,
        })
        assert backend_mock.crop.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_color_banding(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.color_banding.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("color_banding", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.color_banding.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_set_active_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.set_active_sf.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("set_active_sf", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "sf_index": 0,
        })
        assert backend_mock.set_active_sf.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_remove_all_sfs(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.remove_all_sfs.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("remove_all_sfs", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.remove_all_sfs.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_remove_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.remove_sf.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("remove_sf", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "sf_index": 0,
        })
        assert backend_mock.remove_sf.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_rename_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.rename_sf.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("rename_sf", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "new_name": "height",
            "sf_index": 0,
        })
        assert backend_mock.rename_sf.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sf_arithmetic(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sf_arithmetic.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sf_arithmetic", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "operation": "SQRT",
        })
        assert backend_mock.sf_arithmetic.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sf_operation(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sf_operation.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sf_operation", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "value": 1.5,
            "operation": "ADD",
        })
        assert backend_mock.sf_operation.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_coord_to_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.coord_to_sf.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("coord_to_sf", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "dimension": "Z",
        })
        assert backend_mock.coord_to_sf.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sf_gradient(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sf_gradient.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sf_gradient", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.sf_gradient.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_filter_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.filter_sf.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("filter_sf", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.filter_sf.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sf_color_scale(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sf_color_scale.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sf_color_scale", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "scale_file": "/tmp/test.scale",
        })
        assert backend_mock.sf_color_scale.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sf_convert_to_rgb(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sf_convert_to_rgb.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sf_convert_to_rgb", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.sf_convert_to_rgb.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_octree_normals(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.octree_normals.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("octree_normals", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.octree_normals.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_orient_normals_mst(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.orient_normals_mst.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("orient_normals_mst", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "knn": 6,
        })
        assert backend_mock.orient_normals_mst.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_invert_normals(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.invert_normals.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("invert_normals", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.invert_normals.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_clear_normals(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.clear_normals.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("clear_normals", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.clear_normals.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_normals_to_dip(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.normals_to_dip.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("normals_to_dip", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.normals_to_dip.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_normals_to_sfs(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.normals_to_sfs.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("normals_to_sfs", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.normals_to_sfs.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_extract_connected_components(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.extract_connected_components.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("extract_connected_components", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.extract_connected_components.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_approx_density(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.approx_density.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("approx_density", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.approx_density.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_geometric_feature(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.feature.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("geometric_feature", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.feature.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_moment(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.moment.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("moment", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.moment.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_best_fit_plane(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.best_fit_plane.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("best_fit_plane", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.best_fit_plane.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cross_section(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cross_section.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cross_section", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "polyline_file": "/tmp/test.polyline",
        })
        assert backend_mock.cross_section.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_volume(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_volume.return_value = {"volume": 1.0}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_volume", {
            "input_path": "/tmp/test_input.ply",
            "output_file": "/tmp/volume.txt",
        })
        assert backend_mock.mesh_volume.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_extract_vertices(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.extract_vertices.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("extract_vertices", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.extract_vertices.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_flip_triangles(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.flip_triangles.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("flip_triangles", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.flip_triangles.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_merge_clouds(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.merge_clouds.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("merge_clouds", {
            "input_paths": ["/tmp/test_input.ply", "/tmp/test_input2.ply"],
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.merge_clouds.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_merge_meshes(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.merge_meshes.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("merge_meshes", {
            "input_paths": ["/tmp/test_input.obj", "/tmp/test_input2.obj"],
            "output_path": "/tmp/test_output.obj",
        })
        assert backend_mock.merge_meshes.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_remove_rgb(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.remove_rgb.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("remove_rgb", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.remove_rgb.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_remove_scan_grids(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.remove_scan_grids.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("remove_scan_grids", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.remove_scan_grids.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_match_centers(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.match_centers.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("match_centers", {
            "input_paths": ["/tmp/test_input.ply", "/tmp/test_input2.ply"],
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.match_centers.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_drop_global_shift(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.drop_global_shift.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("drop_global_shift", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.drop_global_shift.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_closest_point_set(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.closest_point_set.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("closest_point_set", {
            "input_paths": ["/tmp/test_input.ply", "/tmp/test_input2.ply"],
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.closest_point_set.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_rasterize(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.rasterize.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("rasterize", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.rasterize.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_stat_test(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.stat_test.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("stat_test", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert backend_mock.stat_test.called
        assert len(result) > 0


class TestMCPGuiSceneEntity:
    """Group 2 — GUI scene and entity: remove, visibility, selection, rename, color, export."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_scene_remove(self, mock_get_backend):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("scene_remove", {"entity_id": 42})
        assert backend_mock.scene_remove.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_scene_set_visible(self, mock_get_backend):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("scene_set_visible", {
            "entity_id": 42,
            "visible": True,
        })
        assert backend_mock.scene_set_visible.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_scene_select(self, mock_get_backend):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("scene_select", {"entity_ids": [42, 43]})
        assert backend_mock.scene_select.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_entity_rename(self, mock_get_backend):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("entity_rename", {
            "entity_id": 42,
            "name": "renamed_cloud",
        })
        assert backend_mock.entity_rename.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_entity_set_color(self, mock_get_backend):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("entity_set_color", {
            "entity_id": 42,
            "r": 128,
            "g": 64,
            "b": 32,
        })
        assert backend_mock.entity_set_color.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_export_entity(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.export_file.return_value = {"path": "/tmp/test_output.ply"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("export_entity", {
            "entity_id": 42,
            "filename": "/tmp/test_output.ply",
        })
        assert backend_mock.export_file.called
        assert len(result) > 0


class TestMCPGuiCloudOps:
    """Group 3 — GUI point cloud: scalar fields, filters, RGB/normals, merge."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_paint_by_scalar_field(self, mock_get_backend):
        backend_mock = Mock()
        rpc_mock = Mock()
        rpc_mock.call.return_value = {"entity_id": 42, "field_index": 0}
        backend_mock._rpc = rpc_mock
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_paint_by_scalar_field", {
            "entity_id": 42,
            "field_index": 0,
        })
        assert rpc_mock.call.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_set_active_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_set_active_sf_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_set_active_sf", {
            "entity_id": 42,
            "field_index": 0,
        })
        assert backend_mock.cloud_set_active_sf_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_remove_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_remove_sf_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_remove_sf", {
            "entity_id": 42,
            "field_index": 0,
        })
        assert backend_mock.cloud_remove_sf_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_remove_all_sfs(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_remove_all_sfs_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_remove_all_sfs", {"entity_id": 42})
        assert backend_mock.cloud_remove_all_sfs_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_rename_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_rename_sf_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_rename_sf", {
            "entity_id": 42,
            "new_name": "my_sf",
            "field_index": 0,
        })
        assert backend_mock.cloud_rename_sf_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_filter_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_filter_sf_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_filter_sf", {
            "entity_id": 42,
            "min": 0.0,
            "max": 1.0,
        })
        assert backend_mock.cloud_filter_sf_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_coord_to_sf(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_coord_to_sf_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_coord_to_sf", {
            "entity_id": 42,
            "dimension": "z",
        })
        assert backend_mock.cloud_coord_to_sf_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_remove_rgb(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_remove_rgb_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_remove_rgb", {"entity_id": 42})
        assert backend_mock.cloud_remove_rgb_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_remove_normals_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_remove_normals_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_remove_normals_gui", {"entity_id": 42})
        assert backend_mock.cloud_remove_normals_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_invert_normals_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_invert_normals_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_invert_normals_gui", {"entity_id": 42})
        assert backend_mock.cloud_invert_normals_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_cloud_merge_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.cloud_merge_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("cloud_merge_gui", {
            "entity_ids": [42, 43],
        })
        assert backend_mock.cloud_merge_gui.called
        assert len(result) > 0


class TestMCPGuiMeshOps:
    """Group 4 — GUI mesh: subdivide, sample, vertices, flip, volume, merge."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_subdivide(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_subdivide_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_subdivide", {"entity_id": 42})
        assert backend_mock.mesh_subdivide_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_sample_points(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_sample_points_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_sample_points", {"entity_id": 42})
        assert backend_mock.mesh_sample_points_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_extract_vertices_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_extract_vertices_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_extract_vertices_gui", {"entity_id": 42})
        assert backend_mock.mesh_extract_vertices_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_flip_triangles_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_flip_triangles_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_flip_triangles_gui", {"entity_id": 42})
        assert backend_mock.mesh_flip_triangles_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_volume_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_volume_gui.return_value = {"volume": 3.14}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_volume_gui", {"entity_id": 42})
        assert backend_mock.mesh_volume_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_mesh_merge_gui(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mesh_merge_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("mesh_merge_gui", {"entity_ids": [42, 43]})
        assert backend_mock.mesh_merge_gui.called
        assert len(result) > 0


class TestMCPViewInfo:
    """Group 5 — View and backend info: camera, refresh, orientation, point size, RPC list."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_get_camera(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.get_camera.return_value = {"fov": 45.0}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("get_camera", {})
        assert backend_mock.get_camera.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server.ACloudViewerBackend.find_binary')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_get_info(self, mock_get_backend, mock_find_binary):
        backend_mock = Mock()
        backend_mock.mode = "headless"
        mock_get_backend.return_value = backend_mock
        mock_find_binary.return_value = "/tmp/fake_acv"

        result = await mcp_server.call_tool("get_info", {})
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_list_rpc_methods(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.mode = "gui"
        rpc = Mock()
        rpc.list_methods.return_value = ["scene.list", "entity.getInfo"]
        backend_mock._rpc = rpc
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("list_rpc_methods", {})
        assert rpc.list_methods.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_view_refresh(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_refresh.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("view_refresh", {})
        assert backend_mock.view_refresh.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_view_set_orientation(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_set_orientation.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("view_set_orientation", {"orientation": "top"})
        assert backend_mock.view_set_orientation.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_view_set_point_size(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.view_set_point_size.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("view_set_point_size", {"action": "increase"})
        assert backend_mock.view_set_point_size.called
        assert len(result) > 0


class TestMCPTransform:
    """Group 6 — Transform: matrix on entity (GUI) and matrix file (headless)."""

    _IDENTITY16 = [
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1,
    ]

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_transform_apply(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.transform_apply_gui.return_value = None
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("transform_apply", {
            "entity_id": 42,
            "matrix": self._IDENTITY16,
        })
        assert backend_mock.transform_apply_gui.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_transform_apply_file(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.apply_transformation.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("transform_apply_file", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
            "matrix_file": "/tmp/test_matrix.txt",
        })
        assert backend_mock.apply_transformation.called
        assert len(result) > 0


class TestMCPColmapTools:
    """Group 7 — COLMAP pipeline and generic colmap_run (mock ColmapBackend + backend)."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_auto_reconstruct(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        backend_mock.mode = "headless"
        backend_mock.open_file = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.automatic_reconstruct.return_value = {"outputs": {}}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_auto_reconstruct", {
            "image_path": "/tmp/images",
            "workspace_path": "/tmp/ws",
        })
        assert colmap_inst.automatic_reconstruct.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_extract_features(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.feature_extractor.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_extract_features", {
            "image_path": "/tmp/images",
            "database_path": "/tmp/db.db",
        })
        assert colmap_inst.feature_extractor.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_match_features(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.exhaustive_matcher.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_match_features", {
            "database_path": "/tmp/db.db",
            "method": "exhaustive",
        })
        assert colmap_inst.exhaustive_matcher.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_sparse_reconstruct(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.mapper.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_sparse_reconstruct", {
            "database_path": "/tmp/db.db",
            "image_path": "/tmp/images",
            "output_path": "/tmp/sparse",
        })
        assert colmap_inst.mapper.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_dense_stereo(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.patch_match_stereo.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_dense_stereo", {
            "workspace_path": "/tmp/ws",
        })
        assert colmap_inst.patch_match_stereo.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_stereo_fusion(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.stereo_fusion.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_stereo_fusion", {
            "workspace_path": "/tmp/ws",
            "output_path": "/tmp/test_output.ply",
        })
        assert colmap_inst.stereo_fusion.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_poisson_mesh(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.poisson_mesher.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_poisson_mesh", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert colmap_inst.poisson_mesher.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_model_converter(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.model_converter.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_model_converter", {
            "input_path": "/tmp/sparse/0",
            "output_path": "/tmp/out.ply",
        })
        assert colmap_inst.model_converter.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_undistort(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.image_undistorter.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_undistort", {
            "image_path": "/tmp/images",
            "input_path": "/tmp/sparse/0",
            "output_path": "/tmp/undistorted",
        })
        assert colmap_inst.image_undistorter.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_delaunay_mesh(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.delaunay_mesher.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_delaunay_mesh", {
            "input_path": "/tmp/test_input.ply",
            "output_path": "/tmp/test_output.ply",
        })
        assert colmap_inst.delaunay_mesher.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_image_texturer(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.image_texturer.return_value = {"status": "ok"}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_image_texturer", {
            "input_path": "/tmp/undistorted",
            "output_path": "/tmp/textured",
        })
        assert colmap_inst.image_texturer.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.utils.colmap_backend.ColmapBackend')
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_analyze_model(self, mock_get_backend, mock_colmap_cls):
        backend_mock = Mock()
        mock_get_backend.return_value = backend_mock
        colmap_inst = Mock()
        colmap_inst.model_analyzer.return_value = {"cameras": 10}
        mock_colmap_cls.return_value = colmap_inst

        result = await mcp_server.call_tool("colmap_analyze_model", {
            "input_path": "/tmp/sparse/0",
        })
        assert colmap_inst.model_analyzer.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_colmap_run(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.colmap_run_gui.return_value = {"exit_code": 0}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("colmap_run", {
            "command": "feature_extractor",
            "args": ["--database_path", "/tmp/db.db"],
        })
        assert backend_mock.colmap_run_gui.called
        assert len(result) > 0


class TestMCPSibrTools:
    """Group 8 — SIBR dataset tools and viewer (mock backend)."""

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_viewer(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.launch_sibr_viewer.return_value = {"pid": 12345}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_viewer", {
            "viewer_type": "gaussian",
            "path": "/tmp/dataset",
        })
        assert backend_mock.launch_sibr_viewer.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_tool(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_tool.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_tool", {
            "tool_name": "prepareColmap4Sibr",
            "extra_args": ["--foo"],
        })
        assert backend_mock.sibr_tool.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_prepare_colmap(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_prepare_colmap.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_prepare_colmap", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_prepare_colmap.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_texture_mesh(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_texture_mesh.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_texture_mesh", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_texture_mesh.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_unwrap_mesh(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_unwrap_mesh.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_unwrap_mesh", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_unwrap_mesh.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_tonemapper(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_tonemap.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_tonemapper", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_tonemap.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_align_meshes(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_align_meshes.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_align_meshes", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_align_meshes.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_camera_converter(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_camera_converter.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_camera_converter", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_camera_converter.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_nvm_to_sibr(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_nvm_to_sibr.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_nvm_to_sibr", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_nvm_to_sibr.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_crop_from_center(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_crop_from_center.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_crop_from_center", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_crop_from_center.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_clipping_planes(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_clipping_planes.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_clipping_planes", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_clipping_planes.called
        assert len(result) > 0

    @pytest.mark.asyncio
    @patch('cli_anything.acloudviewer.mcp_server._get_backend')
    async def test_call_sibr_distord_crop(self, mock_get_backend):
        backend_mock = Mock()
        backend_mock.sibr_distord_crop.return_value = {"status": "ok"}
        mock_get_backend.return_value = backend_mock

        result = await mcp_server.call_tool("sibr_distord_crop", {
            "dataset_path": "/tmp/dataset",
        })
        assert backend_mock.sibr_distord_crop.called
        assert len(result) > 0


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
