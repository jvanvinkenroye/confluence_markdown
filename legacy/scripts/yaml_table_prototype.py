#!/usr/bin/env python3
"""Prototype: Convert markdown tables to/from YAML for easier editing."""
import re
import yaml
from typing import List, Dict, Any, Tuple


def parse_markdown_table(md_text: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Parse a markdown table into headers and rows.

    Returns:
        Tuple of (headers list, list of row dicts)
    """
    lines = md_text.strip().split('\n')

    # Find table lines (start with |)
    table_lines = [l for l in lines if l.strip().startswith('|')]

    if len(table_lines) < 2:
        return [], []

    # Parse header
    header_line = table_lines[0]
    headers = [cell.strip() for cell in header_line.split('|')[1:-1]]

    # Skip separator line (second line)
    # Parse data rows
    rows = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                row_dict[header] = cells[i]
            else:
                row_dict[header] = ""
        rows.append(row_dict)

    return headers, rows


def table_to_yaml(headers: List[str], rows: List[Dict[str, str]]) -> str:
    """Convert table data to YAML format."""
    data = {
        "_headers": headers,  # Preserve column order
        "rows": rows
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def yaml_to_table(yaml_text: str) -> str:
    """Convert YAML back to markdown table."""
    data = yaml.safe_load(yaml_text)

    headers = data.get("_headers", [])
    rows = data.get("rows", [])

    if not headers:
        if rows:
            # Infer headers from first row
            headers = list(rows[0].keys())
        else:
            return ""

    # Calculate column widths
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            val = str(row.get(h, ""))
            widths[h] = max(widths[h], len(val))

    # Build table
    lines = []

    # Header row
    header_cells = [h.ljust(widths[h]) for h in headers]
    lines.append("| " + " | ".join(header_cells) + " |")

    # Separator row
    sep_cells = ["-" * widths[h] for h in headers]
    lines.append("| " + " | ".join(sep_cells) + " |")

    # Data rows
    for row in rows:
        cells = [str(row.get(h, "")).ljust(widths[h]) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def find_and_convert_tables(md_content: str) -> str:
    """Find markdown tables in content and convert them to YAML blocks."""
    lines = md_content.split('\n')
    result = []
    i = 0
    table_num = 1

    while i < len(lines):
        line = lines[i]

        # Check if this is the start of a table
        if line.strip().startswith('|') and '|' in line[1:]:
            # Collect all table lines
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1

            # Convert to YAML
            headers, rows = parse_markdown_table('\n'.join(table_lines))
            if headers and rows:
                yaml_content = table_to_yaml(headers, rows)
                result.append(f"```yaml table-{table_num}")
                result.append(yaml_content.rstrip())
                result.append("```")
                table_num += 1
            else:
                # Not a valid table, keep original
                result.extend(table_lines)
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def convert_yaml_blocks_to_tables(content: str) -> str:
    """Convert YAML table blocks back to markdown tables."""
    # Match ```yaml table-N ... ```
    pattern = r'```yaml table-\d+\n(.*?)```'

    def replace_yaml_block(match):
        yaml_content = match.group(1)
        return yaml_to_table(yaml_content)

    return re.sub(pattern, replace_yaml_block, content, flags=re.DOTALL)


# Test the prototype
if __name__ == "__main__":
    # Sample markdown table
    sample_md = """# Test Document

Some text before the table.

| Name       | Age | City      | Occupation     |
|------------|-----|-----------|----------------|
| Alice      | 30  | New York  | Engineer       |
| Bob        | 25  | London    | Designer       |
| Charlie    | 35  | Paris     | Manager        |
| Diana      | 28  | Berlin    | Analyst        |

Some text after the table.

Another table:

| Server     | Status  | CPU | Memory |
|------------|---------|-----|--------|
| prod-01    | running | 45% | 2.1GB  |
| prod-02    | stopped | 0%  | 0GB    |
| staging    | running | 12% | 512MB  |
"""

    print("=" * 60)
    print("ORIGINAL MARKDOWN:")
    print("=" * 60)
    print(sample_md)

    print("\n" + "=" * 60)
    print("CONVERTED TO YAML BLOCKS:")
    print("=" * 60)
    yaml_version = find_and_convert_tables(sample_md)
    print(yaml_version)

    print("\n" + "=" * 60)
    print("CONVERTED BACK TO MARKDOWN:")
    print("=" * 60)
    md_restored = convert_yaml_blocks_to_tables(yaml_version)
    print(md_restored)

    print("\n" + "=" * 60)
    print("COMPARISON:")
    print("=" * 60)
    # Compare tables (ignoring whitespace differences)
    original_tables = [l for l in sample_md.split('\n') if l.strip().startswith('|')]
    restored_tables = [l for l in md_restored.split('\n') if l.strip().startswith('|')]
    print(f"Original table lines: {len(original_tables)}")
    print(f"Restored table lines: {len(restored_tables)}")
