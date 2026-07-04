from pathlib import Path

import pytest

from pytest_given import PytestGivenError, given, scenario, then, when, when_then
from pytest_given.capture import source as source_mod
from pytest_given.capture.glossary import (
    Actor,
    ActorInstance,
    DeferredTermHandle,
    InflectedVerb,
    Verb,
    WorkObject,
    WorkObjectInstance,
    id_derive,
)
from pytest_given.model import Glossary, GlossaryTerm, SourceLocation, TermId
from tests._vocab import pg


@scenario(
    'Term ids are derived as URL-safe slugs',
    tags=['happy-path'],
)
@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Guest', 'guest'),
        ('Order received', 'order-received'),
        ('  Work Object  ', 'work-object'),
        ('do_the_thing', 'do-the-thing'),
        ('Buy / sell', 'buy-sell'),
        ('Guest #1', 'guest-1'),
        ('café', 'caf'),
        ('booking system', 'booking-system'),
    ],
)
def test_id_derive_produces_expected_slug(text, expected):
    with when(t'a {pg["Term"]} name {text!r} is slugified into an id'):
        derived = id_derive(text)
    with then(t'the id is the expected slug {expected!r}'):
        assert derived == expected


@scenario(
    'A name with no id-able characters is rejected',
    tags=['validation'],
)
@pytest.mark.parametrize('text', ['---', '   ', '', '###'])
def test_id_derive_raises_on_empty_result(text):
    with (
        when_then(
            t'{text!r} is slugified into a {pg["Term"]} id',
            'a PytestGivenError reports the derived id is empty',
        ),
        pytest.raises(PytestGivenError, match='derived id is empty'),
    ):
        id_derive(text)


def _term(kind, name='X'):
    return GlossaryTerm(id=TermId('x'), kind=kind, canonical=name)


def test_actor_carries_term_and_glossary_back_ref():
    g = Glossary()
    t = _term('actor')
    a = Actor(_term=t, _glossary=g)
    assert a.term is t
    assert a.glossary is g
    assert a.canonical == 'X'
    assert a.id == 'x'


def test_work_object_carries_term_and_glossary_back_ref():
    g = Glossary()
    t = _term('object')
    w = WorkObject(_term=t, _glossary=g)
    assert w.term is t
    assert w.glossary is g


def test_verb_carries_term_and_glossary_back_ref():
    g = Glossary()
    t = _term('verb')
    v = Verb(_term=t, _glossary=g)
    assert v.term is t
    assert v.glossary is g


@scenario(
    'Calling an actor names a distinct instance',
    tags=['happy-path'],
)
def test_actor_call_returns_instance_with_distinct_display():
    with given(t'an {pg["Actor"]} handle for Guest'):
        g = Glossary()
        t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
        a = Actor(_term=t, _glossary=g)
    with when(t'the {pg["Actor"]} is called with a name'):
        inst = a('Alice')
    with then(t'an {pg["Instance"]} with a distinct display is returned'):
        assert isinstance(inst, ActorInstance)
        assert inst.actor is a
        assert inst.display == 'Alice'


def test_work_object_call_returns_instance_with_distinct_display():
    g = Glossary()
    t = GlossaryTerm(id=TermId('room'), kind='object', canonical='Room')
    w = WorkObject(_term=t, _glossary=g)
    inst = w('Deluxe Suite')
    assert isinstance(inst, WorkObjectInstance)
    assert inst.work_object is w
    assert inst.display == 'Deluxe Suite'


@scenario(
    'Calling a verb records an inflection of the same term',
    tags=['happy-path'],
)
def test_verb_call_returns_inflection_sharing_term_identity():
    with given(t'a {pg["Verb"]} handle for confirm'):
        g = Glossary()
        t = GlossaryTerm(id=TermId('confirm'), kind='verb', canonical='confirm')
        v = Verb(_term=t, _glossary=g)
    with when(t'the {pg["Verb"]} is called with a surface form'):
        infl = v('confirms')
    with then(t'an {pg["Inflection"]} sharing the verb identity is returned'):
        assert isinstance(infl, InflectedVerb)
        assert infl.verb is v
        assert infl.display == 'confirms'


# --- Task 2.4: Glossary.actor/work_object/verb registration methods ---


@scenario(
    'Registering an actor returns a typed handle',
    tags=['happy-path'],
)
def test_glossary_actor_registers_and_returns_handle():
    with given('an empty glossary'):
        g = Glossary()
    with when(t'an {pg["Actor"]} is registered with a definition'):
        a = g.actor('Guest', definition='Person booking accommodation.')
    with then(t'a typed {pg["Actor"]} handle with the {pg["Actor"]} kind is returned'):
        assert isinstance(a, Actor)
        assert a.id == 'guest'
        assert a.canonical == 'Guest'
        assert a.term.definition == 'Person booking accommodation.'
        assert g.get(TermId('guest')).kind == 'actor'


def test_glossary_work_object_registers_and_returns_handle():
    g = Glossary()
    w = g.work_object('Room')
    assert isinstance(w, WorkObject)
    assert g.get(TermId('room')).kind == 'object'


def test_glossary_verb_registers_and_returns_handle():
    g = Glossary()
    v = g.verb('confirm')
    assert isinstance(v, Verb)
    assert g.get(TermId('confirm')).kind == 'verb'


@scenario(
    'Re-registering a term with matching fields is idempotent',
    tags=['happy-path'],
)
def test_glossary_re_registration_with_matching_fields_is_idempotent():
    with given(t'an {pg["Actor"]} already registered with a definition'):
        g = Glossary()
        a1 = g.actor('Guest', definition='d')
    with when('the same name and definition are registered again'):
        a2 = g.actor('Guest', definition='d')
    with then(t'both handles share the one {pg["Term"]}'):
        assert a1.term == a2.term


@scenario(
    'Re-registering a term with a different definition is rejected',
    tags=['validation'],
)
def test_glossary_re_registration_with_mismatched_definition_raises():
    with given(t'an {pg["Actor"]} already registered with one definition'):
        g = Glossary()
        g.actor('Guest', definition='one')
    with (
        when_then(
            'the name is registered again with a different definition',
            'a PytestGivenError reports the conflict with the prior registration',
        ),
        pytest.raises(PytestGivenError, match='conflicts with prior registration'),
    ):
        g.actor('Guest', definition='two')


@scenario(
    'The same name cannot be two different kinds',
    tags=['validation'],
)
def test_glossary_cross_kind_collision_raises():
    with given(t'a name already registered as an {pg["Actor"]}'):
        g = Glossary()
        g.actor('Foo')
    with (
        when_then(
            t'the same name is registered as a {pg["Verb"]}',
            'a PytestGivenError reports the conflict with the prior registration',
        ),
        pytest.raises(PytestGivenError, match='conflicts with prior registration'),
    ):
        g.verb('foo')


def test_glossary_actor_empty_name_raises():
    g = Glossary()
    with pytest.raises(PytestGivenError, match='derived id is empty'):
        g.actor('---')


@scenario(
    'Registering an actor captures its definition site',
    tags=['happy-path'],
)
def test_glossary_actor_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        with given('a rootdir-aware glossary'):
            g = Glossary()
        with when(t'an {pg["Actor"]} is registered'):
            a = g.actor('Guest')
        with then(t'the {pg["Term"]} records a {pg["Source link"]} to this file'):
            assert a.term.source is not None
            assert a.term.source.relpath.endswith('test_glossary.py')
            assert a.term.source.line > 0
    finally:
        source_mod._reset_rootdir()


def test_glossary_work_object_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        g = Glossary()
        w = g.work_object('Room')
        assert w.term.source is not None
        assert w.term.source.relpath.endswith('test_glossary.py')
    finally:
        source_mod._reset_rootdir()


def test_glossary_verb_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        g = Glossary()
        v = g.verb('confirm')
        assert v.term.source is not None
        assert v.term.source.relpath.endswith('test_glossary.py')
    finally:
        source_mod._reset_rootdir()


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
        source_mod._reset_rootdir()


def test_glossary_re_registration_matching_fields_ok_when_source_differs(monkeypatch):
    """Conflict equality must ignore `source`; same kind/canonical/definition
    from a different call site is not a conflict."""
    import pytest_given.capture.glossary as gloss_mod

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
    verb = g.verb('book', 'Reserve a room.')
    assert verb.term.definition == 'Reserve a room.'


# --- Task 3: g(name) declare-or-get and g[name] get-only ---


@scenario(
    'Calling the glossary declares a kindless term',
    tags=['kind-inference', 'happy-path'],
)
def test_call_declares_kindless_term():
    with given('an empty glossary'):
        g = Glossary()
    with when(t'a {pg["Term"]} is declared by call, without a kind'):
        handle = g('loyalty points')
    with then(t'the {pg["Term"]} is registered as {pg["Kindless"]}'):
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
    assert isinstance(handle, DeferredTermHandle)


@scenario(
    'Subscript looks up an already-declared term',
    tags=['happy-path'],
)
def test_subscript_get_only_returns_handle():
    with given(t'a glossary with one declared {pg["Term"]}'):
        g = Glossary()
        g('redeems')
    with then(t'subscripting the name returns that {pg["Term"]}'):
        assert g['redeems'].term.canonical == 'redeems'


@scenario(
    'Subscripting an unknown name raises with a hint',
    tags=['validation'],
)
def test_subscript_unknown_name_raises_with_hint():
    with given(t'a glossary with one declared {pg["Term"]}'):
        g = Glossary()
        g('redeems')
    with (
        when_then(
            'a near-miss name is subscripted',
            'a PytestGivenError is raised with a spelling hint',
        ),
        pytest.raises(PytestGivenError, match='redeems'),
    ):
        g['redeem']
