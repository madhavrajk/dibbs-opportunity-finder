# UX review (ui-designer, S5)

Evaluated by rendering `app/ui.py` against the live DB (`data/dibbs.db`, batch in261115.txt, 2,584 lines) with the demo
fastener profile: 350 matches, 27 hidden by qty, 0 due within 3 days.

## Scores before
- **Executive (10 s): 5/10.** Four plain metrics answer "how many / how many mine", but nothing says the data is
  today's and real (fetch time shows only `12:56`, no date, no age), no approved-source signal, and the page opens on an
  unstyled title with no statement of value.
- **Bid manager at 7 a.m.: 4/10.** Ranked table with reasons and links works, but: same-solicitation lines look like
  duplicate rows (79 solicitations have 2 to 18 lines; PR is not a column); the row-detail picker is keyed by solicitation
  number so 126 of 2,584 lines (17 of 350 in "For you") can never be opened; Qty and Return by are strings so they sort
  wrong; Score is a bare integer.

## Top 5 problems
1. **Lines lost in detail** (priority 2 risk): picker collapses lines sharing a solicitation number.
2. **Scannability**: no PR / line count, no status word for urgency, score not visual, dates and qty unsortable.
3. **Trust signals**: no fetch date or age, no flagged-row count, approved sources show CAGE only (names never loaded).
4. **Hierarchy and copy**: generic title, profile sidebar reads as a raw form, `st.write` dict dump in detail.
5. **States**: no "profile set but nothing matched" state; detail shows `None` fields; deprecated `use_container_width`.

## Functions to keep
| # | Function | Where it lives after |
|---|---|---|
| 1 | Sidebar: Company name | Kept: Sidebar > Your profile (same label) |
| 2 | Sidebar: Keywords | Kept: Sidebar > What you sell, with example help text |
| 3 | Sidebar: NSNs text (dashes ok) | Kept: Sidebar > What you sell |
| 4 | Sidebar: NSN upload CSV/TXT | Kept: Sidebar > What you sell |
| 5 | Sidebar: FSCs | Kept: Sidebar > What you sell, help explains FSC = first 4 NSN digits |
| 6 | Sidebar: Your CAGE code | Kept: Sidebar, help says it boosts approved-source rows |
| 7 | Sidebar: Qty min / Qty max (0 = unset) | Kept: Sidebar > Quantity filter, caption says it is the only hiding filter |
| 8 | Sidebar: Save profile + success message | Kept: Sidebar, primary button + success |
| 9 | Refresh button, spinner, error shown, cache clear + rerun | Kept: Header, right of title; same spinner, error, cache clear, rerun |
| 10 | Batch line: posted date, fetched time, source file | Kept: Header line, now with fetch date, age and source |
| 11 | Empty state: no data, click Refresh | Kept: Main area, same copy + size hint |
| 12 | Metrics: RFQs in batch, Matches for you, Hidden by qty, Due within 3 days | Kept: KPI row (bordered), same 4 in same order, each with a context line |
| 13 | Tabs: For you / All RFQs | Kept: Tabs, now with counts: For you (350) / All RFQs (2584) |
| 14 | For you: empty-profile help (three ways to match) | Kept: For you, rewritten with bold keywords / NSNs / FSC + examples |
| 15 | For you: toggle "Show N rows hidden by your qty filter" | Kept: For you; count now equals the KPI (27, was 512 incl. zero-score rows) |
| 16 | All RFQs: search (sol, NSN, description), FSC multiselect, due-within slider, "x of y" count | Kept: All RFQs, same three filters + count; search has a placeholder |
| 17 | Columns: Solicitation (link to record), NSN, Description, Qty, Return by (+days), Why it matched (HIDDEN prefix), Score, PDF link, Approved sources count, Flags | Kept: Both tables; all kept, plus Status, Line, PR, Unit, Due in. Return by is a DateColumn, Score a ProgressColumn, Flags hidden only when no row has a flag |
| 18 | Row detail picker per tab | Kept: Below each table; click a row or pick; one option per line (2,584 / 350, was 2,458 / 333) |
| 19 | Detail: header sol / NSN / FSC; description, qty, unit, return by, PR, codes, posted, score, why, hidden by | Kept: Detail card: header + 6 facts + why + hidden note |
| 20 | Detail: flags as warnings | Kept: Detail card, 'Flagged: ... shown exactly as published' |
| 21 | Detail: approved sources table (CAGE, part number, name) | Kept: Detail card, plus Company and 'Listed in' columns; new button loads names from the PDF on click, reconcile() flags as warnings |
| 22 | Detail: buttons DIBBS record, Solicitation PDF, NSN history | Kept: Detail card, same three buttons |
| 23 | Pure helpers: split_terms, clean_nsn, parse_nsn_text, parse_nsn_upload, dedupe, profile_is_empty, load/save_profile, days_left, build_rows, for_you, filter_all | Kept: All kept in app/ui.py; added line_numbers, row_label, status_word, merge_sources, kpis, age_text |

**Kept: 23/23.** Nothing removed.

## Scores after
- **Executive: 7/10.** Title states the value; KPI cards add context (2,458 solicitations; 196 matches with approved
  sources on file); freshness shows date, age and source file; flagged-row count is stated. Still no trend or
  "versus yesterday", and the issued date is not stored in the snapshot, so only the posted date is shown.
- **Bid manager: 7/10.** Every line reachable and distinguishable, sortable dates/qty, status words, score bars,
  click-to-detail, company names on demand. Still a wide table on small screens; no export.

## Before → after
- Detail picker keyed by row, not solicitation number: 126 lines (17 in For you) were unreachable, now none.
- Line ("n of N") and PR columns, plus an "All N lines on this solicitation" table in detail: multi-line solicitations no longer look like duplicates.
- Status column and badge in words (Due today / Due soon / Open / Hidden (qty)): colour is never the only signal.
- Qty number + Unit, Return by as a date, "Due in" days: columns sort correctly.
- Score as ProgressColumn scaled to the view's max: rank is visible at a glance.
- KPI cards with context lines and a freshness line (date, age, source file): trust for a 10-second read.
- Caption on flagged identifiers and multi-line solicitations: says what the data is, not just shows it.
- Hidden toggle counts only hidden matches, consistent with the KPI (27, was 512).
- Load company names from the solicitation PDF: on click only, spinner, error shown inline, result kept in session; reconcile() differences shown as warnings; PDF-only CAGEs listed, never dropped.
- Table click selects the detail row (single-row selection); selectbox stays as fallback.
- Profile sidebar grouped into "What you sell" / "Quantity filter" with help text; Save is the one primary button.
- Empty and no-match states: the first teaches the three ways to match; the second suggests broader terms.
- `use_container_width` replaced with `width="stretch"`; `.streamlit/config.toml` sets one blue accent on a light theme.
- Tests added: multi-line rows distinct, merge keeps PDF-only sources, PDF names never fetched on render (only on click).
