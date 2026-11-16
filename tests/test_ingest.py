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
        assert r.sol == ln[0:13] and r.nsn == ln[13:62].split()[0]


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


# ---- story-mode telemetry ----
def _run_refresh(monkeypatch, tmp_path, fail=False):
    import json as _json
    import requests
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(ingest, "REFRESH_LOG", log)
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    cache = tmp_path / "261115"
    cache.mkdir()
    (cache / "in261115.txt").write_bytes((FIX / "in_sample.txt").read_bytes())
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("as261115.txt", (FIX / "as_sample.txt").read_bytes())
    (cache / "bq261115.zip").write_bytes(buf.getvalue())
    html = ('<a href="https://x/in261115.txt">a</a><a href="https://x/bq261115.zip">b</a>')

    def fake_get(s, url, events=None):
        if fail:
            raise RuntimeError("DIBBS request failed: boom")
        return type("R", (), {"text": html, "url": "https://www.dibbs.bsm.dla.mil/"})()
    monkeypatch.setattr(ingest, "_get", fake_get)
    try:
        res = ingest.refresh(tmp_path / "t.db")
    except RuntimeError:
        res = None
    return res, [_json.loads(x) for x in log.read_text().splitlines()]


def test_refresh_writes_story(monkeypatch, tmp_path):
    res, log = _run_refresh(monkeypatch, tmp_path)
    assert res.rows == 313 and len(log) == 1
    e = log[0]
    assert e["outcome"] == "ok" and e["rows"] == 313 and e["flagged"] == 8 and e["source_file"] == "in261115.txt"
    names = [s["name"] for s in e["stages"]]
    assert names == ["consent", "recent page", "download in file", "download bq zip", "parse", "validate", "store"]
    assert all("seconds" in s and "note" in s for s in e["stages"])
    assert any("Newest file on the Recent page: in261115.txt" in x for x in e["story"])
    assert any("8 flagged non-standard NSN, 0 invalid" in x for x in e["story"])


def test_refresh_failure_is_traced_and_raised(monkeypatch, tmp_path):
    res, log = _run_refresh(monkeypatch, tmp_path, fail=True)
    assert res is None and log[0]["outcome"] == "failed"
    assert "Failed at stage 'recent page'" in log[0]["story"][-1] and "boom" in log[0]["story"][-1]


def test_long_nsn_kept_whole():
    ln = next(x for x in _text().splitlines() if x.startswith("SPE7M027T1283N4215863170925"))
    r = ingest.parse_in(ln, POSTED)[0]
    assert r.nsn == "N4215863170925"
    assert "non-standard NSN" in r.flags and "NSN longer than 13 characters" in r.flags
    assert r.pr == ln[62:72]


def _live(**kw):
    d = {"sol": "SPE7M099X0001", "nsn": "5306001234567", "nomenclature": " BOLT,X ", "qty": 5,
         "pr": "7019999999", "return_by": "12-01-2026", "pdf_href": "x.pdf", "nsn_text": "5306-00-123-4567"}
    d.update(kw)
    return d


def test_merge_listing(tmp_path):
    rows = ingest.parse_in(_text(), POSTED)
    db = tmp_path / "t.db"
    ingest._store(db, POSTED, "in261115.txt", rows, [])
    ex = rows[0]
    dup = _live(sol=ex.sol, nsn=ex.nsn, pr=ex.pr)
    new = _live()
    assert ingest.merge_listing(db, [dup, new]) == 1
    assert ingest.merge_listing(db, [dup, new]) == 0
    snap = ingest.load(db)
    assert len(snap.solicitations) == len(rows) + 1
    m = snap.solicitations[-1]
    assert (m.sol, m.nsn, m.pr, m.nomenclature, m.qty) == (new["sol"], new["nsn"], new["pr"], " BOLT,X ", 5)
    assert m.fsc == "5306" and m.ui == "" and m.codes == "" and m.posted == POSTED
    assert m.return_by == date(2026, 12, 1)
    assert ingest.LISTING_FLAG in m.flags
