"""Zero-tolerance live cross-check: python -m app.verify --sample 50
Compares stored rows to the DIBBS issue-date HTML listing. Read-only; never touches the DB."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime

from bs4 import BeautifulSoup

from app.contracts import Snapshot, pdf_url

BASE = "https://www.dibbs.bsm.dla.mil"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
FIELDS = ["sol", "nsn", "qty", "pr", "return_by", "pdf"]
DATE_RE = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")


def parse_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for sp in soup.find_all("span", id=re.compile(r"grdRfqSearch_ctl\d+_lblNsn$")):
        prefix = sp["id"][: -len("lblNsn")]

        def span(name):
            return soup.find("span", id=prefix + name)

        a_nsn = sp.find("a")   # a red "Mil-Spec" tag may follow the link inside the span; the NSN is the link text
        nsn_txt = (a_nsn or sp).get_text(strip=True)
        sol_el = span("lblSolicitation")
        sol = pdf = ""
        if sol_el:
            m = re.search(r"rfqrec\.aspx\?sn=([A-Za-z0-9]+)", str(sol_el), re.I)
            sol = m.group(1) if m else ""
            a = sol_el.find("a", href=re.compile(r"\.pdf", re.I))
            pdf = a["href"] if a else ""
        pr_el = span("lblPr")
        pr_txt = pr_el.get_text(" ", strip=True) if pr_el else ""
        m = re.match(r"(\S+)\s+QTY:\s*(\d+)", pr_txt)
        nom = span("lblNomenclature")
        rb = span("lblReturnBy")
        rows.append({
            "nsn_text": nsn_txt,
            "nomenclature": nom.get_text(strip=True) if nom else "",
            "sol": sol,
            "pdf_href": pdf,
            "pr": m.group(1) if m else pr_txt,
            "qty": int(m.group(2)) if m else None,
            "return_by": rb.get_text(strip=True) if rb else "",
        })
        rows[-1]["nsn"] = nsn_txt.replace("-", "")
    return rows


def _rb(d) -> str:
    return d.strftime("%m-%d-%Y") if d else ""


def _stored_view(s) -> dict:
    return {"sol": s.sol, "nsn": s.nsn, "qty": s.qty, "pr": s.pr,
            "return_by": _rb(s.return_by), "pdf": pdf_url(s.sol).lower()}


def _live_view(row: dict) -> dict:
    return {"sol": row["sol"], "nsn": row["nsn"], "qty": row["qty"], "pr": row["pr"],
            "return_by": row["return_by"], "pdf": row["pdf_href"].lower()}


def _bad(a: dict, b: dict) -> list[str]:
    return [f for f in FIELDS if a[f] != b[f]]


def compare(snapshot: Snapshot, live_rows: list[dict], sample: int | None = None) -> dict:
    """Two-directional, keyed by (sol, nsn, pr). A live row is clean only if a stored line is identical on every
    field. An unkeyed leftover is paired with a leftover stored line of the same solicitation only when the counts
    of leftovers for that sol are equal (then its differing fields are mismatches); otherwise it is missing."""
    if sample is not None:
        live_rows = live_rows[:sample]
    stored_by_key: dict[tuple, list[dict]] = {}
    stored_by_sol: dict[str, list[dict]] = {}
    for s in snapshot.solicitations:
        v = _stored_view(s)
        stored_by_key.setdefault((v["sol"], v["nsn"], v["pr"]), []).append(v)
        stored_by_sol.setdefault(v["sol"], []).append(v)
    mism = {f: 0 for f in FIELDS}
    examples: list[dict] = []
    used: set[int] = set()
    unmatched: list[dict] = []
    matched = 0
    for row in live_rows:
        live = _live_view(row)
        cands = [c for c in stored_by_key.get((live["sol"], live["nsn"], live["pr"]), []) if id(c) not in used]
        if not cands:
            unmatched.append(live)
            continue
        best = min(cands, key=lambda c: len(_bad(c, live)))
        used.add(id(best))
        matched += 1
        for f in _bad(best, live):
            mism[f] += 1
            examples.append({"sol": live["sol"], "field": f, "stored": best[f], "live": live[f]})
    left_stored: dict[str, list[dict]] = {}
    for sol, vs in stored_by_sol.items():
        r = [v for v in vs if id(v) not in used]
        if r:
            left_stored[sol] = r
    left_live: dict[str, list[dict]] = {}
    for live in unmatched:
        left_live.setdefault(live["sol"], []).append(live)
    missing_live: list[dict] = []
    paired_sols = 0
    for sol, lives in left_live.items():
        sts = left_stored.get(sol, [])
        if sts and len(sts) == len(lives):
            paired_sols += 1
            for live in lives:
                best = min(sts, key=lambda c: len(_bad(c, live)))
                sts.remove(best)
                used.add(id(best))
                matched += 1
                for f in _bad(best, live):
                    mism[f] += 1
                    examples.append({"sol": sol, "field": f, "stored": best[f], "live": live[f]})
        else:
            for live in lives:
                missing_live.append({**live, "sol_in_snapshot": sol in stored_by_sol})
    by_prefix: dict[str, int] = {}
    for m in missing_live:
        by_prefix[m["sol"][:6]] = by_prefix.get(m["sol"][:6], 0) + 1
    in_snap = sum(1 for m in missing_live if m["sol_in_snapshot"])
    live_keys = {(r["sol"], r["nsn"], r["pr"]) for r in live_rows}
    missing_snap = []
    if sample is None:
        for vs in stored_by_sol.values():
            for v in vs:
                if id(v) not in used:
                    missing_snap.append(v)
    return {"checked": len(live_rows), "matched": matched, "mismatches": mism,
            "total_mismatches": sum(mism.values()), "mismatch_examples": examples[:20],
            "missing_from_snapshot": len(missing_live),
            "missing_from_snapshot_by_prefix": dict(sorted(by_prefix.items(), key=lambda kv: -kv[1])),
            "missing_from_snapshot_sol_known": in_snap,
            "missing_from_snapshot_sol_unknown": len(missing_live) - in_snap,
            "missing_from_snapshot_examples": missing_live[:20],
            "missing_from_live": len(missing_snap) if sample is None else None,
            "missing_from_live_examples": missing_snap[:20],
            "live_keys": len(live_keys),
            # legacy aliases
            "missing": len(missing_live), "missing_rows": missing_live,
            "examples": [f"{e['sol']} {e['field']}: {e['stored']!r} -> {e['live']!r}" for e in examples[:3]]}


def _session():
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*",
                      "Accept-Language": "en-US,en;q=0.9"})
    return s


def _get(s, url: str) -> str:
    from urllib.parse import urljoin
    r = s.get(url, timeout=30)
    if "dodwarning" in r.url.lower() or 'name="butAgree"' in r.text[:20000]:
        form = BeautifulSoup(r.text, "lxml").find("form")
        data = {i["name"]: i.get("value", "") for i in form.find_all("input")
                if i.get("name") and i.get("type") == "hidden"}
        data["butAgree"] = "OK"
        s.post(urljoin(r.url, form.get("action", "")), data=data, headers={"Referer": r.url}, timeout=30)
        r = s.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def find_issue_date(html: str, posted: date) -> str:
    dates = sorted({datetime.strptime("-".join(m), "%m-%d-%Y").date()
                    for m in DATE_RE.findall(html)})
    if not dates:
        raise RuntimeError("no dates found on RfqDates page")
    after = [d for d in dates if d > posted]
    return (min(after) if after else max(dates)).strftime("%m-%d-%Y")


def records_found(html: str) -> int | None:
    m = re.search(r"Records Found:\s*(?:<[^>]*>\s*)*([\d,]+)", html)
    return int(m.group(1).replace(",", "")) if m else None


def next_page_form(html: str, page_url: str, n: int) -> tuple[str, dict]:
    from urllib.parse import urljoin
    form = BeautifulSoup(html, "lxml").find("form")
    data = {i["name"]: i.get("value", "") for i in form.find_all("input")
            if i.get("name") and i.get("type") == "hidden"}
    data["__EVENTTARGET"] = "ctl00$cph1$grdRfqSearch"
    data["__EVENTARGUMENT"] = f"Page${n}"
    return urljoin(page_url, form.get("action", "")), data


def paginate(fetch_page, total_hint=None, log=print) -> tuple[list[dict], int | None]:
    """fetch_page(n, prev_html) -> (html). Stops at Records Found or a page with 0 new solicitations."""
    rows: list[dict] = []
    seen: set[tuple] = set()
    html, total, n = None, None, 1
    while True:
        html = fetch_page(n, html)
        if total is None:
            total = records_found(html)
        new = 0
        for r in parse_listing(html):
            k = (r["sol"], r["nsn"], r["pr"], r["return_by"], r["qty"])
            if k not in seen:
                seen.add(k)
                rows.append(r)
                new += 1
        if n % 10 == 0:
            log(f"  page {n}: {len(rows)}/{total} rows")
        if new == 0 or (total is not None and len(rows) >= total):
            return rows, total
        n += 1


def fetch_all_listing(session, issue_date: str, cache_dir=None, use_cache: bool = True,
                      pause: float = 0.3, log=print) -> tuple[list[dict], int | None]:
    import time
    from pathlib import Path
    url = f"{BASE}/RFQ/RfqRecs.aspx?category=issue&TypeSrch=dt&Value={issue_date}"
    cache = Path(cache_dir) if cache_dir else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    state = {"url": url}

    def fetch(n, prev):
        f = cache / f"page_{n:03d}.html" if cache else None
        if f and use_cache and f.exists():
            return f.read_text(encoding="utf-8")
        for attempt in range(3):
            try:
                if n == 1:
                    html = _get(session, url)
                else:
                    time.sleep(pause)
                    post_url, data = next_page_form(prev, state["url"], n)
                    r = session.post(post_url, data=data, headers={"Referer": state["url"]}, timeout=60)
                    r.raise_for_status()
                    html = r.text
                    if "grdRfqSearch" not in html:
                        raise RuntimeError("page body has no results grid")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        if f:
            f.write_text(html, encoding="utf-8")
        return html

    return paginate(fetch, log=log)


def main(argv=None) -> int:
    import json
    import time
    from pathlib import Path
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None, help="check only the first N rows of page 1")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)
    from app.ingest import load
    snap = load()
    if snap is None:
        print("No snapshot found; run the refresh first.")
        return 2
    t = {}
    story = []
    t0 = time.time()
    s = _session()
    issue = find_issue_date(_get(s, f"{BASE}/Rfq/RfqDates.aspx?category=issue"), snap.posted)
    t["consent"] = time.time() - t0
    story.append(f"Accepted the consent banner and found issue date {issue} ({t['consent']:.1f}s).")
    t0 = time.time()
    if args.sample:
        html = _get(s, f"{BASE}/RFQ/RfqRecs.aspx?category=issue&TypeSrch=dt&Value={issue}")
        rows, total, pages = parse_listing(html), records_found(html), 1
    else:
        cdir = Path("data") / snap.posted.strftime("%y%m%d") / "listing"
        rows, total = fetch_all_listing(s, issue, cdir, use_cache=not args.no_cache)
        pages = len(list(cdir.glob("page_*.html")))
    t["pages"] = time.time() - t0
    story.append(f"Fetched {pages} listing page(s) ({t['pages']:.1f}s).")
    story.append(f"Parsed {len(rows)} rows; DIBBS says Records Found: {total}.")
    t0 = time.time()
    res = compare(snap, rows, args.sample)
    t["compare"] = time.time() - t0
    story.append(f"Compared {res['checked']} live rows with {len(snap.solicitations)} stored lines "
                 f"by (sol, nsn, pr) ({t['compare']:.2f}s).")
    story.append(f"Result: {res['total_mismatches']} field mismatches; {res['missing_from_snapshot']} live rows "
                 f"not in snapshot; {res['missing_from_live']} snapshot rows not live.")
    print(f"snapshot {snap.source_file} (posted {snap.posted}); live issue date {issue}")
    for line in story:
        print("- " + line)
    print(f"matched: {res['matched']}")
    print("mismatches per field: " + ", ".join(f"{k}={v}" for k, v in res["mismatches"].items()))
    for e in res["mismatch_examples"][:5]:
        print(f"  {e['sol']} {e['field']}: stored {e['stored']!r} live {e['live']!r}")
    print(f"IN HTML, NOT IN FILE: {res['missing_from_snapshot']} "
          f"(sol known with other line: {res['missing_from_snapshot_sol_known']}, "
          f"sol unknown: {res['missing_from_snapshot_sol_unknown']})")
    print("  by prefix: " + ", ".join(f"{k}={v}" for k, v in list(res["missing_from_snapshot_by_prefix"].items())[:10]))
    if res["missing_from_live"] is not None:
        print(f"IN FILE, NOT IN HTML: {res['missing_from_live']}")
        for v in res["missing_from_live_examples"][:5]:
            print(f"  {v['sol']} {v['nsn']} {v['pr']}")
    report = {k: v for k, v in res.items() if k not in ("missing_rows", "examples")}
    report.update({"timestamp": datetime.now().isoformat(timespec="seconds"), "issue_date": issue,
                   "records_found": total, "rows_parsed": len(rows), "pages": pages,
                   "snapshot": snap.source_file, "stage_seconds": t, "story": story})
    Path("data").mkdir(exist_ok=True)
    Path("data/verify_report.json").write_text(json.dumps(report, indent=2))
    return 1 if res["total_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
