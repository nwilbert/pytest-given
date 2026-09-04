# Playwright MCP setup

Used for verifying report frontend changes (see [Report testing](../AGENTS.md#report-testing) for the rules that make it mandatory).

**Setup:** copy `.mcp.json.example` to `.mcp.json` (gitignored) to enable the server. It is deliberately not committed: opening a report needs `--allow-unrestricted-file-access`, because Playwright MCP blocks `file://` navigation entirely by default and offers no narrower scope. That flag also lets the browser read any file the user can, so it stays opt-in per developer rather than arriving with a clone. Keep the version pinned — `@latest` would resolve fresh from npm on every launch.

Known traps:

- **Chrome caches `file://` pages across a `browser_navigate` to the same path**, including a changed query or hash — so a report regenerated mid-session keeps serving the previous build and the change under test looks like it did nothing. Navigate to `about:blank` and back to force a fresh read, and confirm the fix is live (grep the page's inlined script for a string only the new build has) before concluding a behavior is broken.
- The pinned version wants its own browser build; an already-installed chromium fails at the first `browser_navigate` with `Browser "chrome-for-testing" is not installed`. Fix: `npx @playwright/mcp@<pinned-version> install-browser chrome-for-testing`.
- If the browser install hangs after the download reaches 100% (microsoft/playwright#40998 in alpha builds), switch `.mcp.json` from `--browser chromium` to `--browser chrome` to use system Chrome.
