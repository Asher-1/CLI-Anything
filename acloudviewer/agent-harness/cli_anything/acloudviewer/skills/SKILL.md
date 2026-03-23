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

## Usage

### Basic Commands

```bash
# Show help
cli-anything-acloudviewer --help

# Start interactive REPL mode
cli-anything-acloudviewer

# Show backend info
cli-anything-acloudviewer info

# Run with JSON output (for agent consumption)
cli-anything-acloudviewer --json info
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-acloudviewer
# Enter commands interactively with tab-completion and history
```

### Two Backend Modes

| Mode | How it Works | Requirement |
|------|-------------|-------------|
| **GUI** | JSON-RPC WebSocket to running ACloudViewer | ACloudViewer running with JSON-RPC plugin |
| **Headless** | Subprocess: `ACloudViewer -SILENT -O ... -SS ...` | ACloudViewer binary |

## Command Groups

### File I/O

File operations and format conversion.

| Command | Description |
|---------|-------------|
| `open` | Open a 3D file |
| `export` | Export an entity to file |
| `convert` | Convert between formats (PLY, PCD, OBJ, STL, LAS, DRC, etc.) |
| `batch-convert` | Convert all files in a directory |
| `formats` | List supported file formats |
| `clear` | Clear all loaded entities |

### Process

Point cloud and mesh processing commands.

| Command | Description |
|---------|-------------|
| `subsample` | Subsample a point cloud (SPATIAL, RANDOM, OCTREE) |
| `normals` | Compute normals for a point cloud |
| `icp` | ICP registration between two point clouds |
| `sor` | Statistical outlier removal |
| `c2c-dist` | Compute cloud-to-cloud distances |
| `c2m-dist` | Compute cloud-to-mesh distances |
| `density` | Compute local density |
| `curvature` | Compute curvature (MEAN, GAUSS) |
| `roughness` | Compute roughness |
| `delaunay` | Delaunay triangulation (mesh from point cloud) |
| `sample-mesh` | Sample points from a mesh surface |
| `color-banding` | Apply color banding along an axis |

### Reconstruct

3D reconstruction commands (uses Colmap binary for SfM/MVS).

| Command | Description |
|---------|-------------|
| `auto` | Automatic end-to-end reconstruction from images |
| `mesh` | Reconstruct mesh from point cloud (Delaunay via ACloudViewer) |
| `extract-features` | Extract features from images |
| `match` | Match features between images |
| `sparse` | Run sparse reconstruction / SfM |
| `undistort` | Undistort images and prepare dense workspace |
| `dense-stereo` | Run PatchMatch multi-view stereo |
| `fuse` | Fuse depth maps into a dense point cloud |
| `poisson` | Poisson surface reconstruction |
| `delaunay-mesh` | Delaunay meshing with visibility constraints |
| `simplify-mesh` | Simplify mesh |
| `texture-mesh` | Texture a mesh from multi-view images |
| `convert-model` | Convert Colmap model to other formats |
| `analyze-model` | Analyze a sparse reconstruction model |

### SIBR

SIBR dataset preparation tools for image-based rendering.

| Command | Description |
|---------|-------------|
| `prepare-colmap` | Prepare Colmap reconstruction for SIBR viewers |
| `texture-mesh` | Generate textured mesh from SIBR dataset |
| `unwrap-mesh` | UV-unwrap a mesh for texturing |
| `tonemapper` | Apply tonemapping to HDR images |
| `align-meshes` | Align meshes in the dataset |
| `camera-converter` | Convert camera formats for SIBR |
| `nvm-to-sibr` | Convert NVM format to SIBR dataset layout |
| `crop-from-center` | Crop dataset from center coordinates |
| `clipping-planes` | Compute or apply clipping planes |
| `distord-crop` | Apply distortion-aware cropping to images |
| `tool` | Run any SIBR dataset tool by name |

### Scene

Scene tree operations (GUI mode).

| Command | Description |
|---------|-------------|
| `list` | List all entities in the scene |
| `info` | Show entity details |
| `remove` | Remove an entity |
| `show` | Make an entity visible |
| `hide` | Make an entity hidden |
| `select` | Select entities |

### View

View control (GUI mode).

| Command | Description |
|---------|-------------|
| `orient` | Set camera view orientation (top, front, iso1, etc.) |
| `zoom` | Zoom to fit all or a specific entity |
| `refresh` | Force display redraw |
| `screenshot` | Capture viewport screenshot |
| `camera` | Get camera parameters |
| `perspective` | Toggle perspective mode (object/viewer) |
| `pointsize` | Adjust point display size (+/-) |

### Session

Session management commands.

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `undo` | Undo last operation |
| `redo` | Redo last undone operation |
| `save` | Save session to file |
| `history` | Show undo history |

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

## MCP Server (39 tools)

```bash
cli-anything-acloudviewer-mcp --mode auto
```

**File I/O:** `open_file`, `convert_format`, `batch_convert`, `list_formats`
**Processing:** `subsample`, `compute_normals`, `sor_filter`, `crop`, `density`, `curvature`, `roughness`, `color_banding`
**Distance:** `c2c_distance`, `c2m_distance`
**Registration:** `icp_registration`
**Mesh:** `delaunay`, `sample_mesh`
**Scene (GUI):** `scene_list`, `scene_info`, `screenshot`, `get_camera`
**Reconstruction:** `colmap_auto_reconstruct`, `colmap_extract_features`, `colmap_match_features`, `colmap_sparse_reconstruct`, `colmap_undistort`, `colmap_dense_stereo`, `colmap_stereo_fusion`, `colmap_poisson_mesh`, `colmap_delaunay_mesh`, `colmap_image_texturer`, `colmap_model_converter`, `colmap_analyze_model`
**SIBR:** `sibr_tool`, `sibr_prepare_colmap`, `sibr_texture_mesh`, `sibr_unwrap_mesh`

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

3.0.0
