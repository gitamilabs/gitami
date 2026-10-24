from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from src.web.deps import (
    close_shared_clients,
    get_shared_graph_client,
    get_shared_vector_client,
)
from src.web.routes import all_routers
from src.web.routes.chat import _compress_retrieved_context, _execute_single_tool
from src.web.routes.context import retrieve_project_context
from src.web.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    CodeExecuteRequest,
    CodePlanRequest,
    ContextApiRequest,
    DocGenerateRequest,
    IngestRequest,
    IngestUrlRequest,
    InvestigationRequest,
    IssueAnalyzeRequest,
    PRFixRequest,
    PRReviewRequest,
    PromptUpdateRequest,
    ReindexRequest,
    ToolStep,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application, cleanly handling resource cleanup."""
    yield
    await close_shared_clients()


app = FastAPI(
    title="AI Service Knowledge Base & Agent API",
    description="API for Codebase RAG Chat, Graph & Vector Search, Agent Tool Visualization, and Ingestion.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular route collections
for router in all_routers:
    app.include_router(router)

# Backward-compatibility re-exports for unit/integration tests and scripts
__all__ = [
    "app",
    "get_shared_graph_client",
    "get_shared_vector_client",
    "_execute_single_tool",
    "_compress_retrieved_context",
    "retrieve_project_context",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Citation",
    "ToolStep",
    "IngestRequest",
    "IngestUrlRequest",
    "ReindexRequest",
    "PromptUpdateRequest",
    "ContextApiRequest",
    "PRReviewRequest",
    "PRFixRequest",
    "InvestigationRequest",
    "IssueAnalyzeRequest",
    "DocGenerateRequest",
    "CodePlanRequest",
    "CodeExecuteRequest",
]
