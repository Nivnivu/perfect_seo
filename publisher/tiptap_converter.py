"""
Convert markdown text to TipTap JSON format matching the blog-poster app schema.

TipTap JSON structure:
{
  "type": "body",
  "children": [
    {"type": "h2", "attributes": {"dir": "rtl", "data-uid": "_xxx"}, "children": [{"type": "text", "content": "..."}]},
    {"type": "p", "attributes": {"dir": "rtl", "data-uid": "_yyy"}, "children": [{"type": "text", "content": "..."}]},
    ...
  ]
}
"""
import re
import json
import uuid


def _uid():
    return f"_{uuid.uuid4().hex[:10]}"


def _parse_links_only(text):
    """Parse markdown links within text (used inside bold/italic nodes)."""
    children = []
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    last_end = 0

    for match in re.finditer(link_pattern, text):
        start = match.start()
        if start > last_end:
            children.append({"type": "text", "content": text[last_end:start]})

        children.append({
            "type": "a",
            "attributes": {"href": match.group(2)},
            "children": [{"type": "text", "content": match.group(1)}],
        })
        last_end = match.end()

    remaining = text[last_end:]
    if remaining:
        children.append({"type": "text", "content": remaining})

    if not children:
        children = [{"type": "text", "content": text}]

    return children


def _parse_inline(text):
    """Parse inline markdown (links, bold, italic) into TipTap child nodes.

    Handles: [text](url), **[text](url)**, **bold**, *italic*, ***bold-italic***
    Links become proper {"type": "a"} nodes, not raw markdown in text.
    """
    children = []

    # Combined pattern — order matters (most specific first):
    #  1) ***bold-italic***
    #  2) **[link-text](url)**   (bold-wrapped link)
    #  3) **bold**               (may contain links inside)
    #  4) *italic*
    #  5) [link-text](url)       (plain link)
    pattern = re.compile(
        r'\*\*\*(.+?)\*\*\*'
        r'|\*\*\[([^\]]+)\]\(([^)]+)\)\*\*'
        r'|\*\*(.+?)\*\*'
        r'|\*(.+?)\*'
        r'|\[([^\]]+)\]\(([^)]+)\)'
    )

    last_end = 0
    for match in re.finditer(pattern, text):
        start = match.start()
        if start > last_end:
            children.append({"type": "text", "content": text[last_end:start]})

        if match.group(1):  # ***bold-italic***
            children.append({
                "type": "strong",
                "children": [{"type": "em", "children": [{"type": "text", "content": match.group(1)}]}],
            })
        elif match.group(2):  # **[link](url)**
            children.append({
                "type": "strong",
                "children": [{
                    "type": "a",
                    "attributes": {"href": match.group(3)},
                    "children": [{"type": "text", "content": match.group(2)}],
                }],
            })
        elif match.group(4):  # **bold** (parse links inside bold content)
            children.append({
                "type": "strong",
                "children": _parse_links_only(match.group(4)),
            })
        elif match.group(5):  # *italic* (parse links inside italic content)
            children.append({
                "type": "em",
                "children": _parse_links_only(match.group(5)),
            })
        elif match.group(6):  # [link](url)
            children.append({
                "type": "a",
                "attributes": {"href": match.group(7)},
                "children": [{"type": "text", "content": match.group(6)}],
            })

        last_end = match.end()

    # Add remaining plain text
    remaining = text[last_end:]
    if remaining:
        children.append({"type": "text", "content": remaining})

    # If no inline formatting found, return single text node
    if not children:
        children = [{"type": "text", "content": text}]

    return children


def _make_node(node_type, text, attrs=None):
    """Create a TipTap node with RTL attributes."""
    attributes = {"dir": "rtl", "data-uid": _uid()}
    if attrs:
        attributes.update(attrs)

    return {
        "type": node_type,
        "attributes": attributes,
        "children": _parse_inline(text),
    }


def markdown_to_tiptap(markdown_text):
    """
    Convert markdown text to TipTap JSON format.
    Returns a JSON string matching the blog-poster schema.
    """
    lines = markdown_text.split("\n")
    children = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Headings
        if line.startswith("### "):
            children.append(_make_node("h3", line[4:].strip()))
            i += 1
            continue
        if line.startswith("## "):
            children.append(_make_node("h2", line[3:].strip()))
            i += 1
            continue
        if line.startswith("# "):
            children.append(_make_node("h1", line[2:].strip()))
            i += 1
            continue

        # Unordered list (collect consecutive items)
        if re.match(r"^\s*[-*]\s+", line):
            list_items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i].rstrip()):
                item_text = re.sub(r"^\s*[-*]\s+", "", lines[i].rstrip())
                list_items.append({
                    "type": "li",
                    "attributes": {"data-uid": _uid()},
                    "children": [{"type": "p", "attributes": {"dir": "rtl"}, "children": _parse_inline(item_text)}],
                })
                i += 1
            children.append({
                "type": "ul",
                "attributes": {"data-uid": _uid()},
                "children": list_items,
            })
            continue

        # Ordered list (collect consecutive items)
        if re.match(r"^\s*\d+\.\s+", line):
            list_items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i].rstrip()):
                item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i].rstrip())
                list_items.append({
                    "type": "li",
                    "attributes": {"data-uid": _uid()},
                    "children": [{"type": "p", "attributes": {"dir": "rtl"}, "children": _parse_inline(item_text)}],
                })
                i += 1
            children.append({
                "type": "ol",
                "attributes": {"data-uid": _uid()},
                "children": list_items,
            })
            continue

        # Skip markdown horizontal rules
        if re.match(r"^-{3,}$", line.strip()) or re.match(r"^\*{3,}$", line.strip()):
            i += 1
            continue

        # Regular paragraph
        children.append(_make_node("p", line.strip()))
        i += 1

    tiptap_doc = {
        "type": "body",
        "children": children,
    }

    return json.dumps(tiptap_doc, ensure_ascii=False)


def extract_text_from_tiptap(content):
    """
    Extract plain text from a TipTap JSON object (staticPage format).
    Works with both blog-poster format (type/children/content) and
    standard TipTap format (type/content[]/text + marks).
    """
    if isinstance(content, str):
        return content

    texts = []

    def _walk(node):
        if isinstance(node, dict):
            # Standard TipTap text node
            if node.get("type") == "text" and "text" in node:
                texts.append(node["text"])
            # Blog-poster text node
            if node.get("type") == "text" and "content" in node:
                texts.append(node["content"])
            # Recurse into children / content arrays
            for key in ("children", "content"):
                if key in node and isinstance(node[key], list):
                    for child in node[key]:
                        _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(content)
    return "\n".join(texts)


def markdown_to_static_tiptap(markdown_text):
    """
    Convert markdown to TipTap JSON format matching the staticPage schema.
    Uses standard TipTap format: paragraph/heading with textAlign attrs,
    text nodes with 'text' field and optional 'marks'.
    Returns a dict (not JSON string).
    """
    lines = markdown_text.split("\n")
    content_nodes = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        # Headings
        heading_match = re.match(r'^(#{1,3})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            # Strip bold markers from heading text
            clean_text = re.sub(r'\*{1,3}', '', text).strip()
            content_nodes.append({
                "type": "heading",
                "attrs": {"textAlign": "right", "level": level},
                "content": [{"type": "text", "marks": [{"type": "bold"}], "text": clean_text}],
            })
            i += 1
            continue

        # Bullet list
        if re.match(r'^\s*[-*]\s+', line):
            list_items = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i].rstrip()):
                item_text = re.sub(r'^\s*[-*]\s+', '', lines[i].rstrip())
                list_items.append({
                    "type": "listItem",
                    "content": [{
                        "type": "paragraph",
                        "attrs": {"textAlign": None},
                        "content": _text_with_marks(item_text),
                    }],
                })
                i += 1
            content_nodes.append({"type": "bulletList", "content": list_items})
            continue

        # Ordered list
        if re.match(r'^\s*\d+\.\s+', line):
            list_items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i].rstrip()):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i].rstrip())
                list_items.append({
                    "type": "listItem",
                    "content": [{
                        "type": "paragraph",
                        "attrs": {"textAlign": None},
                        "content": _text_with_marks(item_text),
                    }],
                })
                i += 1
            content_nodes.append({"type": "orderedList", "content": list_items})
            continue

        # Skip horizontal rules
        if re.match(r'^-{3,}$', line.strip()) or re.match(r'^\*{3,}$', line.strip()):
            i += 1
            continue

        # Regular paragraph
        content_nodes.append({
            "type": "paragraph",
            "attrs": {"textAlign": "right"},
            "content": _text_with_marks(line.strip()),
        })
        i += 1

    return {"type": "doc", "content": content_nodes}


def _text_with_marks(text):
    """Convert inline markdown to standard TipTap text nodes with marks."""
    nodes = []
    pattern = re.compile(
        r'\*\*\*(.+?)\*\*\*'
        r'|\*\*(.+?)\*\*'
        r'|\*(.+?)\*'
        r'|\[([^\]]+)\]\(([^)]+)\)'
    )
    last_end = 0
    for match in re.finditer(pattern, text):
        start = match.start()
        if start > last_end:
            nodes.append({"type": "text", "text": text[last_end:start]})
        if match.group(1):  # ***bold-italic***
            nodes.append({"type": "text", "marks": [{"type": "bold"}, {"type": "italic"}], "text": match.group(1)})
        elif match.group(2):  # **bold**
            nodes.append({"type": "text", "marks": [{"type": "bold"}], "text": match.group(2)})
        elif match.group(3):  # *italic*
            nodes.append({"type": "text", "marks": [{"type": "italic"}], "text": match.group(3)})
        elif match.group(4):  # [link](url)
            nodes.append({"type": "text", "marks": [{"type": "link", "attrs": {"href": match.group(5)}}], "text": match.group(4)})
        last_end = match.end()
    remaining = text[last_end:]
    if remaining:
        nodes.append({"type": "text", "text": remaining})
    if not nodes:
        nodes = [{"type": "text", "text": text}]
    return nodes


def parse_gemini_output(gemini_text):
    """
    Parse the structured Gemini blog post output into components.
    Expected format:
        TITLE: ...
        META_DESCRIPTION: ...
        SLUG: ...
        ---
        [blog body in markdown]
        ---
        IMAGE_SUGGESTIONS: ...
        INTERNAL_LINK_SUGGESTIONS: ...

    Returns dict with: title, subtitle, slug, body_markdown, body_tiptap
    """
    result = {
        "title": "",
        "subtitle": "",
        "slug": "",
        "body_markdown": "",
        "body_tiptap": "",
    }

    lines = gemini_text.strip().split("\n")

    def _clean_field(text):
        """Strip markdown formatting artifacts from metadata fields."""
        text = re.sub(r"\*{1,3}", "", text)  # Remove *, **, ***
        return text.strip()

    # Extract header fields
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("TITLE:"):
            result["title"] = _clean_field(stripped[6:])
        elif stripped.startswith("META_DESCRIPTION:"):
            result["subtitle"] = _clean_field(stripped[17:])
        elif stripped.startswith("SLUG:"):
            result["slug"] = _clean_field(stripped[5:])
        elif stripped == "---":
            body_start = i + 1
            break

    # Find end of body (next --- or IMAGE_SUGGESTIONS or INTERNAL_LINK_SUGGESTIONS)
    body_end = len(lines)
    for i in range(body_start, len(lines)):
        stripped = lines[i].strip()
        if stripped == "---" or stripped.startswith("IMAGE_SUGGESTIONS:") or stripped.startswith("INTERNAL_LINK_SUGGESTIONS:"):
            body_end = i
            break

    # Extract body
    body_lines = lines[body_start:body_end]
    result["body_markdown"] = "\n".join(body_lines).strip()

    # Convert to TipTap JSON
    if result["body_markdown"]:
        result["body_tiptap"] = markdown_to_tiptap(result["body_markdown"])

    return result
