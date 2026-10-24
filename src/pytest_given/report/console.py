import io
import sys


def write_console_as_utf8() -> None:
    """Python 3.14 writes a piped stdout in the locale's code page — cp1252 on
    Windows, which has none of the report's glyphs. Python 3.15 makes UTF-8
    the default. A stream replaced by something other than a `TextIOWrapper`
    is left as it is."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding='utf-8', errors=stream.errors)
