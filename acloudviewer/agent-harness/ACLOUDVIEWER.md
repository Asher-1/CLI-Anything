# ACloudViewer: Project-Specific Analysis & SOP

## Architecture Summary

ACloudViewer is an open-source 3D point cloud and mesh processing desktop
application based on CloudCompare, Open3D, and colmap. It provides a
rich plugin system, 40+ I/O formats, and GPU-accelerated algorithms.

The CLI harness controls ACloudViewer through two complementary channels:

```
┌────────────────────────────────────────────────────────┐
│             ACloudViewer Desktop (Qt / C++)            │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │  3D Viewport     │  │  Plugin Architecture       │  │
│  │  (OpenGL / VTK)  │  │  qJSonRPC, qPCL, qSIBR…    │  │
│  └────────┬─────────┘  └─────────┬──────────────────┘  │
│           │                      │                     │
│  ┌────────┴──────────────────────┴──────────────────┐  │
│  │    ecvMainAppInterface  /  FileIOFilter          │  │
│  │    ccPointCloud · ccMesh · ccHObject             │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │                            │
│           ┌───────────────┼───────────────┐            │
│           │               │               │            │
│  ┌────────┴────┐ ┌────────┴──────┐ ┌──────┴──────────┐ │
│  │ JSON-RPC    │ │ CLI Flags     │ │ Python Bindings │ │
│  │ WebSocket   │ │ -SILENT -O…   │ │ (cloudViewer)   │ │
│  │ Port 6001   │ │ subprocess    │ │ pybind11        │ │
│  └─────────────┘ └───────────────┘ └─────────────────┘ │
└────────────────────────────────────────────────────────┘
```

The harness uses **JSON-RPC** for GUI mode and **binary subprocess** for
headless mode. It does NOT depend on the `cloudViewer` Python package
because many plugins are only available through the desktop binary.

## CLI Strategy: Binary CLI + JSON-RPC Dual Mode

| Mode | Mechanism | Requirements |
|------|-----------|-------------|
| `gui` | JSON-RPC 2.0 over WebSocket (port 6001) | Running ACloudViewer with qJSonRPC plugin |
| `headless` | `ACloudViewer -SILENT -O … -SS …` via subprocess | ACloudViewer binary on PATH |
| `auto` | Try GUI RPC, fall back to headless binary | Either |

### Binary Discovery

The backend finds the ACloudViewer binary through (in priority order):
1. `ACV_BINARY` environment variable (explicit path)
2. Platform-appropriate names on `$PATH`:
   - **Linux:** `ACloudViewer.sh`, `ACloudViewer`
   - **macOS:** `ACloudViewer` (standalone or inside .app bundle)
   - **Windows:** `ACloudViewer.bat`, `ACloudViewer.exe`
3. Standard install directories per OS:
   - **Linux:** `/usr/local/bin`, `/opt/ACloudViewer/bin`, `~/.local/share/ACloudViewer/bin`, `~/ACloudViewer`
   - **macOS:** `/Applications/ACloudViewer.app/Contents/MacOS`, `~/Applications/ACloudViewer.app/Contents/MacOS`, `~/ACloudViewer/bin/ACloudViewer.app/Contents/MacOS`, `/usr/local/bin`
   - **Windows:** `%PROGRAMFILES%\ACloudViewer`, `%LOCALAPPDATA%\ACloudViewer`, `~\ACloudViewer`
4. macOS `.app` bundle resolution: when a search directory contains `ACloudViewer.app`, automatically resolves to `ACloudViewer.app/Contents/MacOS/ACloudViewer`

When a bare binary (not `.sh`/`.bat`) is found, the backend automatically
sets platform-appropriate library paths (`LD_LIBRARY_PATH` on Linux,
`DYLD_LIBRARY_PATH` on macOS, `PATH` on Windows) and `PYTHONPATH`.

### Auto-Install & Diagnostics (`utils/installer.py`)

When the binary is not found, the CLI provides interactive installation
guidance and automated download/install:

```
Binary not found ──→ Interactive TTY? ──yes──→ Prompt: Install now? [Y/n]
                              │                     ├─→ Channel: stable / beta
                              │                     ├─→ Variant: CUDA / CPU-only
                              │                     └─→ Download + Qt IFW install
                              │
                              └── no (pipe/script) ──→ Raise BackendError with
                                                       3 fix options + URLs
```

**Platform detection** (`detect_platform()`): Identifies OS, distro, version,
arch, Python version, glibc version, and NVIDIA GPU presence.

**Asset matching**: Queries GitHub Releases API, matches the correct installer
(`.run`/`.dmg`/`.exe`) or Python wheel (`.whl`) based on platform info.

**Installer formats supported**:

| Format | Platform | Mechanism |
|--------|----------|-----------|
| `.run` (Qt IFW) | Linux | `<installer> in --accept-licenses --confirm-command --root <dir>` |
| `.run` (makeself) | Linux | `<installer> --noexec --target <dir>` |
| `.dmg` | macOS | `hdiutil attach` → run embedded Qt IFW installer |
| `.exe` | Windows | `<installer> in --accept-licenses --confirm-command --root <dir>` |

**CLI commands**:

| Command | Description |
|---------|-------------|
| `check` (general) | Diagnose installation status (text or JSON) |
| `install app` (general) | Download + install from GitHub (stable/beta, CUDA/CPU) |
| `install app --from-file <path>` (general) | Silent install from local `.run`/`.dmg`/`.exe` |
| `install wheel` (general) | Download + install `cloudViewer` Python package |
| `install auto` (general) | Detect and install all missing components |

**Download strategy**: Prefers `curl` (with retry/progress) > `wget` > `urllib`
fallback, to handle slow or unreliable GitHub CDN connections.

### Version Detection (`get_version()`)

The backend resolves the installed ACloudViewer version through multiple
strategies (in priority order):

```
Binary found ──→ --version / -v flag ──→ Parse "X.Y.Z" from stdout
                        │ (fails)
                        ├─→ maintenancetool li ──→ Parse version="X.Y.Z" from XML
                        │ (not found)
                        ├─→ ACloudViewer.desktop ──→ Parse Version= line
                        │ (not found)
                        ├─→ CHANGELOG.txt / .md ──→ Regex first "X.Y.Z" in header
                        │ (not found)
                        └─→ None
```

The `check` command uses this to report installed version in both text and
JSON output (e.g. `"version": "3.9.5"`).

### Format Conversion Internals (`convert_format()`)

**CLI export format tokens**: ACloudViewer CLI uses `-C_EXPORT_FMT` tokens
that differ from file extensions. Key mapping (`CLOUD_FORMAT_MAP`):

| Extension | CLI Token | Note |
|-----------|-----------|------|
| `.ply` | `PLY` | |
| `.pcd` | `PCD` | |
| `.las`/`.laz` | `LAS` | |
| `.e57` | `E57` | |
| `.vtk` | `VTK` | Also in `MESH_FORMAT_MAP` — dual-format |
| `.asc` | `ASC` | **Not** `ASCII` (ACloudViewer rejects `ASCII`) |
| `.xyz`/`.csv`/`.txt`/`.pts` | `ASC` | All map to `ASC`; output renamed via alias lookup |

**Alias extension lookup** (`_FORMAT_ALIAS_EXTS`): When the CLI writes
`.asc` but the user requested `.xyz`, the post-convert step searches for
alias extensions and renames the output file.

**Cross-type automatic conversion**: The `convert` command handles all four
input/output type combinations transparently:

| Input → Output | Mechanism | CLI Flags |
|---------------|-----------|-----------|
| cloud → cloud | Direct export | `-C_EXPORT_FMT <fmt> -SAVE_CLOUDS` |
| mesh → mesh | Direct export | `-M_EXPORT_FMT <fmt> -SAVE_MESHES` |
| cloud → mesh | Auto Delaunay | `-DELAUNAY -M_EXPORT_FMT <fmt> -SAVE_MESHES` |
| mesh → cloud | Auto sampling | `-SAMPLE_MESH POINTS <n> -C_EXPORT_FMT <fmt> -SAVE_CLOUDS` |

Dispatch priority for dual-format extensions (e.g. `.ply`, `.vtk`):
cloud→cloud > cloud→mesh > mesh→cloud > mesh→mesh.

## Core Domains

| Domain | Module | Key Operations |
|--------|--------|----------------|
| File I/O | `backend.py` | open (GUI), convert (headless), batch-convert (headless), export (GUI) |
| Processing | `backend.py` | subsample, normals, ICP, SOR, crop, rasterize (headless) |
| Scalar Fields | `backend.py` | set/remove/rename/filter SF, arithmetic, gradient, color scale, coord-to-SF (headless + GUI) |
| Advanced Normals | `backend.py` | octree normals, orient MST, invert, clear, normals-to-dip, normals-to-SFs (headless + GUI) |
| Analysis | `backend.py` | C2C distance, C2M distance, density, curvature, roughness, geometric features (headless) |
| Geometry | `backend.py` | connected components, best-fit plane, moment, closest point set (headless) |
| Reconstruction | `backend.py` | Delaunay triangulation, mesh sampling (headless) |
| Mesh Operations | `backend.py` + `rpc_client.py` | volume, extract vertices, flip triangles, simplify, smooth, subdivide, sample (headless + GUI) |
| Merge & Cleanup | `backend.py` | merge clouds/meshes, remove RGB, match centers, drop shift, remove scan grids (headless + GUI) |
| Colmap 3D Reconstruction | `colmap_backend.py` | feature extraction, matching, sparse/dense SfM, meshing, texturing (13 tools, headless) |
| SIBR Dataset Tools | `backend.py` | prepare Colmap, texture mesh, unwrap, tonemapper, camera converter (11 tools, headless) |
| Colorization | `rpc_client.py` | paintUniform, paintByHeight, paintByScalarField (GUI only) |
| Scene | `rpc_client.py` | list, info, remove, visibility, select, clear (GUI only) |
| Entity | `rpc_client.py` | rename, setColor (GUI only) |
| View | `rpc_client.py` | screenshot, camera, orientation, zoom, refresh, perspective, point size (GUI only) |
| Transform | `backend.py` + `rpc_client.py` | apply 4x4 matrix (GUI + file-based headless) |
| Session | `session.py` | undo/redo with snapshot stack (general) |

### Processing Commands (50+ operations)

All headless operations invoke the ACloudViewer binary with
CloudCompare-compatible CLI flags:

#### Basic Processing (15 operations)
| Command | CLI Flags | Description |
|---------|-----------|-------------|
| `subsample` (headless) | `-SS SPATIAL <step>` | Spatial / random / octree subsampling |
| `normals` (headless) | `-OCTREE_NORMALS <radius>` | Normal estimation |
| `icp` (headless) | `-ICP` | Iterative Closest Point registration |
| `sor` (headless) | `-SOR <knn> <sigma>` | Statistical outlier removal |
| `c2c-dist` (headless) | `-C2C_DIST` | Cloud-to-cloud distance computation |
| `c2m-dist` (headless) | `-C2M_DIST` | Cloud-to-mesh distance computation |
| `density` (headless) | `-DENSITY <radius>` | Local density computation |
| `curvature` (headless) | `-CURV <type> <radius>` | Mean or Gaussian curvature |
| `roughness` (headless) | `-ROUGH <radius>` | Surface roughness |
| `delaunay` (headless) | `-DELAUNAY` | Delaunay 2.5D triangulation |
| `sample-mesh` (headless) | `-SAMPLE_MESH POINTS <n>` | Uniform mesh surface sampling |
| `color-banding` (headless) | `-COLOR_BANDING <dim> <freq>` | Height-based color gradient |
| `crop` (headless) | `-CROP <bounds>` | Axis-aligned bounding box crop |
| `rasterize` (headless) | `-RASTERIZE <grid>` | 2.5D rasterization to grid/mesh |
| `stat-test` (headless) | `-STAT_TEST <dist> <p>` | Statistical outlier test |

#### Scalar Field Operations (11 operations)
| Command | CLI Flags | Description |
|---------|-----------|-------------|
| `set-active-sf` (headless) | `-SET_ACTIVE_SF <idx>` | Set active scalar field by index or name |
| `remove-all-sfs` (headless) | `-REMOVE_ALL_SFS` | Remove all scalar fields from cloud |
| `remove-sf` (headless) | `-REMOVE_SF <idx>` | Remove specific scalar field by index |
| `rename-sf` (headless) | `-RENAME_SF <idx> <name>` | Rename a scalar field |
| `sf-arithmetic` (headless) | `-SF_OP <op>` | Unary SF operation (SQRT, ABS, INV, etc.) |
| `sf-operation` (headless) | `-SF_OP <op> <val>` | Binary SF operation with scalar (ADD, SUB, etc.) |
| `coord-to-sf` (headless) | `-COORD_TO_SF <dim>` | Export X/Y/Z coordinate as scalar field |
| `sf-gradient` (headless) | `-SF_GRADIENT` | Compute scalar field gradient |
| `filter-sf` (headless) | `-FILTER_SF <min> <max>` | Filter points by SF value range |
| `sf-color-scale` (headless) | `-SF_COLOR_SCALE <file>` | Apply color scale file to active SF |
| `sf-convert-to-rgb` (headless) | `-SF_CONVERT_TO_RGB` | Convert active SF values to RGB colors |

#### Advanced Normal Operations (6 operations)
| Command | CLI Flags | Description |
|---------|-----------|-------------|
| `octree-normals` (headless) | `-OCTREE_NORMALS <radius>` | Compute normals with octree method |
| `orient-normals-mst` (headless) | `-ORIENT_NORMS_MST <knn>` | Orient normals via Minimum Spanning Tree |
| `invert-normals` (headless) | `-INVERT_NORMALS` | Flip all normal directions |
| `clear-normals` (headless) | `-CLEAR_NORMALS` | Remove all normals from cloud |
| `normals-to-dip` (headless) | `-NORMALS_TO_DIP` | Convert normals to dip/dip-direction SFs |
| `normals-to-sfs` (headless) | `-NORMALS_TO_SFS` | Convert normals to Nx/Ny/Nz scalar fields |

#### Geometry Analysis (6 operations)
| Command | CLI Flags | Description |
|---------|-----------|-------------|
| `extract-cc` (headless) | `-EXTRACT_CC <level> <min>` | Extract connected components |
| `approx-density` (headless) | `-APPROX_DENSITY <type>` | Approximate point density |
| `feature` (headless) | `-FEATURE <type> <size>` | Geometric features (14 types) |
| `moment` (headless) | `-MOMENT <size>` | 1st order moment computation |
| `best-fit-plane` (headless) | `-BEST_FIT_PLANE` | Compute best fit plane |
| `closest-point-set` (headless) | `-CLOSEST_POINT_SET` | Closest point set between clouds |

#### Mesh Operations (6 operations)
| Command | CLI Flags | Description |
|---------|-----------|-------------|
| `mesh-volume` (headless) | `-MESH_VOLUME` | Compute mesh enclosed volume |
| `extract-vertices` (headless) | `-EXTRACT_VERTICES` | Extract mesh vertices to point cloud |
| `flip-triangles` (headless) | `-FLIP_TRI` | Flip mesh triangle normals |
| `merge-clouds` (headless) | `-MERGE_CLOUDS` | Merge multiple point clouds into one |
| `merge-meshes` (headless) | `-MERGE_MESHES` | Merge multiple meshes into one |
| `transform` (headless) | `-APPLY_TRANS <file>` | Apply 4x4 transformation matrix from file |

#### Cleanup Operations (5 operations)
| Command | CLI Flags | Description |
|---------|-----------|-------------|
| `remove-rgb` (headless) | `-REMOVE_RGB` | Remove RGB color data |
| `remove-scan-grids` (headless) | `-REMOVE_SCAN_GRIDS` | Remove scan grid information |
| `match-centers` (headless) | `-MATCH_BBOX_CENTERS` | Match bounding-box centers of entities |
| `drop-global-shift` (headless) | `-DROP_GLOBAL_SHIFT` | Remove global coordinate shift |
| `convert` (headless) | `-O <in> -C_EXPORT_FMT <fmt>` | Format conversion (40+ formats) |

### Supported Formats (40+)

**Point Cloud:** `.ply` `.pcd` `.xyz` `.xyzn` `.xyzrgb` `.pts` `.txt`
`.asc` `.neu` `.csv` `.las` `.laz` `.e57` `.ptx` `.bin` `.sbf` `.drc` `.vtk`

**Mesh:** `.obj` `.stl` `.off` `.gltf` `.glb` `.fbx` `.dae` `.3ds`
`.dxf` `.vtk` `.ply`

**Image:** `.png` `.jpg` `.bmp` `.tif`

**Special:** `.drc` (Draco) `.ifc` `.stp` `.step` (CAD)

### JSON-RPC API (48+ methods)

GUI-mode RPC methods exposed by the `qJSonRPCPlugin`:

| Category | Methods |
|----------|---------|
| File I/O | `open`, `export`, `file.convert` |
| Scene | `scene.list`, `scene.info`, `scene.remove`, `scene.setVisible`, `scene.select`, `scene.clear` |
| Entity | `entity.rename`, `entity.setColor` |
| Cloud Processing | `cloud.computeNormals`, `cloud.subsample`, `cloud.crop` |
| Cloud Scalar Fields | `cloud.getScalarFields`, `cloud.setActiveSf`, `cloud.removeSf`, `cloud.removeAllSfs`, `cloud.renameSf`, `cloud.filterSf`, `cloud.coordToSf` |
| Cloud Painting | `cloud.paintUniform`, `cloud.paintByHeight`, `cloud.paintByScalarField` |
| Cloud Geometry | `cloud.removeRgb`, `cloud.removeNormals`, `cloud.invertNormals`, `cloud.merge` |
| Mesh Operations | `mesh.simplify`, `mesh.smooth`, `mesh.subdivide`, `mesh.samplePoints`, `mesh.extractVertices`, `mesh.flipTriangles`, `mesh.volume`, `mesh.merge` |
| View Control | `view.setOrientation`, `view.zoomFit`, `view.refresh`, `view.setPerspective`, `view.setPointSize`, `view.screenshot`, `view.getCamera` |
| Transform | `transform.apply` |
| Colmap (GUI) | `colmap.reconstruct`, `colmap.run` |
| Introspection | `methods.list`, `ping` |

### Colmap 3D Reconstruction Commands (13 operations)

The `reconstruct` subgroup invokes the Colmap binary for image-based 3D
reconstruction:

| Command | Colmap Command | Description |
|---------|---------------|-------------|
| `auto` (headless) | `automatic_reconstructor` | End-to-end pipeline from images (feature extraction → sparse → dense → meshing) |
| `extract-features` (headless) | `feature_extractor` | Detect SIFT features from images |
| `match` (headless) | `*_matcher` | Match features (exhaustive/sequential/vocab-tree/spatial) |
| `sparse` (headless) | `mapper` | Incremental or hierarchical Structure-from-Motion |
| `undistort` (headless) | `image_undistorter` | Undistort images and prepare dense workspace |
| `dense-stereo` (headless) | `patch_match_stereo` | PatchMatch multi-view stereo depth map generation |
| `fuse` (headless) | `stereo_fusion` | Fuse depth maps into dense colored point cloud |
| `poisson` (headless) | `poisson_mesher` | Poisson surface reconstruction from point cloud |
| `delaunay-mesh` (headless) | `delaunay_mesher` | Delaunay triangulation with visibility constraints |
| `texture-mesh` (headless) | `image_texturer` | Generate multi-view texture atlas for mesh |
| `convert-model` (headless) | `model_converter` | Export sparse model to PLY/NVM/Bundler/VRML/etc. |
| `analyze-model` (headless) | `model_analyzer` | Analyze sparse model and report statistics |
| `run` (headless/GUI) | Any Colmap subcommand | Generic executor for all 44 Colmap subcommands |

**Binary discovery for Colmap**: `COLMAP_PATH` env var > `colmap`/`Colmap` on
`$PATH` > standard install locations per platform. On macOS, automatically
resolves `Colmap.app/Contents/MacOS/Colmap` bundles inside ACloudViewer
installs (`Contents/Resources/Colmap/Colmap.app/Contents/MacOS`).
Colmap now supports full CLI mode on all platforms including macOS.

**Auto-reconstruction quality settings**:
- `low`: Fast preview (max 1024px images)
- `medium`: Balanced (max 2048px images)
- `high`: High quality (max 4096px images, default)
- `extreme`: Maximum quality (no size limit, very slow)

### SIBR Dataset Preparation Tools (12 operations)

SIBR (Structure-based Image-Based Rendering) tools for preprocessing Colmap
reconstructions for novel view synthesis and rendering:

| Command | SIBR Tool | Description |
|---------|-----------|-------------|
| `prepare-colmap` (headless) | `prepareColmap4Sibr` | Convert Colmap reconstruction to SIBR dataset format |
| `texture-mesh` (headless) | `textureMesh` | Generate textured mesh from SIBR dataset |
| `unwrap-mesh` (headless) | `unwrapMesh` | UV-unwrap mesh for texture mapping |
| `tonemapper` (headless) | `tonemapper` | Apply tonemapping to HDR images in dataset |
| `align-meshes` (headless) | `alignMeshes` | Align multiple meshes in the dataset |
| `camera-converter` (headless) | `cameraConverter` | Convert camera formats for SIBR compatibility |
| `nvm-to-sibr` (headless) | `nvmToSIBR` | Convert VisualSFM NVM format to SIBR layout |
| `crop-from-center` (headless) | `cropFromCenter` | Crop dataset around a center point |
| `clipping-planes` (headless) | `clippingPlanes` | Compute or apply scene clipping planes |
| `distord-crop` (headless) | `distordCrop` | Apply distortion-aware image cropping |
| `viewer` (headless) | SIBR viewers | Launch SIBR viewer for novel view synthesis (gaussian, ulr, ulrv2, texturedmesh, pointbased, remoteGaussian) |
| `tool` (headless) | Any SIBR tool | Generic executor for any SIBR dataset tool by name |

**Viewer types**:
- **gaussian**: Gaussian Splatting viewer (requires model path and dataset)
- **ulr/ulrv2**: Unstructured Lumigraph Rendering viewers
- **texturedmesh**: Textured mesh viewer (requires mesh file)
- **pointbased**: Point-based rendering viewer
- **remoteGaussian**: Remote Gaussian viewer (network rendering)

**Note**: SIBR tools are not available on macOS. Requires ACloudViewer built with
`-DPLUGIN_STANDARD_QSIBR=ON` CMake flag.

### MCP Server (178 tools)

The MCP server exposes 178 tools for AI agent frameworks (OpenClaw, Cursor,
Claude Code):

| Category | Count | Tools |
|----------|-------|-------|
| **File I/O** | 5 | `open_file`, `convert_format`, `batch_convert`, `list_formats`, `export_entity` |
| **Processing** | 10 | `subsample`, `compute_normals`, `sor_filter`, `crop`, `density`, `curvature`, `roughness`, `color_banding`, `stat_test`, `rasterize` |
| **Scalar Fields** | 18 | `set_active_sf`, `remove_all_sfs`, `remove_sf`, `rename_sf`, `sf_arithmetic`, `sf_operation`, `coord_to_sf`, `sf_gradient`, `filter_sf`, `sf_color_scale`, `sf_convert_to_rgb`, `cloud_get_scalar_fields`, `cloud_set_active_sf`, `cloud_remove_sf`, `cloud_remove_all_sfs`, `cloud_rename_sf`, `cloud_filter_sf`, `cloud_coord_to_sf` |
| **Normals** | 8 | `octree_normals`, `orient_normals_mst`, `invert_normals`, `clear_normals`, `normals_to_dip`, `normals_to_sfs`, `cloud_remove_normals_gui`, `cloud_invert_normals_gui` |
| **Distance** | 2 | `c2c_distance`, `c2m_distance` |
| **Registration** | 1 | `icp_registration` |
| **Geometry** | 6 | `extract_connected_components`, `approx_density`, `geometric_feature`, `moment`, `best_fit_plane`, `closest_point_set` |
| **Mesh Reconstruction** | 2 | `delaunay`, `sample_mesh` |
| **Mesh Operations** | 10 | `mesh_volume`, `extract_vertices`, `flip_triangles`, `mesh_simplify`, `mesh_smooth`, `mesh_subdivide`, `mesh_sample_points`, `mesh_extract_vertices_gui`, `mesh_flip_triangles_gui`, `mesh_volume_gui` |
| **Merge** | 4 | `merge_clouds`, `merge_meshes`, `cloud_merge_gui`, `mesh_merge_gui` |
| **Cleanup** | 5 | `remove_rgb`, `remove_scan_grids`, `match_centers`, `drop_global_shift`, `cloud_remove_rgb` |
| **Plugin Processing** | 24 | `pcv`, `compass_export`, `compass_import_fol`, `compass_import_lin`, `compass_p21`, `compass_refit`, `sra`, `csf`, `ransac`, `m3c2`, `canupo`, `facets`, `hough_normals`, `poisson_recon`, `cork_boolean`, `voxfall`, `classify_3dmasc`, `treeiso`, `cloud_layers`, `animation`, `mplane`, `auto_seg`, `manual_seg`, `python_script` |
| **IO Settings** | 8 | `draco_settings`, `e57_settings`, `las_settings`, `csv_matrix_settings`, `photoscan_settings`, `mesh_io_settings`, `core_io_settings`, `fbx_settings` |
| **Colorimetric Seg** | 3 | `color_seg_rgb`, `color_seg_hsv`, `color_seg_scalar` |
| **PCL Processing** | 18 | `pcl_sor`, `pcl_normal_estimation`, `pcl_mls`, `pcl_euclidean_cluster`, `pcl_sac_segmentation`, `pcl_region_growing`, `pcl_marching_cubes`, `pcl_greedy_triangulation`, `pcl_poisson_recon`, `pcl_convex_hull`, `pcl_don_segmentation`, `pcl_mincut_segmentation`, `pcl_fast_global_registration`, `pcl_extract_sift`, `pcl_projection_filter`, `pcl_general_filters`, `pcl_template_alignment`, `pcl_correspondence_matching` |
| **Misc** | 4 | `g3point`, `volume_25d`, `crop_2d`, `bundler_import` |
| **Colmap Reconstruction** | 13 | `colmap_auto_reconstruct`, `colmap_extract_features`, `colmap_match_features`, `colmap_sparse_reconstruct`, `colmap_dense_stereo`, `colmap_stereo_fusion`, `colmap_poisson_mesh`, `colmap_model_converter`, `colmap_undistort`, `colmap_delaunay_mesh`, `colmap_image_texturer`, `colmap_analyze_model`, `colmap_run` |
| **SIBR Tools** | 12 | `sibr_viewer`, `sibr_tool`, `sibr_prepare_colmap`, `sibr_texture_mesh`, `sibr_unwrap_mesh`, `sibr_tonemapper`, `sibr_align_meshes`, `sibr_camera_converter`, `sibr_nvm_to_sibr`, `sibr_crop_from_center`, `sibr_clipping_planes`, `sibr_distord_crop` |
| **Scene (GUI)** | 6 | `scene_list`, `scene_info`, `scene_remove`, `scene_set_visible`, `scene_select`, `scene_clear` |
| **Entity (GUI)** | 2 | `entity_rename`, `entity_set_color` |
| **View (GUI)** | 7 | `screenshot`, `get_camera`, `view_set_orientation`, `view_zoom_fit`, `view_refresh`, `view_set_perspective`, `view_set_point_size` |
| **Cloud Painting (GUI)** | 3 | `cloud_paint_uniform`, `cloud_paint_by_height`, `cloud_paint_by_scalar_field` |
| **Transform** | 2 | `transform_apply`, `transform_apply_file` |
| **Utility** | 2 | `get_info`, `list_rpc_methods` |

**Total**: 178 tools supporting both headless CLI and GUI RPC modes.

## RPC Robustness: Automatic Fallback

For format conversion and other operations that may fail via RPC
(e.g., when the GUI's I/O filter doesn't match), the backend implements
an automatic try-RPC-then-fallback-to-binary pattern:

```python
try:
    result = self._rpc.file_convert(input_file, output_file)
except RPCError:
    result = self._run_cli(["-O", input_file, "-C_EXPORT_FMT", ext, ...])
```

This ensures operations succeed regardless of whether the GUI is running.

## Testing Strategy

Six-level test suite covering progressively deeper integration:

| Level | Tests | What | Needs |
|-------|-------|------|-------|
| 0 | Installer | Platform detection, asset matching, download, Qt IFW (61 tests, fully mocked) | None |
| 1 | C++ source | Dispatch table, header declarations, build | cmake (optional) |
| 2 | CLI harness | `--help`, subcommands, JSON output, session | CLI installed |
| 3 | Headless processing | subsample, normals, formats, binary load | ACloudViewer binary |
| 4 | GUI RPC | ping, methods.list, scene.list, camera | Running ACloudViewer |
| 5 | MCP server | tool count, tool names, entry point | MCP SDK |
