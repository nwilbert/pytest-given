"""Whether two reports can be compared at all."""

from ..model import (
    REPORT_SCHEMA_VERSION,
    JsonObject,
    PytestGivenError,
    ReportData,
    is_delta_dict,
)


def check_schema_versions(
    before: JsonObject, after: JsonObject, before_source: str, after_source: str
) -> None:
    """Refuses reports of another schema, whose defaulted fields would read as
    changes. Runs on the dicts, before reading one as a report can fail on a
    field its schema lacks; a delta passes, for `report_from_dict` to name."""
    if is_delta_dict(before) or is_delta_dict(after):
        return
    before_version, after_version = _schema_version(before), _schema_version(after)
    if before_version == after_version == REPORT_SCHEMA_VERSION:
        return
    raise PytestGivenError(
        f'cannot compare {before_source} (report schema version '
        f'{_version(before_version)}) with {after_source} (report schema version '
        f'{_version(after_version)}): a delta needs both at version '
        f'{REPORT_SCHEMA_VERSION}. Regenerate the older report under the current '
        'pytest-given, as the pytest-given-delta skill describes'
    )


def version_warnings(
    before: ReportData, after: ReportData, before_source: str, after_source: str
) -> tuple[str, ...]:
    """Warns when the versions that narrate the suite differ."""
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


def _schema_version(report_dict: JsonObject) -> object:
    metadata = report_dict.get('metadata')
    return metadata.get('schema_version') if isinstance(metadata, dict) else None


def _version(version: object) -> str:
    return 'none' if version is None else str(version)
