"""
Context Engine V1 for Gitami.

Governed retrieval and context-assembly layer sitting between
indexed project intelligence (Neo4j, VectorKB, Git, GitHub) and agents/chat.
"""

from src.context.contracts import (
    ContextItemType,
    ContextSource,
    ContextItem,
    AuthorizedScope,
    ContextBudget,
    ContextRequest,
    ProviderError,
    RetrievalMetadata,
    ContextResult,
)
from src.context.authorization import (
    AuthorizationError,
    ProjectAuthResolver,
    StaticAuthResolver,
    Neo4jAuthResolver,
    ContextAuthorizer,
)
from src.context.ranking import (
    ScoringConfig,
    DeterministicRanker,
    DEFAULT_EXACT_MATCH_SCORE,
    DEFAULT_DIRECT_DEFINITION_SCORE,
    DEFAULT_DIRECT_RELATIONSHIP_SCORE,
    DEFAULT_SEMANTIC_WEIGHT,
    DEFAULT_MULTI_HOP_SCORE,
    DEFAULT_BACKGROUND_SCORE,
)
from src.context.deduplication import ProviderAwareDeduplicator
from src.context.budgeting import ContextBudgeter
from src.context.provenance import validate_provenance, create_source
from src.context.graph_retriever import GraphRetriever
from src.context.semantic_retriever import SemanticRetriever
from src.context.source_retriever import SourceRetriever
from src.context.github_retriever import GitHubRetriever
from src.context.engine import ContextEngine

__all__ = [
    "ContextEngine",
    "ContextItemType",
    "ContextSource",
    "ContextItem",
    "AuthorizedScope",
    "ContextBudget",
    "ContextRequest",
    "ProviderError",
    "RetrievalMetadata",
    "ContextResult",
    "AuthorizationError",
    "ProjectAuthResolver",
    "StaticAuthResolver",
    "Neo4jAuthResolver",
    "ContextAuthorizer",
    "ScoringConfig",
    "DeterministicRanker",
    "ProviderAwareDeduplicator",
    "ContextBudgeter",
    "validate_provenance",
    "create_source",
    "GraphRetriever",
    "SemanticRetriever",
    "SourceRetriever",
    "GitHubRetriever",
    "DEFAULT_EXACT_MATCH_SCORE",
    "DEFAULT_DIRECT_DEFINITION_SCORE",
    "DEFAULT_DIRECT_RELATIONSHIP_SCORE",
    "DEFAULT_SEMANTIC_WEIGHT",
    "DEFAULT_MULTI_HOP_SCORE",
    "DEFAULT_BACKGROUND_SCORE",
]
