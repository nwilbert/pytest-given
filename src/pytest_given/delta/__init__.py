"""The delta report: what changed in a suite's scenarios and glossary between
two reports.

Imports `model/` and `markdown/` only. It runs no pytest and calls no git; the
entry points hand it what those would have told it.
"""

from .build import (
    DeltaInputs,
    DeltaResult,
    build_delta,
    comparable_title,
    is_per_case,
)
from .chains import (
    CaseMap,
    Rewrite,
    Rewrites,
    rewrite_case_id,
    rewrite_identities,
    undo_case_merges,
)
from .check import check_reports
from .identity import scenario_identity
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
    'DeltaInputs',
    'DeltaResult',
    'EntryTable',
    'RenameEntry',
    'RenameLog',
    'Rewrite',
    'Rewrites',
    'build_delta',
    'check_reports',
    'comparable_title',
    'is_per_case',
    'parse_rename_log',
    'read_rename_log',
    'rewrite_case_id',
    'rewrite_identities',
    'scenario_identity',
    'undo_case_merges',
]
