"""The `window.__REPORT_DATA__` payload of a rendered report, decoded.

Shared ground for the unit tests that assert on what the HTML carries and
for the CLI integration tests that assert on what it wrote: the blob is a
`JSON.parse("…")` call, so every quote in it is escaped twice and a substring
match would pin the encoding rather than the data.
"""

import json


def embedded_app_data(content: str) -> dict:
    """The `window.__REPORT_DATA__` payload, decoded.

    Asserting on the parsed value rather than on the emitted text keeps the
    assertions data-shaped: they say what the page carries, not how the
    serializer spelled it.
    """
    start = content.index('window.__REPORT_DATA__ = JSON.parse(') + len(
        'window.__REPORT_DATA__ = JSON.parse('
    )
    end = content.index(');\n', start)
    return json.loads(json.loads(content[start:end]))
