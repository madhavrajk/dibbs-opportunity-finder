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
