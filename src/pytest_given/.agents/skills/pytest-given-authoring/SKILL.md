---
name: pytest-given-authoring
description: Use when writing or changing @scenario tests, glossary terms, or domain stories in a project that uses pytest-given, or converting plain pytest tests into scenarios
---

# Authoring pytest-given artifacts

pytest-given turns pytest tests into a narrated behavioral spec. Tests decorated with `@scenario` describe themselves in `given`/`when`/`then` steps. They can speak a glossary's vocabulary and link to domain stories. The rendered report (HTML, Markdown or JSON) is only as good as the narration, and these guides keep it truthful.

## Core principle

**The narration is the spec.** Write the `@scenario` name and the Given/When/Then step texts before the step bodies, then write the code to match them. When the text comes before the code, the two can't drift apart from the start.

## What to read when

Read the guide for the artifact you are about to change, not all of them:

| Working on | Read |
|---|---|
| Decorating tests with `@scenario`, writing or editing steps | `references/scenarios.md` |
| Adding, renaming, or reorganizing glossary terms | `references/glossaries.md` |
| Writing or extending `story(...)` definitions | `references/stories.md` |
| Modeling questions (actors vs work objects, granularity), or the project's first story | `references/domain-storytelling.md` |
| Exact signatures, imports, step-text forms (t-string vs `Template`), parametrize behavior | `references/api.md` |

`references/api.md` matches the installed package version, so prefer it to external docs for syntax questions. Setup tasks, like installing pytest-given or turning on report output or the narration lint in CI, are not covered here. For those, see the project documentation at <https://nwilbert.github.io/pytest-given/>.

## When the report doesn't show what you expect

| Symptom | Read |
|---|---|
| Glossary tab is empty | `references/glossaries.md` |
| Stories tab is empty | `references/stories.md` |
| A sentence never turns covered | `references/stories.md` |
| A lint run on one file fails where the whole suite passes | `references/scenarios.md` |

## Adoption levels

Each kind of artifact works on its own; using scenarios only is a perfectly good level. They also build on each other. Scenarios can narrate in glossary vocabulary, where term refs render as kind-colored words and allow filtering by term. Stories give the actor-level view that scenarios link into for coverage. Where to start depends on the project:

- **Existing codebase:** start with scenarios. Decorate the tests that assert behavior, and let glossary terms emerge from their narration.
- **New project:** consider starting with stories. Write the results of Domain Storytelling sessions with stakeholders as `story(...)` code before any scenarios exist. That establishes the domain understanding and vocabulary up front.
- **Glossary:** adopt an existing `GLOSSARY.md` with `FileGlossary`, or collect terms from scenarios and stories as you go.

## Verify before committing

- Render the scenarios you changed and read the output as a spec. Every step text must describe something its body actually does: `pytest <selection> --given-md`
- If the project uses the narration lint, run it on the whole suite: `pytest --given-lint`. A selection fails on a `given_lint_ignore` entry for a test it skips. The lint catches structural lies, such as empty steps or a `then` that checks nothing. It can't check whether the narration is true; that is the author's job.

Reviewing someone else's narration rather than writing your own? Use the `pytest-given-reviewing` skill. It restates these rules as a review rubric.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
