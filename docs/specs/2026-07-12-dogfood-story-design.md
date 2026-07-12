# Dogfood Domain Story — Design Spec

## Goal

Narrate one domain story for pytest-given itself and bind self-report scenarios to it, resolving the "Dogfood `story(...)`" item in [TODO.md](../../TODO.md). One story — **Adopt pytest-given** — tells the greenfield adoption arc end to end: humans shape the ubiquitous language, the Agent implements it as scenarios, the plugin machinery records and renders, and the Domain Expert reviews the result. This:

- fills the empty Stories tab of the self-report and exercises scenario↔activity coverage on our own suite,
- retires 12 of the 16 dead glossary terms (opt-in `dead-term` lint rule),
- gives GLOSSARY.md terms kind pills for the first time — kind inference finally has story slots to classify from, instead of every term landing in Uncategorized.

## Background

The backend tests narrate in the project's own vocabulary via `tests/ubiquitous_language.py`, which loads `GLOSSARY.md` as a closed `FileGlossary` (`pg`). Today no backend scenario binds to a story, so:

- the self-report's Stories tab is empty;
- 16 terms trip the opt-in `dead-term` rule ("referenced by no step and no story"): Phase, when_then, Tag, Attachment, Parametrized scenario, Group, Step fixture, Plain fixture, Collector, Node ID, Step stack, Report, Renderer, Parameter coloring, Glossary, Scenario↔activity binding (baseline after the glossary-hygiene commit landed with this spec, which merged the `glossary (lowercase)` / `Glossary (capitalized)` rows into one **Glossary** term, dropped the `Uncategorized` row as a duplicate of *Kindless*, and corrected the *Coverage* definition to per-step matching);
- every GLOSSARY.md term is kindless (the file has no kind column; kinds come only from story slot positions, and there are no stories).

Coverage matching is per-step: an activity gets a badge when some step's narration term refs are a superset of the activity's refs (`A_refs ⊆ S`), or when a step pins it explicitly via `activity=`. Backend steps narrate technical terms (Term, Step, Coverage…), never "Developer", so the story's activities are covered by **explicit pins** on semantically matching scenarios — automatic matching cannot fire. Activities nothing genuinely implements stay uncovered, an honest gap (precedent: activity 7 in the hotel-booking example).

### Design decisions already made

- **One merged story, not three.** Earlier drafts had separate greenfield/legacy process stories plus a technical story. Merged: the technical activities sit naturally between "Agent writes Scenarios" and "Domain Expert reviews the Report" — that *is* the chronology of a suite run. The TODO asks for "a small domain story", singular. The legacy-stabilisation story may return later as a README narrative, not dogfood.
- **Actors are Developer, Domain Expert, Agent** (matching the planned README diagram "Agent ↔ Dev ↔ Domain Expert"), plus **Collector** and **Renderer** as system actors (precedent: Booking System in the hotel example).
- **Pin genuine matches, keep honest gaps.** No stretched pins just to show full coverage.
- **One Glossary term.** The class is the realization of the concept, the normal DDD reading — the old `glossary (lowercase)` / `Glossary (capitalized)` split existed only to keep two rows distinct under case-insensitive lookup. Merged in the glossary-hygiene commit; the story references the merged term.

## The story

Defined in `tests/ubiquitous_language.py` next to `pg`, registered on import as today. Activities auto-number 1–11; pins reference those ints.

| # | Activity (canonical prose) | Retires | Coverage |
|---|---|---|---|
| 1 | Domain Expert **tells** Story to the Developer | — | honest gap (nothing implements elicitation) |
| 2 | Developer **captures** Story as Activity | — | pin in `tests/unit/capture/test_story.py` |
| 3 | Developer **builds** Glossary with the Domain Expert | Glossary | pin in `tests/unit/capture/test_glossary.py` |
| 4 | Agent **writes** Scenario with Tag against the Glossary | Tag | pin in `tests/integration/test_plugin.py` (a tags-carrying collection scenario) |
| 5 | Agent **narrates** Step with a Phase | Phase | pin in a decorator/step test |
| 6 | Agent **attaches** Attachment to a Step | Attachment | pin in an attachment test |
| 7 | Collector **records** Step on the Step stack | Collector, Step stack | pin in `tests/unit/capture/test_collector.py` |
| 8 | Collector **grafts** Fixture recording from a Step fixture | Step fixture | pin in a fixture-recording test |
| 9 | Collector **groups** Parametrized scenario into a Parameter table | Parametrized scenario, Group | pin in `tests/unit/capture/test_template.py` |
| 10 | Renderer **renders** Report with Parameter coloring | Renderer, Report, Parameter coloring | pin in a renderer test |
| 11 | Domain Expert **reviews** Scenario in the Report | — | pin in a report/coverage test if a genuine match exists, else honest gap |

Sketch (noun/actor handle names illustrative; each is a `pg[...]` lookup from the closed `FileGlossary` over GLOSSARY.md — the `_t` suffix means "term handle" and dodges shadowing the `story`/`activity` constructors and `scenario` decorator used in the same module). **Verbs are bare `ActivityWord` strings, not glossary terms** — generic process verbs (*tells*, *captures*, *builds*, …) are story prose, not pytest-given vocabulary, and a word in a verb slot is grammatically fine. The two exceptions are `Graft` and `Group`: existing glossary rows whose meaning *is* the verb, referenced as handles with an inflection (`pg['Graft']('grafts')`). Every activity keeps at least two noun/actor term refs, so all remain coverage-eligible:

```python
domain_expert, developer, agent = pg['Domain Expert'], pg['Developer'], pg['Agent']
# … noun handles for the existing technical terms

adopt = story(
    'Adopt pytest-given',
    [
        activity(domain_expert, 'tells', story_t, 'to the', developer),
        activity(developer, 'captures', story_t, 'as', activity_t),
        activity(developer, 'builds', glossary_t, 'with the', domain_expert),
        activity(agent, 'writes', scenario_t, 'with', tag_t, 'against the', glossary_t),
        activity(agent, 'narrates', step_t, 'with a', phase_t),
        activity(agent, 'attaches', attachment_t, 'to a', step_t),
        activity(collector, 'records', step_t, 'on the', step_stack_t),
        activity(collector, pg['Graft']('grafts'), fixture_recording_t, 'from a', step_fixture_t),
        activity(collector, pg['Group']('groups'), parametrized_scenario_t, 'into a', parameter_table_t),
        activity(renderer, 'renders', report_t, 'with', parameter_coloring_t),
        activity(domain_expert, 'reviews', scenario_t, 'in the', report_t),
    ],
)
```

Path-grammar notes, all verified against `path()` validation and `kind_resolution._slot_for`:

- Every path is a valid node/edge alternation (odd length ≥ 3); connectives like `'to the'` / `'with a'` are single edge words. No standalone articles — a bare word consumes a position and would shift the following noun into a verb slot.
- Actor + noun slots are compatible (`Developer` at position 0 in most activities and position 4 in activity 1; actor wins). Only verb-vs-other slot conflicts raise.
- **Graft** and **Group** are existing GLOSSARY.md rows used in verb slots via deferred-handle inflections (`pg['Graft']('grafts')`) — kind inference classifies them as verbs; neither appears in any noun slot. All other verb slots carry bare words.

## GLOSSARY.md changes

**New "Collaboration" section** (a new pipe table; `FileGlossary` parses all tables in the file) with exactly three actor rows: **Developer** (writes the application code and, with the Agent, the scenarios), **Domain Expert** (owns the domain knowledge and the ubiquitous language; source and reviewer of stories and scenarios), **Agent** (AI coding agent authoring and maintaining scenarios alongside the Developer, guided by the pytest-given skills).

**No verb rows.** Generic process verbs (*tells*, *builds*, *reviews*, …) are bare `ActivityWord`s in the story, not glossary terms — they are story prose, not pytest-given's ubiquitous language. The plugin-operation verbs (*attach*, *record*, *render*, *narrate*) also stay out: each concept already has its noun row (Attachment — whose definition names `attach(...)` — Fixture recording, Renderer, Narration).

Kinds are not declared in the file (no kind column); inference assigns them from the story's slots: Developer / Domain Expert / Agent / Collector / Renderer → actor; Graft and Group → verb; Story, Activity, Glossary, Scenario, Tag, Step, Phase, Attachment, Step stack, Fixture recording, Step fixture, Parametrized scenario, Parameter table, Report, Parameter coloring → work object. Terms referenced only in step narration (Term, Coverage, Path, File glossary, …) stay kindless/Uncategorized — unchanged.

## Pinning mechanics

Each pinned test gets `story=adopt` on its `@scenario(...)` and `activity=N` on the **one step that genuinely demonstrates the activity**:

```python
@scenario('...', story=adopt)
def test_...():
    with when(t'... {pg["Step"]} ...', activity=7):
        ...
```

`activity=` takes an int or sequence of ints (the auto-assigned 1-based activity ids). Scenario-level `activities=` scoping is not needed — step pins alone produce coverage. Exact scenario choices are an implementation-plan concern; candidates are in the story table.

## Dead-term accounting

- Baseline (post-hygiene): 16 dead terms.
- Story references retire 12: Glossary, Tag, Phase, Attachment, Collector, Step stack, Step fixture, Parametrized scenario, Group, Renderer, Report, Parameter coloring.
- Remaining 4, deliberately: **when_then**, **Plain fixture**, **Node ID**, **Scenario↔activity binding** — negative/meta concepts that don't make honest activities. They can earn step references later; `dead-term` stays opt-in.

## Verification

- Full suite green.
- `pytest tests --given-lint=true -o 'given_lint_rules=dead-term=warn'` reports exactly the 4 remaining dead terms.
- Kind inference raises no slot conflicts (any conflict fails the suite at collection).
- `nox -s self_report` regenerates `examples/self-report/`; the Stories tab shows the story with coverage badges on the pinned activities and honest gaps on 1 (and 11 if unpinned); the Glossary tab shows the new kind pills.

## Non-goals

- No activity for the human→Agent guidance hand-off or for the implementation co-evolving with the scenarios. The guidance is already implicit in activity 4 — the Story and Glossary *are* how humans brief the Agent — and the application code's side of the loop sits outside pytest-given's bounded context. If worth recording, it belongs in the README narrative around the Agent ↔ Dev ↔ Domain Expert diagram.
- No legacy-stabilisation story (possible future README narrative, not dogfood).
- No multi-story self-report — Stories-tab multi-story parts (story filter, cross-story term reuse) remain exercised by the hotel-booking example only.
- No retirement of the 4 remaining dead terms.
- No `kind_column` in GLOSSARY.md; kinds stay inference-derived.
