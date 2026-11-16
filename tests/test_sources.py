from pathlib import Path

from app.contracts import ApprovedSource
from app.sources import parse_sources, reconcile

FIX = Path(__file__).parent / "fixtures" / "SPE4A727T4218.txt"


def test_parse_fixture():
    src = parse_sources(FIX.read_text())
    got = {(s.name, s.cage, s.part_no) for s in src}
    assert len(src) == 9  # counted by hand: lines 565-573 only; line 560 "P/N ..." alone is not a source
    assert ("NORDAM GROUP LLC, THE", "29957", "4J52001-132B") in got
    assert ("G. S. E. DYNAMICS, INC.", "29183", "4J52001-132B") in got
    assert all(s.nsn == "" for s in src)


def test_dedupe_and_bare_pn():
    t = "P/N ABC123\nFOO INC 12345 P/N ABC123\nFOO INC 12345 P/N ABC123\n"
    assert len(parse_sources(t)) == 1


def test_reconcile_flags_mismatch():
    pdf = [ApprovedSource(nsn="1", cage="AAAAA", part_no="p", name="A"), ApprovedSource(nsn="1", cage="BBBBB", part_no="p")]
    asf = [ApprovedSource(nsn="1", cage="AAAAA", part_no="p"), ApprovedSource(nsn="1", cage="CCCCC", part_no="p")]
    flags = reconcile(pdf, asf)
    assert len(flags) == 2 and any("BBBBB" in f for f in flags) and any("CCCCC" in f for f in flags)
    assert reconcile(pdf[:1], asf[:1]) == []
