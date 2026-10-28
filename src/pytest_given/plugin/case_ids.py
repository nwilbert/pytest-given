"""Whether a case's id is custom, written by hand, read off the id itself.

pytest builds a generated id from the case's values, so an id made of nothing
but its values' tokens says nothing a reader could not see in the table. Any
other id is custom: `pytest.param(..., id=...)`, `ids=` on a mark, a fixture
or `metafunc.parametrize` alike. The token rules are pytest's own (`IdMaker`),
copied, as pytest exports none of it; tests pin each rule.
"""

import enum
import hashlib
import re
from collections.abc import Mapping

import pytest

from ..model import case_id

# What pytest's `ascii_escaped` writes for an ASCII byte outside printable range.
_NON_PRINTABLE = {
    code: f'\\x{code:02x}' for code in range(128) if code not in range(32, 127)
} | {ord('\t'): '\\t', ord('\r'): '\\r', ord('\n'): '\\n'}


def is_custom_id(
    config: pytest.Config, node_id: str, params: Mapping[str, object]
) -> bool:
    pytest_id = case_id(node_id)
    tokens = [_token(config, value, name) for name, value in params.items()]
    return bool(pytest_id) and not _joins(pytest_id, tokens)


def _joins(written: str, tokens: list[re.Pattern[str]]) -> bool:
    """Whether `written` is the tokens joined by `-`, in order, any of them
    left out: a hidden part leaves its tokens out of the id."""
    ends = [index for index, char in enumerate(written) if char == '-']
    ends.append(len(written))
    # Where the next token may start; one past the end is the whole id read.
    starts = {0}
    for token in tokens:
        starts |= {
            end + 1
            for start in starts
            for end in ends
            if end >= start and token.fullmatch(written, start, end)
        }
    return len(written) + 1 in starts


def _token(config: pytest.Config, value: object, argname: str) -> re.Pattern[str]:
    """What pytest generates for `value`. Its fallback, `argname` and the case's
    position in its parametrize call, is allowed for every value: the position
    is not known here, and the fallback also names an empty parameter set.
    A trailing counter is what pytest appends to tell duplicate ids apart,
    after a `_` where the id ends in a digit."""
    hook_text = _hook_token(config, value, argname)
    texts = [hook_text] if hook_text is not None else _value_tokens(config, value)
    alternatives = []
    for text in texts:
        counter = '_' if text[-1:].isdigit() else ''
        alternatives.append(f'{re.escape(text)}(?:{counter}\\d+)?')
    alternatives.append(f'{re.escape(argname)}\\d+(?:_\\d+)?')
    return re.compile('|'.join(alternatives))


def _hook_token(config: pytest.Config, value: object, argname: str) -> str | None:
    """A failure is no answer: pytest asks the hook only for a generated part,
    so it need not handle a value whose id is custom."""
    try:
        token: str | None = config.hook.pytest_make_parametrize_id(
            config=config, val=value, argname=argname
        )
    except Exception:  # noqa: BLE001 — user hook code; see the docstring
        return None
    return token


def _value_tokens(config: pytest.Config, value: object) -> list[str]:
    """A str or bytes over 100 long may also be named by its sha256 digest
    (pytest 9.2's `parametrize_long_str_id_strategy`). The option goes unread,
    as pytest 9.0 has none. A custom id equal to the digest is no real risk."""
    if isinstance(value, str | bytes):
        if isinstance(value, str) and config.getini(
            'disable_test_id_escaping_and_forfeit_all_rights_to_community_support'
        ):
            text = value
        else:
            text = _ascii_escaped(value)
        texts = [text]
        if len(value) > 100:
            encoded = value.encode('utf-8') if isinstance(value, str) else value
            texts.append(hashlib.sha256(encoded).hexdigest())
        return texts
    if value is None or isinstance(value, float | int | bool | complex):
        return [str(value)]
    if isinstance(value, re.Pattern):
        return [_ascii_escaped(value.pattern)]
    if isinstance(value, enum.Enum):
        return [str(value)]
    name = getattr(value, '__name__', None)
    return [name] if isinstance(name, str) else []


def _ascii_escaped(value: str | bytes) -> str:
    if isinstance(value, bytes):
        text = value.decode('ascii', 'backslashreplace')
    else:
        text = value.encode('unicode_escape').decode('ascii')
    return text.translate(_NON_PRINTABLE)
