"""`pytest-given citations check` and `update`: the report links in a set of
Markdown documents, held to a JSON report.

What each citation should say comes from `report`, which also writes it into
the HTML copy buttons; this package reads documents and edits them.
"""

from .check import (
    CitationFinding,
    CitationsResult,
    check_citations,
    markdown_documents,
)

__all__ = [
    'CitationFinding',
    'CitationsResult',
    'check_citations',
    'markdown_documents',
]
