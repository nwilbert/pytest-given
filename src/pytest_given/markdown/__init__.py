"""Reading Markdown: a document's block structure and tables, placed in its
source, and the inline subset titles, steps and definitions are written in.

The leaf below `model/`: it imports nothing else from the package, so every
package reads Markdown by the same rules.
"""

from .blocks import (
    HtmlBlock,
    SourceLine,
    Span,
    Table,
    TableCell,
    TableRow,
    TextRun,
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
    plain_html_text,
    plain_link_text,
)
from .spans import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    located_spans,
    read_spans,
)

__all__ = [
    'ASCII_PUNCTUATION',
    'LINE_BREAK',
    'CodeSpan',
    'EmphasisSpan',
    'HtmlBlock',
    'InlineSpan',
    'PlainSpan',
    'SourceLine',
    'Span',
    'Table',
    'TableCell',
    'TableRow',
    'TextRun',
    'code_span_at',
    'fold_whitespace',
    'html_blocks',
    'located_spans',
    'plain_html_text',
    'plain_link_text',
    'read_spans',
    'table_cell_spans',
    'tables',
    'text_runs',
]
