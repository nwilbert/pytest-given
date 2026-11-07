"""The delta report: what changed in a suite's scenarios and glossary between
two reports.

Imports `model/`, `markdown/` and `git/`. It runs no pytest.
"""

from .build import DeltaInputs, DeltaResult, build_delta
from .chains import (
    Rewrites,
    rewrite_case_id,
    rewrite_identities,
    undo_case_merges,
)
from .check import check_schema_versions, version_warnings
from .renames import (
    DEFAULT_RENAMES_PATH,
    RenameEntry,
    RenameLog,
    parse_rename_log,
    read_rename_log,
)
from .revs import revs_outside_range

__all__ = [
    'DEFAULT_RENAMES_PATH',
    'DeltaInputs',
    'DeltaResult',
    'RenameEntry',
    'RenameLog',
    'Rewrites',
    'build_delta',
    'check_schema_versions',
    'parse_rename_log',
    'read_rename_log',
    'revs_outside_range',
    'rewrite_case_id',
    'rewrite_identities',
    'undo_case_merges',
    'version_warnings',
]
