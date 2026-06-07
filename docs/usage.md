# confluence-markdown — User Guide

> **Proof of Concept** — This tool is experimental. No guarantee of correctness or stability.

`confluence-markdown` is a CLI tool for reading, editing, and creating Confluence Data Center pages in Markdown format.

---

## Table of Contents

- [Installation](#installation)
- [Authentication](#authentication)
- [Configuration](#configuration)
- [Reading Pages](#reading-pages)
- [Editing Pages](#editing-pages)
- [Creating Pages](#creating-pages)
- [Searching](#searching)
- [Downloading](#downloading)
- [Listing Child Pages](#listing-child-pages)
- [Global Options](#global-options)
- [Shell Completion](#shell-completion)

---

## Installation

```bash
uv tool install git+https://github.com/jvanvinkenroye/confluence_markdown.git
```

---

## Authentication

Three authentication methods are supported:

### Personal Access Token (recommended)

```bash
confluence-markdown --base-url https://confluence.example.com \
  --username myuser \
  --token MY_TOKEN \
  --action test-auth
```

### Username + Password

```bash
confluence-markdown --base-url https://confluence.example.com \
  --username myuser \
  --password mypassword \
  --action test-auth
```

### Bearer Token (OAuth)

```bash
confluence-markdown --base-url https://confluence.example.com \
  --token MY_BEARER_TOKEN \
  --action test-auth
```

---

## Configuration

Credentials can be saved so they don't need to be provided on every call. Secrets (token, password) are stored in the **system keychain** (macOS Keychain) — not as plaintext.

### Initial setup

Interactive (recommended):

```bash
confluence-markdown --action config set
# Base URL: https://confluence.example.com
# Username: myuser
# Token: ****
```

With flags (for scripting):

```bash
confluence-markdown --action config set \
  --base-url https://confluence.example.com \
  --username myuser \
  --token MY_TOKEN
```

### Show current configuration

```bash
confluence-markdown --action config show
# Profile: default
#   base_url: https://confluence.example.com
#   username: myuser
#   token: ****
```

Show a different profile:

```bash
confluence-markdown --action config show --profile work
```

### List all profiles

```bash
confluence-markdown --action config list
# Available profiles:
#   - default (base_url: https://confluence.example.com)
#   - work    (base_url: https://work.confluence.com)
```

### Delete a profile

```bash
confluence-markdown --action config delete --profile work
```

### Test authentication

```bash
confluence-markdown --action config test --config
# Authentication successful!
#    User: John Doe
#    Username: myuser
```

### Multiple profiles

Profiles allow using different Confluence instances or accounts:

```bash
# Create a second profile
confluence-markdown --action config set \
  --base-url https://work.confluence.com \
  --username workuser \
  --token WORK_TOKEN \
  --profile work

# Use a profile
confluence-markdown --action read --config --profile work \
  "https://work.confluence.com/pages/viewpage.action?pageId=12345"
```

### Per-space configuration

Edit `~/.config/confluence-markdown/config.json` to set per-space defaults:

```json
{
  "default": {
    "base_url": "https://confluence.example.com",
    "username": "myuser",
    "token_in_keychain": true,
    "editor": "vim",
    "table_format": "markdown",
    "spaces": {
      "DOCS": { "editor": "code", "table_format": "yaml" },
      "WIKI": { "editor": "nano" }
    }
  }
}
```

**Config file location:** `~/.config/confluence-markdown/config.json`
Permissions are automatically set to `600`. Token and password are stored in the keychain.

---

## Reading Pages

### Read a single page

```bash
confluence-markdown --action read --config \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Raw Markdown output (no Rich rendering):

```bash
confluence-markdown --action read --config --raw \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Save to file:

```bash
confluence-markdown --action read --config \
  --output page.md \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

### Browse recently viewed pages (interactive)

Opens an interactive selector of recently viewed pages:

```bash
confluence-markdown --action read-recent --config
```

Adjust the number of pages shown:

```bash
confluence-markdown --action read-recent --config --limit 20
```

Without fzf (InquirerPy fallback):

```bash
confluence-markdown --action read-recent --config --no-fzf
```

---

## Editing Pages

### Open a page in the editor

Opens the page in the configured editor (`$EDITOR`, default: `nvim`):

```bash
confluence-markdown --action edit --config \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Use a specific editor:

```bash
confluence-markdown --action edit --config --editor code \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Edit tables in YAML format (easier for complex tables):

```bash
confluence-markdown --action edit --config --table-format yaml \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

### Non-interactive editing (scripting)

With `--content`, the editor is skipped — the provided content is uploaded directly:

```bash
confluence-markdown --action edit --config \
  --content "## New Section

This content was added automatically." \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Content from a file:

```bash
confluence-markdown --action edit --config \
  --content "$(cat my-page.md)" \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Upload HTML content:

```bash
confluence-markdown --action edit --config \
  --content "<h2>Title</h2><p>Text</p>" \
  --content-type html \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

### Edit recently modified pages (interactive)

```bash
confluence-markdown --action edit-recent --config
```

### Add content (append / prepend)

Append content to an existing page:

```bash
confluence-markdown --action add --config \
  --content "## Appendix

This text was appended." \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

Prepend content:

```bash
confluence-markdown --action add --config \
  --prepend \
  --content "## Notice

This page is outdated." \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

---

## Creating Pages

### Fully interactive (recommended)

When `--space` and `--parent-id` are omitted, the tool guides you interactively:

1. **Space selection** — fzf list of all available spaces
2. **Parent page selection** — choose one of:
   - *No parent* — page is created at root level
   - *Search in space* — all pages in the space loaded into fzf for fuzzy search
   - *Pick from recent pages* — last 20 modified pages in fzf

```bash
# Fully interactive: select space, parent, then edit in editor
confluence-markdown --action create-edit

# Space known, parent interactive
confluence-markdown --action create-edit --space MYSPACE
```

### Non-interactive (scripting)

Provide all parameters to skip every prompt:

```bash
confluence-markdown --action create \
  --space MYSPACE \
  --title "New Page" \
  --content "## Introduction

This is the content of the new page."
```

As a child of a known page:

```bash
confluence-markdown --action create \
  --space MYSPACE \
  --title "Child Page" \
  --parent-id 12345 \
  --content "## Content"
```

### Create a page in the editor

Opens the editor with a template — title is taken from the first `#` heading:

```bash
# Fully interactive
confluence-markdown --action create-edit

# With pre-filled title
confluence-markdown --action create-edit --space MYSPACE --title "Draft: New Page"
```

### Create a task page

Creates a structured task page (specific format for task tracking):

```bash
confluence-markdown --action create-task --config \
  --parent-id 12345 \
  --title "XWiki Migration" \
  --category "Tools" \
  --priority 80 \
  --status offen \
  --content "Task description"
```

**Priority:** `100` = very high, `80` = high, `50` = medium, `0` = low
**Status:** `offen`, `in Arbeit`, `erledigt`, `Backlog`, `wont do`

---

## Searching

### Full-text search

```bash
confluence-markdown --action search --config --query "Confluence Migration"
```

Limit the number of results:

```bash
confluence-markdown --action search --config --query "Meeting Notes" --limit 20
```

### CQL search (Confluence Query Language)

```bash
confluence-markdown --action search --config \
  --cql "space = MYSPACE AND title ~ 'Meeting' ORDER BY lastmodified DESC"
```

Pages by current user:

```bash
confluence-markdown --action search --config \
  --cql "creator = currentUser() ORDER BY created DESC" \
  --limit 10
```

---

## Downloading

### Download a single page

```bash
confluence-markdown --action download --config \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

To a specific file:

```bash
confluence-markdown --action download --config \
  --output page.md \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

### Download a page and all child pages

```bash
confluence-markdown --action download --config \
  --recursive \
  --output-dir ./export \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

All files are saved as `<page-title>.md` in the target directory.

---

## Listing Child Pages

### Direct children only

```bash
confluence-markdown --action list-children --config \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

### All descendants recursively (parallel)

```bash
confluence-markdown --action list-children --config \
  --recursive \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

---

## Global Options

| Option | Description |
|--------|-------------|
| `--config` | Load credentials from saved profile |
| `--profile NAME` | Select profile (default: `default`) |
| `--base-url URL` | Confluence base URL |
| `--username USER` | Username |
| `--token TOKEN` | Personal Access Token |
| `--password PASS` | Password |
| `--raw` | Output raw Markdown (no Rich rendering) |
| `--width N` | Override output width for Rich rendering |
| `--verbose` | Enable verbose debug output |
| `--quiet` / `-q` | Suppress informational messages (for scripting) |
| `--no-fzf` | Disable fzf, use InquirerPy instead |
| `--no-cache` | Disable response cache |
| `--clear-cache` | Clear cache and exit |
| `--editor PROG` | Editor for edit actions (e.g. `vim`, `nano`, `code`) |
| `--table-format` | Table format when editing: `markdown` or `yaml` |
| `--limit N` | Number of results (default: `10`) |

---

## Shell Completion

### Bash

```bash
# Add to ~/.bashrc:
eval "$(register-python-argcomplete confluence-markdown)"
```

Or with `--completion`:

```bash
confluence-markdown --completion bash >> ~/.bashrc
source ~/.bashrc
```

### Zsh

```bash
confluence-markdown --completion zsh >> ~/.zshrc
source ~/.zshrc
```

---

## Tips & Tricks

### Quiet mode for scripting

```bash
# Output only the page URL, suppress INFO messages
confluence-markdown --action add --config --quiet \
  --content "Automated entry" \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

### Replace page content from a script

```bash
#!/usr/bin/env bash
set -euo pipefail

PAGE_URL="https://confluence.example.com/pages/viewpage.action?pageId=12345"
CONTENT=$(./generate_report.py)

confluence-markdown --action edit --config --quiet \
  --content "$CONTENT" \
  "$PAGE_URL"
```

### Pass token via environment variable

```bash
confluence-markdown --action read \
  --base-url https://confluence.example.com \
  --username myuser \
  --token "$CONFLUENCE_TOKEN" \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```
