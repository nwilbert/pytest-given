"""The pure rules over `Narration` parts."""

from typing import Any, cast

import pytest

from pytest_given.model import narration_text


def test_narration_text_rejects_unknown_variant() -> None:
    # The exhaustive match guards against a NarrationPart variant being added
    # without a text branch — which would drop it from `text` silently, and
    # `text` is what the report's search box and a `jq` query read.
    with pytest.raises(AssertionError):
        narration_text([cast(Any, object())])
