"""Unit tests for the competitor & ablation benchmark subsystem."""

import json
from pathlib import Path
import pytest

from ai_service.benchmark.checkpoint import BenchmarkCheckpointManager
from ai_service.benchmark.competitors.config import (
    COMPETITOR_PRESETS,
    CompetitorConfig,
    get_competitor_config,
)
from ai_service.benchmark.competitors.key_rotator import APIKeyRotator, parse_keys
from ai_service.benchmark.competitors.matrix import CompetitorMatrixGenerator, format_score_cell
from ai_service.benchmark.competitors.simulators import extract_json_from_text, normalize_issues
from ai_service.benchmark.scorer import TestCaseScore


def test_parse_keys():
    """Verify comma/semicolon/whitespace parsing for API key strings."""
    assert parse_keys("key1,key2,key3") == ["key1", "key2", "key3"]
    assert parse_keys(" keyA ; keyB , keyC ") == ["keyA", "keyB", "keyC"]
    assert parse_keys("") == []
    assert parse_keys(None) == []


@pytest.mark.asyncio
async def test_key_rotator():
    """Verify round-robin rotation and lock safety."""
    rotator = APIKeyRotator("TestService", ["key_alpha", "key_beta", "key_gamma"])
    assert rotator.key_count == 3
    assert rotator.get_current_key() == "key_alpha"

    next_key = await rotator.rotate("rate limit test")
    assert next_key == "key_beta"
    assert rotator.get_current_key() == "key_beta"

    next_key = await rotator.rotate("second limit")
    assert next_key == "key_gamma"

    # Wrap-around
    next_key = await rotator.rotate("wrap around")
    assert next_key == "key_alpha"


def test_competitor_presets():
    """Verify all 5 competitor configurations match the research specification."""
    expected_ids = ["B1", "B2", "A1", "A2", "A3"]
    assert list(COMPETITOR_PRESETS.keys()) == expected_ids

    # B1: Raw Diff Only, Single Gemini, Gate Disabled
    b1 = COMPETITOR_PRESETS["B1"]
    assert b1["kb_mode"] == "none"
    assert b1["llm_arch"] == "single_gemini"
    assert b1["conv_gate_enabled"] is False

    # B2: Chroma Only, Dual LLM, Gate Enabled
    b2 = COMPETITOR_PRESETS["B2"]
    assert b2["kb_mode"] == "chroma_only"
    assert b2["llm_arch"] == "dual_llm"
    assert b2["conv_gate_enabled"] is True

    # A1: Neo4j Only, Dual LLM, Gate Enabled
    a1 = COMPETITOR_PRESETS["A1"]
    assert a1["kb_mode"] == "neo4j_only"
    assert a1["llm_arch"] == "dual_llm"
    assert a1["conv_gate_enabled"] is True

    # A2: Dual KB, Worker Only (Llama-70B), Gate Enabled
    a2 = COMPETITOR_PRESETS["A2"]
    assert a2["kb_mode"] == "dual"
    assert a2["llm_arch"] == "worker_only"
    assert a2["conv_gate_enabled"] is True

    # A3: Dual KB, Orch Only (Gemini 2.0), Gate Enabled
    a3 = COMPETITOR_PRESETS["A3"]
    assert a3["kb_mode"] == "dual"
    assert a3["llm_arch"] == "orch_only"
    assert a3["conv_gate_enabled"] is True


def test_competitor_config_factory(tmp_path):
    """Verify factory instantiation with custom and environment paths."""
    cfg = get_competitor_config(
        "B1",
        results_dir=tmp_path / "results",
        repos_dir=tmp_path / "repos",
        sample_size=5,
        gemini_keys=["test_gemini_1", "test_gemini_2"],
        groq_keys=["test_groq_1"],
    )
    assert cfg.config_id == "B1"
    assert cfg.sample_size == 5
    assert len(cfg.gemini_keys) == 2
    assert len(cfg.groq_keys) == 1
    assert cfg.checkpoint_file == tmp_path / "results" / "competitors" / "checkpoints" / "checkpoint_B1.json"


def test_extract_json_from_text():
    """Verify robust extraction of JSON from Markdown code blocks or plain text."""
    # Markdown json block
    sample1 = '```json\n{"verdict": "SUGGEST", "issues": [{"title": "SQLi"}]}\n```'
    parsed1 = extract_json_from_text(sample1)
    assert parsed1["verdict"] == "SUGGEST"
    assert len(parsed1["issues"]) == 1

    # Mixed prose with braces
    sample2 = 'Here is the analysis:\n{"verdict": "ACCEPT", "issues": []}\nHope that helps!'
    parsed2 = extract_json_from_text(sample2)
    assert parsed2["verdict"] == "ACCEPT"
    assert parsed2["issues"] == []

    # Empty string
    parsed3 = extract_json_from_text("")
    assert parsed3["verdict"] == "ACCEPT"


def test_normalize_issues():
    """Verify issue dictionary normalization into BenchmarkScorer schema."""
    raw = [
        {"title": "Buffer Overflow", "severity": "Critical", "category": "security_defect", "line": "42"},
        {"title": "Missing docstring", "severity": "low", "category": "style_violation", "line": 15},
    ]
    norm = normalize_issues(raw, changed_files=["src/main.c"])
    assert len(norm) == 2
    assert norm[0]["severity"] == "error"
    assert norm[0]["category"] == "security"
    assert norm[0]["line"] == 42
    assert norm[0]["file_path"] == "src/main.c"

    assert norm[1]["severity"] == "info"
    assert norm[1]["category"] == "convention"
    assert norm[1]["line"] == 15


def test_matrix_generator_structure(tmp_path):
    """Verify matrix generator produces complete 6-row matrix matching user specification."""
    matrix_gen = CompetitorMatrixGenerator(tmp_path)
    rows = matrix_gen.generate_matrix()

    # 5 competitors + 1 GitAmi reference = 6 rows
    assert len(rows) == 6

    config_ids = [r["Configuration ID"] for r in rows]
    assert config_ids == ["B1", "B2", "A1", "A2", "A3", "GitAmi (Proposed)"]

    for r in rows:
        assert "Knowledge Base" in r
        assert "LLM Architecture" in r
        assert "Conv. Gate" in r
        assert "Martian (5-Case Pilot FI)" in r
        assert "Martian (Full 50 PRs)" in r
        assert "VulnGym (393 Cases, 596 Vulns)" in r

    md = matrix_gen.render_markdown(rows)
    assert "| **B1** |" in md
    assert "| **B2** |" in md
    assert "| **A1** |" in md
    assert "| **A2** |" in md
    assert "| **A3** |" in md
    assert "| **GitAmi (Proposed)** |" in md


def test_independent_checkpoints(tmp_path):
    """Verify checkpoints for different configs remain completely isolated."""
    cp_b1 = tmp_path / "checkpoints" / "checkpoint_B1.json"
    cp_b2 = tmp_path / "checkpoints" / "checkpoint_B2.json"

    mgr_b1 = BenchmarkCheckpointManager(cp_b1)
    mgr_b2 = BenchmarkCheckpointManager(cp_b2)

    score_b1 = TestCaseScore(
        case_id="case_1",
        dataset_name="martian",
        true_positives=1,
        false_positives=0,
        false_negatives=0,
        precision=1.0,
        recall=1.0,
        f1_score=1.0,
    )

    mgr_b1.record_case_score(score_b1)

    assert mgr_b1.completed_count == 1
    assert mgr_b2.completed_count == 0  # B2 remains pristine!
