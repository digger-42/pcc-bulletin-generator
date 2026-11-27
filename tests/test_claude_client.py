from unittest.mock import MagicMock, patch

from pcc_bulletin.claude_client import generate_email


def _make_mock_client(response_text: str = "Generated email") -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(type="text", text=response_text)]
    msg.stop_reason = "end_turn"
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

    mock_cls.assert_called_once_with(api_key="sk-my-key", max_retries=3)


def test_system_prompt_used():
    from pcc_bulletin.prompts import SYSTEM_PROMPT

    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client()
        generate_email("text", "key")

    call_kw = mock_cls.return_value.messages.create.call_args.kwargs
    assert call_kw["system"] == SYSTEM_PROMPT


# ── failures ─────────────────────────────────────────────────────────────────

import pytest  # noqa: E402

from pcc_bulletin.claude_client import MAX_RETRIES, ClaudeAPIError  # noqa: E402

_REQ = MagicMock()


def _status_error(cls, status):
    import anthropic

    resp = MagicMock(status_code=status, request=_REQ, headers={"request-id": "req_123"})
    return getattr(anthropic, cls)("boom", response=resp, body=None)


def _run_with(side_effect=None, message=None):
    with patch("pcc_bulletin.claude_client.anthropic.Anthropic") as mock_cls:
        if side_effect is not None:
            mock_cls.return_value.messages.create.side_effect = side_effect
        else:
            mock_cls.return_value.messages.create.return_value = message
        return generate_email("text", "key")


def test_server_error_after_retries():
    with pytest.raises(ClaudeAPIError) as exc:
        _run_with(side_effect=_status_error("InternalServerError", 529))
    text = str(exc.value)
    assert "HTTP status: 529" in text
    assert "req_123" in text
    assert f"after {MAX_RETRIES} retries" in text


def test_auth_error_not_described_as_retried():
    with pytest.raises(ClaudeAPIError) as exc:
        _run_with(side_effect=_status_error("AuthenticationError", 401))
    assert "HTTP status: 401" in str(exc.value)
    assert "retries" not in str(exc.value)


def test_connection_error():
    import anthropic

    with pytest.raises(ClaudeAPIError) as exc:
        _run_with(side_effect=anthropic.APIConnectionError(request=_REQ))
    assert "APIConnectionError" in str(exc.value)
    assert "retries" in str(exc.value)


def test_non_status_sdk_error():
    import anthropic

    with pytest.raises(ClaudeAPIError) as exc:
        _run_with(side_effect=anthropic.AnthropicError("weird"))
    assert "weird" in str(exc.value)


def _msg(stop_reason="end_turn", blocks=None):
    msg = MagicMock()
    msg.stop_reason = stop_reason
    msg.content = blocks
    return msg


def test_truncated_response():
    with pytest.raises(ClaudeAPIError, match="cut off"):
        _run_with(message=_msg("max_tokens", [MagicMock(type="text", text="half")]))


def test_refusal():
    with pytest.raises(ClaudeAPIError, match="declined"):
        _run_with(message=_msg("refusal", []))


def test_empty_content():
    with pytest.raises(ClaudeAPIError, match="no text"):
        _run_with(message=_msg("end_turn", None))


def test_blank_text():
    with pytest.raises(ClaudeAPIError, match="no text"):
        _run_with(message=_msg("end_turn", [MagicMock(type="text", text="  \n")]))


def test_joins_text_blocks_and_skips_others():
    blocks = [
        MagicMock(type="thinking", text="ignore"),
        MagicMock(type="text", text="Hello "),
        MagicMock(type="text", text="world"),
    ]
    assert _run_with(message=_msg("end_turn", blocks)) == "Hello world"
