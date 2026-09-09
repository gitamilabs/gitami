"""Integration tests for AI service Prompts and Config REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.prompts import reset_prompt, get_prompt

client = TestClient(app)


def test_api_config_endpoint():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "vector_db" in data
    assert "embedder" in data
    assert "models" in data
    assert "gemini_models" in data["models"]
    assert "groq_models" in data["models"]
    assert "primary_orchestrator" in data["models"]
    assert "worker_model" in data["models"]
    assert "storage" in data


def test_api_prompts_list():
    response = client.get("/api/prompts")
    assert response.status_code == 200
    data = response.json()
    assert "prompts" in data
    assert len(data["prompts"]) == 9
    keys = [p["key"] for p in data["prompts"]]
    assert "react_agent" in keys
    assert "tool_planner" in keys
    assert "pr_reviewer_worker" in keys


def test_api_get_single_prompt():
    # Valid key
    response = client.get("/api/prompts/react_agent")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "react_agent"
    assert "ReAct Agent" in data["title"]
    assert len(data["prompt"]) > 50

    # Invalid key
    bad_resp = client.get("/api/prompts/non_existent_key")
    assert bad_resp.status_code == 404


def test_api_update_and_reset_prompt():
    test_key = "tool_planner"
    orig_prompt = get_prompt(test_key)
    new_prompt_text = "Custom tool planner test text for API test."

    try:
        # Update valid
        update_resp = client.put(f"/api/prompts/{test_key}", json={"text": new_prompt_text})
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["status"] == "success"
        assert data["prompt"]["prompt"] == new_prompt_text
        assert data["prompt"]["is_customized"] is True

        # Verify get reflects update
        get_resp = client.get(f"/api/prompts/{test_key}")
        assert get_resp.json()["prompt"] == new_prompt_text

        # Update empty text (should 400)
        bad_empty = client.put(f"/api/prompts/{test_key}", json={"text": "   "})
        assert bad_empty.status_code == 400

        # Update non-existent key (should 404)
        bad_key = client.put("/api/prompts/unknown_xyz", json={"text": "Some text"})
        assert bad_key.status_code == 404

        # Reset prompt
        reset_resp = client.post(f"/api/prompts/{test_key}/reset")
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["status"] == "success"
        assert reset_data["prompt"]["prompt"] == orig_prompt
        assert reset_data["prompt"]["is_customized"] is False
    finally:
        reset_prompt(test_key)
