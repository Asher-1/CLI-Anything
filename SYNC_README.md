# 🔄 Fork Repository Sync Tools

A complete fork repository sync solution with upstream.

## ⚡ Quick Start

```bash
make check-upstream    # Check upstream updates
make sync-merge        # Sync upstream (recommended) + auto-customize
```

**Auto-Customization**: After sync, automatically replaces `HKUDS` with `Asher-1`, suitable for deploying to your own website.

## 📚 Complete Documentation

For detailed usage guide, see: **[SYNC_UPSTREAM.md](./SYNC_UPSTREAM.md)**

## 🛠️ Tools List

- ✅ `sync-upstream.sh` - Automation sync script
- ✅ `Makefile` - Shortcut commands
- ✅ `.gitattributes` - Git smart merge config
- ✅ `.github/workflows/check-upstream.yml` - Auto-detect upstream updates

## 📊 Shortcut Commands

```bash
make sync              # Sync (rebase) + auto-customize
make sync-merge        # Sync (merge) + auto-customize
make sync-ours         # Sync (keep local) + auto-customize
make check-upstream    # Check updates
make show-diff         # View differences
make customize         # Manual customization (HKUDS→Asher-1)
make customize-preview # Preview customization changes
make backup            # Create backup
make restore           # Restore backup
make docs              # View complete documentation
```

## 💡 Recommended Strategy

Not sure which to use? → **`make sync-merge`** (safest)

---

**Detailed Documentation**: [SYNC_UPSTREAM.md](./SYNC_UPSTREAM.md)
