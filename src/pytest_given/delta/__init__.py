"""The delta report: what changed in a suite's scenarios and glossary between
two reports.

Imports `model/`, `markdown/` and `git/`. It runs no pytest.
"""

from .build import DeltaInputs, build_delta
from .check import check_schema_versions, version_warnings
from .renames import read_rename_log
from .revs import revs_outside_range

__all__ = [
    'DeltaInputs',
    'build_delta',
    'check_schema_versions',
    'read_rename_log',
    'revs_outside_range',
    'version_warnings',
]
