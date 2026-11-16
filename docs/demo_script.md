# Demo script for the interviewer (about 6 minutes, then questions)

## Set up before the call (off screen)
```bash
cd ~/Downloads/SalesPatriot/dibbs-finder && source .venv/bin/activate
python scripts/gate.py                     # should end in VERDICT: PASS
streamlit run app/ui.py                    # http://localhost:8501, demo profile already saved
```
Open these tabs: the app, `docs/questions.md`, `docs/rationale.md`, `docs/approach_map.md`, and a terminal in the project.
Do one silent run-through first.

---

## 0. Open (15 s)
**Say:** "You asked how a vendor finds the RFQs worth quoting. I'll show the process first, then the product, then
how I know it's right."

## 1. The process (60 s)
| Do | Say |
|---|---|
| Show `docs/questions.md` | "Before building I asked you these. Three answers shaped everything: vendors think in keywords, NSNs or FSCs; overmapping beats missing one; and one wrong digit in an NSN or solicitation number is unacceptable." |
| Show `CLAUDE.md`, the priorities and the stage table | "Priorities in order: never a wrong identifier, never miss an RFQ, then save time. Stages with gates and a commit per gate." |
| Terminal: `git log --oneline` | "One commit per gate: contracts, thin path, checks, sources, UX, and the full verification." |
| Point at the model table in `CLAUDE.md` | "Opus designed and reviewed. Sonnet agents built the modules in parallel against shared contracts. Haiku ran the mechanical checks. The product itself uses no LLM." |

## 2. The product (2 min)
| Do | Say |
|---|---|
| Point at the header and the freshness line, then open **How this batch was fetched** | "This is today's batch. Every refresh leaves a plain-English trace with timing per stage: the consent banner, which file, how many rows, how many flagged." |
| Point at the KPI row: **RFQs in batch 2,725 · Matches for you 352 · Hidden by your qty filter 27** | "For a fastener supplier: 2,725 RFQ lines today, 352 worth a look. 27 are hidden only because the vendor said 'no qty 1', and they're one toggle away." |
| Sidebar: **What you sell** (keywords, NSNs, FSCs, CAGE) and **Quantity filter** | "The three ways you told me vendors think, plus their CAGE code: if they're an approved source, that row jumps up." |
| **For you** tab: point at **Why it matched** on the top row (`FSC 5310 · keyword: nut · keyword: washer`) | "It ranks rather than filters, and every row says why. A bid manager can trust or dismiss a match in a second." |
| Point at a keyword-only row such as "INSERT,SCREW THREAD" | "26 matches came from keywords outside the vendor's FSCs. A pure FSC filter would have missed them." |
| Point at "CYLINDER, FLATWARE WASH" if it's on screen | "And here's the cost of overmapping: DIBBS cuts descriptions at 20 characters, so 'WASH' could be 'WASHER'. I'd rather show it than miss it, and that was your call." |
| Click a row's **Solicitation** link | "Every row opens its own page on DIBBS. The link is built only from the raw solicitation number." |
| **Row detail:** pick `SPE4A6-27-T-073M` → **Load company names from the solicitation PDF** | "Approved sources: CAGE and part number for every NSN come from DIBBS's bulk file. Company names are only in the PDF, so I fetch them on demand and cache them." |
| Click **Shortlist to quote**, then open the **Shortlist** tab | "The vendor's decisions are recorded. When they disagree with the ranking, a script turns that into a candidate test case. A person promotes it. That's how it improves." |

## 3. How I know it's right (90 s): the strongest part
| Do | Say |
|---|---|
| Terminal: `python -m evals.report` | "21 labelled cases, written by an agent that never saw the code: near misses like CAP versus CAPACITOR, a truncated word, an NSN one digit off, an FSC buried in the NIIN. Precision 1.0, recall 1.0, and every identifier byte-identical to the source." |
| Terminal: `python -m app.verify` (cached, about 30 s) | "Zero tolerance means checking every row. This pages through all 55 pages of DIBBS's own listing and compares 2,725 rows field by field." |
| Show the result: **0 field mismatches, 0 missing either way** | |
| Show `docs/rationale.md` D8 | "Earlier the 50-row sample said zero mismatches. The full check found two real problems. A 14-character NSN was being cut to 13, so we displayed a wrong identifier, and the test had encoded the same mistake. And 141 RFQ lines are on DIBBS but not in the daily file. Two of those were matches for this vendor. Both are fixed: the full NSN is read, and the missing lines are merged in and flagged. All 2,584 file rows now match DIBBS exactly." |

## 4. Close (30 s)
**Say:** "So: today's RFQs, ranked for one vendor with reasons, links back to DIBBS, approved sources, a feedback loop,
and an integrity check on every row. Next I'd add an LLM only where it helps, at profile setup: 'describe what you
make' becomes suggested FSCs and keywords. Then a morning email of new matches and award history per NSN."

---

## If he asks
| Question | Answer |
|---|---|
| Why not scrape the pages directly? | "The daily file is one request with identifiers in fixed columns. The pages are about 55 ASP.NET postbacks. I use the pages as the independent check, and to fill the 141 lines the file misses." |
| Why no LLM? | "NSNs, FSCs and CAGEs are exact strings, so code is exact and free. An LLM is useful for vague input ('we machine stainless fittings') at profile setup, and it never touches identifiers." |
| How does it scale to many vendors? | "Ingest once per day for everyone; matching is pure and runs in milliseconds per vendor. Then saved profiles per tenant, a morning digest, and PDF parsing on a queue for matched rows only." |
| What would you not trust yet? | "The meaning of the trailing code column (probably set-aside or AMSC) isn't decoded. Keyword matching is lexical. And verify compares against the listing that also fills the gaps, so for those 141 rows it's by construction; the 2,584 file rows are the independent proof." |
| How long did it take? | "The functional build was about 10 minutes of agent time after the questions. Then I extended the check to every row, which found the two real issues above." |
| What did you get wrong? | "My recon slice for the NSN. The checks caught it, which is why I check everything against a second source." |

## Do not
- Run `python -m app.verify --no-cache` live on the call: it takes about 3 minutes cold.
- Present the 141 merged rows as independently verified.
