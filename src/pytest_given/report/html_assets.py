"""What the HTML pages inline, so they need no server: our stylesheets and
scripts without their comments, the binary assets as `data:` URLs, and the JSON
blob `app.js` reads."""

# A session that renders no HTML never loads MarkupSafe.
__lazy_modules__ = ['markupsafe']

import base64
import json
import re
from pathlib import Path

from markupsafe import Markup

TEMPLATES_DIR = Path(__file__).parent / 'templates'


def bundled_assets(*extra_stylesheets: str) -> dict[str, Markup]:
    """The stylesheets and scripts inlined into the page — the whole reason the
    report needs no server and no external asset. The vendored Alpine bundle
    is already minified and keeps its licence line."""
    return {
        'css': Markup('').join(
            bundled_script(name) for name in ('styles.css', *extra_stylesheets)
        ),
        'app_js': bundled_script('app.js'),
        'alpine_js': Markup(
            (TEMPLATES_DIR / 'alpine.min.js').read_text(encoding='utf-8')
        ),
    }


def bundled_script(filename: str) -> Markup:
    """One of our own stylesheets or scripts, without its comments."""
    source = (TEMPLATES_DIR / filename).read_text(encoding='utf-8')
    return Markup(strip_comments(source))


BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
COMMENT_LINE = re.compile(r'^[ \t]*//.*$', re.MULTILINE)


def strip_comments(source: str) -> str:
    """Drops the block comments and the comment-only lines of our own CSS and
    JS — about a third of each file is prose meant for a maintainer, not a
    report. Every comment is replaced by the newlines it spanned, so a line
    number in a browser stack trace still points at the same line of the
    source file. A trailing `//` stays: telling it from one inside a string
    takes a tokenizer, and those notes are short. Assumes no string literal
    contains `/*` and no template literal has a line starting with `//`."""
    without_blocks = BLOCK_COMMENT.sub(
        lambda match: '\n' * match.group().count('\n'), source
    )
    return COMMENT_LINE.sub('', without_blocks)


_DATA_URL_MIME = {'.woff2': 'font/woff2', '.svg': 'image/svg+xml'}


def data_url(filename: str) -> Markup:
    """Jinja global: a binary asset under `templates/` as a `data:` URL, so
    the template names each font and the logo beside the rule that uses it.
    The files stay the only copies to update — the docs site stages its logo
    and favicon from the same SVG, see noxfile.py."""
    path = TEMPLATES_DIR / filename
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return Markup(f'data:{_DATA_URL_MIME[path.suffix]};base64,{encoded}')


def script_json_parse(value: object) -> Markup:
    """Serialize `value` as a `JSON.parse(...)` call rather than a JS object
    literal: an engine reads a JSON string faster than the equivalent source,
    and this is the largest blob on the page.

    The tokenizer-steering sequences are neutralized on the way out —
    `json.dumps` escapes neither inside a string literal, and this blob carries
    user-controlled node IDs and sentence prose.
    """
    payload = json.dumps(json.dumps(value, separators=(',', ':')))
    return Markup('JSON.parse(' + neutralize_script_data(payload) + ')')


def neutralize_script_data(text: str) -> str:
    """Escape the two sequences that let text embedded in an inline `<script>`
    steer the HTML tokenizer out of plain script-data state.

    - `</` closes the tag outright.
    - `<!--` opens script-data-*escaped* state; a `<script` after it reaches
      double-escaped state, where the template's own `</script>` no longer
      terminates the element and the rest of the document — the Alpine bundle
      included — is swallowed as script text.

    `\\/` and `\\u003C` are both valid JSON *and* JS escapes, so the blob stays
    parseable and the parsed value is unchanged, while the HTML parser sees
    neither sequence."""
    return text.replace('</', '<\\/').replace('<!--', '\\u003C!--')
