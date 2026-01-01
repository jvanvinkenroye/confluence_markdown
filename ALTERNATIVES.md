# Alternatives for Systems Without fzf

Not all systems have fzf installed. Here are all the options available for creating and managing pages.

## Quick Comparison

| Script | Requires | Interface | Best For |
|--------|----------|-----------|----------|
| `confluence-new.sh` | Python, bash | Auto-detects | **Recommended** - Works everywhere |
| `confluence-create.sh` | fzf, Python, bash | Fuzzy search | Best UX when fzf available |
| `confluence-create-simple.sh` | Python, bash only | Numbered menu | Systems without fzf |
| Direct CLI | Python only | Command line | Scripting, automation |

## Option 1: Smart Wrapper (Recommended)

**Script:** `confluence-new.sh`

This automatically uses the best available method:

```bash
./confluence-new.sh
```

**How it works:**
- Checks if `fzf` is installed
- Uses `confluence-create.sh` (fancy) if fzf available
- Falls back to `confluence-create-simple.sh` if not
- Same arguments work for both

**Advantages:**
✅ Works on any system
✅ No need to remember which script to use
✅ Automatically gives best experience available

**Example:**
```bash
# Works everywhere - auto-detects fzf
./confluence-new.sh

# With template
./confluence-new.sh --template templates/meeting-notes.md

# With profile
./confluence-new.sh --profile production
```

## Option 2: Simple Menu (No fzf Required)

**Script:** `confluence-create-simple.sh`

Uses bash's built-in `select` command - works on any Unix system with bash.

```bash
./confluence-create-simple.sh
```

**Interface:**
```
Step 1: Select Space
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Found 2 spaces

Select a space (enter number):
1) TEST - TEST
2) VAMP - Vampire Lair
Enter selection: 2

✓ Selected space: VAMP (Vampire Lair)
```

**Advantages:**
✅ No external dependencies (except Python)
✅ Works on any Unix/Linux/macOS
✅ Simple numbered menu
✅ Same workflow as fzf version

**Disadvantages:**
❌ No fuzzy search
❌ No preview
❌ Can't filter by typing

## Option 3: Direct CLI Commands

**No script needed** - Use the CLI directly:

### Create Page
```bash
# Create page from command line
uv run confluence-markdown --config --profile localhost \
  --action create \
  --space VAMP \
  --title "My Page" \
  --content "# Content here"
```

### Create Page from File
```bash
# Write content to file first
cat > /tmp/page-content.md << 'EOF'
# My Page Title

Page content goes here...
EOF

# Create page from file
CONTENT=$(cat /tmp/page-content.md)
uv run confluence-markdown --config --profile localhost \
  --action create \
  --space VAMP \
  --title "My Page" \
  --content "$CONTENT"
```

### List Pages and Select Manually
```bash
# List all pages
curl -s -u admin:admin \
  "http://localhost:8090/rest/api/content?type=page&spaceKey=VAMP&limit=100" | \
  python3 -c 'import json, sys;
[print(f"{p[\"id\"]:10} | {p[\"title\"]}") for p in json.load(sys.stdin)["results"]]'

# Then edit specific page
uv run confluence-markdown --config --profile localhost \
  --action edit \
  "http://localhost:8090/pages/viewpage.action?pageId=360473"
```

**Advantages:**
✅ No bash script needed
✅ Full control via command line
✅ Easy to automate
✅ Works in any shell (bash, zsh, fish, etc.)

**Disadvantages:**
❌ Need to remember all options
❌ More typing
❌ Need to know space keys and page IDs

## Option 4: Other Text UI Tools

If you can install alternative tools, these work as fzf replacements:

### dialog / whiptail

Create menus with `dialog` or `whiptail`:

```bash
#!/usr/bin/env bash
# Install: apt-get install dialog  (Linux)
# Install: brew install dialog     (macOS)

CHOICE=$(dialog --menu "Select Space" 15 50 4 \
    "TEST" "TEST Space" \
    "VAMP" "Vampire Lair" \
    2>&1 >/dev/tty)

echo "Selected: $CHOICE"
```

### dmenu (Linux only)

```bash
# For X11/Wayland Linux systems
echo -e "TEST\nVAMP" | dmenu -p "Select Space"
```

### percol / peco

Simpler alternatives to fzf:

```bash
# Install
pip install percol
# or
brew install peco

# Use like fzf
echo -e "TEST\nVAMP" | percol
echo -e "TEST\nVAMP" | peco
```

## Installation Guide for fzf

If you want the best experience, install fzf:

### macOS
```bash
brew install fzf
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install fzf
```

### Fedora/RHEL
```bash
sudo dnf install fzf
```

### From Source (Any Unix)
```bash
git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
~/.fzf/install
```

## Feature Comparison

| Feature | fzf Version | Simple Version | Direct CLI |
|---------|-------------|----------------|------------|
| Fuzzy search | ✅ | ❌ | ❌ |
| Live preview | ✅ | ❌ | ❌ |
| Keyboard shortcuts | ✅ | ❌ | ❌ |
| Filter by typing | ✅ | ❌ | ❌ |
| Numbered menu | ❌ | ✅ | ❌ |
| Works without fzf | ❌ | ✅ | ✅ |
| Scriptable | ✅ | ✅ | ✅ |
| Interactive | ✅ | ✅ | ❌ |
| Template support | ✅ | ✅ | ❌ |
| Auto-completion | ❌ | ❌ | ❌ |

## Recommended Workflow by System Type

### Modern Developer Machine (has package manager)
```bash
# Install fzf for best experience
brew install fzf  # macOS
sudo apt install fzf  # Linux

# Use the fancy version
./confluence-create.sh
./confluence-fzf.sh
```

### Minimal Server / Container
```bash
# Use simple version (no fzf needed)
./confluence-create-simple.sh

# Or use direct CLI
uv run confluence-markdown --config --action create ...
```

### Any Machine (Safest)
```bash
# Use smart wrapper - works everywhere
./confluence-new.sh
```

### CI/CD Pipeline
```bash
# Use direct CLI for automation
uv run confluence-markdown \
  --base-url "$CONFLUENCE_URL" \
  --username "$USER" \
  --token "$TOKEN" \
  --action create \
  --space "DOCS" \
  --title "Build $BUILD_NUMBER" \
  --content "$(cat build-report.md)"
```

## Examples

### Example 1: Using Simple Version

```bash
$ ./confluence-create-simple.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Confluence Page Creator (Simple Mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Select Space
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching spaces from http://localhost:8090...
Found 2 spaces

Select a space (enter number):
1) TEST - TEST
2) VAMP - Vampire Lair
Enter selection: 2
✓ Selected space: VAMP (Vampire Lair)

Step 2: Select Parent Page (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching pages in space VAMP...
Found 6 pages

Select a parent page (or choose 'No Parent'):
1) No Parent (create at root level)
2) Vampire Lair Home
3) Welcome to the Vampire Lair
4) Hunting Grounds Map
Enter selection: 1
✓ Creating page at root level

Step 3: Enter Page Title
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enter page title: Blood Types Reference
✓ Title: Blood Types Reference

[Editor opens...]
```

### Example 2: Using Smart Wrapper

```bash
$ ./confluence-new.sh
Using fzf-powered interface...
[Opens confluence-create.sh with fzf]

# OR on system without fzf:
$ ./confluence-new.sh
fzf not found - using simple menu interface...
(Install fzf for enhanced experience: brew install fzf)

[Opens confluence-create-simple.sh with select menus]
```

### Example 3: Direct CLI Automation

```bash
#!/usr/bin/env bash
# Create multiple pages from a list

pages=(
    "Introduction|# Introduction\n\nWelcome to our docs"
    "Getting Started|# Getting Started\n\nInstall with..."
    "API Reference|# API Reference\n\nEndpoints..."
)

for page in "${pages[@]}"; do
    title=$(echo "$page" | cut -d'|' -f1)
    content=$(echo "$page" | cut -d'|' -f2)

    echo "Creating: $title"
    uv run confluence-markdown --config --profile localhost \
        --action create \
        --space DOCS \
        --title "$title" \
        --content "$content"
done
```

## Troubleshooting

### "select: not found" error

Your shell might not be bash. Run with bash explicitly:
```bash
bash ./confluence-create-simple.sh
```

### "command not found: fzf"

Either:
1. Install fzf (recommended)
2. Use the simple version: `./confluence-create-simple.sh`
3. Use the smart wrapper: `./confluence-new.sh`

### Python not found

All scripts require Python for JSON parsing. Install Python 3:
```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt install python3

# Fedora
sudo dnf install python3
```

## See Also

- [CREATE_PAGES.md](CREATE_PAGES.md) - Full page creation guide
- [FZF_WORKFLOW.md](FZF_WORKFLOW.md) - fzf-powered workflows
- [README.md](README.md) - Main documentation
