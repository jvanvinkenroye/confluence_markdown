#!/usr/bin/env bash
#
# confluence-fzf.sh - Interactive Confluence page selector with fzf
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
NC='\033[0m' # No Color

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
            echo "Usage: $0 [--profile PROFILE] [--action ACTION]"
            echo ""
            echo "Actions:"
            echo "  edit     - Edit selected page in editor (default)"
            echo "  read     - Display selected page content"
            echo "  download - Download selected page to markdown file"
            echo ""
            echo "Examples:"
            echo "  $0"
            echo "  $0 --profile work --action read"
            echo "  $0 --action download"
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

echo -e "${BLUE}Fetching pages from $BASE_URL...${NC}"

# Fetch all pages from Confluence API
# This gets pages with their titles and IDs
PAGES_JSON=$(curl -s -u "$USERNAME:$PASSWORD" \
    "$BASE_URL/rest/api/content?type=page&limit=1000&expand=space" 2>/dev/null)

# Check if curl succeeded
if [[ -z "$PAGES_JSON" ]]; then
    echo -e "${RED}Error: Failed to fetch pages from Confluence${NC}"
    exit 1
fi

# Parse JSON and create fzf-friendly format
# Format: "SPACE_KEY | Page Title | PageID"
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

# Extract page ID from selection (last field after last |)
PAGE_ID=$(echo "$SELECTED" | awk -F'|' '{print $NF}' | tr -d ' ')
PAGE_TITLE=$(echo "$SELECTED" | awk -F'|' '{print $3}' | sed 's/^[ \t]*//;s/[ \t]*$//')
SPACE_KEY=$(echo "$SELECTED" | awk -F'|' '{print $1}' | tr -d ' ')

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
