# Competitor & Ablation Benchmark Comparison Matrix

**Last Updated**: 2026-10-20 08:35:58 UTC

> [!NOTE]
> This matrix tracks independent evaluations of rival architectures against the proposed GitAmi system.
> Checkpoints are recorded continuously after every test case.

| Configuration ID | Knowledge Base | LLM Architecture | Conv. Gate | Martian (5-Case Pilot FI) | Martian (Full 50 PRs) | VulnGym (393 Cases, 596 Vulns) |
|---|---|---|---|---|---|---|
| **B1** | None (Raw Diff Only) | Single (Gemini 2.0 Flash) | Disabled | F1: 0.000 (P: 0.0%, R: 0.0%) | F1: 0.031 (P: 14.3%, R: 1.7%) | F1: 0.197 (P: 100.0%, R: 10.9%) |
| **B2** | ChromA (Only) | Dual-LLM | Enabled | F1: 0.324 (P: 31.6%, R: 33.3%) | F1: 0.215 (P: 28.3%, R: 17.3%) | F1: 0.288 (P: 96.2%, R: 17.0%) |
| **A1** | Neo4j Only (No Vector) | Dual-LLM | Enabled | F1: 0.216 (P: 21.1%, R: 22.2%) | F1: 0.191 (P: 30.4%, R: 13.9%) | [TO BE MEASURED] |
| **A2** | Dual KB (Neo4j + Chroma) | Worker Only (Llama-70B) | Enabled | F1: 0.293 (P: 26.1%, R: 33.3%) | F1: 0.137 (P: 26.7%, R: 9.2%) | [TO BE MEASURED] |
| **A3** | Dual KB (Neo4j + Chroma) | Orch. Only (Gemini 2.0) | Enabled | [TO BE MEASURED] | [TO BE MEASURED] | [TO BE MEASURED] |
| **GitAmi (Proposed)** | Dual KB (Neo4j + Chroma) | Dual-LLM + ReAct Agent | Enabled | [TO BE MEASURED] | F1: 0.083 (P: 20.9%, R: 5.2%) [50 PRs] | F1: 0.556 (P: 88.0%, R: 40.6%) [393 Cases] |


### Architectural Insights & Hypotheses:

1. **Baseline B1 (Raw Diff)**: Establishes pure LLM zero-shot capability without retrieval augmentation or convention checks.
2. **Baseline B2 (Chroma Only)**: Evaluates vector semantic search without graph dependency analysis.
3. **Ablation A1 (Neo4j Only)**: Evaluates structural call-graph blast radius without unstructured vector retrieval.
4. **Ablation A2 (Worker Only)**: Evaluates Groq Llama-3.3-70B running independently without Gemini Orchestrator.
5. **Ablation A3 (Orch Only)**: Evaluates Gemini 2.0 Flash running independently without Groq Worker.
6. **GitAmi (Proposed)**: Synergizes Dual KB (Graph + Vector) with Dual LLM (Gemini + Groq) inside an autonomous ReAct loop.