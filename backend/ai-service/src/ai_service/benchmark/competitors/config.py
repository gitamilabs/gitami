"""Configuration and presets for competitor and ablation benchmark runs."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from typing import Any, Dict, List, Literal, Optional

from ai_service.benchmark.competitors.key_rotator import parse_keys

KBMode = Literal["none", "chroma_only", "neo4j_only", "dual"]
LLMArch = Literal["single_gemini", "dual_llm", "worker_only", "orch_only"]


@dataclass
class CompetitorConfig:
    """Configuration for a specific competitor or ablation benchmark system."""

    config_id: str
    name: str
    kb_mode: KBMode
    llm_arch: LLMArch
    conv_gate_enabled: bool

    # Descriptions matching user research specification
    kb_label: str
    llm_label: str
    gate_label: str

    # Paths
    repos_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("BENCHMARK_REPOS_DIR", "./benchmark_repos")
        )
    )
    results_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("BENCHMARK_RESULTS_DIR", "./benchmark_results")
        )
    )

    # Runtime options
    sample_size: Optional[int] = None
    resume: bool = False
    inter_case_delay: float = 1.5
    cleanup_kb: bool = True
    branch: str = "benchmark_competitors"
    repo_id_prefix: str = "benchmark_comp_"

    # Line distance tolerance & text similarity threshold (same as main benchmark)
    match_line_tolerance: int = 15
    match_text_threshold: float = 0.35

    # API keys for rotation
    gemini_keys: List[str] = field(default_factory=list)
    groq_keys: List[str] = field(default_factory=list)

    @property
    def competitor_dir(self) -> Path:
        return self.results_dir / "competitors"

    @property
    def checkpoint_file(self) -> Path:
        return self.competitor_dir / "checkpoints" / f"checkpoint_{self.config_id}.json"

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist on disk."""
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        (self.competitor_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        (self.competitor_dir / "reports").mkdir(parents=True, exist_ok=True)
        (self.competitor_dir / "matrix").mkdir(parents=True, exist_ok=True)
        (self.repos_dir / "diff_cache").mkdir(parents=True, exist_ok=True)


# Presets for the 5 benchmarked competitors / ablations
COMPETITOR_PRESETS: Dict[str, Dict[str, Any]] = {
    "B1": {
        "config_id": "B1",
        "name": "Baseline 1: Standard LLM (Raw Diff Only)",
        "kb_mode": "none",
        "llm_arch": "single_gemini",
        "conv_gate_enabled": False,
        "kb_label": "None (Raw Diff Only)",
        "llm_label": "Single (Gemini 2.0 Flash)",
        "gate_label": "Disabled",
    },
    "B2": {
        "config_id": "B2",
        "name": "Baseline 2: Vector RAG Only",
        "kb_mode": "chroma_only",
        "llm_arch": "dual_llm",
        "conv_gate_enabled": True,
        "kb_label": "ChromA (Only)",
        "llm_label": "Dual-LLM",
        "gate_label": "Enabled",
    },
    "A1": {
        "config_id": "A1",
        "name": "Ablation 1: Graph Only (No Vector)",
        "kb_mode": "neo4j_only",
        "llm_arch": "dual_llm",
        "conv_gate_enabled": True,
        "kb_label": "Neo4j Only (No Vector)",
        "llm_label": "Dual-LLM",
        "gate_label": "Enabled",
    },
    "A2": {
        "config_id": "A2",
        "name": "Ablation 2: Worker Only (Llama-70B)",
        "kb_mode": "dual",
        "llm_arch": "worker_only",
        "conv_gate_enabled": True,
        "kb_label": "Dual KB (Neo4j + Chroma)",
        "llm_label": "Worker Only (Llama-70B)",
        "gate_label": "Enabled",
    },
    "A3": {
        "config_id": "A3",
        "name": "Ablation 3: Orchestrator Only (Gemini 2.0)",
        "kb_mode": "dual",
        "llm_arch": "orch_only",
        "conv_gate_enabled": True,
        "kb_label": "Dual KB (Neo4j + Chroma)",
        "llm_label": "Orch. Only (Gemini 2.0)",
        "gate_label": "Enabled",
    },
}


def get_competitor_config(
    config_id: str,
    repos_dir: Optional[Path] = None,
    results_dir: Optional[Path] = None,
    sample_size: Optional[int] = None,
    resume: bool = True,
    inter_case_delay: float = 1.5,
    cleanup_kb: bool = True,
    gemini_keys: Optional[List[str]] = None,
    groq_keys: Optional[List[str]] = None,
) -> CompetitorConfig:
    """Factory creating a CompetitorConfig initialized with environment or custom keys."""
    norm_id = config_id.upper().strip()
    if norm_id not in COMPETITOR_PRESETS:
        raise ValueError(
            f"Unknown competitor configuration ID '{config_id}'. Must be one of: {list(COMPETITOR_PRESETS.keys())}"
        )

    preset = COMPETITOR_PRESETS[norm_id]

    # Resolve Gemini keys: custom -> env GEMINI_API_KEYS -> env GEMINI_API_KEY / GOOGLE_API_KEY
    resolved_gemini_keys = list(gemini_keys or [])
    if not resolved_gemini_keys:
        env_keys = parse_keys(os.environ.get("GEMINI_API_KEYS", ""))
        single = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if single and single not in env_keys:
            env_keys.insert(0, single)
        resolved_gemini_keys = env_keys

    # Resolve Groq keys: custom -> env GROQ_API_KEYS -> env GROQ_API_KEY
    resolved_groq_keys = list(groq_keys or [])
    if not resolved_groq_keys:
        env_groq = parse_keys(os.environ.get("GROQ_API_KEYS", ""))
        single_groq = os.environ.get("GROQ_API_KEY")
        if single_groq and single_groq not in env_groq:
            env_groq.insert(0, single_groq)
        resolved_groq_keys = env_groq

    cfg = CompetitorConfig(
        config_id=preset["config_id"],
        name=preset["name"],
        kb_mode=preset["kb_mode"],
        llm_arch=preset["llm_arch"],
        conv_gate_enabled=preset["conv_gate_enabled"],
        kb_label=preset["kb_label"],
        llm_label=preset["llm_label"],
        gate_label=preset["gate_label"],
        repos_dir=repos_dir or Path(os.environ.get("BENCHMARK_REPOS_DIR", "./benchmark_repos")),
        results_dir=results_dir or Path(os.environ.get("BENCHMARK_RESULTS_DIR", "./benchmark_results")),
        sample_size=sample_size,
        resume=resume,
        inter_case_delay=inter_case_delay,
        cleanup_kb=cleanup_kb,
        gemini_keys=resolved_gemini_keys,
        groq_keys=resolved_groq_keys,
    )
    cfg.ensure_directories()
    return cfg
