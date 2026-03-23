# cli-anything-acloudviewer

CLI harness for **ACloudViewer** — 3D point cloud and mesh processing via
the ACloudViewer binary CLI (`-SILENT` mode) and JSON-RPC WebSocket.

Part of the [CLI-Anything](https://github.com/Asher-1/CLI-Anything) project.

**Supported Platforms:** Linux, macOS, Windows.

## Installation

```bash
cd acloudviewer/agent-harness
pip install -e .
```

The ACloudViewer binary must be on `PATH`, or set the `ACV_BINARY`
environment variable to its absolute path.

## Two Modes

| Mode | How it Works | Requirement |
|------|-------------|-------------|
| **Headless** | Subprocess: `ACloudViewer -SILENT -O ... -SS ...` | ACloudViewer binary |
| **GUI** | JSON-RPC WebSocket to running ACloudViewer | ACloudViewer with JSON-RPC plugin |

The CLI auto-detects: if a running ACloudViewer instance responds on
`ws://localhost:6001`, GUI mode is used; otherwise headless.

## Usage Examples

### Basic Operations

```bash
# Enter interactive REPL
cli-anything-acloudviewer

# Show backend info
cli-anything-acloudviewer --json info

# List supported file formats
cli-anything-acloudviewer --json --mode headless formats
```

### File Conversion

```bash
# Convert PLY to PCD
cli-anything-acloudviewer --mode headless convert input.ply output.pcd

# Convert mesh OBJ to STL
cli-anything-acloudviewer --mode headless convert model.obj model.stl

# Batch convert all PLY files to PCD
cli-anything-acloudviewer --mode headless batch-convert ./scans/ ./output/ -f .pcd
```

### Point Cloud Processing

```bash
# Voxel subsample
cli-anything-acloudviewer --mode headless process subsample input.ply -o sub.ply --voxel-size 0.05

# Compute normals
cli-anything-acloudviewer --mode headless process normals input.ply -o normals.ply

# ICP registration (align source to target)
cli-anything-acloudviewer --mode headless process icp source.ply target.ply -o aligned.ply

# Statistical outlier removal
cli-anything-acloudviewer --mode headless process sor input.ply -o clean.ply --knn 6 --std 1.0

# Cloud-to-cloud distance
cli-anything-acloudviewer --mode headless process c2c-dist compared.ply reference.ply -o dist.ply

# Cloud-to-mesh distance
cli-anything-acloudviewer --mode headless process c2m-dist cloud.ply mesh.obj -o dist.ply

# Point density
cli-anything-acloudviewer --mode headless process density input.ply -o density.ply --radius 0.05

# Curvature estimation
cli-anything-acloudviewer --mode headless process curvature input.ply -o curv.ply

# Surface roughness
cli-anything-acloudviewer --mode headless process roughness input.ply -o rough.ply --radius 0.1

# Delaunay triangulation
cli-anything-acloudviewer --mode headless process delaunay input.ply -o mesh.ply

# Sample mesh to point cloud
cli-anything-acloudviewer --mode headless process sample-mesh mesh.obj -o cloud.ply --density 100

# Color banding (height-based coloring)
cli-anything-acloudviewer --mode headless process color-banding input.ply -o colored.ply
```

### 3D Reconstruction (Colmap)

```bash
# Automatic end-to-end reconstruction from images
cli-anything-acloudviewer --json reconstruct auto ./images/ -w ./workspace/ --quality high

# Step-by-step reconstruction pipeline:

# 1. Extract features from images
cli-anything-acloudviewer reconstruct extract-features ./images/ -d ./database.db

# 2. Match features between images
cli-anything-acloudviewer reconstruct match ./database.db --method exhaustive

# 3. Sparse reconstruction (Structure-from-Motion)
cli-anything-acloudviewer reconstruct sparse -d ./database.db --image-path ./images/ -o ./sparse/

# 4. Undistort images for dense reconstruction
cli-anything-acloudviewer reconstruct undistort --image-path ./images/ -i ./sparse/0 -o ./dense/

# 5. Dense stereo (PatchMatch MVS)
cli-anything-acloudviewer reconstruct dense-stereo ./dense/

# 6. Fuse depth maps into dense point cloud
cli-anything-acloudviewer reconstruct fuse ./dense/ -o ./dense/fused.ply

# 7. Poisson surface reconstruction
cli-anything-acloudviewer reconstruct poisson ./dense/fused.ply -o ./mesh.ply

# 8. Delaunay meshing with visibility constraints
cli-anything-acloudviewer reconstruct delaunay-mesh ./dense/fused.ply -o ./mesh_delaunay.ply

# 9. Texture the mesh (uses Colmap image_texturer)
cli-anything-acloudviewer reconstruct texture-mesh ./dense/ -o ./textured/ --mesh ./mesh_delaunay.ply

# Utility: convert model format
cli-anything-acloudviewer reconstruct convert-model ./sparse/0 -o ./model.ply --output-type PLY

# Utility: analyze reconstruction quality
cli-anything-acloudviewer reconstruct analyze-model ./sparse/0

# Mesh reconstruction from point cloud (via ACloudViewer Delaunay)
cli-anything-acloudviewer reconstruct mesh input.ply -o mesh.ply
```

### SIBR Dataset Tools

Requires ACloudViewer built with the SIBR plugin (`-DPLUGIN_STANDARD_QSIBR=ON`).

```bash
# Prepare Colmap output for SIBR rendering
cli-anything-acloudviewer sibr prepare-colmap ./colmap_workspace/

# Prepare with metadata fix
cli-anything-acloudviewer sibr prepare-colmap ./colmap_workspace/ --fix-metadata

# Generate textured mesh from dataset
cli-anything-acloudviewer sibr texture-mesh ./dataset/

# UV-unwrap a mesh for texturing
cli-anything-acloudviewer sibr unwrap-mesh ./dataset/

# Apply tonemapping to HDR images
cli-anything-acloudviewer sibr tonemapper ./dataset/

# Align meshes in the dataset
cli-anything-acloudviewer sibr align-meshes ./dataset/

# Convert camera formats for SIBR
cli-anything-acloudviewer sibr camera-converter ./dataset/

# Convert NVM format to SIBR dataset layout
cli-anything-acloudviewer sibr nvm-to-sibr ./dataset/

# Crop dataset from center
cli-anything-acloudviewer sibr crop-from-center ./dataset/

# Compute clipping planes
cli-anything-acloudviewer sibr clipping-planes ./dataset/

# Distortion-aware image cropping
cli-anything-acloudviewer sibr distord-crop ./dataset/

# Run any SIBR tool by name with passthrough args
cli-anything-acloudviewer sibr tool prepareColmap4Sibr -path ./dataset/ -fix_metadata
```

### Full Reconstruction Pipeline (Colmap + SIBR)

End-to-end example: images to SIBR-ready dataset:

```bash
# 1. Automatic Colmap reconstruction
cli-anything-acloudviewer reconstruct auto ./images/ -w ./workspace/ --quality high

# 2. Prepare the reconstruction for SIBR viewing
cli-anything-acloudviewer sibr prepare-colmap ./workspace/

# 3. Generate textured mesh
cli-anything-acloudviewer sibr texture-mesh ./workspace/

# 4. UV-unwrap the mesh
cli-anything-acloudviewer sibr unwrap-mesh ./workspace/
```

### GUI Mode (Scene & View)

```bash
# List all entities in the scene
cli-anything-acloudviewer --json --mode gui scene list

# Get entity details
cli-anything-acloudviewer --json --mode gui scene info --id 1

# Take a screenshot
cli-anything-acloudviewer --mode gui view screenshot -o screenshot.png --width 1920 --height 1080

# Get camera parameters
cli-anything-acloudviewer --json --mode gui view camera
```

### Session Management

```bash
# Show session status
cli-anything-acloudviewer --json session status

# Undo last operation
cli-anything-acloudviewer session undo

# Redo last undone operation
cli-anything-acloudviewer session redo
```

### JSON Output (for agent/script consumption)

All commands support `--json` flag for structured output:

```bash
cli-anything-acloudviewer --json --mode headless info
cli-anything-acloudviewer --json --mode headless formats
cli-anything-acloudviewer --json --mode headless process subsample input.ply -o sub.ply --voxel-size 0.05
```

## Command Reference

| Group | Subcommands | Description |
|-------|------------|-------------|
| `convert` | — | Convert between 30+ 3D file formats |
| `batch-convert` | — | Batch convert all files in a directory |
| `formats` | — | List supported file formats |
| `info` | — | Show backend info and supported formats |
| `open` | — | Open a file in ACloudViewer |
| `process` | `subsample`, `normals`, `icp`, `sor`, `c2c-dist`, `c2m-dist`, `density`, `curvature`, `roughness`, `delaunay`, `sample-mesh`, `color-banding` | Point cloud and mesh processing |
| `reconstruct` | `mesh`, `auto`, `extract-features`, `match`, `sparse`, `undistort`, `dense-stereo`, `fuse`, `poisson`, `delaunay-mesh`, `texture-mesh`, `convert-model`, `analyze-model` | 3D reconstruction (Colmap SfM/MVS) |
| `sibr` | `tool`, `prepare-colmap`, `texture-mesh`, `unwrap-mesh`, `tonemapper`, `align-meshes`, `camera-converter`, `nvm-to-sibr`, `crop-from-center`, `clipping-planes`, `distord-crop` | SIBR dataset preprocessing (10 tools) |
| `scene` | `list`, `info` | Scene tree operations (GUI mode) |
| `view` | `screenshot`, `camera` | Viewport control and screenshots (GUI mode) |
| `session` | `status`, `undo`, `redo` | Session management |
| `repl` | — | Interactive REPL session |

## Platform Notes

| Platform | Binary Name | Auto-Discovery |
|----------|------------|----------------|
| Linux | `ACloudViewer.sh`, `ACloudViewer` | PATH, `/usr/local/bin`, `/opt/ACloudViewer`, `~/.local/share/ACloudViewer` |
| macOS | `ACloudViewer` | PATH, `/Applications/ACloudViewer.app`, `~/Applications/ACloudViewer.app` |
| Windows | `ACloudViewer.bat`, `ACloudViewer.exe` | PATH, `%PROGRAMFILES%\ACloudViewer`, `%LOCALAPPDATA%\ACloudViewer` |

On all platforms, set `ACV_BINARY` environment variable to override auto-discovery.

## MCP Server

An optional MCP server exposes 39 tools for integration with AI agents:

```bash
pip install -e ".[mcp]"
cli-anything-acloudviewer-mcp --mode auto
```

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest cli_anything/acloudviewer/tests/ -v
```

## Methodology

Built following the
[CLI-Anything HARNESS methodology](https://github.com/Asher-1/CLI-Anything/blob/main/cli-anything-plugin/HARNESS.md).
