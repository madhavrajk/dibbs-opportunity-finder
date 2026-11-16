import json
from pathlib import Path

import pytest

from app import feedback
from scripts import feedback_to_cases as f2c

CASES = Path(__file__).parent / "cases.json"


@pytest.fixture(autouse=True)
def fb(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback, "PATH", tmp_path / "fb.jsonl")


def test_latest_wins_and_ids_untouched():
    feedback.record("SPE1C127T0119", "5305012768198", "PR1", "quote", "", {}, 3, ["kw"])
    feedback.record("SPE1C127T0119", "5305012768198", "PR1", "not_for_us", "too big", {}, 3, ["kw"])
    feedback.record("SPE1C127T0119", "5305012768198", "PR2", "quote", "", {}, 3, [])
    lat = feedback.latest()
    k = ("SPE1C127T0119", "5305012768198", "PR1")
    assert lat[k]["decision"] == "not_for_us" and lat[k]["note"] == "too big" and lat[k]["ts"]
    assert lat[("SPE1C127T0119", "5305012768198", "PR2")]["decision"] == "quote"
    assert len(feedback.path().read_text().splitlines()) == 3
    with pytest.raises(ValueError):
        feedback.record("A", "B", "C", "maybe")


def test_disagreement_detection():
    assert feedback.is_disagreement({"decision": "not_for_us", "match_score": 2})
    assert feedback.is_disagreement({"decision": "quote", "match_score": 0})
    assert not feedback.is_disagreement({"decision": "quote", "match_score": 2})
    assert not feedback.is_disagreement({"decision": "not_for_us", "match_score": 0})


def test_candidate_file_shape_and_cases_untouched(tmp_path, capsys):
    before = CASES.read_bytes()
    feedback.record("SPE1C127T0119", "5305012768198", "PR1", "not_for_us", "wrong size", {"cage": "X"}, 3, [])
    feedback.record("SPE4A527Q0073", "8465012768198", "PR1", "quote", "we make bags", {}, 0, [])
    feedback.record("SPE9ZZ27T0001", "1111111111111", "PR1", "quote", "agree", {}, 4, [])
    out = tmp_path / "cand.json"
    assert f2c.main(out) == 2
    d = json.loads(out.read_text())
    by = {c["sol"]: c for c in d["cases"]}
    assert by["SPE1C127T0119"]["label"] == "not_relevant" and by["SPE4A527Q0073"]["label"] == "relevant"
    assert by["SPE4A527Q0073"]["reason"] == "from vendor feedback: we make bags"
    assert all(c["status"] == "candidate" and c["nsn"] for c in d["cases"])
    assert "Promote by moving entries into tests/cases.json after review." in capsys.readouterr().out
    assert CASES.read_bytes() == before
