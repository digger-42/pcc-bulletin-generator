import anthropic

from .prompts import SYSTEM_PROMPT

_NOTES_PREAMBLE = (
    "\n\nSERMON NOTES SUPPLEMENT (use to enrich the opening paragraph):\n"
    "The following sermon notes give you additional detail about this Sunday's message. "
    "Use them to name the speaker, identify the scripture passages to read, and describe "
    "the theme in a way that prepares and invites the reader. "
    "Weave this into the first paragraph naturally.\n\n"
)


def generate_email(
    bulletin_text: str,
    api_key: str,
    sermon_notes: str = "",
    model: str = "claude-sonnet-4-6",
) -> str:
    """Call Claude to produce the bulletin email text."""
    client = anthropic.Anthropic(api_key=api_key)

    if sermon_notes:
        user_content = f"Here is the bulletin text:\n\n{bulletin_text}{_NOTES_PREAMBLE}{sermon_notes}"
    else:
        user_content = f"Here is the bulletin text:\n\n{bulletin_text}"

    message = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text
