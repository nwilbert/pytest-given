"""The delta report: what changed in a suite's scenarios and glossary between
two reports.

Imports `model/` and `markdown/` only. It runs no pytest and calls no git; the
entry points hand it what those would have told it.
"""

from .chains import CaseMap, Rewrite, Rewrites, rewrite_case_id, rewrite_identities
from .renames import (
    DEFAULT_RENAMES_PATH,
    EntryTable,
    RenameEntry,
    RenameLog,
    parse_rename_log,
    read_rename_log,
)

__all__ = [
    'DEFAULT_RENAMES_PATH',
    'CaseMap',
    'EntryTable',
    'RenameEntry',
    'RenameLog',
    'Rewrite',
    'Rewrites',
    'parse_rename_log',
    'read_rename_log',
    'rewrite_case_id',
    'rewrite_identities',
]
