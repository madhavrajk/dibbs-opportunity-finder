# How this build maps to *How I Approach an AI Build*

Status: **Done**, **Partial** (what's missing is stated), or **Not done**. Evidence is a file or a command.

## Techniques

| Technique | Status | Evidence in this build |
|---|---|---|
| **Win, control cost, minimize exposure** | Done | Priorities in `CLAUDE.md`: no wrong identifier → no missed RFQ → time saved. Cost: $0 per run (no runtime LLM); politeness to DIBBS (sequential, cached). Exposure: public data, one local profile, no auth (agreed) |
| **Socratic prompting and a cross-check** | Partial | The questions were asked and answered (`docs/questions.md`) and the design was restated. **Missing:** no second model challenged the design on cost |
| **Contract-first, parallel subagents** | Done | `app/contracts.py` written first. Builders owned separate files and ran in parallel. Opus designed, Sonnet built, Haiku ran checks |
| **Intent graph and assumption ledger** | Partial | Each decision in `docs/rationale.md` names the assumption it relies on, and the riskiest one ("the newest file is today's issue") is checked live by `app/verify.py`. **Missing:** no automatic rerun of dependent work when an assumption breaks |
| **Running rationale** | Done | `docs/rationale.md` was appended during the build: D0 to D8, with a gate log and the orchestrator's review fixes |
| **Frontier versus open-source models** | Done (build) / N/A (runtime) | Model tiering per agent in `CLAUDE.md`. The product uses no LLM, because exact strings are matched exactly for free. An open-source model isn't needed at $0 |
| **Eval cost in proportion to risk** | Done | Code checks every row (regex validation and the full live cross-check); blind labelled cases on every change; a person reviews a sample (the demo). **No model judge**: none is needed, since the outputs are deterministic |
| **Story-mode telemetry** | Done | The refresh trace (stages, seconds, plain-English story) is in `data/refresh_log.jsonl` and shown in the app's "How this batch was fetched". The verify report has stage timings. Every match carries its reasons |
| **Self-healing loop** | Partial | `python scripts/gate.py [--live]`: tests → evals → live verify, with the tail of each failure. Failures became tests before fixes (truncation, the NSN length). **Missing:** the gate doesn't diagnose from the story automatically |
| **Panel of experts** | Done (once) | `docs/panel.md`, named roles, blockers only. The UX review by the Opus designer scored 2 audiences (`docs/ux_review.md`) |
| **Dashboards per role** | Partial | An executive KPI row and a bid-manager list. **Not built:** separate operations, compliance and cost views. For a single-vendor MVP they would be scope creep (the RFI retro showed dashboards cost money and changed no answer) |
| **Human in the loop** | Done | "Shortlist to quote" or "Not for us" in the row detail, recorded with latest wins (`data/feedback.jsonl`). `scripts/feedback_to_cases.py` turns disagreements into **candidate** eval cases; a person promotes them |
| **Resilience and scale** | Done | Retries with backoff; one bad PDF never stops the others; the cache is per date; the listing pages are cached; small sequential jobs |

## Stages

| Stage | Gate | Status |
|---|---|---|
| 1 Understand | User, decision, worst failure, governing source, who sees what | Done (`docs/questions.md`) |
| 2 Design | Restated; pipeline with code and model steps; metric, zero-tolerance line and cut line | Done (`CLAUDE.md`, `docs/plan.md`) |
| 3 Contracts | Contracts, working agreement and criteria; tests collect | Done (commit `S1: contracts`) |
| 4 Thin path | One real input end to end; every failure ends with a person | Done (live 2,584 rows) |
| 5 Evals | Labelled cases by an agent that hasn't read the code; the harness reports | Done (21/21; `python -m evals.report`). Caveat: the evaluator's isolation was by instruction, not by the hook |
| 6 Hard cases | Near misses before fixes; 0 wrong, 0 leaks | Done. The full live check found 1 wrong identifier and 141 missed lines, both fixed (D8) |
| 7 Interface and telemetry | Upload, run, review; dashboards; story and cost visible | Done, except multi-role dashboards |
| 8 Write-up and review | How to run, eval results, limits, next steps; panel once | Done |

## Checks by cost (Figure 1 in the doc)

| Level | Here |
|---|---|
| **Every change (seconds):** tests, contracts, stub evals, leak check | `scripts/gate.py`: pytest (offline fixtures) and `evals.report` (precision and recall, identifier byte equality) |
| **Each stage gate (minutes):** independent probes, near misses, telemetry | The blind evaluator's near misses; the full live cross-check (`app.verify`, about 3 min cold); the refresh trace |
| **End of build (once):** expert panel, real sample | The panel agent; the Opus UX review; the demo on the live batch |
| **In use:** reviewer decisions → candidate cases | Shortlist and Not-for-us → `scripts/feedback_to_cases.py` → a person promotes them |
