"""The public URL a report is served from."""

import pytest

from pytest_given.model import PytestGivenError, resolve_report_url


def test_an_absolute_https_url_is_the_report_url() -> None:
    url = 'https://example.org/pytest-given/dev/examples/self-report.html'
    assert resolve_report_url(url, '--given-report-url') == url


def test_an_empty_setting_means_no_report_url() -> None:
    assert resolve_report_url('', 'given_report_url') is None


@pytest.mark.parametrize(
    'value',
    [
        'examples/self-report.html',
        '/examples/self-report.html',
        'ftp://example.org/report.html',
        'https://example.org/report.html#tag=x',
        'https://example.org/report.html#',
        'https://example.org/my report.html',
        'https://example.org/report.html\t',
        'https://example.org/report.html\n',
        'https://example.org/re\x00port.html',
        'https://example.org/re\x7fport.html',
        'https://example.org/<report>.html',
        'https://example.org/report(1).html',
        'https://example.org/re\\port.html',
    ],
)
def test_a_url_a_citation_cannot_link_is_refused(value: str) -> None:
    with pytest.raises(PytestGivenError, match='--given-report-url'):
        resolve_report_url(value, '--given-report-url')
