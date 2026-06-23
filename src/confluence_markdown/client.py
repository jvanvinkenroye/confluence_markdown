"""Confluence API client and helpers."""

import asyncio
import base64
import io
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import markdown
import requests
import yaml
from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from .cache import Cache

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """Client for Confluence Data Center API operations."""

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        verbose: bool = False,
        editor: Optional[str] = None,
        table_format: str = "markdown",
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
    ):
        """
        Initialize Confluence client.

        Args:
            base_url: Confluence Data Center base URL
            username: Username for basic auth (used with password)
            password: Password or API token for basic auth
            token: Personal Access Token for bearer auth
            editor: Override editor command (e.g., vim, nano, code)
            table_format: Format for tables during editing: 'markdown' or 'yaml'
            cache_enabled: Whether to enable response caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
        """
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/rest/api"
        self.session = requests.Session()
        self.verbose = verbose
        self.editor_override = editor
        self.table_format = table_format
        self.cache = Cache(enabled=cache_enabled, ttl=cache_ttl)

        # Set up authentication
        if token:
            # For Confluence Data Center, PATs might need to be used as Basic auth
            # Try different token authentication methods
            if username:
                # Method 1: Token as password with username (common for DC)
                auth_string = base64.b64encode(f"{username}:{token}".encode()).decode()
                self.session.headers.update({"Authorization": f"Basic {auth_string}"})
                self._debug(f"Using token as password with username: {username}")
            else:
                # Method 2: Bearer token (OAuth style)
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self._debug("Using Bearer token authentication")
        elif username and password:
            # Regular username/password authentication
            auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
            self.session.headers.update({"Authorization": f"Basic {auth_string}"})
            self.session.auth = (username, password)  # Add this for requests library
            self._debug(f"Using Basic authentication with username: {username}")
        else:
            raise ValueError("Either token or username/password must be provided")

        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

        # Prepare async client auth headers for later use
        self._async_headers = dict(self.session.headers)

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle rate limiting based on response headers."""
        import time

        # Check for rate limit headers (common patterns)
        remaining = response.headers.get("X-RateLimit-Remaining")
        retry_after = response.headers.get("Retry-After")

        # Warn when approaching limit
        if remaining is not None:
            try:
                remaining_int = int(remaining)
                if remaining_int <= 5:
                    logger.warning("Rate limit nearly exhausted: %s requests remaining", remaining)
            except ValueError:
                pass

        # Handle 429 Too Many Requests
        if response.status_code == 429:
            wait_time = 60  # Default wait time
            if retry_after:
                try:
                    wait_time = int(retry_after)
                except ValueError:
                    pass
            logger.warning("Rate limited. Waiting %s seconds...", wait_time)
            time.sleep(wait_time)

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """
        Make an HTTP request with automatic retry on transient errors.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL to request
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object
        """
        self._debug(f"{method} {url}")
        response = self.session.request(method, url, **kwargs)

        # Handle rate limiting
        self._handle_rate_limit(response)

        # Retry on rate limit
        if response.status_code == 429:
            # After sleeping in _handle_rate_limit, retry the request
            response = self.session.request(method, url, **kwargs)

        # Retry on 5xx server errors
        if response.status_code >= 500:
            self._debug(f"Server error {response.status_code}, will retry")
            response.raise_for_status()

        return response

    def test_authentication(self) -> dict:
        """Test authentication by getting current user info."""
        url = f"{self.api_base}/user/current"
        self._debug(f"Testing authentication at: {url}")

        response = self._request("GET", url)
        self._debug(f"Auth test status: {response.status_code}")
        self._debug(f"Auth test response: {response.text[:500]}")

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}", "response": response.text}

    def get_page_by_url(self, page_url: str) -> dict:
        """
        Get page content by URL.

        Args:
            page_url: Full URL to the Confluence page

        Returns:
            Page data dictionary
        """
        # Extract page ID from URL
        page_id = self._extract_page_id_from_url(page_url)
        if not page_id:
            raise ValueError(f"Could not extract page ID from URL: {page_url}")

        return self.get_page_content(page_id)

    def get_page_content(self, page_id: str) -> dict:
        """
        Get page content by ID.

        Args:
            page_id: Confluence page ID

        Returns:
            Page data dictionary
        """
        url = f"{self.api_base}/content/{page_id}"
        params = {"expand": "body.storage,space,version,ancestors"}

        self._debug(f"Making request to: {url}")
        self._debug(f"Request params: {params}")
        self._debug(
            f"Using headers: {self._redact_headers(dict(self.session.headers))}"
        )

        response = self._request("GET", url, params=params)

        self._debug(f"Response status code: {response.status_code}")
        self._debug(f"Response headers: {dict(response.headers)}")
        self._debug(f"Response content (first 500 chars): {response.text[:500]}")

        if response.status_code != 200:
            logger.error("HTTP %s", response.status_code)
            logger.error("Full response: %s", response.text)
            response.raise_for_status()

        try:
            return response.json()
        except Exception as e:
            logger.error("Failed to parse JSON response: %s", e)
            logger.error("Full response text: %s", response.text)
            raise

    def _recent_pages_cql_variants(self) -> list:
        """Provide CQL variants for recent pages edited by the current user."""
        return [
            "type=page AND lastModifiedBy=currentUser() order by lastmodified desc",
            "type=page AND contributor=currentUser() order by lastmodified desc",
            "type=page AND creator=currentUser() order by lastmodified desc",
            "type=page order by lastmodified desc",
        ]

    def _recently_viewed_cql_variants(self) -> list:
        """Provide CQL variants for recently viewed pages."""
        return [
            "type=page AND lastViewed is not EMPTY order by lastViewed desc",
            "type=page AND lastviewed is not EMPTY order by lastviewed desc",
            "type=page order by lastmodified desc",
        ]

    def _build_text_search_cql(self, query: str) -> str:
        """Build a CQL query for free-text search."""
        escaped = query.replace('"', '\\"')
        return f'type=page AND text~"{escaped}" order by lastmodified desc'

    def _ensure_page_cql(self, cql: str) -> str:
        """Ensure CQL limits results to pages."""
        if "type=page" in cql.lower():
            return cql
        return f"type=page AND ({cql})"

    # Confluence Search API max results per page
    _SEARCH_PAGE_SIZE = 25

    def _search_paginated(self, cql: str, limit: int, extra_params: Optional[dict] = None) -> list:
        """Fetch up to `limit` search results, paginating as needed."""
        url = f"{self.api_base}/search"
        results: list = []
        start = 0
        while len(results) < limit:
            fetch = min(self._SEARCH_PAGE_SIZE, limit - len(results))
            params: dict = {
                "cql": cql,
                "limit": fetch,
                "start": start,
                "expand": "content.space,content.version",
            }
            if extra_params:
                params.update(extra_params)
            response = self.session.get(url, params=params)
            if response.status_code != 200:
                logger.error("HTTP %s", response.status_code)
                logger.error("Full response: %s", response.text)
                response.raise_for_status()
            data = response.json()
            batch = data.get("results", [])
            results.extend(batch)
            # Stop if Confluence signals no more results
            if len(batch) < fetch or not data.get("_links", {}).get("next"):
                break
            start += len(batch)
        return results

    def _items_to_pages(self, items: list, page_type_filter: bool = False) -> list:
        pages = []
        for item in items:
            content = item.get("content", item)
            if page_type_filter and content.get("type") and content.get("type") != "page":
                continue
            page_id = content.get("id")
            if not page_id:
                continue
            space = content.get("space", {})
            version = content.get("version", {})
            pages.append(
                {
                    "id": page_id,
                    "title": content.get("title", "(untitled)"),
                    "space": space.get("key", "UNKNOWN"),
                    "last_modified": version.get("when", "unknown"),
                    "url": f"{self.base_url}/pages/viewpage.action?pageId={page_id}",
                }
            )
        return pages

    def list_recent_pages(self, limit: int = 10) -> list:
        """List recently edited pages for the current user."""
        self._debug(f"Fetching recent pages (limit={limit})")
        for cql in self._recent_pages_cql_variants():
            params = {"cql": cql, "limit": 1, "expand": ""}
            probe = self.session.get(f"{self.api_base}/search", params=params)
            if probe.status_code == 400 and (
                "No field exists" in probe.text or "Could not parse cql" in probe.text
            ):
                continue
            if probe.status_code not in (200, 400):
                logger.error("HTTP %s", probe.status_code)
                probe.raise_for_status()
            # This CQL works — fetch full result set with pagination
            items = self._search_paginated(cql, limit)
            return self._items_to_pages(items)

        raise RuntimeError(
            "Confluence rejected all recent-page CQL variants. "
            "This instance may not support user-based filters."
        )

    def list_recently_viewed_pages(self, limit: int = 10, use_cache: bool = True) -> list:
        """List recently viewed pages for the current user."""
        cache_key = f"recently_viewed:{self.base_url}:{limit}"

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self._debug("Using cached recently viewed pages")
                return cached

        self._debug(f"Fetching recently viewed pages (limit={limit})")
        for cql in self._recently_viewed_cql_variants():
            probe = self.session.get(
                f"{self.api_base}/search", params={"cql": cql, "limit": 1, "expand": ""}
            )
            if probe.status_code == 400 and (
                "No field exists" in probe.text or "Could not parse cql" in probe.text
            ):
                continue
            if probe.status_code not in (200, 400):
                logger.error("HTTP %s", probe.status_code)
                probe.raise_for_status()
            items = self._search_paginated(cql, limit)
            pages = self._items_to_pages(items)
            self.cache.set(cache_key, pages)
            return pages

        raise RuntimeError(
            "Confluence rejected all recently-viewed CQL variants. "
            "This instance may not support view tracking."
        )

    def search_pages(self, cql: str, limit: int = 10) -> list:
        """Search pages using the provided CQL."""
        self._debug(f"Searching pages with CQL: {cql} (limit={limit})")
        items = self._search_paginated(cql, limit)
        return self._items_to_pages(items, page_type_filter=True)

    def list_children(self, page_url: str, limit: int = 50) -> list:
        """
        List child pages of a given page.

        Args:
            page_url: URL of the parent page
            limit: Maximum number of children to return

        Returns:
            List of child page dicts with id, title, space, last_modified, url
        """
        page_data = self.get_page_by_url(page_url)
        page_id = page_data["id"]

        url = f"{self.api_base}/content/{page_id}/child/page"
        self._debug(f"Fetching children from: {url}")

        params = {
            "limit": limit,
            "expand": "space,version",
        }
        response = self.session.get(url, params=params)
        if response.status_code != 200:
            self._debug(f"ERROR: HTTP {response.status_code}")
            self._debug(f"ERROR: Full response: {response.text}")
            response.raise_for_status()

        data = response.json()
        pages = []
        for content in data.get("results", []):
            child_id = content.get("id")
            if not child_id:
                continue
            space = content.get("space", {})
            version = content.get("version", {})
            pages.append(
                {
                    "id": child_id,
                    "title": content.get("title", "(untitled)"),
                    "space": space.get("key", "UNKNOWN"),
                    "last_modified": version.get("when", "unknown"),
                    "url": f"{self.base_url}/pages/viewpage.action?pageId={child_id}",
                }
            )

        return pages

    def list_spaces(self, limit: int = 100) -> list:
        """Return list of spaces as [{key, name, url}]."""
        url = f"{self.api_base}/space"
        params = {"limit": limit, "type": "global", "status": "current"}
        response = self._request("GET", url, params=params)
        results = response.json().get("results", [])
        return [
            {
                "key": s["key"],
                "name": s.get("name", s["key"]),
                "url": f"{self.base_url}/display/{s['key']}",
            }
            for s in results
        ]

    def download_page(
        self,
        page_url: str,
        output_file: Optional[str] = None,
        fmt: str = "md",
    ) -> str:
        """Download a page in the requested format.

        Args:
            page_url: Full URL to the Confluence page.
            output_file: Optional file path to save the output.
            fmt: ``"md"`` (default) for Markdown, or ``"storage"`` for
                 Confluence storage format (XHTML), Atlassian's official
                 native page format (``representation: "storage"`` in the
                 REST API).

        Returns:
            Page content as a string (Markdown or storage XHTML).
        """
        page_data = self.get_page_by_url(page_url)
        storage_value = page_data["body"]["storage"]["value"]

        if fmt == "storage":
            # Lossless passthrough: pretty-print storage XHTML for human editing.
            pretty = self._prettify_storage(storage_value)
            header = (
                f"<!-- Page ID: {page_data['id']}, "
                f"Version: {page_data['version']['number']}, "
                f"Title: {page_data['title']} -->\n"
            )
            full_content = header + pretty
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(full_content)
                print(f"Storage XHTML saved to: {output_file}")
            return full_content

        # Default: Markdown
        markdown_content = self._html_to_markdown(storage_value)
        safe_title = self._escape_markdown_heading(page_data["title"])
        metadata = f"""# {safe_title}

**Space:** {page_data["space"]["name"]}
**Page ID:** {page_data["id"]}
**Version:** {page_data["version"]["number"]}
**URL:** {self.base_url}/pages/viewpage.action?pageId={page_data["id"]}

---

"""
        full_markdown = metadata + markdown_content

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_markdown)
            print(f"Content saved to: {output_file}")

        return full_markdown

    def read_page_content(self, page_url: str) -> dict:
        """
        Read page content and return structured data.

        Args:
            page_url: Full URL to the Confluence page

        Returns:
            Dictionary with page information
        """
        page_data = self.get_page_by_url(page_url)

        return {
            "id": page_data["id"],
            "title": page_data["title"],
            "space": page_data["space"]["name"],
            "space_key": page_data["space"]["key"],
            "version": page_data["version"]["number"],
            "html_content": page_data["body"]["storage"]["value"],
            "markdown_content": self._html_to_markdown(
                page_data["body"]["storage"]["value"]
            ),
            "url": f"{self.base_url}/pages/viewpage.action?pageId={page_data['id']}",
        }

    def add_content_to_page(
        self,
        page_url: str,
        content: str,
        append: bool = True,
        content_type: str = "markdown",
    ) -> dict:
        """
        Add content to an existing page.

        Args:
            page_url: Full URL to the Confluence page
            content: Content to add (markdown or HTML)
            append: If True, append to existing content; if False, prepend
            content_type: 'markdown' or 'html'

        Returns:
            Updated page data
        """
        page_data = self.get_page_by_url(page_url)

        # Convert markdown to HTML if needed
        if content_type == "markdown":
            # Simple markdown to HTML conversion
            html_content = self._markdown_to_html(content)
        else:
            html_content = content

        # Get current content
        current_content = page_data["body"]["storage"]["value"]

        # Combine content
        if append:
            new_content = current_content + "\n" + html_content
        else:
            new_content = html_content + "\n" + current_content

        # Update page
        update_data = {
            "version": {"number": page_data["version"]["number"] + 1},
            "title": page_data["title"],
            "type": "page",
            "body": {"storage": {"value": new_content, "representation": "storage"}},
        }

        url = f"{self.api_base}/content/{page_data['id']}"
        response = self._request("PUT", url, json=update_data)
        if response.status_code == 409:
            raise RuntimeError(
                "Confluence rejected the update due to a version conflict. "
                "Refresh the page and try again."
            )
        response.raise_for_status()

        return response.json()

    def create_page(
        self,
        space_key: str,
        title: str,
        content: str,
        parent_id: Optional[str] = None,
        content_type: str = "markdown",
    ) -> dict:
        """
        Create a new page in Confluence.

        Args:
            space_key: Space key where the page will be created (e.g., 'TEST', 'VAMP')
            title: Page title
            content: Page content (markdown or HTML)
            parent_id: Optional parent page ID for hierarchy
            content_type: 'markdown' or 'html'

        Returns:
            Created page data
        """
        # Convert markdown to HTML if needed
        if content_type == "markdown":
            html_content = self._markdown_to_html(content)
        else:
            html_content = content

        # Build page data
        page_data = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": html_content, "representation": "storage"}},
        }

        # Add parent if specified
        if parent_id:
            page_data["ancestors"] = [{"id": parent_id}]

        url = f"{self.api_base}/content"
        self._debug(f"Creating page in space {space_key} with title: {title}")

        response = self._request("POST", url, json=page_data)

        if response.status_code not in (200, 201):
            logger.error("HTTP %s", response.status_code)
            logger.error("Full response: %s", response.text)

        response.raise_for_status()

        created_page = response.json()
        page_id = created_page["id"]
        print("✅ Page created successfully!")
        print(f"   Title: {title}")
        print(f"   Space: {space_key}")
        print(f"   Page ID: {page_id}")
        print(f"   URL: {self.base_url}/pages/viewpage.action?pageId={page_id}")

        return created_page

    def create_page_with_editor(
        self,
        space_key: str,
        title: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Create a new page using the system editor.

        Opens an editor with a template, user writes content, then creates the page.

        Args:
            space_key: Space key where the page will be created
            title: Optional page title (can be set in editor)
            parent_id: Optional parent page ID for hierarchy

        Returns:
            Created page data, or None if cancelled
        """
        # Create template content
        template_title = title or "New Page Title"
        template = f"""# {template_title}

<!-- Edit your page content below -->
<!-- The first # heading will be used as the page title -->

Write your content here in Markdown.

## Section 1

- Item 1
- Item 2

## Section 2

More content...
"""

        # Create temporary file with template
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as temp_file:
            temp_file.write(template)
            temp_file_path = temp_file.name

        try:
            # Detect editor
            editor = self._get_editor()
            self._debug(f"Detected editor: {editor}")
            self._debug(f"Temp file path: {temp_file_path}")

            print(f"Opening editor: {editor}")
            print(f"Creating new page in space: {space_key}")
            print("Save and close the editor to create the page.")
            print("The first # heading will be used as the page title.")

            # Get original file modification time
            original_mtime = os.path.getmtime(temp_file_path)

            # Open editor
            editor_cmd = editor + [temp_file_path]
            editor_name = editor[0].lower()

            # Terminal editors need proper TTY
            terminal_editors = ("vim", "nvim", "vi", "nano", "emacs", "pico", "joe")
            if editor_name in terminal_editors:
                import shlex
                cmd_str = " ".join(shlex.quote(arg) for arg in editor_cmd)
                exit_code = os.system(cmd_str)
                result = type("Result", (), {"returncode": exit_code >> 8})()
            else:
                result = subprocess.run(editor_cmd)

            if result.returncode != 0:
                print("Editor exited with error. Cancelling.")
                return None

            # Check if file was modified
            new_mtime = os.path.getmtime(temp_file_path)
            if new_mtime == original_mtime:
                print("File was not modified. No page created.")
                return None

            # Read edited content
            with open(temp_file_path, "r") as f:
                edited_content = f.read()

            # Extract title from first # heading
            lines = edited_content.split("\n")
            page_title = title
            content_lines = []
            found_title = False

            for line in lines:
                # Skip comment lines
                if line.strip().startswith("<!--") and "-->" in line:
                    continue
                # Extract title from first # heading
                if not found_title and line.startswith("# "):
                    page_title = line[2:].strip()
                    found_title = True
                    continue
                content_lines.append(line)

            if not page_title:
                print("Error: No title found. Use # Title at the start.")
                return None

            content = "\n".join(content_lines).strip()
            if not content:
                print("Error: No content provided.")
                return None

            # Create the page
            print(f"Creating page: {page_title}")
            return self.create_page(
                space_key=space_key,
                title=page_title,
                content=content,
                parent_id=parent_id,
                content_type="markdown",
            )

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def create_task_page(
        self,
        parent_id: str,
        title: str,
        category: str = "",
        priority: str = "",
        status: str = "offen",
        description: str = "",
        tasks: Optional[List[str]] = None,
    ) -> dict:
        """
        Create a new task page with page-properties macro.

        Args:
            parent_id: Parent page ID
            title: Page title
            category: Task category (e.g., 'Tools', 'EvaSys')
            priority: Priority value (e.g., '80', '50')
            status: Status (default: 'offen')
            description: Task description (markdown)
            tasks: List of task items

        Returns:
            Created page data
        """
        # Build the page-properties table as HTML with the details macro
        properties_html = f'''<ac:structured-macro ac:name="details" ac:schema-version="1">
<ac:rich-text-body>
<table>
<tbody>
<tr>
<th>Priorität</th>
<th>Kategorie</th>
<th>Status</th>
</tr>
<tr>
<td>{priority}</td>
<td>{category}</td>
<td>{status}</td>
</tr>
</tbody>
</table>
</ac:rich-text-body>
</ac:structured-macro>'''

        # Convert description from markdown to HTML
        if description:
            description_html = self._markdown_to_html(description)
        else:
            description_html = "<p></p>"

        # Build task list HTML
        tasks_html = ""
        if tasks:
            task_items = ""
            for i, task in enumerate(tasks, 1):
                task_items += f'''<ac:task>
<ac:task-id>{i}</ac:task-id>
<ac:task-status>incomplete</ac:task-status>
<ac:task-body>{task}</ac:task-body>
</ac:task>
'''
            tasks_html = f"<ac:task-list>{task_items}</ac:task-list>"
        else:
            # Empty task list with placeholder
            tasks_html = '''<ac:task-list>
<ac:task>
<ac:task-id>1</ac:task-id>
<ac:task-status>incomplete</ac:task-status>
<ac:task-body></ac:task-body>
</ac:task>
</ac:task-list>'''

        # Combine into full page content
        html_content = f'''{properties_html}

<h2>Beschreibung</h2>
{description_html}

<h2>Nächste Schritte</h2>
{tasks_html}
'''

        # Get space key from parent page
        parent_page = self.session.get(
            f"{self.api_base}/content/{parent_id}?expand=space"
        ).json()
        space_key = parent_page["space"]["key"]

        # Build page data
        page_data = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": parent_id}],
            "body": {"storage": {"value": html_content, "representation": "storage"}},
        }

        url = f"{self.api_base}/content"
        self._debug(f"Creating task page under parent {parent_id} with title: {title}")

        response = self._request("POST", url, json=page_data)

        if response.status_code not in (200, 201):
            logger.error("HTTP %s", response.status_code)
            logger.error("Full response: %s", response.text)

        response.raise_for_status()

        return response.json()

    def _extract_page_id_from_url(self, page_url: str) -> Optional[str]:
        """Extract page ID from Confluence URL."""
        if not page_url:
            return None

        self._debug(f"Extracting page ID from URL: {page_url}")
        parsed = urlparse(page_url)
        self._debug(f"Parsed URL - path: {parsed.path}, query: {parsed.query}")

        # Handle different URL formats
        if "pageId=" in parsed.query:
            # Format: /pages/viewpage.action?pageId=123456
            for param in parsed.query.split("&"):
                if param.startswith("pageId="):
                    page_id = param.split("=")[1]
                    self._debug(f"Found page ID from query param: {page_id}")
                    return page_id

        # Handle other URL formats by trying to extract from path
        path_parts = parsed.path.split("/")
        self._debug(f"Path parts: {path_parts}")
        for i, part in enumerate(path_parts):
            if part == "pages" and i + 1 < len(path_parts):
                candidate = path_parts[i + 1]
                if candidate.isdigit():
                    self._debug(f"Found page ID from path: {candidate}")
                    return candidate
                break

        self._debug("No page ID found in URL")
        return None

    def _extract_space_key_from_url(self, page_url: str) -> Optional[str]:
        """Extract space key from Confluence URL."""
        if not page_url:
            return None

        parsed = urlparse(page_url)

        # Format: /spaces/SPACEKEY/... or /display/SPACEKEY/...
        path_parts = parsed.path.split("/")
        for i, part in enumerate(path_parts):
            if part in ("spaces", "display") and i + 1 < len(path_parts):
                space_key = path_parts[i + 1]
                # Skip user spaces (start with ~)
                if not space_key.startswith("~"):
                    return space_key
                # For user spaces, return the full key
                return space_key

        # Try to get from spaceKey query param
        if "spaceKey=" in parsed.query:
            for param in parsed.query.split("&"):
                if param.startswith("spaceKey="):
                    return param.split("=")[1]

        return None

    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML to Markdown."""
        # Clean up HTML first
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove data-* attributes and other Confluence-specific attributes
        for tag in soup.find_all(True):
            attrs_to_remove = [
                attr for attr in tag.attrs
                if attr.startswith("data-") or attr in ("class", "style", "id")
            ]
            for attr in attrs_to_remove:
                del tag[attr]

        # Convert to markdown
        markdown = markdownify(
            str(soup), heading_style="ATX", bullets="-", strip=["script", "style"]
        )

        return markdown.strip()

    def _html_cell_to_text(self, cell) -> str:
        """Convert HTML cell content (lists, paragraphs) to readable text."""
        lines = []

        def process_element(el, indent=0):
            """Recursively process HTML elements to text."""
            if isinstance(el, str):
                text = el.strip()
                if text:
                    lines.append("  " * indent + text)
                return

            if not hasattr(el, 'name'):
                return

            if el.name == 'p':
                text = el.get_text(strip=True)
                if text:
                    lines.append("  " * indent + text)
            elif el.name == 'br':
                lines.append("")
            elif el.name in ['ul', 'ol']:
                for li in el.find_all('li', recursive=False):
                    process_li(li, indent)
            elif el.name == 'strong':
                text = el.get_text(strip=True)
                if text:
                    lines.append("  " * indent + f"**{text}**")
            elif el.name == 'em':
                text = el.get_text(strip=True)
                if text:
                    lines.append("  " * indent + f"*{text}*")
            else:
                # Process children
                for child in el.children:
                    process_element(child, indent)

        def process_li(li, indent=0):
            """Process a list item, handling nested lists."""
            # Get direct text content (not from nested lists)
            direct_text = []
            nested_list = None
            for child in li.children:
                if hasattr(child, 'name') and child.name in ['ul', 'ol']:
                    nested_list = child
                elif hasattr(child, 'name') and child.name == 'strong':
                    direct_text.append(f"**{child.get_text(strip=True)}**")
                elif hasattr(child, 'name') and child.name == 'em':
                    direct_text.append(f"*{child.get_text(strip=True)}*")
                elif hasattr(child, 'name') and child.name == 'p':
                    direct_text.append(child.get_text(strip=True))
                elif isinstance(child, str):
                    text = child.strip()
                    if text:
                        direct_text.append(text)
                elif hasattr(child, 'get_text'):
                    text = child.get_text(strip=True)
                    if text:
                        direct_text.append(text)

            text = " ".join(direct_text).strip()
            if text:
                lines.append("  " * indent + "- " + text)

            # Process nested list with increased indent
            if nested_list:
                for nested_li in nested_list.find_all('li', recursive=False):
                    process_li(nested_li, indent + 1)

        # Process all top-level children
        for child in cell.children:
            process_element(child, 0)

        return "\n".join(lines)

    def _text_to_html_cell(self, text: str) -> str:
        """Convert readable text format back to HTML for Confluence."""
        lines = text.strip().split("\n")
        result = []
        list_stack = []  # Stack of (indent_level, list_tag)

        for line in lines:
            if not line.strip():
                if not list_stack:
                    result.append("<br/>")
                continue

            # Count leading spaces (2 spaces = 1 indent level)
            stripped = line.lstrip()
            indent = (len(line) - len(stripped)) // 2

            # Close lists if indent decreased
            while list_stack and list_stack[-1][0] >= indent and not stripped.startswith("- "):
                _, tag = list_stack.pop()
                result.append(f"</{tag}>")

            if stripped.startswith("- "):
                # List item
                content = stripped[2:]
                # Convert markdown bold/italic
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)

                # Open new list if needed
                if not list_stack or list_stack[-1][0] < indent:
                    result.append("<ul>")
                    list_stack.append((indent, "ul"))

                result.append(f"<li>{content}</li>")
            else:
                # Regular text - close any open lists first
                while list_stack:
                    _, tag = list_stack.pop()
                    result.append(f"</{tag}>")

                # Convert markdown bold/italic
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
                content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
                result.append(f"<p>{content}</p>")

        # Close any remaining open lists
        while list_stack:
            _, tag = list_stack.pop()
            result.append(f"</{tag}>")

        return "".join(result)

    def _restore_lists_in_cells(self, html_content: str) -> str:
        """Convert text-format lists in table cells back to HTML lists."""
        # Use regex to find and process table cells
        def process_cell(match):
            tag = match.group(1)  # td or th
            content = match.group(2)
            closing = match.group(3)

            # Check if cell contains list-like patterns
            if "<br/>" in content and "- " in content:
                lines = re.split(r'<br\s*/?>', content)
                converted = self._lines_to_html_list(lines)
                return f"<{tag}>{converted}</{closing}>"
            return match.group(0)

        # Match <td>...</td> and <th>...</th>
        pattern = r'<(td|th)(?:\s[^>]*)?>(.+?)</(\1)>'
        return re.sub(pattern, process_cell, html_content, flags=re.DOTALL | re.IGNORECASE)

    def _lines_to_html_list(self, lines: List[str]) -> str:
        """Convert lines with list markers to HTML list structure."""
        result = []
        list_stack = []  # Stack of indent levels

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Count leading whitespace for indent (2 spaces or &nbsp; = 1 level)
            indent = 0
            temp = line
            while temp.startswith("  ") or temp.startswith("&nbsp;&nbsp;"):
                indent += 1
                if temp.startswith("  "):
                    temp = temp[2:]
                else:
                    temp = temp[12:]  # len("&nbsp;&nbsp;")
            stripped = temp.strip()

            # Check for list item marker
            if stripped.startswith("- "):
                content = stripped[2:]

                # Close deeper lists if indent decreased
                while list_stack and list_stack[-1] > indent:
                    list_stack.pop()
                    result.append("</li></ul>")

                # Close previous li at same level
                if list_stack and list_stack[-1] == indent:
                    result.append("</li>")

                # Open new list if this is first item or deeper indent
                if not list_stack or list_stack[-1] < indent:
                    result.append("<ul>")
                    list_stack.append(indent)

                result.append(f"<li>{content}")
            else:
                # Not a list item - close all lists first
                while list_stack:
                    list_stack.pop()
                    result.append("</li></ul>")
                # Just add the content without wrapping (it may already have tags)
                result.append(stripped)

        # Close remaining lists
        while list_stack:
            list_stack.pop()
            result.append("</li></ul>")

        return "".join(result)

    def _html_to_markdown_with_macros(
        self, html_content: str
    ) -> Tuple[str, Dict[str, str]]:
        """Convert HTML to Markdown while preserving Confluence macros."""
        soup = BeautifulSoup(html_content, "html.parser")
        macro_map: Dict[str, str] = {}
        macro_index = 1

        # FIRST: Identify meeting-style tables and store their ORIGINAL HTML
        # BEFORE any attribute modifications
        meeting_table_originals: Dict[int, str] = {}
        for idx, table in enumerate(soup.find_all("table")):
            # Store original HTML with all attributes intact
            meeting_table_originals[idx] = str(table)

        # NOW remove data-* attributes and other Confluence-specific attributes
        for tag in soup.find_all(True):
            if not isinstance(tag, Tag):
                continue
            attrs_to_remove = [
                attr for attr in tag.attrs
                if attr.startswith("data-") or attr in ("class", "style", "id")
            ]
            for attr in attrs_to_remove:
                del tag[attr]

        # Layout tags are containers, not macros - don't preserve them as placeholders
        # Their content should be converted to markdown
        layout_tags = {"ac:layout", "ac:layout-section", "ac:layout-cell"}

        # First, unwrap layout tags so their content becomes part of the document
        for tag_name in layout_tags:
            for tag in soup.find_all(tag_name.split(":")[1], namespace="ac"):
                tag.unwrap()
        # Also try without namespace
        for tag in soup.find_all(["ac:layout", "ac:layout-section", "ac:layout-cell"]):
            if hasattr(tag, 'unwrap'):
                tag.unwrap()

        macro_tags = []
        for tag in soup.find_all(True):
            if not isinstance(tag, Tag):
                continue
            if not tag.name or not tag.name.startswith("ac:"):
                continue
            # Skip layout tags (they should have been unwrapped, but just in case)
            if tag.name in layout_tags:
                continue
            if tag.find_parent(
                lambda parent: isinstance(parent, Tag)
                and parent.name
                and parent.name.startswith("ac:")
                and parent.name not in layout_tags
            ):
                continue
            macro_tags.append(tag)

        for tag in macro_tags:
            placeholder = f"[[CONFLUENCE-MACRO-{macro_index}]]"
            macro_map[placeholder] = str(tag)
            tag.replace_with(placeholder)
            macro_index += 1

        # Check for "meeting notes" style tables (macro + lists in cells)
        # Convert these to a readable section format
        meeting_table_map: Dict[str, dict] = {}
        meeting_table_index = 1
        tables_to_remove = []

        all_tables = soup.find_all("table")
        for table_idx, table in enumerate(all_tables):
            # Check if table has SEPARATE cells for macros and lists
            # (person in one cell, notes in another cell)
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Check data rows (skip header)
            # We need: one cell with ONLY a macro, another cell with a list
            has_meeting_pattern = False
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(["td", "th"])
                macro_only_cell = False
                list_cell = False
                for cell in cells:
                    cell_text = cell.get_text().strip()
                    has_macro = "[[CONFLUENCE-MACRO-" in cell_text
                    has_list = cell.find(["ul", "ol"]) is not None
                    # Cell with ONLY a macro (no list in same cell)
                    if has_macro and not has_list:
                        # Check it's primarily a macro (not much other content)
                        text_without_macro = cell_text
                        import re as re_inner
                        text_without_macro = re_inner.sub(
                            r'\[\[CONFLUENCE-MACRO-\d+\]\]', '', text_without_macro
                        ).strip()
                        if len(text_without_macro) < 20:  # Mostly just the macro
                            macro_only_cell = True
                    # Cell with a list (but no macro, or macro is inline in notes)
                    if has_list and not has_macro:
                        list_cell = True
                if macro_only_cell and list_cell:
                    has_meeting_pattern = True
                    break

            if has_meeting_pattern:
                # Convert table to section format
                placeholder = f"[[MEETING-TABLE-{meeting_table_index}]]"

                # Extract header row
                header_cells = rows[0].find_all(["td", "th"])
                headers = [c.get_text(strip=True) for c in header_cells]

                # Extract data rows as sections
                sections = []
                for row in rows[1:]:
                    cells = row.find_all(["td", "th"])
                    row_data = {}
                    for i, cell in enumerate(cells):
                        col_name = headers[i] if i < len(headers) else f"col{i}"
                        # Convert cell content to readable text
                        row_data[col_name] = self._html_cell_to_text(cell)
                    sections.append(row_data)

                # Use the ORIGINAL HTML (with attributes) stored before cleanup
                original_html = meeting_table_originals.get(table_idx, str(table))
                meeting_table_map[placeholder] = {
                    "headers": headers,
                    "sections": sections,
                    "original_html": original_html
                }
                tables_to_remove.append((table, placeholder))
                meeting_table_index += 1
                self._debug("Converting meeting notes table to section format")

        # Replace tables with placeholders
        for table, placeholder in tables_to_remove:
            table.replace_with(placeholder)

        # Check for complex tables that can't be converted to markdown
        # (tables with colspan/rowspan attributes)
        complex_table_map: Dict[str, str] = {}
        complex_table_index = 1
        for table in soup.find_all("table"):
            has_merged_cells = False
            for cell in table.find_all(["td", "th"]):
                colspan = cell.get("colspan")
                rowspan = cell.get("rowspan")
                if (colspan and colspan != "1") or (rowspan and rowspan != "1"):
                    has_merged_cells = True
                    break

            if has_merged_cells:
                # Keep entire table as HTML
                placeholder = f"[[COMPLEX-TABLE-{complex_table_index}]]"
                complex_table_map[placeholder] = str(table)
                table.replace_with(placeholder)
                complex_table_index += 1
                self._debug("Preserved complex table as HTML (has merged cells)")

        # Protect complex content inside table cells (lists, paragraphs)
        # Markdown tables don't support newlines, so keep as compact HTML
        cell_content_map: Dict[str, str] = {}
        cell_index = 1
        for td in soup.find_all(["td", "th"]):
            # Check if cell has block-level elements that markdown can't handle
            has_complex_content = td.find(["ul", "ol"])
            if has_complex_content:
                placeholder = f"[[CELL-HTML-{cell_index}]]"
                # Store as compact single-line HTML (attrs already cleaned)
                inner_html = "".join(str(c) for c in td.children)
                # Compact: remove extra whitespace but keep structure
                compact_html = " ".join(inner_html.split())
                cell_content_map[placeholder] = compact_html
                td.clear()
                td.string = placeholder
                cell_index += 1

        # Protect <br> tags in remaining cells
        br_placeholder = "[[BR]]"
        for td in soup.find_all(["td", "th"]):
            for br in td.find_all("br"):
                br.replace_with(br_placeholder)

        markdown = markdownify(
            str(soup), heading_style="ATX", bullets="-", strip=["script", "style"]
        )

        # Restore <br> tags
        markdown = markdown.replace(br_placeholder, "<br/>")

        # Restore complex cell content as HTML (preserved for round-trip)
        for placeholder, html_content in cell_content_map.items():
            markdown = markdown.replace(placeholder, html_content)

        # Restore complex tables as HTML (with a note)
        for placeholder, table_html in complex_table_map.items():
            # Add HTML comment to indicate this is a preserved complex table
            preserved_table = f"\n<!-- Complex table preserved as HTML (has merged cells) -->\n{table_html}\n"
            markdown = markdown.replace(placeholder, preserved_table)

        # Convert meeting tables to readable section format
        for placeholder, table_data in meeting_table_map.items():
            sections_md = self._meeting_table_to_sections(table_data)
            markdown = markdown.replace(placeholder, sections_md)

        return markdown.strip(), macro_map

    def _meeting_table_to_sections(self, table_data: dict) -> str:
        """Convert meeting table data to readable section format."""
        sections = table_data["sections"]
        original_html = table_data.get("original_html", "")

        # Encode original HTML for round-trip restoration
        encoded_html = base64.b64encode(original_html.encode("utf-8")).decode("ascii")

        result_lines = [f"\n<!-- MEETING-NOTES-START:{encoded_html} -->"]

        for section in sections:
            # Find the macro placeholder (person identifier) and list content
            person_col = None
            notes_content = []

            for col_name, content in section.items():
                content_stripped = content.strip()
                if "[[CONFLUENCE-MACRO-" in content:
                    person_col = col_name
                # Only include content that looks like list items (notes)
                elif content_stripped.startswith("- ") or "\n- " in content_stripped:
                    notes_content.append(content_stripped)

            if person_col:
                # Output as section header with the macro
                person_content = section[person_col].strip()
                result_lines.append(f"\n### {person_content}")

            # Output the notes content
            for content in notes_content:
                result_lines.append(content)

        result_lines.append("\n<!-- MEETING-NOTES-END -->")
        return "\n".join(result_lines)

    def _sections_to_meeting_table(self, content: str) -> str:
        """Convert section format back to HTML table using original structure."""
        # Find meeting notes blocks with encoded original HTML
        pattern = r'<!-- MEETING-NOTES-START:([A-Za-z0-9+/=]+) -->\s*(.*?)\s*<!-- MEETING-NOTES-END -->'

        def convert_block(match):
            encoded_html = match.group(1)
            block_content = match.group(2)

            # Decode original table HTML
            try:
                original_html = base64.b64decode(encoded_html.encode("ascii")).decode("utf-8")
            except Exception:
                self._debug("Failed to decode original table HTML")
                return match.group(0)  # Return original if decoding failed

            # Parse sections from edited content (### headers followed by list items)
            edited_rows = []
            current_person = None
            current_notes = []

            for line in block_content.split('\n'):
                line = line.rstrip()
                if line.startswith('### '):
                    # Save previous section
                    if current_person is not None:
                        edited_rows.append((current_person, current_notes))
                    current_person = line[4:].strip()
                    current_notes = []
                elif line.startswith('- ') or (line.startswith('  ') and current_notes):
                    current_notes.append(line)
                elif line.strip() and current_person is not None:
                    # Other content line
                    current_notes.append(line)

            # Save last section
            if current_person is not None:
                edited_rows.append((current_person, current_notes))

            if not edited_rows:
                return original_html  # Return original if parsing failed

            # Parse original table to inject updated content
            soup = BeautifulSoup(original_html, "html.parser")
            table = soup.find("table")
            if not table:
                return original_html

            rows = table.find_all("tr")
            if len(rows) < 2:
                return original_html

            # Map the edited content back to original rows
            data_rows = rows[1:]  # Skip header
            for row_idx, row in enumerate(data_rows):
                if row_idx >= len(edited_rows):
                    break

                edited_person, edited_notes = edited_rows[row_idx]
                cells = row.find_all(["td", "th"])

                for cell in cells:
                    # Find cell with macro (person column) - check for both
                    # placeholder format and original ac: tags
                    has_macro = (
                        "[[CONFLUENCE-MACRO-" in cell.get_text() or
                        cell.find(lambda t: t.name and t.name.startswith("ac:"))
                    )
                    has_list = cell.find(["ul", "ol"])

                    if has_macro and not has_list:
                        # Person column - restore the macro placeholder
                        # The macro will be restored later by the macro_map
                        cell.clear()
                        # Wrap in content-wrapper div if original had it
                        wrapper = soup.new_tag("div")
                        wrapper.string = edited_person
                        cell.append(wrapper)
                    elif has_list:
                        # Notes column - update with edited content
                        notes_html = self._text_to_html_cell('\n'.join(edited_notes))
                        cell.clear()
                        # Parse and insert the notes HTML
                        notes_soup = BeautifulSoup(notes_html, "html.parser")
                        for child in notes_soup.children:
                            cell.append(child)

            return str(table)

        # Also try pattern without encoded HTML (fallback for old format)
        fallback_pattern = r'<!-- MEETING-NOTES-START -->\s*(.*?)\s*<!-- MEETING-NOTES-END -->'

        def fallback_convert(match):
            block_content = match.group(1)
            rows = []
            current_person = None
            current_notes = []

            for line in block_content.split('\n'):
                line = line.rstrip()
                if line.startswith('### '):
                    if current_person is not None:
                        rows.append((current_person, current_notes))
                    current_person = line[4:].strip()
                    current_notes = []
                elif line.startswith('- ') or (line.startswith('  ') and current_notes):
                    current_notes.append(line)
                elif line.strip() and current_person is not None:
                    current_notes.append(line)

            if current_person is not None:
                rows.append((current_person, current_notes))

            if not rows:
                return match.group(0)

            table_rows = []
            for person, notes in rows:
                notes_html = self._text_to_html_cell('\n'.join(notes))
                table_rows.append(f'<tr><td>{person}</td><td>{notes_html}</td></tr>')

            return f'''<table>
<tr><th>Wer</th><th>Notizen</th></tr>
{''.join(table_rows)}
</table>'''

        # Try the new pattern first, then fallback
        result = re.sub(pattern, convert_block, content, flags=re.DOTALL)
        result = re.sub(fallback_pattern, fallback_convert, result, flags=re.DOTALL)
        return result

    def _escape_markdown_heading(self, text: str) -> str:
        """Escape characters that can break markdown headings."""
        escaped = text.replace("\r", " ").replace("\n", " ")
        escaped = escaped.replace("\\", "\\\\").replace("#", "\\#")
        return escaped

    def _redact_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Redact sensitive headers before logging."""
        sensitive = {"authorization", "x-authorization", "token", "x-auth-token", "cookie"}
        return {
            k: "REDACTED" if k.lower() in sensitive else v
            for k, v in headers.items()
        }

    def _debug(self, message: str) -> None:
        """Print debug output when verbose is enabled."""
        if self.verbose:
            print(f"DEBUG: {message}")

    def _encode_macro_map(self, macro_map: Dict[str, str]) -> str:
        """Encode macro map for embedding in markdown."""
        payload = json.dumps(macro_map).encode("utf-8")
        return base64.b64encode(payload).decode("ascii")

    def _decode_macro_map(self, encoded: str) -> Dict[str, str]:
        """Decode macro map embedded in markdown."""
        try:
            payload = base64.b64decode(encoded.encode("ascii"))
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return {}

    def _is_table_separator(self, line: str) -> bool:
        """Check if a line is a markdown table separator."""
        pattern = r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
        return re.match(pattern, line) is not None

    def _split_table_row(self, line: str) -> List[str]:
        """Split a markdown table row into cells."""
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        return [cell.strip() for cell in stripped.split("|")]

    def _parse_markdown_table(self, table_lines: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
        """Parse markdown table lines into headers and row dicts."""
        if len(table_lines) < 2:
            return [], []

        # Parse header
        headers = self._split_table_row(table_lines[0])

        # Skip separator line, parse data rows
        rows = []
        for line in table_lines[2:]:
            cells = self._split_table_row(line)
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = cells[i] if i < len(cells) else ""
            rows.append(row_dict)

        return headers, rows

    def _table_to_yaml(self, headers: List[str], rows: List[Dict[str, str]]) -> str:
        """Convert table data to YAML format."""
        data = {"_headers": headers, "rows": rows}
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _yaml_to_table(self, yaml_text: str) -> str:
        """Convert YAML back to markdown table."""
        data = yaml.safe_load(yaml_text)
        headers = data.get("_headers", [])
        rows = data.get("rows", [])

        if not headers:
            if rows:
                headers = list(rows[0].keys())
            else:
                return ""

        def normalize_cell(val: Any) -> str:
            """Normalize cell value, preserving line breaks as <br/>."""
            s = str(val) if val is not None else ""
            # Replace newlines with <br/> for XHTML (markdown tables can't have newlines)
            s = s.replace("\n", "<br/>")
            return s

        # Calculate column widths (using normalized values)
        widths = {h: len(h) for h in headers}
        for row in rows:
            for h in headers:
                val = normalize_cell(row.get(h, ""))
                widths[h] = max(widths[h], len(val))

        # Build table
        lines = []
        header_cells = [h.ljust(widths[h]) for h in headers]
        lines.append("| " + " | ".join(header_cells) + " |")
        sep_cells = ["-" * widths[h] for h in headers]
        lines.append("| " + " | ".join(sep_cells) + " |")
        for row in rows:
            cells = [normalize_cell(row.get(h, "")).ljust(widths[h]) for h in headers]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _convert_tables_to_yaml(self, md_content: str) -> str:
        """Find markdown tables and convert them to YAML blocks."""
        lines = md_content.split('\n')
        result = []
        i = 0
        table_num = 1

        while i < len(lines):
            line = lines[i]

            # Check if this is the start of a table
            if line.strip().startswith('|') and '|' in line[1:]:
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    table_lines.append(lines[i])
                    i += 1

                # Check if it's a valid table (has separator)
                if len(table_lines) >= 2 and self._is_table_separator(table_lines[1]):
                    headers, rows = self._parse_markdown_table(table_lines)
                    if headers and rows:
                        yaml_content = self._table_to_yaml(headers, rows)
                        result.append(f"```yaml table-{table_num}")
                        result.append(yaml_content.rstrip())
                        result.append("```")
                        table_num += 1
                        continue

                # Not a valid table, keep original
                result.extend(table_lines)
            else:
                result.append(line)
                i += 1

        return '\n'.join(result)

    def _convert_yaml_to_tables(self, content: str) -> str:
        """Convert YAML table blocks back to markdown tables."""
        pattern = r'```yaml table-\d+\n(.*?)```'

        def replace_yaml_block(match):
            yaml_content = match.group(1)
            return self._yaml_to_table(yaml_content)

        return re.sub(pattern, replace_yaml_block, content, flags=re.DOTALL)

    def _build_rich_renderables(self, markdown_content: str) -> list:
        """Build Rich renderables from markdown with table support."""
        from rich import box
        from rich.markdown import Markdown
        from rich.table import Table
        from rich.text import Text

        renderables = []
        text_lines: List[str] = []
        lines = markdown_content.splitlines()
        index = 0

        while index < len(lines):
            line = lines[index]
            if (
                "|" in line
                and index + 1 < len(lines)
                and self._is_table_separator(lines[index + 1])
            ):
                if text_lines:
                    renderables.append(Markdown("\n".join(text_lines)))
                    text_lines = []

                header = self._split_table_row(line)
                index += 2
                rows = []
                while (
                    index < len(lines) and lines[index].strip() and "|" in lines[index]
                ):
                    rows.append(self._split_table_row(lines[index]))
                    index += 1

                table = Table(
                    show_header=True,
                    header_style="bold cyan",
                    box=box.HEAVY,
                    show_lines=True,
                    border_style="cyan",
                )
                for col in header:
                    table.add_column(col, style="white")
                for row in rows:
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    table.add_row(*row[: len(header)])
                renderables.append(table)
                continue

            if line.startswith("# "):
                if text_lines:
                    renderables.append(Markdown("\n".join(text_lines)))
                    text_lines = []
                renderables.append(Text(line[2:], style="bold magenta"))
                index += 1
                continue
            if line.startswith("## "):
                if text_lines:
                    renderables.append(Markdown("\n".join(text_lines)))
                    text_lines = []
                renderables.append(Text(line[3:], style="bold blue"))
                index += 1
                continue
            if line.startswith("### "):
                if text_lines:
                    renderables.append(Markdown("\n".join(text_lines)))
                    text_lines = []
                renderables.append(Text(line[4:], style="bold green"))
                index += 1
                continue

            text_lines.append(line)
            index += 1

        if text_lines:
            renderables.append(Markdown("\n".join(text_lines)))

        return renderables

    def _paginate_text(self, text: str, show_actions: bool = False) -> str:
        """Print text in pages, waiting for user input between chunks.

        Args:
            text: The text to display
            show_actions: If True, show [e]dit [b]ack [q]uit options

        Returns:
            The last action: 'e', 'b', 'q', or 'done' (finished reading)
        """
        term_height = shutil.get_terminal_size((80, 24)).lines
        page_size = max(5, term_height - 2)
        lines = text.splitlines()
        index = 0

        if show_actions:
            prompt = "[Enter] more  [e]dit  [b]ack  [q]uit: "
        else:
            prompt = "Press Enter for more, or 'q' to quit: "

        while index < len(lines):
            chunk = "\n".join(lines[index : index + page_size])
            print(chunk)
            index += page_size
            if index >= len(lines):
                break
            choice = input(prompt).strip().lower()
            if choice in ("q", "e", "b"):
                return choice

        # Finished reading - show final prompt if actions enabled
        if show_actions:
            print("\n[e]dit  [b]ack  [q]uit")
            choice = input("> ").strip().lower()
            if choice in ("e", "b", "q"):
                return choice

        return "done"

    def _render_markdown_to_ansi(self, markdown_content: str, width: int) -> str:
        """Render markdown with Rich and return ANSI text without printing."""
        from rich.console import Console

        console = Console(
            width=width,
            record=True,
            force_terminal=True,
            file=io.StringIO(),
        )
        for renderable in self._build_rich_renderables(markdown_content):
            console.print(renderable)
        return console.export_text(styles=True)

    def _extract_macro_map_from_markdown(self, content: str) -> Dict[str, str]:
        """Extract macro map from the markdown content."""
        pattern = r"<!-- CONFLUENCE_MACROS_START\n(.*?)\nCONFLUENCE_MACROS_END -->"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}
        encoded = match.group(1).strip()
        return self._decode_macro_map(encoded)

    def _remove_macro_block(self, content: str) -> str:
        """Remove the macro block from markdown content."""
        pattern = r"<!-- CONFLUENCE_MACROS_START\n(.*?)\nCONFLUENCE_MACROS_END -->\n?"
        return re.sub(pattern, "", content, flags=re.DOTALL)

    # ── Confluence storage format (XHTML) helpers ─────────────────────────────

    # Void HTML elements that must be self-closing in XML/XHTML
    _VOID_ELEMENTS = frozenset(
        ["br", "hr", "img", "input", "link", "meta", "area", "base",
         "col", "embed", "param", "source", "track", "wbr"]
    )

    # Elements where internal whitespace is semantically significant
    _PRESERVE_WS_TAGS = ("ac:plain-text-body", "ac:plain-text-link-body", "pre")

    # Namespace declarations common in Confluence storage format
    _STORAGE_NS = (
        'xmlns:ac="http://atlassian.com/content/ac" '
        'xmlns:ri="http://atlassian.com/content/ri" '
        'xmlns:at="http://atlassian.com/content/at"'
    )

    def _validate_storage_xhtml(self, html: str) -> tuple[bool, str | None]:
        """Validate Confluence storage format XHTML for well-formedness.

        Normalizes ``<br>`` → ``<br/>`` and void elements before checking.
        Returns ``(True, None)`` on success or ``(False, error_message)`` on
        failure. Call this before every PUT/POST in storage mode so malformed
        input fails locally with a clear message instead of an opaque HTTP 400.
        """
        import xml.etree.ElementTree as ET

        # Step 1: normalize void elements to be self-closing
        content = html
        for tag in self._VOID_ELEMENTS:
            # Match <tag> or <tag attrs> NOT already self-closed and NOT followed
            # by </tag> (i.e. the element is empty and must be self-closed).
            content = re.sub(
                rf'<({re.escape(tag)})(\s[^>]*)?(?<!/)>',
                r'<\1\2/>',
                content,
                flags=re.IGNORECASE,
            )

        # Step 2: detect bare & not part of a valid XML entity or char ref
        bare_amp = re.search(
            r'&(?!(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);)',
            content,
        )
        if bare_amp:
            pos = bare_amp.start()
            ctx = content[max(0, pos - 20): pos + 40]
            return (
                False,
                f"Unescaped '&' found near: …{ctx!r}… — replace with '&amp;'.",
            )

        # Step 3: try parsing as XML with known Confluence namespace declarations
        wrapped = f'<_root {self._STORAGE_NS}>{content}</_root>'
        try:
            ET.fromstring(wrapped)
        except ET.ParseError as exc:
            return (
                False,
                f"Storage XHTML is not well-formed: {exc}. "
                "Check for unclosed tags, mismatched elements, or invalid characters.",
            )

        return True, None

    def _prettify_storage(self, html: str) -> str:
        """Pretty-print Confluence storage format XHTML for human editing.

        Preserves significant whitespace inside ``<pre>``,
        ``<ac:plain-text-body>``, and ``<ac:plain-text-link-body>`` elements
        so that code block content is not indented by the prettifier.
        Confluence re-normalizes storage on save, so this is cosmetic only.
        """
        import uuid

        preserved: dict[str, str] = {}
        content = html

        for tag in self._PRESERVE_WS_TAGS:
            pattern = re.compile(
                rf'(<{re.escape(tag)}(?:\s[^>]*)?>)(.*?)(</{re.escape(tag)}>)',
                re.DOTALL | re.IGNORECASE,
            )

            def _replacer(m: re.Match, _tag: str = tag) -> str:
                key = f"__PRESERVE_{uuid.uuid4().hex}__"
                preserved[key] = m.group(0)
                return key

            content = pattern.sub(_replacer, content)

        soup = BeautifulSoup(content, "html.parser")
        pretty = soup.prettify()

        for key, original in preserved.items():
            pretty = pretty.replace(key, original)

        return pretty

    # ── End storage helpers ────────────────────────────────────────────────────

    def _markdown_to_html(self, markdown_content: str) -> str:
        """Convert markdown to HTML using proper markdown parser."""
        # Use markdown library with table support and HTML passthrough
        md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br", "md_in_html"])
        html_content = md.convert(markdown_content)
        # Convert HTML5 <br> to XHTML <br/> for Confluence compatibility
        html_content = re.sub(r'<br\s*/?>', '<br/>', html_content)
        return html_content

    def edit_page_with_editor(
        self, page_url: str, content: Optional[str] = None, content_type: str = "markdown"
    ) -> dict:
        """
        Edit page content using system editor or provided content.

        Args:
            page_url: Full URL to the Confluence page
            content: If provided, skip the editor and use this content directly.
            content_type: 'markdown' (default) or 'html' — only used when content is provided.

        Returns:
            Updated page data
        """
        # Get current page content
        page_data = self.get_page_by_url(page_url)
        current_markdown, macro_map = self._html_to_markdown_with_macros(
            page_data["body"]["storage"]["value"]
        )
        original_macro_map = dict(macro_map)

        # Convert tables to YAML if requested
        edit_content = current_markdown
        if self.table_format == "yaml":
            edit_content = self._convert_tables_to_yaml(current_markdown)
            self._debug("Converted tables to YAML format")

        # Create temporary file with current content
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as temp_file:
            temp_file.write(f"# {page_data['title']}\n\n")
            temp_file.write(
                "<!-- Edit the content below. Lines starting with <!-- are comments and will be ignored -->\n"
            )
            temp_file.write(
                f"<!-- Page ID: {page_data['id']}, Version: {page_data['version']['number']} -->\n\n"
            )
            if self.table_format == "yaml":
                temp_file.write("<!-- Tables are in YAML format for easier editing -->\n\n")
            temp_file.write(edit_content)
            if macro_map:
                encoded_macros = self._encode_macro_map(macro_map)
                temp_file.write("\n\n<!-- CONFLUENCE_MACROS_START\n")
                temp_file.write(encoded_macros)
                temp_file.write("\nCONFLUENCE_MACROS_END -->\n")
            temp_file_path = temp_file.name

        try:
            if content is not None:
                # Non-interactive mode: write provided content directly.
                self._debug("Non-interactive edit: using provided content")
                if content_type in ("html", "storage"):
                    # Storage XHTML passthrough: validate then PUT directly,
                    # bypassing the markdown pipeline entirely.  This fixes the
                    # former html→markdown→html round-trip that was lossy for
                    # tables and macros.
                    ok, err = self._validate_storage_xhtml(content)
                    if not ok:
                        raise ValueError(
                            f"Invalid Confluence storage format XHTML: {err}"
                        )
                    self._debug("Storage passthrough validated; uploading directly")
                    update_data = {
                        "version": {"number": page_data["version"]["number"] + 1},
                        "title": page_data["title"],
                        "type": "page",
                        "body": {
                            "storage": {"value": content, "representation": "storage"}
                        },
                    }
                    url = f"{self.api_base}/content/{page_data['id']}"
                    response = self._request("PUT", url, json=update_data)
                    self._debug(f"Storage PUT response: {response.status_code}")
                    if response.status_code == 409:
                        raise RuntimeError(
                            "Confluence rejected the update due to a version conflict. "
                            "Refresh the page and try again."
                        )
                    response.raise_for_status()
                    return response.json()
                else:
                    write_content = content
                with open(temp_file_path, "w") as f:
                    f.write(f"# {page_data['title']}\n\n")
                    f.write(write_content)
                    if macro_map:
                        encoded_macros = self._encode_macro_map(macro_map)
                        f.write("\n\n<!-- CONFLUENCE_MACROS_START\n")
                        f.write(encoded_macros)
                        f.write("\nCONFLUENCE_MACROS_END -->\n")
            else:
                # Interactive mode: open system editor
                editor = self._get_editor()
                self._debug(f"Detected editor: {editor}")
                self._debug(f"Temp file path: {temp_file_path}")

                print(f"Opening editor: {editor}")
                print(f"Editing page: {page_data['title']}")
                print(
                    "Save and close the editor to upload changes, or exit without saving to cancel."
                )

                # Get original file modification time
                original_mtime = os.path.getmtime(temp_file_path)
                self._debug(f"Original file mtime: {original_mtime}")

                editor_cmd = editor + [temp_file_path]
                editor_name = editor[0].lower()
                self._debug(f"Editor name: {editor_name}")

                if editor_name == "code":
                    editor_cmd = editor + ["--wait", temp_file_path]
                    self._debug("Added --wait flag for VS Code")

                terminal_editors = ("vim", "nvim", "vi", "nano", "emacs", "pico", "joe")
                if editor_name in terminal_editors:
                    cmd_str = " ".join(shlex.quote(arg) for arg in editor_cmd)
                    self._debug(f"Using os.system for terminal editor: {cmd_str}")
                    exit_code = os.system(cmd_str)
                    self._debug(f"os.system exit code (raw): {exit_code}")
                    result = type("Result", (), {"returncode": exit_code >> 8})()
                    self._debug(f"Editor return code: {result.returncode}")
                else:
                    self._debug(f"Using subprocess.run: {editor_cmd}")
                    result = subprocess.run(editor_cmd)
                    self._debug(f"Editor return code: {result.returncode}")

                if result.returncode != 0:
                    self._debug(f"Editor failed with code: {result.returncode}")
                    print("Editor exited with error code. Cancelling upload.")
                    return None

                # Check if file was modified
                new_mtime = os.path.getmtime(temp_file_path)
                self._debug(f"New file mtime: {new_mtime}")
                if new_mtime == original_mtime:
                    self._debug("File mtime unchanged - no modifications detected")
                    print("File was not modified. No changes to upload.")
                    return None

            self._debug("File was modified, reading content...")
            # Read edited content
            with open(temp_file_path, "r") as f:
                edited_content = f.read()
            self._debug(f"Read {len(edited_content)} bytes from temp file")

            extracted_macro_map = self._extract_macro_map_from_markdown(edited_content)
            if extracted_macro_map:
                macro_map = extracted_macro_map
            else:
                macro_map = original_macro_map
            edited_content = self._remove_macro_block(edited_content)

            # Convert YAML table blocks back to markdown tables
            if self.table_format == "yaml":
                edited_content = self._convert_yaml_to_tables(edited_content)
                self._debug("Converted YAML blocks back to markdown tables")

            # Remove metadata comments and title
            lines = edited_content.split("\n")
            content_lines = []
            skip_title = True

            for line in lines:
                # Skip metadata comments but keep MEETING-NOTES markers
                if line.startswith("<!--") and "-->" in line:
                    if "MEETING-NOTES-" in line:
                        content_lines.append(line)  # Keep meeting notes markers
                    continue  # Skip other comment lines
                if skip_title and line.startswith("# "):
                    skip_title = False
                    continue  # Skip title line
                content_lines.append(line)

            # Join and clean up
            cleaned_content = "\n".join(content_lines).strip()

            # Convert meeting notes sections back to table format
            if "MEETING-NOTES-START" in cleaned_content:
                self._debug("Found MEETING-NOTES markers, converting to table")
                cleaned_content = self._sections_to_meeting_table(cleaned_content)
                self._debug(f"After conversion (first 500): {cleaned_content[:500]}")
            else:
                self._debug("No MEETING-NOTES markers found in content")

            # Convert markdown to HTML first (with placeholders intact)
            html_content = self._markdown_to_html(cleaned_content)

            # Restore macro placeholders AFTER HTML conversion
            # This prevents the markdown parser from corrupting macro XML
            for placeholder, macro_html in macro_map.items():
                # Handle case where placeholder is wrapped in <p> tags
                html_content = html_content.replace(f"<p>{placeholder}</p>", macro_html)
                html_content = html_content.replace(placeholder, macro_html)

            # Final XHTML cleanup - ensure all <br> tags are self-closing
            html_content = re.sub(r'<br\s*(?!/)>', '<br/>', html_content)

            self._debug(f"Final HTML length: {len(html_content)}")
            self._debug(f"Final HTML (first 1000 chars): {html_content[:1000]}")

            # Update page
            update_data = {
                "version": {"number": page_data["version"]["number"] + 1},
                "title": page_data["title"],
                "type": "page",
                "body": {
                    "storage": {"value": html_content, "representation": "storage"}
                },
            }

            url = f"{self.api_base}/content/{page_data['id']}"
            response = self._request("PUT", url, json=update_data)
            self._debug(f"Update response status: {response.status_code}")
            if response.status_code != 200:
                self._debug(f"Update response body: {response.text[:2000]}")
                logger.error("HTTP %s", response.status_code)
                logger.error("%s", response.text[:500])
            if response.status_code == 409:
                raise RuntimeError(
                    "Confluence rejected the update due to a version conflict. "
                    "Refresh the page and try again."
                )
            response.raise_for_status()

            print("✅ Page updated successfully!")
            print(f"   New version: {update_data['version']['number']}")

            return response.json()

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def _get_editor(self) -> List[str]:
        """Get the preferred editor from environment or defaults."""
        # Check for command-line override first
        if self.editor_override:
            editor_parts = shlex.split(self.editor_override)
            if editor_parts and shutil.which(editor_parts[0]):
                self._debug(f"Using editor override: {editor_parts}")
                return editor_parts
            self._debug(f"Editor override not found: {self.editor_override}")

        # Try EDITOR environment variable
        editor = os.environ.get("EDITOR")
        if editor:
            editor_parts = shlex.split(editor)
            if editor_parts and shutil.which(editor_parts[0]):
                return editor_parts

        # Try common editors
        editors = ["code", "vim", "nano", "emacs", "gedit", "notepad++"]

        for ed in editors:
            if shutil.which(ed):
                return [ed]

        # Last resort
        if os.name == "nt":  # Windows
            return ["notepad"]
        else:
            return ["vi"]  # Should be available on all Unix systems

    # ==================== Async Methods ====================

    async def _async_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Make an async HTTP request with retry on transient errors.

        Args:
            client: httpx.AsyncClient instance
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL to request
            **kwargs: Additional arguments passed to httpx

        Returns:
            Response object
        """
        self._debug(f"ASYNC {method} {url}")
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await client.request(method, url, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    wait_time = int(retry_after) if retry_after.isdigit() else 60
                    logger.warning("Rate limited. Waiting %s seconds...", wait_time)
                    await asyncio.sleep(wait_time)
                    continue

                # Retry on 5xx server errors
                if response.status_code >= 500:
                    self._debug(f"Server error {response.status_code}, retrying...")
                    await asyncio.sleep(2 ** attempt)
                    continue

                return response

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                self._debug(f"Connection error on attempt {attempt + 1}: {e}")
                await asyncio.sleep(2 ** attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Max retries exceeded")

    async def async_get_page_content(self, page_id: str) -> dict:
        """
        Get page content by ID asynchronously.

        Args:
            page_id: Confluence page ID

        Returns:
            Page data dictionary
        """
        url = f"{self.api_base}/content/{page_id}"
        params = {"expand": "body.storage,space,version,ancestors"}

        async with httpx.AsyncClient(
            headers=self._async_headers, timeout=30.0
        ) as client:
            response = await self._async_request(
                client, "GET", url, params=params
            )

            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

            return response.json()

    async def async_list_children(self, page_id: str, limit: int = 50) -> list:
        """
        List child pages of a given page asynchronously.

        Args:
            page_id: Parent page ID
            limit: Maximum number of children to return

        Returns:
            List of child page dicts
        """
        url = f"{self.api_base}/content/{page_id}/child/page"
        params = {"limit": limit, "expand": "space,version"}

        async with httpx.AsyncClient(
            headers=self._async_headers, timeout=30.0
        ) as client:
            response = await self._async_request(
                client, "GET", url, params=params
            )

            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            pages = []
            for content in data.get("results", []):
                child_id = content.get("id")
                if not child_id:
                    continue
                space = content.get("space", {})
                version = content.get("version", {})
                pages.append(
                    {
                        "id": child_id,
                        "title": content.get("title", "(untitled)"),
                        "space": space.get("key", "UNKNOWN"),
                        "last_modified": version.get("when", "unknown"),
                        "url": f"{self.base_url}/pages/viewpage.action?pageId={child_id}",
                    }
                )

            return pages

    async def async_get_pages_batch(self, page_ids: List[str]) -> List[dict]:
        """
        Get multiple pages in parallel.

        Args:
            page_ids: List of page IDs to fetch

        Returns:
            List of page data dictionaries
        """
        async with httpx.AsyncClient(
            headers=self._async_headers, timeout=30.0
        ) as client:
            tasks = []
            for page_id in page_ids:
                url = f"{self.api_base}/content/{page_id}"
                params = {"expand": "body.storage,space,version,ancestors"}
                tasks.append(
                    self._async_request(client, "GET", url, params=params)
                )

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for response in responses:
                if isinstance(response, Exception):
                    logger.error("Failed to fetch page: %s", response)
                    continue
                if response.status_code == 200:
                    results.append(response.json())
                else:
                    logger.error("HTTP %s fetching page", response.status_code)

            return results

    async def async_download_pages_batch(
        self, page_urls: List[str]
    ) -> List[Tuple[str, str]]:
        """
        Download multiple pages as markdown in parallel.

        Args:
            page_urls: List of page URLs

        Returns:
            List of tuples (title, markdown_content)
        """
        # First, extract page IDs
        page_ids = []
        for url in page_urls:
            page_id = self._extract_page_id_from_url(url)
            if page_id:
                page_ids.append(page_id)

        # Fetch pages in parallel
        pages = await self.async_get_pages_batch(page_ids)

        # Convert to markdown
        results = []
        for page_data in pages:
            html_content = page_data["body"]["storage"]["value"]
            markdown_content = self._html_to_markdown(html_content)

            safe_title = self._escape_markdown_heading(page_data["title"])
            metadata = f"""# {safe_title}

**Space:** {page_data["space"]["name"]}
**Page ID:** {page_data["id"]}
**Version:** {page_data["version"]["number"]}
**URL:** {self.base_url}/pages/viewpage.action?pageId={page_data["id"]}

---

"""
            full_markdown = metadata + markdown_content
            results.append((page_data["title"], full_markdown))

        return results

    async def async_list_children_recursive(
        self,
        page_id: str,
        max_depth: int = 10,
        current_depth: int = 0,
    ) -> List[dict]:
        """
        Recursively list all descendant pages in parallel.

        Args:
            page_id: Root page ID
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth (internal)

        Returns:
            List of all descendant pages with 'depth' field
        """
        if current_depth >= max_depth:
            return []

        children = await self.async_list_children(page_id)

        # Add depth to each child
        for child in children:
            child["depth"] = current_depth

        # Recursively get grandchildren in parallel
        if children:
            tasks = [
                self.async_list_children_recursive(
                    child["id"], max_depth, current_depth + 1
                )
                for child in children
            ]
            nested_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in nested_results:
                if isinstance(result, Exception):
                    logger.error("Error in recursive listing: %s", result)
                    continue
                children.extend(result)

        return children

    def download_pages_parallel(self, page_urls: List[str]) -> List[Tuple[str, str]]:
        """
        Synchronous wrapper for parallel page download.

        Args:
            page_urls: List of page URLs to download

        Returns:
            List of tuples (title, markdown_content)
        """
        return asyncio.run(self.async_download_pages_batch(page_urls))

    def list_children_recursive_parallel(
        self, page_url: str, max_depth: int = 10
    ) -> List[dict]:
        """
        Synchronous wrapper for recursive child listing.

        Args:
            page_url: Parent page URL
            max_depth: Maximum recursion depth

        Returns:
            List of all descendant pages
        """
        page_data = self.get_page_by_url(page_url)
        return asyncio.run(
            self.async_list_children_recursive(page_data["id"], max_depth)
        )
