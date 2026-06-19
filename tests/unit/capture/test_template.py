from pathlib import Path
from string import templatelib

import pytest

from pytest_given.capture.draft import draft
from pytest_given.capture.file_glossary import FileGlossary
from pytest_given.capture.template import Template, parse_tstring
from pytest_given.model import (
    Glossary,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PytestGivenError,
)


def test_template_parses_literal_only() -> None:
    t = Template('hello world')
    assert t.template == 'hello world'
    assert t.parts == [NarrationLiteral(value='hello world')]


def test_template_parses_single_placeholder() -> None:
    t = Template('Brew {cup_size} ml')
    assert t.parts == [
        NarrationLiteral(value='Brew '),
        NarrationPlaceholder(name='cup_size', format_spec='', conversion=None),
        NarrationLiteral(value=' ml'),
    ]


def test_template_parses_format_spec_and_conversion() -> None:
    t = Template('n={n:03d} r={obj!r}')
    assert t.parts == [
        NarrationLiteral(value='n='),
        NarrationPlaceholder(name='n', format_spec='03d', conversion=None),
        NarrationLiteral(value=' r='),
        NarrationPlaceholder(name='obj', format_spec='', conversion='r'),
    ]


def test_template_get_identifiers() -> None:
    t = Template('a {x} b {y} c {x}')
    assert t.get_identifiers() == ['x', 'y', 'x']


def test_template_substitute_basic() -> None:
    t = Template('Brew {cup_size} ml')
    assert t.substitute({'cup_size': 200}) == 'Brew 200 ml'


def test_template_substitute_with_format_spec() -> None:
    t = Template('n={n:03d}')
    assert t.substitute({'n': 7}) == 'n=007'


def test_template_substitute_with_conversion() -> None:
    t = Template('r={obj!r}')
    assert t.substitute({'obj': 'hi'}) == "r='hi'"


def test_template_substitute_missing_key_raises() -> None:
    t = Template('Brew {cup_size} ml')
    with pytest.raises(KeyError, match='cup_size'):
        t.substitute({})


def test_template_escape_braces_round_trip() -> None:
    t = Template('escaped {{name}} literal')
    assert t.substitute({}) == 'escaped {name} literal'


def test_template_unclosed_brace_raises_value_error() -> None:
    with pytest.raises(ValueError, match="expected '}'"):
        Template('a {cup_size')


@pytest.mark.parametrize(
    'text',
    ['count={obj.attr}', '{d[key]}', '{x + 1}'],
    ids=['attribute', 'indexing', 'expression'],
)
def test_template_non_identifier_raises_pytest_given_error(text: str) -> None:
    with pytest.raises(PytestGivenError, match='bare identifiers'):
        Template(text)


def test_parse_tstring_literal_only() -> None:
    cup_size = 200  # noqa: F841
    rendered, parts = parse_tstring(t'just a label')
    assert rendered == 'just a label'
    assert parts == [NarrationLiteral(value='just a label')]


def test_parse_tstring_single_interpolation() -> None:
    cup_size = 200
    rendered, parts = parse_tstring(t'a {cup_size} ml cup')
    assert rendered == 'a 200 ml cup'
    assert parts == [
        NarrationLiteral(value='a '),
        NarrationValue(
            rendered='200',
            expression='cup_size',
            format_spec='',
            conversion=None,
        ),
        NarrationLiteral(value=' ml cup'),
    ]


def test_parse_tstring_format_spec() -> None:
    n = 7
    rendered, parts = parse_tstring(t'n={n:03d}')
    assert rendered == 'n=007'
    assert parts == [
        NarrationLiteral(value='n='),
        NarrationValue(
            rendered='007',
            expression='n',
            format_spec='03d',
            conversion=None,
        ),
    ]


def test_parse_tstring_conversion() -> None:
    obj = 'hi'
    rendered, parts = parse_tstring(t'r={obj!r}')
    assert rendered == "r='hi'"
    assert parts == [
        NarrationLiteral(value='r='),
        NarrationValue(
            rendered="'hi'",
            expression='obj',
            format_spec='',
            conversion='r',
        ),
    ]


def test_parse_tstring_consecutive_interpolations() -> None:
    a = 1
    b = 2
    rendered, parts = parse_tstring(t'{a}{b}')
    assert rendered == '12'
    assert parts == [
        NarrationValue(rendered='1', expression='a', format_spec='', conversion=None),
        NarrationValue(rendered='2', expression='b', format_spec='', conversion=None),
    ]


def test_parse_tstring_expression() -> None:
    price = 10
    rendered, parts = parse_tstring(t'cost: {price * 1.2}')
    assert rendered == 'cost: 12.0'
    assert parts[1] == NarrationValue(
        rendered='12.0',
        expression='price * 1.2',
        format_spec='',
        conversion=None,
    )


def test_parse_tstring_accepts_templatelib_template() -> None:
    """Sanity check: the input type is string.templatelib.Template."""
    cup_size = 200
    tpl = t'{cup_size}'
    assert isinstance(tpl, templatelib.Template)
    rendered, _ = parse_tstring(tpl)
    assert rendered == '200'


# --- Task 5.1: glossary handles emit NarrationTermRef ---


@pytest.fixture
def glossary() -> Glossary:
    g = Glossary()
    g.actor('Guest', definition='')
    g.work_object('Room', definition='')
    g.verb('search', definition='')
    return g


def test_tstring_with_actor_emits_term_ref(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')  # idempotent re-fetch
    _, parts = parse_tstring(t'a {guest} arrives')
    assert any(
        isinstance(p, NarrationTermRef)
        and p.term_id == 'guest'
        and p.display == 'Guest'
        and p.param_column is None
        for p in parts
    )


def test_tstring_with_actor_instance_emits_term_ref_with_instance_display(
    glossary: Glossary,
) -> None:
    guest = glossary.actor('Guest')
    _, parts = parse_tstring(t'{guest("Alice")} arrives')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert len(term_refs) == 1
    assert term_refs[0].term_id == 'guest'
    assert term_refs[0].display == 'Alice'


def test_tstring_with_work_object_emits_term_ref(glossary: Glossary) -> None:
    room = glossary.work_object('Room')
    _, parts = parse_tstring(t'the {room} is clean')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert term_refs[0].term_id == 'room'
    assert term_refs[0].display == 'Room'


def test_tstring_with_work_object_instance_emits_term_ref(glossary: Glossary) -> None:
    room = glossary.work_object('Room')
    _, parts = parse_tstring(t'the {room("Deluxe Suite")} is clean')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert term_refs[0].display == 'Deluxe Suite'


def test_tstring_with_verb_emits_term_ref_with_canonical_display(
    glossary: Glossary,
) -> None:
    search = glossary.verb('search')
    _, parts = parse_tstring(t'they {search}')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert term_refs[0].display == 'search'


def test_tstring_with_inflected_verb_emits_term_ref_with_inflected_display(
    glossary: Glossary,
) -> None:
    search = glossary.verb('search')
    _, parts = parse_tstring(t'they {search("searches for")} a room')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert term_refs[0].display == 'searches for'
    assert term_refs[0].term_id == 'search'


def test_tstring_with_plain_value_still_emits_narration_value(
    glossary: Glossary,
) -> None:
    name = 'Alice'
    _, parts = parse_tstring(t'hi {name}')
    assert any(isinstance(p, NarrationValue) for p in parts)


def test_tstring_rendered_text_uses_display_for_term_refs(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    text, _ = parse_tstring(t'the {guest("Alice")} arrives')
    assert text == 'the Alice arrives'


# --- Task 5.2: draft interpolations raise PytestGivenError ---


def test_tstring_with_draft_actor_raises() -> None:
    d = draft.actor('Concierge')
    with pytest.raises(PytestGivenError, match='draft'):
        parse_tstring(t'the {d} greets')


def test_tstring_with_draft_work_object_raises() -> None:
    d = draft.work_object('loyalty bonus')
    with pytest.raises(PytestGivenError, match='draft'):
        parse_tstring(t'the {d} is applied')


def test_tstring_with_draft_verb_raises() -> None:
    d = draft.verb('redeems')
    with pytest.raises(PytestGivenError, match='draft'):
        parse_tstring(t'the guest {d} the bonus')


def test_tstring_with_draft_error_message_suggests_promotion() -> None:
    d = draft.actor('Concierge')
    with pytest.raises(
        PytestGivenError,
        match=r'Concierge.*promote.*g\.actor',
    ):
        parse_tstring(t'the {d}')


# --- Task 5.3: expression field populated; param_column via _templatize_narration ---


def test_tstring_with_term_ref_populates_expression(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    _, parts = parse_tstring(t'a {guest} arrives')
    ref = next(p for p in parts if isinstance(p, NarrationTermRef))
    assert ref.expression == 'guest'


def test_tstring_term_ref_with_format_spec_raises(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    with pytest.raises(PytestGivenError, match='format spec or conversion'):
        parse_tstring(t'hi {guest:>10}')


def test_tstring_term_ref_with_conversion_raises(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    with pytest.raises(PytestGivenError, match='format spec or conversion'):
        parse_tstring(t'hi {guest!r}')


def test_tstring_term_ref_instance_with_format_spec_raises(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    with pytest.raises(PytestGivenError, match='format spec or conversion'):
        parse_tstring(t'hi {guest("Alice"):>10}')


# --- FileTermHandle / FileTermInstance in t-strings ---

_FILE_GLOSSARY_MD = (
    '| Term | Meaning |\n|---|---|\n| Guest | A person. |\n| Room | A room. |\n'
)


@pytest.fixture
def _reset_glossary_registry():
    from pytest_given.capture.glossary import clear_glossary_registry

    clear_glossary_registry()
    yield
    clear_glossary_registry()


@pytest.fixture
def file_glossary(tmp_path: Path, _reset_glossary_registry) -> FileGlossary:
    path = tmp_path / 'G.md'
    path.write_text(_FILE_GLOSSARY_MD, encoding='utf-8')
    return FileGlossary(path)


def test_tstring_with_file_term_handle_emits_term_ref(
    file_glossary: FileGlossary,
) -> None:
    guest = file_glossary['Guest']
    _, parts = parse_tstring(t'a {guest} arrives')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert len(term_refs) == 1
    assert term_refs[0].term_id == 'guest'
    assert term_refs[0].display == 'Guest'


def test_tstring_with_file_term_instance_emits_term_ref_with_override_display(
    file_glossary: FileGlossary,
) -> None:
    guest = file_glossary['Guest']
    _, parts = parse_tstring(t'{guest("Alice")} books a room')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert len(term_refs) == 1
    assert term_refs[0].term_id == 'guest'
    assert term_refs[0].display == 'Alice'
