"""The term refs in rendered HTML, read as data rather than as markup."""

from html.parser import HTMLParser


class _TermRefs(HTMLParser):
    """Each element carrying a term id, as `(term id, its text)`."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: list[tuple[str, str]] = []
        self._open: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open = dict(attrs).get('data-term-id')

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self.refs.append((self._open, data))
            self._open = None


def term_refs(html: str) -> list[tuple[str, str]]:
    parser = _TermRefs()
    parser.feed(html)
    return parser.refs


def referenced_ids(html: str) -> list[str]:
    return [term_id for term_id, _ in term_refs(html)]
