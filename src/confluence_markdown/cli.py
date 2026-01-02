"""CLI entrypoint and argument handling."""
import argparse
import getpass
import shutil
import sys

from .client import ConfluenceClient
from .config import ConfigManager


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Confluence Data Center Markdown Tool")
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
            "test-auth",
            "edit-recent",
            "read-recent",
            "search",
        ],
        default="download",
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

    # Recent pages options
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent pages to fetch (default: 10)",
    )
    parser.add_argument("--query", help="Search query text")
    parser.add_argument("--cql", help="Confluence CQL for search action")

    # Config file options
    parser.add_argument(
        "--save-config", action="store_true", help="Save credentials to config file"
    )
    parser.add_argument(
        "--config", action="store_true", help="Load credentials from config file"
    )
    parser.add_argument(
        "--profile", default="default", help='Config profile name (default: "default")'
    )
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

    args = parser.parse_args()

    # Initialize config manager
    config_manager = ConfigManager()

    # Handle config-only operations
    if args.init_config:
        config_manager.ensure_config_dir()
        if not config_manager.config_file.exists():
            # Create config with example entries
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
            print(
                f"✅ Created config file with example entries at: {config_manager.config_file}"
            )
            print(f"   Edit the file to add your actual credentials")
            print(f"   Example profiles created: 'default' and 'work'")
        else:
            print(f"ℹ️  Config file already exists at: {config_manager.config_file}")
        sys.exit(0)

    if args.list_profiles:
        profiles = config_manager.list_profiles()
        if profiles:
            print("Available profiles:")
            for profile in profiles:
                config = config_manager.load_config(profile)
                print(f"  - {profile} (base_url: {config.get('base_url', 'N/A')})")
        else:
            print("No saved profiles found")
        sys.exit(0)

    if args.delete_profile:
        config_manager.delete_profile(args.profile)
        sys.exit(0)

    # Load config if requested
    if args.config:
        config = config_manager.load_config(args.profile)
        if config:
            print(f"📋 Loading config from profile: {args.profile}")
            args.base_url = args.base_url or config.get("base_url")
            args.username = args.username or config.get("username")
            args.password = args.password or config.get("password")
            args.token = args.token or config.get("token")
        else:
            print(f"❌ No config found for profile: {args.profile}")
            print(f"   Create one with --save-config")
            sys.exit(1)
    else:
        auto_config = config_manager.load_config("default")
        if auto_config:
            print("📋 Loading config from profile: default")
            args.base_url = args.base_url or auto_config.get("base_url")
            args.username = args.username or auto_config.get("username")
            args.password = args.password or auto_config.get("password")
            args.token = args.token or auto_config.get("token")

    # Prompt for missing parameters if no config was available
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

    # Check if base_url is provided (required unless loading from config)
    if not args.base_url:
        print(
            "Error: --base-url is required (or use --config to load from saved profile)"
        )
        sys.exit(1)

    # Save config if requested
    if args.save_config:
        # Prompt for password if not provided
        if args.username and not args.password and not args.token:
            args.password = getpass.getpass(f"Password for {args.username}: ")

        config_data = {
            "base_url": args.base_url,
            "username": args.username,
        }

        # Save either token or password (not both)
        if args.token:
            config_data["token"] = args.token
        elif args.password:
            # Optionally prompt to confirm saving password
            save_pass = input("Save password in config? (y/N): ").lower() == "y"
            if save_pass:
                config_data["password"] = args.password

        config_manager.save_config(config_data, args.profile)

    # Validate authentication
    if not args.token and not (args.username and args.password):
        print("Error: Either --token or --username/--password must be provided")
        print("       (or use --config to load from saved profile)")
        sys.exit(1)

    try:
        # Initialize client
        client = ConfluenceClient(
            base_url=args.base_url,
            username=args.username,
            password=args.password,
            token=args.token,
            verbose=args.verbose,
        )

        if args.action == "test-auth":
            print("Testing authentication...")
            auth_result = client.test_authentication()
            if "error" not in auth_result:
                print(f"✅ Authentication successful!")
                print(f"   User: {auth_result.get('displayName', 'Unknown')}")
                print(f"   Username: {auth_result.get('username', 'Unknown')}")
                print(f"   User Key: {auth_result.get('userKey', 'Unknown')}")
            else:
                print(f"❌ Authentication failed: {auth_result['error']}")
                return
        elif args.action == "edit-recent":
            pages = client.list_recent_pages(args.limit)
            if not pages:
                print("No recent pages found.")
                return
            try:
                from InquirerPy import inquirer
            except ImportError:
                print(
                    "Error: InquirerPy is required for interactive selection. "
                    "Install it with `uv add InquirerPy`."
                )
                sys.exit(1)

            choices = []
            for page in pages:
                label = f"{page['title']} - {page['space']} - {page['last_modified']}"
                choices.append({"name": label, "value": page["url"]})

            selected_url = inquirer.select(
                message="Select a page", choices=choices
            ).execute()
            print(f"Page URL: {selected_url}")
            result = client.edit_page_with_editor(selected_url)
            if result is None:
                print("Edit cancelled or no changes made.")
        elif args.action == "read-recent":
            pages = client.list_recently_viewed_pages(args.limit)
            if not pages:
                print("No recently viewed pages found.")
                return
            try:
                from InquirerPy import inquirer
            except ImportError:
                print(
                    "Error: InquirerPy is required for interactive selection. "
                    "Install it with `uv add InquirerPy`."
                )
                sys.exit(1)
            try:
                from rich.console import Console
                from rich.markdown import Markdown
            except ImportError:
                Console = None
                Markdown = None

            choices = []
            for page in pages:
                label = f"{page['title']} - {page['space']} - {page['last_modified']}"
                choices.append({"name": label, "value": page["url"]})

            selected_url = inquirer.select(
                message="Select a page", choices=choices
            ).execute()
            print(f"Page URL: {selected_url}")
            page_info = client.read_page_content(selected_url)
            markdown_content = page_info["markdown_content"]
            if args.raw:
                output = f"{markdown_content}\n\nPage URL: {page_info['url']}"
                client._paginate_text(output)
            elif Console and Markdown:
                render_width = args.width or shutil.get_terminal_size((80, 24)).columns
                rendered = client._render_markdown_to_ansi(
                    markdown_content, render_width
                )
                client._paginate_text(f"{rendered}\nPage URL: {page_info['url']}")
            else:
                output = f"{markdown_content}\n\nPage URL: {page_info['url']}"
                client._paginate_text(output)
        elif args.action == "search":
            cql = None
            if args.cql:
                cql = client._ensure_page_cql(args.cql)
            elif args.query:
                cql = client._build_text_search_cql(args.query)
            else:
                print("Error: --query or --cql is required for search action")
                sys.exit(1)

            pages = client.search_pages(cql, args.limit)
            if not pages:
                print("No search results found.")
                return

            try:
                from InquirerPy import inquirer
            except ImportError:
                print(
                    "Error: InquirerPy is required for interactive selection. "
                    "Install it with `uv add InquirerPy`."
                )
                sys.exit(1)
            try:
                from rich.console import Console
                from rich.markdown import Markdown
            except ImportError:
                Console = None
                Markdown = None

            choices = []
            for page in pages:
                label = f"{page['title']} - {page['space']} - {page['last_modified']}"
                choices.append({"name": label, "value": page["url"]})

            selected_url = inquirer.select(
                message="Select a page", choices=choices
            ).execute()
            print(f"Page URL: {selected_url}")
            page_info = client.read_page_content(selected_url)
            markdown_content = page_info["markdown_content"]
            if args.raw:
                output = f"{markdown_content}\n\nPage URL: {page_info['url']}"
                client._paginate_text(output)
            elif Console and Markdown:
                render_width = args.width or shutil.get_terminal_size((80, 24)).columns
                rendered = client._render_markdown_to_ansi(
                    markdown_content, render_width
                )
                client._paginate_text(f"{rendered}\nPage URL: {page_info['url']}")
            else:
                output = f"{markdown_content}\n\nPage URL: {page_info['url']}"
                client._paginate_text(output)

        elif args.action == "download":
            if not args.url:
                print("Error: URL is required for download action")
                sys.exit(1)

            markdown_content = client.download_as_markdown(args.url, args.output)
            if not args.output:
                print(markdown_content)
            print(f"Page URL: {args.url}")

        elif args.action == "read":
            if not args.url:
                print("Error: URL is required for read action")
                sys.exit(1)

            page_info = client.read_page_content(args.url)
            print(f"Title: {page_info['title']}")
            print(f"Space: {page_info['space']} ({page_info['space_key']})")
            print(f"Version: {page_info['version']}")
            print(f"URL: {page_info['url']}")
            print("\nMarkdown Content:")
            print("=" * 50)
            print(page_info["markdown_content"])
            print(f"Page URL: {page_info['url']}")

        elif args.action == "add":
            if not args.url:
                print("Error: URL is required for add action")
                sys.exit(1)
            if not args.content:
                print("Error: --content is required for add action")
                sys.exit(1)

            result = client.add_content_to_page(
                args.url,
                args.content,
                append=args.append,
                content_type=args.content_type,
            )
            print(
                f"Content added successfully. New version: {result['version']['number']}"
            )
            page_id = result.get("id")
            page_url = (
                f"{client.base_url}/pages/viewpage.action?pageId={page_id}"
                if page_id
                else args.url
            )
            print(f"Page URL: {page_url}")

        elif args.action == "edit":
            if not args.url:
                print("Error: URL is required for edit action")
                sys.exit(1)

            result = client.edit_page_with_editor(args.url)
            if result is None:
                print("Edit cancelled or no changes made.")
            else:
                page_id = result.get("id")
                page_url = (
                    f"{client.base_url}/pages/viewpage.action?pageId={page_id}"
                    if page_id
                    else args.url
                )
                print(f"Page URL: {page_url}")

        elif args.action == "create":
            if not args.space:
                print("Error: --space is required for create action")
                sys.exit(1)
            if not args.title:
                print("Error: --title is required for create action")
                sys.exit(1)
            if not args.content:
                print("Error: --content is required for create action")
                sys.exit(1)

            result = client.create_page(
                space_key=args.space,
                title=args.title,
                content=args.content,
                parent_id=args.parent_id,
                content_type=args.content_type,
            )
            page_id = result.get("id")
            if page_id:
                print(
                    f"Page URL: {client.base_url}/pages/viewpage.action?pageId={page_id}"
                )

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
