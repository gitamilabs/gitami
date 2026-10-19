import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.llm_client import DualLLMClient
from src.context import ContextAuthorizer, ContextEngine, ContextRequest, StaticAuthResolver
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Standardized result wrapper across all Gitami agents."""
    agent_name: str
    status: str  # "completed", "failed", "requires_approval"
    summary: str
    confidence: float = 1.0  # 0.0 to 1.0
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0


def clean_json_text(text: str) -> str:
    """Strips markdown code block markers and trims whitespace for JSON parsing."""
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0]
    return cleaned.strip()


def parse_llm_json(raw_text: str, fallback_factory: Optional[callable] = None) -> Any:
    """Safely extracts JSON from an LLM response string."""
    if not raw_text:
        return fallback_factory() if fallback_factory else {}
    cleaned = clean_json_text(raw_text)
    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.debug(f"JSON parsing fallback notice: {e}")
        if fallback_factory:
            return fallback_factory()
        return {}


class BaseAgent:
    """
    Abstract base class providing governed context, dual-model LLM access,
    and structured lifecycle management for all Gitami agents.
    """

    def __init__(
        self,
        llm_client: Optional[DualLLMClient] = None,
        graph_client: Optional[Neo4jClient] = None,
        vector_client: Optional[VectorKBClient] = None,
    ):
        self.llm_client = llm_client or DualLLMClient()
        self.graph_client = graph_client or Neo4jClient()
        self.vector_client = vector_client or VectorKBClient()

    def get_context_engine(self, repo_id: str) -> ContextEngine:
        """Constructs an authorized ContextEngine instance for the target repository."""
        resolver = StaticAuthResolver({repo_id: {repo_id: None}})
        authorizer = ContextAuthorizer(resolver=resolver, graph_client=self.graph_client)
        return ContextEngine(
            graph_client=self.graph_client,
            vector_client=self.vector_client,
            authorizer=authorizer,
        )

    async def fetch_governed_context(
        self,
        repo_id: str,
        query: str,
        branch: str = "main",
        max_items: int = 4,
        max_tokens: int = 2500,
    ) -> List[Dict[str, Any]]:
        """Retrieves governed, scored context items from the unified intelligence layer."""
        engine = self.get_context_engine(repo_id)
        try:
            req = ContextRequest(
                project_id=repo_id,
                query=query,
                repository_ids=[repo_id],
                branch=branch,
                max_items=max_items,
                max_tokens=max_tokens,
            )
            ctx = await engine.retrieve(req)
            return [
                {
                    "title": item.title,
                    "content": item.content,
                    "file_path": item.file_path,
                    "symbol": item.symbol,
                    "type": item.type.value if hasattr(item.type, "value") else str(item.type),
                    "score": item.score,
                    "line_range": item.line_range,
                }
                for item in ctx.items
            ]
        except Exception as e:
            logger.warning(f"Error fetching governed context for {repo_id}: {e}")
            return []
