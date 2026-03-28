#!/bin/bash

# CLI-Anything Auto-Customization Script
# Automatically replace upstream references with own repository info after sync

set -e

CONFIG_FILE=".sync-config.json"
DRY_RUN=false
VERBOSE=false

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

print_info() {
    if [[ "$VERBOSE" == true ]]; then
        echo -e "  ${1}"
    fi
}

# Check config file
check_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        print_error "Config file $CONFIG_FILE not found"
        exit 1
    fi
}

# Apply replacement rules
apply_replacements() {
    local files_changed=0
    local total_replacements=0
    
    print_step "Applying replacement rules..."
    
    # Read replacement rules
    local replacements=$(jq -r '.replacements[] | @json' "$CONFIG_FILE")
    
    # Get include and exclude patterns
    local include_patterns=$(jq -r '.include_patterns[]' "$CONFIG_FILE")
    local exclude_patterns=$(jq -r '.exclude_patterns[]' "$CONFIG_FILE")
    local exclude_content=$(jq -r '.exclude_content[]' "$CONFIG_FILE" 2>/dev/null || echo "")
    
    # Build file list
    local file_list=""
    while IFS= read -r pattern; do
        if [[ -n "$pattern" ]]; then
            # Use find to handle various patterns
            if [[ "$pattern" == *"**"* ]]; then
                # Handle ** recursive patterns
                if [[ "$pattern" == "**/"* ]]; then
                    # Top-level recursive: **/*.md
                    local file_pattern="${pattern#**/}"
                    file_list="$file_list $(find . -type f -name "$file_pattern" 2>/dev/null | sed 's|^\./||' || true)"
                elif [[ "$pattern" == *"/**/"* ]]; then
                    # Mid-level recursive: dir/**/file
                    local base_dir="${pattern%%/**/*}"
                    local rest="${pattern#*/**/}"
                    if [[ -d "$base_dir" ]]; then
                        file_list="$file_list $(find "$base_dir" -type f -path "*/$rest" 2>/dev/null || true)"
                    fi
                else
                    # Other ** patterns
                    local base_dir="${pattern%%/**}"
                    local file_pattern="${pattern##**/}"
                    if [[ -d "$base_dir" ]]; then
                        file_list="$file_list $(find "$base_dir" -type f -name "*$file_pattern" 2>/dev/null || true)"
                    else
                        # May be top-level directory
                        file_list="$file_list $(find . -type f -name "*$file_pattern" 2>/dev/null | sed 's|^\./||' || true)"
                    fi
                fi
            elif [[ "$pattern" == *"*"* ]]; then
                # Simple glob pattern
                file_list="$file_list $(find . -maxdepth 1 -type f -name "$pattern" 2>/dev/null | sed 's|^\./||' || true)"
            else
                # Exact filename
                if [[ -f "$pattern" ]]; then
                    file_list="$file_list $pattern"
                fi
            fi
        fi
    done <<< "$include_patterns"
    
    # Remove duplicates
    file_list=$(echo "$file_list" | tr ' ' '\n' | sort -u | tr '\n' ' ')
    
    # Filter excluded files
    local filtered_files=""
    for file in $file_list; do
        local excluded=false
        while IFS= read -r exclude_pattern; do
            if [[ -n "$exclude_pattern" && "$file" == $exclude_pattern ]]; then
                excluded=true
                print_info "Skipping excluded file: $file"
                break
            fi
        done <<< "$exclude_patterns"
        
        if [[ "$excluded" == false ]]; then
            filtered_files="$filtered_files $file"
        fi
    done
    
    # Apply replacements to each file
    for file in $filtered_files; do
        if [[ ! -f "$file" ]]; then
            continue
        fi
        
        local file_changed=false
        local file_replacements=0
        
        # For each replacement rule
        while IFS= read -r replacement; do
            local from=$(echo "$replacement" | jq -r '.from')
            local to=$(echo "$replacement" | jq -r '.to')
            local desc=$(echo "$replacement" | jq -r '.description')
            
            # Check if file contains content to replace
            if grep -q "$from" "$file" 2>/dev/null; then
                # Smart replacement: skip lines with excluded content
                if [[ -n "$exclude_content" && "$DRY_RUN" == false ]]; then
                    # Use temp file for line-by-line processing
                    local temp_file="${file}.tmp"
                    local skipped_lines=0
                    
                    while IFS= read -r line || [[ -n "$line" ]]; do
                        local should_skip_line=false
                        
                        # Check if this line contains excluded content
                        if [[ -n "$exclude_content" ]]; then
                            while IFS= read -r exclude_pattern; do
                                if [[ -n "$exclude_pattern" && "$line" =~ $exclude_pattern ]]; then
                                    should_skip_line=true
                                    skipped_lines=$((skipped_lines + 1))
                                    break
                                fi
                            done <<< "$exclude_content"
                        fi
                        
                        # If this line should not be skipped, perform replacement
                        if [[ "$should_skip_line" == false ]]; then
                            echo "$line" | sed "s|$from|$to|g" >> "$temp_file"
                        else
                            echo "$line" >> "$temp_file"
                        fi
                    done < "$file"
                    
                    # Calculate actual replacement count
                    local count=$(diff -U 0 "$file" "$temp_file" 2>/dev/null | grep -c "^-.*$from" || echo "0")
                    
                    if [[ "$count" -gt 0 ]]; then
                        mv "$temp_file" "$file"
                        print_info "Replaced $count occurrences in $file: $from → $to ($desc)"
                        if [[ "$skipped_lines" -gt 0 ]]; then
                            print_info "  Skipped $skipped_lines lines with excluded content"
                        fi
                        file_changed=true
                        file_replacements=$((file_replacements + count))
                        total_replacements=$((total_replacements + count))
                    else
                        rm -f "$temp_file"
                    fi
                else
                    # Preview mode or no exclusion rules: count replacements
                    local count=$(grep -o "$from" "$file" | wc -l | tr -d ' ')
                    
                    if [[ "$DRY_RUN" == true ]]; then
                        # Check for excluded lines
                        local skipped=0
                        if [[ -n "$exclude_content" ]]; then
                            while IFS= read -r exclude_pattern; do
                                if [[ -n "$exclude_pattern" ]]; then
                                    local skip_count=$(grep -c "$exclude_pattern" "$file" 2>/dev/null | head -1 || echo "0")
                                    # Ensure it's a number
                                    skip_count=$(echo "$skip_count" | tr -d '\n' | grep -o '[0-9]*' | head -1)
                                    if [[ -n "$skip_count" && "$skip_count" =~ ^[0-9]+$ ]]; then
                                        skipped=$((skipped + skip_count))
                                    fi
                                fi
                            done <<< "$exclude_content"
                        fi
                        
                        print_info "Will replace ~$count occurrences in $file: $from → $to"
                        if [[ $skipped -gt 0 ]]; then
                            print_info "  (Will skip $skipped lines with excluded content)"
                        fi
                    else
                        # Simple replacement (no exclusion rules)
                        if [[ "$OSTYPE" == "darwin"* ]]; then
                            sed -i '' "s|$from|$to|g" "$file"
                        else
                            sed -i "s|$from|$to|g" "$file"
                        fi
                        print_info "Replaced $count occurrences in $file: $from → $to ($desc)"
                    fi
                    
                    if [[ "$count" -gt 0 ]]; then
                        file_changed=true
                        file_replacements=$((file_replacements + count))
                        total_replacements=$((total_replacements + count))
                    fi
                fi
            fi
        done <<< "$replacements"
        
        if [[ "$file_changed" == true ]]; then
            files_changed=$((files_changed + 1))
            if [[ "$DRY_RUN" == false ]]; then
                print_success "Updated: $file ($file_replacements replacements)"
            fi
        fi
    done
    
    echo ""
    if [[ "$DRY_RUN" == true ]]; then
        print_warning "Preview mode: will affect $files_changed files, total $total_replacements replacements"
        print_step "Run './customize.sh' to execute actual replacements"
    else
        print_success "Complete! Updated $files_changed files, total $total_replacements replacements"
    fi
}

# Show help
show_help() {
    cat << EOF
CLI-Anything Auto-Customization Tool

Usage:
  $0 [options]

Options:
  --dry-run    Preview mode, don't modify files
  --verbose    Show detailed output
  --help       Show this help message

Configuration:
  Edit $CONFIG_FILE to customize replacement rules

Examples:
  $0                # Execute replacements
  $0 --dry-run      # Preview changes to be made
  $0 --verbose      # Show detailed output

EOF
}

# Main workflow
main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
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
    
    print_step "CLI-Anything Auto-Customization Tool"
    echo ""
    
    # Check dependencies
    if ! command -v jq &> /dev/null; then
        print_error "jq is required: brew install jq (macOS) or apt install jq (Linux)"
        exit 1
    fi
    
    # Check config
    check_config
    
    # Apply replacements
    apply_replacements
    
    echo ""
    if [[ "$DRY_RUN" == false ]]; then
        print_success "Customization complete!"
        print_step "Suggestion: Run 'git diff' to see all changes"
    fi
}

# Run main workflow
main "$@"
