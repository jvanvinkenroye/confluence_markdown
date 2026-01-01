# Confluence Data Center Markdown Tool

A Python tool to download, read, and update Confluence Data Center pages with markdown support.

## Features

- Download Confluence pages as markdown files
- Read page content directly in terminal
- Add content to existing pages (markdown or HTML)
- Create new pages with templates
- Interactive page selection with fzf (optional)
- **Automatic pagination** - Fetches ALL pages and spaces (1000+)
- Support for multiple authentication methods
- Save credentials in config file for easy reuse
- Support for multiple configuration profiles
- Debug mode for troubleshooting

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone <repository-url>
cd confluence-markdown

# Install with uv
uv sync

# Run with uv
uv run confluence-markdown --help
```

### Using pip

```bash
# Clone and install
git clone <repository-url>
cd confluence-markdown
pip install .

# Run directly
confluence-markdown --help
```

## Authentication Methods

### Personal Access Token (PAT) - Recommended for Confluence DC 7.9+

For Confluence Data Center, use your PAT with your username:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  URL
```

### Username/Password or API Token

For older versions or if PAT is not available:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD_OR_API_TOKEN \
  URL
```

## Configuration File Support

The tool supports saving credentials in a config file located at `~/.config/confluence-markdown/config.json`.

### Initialize Config File

Create an empty config file structure:
```bash
confluence-markdown --init-config
```
This creates `~/.config/confluence-markdown/config.json` with secure permissions (600).

### Save Configuration

Save your credentials for easy reuse:
```bash
# Save config with PAT
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --save-config \
  --action test-auth

# Save config with password (interactive prompt)
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --save-config \
  --action test-auth
```

### Use Saved Configuration

Once saved, use the config without re-entering credentials:
```bash
# Use default profile
confluence-markdown --config URL

# Use specific profile
confluence-markdown --config --profile work URL
```

### Manage Profiles

Create multiple profiles for different Confluence instances:
```bash
# Save to specific profile
confluence-markdown \
  --base-url https://work.confluence.com \
  --username work_user \
  --token WORK_TOKEN \
  --save-config \
  --profile work \
  --action test-auth

# List all profiles
confluence-markdown --list-profiles

# Delete a profile
confluence-markdown --delete-profile --profile old_profile
```

## Usage Examples

### Test Authentication

Verify your credentials are working:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action test-auth
```

### Download Page as Markdown

Download a Confluence page and save as markdown:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --output page.md \
  "https://confluence.company.com/spaces/SPACE/pages/12345/Page+Title"
```

### Read Page Content

Display page content in terminal without saving:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action read \
  "https://confluence.company.com/pages/viewpage.action?pageId=12345"
```

### Create New Page

Create a new page in a space:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action create \
  --space MYSPACE \
  --title "My New Page" \
  --content "# Welcome\n\nThis is my new page content"
```

Create a page under a parent (for hierarchy):
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action create \
  --space MYSPACE \
  --title "Child Page" \
  --parent-id 12345 \
  --content "Content for the child page"
```

### Add Content to Page

Append markdown content to an existing page:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action add \
  --content "## New Section\nThis is new content" \
  "https://confluence.company.com/pages/viewpage.action?pageId=12345"
```

Prepend content instead:
```bash
confluence-markdown \
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
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action add \
  --content "<h2>HTML Section</h2><p>HTML content</p>" \
  --content-type html \
  URL
```

### Edit Page Interactively

Open page content in your preferred editor, make changes, and upload automatically:
```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --action edit \
  URL

# Or with saved config
confluence-markdown --config --action edit URL
```

**How it works:**
1. Downloads current page content as markdown
2. Opens in your editor (respects `$EDITOR` environment variable)
3. Detects common editors: VS Code, vim, nano, emacs, etc.
4. After saving and closing, uploads changes back to Confluence
5. If you exit without saving, no changes are made

## Supported URL Formats

The tool supports various Confluence URL formats:
- `/pages/viewpage.action?pageId=123456`
- `/spaces/SPACE/pages/123456/Page+Title`
- `/display/SPACE/Page+Title` (if page ID is in the path)

## Command Line Options

```
positional arguments:
  url                   Confluence page URL (optional for test-auth/config ops)

options:
  -h, --help           Show help message
  --base-url           Confluence base URL (required unless using --config)
  --username           Username for authentication
  --password           Password or API token
  --token              Personal Access Token (use with username for DC)
  --output, -o         Output file for markdown (download action)
  --action             Action: download (default), read, add, edit, create, test-auth
  --content            Content to add (for add/create action)
  --content-type       Content type: markdown (default) or html
  --append             Append content (default: True)
  --prepend            Prepend content instead of append

create options:
  --space              Space key for new page (required for create)
  --title              Title for new page (required for create)
  --parent-id          Parent page ID for hierarchy (optional)

config options:
  --init-config        Initialize empty config file structure
  --save-config        Save credentials to config file
  --config             Load credentials from config file
  --profile            Config profile name (default: "default")
  --list-profiles      List all saved config profiles
  --delete-profile     Delete a config profile
```

## Getting Credentials

### Personal Access Token (Confluence DC 7.9+)
1. Log into Confluence
2. Click profile picture � **Personal Access Tokens**
3. Create token with appropriate permissions
4. Save the token securely

### API Token (older versions)
1. Log into Confluence
2. Go to Account Settings � Security
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

WTFPL - Do What The Fuck You Want To Public License