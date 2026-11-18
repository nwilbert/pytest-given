"""The delta report: what changed in a suite's scenarios and glossary between
two reports, and the JSON schema `report/` renders it from.

Imports `model/`, `markdown/` and `git/`. It runs no pytest.
"""

from .build import DeltaInputs, build_delta
from .check import check_schema_versions, version_warnings
from .renames import read_rename_log
from .revs import revs_outside_range
from .schema import (
    CHANGED_PARTS,
    SIDE_MARK,
    AttachmentChange,
    AttachmentDelta,
    CasePair,
    Change,
    DeltaData,
    DeltaSide,
    DiffSegment,
    LineChange,
    LineDelta,
    Mark,
    ParameterDelta,
    ScenarioDelta,
    Side,
    StepChange,
    StepDelta,
    TermDelta,
    TermFacts,
    TextSegment,
    change_counts,
    on_side,
    other_side,
    terms_read_the_same,
)
from .serde import delta_from_dict, delta_to_dict

__all__ = [
    'CHANGED_PARTS',
    'SIDE_MARK',
    'AttachmentChange',
    'AttachmentDelta',
    'CasePair',
    'Change',
    'DeltaData',
    'DeltaInputs',
    'DeltaSide',
    'DiffSegment',
    'LineChange',
    'LineDelta',
    'Mark',
    'ParameterDelta',
    'ScenarioDelta',
    'Side',
    'StepChange',
    'StepDelta',
    'TermDelta',
    'TermFacts',
    'TextSegment',
    'build_delta',
    'change_counts',
    'check_schema_versions',
    'delta_from_dict',
    'delta_to_dict',
    'on_side',
    'other_side',
    'read_rename_log',
    'revs_outside_range',
    'terms_read_the_same',
    'version_warnings',
]
