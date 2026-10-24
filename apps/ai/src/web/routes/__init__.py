from src.web.routes.agents import router as agents_router
from src.web.routes.chat import router as chat_router
from src.web.routes.context import router as context_router
from src.web.routes.graph import router as graph_router
from src.web.routes.health import router as health_router
from src.web.routes.ingest import router as ingest_router
from src.web.routes.pr import router as pr_router
from src.web.routes.prompts import router as prompts_router
from src.web.routes.repos import router as repos_router

all_routers = [
    health_router,
    context_router,
    prompts_router,
    repos_router,
    ingest_router,
    chat_router,
    pr_router,
    agents_router,
    graph_router,
]

__all__ = [
    "agents_router",
    "chat_router",
    "context_router",
    "graph_router",
    "health_router",
    "ingest_router",
    "pr_router",
    "prompts_router",
    "repos_router",
    "all_routers",
]
