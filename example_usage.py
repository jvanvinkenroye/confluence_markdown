#!/usr/bin/env python3
"""
Example usage of the Confluence Markdown Tool
"""

from confluence_markdown_tool import ConfluenceClient


def example_download_page():
    """Example: Download a page as markdown."""
    print("Example 1: Download page as markdown")
    print("-" * 40)
    
    # Initialize client with Personal Access Token
    client = ConfluenceClient(
        base_url="https://your-confluence.company.com",
        token="your-personal-access-token"
    )
    
    # Or with username/password (API token)
    # client = ConfluenceClient(
    #     base_url="https://your-confluence.company.com",
    #     username="your-username",
    #     password="your-api-token"
    # )
    
    page_url = "https://your-confluence.company.com/pages/viewpage.action?pageId=123456"
    
    try:
        # Download and save to file
        markdown_content = client.download_as_markdown(page_url, "downloaded_page.md")
        print("Page downloaded successfully!")
        
        # Or just get the markdown content
        # markdown_content = client.download_as_markdown(page_url)
        # print(markdown_content)
        
    except Exception as e:
        print(f"Error downloading page: {e}")


def example_read_page():
    """Example: Read page content and metadata."""
    print("\nExample 2: Read page content")
    print("-" * 40)
    
    client = ConfluenceClient(
        base_url="https://your-confluence.company.com",
        token="your-personal-access-token"
    )
    
    page_url = "https://your-confluence.company.com/pages/viewpage.action?pageId=123456"
    
    try:
        page_info = client.read_page_content(page_url)
        
        print(f"Title: {page_info['title']}")
        print(f"Space: {page_info['space']} ({page_info['space_key']})")
        print(f"Version: {page_info['version']}")
        print(f"URL: {page_info['url']}")
        print(f"Content length: {len(page_info['markdown_content'])} characters")
        
    except Exception as e:
        print(f"Error reading page: {e}")


def example_add_content():
    """Example: Add content to an existing page."""
    print("\nExample 3: Add content to page")
    print("-" * 40)
    
    client = ConfluenceClient(
        base_url="https://your-confluence.company.com",
        token="your-personal-access-token"
    )
    
    page_url = "https://your-confluence.company.com/pages/viewpage.action?pageId=123456"
    
    # Markdown content to add
    new_content = """
## Updated Section

This content was added programmatically using the Confluence Markdown Tool.

- **Date**: {date}
- **Status**: Updated automatically
- **Note**: This is markdown that will be converted to HTML
"""
    
    try:
        # Add content (append by default)
        result = client.add_content_to_page(
            page_url, 
            new_content,
            append=True,  # Set to False to prepend
            content_type='markdown'
        )
        
        print(f"Content added successfully!")
        print(f"New version number: {result['version']['number']}")
        
    except Exception as e:
        print(f"Error adding content: {e}")


def cli_examples():
    """Show CLI usage examples."""
    print("\nCLI Usage Examples:")
    print("=" * 50)
    
    examples = [
        {
            "title": "Download page as markdown",
            "command": "python confluence_markdown_tool.py --base-url https://confluence.company.com --token YOUR_TOKEN --output page.md https://confluence.company.com/pages/viewpage.action?pageId=123456"
        },
        {
            "title": "Download with username/password",
            "command": "python confluence_markdown_tool.py --base-url https://confluence.company.com --username your-user --password your-token --output page.md https://confluence.company.com/pages/viewpage.action?pageId=123456"
        },
        {
            "title": "Read page content (no download)",
            "command": "python confluence_markdown_tool.py --base-url https://confluence.company.com --token YOUR_TOKEN --action read https://confluence.company.com/pages/viewpage.action?pageId=123456"
        },
        {
            "title": "Add markdown content to page",
            "command": 'python confluence_markdown_tool.py --base-url https://confluence.company.com --token YOUR_TOKEN --action add --content "## New Section\\nThis is new content" https://confluence.company.com/pages/viewpage.action?pageId=123456'
        },
        {
            "title": "Add HTML content to page",
            "command": 'python confluence_markdown_tool.py --base-url https://confluence.company.com --token YOUR_TOKEN --action add --content "<h2>New Section</h2><p>This is HTML content</p>" --content-type html https://confluence.company.com/pages/viewpage.action?pageId=123456'
        },
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['title']}:")
        print(f"   {example['command']}")


if __name__ == '__main__':
    print("Confluence Markdown Tool - Usage Examples")
    print("=" * 50)
    
    # Note: These examples won't actually run without valid credentials
    # They are shown for demonstration purposes
    
    print("Note: Update the credentials and URLs before running these examples")
    print()
    
    # example_download_page()
    # example_read_page() 
    # example_add_content()
    
    cli_examples()