# Gitami Documentation Hub

Welcome to the central documentation index for **Gitami**.

---

## 🧭 Navigation Map

```
docs/
├── README.md                              # This navigation index
├── product/                               # Product & feature specifications
│   ├── FEATURES.md                        # Curated Agents & Chat capabilities
│   └── BENCHMARK_GUIDE.md                 # Evaluation benchmarks & metrics
├── architecture/                          # Core system architecture & blueprints
│   ├── solutions-and-implementation-guide.md  # Primary system specification (72KB)
│   ├── systems-overview.md                # High-level architecture & interview guide
│   ├── knowledge-base.md                  # Core system boundary rules & data flows
│   └── specs/                             # Indexing & storage specifications
│       ├── indexing-v1.md                 # V1 full repository indexing spec
│       ├── incremental-indexing.md        # AST diffing & incremental update spec
│       └── intelligence-storage.md        # Graph & vector storage schema specs
├── adr/                                   # Architectural Decision Records (ADRs)
├── agents/                                # Agent skill conventions & operational rules
│   ├── issue-tracker.md                   # Local markdown issue tracking conventions
│   ├── triage-labels.md                   # 5-role triage label vocabulary
│   └── domain.md                          # Domain doc reading rules
└── archive/                               # Historical & superseded documentation
    ├── 2026-10-sprint-todo.md             # Completed October 2026 tasks checklist
    ├── 2026-10-audit.md                   # Baseline system audit (October 2026)
    ├── ai_service_spec.md                 # Early AI service draft
    └── current-indexing.md                # Legacy indexing notes
```

---

## 📌 Document Guide

### 1. Product & Capabilities
* **[Product Features (`docs/product/FEATURES.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/product/FEATURES.md):** The core product definition outlining the 5 Curated Agents (Investigation, Issue, Review, Code, Doc) and the Context Engine Chat Interface.
* **[Benchmark Guide (`docs/product/BENCHMARK_GUIDE.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/product/BENCHMARK_GUIDE.md):** Ground truth datasets, precision/recall metrics, and test harnesses for measuring code review quality.

### 2. Architecture & Implementation Specifications
* **[Solutions & Implementation Guide (`docs/architecture/solutions-and-implementation-guide.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/architecture/solutions-and-implementation-guide.md):** The primary 72 KB architecture reference detailing data contracts, SQL DDL migrations, Cypher queries, and execution blueprints for the 6 core systems.
* **[Systems Overview (`docs/architecture/systems-overview.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/architecture/systems-overview.md):** Architectural walkthrough and senior systems engineering talking points.
* **[Knowledge Base Rules (`docs/architecture/knowledge-base.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/architecture/knowledge-base.md):** Strict system boundaries between Next.js, Bun API, and Python FastAPI.
* **[Component Specs (`docs/architecture/specs/`)](file:///home/aryanracha/Coding/projects/gitami/docs/architecture/specs):** Detailed technical specifications for V1 full indexing, incremental graph synchronization, and dual-store schemas.

### 3. Agent Skills & Operations
* **[Issue Tracker Conventions (`docs/agents/issue-tracker.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/agents/issue-tracker.md):** Guidelines for `.scratch/<feature-slug>/` issues and wayfinding maps.
* **[Triage Labels (`docs/agents/triage-labels.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/agents/triage-labels.md):** Mapping canonical triage states to local markdown issues.
* **[Domain Rules (`docs/agents/domain.md`)](file:///home/aryanracha/Coding/projects/gitami/docs/agents/domain.md):** Guidelines for reading [`GLOSSARY.md`](file:///home/aryanracha/Coding/projects/gitami/GLOSSARY.md) and [`docs/adr/`](file:///home/aryanracha/Coding/projects/gitami/docs/adr).

### 4. Historical Archive
* **[Archive Directory (`docs/archive/`)](file:///home/aryanracha/Coding/projects/gitami/docs/archive):** Contains superseded sprint task lists, legacy indexing specifications, and earlier audits preserved for provenance.
