from datetime import date
from pathlib import Path

from app import ingest

FIX = Path(__file__).parent / "fixtures"
POSTED = date(2026, 11, 15)


def _text():
    return (FIX / "in_sample.txt").read_bytes().decode("latin-1")


def test_parse_in_counts_and_first_row():
    rows = ingest.parse_in(_text(), POSTED)
    assert len(rows) == 313
    r = rows[0]
    assert r.sol == "SPE1C127T0119" and r.nsn == "8465012768198" and r.fsc == "8465"
    assert r.qty == 12 and r.ui == "EA" and r.return_by == date(2026, 11, 27)
    assert r.nomenclature == "SNAP LINK,RAPPELLER" and r.posted == POSTED


def test_flags():
    rows = ingest.parse_in(_text(), POSTED)
    assert sum("non-standard NSN" in r.flags for r in rows) == 8
    assert sum("invalid solicitation number" in r.flags for r in rows) == 0


def test_identifiers_byte_equal_to_source():
    lines = [ln for ln in _text().splitlines() if ln.strip()]
    rows = ingest.parse_in(_text(), POSTED)
    assert len(lines) == len(rows)
    for ln, r in zip(lines, rows):
        assert r.sol == ln[0:13] and r.nsn == ln[13:26]


def test_parse_as_count():
    text = (FIX / "as_sample.txt").read_bytes().decode("latin-1")
    out = ingest.parse_as(text)
    assert len(out) == len(text.splitlines())
    assert out[0].nsn == "1680014826438" and out[0].cage == "97499" and out[0].part_no == "901-025-930-107"


def test_store_load_round_trip(tmp_path):
    rows = ingest.parse_in(_text(), POSTED)
    appr = ingest.parse_as((FIX / "as_sample.txt").read_bytes().decode("latin-1"))
    db = tmp_path / "t.db"
    assert ingest.load(db) is None
    ingest._store(db, POSTED, "in261115.txt", rows, appr)
    snap = ingest.load(db)
    assert snap.solicitations == rows
    assert snap.source_file == "in261115.txt" and snap.posted == POSTED
    assert sum(len(v) for v in snap.approved.values()) == len(appr)


def test_consent_detection_and_form():
    html = ('<html><form action="dodwarning.aspx?goto=x"><input type="hidden" name="__VIEWSTATE" value="abc"/>'
            '<input type="submit" name="butAgree" value="OK"/></form></html>')
    assert ingest.needs_consent(html)
    assert not ingest.needs_consent("<html>hello</html>")
    action, data = ingest._hidden_inputs(html)
    assert action == "dodwarning.aspx?goto=x" and data == {"__VIEWSTATE": "abc"}


def test_find_latest():
    html = ('<a href="https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/in261114.txt">a</a>'
            '<a href="https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/in261115.txt">a</a>'
            '<a href="https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/bq261115.zip">b</a>')
    d, i, b = ingest._find_latest(html, "https://www.dibbs.bsm.dla.mil/")
    assert d == "261115" and i.endswith("in261115.txt") and b.endswith("bq261115.zip")


def test_find_latest_single_quotes():
    html = ("<a href='https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/in261115.txt' title='d'>a</a>"
            "<a href='https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/bq261115.zip' title='d'>b</a>")
    assert ingest._find_latest(html, "https://x/")[0] == "261115"
