# Session plan: 40 minutes, hard stop

Keep this open beside the terminal. One prompt per stage; read what comes back (the diff, `docs/rationale.md`, the test line).

## Before the clock starts
- [ ] `cd dibbs-finder && git init && git add -A && git commit -m "S0: starter (agents, recon, fixtures)"`; create the GitHub repo and push.
- [ ] `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- [ ] `python -I scripts/dibbs_fetch.py /tmp/dibbs "/Rfq/RfqDates.aspx?category=recent"` should print a 200. That proves the network passes the WAF and the banner.
- [ ] `claude`, then `/agents` should list builder, evaluator, verifier, summarizer, panel.
- [ ] Tell the interviewer in one line: "I brought a starter: agents, a working agreement, DIBBS recon notes and offline fixtures. No app code."

## S0 Restate (0:00 to 0:03): say it, don't build
"A vendor knows their products as keywords, NSNs or FSCs, maybe with quantity limits. Missing an RFQ is worse than
noise, so I rank and explain rather than hide. Identifiers are zero-tolerance, so code parses and validates them and an
LLM never touches them. I pull today's daily file in one request instead of paging 55 HTML pages, and I use the HTML
listing to verify the file. Approved-source names come from the PDF, for the top matches only."

## S1 Contracts (0:03 to 0:07)
```
Read CLAUDE.md and docs/dibbs_recon.md. No implementation yet. Write:
1. app/contracts.py (pydantic):
   - Solicitation: sol, nsn, fsc, pr, return_by (date), qty (int), ui, nomenclature, codes, issue_date,
     flags (list[str]), record_url, pdf_url
   - ApprovedSource: nsn, cage, part_no, name (optional)
   - Profile: keywords, nsns, fscs, cage (optional), qty_min (optional), qty_max (optional)
   - Match: sol (Solicitation), score (int), reasons (list[str]), hidden_by (optional str)
2. docs/criteria.md: fill row 6 onwards for this problem; keep it checkable by running something.
3. docs/rationale.md: D1 daily file over HTML, D2 rank-not-filter, D3 no LLM on identifiers.
4. requirements.txt is done. Make pytest collect.
```
**Check:** does `Profile` hold what the interviewer described? Is `flags` there for invalid identifiers? Then commit.

## S2 Thin path (0:07 to 0:20): 3 builders in parallel
```
Use 3 builder agents in parallel, each with only its own files, all against app/contracts.py:
A) app/ingest.py + tests/test_ingest.py: session with browser headers, consent POST on both hosts (reuse
   scripts/dibbs_fetch.py logic), find the newest in/bq links on the Recent page, parse `in` with the slices in
   docs/dibbs_recon.md, parse as*.txt from the bq zip, validate with the recon regexes (flag, never fix), build both
   URLs, cache raw files under data/YYMMDD/, store in SQLite data/dibbs.db. Tests on tests/fixtures only.
B) app/match.py + tests/test_match.py: score(profile, solicitation, approved_sources) -> Match.
   NSN exact on the raw 13 chars = 100; vendor CAGE among the approved sources = 80; FSC == nsn[:4] = 40;
   keyword = 30 each, matched on word boundaries over nomenclature tokens split on spaces and commas, case
   insensitive, also as a prefix of the last token (the 20-char truncation). Every hit adds a human reason string.
   Qty min/max is the only hard filter: set hidden_by and keep the row. Sort by score desc, then return_by asc.
C) app/ui.py: Streamlit. Sidebar profile (keywords, NSNs pasted or CSV, FSCs, CAGE, qty min/max), saved to
   data/profile.json. Top bar: "Issued <date> · N RFQs · Refresh". Tabs: "For you" (matches with reason chips,
   "N hidden by your qty filter" with a show toggle) and "All RFQs" (search box and column filters).
   Columns: Solicitation (link to record page), NSN (####-##-###-####), Description, Qty+UI, Return by
   (days left, red when 2 or fewer), PDF link. Read from SQLite only; never call DIBBS on render.
Then integrate, run pytest -q, and launch streamlit once to confirm the first screen renders.
```
**While they run:** read `docs/rationale.md` and decide what you would challenge.
**Check:** click Refresh, pick a real row, open its DIBBS link, and compare the solicitation number and NSN by eye. Commit and push.

## S3 Checks (0:20 to 0:28): evaluator (Sonnet) and verifier (Haiku) in parallel
```
In parallel:
1) evaluator agent: write tests/cases.json and tests/test_cases.py (sample profile, 15-20 labelled rows from the
   fixtures, near misses per its brief, identifier byte-equality, link format).
2) builder agent: app/verify.py: fetch the issue-date HTML listing for the stored issue date (page 1, plus page 2
   via __doPostBack if quick), and for each row compare sol, NSN, qty and return-by against SQLite. Print the
   counts by field and a non-zero exit code on any mismatch. Then the verifier agent runs `python -m app.verify --sample 50`.
Then run pytest -q. Fix the code, not the labels, at most 3 attempts per failure; log each fix in rationale.
```
**Check:** read 3 labels yourself. Would a vendor agree? The integrity check should show 0 mismatches. Commit.

## S4 Approved sources (0:28 to 0:31)
```
builder: app/sources.py: for the top 20 matches (and on row expand), fetch the solicitation PDF (dibbs2 consent),
extract text with PyMuPDF, parse `<NAME> <CAGE5> P/N <PN>` lines (see tests/fixtures/SPE4A727T4218.txt), cache the result
by solicitation. Join on CAGE with the as-file rows; show "Approved sources: NAME (CAGE) P/N" in the row
detail; flag name/CAGE disagreements. Add a test on the fixture text. UI: an "Approved source" column showing a
count and the expander.
```
**Check:** open one with sources and compare it against the PDF on DIBBS. Commit.

## S5 UX redesign (0:31 to 0:37): ui-designer (Opus)
```
Use the ui-designer agent: evaluate the UX for an executive audience and for paying customers, inventory every
function, redesign app/ui.py keeping all of them, keep pytest green, write docs/ux_review.md.
```
**Check:** open the app; tick the "Functions to keep" list yourself. Commit.

## S6 Write-up (0:37 to 0:40)
```
Write README.md: what it does, how to run, an ASCII diagram (DIBBS -> ingest+validate -> SQLite -> match -> Streamlit),
matching rules and why, the integrity-check result, eval results, what was cut and why, next steps
(LLM profile builder, alerts, multi-profile, award history). Under 1 page. If 2+ minutes remain, run the panel agent once.
```
Commit and push at 0:40. **Stop at 0:40 whatever the state.**

## If you are behind
| At | If | Then |
|---|---|---|
| 0:12 | The consent or WAF fails from this network | Load the `in` file from `tests/fixtures/` behind the same parser, label it "snapshot" in the UI, and keep going |
| 0:20 | The thin path doesn't run end to end | Cut the UI to one table with links. Ranking and links beat filters |
| 0:28 | The verifier is not done | Skip it and show the regex validation counts instead. Cut the evaluator to 8 hand-picked cases |
| 0:34 | PDF parsing isn't working | Show CAGE and part number from the as-file only; list names as next steps |
| 0:36 | Anything | Stop building. Write the README and push |

## Only if ahead: the LLM nice-to-have (Haiku, cheap)
"Describe what you make" → Haiku suggests FSCs and keywords → the user ticks which to keep → saved into the profile.
The LLM writes profile suggestions only, never rows or identifiers. Needs an API key: ask the interviewer first.

## Demo order (3 minutes)
1. Notes: the questions you asked and the interviewer's answers (docs/questions.md), then CLAUDE.md priorities.
2. The app: set the profile, open "For you", point at the reason chips, the qty-hidden count, the days-left column and an approved source.
3. Click through to DIBBS on one row.
4. The integrity check output: 0 mismatches against live DIBBS. Then the cases.
5. `git log --oneline`: one commit per gate. `docs/rationale.md`: the calls you made and what you cut.

## Likely questions
| Q | A |
|---|---|
| Why the daily file and not scraping the pages? | One request instead of about 55 postbacks, fixed-width exact identifiers, and the same data. The HTML is still used: as the independent check |
| Why rank instead of filter? | The interviewer said overmapping beats undermapping. The only hiding is a filter the user set, and it shows the count |
| Why not an LLM for matching? | The identifiers are exact strings, so code is exact and free. An LLM helps build the profile, not judge rows |
| How would this scale? | Daily cron after the overnight post, cache per date, PDF parsing on a queue for matched rows only, alerts by email or Slack |
| What's still unknown? | About 140 records in the HTML but not in the file; the meaning of the trailing code field; whether `ca` is cancellations |
