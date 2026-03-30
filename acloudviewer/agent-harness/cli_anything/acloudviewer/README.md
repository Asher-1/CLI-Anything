# cli-anything-acloudviewer  v3.1.0

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

## Command modes

### Runtime behavior (auto-detect)

| Mode | How it Works | Requirement |
|------|-------------|-------------|
| **Headless** | Subprocess: `ACloudViewer -SILENT -O ... -SS ...` | ACloudViewer binary |
| **GUI** | JSON-RPC WebSocket to running ACloudViewer | ACloudViewer with JSON-RPC plugin |

The CLI auto-detects: if a running ACloudViewer instance responds on
`ws://localhost:6001`, GUI mode is used; otherwise headless.

### Commands by category (what each command needs)

**General** (no ACloudViewer backend required):

`info`, `check`, `install`, `formats`, `session`, `repl`

**Headless** (binary `-SILENT` mode; no GUI):

- `convert`, `batch-convert`
- `process`: `subsample`, `normals`, `icp`, `sor`, `c2c-dist`, `c2m-dist`, `crop`, `density`, `curvature`, `roughness`, `delaunay`, `sample-mesh`, `color-banding`, `volume-25d`, `crop-2d`, `rasterize`, `cross-section`, `stat-test`, `approx-density`, `feature`, `best-fit-plane`, `extract-cc`, `set-active-sf`, `remove-sf`, `remove-all-sfs`, `rename-sf`, `filter-sf`, `coord-to-sf`, `sf-arithmetic`, `sf-op`, `octree-normals`, `orient-normals`, `invert-normals`, `clear-normals`, `normals-to-dip`, `normals-to-sfs`, `remove-rgb`, `merge-clouds`, `extract-vertices`, `flip-triangles`, `mesh-volume`, `merge-meshes`, `match-centers`, `drop-global-shift`, `closest-point-set`, `remove-scan-grids`
- `reconstruct`: `mesh`, `auto`, `extract-features`, `match`, `sparse`, `undistort`, `dense-stereo`, `fuse`, `poisson`, `simplify-mesh`, `texture-mesh`, `convert-model`, `analyze-model`, `delaunay-mesh`
- `sibr`: `tool`, `prepare-colmap`, `texture-mesh`, `unwrap-mesh`, `tonemapper`, `align-meshes`, `camera-converter`, `nvm-to-sibr`, `crop-from-center`, `clipping-planes`, `distord-crop`

**GUI** (requires ACloudViewer running with the JSON-RPC plugin):

- `open`, `clear`
- `scene`: `list`, `info`, `remove`, `set-visible`
- `entity`: `rename`, `set-color`
- `view`: `screenshot`, `camera`, `orientation`, `zoom-fit`, `refresh`, `perspective`, `point-size`
- `cloud`: `compute-normals`, `subsample`, `crop`, `scalar-fields`, `paint-uniform`, `paint-by-height`, `set-active-sf`, `remove-sf`, `remove-all-sfs`, `rename-sf`, `filter-sf`, `coord-to-sf`, `remove-rgb`, `remove-normals`, `invert-normals`, `merge`
- `mesh`: `simplify`, `smooth`, `sample-points`, `extract-vertices`, `flip-triangles`, `volume`, `merge`
- `transform`: `apply`
- `export`
- `methods`: `list`
- `colmap`: `reconstruct`, `run` (generic subcommand executor)

## Usage Examples

### Basic operations — **General**

```bash
# Enter interactive REPL
cli-anything-acloudviewer

# Show backend info
cli-anything-acloudviewer --json info

# Diagnostics: binary, wheel, install hints
cli-anything-acloudviewer check

# Install app, wheel, or auto (see --help)
cli-anything-acloudviewer install --help

# List supported file formats
cli-anything-acloudviewer --json formats
```

### File conversion — **Headless**

```bash
# Convert PLY to PCD
cli-anything-acloudviewer --mode headless convert input.ply output.pcd

# Convert mesh OBJ to STL
cli-anything-acloudviewer --mode headless convert model.obj model.stl

# Batch convert all PLY files to PCD
cli-anything-acloudviewer --mode headless batch-convert ./scans/ ./output/ -f .pcd
```

### Point cloud processing — **Headless**

```bash
# Voxel subsample
cli-anything-acloudviewer --mode headless process subsample input.ply -o sub.ply --voxel-size 0.05

# Compute normals (standard k-NN method)
cli-anything-acloudviewer --mode headless process normals input.ply -o normals.ply

# Compute normals with octree (faster for large clouds)
cli-anything-acloudviewer --mode headless normals octree input.ply -o normals.ply --radius AUTO

# Orient normals consistently (MST algorithm)
cli-anything-acloudviewer --mode headless normals orient-mst input.ply -o oriented.ply --knn 6

# Invert all normal directions
cli-anything-acloudviewer --mode headless normals invert input.ply -o inverted.ply

# Convert normals to scalar fields (Nx, Ny, Nz)
cli-anything-acloudviewer --mode headless normals to-sfs input.ply -o normals_sf.ply

# ICP registration (align source to target)
cli-anything-acloudviewer --mode headless process icp source.ply target.ply -o aligned.ply

# Statistical outlier removal
cli-anything-acloudviewer --mode headless process sor input.ply -o clean.ply --knn 6 --sigma 1.0

# Cloud-to-cloud distance
cli-anything-acloudviewer --mode headless process c2c-dist compared.ply reference.ply -o dist.ply

# Cloud-to-mesh distance
cli-anything-acloudviewer --mode headless process c2m-dist cloud.ply mesh.obj -o dist.ply

# Point density
cli-anything-acloudviewer --mode headless process density input.ply -o density.ply --radius 0.05

# Curvature estimation
cli-anything-acloudviewer --mode headless process curvature input.ply -o curv.ply --type MEAN --radius 0.05

# Surface roughness
cli-anything-acloudviewer --mode headless process roughness input.ply -o rough.ply --radius 0.1

# Geometric features (surface variation, etc.)
cli-anything-acloudviewer --mode headless process feature input.ply -o features.ply --type SURFACE_VARIATION --kernel-size 0.1

# Extract connected components
cli-anything-acloudviewer --mode headless process extract-cc input.ply -o components.ply --min-points 100

# Delaunay triangulation
cli-anything-acloudviewer --mode headless process delaunay input.ply -o mesh.ply

# Sample mesh to point cloud
cli-anything-acloudviewer --mode headless process sample-mesh mesh.obj -o cloud.ply --density 100

# Color banding (height-based coloring)
cli-anything-acloudviewer --mode headless process color-banding input.ply -o colored.ply --axis Z --frequency 10.0

# Extract cross-section along polyline
cli-anything-acloudviewer --mode headless process cross-section input.ply -o section.ply --polyline path.ply

# Compute 2.5D volume between two clouds
cli-anything-acloudviewer --mode headless process volume-25d ground.ply surface.ply -o volume_mesh.ply --grid-step 0.5

# Crop by 2D polygon (orthogonal to Z axis)
cli-anything-acloudviewer --mode headless process crop-2d input.ply -o cropped.ply --dim Z --polygon "0,0;10,0;10,10;0,10"
```

### Scalar field operations — **Headless**

```bash
# Create scalar field from coordinate (X, Y, or Z)
cli-anything-acloudviewer --mode headless sf coord-to-sf input.ply -o height.ply --dimension Z

# Apply arithmetic operation (SQRT, ABS, EXP, LOG, etc.)
cli-anything-acloudviewer --mode headless sf arithmetic input.ply -o sqrt.ply --sf-index 0 --operation SQRT

# Apply operation with constant (ADD, SUB, MULTIPLY, DIVIDE)
cli-anything-acloudviewer --mode headless sf operation input.ply -o scaled.ply --sf-index 0 --operation MULTIPLY --value 2.0

# Compute scalar field gradient
cli-anything-acloudviewer --mode headless sf gradient input.ply -o gradient.ply

# Filter points by scalar field value
cli-anything-acloudviewer --mode headless sf filter input.ply -o filtered.ply --min 0.0 --max 10.0

# Convert active scalar field to RGB colors
cli-anything-acloudviewer --mode headless sf convert-to-rgb input.ply -o colored.ply

# Set active scalar field
cli-anything-acloudviewer --mode headless sf set-active input.ply -o active.ply --sf-index 0

# Rename scalar field
cli-anything-acloudviewer --mode headless sf rename input.ply -o renamed.ply --sf-index 0 --name "Elevation"

# Remove scalar field
cli-anything-acloudviewer --mode headless sf remove input.ply -o removed.ply --sf-index 0

# Remove all scalar fields
cli-anything-acloudviewer --mode headless sf remove-all input.ply -o clean.ply
```

### 3D reconstruction (Colmap) — **Headless**

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

### SIBR dataset tools — **Headless**

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

# Launch SIBR viewers for novel view synthesis visualization
cli-anything-acloudviewer sibr viewer gaussian --model-path ./output/ --path ./dataset/
cli-anything-acloudviewer sibr viewer ulr --path ./dataset/
cli-anything-acloudviewer sibr viewer texturedmesh --mesh ./model.obj --path ./dataset/
cli-anything-acloudviewer sibr viewer remoteGaussian --ip 127.0.0.1 --port 6009
```

**Available SIBR viewer types**:
- `gaussian`: Gaussian Splatting viewer (requires `--model-path` and `--path`)
- `ulr` / `ulrv2`: Unstructured Lumigraph Rendering viewers
- `texturedmesh`: Textured mesh viewer (requires `--mesh` and `--path`)
- `pointbased`: Point-based rendering viewer
- `remoteGaussian`: Remote Gaussian viewer for network rendering
```

### Full reconstruction pipeline (Colmap + SIBR) — **Headless**

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

### Scene, entity, view & open — **GUI**

Requires a running ACloudViewer with the JSON-RPC plugin (`--mode gui` or auto-detect when `ws://localhost:6001` is available).

```bash
# Open a file in the viewer
cli-anything-acloudviewer --mode gui open /path/to/model.ply

# List all entities in the scene
cli-anything-acloudviewer --json --mode gui scene list

# Get entity details
cli-anything-acloudviewer --json --mode gui scene info --id 1

# Remove an entity from the scene
cli-anything-acloudviewer --mode gui scene remove --id 1

# Rename an entity
cli-anything-acloudviewer --mode gui entity rename --id 1 --name "MyCloud"

# Set entity color
cli-anything-acloudviewer --mode gui entity set-color --id 1 --r 255 --g 0 --b 0

# Take a screenshot
cli-anything-acloudviewer --mode gui view screenshot -o screenshot.png --width 1920 --height 1080

# Get camera parameters
cli-anything-acloudviewer --json --mode gui view camera

# Set view orientation
cli-anything-acloudviewer --mode gui view orientation --orient top

# Clear the scene
cli-anything-acloudviewer --mode gui clear

# List available RPC methods
cli-anything-acloudviewer --json --mode gui methods list
```

### Cloud operations — **GUI**

```bash
# Compute normals on a loaded cloud
cli-anything-acloudviewer --json --mode gui cloud compute-normals --id 1 --radius 0.05

# Subsample a cloud
cli-anything-acloudviewer --json --mode gui cloud subsample --id 1 --method SPATIAL --param 0.1

# Get scalar field list
cli-anything-acloudviewer --json --mode gui cloud scalar-fields --id 1

# Set active scalar field
cli-anything-acloudviewer --json --mode gui cloud set-active-sf --id 1 --index 0

# Remove a scalar field
cli-anything-acloudviewer --json --mode gui cloud remove-sf --id 1 --index 0

# Coordinate to scalar field
cli-anything-acloudviewer --json --mode gui cloud coord-to-sf --id 1 --axis z

# Remove RGB colors
cli-anything-acloudviewer --mode gui cloud remove-rgb --id 1

# Remove/Invert normals
cli-anything-acloudviewer --mode gui cloud remove-normals --id 1
cli-anything-acloudviewer --mode gui cloud invert-normals --id 1

# Merge multiple clouds
cli-anything-acloudviewer --json --mode gui cloud merge --ids 1 2 3
```

### Mesh operations — **GUI**

```bash
# Simplify mesh
cli-anything-acloudviewer --json --mode gui mesh simplify --id 1 --target-count 10000

# Smooth mesh (Laplacian)
cli-anything-acloudviewer --json --mode gui mesh smooth --id 1 --iterations 3

# Extract vertices as point cloud
cli-anything-acloudviewer --json --mode gui mesh extract-vertices --id 1

# Compute mesh volume
cli-anything-acloudviewer --json --mode gui mesh volume --id 1

# Flip triangle normals
cli-anything-acloudviewer --mode gui mesh flip-triangles --id 1

# Merge meshes
cli-anything-acloudviewer --json --mode gui mesh merge --ids 1 2
```

### COLMAP via RPC — **GUI**

```bash
# Run automatic reconstruction via RPC (live Colmap progress in GUI console)
cli-anything-acloudviewer --json --mode gui colmap reconstruct --image-path ./images/ -w ./workspace/

# Run any Colmap subcommand via RPC
cli-anything-acloudviewer --json --mode gui colmap run --subcommand feature_extractor --args "--image_path ./images/"
```

### Session management — **General**

```bash
# Show session status
cli-anything-acloudviewer --json session status

# Undo last operation
cli-anything-acloudviewer session undo

# Redo last undone operation
cli-anything-acloudviewer session redo
```

### JSON output (for agent/script consumption)

All commands support `--json` flag for structured output. Use **`--mode headless`** or **`--mode gui`** when the command belongs to that category; General commands do not require a backend mode.

```bash
cli-anything-acloudviewer --json info
cli-anything-acloudviewer --json formats
cli-anything-acloudviewer --json --mode headless process subsample input.ply -o sub.ply --voxel-size 0.05
```

## Command Reference

| Mode | Group | Subcommands | Description |
|------|-------|------------|-------------|
| **General** | `check` | — | Installation diagnostics and fix hints |
| **General** | `install` | `app`, `wheel`, `auto` | Download / install binary or Python wheel |
| **General** | `formats` | — | List supported file formats |
| **General** | `info` | — | Show backend info and supported formats |
| **General** | `session` | `status`, `undo`, `redo` | Session management |
| **General** | `repl` | — | Interactive REPL session |
| **Headless** | `convert` | — | Convert between 30+ 3D file formats |
| **Headless** | `batch-convert` | — | Batch convert all files in a directory |
| **Headless** | `process` | `subsample`, `normals`, `icp`, `sor`, `c2c-dist`, `c2m-dist`, `crop`, `density`, `curvature`, `roughness`, `delaunay`, `sample-mesh`, `color-banding`, `set-active-sf`, `remove-sf`, `remove-all-sfs`, `rename-sf`, `filter-sf`, `coord-to-sf`, `remove-rgb`, `remove-normals`, `invert-normals`, `merge-clouds`, `extract-vertices`, `flip-triangles`, `mesh-volume`, `merge-meshes`, `volume-25d`, `crop-2d`, `rasterize`, `cross-section`, `stat-test`, … | Point cloud and mesh processing (35+ operations) |
| **Headless** | `reconstruct` | `mesh`, `auto`, `extract-features`, `match`, `sparse`, `undistort`, `dense-stereo`, `fuse`, `poisson`, `simplify-mesh`, `texture-mesh`, `convert-model`, `analyze-model`, `delaunay-mesh` | 3D reconstruction (Colmap SfM/MVS) |
| **Headless** | `sibr` | `tool`, `prepare-colmap`, `texture-mesh`, `unwrap-mesh`, `tonemapper`, `align-meshes`, `camera-converter`, `nvm-to-sibr`, `crop-from-center`, `clipping-planes`, `distord-crop` | SIBR dataset preprocessing (11 tools) |
| **GUI** | `open` | — | Open a file in the running ACloudViewer |
| **GUI** | `clear` | — | Clear all entities from the scene |
| **GUI** | `scene` | `list`, `info`, `remove`, `set-visible`, `select`, `clear` | Scene tree operations |
| **GUI** | `entity` | `rename`, `set-color` | Entity property management |
| **GUI** | `view` | `screenshot`, `camera`, `orientation`, `zoom-fit`, `refresh`, `perspective`, `point-size` | Viewport control (7 operations) |
| **GUI** | `cloud` | `compute-normals`, `subsample`, `crop`, `scalar-fields`, `paint-uniform`, `paint-by-height`, `set-active-sf`, `remove-sf`, `remove-all-sfs`, `rename-sf`, `filter-sf`, `coord-to-sf`, `remove-rgb`, `remove-normals`, `invert-normals`, `merge` | Point cloud operations (16 operations) |
| **GUI** | `mesh` | `simplify`, `smooth`, `sample-points`, `extract-vertices`, `flip-triangles`, `volume`, `merge` | Mesh operations (7 operations) |
| **GUI** | `transform` | `apply` | Apply transformations to entities |
| **GUI** | `export` | — | Export entities to file |
| **GUI** | `methods` | `list` | List available RPC methods (dynamic discovery) |
| **GUI** | `colmap` | `reconstruct`, `run` | COLMAP reconstruction via RPC |

## JSON-RPC API (67 Methods)

When running in GUI mode, the harness communicates via JSON-RPC 2.0 over WebSocket. The method registry is dynamic — use `methods.list` to discover all available methods at runtime.

Key method groups:

| Category | Methods |
|----------|---------|
| **Lifecycle** | `ping`, `methods.list` |
| **File I/O** | `open`, `export`, `file.convert`, `clear` |
| **Scene** | `scene.list`, `scene.info`, `scene.remove`, `scene.setVisible` |
| **Entity** | `entity.rename`, `entity.setColor` |
| **View** | `view.screenshot`, `view.setOrientation`, `view.zoomFit`, `view.refresh`, `view.setPerspective`, `view.setPointSize`, `view.getCamera` |
| **Cloud** | `cloud.computeNormals`, `cloud.subsample`, `cloud.crop`, `cloud.getScalarFields`, `cloud.paintUniform`, `cloud.paintByHeight`, `cloud.paintByScalarField`, `cloud.setActiveSf`, `cloud.removeSf`, `cloud.removeAllSfs`, `cloud.renameSf`, `cloud.filterSf`, `cloud.coordToSF`, `cloud.removeRgb`, `cloud.removeNormals`, `cloud.invertNormals`, `cloud.merge`, `cloud.density`, `cloud.curvature`, `cloud.roughness`, `cloud.geometricFeature`, `cloud.approxDensity`, `cloud.colorBanding`, `cloud.sorFilter`, `cloud.sfArithmetic`, `cloud.sfOperation`, `cloud.sfGradient`, `cloud.sfConvertToRGB`, `cloud.octreeNormals`, `cloud.orientNormalsMST`, `cloud.clearNormals`, `cloud.normalsToSFs`, `cloud.normalsToDip`, `cloud.extractConnectedComponents`, `cloud.bestFitPlane`, `cloud.delaunay` |
| **Mesh** | `mesh.simplify`, `mesh.smooth`, `mesh.samplePoints`, `mesh.extractVertices`, `mesh.flipTriangles`, `mesh.volume`, `mesh.merge` |
| **Transform** | `transform.apply` |
| **COLMAP** | `colmap.reconstruct`, `colmap.run` |

## MCP Server (121 Tools)

An optional MCP server exposes 121 tools for integration with AI agents:

```bash
pip install -e .
cli-anything-acloudviewer-mcp --mode auto
```

MCP tool categories mirror the JSON-RPC methods above, plus additional CLI-only tools for headless processing, file conversion, batch operations, SIBR, and session management.

## Supported File Formats

### Point Cloud (Import/Export)

| Format | Extensions | Plugin Required |
|--------|-----------|----------------|
| PLY | `.ply` | — (built-in) |
| ASCII | `.asc`, `.xyz`, `.xyzn`, `.xyzrgb`, `.pts`, `.txt`, `.csv`, `.neu` | — (built-in) |
| BIN | `.bin` | — (built-in) |
| VTK | `.vtk` | — (built-in) |
| PCD | `.pcd` | qPCL |
| LAS/LAZ | `.las`, `.laz` | qLASIO or qPDALIO |
| E57 | `.e57` | qE57IO |
| DRC | `.drc` | qDracoIO |
| SBF | `.sbf` | qCoreIO |
| PTX (import only) | `.ptx` | — (built-in) |

### Mesh (Import/Export)

| Format | Extensions | Plugin Required |
|--------|-----------|----------------|
| OBJ | `.obj` | — (built-in) |
| STL | `.stl` | — (built-in) |
| OFF | `.off` | — (built-in) |
| FBX | `.fbx` | qFBXIO |
| DXF | `.dxf` | — (requires CV_DXF_SUPPORT) |
| glTF (import only) | `.gltf`, `.glb` | qMeshIO |
| DAE (import only) | `.dae` | qMeshIO |
| 3DS (import only) | `.3ds` | qMeshIO |

## Platform Notes

| Platform | Binary Name | Auto-Discovery |
|----------|------------|----------------|
| Linux | `ACloudViewer.sh`, `ACloudViewer` | PATH, `/usr/local/bin`, `/opt/ACloudViewer`, `~/.local/share/ACloudViewer` |
| macOS | `ACloudViewer` | PATH, `/Applications/ACloudViewer.app`, `~/Applications/ACloudViewer.app` |
| Windows | `ACloudViewer.bat`, `ACloudViewer.exe` | PATH, `%PROGRAMFILES%\ACloudViewer`, `%LOCALAPPDATA%\ACloudViewer` |

On all platforms, set `ACV_BINARY` environment variable to override auto-discovery.

### Platform-specific format availability

- **LAS FWF** (full waveform): Windows only (`qLASFWF` plugin)
- **STEP/STP** import: Requires OpenCASCADE (varies by build)
- **GDAL rasters** (`.tif`, `.tiff`): Requires `CV_GDAL_SUPPORT` build flag
- **SHP**: Requires `CV_SHP_SUPPORT` build flag
- **SIBR tools**: Not available on macOS

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest cli_anything/acloudviewer/tests/ -v
```

Test suite: ~592 tests covering CLI structure, format maps, backend logic, RPC client wrappers (20 new cloud analysis/SF/normals wrappers), MCP tool registration (121 tools), and session management.

## Methodology

Built following the
[CLI-Anything HARNESS methodology](https://github.com/Asher-1/CLI-Anything/blob/main/cli-anything-plugin/HARNESS.md).
