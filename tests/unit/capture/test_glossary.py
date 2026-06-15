from pathlib import Path

import pytest

from pytest_given import PytestGivenError
from pytest_given.capture import source as source_mod
from pytest_given.capture.glossary import (
    Actor,
    ActorInstance,
    InflectedVerb,
    Verb,
    WorkObject,
    WorkObjectInstance,
    id_derive,
)
from pytest_given.model import Glossary, GlossaryTerm, SourceLocation, TermId


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
    assert id_derive(text) == expected


@pytest.mark.parametrize('text', ['---', '   ', '', '###'])
def test_id_derive_raises_on_empty_result(text):
    with pytest.raises(PytestGivenError, match='derived id is empty'):
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


def test_actor_call_returns_instance_with_distinct_display():
    g = Glossary()
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    a = Actor(_term=t, _glossary=g)
    inst = a('Alice')
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


def test_verb_call_returns_inflection_sharing_term_identity():
    g = Glossary()
    t = GlossaryTerm(id=TermId('confirm'), kind='verb', canonical='confirm')
    v = Verb(_term=t, _glossary=g)
    infl = v('confirms')
    assert isinstance(infl, InflectedVerb)
    assert infl.verb is v
    assert infl.display == 'confirms'


# --- Task 2.4: Glossary.actor/work_object/verb registration methods ---


def test_glossary_actor_registers_and_returns_handle():
    g = Glossary()
    a = g.actor('Guest', definition='Person booking accommodation.')
    assert isinstance(a, Actor)
    assert a.id == 'guest'
    assert a.canonical == 'Guest'
    assert a.term.definition == 'Person booking accommodation.'
    assert g[TermId('guest')].kind == 'actor'


def test_glossary_work_object_registers_and_returns_handle():
    g = Glossary()
    w = g.work_object('Room')
    assert isinstance(w, WorkObject)
    assert g[TermId('room')].kind == 'object'


def test_glossary_verb_registers_and_returns_handle():
    g = Glossary()
    v = g.verb('confirm')
    assert isinstance(v, Verb)
    assert g[TermId('confirm')].kind == 'verb'


def test_glossary_re_registration_with_matching_fields_is_idempotent():
    g = Glossary()
    a1 = g.actor('Guest', definition='d')
    a2 = g.actor('Guest', definition='d')
    assert a1.term == a2.term


def test_glossary_re_registration_with_mismatched_definition_raises():
    g = Glossary()
    g.actor('Guest', definition='one')
    with pytest.raises(PytestGivenError, match='conflicts with prior registration'):
        g.actor('Guest', definition='two')


def test_glossary_cross_kind_collision_raises():
    g = Glossary()
    g.actor('Foo')
    with pytest.raises(PytestGivenError, match='conflicts with prior registration'):
        g.verb('foo')


def test_glossary_actor_empty_name_raises():
    g = Glossary()
    with pytest.raises(PytestGivenError, match='derived id is empty'):
        g.actor('---')


def test_glossary_actor_captures_source():
    source_mod.set_rootdir(Path(__file__).resolve().parents[3])
    try:
        g = Glossary()
        a = g.actor('Guest')
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


def test_glossary_re_registration_with_matching_fields_succeeds_when_source_differs(monkeypatch):
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
