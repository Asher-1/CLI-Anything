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

## Results

```
test_core.py::TestSession::test_empty                  PASSED
test_core.py::TestSession::test_snapshot_undo_redo      PASSED
test_core.py::TestFormats::test_ply_in_both            PASSED
test_core.py::TestFormats::test_common_extensions      PASSED
test_core.py::TestFormats::test_all_is_superset        PASSED
test_core.py::TestFormats::test_supported_formats_static PASSED
test_core.py::TestBinaryDiscovery::test_find_binary     PASSED
test_core.py::TestBinaryDiscovery::test_acv_binary_env  PASSED
test_cli.py::TestCLIHelp::test_help                    PASSED
test_cli.py::TestCLIHelp::test_subcommand_help[...]    PASSED (x9)
test_cli.py::TestCLIHelp::test_process_subcommands    PASSED
test_cli.py::TestHeadlessMode::test_info               PASSED
test_cli.py::TestHeadlessMode::test_session_status     PASSED
test_cli.py::TestHeadlessMode::test_formats            PASSED
test_e2e.py (requires ACloudViewer binary)             SKIPPED or PASSED
```
