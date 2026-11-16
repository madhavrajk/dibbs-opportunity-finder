# Working agreement: DIBBS opportunity finder

## Goal
A Streamlit app that pulls today's DIBBS RFQs and helps one vendor (a manufacturer or distributor) find the ones worth
quoting. Reviewer: the SalesPatriot interviewer. **Hard stop at 40 minutes.** No wrong answers; explain every choice.

Priorities, higher wins when they conflict:
1. **Never a wrong identifier.** A solicitation number or NSN off by one character means quoting the wrong part. Code parses
   and validates; no LLM ever writes, edits or "cleans" an identifier. Invalid means flagged and shown, never fixed or dropped.
2. **Never miss a relevant RFQ.** Overmap rather than undermap: rank and explain, don't hide. The only hard filter is
   one the user sets explicitly (quantity min/max), and the UI says how many rows it hid.
3. Save the vendor time: the best matches first, each with the reason it matched, and one click to DIBBS.

## What the interviewer said (full notes: docs/questions.md)
- Vendors know their products as **keywords** in the description, a **list of NSNs**, or **FSC** groups. Some skip qty 1 or large quantities.
- Today's RFQs only, on-demand refresh, scraping is fine, the consent banner is always there, DIBBS is up.
- Link to the DIBBS record page or the PDF. Approved sources (from the solicitation) are worth showing.
- One vendor profile, no auth. Streamlit counts as full stack. An LLM is optional, if it is worth the cost.
- He wants to see the process: questions asked, rationale, gates, agents.

## Facts from recon: read docs/dibbs_recon.md before writing the ingest code
Daily fixed-width `in` file plus `as` approved-source file are the primary sources; the HTML listing is the verifier.
The consent banner needs a POST on each host. Field slices, regexes and URL rules are in that file and were verified.

## Models and agents
The main session (Opus) designs, orchestrates and reviews diffs. It does not write modules itself.
| Agent | Model | Job |
|---|---|---|
| `builder` | Sonnet | One module against `app/contracts.py`, test first, its own files only. Run in parallel |
| `evaluator` | Sonnet | Labelled relevance cases from `docs/` and `tests/fixtures/` only; a hook blocks it from `app/` |
| `verifier` | Haiku | Runs the integrity check (DB versus live DIBBS HTML, field by field) and reports. Mechanical |
| `summarizer` | Haiku | Condenses logs and test output. Never paste long output into the main session |
| `ui-designer` | Opus | Once, after S4: evaluates the UX for executives and paying customers, then redesigns it with every function kept |
| `panel` | Sonnet | Once at the end, if time allows: pass/fail against `docs/criteria.md`, blockers only |

## Stage gates (40 minutes total; plan and prompts in docs/session_plan.md)
| Stage | Ends at | Gate | Commit |
|---|---|---|---|
| S0 restate | 0:03 | Design restated to the interviewer, matching rules agreed | `S0: brief` |
| S1 contracts | 0:07 | `app/contracts.py`, `docs/criteria.md` and the first rationale entries; `pytest` collects | `S1: contracts` |
| S2 thin path | 0:20 | Refresh pulls today's file, validated rows in SQLite, ranked table with reasons and DIBBS links | `S2: thin path` |
| S3 checks | 0:28 | Labelled cases pass; integrity check 0 mismatches on a sample of 50 rows | `S3: checks` |
| S4 approved sources | 0:31 | Company names from the PDF for the top N, "I'm an approved source" boost | `S4: sources` |
| S5 UX redesign | 0:37 | `ui-designer` review in docs/ux_review.md; redesign keeps every listed function; tests green | `S5: UX` |
| S6 write-up | 0:40 | README: how to run, diagram, results, cut list | `S6: done` |
When a timebox ends, cut scope, write the cut under "Next steps" and move on. Commit at every gate, pushed.

## Rules
- After each change: `pytest -q`. At most 3 fix attempts per failure, then cut it and record why.
- Never weaken a test or case to make it pass. A failure found goes into the tests before the fix.
- Append decisions to `docs/rationale.md` as they happen (decision, assumption, why, tradeoff).
- Tests run offline on `tests/fixtures/`; only `refresh` and the verifier touch the network. Be polite: one session,
  no parallel hammering, cache everything by date.
- Real names only for data DIBBS published; no invented rows in the UI. Stub data lives in tests only.

## Run
```bash
pip install -r requirements.txt
streamlit run app/ui.py
pytest -q
python -m app.verify --sample 50     # live check: DB versus the DIBBS HTML listing
```
