# Fork Upstream Sync (Asher-1/CLI-Anything)

This fork tracks [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) while keeping:

- `acloudviewer/` harness and registry entry
- Fork-only hub domain: `https://asher-1.github.io/CLI-Anything/`
- Agent catalog URL: `https://asher-1.github.io/CLI-Anything/SKILL.txt`
- No dependency on upstream `clianything.cc` or DigitalOcean Spaces

## Quick Start (recommended)

```bash
# 1. Check how far behind upstream you are
make check-upstream

# 2. Rebase onto upstream + auto-adapt fork branding/registry/skills/CI
make sync-adapt

# 3. Verify fork isolation (no HKUDS hub URLs left)
make verify-fork

# 4. Push when tests pass
./scripts/sync-upstream-adapt.sh --yes --push
```

## What `sync-adapt` does

1. Creates `backup-before-sync-YYYYMMDD-HHMMSS`
2. `git fetch upstream` + **rebase** onto `upstream/main`
3. Auto-resolves common conflicts via `scripts/resolve-rebase-conflicts.sh`
4. Runs `scripts/post-sync-adapt.py`:
   - merge `acloudviewer` into `registry.json`
   - patch `repl_skin.py`, `.gitignore`, `cli-hub` registry URLs
   - disable upstream PyPI publish workflow on fork
   - patch `deploy-pages.yml` to publish `SKILL.txt` on GitHub Pages (no DO Spaces)
   - run `customize.sh`, sync `skills/`, validate root skills
5. Runs `scripts/verify-fork-isolation.sh`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/sync-upstream-adapt.sh` | Main orchestrator (rebase/merge + adapt + optional push) |
| `scripts/post-sync-adapt.py` | Fork-specific post-sync adaptation |
| `scripts/resolve-rebase-conflicts.sh` | Auto-resolve known conflict files during rebase |
| `scripts/verify-fork-isolation.sh` | Ensure no upstream hub/skill CDN URLs remain |
| `customize.sh` | URL/branding replacements from `.sync-config.json` |
| `sync-upstream.sh` | Legacy sync script (customize only, no full adaptation) |

## Makefile shortcuts

```bash
make sync-adapt          # rebase + adapt + verify
make sync-adapt-only     # adapt current tree only (after manual conflict fix)
make verify-fork         # isolation checks
make customize           # run URL replacements only
make check-upstream      # show behind/ahead counts
```

## Manual recovery

```bash
git checkout main
git reset --hard backup-before-sync-YYYYMMDD-HHMMSS
```

## Configuration

Edit `.sync-config.json` for fork URLs and replacement rules.

## Full guide

See [SYNC_UPSTREAM.md](./SYNC_UPSTREAM.md) for conflict handling, CI notes, and testing checklist.
