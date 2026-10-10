# Repairing a citation whose target is gone

`citations update` marked it `❓` and kept its URL and last confirmed link text. Find what it should point to now:

1. **Read the claim.** The link text is the last text the check confirmed, and the prose around it says why the document cites it. Together they are what the new target must state.
2. **Gather candidates.** `citations check` lists the closest by node id and by scenario title. Git history finds a renamed or moved test in the commit that changed it: `git log -S '<function name>'` for a function, `git log --diff-filter=R --stat` for a file. For the rest, query the report (the navigating skill's `jq` queries by narration words, term and tag); for a tag or story, list the report's tags and story titles.
3. **Verify, don't match.** Read each candidate's steps and test body. It qualifies only if it states the claim — not a similar one, and not its opposite, which a similar title often is.
4. **Repoint.** Edit only the URL's fragment, run `citations update` to write glyph, text and summary, and read the new link text against the prose around it: a reworded title can stop fitting the sentence that cites it.
5. **No candidate states the claim.** Leave the citation marked `❓` and tell the human: the behavior is gone or untested. Dropping the citation, rewriting the prose, or writing a scenario for it (the authoring skill) is their choice.

Report every repoint as old target → new target, with the evidence you used, so a human reviews the change rather than repeats the search.
