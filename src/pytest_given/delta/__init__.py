"""The delta report: what changed in a suite's scenarios and glossary between
two reports, and the JSON schema `report/` renders it from.

Imports `model/`, `markdown/` and `git/`. It runs no pytest.
"""

from .compare import compare_reports
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
    'change_counts',
    'compare_reports',
    'delta_from_dict',
    'delta_to_dict',
    'on_side',
    'other_side',
    'terms_read_the_same',
]
