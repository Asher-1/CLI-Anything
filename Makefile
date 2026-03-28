.PHONY: help sync sync-merge sync-ours sync-dry-run check-upstream show-diff backup restore clean customize customize-preview

# Default target
help:
	@echo "CLI-Anything Upstream Sync Tool"
	@echo ""
	@echo "Common Commands:"
	@echo "  make sync              - Sync upstream (rebase strategy)"
	@echo "  make sync-merge        - Sync upstream (merge strategy, safer)"
	@echo "  make sync-ours         - Sync upstream (keep our version)"
	@echo "  make sync-dry-run      - Preview sync results, no modifications"
	@echo ""
	@echo "View Commands:"
	@echo "  make check-upstream    - Check if upstream has updates"
	@echo "  make show-diff         - Show differences with upstream"
	@echo "  make show-conflicts    - Preview potential conflict files"
	@echo ""
	@echo "Backup & Restore:"
	@echo "  make backup            - Manually create backup branch"
	@echo "  make restore           - Interactive restore to backup"
	@echo "  make list-backups      - List all backup branches"
	@echo ""
	@echo "Customization Commands:"
	@echo "  make customize         - Manually apply customization rules (HKUDS→Asher-1)"
	@echo "  make customize-preview - Preview customization changes"
	@echo ""
	@echo "Other:"
	@echo "  make clean             - Clean old backup branches (30+ days)"
	@echo "  make docs              - View sync documentation"
	@echo ""
	@echo "Documentation: SYNC_UPSTREAM.md"
	@echo "Configuration: .sync-config.json"
	@echo ""

# Sync commands
sync:
	@echo "🚀 Starting upstream sync (rebase strategy)..."
	@./sync-upstream.sh

sync-merge:
	@echo "🚀 Starting upstream sync (merge strategy)..."
	@./sync-upstream.sh --merge

sync-ours:
	@echo "🚀 Starting upstream sync (keep our version)..."
	@./sync-upstream.sh --ours

sync-dry-run:
	@echo "🔍 Previewing sync results (no modifications)..."
	@./sync-upstream.sh --no-push
	@echo ""
	@echo "✅ Preview complete. If satisfied, run 'make sync' for actual sync"

# Check commands
check-upstream:
	@echo "🔍 Checking upstream updates..."
	@git fetch upstream --quiet 2>/dev/null || (git remote add upstream https://github.com/HKUDS/CLI-Anything.git && git fetch upstream --quiet)
	@BEHIND=$$(git rev-list --count HEAD..upstream/main 2>/dev/null || echo "0"); \
	AHEAD=$$(git rev-list --count upstream/main..HEAD 2>/dev/null || echo "0"); \
	if [ "$$BEHIND" = "0" ]; then \
		echo "✅ Already synced with upstream"; \
	else \
		echo "⚠️  Behind upstream by $$BEHIND commits"; \
		echo "   Ahead of upstream by $$AHEAD commits"; \
		echo ""; \
		echo "Latest upstream commits:"; \
		git log --oneline --no-merges HEAD..upstream/main | head -5; \
		echo ""; \
		echo "Run 'make sync' to sync"; \
	fi

show-diff:
	@echo "📊 Differences with upstream..."
	@git fetch upstream --quiet 2>/dev/null || true
	@git diff --stat HEAD...upstream/main

show-conflicts:
	@echo "🔍 Checking potential conflicts..."
	@git fetch upstream --quiet 2>/dev/null || true
	@echo "Files that may conflict:"
	@git diff --name-only --diff-filter=U HEAD upstream/main 2>/dev/null || \
		git diff --name-only HEAD upstream/main | grep -v "^$$" || echo "  (Need to try merge/rebase first for accurate judgment)"

# Backup & restore
backup:
	@BACKUP_BRANCH="backup-manual-$$(date +%Y%m%d-%H%M%S)"; \
	git branch "$$BACKUP_BRANCH"; \
	echo "✅ Created backup branch: $$BACKUP_BRANCH"

list-backups:
	@echo "📦 Backup branch list:"
	@git branch | grep backup || echo "  (No backup branches)"

restore:
	@echo "📦 Available backup branches:"
	@git branch | grep backup | nl
	@echo ""
	@read -p "Enter branch number to restore (Ctrl+C to cancel): " num; \
	BRANCH=$$(git branch | grep backup | sed -n "$${num}p" | xargs); \
	if [ -n "$$BRANCH" ]; then \
		echo "⚠️  About to restore to branch: $$BRANCH"; \
		read -p "Are you sure? This will lose all uncommitted changes! (yes/no): " confirm; \
		if [ "$$confirm" = "yes" ]; then \
			git reset --hard "$$BRANCH"; \
			echo "✅ Restored to: $$BRANCH"; \
		else \
			echo "❌ Cancelled"; \
		fi \
	else \
		echo "❌ Invalid selection"; \
	fi

# Clean command
clean:
	@echo "🧹 Cleaning old backup branches (30+ days)..."
	@for branch in $$(git branch | grep backup); do \
		BRANCH_DATE=$$(echo $$branch | grep -oE '[0-9]{8}' || echo "00000000"); \
		CUTOFF_DATE=$$(date -v-30d +%Y%m%d 2>/dev/null || date -d '30 days ago' +%Y%m%d 2>/dev/null || echo "99999999"); \
		if [ "$$BRANCH_DATE" -lt "$$CUTOFF_DATE" ] && [ "$$BRANCH_DATE" != "00000000" ]; then \
			echo "  Deleting: $$branch ($$BRANCH_DATE)"; \
			git branch -D $$branch; \
		fi \
	done
	@echo "✅ Cleanup complete"

# Customization commands
customize:
	@echo "🎨 Applying customization rules (HKUDS → Asher-1)..."
	@./customize.sh --verbose

customize-preview:
	@echo "🔍 Previewing customization changes..."
	@./customize.sh --dry-run --verbose

# Documentation command
docs:
	@if command -v open >/dev/null 2>&1; then \
		open SYNC_UPSTREAM.md; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open SYNC_UPSTREAM.md; \
	else \
		cat SYNC_UPSTREAM.md; \
	fi
