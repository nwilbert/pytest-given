---
name: pytest-given-authoring
description: Use when writing or changing @scenario tests, glossary terms, or domain stories in a project that uses pytest-given
---

# Authoring pytest-given artifacts

pytest-given turns pytest tests into a narrated behavioral spec: `@scenario`-decorated tests with `given`/`when`/`then` steps, optionally speaking a glossary's vocabulary and linked to domain stories. The rendered report (HTML / Markdown / JSON) is only as good as the narration — these guides keep it truthful.

## Core principle

**The narration is the spec.** Write the `@scenario` name and the Given/When/Then step texts before the step bodies, then make the code fill them in. Drift can't creep in at birth when the text precedes the code.

## What to read when

Read the guide for the artifact you are about to touch — not all of them:

| Working on | Read |
|---|---|
| Decorating tests with `@scenario`, writing or editing steps | `references/scenarios.md` |
| Adding, renaming, or reorganizing glossary terms | `references/glossaries.md` |
| Writing or extending `story(...)` definitions | `references/stories.md` |
| Modeling questions (actors vs work objects, granularity), or the project's first story | `references/domain-storytelling.md` |
| Exact signatures, imports, step-text forms (t-string vs `Template`), parametrize behavior | `references/api.md` |

`references/api.md` matches the installed package version — prefer it over external docs for syntax questions. Setup tasks (installing pytest-given, enabling report output or the narration lint in CI) are out of scope for these guides; see the project README at <https://github.com/nwilbert/pytest-given>.

## When the report doesn't show what you expect

| Symptom | Read |
|---|---|
| Glossary tab is empty | `references/glossaries.md` |
| Stories tab is empty | `references/stories.md` |
| An activity never turns covered | `references/stories.md` |
| A file-scoped lint run fails where the whole suite passes | `references/scenarios.md` |

## Adoption levels

Each artifact kind stands on its own — scenarios-only is a perfectly good level — and they compound: scenarios narrate in glossary vocabulary (term refs render as kind-colored words and power per-term filtering), and stories give the actor-level view scenarios link into for coverage. Where to start depends on the project:

- **Existing codebase** — scenarios: decorate the tests that assert behavior, and let glossary terms emerge from their narration.
- **Greenfield** — consider stories first, transferring Domain Storytelling sessions with stakeholders into `story(...)` code before any scenarios exist, so domain understanding and vocabulary are established up front.
- **Glossary** — adopt an existing `GLOSSARY.md` via `FileGlossary`, or discover terms from scenarios and stories along the way.

## Verify before committing

- Render the touched scenarios and read the output as a spec — every step text must be something its body actually does: `pytest <selection> --given-md`
- If the project enables the narration lint, run it: `pytest <selection> --given-lint`. It catches structural lies (empty steps, a `then` that checks nothing); it cannot check semantic truth — that is the author's job.

Auditing someone else's narration rather than writing your own? That is the `pytest-given-reviewing` skill, which restates these rules as a review rubric.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
