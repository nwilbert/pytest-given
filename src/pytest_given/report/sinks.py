"""The sinks a run writes, rendered as a set and written as a set.

A run may be told to write any combination of JSON, HTML and Markdown, and
they have to agree with each other: a render that raises must not leave this
run's JSON beside the previous run's HTML, with nothing on either saying so.
So rendering and writing are separate steps — `render_sinks` does everything
that can fail and touches no file, `write_sinks` touches files and cannot fail
on content, and `discard_stale_sinks` removes a previous run's report that
would otherwise read as current.

`emit_sinks` is the whole transaction and the entry point callers want: the
sequencing *is* the guarantee, so keeping it here is what stops two callers
from each spelling it out and drifting apart.

Pytest-free like the rest of `report/`: the caller resolves its options into a
`SinkConfig`, which is also what lets `pytest-given report` reach the same code.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from ..model import PytestGivenError, report_from_dict
from .html_renderer import render_html_string
from .md_renderer import render_md

# Where a bare --given-json / --given-html / `pytest-given report` writes.
# Report-layout facts, so both entry points read them from here rather than
# each spelling their own.
DEFAULT_JSON_PATH = Path('given-report/report-data.json')
DEFAULT_HTML_PATH = Path('given-report/report.html')


@dataclass(frozen=True)
class SinkConfig:
    """Which sinks a run was told to write, and how to render them.

    `md_to_stdout` is its own flag rather than a sentinel path, so nothing
    downstream has to know that a bare `--given-md` means `-`.
    """

    json_path: Path | None = None
    html_path: Path | None = None
    md_path: Path | None = None
    md_to_stdout: bool = False
    source_link_template: str | None = None

    def __post_init__(self) -> None:
        _require_suffix('JSON', self.json_path, ('.json',))
        _require_suffix('HTML', self.html_path, ('.html', '.htm'))
        _require_suffix('Markdown', self.md_path, ('.md', '.markdown'))

    def file_paths(self) -> list[Path]:
        """The paths this run would write, in sink order. Only real files —
        Markdown bound for stdout has no path to overwrite or discard."""
        return [
            path
            for path in (self.json_path, self.html_path, self.md_path)
            if path is not None
        ]

    def writes_anything(self) -> bool:
        """Whether any sink is configured — `file_paths()` plus stdout Markdown,
        which writes no file but still has to be rendered."""
        return bool(self.file_paths()) or self.md_to_stdout


def _require_suffix(sink: str, path: Path | None, allowed: tuple[str, ...]) -> None:
    """Refuse a sink path that could not be a report file.

    These paths come from CLIs where a bare flag takes the next argument as
    its value, so a mis-ordered `--given-html tests/test_x.py` would aim the
    renderer at the author's own source — and `discard_stale_sinks` would then
    unlink it on a run that failed to render. The suffix is the cheapest thing
    that tells the two apart, and checking it turns silent data loss into a
    message before the suite runs.
    """
    if path is None or path.suffix.lower() in allowed:
        return
    raise PytestGivenError(
        f'The {sink} report path must end in {" or ".join(allowed)}, '
        f'but got {str(path)!r}.'
    )


class RenderedFile(NamedTuple):
    path: Path
    text: str


@dataclass(frozen=True)
class RenderedSinks:
    """Every configured sink rendered to text, before any of them is written."""

    files: list[RenderedFile] = field(default_factory=list)
    md_stdout: str | None = None


def emit_sinks(
    report_dict: dict[str, Any], config: SinkConfig, source: str | None = None
) -> RenderedSinks:
    """Render and write every configured sink, or leave none of them behind.

    Rendering can fail on content and writing can fail on the filesystem, and
    either failure has to take the whole set with it — including the *previous*
    run's report, which would otherwise sit there reading as current. Callers
    get that as one call rather than as a sequence they each reassemble.

    The discard notes are folded into the raised message, so a caller reports
    the failure by printing it.
    """
    try:
        rendered = render_sinks(report_dict, config, source)
        write_sinks(rendered)
    except (PytestGivenError, OSError) as error:
        raise PytestGivenError(sink_failure(error, config)) from error
    except Exception:
        # A renderer bug (an undefined template name, a missing color key) is
        # not a user error and keeps its own traceback — but it fails the same
        # way for the stale report on disk, which must still go.
        discard_stale_sinks(config)
        raise
    return rendered


def render_sinks(
    report_dict: dict[str, Any], config: SinkConfig, source: str | None = None
) -> RenderedSinks:
    """Render the configured sinks to text. Nothing here touches the filesystem.

    Takes only the serialized report and deserializes it here, so the JSON sink
    can write the dict verbatim while the other two render from a copy that has
    been through serde — every sink then shows exactly what the JSON can
    express, and no caller has to keep two views of one run in agreement.
    """
    report = report_from_dict(report_dict, source)
    files: list[RenderedFile] = []
    if config.json_path is not None:
        files.append(RenderedFile(config.json_path, json.dumps(report_dict, indent=2)))
    if config.html_path is not None:
        files.append(
            RenderedFile(
                config.html_path,
                render_html_string(
                    report, source_link_template=config.source_link_template
                ),
            )
        )
    md_stdout: str | None = None
    if config.md_path is not None or config.md_to_stdout:
        md = render_md(report)
        if config.md_to_stdout:
            md_stdout = md
        if config.md_path is not None:
            files.append(RenderedFile(config.md_path, md))
    return RenderedSinks(files=files, md_stdout=md_stdout)


def write_sinks(rendered: RenderedSinks) -> None:
    for path, text in rendered.files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def sink_failure(error: Exception, config: SinkConfig) -> str:
    """What to report when a run produces no report: the failure, and what
    discarding the stale sinks did.

    `emit_sinks` covers a failure inside itself, but a report that fails to
    *build* never reaches it and leaves the same stale files behind — so the
    plugin needs this composition too, and this is the one place it is spelled.
    """
    return '\n'.join([str(error), *discard_stale_sinks(config)])


def discard_stale_sinks(config: SinkConfig) -> list[str]:
    """Delete the sinks this run would have written, and say what happened.

    Writing no report leaves the *previous* run's in place, where it reads as
    current — the one outcome worse than no report at all. Only the paths this
    run was told to write are touched. Cannot raise: the caller is already
    handling a failure, and the usual reason a write failed (an unwritable
    directory) is also a reason the unlink will.
    """
    notes = []
    for path in config.file_paths():
        if not path.is_file():
            continue
        try:
            path.unlink()
        except OSError as error:
            notes.append(f'Could not remove the previous {path}: {error}')
        else:
            notes.append(f'Removed the previous {path} — it would read as current.')
    return notes
