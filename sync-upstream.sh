#!/bin/bash

# CLI-Anything Upstream Sync Script
# Gracefully sync fork repository with upstream, auto-handling conflicts

set -e

UPSTREAM_REPO="https://github.com/HKUDS/CLI-Anything.git"
MAIN_BRANCH="main"
BACKUP_BRANCH="backup-before-sync-$(date +%Y%m%d-%H%M%S)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}==>${NC} ${1}"
}

print_success() {
    echo -e "${GREEN}✓${NC} ${1}"
}

print_warning() {
    echo -e "${YELLOW}!${NC} ${1}"
}

print_error() {
    echo -e "${RED}✗${NC} ${1}"
}

# Check for uncommitted changes
check_clean_workspace() {
    if [[ -n $(git status -s) ]]; then
        print_error "Working directory has uncommitted changes, please commit or stash first"
        git status -s
        exit 1
    fi
}

# Configure upstream repository
setup_upstream() {
    if git remote | grep -q "^upstream$"; then
        print_success "Upstream repository already configured"
        git remote set-url upstream "$UPSTREAM_REPO"
    else
        print_step "Adding upstream repository..."
        git remote add upstream "$UPSTREAM_REPO"
        print_success "Upstream repository added"
    fi
}

# Backup current branch
backup_current_branch() {
    print_step "Creating backup branch: $BACKUP_BRANCH"
    git branch "$BACKUP_BRANCH"
    print_success "Backup complete, restore with 'git checkout $BACKUP_BRANCH' if needed"
}

# Fetch upstream updates
fetch_upstream() {
    print_step "Fetching updates from upstream repository..."
    git fetch upstream
    print_success "Upstream updates fetched"
}

# Strategy 1: Rebase (recommended, keeps history clean)
sync_with_rebase() {
    print_step "Syncing upstream updates using rebase strategy..."
    
    if git rebase upstream/$MAIN_BRANCH; then
        print_success "Rebase completed successfully"
        return 0
    else
        print_warning "Rebase encountered conflicts, manual resolution needed"
        print_step "Please follow these steps to resolve conflicts:"
        echo "  1. Edit conflicted files"
        echo "  2. git add <resolved-files>"
        echo "  3. git rebase --continue"
        echo "  4. Repeat until all conflicts are resolved"
        echo ""
        print_step "Or abort rebase:"
        echo "  git rebase --abort"
        echo "  Then try: $0 --merge"
        return 1
    fi
}

# Strategy 2: Merge (if rebase is too difficult)
sync_with_merge() {
    print_step "Syncing upstream updates using merge strategy..."
    
    if git merge upstream/$MAIN_BRANCH -m "Merge upstream changes from HKUDS/CLI-Anything"; then
        print_success "Merge completed successfully"
        return 0
    else
        print_warning "Merge encountered conflicts, manual resolution needed"
        print_step "Please follow these steps to resolve conflicts:"
        echo "  1. Edit conflicted files"
        echo "  2. git add <resolved-files>"
        echo "  3. git commit"
        echo ""
        print_step "Or abort merge:"
        echo "  git merge --abort"
        return 1
    fi
}

# Strategy 3: Force use our version (use with caution)
sync_with_ours() {
    print_warning "Using 'ours' strategy - all conflicts will keep your version"
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    print_step "Merging upstream updates, keeping our version on conflicts..."
    git merge -X ours upstream/$MAIN_BRANCH -m "Merge upstream changes (keep ours on conflict)"
    print_success "Merge complete, all conflicts kept your version"
}

# Auto-customize (replace upstream references with own repository)
auto_customize() {
    if [[ -f "customize.sh" && -f ".sync-config.json" ]]; then
        print_step "Applying auto-customization rules..."
        if ./customize.sh --verbose; then
            print_success "Auto-customization complete"
        else
            print_warning "Auto-customization failed, please run manually: ./customize.sh"
        fi
    fi
}

# Push to remote
push_changes() {
    print_step "Preparing to push to remote repository..."
    print_warning "This will use --force-with-lease push, overwriting remote history"
    read -p "Are you sure you want to push? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin $MAIN_BRANCH --force-with-lease
        print_success "Push successful"
    else
        print_warning "Skipping push, you can push manually later:"
        echo "  git push origin $MAIN_BRANCH --force-with-lease"
    fi
}

# Show help
show_help() {
    cat << EOF
CLI-Anything Upstream Sync Tool

Usage:
  $0 [options]

Options:
  --rebase    Use rebase strategy (default, recommended)
  --merge     Use merge strategy
  --ours      Use 'ours' strategy, keep our version on conflicts
  --no-push   Sync without pushing to remote
  --help      Show this help message

Strategy explanation:
  rebase: Reapply your commits on top of upstream's latest, keeps history clean
  merge:  Create a merge commit, preserves full branch history
  ours:   Auto-resolve conflicts, all conflicts keep your version (use with caution)

Examples:
  $0                # Default uses rebase strategy
  $0 --merge        # Use merge strategy
  $0 --ours         # Use ours strategy (keep our version)
  $0 --no-push      # Sync without pushing

EOF
}

# Main workflow
main() {
    local strategy="rebase"
    local do_push=true
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --rebase)
                strategy="rebase"
                shift
                ;;
            --merge)
                strategy="merge"
                shift
                ;;
            --ours)
                strategy="ours"
                shift
                ;;
            --no-push)
                do_push=false
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown argument: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_step "Starting CLI-Anything upstream sync..."
    echo ""
    
    # Execute sync workflow
    check_clean_workspace
    setup_upstream
    backup_current_branch
    fetch_upstream
    
    case $strategy in
        rebase)
            if sync_with_rebase; then
                auto_customize
                if [[ "$do_push" == true ]]; then
                    push_changes
                fi
            else
                exit 1
            fi
            ;;
        merge)
            if sync_with_merge; then
                auto_customize
                if [[ "$do_push" == true ]]; then
                    push_changes
                fi
            else
                exit 1
            fi
            ;;
        ours)
            sync_with_ours
            auto_customize
            if [[ "$do_push" == true ]]; then
                push_changes
            fi
            ;;
    esac
    
    echo ""
    print_success "Sync complete!"
    print_step "Backup branch: $BACKUP_BRANCH"
    print_step "If there are issues, restore with:"
    echo "  git checkout $MAIN_BRANCH"
    echo "  git reset --hard $BACKUP_BRANCH"
}

# Run main workflow
main "$@"
