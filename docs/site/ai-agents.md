# Working with AI agents

The `with given(...)` / `with when(...)` / `with then(...)` blocks keep the *claim* about behavior directly adjacent to the code that implements it. That proximity is what makes the [people–agents–artifacts loop](index.md#why-pytest-given) work: auditing "does the code under `with when('I insert $2')` actually insert $2?" is cheaper and higher-leverage than reading raw test code, and far less prone to drift than documentation kept in separate files.

**Know what the narration is and isn't.** Narration is *auditable, not verified*: in an agentic workflow the same agent writes both the code and the claim about the code, and nothing mechanically checks that a step's text matches its body. The [narration lint](configuration/narration-lint.md) catches structural lies (an empty step, a `then` that checks nothing, a missing phase), never semantic truth. The report is worth as much as your review process's habit of reading step text against step bodies — treat it as a review aid, not as evidence.

What the agent itself gets out of it:

- **Context economy.** `pytest --given-md` renders a run's narration as Markdown to stdout — a fraction of the tokens of the test code it summarizes, useful for orienting in an unfamiliar suite or handing a run summary to a human. Combine with pytest's own selection (`-k`, `--lf`, node ids).
- **Structured queries.** `--given-json` + `jq` filter scenarios by tag, status, or glossary term.
- **A controlled vocabulary.** A `Glossary` — or a `FileGlossary` over the `GLOSSARY.md` you already keep — gives the agent a stable set of domain terms to narrate with, keeping naming consistent across sessions.
- **Early, typed errors.** Misusing a step-text form (a t-string on a decorator, a `Template` in a test body) raises `PytestGivenError` immediately with a clear message — cheap for an agent to learn from.

Adopt selectively: decorate the tests that assert behavior, and leave plumbing (trivial getters, constructors, round-trips) as plain tests — they add report noise, not signal. pytest-given's own suite decorates about a fifth of its tests. Codify your narration conventions where agents will read them; the bundled [authoring skill](https://github.com/nwilbert/pytest-given/blob/main/src/pytest_given/.agents/skills/pytest-given-authoring/SKILL.md) ships a battle-tested set of rules for keeping narration truthful.

## Agent skills

Three [Agent Skills](https://agentskills.io) ship in the wheel, under `pytest_given/.agents/skills/`:

- **`pytest-given-authoring`** — a slim router plus on-demand guides for writing truthful scenarios, glossaries, and domain stories.
- **`pytest-given-navigating`** — exploring a codebase through its rendered reports instead of grepping test bodies.
- **`pytest-given-reviewing`** — a layered review of narrated tests: the narration lint as the structural gate, a semantic audit of step text against step bodies, a completeness audit of what the report leaves out, then a hygiene pass over the glossary, tags and stories.

Two ways to get them into your repo, where Claude Code (and other harnesses following the same format) auto-discover them:

- **`pytest-given skills install`** copies them into `.claude/skills/`. The files are library-owned — reinstalling after an upgrade overwrites them (keep your own conventions in your project's instructions file), and `--check` exits 1 on drift, for a CI guard. Use `--dest` for a non-default skills directory.
- **`uvx library-skills install --claude`** — [library-skills](https://library-skills.io) scans your project's dependencies for bundled skills and links them into `.agents/skills/` (and, with `--claude`, `.claude/skills/`), so one command covers pytest-given and every other library that ships skills. Symlinks track upgrades automatically; on Windows without developer mode add `--copy`.

