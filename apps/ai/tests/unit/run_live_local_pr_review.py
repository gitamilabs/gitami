import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from src.agents.reviewer import run_agentic_pr_review
from src.agents.llm_client import DualLLMClient


async def main():
    llm = DualLLMClient()
    print("=" * 60)
    print("GITAMI PR AGENT - LIVE LOCAL LLM TEST")
    print("=" * 60)
    print(f"Orchestrator Provider : {llm.orchestrator_provider} ({llm.local_orchestrator_model})")
    print(f"Worker Provider       : {llm.worker_provider} ({llm.local_worker_model})")
    print(f"Local Health Check    : {await llm.check_local_health()}")
    print("=" * 60)

    # Mock Neo4j and Vector store to isolate LLM evaluation
    mock_graph = MagicMock()
    mock_graph.connect = AsyncMock()
    mock_graph.close = AsyncMock()
    mock_graph.execute_query = AsyncMock(return_value=[])

    mock_vector = MagicMock()
    mock_vector.query = MagicMock(return_value={"documents": [], "metadatas": []})

    test_diff = """--- a/src/payments/processor.ts
+++ b/src/payments/processor.ts
@@ -12,6 +12,12 @@ export class PaymentProcessor {
   async chargeCustomer(customerId: string, amountCents: number) {
+    const stripe_secret_key = "sk_live_abcdef1234567890abcdef";
+    console.log("Charging customer:", customerId, amountCents);
+    // TODO: implement real retry logic later
+    if (amountCents < 0) return null;
+    const resp = await customerId.nonExistentChargeCall();
+    return resp.status;
   }
 }
"""

    print("\nRunning Agentic PR Review with local dual-model inference...")
    t0 = time.time()
    result = await run_agentic_pr_review(
        client=mock_graph,
        repo_id="my-org/core-payments",
        branch="feat/stripe-integration",
        changed_symbols=["PaymentProcessor.chargeCustomer"],
        raw_diff_text=test_diff,
        symbols=[],
        vector_client=mock_vector,
        llm_client=llm,
    )
    t1 = time.time()
    elapsed = round(t1 - t0, 2)

    print("\n" + "=" * 60)
    print(f"REVIEW COMPLETED in {elapsed}s")
    print("=" * 60)
    print(f"Verdict             : {result.decision.verdict}")
    print(f"Risk Score          : {result.decision.risk_score} / 10.0")
    print(f"Diff Hunks Processed: {result.diff_hunks_count}")
    print(f"Summary             : {result.decision.summary}")
    print(f"LLM Orchestrator    : {result.llm_orchestrator_used}")
    print("-" * 60)
    print(f"Issues Detected ({len(result.issues)}):")
    for i, issue in enumerate(result.issues, start=1):
        sev = issue.get("severity", "warning").upper()
        title = issue.get("title", "")
        file_path = issue.get("file_path", "")
        line = issue.get("line", 1)
        cat = issue.get("category", "")
        print(f"  {i}. [{sev}] [{cat}] {title}")
        print(f"     Location : {file_path}:{line}")
        print(f"     Fix      : {issue.get('suggested_fix', '')}")

    print("-" * 60)
    print("Orchestrator Rationale Excerpt:")
    print(result.agent_rationale[:400] + ("..." if len(result.agent_rationale) > 400 else ""))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
