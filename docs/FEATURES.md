# Gitami — Features

## Agents

* **`INVESTIGATION AGENT`**
  * Takes in a query along with context from the intelligence layer and investigates to give an appropriate answer. Can also be triggered automatically when something breaks in production. Returns structured JSON when called by another agent, or plain text when a user queries it through the Chat Interface.
  * For simple questions it gives a fast single-shot answer. For complex root cause questions it runs an iterative loop — forming a hypothesis, querying the codebase, and refining — up to 8 steps before returning a final answer with a confidence score and a full reasoning trace.

* **`DOC AGENT`**
  * Creates documentation about the workflow, architecture, and working of the project using the intelligence layer. Generated docs are also fed back into the intelligence layer so other agents can use them as context.
  * Can generate: workflow guides, onboarding docs per domain, weekly changelogs from merged PRs, and decision logs when a PR overrides a known convention. Docs are automatically marked stale when the code they describe changes.

* **`ISSUE AGENT`**
  * Triggered when a GitHub Issue is raised. Verifies if it's a duplicate, spam, or critical and applies relevant tags automatically. The maintainer can then run the Investigation Agent to find a solution, and trigger the Code Agent once the solution is ready.
  * Checks for duplicates across both open and closed issues. Scores criticality based on which part of the system is affected. Tags include domain, severity, and an `ai-code-suspected` flag if the relevant code looks AI-generated.

* **`REVIEW AGENT`**
  * Reviews incoming PRs, searches for bugs, gives a risk score, and runs other checks. Creates a checklist of all issues it finds and stores the context. The maintainer can either trigger the Code Agent to fix the issues, or export the context directly to their local Claude Code or Codex session.
  * Checks include: blast radius (what else could break), convention violations, test coverage gaps, AI-generated code detection, security anti-patterns, and cross-repo contract breaks. Each checklist item has a severity — `blocking`, `warning`, or `suggestion`.

* **`CODE AGENT`**
  * Spins up a sandbox environment where it resolves the identified issue. Can be triggered from the Chat, the Issues section, or the Review section — once the issue has been identified and a solution plan is ready. Always requires maintainer approval before executing.
  * Generates a fix plan first — which files it will touch and in what order — and waits for approval before writing any code. Writes tests before the implementation, runs them, and only opens a PR if they pass. The PR description includes the full trail of what triggered the fix.

* **`CHAT INTERFACE`**
  * Lets users ask anything about the project in natural language. Queries are either answered directly by the LLM or routed to the Investigation Agent using the intelligence layer context, depending on the complexity of the question.
  * Always shows which path was taken and why. Supports triggering agents directly from chat — e.g. "review PR #42" or "generate docs for the auth service".
