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

## Core Domains

| Domain | Module | Key Operations |
|--------|--------|----------------|
| File I/O | `backend.py` | open (GUI), convert (headless), batch-convert (headless), export |
| Processing | `backend.py` | subsample (headless), normals (headless), ICP (headless), SOR (headless), crop (headless) |
| Analysis | `backend.py` | C2C distance (headless), C2M distance (headless), density (headless), curvature (headless), roughness (headless) |
| Reconstruction | `backend.py` | Delaunay triangulation (headless), mesh sampling (headless) |
| Colorization | `rpc_client.py` | paintUniform, paintByHeight, paintByScalarField (GUI only) |
| Scene | `rpc_client.py` | list (GUI), info (GUI), remove (GUI), visibility (GUI), select (GUI) |
| View | `rpc_client.py` | screenshot (GUI), camera (GUI), orientation (GUI), zoom (GUI) |
| Session | `session.py` | undo/redo with snapshot stack (general) |

### Processing Commands (15 operations)

All headless operations invoke the ACloudViewer binary with
CloudCompare-compatible CLI flags:

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
| `transform` (headless) | `-APPLY_TRANS <matrix>` | Apply 4x4 transformation matrix |
| `convert` (headless) | `-O <in> -C_EXPORT_FMT <fmt>` | Format conversion (40+ formats) |

### Supported Formats (40+)

**Point Cloud:** `.ply` `.pcd` `.xyz` `.xyzrgb` `.pts` `.txt` `.asc`
`.csv` `.las` `.laz` `.e57` `.ptx` `.bin` `.sbf`

**Mesh:** `.obj` `.stl` `.off` `.gltf` `.glb` `.fbx` `.dae` `.3ds`
`.dxf` `.vtk` `.ply`

**Image:** `.png` `.jpg` `.bmp` `.tif`

**Special:** `.drc` (Draco) `.ifc` `.stp` `.step` (CAD)

### JSON-RPC API (33 methods)

GUI-mode RPC methods exposed by the `qJSonRPCPlugin`:

| Category | Methods |
|----------|---------|
| File I/O | `open`, `export`, `file.convert` |
| Scene | `scene.list`, `scene.info`, `scene.remove`, `scene.setVisible`, `scene.select`, `clear` |
| Entity | `entity.rename`, `entity.setColor` |
| Cloud | `cloud.computeNormals`, `cloud.subsample`, `cloud.crop`, `cloud.getScalarFields`, `cloud.paintUniform`, `cloud.paintByHeight`, `cloud.paintByScalarField` |
| Mesh | `mesh.simplify`, `mesh.smooth`, `mesh.subdivide`, `mesh.samplePoints` |
| View | `view.setOrientation`, `view.zoomFit`, `view.refresh`, `view.setPerspective`, `view.setPointSize`, `view.screenshot`, `view.getCamera` |
| Transform | `transform.apply` |
| Introspection | `methods.list`, `ping` |

### Reconstruction Commands (14 operations via Colmap binary)

The `reconstruct` subgroup invokes the Colmap binary for image-based 3D
reconstruction:

| Command | Colmap Command | Description |
|---------|---------------|-------------|
| `auto` (headless) | `automatic_reconstructor` | End-to-end pipeline from images |
| `extract-features` (headless) | `feature_extractor` | Detect SIFT features |
| `match` (headless) | `*_matcher` | Match features (exhaustive/sequential/vocab-tree/spatial) |
| `sparse` (headless) | `mapper` | Incremental or hierarchical SfM |
| `undistort` (headless) | `image_undistorter` | Prepare dense workspace |
| `dense-stereo` (headless) | `patch_match_stereo` | Multi-view stereo depth maps |
| `fuse` (headless) | `stereo_fusion` | Fuse depth maps to point cloud |
| `poisson` (headless) | `poisson_mesher` | Poisson surface reconstruction |
| `delaunay-mesh` (headless) | `delaunay_mesher` | Delaunay + visibility meshing |
| `simplify-mesh` (headless) | `mesh_simplifier` | QEM mesh simplification |
| `texture-mesh` (headless) | `mesh_texturer` | Multi-view texture atlas |
| `convert-model` (headless) | `model_converter` | Export to PLY/NVM/Bundler/etc. |
| `analyze-model` (headless) | `model_analyzer` | Model statistics |
| `mesh` (headless) | ACloudViewer `-DELAUNAY` | Point cloud Delaunay (no images) |

Binary discovery for Colmap: `COLMAP_PATH` env var > `colmap`/`Colmap` on
`$PATH` > standard install locations per platform. On macOS, automatically
resolves `Colmap.app/Contents/MacOS/Colmap` bundles inside ACloudViewer
installs (`Contents/Resources/Colmap/Colmap.app/Contents/MacOS`).
Colmap now supports full CLI mode on all platforms including macOS.

### MCP Server (39 tools)

The MCP server exposes tools for AI agent frameworks (OpenClaw, Cursor,
Claude Code):

| Category | Tools |
|----------|-------|
| File I/O | `open_file`, `convert_format`, `batch_convert`, `list_formats` |
| Processing | `subsample`, `compute_normals`, `icp_registration`, `sor_filter`, `crop` |
| Analysis | `c2c_distance`, `c2m_distance`, `density`, `curvature`, `roughness` |
| Mesh | `delaunay`, `sample_mesh` |
| Colorization | `color_banding` |
| Scene (GUI) | `scene_list`, `scene_info` |
| View (GUI) | `screenshot`, `get_camera` |
| Utility | `get_info`, `list_rpc_methods` |
| Reconstruction (Colmap) | `colmap_auto_reconstruct`, `colmap_extract_features`, `colmap_match_features`, `colmap_sparse_reconstruct`, `colmap_undistort`, `colmap_dense_stereo`, `colmap_stereo_fusion`, `colmap_poisson_mesh`, `colmap_delaunay_mesh`, `colmap_image_texturer`, `colmap_model_converter`, `colmap_analyze_model` |
| SIBR | `sibr_prepare_colmap`, `sibr_texture_mesh`, `sibr_tool`, `sibr_unwrap_mesh` |

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
