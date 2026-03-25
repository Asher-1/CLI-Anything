---
name: >-
  cli-anything-acloudviewer
description: >-
  Command-line interface for ACloudViewer — 3D point cloud and mesh processing via ACloudViewer binary CLI and JSON-RPC, with Colmap-based 3D reconstruction and SIBR image-based rendering pipelines.
---

# cli-anything-acloudviewer

A dual-mode command-line interface for 3D point cloud and mesh processing. Supports 30+ file formats, point cloud processing, mesh operations, Colmap 3D reconstruction, and SIBR dataset preparation. GUI mode controls a running ACloudViewer via JSON-RPC WebSocket; headless mode invokes the ACloudViewer binary in `-SILENT` CLI mode.

## Installation

This CLI is installed as part of the cli-anything-acloudviewer package:

```bash
pip install cli-anything-acloudviewer
```

**Prerequisites:**
- Python 3.10+
- ACloudViewer binary on PATH or set `ACV_BINARY` env var
- For reconstruction: Colmap binary on PATH or set `COLMAP_PATH` env var

### Auto-Install ACloudViewer Binary

If ACloudViewer is not installed, the CLI will **interactively prompt** you to download and install it. You can also use these commands:

```bash
# Check what's installed and what's missing
cli-anything-acloudviewer check

# Auto-install desktop app (detects platform, downloads from GitHub Releases)
cli-anything-acloudviewer install app                    # CUDA version (if GPU detected)
cli-anything-acloudviewer install app --cpu-only          # CPU-only (smaller download)
cli-anything-acloudviewer install app --channel beta      # Latest beta build

# Install from a local .run/.dmg/.exe file (no download needed)
cli-anything-acloudviewer install app --from-file /path/to/ACloudViewer-*.run

# Auto-detect missing components and install everything
cli-anything-acloudviewer install auto

# Optionally install cloudViewer Python package (for Python bindings)
cli-anything-acloudviewer install wheel
cli-anything-acloudviewer install wheel --cpu-only
```

Supported platforms: Ubuntu 18.04-24.04, macOS (ARM64/x86_64), Windows (x86_64).
Download page: https://asher-1.github.io/ACloudViewer/

## Usage

### Basic Commands

```bash
# Show help
cli-anything-acloudviewer --help

# Start interactive REPL mode (general)
cli-anything-acloudviewer

# Show backend info (general)
cli-anything-acloudviewer info

# Run with JSON output (for agent consumption)
cli-anything-acloudviewer --json info
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-acloudviewer  # REPL (general)
# Enter commands interactively with tab-completion and history
```

### Two Backend Modes

| Mode | How it Works | Requirement |
|------|-------------|-------------|
| **GUI** | JSON-RPC WebSocket to running ACloudViewer | ACloudViewer running with JSON-RPC plugin |
| **Headless** | Subprocess: `ACloudViewer -SILENT -O ... -SS ...` | ACloudViewer binary |

## Command Groups

### Check & Install

Installation diagnostics and auto-install commands.

| Command | Description |
|---------|-------------|
| `check` | Check installation status and suggest fixes |
| `install app` | Download and install ACloudViewer desktop binary |
| `install app --from-file` | Install from a local .run/.dmg/.exe file |
| `install wheel` | Download and install cloudViewer Python wheel |
| `install auto` | Auto-detect missing components and install them |

### File I/O

File operations and format conversion.

| Command | Description |
|---------|-------------|
| `open` (GUI) | Open a 3D file |
| `export` | Export an entity to file |
| `convert` (headless) | Convert between formats (PLY, PCD, OBJ, STL, LAS, DRC, etc.) |
| `batch-convert` (headless) | Convert all files in a directory |
| `formats` (general) | List supported file formats |
| `clear` (GUI) | Clear all loaded entities |

### Process

Point cloud and mesh processing commands.

| Command | Description |
|---------|-------------|
| `subsample` (headless) | Subsample a point cloud (SPATIAL, RANDOM, OCTREE) |
| `normals` (headless) | Compute normals for a point cloud |
| `icp` (headless) | ICP registration between two point clouds |
| `sor` (headless) | Statistical outlier removal |
| `c2c-dist` (headless) | Compute cloud-to-cloud distances |
| `c2m-dist` (headless) | Compute cloud-to-mesh distances |
| `density` (headless) | Compute local density |
| `curvature` (headless) | Compute curvature (MEAN, GAUSS) |
| `roughness` (headless) | Compute roughness |
| `delaunay` (headless) | Delaunay triangulation (mesh from point cloud) |
| `sample-mesh` (headless) | Sample points from a mesh surface |
| `color-banding` (headless) | Apply color banding along an axis |
| `set-active-sf` (headless) | Set active scalar field |
| `remove-all-sfs` (headless) | Remove all scalar fields |
| `remove-sf` (headless) | Remove a specific scalar field by index |
| `rename-sf` (headless) | Rename a scalar field |
| `sf-arithmetic` (headless) | Unary SF operation (SQRT, ABS, INV, EXP, LOG, etc.) |
| `sf-op` (headless) | Binary SF operation with scalar (ADD, SUB, MULTIPLY, DIVIDE) |
| `coord-to-sf` (headless) | Export coordinate (X/Y/Z) as scalar field |
| `sf-gradient` (headless) | Compute scalar field gradient |
| `filter-sf` (headless) | Filter points by SF value range |
| `sf-color-scale` (headless) | Apply color scale to active SF |
| `sf-to-rgb` (headless) | Convert active SF to RGB colors |
| `octree-normals` (headless) | Compute normals with octree (orient, model options) |
| `orient-normals` (headless) | Orient normals via MST |
| `invert-normals` (headless) | Invert point cloud normals |
| `clear-normals` (headless) | Remove all normals |
| `normals-to-dip` (headless) | Convert normals to dip/dip-direction SFs |
| `normals-to-sfs` (headless) | Convert normals to Nx/Ny/Nz scalar fields |
| `extract-cc` (headless) | Extract connected components |
| `approx-density` (headless) | Approximate point density |
| `feature` (headless) | Geometric features (14 types) |
| `moment` (headless) | 1st order moment |
| `best-fit-plane` (headless) | Best fit plane computation |
| `mesh-volume` (headless) | Compute mesh enclosed volume |
| `extract-vertices` (headless) | Extract mesh vertices to point cloud |
| `flip-triangles` (headless) | Flip mesh triangle normals |
| `merge-clouds` (headless) | Merge multiple point clouds |
| `merge-meshes` (headless) | Merge multiple meshes |
| `remove-rgb` (headless) | Remove RGB colors |
| `remove-scan-grids` (headless) | Remove scan grid info |
| `match-centers` (headless) | Match bounding-box centers |
| `drop-global-shift` (headless) | Remove global coordinate shift |
| `closest-point-set` (headless) | Closest point set between clouds |
| `rasterize` (headless) | 2.5D rasterization |
| `stat-test` (headless) | Statistical outlier test |

### Reconstruct

3D reconstruction commands (uses Colmap binary for SfM/MVS).

| Command | Description |
|---------|-------------|
| `auto` (headless) | Automatic end-to-end reconstruction from images |
| `mesh` (headless) | Reconstruct mesh from point cloud (Delaunay via ACloudViewer) |
| `extract-features` (headless) | Extract features from images |
| `match` (headless) | Match features between images |
| `sparse` (headless) | Run sparse reconstruction / SfM |
| `undistort` (headless) | Undistort images and prepare dense workspace |
| `dense-stereo` (headless) | Run PatchMatch multi-view stereo |
| `fuse` (headless) | Fuse depth maps into a dense point cloud |
| `poisson` (headless) | Poisson surface reconstruction |
| `delaunay-mesh` (headless) | Delaunay meshing with visibility constraints |
| `simplify-mesh` (headless) | Simplify mesh |
| `texture-mesh` (headless) | Texture a mesh from multi-view images |
| `convert-model` (headless) | Convert Colmap model to other formats |
| `analyze-model` (headless) | Analyze a sparse reconstruction model |

### SIBR

SIBR dataset preparation tools for image-based rendering.

| Command | Description |
|---------|-------------|
| `prepare-colmap` (headless) | Prepare Colmap reconstruction for SIBR viewers |
| `texture-mesh` (headless) | Generate textured mesh from SIBR dataset |
| `unwrap-mesh` (headless) | UV-unwrap a mesh for texturing |
| `tonemapper` (headless) | Apply tonemapping to HDR images |
| `align-meshes` (headless) | Align meshes in the dataset |
| `camera-converter` (headless) | Convert camera formats for SIBR |
| `nvm-to-sibr` (headless) | Convert NVM format to SIBR dataset layout |
| `crop-from-center` (headless) | Crop dataset from center coordinates |
| `clipping-planes` (headless) | Compute or apply clipping planes |
| `distord-crop` (headless) | Apply distortion-aware cropping to images |
| `tool` (headless) | Run any SIBR dataset tool by name |

### Scene

Scene tree operations (GUI mode).

| Command | Description |
|---------|-------------|
| `list` (GUI) | List all entities in the scene |
| `info` (GUI) | Show entity details |
| `remove` (GUI) | Remove an entity |
| `show` (GUI) | Make an entity visible |
| `hide` (GUI) | Make an entity hidden |
| `select` (GUI) | Select entities |
| `clear` (GUI) | Clear all entities from scene |

### Entity

Entity manipulation (GUI mode).

| Command | Description |
|---------|-------------|
| `rename` (GUI) | Rename an entity |
| `set-color` (GUI) | Set entity display color (RGB 0-255) |

### Cloud

Point cloud operations on scene entities (GUI mode).

| Command | Description |
|---------|-------------|
| `paint-uniform` (GUI) | Paint all points with a uniform color |
| `paint-by-height` (GUI) | Colorize by height gradient |
| `paint-by-scalar-field` (GUI) | Colorize by a scalar field |
| `get-scalar-fields` (GUI) | List all scalar fields on a cloud |
| `crop` (GUI) | Crop by bounding box |
| `set-active-sf` (GUI) | Set active scalar field by index or name |
| `remove-sf` (GUI) | Remove a scalar field by index or name |
| `remove-all-sfs` (GUI) | Remove all scalar fields |
| `rename-sf` (GUI) | Rename a scalar field |
| `filter-sf` (GUI) | Filter points by scalar field value range |
| `coord-to-sf` (GUI) | Create scalar field from coordinates (X/Y/Z) |
| `remove-rgb` (GUI) | Remove color data |
| `remove-normals` (GUI) | Remove normals |
| `invert-normals` (GUI) | Flip normal directions |
| `merge` (GUI) | Group multiple point clouds |

### Mesh (GUI)

Mesh operations on scene entities (GUI mode).

| Command | Description |
|---------|-------------|
| `simplify` (GUI) | Simplify a triangle mesh (quadric/vertex_clustering) |
| `smooth` (GUI) | Smooth a mesh (laplacian/taubin/simple) |
| `subdivide` (GUI) | Subdivide a mesh (midpoint/loop) |
| `sample-points` (GUI) | Sample points from mesh surface |
| `extract-vertices` (GUI) | Extract mesh vertices as point cloud |
| `flip-triangles` (GUI) | Flip triangle winding order |
| `volume` (GUI) | Compute enclosed volume |
| `merge` (GUI) | Group multiple meshes |

### COLMAP Generic (GUI)

Run any COLMAP subcommand via the JSON-RPC plugin.

| Command | Description |
|---------|-------------|
| `colmap-run` (GUI) | Execute any COLMAP subcommand with arbitrary arguments |

### Transform

Transformation operations.

| Command | Description |
|---------|-------------|
| `apply` (GUI) | Apply 4x4 matrix to entity |
| `apply-file` (headless) | Apply transformation matrix from file |

### View

View control (GUI mode).

| Command | Description |
|---------|-------------|
| `orient` (GUI) | Set camera view orientation (top, front, iso1, etc.) |
| `zoom` (GUI) | Zoom to fit all or a specific entity |
| `refresh` (GUI) | Force display redraw |
| `screenshot` (GUI) | Capture viewport screenshot |
| `camera` (GUI) | Get camera parameters |
| `perspective` (GUI) | Toggle perspective mode (object/viewer) |
| `pointsize` (GUI) | Adjust point display size (+/-) |

### Session

Session management commands.

| Command | Description |
|---------|-------------|
| `status` (general) | Show session status |
| `undo` (general) | Undo last operation |
| `redo` (general) | Redo last undone operation |
| `save` (general) | Save session to file |
| `history` (general) | Show undo history |

## Examples

### Convert Point Cloud Format

```bash
cli-anything-acloudviewer convert input.ply output.pcd
```

### Subsample and Compute Normals

```bash
cli-anything-acloudviewer process subsample input.ply -o sub.ply --voxel-size 0.05
cli-anything-acloudviewer process normals sub.ply -o normals.ply
```

### Batch Convert Directory

```bash
cli-anything-acloudviewer batch-convert ./input/ ./output/ -f .ply
```

### Full 3D Reconstruction Pipeline

```bash
cli-anything-acloudviewer reconstruct auto ./images -w ./workspace --quality high
```

### SIBR Dataset Preparation

```bash
cli-anything-acloudviewer sibr prepare-colmap ./workspace/
cli-anything-acloudviewer sibr texture-mesh ./workspace/
```

## State Management

The CLI maintains session state with:

- **Undo/Redo**: Up to 50 levels of history
- **Session tracking**: Track modifications and operations

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-acloudviewer info

# JSON output for agents
cli-anything-acloudviewer --json info
```

## MCP Server (100+ tools)

```bash
cli-anything-acloudviewer-mcp --mode auto
```

**File I/O:** `open_file`, `convert_format`, `batch_convert`, `list_formats`, `export_entity`
**Processing:** `subsample`, `compute_normals`, `sor_filter`, `crop`, `density`, `curvature`, `roughness`, `color_banding`
**Scalar Fields:** `set_active_sf`, `remove_all_sfs`, `remove_sf`, `rename_sf`, `sf_arithmetic`, `sf_operation`, `coord_to_sf`, `sf_gradient`, `filter_sf`, `sf_color_scale`, `sf_convert_to_rgb`
**Advanced Normals:** `octree_normals`, `orient_normals_mst`, `invert_normals`, `clear_normals`, `normals_to_dip`, `normals_to_sfs`
**Geometry:** `extract_connected_components`, `approx_density`, `geometric_feature`, `moment`, `best_fit_plane`, `mesh_volume`, `extract_vertices`, `flip_triangles`
**Merge & Cleanup:** `merge_clouds`, `merge_meshes`, `remove_rgb`, `remove_scan_grids`, `match_centers`, `drop_global_shift`, `closest_point_set`
**Rasterize:** `rasterize`, `stat_test`
**Distance:** `c2c_distance`, `c2m_distance`
**Registration:** `icp_registration`
**Mesh Headless:** `delaunay`, `sample_mesh`
**Scene (GUI):** `scene_list`, `scene_info`, `scene_remove`, `scene_set_visible`, `scene_select`, `scene_clear`
**Entity (GUI):** `entity_rename`, `entity_set_color`
**Cloud (GUI):** `cloud_get_scalar_fields`, `cloud_paint_uniform`, `cloud_paint_by_height`, `cloud_paint_by_scalar_field`, `cloud_set_active_sf`, `cloud_remove_sf`, `cloud_remove_all_sfs`, `cloud_rename_sf`, `cloud_filter_sf`, `cloud_coord_to_sf`, `cloud_remove_rgb`, `cloud_remove_normals_gui`, `cloud_invert_normals_gui`, `cloud_merge_gui`
**Mesh (GUI):** `mesh_simplify`, `mesh_smooth`, `mesh_subdivide`, `mesh_sample_points`, `mesh_extract_vertices_gui`, `mesh_flip_triangles_gui`, `mesh_volume_gui`, `mesh_merge_gui`
**View (GUI):** `screenshot`, `get_camera`, `view_set_orientation`, `view_zoom_fit`, `view_refresh`, `view_set_perspective`, `view_set_point_size`
**Transform:** `transform_apply`, `transform_apply_file`
**Reconstruction:** `colmap_auto_reconstruct`, `colmap_extract_features`, `colmap_match_features`, `colmap_sparse_reconstruct`, `colmap_undistort`, `colmap_dense_stereo`, `colmap_stereo_fusion`, `colmap_poisson_mesh`, `colmap_delaunay_mesh`, `colmap_image_texturer`, `colmap_model_converter`, `colmap_analyze_model`, `colmap_run`
**SIBR:** `sibr_tool`, `sibr_prepare_colmap`, `sibr_texture_mesh`, `sibr_unwrap_mesh`, `sibr_tonemapper`, `sibr_align_meshes`, `sibr_camera_converter`, `sibr_nvm_to_sibr`, `sibr_crop_from_center`, `sibr_clipping_planes`, `sibr_distord_crop`
**System:** `get_info`, `list_rpc_methods`

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after processing operations

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

3.1.0
