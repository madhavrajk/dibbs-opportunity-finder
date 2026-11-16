# Rationale

Append as you go, one entry per decision. If blocked, make a reasonable assumption, record it here, and continue.

## Decisions

### D0. Use the daily `in`/`as` files as the source and the HTML listing as the verifier (from recon, before the session)
- **Decision:** parse `inYYMMDD.txt` (fixed width) and `asYYMMDD.txt`, found via the Recent RFQs page.
- **Assumption:** the newest file is the set issued today (checked 11-16: page 1 of the listing was 50/50 in the file).
- **Why:** one request versus about 55 ASP.NET postbacks; identifiers come in fixed columns, so nothing is guessed.
- **Tradeoff:** about 140 records appear in the HTML but not in the file (unexplained). The 20-character description is truncated.

## Gate log

| Stage | Time | Tests | Integrity mismatches | Cases | Note |
|---|---|---|---|---|---|
| S1 contracts | 0:03 | 2/2 | n/a | n/a | contracts, links, display formats |

### D1. Rank, don't filter
- **Decision:** profile hits add score and a reason; only qty min/max hides rows, and the UI shows how many it hid.
- **Assumption:** a vendor would rather skim 30 extra rows than miss one RFQ (interviewer: "overmap rather than undermap").
- **Why:** a keyword miss caused by the 20-character truncation, or by DIBBS's NOUN,MODIFIER wording, is invisible to the user. A low score is not.
- **Tradeoff:** a longer "For you" list. Mitigated by sorting on score, then the soonest return-by date.

### D2. No LLM touches identifiers; matching is code
- **Decision:** solicitation numbers, NSNs and CAGE codes are copied byte for byte and validated by regex; invalid ones are flagged, never fixed.
- **Why:** zero tolerance. A one-character change means quoting the wrong part. Exact string matching is also free and instant.
- **Tradeoff:** no semantic matching ("fastener" will not find "SCREW"). Next step: an LLM suggests keywords and FSCs at profile setup and the user confirms them.

### D3. Subagents on cheaper models; evaluator isolation by instruction
- **Decision:** Opus orchestrates, Sonnet builds and evaluates, Haiku verifies and summarises.
- **Note:** this session's Agent tool runs general-purpose agents with a model override. The `.claude/agents` hook that blocks the evaluator from `app/` only applies when the evaluator runs as a project agent, so here the isolation is an instruction, not enforced.

### D4. Match scoring: NSN 100, approved-source CAGE 80, FSC 40, keyword 30 each
- **Decision:** additive scores, each with a human-readable reason; sorted by score, then the soonest return-by date.
- **Why:** an exact NSN means "you make this part". Being an approved source means you can win it outright. An FSC is the product family. A keyword is the weakest signal.
- **Keyword rules:** whole words only ("CAP" never matches "CAPACITOR"), plus simple plurals. The last word is prefix-matched only when DIBBS's 20-character field is full, i.e. the word was cut off.
- **Review fix (orchestrator):** the builder detected truncation by `len == 20`. The raw field is space-padded to 20, so every row would have counted as truncated ("PINION" would match "SPRING,PIN"). Changed it to `len(rstrip) >= 20` and added a test. The "hidden by qty" count now covers matched rows only, otherwise it counts thousands of irrelevant rows.

### D5. The integrity check compares against DIBBS's own HTML listing, field by field
- **Decision:** `python -m app.verify` fetches page 1 of the live issue-date listing (50 rows) and compares sol, NSN, qty, PR, return-by date and the PDF link with the stored rows. It exits 1 on any mismatch.
- **Result (live, 12:57):** 50 checked, 50 found, 0 missing, 0 mismatches on every field.
- **Review note:** one solicitation and NSN can appear on several lines (different PRs), so a live row is compared with each stored line for that key. It counts as clean only if one of them is identical in every field, so this cannot hide a wrong identifier.
- **Tradeoff:** it checks a 50-row sample from page 1, not all 2,584. Paging the rest needs ASP.NET postbacks; that's the next step.

### D6. Approved-source names only on demand
- **Decision:** CAGE and P/N for every row come from the bulk `as` file (1,803 NSNs). Company names come from the solicitation PDF only when the user asks, and are cached per solicitation.
- **Why:** 2,458 PDFs at roughly 400 KB each would be about 1 GB a day and thousands of requests to a government site.
- **Live check:** SPE4A727T4218 gave 9 named sources, the same as the hand count from the fixture.

| S2 thin path | 0:04 | 57/57 | n/a | 21/21 | live ingest 2,584 rows, 2,458 sols, 8 flagged, 1,803 approved NSNs |
| S3 checks | 0:05 | 59/59 | 0 / 50 | 21/21 | evaluator labelled blind; verifier 0 mismatches |

### D7. UX redesign for executives and paying customers (Opus designer)
- **Decision:** a KPI header with data freshness, a "For you" list with status, due-in and score columns, Line and PR columns for multi-line solicitations, and company names from the PDF on demand. It inventoried all 23 functions before changing anything and kept every one.
- **Bug found by the designer:** the detail picker was keyed by solicitation number, so 126 of 2,584 lines (17 of 350 matches) could never be opened. Now there is one option per line. This is the "never miss" priority showing up in the UI.
- **Orchestrator review:** no DIBBS URL is built outside `contracts.py`; the only network calls are the Refresh and Load-names buttons; 60/60 tests pass; renders on live data.
- **Not reached (honest scores of 7):** no "new since yesterday" view, no export, no issue date stored (only the posted date).

| S5 UX | 0:09 | 60/60 | 0 / 50 | 21/21 | 23/23 functions kept |
| S6 write-up | 0:10 | 60/60 | 0 / 50 | 21/21 | README final |

### D8. The live check covers every row, and it found a wrong identifier and 141 missed lines
- **Decision:** `python -m app.verify` now pages through the whole issue-date listing (55 ASP.NET postback pages, 2,725 rows; about 165 s cold, 26 s cached) and compares in both directions, keyed by (sol, NSN, PR).
- **Found 1: a wrong identifier shown to users.** The 14-character NSN `N4215863170925` was stored as `N421586317092`. The source was my recon slice `[13:26]`, and the evaluator's byte-equality test inherited it, so the tests encoded the bug. It was flagged "non-standard" but still displayed wrong. Fix: read the full token from `[13:62]`.
- **Found 2: 141 RFQ lines on DIBBS but not in the daily file** (113 extra lines on known solicitations, 28 unknown solicitations; mostly return-by 11-23 and 11-27). That breaks priority 2, "never miss". Fix: merge listing-only rows, copied byte for byte and flagged "from DIBBS listing (not in daily file)".
- **Found 3 (in the checker itself):** a "Mil-Spec" tag under the NSN on the listing gave 157 false mismatches; the parser was fixed.
- **Lesson:** a 50-row sample said 0 mismatches. Only checking every row against an independent source found the defect. This is the RFI-retro lesson again: green checks only mean no known failure came back.
- **Re-verified by the orchestrator (13:14):** 55 pages, 2,725/2,725 rows, 0 field mismatches, 0 missing either way; `SPE7M027T1283` now stores `N4215863170925` (flagged as longer than 13). Caveat: the 141 merged rows came from the listing, so they match it by construction. The independent result is that all 2,584 daily-file rows are identical to DIBBS's own listing.

| Full verify | 0:22 | 71/72 (1 known UI tab-count test) | 0 / 2,725 | 21/21 | NSN fix + 141 merged lines |
