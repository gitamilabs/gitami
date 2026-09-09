# Gitami Test Suites

This directory contains test suites for the Gitami platform.

## Structure

- `e2e/`: End-to-end browser tests written in Python using Selenium WebDriver and pytest. These tests validate the Next.js frontend (`apps/web`), authentication routing, repository views, chat interfaces, and graph visualizations.
- `apps/ai/tests/`:
  - `unit/`: Fast, hermetic unit tests for the V1 indexing pipeline, snapshot engine, AST extractors, graph indexer, decision engine, blast radius, and vector store adapters.
  - `integration/`: Integration tests testing full pipeline flows, PR evaluation agent cycles, and multi-service workflows.
- `apps/ai/scripts/`: Developer utility and debugging scripts (e.g. graph inspection, MCP interactive demos, knowledge graph visualization).

## Running Tests

### End-to-End Tests (E2E)
Ensure the frontend is built or dev server can start:
```bash
python tests/e2e/run_tests.py
```
Or run directly with pytest:
```bash
cd tests/e2e
uv run --with selenium --with pytest pytest -v
```

### AI Service Unit & Integration Tests
```bash
cd apps/ai
uv run pytest
```
Run only unit tests:
```bash
uv run pytest tests/unit/
```
Run only integration tests:
```bash
uv run pytest tests/integration/
```
