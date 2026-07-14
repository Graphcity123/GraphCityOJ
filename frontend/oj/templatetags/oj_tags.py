"""Custom template tags for GCOJ.

markdown — renders Markdown to HTML (like graphcity_blog's blog_tags.py).
"""
from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='markdown')
def render_markdown(text: str) -> str:
    """Render Markdown text to HTML with syntax highlighting.

    Uses the same extensions as graphcity_blog:
    - fenced_code: ```python code blocks
    - codehilite: syntax highlighting via Pygments
    - tables: GitHub-style tables
    - toc: table of contents
    """
    import markdown as md

    if not text:
        return ""

    # Strip custom directives like ::cute-table{...}
    import re as _re
    text = _re.sub(r"::cute-table\{[^}]*\}", "", text)

    html = md.markdown(
        text,
        extensions=[
            'fenced_code',
            'codehilite',
            'tables',
            'toc',
            'attr_list',
            'md_in_html',
        ],
        extension_configs={
            'codehilite': {
                'css_class': 'highlight',
                'guess_lang': True,
            },
        },
    )

    # Post-process: merge ^ cells into rowspan
    html = _merge_table_cells(html)

    return mark_safe(html)


@register.filter(name='highlight_code')
def highlight_code(code: str, language: str = "python") -> str:
    """Syntax-highlight code using Pygments. Language defaults to python."""
    if not code:
        return ""
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_by_name
        lexer = get_lexer_by_name(language, stripall=True)
    except Exception:
        from pygments.lexers import PythonLexer
        lexer = PythonLexer()
    formatter = HtmlFormatter(cssclass="highlight", style="monokai")
    result = highlight(code, lexer, formatter)
    return mark_safe(result)


@register.filter(name='first_fail')
def first_fail(details: list) -> str:
    """Return the first non-AC result from details, or empty string."""
    if not details:
        return ""
    for tc in details:
        if isinstance(tc, dict) and tc.get("result", "AC") != "AC":
            return tc["result"]
    return ""


@register.filter(name='range_n')
def range_n(value: int) -> range:
    """Return a range from 1 to value (inclusive)."""
    try:
        return range(1, int(value) + 1)
    except (ValueError, TypeError):
        return range(0)


RESULT_NAMES = {
    "AC": "Accepted", "WA": "Wrong Answer",
    "TLE": "Time Limit Exceeded", "MLE": "Memory Limit Exceeded",
    "RE": "Runtime Error", "CE": "Compile Error",
}


@register.filter(name='result_name')
def result_name(code: str) -> str:
    """Map short result code to full name."""
    return RESULT_NAMES.get(code, code)


@register.filter(name='banner_class')
def banner_class(details: list) -> str:
    """Return CSS class for the result banner based on first failure."""
    fail = first_fail(details)
    if not fail:
        return "result-ac"
    suffix = fail.lower()
    if suffix in ("tle", "mle", "re", "ce"):
        return f"result-partial-{suffix}"
    return "result-partial"


def _merge_table_cells(html: str) -> str:
    """Post-process HTML tables: convert ^ cells into rowspan."""
    import re

    def _merge_table(table_html: str) -> str:
        rows = re.findall(r"<tr>(.*?)</tr>", table_html, re.DOTALL)
        if not rows:
            return table_html

        # Parse each row's cells
        parsed: list[list[str]] = []
        for row in rows:
            cells = re.findall(r"<(t[dh])(.*?)>(.*?)</t[dh]>", row, re.DOTALL)
            parsed.append(cells)

        num_cols = max((len(r) for r in parsed), default=0)
        # Track how many rows to skip per column (rowspan in progress)
        rowspan_remaining = [0] * num_cols

        new_rows = []
        for ri, cells in enumerate(parsed):
            new_cells: list[str] = []
            col_idx = 0
            for tag, attrs, content in cells:
                # Skip columns consumed by ongoing rowspan
                while col_idx < num_cols and rowspan_remaining[col_idx] > 0:
                    rowspan_remaining[col_idx] -= 1
                    col_idx += 1
                if col_idx >= num_cols:
                    break

                stripped = content.strip()
                if stripped == "^":
                    # Find above cell to merge with
                    rowspan_remaining[col_idx] += 0  # mark for counting
                    # Count consecutive ^ below this one
                    span = 1
                    for r2 in range(ri + 1, len(parsed)):
                        if col_idx < len(parsed[r2]):
                            below = parsed[r2][col_idx][2].strip() if col_idx < len(parsed[r2]) else ""
                            if below == "^":
                                span += 1
                                # Mark this future row as consumed
                                pass
                            else:
                                break
                    # Actually, we need to modify the cell ABOVE, not here.
                    # For rowspan implementation, we'd need to go back and edit
                    # the first occurrence. This is complex in regex.
                    # Simpler approach: expand values first, then detect dupes.
                    if ri > 0 and col_idx < len(parsed[ri - 1]):
                        prev_content = parsed[ri - 1][col_idx][2]
                        new_cells.append(f"<{tag}{attrs}>{prev_content}</{tag}>")
                        col_idx += 1
                        continue
                    new_cells.append(f"<{tag}{attrs}>^</{tag}>")
                else:
                    new_cells.append(f"<{tag}{attrs}>{content}</{tag}>")
                col_idx += 1

            new_rows.append("<tr>" + "".join(new_cells) + "</tr>")

        # Actually do rowspan properly: scan columns, find ^ sequences
        final_cells = [[f"<{tag}{attrs}>{content}</{tag}>"
                        for tag, attrs, content in row]
                       for row in parsed]

        for ci in range(num_cols):
            ri = 0
            while ri < len(final_cells):
                if ci < len(final_cells[ri]):
                    tag_match = re.match(r"<(t[dh])", final_cells[ri][ci])
                    content_match = re.search(r">(.*?)</t[dh]>", final_cells[ri][ci])
                    if content_match and content_match.group(1).strip() == "^":
                        # Found a ^ cell, now count how many consecutive ^ below
                        span = 1
                        for r2 in range(ri + 1, len(final_cells)):
                            if ci < len(final_cells[r2]):
                                c2 = re.search(r">(.*?)</t[dh]>", final_cells[r2][ci])
                                if c2 and c2.group(1).strip() == "^":
                                    span += 1
                                else:
                                    break
                        # Copy value from cell above
                        if ri > 0 and ci < len(final_cells[ri - 1]):
                            above = final_cells[ri - 1][ci]
                            # Add rowspan to the first cell in the sequence
                            # Actually, the merge starts at ri-1 (the cell with real value)
                            base = final_cells[ri - 1][ci]
                            base = re.sub(r"<(t[dh])", r'<\1 rowspan="{}"'.format(span + 1), base)
                            final_cells[ri - 1][ci] = base
                            # Remove the ^ cells in this span
                            for r2 in range(ri, ri + span):
                                if ci < len(final_cells[r2]):
                                    final_cells[r2][ci] = ""
                        ri += span
                        continue
                ri += 1

        # Rebuild rows, removing empty cells
        rebuilt = []
        for row_cells in final_cells:
            non_empty = [c for c in row_cells if c]
            if non_empty:
                rebuilt.append("<tr>" + "".join(non_empty) + "</tr>")

        return "<table>" + "".join(rebuilt) + "</table>"

    # Find and process all tables
    tables = re.findall(r"<table>.*?</table>", html, re.DOTALL)
    for t in tables:
        merged = _merge_table(t)
        html = html.replace(t, merged)
    return html
