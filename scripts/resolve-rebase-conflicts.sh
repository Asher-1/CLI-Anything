#!/usr/bin/env bash
# Resolve common rebase/merge conflicts for Asher-1/CLI-Anything fork.
# During rebase onto upstream/main:
#   --ours   = upstream (base)
#   --theirs = fork commit being replayed

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}==>${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }

if ! git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1 && [[ ! -d .git/rebase-merge && ! -d .git/rebase-apply ]]; then
  echo "No merge/rebase in progress; nothing to resolve."
  exit 0
fi

conflicted() {
  git diff --name-only --diff-filter=U
}

resolve_take_upstream() {
  local file="$1"
  git checkout --ours -- "$file"
  git add -- "$file"
  ok "upstream base: $file"
}

resolve_take_fork() {
  local file="$1"
  git checkout --theirs -- "$file"
  git add -- "$file"
  ok "fork version: $file"
}

resolve_remove_openclaw() {
  if [[ -d openclaw-skill ]]; then
    git rm -rf openclaw-skill 2>/dev/null || rm -rf openclaw-skill
    ok "removed deprecated openclaw-skill/"
  fi
  if git diff --name-only --diff-filter=U | grep -q '^openclaw-skill/'; then
    git rm -rf openclaw-skill 2>/dev/null || true
    git add -A openclaw-skill 2>/dev/null || true
  fi
}

info "Auto-resolving fork rebase conflicts..."
mapfile -t files < <(conflicted)
if [[ ${#files[@]} -eq 0 ]]; then
  ok "No conflicted files"
  exit 0
fi

for file in "${files[@]}"; do
  case "$file" in
    registry.json)
      resolve_take_upstream "$file"
      ;;
    .gitignore)
      resolve_take_upstream "$file"
      ;;
    .github/PULL_REQUEST_TEMPLATE.md|CONTRIBUTING.md|README.md|README_CN.md|README_JA.md)
      resolve_take_upstream "$file"
      ;;
    .github/scripts/generate_meta_skill.py)
      resolve_take_upstream "$file"
      ;;
    docs/hub/index.html|docs/hub/SKILL.md)
      resolve_take_upstream "$file"
      ;;
    cli-anything-plugin/HARNESS.md|cli-anything-plugin/README.md|cli-anything-plugin/repl_skin.py)
      resolve_take_upstream "$file"
      ;;
    cli-hub-meta-skill/SKILL.md)
      resolve_take_upstream "$file"
      ;;
    browser/agent-harness/*)
      resolve_take_upstream "$file"
      ;;
    */agent-harness/setup.py)
      resolve_take_upstream "$file"
      ;;
    openclaw-skill/SKILL.md)
      resolve_remove_openclaw
      ;;
    .github/workflows/check-upstream.yml)
      resolve_take_fork "$file"
      ;;
    sync-upstream.sh|.sync-config.json|SYNC_*.md|Makefile|.gitattributes|scripts/*)
      resolve_take_fork "$file"
      ;;
    acloudviewer/*)
      resolve_take_fork "$file"
      ;;
    *)
      info "Manual review suggested: $file (defaulting to upstream base)"
      resolve_take_upstream "$file"
      ;;
  esac
done

resolve_remove_openclaw
ok "Conflict auto-resolution pass complete"
