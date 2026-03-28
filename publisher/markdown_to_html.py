"""Convert markdown text to HTML for non-MongoDB platforms (WordPress, Shopify, etc.)."""
import re


def markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown to HTML.
    Handles: headings, bold, italic, links, bullet lists, ordered lists, paragraphs.
    """
    if not markdown_text:
        return ""

    lines = markdown_text.split("\n")
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        # Headings
        if line.startswith("### "):
            html_parts.append(f"<h3>{_inline(line[4:].strip())}</h3>")
            i += 1
            continue
        if line.startswith("## "):
            html_parts.append(f"<h2>{_inline(line[3:].strip())}</h2>")
            i += 1
            continue
        if line.startswith("# "):
            html_parts.append(f"<h1>{_inline(line[2:].strip())}</h1>")
            i += 1
            continue

        # Unordered list
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i].rstrip()):
                item_text = re.sub(r"^\s*[-*]\s+", "", lines[i].rstrip())
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i].rstrip()):
                item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i].rstrip())
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            html_parts.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Skip horizontal rules
        if re.match(r"^-{3,}$", line.strip()) or re.match(r"^\*{3,}$", line.strip()):
            i += 1
            continue

        # Paragraph
        html_parts.append(f"<p>{_inline(line.strip())}</p>")
        i += 1

    return "\n".join(html_parts)


def _inline(text: str) -> str:
    """Convert inline markdown (bold, italic, links) to HTML."""
    # Bold-italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text
