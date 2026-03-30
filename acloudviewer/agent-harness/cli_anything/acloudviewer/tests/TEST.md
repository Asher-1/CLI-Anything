# ACloudViewer CLI — Test Plan & Results

## Test Architecture

| Layer | What it tests | File(s) |
|-------|--------------|---------|
| **Unit tests** | Session, format sets, binary discovery, backend static methods, format conversion dispatch, version detection | `test_core.py` |
| **Backend mocks** | RPC client, backend methods, convert, batch-convert, processing, SIBR, Colmap | `test_utils.py`, `test_backend.py` |
| **CLI structure** | `--help` output, subcommand availability, JSON mode, comprehensive CLI coverage | `test_cli.py`, `test_cli_comprehensive.py` |
| **Installer** | Platform detection, asset matching, download, Qt IFW install | `test_installer.py` |
| **MCP server** | Tool registration, schema validation, tool dispatch | `test_mcp.py` |
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

## Test Coverage (592 tests)

| File | What it covers | Count |
|------|---------------|-------|
| `test_utils.py` | RPC client, backend methods, convert, batch-convert, processing, SIBR, Colmap, ReplSkin | 171 |
| `test_mcp.py` | MCP tool registration, schema validation, 121 tool dispatch | 144 |
| `test_cli_comprehensive.py` | Comprehensive CLI subcommand coverage, JSON mode, help text | 141 |
| `test_core.py` | Session, Scene, Formats, FormatConversion, VersionDetection, BinaryDiscovery, ColmapBackend, RPCClient, BackendMode | 96 |
| `test_installer.py` | Platform detection, asset matching, download, Qt IFW, --from-file | 81 |
| `test_backend.py` | Backend open/export/scene/GUI-only methods | 39 |
| `test_cli.py` | CLI help, subcommands, process, session, headless mode | 38 |
| `test_e2e.py` | E2E with real ACloudViewer binary (skipped if not installed) | 16 |

---

## Latest Test Results (2026-03-30)

```
$ python -m pytest cli_anything/acloudviewer/tests/ -v --tb=short

============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0

592 passed in 10.36s
```

### Notes

- **592 tests passed** — all core functionality fully tested
- **121 MCP tools verified** — full tool registration and schema validation
- **Format conversion**: ASC mapping, alias extension lookup, VTK dual-format, cross-type (cloud↔mesh)
- **Version detection**: maintenancetool, .desktop, CHANGELOG, --version fallback chain
- **Installer**: Platform detection, Qt IFW headless install, --from-file, curl/wget download
- **Reconstruction**: Colmap pipeline (13 tools), SIBR workflows (12 tools)
- **CLI**: info, check, formats, session, all with JSON output
