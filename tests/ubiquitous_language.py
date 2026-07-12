"""The ubiquitous language of pytest-given's own bounded context.

The project's own ``GLOSSARY.md`` is the ubiquitous language of pytest-given's
bounded context. Loading it as a :class:`FileGlossary` lets the backend tests
narrate their behaviour in that vocabulary, so ``pytest --given-html`` renders a
living, filterable behavioural spec of the plugin itself.

Term handles are referenced as ``pg['Scenario']`` inside t-string steps. The
name ``pg`` (pytest-given) is deliberately distinct from the throwaway ``g``
Glossary fixtures/locals the unit tests build for their own domain-under-test.

``adopt_pytest_given`` is the dogfood domain story: the greenfield adoption
arc, from Domain Expert elicitation through Agent-authored scenarios and the
Collector/Renderer machinery to stakeholder review. Backend scenarios bind to
it via ``@scenario(story=adopt_pytest_given)`` plus an ``activity=N`` pin on
the one step that genuinely demonstrates activity N. Verbs are bare words —
story prose, not glossary vocabulary (see the design spec) — except *Graft*
and *Group*, existing terms whose meaning is the verb. The ``_t`` suffix
("term handle") dodges shadowing the ``story``/``activity`` constructors.
"""

from pathlib import Path

from pytest_given import FileGlossary, activity, story

_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / 'GLOSSARY.md'

pg = FileGlossary(_GLOSSARY_PATH)

developer = pg['Developer']
domain_expert = pg['Domain Expert']
agent = pg['Agent']
collector_t = pg['Collector']
renderer_t = pg['Renderer']
story_t = pg['Story']
activity_t = pg['Activity']
glossary_t = pg['Glossary']
scenario_t = pg['Scenario']
tag_t = pg['Tag']
step_t = pg['Step']
phase_t = pg['Phase']
attachment_t = pg['Attachment']
step_stack_t = pg['Step stack']
fixture_recording_t = pg['Fixture recording']
step_fixture_t = pg['Step fixture']
parametrized_scenario_t = pg['Parametrized scenario']
parameter_table_t = pg['Parameter table']
report_t = pg['Report']
parameter_coloring_t = pg['Parameter coloring']

adopt_pytest_given = story(
    'Adopt pytest-given',
    [
        # 1 — honest gap: nothing implements elicitation.
        activity(domain_expert, 'tells', story_t, 'to the', developer),
        # 2
        activity(developer, 'captures', story_t, 'as', activity_t),
        # 3
        activity(developer, 'builds', glossary_t, 'with the', domain_expert),
        # 4
        activity(
            agent, 'writes', scenario_t, 'with', tag_t, 'against the', glossary_t
        ),
        # 5
        activity(agent, 'narrates', step_t, 'with a', phase_t),
        # 6
        activity(agent, 'attaches', attachment_t, 'to a', step_t),
        # 7
        activity(collector_t, 'records', step_t, 'on the', step_stack_t),
        # 8
        activity(
            collector_t,
            pg['Graft']('grafts'),
            fixture_recording_t,
            'from a',
            step_fixture_t,
        ),
        # 9
        activity(
            collector_t,
            pg['Group']('groups'),
            parametrized_scenario_t,
            'into a',
            parameter_table_t,
        ),
        # 10
        activity(renderer_t, 'renders', report_t, 'with', parameter_coloring_t),
        # 11 — honest gap: review is a human activity.
        activity(domain_expert, 'reviews', scenario_t, 'in the', report_t),
    ],
)
