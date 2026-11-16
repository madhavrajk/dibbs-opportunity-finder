# Demo script for the interviewer (about 5 minutes)

## The whole story in one breath
> "Every day DIBBS posts thousands of RFQs. I built a tool that pulls today's list, ranks it for one vendor, explains
> why each one matched, and links straight back to DIBBS. And I check every row against DIBBS so no part number is ever wrong."

---

## Before the call (off screen)
```bash
cd ~/Downloads/SalesPatriot/dibbs-finder && source .venv/bin/activate
python scripts/gate.py        # must say VERDICT: PASS
streamlit run app/ui.py       # opens the app in the browser
```
Have open: the app, `docs/questions.md`, and a terminal. Practise once.

**Tip:** if you click Refresh on the day, DIBBS gives a new batch and the numbers change. Read them off the screen instead of saying the ones below.

---

## Part 1: How I worked (1 minute)

**Show `docs/questions.md`.**
> "Before writing any code, I asked you questions. Three answers shaped the whole design:
> 1. Vendors search by **keywords**, **part numbers (NSNs)** or **product groups (FSCs)**.
> 2. It's better to **show too many than miss one**.
> 3. A part number or solicitation number must **never be wrong**, not even one digit."

**Then say:**
> "I used AI agents like a small team. A strong model planned and reviewed the work. Cheaper models wrote the code
> in parallel, and the cheapest model ran the checks. I saved my work after every step, so there's a clear history."

---

## Part 2: The app (2 minutes)

**1. Point at the four numbers at the top.**
> "Today DIBBS has **2,725** RFQs. For this fastener supplier, **352** are worth a look. **27** are hidden only because
> the vendor said 'no orders of 1', and they can show them with one click."

**2. Point at the left sidebar.**
> "This is the vendor's profile: the words they sell, their part numbers, their product groups, and their company code.
> If they're an approved supplier for a part, that RFQ moves to the top."

**3. Point at the "Why it matched" column.**
> "Every row says why it's there, for example 'FSC 5310, keyword: nut'. The bid manager can decide in a second."

**4. Click a solicitation number.**
> "One click opens the real page on DIBBS."

**5. Pick a row in "Row detail" and click "Load company names from the solicitation PDF".**
> "This shows which companies are approved to supply this part. The names are only in the PDF, so I read it when you ask."

**6. Click "Shortlist to quote", then open the Shortlist tab.**
> "The vendor marks what they'll quote. If they disagree with my ranking, that turns into a new test case, so the
> tool gets better over time."

---

## Part 3: How I know it's right (1.5 minutes): the strongest part

**1. In the terminal run `python -m evals.report`.**
> "I had a separate AI agent write 21 test cases **without seeing my code**, including tricky ones like 'CAP' versus
> 'CAPACITOR'. All 21 pass."

**2. Run `python -m app.verify` (about 30 seconds).**
> "This compares **every one of the 2,725 rows** in my app with DIBBS's own website, one by one. Result: **zero differences.**"

**3. Tell the story of what it caught.**
> "The first time I ran the full check, it caught two real problems that a small sample had missed:
> - One part number was being cut short by one character. Fixed.
> - 141 RFQs were on the website but missing from DIBBS's download file. Two of them were good matches for this vendor. Now I add them in.
>
> That's why I check everything against a second source."

---

## Part 4: Close (30 seconds)
> "So it pulls today's RFQs, ranks them for the vendor with reasons, links back to DIBBS, shows approved suppliers,
> learns from the vendor's choices, and checks every row. Next I'd add AI to help vendors set up their profile:
> they describe what they make, and it suggests keywords and product groups. Then a morning email with new matches."

---

## Numbers to remember
| What | Number |
|---|---|
| RFQs today | 2,725 |
| Matches for the demo vendor | 352 |
| Hidden by the quantity filter | 27 |
| Test cases passing | 21 of 21 |
| Rows checked against DIBBS | 2,725, zero differences |
| Real problems the full check caught | 2 (a cut-off part number, 141 missing RFQs) |

## Words you might need
| Word | Plain meaning |
|---|---|
| RFQ / solicitation | A request from the government for a price on a part |
| NSN | The part's 13-digit stock number, e.g. 5305-01-234-5678 |
| FSC | The first 4 digits of the NSN: the product group (5305 = screws) |
| CAGE code | A company's ID code |
| Approved source | A company the government already accepts for that part |

## If he asks
| Question | Simple answer |
|---|---|
| Why not just scrape the website? | "DIBBS posts a daily file. One download beats clicking 55 pages. I still use the website, to double-check the file and to fill in what the file misses." |
| Why no AI in the app itself? | "Part numbers are exact, so plain code matches them perfectly and for free. AI is useful later, for helping vendors describe what they make." |
| Will it work for many vendors? | "Yes. Download once a day for everyone, then each vendor's ranking takes milliseconds." |
| What isn't finished? | "Some DIBBS codes (like set-asides) aren't decoded yet, and keyword matching is exact words, so 'fastener' won't find 'screw' yet." |
| What did you get wrong? | "One part number was cut short in my early notes. The full check caught it. That's why I check every row." |

## Don't
- Don't run the check with `--no-cache` on the call; it takes about 3 minutes.
- Don't say the 141 added RFQs were "independently verified". They came from the website itself. The independent proof is that the other 2,584 rows match the website exactly.
