"""Confluence API client and helpers."""

import base64
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import markdown
import requests
import yaml
from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify


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
        """
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/rest/api"
        self.session = requests.Session()
        self.verbose = verbose
        self.editor_override = editor
        self.table_format = table_format

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

    def test_authentication(self) -> dict:
        """Test authentication by getting current user info."""
        url = f"{self.api_base}/user/current"
        self._debug(f"Testing authentication at: {url}")

        response = self.session.get(url)
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

        response = self.session.get(url, params=params)

        self._debug(f"Response status code: {response.status_code}")
        self._debug(f"Response headers: {dict(response.headers)}")
        self._debug(f"Response content (first 500 chars): {response.text[:500]}")

        if response.status_code != 200:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"ERROR: Full response: {response.text}")
            response.raise_for_status()

        try:
            return response.json()
        except Exception as e:
            print(f"ERROR: Failed to parse JSON response: {e}")
            print(f"ERROR: Full response text: {response.text}")
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

    def list_recent_pages(self, limit: int = 10) -> list:
        """List recently edited pages for the current user."""
        url = f"{self.api_base}/search"
        self._debug(f"Fetching recent pages from: {url}")
        data = None
        for cql in self._recent_pages_cql_variants():
            params = {
                "cql": cql,
                "limit": limit,
                "expand": "content.space,content.version",
            }
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                break
            if response.status_code == 400 and (
                "No field exists" in response.text
                or "Could not parse cql" in response.text
            ):
                continue
            print(f"ERROR: HTTP {response.status_code}")
            print(f"ERROR: Full response: {response.text}")
            response.raise_for_status()

        if data is None:
            raise RuntimeError(
                "Confluence rejected all recent-page CQL variants. "
                "This instance may not support user-based filters."
            )
        pages = []
        for item in data.get("results", []):
            content = item.get("content", item)
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

    def list_recently_viewed_pages(self, limit: int = 10) -> list:
        """List recently viewed pages for the current user."""
        url = f"{self.api_base}/search"
        self._debug(f"Fetching recently viewed pages from: {url}")
        data = None
        for cql in self._recently_viewed_cql_variants():
            params = {
                "cql": cql,
                "limit": limit,
                "expand": "content.space,content.version",
            }
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                break
            if response.status_code == 400 and (
                "No field exists" in response.text
                or "Could not parse cql" in response.text
            ):
                continue
            print(f"ERROR: HTTP {response.status_code}")
            print(f"ERROR: Full response: {response.text}")
            response.raise_for_status()

        if data is None:
            raise RuntimeError(
                "Confluence rejected all recently-viewed CQL variants. "
                "This instance may not support view tracking."
            )

        pages = []
        for item in data.get("results", []):
            content = item.get("content", item)
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

    def search_pages(self, cql: str, limit: int = 10) -> list:
        """Search pages using the provided CQL."""
        url = f"{self.api_base}/search"
        self._debug(f"Searching pages with CQL: {cql}")
        params = {
            "cql": cql,
            "limit": limit,
            "expand": "content.space,content.version",
        }
        response = self.session.get(url, params=params)
        if response.status_code != 200:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"ERROR: Full response: {response.text}")
            response.raise_for_status()

        data = response.json()
        pages = []
        for item in data.get("results", []):
            content = item.get("content", item)
            if content.get("type") and content.get("type") != "page":
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

    def download_as_markdown(
        self, page_url: str, output_file: Optional[str] = None
    ) -> str:
        """
        Download page content and convert to markdown.

        Args:
            page_url: Full URL to the Confluence page
            output_file: Optional file path to save markdown

        Returns:
            Markdown content as string
        """
        page_data = self.get_page_by_url(page_url)

        # Extract HTML content
        html_content = page_data["body"]["storage"]["value"]

        # Convert HTML to Markdown
        markdown_content = self._html_to_markdown(html_content)

        # Add metadata header
        safe_title = self._escape_markdown_heading(page_data["title"])
        metadata = f"""# {safe_title}

**Space:** {page_data["space"]["name"]}
**Page ID:** {page_data["id"]}
**Version:** {page_data["version"]["number"]}
**URL:** {self.base_url}/pages/viewpage.action?pageId={page_data["id"]}

---

"""

        full_markdown = metadata + markdown_content

        # Save to file if specified
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
        response = self.session.put(url, json=update_data)
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

        response = self.session.post(url, json=page_data)

        if response.status_code not in (200, 201):
            print(f"ERROR: HTTP {response.status_code}")
            print(f"ERROR: Full response: {response.text}")

        response.raise_for_status()

        created_page = response.json()
        page_id = created_page["id"]
        print(f"✅ Page created successfully!")
        print(f"   Title: {title}")
        print(f"   Space: {space_key}")
        print(f"   Page ID: {page_id}")
        print(f"   URL: {self.base_url}/pages/viewpage.action?pageId={page_id}")

        return created_page

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

    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML to Markdown."""
        # Clean up HTML first
        soup = BeautifulSoup(html_content, "html.parser")

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

        # Protect complex content inside table cells (lists, multiple paragraphs, etc.)
        # Markdown tables don't support block-level content in cells
        # Keep as HTML to avoid breaking the structure
        cell_content_map: Dict[str, str] = {}
        cell_index = 1
        for td in soup.find_all(["td", "th"]):
            # Check if cell has block-level elements that markdown can't handle
            has_complex_content = td.find(["ul", "ol"])
            if has_complex_content:
                placeholder = f"[[CELL-HTML-{cell_index}]]"
                # Store original HTML
                cell_content_map[placeholder] = "".join(str(c) for c in td.children)
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

        # Restore complex cell content as HTML (safe, no conversion)
        for placeholder, html_content in cell_content_map.items():
            markdown = markdown.replace(placeholder, html_content)

        return markdown.strip(), macro_map

    def _escape_markdown_heading(self, text: str) -> str:
        """Escape characters that can break markdown headings."""
        escaped = text.replace("\r", " ").replace("\n", " ")
        escaped = escaped.replace("\\", "\\\\").replace("#", "\\#")
        return escaped

    def _redact_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Redact sensitive headers before logging."""
        redacted = dict(headers)
        if "Authorization" in redacted:
            redacted["Authorization"] = "REDACTED"
        return redacted

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

    def _markdown_to_html(self, markdown_content: str) -> str:
        """Convert markdown to HTML using proper markdown parser."""
        # Use markdown library with table support
        md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
        html_content = md.convert(markdown_content)
        # Convert HTML5 <br> to XHTML <br/> for Confluence compatibility
        html_content = re.sub(r'<br\s*/?>', '<br/>', html_content)
        return html_content

    def edit_page_with_editor(self, page_url: str) -> dict:
        """
        Edit page content using system editor.

        Args:
            page_url: Full URL to the Confluence page

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
            # Detect editor
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

            # Open editor - use os.system for proper TTY handling with terminal editors
            editor_cmd = editor + [temp_file_path]
            editor_name = editor[0].lower()
            self._debug(f"Editor name: {editor_name}")

            # GUI editors need --wait flag
            if editor_name == "code":
                editor_cmd = editor + ["--wait", temp_file_path]
                self._debug("Added --wait flag for VS Code")

            # Terminal editors (vim, nvim, nano, etc.) need proper TTY
            terminal_editors = ("vim", "nvim", "vi", "nano", "emacs", "pico", "joe")
            if editor_name in terminal_editors:
                # Use os.system for proper TTY handling
                import shlex
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
                if line.startswith("<!--") and "-->" in line:
                    continue  # Skip comment lines
                if skip_title and line.startswith("# "):
                    skip_title = False
                    continue  # Skip title line
                content_lines.append(line)

            # Join and clean up
            cleaned_content = "\n".join(content_lines).strip()

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
            response = self.session.put(url, json=update_data)
            self._debug(f"Update response status: {response.status_code}")
            if response.status_code != 200:
                self._debug(f"Update response body: {response.text[:2000]}")
                print(f"ERROR: HTTP {response.status_code}")
                print(f"ERROR: {response.text[:500]}")
            if response.status_code == 409:
                raise RuntimeError(
                    "Confluence rejected the update due to a version conflict. "
                    "Refresh the page and try again."
                )
            response.raise_for_status()

            print(f"✅ Page updated successfully!")
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
