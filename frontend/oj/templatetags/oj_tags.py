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
