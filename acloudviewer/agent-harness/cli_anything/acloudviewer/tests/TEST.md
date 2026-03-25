# ACloudViewer CLI — Test Plan & Results

## Test Architecture

| Layer | What it tests | File |
|-------|--------------|------|
| **Unit tests** | Session, format sets, binary discovery, backend static methods | `test_core.py` |
| **CLI structure** | `--help` output, subcommand availability, JSON mode | `test_cli.py` |
| **E2E tests** | Real ACloudViewer binary invocation with sample data | `test_e2e.py` |

## Running Tests

```bash
cd acloudviewer/agent-harness
pip install -e ".[dev]"

# Unit + CLI structure (no ACloudViewer binary needed)
python -m pytest cli_anything/acloudviewer/tests/test_core.py cli_anything/acloudviewer/tests/test_cli.py -v

# E2E (requires ACloudViewer binary on PATH or ACV_BINARY set)
python -m pytest cli_anything/acloudviewer/tests/test_e2e.py -v

# All tests
python -m pytest cli_anything/acloudviewer/tests/ -v
```

## Test Coverage (310 tests)

| File | Test Classes | Count |
|------|-------------|-------|
| `test_core.py` | Session, Scene, Formats, FormatConversion, VersionDetection, BinaryDiscovery, ColmapBackend, RPCClient, BackendMode | ~85 |
| `test_utils.py` | RPCClientCall, RPCClientConvenience, RPCClientNewWrappers, BackendOpenFile, BackendExportFile, BackendSceneOps, BackendGUIOnly (incl. new SF/mesh/colmap methods), BackendRunCLI, BackendConvertFormat, BackendBatchConvert, BackendProcessing, BackendSIBR, ColmapRun, ColmapBinaryDiscovery, ColmapArgConstruction, ReplSkin | ~141 |
| `test_cli.py` | CLIHelp, SubcommandHelp, ProcessSubcommands, SessionHistory, HeadlessMode | ~70 |
| `test_installer.py` | Installer commands (check, install) | ~5 |
| `test_e2e.py` | E2E with real ACloudViewer binary (skipped if not installed) | ~9 |

### New tests added for extended RPC capabilities

- `TestRPCClientNewWrappers`: 15 tests for new RPC convenience methods (cloud SF management, cloud geometry, mesh operations, colmap.run)
- `TestBackendGUIOnly` (extended): 15 new tests verifying all new GUI-only methods correctly raise `BackendError` in headless mode
- `test_call_raises_on_error_with_data`: Verifies RPCError includes structured `data` field from error responses
