"""CLI entrypoint and argument handling."""
import argparse
import getpass
import json
import logging
import os
import re
import shutil
import sys
from typing import Any

import argcomplete

from . import __version__
from .cache import Cache
from .client import ConfluenceClient
from .config import ConfigManager
from .exceptions import AuthenticationError, ConfigurationError, ConfluenceError

# Configure logging
logger = logging.getLogger(__name__)


def profile_completer(**kwargs) -> list[str]:
    """Completer for --profile argument."""
    config_manager = ConfigManager()
    return config_manager.list_profiles()


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging for the CLI."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" if verbose else "%(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=format_str)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(description="Confluence Data Center Markdown Tool")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Confluence page URL (not required for test-auth or config operations)",
    )
    parser.add_argument("--base-url", help="Confluence base URL")
    parser.add_argument("--username", help="Username (for basic auth)")
    parser.add_argument("--password", help="Password or API token (for basic auth)")
    parser.add_argument("--token", help="Personal Access Token (for bearer auth)")
    parser.add_argument("--output", "-o", help="Output file for markdown")
    parser.add_argument(
        "--action",
        choices=[
            "download",
            "read",
            "add",
            "edit",
            "create",
            "create-edit",
            "create-task",
            "test-auth",
            "edit-recent",
            "read-recent",
            "search",
            "list-children",
        ],
        default="read-recent",
        help="Action to perform",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw markdown instead of Rich rendering",
    )
    parser.add_argument(
        "--width",
        type=int,
        help="Override render width for Rich output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress informational output (for scripting)",
    )
    parser.add_argument(
        "--no-fzf",
        action="store_true",
        help="Disable fzf for page selection (use InquirerPy instead)",
    )
    parser.add_argument(
        "--editor",
        help="Editor to use for edit actions (e.g., vim, nano, code)",
    )
    parser.add_argument(
        "--table-format",
        choices=["markdown", "yaml"],
        default="markdown",
        help="Table format during editing: markdown (default) or yaml (easier to edit)",
    )
    parser.add_argument("--content", help="Content to add (for add/create action)")
    parser.add_argument(
        "--content-type",
        choices=["markdown", "html"],
        default="markdown",
        help="Type of content to add",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        default=True,
        help="Append content (default: True)",
    )
    parser.add_argument(
        "--prepend",
        dest="append",
        action="store_false",
        help="Prepend content instead of append",
    )

    # Create page options
    parser.add_argument(
        "--space", help="Space key for creating new page (e.g., TEST, VAMP)"
    )
    parser.add_argument("--title", help="Title for new page")
    parser.add_argument("--parent-id", help="Parent page ID for hierarchy")

    # Task page options (for create-task action)
    parser.add_argument(
        "--category", help="Category for task page (e.g., Tools, EvaSys)"
    )
    parser.add_argument(
        "--priority", help="Priority for task page (e.g., 80, 50, 0)"
    )
    parser.add_argument(
        "--status", default="offen", help="Status for task page (default: offen)"
    )

    # Recent pages options
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent pages to fetch (default: 10)",
    )
    parser.add_argument("--query", help="Search query text")
    parser.add_argument("--cql", help="Confluence CQL for search action")

    # Batch options
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Process child pages recursively (for list-children, download)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for batch downloads",
    )

    # Config file options
    parser.add_argument(
        "--save-config", action="store_true", help="Save credentials to config file"
    )
    parser.add_argument(
        "--config", action="store_true", help="Load credentials from config file"
    )
    profile_arg = parser.add_argument(
        "--profile", default="default", help='Config profile name (default: "default")'
    )
    profile_arg.completer = profile_completer  # type: ignore[attr-defined]
    parser.add_argument(
        "--list-profiles", action="store_true", help="List all saved config profiles"
    )
    parser.add_argument(
        "--delete-profile", action="store_true", help="Delete a config profile"
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Initialize empty config file structure",
    )

    # Cache options
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable response caching",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all cached data and exit",
    )

    parser.add_argument(
        "--completion",
        choices=["bash", "zsh"],
        help="Output shell completion script",
    )

    return parser


def handle_init_config(config_manager: ConfigManager) -> None:
    """Initialize config file with example entries."""
    config_manager.ensure_config_dir()
    if not config_manager.config_file.exists():
        example_config = {
            "default": {
                "base_url": "https://confluence.example.com",
                "username": "your-username",
                "token": "YOUR_PERSONAL_ACCESS_TOKEN_HERE",
            },
            "work": {
                "base_url": "https://work.confluence.com",
                "username": "work-user",
                "token": "WORK_TOKEN_HERE",
            },
        }
        with open(config_manager.config_file, "w") as f:
            json.dump(example_config, f, indent=2)
        os.chmod(config_manager.config_file, 0o600)
        logger.info("Created config file at: %s", config_manager.config_file)
        logger.info("Edit the file to add your actual credentials")
        logger.info("Example profiles created: 'default' and 'work'")
    else:
        logger.info("Config file already exists at: %s", config_manager.config_file)


def handle_list_profiles(config_manager: ConfigManager) -> None:
    """List all saved config profiles."""
    profiles = config_manager.list_profiles()
    if profiles:
        print("Available profiles:")
        for profile in profiles:
            config = config_manager.load_config(profile)
            print(f"  - {profile} (base_url: {config.get('base_url', 'N/A')})")
    else:
        print("No saved profiles found")


def load_credentials(args: argparse.Namespace, config_manager: ConfigManager) -> None:
    """Load credentials from config or prompt user."""
    if args.config:
        config = config_manager.load_config(args.profile)
        if config:
            logger.info("Loading config from profile: %s", args.profile)
            args.base_url = args.base_url or config.get("base_url")
            args.username = args.username or config.get("username")
            args.password = args.password or config.get("password")
            args.token = args.token or config.get("token")
        else:
            raise ConfigurationError(f"No config found for profile: {args.profile}")
    else:
        auto_config = config_manager.load_config("default")
        if auto_config:
            logger.info("Loading config from profile: default")
            args.base_url = args.base_url or auto_config.get("base_url")
            args.username = args.username or auto_config.get("username")
            args.password = args.password or auto_config.get("password")
            args.token = args.token or auto_config.get("token")

    # Prompt for missing parameters
    if not args.base_url:
        args.base_url = input("Confluence base URL: ").strip() or None

    if not args.username:
        username = input(
            "Username (leave blank to use bearer token authentication): "
        ).strip()
        args.username = username or None

    if not args.token and not args.password:
        token = getpass.getpass(
            "Personal Access Token (leave blank to use password): "
        ).strip()
        if token:
            args.token = token
        else:
            args.password = getpass.getpass("Password: ")


def save_config_if_requested(args: argparse.Namespace, config_manager: ConfigManager) -> None:
    """Save credentials to config if requested."""
    if not args.save_config:
        return

    if args.username and not args.password and not args.token:
        args.password = getpass.getpass(f"Password for {args.username}: ")

    config_data = {
        "base_url": args.base_url,
        "username": args.username,
    }

    if args.token:
        config_data["token"] = args.token
    elif args.password:
        save_pass = input("Save password in config? (y/N): ").lower() == "y"
        if save_pass:
            config_data["password"] = args.password

    config_manager.save_config(config_data, args.profile)


def validate_auth(args: argparse.Namespace) -> None:
    """Validate that authentication credentials are provided."""
    if not args.base_url:
        raise ConfigurationError(
            "--base-url is required (or use --config to load from saved profile)"
        )
    if not args.token and not (args.username and args.password):
        raise AuthenticationError(
            "Either --token or --username/--password must be provided"
        )


def apply_space_config(
    args: argparse.Namespace, config_manager: ConfigManager
) -> None:
    """Apply space-specific configuration if URL is provided."""
    if not args.url:
        return

    # Extract space key from URL
    from urllib.parse import urlparse

    parsed = urlparse(args.url)
    path_parts = parsed.path.split("/")

    space_key = None
    for i, part in enumerate(path_parts):
        if part in ("spaces", "display") and i + 1 < len(path_parts):
            space_key = path_parts[i + 1]
            break

    if not space_key:
        return

    # Get space-specific config
    space_config = config_manager.get_space_config(args.profile, space_key)

    # Apply space-specific settings (only if not already set via CLI)
    if not args.editor and "editor" in space_config:
        args.editor = space_config["editor"]
        logger.debug("Using space-specific editor: %s", args.editor)

    if args.table_format == "markdown" and "table_format" in space_config:
        args.table_format = space_config["table_format"]
        logger.debug("Using space-specific table format: %s", args.table_format)


def create_client(args: argparse.Namespace) -> ConfluenceClient:
    """Create and return a configured ConfluenceClient."""
    return ConfluenceClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        token=args.token,
        verbose=args.verbose,
        editor=args.editor,
        table_format=args.table_format,
        cache_enabled=not getattr(args, "no_cache", False),
    )


def is_fzf_available() -> bool:
    """Check if fzf is available in PATH."""
    return shutil.which("fzf") is not None


def select_with_fzf(choices: list[dict], prompt: str = "Select") -> str | None:
    """Use fzf for selection. Returns selected value or None if cancelled."""
    import subprocess

    # Build input for fzf: "label\tvalue" format
    fzf_input = "\n".join(f"{c['name']}\t{c['value']}" for c in choices)

    try:
        result = subprocess.run(
            ["fzf", "--prompt", f"{prompt}> ", "--with-nth=1", "--delimiter=\t",
             "--height=40%", "--reverse", "--border"],
            input=fzf_input,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Extract value from "label\tvalue" output
            parts = result.stdout.strip().split("\t")
            return parts[-1] if len(parts) > 1 else parts[0]
        return None
    except Exception as e:
        logger.debug("fzf error: %s", e)
        return None


def select_page(choices: list[dict], prompt: str = "Select a page", use_fzf: bool = True) -> str | None:
    """
    Interactive page selection using fzf (if available) or InquirerPy.

    Args:
        choices: List of dicts with 'name' and 'value' keys
        prompt: Prompt message
        use_fzf: Whether to try fzf first (default: True)

    Returns:
        Selected value or None if cancelled
    """
    if use_fzf and is_fzf_available():
        result = select_with_fzf(choices, prompt)
        if result is not None:
            return result
        # User cancelled fzf (Ctrl+C or Esc)
        return None

    # Fall back to InquirerPy
    try:
        from InquirerPy import inquirer
        return inquirer.select(message=prompt, choices=choices).execute()
    except ImportError:
        logger.error(
            "Neither fzf nor InquirerPy available for interactive selection. "
            "Install fzf or run `uv add InquirerPy`."
        )
        sys.exit(1)


def require_inquirer():
    """Import and return InquirerPy, or exit with error."""
    try:
        from InquirerPy import inquirer
        return inquirer
    except ImportError:
        logger.error(
            "InquirerPy is required for interactive selection. "
            "Install it with `uv add InquirerPy`."
        )
        sys.exit(1)


def get_rich_modules():
    """Import and return Rich modules, or None if not available."""
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        return Console, Markdown
    except ImportError:
        return None, None


def handle_test_auth(client: ConfluenceClient) -> None:
    """Test authentication with the Confluence server."""
    logger.info("Testing authentication...")
    auth_result = client.test_authentication()
    if "error" not in auth_result:
        logger.info("Authentication successful!")
        print(f"   User: {auth_result.get('displayName', 'Unknown')}")
        print(f"   Username: {auth_result.get('username', 'Unknown')}")
        print(f"   User Key: {auth_result.get('userKey', 'Unknown')}")
    else:
        raise AuthenticationError(f"Authentication failed: {auth_result['error']}")


def handle_edit_recent(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle edit-recent action."""
    pages = client.list_recent_pages(args.limit)
    if not pages:
        logger.info("No recent pages found.")
        return

    choices = [
        {"name": f"{p['title']} - {p['space']} - {p['last_modified']}", "value": p["url"]}
        for p in pages
    ]

    selected_url = select_page(choices, "Select a page to edit", use_fzf=not args.no_fzf)
    if not selected_url:
        logger.info("Selection cancelled.")
        return
    print(f"Page URL: {selected_url}")
    result = client.edit_page_with_editor(selected_url)
    if result is None:
        logger.info("Edit cancelled or no changes made.")


def handle_read_recent(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle read-recent action with interactive loop."""
    pages = client.list_recently_viewed_pages(args.limit)
    if not pages:
        logger.info("No recently viewed pages found.")
        return

    Console, Markdown = get_rich_modules()

    choices = [
        {"name": f"{p['title']} - {p['space']} - {p['last_modified']}", "value": p["url"]}
        for p in pages
    ]
    choices.append({"name": "[q] Quit", "value": "__QUIT__"})

    while True:
        selected_url = select_page(choices, "Select a page (q to quit)", use_fzf=not args.no_fzf)

        if selected_url is None or selected_url == "__QUIT__":
            print("Bye!")
            break

        print(f"Page URL: {selected_url}")
        page_info = client.read_page_content(selected_url)
        markdown_content = page_info["markdown_content"]

        action = display_page_content(client, args, page_info, markdown_content, Console, Markdown)

        if action == "e":
            result = client.edit_page_with_editor(selected_url)
            if result is None:
                logger.info("Edit cancelled or no changes made.")
            else:
                logger.info("Page updated successfully.")
        elif action == "q":
            print("Bye!")
            break


def display_page_content(
    client: ConfluenceClient,
    args: argparse.Namespace,
    page_info: dict[str, Any],
    markdown_content: str,
    Console,
    Markdown,
    show_actions: bool = True,
) -> str | None:
    """Display page content and return user action."""
    if args.raw:
        output = f"{markdown_content}\n\nPage URL: {page_info['url']}"
        return client._paginate_text(output, show_actions=show_actions)
    elif Console and Markdown:
        render_width = args.width or shutil.get_terminal_size((80, 24)).columns
        rendered = client._render_markdown_to_ansi(markdown_content, render_width)
        return client._paginate_text(
            f"{rendered}\nPage URL: {page_info['url']}", show_actions=show_actions
        )
    else:
        output = f"{markdown_content}\n\nPage URL: {page_info['url']}"
        return client._paginate_text(output, show_actions=show_actions)


def handle_search(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle search action."""
    if args.cql:
        cql = client._ensure_page_cql(args.cql)
    elif args.query:
        cql = client._build_text_search_cql(args.query)
    else:
        raise ConfigurationError("--query or --cql is required for search action")

    pages = client.search_pages(cql, args.limit)
    if not pages:
        logger.info("No search results found.")
        return

    Console, Markdown = get_rich_modules()

    choices = [
        {"name": f"{p['title']} - {p['space']} - {p['last_modified']}", "value": p["url"]}
        for p in pages
    ]

    selected_url = select_page(choices, "Select a page", use_fzf=not args.no_fzf)
    if not selected_url:
        logger.info("Selection cancelled.")
        return
    print(f"Page URL: {selected_url}")

    page_info = client.read_page_content(selected_url)
    display_page_content(client, args, page_info, page_info["markdown_content"], Console, Markdown, show_actions=False)


def sanitize_filename(title: str) -> str:
    """Convert page title to safe filename."""
    # Replace problematic characters with underscores
    safe = re.sub(r'[<>:"/\\|?*]', '_', title)
    # Replace multiple spaces/underscores with single underscore
    safe = re.sub(r'[\s_]+', '_', safe)
    return safe.strip('_')[:100]  # Limit length


def handle_download(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle download action."""
    if not args.url:
        raise ConfigurationError("URL is required for download action")

    if args.recursive:
        # Download page and all children using parallel async
        output_dir = args.output_dir or "confluence_export"
        os.makedirs(output_dir, exist_ok=True)

        # Get all children URLs recursively
        children = client.list_children_recursive_parallel(args.url)

        # Collect all URLs for parallel download
        all_urls = [args.url] + [child["url"] for child in children]

        logger.info("Downloading %d pages in parallel...", len(all_urls))

        # Use parallel download
        results = client.download_pages_parallel(all_urls)

        # Save all files
        for title, markdown_content in results:
            file_path = os.path.join(output_dir, f"{sanitize_filename(title)}.md")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info("Downloaded: %s", title)

        print(f"Downloaded {len(results)} pages to {output_dir}/")
    else:
        markdown_content = client.download_as_markdown(args.url, args.output)
        if not args.output:
            print(markdown_content)
        print(f"Page URL: {args.url}")


def handle_read(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle read action."""
    if not args.url:
        raise ConfigurationError("URL is required for read action")

    page_info = client.read_page_content(args.url)
    print(f"Title: {page_info['title']}")
    print(f"Space: {page_info['space']} ({page_info['space_key']})")
    print(f"Version: {page_info['version']}")
    print(f"URL: {page_info['url']}")
    print("\nMarkdown Content:")
    print("=" * 50)
    print(page_info["markdown_content"])
    print(f"Page URL: {page_info['url']}")


def handle_add(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle add action."""
    if not args.url:
        raise ConfigurationError("URL is required for add action")
    if not args.content:
        raise ConfigurationError("--content is required for add action")

    result = client.add_content_to_page(
        args.url,
        args.content,
        append=args.append,
        content_type=args.content_type,
    )
    logger.info("Content added successfully. New version: %s", result['version']['number'])
    page_id = result.get("id")
    page_url = (
        f"{client.base_url}/pages/viewpage.action?pageId={page_id}"
        if page_id
        else args.url
    )
    print(f"Page URL: {page_url}")


def handle_edit(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle edit action."""
    if not args.url:
        raise ConfigurationError("URL is required for edit action")

    result = client.edit_page_with_editor(args.url)
    if result is None:
        logger.info("Edit cancelled or no changes made.")
    else:
        page_id = result.get("id")
        page_url = (
            f"{client.base_url}/pages/viewpage.action?pageId={page_id}"
            if page_id
            else args.url
        )
        print(f"Page URL: {page_url}")


def handle_create(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle create action."""
    if not args.space:
        raise ConfigurationError("--space is required for create action")
    if not args.title:
        raise ConfigurationError("--title is required for create action")
    if not args.content:
        raise ConfigurationError("--content is required for create action")

    result = client.create_page(
        space_key=args.space,
        title=args.title,
        content=args.content,
        parent_id=args.parent_id,
        content_type=args.content_type,
    )
    page_id = result.get("id")
    if page_id:
        print(f"Page URL: {client.base_url}/pages/viewpage.action?pageId={page_id}")


def handle_create_edit(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle create-edit action - create page via editor."""
    if not args.space:
        raise ConfigurationError("--space is required for create-edit action")

    result = client.create_page_with_editor(
        space_key=args.space,
        title=args.title,  # Optional
        parent_id=args.parent_id,  # Optional
    )
    if result is None:
        logger.info("Page creation cancelled or failed.")


def handle_create_task(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle create-task action."""
    if not args.parent_id:
        raise ConfigurationError("--parent-id is required for create-task action")
    if not args.title:
        raise ConfigurationError("--title is required for create-task action")

    result = client.create_task_page(
        parent_id=args.parent_id,
        title=args.title,
        category=args.category or "",
        priority=args.priority or "",
        status=args.status or "offen",
        description=args.content or "",
    )
    page_id = result.get("id")
    if page_id:
        logger.info("Task page created: %s", args.title)
        print(f"Page URL: {client.base_url}/pages/viewpage.action?pageId={page_id}")


def list_children_recursive(
    client: ConfluenceClient, page_url: str, limit: int, indent: int = 0
) -> list[dict]:
    """Recursively list all children of a page."""
    all_children = []
    children = client.list_children(page_url, limit)

    for child in children:
        child["indent"] = indent
        all_children.append(child)
        # Recursively get children of this child
        grandchildren = list_children_recursive(client, child["url"], limit, indent + 1)
        all_children.extend(grandchildren)

    return all_children


def handle_list_children(client: ConfluenceClient, args: argparse.Namespace) -> None:
    """Handle list-children action."""
    if not args.url:
        raise ConfigurationError("URL is required for list-children action")

    if args.recursive:
        # Use parallel async method for faster recursive listing
        children = client.list_children_recursive_parallel(args.url)
    else:
        children = client.list_children(args.url, args.limit)

    if not children:
        logger.info("No child pages found.")
        return

    print(f"Found {len(children)} child pages:\n")
    for child in children:
        indent = "  " * child.get("depth", child.get("indent", 0))
        print(f"{indent}  - {child['title']}")
        print(f"{indent}    ID: {child['id']}")
        print(f"{indent}    URL: {child['url']}")
        print()


# Action handlers mapping
ACTION_HANDLERS = {
    "test-auth": handle_test_auth,
    "edit-recent": handle_edit_recent,
    "read-recent": handle_read_recent,
    "search": handle_search,
    "download": handle_download,
    "read": handle_read,
    "add": handle_add,
    "edit": handle_edit,
    "create": handle_create,
    "create-edit": handle_create_edit,
    "create-task": handle_create_task,
    "list-children": handle_list_children,
}


def main():
    """Main CLI function."""
    parser = create_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Output completion script if requested
    if args.completion:
        print(f"""# Add this to your ~/.{args.completion}rc:
# eval "$(confluence-markdown --completion {args.completion})"

# Or for {args.completion}, add this to enable completion:""")
        if args.completion == "bash":
            print('eval "$(register-python-argcomplete confluence-markdown)"')
        else:  # zsh
            print("autoload -U bashcompinit && bashcompinit")
            print('eval "$(register-python-argcomplete confluence-markdown)"')
        sys.exit(0)

    # Handle clear-cache (no auth needed)
    if args.clear_cache:
        cache = Cache()
        count = cache.clear()
        print(f"Cleared {count} cached entries.")
        sys.exit(0)

    # Setup logging
    setup_logging(args.verbose, args.quiet)

    # Initialize config manager
    config_manager = ConfigManager()

    try:
        # Handle config-only operations (exit early)
        if args.init_config:
            handle_init_config(config_manager)
            sys.exit(0)

        if args.list_profiles:
            handle_list_profiles(config_manager)
            sys.exit(0)

        if args.delete_profile:
            config_manager.delete_profile(args.profile)
            sys.exit(0)

        # Load credentials
        load_credentials(args, config_manager)
        save_config_if_requested(args, config_manager)
        validate_auth(args)

        # Apply space-specific configuration
        apply_space_config(args, config_manager)

        # Create client and execute action
        client = create_client(args)
        handler = ACTION_HANDLERS.get(args.action)
        if handler:
            if args.action == "test-auth":
                handler(client)
            else:
                handler(client, args)

    except ConfigurationError as e:
        logger.error("%s", e)
        sys.exit(1)
    except AuthenticationError as e:
        logger.error("%s", e)
        sys.exit(1)
    except ConfluenceError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        if args.verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
