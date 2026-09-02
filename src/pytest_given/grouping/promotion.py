"""What the baseline walk is handed: the group it reads, the columns it writes.

Its own module because `templatize` and `attachments` are the two halves of
that walk and both take it, while neither takes the other.
"""

from dataclasses import dataclass

from .columns import ColumnBuilder
from .context import Group


@dataclass(frozen=True)
class Promotion:
    group: Group
    columns: ColumnBuilder
