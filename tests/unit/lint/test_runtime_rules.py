"""Unit tests for the runtime-surface lint rules (`lint/runtime_rules.py`)."""

import dataclasses

from pytest_given import given, scenario, then, when
from pytest_given.lint import DEFAULTS
from pytest_given.lint.base import RuleId
from pytest_given.lint.runtime_rules import run_runtime_rules
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationTermRef,
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
        t'the runtime {pg["Lint rule"]("rules")} run', pins=adopt_pytest_given['flag']
    ):
        findings = _runtime(grouped=[two_phase])
    with then(
        t'one missing-phase {pg["Finding"].l} names the absent when and the '
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


def _glossary(*names):
    return Glossary(
        terms=[
            GlossaryTerm(id=id_derive(name), kind=None, canonical=name)
            for name in names
        ]
    )


@scenario(
    t'{pg["Narration lint"]} flags a {pg["Tag"].l} that duplicates a {pg["Term"].l}',
    stories=adopt_pytest_given,
)
def test_tag_shadows_term_fires_once_per_unique_tag() -> None:
    with given(t'a {pg["Glossary"].l} defining one {pg["Term"].l}'):
        glossary = _glossary('File glossary')
    with given(t'two scenarios carrying that word as a {pg["Tag"].l}'):
        scenarios = [
            _phases_scenario(
                'test_x.py::test_a', ['given', 'when', 'then'], tags=['File Glossary']
            ),
            _phases_scenario(
                'test_x.py::test_b', ['given', 'when', 'then'], tags=['File Glossary']
            ),
        ]
    with when(
        t'the runtime {pg["Lint rule"]("rules")} run', pins=adopt_pytest_given['flag']
    ):
        findings = _rule_findings(
            _runtime(grouped=scenarios, glossary=glossary), 'tag-shadows-term'
        )
    with then(
        t'a single warn {pg["Finding"].l} names the {pg["Tag"].l} and the '
        t'{pg["Term"].l} it shadows, counting the scenarios and naming one'
    ):
        [finding] = findings
        assert DEFAULTS[finding.rule] == 'warn'
        assert finding.subject == 'file-glossary'
        assert finding.message == (
            "tag 'File Glossary' duplicates glossary term 'File glossary' "
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
    glossary = _glossary('File glossary')
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
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['file-glossary']
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
    t'{pg["Scenario"].l} name, {pg["Step"].l} or {pg["Story"].l}',
    stories=adopt_pytest_given,
)
def test_dead_term_flags_unreferenced_term() -> None:
    with given(t'a {pg["Glossary"].l} holding one unreferenced {pg["Term"].l}'):
        glossary = _glossary('Ghost term')
    with when(
        t'the runtime {pg["Lint rule"]("rules")} run over no scenarios and no stories',
        pins=adopt_pytest_given['flag'],
    ):
        findings = _dead_term_findings(glossary)
    with then(t'the {pg["Finding"].l} names the unreferenced {pg["Term"].l}'):
        [finding] = findings
        assert finding.subject == 'ghost-term'
        assert finding.message == (
            "term 'Ghost term' is referenced by no scenario name, "
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


def test_dead_term_passes_term_referenced_by_a_scenario_name() -> None:
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
    with when(t'the runtime {pg["Lint rule"]("rules")} run over that story'):
        findings = _dead_term_findings(
            _glossary('Guest', 'Clerk', 'sign', 'Register'), stories=[story]
        )
    with then('dead-term flags none of its terms'):
        assert findings == []


def test_dead_term_needs_a_glossary() -> None:
    assert _dead_term_findings(None) == []
