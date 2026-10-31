"""Whether two reports can be compared at all."""

from ..model import REPORT_SCHEMA_VERSION, PytestGivenError, ReportData


def check_reports(
    before: ReportData, after: ReportData, before_source: str, after_source: str
) -> tuple[str, ...]:
    """Refuses reports of another schema, whose defaulted fields would read as
    changes; warns when the versions that narrate the suite differ."""
    before_version = before.metadata.schema_version
    after_version = after.metadata.schema_version
    if (
        before_version != REPORT_SCHEMA_VERSION
        or after_version != REPORT_SCHEMA_VERSION
    ):
        raise PytestGivenError(
            f'cannot compare {before_source} (report schema version '
            f'{_version(before_version)}) with {after_source} (report schema version '
            f'{_version(after_version)}): a delta needs both at version '
            f'{REPORT_SCHEMA_VERSION}. Regenerate the older report under the current '
            'pytest-given, as the pytest-given-delta skill describes'
        )
    warnings: list[str] = []
    for name, what, before_value, after_value in (
        (
            'pytest-given',
            'a newer one can narrate the same test differently',
            before.metadata.plugin_version,
            after.metadata.plugin_version,
        ),
        (
            'pytest',
            'a newer one can generate other case IDs for the same values',
            before.metadata.pytest_version,
            after.metadata.pytest_version,
        ),
    ):
        if before_value != after_value:
            warnings.append(
                f'{before_source} comes from {name} {before_value} and '
                f'{after_source} from {name} {after_value}: {what}, which the '
                'delta reads as a change'
            )
    return tuple(warnings)


def _version(version: int | None) -> str:
    return 'none' if version is None else str(version)
