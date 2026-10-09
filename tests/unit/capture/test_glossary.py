from operator import attrgetter
from pathlib import Path
from typing import Annotated

import pytest

from pytest_given import (
    PytestGivenError,
    Template,
    given,
    scenario,
    then,
    when,
    when_then,
)
from pytest_given.capture import glossary as gloss_mod
from pytest_given.capture import source as source_mod
from pytest_given.capture.glossary import (
    Glossary,
    TermHandle,
    TermInstance,
    id_derive,
)
from pytest_given.model import GlossaryTerm, SourceLocation, TermId
from tests.ubiquitous_language import adopt_pytest_given, pg


@scenario(
    t'{pg["Term"]} ids are derived as URL-safe slugs, and a name with none is refused',
    tags=['validation'],
)
@pytest.mark.parametrize(
    ('text', 'refused', 'slug'),
    [
        ('Guest', False, 'guest'),
        ('Order received', False, 'order-received'),
        ('  Work Object  ', False, 'work-object'),
        ('do_the_thing', False, 'do-the-thing'),
        ('Buy / sell', False, 'buy-sell'),
        ('Guest #1', False, 'guest-1'),
        ('café', False, 'caf'),
        ('booking system', False, 'booking-system'),
        ('---', True, None),
        ('   ', True, None),
        ('', True, None),
        ('###', True, None),
    ],
)
def test_term_ids_are_derived_as_url_safe_slugs(
    text: Annotated[str, given(Template('the name {text}'))],
    refused,
    slug,
):
    with when(t'it is slugified into a {pg["Term"].l} id'):
        try:
            derived, refusal = id_derive(text), ''
        except PytestGivenError as error:
            derived, refusal = None, str(error)
    with then(t'a PytestGivenError reports the derived id is empty: {refused}'):
        assert ('derived id is empty' in refusal) == refused
    with then(t'the id is {slug!r}'):
        assert derived == slug


def _term(kind, name='X'):
    return GlossaryTerm(id=TermId('x'), kind=kind, canonical=name)


def test_actor_carries_term_and_glossary_back_ref():
    g = Glossary()
    t = _term('actor')
    a = TermHandle(_term=t, _glossary=g)
    assert a.term is t
    assert a.glossary is g
    assert a.canonical == 'X'
    assert a.id == 'x'


def test_work_object_carries_term_and_glossary_back_ref():
    g = Glossary()
    t = _term('object')
    w = TermHandle(_term=t, _glossary=g)
    assert w.term is t
    assert w.glossary is g


def test_activity_carries_term_and_glossary_back_ref():
    g = Glossary()
    t = _term('activity')
    v = TermHandle(_term=t, _glossary=g)
    assert v.term is t
    assert v.glossary is g


@scenario(
    t'Calling an {pg["Actor"].l} names a distinct {pg["Instance"].l}',
)
def test_actor_call_returns_instance_with_distinct_display():
    with given(t'an {pg["Actor"].l} handle for Guest'):
        g = Glossary()
        t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
        a = TermHandle(_term=t, _glossary=g)
    with when(t'the {pg["Actor"].l} is called with a name'):
        inst = a('Alice')
    with then(t'an {pg["Instance"].l} with a distinct display is returned'):
        assert isinstance(inst, TermInstance)
        assert inst.handle is a
        assert inst.display == 'Alice'


def test_work_object_call_returns_instance_with_distinct_display():
    g = Glossary()
    t = GlossaryTerm(id=TermId('room'), kind='object', canonical='Room')
    w = TermHandle(_term=t, _glossary=g)
    inst = w('Deluxe Suite')
    assert isinstance(inst, TermInstance)
    assert inst.handle is w
    assert inst.display == 'Deluxe Suite'


@scenario(
    t'Calling an {pg["Activity"].l} records an {pg["Inflection"].l} '
    t'of the same {pg["Term"].l}',
)
def test_activity_call_returns_inflection_sharing_term_identity():
    with given(t'an {pg["Activity"].l} handle for confirm'):
        g = Glossary()
        t = GlossaryTerm(id=TermId('confirm'), kind='activity', canonical='confirm')
        v = TermHandle(_term=t, _glossary=g)
    with when(t'the {pg["Activity"].l} is called with a surface form'):
        infl = v('confirms')
    with then(t'an {pg["Inflection"].l} sharing the activity identity is returned'):
        assert isinstance(infl, TermInstance)
        assert infl.handle is v
        assert infl.display == 'confirms'


# --- Task 2.4: Glossary.actor/work_object/activity registration methods ---


@scenario(
    t'Registering an {pg["Actor"].l} returns a typed handle',
    stories=adopt_pytest_given,
)
def test_glossary_actor_registers_and_returns_handle():
    with given('an empty glossary'):
        g = Glossary()
    with when(
        t'an {pg["Actor"].l} is registered with a definition',
        pins=adopt_pytest_given['build'],
    ):
        a = g.actor('Guest', definition='Person booking accommodation.')
    with then(t'a handle carrying the {pg["Actor"].l} kind is returned'):
        assert isinstance(a, TermHandle)
        assert a.declared_kind == 'actor'
        assert a.id == 'guest'
        assert a.canonical == 'Guest'
        assert a.term.definition == 'Person booking accommodation.'
        assert g.get(TermId('guest')).kind == 'actor'


def test_glossary_work_object_registers_and_returns_handle():
    g = Glossary()
    w = g.work_object('Room')
    assert w.declared_kind == 'object'
    assert g.get(TermId('room')).kind == 'object'


def test_glossary_activity_registers_and_returns_handle():
    g = Glossary()
    v = g.activity('confirm')
    assert v.declared_kind == 'activity'
    assert g.get(TermId('confirm')).kind == 'activity'


@scenario(
    t'Re-registering a {pg["Term"].l} is idempotent only with matching fields',
    stories=adopt_pytest_given,
    tags=['validation'],
)
@pytest.mark.parametrize(
    ('same_definition', 'outcome'),
    [(True, 'one shared term'), (False, 'refused')],
)
def test_re_registering_a_term_is_idempotent_only_with_matching_fields(
    same_definition, outcome
):
    with given(t'an {pg["Actor"].l} already registered with a definition'):
        g = Glossary()
        first = g.actor('Guest', definition='d')
    with when(
        t'the same name is registered again, with the same definition: '
        t'{same_definition}',
        pins=adopt_pytest_given['build'],
    ):
        try:
            second = g.actor('Guest', definition='d' if same_definition else 'two')
            refusal = ''
        except PytestGivenError as error:
            second, refusal = None, str(error)
    with then(t'the re-registration yields {outcome}'):
        shared = second is not None and second.term is first.term
        assert ('one shared term' if shared else 'refused') == outcome
    with then('a refusal reports the conflict with the prior registration'):
        assert ('conflicts with prior registration' in refusal) == (
            outcome == 'refused'
        )


@scenario(
    'The same name cannot be two different kinds',
    tags=['validation'],
)
def test_glossary_cross_kind_collision_raises():
    with given(t'a name already registered as an {pg["Actor"].l}'):
        g = Glossary()
        g.actor('Foo')
    with (
        when_then(
            t'the same name is registered as an {pg["Activity"].l}',
            'a PytestGivenError reports the conflict with the prior registration',
        ),
        pytest.raises(PytestGivenError, match='conflicts with prior registration'),
    ):
        g.activity('foo')


def test_glossary_actor_empty_name_raises():
    g = Glossary()
    with pytest.raises(PytestGivenError, match='derived id is empty'):
        g.actor('---')


@scenario(
    t'Registering an {pg["Actor"].l} captures its definition site',
)
def test_glossary_actor_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        with given('a rootdir-aware glossary'):
            g = Glossary()
        with when(t'an {pg["Actor"].l} is registered'):
            a = g.actor('Guest')
        with then(t'the {pg["Term"].l} records a {pg["Source link"].l} to this file'):
            assert a.term.source is not None
            assert a.term.source.relpath.endswith('test_glossary.py')
            assert a.term.source.line > 0
    finally:
        source_mod.restore_rootdir(None)


def test_glossary_work_object_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        g = Glossary()
        w = g.work_object('Room')
        assert w.term.source is not None
        assert w.term.source.relpath.endswith('test_glossary.py')
    finally:
        source_mod.restore_rootdir(None)


def test_glossary_activity_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        g = Glossary()
        v = g.activity('confirm')
        assert v.term.source is not None
        assert v.term.source.relpath.endswith('test_glossary.py')
    finally:
        source_mod.restore_rootdir(None)


def test_glossary_re_registration_preserves_first_source(monkeypatch):
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        g = Glossary()
        a1 = g.actor('Guest', definition='d')
        first_source = a1.term.source
        assert first_source is not None

        fake = SourceLocation(relpath='other/file.py', line=999)
        monkeypatch.setattr(
            'pytest_given.capture.glossary.capture_caller_source',
            lambda skip=2: fake,
        )
        a2 = g.actor('Guest', definition='d')
        assert a2.term is a1.term
        assert a2.term.source == first_source
    finally:
        source_mod.restore_rootdir(None)


def test_glossary_re_registration_matching_fields_ok_when_source_differs(monkeypatch):
    """Conflict equality must ignore `source`; same kind/canonical/definition
    from a different call site is not a conflict."""
    g = Glossary()

    src1 = SourceLocation(relpath='a.py', line=1)
    monkeypatch.setattr(gloss_mod, 'capture_caller_source', lambda skip=2: src1)
    a1 = g.actor('Guest', definition='d')

    src2 = SourceLocation(relpath='b.py', line=99)
    monkeypatch.setattr(gloss_mod, 'capture_caller_source', lambda skip=2: src2)
    a2 = g.actor('Guest', definition='d')

    assert a1.term is a2.term
    assert a1.term.source == src1  # first-registration wins


def test_blank_definition_normalizes_to_none():
    g = Glossary()
    actor = g.actor('Guest', '   ')
    assert actor.term.definition is None


def test_real_definition_is_kept():
    g = Glossary()
    verb = g.activity('book', 'Reserve a room.')
    assert verb.term.definition == 'Reserve a room.'


# --- Task 3: g(name) declare-or-get and g[name] get-only ---


@scenario(
    t'Calling the {pg["Glossary"].l} declares a {pg["Kindless"].l} {pg["Term"].l}',
    stories=adopt_pytest_given,
)
def test_call_declares_kindless_term():
    with given('an empty glossary'):
        g = Glossary()
    with when(
        t'a {pg["Term"].l} is declared by call, without a kind',
        pins=adopt_pytest_given['build'],
    ):
        handle = g('loyalty points')
    with then(t'the {pg["Term"].l} is registered as {pg["Kindless"].l}'):
        assert handle.term.kind is None
        assert handle.term.canonical == 'loyalty points'


def test_call_is_idempotent():
    g = Glossary()
    first = g('redeems')
    second = g('redeems')
    assert first.term is second.term


def test_call_accepts_definition():
    g = Glossary()
    handle = g('redeems', 'Exchange points for a benefit.')
    assert handle.term.definition == 'Exchange points for a benefit.'


def test_call_returns_deferred_handle():
    g = Glossary()
    handle = g('loyalty points')
    assert isinstance(handle, TermHandle)
    assert handle.declared_kind is None


def test_a_term_handle_is_hashable_and_keys_on_its_term():
    """Handles are public return values, so a user may put one in a set or key
    a dict on it, although the `Glossary` they carry is mutable."""
    g = Glossary()
    guest, room = g.actor('Guest'), g.work_object('Room')
    assert {guest, room, guest} == {guest, room}
    assert hash(guest('Alice')) == hash(guest('Alice'))


def test_a_lookup_equals_the_registration_of_the_same_term():
    """Which accessor handed the term over is not part of its identity."""
    g = Glossary()
    assert g.actor('Guest') == g['Guest']


@scenario(
    t'The lowercase {pg["Handle"].l} form lowercases only capitalized words, '
    t'so acronyms and standalone letters keep their case',
)
@pytest.mark.parametrize(
    ('canonical', 'lowered'),
    [
        ('Booking Request', 'booking request'),
        ('LLM Call', 'LLM call'),
        ('Check-In', 'check-in'),
        ('Plan B', 'plan B'),
        ('E-Mail', 'e-mail'),
        ('LLM-Based Search', 'LLM-based search'),
        ('iPhone', 'iPhone'),
        ('McDonald', 'McDonald'),
    ],
)
def test_lowercase_form_keeps_acronyms_and_mixed_case_words(canonical, lowered):
    with given(t'a {pg["Term"].l} named {canonical!r}'):
        handle = Glossary()(canonical)
    with when(t'its lowercase {pg["Handle"].l} form is taken'):
        result = handle.l
    with then(t'it reads {lowered!r}'):
        assert result.display == lowered


@scenario(
    t'The {pg["S-form"]} and lowercase {pg["Handle"].l} forms chain, '
    t'and every reading stays the same {pg["Term"].l}',
)
@pytest.mark.parametrize(
    ('canonical', 'forms', 'reading'),
    [
        ('Room', 's', 'Rooms'),
        ('Room', 'l.s', 'rooms'),
        ('Room', 's.l', 'rooms'),
        ('Box', 'l.s', 'boxes'),
        ('Category', 'l.s', 'categories'),
        ('API Key', 'l.s', 'API keys'),
        ('API', 's', 'APIs'),
        ('book', 's', 'books'),
    ],
)
def test_s_form_chains_with_lowercase_form(canonical, forms, reading):
    with given(t'a {pg["Term"].l} named {canonical!r}'):
        handle = Glossary()(canonical)
    with when(t'the {pg["Handle"].l} forms {forms!r} are applied in order'):
        result = attrgetter(forms)(handle)
    with then(t'it reads {reading!r} and refers to the same {pg["Term"].l}'):
        assert result.display == reading
        assert result.handle is handle


@scenario(
    t'The {pg["S-form"]} and lowercase {pg["Handle"].l} forms also apply to '
    t'a called form',
)
def test_s_form_and_lowercase_form_apply_to_a_called_form():
    with given(t'a {pg["Term"].l} named "Room"'):
        room = Glossary()('Room')
    with when(t'it is called as "Deluxe Suite" and both forms are applied'):
        suites = room('Deluxe Suite').l.s
    with then(t'it reads "deluxe suites" and refers to the same {pg["Term"].l}'):
        assert suites.display == 'deluxe suites'
        assert suites.handle is room


@scenario(
    t'Subscript looks up an already-declared {pg["Term"].l}',
)
def test_subscript_get_only_returns_handle():
    with given(t'a glossary with one declared {pg["Term"].l}'):
        g = Glossary()
        g('redeems')
    with when('the name is looked up by subscript'):
        handle = g['redeems']
    with then(t'the returned {pg["Term"].l} is the declared one'):
        assert handle.term.canonical == 'redeems'


@scenario(
    'Subscripting an unknown name raises with a hint',
    tags=['diagnostics', 'validation'],
)
def test_subscript_unknown_name_raises_with_hint():
    with given(t'a glossary with one declared {pg["Term"].l}'):
        g = Glossary()
        g('redeems')
    with (
        when_then(
            'a near-miss name is subscripted',
            'a PytestGivenError is raised with a spelling hint',
        ),
        pytest.raises(PytestGivenError, match='Did you mean: redeems'),
    ):
        g['redeem']


def test_subscript_miss_is_a_lookup_error():
    """Jinja's attribute fallback probes a live run's glossary with
    `glossary[name]`, catching only `LookupError`."""
    with pytest.raises(LookupError):
        Glossary()['description']
