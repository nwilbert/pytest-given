"""Unit tests for the runtime-surface lint rules (`lint/runtime_rules.py`)."""

import dataclasses

from pytest_given.lint import RuleId, run_runtime_rules
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    GlossaryTerm,
    Narration,
    NarrationTermRef,
    NodeId,
    Scenario,
    SourceLocation,
    Step,
    Story,
    StoryId,
    id_derive,
)


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


# --- Runtime rules: missing-phase, divergent-case-structure,
# --- tag-shadows-term, dead-term ---


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


def _runtime(grouped=(), per_case=(), glossary=None, stories=()):
    return run_runtime_rules(list(grouped), list(per_case), glossary, list(stories))


def test_missing_phase_fires_on_passed_two_phase_scenario() -> None:
    scenario = _phases_scenario('test_x.py::test_a', ['given', 'then'])
    [finding] = _runtime(grouped=[scenario])
    assert finding.rule == RuleId('missing-phase')
    assert finding.severity == 'warn'
    assert finding.subject == 'test_x.py::test_a'
    assert finding.location == SourceLocation(relpath='test_x.py', line=7)
    assert finding.message == 'missing: when (test_x.py:7)'


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


def test_divergent_case_structure_passes_matching_cases() -> None:
    cases = [
        _case('test_x.py::test_a[1]', ['given', 'when', 'then']),
        _case('test_x.py::test_a[2]', ['given', 'when', 'then']),
    ]
    assert _runtime(per_case=cases) == []


def test_divergent_case_structure_fires_once_naming_the_case() -> None:
    cases = [
        _case('test_x.py::test_a[1]', ['given', 'when', 'then']),
        _case('test_x.py::test_a[2]', ['given', 'then']),
        _case('test_x.py::test_a[3]', ['given', 'then']),
    ]
    [finding] = _runtime(per_case=cases)
    assert finding.rule == RuleId('divergent-case-structure')
    assert finding.severity == 'warn'
    assert finding.subject == 'test_x.py::test_a'
    assert '[2]' in finding.message
    assert '[3]' in finding.message


def test_divergent_case_structure_detects_nested_differences() -> None:
    nested = [
        _step('given', 'g', None),
        _step('when', 'w', None, [_step('when', 'sub', None)]),
        _step('then', 't', None),
    ]
    flat = [
        _step('given', 'g', None),
        _step('when', 'w', None),
        _step('then', 't', None),
    ]
    cases = [
        _phases_scenario('test_x.py::test_a[1]', [], steps=nested),
        _phases_scenario('test_x.py::test_a[2]', [], steps=flat),
    ]
    [finding] = _runtime(per_case=cases)
    assert finding.rule == RuleId('divergent-case-structure')


def test_divergent_case_structure_exempts_non_passed_cases() -> None:
    cases = [
        _case('test_x.py::test_a[1]', ['given', 'when', 'then']),
        _case('test_x.py::test_a[2]', ['given'], status='failed'),
        _case('test_x.py::test_a[3]', [], status='skipped'),
    ]
    assert _runtime(per_case=cases) == []


def test_divergent_case_structure_ignores_unparametrized_scenarios() -> None:
    cases = [
        _case('test_x.py::test_a', ['given', 'when', 'then']),
        _case('test_x.py::test_b', ['given', 'then']),
    ]
    assert _runtime(per_case=cases) == []


def _glossary(*names):
    return Glossary(
        terms=[
            GlossaryTerm(id=id_derive(name), kind=None, canonical=name)
            for name in names
        ]
    )


def test_tag_shadows_term_fires_once_per_unique_tag() -> None:
    glossary = _glossary('File glossary')
    scenarios = [
        _phases_scenario(
            'test_x.py::test_a', ['given', 'when', 'then'], tags=['File Glossary']
        ),
        _phases_scenario(
            'test_x.py::test_b', ['given', 'when', 'then'], tags=['File Glossary']
        ),
    ]
    [finding] = _rule_findings(
        _runtime(grouped=scenarios, glossary=glossary), 'tag-shadows-term'
    )
    assert finding.severity == 'warn'
    assert finding.subject == 'file-glossary'
    assert finding.message == (
        "tag 'File Glossary' duplicates glossary term 'File glossary' "
        '(2 scenarios, e.g. test_x.py::test_a)'
    )


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
            parts=[NarrationTermRef(term_id=id_derive(term), display=term)],
        ),
    )


def _dead_term_findings(glossary, grouped=(), stories=()):
    findings = _runtime(grouped=grouped, glossary=glossary, stories=stories)
    return _rule_findings(findings, 'dead-term')


def test_dead_term_flags_unreferenced_term() -> None:
    [finding] = _dead_term_findings(_glossary('Ghost term'))
    assert finding.subject == 'ghost-term'
    assert finding.severity == 'off'  # catalog default; apply_config drops it
    assert finding.message == "term 'Ghost term' is referenced by no step and no story"


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
            parts=[
                NarrationTermRef(term_id=id_derive('Ghost term'), display='Ghost term')
            ],
        ),
    )
    assert _dead_term_findings(_glossary('Ghost term'), grouped=[scenario]) == []


def test_dead_term_passes_term_referenced_by_a_story() -> None:
    story = Story(
        id=StoryId('s'),
        title='S',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityTermRef(
                                term_id=id_derive('Ghost term'), display='Ghost term'
                            ),
                        )
                    ),
                ),
            ),
        ),
    )
    assert _dead_term_findings(_glossary('Ghost term'), stories=[story]) == []


def test_dead_term_needs_a_glossary() -> None:
    assert _dead_term_findings(None) == []
