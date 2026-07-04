"""Shared pytest-given self-documentation vocabulary.

The project's own ``GLOSSARY.md`` is the ubiquitous language of pytest-given's
bounded context. Loading it as a :class:`FileGlossary` lets the backend tests
narrate their behaviour in that vocabulary, so ``pytest --given-html`` renders a
living, filterable behavioural spec of the plugin itself.

Term handles are referenced as ``pg['Scenario']`` inside t-string steps. The
name ``pg`` (pytest-given) is deliberately distinct from the throwaway ``g``
Glossary fixtures/locals the unit tests build for their own domain-under-test.
"""

from pathlib import Path

from pytest_given import FileGlossary

_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / 'GLOSSARY.md'

pg = FileGlossary(_GLOSSARY_PATH)
