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

        nsn_txt = sp.get_text(strip=True)
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


def compare(snapshot: Snapshot, live_rows: list[dict], sample: int) -> dict:
    index: dict[tuple, list] = {}
    for s in snapshot.solicitations:   # a sol+nsn can appear on several lines (different PRs)
        index.setdefault((s.sol, s.nsn), []).append(s)
    checked = matched = 0
    missing: list[dict] = []
    mism = {f: 0 for f in FIELDS}
    examples: list[str] = []
    for row in live_rows[:sample]:
        checked += 1
        cands = index.get((row["sol"], row["nsn"]))
        if not cands:
            missing.append(row)
            continue
        matched += 1
        live = {"sol": row["sol"], "nsn": row["nsn"], "qty": row["qty"], "pr": row["pr"],
                "return_by": row["return_by"], "pdf": row["pdf_href"].lower()}
        best = None
        for s in cands:
            stored = {"sol": s.sol, "nsn": s.nsn, "qty": s.qty, "pr": s.pr,
                      "return_by": _rb(s.return_by), "pdf": pdf_url(s.sol).lower()}
            bad = [f for f in FIELDS if stored[f] != live[f]]
            if best is None or len(bad) < len(best[0]):
                best = (bad, stored)
        for f in best[0]:
            mism[f] += 1
            examples.append(f"{row['sol']} {f}: {best[1][f]!r} → {live[f]!r}")
    return {"checked": checked, "matched": matched, "missing": len(missing),
            "missing_rows": missing, "mismatches": mism,
            "total_mismatches": sum(mism.values()), "examples": examples[:3]}


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=50)
    args = ap.parse_args(argv)
    from app.ingest import load
    snap = load()
    if snap is None:
        print("No snapshot found; run the refresh first.")
        return 2
    s = _session()
    issue = find_issue_date(_get(s, f"{BASE}/Rfq/RfqDates.aspx?category=issue"), snap.posted)
    html = _get(s, f"{BASE}/RFQ/RfqRecs.aspx?category=issue&TypeSrch=dt&Value={issue}")
    rows = parse_listing(html)
    res = compare(snap, rows, args.sample)
    print(f"snapshot {snap.source_file} (posted {snap.posted}); live issue date {issue}")
    print(f"rows checked: {res['checked']}")
    print(f"matched in snapshot: {res['matched']}")
    print(f"missing from snapshot: {res['missing']}")
    print("mismatches per field: " + ", ".join(f"{k}={v}" for k, v in res["mismatches"].items()))
    for e in res["examples"]:
        print("  " + e)
    return 1 if res["total_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
