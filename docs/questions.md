###Customer

Customers are people who make the things and distributors/suppliers are going to be using this. 

THERE ARE NO WRONG ANSWERS JUST NEED TO BE ABLE TO EXPLAIN THINKING AND WHY CHOICES WERE MADE. 

A. Does Streamlit count as a full-stack web app, or does he expect a separate frontend and API? This decides whether you can start from the starter's UI or from the RFI React/MUI shell.
- Yes Streamlit counts as a full-stack web app.

B. Can you bring your own scaffold or template? Disclose it up front: "I keep a starter with gates, an eval harness and a UI shell." That's better than having it discovered.
- yes you can bring your own scaffold/template and you can use anything that you want. 

C. Is there an API key on site, or can you use your own? This only matters if an LLM feature is in scope.
- no API key just use any LLMs and resources as needed.

D. In the walkthrough, does he want to see your process (rationale, gates, commits, agents) or mostly the product? At Arata the process was the differentiator. Here the rubric leans toward product sense.
- he does want to see my process so I will show him this document as well as what questions I wrote down before the solution. 



1. What does "matters to me" mean for a vendor today? This is what they're grading ("how users find opportunities"). Do vendors match on a list of NSNs they've quoted or made before, FSC classes, part-name keywords, their CAGE code or part numbers on the approved-source list, set-asides, quantity, or due date? Does a manufacturer filter differently from a distributor?
- manufacturers and distributors typically know one of three things: a keyword from the description (screw, cap, etc.) in the description. either it is a list of NSNs they can produce for them for FSEs which is a general group of products they expect. Essentially, what are the products they can bid on. Some might not want to bid on quantity of 1 or larger quantities. 


2. What decision does this feed, and which failure is worse? I assume it's a morning "quote or skip" triage. Is missing a relevant RFQ worse than showing noise? The answer decides whether you rank everything (recall) or filter hard (precision).
- its better to overmap than undermap and show them more than less.

3. Data source and access. Is scraping the DIBBS RFQ search pages fine, or would he prefer the daily RFQ download files? Has anyone hit the consent banner, rate limits or bot blocking from this network? If DIBBS is down, can you fall back to a cached snapshot?
- you can scrape them. the consent banner is always there and DIBBS should not be down. 

4. Is an LLM in the product welcome, and is there an API key or budget on site? For example, natural-language search ("hydraulic fittings we can machine") or semantic matching on part names. Or does he want to see deterministic filters and ranking?
- you can use an LLM. 

5. Which "original page" should each row link to? The RFQ record page or the solicitation PDF? Is it OK if the link lands on the DIBBS consent banner first?
- RFQ and soliticitation are the same thing. you can either link it to the DIBBS page or PDF. 

Should-ask (scope and cut line)
6. How much data counts as "daily"? Only today's postings, or every open RFQ / the last N days? Is an on-demand "Refresh" button enough, or does he expect a scheduled job?
- you can just consider the ones released today and on demand refresh button. if you scrape it once for the day you are fine. 

7. Which extra fields matter most? Candidates: part name, quantity, return-by date, FSC, set-aside, purchase request number, approved sources. Is parsing the solicitation PDF in scope?
- NSN, Description, etc. if you click on the solicitation number then you can get interesting info about approved source like "LIBERTY MOUNTAIN SPORTS LLC". 

8. Single user or multi-tenant? Are logins or saved profiles per vendor expected? This is your "who may see what" item.
- multi-tenant but no need for auth system. the actual web page will be single tenant but will be used used by many. 

9. What is the zero-tolerance line? Proposal: every row's solicitation number, NSN, close date and DIBBS link must be correct, and expired RFQs are never shown as open. Ask him to confirm or add to it.
- if you change even one number in NSN or solicitation, then it will mess up what will produce, so it is zero-tolerance on scraping. 

10. The reviewers are basically an engineer at SalesPatriot and will be going through the implementation, what choices I made, and how to solve it. 