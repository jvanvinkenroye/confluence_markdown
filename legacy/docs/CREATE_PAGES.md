# Creating Pages Interactively

The `confluence-create.sh` script provides a guided, interactive workflow for creating Confluence pages with fzf-powered selection.

## Quick Start

```bash
./confluence-create.sh
```

This launches an interactive wizard that walks you through:
1. 📁 Select a space
2. 📄 Choose a parent page (optional)
3. ✍️  Enter page title
4. 📝 Edit content in your editor
5. ✅ Page created automatically!

## Workflow

### Step 1: Select Space

The script fetches all available spaces and presents them in an fzf menu:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Confluence Page Creator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Select Space
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching spaces from http://localhost:8090...
Found 2 spaces

┌─ Select space > ─────────────────────────┐
│ > test                                   │
│   2/2                                    │
├──────────────────────────────────────────┤
│   TEST | TEST               | global    │
│   VAMP | Vampire Lair       | global    │
└──────────────────────────────────────────┘
```

**Search/Filter:**
- Type to filter: `vamp` shows only Vampire Lair
- Arrow keys to navigate
- Enter to select

### Step 2: Select Parent Page (Optional)

If you want to create a child page under an existing page:

```
Step 2: Select Parent Page (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching pages in space VAMP...
Found 5 pages
Select a parent page, or press ESC to create at root level

┌─ Select parent (ESC for none) > ────────┐
│ >                                        │
│   6/6                                    │
├──────────────────────────────────────────┤
│   [ No Parent - Create at root level ]  │
│   Vampire Lair Home                      │
│   Welcome to the Vampire Lair            │
│   Hunting Grounds Map                    │
│   Ancient Vampire Registry               │
│   Elephant Migration Patterns            │
└──────────────────────────────────────────┘
```

**Options:**
- Select "No Parent" for root-level page
- Select a page to create as child
- Press ESC to skip (same as No Parent)

### Step 3: Enter Title

```
Step 3: Enter Page Title
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enter page title: My New Documentation Page
✓ Title: My New Documentation Page
```

### Step 4: Edit Content

Your default editor opens with a markdown template:

```markdown
# My New Documentation Page

## Overview

Write your page content here using Markdown.

## Sections

### Section 1

Content goes here...
```

**Edit, save, and close** the editor to continue.

### Step 5: Page Created!

```
Step 5: Creating Page
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Creating page...
✅ Page created successfully!
   Title: My New Documentation Page
   Space: VAMP
   Page ID: 360488
   URL: http://localhost:8090/pages/viewpage.action?pageId=360488

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Page created successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Using Templates

The script includes pre-made templates for common page types.

### Available Templates

**Meeting Notes:**
```bash
./confluence-create.sh --template templates/meeting-notes.md
```

Includes sections for:
- Attendees
- Agenda
- Discussion
- Decisions
- Action items (with table)
- Next steps

**Project Plan:**
```bash
./confluence-create.sh --template templates/project-plan.md
```

Includes sections for:
- Overview & objectives
- Timeline (with phases table)
- Team & resources
- Risks & mitigation
- Success criteria

**Documentation:**
```bash
./confluence-create.sh --template templates/documentation.md
```

Includes sections for:
- Usage & examples
- API reference
- Configuration
- Architecture
- Testing
- Troubleshooting

### Creating Custom Templates

Create a markdown file in the `templates/` directory:

```bash
cat > templates/custom.md << 'EOF'
# Custom Template

Your custom content here...
EOF

# Use it
./confluence-create.sh --template templates/custom.md
```

## Advanced Usage

### Different Profile

```bash
./confluence-create.sh --profile work
```

### Environment Variable

```bash
export CONFLUENCE_PROFILE=production
./confluence-create.sh
```

### Customize Editor

```bash
export EDITOR=vim
./confluence-create.sh
```

Or use VS Code:
```bash
export EDITOR=code
./confluence-create.sh
```

## Aliases for Quick Access

Add to your `.bashrc` or `.zshrc`:

```bash
# Quick page creation
alias cnew='~/src_own/confluence_markdown/confluence-create.sh'

# With templates
alias cmeet='~/src_own/confluence_markdown/confluence-create.sh --template templates/meeting-notes.md'
alias cproj='~/src_own/confluence_markdown/confluence-create.sh --template templates/project-plan.md'
alias cdoc='~/src_own/confluence_markdown/confluence-create.sh --template templates/documentation.md'
```

Then use:
```bash
cnew          # Create any page
cmeet         # Create meeting notes
cproj         # Create project plan
cdoc          # Create documentation
```

## Tips & Tricks

### 1. Organize with Hierarchy

Create a structured documentation tree:

```
Documentation Root (manually created)
├── API Documentation (confluence-create.sh with parent)
│   ├── REST Endpoints (confluence-create.sh with parent)
│   └── WebSocket API (confluence-create.sh with parent)
└── Guides (confluence-create.sh with parent)
    ├── Getting Started (confluence-create.sh with parent)
    └── Advanced Topics (confluence-create.sh with parent)
```

### 2. Use Templates as Starting Points

Don't like the template? Just delete the template content and write your own!

### 3. Quick Iteration

The script shows the page URL at the end. Keep it open in your browser and use:
```bash
./confluence-fzf.sh --action edit
```
to quickly make changes.

### 4. Bulk Creation

Create multiple pages quickly:
```bash
# Create several related pages
for topic in "Introduction" "Installation" "Configuration" "Usage"; do
    echo "# $topic" | \
    uv run confluence-markdown --config --profile localhost \
      --action create --space DOCS --title "$topic" --content -
done
```

## Troubleshooting

### fzf Not Found

```
Error: fzf command not found
```

Install fzf:
```bash
brew install fzf  # macOS
sudo apt install fzf  # Ubuntu/Debian
```

### No Spaces Found

```
Error: No spaces found
```

Check your credentials:
```bash
uv run confluence-markdown --config --profile localhost --action test-auth
```

### Editor Doesn't Open

Set your EDITOR:
```bash
export EDITOR=vim
./confluence-create.sh
```

### File Not Modified

If you exit the editor without saving:
```
No changes made. Aborting.
```

This is intentional - the script detects if you didn't make changes.

## Full Example Session

```bash
$ ./confluence-create.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Confluence Page Creator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Select Space
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching spaces from http://localhost:8090...
Found 2 spaces

[Select VAMP space in fzf]

✓ Selected space: VAMP (Vampire Lair)

Step 2: Select Parent Page (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching pages in space VAMP...
Found 6 pages
Select a parent page, or press ESC to create at root level

[Select "Vampire Lair Home" in fzf]

✓ Parent page: Vampire Lair Home (ID: 360473)

Step 3: Enter Page Title
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enter page title: Vampire Diet and Nutrition
✓ Title: Vampire Diet and Nutrition

Step 4: Create Content
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Opening editor: vim
Edit your content, save, and close the editor to continue...

[vim opens, you edit content, save and quit]

✓ Content ready (25 lines)

Step 5: Creating Page
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Creating page...
✅ Page created successfully!
   Title: Vampire Diet and Nutrition
   Space: VAMP
   Page ID: 360489
   URL: http://localhost:8090/pages/viewpage.action?pageId=360489

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Page created successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Comparison: Manual vs Script

### Before (Manual Web UI)
1. Log into Confluence
2. Navigate to space
3. Click "Create"
4. Select page type
5. Enter title
6. Select parent (if needed)
7. Use slow rich-text editor
8. Click Save

**Time:** ~2-3 minutes

### After (With Script)
1. Run `./confluence-create.sh`
2. Select space (type to filter)
3. Select parent (optional)
4. Enter title
5. Edit in your favorite editor
6. Done!

**Time:** ~30 seconds

**Bonus:** Your preferred editor, version control possible, scriptable!

## See Also

- [confluence-fzf.sh](FZF_WORKFLOW.md) - Edit existing pages
- [CONTENT_TYPES.md](CONTENT_TYPES.md) - Supported formats
- [README.md](README.md) - Main documentation
