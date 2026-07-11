# Domain Storytelling — the method behind stories

pytest-given's story grammar is a code-native rendition of **Domain Storytelling**, a collaborative modeling technique. Canonical reference: [domainstorytelling.org](https://domainstorytelling.org/) — the method's official home, with a quick-start guide, the Hofer/Schwentner book (*Domain Storytelling*, Addison-Wesley Signature Series), and the open-source Egon.io modeling tool. This file gives only what you need to map the method onto pytest-given; link out rather than restating it.

## The method in one paragraph

Domain experts narrate a **concrete case** ("Carol books rooms for her team", not "users can book rooms") while a moderator records it live as **pictographic sentences** — actor, activity, work object — numbered in sequence. The group validates by replaying the recorded story back: misunderstandings surface immediately, because a wrong sentence reads wrong. The output is shared domain understanding and, as a by-product, the domain's vocabulary.

## Core concepts

- **Actors** — people, roles, or systems that *do* something (an organizer, a booking system). An actor appears once; the story flows through it.
- **Work objects** — the things actors work *with* and pass around: documents, items, information (a booking, a payment, a confirmation).
- **Activities** — the verbs connecting an actor to work objects; numbered, forming the story's sequence.
- **Granularity** — stories exist at levels: coarse-grained (a whole process, for overview) down to fine-grained (one step's detail). Pick one level per story; don't mix.
- **As-is vs to-be** — a story records either how work happens today or how it should happen after the change. Label which.

## Mapping onto pytest-given

| Domain Storytelling | pytest-given |
|---|---|
| Actor / work object / activity verb | Glossary term kinds (`actor`, `work_object`, `verb`) |
| A recorded sentence | `activity(actor, verb('phrase'), work_object, ...)` |
| A numbered story | `story(title, [activity(...), ...])` — order is the sequence |
| Parallel / branching sentences | `path(...)` inside an activity |
| The emerging vocabulary | The glossary (see [glossaries.md](glossaries.md)) |
| "Does the software do this?" | Scenario ↔ activity coverage in the Stories tab |

The step past the method: binding scenarios (`@scenario(..., story=...)`) turns a story from a picture of shared understanding into a **claim backed by executing tests** — each activity's coverage chip says whether code demonstrably implements it.

## Greenfield workflow

1. Run Domain Storytelling sessions with stakeholders (a whiteboard or Egon.io is fine — the method works on paper).
2. Transfer the agreed stories into `story(...)` code; the glossary emerges from the activity slots (kinds inferred from positions).
3. Write scenarios against the stories as behaviour gets implemented; uncovered activities are your living backlog.

This is why a greenfield project may want stories *before* any scenarios: the domain understanding and vocabulary are established up front, and every later scenario has a place to link into.
