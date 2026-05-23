from __future__ import annotations


class PytestGivenError(RuntimeError):
    """Raised when given/when/then/attach is called in an invalid lifecycle context."""
