"""The inline-Markdown emphasis grammar, shared by capture and report.

`capture/markdown_glossary.py` *strips* this markup from a glossary term cell
while `report/inline_markdown.py` *renders* it in a definition cell: a term
written ``**Guest**`` has to canonicalize to the same word its definition
renders bold, so the two must recognize exactly the same spans. Neither package
may import the other, so the pattern lives here in the leaf.

Only the pattern is shared: what a match *becomes* differs by caller, so each
keeps its own substitution function.
"""

import re

# Code span first, so a `*` inside `code` is not treated as emphasis. The group
# order is part of the contract every substitution function reads: code span,
# **bold**, __bold__, *italic*. Only paired markers match, so a lone underscore
# inside an identifier (`work_object`) is left untouched.
EMPHASIS = re.compile(r'`(.+?)`|\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*')
