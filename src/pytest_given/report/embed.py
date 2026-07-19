import json

from markupsafe import Markup


def neutralize_script_close(text: str) -> str:
    """Replace `</` with `<\\/` so text embedded in an inline `<script>` can't
    close the tag. `\\/` is a valid JS/JSON escape for `/`, so the parsed value
    is unchanged while the HTML parser no longer sees a closing tag."""
    return text.replace('</', '<\\/')


def script_json(value: object) -> Markup:
    """Serialize `value` to JSON for embedding in an inline `<script>`, with
    `</` neutralized. `json.dumps` does not escape `</` inside string literals,
    and these blobs carry user-controlled node ids — so a parametrize id
    containing `</script>` would otherwise break out of the tag (stored XSS)."""
    return Markup(neutralize_script_close(json.dumps(value)))
