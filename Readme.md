# Gitami

An AI-powered software maintenance and intelligence platform featuring structural code graph indexing, semantic knowledge storage, and autonomous multi-modal review agents.

---

## 🏗️ Repository Architecture

Gitami is structured as a clean, minimal monorepo:

```
gitami/
├── apps/
│   ├── web/                # Next.js frontend (React 19, TailwindCSS)
│   ├── api/                # Bun / Hono control plane API & GitHub integrations
│   └── ai/                 # Python AI intelligence service (FastAPI, Neo4j, UV)
├── tests/
│   └── e2e/                # End-to-end browser test suite (Selenium + Pytest)
├── docs/
│   └── architecture/       # System and V1 indexing architecture specifications
├── docker-compose.yml       # Local infrastructure (Neo4j Community & PostgreSQL)
├── package.json            # Monorepo root workspace configuration
└── turbo.json              # Turborepo task pipeline configuration
```

---

## 🛠️ Prerequisites

- **Docker Desktop** (for local Neo4j & PostgreSQL)
- **Bun** runtime (`>= 1.2`)
- **UV** Python package manager (`>= 0.1.0`)
- **Node.js** (`>= 18.0`)

---

## 🚀 Quick Start Guide

### 1. Infrastructure Services (Docker)
Start Neo4j and PostgreSQL from the repository root:

```bash
docker compose up -d
```
- **Neo4j Browser:** [http://localhost:7474](http://localhost:7474) (`neo4j` / `gitamipassword`)
- **PostgreSQL:** `localhost:5432` (`gitami` / `gitamipassword`)

### 2. TypeScript Applications (`apps/web`, `apps/api`)
Install dependencies and run tasks across the monorepo via Turborepo:

```bash
# Install all workspace dependencies
bun install

# Typecheck all TypeScript projects
bun run typecheck

# Build web & api production bundles
bun run build

# Start development servers
bun run dev
```
- **Web App:** [http://localhost:3000](http://localhost:3000)
- **Control Plane API:** [http://localhost:5000](http://localhost:5000)

### 3. Python AI Intelligence Service (`apps/ai`)
The AI service is independently managed with UV:

```bash
cd apps/ai

# Configure environment
cp .env.example .env
# Fill in GEMINI_API_KEY, GROQ_API_KEY, and NEO4J credentials

# Start FastAPI server
uv run ai-service serve
```
- **AI Service API:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 💻 AI Indexing CLI

The canonical indexing pipeline is executed directly from `apps/ai`:

```bash
cd apps/ai

# Run canonical V1 repository indexing against an explicit commit
uv run ai-service index --repo-id <owner/repo> --commit HEAD --repo-dir /path/to/repo

# Validate indexing with dry-run
uv run ai-service index --repo-id <owner/repo> --commit HEAD --repo-dir /path/to/repo --validate-only

# Run pull request evaluation
uv run ai-service eval-pr --repo-id <owner/repo> --repo-dir /path/to/repo --base-ref main --head-ref pr-branch
```

---

## 🧪 Testing

### AI Service Unit & Integration Tests
```bash
cd apps/ai
uv run pytest tests/unit/
uv run pytest tests/integration/
```

### End-to-End Tests
```bash
python tests/e2e/run_tests.py
```
