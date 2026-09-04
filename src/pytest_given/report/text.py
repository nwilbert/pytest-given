"""Wording helpers the renderers and view builders share."""


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """`'1 scenario'` / `'3 scenarios'` — the noun agreeing with its count."""
    if count == 1:
        return f'{count} {singular}'
    return f'{count} {plural_form or singular + "s"}'
