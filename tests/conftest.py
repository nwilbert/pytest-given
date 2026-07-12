# Expose the pytest-given FileGlossary at conftest module level so the plugin
# discovers it and renders the Glossary tab for the self-documenting scenarios.
from tests.ubiquitous_language import pg  # noqa: F401
