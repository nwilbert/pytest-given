"""Draft placeholders — kind-tagged, no glossary registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..model import PytestGivenError


@dataclass(frozen=True)
class _DraftBase:
    kind: Literal['actor', 'object', 'verb']
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class DraftActor(_DraftBase):
    pass


@dataclass(frozen=True)
class DraftWorkObject(_DraftBase):
    pass


@dataclass(frozen=True)
class DraftVerb(_DraftBase):
    pass


def _check_text(text: str) -> str:
    if not text.strip():
        raise PytestGivenError(
            f'draft text is empty (got {text!r}); drafts must display '
            f'something. To leave an activity entirely vague, omit it.'
        )
    return text


class _DraftFactory:
    """Singleton exposing draft.actor(...), draft.work_object(...), draft.verb(...)."""

    def actor(self, text: str) -> DraftActor:
        return DraftActor(kind='actor', text=_check_text(text))

    def work_object(self, text: str) -> DraftWorkObject:
        return DraftWorkObject(kind='object', text=_check_text(text))

    def verb(self, text: str) -> DraftVerb:
        return DraftVerb(kind='verb', text=_check_text(text))


draft = _DraftFactory()
