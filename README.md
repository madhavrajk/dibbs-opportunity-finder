# DIBBS Opportunity Finder

Pulls today's DLA DIBBS RFQs and ranks them for one vendor (a manufacturer or distributor) by how likely they are to
be worth quoting. Every match says why it matched, and every row opens its own page on DIBBS.

## Run
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m app.ingest                 # pull today's batch (about 10 s), or use Refresh in the app
streamlit run app/ui.py              # http://localhost:8501
python -m app.verify --sample 50     # integrity check against the live DIBBS listing
pytest -q                            # offline; fixtures only
```

## How it works
```
 DIBBS "Recent RFQs" page ──► newest inYYMMDD.txt (fixed width, ~2,600 lines)
                          └─► bqYYMMDD.zip → asYYMMDD.txt (approved sources: NSN, CAGE, P/N)
        │  consent banner handled on both hosts; files cached in data/YYMMDD/
        ▼
 ingest: parse by fixed columns ─► validate (regex) ─► flag, never fix ─► SQLite
        ▼
 match: profile (keywords · NSNs · FSCs · CAGE · qty limits) ─► score + reasons     (pure code, no LLM)
        ▼
 Streamlit: "For you" ranked list · "All RFQs" search · row detail ─► DIBBS record page / PDF
        │
        └─ on demand: solicitation PDF ─► approved-source company names (cached)

 verify: DIBBS HTML listing ──► field-by-field comparison with SQLite (zero-tolerance check)
```

## Choices, and why
| Choice | Why |
|---|---|
| **The daily file, not page scraping** | One request instead of about 55 ASP.NET postbacks. Identifiers sit in fixed columns, so nothing is inferred. The HTML listing is still used, as the independent check |
| **Rank, don't filter** | Interviewer: better to overmap than undermap. Only the user's quantity limits hide rows, and the app shows how many it hid |
| **Matching in code, not an LLM** | NSNs, FSCs and CAGEs are exact strings: code is exact, instant and free. On today's batch the keyword rules found 25 relevant rows outside the vendor's FSCs |
| **Identifiers are never edited** | One wrong digit means quoting the wrong part. Invalid ones are flagged and shown (8 non-standard NSNs today) |
| **Approved-source names on demand** | CAGE and P/N for all 1,803 NSNs come from the bulk file. Names need the PDF (about 400 KB each), so they're fetched per row and cached |

Matching rules: exact NSN +100 · vendor CAGE among the approved sources +80 · FSC (first 4 digits of the NSN) +40 ·
keyword +30 each, whole words and plurals only ("CAP" never matches "CAPACITOR"), with the last word prefix-matched when
DIBBS's 20-character description was cut off. Sorted by score, then the soonest return-by date.

## Results (2026-11-16 batch, posted 11-15)
| Check | Result |
|---|---|
| Live ingest | 2,584 lines · 2,458 solicitations · 8 flagged (non-standard NSN) · 1,803 NSNs with approved sources |
| Identifier validation over the whole file | 0 invalid solicitation numbers; 8 non-standard NSNs kept and flagged |
| Integrity check against live DIBBS (page 1, 50 rows) | 50/50 found · 0 mismatches in sol, NSN, qty, PR, return-by date and PDF link |
| Blind labelled cases (written by an agent that never saw the code) | 21/21, plus byte equality on 313 fixture lines |
| Unit tests | all passing, offline |
| Demo profile (fastener supplier) | 350 matches · 27 hidden by qty ≥ 2 |
| UX review (Opus designer, `docs/ux_review.md`) | executive 5 → 7, bid manager 4 → 7; all 23 functions kept; fixed 126 lines that could not be opened in detail |

## How it was built
Staged with gates and a commit per gate (`git log`). Opus orchestrated and reviewed diffs; Sonnet agents built ingest,
match, UI, sources and verify in parallel against `app/contracts.py`; a Sonnet evaluator wrote the labelled cases
without reading the code; Haiku ran the live integrity check; Opus did the UX review and redesign
(`docs/ux_review.md`). Decisions and the fixes I made on review are in `docs/rationale.md`. DIBBS recon notes are in
`docs/dibbs_recon.md`, and the questions asked before building are in `docs/questions.md`.

## Limits
- The integrity check covers 50 rows from page 1, not all 2,584 (paging needs ASP.NET postbacks).
- About 140 records appear in the HTML listing but not in the daily file; unexplained.
- Descriptions are DIBBS's 20-character truncation. The trailing code field isn't decoded yet (probably set-aside or AMSC).
- Keyword matching is lexical: "fastener" will not find "SCREW". One vendor profile, no auth (as agreed).

## Next steps
1. **LLM profile builder (Haiku, cents a day):** "describe what you make" → suggested FSCs and keywords → the vendor confirms. The LLM never touches identifiers.
2. Alerts: email or Slack each morning with the new matches above a score.
3. Decode the set-aside and AMSC codes (from the `bq` file's 121 fields) and add them as filters.
4. Award history per NSN (who won, at what price) to rank by win likelihood.
5. Full-listing verification via postback paging; scheduled daily ingest after the overnight post.
