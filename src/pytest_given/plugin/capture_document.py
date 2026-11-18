"""The session capture's JSON document, apart from `session_capture` so that only
a pytest-xdist run builds its model.

Never written to disk: the same installation writes and reads it within one
run, so it carries no schema version.
"""

# No `__lazy_modules__`: the `BaseModel` subclass below imports Pydantic as this
# module loads.

from ..model import (
    CapturedScenario,
    Document,
    Glossary,
    JsonObject,
    NodeId,
    Story,
    dump_document,
    load_document,
)
from .session_capture import SessionCapture


def session_capture_to_dict(capture: SessionCapture) -> JsonObject:
    return dump_document(SessionCaptureDocument, capture)


def session_capture_from_dict(d: JsonObject) -> SessionCapture:
    return load_document(
        SessionCaptureDocument, SessionCapture, d, 'session capture', None
    )


class SessionCaptureDocument(Document):
    scenarios: list[CapturedScenario]
    collection_index: dict[NodeId, int]
    stories: list[Story]
    glossary: Glossary | None
