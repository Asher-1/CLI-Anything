#!/usr/bin/env bash
# Sync CLI-Anything fork with upstream and apply Asher-1-specific adaptation.
#
# Usage:
#   ./scripts/sync-upstream-adapt.sh                  # rebase + adapt + verify
#   ./scripts/sync-upstream-adapt.sh --adapt-only     # adapt current tree only
#   ./scripts/sync-upstream-adapt.sh --verify-only   # isolation checks only
#   ./scripts/sync-upstream-adapt.sh --yes --push     # non-interactive + push

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UPSTREAM_REPO="https://github.com/HKUDS/CLI-Anything.git"
MAIN_BRANCH="main"
BACKUP_BRANCH="backup-before-sync-$(date +%Y%m%d-%H%M%S)"

STRATEGY="rebase"
DO_PUSH=false
AUTO_YES=false
ADAPT_ONLY=false
VERIFY_ONLY=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}==>${NC} $1"; }
print_ok() { echo -e "${GREEN}✓${NC} $1"; }
print_warn() { echo -e "${YELLOW}!${NC} $1"; }
print_err() { echo -e "${RED}✗${NC} $1"; }

confirm() {
  local prompt="$1"
  if [[ "$AUTO_YES" == true ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

usage() {
  cat <<'EOF'
Asher-1 CLI-Anything upstream sync + adaptation tool

Usage:
  ./scripts/sync-upstream-adapt.sh [options]

Options:
  --rebase         Rebase fork commits onto upstream/main (default)
  --merge          Merge upstream/main instead of rebase
  --adapt-only     Run post-sync adaptation on current working tree
  --verify-only    Run fork isolation verification
  --yes            Non-interactive (auto-confirm prompts)
  --push           Push to origin/main with --force-with-lease after success
  --help           Show this help

Typical workflow:
  1. ./scripts/sync-upstream-adapt.sh --yes
  2. Review git diff / run tests
  3. ./scripts/sync-upstream-adapt.sh --yes --push

Recovery:
  git checkout main
  git reset --hard backup-before-sync-YYYYMMDD-HHMMSS
EOF
}

require_clean_tree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    print_err "Working tree is not clean. Commit or stash changes first."
    git status -sb
    exit 1
  fi
}

setup_upstream() {
  if git remote | grep -qx upstream; then
    git remote set-url upstream "$UPSTREAM_REPO"
  else
    git remote add upstream "$UPSTREAM_REPO"
  fi
  git fetch upstream
  print_ok "Fetched upstream"
}

bootstrap_conflict_tools() {
  if [[ -x scripts/resolve-rebase-conflicts.sh ]]; then
    return 0
  fi
  local backup
  backup="$(git for-each-ref --sort=-creatordate --format='%(refname:short)' refs/heads/backup-before-sync-* | head -1 || true)"
  if [[ -n "$backup" ]]; then
    print_warn "Bootstrapping scripts/ from $backup for conflict resolution"
    git checkout "$backup" -- scripts/ 2>/dev/null || true
    chmod +x scripts/*.sh scripts/post-sync-adapt.py 2>/dev/null || true
  fi
}

run_adaptation() {
  print_step "Running post-sync adaptation..."
  python3 scripts/post-sync-adapt.py
  bash scripts/verify-fork-isolation.sh
  print_ok "Adaptation and verification complete"
}

continue_rebase_loop() {
  local max_rounds=20
  local round=0
  bootstrap_conflict_tools
  while [[ $round -lt $max_rounds ]]; do
    if [[ ! -d .git/rebase-merge && ! -d .git/rebase-apply ]]; then
      return 0
    fi
    round=$((round + 1))
    print_step "Rebase conflict round $round"
    bash scripts/resolve-rebase-conflicts.sh
    python3 scripts/post-sync-adapt.py
    if GIT_EDITOR=true git rebase --continue; then
      print_ok "Rebase continued"
    else
      if [[ -d .git/rebase-merge || -d .git/rebase-apply ]]; then
        print_warn "Conflicts remain; resolve manually then run:"
        echo "  bash scripts/resolve-rebase-conflicts.sh"
        echo "  python3 scripts/post-sync-adapt.py"
        echo "  git add -A && GIT_EDITOR=true git rebase --continue"
        exit 1
      fi
    fi
  done
  print_err "Exceeded rebase conflict rounds"
  exit 1
}

sync_rebase() {
  print_step "Rebasing onto upstream/$MAIN_BRANCH..."
  if git rebase "upstream/$MAIN_BRANCH"; then
    print_ok "Rebase completed without conflicts"
    return 0
  fi
  continue_rebase_loop
}

sync_merge() {
  print_step "Merging upstream/$MAIN_BRANCH..."
  if git merge "upstream/$MAIN_BRANCH" -m "Merge upstream changes from HKUDS/CLI-Anything"; then
    print_ok "Merge completed without conflicts"
    return 0
  fi
  bash scripts/resolve-rebase-conflicts.sh
  if confirm "Create merge commit now?"; then
    git commit --no-edit
  else
    print_err "Merge paused with unresolved conflicts"
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebase) STRATEGY="rebase"; shift ;;
    --merge) STRATEGY="merge"; shift ;;
    --adapt-only) ADAPT_ONLY=true; shift ;;
    --verify-only) VERIFY_ONLY=true; shift ;;
    --yes) AUTO_YES=true; shift ;;
    --push) DO_PUSH=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) print_err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ "$VERIFY_ONLY" == true ]]; then
  bash scripts/verify-fork-isolation.sh
  exit 0
fi

if [[ "$ADAPT_ONLY" == true ]]; then
  run_adaptation
  exit 0
fi

print_step "Starting upstream sync + fork adaptation"
require_clean_tree
setup_upstream

print_step "Creating backup branch: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
print_ok "Backup created: $BACKUP_BRANCH"

case "$STRATEGY" in
  rebase) sync_rebase ;;
  merge) sync_merge ;;
esac

run_adaptation

if [[ "$DO_PUSH" == true ]]; then
  if confirm "Push to origin/$MAIN_BRANCH with --force-with-lease?"; then
    git push origin "$MAIN_BRANCH" --force-with-lease
    print_ok "Push complete"
  else
    print_warn "Skipped push"
  fi
else
  print_step "Next steps:"
  echo "  git log --oneline -5"
  echo "  bash scripts/verify-fork-isolation.sh"
  echo "  ./scripts/sync-upstream-adapt.sh --yes --push"
fi

print_ok "Sync + adaptation finished"
echo "Backup branch: $BACKUP_BRANCH"
