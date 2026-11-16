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
    assert r["missing"] == 1
    bad = [dict(r) for r in rows]
    bad[1]["qty"] += 1
    r = compare(snap, bad, 50)
    assert r["mismatches"]["qty"] == 1 and r["total_mismatches"] == 1
    # one-digit NSN change on the stored side is also caught as a missing key
    snap2 = _snap(rows)
    snap2.solicitations[2].nsn = snap2.solicitations[2].nsn[:-1] + "0" if snap2.solicitations[2].nsn[-1] != "0" else "1"
    assert compare(snap2, rows, 50)["missing"] == 1
