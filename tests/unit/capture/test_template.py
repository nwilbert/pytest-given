from pathlib import Path
from string import templatelib
from typing import Annotated, Any, cast

import pytest

from pytest_given import Glossary, given, scenario, then, when, when_then
from pytest_given.capture.file_glossary import FileGlossary
from pytest_given.capture.template import (
    Template,
    narration_from,
    parse_tstring,
    resolve_template_parts,
)
from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PytestGivenError,
    TermId,
    narration_text,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


def test_narration_from_passes_through_narration() -> None:
    """A pre-rendered Narration (an eager glossary-t-string scenario name)
    flows through unchanged, without a second parse."""
    narration = Narration(text='hi', parts=(NarrationLiteral(value='hi'),))
    assert narration_from(narration) is narration


def test_template_parses_literal_only() -> None:
    t = Template('hello world')
    assert t.template == 'hello world'
    assert t.parts == (NarrationLiteral(value='hello world'),)


@scenario(
    'A Template parses a bare placeholder',
    tags=['parametrization'],
)
def test_template_parses_single_placeholder() -> None:
    with given(t'a deferred {pg["Templatize"]} template with one placeholder'):
        source = 'Brew {cup_size} ml'
    with when('the template is parsed'):
        t = Template(source)
    with then(t'it splits into literal and placeholder {pg["Narration"]} parts'):
        assert t.parts == (
            NarrationLiteral(value='Brew '),
            NarrationPlaceholder(
                name='cup_size', column_id='cup_size', format_spec='', conversion=None
            ),
            NarrationLiteral(value=' ml'),
        )


def test_template_parses_format_spec_and_conversion() -> None:
    t = Template('n={n:03d} r={obj!r}')
    assert t.parts == (
        NarrationLiteral(value='n='),
        NarrationPlaceholder(
            name='n', column_id='n', format_spec='03d', conversion=None
        ),
        NarrationLiteral(value=' r='),
        NarrationPlaceholder(
            name='obj', column_id='obj', format_spec='', conversion='r'
        ),
    )


def _rendered(template: Template, mapping: dict[str, object]) -> str:
    """A Template rendered the way production renders one: its placeholders
    resolved against a mapping, then the text read off the resulting parts."""
    return narration_text(resolve_template_parts(template.parts, mapping))


def test_template_get_identifiers() -> None:
    t = Template('a {x} b {y} c {x}')
    assert t.get_identifiers() == ['x', 'y', 'x']


@scenario(
    'A Template substitutes parametrize values',
    tags=['parametrization'],
)
def test_template_substitute_basic() -> None:
    with given(t'a {pg["Templatize"]} template referencing a {pg["Case"]} column'):
        template = Template('Brew {cup_size} ml')
    with when(t'a {pg["Parameter table"]} value is substituted in'):
        rendered = _rendered(template, {'cup_size': 200})
    with then('the placeholder is filled with that value'):
        assert rendered == 'Brew 200 ml'


def test_template_substitute_with_format_spec() -> None:
    assert _rendered(Template('n={n:03d}'), {'n': 7}) == 'n=007'


def test_template_substitute_with_conversion() -> None:
    assert _rendered(Template('r={obj!r}'), {'obj': 'hi'}) == "r='hi'"


def test_template_substitute_missing_key_raises() -> None:
    with pytest.raises(KeyError, match='cup_size'):
        _rendered(Template('Brew {cup_size} ml'), {})


def test_template_escape_braces_round_trip() -> None:
    assert _rendered(Template('escaped {{name}} literal'), {}) == (
        'escaped {name} literal'
    )


def test_template_unclosed_brace_raises_value_error() -> None:
    with pytest.raises(ValueError, match="expected '}'"):
        Template('a {cup_size')


@scenario(
    'A Template accepts bare identifiers only',
    tags=['validation'],
)
@pytest.mark.parametrize(
    'text',
    ['count={obj.attr}', '{d[key]}', '{x + 1}'],
    ids=['attribute', 'indexing', 'expression'],
)
def test_template_non_identifier_raises_pytest_given_error(
    text: Annotated[str, given(Template('the placeholder {text}'))],
) -> None:
    with (
        when_then(
            t'a {pg["Templatize"]} template is built from it',
            'a PytestGivenError says bare identifiers only',
        ),
        pytest.raises(PytestGivenError, match='bare identifiers'),
    ):
        Template(text)


def test_parse_tstring_literal_only() -> None:
    cup_size = 200  # noqa: F841
    rendered, parts = parse_tstring(t'just a label')
    assert rendered == 'just a label'
    assert parts == (NarrationLiteral(value='just a label'),)


@scenario(
    'A t-string interpolation becomes a value part',
)
def test_parse_tstring_single_interpolation() -> None:
    with given('a t-string step with one interpolated value'):
        cup_size = 200
    with when('the t-string is parsed at runtime'):
        rendered, parts = parse_tstring(t'a {cup_size} ml cup')
    with then(t'the interpolation becomes a {pg["Narration"]} value part'):
        assert rendered == 'a 200 ml cup'
        assert parts == (
            NarrationLiteral(value='a '),
            NarrationValue(
                rendered='200',
                expression='cup_size',
                format_spec='',
                conversion=None,
            ),
            NarrationLiteral(value=' ml cup'),
        )


def test_parse_tstring_format_spec() -> None:
    n = 7
    rendered, parts = parse_tstring(t'n={n:03d}')
    assert rendered == 'n=007'
    assert parts == (
        NarrationLiteral(value='n='),
        NarrationValue(
            rendered='007',
            expression='n',
            format_spec='03d',
            conversion=None,
        ),
    )


def test_parse_tstring_conversion() -> None:
    obj = 'hi'
    rendered, parts = parse_tstring(t'r={obj!r}')
    assert rendered == "r='hi'"
    assert parts == (
        NarrationLiteral(value='r='),
        NarrationValue(
            rendered="'hi'",
            expression='obj',
            format_spec='',
            conversion='r',
        ),
    )


def test_parse_tstring_consecutive_interpolations() -> None:
    a = 1
    b = 2
    rendered, parts = parse_tstring(t'{a}{b}')
    assert rendered == '12'
    assert parts == (
        NarrationValue(rendered='1', expression='a', format_spec='', conversion=None),
        NarrationValue(rendered='2', expression='b', format_spec='', conversion=None),
    )


@scenario(
    'A t-string can interpolate an arbitrary expression',
)
def test_parse_tstring_expression() -> None:
    with given('a t-string step interpolating a computed expression'):
        price = 10
    with when('the t-string is parsed'):
        rendered, parts = parse_tstring(t'cost: {price * 1.2}')
    with then(t'the {pg["Value highlight"]} part records the full expression'):
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


@scenario(
    t'A {pg["Glossary"].low} handle in a t-string emits a {pg["Term ref"].low}',
)
def test_tstring_with_actor_emits_term_ref(glossary: Glossary) -> None:
    with given(t'an {pg["Actor"]} handle from the glossary'):
        guest = glossary.actor('Guest')  # idempotent re-fetch
    with when('the handle is interpolated into a t-string step'):
        _, parts = parse_tstring(t'a {guest} arrives')
    with then(t'the step carries a {pg["Term ref"]} for that {pg["Actor"]}'):
        assert any(
            isinstance(p, NarrationTermRef)
            and p.term_id == 'guest'
            and p.display == 'Guest'
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


@scenario(
    t'A {pg["Work Object"].low} handle in a t-string emits a {pg["Term ref"].low}',
)
def test_tstring_with_work_object_emits_term_ref(glossary: Glossary) -> None:
    with given(t'a {pg["Work Object"]} handle from the glossary'):
        room = glossary.work_object('Room')
    with when('it is interpolated into a t-string step'):
        _, parts = parse_tstring(t'the {room} is clean')
    with then(t'the step carries a {pg["Term ref"]} for that {pg["Work Object"]}'):
        term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
        assert term_refs[0].term_id == 'room'
        assert term_refs[0].display == 'Room'


def test_tstring_with_work_object_instance_emits_term_ref(glossary: Glossary) -> None:
    room = glossary.work_object('Room')
    _, parts = parse_tstring(t'the {room("Deluxe Suite")} is clean')
    term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
    assert term_refs[0].display == 'Deluxe Suite'


@scenario(
    t'A bare {pg["Verb"].low} handle keeps its canonical display',
)
def test_tstring_with_verb_emits_term_ref_with_canonical_display(
    glossary: Glossary,
) -> None:
    with given(t'a {pg["Verb"]} handle used without an {pg["Inflection"]}'):
        search = glossary.verb('search')
    with when('it is interpolated into a t-string step'):
        _, parts = parse_tstring(t'they {search}')
    with then(t'the {pg["Term ref"]} shows the canonical verb'):
        term_refs = [p for p in parts if isinstance(p, NarrationTermRef)]
        assert term_refs[0].display == 'search'


@scenario(
    t'An inflected {pg["Verb"].low} in a t-string shows the {pg["Inflection"].low}',
)
def test_tstring_with_inflected_verb_emits_term_ref_with_inflected_display(
    glossary: Glossary,
) -> None:
    with given(t'a {pg["Verb"]} handle called with an {pg["Inflection"]}'):
        search = glossary.verb('search')
    with when('it is interpolated into a t-string step'):
        _, parts = parse_tstring(t'they {search("searches for")} a room')
    with then(t'the {pg["Term ref"]} shows the inflection but keeps the verb id'):
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


# --- Task 5.3: expression field populated ---


def test_tstring_with_term_ref_populates_expression(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    _, parts = parse_tstring(t'a {guest} arrives')
    ref = next(p for p in parts if isinstance(p, NarrationTermRef))
    assert ref.expression == 'guest'


@scenario(
    t'A {pg["Term ref"].low} may not carry a format spec',
    tags=['validation'],
)
def test_tstring_term_ref_with_format_spec_raises(glossary: Glossary) -> None:
    with given(t'an {pg["Actor"]} handle interpolated with a format spec'):
        guest = glossary.actor('Guest')
    with (
        when_then(
            'the t-string is parsed',
            t'a PytestGivenError says a {pg["Term ref"]} takes no format spec',
        ),
        pytest.raises(PytestGivenError, match='format spec or conversion'),
    ):
        parse_tstring(t'hi {guest:>10}')


def test_tstring_term_ref_with_conversion_raises(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    with pytest.raises(PytestGivenError, match='format spec or conversion'):
        parse_tstring(t'hi {guest!r}')


def test_tstring_term_ref_instance_with_format_spec_raises(glossary: Glossary) -> None:
    guest = glossary.actor('Guest')
    with pytest.raises(PytestGivenError, match='format spec or conversion'):
        parse_tstring(t'hi {guest("Alice"):>10}')


# --- Deferred-kind terms in t-strings ---

_FILE_GLOSSARY_MD = (
    '| Term | Meaning |\n|---|---|\n| Guest | A person. |\n| Room | A room. |\n'
)


@pytest.fixture
def file_glossary(tmp_path: Path) -> FileGlossary:
    path = tmp_path / 'G.md'
    path.write_text(_FILE_GLOSSARY_MD, encoding='utf-8')
    return FileGlossary(path)


@scenario(
    t'A {pg["File glossary"]("FileGlossary")} handle works in a t-string '
    t'{pg["Step"].low}',
    story=adopt_pytest_given,
)
def test_tstring_with_file_term_handle_emits_term_ref(
    file_glossary: FileGlossary,
) -> None:
    with given(t'a {pg["Deferred term"]} from a {pg["File glossary"]}'):
        guest = file_glossary['Guest']
    with when('it is interpolated into a t-string step', activity=4):
        _, parts = parse_tstring(t'a {guest} arrives')
    with then(t'the step carries a single {pg["Term ref"]}'):
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


def test_resolve_template_parts_rejects_a_part_template_cannot_produce() -> None:
    # Template parses only literals and placeholders; anything else reaching
    # here is a bug, and the asserts say so rather than dropping the part.
    ref = NarrationTermRef(term_id=TermId('guest'), display='Guest', expression='g')
    with pytest.raises(AssertionError):
        resolve_template_parts([ref], {})
    with pytest.raises(AssertionError):
        resolve_template_parts([cast(Any, object())], {})
