# Pass/fail criteria

Written at S1, before the build. The panel checks these and nothing else. Each one can be checked by running something.

| # | Criterion | How to check |
|---|---|---|
| 1 | Every solicitation number and NSN shown equals the source bytes | `pytest -q tests/test_cases.py`; `python -m app.verify --sample 50` shows 0 mismatches |
| 2 | Invalid identifiers are flagged, never fixed or dropped | `pytest -q tests/test_ingest.py` (non-standard NSN fixture row present, flagged) |
| 3 | Every row opens its own DIBBS record page and PDF | link-format test; click one in the app |
| 4 | No relevant RFQ hidden silently: only the user's qty filter hides rows, and the UI shows the count | `pytest -q tests/test_match.py` |
| 5 | Every match says why it matched | `streamlit run app/ui.py`: a reason chip on each row in "For you" |
| 6 | <filled at S1> | <command> |
