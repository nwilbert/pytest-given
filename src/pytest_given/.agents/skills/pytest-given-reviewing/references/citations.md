# Reviewing citations

Citations are optional: a document without them is no finding. Where a document cites the report:

1. Run `pytest-given citations check`, and hand its citation findings to the `pytest-given-citing` skill.
2. Where a cited scenario's title or behavior changed, run `citations update`, then `citations check --covering <node ID>`. Reread each sentence it lists, unresolved links included: the claim may no longer hold.
3. Read each citing passage against its citations:
   - A cited scenario must not contradict the prose that cites it. A narrated citation's body is the behavior its document claims. A contradiction is a false claim.
   - A passage that cites must cover all the logic it describes. Citing one case and leaving out another is a finding.
   - If the project has a glossary, the passage uses its terms consistently, as the cited scenarios do.
