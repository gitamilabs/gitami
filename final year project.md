cd frontend
bun run dev

cd backend/api-service
bun run start
npx localtunnel --port 5000


cd backend/ai-service
uv run ai-service serve

Other vector databases to consider qdrant, Pinecone and PGvector

Vul4J for benchmarking


Yes, **it is entirely possible to implement the core philosophy and methodology of this paper in your project**. In fact, your project (**GitAmi**) is uniquely positioned for this because you **already have the structural foundations** that the paper describes.

---

### Key Takeaways from the Paper (*VulAgentRL*)

1. **The Core Problem**: **71.7% of real-world vulnerabilities cannot be verified from the function or diff alone**. The true bug or guard condition resides across procedural boundaries (60% in callees, 19% in callers, 13% in types/globals, 8% in dataflow predecessors). Single-function/diff-only LLMs either miss the bug or hallucinate false positives.
2. **The Solution**: An **Agentic Code Navigation Loop** over a Code Graph (CPG):
   - The agent does not just guess from the diff. It uses tools to query callers, callees, and dependencies.
   - It follows a 5-step auditor protocol: **Inspect $\rightarrow$ Hypothesize $\rightarrow$ Query Graph $\rightarrow$ Falsify $\rightarrow$ Decide**.
   - Crucially, it must run **falsification queries** (e.g. *"Did the caller already sanitize this input?"* or *"Does the callee already enforce bounds checks?"*).
3. **Graph Is the Verifier**: Instead of relying on a subjective LLM-as-judge or fragile text matching, the agent must cite **exact persistent graph node IDs** as evidence. The reward/verification is a mathematical set intersection ($F_1$ score) against verified graph nodes.
4. **SFT Warm-Start is Structurally Required**: The authors discovered that RL (GRPO) from a cold-start base model completely fails to discover tool use. A distillation/SFT warm-start from a frontier teacher (e.g. Claude/Gemini) is strictly necessary.

---

### How the Research Maps to GitAmi

| Component in Paper (*VulAgentRL*) | Current GitAmi Architecture | Feasibility & Alignment |
| :--- | :--- | :--- |
| **Code Property Graph (CPG)** via Joern | **Neo4j Knowledge Graph** (`Symbol`, `File`, `CALLS`, `DEFINES`, `DEPENDS_ON_FILE`) | **Strong match**: You already have interprocedural call graphs and symbol hierarchies indexed in Neo4j. |
| **CPG Query Tools** (`cpg_callers`, `cpg_callees`, `cpg_search`) | **FastMCP Tools** in [`mcp/tools.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/mcp/tools.py) (`get_symbol_details`, `get_file_dependencies`, `get_blast_radius`, `get_file_content`) | **Direct 1:1 match**: Your tools already return callers, callees, dependencies, and blast radius. |
| **Multi-Turn Agent Navigation** | ReAct Agent Loop in [`agent_loop.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/agent_loop.py) | **Direct match**: ReAct loop exists for Q&A, but PR review is currently mostly single-turn. |
| **PR Review Strategy** | Currently [`reviewer.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/reviewer.py) sends diff slices to Groq worker + Gemini orchestrator | **Improvement target**: Currently `reviewer.py` only passes `raw_diff_text[:5000]` and precomputed blast radius, without an active multi-turn interprocedural investigation loop. |
| **Graph Node Citations** | Unstructured issue text | **Adaptable**: You can require the agent to output exact Neo4j `qualified_name` or `elementId` as `evidence_nodes`. |
| **GRPO RL Training** (4x H100 80GB) | Inference-time dual LLMs (Groq + Gemini) | **Adaptation needed**: Full GRPO training is compute-heavy, but prompt-driven agentic inference and lightweight LoRA distillation are immediately practical. |

---

### Practical Implementation Strategy for Your Final Year Project

You can implement this in **two distinct phases**:

#### Phase 1: Inference-Time Agentic Investigation in `reviewer.py` (Zero Extra Compute Needed)
You don't need 4x H100 GPUs to gain the benefits of the paper. You can implement the paper's **5-Stage Investigation & Falsification Protocol** directly inside your PR Reviewer:

1. **Upgrade [`reviewer.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/reviewer.py) to an Interprocedural Agent Loop**:
   - Instead of passing raw diff text to Groq in a single shot, the reviewer initializes an investigation loop when high-risk symbols or dangerous APIs (e.g., SQL queries, unescaped HTML, memory buffers, auth decorators) are touched.
2. **Enforce the Paper's 5-Step Protocol**:
   - **Step 1 (Inspect)**: Detect parameters, return types, and sinks in the diff hunks.
   - **Step 2 (Hypothesize)**: Propose candidate bugs or vulnerabilities (e.g., *“CWE-89 SQL injection if `user_input` is unsanitized”*).
   - **Step 3 (Query Neo4j)**: Fetch callers of the modified function to see where inputs come from, or callees to see how arguments are handled.
   - **Step 4 (Falsify — Crucial contribution of the paper)**: Specifically issue queries seeking guards or sanitizers that would disprove the bug (e.g., checking if the caller ran an auth check or input validation). Only if falsification fails is a vulnerability confirmed.
   - **Step 5 (Graph Grounding)**: Output the final report with `evidence_symbols` containing the exact Neo4j qualified names (e.g. `src/auth/service.py::validate_token`).

```json
{
  "verdict": "vulnerable",
  "cwe": "CWE-89",
  "evidence_nodes": ["app/api/users.py::get_user_by_id", "app/db/client.py::raw_query"],
  "falsification_attempt": "Queried callers in api/routes.py; verified that no sanitization middleware wraps user_id before calling get_user_by_id.",
  "justification": "Tainted parameter flows directly to raw SQL query without parameterization."
}
```

#### Phase 2: Evaluation & Benchmark (Demonstrating Research Value for Your Thesis)
For your final year project presentation/defense, you can evaluate your system following the paper's methodology:
1. **Curate Test Cases**: Use 20–30 vulnerability/patch pairs from repositories or benchmarks like PrimeVul/CVEs.
2. **Compare Baselines**:
   - **Baseline A (Diff-only)**: Standard PR review prompt looking only at the diff (current implementation).
   - **Baseline B (VulAgentRL-adapted GitAmi)**: Multi-turn agent using Neo4j tools + Falsification protocol.
3. **Metric**: Measure the **Pair-wise Correct Rate (P-C)** and **False Positive Reduction**. The paper proves that falsification queries drastically cut down false positives.

#### Phase 3: Model Distillation / Fine-Tuning (Optional / Advanced)
If you wish to train an open-source model (like Qwen2.5-Coder-7B) as in the paper:
- **Teacher Distillation**: Use Gemini 1.5 Pro or Claude 3.5 Sonnet to generate 500–1000 multi-turn trajectories querying your Neo4j database.
- **Rejection Sampling**: Keep only trajectories that reach the right verdict and cite real Neo4j nodes within 2 hops.
- **LoRA SFT**: Fine-tune Qwen2.5-Coder-7B using LoRA on Google Colab or a single cloud GPU (e.g., RTX 3090/4090 or A10G) instead of multi-node H100 GRPO.

---

### Immediate Next Steps

Would you like to start by:
1. **Refactoring the PR Reviewer (`reviewer.py`)** to incorporate the multi-turn **Hypothesize $\rightarrow$ Graph Query $\rightarrow$ Falsify $\rightarrow$ Graph Grounding** loop using your existing FastMCP tools?
2. **Adding targeted CPG-style tools** to [`mcp/tools.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/mcp/tools.py) (e.g. querying upstream data sources and downstream sanitizers in Neo4j)?

**No, you are currently NOT storing data dependency flow (dataflow/taint edges) in the graph.**

Here is an exact breakdown of what your graph currently stores versus what data dependency flow means in the research paper:

---

### 1. What You ARE Currently Storing (Symbol & Call Graph)

Looking at [`writer.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/graph/writer.py) and your tree-sitter extractors ([`python.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/parsing/extractors/python.py), [`mern.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/parsing/extractors/mern.py)), your Neo4j database contains:

* **Nodes**:
  * `File`: path, language.
  * `Symbol`: function, class, method, or component definitions (stores `name`, `signature`, line numbers, `docstring`, `code_body`).
  * `Package`: external library imports (e.g. `express`, `numpy`).
* **Relationships**:
  * `(File)-[:DEFINES]->(Symbol)`
  * `(Symbol)-[:CALLS]->(Symbol)` *(Invocation/Call Graph: function A calls function B)*
  * `(File)-[:IMPORTS]->(Symbol)` *(Module imports)*
  * `(File)-[:DEPENDS_ON]->(Package)` *(External dependency)*

👉 **Summary of what you have**: You have a **High-Level Call Graph + Module Dependency Graph**.

---

### 2. What is "Data Dependency Flow" in the Paper?

In the paper (*VulAgentRL*), the authors use **Joern** to generate a **Code Property Graph (CPG)**, which combines three layers:
1. **AST** (Abstract Syntax Tree down to statement and expression tokens).
2. **CFG** (Control Flow Graph: execution order, `if/else` branching).
3. **PDG / DDG (Data Dependence Graph / Reaching Definitions)**:
   * Tracks **how values and variables propagate**: e.g., `user_input` from `req.body.name` $\rightarrow$ assigned to `var formatted` $\rightarrow$ passed into `db.query(formatted)`.
   * Allows queries like `cpg_dataflow(source, sink)` to prove whether tainted data reaches a dangerous function without being sanitized.

In your current Neo4j schema:
* You do **not** have nodes for variables, parameters, expressions, or statements.
* You do **not** have edges like `DATA_FLOW`, `REACHES`, or `DEFINES_VARIABLE`.

---

### 3. Does This Prevent You from Implementing the Paper's Approach?

**No, not at all!** Here is why:

1. **Callers and Callees Account for the Vast Majority of Bugs**:
   * The paper's own empirical finding (Section 2.2) shows:
     * **60%** of needed evidence resides in **callees** (e.g., does the called function validate input or check bounds?).
     * **19%** resides in **callers** (e.g., does the caller sanitize input before passing it?).
     * Only **8%** strictly required low-level intra-statement dataflow predecessor queries.
   * Your Neo4j graph **already supports caller and callee traversal** via `tool_get_symbol_details` (`dependents` and `dependencies`).

2. **The LLM Can Perform Intra-Function Dataflow Reasoning on Demand**:
   * Because your `Symbol` nodes store `code_body`, and your `get_file_content` tool retrieves the actual source code, the LLM agent can trace variable dataflow inside the function body once it fetches the caller/callee code.

---

### 4. How You Can Bridge This Gap in GitAmi

If you want to bring your graph closer to the paper's CPG, you have two practical paths:

#### Option A: Hybrid Approach (Recommended for your Project)
* Keep Neo4j at the **Symbol & Call Graph** level.
* Use the agentic loop from the paper: When inspecting a function, the agent queries Neo4j for callers/callees (`tool_get_symbol_details`), fetches their code bodies, and **the LLM traces the data flow between parameters and arguments**.
* This avoids exploding the size of Neo4j with millions of low-level AST/variable nodes.

#### Option B: Enrich Neo4j with Function Parameters & Return Types (Lightweight Dataflow)
* Update your tree-sitter extractors ([`python.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/parsing/extractors/python.py) and [`mern.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/parsing/extractors/mern.py)) to extract:
  * Function parameters as nodes or attributes.
  * Connect `(Symbol)-[:CALLS {arg_mapped_to: "param_name"}]->(Symbol)`.
* This gives you basic interprocedural parameter dataflow in Neo4j without needing the heavyweight complexity of Joern.



**Yes, you can absolutely use Joern with your current project.** In fact, that is exactly how the research paper built their system: 

> *"We implement VulAgentRL ... with a Joern-based CPG service behind the tool layer."* (Section 4.3)

Here is a comprehensive breakdown of how Joern works, how it integrates into GitAmi, and the practical pros and cons.

---

### 1. How Joern Would Fit into GitAmi's Architecture

Currently, your architecture looks like this:
```
Repo Files ──> Tree-sitter ──> Neo4j (Call Graph & Symbols) ──> FastMCP Tools ──> LLM Reviewer
```

If you add Joern as a **CPG Sidecar Service**, your architecture becomes:
```
                                ┌──> Neo4j (High-level architecture, Blast Radius, Imports)
Repo Files ──┬──> Tree-sitter ──┘
             │
             └──> Joern Engine ──> CPG Database (AST + CFG + Dataflow/PDG)
                        │
                        └──> Joern REST/Py Client ──> FastMCP CPG Tools ──> LLM Reviewer
```

In this hybrid setup:
1. **Neo4j** remains your fast, persistent knowledge base for high-level repository structure, module imports, and blast radius.
2. **Joern** acts as your deep static analysis engine, answering precise questions about **taint tracking, variable propagation, and control-flow reachability**.

---

### 2. What Joern Adds That You Don't Have Today

With Joern, you can expose new FastMCP tools in [`mcp/tools.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/mcp/tools.py) that directly replicate the research paper:

| New Tool | What It Does (via Joern CPGQL) | Why the Agent Needs It |
| :--- | :--- | :--- |
| `cpg_dataflow(source, sink)` | Traces if an untrusted variable at `source` flows into a dangerous function at `sink` without passing through a sanitizer. | **Detects injection/taint bugs** (SQLi, XSS, Path Traversal, Command Injection). |
| `cpg_reachable_guards(symbol)` | Finds all `if` / condition blocks controlling execution before reaching `symbol`. | **Falsification check**: Verifies whether an auth check or bounds validation actually protects the vulnerable code. |
| `cpg_callers_with_args(func)` | Returns callers along with the exact argument expressions passed at call sites. | Discovers where input parameters originate. |

---

### 3. Practical Implementation: How to Set It Up

Because Joern is written in Scala and runs on the JVM, and you are working on **Windows**, the cleanest way to integrate Joern into your project is via **Docker**:

#### Step 1: Run Joern Server via Docker
Add a Joern container to your `docker-compose.yml`:
```yaml
  joern:
    image: ghcr.io/joernio/joern:latest
    container_name: gitami-joern
    ports:
      - "8080:8080"
    volumes:
      - ./chroma_db/repos:/workspace
    entrypoint: ["joern", "--server", "--server-host", "0.0.0.0", "--server-port", "8080"]
```

#### Step 2: Add a Joern Client in `ai-service`
Install the official Python client or query Joern's HTTP/WebSocket API:
```bash
pip install cpgclientpy
```
Create `src/ai_service/cpg/client.py`:
```python
from cpgclientpy import CPGClient

class JoernClient:
    def __init__(self, host="localhost", port=8080):
        self.client = CPGClient(host, port)

    async def generate_cpg(self, repo_path: str):
        # Joern parses the repo directory (supports Python, JS/TS, C/C++, Java, Go)
        return self.client.create_cpg(repo_path)

    async def check_dataflow(self, source_pattern: str, sink_pattern: str):
        # Query reachable dataflow paths using CPGQL
        query = f'def src = cpg.call.name("{source_pattern}"); def snk = cpg.call.name("{sink_pattern}"); snk.reachableByFlows(src).p'
        return self.client.query(query)
```

#### Step 3: Expose FastMCP Tools to the Reviewer Agent
Wrap Joern queries as agent tools in [`mcp/tools.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/mcp/tools.py):
```python
async def tool_check_taint_flow(source_api: str, sink_api: str) -> str:
    """Verifies whether data flows from source to sink across function boundaries."""
    flows = await joern_client.check_dataflow(source_api, sink_api)
    return json.dumps({"reachable": bool(flows), "traces": flows})
```

---

### 4. Honest Trade-offs & What to Watch Out For

| Aspect | Reality with Joern | Recommendation |
| :--- | :--- | :--- |
| **Language Support** | Joern natively supports **Python, JavaScript, TypeScript**, C/C++, Java, PHP, and Go. Fits your MERN + Python stack. | Supported out-of-the-box. |
| **Windows OS** | Running Joern natively on Windows command prompt can cause path/batch script friction. | **Use Docker or WSL2** to run the Joern server cleanly. |
| **Parsing Overhead** | Joern generates deep statement-level graphs, so parsing a repository takes longer (e.g. 15–45 seconds) and uses ~1–3 GB RAM. | Run `joern-parse` in the background when a repository is indexed or a PR is opened, rather than on every single keystroke. |
| **Complexity** | CPGQL (Scala DSL) has a learning curve for custom queries. | Stick to 3–4 standard Joern queries (`reachableByFlows`, `callers`, `callees`, `controlDependencies`). |

---

### Summary Recommendation

* **For your Final Year Project thesis / demonstration**: 
  Integrating Joern would make your project **exceptionally strong academically**, directly implementing state-of-the-art methodology from top-tier security papers (like *VulAgentRL*).
* **Next Step**: We can either:
  1. Set up a lightweight **Joern Docker integration** with a Python bridge in `ai-service`.
  2. Or first enhance your existing **Neo4j + Tree-sitter** tools with the paper's **Hypothesize $\rightarrow$ Query $\rightarrow$ Falsify** reasoning loop, and plug in Joern when ready.


That is a **fantastic question**. It gets right to the heart of system design and graph database architecture.

The short answer is: **No, they are not redundant because they operate at two completely different granularities and serve fundamentally different roles in your system.**

Here is the breakdown of why systems like GitAmi use both rather than relying on Joern alone:

---

### 1. Macro-Level vs. Micro-Level Granularity

| Dimension | **Your Neo4j Graph** (Macro / Architectural) | **Joern's CPG** (Micro / Statement-Level) |
| :--- | :--- | :--- |
| **Node Granularity** | High-level entities: `Files`, `Functions`, `Classes`, `Modules`, `Packages`. | Every single token: `Identifiers`, `Literals`, `Operators`, `Expressions`, `ControlStructures` (`if`, `while`), `ReturnStatements`. |
| **Graph Size (per repo)** | Typically **500 – 5,000 nodes**. Very lightweight. | Typically **200,000 – 2,000,000+ nodes** for the exact same repository. |
| **Query Speed** | **1 – 5 milliseconds** via Cypher with indexed lookups. | Can take **seconds** to traverse millions of AST and CFG edges in memory. |
| **RAM Footprint** | Extremely low. Stored permanently on disk; easy to query. | Heavy (needs **1 – 4 GB RAM** per active repository in the JVM heap). |
| **What it's best for** | Blast radius, cross-file impact, UI dependency visualization, architecture metrics. | Variable taint tracking, line-by-line dataflow, compiler-level reachability. |

---

### 2. The "System-of-Record Database" vs. "On-Demand Compiler Engine"

Think of the difference between **PostgreSQL/Neo4j** and a **compiler like GCC or Clang**:

* **Neo4j is your Platform Database (System of Record)**:
  * In your project, Neo4j maintains **multi-repository isolation** and **branch isolation** (see your constraint: `(s.repo_id, s.branch, s.qualified_name)`).
  * It powers your web application: your frontend dashboard, hybrid vector-graph search, and graph visualization. If you tried to visualize Joern's 500,000 AST nodes on your frontend UI, the browser would immediately freeze.
  * It answers high-level questions instantly: *"Which 5 files depend on `auth.py`?"* or *"What is the blast radius score of this PR?"*

* **Joern is an On-Demand Static Analysis Engine**:
  * Joern is not a multi-tenant application database. It operates on a single codebase snapshot in a `cpg.bin` file.
  * You don't keep Joern running 24/7 storing all branches and repos for your platform.
  * Instead, your reviewer agent invokes Joern **on-demand** like a deep inspection tool when examining a suspicious PR diff: *"Does the untrusted parameter at line 42 flow into the SQL query at line 88 without sanitization?"*

---

### 3. A Fun Historical Fact About Joern & Neo4j

When Joern was originally created in 2014 by Fabian Yamaguchi and his team:
* **Joern actually used Neo4j as its backend!**
* However, they found that because a Code Property Graph stores *every single operator, variable, and statement*, storing all that low-level AST data in Neo4j made graph traversals too slow for large C/C++ codebases.
* That is why Joern later created **OverflowDB** (a specialized in-memory graph engine optimized specifically for compiler-level code traversals).

---

### 4. What Would Happen If You Replaced Neo4j with Joern Entirely?

If you tried to eliminate Neo4j and use Joern for everything:
1. **No Clean Multi-Repo / Branch Support**: Joern doesn't have native multi-tenant scoping or declarative constraints like Neo4j Cypher (`MATCH (s:Symbol {repo_id: $repo, branch: $branch})`).
2. **Frontend UI Breakdown**: Your UI visualization ([`visualize.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/visualize.py)) relies on clean, high-level symbol graphs that developers can actually understand. Joern's graph is far too noisy for human-facing architecture diagrams.
3. **Complex Querying**: Querying Neo4j using Cypher is simple and native in Python. Querying Joern requires sending Scala scripts/CPGQL queries over a WebSocket.

---

### Summary: The Ideal Division of Labor

* **Keep Neo4j**: As your **fast, persistent knowledge base** for repository structure, architecture visualization, and blast radius calculation.
* **Use Joern (as a specialized worker)**: As a **targeted security analysis tool** that the agent calls specifically when it needs to verify deep dataflow or sanitize-check a potential bug.


**Yes, absolutely.** In fact, Joern was specifically designed from the ground up for **whole-repository analysis**, not single files or isolated snippets.

That is why the research paper (*VulAgentRL*) was able to track vulnerabilities across files:

> *"The unifying idea is a Code Property Graph (CPG), built once per project with Joern..."* (Section 2)

Here is how Joern handles a whole repository, what works smoothly, and what you need to be aware of:

---

### 1. How Joern Analyzes a Whole Repo

When you run Joern on a repository:
```bash
joern-parse /path/to/my-repo --output /path/to/cpg.bin
```

Joern automatically:
1. **Recursively traverses the entire directory tree**.
2. **Parses every source file** in the project into an Abstract Syntax Tree (AST).
3. **Resolves cross-file imports and calls**: When `app/routes.py` imports and calls `calculate_risk()` defined in `utils/math.py`, Joern links them with an interprocedural `CALL` edge.
4. **Builds project-wide dataflow**: It can trace a variable from an API route in file A, through helper functions in file B, all the way to a database query in file C.

---

### 2. How Well It Scales (Real-World Performance)

Joern was originally battle-tested on massive real-world open-source projects (like the Linux Kernel, QEMU, VLC, and FFmpeg):

| Repo Size                                        | Lines of Code (LoC)    | Parsing Time     | RAM Needed |
| :----------------------------------------------- | :--------------------- | :--------------- | :--------- |
| **Small** (Microservices, scripts)               | < 10,000 LoC           | ~5 – 15 seconds  | ~1 GB      |
| **Medium** (Typical web apps, MERN, FastAPI)     | 10,000 – 100,000 LoC   | ~20 – 60 seconds | ~2 – 4 GB  |
| **Large** (Open-source monoliths, e.g. VLC, mpv) | 100,000 – 500,000+ LoC | 2 – 5 minutes    | ~4 – 8 GB  |

For your GitAmi platform, parsing a typical user repository will take around **20–45 seconds**.

---

### 3. Crucial Rules for Whole-Repo Parsing in GitAmi

If you use Joern on a whole repository, there are two important best practices to follow:

#### A. Always Exclude "Dependency & Junk" Folders (Critical!)
If you run Joern naively on a JavaScript/Node.js or Python repository without exclusions, it might try to parse `node_modules` or `.venv`. Parsing 50,000 third-party library files will waste 10 minutes and consume gigabytes of RAM.
* **Always exclude**: `node_modules/`, `venv/`, `.git/`, `dist/`, `build/`, and `__pycache__/`.
* Joern supports `--exclude` flags for this:
  ```bash
  joern-parse ./my-repo --exclude node_modules,venv,.git -o cpg.bin
  ```

#### B. Handling Multi-Language Repositories (e.g. Python Backend + React Frontend)
Joern uses specialized language frontends:
* `pysrc2cpg` for Python
* `jssrc2cpg` for JavaScript / TypeScript
* `c2cpg` for C/C++
* `javasrc2cpg` for Java

If a repository contains **both** a Python backend and a React/Node frontend:
* The cleanest approach is to generate **two CPG files**:
  * `cpg_backend.bin` (pointing to `backend/`)
  * `cpg_frontend.bin` (pointing to `frontend/`)
* This keeps parsing blazing fast and prevents language-specific parser conflicts.

---

### 4. How It Fits Into Your Background Job Pipeline

Just like you currently index repositories into Neo4j in a background job when a repo is connected:
1. When a user connects a repo or opens a PR, a worker job runs:
   ```bash
   joern-parse ./repos/{repo_id} --exclude node_modules,venv -o ./cpgs/{repo_id}.bin
   ```
2. The resulting `cpg.bin` is saved on disk.
3. The Reviewer Agent can then query that CPG instantly whenever it needs to inspect cross-file dataflow!