"""A citation's link text, written so it renders as the title it stands for."""

from ..model import Narration
from .markdown_writer import literal_markdown, narration_markdown, one_line


def link_text(title: Narration | str, *, in_table_row: bool = False) -> str:
    """A citation's link text: a scenario title as the Markdown report writes
    it, a tag or story title literal."""
    if isinstance(title, str):
        return literal_markdown(one_line(title))
    return narration_markdown(title, in_table_row=in_table_row)
