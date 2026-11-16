import sys
import types
from pathlib import Path
from datetime import date, datetime

import pytest
from streamlit.testing.v1 import AppTest

from app import contracts
from app.contracts import ApprovedSource, Match, Snapshot, Solicitation

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")


def sol(s, nsn, qty=5, days=2, nom="HEX SCREW", flags=None):
    return Solicitation(sol=s, nsn=nsn, fsc=nsn[:4], pr="PR1", return_by=date(2026, 11, 16 + days),
                        qty=qty, ui="EA", nomenclature=nom, codes="X", posted=date(2026, 11, 16),
                        flags=flags or [])


SOLS = [sol("SPE1C127T0119", "5305012768198"), sol("SPE4A527Q0073", "8465012768198", qty=1, nom="BAG"),
        sol("BADSOL", "123", flags=["invalid solicitation number"])]
SNAP = Snapshot(posted=date(2026, 11, 16), fetched_at=datetime(2026, 11, 16, 9, 30), source_file="in261116.txt",
                solicitations=SOLS,
                approved={"5305012768198": [ApprovedSource(nsn="5305012768198", cage="1ABC2", part_no="P-1")]})


def fake_rank(profile, snapshot):
    return [Match(sol=SOLS[0], score=3, reasons=["keyword: screw", "FSC 5305"]),
            Match(sol=SOLS[1], score=1, reasons=["x"], hidden_by="qty 1 < your minimum 2"),
            Match(sol=SOLS[2], score=0)]


def fake_summary(ms):
    return {"total": len(ms), "matched": 1, "hidden": 1, "due_soon": 2}


@pytest.fixture
def app(monkeypatch, tmp_path):
    import streamlit as st
    st.cache_data.clear()
    monkeypatch.setattr(contracts, "PROFILE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(contracts, "DB_PATH", tmp_path / "x.db")
    ingest = types.ModuleType("app.ingest")
    match = types.ModuleType("app.match")
    ingest.load = lambda db_path=None: ingest.snapshot
    ingest.snapshot = None
    ingest.refresh = lambda db_path=None: (_ for _ in ()).throw(RuntimeError("DIBBS unreachable"))
    match.rank, match.summary = fake_rank, fake_summary
    import app as pkg
    for name, mod in (("ingest", ingest), ("match", match)):
        monkeypatch.setitem(sys.modules, f"app.{name}", mod)
        monkeypatch.setattr(pkg, name, mod, raising=False)
    return ingest


def test_empty_state(app):
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert any("Refresh" in i.value for i in at.info)


def test_refresh_error_shown(app):
    at = AppTest.from_file(UI, default_timeout=30).run()
    [b for b in at.button if b.label == "Refresh"][0].click().run()
    assert "DIBBS unreachable" in at.error[0].value


def test_with_snapshot(app):
    app.snapshot = SNAP
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert [m.value for m in at.metric] == ["3", "1", "1", "2"]
    assert len(at.tabs) == 2 and len(at.dataframe) >= 2
    assert any("posted 2026-11-16" in m.value for m in at.markdown)
    at.toggle[0].set_value(True).run()
    assert not at.exception


def test_pure_helpers():
    from app import ui
    assert ui.parse_nsn_text("5305-01-276-8198, 8465 01 276 8198\n") == ["5305012768198", "8465012768198"]
    assert ui.parse_nsn_upload(b"nsn,desc\n5305-01-276-8198,x\n") == ["5305012768198"]
    assert ui.split_terms("screw, bolt\nnut") == ["screw", "bolt", "nut"]
    ms = fake_rank(None, SNAP)
    assert [m.sol.sol for m in ui.filter_all(ms, "5305-01-276-8198", [], None)] == ["SPE1C127T0119"]
    assert [m.sol.sol for m in ui.filter_all(ms, "bag", [], None)] == ["SPE4A527Q0073"]
    assert len(ui.for_you(ms, False)) == 1 and len(ui.for_you(ms, True)) == 2
    df = ui.build_rows(ms, SNAP, date(2026, 11, 16))
    assert df.loc[0, "Approved sources"] == 1 and df.loc[0, "NSN"] == "5305-01-276-8198"
    assert df.loc[2, "NSN"] == "123"
