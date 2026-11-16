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
