from collections.abc import Callable, Mapping
from dataclasses import dataclass
from string import Formatter, templatelib
from typing import Any

from pytest_given.errors import PytestGivenError

_CONVERSIONS: dict[str, Callable[[Any], str]] = {'s': str, 'r': repr, 'a': ascii}


@dataclass(frozen=True, kw_only=True)
class NarrationLiteral:
    value: str


@dataclass(frozen=True, kw_only=True)
class NarrationValue:
    """A t-string interpolation — value already known at construction time."""

    rendered: str
    expression: str
    format_spec: str = ''
    conversion: str | None = None


@dataclass(frozen=True, kw_only=True)
class NarrationPlaceholder:
    """A deferred placeholder — resolved at render time from a per-case mapping."""

    name: str
    format_spec: str = ''
    conversion: str | None = None


type NarrationPart = NarrationLiteral | NarrationValue | NarrationPlaceholder


class Template:
    """Deferred brace-style template. Same `{...}` syntax as f/t-strings.

    Supports bare identifiers only — `{name}`, `{name:spec}`, `{name!conv}`.
    Attribute access, indexing, and arbitrary expressions raise PytestGivenError
    at construction time.
    """

    def __init__(self, template: str) -> None:
        self.template = template
        formatter = Formatter()
        parts: list[NarrationPart] = []
        for literal, name, spec, conversion in formatter.parse(template):
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
                    resolved = mapping[name]
                    if conv is not None:
                        resolved = _CONVERSIONS[conv](resolved)
                    out.append(format(resolved, spec))
        return ''.join(out)

    def get_identifiers(self) -> list[str]:
        return [p.name for p in self.parts if isinstance(p, NarrationPlaceholder)]


def parse_tstring(
    tstring: templatelib.Template,
) -> tuple[str, list[NarrationPart]]:
    """Convert a t-string Template into (rendered text, structured parts).

    Iterates the t-string yielding str | Interpolation. Each interpolation
    becomes a NarrationValue carrying the rendered string plus the source
    expression and any conversion / format_spec — preserved so that the
    templatize step can convert matching expressions to NarrationPlaceholder.
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
                if conversion is not None:
                    value = _CONVERSIONS[conversion](value)
                rendered = format(value, format_spec)
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
