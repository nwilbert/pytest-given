"""Recording a run: the authoring surface, and the machinery behind it.

Two audiences share this namespace. The authoring surface — `given` / `when` /
`then` / `when_then` / `attach`, `@scenario`, `story` / `activity` / `path`,
`Glossary` / `FileGlossary` / `Template` — is re-exported from the package
root and is what a test author writes. Everything else is the seam `plugin/`
drives it through, public only because a sibling subpackage may import solely
from a subpackage root. `__all__` stays sorted rather than grouped, so this
note is where the two are told apart.
"""

from .collector import (
    Collector,
    FixtureRecording,
    get_active_collector,
    set_active_collector,
)
from .discovery import resolve_glossary
from .file_glossary import FileGlossary
from .glossary import Glossary
from .kind_inference import infer_glossary_kinds
from .process_state import (
    begin_capture_session,
    capture_snapshot,
    restore_capture_state,
)
from .scenario import (
    ScenarioDecorator,
    annotated_given_descriptors,
    scenario,
    scenario_marker,
)
from .source import item_source
from .steps import (
    StepDescriptor,
    attach,
    given,
    step_descriptor,
    then,
    when,
    when_then,
)
from .story import (
    activity,
    path,
    story,
)
from .template import (
    Template,
    resolved_placeholder_part,
    try_term_ref,
)
from .traceback import is_internal_path, parse_short_repr

__all__ = [
    'Collector',
    'FileGlossary',
    'FixtureRecording',
    'Glossary',
    'ScenarioDecorator',
    'StepDescriptor',
    'Template',
    'activity',
    'annotated_given_descriptors',
    'attach',
    'begin_capture_session',
    'capture_snapshot',
    'get_active_collector',
    'given',
    'infer_glossary_kinds',
    'is_internal_path',
    'item_source',
    'parse_short_repr',
    'path',
    'resolve_glossary',
    'resolved_placeholder_part',
    'restore_capture_state',
    'scenario',
    'scenario_marker',
    'set_active_collector',
    'step_descriptor',
    'story',
    'then',
    'try_term_ref',
    'when',
    'when_then',
]
