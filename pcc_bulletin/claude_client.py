import anthropic

from .prompts import SYSTEM_PROMPT

_NOTES_PREAMBLE = (
    "\n\nSERMON NOTES SUPPLEMENT (use to enrich the opening paragraph):\n"
    "The following sermon notes give you additional detail about this Sunday's message. "
    "Use them to name the speaker, identify the scripture passages to read, and describe "
    "the theme in a way that prepares and invites the reader. "
    "Weave this into the first paragraph naturally.\n\n"
)

# The SDK retries connection errors, 408/409/429 and 5xx responses with backoff.
MAX_RETRIES = 3


class ClaudeAPIError(RuntimeError):
    """The Claude API call failed or returned something unusable."""


def _describe(exc: Exception) -> str:
    """One-paragraph summary of an SDK exception, with status and request id if present."""
    parts = [f"{type(exc).__name__}: {exc}"]
    status = getattr(exc, "status_code", None)
    if status is not None:
        parts.append(f"HTTP status: {status}")
    request_id = getattr(exc, "request_id", None)
    if request_id:
        parts.append(f"Request id: {request_id}")
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError)) or (
        isinstance(status, int) and status >= 500
    ):
        parts.append(f"(Gave up after {MAX_RETRIES} retries.)")
    return "\n".join(parts)


def generate_email(
    bulletin_text: str,
    api_key: str,
    sermon_notes: str = "",
    model: str = "claude-sonnet-4-6",
) -> str:
    """
    Call Claude to produce the bulletin email text.

    Raises ClaudeAPIError if the call fails (after retries) or the response is
    empty, truncated, refused, or otherwise unusable.
    """
    if sermon_notes:
        user_content = (
            f"Here is the bulletin text:\n\n{bulletin_text}{_NOTES_PREAMBLE}{sermon_notes}"
        )
    else:
        user_content = f"Here is the bulletin text:\n\n{bulletin_text}"

    try:
        client = anthropic.Anthropic(api_key=api_key, max_retries=MAX_RETRIES)
        message = client.messages.create(
            model=model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AnthropicError as exc:
        raise ClaudeAPIError(_describe(exc)) from exc

    stop_reason = getattr(message, "stop_reason", None)
    if stop_reason == "max_tokens":
        raise ClaudeAPIError(
            "Claude's response was cut off at the max_tokens limit, so the email is incomplete."
        )
    if stop_reason == "refusal":
        raise ClaudeAPIError("Claude declined to generate the email (stop_reason=refusal).")

    text = "".join(
        block.text for block in (message.content or []) if getattr(block, "type", "") == "text"
    )
    if not text.strip():
        raise ClaudeAPIError(
            f"Claude returned no text (stop_reason={stop_reason}, "
            f"{len(message.content or [])} content block(s))."
        )
    return text
