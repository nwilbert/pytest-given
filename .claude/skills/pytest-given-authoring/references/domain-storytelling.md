# Domain Storytelling, the method behind stories

pytest-given's story grammar is a code version of **Domain Storytelling**, a collaborative modeling technique. The method's official home is [domainstorytelling.org](https://domainstorytelling.org/). It has a quick-start guide, the book by Hofer and Schwentner (*Domain Storytelling*, Addison-Wesley Signature Series), and the open-source modeling tool Egon.io. This file covers only what you need to map the method onto pytest-given.

## The method in one paragraph

Domain experts tell a **concrete case** ("Carol books rooms for her team", not "users can book rooms"). A moderator records it live as **pictographic sentences** (actor, activity, work object), numbered in sequence. The group then checks the story by reading it back. Misunderstandings show up immediately, because a wrong sentence sounds wrong. The result is a shared understanding of the domain and, along the way, its vocabulary.

## Core concepts

- **Actors** are people, roles or systems that *do* something, like an organizer or a booking system. An actor appears once, and the story flows through it.
- **Work objects** are the things actors work *with* and pass around: documents, items, information. Examples are a booking, a payment or a confirmation.
- **Activities** are what an actor does. They are drawn as an arrow labelled with a verb, connecting the actor to work objects.
- **Sentences** combine an actor, an activity and its work objects. They are numbered, and their order is the story's sequence. One sentence may have several arrows under one number: an actor handing a work object to two recipients, or two actors working side by side.
- **Granularity:** stories exist at different levels, from coarse (a whole process, for an overview) to fine (the detail of one step). Pick one level per story; don't mix them. `@scenario(stories=...)` can bind a coarse and a fine story of the same flow at once. Each story is matched separately, so a step covers a sentence in each only if its narration names the terms of both sentences.
- **As-is and to-be:** a story records either how work happens today or how it should happen after the change. Say which one it is.

## Mapping onto pytest-given

| Domain Storytelling | pytest-given |
|---|---|
| Actor / work object / activity | Glossary term kinds (`actor`, `object`, `activity`) |
| A recorded sentence | `sentence(actor, activity('phrase'), work_object, ...)` |
| A numbered story | `story(title, [sentence(...), ...])`, where the order is the sequence |
| Several arrows under one number | one `clause(...)` per arrow chain inside a `sentence(...)` |
| The emerging vocabulary | The glossary (see [glossaries.md](glossaries.md)) |
| "Does the software do this?" | Scenario ↔ sentence coverage in the Stories tab |

pytest-given goes one step beyond the method. Binding scenarios with `@scenario(..., stories=...)` turns a story from a picture of shared understanding into a **claim backed by running tests**. Each sentence's coverage chip shows whether code demonstrably implements it.

## Greenfield workflow

1. Run Domain Storytelling sessions with stakeholders. A whiteboard or Egon.io is fine; the method works on paper.
2. Write the agreed stories as `story(...)` code. The glossary grows out of the clause slots, with kinds inferred from positions.
3. Write scenarios against the stories as you implement the behavior. The uncovered sentences are your living backlog.
