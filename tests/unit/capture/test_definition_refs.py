from pytest_given import given, scenario, then, when
from pytest_given.capture.definition_refs import resolve_definition_refs
from pytest_given.model import (
    Definition,
    Glossary,
    GlossaryTerm,
    NarrationLiteral,
    NarrationTermRef,
    TermId,
)
from tests.ubiquitous_language import pg
from tests.unit.citation_reports import term_


def _resolved(*terms: GlossaryTerm) -> Definition | None:
    """The first term's definition, resolved over the glossary of all of them."""
    [first, *_] = resolve_definition_refs(Glossary(terms=list(terms))).terms
    return first.definition


def _ref(term_id: str, display: str) -> NarrationTermRef:
    return NarrationTermRef(term_id=TermId(term_id), display=display)


@scenario(
    t'A {pg["Definition ref"].l} names its {pg["Term"].l} by canonical name or '
    t'{pg["S-form"]}, in any case',
    tags=['spec/definition-refs'],
)
def test_a_definition_ref_names_its_term_by_canonical_name_or_s_form() -> None:
    with given(
        t'a {pg["Glossary"].l} whose Step definition bolds "phase" and "Attachments"'
    ):
        step = term_('Step', 'In one **phase**, carrying **Attachments**.')
        glossary = Glossary(terms=[step, term_('Phase'), term_('Attachment')])
    with when(t'its {pg["Definition ref"].l.s} resolve at session finish'):
        [resolved, *_] = resolve_definition_refs(glossary).terms
    with then(
        t'each bold span is a {pg["Term ref"].l} to the {pg["Term"].l} it names, '
        t'in the words its author wrote'
    ):
        assert resolved.definition is not None
        assert resolved.definition.parts == (
            NarrationLiteral(value='In one '),
            _ref('phase', 'phase'),
            NarrationLiteral(value=', carrying '),
            _ref('attachment', 'Attachments'),
            NarrationLiteral(value='.'),
        )


def test_an_unresolved_bold_span_and_a_bold_code_span_stay_literal() -> None:
    text = 'A **sentence handle** or **`.l`**.'
    assert _resolved(term_('Handle', text), term_('Sentence')) == (
        Definition.literal(text)
    )


def test_a_self_reference_is_stored_as_a_ref() -> None:
    definition = _resolved(term_('Step', 'A **Step** nests.'))
    assert definition is not None
    assert definition.parts[1] == _ref('step', 'Step')


def test_a_ref_to_a_term_registered_after_the_referencing_term_resolves() -> None:
    glossary = Glossary(terms=[term_('Step', 'In one **Phase**.')])
    glossary.register(term_('Phase'))
    [step, _] = resolve_definition_refs(glossary).terms
    assert step.definition is not None
    assert _ref('phase', 'Phase') in step.definition.parts


def test_a_ref_at_either_end_of_a_definition_resolves() -> None:
    definition = _resolved(term_('Step', '**Phase**s and a **Phase**'), term_('Phase'))
    assert definition is not None
    assert definition.parts[0] == _ref('phase', 'Phase')
    assert definition.parts[-1] == _ref('phase', 'Phase')


def test_an_undefined_term_stays_undefined() -> None:
    assert _resolved(term_('Step')) is None
