#!/usr/bin/env bash
#
# confluence-new.sh - Smart wrapper that auto-detects fzf availability
#
# Automatically uses:
#   - confluence-create.sh (fzf version) if fzf is available
#   - confluence-create-simple.sh (select version) if fzf is not available
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if fzf is available
if command -v fzf &> /dev/null; then
    # fzf is available - use the fancy version
    echo "Using fzf-powered interface..."
    exec "$SCRIPT_DIR/confluence-create.sh" "$@"
else
    # fzf not available - use simple select version
    echo "fzf not found - using simple menu interface..."
    echo "(Install fzf for enhanced experience: brew install fzf)"
    echo ""
    exec "$SCRIPT_DIR/confluence-create-simple.sh" "$@"
fi
