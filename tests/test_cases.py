import json
from datetime import date, datetime
from pathlib import Path

import pytest

pytest.importorskip("app.ingest")
pytest.importorskip("app.match")

from app.contracts import Profile, Snapshot, pdf_url, record_url  # noqa: E402
from app.ingest import parse_as, parse_in  # noqa: E402
from app.match import rank  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
DATA = json.loads((Path(__file__).parent / "cases.json").read_text())
IN_TEXT = (FIX / "in_sample.txt").read_text(encoding="latin-1")
LINES = IN_TEXT.splitlines()


@pytest.fixture(scope="module")
def sols():
    return parse_in(IN_TEXT, date(2026, 11, 16))


@pytest.fixture(scope="module")
def matches(sols):
    approved = {}
    for a in parse_as((FIX / "as_sample.txt").read_text(encoding="latin-1")):
        approved.setdefault(a.nsn, []).append(a)
    snap = Snapshot(posted=date(2026, 11, 16), fetched_at=datetime(2026, 11, 16, 12),
                    source_file="in261115.txt", solicitations=sols, approved=approved)
    return rank(Profile(**DATA["profile"]), snap)


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda c: f"{c['line']}-{c['label']}")
def test_label(case, sols, matches):
    s = sols[case["line"]]
    assert (s.sol, s.nsn) == (case["sol"], case["nsn"])
    found = [m for m in matches if m.sol == s]
    assert found, "row dropped from ranked output"
    m = found[0]
    if case["label"] == "relevant":
        assert m.score > 0 and m.hidden_by is None, case["reason"]
    elif case["label"] == "not_relevant":
        assert m.score == 0, case["reason"]
    else:
        assert m.hidden_by is not None, case["reason"]


def test_identifiers_are_fixture_bytes(sols):
    assert len(sols) == len(LINES)
    for s, line in zip(sols, LINES):
        assert s.sol == line[0:13]
        assert s.nsn == line[13:26]


def test_links(sols):
    for s, line in zip(sols, LINES):
        sol = line[0:13]
        assert record_url(s.sol) == f"https://www.dibbs.bsm.dla.mil/rfq/rfqrec.aspx?sn={sol}"
        assert pdf_url(s.sol) == f"https://dibbs2.bsm.dla.mil/Downloads/RFQ/{sol[-1]}/{sol}.PDF"
