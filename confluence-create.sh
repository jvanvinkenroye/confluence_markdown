#!/usr/bin/env bash
#
# confluence-create.sh - Interactive Confluence page creator
#
# Automatically detects and uses:
#   - fzf (if available) for fuzzy search
#   - bash select (if fzf not available) for numbered menus
#
# Usage:
#   ./confluence-create.sh [--profile PROFILE] [--template TEMPLATE]
#

set -euo pipefail

# Configuration
PROFILE="${CONFLUENCE_PROFILE:-localhost}"
TEMPLATE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Detect if fzf is available
HAS_FZF=false
if command -v fzf &> /dev/null; then
    HAS_FZF=true
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --template)
            TEMPLATE="$2"
            shift 2
            ;;
        --help|-h)
            cat << 'EOF'
Usage: ./confluence-create.sh [OPTIONS]

Interactive Confluence page creator with automatic UI detection.

OPTIONS:
    --profile PROFILE   Config profile to use (default: localhost)
    --template FILE     Use markdown template file
    --help, -h          Show this help message

FEATURES:
    - Auto-detects fzf availability
    - Uses fuzzy search if fzf is installed
    - Falls back to numbered menus if fzf is not available
    - Same workflow regardless of UI method

WORKFLOW:
    1. Select space
    2. Optionally select parent page
    3. Enter page title
    4. Edit content in your editor
    5. Page is created automatically

EXAMPLES:
    ./confluence-create.sh
    ./confluence-create.sh --profile work
    ./confluence-create.sh --template templates/meeting-notes.md

EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Load config
CONFIG_FILE="$HOME/.config/confluence-markdown/config.json"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}Error: Config file not found at $CONFIG_FILE${NC}"
    echo "Create one with: uv run confluence-markdown --init-config"
    exit 1
fi

# Extract config values
read -r BASE_URL USERNAME PASSWORD < <(python3 -c "
import json
import sys

try:
    with open('$CONFIG_FILE') as f:
        config = json.load(f)

    if '$PROFILE' not in config:
        print('', file=sys.stderr)
        print(f'Profile \"$PROFILE\" not found in config', file=sys.stderr)
        sys.exit(1)

    profile = config['$PROFILE']
    base_url = profile.get('base_url', '')
    username = profile.get('username', '')
    password = profile.get('password', profile.get('token', ''))

    print(f'{base_url} {username} {password}')
except Exception as e:
    print('', file=sys.stderr)
    print(f'Error loading config: {e}', file=sys.stderr)
    sys.exit(1)
")

if [[ -z "$BASE_URL" ]]; then
    echo -e "${RED}Error: Could not load profile '$PROFILE' from config${NC}"
    exit 1
fi

# Show UI mode
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if $HAS_FZF; then
    echo -e "${BOLD}${CYAN}  Confluence Page Creator (fzf mode)${NC}"
else
    echo -e "${BOLD}${CYAN}  Confluence Page Creator (menu mode)${NC}"
    echo -e "${YELLOW}  Tip: Install fzf for enhanced fuzzy search experience${NC}"
fi
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 1: Select Space
echo -e "${BLUE}Step 1: Select Space${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Fetching spaces from $BASE_URL..."

# Fetch ALL spaces with pagination
SPACES_JSON=""
START=0
LIMIT=100

while true; do
    PAGE_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
        "$BASE_URL/rest/api/space?limit=$LIMIT&start=$START" 2>/dev/null)

    if [[ -z "$PAGE_JSON" ]]; then
        if [[ -z "$SPACES_JSON" ]]; then
            echo -e "${RED}Error: Failed to fetch spaces from Confluence${NC}"
            exit 1
        fi
        break
    fi

    # Merge results
    if [[ -z "$SPACES_JSON" ]]; then
        SPACES_JSON="$PAGE_JSON"
    else
        SPACES_JSON=$(printf "%s\n%s\n" "$SPACES_JSON" "$PAGE_JSON" | python3 -c '
import json, sys
lines = sys.stdin.read().strip().split("\n")
data1 = json.loads(lines[0])
data2 = json.loads(lines[1])
data1["results"].extend(data2.get("results", []))
print(json.dumps(data1))
')
    fi

    # Check if there are more results
    if [[ -n "$PAGE_JSON" ]]; then
        PAGE_SIZE=$(echo "$PAGE_JSON" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("results", [])))')
        if [[ $PAGE_SIZE -lt $LIMIT ]]; then
            break
        fi
    fi

    START=$((START + LIMIT))
    echo "  Fetched $START spaces so far..."
done

# Parse spaces
if $HAS_FZF; then
    # FZF MODE: Create fzf-friendly format
    SPACES_LIST=$(echo "$SPACES_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for s in data.get("results", []):
    key = s.get("key", "UNKNOWN")
    name = s.get("name", "Unknown Space")
    stype = s.get("type", "unknown")
    print(f"{key:15} | {name:50} | {stype}")
')

    if [[ -z "$SPACES_LIST" ]]; then
        echo -e "${RED}Error: No spaces found${NC}"
        exit 1
    fi

    SPACE_COUNT=$(echo "$SPACES_LIST" | wc -l | tr -d ' ')
    echo -e "${GREEN}Found $SPACE_COUNT spaces${NC}"
    echo ""

    SELECTED_SPACE=$(echo "$SPACES_LIST" | fzf \
        --height=40% \
        --border=rounded \
        --prompt="Select space > " \
        --header="Key | Name | Type" \
        --preview="echo {}" \
        --preview-window=up:3:wrap \
        --color="header:italic:underline")

    if [[ -z "$SELECTED_SPACE" ]]; then
        echo -e "${YELLOW}No space selected. Aborting.${NC}"
        exit 0
    fi

    SPACE_KEY=$(echo "$SELECTED_SPACE" | awk -F'|' '{print $1}' | tr -d ' ')
    SPACE_NAME=$(echo "$SELECTED_SPACE" | awk -F'|' '{print $2}' | sed 's/^[ \t]*//;s/[ \t]*$//')

else
    # SELECT MODE: Parse into arrays
    mapfile -t SPACE_KEYS < <(echo "$SPACES_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for s in data.get("results", []): print(s.get("key", ""))
')

    mapfile -t SPACE_NAMES < <(echo "$SPACES_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for s in data.get("results", []): print(s.get("name", ""))
')

    if [[ ${#SPACE_KEYS[@]} -eq 0 ]]; then
        echo -e "${RED}Error: No spaces found${NC}"
        exit 1
    fi

    echo -e "${GREEN}Found ${#SPACE_KEYS[@]} spaces${NC}"
    echo ""

    # Create menu options
    OPTIONS=()
    for i in "${!SPACE_KEYS[@]}"; do
        OPTIONS+=("${SPACE_KEYS[$i]} - ${SPACE_NAMES[$i]}")
    done

    # Use bash select
    echo "Select a space (enter number):"
    PS3="Enter selection: "
    select opt in "${OPTIONS[@]}"; do
        if [[ -n "$opt" ]]; then
            SPACE_KEY=$(echo "$opt" | awk '{print $1}')
            SPACE_NAME=$(echo "$opt" | cut -d'-' -f2- | sed 's/^ *//')
            break
        else
            echo -e "${RED}Invalid selection${NC}"
        fi
    done
fi

echo -e "${GREEN}✓${NC} Selected space: ${BOLD}$SPACE_KEY${NC} ($SPACE_NAME)"
echo ""

# Step 2: Select Parent Page (Optional)
echo -e "${BLUE}Step 2: Select Parent Page (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Fetching pages in space $SPACE_KEY..."

# Fetch ALL pages with pagination
PAGES_JSON=""
START=0
LIMIT=100

while true; do
    PAGE_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
        "$BASE_URL/rest/api/content?type=page&spaceKey=$SPACE_KEY&limit=$LIMIT&start=$START" 2>/dev/null)

    if [[ -z "$PAGE_JSON" ]]; then
        break
    fi

    # Merge results
    if [[ -z "$PAGES_JSON" ]]; then
        PAGES_JSON="$PAGE_JSON"
    else
        PAGES_JSON=$(printf "%s\n%s\n" "$PAGES_JSON" "$PAGE_JSON" | python3 -c '
import json, sys
lines = sys.stdin.read().strip().split("\n")
data1 = json.loads(lines[0])
data2 = json.loads(lines[1])
data1["results"].extend(data2.get("results", []))
print(json.dumps(data1))
')
    fi

    # Check if there are more results
    if [[ -n "$PAGE_JSON" ]]; then
        PAGE_SIZE=$(echo "$PAGE_JSON" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("results", [])))')
        if [[ $PAGE_SIZE -lt $LIMIT ]]; then
            break
        fi
    fi

    START=$((START + LIMIT))
    echo "  Fetched $START pages so far..."
done

PARENT_ID=""

if $HAS_FZF; then
    # FZF MODE
    PAGES_LIST=$(echo "$PAGES_JSON" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    for p in data.get("results", []):
        page_id = p.get("id", "")
        title = p.get("title", "Untitled")
        print(f"{title:70} | {page_id}")
except: pass
' 2>/dev/null || echo "")

    if [[ -n "$PAGES_LIST" ]]; then
        PAGE_COUNT=$(echo "$PAGES_LIST" | wc -l | tr -d ' ')
        echo -e "${GREEN}Found $PAGE_COUNT pages${NC}"
        echo -e "${YELLOW}Select a parent page, or press ESC to create at root level${NC}"
        echo ""

        PAGES_WITH_NONE=$(echo -e "[ No Parent - Create at root level ]                                 | NONE\n$PAGES_LIST")

        SELECTED_PARENT=$(echo "$PAGES_WITH_NONE" | fzf \
            --height=40% \
            --border=rounded \
            --prompt="Select parent (ESC for none) > " \
            --header="Title | Page ID" \
            --preview="echo {}" \
            --preview-window=up:3:wrap \
            --color="header:italic:underline" || echo "")

        if [[ -n "$SELECTED_PARENT" ]]; then
            PARENT_ID=$(echo "$SELECTED_PARENT" | awk -F'|' '{print $NF}' | tr -d ' ')
            if [[ "$PARENT_ID" == "NONE" ]]; then
                PARENT_ID=""
                echo -e "${GREEN}✓${NC} Creating page at root level"
            else
                PARENT_TITLE=$(echo "$SELECTED_PARENT" | awk -F'|' '{print $1}' | sed 's/^[ \t]*//;s/[ \t]*$//')
                echo -e "${GREEN}✓${NC} Parent page: ${BOLD}$PARENT_TITLE${NC} (ID: $PARENT_ID)"
            fi
        else
            echo -e "${GREEN}✓${NC} No parent selected - creating at root level"
        fi
    else
        echo -e "${YELLOW}No pages in this space yet - creating at root level${NC}"
    fi

else
    # SELECT MODE
    mapfile -t PAGE_IDS < <(echo "$PAGES_JSON" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    for p in data.get("results", []): print(p.get("id", ""))
except: pass
' 2>/dev/null)

    mapfile -t PAGE_TITLES < <(echo "$PAGES_JSON" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    for p in data.get("results", []): print(p.get("title", ""))
except: pass
' 2>/dev/null)

    if [[ ${#PAGE_IDS[@]} -gt 0 ]]; then
        echo -e "${GREEN}Found ${#PAGE_IDS[@]} pages${NC}"
        echo ""

        PAGE_OPTIONS=("No Parent (create at root level)")
        for i in "${!PAGE_IDS[@]}"; do
            PAGE_OPTIONS+=("${PAGE_TITLES[$i]}")
        done

        echo "Select a parent page (or choose 'No Parent'):"
        PS3="Enter selection: "
        select page_opt in "${PAGE_OPTIONS[@]}"; do
            if [[ -n "$page_opt" ]]; then
                if [[ "$page_opt" == "No Parent"* ]]; then
                    PARENT_ID=""
                    echo -e "${GREEN}✓${NC} Creating page at root level"
                else
                    for i in "${!PAGE_TITLES[@]}"; do
                        if [[ "${PAGE_TITLES[$i]}" == "$page_opt" ]]; then
                            PARENT_ID="${PAGE_IDS[$i]}"
                            echo -e "${GREEN}✓${NC} Parent page: ${BOLD}$page_opt${NC} (ID: $PARENT_ID)"
                            break
                        fi
                    done
                fi
                break
            else
                echo -e "${RED}Invalid selection${NC}"
            fi
        done
    else
        echo -e "${YELLOW}No pages in this space yet - creating at root level${NC}"
    fi
fi

echo ""

# Step 3: Enter Title
echo -e "${BLUE}Step 3: Enter Page Title${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

read -p "Enter page title: " PAGE_TITLE

if [[ -z "$PAGE_TITLE" ]]; then
    echo -e "${RED}Error: Page title cannot be empty${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Title: ${BOLD}$PAGE_TITLE${NC}"
echo ""

# Step 4: Edit Content
echo -e "${BLUE}Step 4: Create Content${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

TEMP_FILE=$(mktemp /tmp/confluence-create-XXXXXX.md)

if [[ -n "$TEMPLATE" && -f "$TEMPLATE" ]]; then
    cat "$TEMPLATE" > "$TEMP_FILE"
    echo -e "${GREEN}✓${NC} Loaded template from: $TEMPLATE"
else
    cat > "$TEMP_FILE" << EOF
# $PAGE_TITLE

## Overview

Write your page content here using Markdown.

## Sections

### Section 1

Content goes here...

### Section 2

More content...

## Tips

- Use **bold** for emphasis
- Use *italic* for subtle emphasis
- Use tables, lists, and code blocks
- Delete this template content and write your own!

EOF
fi

# Detect editor
EDITOR="${EDITOR:-}"
if [[ -z "$EDITOR" ]]; then
    for ed in code vim nano emacs gedit; do
        if command -v "$ed" &> /dev/null; then
            EDITOR="$ed"
            break
        fi
    done
fi

if [[ -z "$EDITOR" ]]; then
    EDITOR="vi"
fi

echo "Opening editor: $EDITOR"
echo "Edit your content, save, and close the editor to continue..."
echo ""

ORIGINAL_MTIME=$(stat -f %m "$TEMP_FILE" 2>/dev/null || stat -c %Y "$TEMP_FILE" 2>/dev/null)

$EDITOR "$TEMP_FILE"

NEW_MTIME=$(stat -f %m "$TEMP_FILE" 2>/dev/null || stat -c %Y "$TEMP_FILE" 2>/dev/null)

if [[ "$NEW_MTIME" == "$ORIGINAL_MTIME" ]]; then
    echo -e "${YELLOW}No changes made. Aborting.${NC}"
    rm -f "$TEMP_FILE"
    exit 0
fi

CONTENT=$(cat "$TEMP_FILE")
rm -f "$TEMP_FILE"

echo -e "${GREEN}✓${NC} Content ready ($(echo "$CONTENT" | wc -l) lines)"
echo ""

# Step 5: Create Page
echo -e "${BLUE}Step 5: Creating Page${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

CMD_ARGS=(
    "uv" "run" "confluence-markdown"
    "--config"
    "--profile" "$PROFILE"
    "--action" "create"
    "--space" "$SPACE_KEY"
    --title "$PAGE_TITLE"
    "--content" "$CONTENT"
)

if [[ -n "$PARENT_ID" ]]; then
    CMD_ARGS+=("--parent-id" "$PARENT_ID")
fi

echo "Creating page..."
"${CMD_ARGS[@]}" 2>&1 | grep -v "^DEBUG:" | grep -v "warning:"

echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  Page created successfully!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
