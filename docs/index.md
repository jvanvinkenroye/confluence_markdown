# confluence-markdown

> **Proof of Concept** — This tool is experimental. No guarantee of correctness or stability.

A Python CLI tool for reading, editing, and managing Confluence Data Center pages in Markdown format.

## Features

- Read and download Confluence pages as Markdown
- Edit pages in your preferred editor (vim, VS Code, nano, …)
- Add content to existing pages (Markdown or HTML)
- Create new pages and task pages
- Interactive page selection with fzf or InquirerPy
- Search pages by full-text or CQL query
- Recursive batch download of entire page trees
- Response caching for faster repeated access
- Multiple configuration profiles, per-space settings
- Secrets stored securely in the system keychain (macOS)
- Shell tab completion (bash/zsh)

## Installation

```bash
uv tool install git+https://github.com/jvanvinkenroye/confluence_markdown.git
```

## Quick Start

### 1. Set up configuration

```bash
confluence-markdown --action config set
# Base URL: https://confluence.example.com
# Username: myuser
# Token: ****
```

### 2. Test authentication

```bash
confluence-markdown --action config test --config
```

### 3. Browse recent pages

```bash
confluence-markdown --action read-recent --config
```

### 4. Edit a page

```bash
confluence-markdown --action edit --config \
  "https://confluence.example.com/pages/viewpage.action?pageId=12345"
```

## License

[WTFPL](https://en.wikipedia.org/wiki/WTFPL)
