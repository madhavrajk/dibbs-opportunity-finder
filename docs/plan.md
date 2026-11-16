# Plan: how I take a timed AI build from problem to demo

A reusable plan, with the DIBBS opportunity finder as the worked example. It applies the method in
*How I Approach an AI Build*: stages with gates, contracts first, parallel agents on the cheapest model that is good
enough, cheap checks run often and costly ones once, and every decision written down as it is made.

---

## 1. The steps, in order

| # | Stage | What I do | Gate to move on | DIBBS example |
|---|---|---|---|---|
| 0 | **Prepare** (before the clock) | Read the brief and my method. Reconnoitre the data source read-only. Set up agents, working agreement, fixtures | The riskiest assumption is tested before the session | WAF needs browser headers; consent banner is a POST on 2 hosts; a daily fixed-width file exists. All verified live |
| 1 | **Understand** | Ask the questions that would change the design (section 2), and write the answers down verbatim | I know who uses it, the decision it feeds, the worst failure, the source of truth, who sees what | `docs/questions.md`, answered by the interviewer |
| 2 | **Design** | Restate the problem; draw the pipeline; mark code steps and model steps; agree the metric, the zero-tolerance line and the cut line | The reviewer agrees with the restatement | "Rank, don't filter; identifiers are zero-tolerance; code matches, no LLM on identifiers" |
| 3 | **Contracts** | Write the typed interfaces between modules and the pass/fail criteria. Tests collect | Contracts and criteria committed | `app/contracts.py`, `docs/criteria.md` |
| 4 | **Thin path** | Parallel builders, one module each, test first, against the contracts. One real input end to end | Live data flows to a screen; every failure ends with a message to a person | 3 Sonnet builders: ingest, match, UI. Live: 2,584 rows |
| 5 | **Evals** | Labelled cases written by an agent that has not read the code. A harness that reports numbers | The harness runs and reports | 21 blind cases; `python -m evals.report` |
| 6 | **Hard cases** | Near misses written before any fix. Zero wrong answers is the bar | 0 wrong on near misses | CAP/CAPACITOR, truncated words, NSN off by one digit, FSC inside the NIIN, non-standard NSN, multi-line solicitations |
| 7 | **Interface and telemetry** | A designer pass for the real audiences; a story per outcome; feedback becomes eval cases | Every function kept; a trace visible | Opus UX review (23/23 functions kept); refresh trace; shortlist feedback |
| 8 | **Write-up and review** | README (how to run, diagram, results, limits, next steps). Expert panel once | Blockers only | `README.md`, `docs/panel.md` |

**Timebox rule:** when a stage's time runs out, cut scope, write down what was cut, and move on. Commit at every gate.

---

## 2. The questions I ask before building

Grouped by what each one decides. Ask in this order; stop when the design is clear. Have a default ready for each.

| Decides | Generic question | Asked here | Answer here |
|---|---|---|---|
| **The user and the output** | Who uses this, and what decision does it feed? | Who are the vendors, and what does "matters to me" mean? | Manufacturers and distributors; they match on keywords, NSN lists or FSCs; some avoid qty 1 or large quantities |
| **The metric** | Which failure is worse: a miss or a false alarm? | Is missing an RFQ worse than noise? | Overmap: show more rather than less |
| **Zero tolerance** | What must never be wrong? | Which fields must be exact? | One wrong digit in an NSN or solicitation number means the wrong part |
| **Source of truth** | Which document or system governs? How do I know what's current? | Scrape or download? Today only? | Scraping is fine; today's batch; refresh on demand |
| **Exposure** | Who may see what? | Single or multi-tenant? | One vendor profile, no auth |
| **Model use** | Is an LLM welcome, and at what cost? | Is there a key or budget? | Any LLM, if it's worth it; a no-LLM path is fine |
| **Scope and cut line** | What must work end to end, and what can be faked? | Which extra fields? Is the PDF in scope? | NSN, description; approved sources from the solicitation are valuable |
| **Logistics** | Time, demo format, what they want to see | Hard stop? Process or product? | 40 minutes; he wants to see the process |

---

## 3. How the project is structured

```
CLAUDE.md                 working agreement: goal, priorities in order, stage gates, model per agent, rules
.claude/agents/           builder (Sonnet) · evaluator (Sonnet, blocked from app/) · verifier (Haiku)
                          summarizer (Haiku) · ui-designer (Opus) · panel (Sonnet)
app/contracts.py          the only thing that crosses module boundaries (typed models, URL builders, regexes)
app/ingest.py             the only code that downloads the batch; parse → validate (flag, never fix) → SQLite; refresh trace
app/match.py              pure scoring with a reason per hit; no I/O
app/sources.py            approved-source names from the PDF, on demand, cached
app/verify.py             live cross-check of every stored row against DIBBS's own listing
app/feedback.py           vendor decisions (quote / not for us); latest wins
app/ui.py                 Streamlit: KPIs, For you, All RFQs, Shortlist, row detail
evals/report.py           precision / recall on the labelled cases + identifier byte equality
scripts/gate.py           one command after every change: tests → evals → (--live) verify, with diagnosis
tests/                    offline only, on fixtures saved from the live site
docs/                     questions, recon, rationale (decisions as made), criteria, UX review, panel, this plan
```

**Model routing (strong models design, cheaper ones build):**

| Work | Model | Why |
|---|---|---|
| Orchestration, design, reviewing every diff | Opus | Judgment; few tokens |
| Module builds, blind eval writing | Sonnet | Good code at a lower price; run in parallel |
| Running checks, summarising logs, mechanical scripts | Haiku | Cheapest; no judgment needed |
| UX evaluation and redesign | Opus | Taste is judgment |
| The product at runtime | No LLM | Exact strings are matched exactly, for free |

---

## 4. How the solution was reached

1. **Recon turned the riskiest assumption into a fact.** Scraping 55 pages of ASP.NET postbacks was the obvious path.
   The Downloads page instead had a daily fixed-width file: one request, identifiers in fixed columns. The HTML stayed in
   the design as the **independent check**, not the source.
2. **Validation found my own bug first.** My first solicitation regex rejected 717 good rows (serials can end in a
   letter). That set the rule for the build: flag, never fix, never drop.
3. **The metric came from the answer to "which failure is worse".** Overmap → ranking with reasons instead of filters;
   the only hiding is a filter the user sets, with the count shown.
4. **Matching in code, not a model.** NSN exact (+100), approved-source CAGE (+80), FSC (+40), keyword whole words and
   plurals, with truncation handled (+30). An LLM would add cost and risk to exact-string work. It belongs in profile setup
   ("describe what you make" → FSCs), which is the next step.
5. **Review caught what tests passed.** The space-padded 20-character description made every row look truncated
   (fixed by me on review); the detail picker hid 126 multi-line rows (found by the designer). Both became tests.
6. **Checks scaled with risk.** Regex on every row, blind labelled cases on every change, a full live cross-check of every
   row against DIBBS once per batch, and an expert panel once.

---

## 5. What I kept in mind throughout

- **Priorities in order:** never a wrong identifier → never miss a relevant RFQ → save the vendor time.
- **Code decides, models assist.** No model writes or edits an identifier.
- **Every failure ends with a person:** refresh errors are shown with the stage that failed; a bad PDF never stops the rest.
- **Independent probes:** the evaluator labels from the data alone; the live check compares with a source the ingest never used.
- **Nothing is made to pass** by weakening a test; failures become cases before fixes.
- **Cost:** the product costs $0 per run; build agents were tiered by model; DIBBS was hit politely (sequential, cached).
- **Honest limits** are written down: what wasn't verified, what's unexplained, what was cut.
- **The audience:** an executive needs the value in 10 seconds; a bid manager needs the right 20 rows at 7 a.m.

---

## 6. Reusing this plan for the next problem

Keep sections 1, 3 and 5. Replace:
- the questions' "asked here" column (section 2) with the new domain,
- the contracts and the zero-tolerance line,
- the hard cases (what looks right but isn't, in that domain),
- the independent check (what second source can confirm the first).
