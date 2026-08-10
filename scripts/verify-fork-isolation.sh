#!/usr/bin/env bash
# Verify fork isolation — no upstream hub/skill URLs remain in tracked files.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

fail=0

check_absent() {
  local pattern="$1"
  local desc="$2"
  if rg -n "$pattern" . \
      --glob '!.git/**' \
      --glob '!SYNC_UPSTREAM.md' \
      --glob '!SYNC_README.md' \
      --glob '!scripts/**' \
      --glob '!.sync-config.json' >/tmp/fork-isolation-hits.txt 2>/dev/null; then
    echo -e "${RED}✗${NC} Found forbidden $desc:"
    cat /tmp/fork-isolation-hits.txt
    fail=1
  else
    echo -e "${GREEN}✓${NC} No forbidden $desc"
  fi
}

check_present() {
  local pattern="$1"
  local desc="$2"
  if rg -q "$pattern" registry.json 2>/dev/null; then
    echo -e "${GREEN}✓${NC} $desc"
  else
    echo -e "${RED}✗${NC} Missing $desc"
    fail=1
  fi
}

echo "Fork isolation verification"
echo "==========================="

check_absent 'hkuds\.github\.io/CLI-Anything' 'upstream GitHub Pages URLs'
check_absent 'HKUDS/CLI-Anything' 'upstream GitHub repo slug'
check_absent 'clianything\.cc' 'upstream custom hub domain'
check_absent 'digitaloceanspaces\.com/SKILL\.md' 'upstream DO Spaces skill CDN'

check_present 'Asher-1/CLI-Anything' 'fork repo in registry.json'
check_present '"name": "acloudviewer"' 'acloudviewer registry entry'

if [[ -f skills/cli-anything-acloudviewer/SKILL.md ]]; then
  echo -e "${GREEN}✓${NC} Root skill mirror exists for acloudviewer"
else
  echo -e "${YELLOW}!${NC} skills/cli-anything-acloudviewer/SKILL.md not found (run post-sync-adapt.py)"
  fail=1
fi

if rg -q 'if: false' .github/workflows/publish-cli-hub.yml 2>/dev/null; then
  echo -e "${GREEN}✓${NC} publish-cli-hub workflow disabled on fork"
elif [[ ! -f .github/workflows/publish-cli-hub.yml ]]; then
  echo -e "${YELLOW}!${NC} publish-cli-hub workflow absent"
else
  echo -e "${RED}✗${NC} publish-cli-hub workflow still active"
  fail=1
fi

exit "$fail"
