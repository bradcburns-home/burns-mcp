"""Unit tests for burns_mcp errors and author resolution."""

from __future__ import annotations

import json
from pathlib import Path

from burns_mcp.authors import load_registered_agent_slugs, resolve_author
from burns_mcp.errors import (
    McpServiceError,
    format_three_layer_error,
    format_three_layer_error_json,
    sanitize_text,
)


def test_format_three_layer_error_json():
    json_str = format_three_layer_error_json("Bad input", "Pass valid number", retryable=False)
    data = json.loads(json_str)
    assert data["status"] == "error"
    assert data["error"] == "Bad input"
    assert data["guidance"]["next_action"] == "Pass valid number"
    assert data["guidance"]["retryable"] is False
    raw = "Failed connecting to postgresql://plaid_svc:supersecret123@localhost:5432/db with password=my_db_pass"
    sanitized = sanitize_text(raw)
    assert "supersecret123" not in sanitized
    assert "my_db_pass" not in sanitized
    assert "[REDACTED]" in sanitized

    bearer = "Header Authorization: Bearer bgw_123456789abcdef"
    assert "123456789abcdef" not in sanitize_text(bearer)


def test_mcp_service_error_serialization():
    err = McpServiceError(
        error="Invalid parameter value",
        guidance="Fix the parameter format to YYYY-MM-DD",
        retryable=False,
        error_type="ValidationFailed",
        detail="Target date 'bad' could not be parsed",
    )
    d = err.to_dict()
    assert d["status"] == "error"
    assert d["error"] == "Invalid parameter value"
    assert d["guidance"]["retryable"] is False
    assert d["guidance"]["next_action"] == "Fix the parameter format to YYYY-MM-DD"
    assert d["diagnostic"]["error_type"] == "ValidationFailed"
    assert d["diagnostic"]["trace_id"].startswith("err_")
    assert d["diagnostic"]["timestamp"] is not None

    parsed = json.loads(err.to_json())
    assert parsed == d


def test_format_three_layer_error_with_exception():
    try:
        raise ValueError("Cannot divide by zero in password=plaintext_secret")
    except Exception as e:
        res = format_three_layer_error(
            "Mathematical computation failed",
            "Verify divisor is non-zero",
            exc=e,
            include_traceback=True,
        )
        assert res["status"] == "error"
        assert res["error"] == "Mathematical computation failed"
        assert res["diagnostic"]["error_type"] == "ValueError"
        assert "plaintext_secret" not in res["diagnostic"]["detail"]
        assert "traceback" in res["diagnostic"]
        assert "plaintext_secret" not in res["diagnostic"]["traceback"]


def test_author_resolution_special_principals():
    slugs = {"savoy", "doctor"}
    author, err = resolve_author("cursor", slugs, registry_loaded=True)
    assert author == "agent:cursor"
    assert err is None

    author, err = resolve_author("brad", slugs, registry_loaded=True)
    assert author == "human:brad"
    assert err is None

    author, err = resolve_author("human:brad", slugs, registry_loaded=True)
    assert author == "human:brad"
    assert err is None


def test_author_resolution_registered_agent():
    slugs = {"savoy", "doctor"}
    author, err = resolve_author("savoy", slugs, registry_loaded=True)
    assert author == "agent:savoy"
    assert err is None

    author, err = resolve_author("agent:doctor", slugs, registry_loaded=True)
    assert author == "agent:doctor"
    assert err is None


def test_author_resolution_unknown_agent_rejected():
    slugs = {"savoy", "doctor"}
    author, err = resolve_author("rogue_agent", slugs, registry_loaded=True)
    assert author is None
    assert err["status"] == "error"
    assert err["diagnostic"]["error_type"] == "UnknownAuthorError"
    assert "savoy" in err["guidance"]["next_action"]


def test_author_resolution_empty_rejected():
    slugs = {"savoy", "doctor"}
    author, err = resolve_author("", slugs, registry_loaded=True)
    assert author is None
    assert err["diagnostic"]["error_type"] == "AuthorRequiredError"


def test_author_resolution_registry_unloaded_fails_closed():
    author, err = resolve_author("savoy", set(), registry_loaded=False, fail_closed=True)
    assert author is None
    assert err["diagnostic"]["error_type"] == "RegistryUnavailableError"
    assert err["guidance"]["retryable"] is True


def test_load_registered_agent_slugs(tmp_path: Path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    savoy_dir = agents_dir / "savoy"
    savoy_dir.mkdir()
    (savoy_dir / "agent.yaml").write_text("name: savoy\ndescription: Travel\n")

    doc_dir = agents_dir / "doctor"
    doc_dir.mkdir()
    (doc_dir / "agent.yaml").write_text("name: 'Doctor'\n")

    slugs, loaded = load_registered_agent_slugs(agents_dir)
    assert loaded is True
    assert slugs == {"savoy", "doctor"}
