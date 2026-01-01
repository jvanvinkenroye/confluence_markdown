#!/usr/bin/env bash
#
# confluence-fzf.sh - Interactive Confluence page selector
#
# Automatically detects and uses:
#   - fzf (if available) for fuzzy search
#   - bash select (if fzf not available) for numbered menus
#
# Usage:
#   ./confluence-fzf.sh [--profile PROFILE] [--action ACTION]
#
# Actions:
#   edit   - Edit selected page in editor (default)
#   read   - Display selected page content
#   download - Download selected page to markdown file
#

set -euo pipefail

# Configuration
PROFILE="${CONFLUENCE_PROFILE:-localhost}"
ACTION="edit"
BASE_URL=""
USERNAME=""
PASSWORD=""

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
        --action)
            ACTION="$2"
            shift 2
            ;;
        --help|-h)
            cat << 'EOF'
Usage: ./confluence-fzf.sh [OPTIONS]

Interactive Confluence page selector with automatic UI detection.

OPTIONS:
    --profile PROFILE   Config profile to use (default: localhost)
    --action ACTION     Action to perform (default: edit)
                        - edit: Open page in editor
                        - read: Display page content
                        - download: Save page as markdown file
    --help, -h          Show this help message

FEATURES:
    - Auto-detects fzf availability
    - Uses fuzzy search if fzf is installed
    - Falls back to numbered menus if fzf is not available
    - Same workflow regardless of UI method

EXAMPLES:
    ./confluence-fzf.sh
    ./confluence-fzf.sh --action read
    ./confluence-fzf.sh --profile work --action download

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

# Load config from confluence-markdown config file
CONFIG_FILE="$HOME/.config/confluence-markdown/config.json"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}Error: Config file not found at $CONFIG_FILE${NC}"
    echo "Create one with: uv run confluence-markdown --init-config"
    exit 1
fi

# Extract config values using Python
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

# Show mode
if $HAS_FZF; then
    echo -e "${BLUE}Fetching pages from $BASE_URL... (fzf mode)${NC}"
else
    echo -e "${BLUE}Fetching pages from $BASE_URL... (menu mode)${NC}"
    echo -e "${YELLOW}Tip: Install fzf for fuzzy search: brew install fzf${NC}"
fi

# Fetch ALL pages from Confluence API with pagination
PAGES_JSON=""
START=0
LIMIT=100

while true; do
    PAGE_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
        "$BASE_URL/rest/api/content?type=page&limit=$LIMIT&start=$START&expand=space" 2>/dev/null)

    if [[ -z "$PAGE_JSON" ]]; then
        if [[ -z "$PAGES_JSON" ]]; then
            echo -e "${RED}Error: Failed to fetch pages from Confluence${NC}"
            exit 1
        fi
        break
    fi

    # Merge results
    if [[ -z "$PAGES_JSON" ]]; then
        PAGES_JSON="$PAGE_JSON"
    else
        PAGES_JSON=$(echo "$PAGES_JSON" "$PAGE_JSON" | python3 -c '
import json, sys
lines = sys.stdin.read().strip().split("\n")
data1 = json.loads(lines[0])
data2 = json.loads(lines[1])
data1["results"].extend(data2.get("results", []))
print(json.dumps(data1))
')
    fi

    # Check if there are more results
    PAGE_SIZE=$(echo "$PAGE_JSON" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("results", [])))')
    if [[ $PAGE_SIZE -lt $LIMIT ]]; then
        break
    fi

    START=$((START + LIMIT))
    echo "  Fetched $START pages so far..."
done

if $HAS_FZF; then
    # FZF MODE: Parse JSON and create fzf-friendly format
    PAGES_LIST=$(echo "$PAGES_JSON" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    results = data.get('results', [])

    if not results:
        print('No pages found', file=sys.stderr)
        sys.exit(1)

    for page in results:
        page_id = page.get('id', '')
        title = page.get('title', 'Untitled')
        space = page.get('space', {})
        space_key = space.get('key', 'UNKNOWN')
        space_name = space.get('name', 'Unknown Space')

        # Format: SPACE_KEY | SPACE_NAME | Title | PageID
        print(f'{space_key:15} | {space_name:30} | {title:50} | {page_id}')
except Exception as e:
    print(f'Error parsing JSON: {e}', file=sys.stderr)
    sys.exit(1)
")

    if [[ -z "$PAGES_LIST" ]]; then
        echo -e "${RED}Error: No pages found or failed to parse response${NC}"
        exit 1
    fi

    # Count pages
    PAGE_COUNT=$(echo "$PAGES_LIST" | wc -l | tr -d ' ')
    echo -e "${GREEN}Found $PAGE_COUNT pages${NC}"
    echo ""

    # Use fzf to select a page
    SELECTED=$(echo "$PAGES_LIST" | fzf \
        --height=80% \
        --border=rounded \
        --prompt="Select page > " \
        --header="Space | Space Name | Title | ID" \
        --preview="echo {}" \
        --preview-window=up:3:wrap \
        --bind="ctrl-/:toggle-preview" \
        --color="header:italic:underline" \
        --no-sort)

    if [[ -z "$SELECTED" ]]; then
        echo -e "${YELLOW}No page selected${NC}"
        exit 0
    fi

    # Extract page details from selection
    PAGE_ID=$(echo "$SELECTED" | awk -F'|' '{print $NF}' | tr -d ' ')
    PAGE_TITLE=$(echo "$SELECTED" | awk -F'|' '{print $3}' | sed 's/^[ \t]*//;s/[ \t]*$//')
    SPACE_KEY=$(echo "$SELECTED" | awk -F'|' '{print $1}' | tr -d ' ')

else
    # SELECT MODE: Parse into arrays
    mapfile -t PAGE_IDS < <(echo "$PAGES_JSON" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    for page in results:
        print(page.get('id', ''))
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
")

    mapfile -t PAGE_TITLES < <(echo "$PAGES_JSON" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    for page in results:
        print(page.get('title', 'Untitled'))
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
")

    mapfile -t SPACE_KEYS < <(echo "$PAGES_JSON" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    for page in results:
        space = page.get('space', {})
        print(space.get('key', 'UNKNOWN'))
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
")

    if [[ ${#PAGE_IDS[@]} -eq 0 ]]; then
        echo -e "${RED}Error: No pages found${NC}"
        exit 1
    fi

    echo -e "${GREEN}Found ${#PAGE_IDS[@]} pages${NC}"
    echo ""

    # Create menu options with space key and title
    PAGE_OPTIONS=()
    for i in "${!PAGE_IDS[@]}"; do
        PAGE_OPTIONS+=("${SPACE_KEYS[$i]} | ${PAGE_TITLES[$i]}")
    done

    # Use bash select
    echo "Select a page (enter number):"
    PS3="Enter selection: "
    select opt in "${PAGE_OPTIONS[@]}"; do
        if [[ -n "$opt" ]]; then
            # Find index of selected option
            for i in "${!PAGE_OPTIONS[@]}"; do
                if [[ "${PAGE_OPTIONS[$i]}" == "$opt" ]]; then
                    PAGE_ID="${PAGE_IDS[$i]}"
                    PAGE_TITLE="${PAGE_TITLES[$i]}"
                    SPACE_KEY="${SPACE_KEYS[$i]}"
                    break
                fi
            done
            break
        else
            echo -e "${RED}Invalid selection${NC}"
        fi
    done
fi

echo ""
echo -e "${BLUE}Selected:${NC} $PAGE_TITLE (ID: $PAGE_ID)"
echo -e "${BLUE}Space:${NC} $SPACE_KEY"
echo ""

# Construct page URL
PAGE_URL="$BASE_URL/pages/viewpage.action?pageId=$PAGE_ID"

# Perform action
case "$ACTION" in
    edit)
        echo -e "${GREEN}Opening in editor...${NC}"
        uv run confluence-markdown \
            --config \
            --profile "$PROFILE" \
            --action edit \
            "$PAGE_URL"
        ;;

    read)
        echo -e "${GREEN}Reading page content...${NC}"
        echo ""
        uv run confluence-markdown \
            --config \
            --profile "$PROFILE" \
            --action read \
            "$PAGE_URL"
        ;;

    download)
        # Create filename from page title
        FILENAME=$(echo "$PAGE_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g').md
        echo -e "${GREEN}Downloading to: $FILENAME${NC}"
        uv run confluence-markdown \
            --config \
            --profile "$PROFILE" \
            --output "$FILENAME" \
            "$PAGE_URL"
        ;;

    *)
        echo -e "${RED}Unknown action: $ACTION${NC}"
        echo "Valid actions: edit, read, download"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Done!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}Page Details:${NC}"
echo -e "  ${BLUE}Title:${NC} $PAGE_TITLE"
echo -e "  ${BLUE}Space:${NC} $SPACE_KEY"
echo -e "  ${BLUE}ID:${NC}    $PAGE_ID"
echo ""
echo -e "${BOLD}View in browser:${NC}"
echo -e "  ${CYAN}$PAGE_URL${NC}"
echo ""
