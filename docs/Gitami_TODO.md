# Gitami — Product & Engineering TODO

> Goal: evolve Gitami from the current repository-centric AI code review prototype into a project-centric software maintenance platform with a shared Intelligence Layer powering agents and chat.

---

## 0. Current State / Baseline

- [ ] Document the current Gitami architecture.
- [ ] Document current frontend architecture.
- [ ] Document current Bun/API service architecture.
- [ ] Document current Python/AI service architecture.
- [ ] Document current Neo4j schema.
- [ ] Document current vector database schema.
- [ ] Document current repository indexing flow.
- [ ] Document current PR evaluation flow.
- [ ] Document current MCP functionality.
- [ ] Add integration tests around the existing PR review flow.
- [ ] Add integration tests around the existing indexing flow.
- [ ] Record known technical debt and current limitations.

---

# 1. Repository / Monorepo Structure

## 1.1 Monorepo Migration

- [ ] Decide and document monorepo conventions.
- [ ] Add Turborepo for JS/TS workspace management.
- [ ] Move Next.js frontend to `apps/web`.
- [ ] Move Bun API service to `apps/api`.
- [ ] Keep Python services/workers independently managed with `uv`.
- [ ] Move shared TypeScript code to `packages/`.
- [ ] Create `packages/contracts`.
- [ ] Create `packages/ui` for shared UI components where useful.
- [ ] Create `packages/github` for shared GitHub integration logic where useful.
- [ ] Create `packages/config` for shared configuration.
- [ ] Add root development scripts.
- [ ] Add lint/typecheck/test/build tasks.
- [ ] Configure Turborepo caching.
- [ ] Update CI for the new monorepo structure.
- [ ] Update Docker/deployment configuration.
- [ ] Update documentation.

## 1.2 Python Structure

- [ ] Establish clean Python package structure.
- [ ] Separate API code from worker/indexer code.
- [ ] Create `indexer` package.
- [ ] Create `agents` package.
- [ ] Create `context_engine` package.
- [ ] Create `github` integration package.
- [ ] Create `model_gateway` package.
- [ ] Create shared Python domain models.
- [ ] Add Python tests for all major components.

---

# 2. Core Product Domain Model

## 2.1 Organization

- [ ] Create `Organization`.
- [ ] Create organization membership.
- [ ] Define organization roles.
- [ ] Define organization-level settings.

## 2.2 Users

- [ ] Create `User`.
- [ ] Connect GitHub identity to User.
- [ ] Store GitHub installation/account information safely.
- [ ] Define user/project access.

## 2.3 Teams

- [ ] Create `Team`.
- [ ] Create team membership.
- [ ] Support team-level project access.
- [ ] Support team ownership of repositories/services.

## 2.4 Projects

- [ ] Create `Project`.
- [ ] Make Project the primary software-system boundary.
- [ ] Allow multiple repositories under a Project.
- [ ] Add Project settings.
- [ ] Add Project-level Intelligence configuration.
- [ ] Add Project-level agent configuration.
- [ ] Add Project-level AI/model configuration.

Target hierarchy:

```text
Organization
├── Users
├── Teams
└── Projects
    ├── Repository
    ├── Repository
    └── Repository
```

---

# 3. Repository Management

- [ ] Create Repository entity.
- [ ] Connect GitHub repository to Project.
- [ ] Support multiple repositories per Project.
- [ ] Store default branch.
- [ ] Store current indexed commit SHA.
- [ ] Store GitHub repository metadata.
- [ ] Store repository indexing status.
- [ ] Support repository disconnect/removal.
- [ ] Support repository reconfiguration.
- [ ] Respect GitHub repository permissions.
- [ ] Prevent unauthorized cross-repository context access.

---

# 4. Repository Indexing System

## 4.1 Indexing Architecture

- [ ] Create `IndexJob`.
- [ ] Create `RepositoryIndexState`.
- [ ] Add indexing job queue.
- [ ] Move indexing out of synchronous API requests.
- [ ] Create Index Manager.
- [ ] Create Index Worker.
- [ ] Track indexing progress.
- [ ] Track indexing errors.
- [ ] Support retrying failed indexing jobs.
- [ ] Support cancelling indexing jobs.
- [ ] Support manual reindexing.

## 4.2 Index Job Types

- [ ] `INITIAL`
- [ ] `PUSH`
- [ ] `MANUAL`
- [ ] `REINDEX`
- [ ] `SCHEMA_UPDATE`
- [ ] `PARSER_UPDATE`

## 4.3 Initial Repository Index

- [ ] Clone repository.
- [ ] Checkout target branch/commit.
- [ ] Discover repository files.
- [ ] Respect `.gitignore`.
- [ ] Detect languages.
- [ ] Detect generated files.
- [ ] Detect binary files.
- [ ] Detect configuration files.
- [ ] Detect documentation.
- [ ] Detect test files.
- [ ] Record file metadata.
- [ ] Calculate file hashes.
- [ ] Record repository commit SHA.

## 4.4 Source / AST Indexing

- [ ] Select supported language parsers.
- [ ] Parse source files using AST/tree-sitter or equivalent.
- [ ] Extract files.
- [ ] Extract modules.
- [ ] Extract classes.
- [ ] Extract interfaces.
- [ ] Extract functions.
- [ ] Extract methods.
- [ ] Extract variables.
- [ ] Extract types.
- [ ] Extract enums.
- [ ] Extract imports.
- [ ] Extract exports.
- [ ] Extract decorators/annotations.
- [ ] Extract function calls.
- [ ] Extract inheritance.
- [ ] Extract interface implementation.
- [ ] Extract type relationships.
- [ ] Preserve source file and line/column locations.
- [ ] Store parser version.

## 4.5 Dependency Indexing

- [ ] Detect package manifests.
- [ ] Parse package dependencies.
- [ ] Parse internal workspace dependencies.
- [ ] Detect repository/service dependencies where possible.
- [ ] Detect API dependencies where possible.
- [ ] Detect database dependencies where possible.
- [ ] Detect queues/events where possible.
- [ ] Store dependency provenance.

## 4.6 Git History Indexing

- [ ] Index commits.
- [ ] Index commit authors.
- [ ] Index commit messages.
- [ ] Index commit timestamps.
- [ ] Index commit parents.
- [ ] Map commits to changed files.
- [ ] Map changed files to changed symbols where possible.
- [ ] Index branches where useful.
- [ ] Index tags/releases.
- [ ] Preserve commit SHA as immutable identity.

## 4.7 GitHub Metadata Indexing

- [ ] Index Pull Requests.
- [ ] Index PR authors.
- [ ] Index PR reviews.
- [ ] Index PR comments.
- [ ] Index PR labels.
- [ ] Index PR commits.
- [ ] Index Issues.
- [ ] Index Issue comments.
- [ ] Index Issue labels.
- [ ] Index Issue/PR relationships.
- [ ] Index releases.
- [ ] Index workflow runs.
- [ ] Index CI status.
- [ ] Index relevant deployment information where available.

---

# 5. Knowledge Graph

## 5.1 Graph Ontology

Define canonical node types.

### Code

- [ ] Repository
- [ ] Directory
- [ ] File
- [ ] Module
- [ ] Package
- [ ] Class
- [ ] Function
- [ ] Method
- [ ] Variable
- [ ] Type
- [ ] Interface
- [ ] Enum
- [ ] Endpoint
- [ ] Service
- [ ] Database
- [ ] Table
- [ ] Queue/Event

### Development

- [ ] Commit
- [ ] Branch
- [ ] PullRequest
- [ ] Review
- [ ] Issue
- [ ] Comment
- [ ] Release

### Operations

- [ ] CIRun
- [ ] Test
- [ ] Deployment
- [ ] Environment
- [ ] Incident
- [ ] Alert
- [ ] ErrorSignature

### Knowledge

- [ ] Document
- [ ] ADR
- [ ] Runbook
- [ ] Requirement
- [ ] ArchitectureDecision

### Organization

- [ ] User
- [ ] Team

## 5.2 Core Relationships

### Code

- [ ] `Repository CONTAINS Directory`
- [ ] `Directory CONTAINS File`
- [ ] `File DEFINES Symbol`
- [ ] `File IMPORTS File/Module`
- [ ] `Function CALLS Function`
- [ ] `Class HAS_METHOD Method`
- [ ] `Class EXTENDS Class`
- [ ] `Class IMPLEMENTS Interface`
- [ ] `Function ACCEPTS Type`
- [ ] `Function RETURNS Type`
- [ ] `Function READS Database/Table`
- [ ] `Function WRITES Database/Table`
- [ ] `Function EMITS Event`
- [ ] `Function CONSUMES Event`
- [ ] `Test TESTS Symbol`
- [ ] `Service DEPENDS_ON Service`
- [ ] `Service USES Database`

### Development

- [ ] `PR TARGETS Repository`
- [ ] `PR CONTAINS Commit`
- [ ] `PR CHANGES File`
- [ ] `PR CHANGES Symbol`
- [ ] `PR FIXES Issue`
- [ ] `PR REVIEWED_BY User`
- [ ] `Commit MODIFIES File`
- [ ] `Commit MODIFIES Symbol`
- [ ] `Issue AFFECTS Service/Symbol`
- [ ] `Issue DUPLICATE_OF Issue`
- [ ] `Issue RELATED_TO PR/Issue`
- [ ] `Release CONTAINS Commit`

### CI / Operations

- [ ] `CIRun TRIGGERED_BY Commit/PR`
- [ ] `CIRun RUNS Test`
- [ ] `CIRun FAILED_TEST Test`
- [ ] `CIRun PRODUCES ErrorSignature`
- [ ] `Deployment DEPLOYS Service`
- [ ] `Deployment CONTAINS Commit`
- [ ] `Incident AFFECTS Service`
- [ ] `Incident CAUSED_BY Deployment`
- [ ] `Incident RESOLVED_BY PR`

### Knowledge

- [ ] `Document DESCRIBES Service/Symbol`
- [ ] `ADR CONCERNS Service`
- [ ] `ADR CONSTRAINS Service/Symbol`
- [ ] `Runbook APPLIES_TO Service`
- [ ] `Requirement IMPLEMENTED_BY Symbol/Service`

### Organization

- [ ] `User MEMBER_OF Organization`
- [ ] `User MEMBER_OF Team`
- [ ] `Team OWNS Service`
- [ ] `Team OWNS Repository`
- [ ] `User OWNS/MAINTAINS Service` where appropriate

---

# 6. Graph Quality / Provenance

- [ ] Add relationship confidence.
- [ ] Add relationship provenance.
- [ ] Distinguish deterministic relationships from inferred relationships.
- [ ] Store source of every inferred relationship.
- [ ] Store parser/model version used for inference.
- [ ] Store evidence references.
- [ ] Store source file/line where applicable.
- [ ] Add timestamps.
- [ ] Add graph schema version.
- [ ] Add index version.
- [ ] Add parser version.
- [ ] Add confidence levels.
- [ ] Support explaining why an edge exists.
- [ ] Add graph validation jobs.
- [ ] Detect orphaned nodes.
- [ ] Detect invalid relationships.
- [ ] Detect duplicate entities.

---

# 7. Temporal / Versioned Graph

- [ ] Associate graph facts with repository commit/version.
- [ ] Track when relationships become valid.
- [ ] Track when relationships are removed.
- [ ] Support historical queries where needed.
- [ ] Allow investigation against historical repository state.
- [ ] Ensure incidents can be investigated using the relevant historical state.
- [ ] Define strategy for graph snapshots vs versioned relationships.
- [ ] Test historical graph reconstruction.

---

# 8. Cross-Repository Intelligence

- [ ] Allow multiple repositories under one Project.
- [ ] Give every entity a globally unique canonical ID.
- [ ] Add repository identity to graph entities.
- [ ] Detect aliases across repositories.
- [ ] Resolve cross-repository services.
- [ ] Resolve cross-repository APIs.
- [ ] Resolve shared packages.
- [ ] Resolve shared types/contracts.
- [ ] Resolve cross-repository dependencies.
- [ ] Support graph traversal across repositories.
- [ ] Support project-wide search.
- [ ] Ensure permissions are enforced across repositories.

---

# 9. Vector / Semantic Knowledge Layer

- [ ] Define what content should be embedded.
- [ ] Index README files.
- [ ] Index documentation.
- [ ] Index ADRs.
- [ ] Index runbooks.
- [ ] Index Issue descriptions/comments.
- [ ] Index PR descriptions/comments/reviews.
- [ ] Index incident information.
- [ ] Index useful code summaries.
- [ ] Chunk content appropriately.
- [ ] Store source references for every chunk.
- [ ] Store entity/project/repository associations.
- [ ] Store commit/version where relevant.
- [ ] Support deleting stale embeddings.
- [ ] Support incremental embedding updates.
- [ ] Track embedding model/version.
- [ ] Support semantic search.

---

# 10. Context Engine

Create one unified interface between Intelligence and Agents.

## 10.1 Context APIs

- [ ] `get_project_context()`
- [ ] `get_repository_context()`
- [ ] `get_code_context()`
- [ ] `get_symbol_context()`
- [ ] `get_pr_context()`
- [ ] `get_issue_context()`
- [ ] `get_ci_context()`
- [ ] `get_incident_context()`
- [ ] `get_change_impact()`
- [ ] `trace_dependencies()`
- [ ] `get_related_prs()`
- [ ] `get_related_issues()`
- [ ] `get_historical_context()`
- [ ] `find_constraints()`
- [ ] `find_owners()`
- [ ] `search_project()`

## 10.2 Graph + RAG Retrieval

- [ ] Use graph traversal to identify relevant entities.
- [ ] Use graph context to constrain semantic search.
- [ ] Retrieve relevant documents/issues/PRs.
- [ ] Retrieve exact source files/symbols.
- [ ] Retrieve relevant Git history.
- [ ] Retrieve CI evidence.
- [ ] Deduplicate retrieved context.
- [ ] Rank context by relevance.
- [ ] Attach provenance/evidence.
- [ ] Enforce authorization before returning context.
- [ ] Add token/context budgets.

---

# 11. Agent Runtime

- [ ] Create generic Agent Runtime.
- [ ] Create Agent definition/configuration.
- [ ] Create AgentRun model.
- [ ] Track agent status.
- [ ] Track agent inputs.
- [ ] Track agent outputs.
- [ ] Track agent tool calls.
- [ ] Track token/model usage.
- [ ] Track errors.
- [ ] Support retries.
- [ ] Support cancellation.
- [ ] Support human approval checkpoints.
- [ ] Store structured agent results.
- [ ] Store agent evidence/context references.

## 11.1 Tool Registry

- [ ] GitHub tools.
- [ ] Graph tools.
- [ ] Context Engine tools.
- [ ] Source retrieval tools.
- [ ] Search tools.
- [ ] Git tools.
- [ ] CI tools.
- [ ] Sandbox tools.
- [ ] Documentation tools.

---

# 12. Review Agent

- [ ] Move current PR evaluation into Agent Runtime.
- [ ] Resolve changed files.
- [ ] Resolve changed symbols.
- [ ] Calculate graph impact.
- [ ] Identify affected services.
- [ ] Identify affected tests.
- [ ] Retrieve relevant documentation.
- [ ] Retrieve related Issues.
- [ ] Retrieve related historical PRs.
- [ ] Retrieve historical incidents.
- [ ] Analyze actual source.
- [ ] Detect bugs.
- [ ] Detect regressions.
- [ ] Detect missing tests.
- [ ] Detect architecture/contract violations.
- [ ] Produce risk score.
- [ ] Produce structured findings.
- [ ] Produce evidence for each finding.
- [ ] Store review context.
- [ ] Post findings to GitHub.
- [ ] Allow human feedback on findings.
- [ ] Feed review feedback into future context where appropriate.

---

# 13. Investigation Agent

- [ ] Create Investigation Agent.
- [ ] Accept natural-language investigation query.
- [ ] Accept structured machine-triggered investigations.
- [ ] Build investigation context.
- [ ] Search graph.
- [ ] Search semantic knowledge.
- [ ] Search Git history.
- [ ] Search PRs/issues.
- [ ] Search CI.
- [ ] Identify possible root causes.
- [ ] Gather evidence.
- [ ] Assign confidence.
- [ ] Produce structured JSON output.
- [ ] Produce human-readable output.
- [ ] Produce recommended next steps.
- [ ] Produce optional solution plan.
- [ ] Support production incident trigger.

---

# 14. Issue Agent

- [ ] Trigger on new GitHub Issue.
- [ ] Detect spam.
- [ ] Classify issue.
- [ ] Detect duplicates.
- [ ] Detect severity.
- [ ] Detect affected components.
- [ ] Suggest labels.
- [ ] Link related Issues.
- [ ] Link related PRs.
- [ ] Link relevant documentation.
- [ ] Optionally run Investigation Agent.
- [ ] Generate solution plan.
- [ ] Allow human approval.
- [ ] Optionally trigger Code Agent.

---

# 15. Code Agent

- [ ] Create sandbox abstraction.
- [ ] Create isolated workspace per run.
- [ ] Clone repository into sandbox.
- [ ] Checkout requested commit/branch.
- [ ] Provide project context.
- [ ] Provide investigation/review context.
- [ ] Allow code modifications.
- [ ] Run tests.
- [ ] Run lint.
- [ ] Run type checks.
- [ ] Run project-specific checks.
- [ ] Capture command output.
- [ ] Capture changed files.
- [ ] Generate diff.
- [ ] Validate changes.
- [ ] Optionally run Review Agent.
- [ ] Create branch.
- [ ] Create PR.
- [ ] Store agent run metadata.
- [ ] Clean up sandbox.

---

# 16. Documentation Agent

- [ ] Generate project overview.
- [ ] Generate repository overview.
- [ ] Generate architecture documentation.
- [ ] Generate service documentation.
- [ ] Generate workflow documentation.
- [ ] Generate dependency documentation.
- [ ] Generate operational/runbook documentation.
- [ ] Link documentation to graph entities.
- [ ] Version generated documentation.
- [ ] Detect stale documentation.
- [ ] Regenerate affected documentation after code changes.
- [ ] Feed useful documentation back into semantic retrieval.

---

# 17. Chat

- [ ] Create Project Chat.
- [ ] Add project-scoped conversations.
- [ ] Build query router.
- [ ] Determine when direct retrieval is enough.
- [ ] Determine when Investigation Agent is needed.
- [ ] Support graph questions.
- [ ] Support semantic questions.
- [ ] Support code questions.
- [ ] Support PR questions.
- [ ] Support Issue questions.
- [ ] Support CI questions.
- [ ] Support cross-repository questions.
- [ ] Show evidence/source references.
- [ ] Show related entities.
- [ ] Allow users to launch agents from chat.
- [ ] Allow users to launch Code Agent from approved plans.

---

# 18. Model Gateway

- [ ] Create provider-independent model interface.
- [ ] Add Gitami-managed models.
- [ ] Support model selection.
- [ ] Support model-specific configuration.
- [ ] Track model usage.
- [ ] Track token usage.
- [ ] Track costs.
- [ ] Support BYOK.
- [ ] Support custom OpenAI-compatible endpoints where useful.
- [ ] Support enterprise/private model endpoints later.
- [ ] Keep Intelligence Layer independent from model provider.

---

# 19. GitHub Integration

- [ ] GitHub OAuth/App authentication.
- [ ] GitHub App installation flow.
- [ ] Repository discovery.
- [ ] Repository permission checks.
- [ ] Webhook handling.
- [ ] Push event handling.
- [ ] PR event handling.
- [ ] Issue event handling.
- [ ] Workflow/CI event handling.
- [ ] Release event handling.
- [ ] Webhook signature verification.
- [ ] Webhook idempotency.
- [ ] GitHub API rate-limit handling.
- [ ] GitHub API retry handling.

---

# 20. Incremental Reindexing

- [ ] Store last indexed commit SHA.
- [ ] Detect new commit SHA.
- [ ] Calculate `git diff` between indexed and new SHA.
- [ ] Identify added files.
- [ ] Identify modified files.
- [ ] Identify deleted files.
- [ ] Identify renamed files.
- [ ] Reparse changed files.
- [ ] Remove deleted entities.
- [ ] Update changed entities.
- [ ] Update changed relationships.
- [ ] Identify affected graph neighborhood.
- [ ] Recalculate impacted relationships.
- [ ] Re-embed changed documents only.
- [ ] Update GitHub metadata incrementally.
- [ ] Update CI metadata incrementally.
- [ ] Update index state atomically.
- [ ] Handle failed incremental indexing safely.
- [ ] Fall back to full rebuild when necessary.

---

# 21. Full Reindex / Recovery

- [ ] Support manual full reindex.
- [ ] Support parser-version-triggered rebuild.
- [ ] Support graph-schema-triggered rebuild.
- [ ] Support embedding-model-triggered rebuild.
- [ ] Detect index corruption.
- [ ] Rebuild graph from source of truth.
- [ ] Rebuild vector index from source of truth.
- [ ] Validate rebuilt index.
- [ ] Swap new index into production atomically where possible.

---

# 22. Project Dashboard

Target experience:

```text
Project
├── Overview
├── Chat
├── Repositories
├── Pull Requests
├── Issues
├── CI
├── Knowledge
├── Agents
└── Settings
```

## Overview

- [ ] Project health summary.
- [ ] Repository status.
- [ ] Open PR count.
- [ ] High-risk PR count.
- [ ] Open Issue count.
- [ ] CI failures.
- [ ] Recent deployments.
- [ ] Recent agent activity.
- [ ] Recent investigations.
- [ ] Indexing status.
- [ ] Ask Project Chat interface.

---

# 23. Agent / Automation UX

- [ ] Agent run history.
- [ ] Agent status.
- [ ] Agent result page.
- [ ] Agent evidence display.
- [ ] Agent context display.
- [ ] Human approval UI.
- [ ] Agent action confirmation.
- [ ] Agent cancellation.
- [ ] Agent retry.
- [ ] Agent logs.
- [ ] Agent usage/cost visibility.

---

# 24. Permissions / RBAC

Start simple.

Roles:

- [ ] Owner
- [ ] Admin
- [ ] Member
- [ ] Viewer

Permissions:

- [ ] View project.
- [ ] Manage project.
- [ ] Manage repositories.
- [ ] Run agents.
- [ ] Configure AI.
- [ ] Manage team.
- [ ] Manage billing.
- [ ] Manage API keys.

Rules:

- [ ] Never expose repository content beyond GitHub-authorized access.
- [ ] Enforce permissions in Context Engine.
- [ ] Enforce permissions in Chat.
- [ ] Enforce permissions in Agents.
- [ ] Enforce permissions in API.
- [ ] Enforce permissions in cross-repository retrieval.

---

# 25. API

- [ ] Design project-centric API.
- [ ] `/organizations`
- [ ] `/projects`
- [ ] `/projects/:id/repositories`
- [ ] `/projects/:id/graph`
- [ ] `/projects/:id/search`
- [ ] `/projects/:id/chat`
- [ ] `/projects/:id/agents`
- [ ] `/projects/:id/issues`
- [ ] `/projects/:id/pull-requests`
- [ ] `/projects/:id/ci`
- [ ] `/projects/:id/index`
- [ ] API authentication.
- [ ] API keys.
- [ ] API scopes.
- [ ] API rate limits.
- [ ] API usage tracking.
- [ ] API documentation.
- [ ] SDK later.

---

# 26. Billing / Usage

- [ ] Define pricing model.
- [ ] Define project limits.
- [ ] Define repository limits.
- [ ] Define AI usage limits.
- [ ] Define agent execution limits.
- [ ] Define indexing/storage limits.
- [ ] Add usage metering.
- [ ] Add billing provider.
- [ ] Add subscription management.
- [ ] Add invoices.
- [ ] Add plan enforcement.
- [ ] Add usage dashboard.
- [ ] Add enterprise billing later.

---

# 27. Observability

- [ ] API logs.
- [ ] Worker logs.
- [ ] Indexing logs.
- [ ] Agent execution logs.
- [ ] Model usage metrics.
- [ ] Queue metrics.
- [ ] Neo4j metrics.
- [ ] Vector DB metrics.
- [ ] Error tracking.
- [ ] Request tracing.
- [ ] Indexing latency metrics.
- [ ] Agent latency metrics.
- [ ] Context retrieval metrics.

---

# 28. Security

- [ ] Secure GitHub token storage.
- [ ] Encrypt sensitive credentials.
- [ ] Verify GitHub webhook signatures.
- [ ] Sandbox Code Agent execution.
- [ ] Restrict sandbox network access.
- [ ] Restrict filesystem access.
- [ ] Prevent cross-project data leakage.
- [ ] Prevent cross-organization data leakage.
- [ ] Audit agent actions.
- [ ] Audit repository access.
- [ ] Audit permission changes.
- [ ] Add secret scanning where appropriate.
- [ ] Define data retention policy.

---

# 29. Testing

## Unit

- [ ] AST extraction tests.
- [ ] Graph construction tests.
- [ ] Entity resolution tests.
- [ ] Incremental indexing tests.
- [ ] Context Engine tests.
- [ ] Agent tool tests.
- [ ] Permission tests.

## Integration

- [ ] GitHub integration.
- [ ] Neo4j integration.
- [ ] Vector DB integration.
- [ ] Indexing pipeline.
- [ ] PR review pipeline.
- [ ] Issue investigation pipeline.
- [ ] Code Agent sandbox.

## End-to-End

- [ ] Connect repository.
- [ ] Initial index.
- [ ] Ask Chat question.
- [ ] Create PR.
- [ ] Review PR.
- [ ] Create Issue.
- [ ] Investigate Issue.
- [ ] Generate code fix.
- [ ] Run tests.
- [ ] Create PR from Code Agent.
- [ ] Incremental reindex after merge.

---

# 30. Intelligence Layer Quality Metrics

- [ ] Measure graph coverage.
- [ ] Measure relationship accuracy.
- [ ] Measure graph freshness.
- [ ] Measure provenance coverage.
- [ ] Measure entity resolution accuracy.
- [ ] Measure retrieval precision.
- [ ] Measure retrieval recall.
- [ ] Measure context size.
- [ ] Measure agent answer accuracy.
- [ ] Measure false-positive review findings.
- [ ] Measure false-negative review findings.
- [ ] Track human feedback.

---

# 31. Suggested MVP Milestones

## Milestone 1 — Project Foundation

- [ ] Monorepo
- [ ] Organization
- [ ] Project
- [ ] Repository
- [ ] GitHub connection
- [ ] Basic permissions

## Milestone 2 — Project Intelligence

- [ ] Initial repository indexing
- [ ] AST graph
- [ ] Git history
- [ ] GitHub PR/Issue metadata
- [ ] Vector knowledge
- [ ] Cross-repository graph
- [ ] Incremental indexing

## Milestone 3 — Context Engine

- [ ] Project context
- [ ] Code context
- [ ] PR context
- [ ] Issue context
- [ ] CI context
- [ ] Graph + RAG retrieval
- [ ] Provenance/evidence

## Milestone 4 — Review Agent

- [ ] PR context
- [ ] Impact analysis
- [ ] Review findings
- [ ] Risk score
- [ ] GitHub integration

## Milestone 5 — Investigation Agent

- [ ] Issue investigation
- [ ] CI investigation
- [ ] Root-cause analysis
- [ ] Evidence-backed answers
- [ ] Solution plans

## Milestone 6 — Code Agent

- [ ] Sandbox
- [ ] Code modification
- [ ] Tests
- [ ] Validation
- [ ] PR creation

## Milestone 7 — Project Chat

- [ ] Project-scoped chat
- [ ] Graph queries
- [ ] Semantic queries
- [ ] Investigation routing
- [ ] Evidence display
- [ ] Agent triggers

## Milestone 8 — SaaS Platform

- [ ] Teams
- [ ] RBAC
- [ ] API keys
- [ ] Usage metering
- [ ] Billing
- [ ] Model gateway
- [ ] BYOK

---

# 32. Recommended Build Order

Prioritize in this order:

1. [ ] Monorepo cleanup
2. [ ] Organization / Project / Repository domain
3. [ ] IndexJob + repository index state
4. [ ] Production indexing pipeline
5. [ ] Canonical graph schema
6. [ ] Incremental indexing
7. [ ] Cross-repository intelligence
8. [ ] Vector/semantic indexing
9. [ ] Context Engine
10. [ ] Move existing PR reviewer onto Context Engine
11. [ ] Review Agent
12. [ ] Investigation Agent
13. [ ] Project Chat
14. [ ] Code Agent
15. [ ] Issue Agent
16. [ ] Documentation Agent
17. [ ] Teams / RBAC
18. [ ] Model Gateway / BYOK
19. [ ] API platform
20. [ ] Billing
21. [ ] Enterprise features

---

# 33. North Star Architecture

```text
                         ORGANIZATION
                              │
                              ▼
                           PROJECT
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
             REPOSITORIES             KNOWLEDGE
                  │                       │
                  └───────────┬───────────┘
                              ▼
                    PROJECT INTELLIGENCE
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
            GRAPH           VECTOR           GIT
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                       CONTEXT ENGINE
                              │
                              ▼
                        AGENT RUNTIME
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
          REVIEW        INVESTIGATION        ISSUE
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                         CODE AGENT
                              │
                              ▼
                             PR

                        PROJECT CHAT
                              │
                              ▼
                       CONTEXT ENGINE
```

---

# 34. Immediate Next Tasks

The first implementation sprint should focus only on these:

- [ ] Define `Organization`, `Project`, and `Repository`.
- [ ] Define `IndexJob` and `RepositoryIndexState`.
- [ ] Map the current indexing code into the new indexer package.
- [ ] Document the existing Neo4j schema.
- [ ] Define the v1 canonical graph ontology.
- [ ] Define what goes into Neo4j vs vector DB vs Postgres/object storage.
- [ ] Implement initial repository indexing as an asynchronous job.
- [ ] Store indexed commit SHA.
- [ ] Implement file hashing/change detection.
- [ ] Implement incremental indexing from commit A → commit B.
- [ ] Add GitHub push webhook → indexing job.
- [ ] Build the first `get_project_context()` API.
- [ ] Build the first `get_pr_context()` API.
- [ ] Move the existing PR evaluator to use the Context Engine.
- [ ] Validate the architecture with one multi-repository Project.

> **Core principle:** Build the Intelligence Layer first. Agents should consume the Intelligence Layer rather than independently building their own understanding of the repositories.
