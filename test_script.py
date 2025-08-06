#!/usr/bin/env python3
"""
Test script for Confluence Markdown Tool
"""

from confluence_markdown_tool import ConfluenceClient


def test_client_initialization():
    """Test that the client initializes correctly."""
    print("Testing client initialization...")
    
    # Test with token
    try:
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token"
        )
        print("✓ Token authentication initialization successful")
    except Exception as e:
        print(f"✗ Token authentication failed: {e}")
    
    # Test with username/password
    try:
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            username="test-user",
            password="test-pass"
        )
        print("✓ Basic authentication initialization successful")
    except Exception as e:
        print(f"✗ Basic authentication failed: {e}")
    
    # Test invalid auth
    try:
        client = ConfluenceClient(base_url="https://example.confluence.com")
        print("✗ Should have failed with no auth")
    except ValueError as e:
        print("✓ Correctly rejected missing authentication")


def test_url_parsing():
    """Test URL parsing functionality."""
    print("\nTesting URL parsing...")
    
    client = ConfluenceClient(
        base_url="https://example.confluence.com",
        token="test-token"
    )
    
    # Test different URL formats
    test_urls = [
        ("https://example.confluence.com/pages/viewpage.action?pageId=123456", "123456"),
        ("https://example.confluence.com/display/SPACE/Page+Title", None),
        ("https://example.confluence.com/pages/123456/Page+Title", "123456"),
    ]
    
    for url, expected_id in test_urls:
        result = client._extract_page_id_from_url(url)
        if result == expected_id:
            print(f"✓ Correctly parsed URL: {url} -> {result}")
        else:
            print(f"✗ Failed to parse URL: {url} -> got {result}, expected {expected_id}")


def test_markdown_conversion():
    """Test HTML to Markdown conversion."""
    print("\nTesting markdown conversion...")
    
    client = ConfluenceClient(
        base_url="https://example.confluence.com",
        token="test-token"
    )
    
    test_html = """
    <h1>Test Title</h1>
    <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
    <ul>
        <li>List item 1</li>
        <li>List item 2</li>
    </ul>
    """
    
    markdown = client._html_to_markdown(test_html)
    print("HTML to Markdown conversion:")
    print("Original HTML:", test_html)
    print("Converted Markdown:", markdown)
    
    if "# Test Title" in markdown and "**bold**" in markdown:
        print("✓ HTML to Markdown conversion working")
    else:
        print("✗ HTML to Markdown conversion failed")


if __name__ == '__main__':
    print("Running Confluence Markdown Tool Tests")
    print("=" * 50)
    
    test_client_initialization()
    test_url_parsing()
    test_markdown_conversion()
    
    print("\n" + "=" * 50)
    print("Tests completed!")