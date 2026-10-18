# Citations in documents

A citation links a Markdown document, such as a design spec, to a scenario, tag or story in the HTML report. It ties the document's prose to the code and shows the rules it describes at work.

Citations are optional. Add them only where the user asks for them. This guide keeps them right once a document uses them. The `pytest-given-citing` skill covers how to write and repair them.

## Where a document cites

- The cited scenario must not contradict the prose that cites it.
- A passage that cites must cover all the logic it describes: cite every case, not just one.
- If the project has a glossary, the passage uses its terms consistently, as the cited scenarios do.

## Changing a cited scenario

Run `pytest-given citations check`. A renamed test, a reworded title, or reworded steps under a narrated citation change their citations. The `pytest-given-citing` skill handles its citation findings. A changed step body under the same narration changes none: reread each sentence that `citations check --covering <node ID>` lists.
