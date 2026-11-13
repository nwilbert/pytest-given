"""Reading Markdown — a document's block structure and tables, placed in its
source, and the inline subset titles, steps and definitions are written in —
and writing that subset back as Markdown or rendering it as HTML.

The leaf below `model/`: it imports nothing else from the package, so every
package reads and writes Markdown by the same rules.
"""

from .blocks import (
    DocumentBlock,
    Heading,
    HtmlBlock,
    Paragraph,
    SourceLine,
    Span,
    Table,
    TableCell,
    TableRow,
    TextRun,
    document_blocks,
    html_blocks,
    table_cell_spans,
    tables,
    text_runs,
)
from .plain_text import (
    ASCII_PUNCTUATION,
    LINE_BREAK,
    code_span_at,
    fold_whitespace,
    one_line,
    plain_html_text,
    plain_link_text,
)
from .rendering import definition_html, definition_span_html, span_html
from .spans import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    located_spans,
    read_spans,
    span_text,
)
from .writing import (
    code_span_markdown,
    definition_markdown,
    literal_markdown,
    span_markdown,
)

__all__ = [
    'ASCII_PUNCTUATION',
    'LINE_BREAK',
    'CodeSpan',
    'DocumentBlock',
    'EmphasisSpan',
    'Heading',
    'HtmlBlock',
    'InlineSpan',
    'Paragraph',
    'PlainSpan',
    'SourceLine',
    'Span',
    'Table',
    'TableCell',
    'TableRow',
    'TextRun',
    'code_span_at',
    'code_span_markdown',
    'definition_html',
    'definition_markdown',
    'definition_span_html',
    'document_blocks',
    'fold_whitespace',
    'html_blocks',
    'literal_markdown',
    'located_spans',
    'one_line',
    'plain_html_text',
    'plain_link_text',
    'read_spans',
    'span_html',
    'span_markdown',
    'span_text',
    'table_cell_spans',
    'tables',
    'text_runs',
]
