from collections.abc import Mapping
from string import Formatter, templatelib
from typing import Any

from ..model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PytestGivenError,
)
from .draft import DraftActor, DraftVerb, DraftWorkObject
from .file_glossary import FileTermHandle, FileTermInstance
from .glossary import (
    Actor,
    ActorInstance,
    InflectedVerb,
    Verb,
    WorkObject,
    WorkObjectInstance,
)

_FORMATTER = Formatter()


def narration_from(value: str | Template | templatelib.Template) -> Narration:
    """Build a Narration from a plain string, a Template, or a t-string."""
    if isinstance(value, templatelib.Template):
        text, parts = parse_tstring(value)
        return Narration(text=text, parts=parts)
    if isinstance(value, Template):
        return Narration(text=value.template, parts=list(value.parts))
    return Narration(text=value)


class Template:
    """Deferred brace-style template. Same `{...}` syntax as f/t-strings.

    Supports bare identifiers only — `{name}`, `{name:spec}`, `{name!conv}`.
    Attribute access, indexing, and arbitrary expressions raise PytestGivenError
    at construction time.
    """

    def __init__(self, template: str) -> None:
        self.template = template
        parts: list[NarrationPart] = []
        for literal, name, spec, conversion in _FORMATTER.parse(template):
            if literal:
                parts.append(NarrationLiteral(value=literal))
            if name is not None:
                if not name.isidentifier():
                    raise PytestGivenError(
                        f'pytest_given.Template only supports bare identifiers '
                        f'as placeholders; got {name!r}. For attribute access '
                        f'or expressions, use a t-string in the test body '
                        f'(where the value is in scope).'
                    )
                parts.append(
                    NarrationPlaceholder(
                        name=name,
                        format_spec=spec or '',
                        conversion=conversion,
                    )
                )
        self.parts: list[NarrationPart] = parts

    def substitute(self, mapping: Mapping[str, Any]) -> str:
        out: list[str] = []
        for part in self.parts:
            match part:
                case NarrationLiteral(value=value):
                    out.append(value)
                case NarrationPlaceholder(name=name, format_spec=spec, conversion=conv):
                    if name not in mapping:
                        raise KeyError(name)
                    resolved = _FORMATTER.convert_field(mapping[name], conv)
                    out.append(format(resolved, spec))
        return ''.join(out)

    def get_identifiers(self) -> list[str]:
        return [p.name for p in self.parts if isinstance(p, NarrationPlaceholder)]


def parse_tstring(
    tstring: templatelib.Template,
) -> tuple[str, list[NarrationPart]]:
    """Convert a t-string Template into (rendered text, structured parts).

    Iterates the t-string yielding str | Interpolation. Each interpolation
    is inspected:
    - Draft handles raise PytestGivenError immediately.
    - Glossary handles (Actor, WorkObject, Verb, and their instances/inflections)
      become NarrationTermRef carrying term_id, display, and the source expression.
    - All other values become NarrationValue as before.
    """
    parts: list[NarrationPart] = []
    rendered_chunks: list[str] = []
    for chunk in tstring:
        match chunk:
            case str() as literal:
                if literal:
                    parts.append(NarrationLiteral(value=literal))
                    rendered_chunks.append(literal)
            case templatelib.Interpolation(
                value=value,
                expression=expression,
                conversion=conversion,
                format_spec=format_spec,
            ):
                _reject_draft_in_narration(value)
                term_ref = _try_term_ref(
                    value, expression, format_spec=format_spec, conversion=conversion
                )
                if term_ref is not None:
                    parts.append(term_ref)
                    rendered_chunks.append(term_ref.display)
                    continue
                rendered = format(
                    _FORMATTER.convert_field(value, conversion), format_spec
                )
                parts.append(
                    NarrationValue(
                        rendered=rendered,
                        expression=expression,
                        format_spec=format_spec,
                        conversion=conversion,
                    )
                )
                rendered_chunks.append(rendered)
    return ''.join(rendered_chunks), parts


def _reject_draft_in_narration(value: object) -> None:
    """Raise PytestGivenError if `value` is a draft handle.

    Drafts are story-side only; they must not appear in step narrations.
    """
    if not isinstance(value, (DraftActor, DraftWorkObject, DraftVerb)):
        return
    kind_to_method = {
        'actor': 'g.actor',
        'object': 'g.work_object',
        'verb': 'g.verb',
    }
    method = kind_to_method[value.kind]
    raise PytestGivenError(
        f'draft {value.kind} {value.text!r} cannot appear in a step narration; '
        f'drafts are story-side only. Either promote it to a glossary term '
        f'({method}({value.text!r})) and use the typed handle in the t-string, '
        f'or replace the interpolation with a plain string.'
    )


def _try_term_ref(
    value: object,
    expression: str = '',
    *,
    format_spec: str = '',
    conversion: str | None = None,
) -> NarrationTermRef | None:
    """Return a NarrationTermRef if `value` is a glossary handle, instance, or
    inflection — else None (fall back to NarrationValue).

    Glossary handles render as kind-coloured pills carrying the term's
    canonical or instance display; format_spec and conversion have no
    meaningful target on a pill, so a non-empty value is rejected at
    parse time rather than silently dropped.
    """
    match value:
        case Actor() | WorkObject() | Verb():
            display = value.canonical
            term_id = value.id
        case ActorInstance(actor=h, display=display):
            term_id = h.id
        case WorkObjectInstance(work_object=h, display=display):
            term_id = h.id
        case InflectedVerb(verb=h, display=display):
            term_id = h.id
        case FileTermHandle():
            display = value.canonical
            term_id = value.id
        case FileTermInstance(handle=handle, display=display):
            term_id = handle.id
        case _:
            return None
    if format_spec or conversion:
        suffix = f':{format_spec}' if format_spec else ''
        conv = f'!{conversion}' if conversion else ''
        raise PytestGivenError(
            f'glossary term interpolation {{{expression}{conv}{suffix}}} '
            f'cannot carry a format spec or conversion — glossary handles '
            f'render as kind pills with a fixed display ({display!r}). '
            f'Drop the spec, or interpolate the underlying value separately.'
        )
    return NarrationTermRef(term_id=term_id, display=display, expression=expression)
