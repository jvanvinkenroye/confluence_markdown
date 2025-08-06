# Confluence Data Center Markdown Tool

A Python tool to download, read, and update Confluence Data Center pages with markdown support.

## Features

- Download Confluence pages as markdown files
- Read page content directly in terminal
- Add content to existing pages (markdown or HTML)
- Support for multiple authentication methods
- Debug mode for troubleshooting

## Installation

1. Install dependencies using uv:
```bash
uv sync
```

Or with pip:
```bash
pip install requests markdownify beautifulsoup4
```

## Authentication Methods

### Personal Access Token (PAT) - Recommended for Confluence DC 7.9+

For Confluence Data Center, use your PAT with your username:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  URL
```

### Username/Password or API Token

For older versions or if PAT is not available:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD_OR_API_TOKEN \
  URL
```

## Usage Examples

### Test Authentication

Verify your credentials are working:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action test-auth
```

### Download Page as Markdown

Download a Confluence page and save as markdown:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --output page.md \
  "https://confluence.company.com/spaces/SPACE/pages/12345/Page+Title"
```

### Read Page Content

Display page content in terminal without saving:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action read \
  "https://confluence.company.com/pages/viewpage.action?pageId=12345"
```

### Add Content to Page

Append markdown content to an existing page:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action add \
  --content "## New Section\nThis is new content" \
  "https://confluence.company.com/pages/viewpage.action?pageId=12345"
```

Prepend content instead:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action add \
  --content "## Important Update\nThis goes at the top" \
  --prepend \
  URL
```

Add HTML content directly:
```bash
python confluence_markdown_tool.py \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action add \
  --content "<h2>HTML Section</h2><p>HTML content</p>" \
  --content-type html \
  URL
```

## Supported URL Formats

The tool supports various Confluence URL formats:
- `/pages/viewpage.action?pageId=123456`
- `/spaces/SPACE/pages/123456/Page+Title`
- `/display/SPACE/Page+Title` (if page ID is in the path)

## Command Line Options

```
positional arguments:
  url                   Confluence page URL (optional for test-auth)

options:
  -h, --help           Show help message
  --base-url           Confluence base URL (required)
  --username           Username for authentication
  --password           Password or API token
  --token              Personal Access Token (use with username for DC)
  --output, -o         Output file for markdown (download action)
  --action             Action: download (default), read, add, test-auth
  --content            Content to add (for add action)
  --content-type       Content type: markdown (default) or html
  --append             Append content (default: True)
  --prepend            Prepend content instead of append
```

## Getting Credentials

### Personal Access Token (Confluence DC 7.9+)
1. Log into Confluence
2. Click profile picture ’ **Personal Access Tokens**
3. Create token with appropriate permissions
4. Save the token securely

### API Token (older versions)
1. Log into Confluence
2. Go to Account Settings ’ Security
3. Create API token
4. Use with your username

## Troubleshooting

The script includes debug output to help troubleshoot issues:
- Shows extracted page ID from URL
- Displays request details and authentication method
- Shows server response status and content

If you encounter authentication errors:
1. First run with `--action test-auth` to verify credentials
2. Ensure you're using the correct authentication method for your Confluence version
3. For Data Center with PAT, always include both `--username` and `--token`
4. Check that your account has permission to access the requested page

## Requirements

- Python 3.7+
- requests
- markdownify
- beautifulsoup4

## License

MIT