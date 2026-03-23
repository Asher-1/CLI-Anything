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
    print("MCP SDK not installed. Install with: pip install 'cli-anything-acloudviewer[mcp]'",
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

        elif name == "scene_list":
            return _result(backend.scene_list(
                recursive=arguments.get("recursive", True)))

        elif name == "scene_info":
            return _result(backend.scene_info(arguments["entity_id"]))

        elif name == "screenshot":
            return _result(backend.screenshot_gui(arguments["filename"]))

        elif name == "get_camera":
            return _result(backend.get_camera())

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
