from datetime import date, datetime
from pathlib import Path

from app.contracts import Snapshot, Solicitation, pdf_url
from app.verify import compare, parse_listing

FIX = Path(__file__).parent / "fixtures" / "listing_issue_page1.html"


def _snap(rows):
    sols = [Solicitation(sol=r["sol"], nsn=r["nsn"], fsc=r["nsn"][:4], pr=r["pr"],
                         return_by=datetime.strptime(r["return_by"], "%m-%d-%Y").date(),
                         qty=r["qty"], ui="EA", nomenclature=r["nomenclature"], codes="",
                         posted=date(2026, 11, 15)) for r in rows]
    return Snapshot(posted=date(2026, 11, 15), fetched_at=datetime(2026, 11, 16),
                    source_file="in261115.txt", solicitations=sols, approved={})


def test_parse_fixture():
    rows = parse_listing(FIX.read_text())
    assert len(rows) == 50
    assert rows[0]["sol"] == "SPE1C127T0119" and rows[0]["nsn"] == "8465012768198"
    assert rows[0]["qty"] == 12 and rows[0]["pr"] == "7019120187"
    assert rows[0]["pdf_href"].lower() == pdf_url("SPE1C127T0119").lower()


def test_compare():
    rows = parse_listing(FIX.read_text())
    snap = _snap(rows)
    assert compare(snap, rows, 50)["total_mismatches"] == 0
    bad = [dict(r) for r in rows]
    bad[0]["nsn"] = "8465012768199"
    r = compare(snap, bad, 50)
    assert r["mismatches"]["nsn"] == 1 and r["total_mismatches"] == 1   # paired by sol, now a field mismatch
    bad = [dict(r) for r in rows]
    bad[1]["qty"] += 1
    r = compare(snap, bad, 50)
    assert r["mismatches"]["qty"] == 1 and r["total_mismatches"] == 1
    # one-digit NSN change on the stored side is also caught as a missing key
    snap2 = _snap(rows)
    snap2.solicitations[2].nsn = snap2.solicitations[2].nsn[:-1] + "0" if snap2.solicitations[2].nsn[-1] != "0" else "1"
    assert compare(snap2, rows, 50)["mismatches"]["nsn"] == 1


def _row(sol, nsn, pr, qty=1, rb="12-01-2026"):
    return {"sol": sol, "nsn": nsn, "pr": pr, "qty": qty, "return_by": rb, "nomenclature": "X",
            "pdf_href": pdf_url(sol)}


def test_paginate_stops_at_records_found():
    from app.verify import paginate
    pages = {1: [_row("SPE1A", "1" * 13, "P1"), _row("SPE1B", "1" * 13, "P2")],
             2: [_row("SPE2A", "1" * 13, "P3"), _row("SPE2B", "1" * 13, "P4")],
             3: [_row("SPE3A", "1" * 13, "P5")]}
    calls = []
    import app.verify as v
    orig_p, orig_r = v.parse_listing, v.records_found
    v.parse_listing = lambda h: pages[h]
    v.records_found = lambda h: 5
    try:
        rows, total = paginate(lambda n, prev: calls.append(n) or n, log=lambda *_: None)
    finally:
        v.parse_listing, v.records_found = orig_p, orig_r
    assert calls == [1, 2, 3] and len(rows) == 5 and total == 5


def test_paginate_stops_on_no_new_rows():
    import app.verify as v
    orig_p, orig_r = v.parse_listing, v.records_found
    v.parse_listing = lambda h: [_row("SPE1A", "1" * 13, "P1")]
    v.records_found = lambda h: 99
    try:
        rows, _ = v.paginate(lambda n, prev: n, log=lambda *_: None)
    finally:
        v.parse_listing, v.records_found = orig_p, orig_r
    assert len(rows) == 1


def test_compare_two_directional():
    a = _row("SPE1A", "1111111111111", "P1")
    b1 = _row("SPE1B", "2222222222222", "P2")
    b2 = _row("SPE1B", "2222222222222", "P3", qty=5)   # multi-line PR
    c = _row("SPE1C", "3333333333333", "P4")
    snap = _snap([a, b1, b2, c])
    live = [a, b1, b2, dict(c, nsn="3333333333334"), _row("SPE9Z", "4444444444444", "P9"),
            _row("SPE1B", "2222222222222", "P7")]
    r = compare(snap, live)
    # the one-digit NSN change is paired with its stored line and counted as an nsn mismatch
    assert r["mismatches"]["nsn"] == 1 and r["total_mismatches"] == 1
    # new sol and new line for a known sol are missing from the snapshot
    assert r["missing_from_snapshot"] == 2
    assert r["missing_from_snapshot_sol_known"] == 1 and r["missing_from_snapshot_by_prefix"]["SPE9Z"] == 1
    assert r["missing_from_live"] == 0
    # snapshot row absent from live
    r = compare(snap, [a, b1, c])
    assert r["missing_from_live"] == 1 and r["missing_from_live_examples"][0]["pr"] == "P3"
    assert r["total_mismatches"] == 0
    # multi-line keyed by PR: qty differs only on the right line
    r = compare(snap, [a, b1, dict(b2, qty=6), c])
    assert r["mismatches"]["qty"] == 1 and r["total_mismatches"] == 1


def test_parse_nsn_ignores_milspec_tag():
    html = ('<span id="x_grdRfqSearch_ctl02_lblNsn"><a href="#">5310-01-702-2315</a><br/>'
            '<span style="color:red">Mil-Spec</span></span>')
    r = parse_listing(html)
    assert r[0]["nsn"] == "5310017022315" and r[0]["nsn_text"] == "5310-01-702-2315"
