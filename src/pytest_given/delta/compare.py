"""The comparison `pytest-given delta` runs on two reports' JSON."""

from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from ..git import tags_by_commit
from ..model import JsonObject, report_from_dict
from .build import DeltaInputs, DeltaResult, build_delta
from .check import check_schema_versions, version_warnings
from .renames import read_rename_log
from .revs import revs_outside_range


def compare_reports(
    before_dict: JsonObject,
    after_dict: JsonObject,
    *,
    before_source: str,
    after_source: str,
    before_label: str | None,
    after_label: str | None,
    title: str | None,
    rename_log: Path | None,
    repo: Path,
) -> DeltaResult:
    """A side without a label takes its commit's highest tag. The result's
    warnings include every check's, in the order the checks ran."""
    check_schema_versions(before_dict, after_dict, before_source, after_source)
    before = report_from_dict(before_dict, before_source)
    after = report_from_dict(after_dict, after_source)
    warnings = list(version_warnings(before, after, before_source, after_source))
    renames = read_rename_log(rename_log)
    before_sha, after_sha = before.metadata.commit_sha, after.metadata.commit_sha
    skipped_revs, rev_warnings = revs_outside_range(
        renames.revs(), before_sha, after_sha, repo
    )
    before_label, after_label = _labels(
        [(before_label, before_sha), (after_label, after_sha)], repo
    )
    result = build_delta(
        DeltaInputs(
            before=before,
            after=after,
            renames=renames,
            skipped_revs=skipped_revs,
            before_label=before_label,
            after_label=after_label,
            title=title,
            plugin_version=version('pytest-given'),
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
    )
    return DeltaResult(
        delta=result.delta, warnings=(*warnings, *rev_warnings, *result.warnings)
    )


def _labels(sides: list[tuple[str | None, str | None]], repo: Path) -> list[str | None]:
    """Git is asked once for both sides, and not at all when neither needs a
    tag."""
    wanted = any(not label and sha for label, sha in sides)
    tags = tags_by_commit(repo) if wanted else {}
    return [label or _highest_tag(tags, sha) for label, sha in sides]


def _highest_tag(tags: dict[str, list[str]], sha: str | None) -> str | None:
    found = tags.get(sha, []) if sha else []
    return found[0] if found else None
