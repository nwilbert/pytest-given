from collections.abc import Callable, Mapping
from dataclasses import dataclass
from string import Formatter
from typing import Any

from pytest_given.errors import PytestGivenError

_CONVERSIONS: dict[str, Callable[[Any], str]] = {'s': str, 'r': repr, 'a': ascii}


@dataclass(frozen=True, kw_only=True)
class TextLiteral:
    value: str


@dataclass(frozen=True, kw_only=True)
class TextValue:
    """A t-string interpolation — value already known at construction time."""

    rendered: str
    expression: str
    format_spec: str = ''
    conversion: str | None = None


@dataclass(frozen=True, kw_only=True)
class TextPlaceholder:
    """A deferred placeholder — resolved at render time from a per-case mapping."""

    name: str
    format_spec: str = ''
    conversion: str | None = None


type TextPart = TextLiteral | TextValue | TextPlaceholder


class Template:
    """Deferred brace-style template. Same `{...}` syntax as f/t-strings.

    Supports bare identifiers only — `{name}`, `{name:spec}`, `{name!conv}`.
    Attribute access, indexing, and arbitrary expressions raise PytestGivenError
    at construction time.
    """

    def __init__(self, template: str) -> None:
        self.template = template
        formatter = Formatter()
        parts: list[TextPart] = []
        for literal, name, spec, conversion in formatter.parse(template):
            if literal:
                parts.append(TextLiteral(value=literal))
            if name is not None:
                if not name.isidentifier():
                    raise PytestGivenError(
                        f'pytest_given.Template only supports bare identifiers '
                        f'as placeholders; got {name!r}. For attribute access '
                        f'or expressions, use a t-string in the test body '
                        f'(where the value is in scope).'
                    )
                parts.append(
                    TextPlaceholder(
                        name=name,
                        format_spec=spec or '',
                        conversion=conversion,
                    )
                )
        self.parts: list[TextPart] = parts

    def substitute(self, mapping: Mapping[str, Any]) -> str:
        out: list[str] = []
        for part in self.parts:
            match part:
                case TextLiteral(value=value):
                    out.append(value)
                case TextPlaceholder(name=name, format_spec=spec, conversion=conv):
                    if name not in mapping:
                        raise KeyError(name)
                    resolved = mapping[name]
                    if conv is not None:
                        resolved = _CONVERSIONS[conv](resolved)
                    out.append(format(resolved, spec))
        return ''.join(out)

    def get_identifiers(self) -> list[str]:
        return [p.name for p in self.parts if isinstance(p, TextPlaceholder)]
