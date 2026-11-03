import asyncio
import json
from src.agents.llm_client import DualLLMClient
from src.agents.agent_loop import AutonomousAgentLoop
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient


async def test_query():
    llm = DualLLMClient()
    loop = AutonomousAgentLoop(llm)
    graph = Neo4jClient()
    await graph.connect()
    vector = VectorKBClient()

    repo_id = "AryanRacha/nodejs-backend-template"
    print(f"Testing query on {repo_id}...")

    async for sse in loop.run_stream(
        user_query="What is this project about?",
        repo_id=repo_id,
        branch="main",
        graph_client=graph,
        vector_client=vector,
        max_steps=3,
    ):
        if not sse.startswith("data: "):
            continue
        try:
            data = json.loads(sse[6:].strip())
        except Exception:
            continue

        t = data.get("type")
        if t == "thought":
            print(f"\n[THOUGHT]: {data.get('content')}")
        elif t == "tool_start":
            print(f"[TOOL_START]: {data.get('tool_name')}({data.get('args')})")
        elif t == "tool_end":
            print(f"[TOOL_END]: {data.get('tool_name')} ({data.get('latency_ms')}ms)")
            print(f"  Summary: {data.get('summary')}")
            raw = str(data.get("raw_output", ""))
            print(f"  Raw: {raw[:300]}...")
        elif t == "answer_delta":
            print(f"\n[FINAL ANSWER]:\n{data.get('delta')}")
        elif t == "citations":
            print(f"\n[CITATIONS] ({len(data.get('citations', []))}):")
            for c in data.get("citations", []):
                print(f"  - [{c.get('id')}] {c.get('file_path')} (lines: {c.get('lines')}): {c.get('snippet')[:100]}...")

    await graph.close()


if __name__ == "__main__":
    asyncio.run(test_query())
