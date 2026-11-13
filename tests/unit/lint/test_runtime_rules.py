"""Unit tests for the runtime-surface lint rules (`lint/runtime_rules.py`)."""

import dataclasses

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.capture.definition_refs import resolve_definition_refs
from pytest_given.lint import DEFAULTS
from pytest_given.lint.catalog import RuleId
from pytest_given.lint.runtime_rules import _unresolved_bold_spans, run_runtime_rules
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    ClauseWord,
    ColumnId,
    Definition,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Scenario,
    Sentence,
    SentenceId,
    SourceLocation,
    Step,
    Story,
    StoryId,
    id_derive,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


def _step(phase, text, line, children=()):
    return Step(
        phase=phase,
        narration=Narration(text=text),
        children=list(children),
        source=SourceLocation(relpath='test_x.py', line=line)
        if line is not None
        else None,
    )


def _rule_findings(findings, rule):
    return [f for f in findings if f.rule == RuleId(rule)]


# --- Runtime rules: missing-phase, tag-shadows-term, dead-term ---


def _phases_scenario(node_id, phases, *, status='passed', steps=None, tags=None):
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='S'),
        module='m',
        status=status,
        tags=tags or [],
        steps=steps if steps is not None else [_step(p, p, None) for p in phases],
        source=SourceLocation(relpath='test_x.py', line=7),
    )


def _runtime(grouped=(), glossary=None, stories=()):
    return run_runtime_rules(list(grouped), glossary, list(stories), set(DEFAULTS))


@scenario(
    t'{pg["Narration lint"]} flags a passed {pg["Scenario"].l} that skips a '
    t'{pg["Phase"].l}',
    stories=adopt_pytest_given,
)
def test_missing_phase_fires_on_passed_two_phase_scenario() -> None:
    with given(t'a passed {pg["Scenario"].l} narrating only given and then'):
        two_phase = _phases_scenario('test_x.py::test_a', ['given', 'then'])
    with when(
        t'the runtime {pg["Lint rule"].l.s} run', pins=adopt_pytest_given['flag']
    ):
        findings = _runtime(grouped=[two_phase])
    with then(
        t'one missing-phase {pg["Lint finding"].l} names the absent when and the '
        t'{pg["Scenario"].l} source'
    ):
        [finding] = findings
        assert finding.rule == RuleId('missing-phase')
        assert finding.subject == 'test_x.py::test_a'
        assert finding.location == SourceLocation(relpath='test_x.py', line=7)
        assert finding.message == 'missing: when'
    with then(t'its {pg["Severity"].l} is the catalog default, warn'):
        assert DEFAULTS[finding.rule] == 'warn'


def test_missing_phase_passes_a_complete_scenario() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'when', 'then'])
    assert _runtime(grouped=[scenario]) == []


def test_missing_phase_skips_non_passed_scenarios() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given'], status='failed')
    assert _runtime(grouped=[scenario]) == []


def test_missing_phase_reports_in_canonical_gwt_order() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given'])
    [finding] = _runtime(grouped=[scenario])
    assert 'missing: when, then' in finding.message


def test_missing_phase_counts_phases_of_nested_steps() -> None:
    steps = [
        _step('given', 'g', None),
        _step('when', 'w', None, [_step('then', 't', None)]),
    ]
    scenario = _phases_scenario('test_x.py::test_a', [], steps=steps)
    assert _runtime(grouped=[scenario]) == []


def test_missing_phase_without_scenario_source_omits_location() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'then'])
    scenario = dataclasses.replace(scenario, source=None)
    [finding] = _runtime(grouped=[scenario])
    assert finding.location is None
    assert finding.message == 'missing: when'


def _case(node_id, phases, *, status='passed'):
    return _phases_scenario(node_id, phases, status=status)


def _term(name, definition=None):
    return GlossaryTerm(
        id=id_derive(name),
        kind=None,
        canonical=name,
        definition=None if definition is None else Definition.literal(definition),
        source=SourceLocation(relpath='GLOSSARY.md', line=3),
    )


def _glossary(*names):
    return Glossary(terms=[_term(name) for name in names])


@scenario(
    t'{pg["Narration lint"]} flags a {pg["Tag"].l} that duplicates a {pg["Term"].l}',
    stories=adopt_pytest_given,
)
def test_tag_shadows_term_fires_once_per_unique_tag() -> None:
    with given(t'a {pg["Glossary"].l} defining one {pg["Term"].l}'):
        glossary = _glossary('Markdown glossary')
    with given(t'two scenarios carrying that word as a {pg["Tag"].l}'):
        scenarios = [
            _phases_scenario(
                'test_x.py::test_a',
                ['given', 'when', 'then'],
                tags=['Markdown Glossary'],
            ),
            _phases_scenario(
                'test_x.py::test_b',
                ['given', 'when', 'then'],
                tags=['Markdown Glossary'],
            ),
        ]
    with when(
        t'the runtime {pg["Lint rule"].l.s} run', pins=adopt_pytest_given['flag']
    ):
        findings = _rule_findings(
            _runtime(grouped=scenarios, glossary=glossary), 'tag-shadows-term'
        )
    with then(
        t'a single warn {pg["Lint finding"].l} names the {pg["Tag"].l} and the '
        t'{pg["Term"].l} it shadows, counting the scenarios and naming one'
    ):
        [finding] = findings
        assert DEFAULTS[finding.rule] == 'warn'
        assert finding.subject == 'markdown-glossary'
        assert finding.message == (
            "tag 'Markdown Glossary' duplicates glossary term 'Markdown glossary' "
            '(2 scenarios, e.g. test_x.py::test_a)'
        )


def test_tag_shadows_term_skips_a_tag_with_no_derivable_slug() -> None:
    """Tags are stored as written and `id_derive` raises on a name with no
    ASCII alphanumerics, which from here escaped as a bare traceback. Such a
    tag cannot collide with a term id anyway."""
    glossary = _glossary('Guest')
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a',
            ['given', 'when', 'then'],
            tags=['日本語', '++', 'Guest'],
        )
    ]
    findings = _rule_findings(
        _runtime(grouped=scenarios, glossary=glossary), 'tag-shadows-term'
    )
    [finding] = findings
    assert finding.subject == 'guest'


def test_tag_shadows_term_counts_a_scenario_once_across_spellings() -> None:
    """Two tags folding to one slug on the same scenario are one scenario."""
    glossary = _glossary('Guest')
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['Guest', 'guest']
        )
    ]
    [finding] = _rule_findings(
        _runtime(grouped=scenarios, glossary=glossary), 'tag-shadows-term'
    )
    assert '(1 scenario, e.g. test_x.py::test_a)' in finding.message


def test_tag_shadows_term_passes_orthogonal_tags() -> None:
    glossary = _glossary('Markdown glossary')
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['happy-path']
        ),
    ]
    findings = _runtime(grouped=scenarios, glossary=glossary)
    assert _rule_findings(findings, 'tag-shadows-term') == []


def test_tag_shadows_term_needs_a_glossary() -> None:
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['markdown-glossary']
        ),
    ]
    assert _runtime(grouped=scenarios, glossary=None) == []


def _term_ref_step(term):
    step = _step('given', f'a {term}', None)
    return dataclasses.replace(
        step,
        narration=Narration(
            text=f'a {term}',
            parts=(NarrationTermRef(term_id=id_derive(term), display=term),),
        ),
    )


def _dead_term_findings(glossary, grouped=(), stories=()):
    findings = _runtime(grouped=grouped, glossary=glossary, stories=stories)
    return _rule_findings(findings, 'dead-term')


@scenario(
    t'{pg["Narration lint"]} flags a {pg["Term"].l} referenced by no '
    t'{pg["Scenario title"].l}, {pg["Step"].l} or {pg["Story"].l}',
    stories=adopt_pytest_given,
)
def test_dead_term_flags_unreferenced_term() -> None:
    with given(t'a {pg["Glossary"].l} holding one unreferenced {pg["Term"].l}'):
        glossary = _glossary('Ghost term')
    with when(
        t'the runtime {pg["Lint rule"].l.s} run over no scenarios and no stories',
        pins=adopt_pytest_given['flag'],
    ):
        findings = _dead_term_findings(glossary)
    with then(t'the {pg["Lint finding"].l} names the unreferenced {pg["Term"].l}'):
        [finding] = findings
        assert finding.subject == 'ghost-term'
        assert finding.message == (
            "term 'Ghost term' is referenced by no scenario title, "
            'no step and no story sentence'
        )
    with then(t'its {pg["Severity"].l} is off — the rule is opt-in'):
        # Catalog default; `apply_config` drops it unless the suite opts in.
        assert DEFAULTS[finding.rule] == 'off'


def test_dead_term_passes_term_referenced_by_a_step() -> None:
    steps = [
        _term_ref_step('Ghost term'),
        _step('when', 'w', None),
        _step('then', 't', None),
    ]
    scenario = _phases_scenario('test_x.py::test_a', [], steps=steps)
    assert _dead_term_findings(_glossary('Ghost term'), grouped=[scenario]) == []


def test_dead_term_passes_term_referenced_by_a_scenario_title() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'when', 'then'])
    scenario = dataclasses.replace(
        scenario,
        narration=Narration(
            text='about Ghost term',
            parts=(
                NarrationTermRef(term_id=id_derive('Ghost term'), display='Ghost term'),
            ),
        ),
    )
    assert _dead_term_findings(_glossary('Ghost term'), grouped=[scenario]) == []


def test_dead_term_passes_term_referenced_by_a_story() -> None:
    story = Story(
        id=StoryId('s'),
        title='S',
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(
                    Clause(
                        parts=(
                            ClauseTermRef(
                                term_id=id_derive('Ghost term'), display='Ghost term'
                            ),
                        )
                    ),
                ),
            ),
        ),
    )
    assert _dead_term_findings(_glossary('Ghost term'), stories=[story]) == []


@scenario(
    t'{pg["Narration lint"]} counts a {pg["Term"].l} named only in the '
    t'second {pg["Clause"].l} of a {pg["Sentence"].l} as referenced',
)
def test_dead_term_passes_term_referenced_only_by_a_second_clause() -> None:
    def ref(name):
        return ClauseTermRef(term_id=id_derive(name), display=name)

    with given(
        t'a {pg["Story"].l} whose one {pg["Sentence"].l} names the '
        t'{pg["Term"].l} only in its second {pg["Clause"].l}'
    ):
        story = Story(
            id=StoryId('s'),
            title='S',
            sentences=(
                Sentence(
                    id=SentenceId(1),
                    clauses=(
                        Clause(parts=(ref('Guest'), ref('sign'), ref('Register'))),
                        Clause(parts=(ref('Clerk'), ref('sign'), ref('Register'))),
                    ),
                ),
            ),
        )
    with when(t'the runtime {pg["Lint rule"].l.s} run over that story'):
        findings = _dead_term_findings(
            _glossary('Guest', 'Clerk', 'sign', 'Register'), stories=[story]
        )
    with then('dead-term flags none of its terms'):
        assert findings == []


def test_dead_term_needs_a_glossary() -> None:
    assert _dead_term_findings(None) == []


# --- Runtime rule: unresolved-definition-ref ---


def _definition_ref_findings(*terms):
    glossary = resolve_definition_refs(Glossary(terms=list(terms)))
    return _rule_findings(_runtime(glossary=glossary), 'unresolved-definition-ref')


@scenario(
    t"{pg['Narration lint']} flags a bold span in a {pg['Term'].l}'s definition "
    t'that names no {pg["Term"].l}',
    tags=['spec/definition-refs'],
)
def test_unresolved_definition_ref_flags_a_bold_span_naming_no_term() -> None:
    with given(
        t'a {pg["Glossary"].l} whose Handle definition bolds a {pg["Term"].l} '
        t'and a word naming none'
    ):
        handle = _term('Handle', 'Names a **Term**, or a **sentence handle**.')
        glossary = (handle, _term('Term'))
    with when(t'the runtime {pg["Lint rule"].l.s} run'):
        findings = _definition_ref_findings(*glossary)
    with then(
        t'one {pg["Lint finding"].l} names the bold word, not the {pg["Term"].l}'
    ):
        [finding] = findings
        assert finding.subject == 'handle'
        assert finding.location == handle.source
        assert finding.message == (
            "definition of 'Handle' bolds 'sentence handle', "
            'which names no glossary term'
        )
    with then(t'its {pg["Severity"].l} is warn by default'):
        assert DEFAULTS[finding.rule] == 'warn'


def test_unresolved_definition_ref_flags_one_text_once_per_definition() -> None:
    findings = _definition_ref_findings(
        _term('Step', '**bare** or **bare**.'),
        _term('Phase', 'A **bare** word.'),
    )
    assert [finding.subject for finding in findings] == ['step', 'phase']


def test_unresolved_definition_ref_passes_a_resolved_ref() -> None:
    assert (
        _definition_ref_findings(_term('Step', 'In one **Phase**.'), _term('Phase'))
        == []
    )


def test_unresolved_definition_ref_flags_a_bold_span_left_in_a_literal_part() -> None:
    """The rule reads the stored parts and resolves no name of its own."""
    glossary = Glossary(terms=[_term('Step', 'In one **Phase**.'), _term('Phase')])
    findings = _rule_findings(_runtime(glossary=glossary), 'unresolved-definition-ref')
    assert [finding.subject for finding in findings] == ['step']


def test_unresolved_definition_ref_reads_bold_holding_no_code_span() -> None:
    definition = Definition.literal(
        "In one **Phase**, which *nests*, by a **`.l`** or **`.s` form** **Case**'s."
    )
    assert list(_unresolved_bold_spans(definition)) == ['Phase', 'Case']


def test_unresolved_definition_ref_passes_without_a_glossary() -> None:
    assert _rule_findings(_runtime(), 'unresolved-definition-ref') == []


# --- avoided-word ---


def _avoiding(name, *avoid):
    return dataclasses.replace(_term(name), avoid=tuple(avoid))


def _avoid_glossary(*avoid, term='Guest'):
    return Glossary(terms=[_avoiding(term, *avoid)])


def _worded_scenario(*step_texts, title='Booking', narrations=()):
    steps = [_step('given', text, 10 + index) for index, text in enumerate(step_texts)]
    steps += [
        Step(
            phase='given',
            narration=narration,
            source=SourceLocation(relpath='test_x.py', line=40),
        )
        for narration in narrations
    ]
    return dataclasses.replace(
        _phases_scenario('test_x.py::test_a', ['given', 'when', 'then']),
        narration=Narration(text=title),
        steps=steps,
    )


def _avoided_findings(glossary, scenario=None, stories=()):
    findings = _runtime(
        grouped=[] if scenario is None else [scenario],
        glossary=glossary,
        stories=stories,
    )
    return _rule_findings(findings, 'avoided-word')


def _step_message(word, preferred="'Guest'"):
    return (
        f'step text uses {word!r}, which the glossary avoids in favour of {preferred}'
    )


@scenario(
    t'The {pg["Narration lint"].l} flags an {pg["Avoided word"].l} in step text',
    tags=['spec/glossary-sections'],
)
def test_plain_text_finding() -> None:
    with given(t'a {pg["Glossary"].l} where Guest avoids Customer'):
        glossary = _avoid_glossary('Customer')
    with given(t'a {pg["Scenario"].l} whose step text says Customer'):
        booking = _worded_scenario('the Customer books a room')
    with when(t'the runtime {pg["Lint rule"].l.s} run'):
        [finding] = _avoided_findings(glossary, booking)
    with then(t'the {pg["Lint finding"].l} names the word and the step'):
        assert finding.subject == 'test_x.py::test_a'
        assert finding.location == SourceLocation(relpath='test_x.py', line=10)
        assert finding.message == _step_message('Customer')
    with then(t'its {pg["Severity"].l} is warn by default'):
        assert DEFAULTS[finding.rule] == 'warn'


def test_other_case_finding() -> None:
    glossary = _avoid_glossary('Customer')
    [finding] = _avoided_findings(glossary, _worded_scenario('a CUSTOMER books'))
    assert finding.message == _step_message('Customer')


def test_bold_finding() -> None:
    glossary = _avoid_glossary('Customer')
    booking = _worded_scenario('a **Customer** books')
    assert len(_avoided_findings(glossary, booking)) == 1
    assert len(_avoided_findings(glossary, _worded_scenario('an *e-Customer*'))) == 1


def test_term_ref_clean() -> None:
    glossary = _avoid_glossary('Customer', term='Customer')
    ref = NarrationTermRef(term_id=id_derive('Customer'), display='Customer')
    narration = Narration(
        text='the Customer pays',
        parts=(NarrationLiteral(value='the '), ref, NarrationLiteral(value=' pays')),
    )
    booking = _worded_scenario(narrations=[narration])
    assert _avoided_findings(glossary, booking) == []


@pytest.mark.parametrize(
    'part',
    [
        NarrationValue(
            rendered='still open',
            expression='paid',
            format_spec='paid by the Customer|still open',
        ),
        NarrationPlaceholder(
            name='paid',
            column_id=ColumnId('paid'),
            format_spec='paid by the Customer|still open',
        ),
    ],
)
def test_boolean_phrase_finding(part) -> None:
    glossary = _avoid_glossary('Customer')
    narration = Narration(
        text='the booking is still open',
        parts=(NarrationLiteral(value='the booking is '), part),
    )
    [finding] = _avoided_findings(glossary, _worded_scenario(narrations=[narration]))
    assert finding.message == _step_message('Customer')


def test_value_clean() -> None:
    glossary = _avoid_glossary('Customer')
    value = NarrationValue(rendered='Customer', expression='name')
    narration = Narration(text='Customer', parts=(value,))
    assert _avoided_findings(glossary, _worded_scenario(narrations=[narration])) == []


def test_code_span_clean() -> None:
    glossary = _avoid_glossary('Customer')
    assert _avoided_findings(glossary, _worded_scenario('the `Customer` row')) == []


def test_s_form_finding() -> None:
    glossary = _avoid_glossary('Customer')
    booking = _worded_scenario('the customers pay')
    assert len(_avoided_findings(glossary, booking)) == 1


@pytest.mark.parametrize('words', ['two SMSs are sent', 'two SMSes are sent'])
def test_acronym_s_forms_finding(words) -> None:
    glossary = _avoid_glossary('SMS')
    [finding] = _avoided_findings(glossary, _worded_scenario(words))
    assert finding.message == _step_message('SMS')


def test_inside_longer_word_clean() -> None:
    glossary = _avoid_glossary('Customer')
    assert _avoided_findings(glossary, _worded_scenario('the customerId is set')) == []


def test_multiword_split_by_line_break() -> None:
    glossary = _avoid_glossary('payment request')
    booking = _worded_scenario('a payment\n   request arrives')
    [finding] = _avoided_findings(glossary, booking)
    assert finding.message == _step_message('payment request')


def test_note_ignored() -> None:
    glossary = _avoid_glossary('Customer (a person who buys)')
    assert _avoided_findings(glossary, _worded_scenario('a person who buys')) == []
    [finding] = _avoided_findings(glossary, _worded_scenario('a Customer'))
    assert finding.message == _step_message('Customer')


def test_one_finding_per_scenario_and_word() -> None:
    glossary = _avoid_glossary('Customer', 'Patron')
    booking = _worded_scenario('a Customer', 'the Customer again', 'a Patron')
    findings = _avoided_findings(glossary, booking)
    assert [finding.message for finding in findings] == [
        _step_message('Customer'),
        _step_message('Patron'),
    ]


def test_scenario_title_finding() -> None:
    glossary = _avoid_glossary('Customer')
    booking = _worded_scenario('plain', title='A Customer books')
    [finding] = _avoided_findings(glossary, booking)
    assert finding.location == booking.source
    assert finding.message == (
        "scenario title uses 'Customer', which the glossary avoids in favour of 'Guest'"
    )


def test_title_and_step_one_finding_on_title() -> None:
    glossary = _avoid_glossary('Customer')
    booking = _worded_scenario('a Customer', title='A Customer books')
    [finding] = _avoided_findings(glossary, booking)
    assert finding.message.startswith('scenario title uses')
    assert finding.location == booking.source


def _story(*clauses):
    return Story(
        id=StoryId('booking'),
        title='Booking',
        sentences=(Sentence(id=SentenceId(0), clauses=clauses),),
        source=SourceLocation(relpath='stories.py', line=4),
    )


def test_story_sentence_finding() -> None:
    glossary = _avoid_glossary('Customer')
    ref = ClauseTermRef(term_id=id_derive('Guest'), display='Guest')
    story = _story(Clause(parts=(ref, ClauseWord(text='is a Customer'))))
    [finding] = _avoided_findings(glossary, stories=[story])
    assert finding.subject == 'booking'
    assert finding.location == SourceLocation(relpath='stories.py', line=4)
    assert finding.message == (
        "story sentence uses 'Customer', which the glossary avoids in favour of 'Guest'"
    )


def test_bare_clause_words_joined() -> None:
    glossary = _avoid_glossary('payment request')
    story = _story(
        Clause(parts=(ClauseWord(text='payment'), ClauseWord(text='request')))
    )
    assert len(_avoided_findings(glossary, stories=[story])) == 1


def test_bare_clause_words_split_by_a_term_ref_clean() -> None:
    glossary = _avoid_glossary('payment request')
    ref = ClauseTermRef(term_id=id_derive('Guest'), display='Guest')
    story = _story(
        Clause(parts=(ClauseWord(text='payment'), ref, ClauseWord(text='request')))
    )
    assert _avoided_findings(glossary, stories=[story]) == []


def test_two_terms_avoid_word() -> None:
    glossary = Glossary(
        terms=[_avoiding('Guest', 'Customer'), _avoiding('Clerk', 'customer')]
    )
    [finding] = _avoided_findings(glossary, _worded_scenario('a Customer'))
    assert finding.message == _step_message('Customer', "'Guest' or 'Clerk'")


def test_no_glossary_no_findings() -> None:
    assert _avoided_findings(None, _worded_scenario('a Customer')) == []


def test_avoided_word_with_punctuation() -> None:
    glossary = _avoid_glossary('C++', 'e.g.')
    uses = _worded_scenario('it uses C++ daily, e.g. here')
    assert [f.message for f in _avoided_findings(glossary, uses)] == [
        _step_message('C++'),
        _step_message('e.g.'),
    ]
    assert _avoided_findings(glossary, _worded_scenario('it uses C++x daily')) == []


@pytest.mark.parametrize('words', ['the check in desk', 'the check-in desk'])
def test_avoided_word_hyphen_or_space_finding(words) -> None:
    glossary = _avoid_glossary('check-in desk')
    [finding] = _avoided_findings(glossary, _worded_scenario(words))
    assert finding.message == _step_message('check-in desk')
