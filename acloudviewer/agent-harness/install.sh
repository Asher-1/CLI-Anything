#!/usr/bin/env sh
# One-line installer for the ACloudViewer CLI/MCP harness (cli-anything-acloudviewer).
#
# Usage:
#   curl -LsSf https://raw.githubusercontent.com/Asher-1/CLI-Anything/main/acloudviewer/agent-harness/install.sh | sh
#
# What it does:
#   1. Verifies python3 (>= 3.10) is available
#   2. Installs the harness from this repository (pipx if present, else pip --user)
#   3. Runs `cli-anything-acloudviewer check`
#   4. Registers the MCP server with detected AI clients
#      (Claude Code, Claude Desktop, Codex, Cursor) via `install clients --all`
#
# Environment flags:
#   ACV_SKIP_CLIENTS=1   skip step 4 (no MCP client configs are touched)
#   ACV_PIP_ARGS="..."   extra arguments passed to pip (e.g. "--upgrade")
set -eu

REPO_URL="https://github.com/Asher-1/CLI-Anything.git"
PKG_SUBDIR="acloudviewer/agent-harness"

log() { printf '[acv] %s\n' "$*"; }
err() { printf '[acv] %s\n' "$*" >&2; }

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    err "Windows: run 'pip install cli-anything-acloudviewer' instead of this script."
    exit 1
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  err "python3 (>= 3.10) is required. Install it first: https://www.python.org/downloads/"
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  err "python3 >= 3.10 required, found $(python3 -V 2>&1)."
  exit 1
fi
log "Python $(python3 -V 2>&1 | cut -d' ' -f2) detected."

if command -v pipx >/dev/null 2>&1; then
  log "Installing harness with pipx ..."
  pipx install "git+${REPO_URL}#subdirectory=${PKG_SUBDIR}"
else
  log "Installing harness with pip --user ..."
  if ! python3 -m pip install --user ${ACV_PIP_ARGS:-} \
      "git+${REPO_URL}#subdirectory=${PKG_SUBDIR}"; then
    err "pip install failed. On externally-managed systems (PEP 668) use pipx instead:"
    err "  pipx install \"git+${REPO_URL}#subdirectory=${PKG_SUBDIR}\""
    exit 1
  fi
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) log "Note: ${HOME}/.local/bin is not on PATH; add it to call the CLI directly." ;;
  esac
fi

CLI=cli-anything-acloudviewer
if ! command -v "$CLI" >/dev/null 2>&1; then
  if [ -x "${HOME}/.local/bin/${CLI}" ]; then
    CLI="${HOME}/.local/bin/${CLI}"
  else
    err "Installed, but '${CLI}' is not on PATH. Open a new shell, then run '${CLI} check'."
    exit 1
  fi
fi

log "Running installation check ..."
"$CLI" check || true

if [ "${ACV_SKIP_CLIENTS:-0}" != "1" ]; then
  log "Registering MCP server with detected AI clients (skip: ACV_SKIP_CLIENTS=1) ..."
  "$CLI" install clients --all || true
fi

log "Done. Try: ${CLI} --json info"
