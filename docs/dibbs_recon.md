# DIBBS recon (checked 2026-11-16, read-only)

Everything below was fetched and checked against live pages. Fixtures from that day are in `tests/fixtures/`.

## Access
- **WAF:** a bare user-agent gets an F5 "Request Rejected" page. Send browser headers (User-Agent, Accept, Accept-Language).
- **Consent banner:** every host shows a DoD warning page first. It is an ASP.NET form: POST all hidden inputs
  (`__VIEWSTATE*`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`) plus `butAgree=OK` to the form's `action`, keep the cookies,
  then GET the target again.
  - `www.dibbs.bsm.dla.mil` redirects to `/dodwarning.aspx?goto=...`.
  - `dibbs2.bsm.dla.mil` (downloads, PDFs) serves the consent page **in place, without a redirect**. Detect it by
    `name="butAgree"` in the body, not by URL. It needs its own consent; the cookies are per host.
  - `scripts/dibbs_fetch.py` does all of this and works.

## Data sources: use the daily files, keep HTML for verification
| Source | URL | What it gives | Verdict |
|---|---|---|---|
| Daily index file | `https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/inYYMMDD.txt` | Fixed width, 140 chars, one line per solicitation line item | **Primary.** One request, exact identifiers |
| Approved sources | `bqYYMMDD.zip` → `asYYMMDD.txt` | CSV `"NSN","CAGE","PART_NO",""` | **Primary** for approved-source CAGE and part number |
| Batch quote file | `bqYYMMDD.zip` → `bqYYMMDD.txt` | CSV, 121 fields per row (format documented on DIBBS under "Batch Quoting File Format") | Optional: set-aside and other flags |
| Cancellations? | `caYYMMDD.zip` | Not opened | Unverified |
| Issue-date listing | `/RFQ/RfqRecs.aspx?category=issue&TypeSrch=dt&Value=MM-DD-YYYY` | HTML grid, 50 rows a page, paged by `__doPostBack` | **Verifier only:** cross-check rows field by field |
| Recent list | `/Rfq/RfqDates.aspx?category=recent` | Links to every daily `in`, `bq` and `ca` file | **Use it to find the latest file**, don't compute dates |

**"Today" is the latest posted file.** `in261115.txt` (posted overnight on 11-15) is the set issued **11-16**: all 50 rows on
page 1 of the 11-16 listing are in it. On 11-16 the file `in261116.txt` did not exist yet. So: read the Recent page,
take the newest `in` link, and show its issue date in the UI.

**Volume:** 2,584 lines and 2,458 unique solicitations in one day (some solicitations have several lines). The HTML
listing said "Records Found: 2725" for the same date, so about 140 more appear in the HTML than in the file.
Unexplained: say so in the README rather than guess.

## `in` file layout (0-based Python slices, every line is exactly 140 chars)
The file has **CRLF line endings**: decode as latin-1 and use `splitlines()`. `split("\n")` leaves a `\r` that shifts
nothing but pollutes the last field. `tests/fixtures/in_sample.txt` has 313 lines: the first 300 of the 11-16 file plus 8
non-standard NSNs and 5 solicitation numbers ending in a letter. 72 of them repeat a solicitation number (multi-line RFQs).
| Slice | Field | Example |
|---|---|---|
| `[0:13]` | Solicitation number | `SPE1C127T0119` |
| `[13:26]` | NSN (13) | `8465012768198` |
| `[26:62]` | Blank in the sample (maybe part number when there is no NSN) | |
| `[62:72]` | Purchase request number | `7019120187` |
| `[72:80]` | Return-by date `MM/DD/YY` | `11/27/26` |
| `[80:97]` | PDF filename | `SPE1C127T0119.pdf` |
| `[97:106]` | Quantity, zero padded | `  0000012` |
| `[106:108]` | Unit of issue | `EA` |
| `[108:128]` | Nomenclature, **truncated to 20 chars**, DIBBS style `NOUN,MODIFIER` | `SNAP LINK,RAPPELLER` |
| `[128:140]` | Codes (unknown; probably set-aside or AMSC style flags) | ` PSPTPZ1N000` |

## Zero-tolerance checks (run on the whole 11-16 file)
- Solicitation number: `^SP[A-Z0-9]{4}\d{2}[A-Z][A-Z0-9]{4}$`. **0 failures in 2,584.** The serial can end in a letter
  (`SPE4A627T065C`). An earlier stricter regex rejected 717 good rows. **Never "fix" an identifier; flag it.**
- NSN: 13 digits. **8 lines are not standard NSNs**, e.g. `5365LN0021113` (a local "LN" number) and `N4215863170925`.
  Keep them, mark them "non-standard NSN", and match on them exactly; don't drop them.
- FSC = NSN `[0:4]`. Top FSCs that day: 5305 screws (126), 6515 medical (121), 5310 nuts and washers (120), 5306 bolts, 5340 hardware.
- PDF filename `[80:97]` == solicitation + `.pdf`: a free cross-check, 0 mismatches.
- Display the NSN as `####-##-###-####` and the solicitation as `SPE4A5-27-Q-0073`, the way DIBBS shows them; the stored value stays raw.

## Links (the "open on DIBBS" requirement)
- Record page: `https://www.dibbs.bsm.dla.mil/rfq/rfqrec.aspx?sn=<SOL>`, the "original page".
- PDF: `https://dibbs2.bsm.dla.mil/Downloads/RFQ/<last char of SOL>/<SOL>.PDF`. Checked for digit and letter endings (`/C/`).
- NSN history: `https://www.dibbs.bsm.dla.mil/RFQ/RFQNsn.aspx?value=<NSN13>&category=issue&Scope=`
- A user who has not accepted the banner sees it once, then the page (interviewer: acceptable).

## Approved sources with company names
- The record page does **not** list approved sources.
- The **solicitation PDF** does, as lines like `NORDAM GROUP LLC, THE 29957 P/N 4J52001-132B`, so
  `^(?P<name>.+?)\s+(?P<cage>[A-Z0-9]{5})\s+P/N\s+(?P<pn>\S+)$` on `pdftotext -layout` or PyMuPDF text. Sample:
  `tests/fixtures/SPE4A727T4218.txt` (around line 560; 21-page PDF, about 400 KB).
- `asYYMMDD.txt` already has CAGE and part number for 1,803 NSNs in bulk, so names are the only thing the PDF adds.
  Plan: CAGE and part number for every row from the `as` file; company names from the PDF **for the top matches or on row
  expand**, cached by solicitation. Don't fetch 2,500 PDFs.
- When a name from the PDF and a CAGE from the `as` file disagree, show both and flag it. The `as` file wins for the CAGE.
