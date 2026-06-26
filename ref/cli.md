# CLI reference

Entry point: `confluence_markdown.main:main` → `cli.main()`

## Positional argument

| Arg | Required | Notes |
|-----|----------|-------|
| `url` | No | Confluence page URL. For `--action config`, this holds the config subcommand (`show`/`list`/`set`/`delete`/`test`). |

## Flags

### Auth
| Flag | Notes |
|------|-------|
| `--base-url` | Confluence Data Center base URL |
| `--username` | Username (basic auth) |
| `--password` | Password or API token (basic auth) |
| `--token` | Personal Access Token (bearer auth) |
| `--config` | Load credentials from saved profile |
| `--profile` | Profile name (default: `"default"`) |
| `--save-config` | Save credentials to config after use |

### Actions
`--action` choices (default: `read-recent`):

| Action | URL required | Description |
|--------|-------------|-------------|
| `read` | yes | Read and display a page |
| `download` | yes | Download page as markdown file |
| `add` | yes | Add content to existing page |
| `edit` | yes | Edit page in `$EDITOR` (or `--content` for non-interactive) |
| `create` | no (space+title) | Create new page interactively |
| `create-edit` | no | Create new page, then open in editor |
| `create-task` | no | Create task page from template |
| `test-auth` | no | Verify credentials |
| `edit-recent` | no | Pick from recently modified pages, edit |
| `read-recent` | no | Pick from recently viewed pages, read |
| `search` | no | Search via `--query` or `--cql`, then read |
| `list-children` | yes | List child pages |
| `config` | no | Manage config (subcommand via positional `url`) |

### Content / format
| Flag | Notes |
|------|-------|
| `--content` | Non-interactive content for `add`/`edit`/`create` |
| `--content-type` | `markdown` (default) or `html` |
| `--append` / `--prepend` | Position for `add` action (default: append) |
| `--table-format` | `markdown` (default) or `yaml` during editing |
| `--editor` | Override editor command |

### Output
| Flag | Notes |
|------|-------|
| `--output` / `-o` | Write markdown to file instead of stdout |
| `--output-dir` | Directory for batch downloads |
| `--raw` | Print raw markdown (skip Rich rendering) |
| `--width` | Override terminal width for Rich |

### Create page
| Flag | Notes |
|------|-------|
| `--space` | Space key (e.g. `TEST`) |
| `--title` | Page title |
| `--parent-id` | Parent page ID |

### Task page
| Flag | Notes |
|------|-------|
| `--category` | Category label |
| `--priority` | Priority number |
| `--status` | Status (default: `offen`) |

### Search / listing
| Flag | Notes |
|------|-------|
| `--query` | Free-text search |
| `--cql` | Confluence Query Language expression |
| `--limit` | Result count (default: 10) |
| `--recursive` / `-r` | Process children recursively |

### Config management (legacy flags, still work)
| Flag | Notes |
|------|-------|
| `--list-profiles` | Print all saved profiles |
| `--delete-profile` | Delete the named profile |
| `--init-config` | Write example config file |

### Misc
| Flag | Notes |
|------|-------|
| `--no-cache` | Disable response cache |
| `--clear-cache` | Delete all cache files and exit |
| `--no-fzf` | Force InquirerPy instead of fzf |
| `--verbose` | Debug logging |
| `--quiet` / `-q` | Warnings only |
| `--completion bash\|zsh` | Print shell completion script |
| `--version` | Print version |

## config subcommand

```bash
confluence-markdown --action config show          # show current profile (default)
confluence-markdown --action config list          # list all profiles
confluence-markdown --action config set           # interactive credential input
confluence-markdown --action config delete        # delete profile
confluence-markdown --action config test          # test-auth with saved profile
```

`show`/`list`/`set`/`delete` exit before auth; `test` falls through to client creation.

## Key functions (cli.py)

| Function | Line | Purpose |
|----------|------|---------|
| `create_parser()` | 42 | Build argparse parser |
| `load_credentials()` | 256 | Merge config / prompts into `args` |
| `validate_auth()` | 318 | Raise if required creds missing |
| `apply_space_config()` | 333 | Override editor/table-format from space config |
| `create_client()` | 368 | Instantiate `ConfluenceClient` |
| `select_page()` | 412 | fzf / InquirerPy picker |
| `handle_config()` | 797 | Config subcommand handler |
| `main()` | 863 | Full dispatch |
