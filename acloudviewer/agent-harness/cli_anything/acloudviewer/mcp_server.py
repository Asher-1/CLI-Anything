"""ACloudViewer MCP Server — exposes ACloudViewer as MCP tools.

All headless operations run via the ACloudViewer binary (subprocess),
NOT via any Python 3D library. GUI operations use JSON-RPC WebSocket.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Install with: pip install 'cli-anything-acloudviewer'",
          file=sys.stderr)
    sys.exit(1)

from cli_anything.acloudviewer.utils.acloudviewer_backend import (
    ACloudViewerBackend, BackendError,
    POINT_CLOUD_FORMATS, MESH_FORMATS, ALL_SUPPORTED_FORMATS,
)

app = Server("acloudviewer")
_backend: ACloudViewerBackend | None = None


def _get_backend() -> ACloudViewerBackend:
    global _backend
    if _backend is None:
        _backend = ACloudViewerBackend(mode="auto")
    return _backend


def _result(data: Any) -> list[TextContent]:
    if isinstance(data, str):
        return [TextContent(type="text", text=data)]
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def _error(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}))]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="open_file",
            description="Load a 3D file into ACloudViewer (GUI) or verify existence (headless).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to load"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="convert_format",
            description="Convert between 3D file formats (PLY, PCD, OBJ, STL, LAS, etc). "
                        "Uses ACloudViewer binary in headless mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="batch_convert",
            description="Convert all files in a directory to a target format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_dir": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "output_format": {"type": "string", "default": ".ply"},
                },
                "required": ["input_dir", "output_dir"],
            },
        ),
        Tool(
            name="list_formats",
            description="List all supported file formats by category.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="subsample",
            description="Subsample a point cloud (SPATIAL/RANDOM/OCTREE).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "method": {"type": "string", "default": "SPATIAL",
                               "description": "SPATIAL, RANDOM, or OCTREE"},
                    "parameter": {"type": "number", "default": 0.05},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="compute_normals",
            description="Compute normals for a point cloud.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "radius": {"type": "number", "default": 0.0,
                               "description": "Search radius (0 = auto)"},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="icp_registration",
            description="ICP registration between two point clouds.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_path": {"type": "string"},
                    "reference_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "iterations": {"type": "integer", "default": 100},
                },
                "required": ["data_path", "reference_path"],
            },
        ),
        Tool(
            name="sor_filter",
            description="Statistical Outlier Removal filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "knn": {"type": "integer", "default": 6},
                    "sigma": {"type": "number", "default": 1.0},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="c2c_distance",
            description="Compute cloud-to-cloud distances.",
            inputSchema={
                "type": "object",
                "properties": {
                    "compared_path": {"type": "string"},
                    "reference_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "max_dist": {"type": "number", "default": 0.0},
                },
                "required": ["compared_path", "reference_path"],
            },
        ),
        Tool(
            name="c2m_distance",
            description="Compute cloud-to-mesh distances.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cloud_path": {"type": "string"},
                    "mesh_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "max_dist": {"type": "number", "default": 0.0},
                },
                "required": ["cloud_path", "mesh_path"],
            },
        ),
        Tool(
            name="crop",
            description="Crop a point cloud by bounding box.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "min_x": {"type": "number"}, "min_y": {"type": "number"},
                    "min_z": {"type": "number"},
                    "max_x": {"type": "number"}, "max_y": {"type": "number"},
                    "max_z": {"type": "number"},
                },
                "required": ["input_path", "output_path",
                             "min_x", "min_y", "min_z", "max_x", "max_y", "max_z"],
            },
        ),
        Tool(
            name="delaunay",
            description="Delaunay triangulation — reconstruct mesh from point cloud.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "max_edge_length": {"type": "number", "default": 0.0},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="density",
            description="Compute local point density.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "radius": {"type": "number", "default": 0.5},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="curvature",
            description="Compute curvature (MEAN or GAUSS).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "type": {"type": "string", "default": "MEAN"},
                    "radius": {"type": "number", "default": 0.5},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="roughness",
            description="Compute roughness.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "radius": {"type": "number", "default": 0.5},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="sample_mesh",
            description="Sample points from a mesh surface.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "points": {"type": "integer", "default": 100000},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="color_banding",
            description="Apply color banding along an axis (X/Y/Z).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "axis": {"type": "string", "default": "Z"},
                    "frequency": {"type": "number", "default": 10.0},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        # ── Scalar field operations ──
        Tool(name="set_active_sf", description="Set active scalar field (headless).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "sf_index": {"type": ["integer", "string"], "default": 0}},
              "required": ["input_path", "output_path"]}),
        Tool(name="remove_all_sfs", description="Remove all scalar fields (headless).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="remove_sf", description="Remove a specific scalar field by index (headless).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "sf_index": {"type": "integer", "default": 0}},
              "required": ["input_path", "output_path"]}),
        Tool(name="rename_sf", description="Rename a scalar field (headless).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "sf_index": {"type": ["integer", "string"], "default": 0},
                 "new_name": {"type": "string"}},
              "required": ["input_path", "output_path", "new_name"]}),
        Tool(name="sf_arithmetic", description="Apply unary SF arithmetic (SQRT, ABS, etc.).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "sf_index": {"type": ["integer", "string"], "default": 0},
                 "operation": {"type": "string", "default": "SQRT"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="sf_operation", description="Apply SF arithmetic with scalar (ADD/SUB/MULTIPLY/DIVIDE).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "sf_index": {"type": ["integer", "string"], "default": 0},
                 "operation": {"type": "string", "default": "ADD"},
                 "value": {"type": "number"}},
              "required": ["input_path", "output_path", "value"]}),
        Tool(name="coord_to_sf", description="Export coordinate as scalar field (X/Y/Z).",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "dimension": {"type": "string", "default": "Z"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="sf_gradient", description="Compute scalar field gradient.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "euclidean": {"type": "boolean", "default": False}},
              "required": ["input_path", "output_path"]}),
        Tool(name="filter_sf", description="Filter points by active SF value range.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "min_val": {"type": "string", "default": "MIN"},
                 "max_val": {"type": "string", "default": "MAX"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="sf_color_scale", description="Apply a color scale to active SF.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "scale_file": {"type": "string"}},
              "required": ["input_path", "output_path", "scale_file"]}),
        Tool(name="sf_convert_to_rgb", description="Convert active SF to RGB colors.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        # ── Advanced normals ──
        Tool(name="octree_normals", description="Compute normals with octree method.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "radius": {"type": "string", "default": "AUTO"},
                 "orient": {"type": "string", "default": ""},
                 "model": {"type": "string", "default": ""}},
              "required": ["input_path", "output_path"]}),
        Tool(name="orient_normals_mst", description="Orient normals via MST.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "knn": {"type": "integer", "default": 6}},
              "required": ["input_path", "output_path"]}),
        Tool(name="invert_normals", description="Invert point cloud normals.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="clear_normals", description="Remove all normals from a cloud.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="normals_to_dip", description="Convert normals to dip/dip-direction SFs.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="normals_to_sfs", description="Convert normals to Nx/Ny/Nz scalar fields.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        # ── Geometry / analysis ──
        Tool(name="extract_connected_components", description="Extract connected components.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "octree_level": {"type": "integer", "default": 8},
                 "min_points": {"type": "integer", "default": 100}},
              "required": ["input_path", "output_path"]}),
        Tool(name="approx_density", description="Compute approximate point density.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "density_type": {"type": "string", "default": ""}},
              "required": ["input_path", "output_path"]}),
        Tool(name="geometric_feature", description="Compute geometric feature as SF.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "feature_type": {"type": "string", "default": "SURFACE_VARIATION"},
                 "kernel_size": {"type": "number", "default": 0.1}},
              "required": ["input_path", "output_path"]}),
        Tool(name="moment", description="Compute 1st order moment.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "kernel_size": {"type": "number", "default": 0.1}},
              "required": ["input_path", "output_path"]}),
        Tool(name="best_fit_plane", description="Compute best fit plane.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "make_horiz": {"type": "boolean", "default": False},
                 "keep_loaded": {"type": "boolean", "default": False}},
              "required": ["input_path", "output_path"]}),
        Tool(name="cross_section", description="Extract cross-section from point cloud or mesh along polyline.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "polyline_file": {"type": "string"}},
              "required": ["input_path", "output_path", "polyline_file"]}),
        Tool(name="mesh_volume", description="Compute mesh enclosed volume.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"},
                 "output_file": {"type": "string", "default": ""}},
              "required": ["input_path"]}),
        Tool(name="extract_vertices", description="Extract mesh vertices to point cloud.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="flip_triangles", description="Flip mesh triangle normals.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        # ── Merge ──
        Tool(name="merge_clouds", description="Merge multiple clouds into one.",
             inputSchema={"type": "object", "properties": {
                 "input_paths": {"type": "array", "items": {"type": "string"}},
                 "output_path": {"type": "string"}},
              "required": ["input_paths", "output_path"]}),
        Tool(name="merge_meshes", description="Merge multiple meshes into one.",
             inputSchema={"type": "object", "properties": {
                 "input_paths": {"type": "array", "items": {"type": "string"}},
                 "output_path": {"type": "string"}},
              "required": ["input_paths", "output_path"]}),
        # ── Cleanup ──
        Tool(name="remove_rgb", description="Remove RGB colors from a point cloud.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="remove_scan_grids", description="Remove scan grid info.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="match_centers", description="Match bounding-box centers of entities.",
             inputSchema={"type": "object", "properties": {
                 "input_paths": {"type": "array", "items": {"type": "string"}},
                 "output_path": {"type": "string"}},
              "required": ["input_paths", "output_path"]}),
        Tool(name="drop_global_shift", description="Remove global coordinate shift.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="closest_point_set", description="Compute closest point set between clouds.",
             inputSchema={"type": "object", "properties": {
                 "input_paths": {"type": "array", "items": {"type": "string"}},
                 "output_path": {"type": "string"}},
              "required": ["input_paths", "output_path"]}),
        # ── Rasterize / Volume ──
        Tool(name="rasterize", description="2.5D rasterization of a point cloud.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "grid_step": {"type": "number", "default": 1.0},
                 "vert_dir": {"type": "integer", "default": 2},
                 "output_cloud": {"type": "boolean", "default": True},
                 "output_mesh": {"type": "boolean", "default": False},
                 "proj": {"type": "string", "default": "AVG"},
                 "empty_fill": {"type": "string", "default": "MIN_H"}},
              "required": ["input_path", "output_path"]}),
        Tool(name="stat_test", description="Statistical outlier test.",
             inputSchema={"type": "object", "properties": {
                 "input_path": {"type": "string"}, "output_path": {"type": "string"},
                 "distribution": {"type": "string", "default": "GAUSS"},
                 "p_value": {"type": "number", "default": 0.0001},
                 "knn": {"type": "integer", "default": 16}},
              "required": ["input_path", "output_path"]}),
        # ── Scene / Entity / View (GUI) ──
        Tool(
            name="export_entity",
            description="Export a scene entity to a file (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "filename": {"type": "string", "description": "Output file path"},
                },
                "required": ["entity_id", "filename"],
            },
        ),
        Tool(
            name="scene_list",
            description="List entities in scene (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "recursive": {"type": "boolean", "default": True},
                },
            },
        ),
        Tool(
            name="scene_info",
            description="Get entity details (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="scene_remove",
            description="Remove an entity from the scene (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="scene_set_visible",
            description="Toggle entity visibility (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "visible": {"type": "boolean"},
                },
                "required": ["entity_id", "visible"],
            },
        ),
        Tool(
            name="scene_select",
            description="Select one or more entities (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["entity_ids"],
            },
        ),
        Tool(
            name="scene_clear",
            description="Remove all entities from the scene (GUI mode only).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="entity_rename",
            description="Rename an entity (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "name": {"type": "string"},
                },
                "required": ["entity_id", "name"],
            },
        ),
        Tool(
            name="entity_set_color",
            description="Set entity display color (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "r": {"type": "integer", "description": "Red 0-255"},
                    "g": {"type": "integer", "description": "Green 0-255"},
                    "b": {"type": "integer", "description": "Blue 0-255"},
                },
                "required": ["entity_id", "r", "g", "b"],
            },
        ),
        Tool(
            name="cloud_get_scalar_fields",
            description="List all scalar fields on a point cloud (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_paint_uniform",
            description="Paint all points with a uniform color (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "r": {"type": "integer", "default": 255},
                    "g": {"type": "integer", "default": 255},
                    "b": {"type": "integer", "default": 255},
                },
                "required": ["entity_id", "r", "g", "b"],
            },
        ),
        Tool(
            name="cloud_paint_by_height",
            description="Colorize a point cloud by height gradient (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "axis": {"type": "string", "default": "z",
                             "description": "x, y, or z"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_paint_by_scalar_field",
            description="Colorize a point cloud by a scalar field (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "field_index": {"type": "integer", "default": 0},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_simplify",
            description="Simplify a triangle mesh (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "method": {"type": "string", "default": "quadric",
                               "description": "quadric or vertex_clustering"},
                    "target_triangles": {"type": "integer", "default": 10000},
                    "voxel_size": {"type": "number", "default": 0.05},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_smooth",
            description="Smooth a triangle mesh (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "method": {"type": "string", "default": "laplacian",
                               "description": "laplacian, taubin, or simple"},
                    "iterations": {"type": "integer", "default": 5},
                    "lambda": {"type": "number", "default": 0.5},
                    "mu": {"type": "number", "default": -0.53},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_subdivide",
            description="Subdivide a triangle mesh (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "method": {"type": "string", "default": "midpoint",
                               "description": "midpoint or loop"},
                    "iterations": {"type": "integer", "default": 1},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_sample_points",
            description="Sample points from a mesh surface (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "method": {"type": "string", "default": "uniform",
                               "description": "uniform or poisson_disk"},
                    "count": {"type": "integer", "default": 100000},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="screenshot",
            description="Capture viewport screenshot (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="get_camera",
            description="Get camera parameters (GUI mode only).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="view_set_orientation",
            description="Set camera view orientation (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "orientation": {"type": "string",
                                    "description": "top, bottom, front, back, left, right, iso1, iso2"},
                },
                "required": ["orientation"],
            },
        ),
        Tool(
            name="view_zoom_fit",
            description="Zoom to fit all entities or a specific entity (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer", "description": "Optional entity to zoom to"},
                },
            },
        ),
        Tool(
            name="view_refresh",
            description="Force a display redraw (GUI mode only).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="view_set_perspective",
            description="Set perspective projection mode (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "object or viewer"},
                },
                "required": ["mode"],
            },
        ),
        Tool(
            name="view_set_point_size",
            description="Adjust point display size (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "increase or decrease"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="transform_apply",
            description="Apply a 4x4 transformation matrix to an entity (GUI mode only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "matrix": {"type": "array", "items": {"type": "number"},
                               "description": "16 floats in column-major order"},
                },
                "required": ["entity_id", "matrix"],
            },
        ),
        Tool(
            name="transform_apply_file",
            description="Apply a transformation matrix from file to a point cloud (headless).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "matrix_file": {"type": "string", "description": "Path to 4x4 matrix file"},
                },
                "required": ["input_path", "output_path", "matrix_file"],
            },
        ),
        Tool(
            name="get_info",
            description="Get ACloudViewer backend info: mode, binary path.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_rpc_methods",
            description="List all available JSON-RPC methods (GUI mode only).",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Colmap Reconstruction Tools ──────────────────────────────
        Tool(
            name="colmap_auto_reconstruct",
            description="Run automatic end-to-end 3D reconstruction from images using Colmap. "
                        "Performs feature extraction, matching, sparse SfM, dense MVS, and meshing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Directory containing input images"},
                    "workspace_path": {"type": "string", "description": "Output workspace directory"},
                    "quality": {"type": "string", "default": "high",
                               "description": "low, medium, high, or extreme"},
                    "data_type": {"type": "string", "default": "individual",
                                 "description": "individual, video, or internet"},
                    "mesher": {"type": "string", "default": "poisson",
                              "description": "poisson or delaunay"},
                    "camera_model": {"type": "string", "default": "",
                                    "description": "Camera model (e.g. SIMPLE_RADIAL)"},
                    "single_camera": {"type": "boolean", "default": False},
                    "use_gpu": {"type": "boolean", "default": True},
                    "import_results": {"type": "boolean",
                                       "description": "Import results into ACloudViewer scene "
                                                       "(default: true in gui mode, false in headless)"},
                },
                "required": ["image_path", "workspace_path"],
            },
        ),
        Tool(
            name="colmap_extract_features",
            description="Extract SIFT features from images (Colmap feature_extractor).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string"},
                    "database_path": {"type": "string"},
                    "camera_model": {"type": "string", "default": "SIMPLE_RADIAL"},
                    "single_camera": {"type": "boolean", "default": False},
                    "use_gpu": {"type": "boolean", "default": True},
                },
                "required": ["image_path", "database_path"],
            },
        ),
        Tool(
            name="colmap_match_features",
            description="Match features between images (Colmap matcher). "
                        "Supports exhaustive, sequential, vocab_tree, and spatial matching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_path": {"type": "string"},
                    "method": {"type": "string", "default": "exhaustive",
                              "description": "exhaustive, sequential, vocab_tree, or spatial"},
                    "use_gpu": {"type": "boolean", "default": True},
                },
                "required": ["database_path"],
            },
        ),
        Tool(
            name="colmap_sparse_reconstruct",
            description="Run sparse reconstruction / Structure from Motion (Colmap mapper).",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_path": {"type": "string"},
                    "image_path": {"type": "string"},
                    "output_path": {"type": "string"},
                },
                "required": ["database_path", "image_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_dense_stereo",
            description="Run PatchMatch multi-view stereo on undistorted workspace (Colmap).",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_path": {"type": "string"},
                    "geom_consistency": {"type": "boolean", "default": True},
                },
                "required": ["workspace_path"],
            },
        ),
        Tool(
            name="colmap_stereo_fusion",
            description="Fuse depth maps into a dense colored point cloud (Colmap stereo_fusion).",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_path": {"type": "string"},
                    "output_path": {"type": "string", "description": "Output PLY file path"},
                },
                "required": ["workspace_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_poisson_mesh",
            description="Poisson surface reconstruction from fused point cloud (Colmap).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Fused PLY file"},
                    "output_path": {"type": "string"},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_model_converter",
            description="Convert Colmap sparse model to PLY, NVM, Bundler, or other formats.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "output_type": {"type": "string", "default": "PLY",
                                   "description": "BIN, TXT, NVM, Bundler, VRML, PLY, R3D, CAM"},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_undistort",
            description="Undistort images for dense reconstruction (Colmap image_undistorter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Directory containing input images"},
                    "input_path": {"type": "string", "description": "Sparse reconstruction input (e.g. sparse/0)"},
                    "output_path": {"type": "string", "description": "Output directory for undistorted images"},
                    "output_type": {"type": "string", "default": "COLMAP",
                                   "description": "COLMAP, PMVS, or CMP-MVS"},
                    "max_image_size": {"type": "integer", "default": 0,
                                      "description": "Max image dimension (0 = no limit)"},
                },
                "required": ["image_path", "input_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_delaunay_mesh",
            description="Delaunay surface meshing with visibility constraints (Colmap delaunay_mesher).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Fused PLY or dense workspace"},
                    "output_path": {"type": "string"},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_image_texturer",
            description="Texture a mesh using multi-view images (Colmap image_texturer).",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Undistorted image directory"},
                    "output_path": {"type": "string"},
                    "mesh_path": {"type": "string", "default": "",
                                 "description": "Path to mesh file (auto-detected if omitted)"},
                },
                "required": ["input_path", "output_path"],
            },
        ),
        Tool(
            name="colmap_analyze_model",
            description="Analyze a Colmap sparse model and report statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Path to the sparse model"},
                },
                "required": ["input_path"],
            },
        ),
        # ── SIBR Dataset Tools ──────────────────────────────────────
        Tool(
            name="sibr_tool",
            description="Run any SIBR dataset tool by name. Available: prepareColmap4Sibr, "
                        "tonemapper, unwrapMesh, textureMesh, clippingPlanes, cropFromCenter, "
                        "nvmToSIBR, distordCrop, cameraConverter, alignMeshes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "SIBR tool name"},
                    "extra_args": {"type": "array", "items": {"type": "string"},
                                   "description": "Passthrough arguments for the tool"},
                },
                "required": ["tool_name"],
            },
        ),
        Tool(
            name="sibr_prepare_colmap",
            description="Prepare Colmap output for SIBR rendering (prepareColmap4Sibr). "
                        "Converts Colmap reconstruction into SIBR-compatible dataset format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string", "description": "Path to the dataset directory"},
                    "fix_metadata": {"type": "boolean", "default": False,
                                    "description": "Fix metadata issues in the dataset"},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_texture_mesh",
            description="Generate textured mesh from a SIBR dataset.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_unwrap_mesh",
            description="UV-unwrap a mesh for texturing (SIBR unwrapMesh).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_tonemapper",
            description="Apply tonemapping to HDR images in a dataset (SIBR tonemapper).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_align_meshes",
            description="Align meshes in the dataset (SIBR alignMeshes).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_camera_converter",
            description="Convert camera formats for SIBR (SIBR cameraConverter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_nvm_to_sibr",
            description="Convert NVM format to SIBR dataset layout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_crop_from_center",
            description="Crop dataset from center coordinates (SIBR cropFromCenter).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_clipping_planes",
            description="Compute or apply clipping planes (SIBR clippingPlanes).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_distord_crop",
            description="Apply distortion-aware cropping to images (SIBR distordCrop).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_path": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_path"],
            },
        ),
        Tool(
            name="sibr_viewer",
            description="Launch a SIBR viewer for novel view synthesis visualization (gaussian, ulr, texturedmesh, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "viewer_type": {"type": "string", 
                                   "enum": ["gaussian", "ulr", "ulrv2", "texturedmesh", "pointbased", "remoteGaussian"],
                                   "description": "Type of SIBR viewer to launch"},
                    "path": {"type": "string", "description": "Dataset directory path"},
                    "model_path": {"type": "string", "description": "Trained model directory (for gaussian viewer)"},
                    "mesh": {"type": "string", "description": "Mesh file path (for texturedmesh viewer)"},
                    "width": {"type": "integer", "default": 1920, "description": "Window width"},
                    "height": {"type": "integer", "default": 1080, "description": "Window height"},
                    "iteration": {"type": "integer", "description": "Specific iteration to load (gaussian viewer)"},
                    "device": {"type": "integer", "default": 0, "description": "CUDA device ID"},
                    "no_interop": {"type": "boolean", "default": False, "description": "Disable CUDA-OpenGL interop"},
                    "ip": {"type": "string", "default": "127.0.0.1", "description": "IP address (remoteGaussian)"},
                    "port": {"type": "integer", "default": 6009, "description": "Port (remoteGaussian)"},
                },
                "required": ["viewer_type"],
            },
        ),
        # ── Cloud scalar-field management (GUI) ─────────────────────────
        Tool(
            name="cloud_set_active_sf",
            description="Set the active scalar field on a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "field_index": {"type": "integer", "description": "SF index (-1 for default)"},
                    "field_name": {"type": "string", "description": "SF name (alternative to index)"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_remove_sf",
            description="Remove a scalar field from a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "field_index": {"type": "integer"},
                    "field_name": {"type": "string"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_remove_all_sfs",
            description="Remove all scalar fields from a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_rename_sf",
            description="Rename a scalar field on a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "new_name": {"type": "string"},
                    "field_index": {"type": "integer"},
                    "old_name": {"type": "string"},
                },
                "required": ["entity_id", "new_name"],
            },
        ),
        Tool(
            name="cloud_filter_sf",
            description="Filter point cloud by scalar field value range (GUI mode). Keeps points where SF is in [min, max].",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "field_index": {"type": "integer"},
                    "field_name": {"type": "string"},
                },
                "required": ["entity_id", "min", "max"],
            },
        ),
        Tool(
            name="cloud_coord_to_sf",
            description="Create a scalar field from point coordinates (X/Y/Z) on a cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer"},
                    "dimension": {"type": "string", "enum": ["x", "y", "z"]},
                },
                "required": ["entity_id"],
            },
        ),
        # ── Cloud geometry (GUI) ────────────────────────────────────────
        Tool(
            name="cloud_remove_rgb",
            description="Remove color data from a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_remove_normals_gui",
            description="Remove normals from a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_invert_normals_gui",
            description="Invert normal directions on a point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="cloud_merge_gui",
            description="Merge multiple point clouds into one (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {"type": "array", "items": {"type": "integer"},
                                   "description": "List of cloud entity IDs to merge (min 2)"},
                },
                "required": ["entity_ids"],
            },
        ),
        # ── Mesh extended (GUI) ─────────────────────────────────────────
        Tool(
            name="mesh_extract_vertices_gui",
            description="Extract mesh vertices as a new point cloud (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_flip_triangles_gui",
            description="Flip triangle winding order on a mesh (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_volume_gui",
            description="Compute the volume of a closed mesh (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {"entity_id": {"type": "integer"}},
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="mesh_merge_gui",
            description="Merge multiple meshes into one (GUI mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["entity_ids"],
            },
        ),
        # ── COLMAP generic executor ─────────────────────────────────────
        Tool(
            name="colmap_run",
            description="Run any COLMAP subcommand (e.g. feature_extractor, mapper, stereo_fusion). "
                        "Supports all 44 COLMAP subcommands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string",
                                "description": "COLMAP subcommand name (e.g. feature_extractor, mapper)"},
                    "args": {"type": "array", "items": {"type": "string"},
                             "description": "Positional arguments"},
                    "kwargs": {"type": "object",
                               "description": "Key-value arguments (without --prefix, added automatically)"},
                    "colmap_binary": {"type": "string", "default": "colmap"},
                    "timeout_ms": {"type": "integer", "default": 3600000},
                },
                "required": ["command"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        backend = _get_backend()

        if name == "open_file":
            return _result(backend.open_file(arguments["path"]))

        elif name == "convert_format":
            return _result(backend.convert_format(
                arguments["input_path"], arguments["output_path"]))

        elif name == "batch_convert":
            return _result(backend.batch_convert(
                arguments["input_dir"], arguments["output_dir"],
                output_format=arguments.get("output_format", ".ply")))

        elif name == "list_formats":
            return _result(ACloudViewerBackend.supported_formats())

        elif name == "subsample":
            return _result(backend.subsample(
                arguments["input_path"], arguments["output_path"],
                method=arguments.get("method", "SPATIAL"),
                parameter=arguments.get("parameter", 0.05)))

        elif name == "compute_normals":
            return _result(backend.compute_normals(
                arguments["input_path"], arguments["output_path"],
                radius=arguments.get("radius", 0.0)))

        elif name == "icp_registration":
            return _result(backend.icp_registration(
                arguments["data_path"], arguments["reference_path"],
                output_path=arguments.get("output_path"),
                iterations=arguments.get("iterations", 100)))

        elif name == "sor_filter":
            return _result(backend.sor_filter(
                arguments["input_path"], arguments["output_path"],
                knn=arguments.get("knn", 6),
                sigma=arguments.get("sigma", 1.0)))

        elif name == "c2c_distance":
            return _result(backend.c2c_distance(
                arguments["compared_path"], arguments["reference_path"],
                output_path=arguments.get("output_path"),
                max_dist=arguments.get("max_dist", 0.0)))

        elif name == "c2m_distance":
            return _result(backend.c2m_distance(
                arguments["cloud_path"], arguments["mesh_path"],
                output_path=arguments.get("output_path"),
                max_dist=arguments.get("max_dist", 0.0)))

        elif name == "crop":
            return _result(backend.crop(
                arguments["input_path"], arguments["output_path"],
                **{k: arguments[k] for k in
                   ("min_x", "min_y", "min_z", "max_x", "max_y", "max_z")}))

        elif name == "delaunay":
            return _result(backend.delaunay(
                arguments["input_path"], arguments["output_path"],
                max_edge_length=arguments.get("max_edge_length", 0.0)))

        elif name == "density":
            return _result(backend.density(
                arguments["input_path"], arguments["output_path"],
                radius=arguments.get("radius", 0.5)))

        elif name == "curvature":
            return _result(backend.curvature(
                arguments["input_path"], arguments["output_path"],
                curvature_type=arguments.get("type", "MEAN"),
                radius=arguments.get("radius", 0.5)))

        elif name == "roughness":
            return _result(backend.roughness(
                arguments["input_path"], arguments["output_path"],
                radius=arguments.get("radius", 0.5)))

        elif name == "sample_mesh":
            return _result(backend.sample_mesh(
                arguments["input_path"], arguments["output_path"],
                points=arguments.get("points", 100000)))

        elif name == "color_banding":
            return _result(backend.color_banding(
                arguments["input_path"], arguments["output_path"],
                axis=arguments.get("axis", "Z"),
                frequency=arguments.get("frequency", 10.0)))

        # ── Scalar field operations ──
        elif name == "set_active_sf":
            return _result(backend.set_active_sf(
                arguments["input_path"], arguments["output_path"],
                sf_index=arguments.get("sf_index", 0)))
        elif name == "remove_all_sfs":
            return _result(backend.remove_all_sfs(
                arguments["input_path"], arguments["output_path"]))
        elif name == "remove_sf":
            return _result(backend.remove_sf(
                arguments["input_path"], arguments["output_path"],
                sf_index=arguments.get("sf_index", 0)))
        elif name == "rename_sf":
            return _result(backend.rename_sf(
                arguments["input_path"], arguments["output_path"],
                sf_index=arguments.get("sf_index", 0),
                new_name=arguments["new_name"]))
        elif name == "sf_arithmetic":
            return _result(backend.sf_arithmetic(
                arguments["input_path"], arguments["output_path"],
                sf_index=arguments.get("sf_index", 0),
                operation=arguments.get("operation", "SQRT")))
        elif name == "sf_operation":
            return _result(backend.sf_operation(
                arguments["input_path"], arguments["output_path"],
                sf_index=arguments.get("sf_index", 0),
                operation=arguments.get("operation", "ADD"),
                value=arguments["value"]))
        elif name == "coord_to_sf":
            return _result(backend.coord_to_sf(
                arguments["input_path"], arguments["output_path"],
                dimension=arguments.get("dimension", "Z")))
        elif name == "sf_gradient":
            return _result(backend.sf_gradient(
                arguments["input_path"], arguments["output_path"],
                euclidean=arguments.get("euclidean", False)))
        elif name == "filter_sf":
            return _result(backend.filter_sf(
                arguments["input_path"], arguments["output_path"],
                min_val=arguments.get("min_val", "MIN"),
                max_val=arguments.get("max_val", "MAX")))
        elif name == "sf_color_scale":
            return _result(backend.sf_color_scale(
                arguments["input_path"], arguments["output_path"],
                scale_file=arguments["scale_file"]))
        elif name == "sf_convert_to_rgb":
            return _result(backend.sf_convert_to_rgb(
                arguments["input_path"], arguments["output_path"]))

        # ── Advanced normals ──
        elif name == "octree_normals":
            return _result(backend.octree_normals(
                arguments["input_path"], arguments["output_path"],
                radius=arguments.get("radius", "AUTO"),
                orient=arguments.get("orient", ""),
                model=arguments.get("model", "")))
        elif name == "orient_normals_mst":
            return _result(backend.orient_normals_mst(
                arguments["input_path"], arguments["output_path"],
                knn=arguments.get("knn", 6)))
        elif name == "invert_normals":
            return _result(backend.invert_normals(
                arguments["input_path"], arguments["output_path"]))
        elif name == "clear_normals":
            return _result(backend.clear_normals(
                arguments["input_path"], arguments["output_path"]))
        elif name == "normals_to_dip":
            return _result(backend.normals_to_dip(
                arguments["input_path"], arguments["output_path"]))
        elif name == "normals_to_sfs":
            return _result(backend.normals_to_sfs(
                arguments["input_path"], arguments["output_path"]))

        # ── Geometry / analysis ──
        elif name == "extract_connected_components":
            return _result(backend.extract_connected_components(
                arguments["input_path"], arguments["output_path"],
                octree_level=arguments.get("octree_level", 8),
                min_points=arguments.get("min_points", 100)))
        elif name == "approx_density":
            return _result(backend.approx_density(
                arguments["input_path"], arguments["output_path"],
                density_type=arguments.get("density_type", "")))
        elif name == "geometric_feature":
            return _result(backend.feature(
                arguments["input_path"], arguments["output_path"],
                feature_type=arguments.get("feature_type", "SURFACE_VARIATION"),
                kernel_size=arguments.get("kernel_size", 0.1)))
        elif name == "moment":
            return _result(backend.moment(
                arguments["input_path"], arguments["output_path"],
                kernel_size=arguments.get("kernel_size", 0.1)))
        elif name == "best_fit_plane":
            return _result(backend.best_fit_plane(
                arguments["input_path"], arguments["output_path"],
                make_horiz=arguments.get("make_horiz", False),
                keep_loaded=arguments.get("keep_loaded", False)))
        elif name == "cross_section":
            return _result(backend.cross_section(
                arguments["input_path"], arguments["output_path"],
                polyline_file=arguments["polyline_file"]))
        elif name == "mesh_volume":
            return _result(backend.mesh_volume(
                arguments["input_path"],
                output_file=arguments.get("output_file", "")))
        elif name == "extract_vertices":
            return _result(backend.extract_vertices(
                arguments["input_path"], arguments["output_path"]))
        elif name == "flip_triangles":
            return _result(backend.flip_triangles(
                arguments["input_path"], arguments["output_path"]))

        # ── Merge ──
        elif name == "merge_clouds":
            return _result(backend.merge_clouds(
                arguments["input_paths"], arguments["output_path"]))
        elif name == "merge_meshes":
            return _result(backend.merge_meshes(
                arguments["input_paths"], arguments["output_path"]))

        # ── Cleanup ──
        elif name == "remove_rgb":
            return _result(backend.remove_rgb(
                arguments["input_path"], arguments["output_path"]))
        elif name == "remove_scan_grids":
            return _result(backend.remove_scan_grids(
                arguments["input_path"], arguments["output_path"]))
        elif name == "match_centers":
            return _result(backend.match_centers(
                arguments["input_paths"], arguments["output_path"]))
        elif name == "drop_global_shift":
            return _result(backend.drop_global_shift(
                arguments["input_path"], arguments["output_path"]))
        elif name == "closest_point_set":
            return _result(backend.closest_point_set(
                arguments["input_paths"], arguments["output_path"]))

        # ── Rasterize / Volume / Stats ──
        elif name == "rasterize":
            return _result(backend.rasterize(
                arguments["input_path"], arguments["output_path"],
                grid_step=arguments.get("grid_step", 1.0),
                vert_dir=arguments.get("vert_dir", 2),
                output_cloud=arguments.get("output_cloud", True),
                output_mesh=arguments.get("output_mesh", False),
                proj=arguments.get("proj", "AVG"),
                empty_fill=arguments.get("empty_fill", "MIN_H")))
        elif name == "stat_test":
            return _result(backend.stat_test(
                arguments["input_path"], arguments["output_path"],
                distribution=arguments.get("distribution", "GAUSS"),
                p_value=arguments.get("p_value", 0.0001),
                knn=arguments.get("knn", 16)))

        elif name == "export_entity":
            return _result(backend.export_file(
                arguments["entity_id"], arguments["filename"]))

        elif name == "scene_list":
            return _result(backend.scene_list(
                recursive=arguments.get("recursive", True)))

        elif name == "scene_info":
            return _result(backend.scene_info(arguments["entity_id"]))

        elif name == "scene_remove":
            backend.scene_remove(arguments["entity_id"])
            return _result({"entity_id": arguments["entity_id"], "status": "removed"})

        elif name == "scene_set_visible":
            backend.scene_set_visible(arguments["entity_id"], arguments["visible"])
            return _result({"entity_id": arguments["entity_id"],
                           "visible": arguments["visible"]})

        elif name == "scene_select":
            backend.scene_select(arguments["entity_ids"])
            return _result({"selected": arguments["entity_ids"]})

        elif name == "scene_clear":
            backend.scene_clear()
            return _result({"status": "cleared"})

        elif name == "entity_rename":
            backend.entity_rename(arguments["entity_id"], arguments["name"])
            return _result({"entity_id": arguments["entity_id"],
                           "name": arguments["name"]})

        elif name == "entity_set_color":
            backend.entity_set_color(
                arguments["entity_id"],
                arguments["r"], arguments["g"], arguments["b"])
            return _result({"entity_id": arguments["entity_id"],
                           "color": [arguments["r"], arguments["g"], arguments["b"]]})

        elif name == "cloud_get_scalar_fields":
            return _result(backend.cloud_get_scalar_fields(arguments["entity_id"]))

        elif name == "cloud_paint_uniform":
            return _result(backend.cloud_paint_uniform_gui(
                arguments["entity_id"],
                arguments["r"], arguments["g"], arguments["b"]))

        elif name == "cloud_paint_by_height":
            return _result(backend.cloud_paint_by_height_gui(
                arguments["entity_id"],
                axis=arguments.get("axis", "z")))

        elif name == "cloud_paint_by_scalar_field":
            return _result(backend.cloud_paint_by_scalar_field_gui(
                arguments["entity_id"],
                field_name=str(arguments.get("field_index", 0))))

        elif name == "mesh_simplify":
            return _result(backend.mesh_simplify_gui(
                arguments["entity_id"],
                method=arguments.get("method", "quadric"),
                target_triangles=arguments.get("target_triangles", 10000),
                voxel_size=arguments.get("voxel_size", 0.05)))

        elif name == "mesh_smooth":
            return _result(backend.mesh_smooth_gui(
                arguments["entity_id"],
                method=arguments.get("method", "laplacian"),
                iterations=arguments.get("iterations", 5),
                lambda_val=arguments.get("lambda", 0.5),
                mu=arguments.get("mu", -0.53)))

        elif name == "mesh_subdivide":
            return _result(backend.mesh_subdivide_gui(
                arguments["entity_id"],
                method=arguments.get("method", "midpoint"),
                iterations=arguments.get("iterations", 1)))

        elif name == "mesh_sample_points":
            return _result(backend.mesh_sample_points_gui(
                arguments["entity_id"],
                method=arguments.get("method", "uniform"),
                count=arguments.get("count", 100000)))

        elif name == "screenshot":
            return _result(backend.screenshot_gui(arguments["filename"]))

        elif name == "get_camera":
            return _result(backend.get_camera())

        elif name == "view_set_orientation":
            backend.view_set_orientation(arguments["orientation"])
            return _result({"orientation": arguments["orientation"]})

        elif name == "view_zoom_fit":
            backend.view_zoom_fit(arguments.get("entity_id"))
            return _result({"status": "zoomed"})

        elif name == "view_refresh":
            backend.view_refresh()
            return _result({"status": "refreshed"})

        elif name == "view_set_perspective":
            backend.view_set_perspective(arguments["mode"])
            return _result({"mode": arguments["mode"]})

        elif name == "view_set_point_size":
            backend.view_set_point_size(arguments["action"])
            return _result({"action": arguments["action"]})

        elif name == "transform_apply":
            backend.transform_apply_gui(
                arguments["entity_id"], arguments["matrix"])
            return _result({"entity_id": arguments["entity_id"],
                           "status": "transformed"})

        elif name == "transform_apply_file":
            return _result(backend.apply_transformation(
                arguments["input_path"], arguments["output_path"],
                arguments["matrix_file"]))

        elif name == "get_info":
            info = {
                "mode": backend.mode,
                "binary": ACloudViewerBackend.find_binary() or "not found",
            }
            return _result(info)

        elif name == "list_rpc_methods":
            if backend.mode != "gui":
                return _error("Only available in GUI mode")
            return _result(backend._rpc.list_methods())

        # ── Colmap Reconstruction Handlers ────────────────────────────
        elif name.startswith("colmap_"):
            from cli_anything.acloudviewer.utils.colmap_backend import ColmapBackend, ColmapError
            try:
                colmap = ColmapBackend()
            except ColmapError as e:
                return _error(str(e))

            if name == "colmap_auto_reconstruct":
                result = colmap.automatic_reconstruct(
                    arguments["workspace_path"], arguments["image_path"],
                    quality=arguments.get("quality", "high"),
                    data_type=arguments.get("data_type", "individual"),
                    mesher=arguments.get("mesher", "poisson"),
                    camera_model=arguments.get("camera_model", ""),
                    single_camera=arguments.get("single_camera", False),
                    use_gpu=arguments.get("use_gpu", True))

                do_import = arguments.get("import_results")
                if do_import is None:
                    do_import = (backend.mode == "gui")
                if do_import and result.get("outputs"):
                    imported = []
                    for cat in ("textured_mesh", "mesh", "fused_ply"):
                        for path in result["outputs"].get(cat, []):
                            try:
                                backend.open_file(path, silent=True)
                                imported.append(path)
                            except Exception:
                                pass
                    result["imported"] = imported

                return _result(result)

            elif name == "colmap_extract_features":
                return _result(colmap.feature_extractor(
                    arguments["database_path"], arguments["image_path"],
                    camera_model=arguments.get("camera_model", "SIMPLE_RADIAL"),
                    single_camera=arguments.get("single_camera", False),
                    use_gpu=arguments.get("use_gpu", True)))

            elif name == "colmap_match_features":
                method = arguments.get("method", "exhaustive")
                use_gpu = arguments.get("use_gpu", True)
                if method == "exhaustive":
                    return _result(colmap.exhaustive_matcher(
                        arguments["database_path"], use_gpu=use_gpu))
                elif method == "sequential":
                    return _result(colmap.sequential_matcher(
                        arguments["database_path"], use_gpu=use_gpu))
                elif method == "spatial":
                    return _result(colmap.spatial_matcher(
                        arguments["database_path"], use_gpu=use_gpu))
                else:
                    return _error(f"Unknown matcher method: {method}")

            elif name == "colmap_sparse_reconstruct":
                return _result(colmap.mapper(
                    arguments["database_path"], arguments["image_path"],
                    arguments["output_path"]))

            elif name == "colmap_dense_stereo":
                return _result(colmap.patch_match_stereo(
                    arguments["workspace_path"],
                    geom_consistency=arguments.get("geom_consistency", True)))

            elif name == "colmap_stereo_fusion":
                return _result(colmap.stereo_fusion(
                    arguments["workspace_path"], arguments["output_path"]))

            elif name == "colmap_poisson_mesh":
                return _result(colmap.poisson_mesher(
                    arguments["input_path"], arguments["output_path"]))

            elif name == "colmap_model_converter":
                return _result(colmap.model_converter(
                    arguments["input_path"], arguments["output_path"],
                    output_type=arguments.get("output_type", "PLY")))

            elif name == "colmap_undistort":
                return _result(colmap.image_undistorter(
                    arguments["image_path"], arguments["input_path"],
                    arguments["output_path"],
                    output_type=arguments.get("output_type", "COLMAP"),
                    max_image_size=arguments.get("max_image_size", 0)))

            elif name == "colmap_delaunay_mesh":
                return _result(colmap.delaunay_mesher(
                    arguments["input_path"], arguments["output_path"]))

            elif name == "colmap_image_texturer":
                return _result(colmap.image_texturer(
                    arguments["input_path"], arguments["output_path"],
                    mesh_path=arguments.get("mesh_path", "")))

            elif name == "colmap_analyze_model":
                return _result(colmap.model_analyzer(
                    arguments["input_path"]))

            else:
                return _error(f"Unknown colmap tool: {name}")

        # ── Cloud scalar-field management (GUI) ─────────────────────────
        elif name == "cloud_set_active_sf":
            return _result(backend.cloud_set_active_sf_gui(
                arguments["entity_id"],
                field_index=arguments.get("field_index", -1),
                field_name=arguments.get("field_name", "")))

        elif name == "cloud_remove_sf":
            return _result(backend.cloud_remove_sf_gui(
                arguments["entity_id"],
                field_index=arguments.get("field_index", -1),
                field_name=arguments.get("field_name", "")))

        elif name == "cloud_remove_all_sfs":
            return _result(backend.cloud_remove_all_sfs_gui(
                arguments["entity_id"]))

        elif name == "cloud_rename_sf":
            return _result(backend.cloud_rename_sf_gui(
                arguments["entity_id"],
                arguments["new_name"],
                field_index=arguments.get("field_index", -1),
                old_name=arguments.get("old_name", "")))

        elif name == "cloud_filter_sf":
            return _result(backend.cloud_filter_sf_gui(
                arguments["entity_id"],
                min_val=arguments["min"],
                max_val=arguments["max"],
                field_index=arguments.get("field_index", -1),
                field_name=arguments.get("field_name", "")))

        elif name == "cloud_coord_to_sf":
            return _result(backend.cloud_coord_to_sf_gui(
                arguments["entity_id"],
                dimension=arguments.get("dimension", "z")))

        # ── Cloud geometry (GUI) ────────────────────────────────────────
        elif name == "cloud_remove_rgb":
            return _result(backend.cloud_remove_rgb_gui(
                arguments["entity_id"]))

        elif name == "cloud_remove_normals_gui":
            return _result(backend.cloud_remove_normals_gui(
                arguments["entity_id"]))

        elif name == "cloud_invert_normals_gui":
            return _result(backend.cloud_invert_normals_gui(
                arguments["entity_id"]))

        elif name == "cloud_merge_gui":
            return _result(backend.cloud_merge_gui(
                arguments["entity_ids"]))

        # ── Mesh extended (GUI) ─────────────────────────────────────────
        elif name == "mesh_extract_vertices_gui":
            return _result(backend.mesh_extract_vertices_gui(
                arguments["entity_id"]))

        elif name == "mesh_flip_triangles_gui":
            return _result(backend.mesh_flip_triangles_gui(
                arguments["entity_id"]))

        elif name == "mesh_volume_gui":
            return _result(backend.mesh_volume_gui(
                arguments["entity_id"]))

        elif name == "mesh_merge_gui":
            return _result(backend.mesh_merge_gui(
                arguments["entity_ids"]))

        # ── COLMAP generic executor ─────────────────────────────────────
        elif name == "colmap_run":
            return _result(backend.colmap_run_gui(
                arguments["command"],
                args=arguments.get("args"),
                kwargs_=arguments.get("kwargs"),
                colmap_binary=arguments.get("colmap_binary", "colmap"),
                timeout_ms=arguments.get("timeout_ms", 3600000)))

        elif name.startswith("sibr_"):
            if name == "sibr_tool":
                return _result(backend.sibr_tool(
                    arguments["tool_name"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_prepare_colmap":
                return _result(backend.sibr_prepare_colmap(
                    arguments["dataset_path"],
                    fix_metadata=arguments.get("fix_metadata", False)))

            elif name == "sibr_texture_mesh":
                return _result(backend.sibr_texture_mesh(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_unwrap_mesh":
                return _result(backend.sibr_unwrap_mesh(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_tonemapper":
                return _result(backend.sibr_tonemap(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_align_meshes":
                return _result(backend.sibr_align_meshes(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_camera_converter":
                return _result(backend.sibr_camera_converter(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_nvm_to_sibr":
                return _result(backend.sibr_nvm_to_sibr(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_crop_from_center":
                return _result(backend.sibr_crop_from_center(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_clipping_planes":
                return _result(backend.sibr_clipping_planes(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_distord_crop":
                return _result(backend.sibr_distord_crop(
                    arguments["dataset_path"],
                    extra_args=arguments.get("extra_args")))

            elif name == "sibr_viewer":
                return _result(backend.launch_sibr_viewer(
                    arguments["viewer_type"],
                    path=arguments.get("path"),
                    model_path=arguments.get("model_path"),
                    mesh=arguments.get("mesh"),
                    width=arguments.get("width", 1920),
                    height=arguments.get("height", 1080),
                    iteration=arguments.get("iteration"),
                    device=arguments.get("device", 0),
                    no_interop=arguments.get("no_interop", False),
                    ip=arguments.get("ip", "127.0.0.1"),
                    port=arguments.get("port", 6009)))

            else:
                return _error(f"Unknown SIBR tool: {name}")

        else:
            return _error(f"Unknown tool: {name}")

    except BackendError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"{type(e).__name__}: {e}")


async def _run(mode: str, rpc_url: str):
    global _backend
    _backend = ACloudViewerBackend(mode=mode, rpc_url=rpc_url)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description="ACloudViewer MCP Server")
    parser.add_argument("--mode", choices=["auto", "gui", "headless"], default="auto")
    parser.add_argument("--rpc-url", default="ws://localhost:6001")
    args = parser.parse_args()
    asyncio.run(_run(args.mode, args.rpc_url))


if __name__ == "__main__":
    main()
