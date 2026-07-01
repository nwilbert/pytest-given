"""Shared pytest-given self-documentation vocabulary.

The project's own ``GLOSSARY.md`` is the ubiquitous language of pytest-given's
bounded context. Loading it as a :class:`FileGlossary` lets the backend tests
narrate their behaviour in that vocabulary, so ``pytest --given-html`` renders a
living, filterable behavioural spec of the plugin itself.

Term handles are referenced as ``pg['Scenario']`` inside t-string steps. The
name ``pg`` (pytest-given) is deliberately distinct from the throwaway ``g``
Glossary fixtures/locals the unit tests build for their own domain-under-test.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from pytest_given import FileGlossary, then, when

_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / 'GLOSSARY.md'

pg = FileGlossary(_GLOSSARY_PATH)


@contextmanager
def then_raises(
    text: str, exception: type[BaseException], *, match: str | None = None
) -> Iterator[None]:
    """A `then` step whose body is expected to raise, so a validation scenario
    stays a single narration context manager instead of a nested one."""
    with then(text), pytest.raises(exception, match=match):
        yield


@contextmanager
def when_raises(
    text: str, exception: type[BaseException], *, match: str | None = None
) -> Iterator[pytest.ExceptionInfo[BaseException]]:
    """A `when` step whose body raises; yields the captured ExceptionInfo so a
    following `then` step can assert on the raised message."""
    with when(text), pytest.raises(exception, match=match) as excinfo:
        yield excinfo
