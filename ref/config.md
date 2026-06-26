# ConfigManager reference

`src/confluence_markdown/config.py`

## Paths

| Path | Notes |
|------|-------|
| `~/.config/confluence-markdown/config.json` | Profile store (permissions 600) |
| `~/.config/confluence-markdown/` | Directory (permissions 700) |

## Keychain integration

Service name: `"confluence-markdown"`  
Account format: `"<profile>:<field>"` (e.g. `"default:token"`)

Secrets are stored per field (`token`, `password`). The JSON file stores a marker flag instead of the plaintext value:

```json
{
  "default": {
    "base_url": "https://confluence.example.com",
    "username": "jdoe",
    "token_in_keychain": true
  }
}
```

If `keyring` is unavailable, the secret falls back to plaintext in JSON with a warning.

## ConfigManager methods

| Method | Notes |
|--------|-------|
| `ensure_config_dir()` | Create dir with mode 700 |
| `save_config(config, profile="default")` | Extract secrets → keychain, write JSON |
| `load_config(profile="default")` | Read JSON, resolve secrets from keychain |
| `load_all_configs()` | Return full dict of all profiles |
| `list_profiles()` | Return profile name list |
| `delete_profile(profile)` | Remove profile + keychain secrets |
| `get_space_config(profile, space_key)` | Profile config merged with space override |
| `save_space_config(profile, space_key, settings)` | Write space-specific settings |

## Config file structure

```json
{
  "default": {
    "base_url": "https://confluence.example.com",
    "username": "jdoe",
    "token_in_keychain": true,
    "editor": "vim",
    "table_format": "yaml",
    "spaces": {
      "DOCS": { "editor": "code" },
      "WIKI": { "table_format": "markdown" }
    }
  },
  "work": {
    "base_url": "https://work.confluence.com",
    "token_in_keychain": true
  }
}
```

## Updating a token in keychain (macOS)

```bash
security add-generic-password -U \
  -s "confluence-markdown" \
  -a "default:token" \
  -w "<NEW_TOKEN>"
```
