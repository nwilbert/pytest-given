# Repairing a report link whose target is gone

`citations update` marked a citation `❓` and kept its URL and last confirmed link text; a plain report link keeps its author's text. Find what the link should point to now:

1. **Read the claim.** The link text and the prose around it say why the document cites the target. Together they are what the new target must state.
2. **Gather candidates.** `citations check` lists the closest by node ID and by scenario title. Git history finds a renamed or moved test in the commit that changed it: `git log -S '<function name>'` for a function, `git log --diff-filter=R --stat` for a file. For the rest, query the report (the navigating skill's `jq` queries by words, term and tag); for a tag or story, list the report's tags and story titles.
3. **Verify, don't match.** Read each candidate's steps and test body. It qualifies only if it states the claim — not a similar one, and not its opposite, which a similar title often is.
4. **Repoint.** Edit only the URL's fragment, run `citations update` to write a citation's glyph, text and summary, and read the link text against the prose around it: a reworded title can stop fitting the sentence that cites it.
5. **No candidate states the claim.** Leave the link as it is and tell the human: the behavior is gone or untested. Dropping the link, rewriting the prose, or writing a scenario for it (the authoring skill) is their choice.

Report every repoint as old target → new target, with the evidence you used, so a human reviews the change rather than repeats the search.
