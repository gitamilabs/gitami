"""Unit tests for modular AI system prompts."""

import pytest
from src.prompts import (
    PROMPT_MODULES,
    get_prompt,
    get_prompt_info,
    list_prompts,
    update_prompt,
    reset_prompt,
)


def test_all_prompts_registered():
    expected_keys = [
        "react_agent",
        "chat_synthesis",
        "context_compressor",
        "tool_planner",
        "pr_orchestrator",
        "pr_worker",
        "pr_reviewer_worker",
        "fixer_orchestrator",
        "fixer_worker",
    ]
    assert len(PROMPT_MODULES) == 9
    for key in expected_keys:
        assert key in PROMPT_MODULES


def test_list_prompts_returns_all_metadata():
    prompts = list_prompts()
    assert len(prompts) == 9
    for p in prompts:
        assert "key" in p
        assert "title" in p
        assert "description" in p
        assert "prompt" in p
        assert "default_prompt" in p
        assert "is_customized" in p
        assert len(p["prompt"]) > 10
        assert len(p["description"]) > 5


def test_get_prompt_valid_and_invalid():
    react_prompt = get_prompt("react_agent")
    assert "GitAmi ReAct Agent" in react_prompt

    # Invalid key returns fallback
    fallback = get_prompt("non_existent_key", default="fallback_val")
    assert fallback == "fallback_val"


def test_get_prompt_info():
    info = get_prompt_info("react_agent")
    assert info is not None
    assert info["key"] == "react_agent"
    assert info["title"] == "ReAct Agent Reasoning Loop"
    assert not info["is_customized"]

    # Non-existent
    assert get_prompt_info("unknown_key") is None


def test_update_and_reset_prompt():
    test_key = "context_compressor"
    original_info = get_prompt_info(test_key)
    assert original_info is not None
    original_text = original_info["prompt"]

    custom_text = "Custom compression test prompt text 12345."
    try:
        # Update prompt
        updated_info = update_prompt(test_key, custom_text)
        assert updated_info is not None
        assert updated_info["prompt"] == custom_text
        assert updated_info["is_customized"] is True
        assert get_prompt(test_key) == custom_text

        # Reset prompt
        reset_info = reset_prompt(test_key)
        assert reset_info is not None
        assert reset_info["prompt"] == original_text
        assert reset_info["is_customized"] is False
        assert get_prompt(test_key) == original_text
    finally:
        # Ensure reset even if test assertions fail
        reset_prompt(test_key)
