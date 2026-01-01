# Interactive Page Selection with fzf

This guide shows how to use fzf (fuzzy finder) for interactive Confluence page selection and editing.

## Quick Start

```bash
# Install fzf if not already installed
brew install fzf

# Use the interactive selector
./confluence-fzf.sh

# With specific profile
./confluence-fzf.sh --profile work

# Different actions
./confluence-fzf.sh --action read
./confluence-fzf.sh --action download
```

## What It Does

The `confluence-fzf.sh` script:

1. **Fetches all pages** from your Confluence instance via REST API
2. **Displays them** in an interactive fzf menu with:
   - Space key
   - Space name
   - Page title
   - Page ID
3. **Lets you search/filter** using fuzzy matching
4. **Performs action** on selected page (edit/read/download)

## Usage

### Basic Interactive Edit

```bash
./confluence-fzf.sh
```

This will:
1. Show all pages from the `localhost` profile
2. Open fzf for selection
3. Open selected page in your editor
4. Upload changes when you save and close

### With Different Profile

```bash
./confluence-fzf.sh --profile work
```

### Different Actions

**Read page content:**
```bash
./confluence-fzf.sh --action read
```

**Download to file:**
```bash
./confluence-fzf.sh --action download
```
Creates a file named `page-title.md`

## fzf Navigation

When the fzf menu appears:

- **Type** to filter/search pages
- **↑/↓ arrows** to navigate
- **Enter** to select
- **Esc** or **Ctrl+C** to cancel
- **Ctrl+/** to toggle preview
- **Tab** to multi-select (not used in this script)

## Search Examples

In the fzf interface, you can search by:

**Space key:**
```
TEST
```
Shows all pages in TEST space

**Page title:**
```
elephant
```
Shows all pages with "elephant" in the title

**Fuzzy matching:**
```
vlh
```
Matches "Vampire Lair Home"

**Multiple terms:**
```
vamp home
```
Matches pages with both "vamp" and "home"

## Example Workflow

### Scenario: Edit a page about elephants

```bash
# 1. Run the script
./confluence-fzf.sh

# 2. In fzf, type: elephant
#    This filters to pages with "elephant" in title

# 3. Press Enter to select the page

# 4. Your editor opens with the page content

# 5. Make changes and save

# 6. Close editor

# 7. Changes are automatically uploaded to Confluence
```

## Script Output

```
Fetching pages from http://localhost:8090...
Found 5 pages

TEST            | TEST                           | TEST
VAMP            | Vampire Lair                   | Vampire Lair Home
VAMP            | Vampire Lair                   | Welcome to the Vampire Lair
VAMP            | Vampire Lair                   | Hunting Grounds Map
VAMP            | Vampire Lair                   | Ancient Vampire Registry

[fzf interface appears here]

Selected: Vampire Lair Home (ID: 360473)
Space: VAMP

Opening in editor...
[Editor opens, you make changes, save and close]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Done!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Page Details:
  Title: Vampire Lair Home
  Space: VAMP
  ID:    360473

View in browser:
  http://localhost:8090/pages/viewpage.action?pageId=360473
```

## Requirements

1. **fzf** - Fuzzy finder
   ```bash
   # macOS
   brew install fzf

   # Linux (Debian/Ubuntu)
   sudo apt install fzf

   # Linux (Fedora)
   sudo dnf install fzf
   ```

2. **curl** - For API requests (usually pre-installed)

3. **python3** - For JSON parsing (usually pre-installed)

4. **Saved config** - Must have a profile in `~/.config/confluence-markdown/config.json`

## Customization

### Change Default Profile

Edit the script or set environment variable:
```bash
export CONFLUENCE_PROFILE=work
./confluence-fzf.sh
```

### Change fzf Appearance

Modify the `fzf` command in the script (around line 120):

```bash
SELECTED=$(echo "$PAGES_LIST" | fzf \
    --height=90% \              # Make it taller
    --border=sharp \            # Different border style
    --prompt="Choose > " \      # Different prompt
    --color="dark" \            # Dark color scheme
    --preview-window=right:50%  # Preview on right side
)
```

See `man fzf` for all options.

### Add More Page Information

Modify the Python parsing code to include more fields:

```python
# Example: Add page status and creation date
for page in results:
    page_id = page.get('id', '')
    title = page.get('title', 'Untitled')
    status = page.get('status', 'current')
    # ... format with additional fields
```

## Advanced Usage

### Create Alias

Add to your `.bashrc` or `.zshrc`:

```bash
alias cedit='~/path/to/confluence-fzf.sh --action edit'
alias cread='~/path/to/confluence-fzf.sh --action read'
alias cdownload='~/path/to/confluence-fzf.sh --action download'
```

Then use:
```bash
cedit        # Quick edit
cread        # Quick read
cdownload    # Quick download
```

### Integration with Other Tools

**Preview page in bat (syntax highlighter):**

Modify the fzf command:
```bash
--preview="uv run confluence-markdown --config --profile $PROFILE --action read $BASE_URL/pages/viewpage.action?pageId={-1} 2>/dev/null | bat --style=plain --color=always -l markdown"
```

**Open in browser instead of editor:**

Create a variant:
```bash
# Open selected page in default browser
PAGE_URL="$BASE_URL/pages/viewpage.action?pageId=$PAGE_ID"
open "$PAGE_URL"  # macOS
# or
xdg-open "$PAGE_URL"  # Linux
```

## Troubleshooting

### fzf Not Found

```
Error: fzf command not found
```

**Solution:** Install fzf:
```bash
brew install fzf  # macOS
```

### No Pages Found

```
Error: No pages found or failed to parse response
```

**Possible causes:**
1. Wrong credentials in config
2. Network issue
3. Confluence instance down
4. Profile doesn't exist

**Solution:** Test authentication:
```bash
uv run confluence-markdown --config --profile localhost --action test-auth
```

### Cannot Load Config

```
Error: Config file not found
```

**Solution:** Create config:
```bash
uv run confluence-markdown --init-config
# Edit ~/.config/confluence-markdown/config.json
```

### Editor Doesn't Open

**Solution:** Set EDITOR environment variable:
```bash
export EDITOR=vim
./confluence-fzf.sh
```

## Performance Tips

### Limit Page Count

For large Confluence instances with thousands of pages:

1. **Filter by space:**

   Modify the API call to specific space:
   ```bash
   curl -s -u "$USERNAME:$PASSWORD" \
       "$BASE_URL/rest/api/content?type=page&spaceKey=MYSPACE&limit=1000"
   ```

2. **Recent pages only:**

   Add ordering:
   ```bash
   "$BASE_URL/rest/api/content?type=page&limit=100&orderby=lastmodified"
   ```

3. **Cache results:**

   Save pages list to file and refresh periodically:
   ```bash
   # Cache for 1 hour
   CACHE_FILE="/tmp/confluence-pages-$PROFILE.json"
   if [[ ! -f "$CACHE_FILE" ]] || [[ $(find "$CACHE_FILE" -mmin +60) ]]; then
       curl ... > "$CACHE_FILE"
   fi
   PAGES_JSON=$(cat "$CACHE_FILE")
   ```

## Comparison with Manual Workflow

### Before (Manual):
1. Open browser
2. Go to Confluence
3. Search for page
4. Click page
5. Click Edit
6. Edit in browser (slow rich text editor)
7. Click Save

### After (With fzf):
1. Run `./confluence-fzf.sh`
2. Type search term
3. Press Enter
4. Edit in your preferred editor
5. Save and close

**Time saved:** ~30 seconds per edit
**Bonus:** Use your favorite editor with all its features!

## See Also

- [README.md](README.md) - Main documentation
- [CONTENT_TYPES.md](CONTENT_TYPES.md) - Supported content formats
- [TODO.md](TODO.md) - Planned improvements
- [CLAUDE.md](CLAUDE.md) - Architecture documentation
