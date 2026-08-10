# 🔄 Fork Repository Upstream Sync Guide

> Gracefully manage fork repository sync with upstream HKUDS/CLI-Anything, auto-handling conflicts.

## ⚡ Quick Start (3 steps)

```bash
# 1. Check upstream updates
make check-upstream

# 2. Sync upstream
make sync              # Default strategy (rebase)
# or
make sync-merge        # Safer strategy (recommended)

# 3. Done! 🎉
```

## 📦 Configured Tools

### 1. Automation Script: `sync-upstream.sh`

```bash
./sync-upstream.sh              # Default rebase strategy
./sync-upstream.sh --merge      # merge strategy (safer)
./sync-upstream.sh --ours       # Keep local version
./sync-upstream.sh --no-push    # Don't auto-push
./sync-upstream.sh --help       # View help
```

### 2. Makefile Shortcuts

```bash
make help              # View all commands
make sync              # Sync (rebase) + auto-customize
make sync-merge        # Sync (merge) + auto-customize
make sync-ours         # Sync (keep local) + auto-customize
make check-upstream    # Check updates
make show-diff         # View differences
make customize         # Manually apply customization rules
make customize-preview # Preview customization changes
make backup            # Create backup
make restore           # Restore backup
make list-backups      # List backups
make clean             # Clean old backups
```

### 3. Git Smart Config: `.gitattributes`

Auto-handle common conflicts:
- **Keep local**: `*.local`, `.env*`, `.vscode/settings.json`
- **Merge both**: `*.json`, `*.md`, `**/tests/**`

### 4. GitHub Actions: `.github/workflows/check-upstream.yml`

Automatically check upstream updates daily and create issue reminders.

### 5. Auto-Customization Script: `customize.sh` ⭐ New Feature

Auto-replace all `HKUDS` references with `Asher-1` after sync:

```bash
./customize.sh              # Execute replacements
./customize.sh --dry-run    # Preview changes
./customize.sh --verbose    # Show detailed output
```

**Config file**: `.sync-config.json`
- Customize replacement rules
- Specify include/exclude file patterns
- Protect specific content from replacement

## 🎯 Three Sync Strategies

### Strategy Comparison

| Strategy | Command | When to Use | Pros | Cons |
|----------|---------|-------------|------|------|
| **Rebase** | `make sync` | Regular sync, few commits | Clean history, easy review | Requires force push |
| **Merge** | `make sync-merge` | Long unsync, many commits | Safer, preserves history | Creates merge commits |
| **Ours** | `make sync-ours` | Heavy customization, keep local | Auto-resolves conflicts | May miss improvements |

### Strategy Selection Decision Tree

```
Haven't synced for a long time (>1 month)?
├─ Yes → make sync-merge
└─ No → ↓

Have heavy customization?
├─ Yes → make sync-ours or make sync-merge
└─ No → make sync (default)

Not sure which to use?
└─ Use make sync-merge (safest)
```

## 🔧 Conflict Resolution

### Rebase Conflicts

```bash
# 1. Edit conflicted files
vim <conflicted-file>

# 2. Mark as resolved
git add <file>

# 3. Continue rebase
git rebase --continue

# Abort rebase
git rebase --abort
```

### Merge Conflicts

```bash
# 1. Edit conflicted files
vim <conflicted-file>

# 2. Mark and commit
git add <file>
git commit

# Abort merge
git merge --abort
```

### Batch Processing

```bash
# Use local version
git checkout --ours '*.local'
git add '*.local'

# Use upstream version
git checkout --theirs 'docs/*.md'
git add 'docs/*.md'
```

## 🎓 Best Practices

### 1. Regular Weekly Sync

```bash
# Recommended to run every Monday
make check-upstream
make sync-merge
```

### 2. Sync Before New Features

```bash
git checkout main
make sync-merge
git checkout -b feature/my-feature
```

### 3. Restore Immediately if Issues

```bash
make list-backups
make restore
```

## 📊 Common Scenarios

### Scenario 1: Regular Scheduled Sync

```bash
make check-upstream
make sync-merge
```

### Scenario 2: Many Conflicts

```bash
# Use safer strategy
make sync-merge
```

### Scenario 3: Keep All Local Modifications

```bash
make sync-ours
```

### Scenario 4: Preview Before Sync

```bash
make show-diff
```

### Scenario 5: Sync Went Wrong

```bash
make list-backups
make restore
make sync-merge  # Try again
```

## 🚨 Troubleshooting

### Issue 1: force push Failed

```bash
git push origin main --force-with-lease
```

### Issue 2: Too Many Conflicts to Handle

```bash
# Option 1: Use ours strategy
make sync-ours

# Option 2: Restore and use merge
make restore
make sync-merge
```

### Issue 3: Function Broken After Sync

```bash
# Immediately rollback
make restore

# Run tests
make test  # if you have tests

# Re-sync
make sync-merge
```

## 🔄 Recommended Workflow

```
Weekly routine
    ↓
make check-upstream
    ↓
  Updates?
    ↓
 ┌──┴──┐
No      Yes
 │      ↓
 │  make sync-merge
 │      ↓
 │   Conflicts?
 │      ↓
 │  ┌──┴──┐
 │ No      Yes
 │  │      ↓
 │  │  Resolve conflicts
 │  │      ↓
 │  │  git add
 │  │      ↓
 │  │  git commit
 │  │      ↓
 └──┴──────┘
    ↓
 Run tests
    ↓
  Done!
```

## 💡 Expert Tips

1. **Regular Sync** - Weekly to avoid conflict accumulation
2. **Small Commits** - Keep commits small and focused
3. **Use Backups** - Auto-created with each sync
4. **Choose Right Strategy** - Use `make sync-merge` if unsure
5. **Test Validation** - Run tests after sync

## 📞 Getting Help

```bash
./sync-upstream.sh --help     # Script help
make help                     # Makefile commands
```

## 🎯 File Handling Recommendations

| File Type | Recommended Strategy | Reason |
|-----------|---------------------|---------|
| Config files (`.env`, `.vscode/`) | Keep local | Environment-specific |
| Documentation (`.md`) | Merge both | Both may have value |
| Source code | Review per-file | Depends on modification nature |
| Test code | Merge both | More tests are better |
| Dependency files | Manual merge | Version compatibility |

## 🎨 Auto-Customization Feature (New)

Auto-replace `HKUDS` with `Asher-1` after sync, suitable for deploying to your own website.

### How It Works

1. **Auto-triggered**: `make sync-merge` automatically runs customization script after successful sync
2. **Smart replacement**: Only replaces GitHub URLs and documentation references, preserves upstream acknowledgments
3. **Configurable**: Customize rules via `.sync-config.json`

### Manual Usage

```bash
# Preview changes to be made
make customize-preview

# Execute customization
make customize

# View changes
git diff
```

### Config File: `.sync-config.json`

```json
{
  "replacements": [
    {
      "from": "HKUDS/CLI-Anything",
      "to": "Asher-1/CLI-Anything",
      "description": "GitHub repository references"
    },
    {
      "from": "hkuds.github.io/CLI-Anything",
      "to": "asher-1.github.io/CLI-Anything",
      "description": "GitHub Pages URLs"
    }
  ],
  "include_patterns": [
    "README*.md",
    "registry.json",
    "docs/**/*.md",
    "**/SKILL.md"
  ],
  "exclude_patterns": [
    "CONTRIBUTING.md",
    "sync-upstream.sh"
  ]
}
```

**Protected content**:
- ✅ Upstream repository references in CONTRIBUTING.md
- ✅ Acknowledgments like "Thanks to HKUDS"
- ✅ Source attribution like "based on HKUDS"

## 🚀 Get Started Now

```bash
# Check current status
git remote -v
make check-upstream

# Execute sync (auto-applies customization)
make sync-merge

# View customization results
git diff
```

---

**Tip**: All sync operations automatically create backup branches, can restore anytime. Feel free to try!

**Current Config Status**:
- ✅ Upstream remote repository configured
- ✅ Git merge strategy optimized
- ✅ Auto-reminder system deployed
- ✅ Backup restore mechanism ready
- ✅ Auto-customization rules configured
