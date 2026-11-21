"""The sinks a run writes, rendered as a set and written as a set.

A run may be told to write any combination of JSON, HTML, Markdown, the
diagrams page and the egon.io files, and they have to agree with each other: a
render that raises must not leave this run's JSON beside the previous run's
HTML, with nothing on either saying so.
So rendering and writing are separate steps — `render_sinks` does everything
that can fail and touches no file, `write_all_or_none` touches files and
cannot fail on content, and `discard_files` removes a previous run's report
that would otherwise read as current.

`emit_sinks` is the whole transaction and the entry point callers want: the
sequencing *is* the guarantee, so keeping it in one place (`emit_files`, which
the delta's sinks share) is what stops callers from each spelling it out and
drifting apart.

Pytest-free like the rest of `report/`: the caller resolves its options into a
`SinkConfig`, which is also what lets `pytest-given report` reach the same code.
"""

# Deferred, since most runs draw no diagram.
__lazy_modules__ = ['pytest_given.report.diagram']

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import NamedTuple, Protocol

from ..model import (
    JsonObject,
    PytestGivenError,
    ReportData,
    ReportUrl,
    report_from_dict,
)
from .diagram import layout_stories, render_diagrams_html, render_egn
from .function_source import read_function_sources
from .html_renderer import render_html_string, tab_visibility
from .md_renderer import render_md
from .staged_write import write_all_or_none
from .theme import DEFAULT_THEME, Theme

# Where a bare --given-json / --given-html / `pytest-given report` writes.
# Report-layout facts, so both entry points read them from here rather than
# each spelling their own.
DEFAULT_JSON_PATH = Path('given-report/report-data.json')
DEFAULT_HTML_PATH = Path('given-report/report.html')
DEFAULT_DIAGRAMS_PATH = Path('given-report/diagrams.html')
DEFAULT_EGN_DIR = Path('given-report/egn')
DEFAULT_DELTA_JSON_PATH = Path('given-report/delta-data.json')
DEFAULT_DELTA_HTML_PATH = Path('given-report/delta.html')

# What a Markdown sink path may end in — also how `pytest-given report` tells
# a Markdown `-o` from an HTML one.
MD_SUFFIXES = ('.md', '.markdown')


@dataclass(frozen=True)
class SinkConfig:
    """Which sinks a run was told to write, and how to render them.

    `md_to_stdout` is its own flag rather than a sentinel path, so nothing
    downstream has to know that a bare `--given-md` means `-`. `source_root`
    is the rootdir a live run's source paths are relative to; None for a saved
    report, which does not carry it. `report_url` replaces the report's own in
    the HTML, for a saved report re-rendered to be served elsewhere.
    `html_glossary_only` renders the HTML without scenarios, stories or report
    URL: a term citation counts its scenarios, so a copied one would be stale.
    `md_source` reads the test functions from under `source_root`, so only a
    live run sets it. `egn_dir` gets one `<story id>.egn` file per story.
    """

    json_path: Path | None = None
    html_path: Path | None = None
    md_path: Path | None = None
    diagrams_path: Path | None = None
    egn_dir: Path | None = None
    md_to_stdout: bool = False
    md_lines: bool = True
    md_source: bool = False
    source_link_template: str | None = None
    source_root: Path | None = None
    theme: Theme = DEFAULT_THEME
    report_url: ReportUrl | None = None
    html_glossary_only: bool = False

    def __post_init__(self) -> None:
        require_suffix('JSON', self.json_path, ('.json',))
        require_suffix('HTML', self.html_path, ('.html', '.htm'))
        require_suffix('Markdown', self.md_path, MD_SUFFIXES)
        require_suffix('diagrams', self.diagrams_path, ('.html', '.htm'))
        if self.html_glossary_only and self.html_path is None:
            raise PytestGivenError(
                'A glossary-only report is HTML, but no HTML path is set.'
            )
        if self.html_glossary_only and self.report_url is not None:
            raise PytestGivenError(
                'A glossary-only report has no citations, so it takes no report URL.'
            )

    def file_paths(self) -> list[Path]:
        """The paths this run would write, in sink order. Only real files —
        Markdown bound for stdout has no path to overwrite or discard. The
        egon.io files are named by stories the report has not yet been read
        for, so every `.egn` file already in `egn_dir` counts."""
        paths = [
            path
            for path in (
                self.json_path,
                self.html_path,
                self.md_path,
                self.diagrams_path,
            )
            if path is not None
        ]
        if self.egn_dir is not None:
            paths.extend(sorted(self.egn_dir.glob('*.egn')))
        return paths

    def writes_anything(self) -> bool:
        """Whether any sink is configured — `file_paths()` plus stdout Markdown,
        which writes no file but still has to be rendered, and an `egn_dir`
        that holds no file yet."""
        return bool(self.file_paths()) or self.md_to_stdout or self.egn_dir is not None


def require_suffix(sink: str, path: Path | None, allowed: tuple[str, ...]) -> None:
    """Refuse a sink path that could not be a report file.

    These paths come from CLIs where a bare flag takes the next argument as
    its value, so a mis-ordered `--given-html tests/test_x.py` would aim the
    renderer at the author's own source — and `discard_files` would then
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


class Rendered(Protocol):
    @property
    def files(self) -> Sequence[RenderedFile]: ...


@dataclass(frozen=True)
class RenderedSinks:
    """Every configured sink rendered to text, before any of them is written."""

    files: list[RenderedFile] = field(default_factory=list)
    md_stdout: str | None = None


def emit_sinks(
    load: Callable[[], JsonObject], config: SinkConfig, source: str | None = None
) -> RenderedSinks:
    """Load the report dict, render and write every configured sink, or leave
    none of them behind: an input that can't be loaded fails the same way."""
    return emit_files(lambda: render_sinks(load(), config, source), config.file_paths())


def refuse_writing_over_an_input(
    outputs: Mapping[str, Path | None], inputs: Sequence[Path]
) -> None:
    """A failed run discards its outputs, so an output that is an input would
    delete it. `outputs` maps each sink's name to its path."""
    for name, output in outputs.items():
        if output is None:
            continue
        for input_path in inputs:
            if output.resolve() == input_path.resolve():
                raise PytestGivenError(
                    f'the {name} {output.as_posix()} is the input '
                    f'{input_path.as_posix()}; write it elsewhere'
                )


def emit_files[Files: Rendered](
    render: Callable[[], Files], paths: list[Path]
) -> Files:
    """Render, then write every file, or leave none of `paths` behind.

    Rendering can fail on content and writing can fail on the filesystem, and
    either failure has to take the whole set with it — including the *previous*
    run's, which would otherwise sit there reading as current.

    The discard notes are folded into the raised message, so a caller reports
    the failure by printing it.
    """
    try:
        rendered = render()
        # A truncated file would read as current, so none is written in place.
        write_all_or_none(rendered.files)
    except (PytestGivenError, OSError) as error:
        raise PytestGivenError(_failure_discarding(error, paths)) from error
    except BaseException:
        # A renderer bug (an undefined template name, a missing color key) or
        # a Ctrl-C is not a user error and keeps its own traceback — but it
        # fails the same way for the stale files on disk, which must still go.
        discard_files(paths)
        raise
    return rendered


def render_sinks(
    report_dict: JsonObject, config: SinkConfig, source: str | None = None
) -> RenderedSinks:
    """Render the configured sinks to text. Nothing here writes to the filesystem.

    Takes only the serialized report and deserializes it here, so the JSON sink
    writes the dict itself while the other two render from a copy that has been
    through serde — every sink then shows exactly what the JSON can express,
    and no caller has to keep two views of one run in agreement.
    """
    report = report_from_dict(report_dict, source)
    files: list[RenderedFile] = []
    if config.json_path is not None:
        files.append(RenderedFile(config.json_path, json.dumps(report_dict, indent=2)))
    if config.html_path is not None:
        html_report = report
        if config.report_url is not None:
            html_report = replace(
                report, metadata=replace(report.metadata, report_url=config.report_url)
            )
        if config.html_glossary_only:
            html_report = _glossary_only(html_report)
        files.append(
            RenderedFile(
                config.html_path,
                render_html_string(
                    html_report,
                    source_link_template=config.source_link_template,
                    theme=config.theme,
                    source_root=config.source_root,
                    diagrams_href=_diagrams_href(config),
                ),
            )
        )
    md_stdout: str | None = None
    if config.md_path is not None or config.md_to_stdout:
        sources = None
        if config.md_source:
            assert config.source_root is not None, 'md_source needs a live run'
            sources = read_function_sources(report.scenarios, config.source_root)
        md = render_md(report, with_lines=config.md_lines, sources=sources)
        if config.md_to_stdout:
            md_stdout = md
        if config.md_path is not None:
            files.append(RenderedFile(config.md_path, md))
    if config.diagrams_path is not None or config.egn_dir is not None:
        layouts = layout_stories(report)
        if config.diagrams_path is not None:
            files.append(
                RenderedFile(
                    config.diagrams_path,
                    render_diagrams_html(report, layouts, config.theme),
                )
            )
        if config.egn_dir is not None:
            files.extend(
                RenderedFile(
                    config.egn_dir / f'{layout.graph.story_id}.egn', render_egn(layout)
                )
                for layout in layouts
            )
    return RenderedSinks(files=files, md_stdout=md_stdout)


def _diagrams_href(config: SinkConfig) -> str | None:
    """The diagrams page relative to the HTML report's directory, or None when
    either is not written or, on Windows, they sit on different drives."""
    if config.html_path is None or config.diagrams_path is None:
        return None
    try:
        relative = os.path.relpath(config.diagrams_path, config.html_path.parent)
    except ValueError:
        return None
    return Path(relative).as_posix()


def require_glossary_terms(report: ReportData) -> None:
    """Refuse a glossary-only render with nothing to show.

    Public so a caller can refuse before `emit_sinks`, which takes a refusal
    inside it for a failed render and discards the previous report.
    """
    if not tab_visibility(report).glossary:
        raise PytestGivenError(
            'A glossary-only report needs glossary terms, but the report has none.'
        )


def _glossary_only(report: ReportData) -> ReportData:
    require_glossary_terms(report)
    return replace(
        report,
        scenarios=[],
        stories=[],
        metadata=replace(report.metadata, report_url=None),
    )


def sink_failure(error: Exception, config: SinkConfig) -> str:
    """What to report when a run produces no report: the failure, and what
    discarding the stale sinks did.

    `emit_sinks` covers a failure inside itself, but a report that fails to
    *build* never reaches it and leaves the same stale files behind — so the
    plugin needs this composition too.
    """
    return _failure_discarding(error, config.file_paths())


def _failure_discarding(error: Exception, paths: Sequence[Path]) -> str:
    return '\n'.join([str(error), *discard_files(paths)])


def discard_files(paths: Sequence[Path]) -> list[str]:
    """Delete each existing file, and say what happened.

    Writing no report leaves the *previous* run's in place, where it reads as
    current — the one outcome worse than no report at all. Only the paths this
    run was told to write are passed.

    Cannot raise: the caller is already handling a failure, and the usual
    reason a write failed (an unwritable directory) is also a reason the
    unlink will.
    """
    notes = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            path.unlink()
        except OSError as error:
            notes.append(f'Could not remove the previous {path}: {error}')
        else:
            notes.append(f'Removed the previous {path} — it would read as current.')
    return notes
