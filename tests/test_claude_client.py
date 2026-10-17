from unittest.mock import MagicMock, patch

from pcc_bulletin.claude_client import generate_email


def _make_mock_client(response_text: str = "Generated email") -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


def test_without_sermon_notes():
    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client("Result")
        result = generate_email("Bulletin text", "sk-test")

    assert result == "Result"
    call_kw = mock_cls.return_value.messages.create.call_args.kwargs
    assert "SERMON NOTES SUPPLEMENT" not in call_kw["messages"][0]["content"]
    assert "Bulletin text" in call_kw["messages"][0]["content"]


def test_with_sermon_notes():
    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client("Result with notes")
        result = generate_email("Bulletin text", "sk-test", sermon_notes="Notes here")

    assert result == "Result with notes"
    call_kw = mock_cls.return_value.messages.create.call_args.kwargs
    content = call_kw["messages"][0]["content"]
    assert "SERMON NOTES SUPPLEMENT" in content
    assert "Notes here" in content


def test_model_forwarded():
    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client()
        generate_email("text", "key", model="claude-special")

    call_kw = mock_cls.return_value.messages.create.call_args.kwargs
    assert call_kw["model"] == "claude-special"


def test_api_key_forwarded():
    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client()
        generate_email("text", "sk-my-key")

    mock_cls.assert_called_once_with(api_key="sk-my-key")


def test_system_prompt_used():
    from pcc_bulletin.prompts import SYSTEM_PROMPT

    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client()
        generate_email("text", "key")

    call_kw = mock_cls.return_value.messages.create.call_args.kwargs
    assert call_kw["system"] == SYSTEM_PROMPT
