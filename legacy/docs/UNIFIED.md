# Unified Scripts - No fzf Required!

Both main scripts now work with OR without fzf! 🎉

## ✅ What's Changed

Both scripts are now **unified** with automatic fzf detection:

### 1. confluence-create.sh
**Create new pages** - Works everywhere!
```bash
./confluence-create.sh
```

### 2. confluence-fzf.sh
**Edit/read existing pages** - Works everywhere!
```bash
./confluence-fzf.sh
```

## 🎯 Auto-Detection

Both scripts automatically detect if fzf is installed:

**With fzf:**
```
Fetching pages from http://localhost:8090... (fzf mode)
[Shows fancy fuzzy search with filtering]
```

**Without fzf:**
```
Fetching pages from http://localhost:8090... (menu mode)
Tip: Install fzf for fuzzy search: brew install fzf

Select a page (enter number):
1) VAMP | Vampire Lair Home
2) VAMP | Welcome to the Vampire Lair
3) TEST | TEST
Enter selection:
```

## 📋 Complete Workflow Comparison

### Creating Pages

**With fzf:**
```bash
$ ./confluence-create.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Confluence Page Creator (fzf mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Select Space
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching spaces...
Found 2 spaces

┌─ Select space > ───────────┐
│ > vamp                     │  ← Type to filter!
├────────────────────────────┤
│ VAMP | Vampire Lair        │
└────────────────────────────┘
```

**Without fzf:**
```bash
$ ./confluence-create.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Confluence Page Creator (menu mode)
  Tip: Install fzf for enhanced fuzzy search experience
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Select Space
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching spaces...
Found 2 spaces

Select a space (enter number):
1) TEST - TEST
2) VAMP - Vampire Lair
Enter selection: 2
✓ Selected space: VAMP (Vampire Lair)
```

### Editing Pages

**With fzf:**
```bash
$ ./confluence-fzf.sh

Fetching pages from http://localhost:8090... (fzf mode)
Found 6 pages

┌─ Select page > ────────────────────────────┐
│ > elephant                                 │
├────────────────────────────────────────────┤
│ VAMP | Elephant Migration Patterns        │
│ TEST | Elephant Diet Guide                │
└────────────────────────────────────────────┘

Selected: Elephant Migration Patterns
Opening in editor...
```

**Without fzf:**
```bash
$ ./confluence-fzf.sh

Fetching pages from http://localhost:8090... (menu mode)
Tip: Install fzf for fuzzy search: brew install fzf
Found 6 pages

Select a page (enter number):
1) VAMP | Vampire Lair Home
2) VAMP | Welcome to the Vampire Lair
3) VAMP | Elephant Migration Patterns
4) TEST | TEST
5) TEST | Elephant Diet Guide
Enter selection: 3
✓ Selected: Elephant Migration Patterns

Opening in editor...
```

## 🚀 All Features Work in Both Modes

| Feature | fzf Mode | Menu Mode |
|---------|----------|-----------|
| Create pages | ✅ | ✅ |
| Edit pages | ✅ | ✅ |
| Read pages | ✅ | ✅ |
| Download pages | ✅ | ✅ |
| Select space | ✅ | ✅ |
| Select parent | ✅ | ✅ |
| Templates | ✅ | ✅ |
| Multiple profiles | ✅ | ✅ |
| Fuzzy search | ✅ | ❌ |
| Live preview | ✅ | ❌ |

## 📁 Final Script Status

| Script | Status | Purpose | Requires fzf? |
|--------|--------|---------|---------------|
| **confluence-create.sh** | ✅ Unified | Create new pages | ❌ No |
| **confluence-fzf.sh** | ✅ Unified | Edit existing pages | ❌ No |
| confluence-create-simple.sh | 🗑️ Removed | Merged into confluence-create.sh | - |
| confluence-new.sh | 🗑️ Removed | No longer needed | - |

## 💡 Usage Examples

### Creating a New Page

```bash
# Works with or without fzf
./confluence-create.sh

# With template
./confluence-create.sh --template templates/meeting-notes.md

# Different profile
./confluence-create.sh --profile production
```

### Editing an Existing Page

```bash
# Works with or without fzf
./confluence-fzf.sh

# Just read it
./confluence-fzf.sh --action read

# Download to file
./confluence-fzf.sh --action download
```

### Recommended Aliases

Add to your `.bashrc` or `.zshrc`:

```bash
# Page creation
alias cnew='~/src_own/confluence_markdown/confluence-create.sh'
alias cmeet='~/src_own/confluence_markdown/confluence-create.sh --template templates/meeting-notes.md'
alias cproj='~/src_own/confluence_markdown/confluence-create.sh --template templates/project-plan.md'

# Page editing
alias cedit='~/src_own/confluence_markdown/confluence-fzf.sh'
alias cread='~/src_own/confluence_markdown/confluence-fzf.sh --action read'
alias cdown='~/src_own/confluence_markdown/confluence-fzf.sh --action download'
```

Then use:
```bash
cnew     # Create new page
cedit    # Edit existing page
cread    # Read page
cdown    # Download page
cmeet    # New meeting notes
cproj    # New project plan
```

## 🎨 Installation Options

### Option 1: Use Without fzf (Works Now!)
```bash
# Just run it - works on any system
./confluence-create.sh
./confluence-fzf.sh
```

### Option 2: Install fzf for Better Experience
```bash
# macOS
brew install fzf

# Ubuntu/Debian
sudo apt install fzf

# Fedora
sudo dnf install fzf

# From source (any Unix)
git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
~/.fzf/install
```

After installing fzf, the scripts automatically use it!

## 🔄 Migration Guide

If you were using the old separate scripts:

**Old way:**
```bash
# Had to choose which script
./confluence-create-simple.sh   # For systems without fzf
./confluence-new.sh              # Wrapper script
```

**New way:**
```bash
# Just use the main script - it auto-detects
./confluence-create.sh
```

## 🎯 Benefits

✅ **Single codebase** - Easier to maintain
✅ **Automatic fallback** - Works everywhere
✅ **Same commands** - No need to remember different scripts
✅ **Better UX** - Clear indication of which mode is active
✅ **Helpful tips** - Suggests installing fzf when in menu mode
✅ **No breaking changes** - Existing aliases still work

## 📊 Performance

Both modes perform equally well:

- **API calls**: Automatic pagination fetches ALL results
- **Speed**: Identical for page operations
- **Memory**: Similar usage
- **Pagination**: Automatically fetches 100+ spaces and 1000+ pages

### Pagination Support (v2.0)

Both scripts now automatically fetch **ALL** results using pagination:
- **Small instances (<100 items)**: Single API call (fast)
- **Large instances (>1000 items)**: Multiple calls with progress indicators
- **No data loss**: Every space and page is now visible

See [PAGINATION.md](PAGINATION.md) for technical details.

The only difference is the UI for selection:
- **fzf mode**: Can type to filter, see preview
- **Menu mode**: Select by number

## 🐛 Troubleshooting

### "select: not found"

Your shell might not be bash. Run with:
```bash
bash ./confluence-create.sh
```

### Want to force menu mode even with fzf?

Currently not supported, but you can temporarily rename fzf:
```bash
alias fzf_backup=$(which fzf)
sudo mv $(which fzf) $(which fzf).backup
./confluence-create.sh   # Uses menu mode
sudo mv $(which fzf).backup $(which fzf)
```

### Scripts still require Python

Yes, Python 3 is still required for JSON parsing. This is available on virtually all systems.

## 📚 Documentation

- [README.md](README.md) - Main documentation
- [CREATE_PAGES.md](CREATE_PAGES.md) - Page creation guide
- [FZF_WORKFLOW.md](FZF_WORKFLOW.md) - Advanced workflows
- [CONTENT_TYPES.md](CONTENT_TYPES.md) - Supported formats
- [ALTERNATIVES.md](ALTERNATIVES.md) - Alternative methods
- [CLAUDE.md](CLAUDE.md) - Architecture overview

## 🎉 Summary

**Both main scripts now work on ANY system!**

- ✅ No fzf? No problem!
- ✅ Have fzf? Even better!
- ✅ Same commands everywhere
- ✅ Automatic detection
- ✅ Clear feedback

Just run the scripts - they'll figure out the rest! 🚀
