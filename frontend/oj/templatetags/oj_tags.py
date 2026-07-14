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
