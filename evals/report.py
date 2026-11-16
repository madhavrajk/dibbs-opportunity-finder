"""Score tests/cases.json against the fixture snapshot. Run: python -m evals.report

Exit 1 if any labelled case is wrong or any fixture identifier differs from its source bytes.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from app.contracts import Profile, Snapshot
from app.ingest import parse_as, parse_in
from app.match import rank

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
CASES_PATH = ROOT / "tests" / "cases.json"
LOG_PATH = ROOT / "logs" / "eval_report.json"
LABELS = ("relevant", "not_relevant", "hidden_by_qty")


def predict(score: int, hidden_by: str | None) -> str:
    """The label the app implies for one row: hidden rows first, then score > 0 means relevant."""
    if hidden_by is not None:
        return "hidden_by_qty"
    return "relevant" if score > 0 else "not_relevant"


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def main() -> int:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    in_text = (FIX / "in_sample.txt").read_text(encoding="latin-1")
    as_text = (FIX / "as_sample.txt").read_text(encoding="latin-1")

    sols = parse_in(in_text, date(2026, 11, 15))
    approved: dict = {}
    for a in parse_as(as_text):
        approved.setdefault(a.nsn, []).append(a)
    snap = Snapshot(posted=date(2026, 11, 15), fetched_at=datetime.now(),
                    source_file="in_sample.txt", solicitations=sols, approved=approved)
    matches = rank(Profile(**data["profile"]), snap)

    # Identifier byte equality over every non-blank fixture line (same rule parse_in uses).
    lines = [ln for ln in in_text.splitlines() if ln.strip()]
    ident_ok = sum(1 for i, ln in enumerate(lines)
                   if i < len(sols) and sols[i].sol == ln[0:13] and sols[i].nsn == ln[13:62].split()[0])
    ident_total = len(lines)

    confusion = {t: {p: 0 for p in LABELS} for t in LABELS}
    wrong, errors = [], []
    for case in data["cases"]:
        idx = case["line"]
        if idx >= len(sols):
            errors.append(f"line {idx}: no parsed row")
            continue
        s = sols[idx]
        if (s.sol, s.nsn) != (case["sol"], case["nsn"]):
            errors.append(f"line {idx}: case key {case['sol']}/{case['nsn']} != parsed {s.sol}/{s.nsn}")
        m = next((m for m in matches if m.sol == s), None)
        if m is None:
            errors.append(f"line {idx}: row dropped from ranked output")
            continue
        pred = predict(m.score, m.hidden_by)
        confusion[case["label"]][pred] += 1
        if pred != case["label"]:
            wrong.append({"line": idx, "sol": s.sol, "nsn": s.nsn, "label": case["label"],
                          "predicted": pred, "score": m.score, "hidden_by": m.hidden_by,
                          "reasons": m.reasons, "case_reason": case.get("reason", "")})

    n_cases = sum(sum(row.values()) for row in confusion.values())
    n_correct = sum(confusion[t][t] for t in LABELS)
    rel_tp = confusion["relevant"]["relevant"]
    rel_pred = sum(confusion[t]["relevant"] for t in LABELS)
    rel_true = sum(confusion["relevant"].values())
    hid_true = sum(confusion["hidden_by_qty"].values())
    precision = _ratio(rel_tp, rel_pred)
    recall = _ratio(rel_tp, rel_true)
    hidden_acc = _ratio(confusion["hidden_by_qty"]["hidden_by_qty"], hid_true)
    overall = _ratio(n_correct, n_cases)

    print("Confusion (rows = label, cols = predicted)")
    print(f"{'label':<16}" + "".join(f"{p:>16}" for p in LABELS))
    for t in LABELS:
        print(f"{t:<16}" + "".join(f"{confusion[t][p]:>16}" for p in LABELS))
    print()
    print(f"relevant precision: {precision}   recall: {recall}")
    print(f"hidden_by_qty accuracy: {hidden_acc} ({confusion['hidden_by_qty']['hidden_by_qty']}/{hid_true})")
    print(f"overall accuracy: {overall} ({n_correct}/{n_cases})")
    print()
    if wrong:
        print("Wrong cases:")
        for w in wrong:
            print(f"  line {w['line']} {w['sol']} {w['nsn']}: label={w['label']} predicted={w['predicted']} "
                  f"score={w['score']} hidden_by={w['hidden_by']}")
            print(f"    reasons: {w['reasons']}")
            print(f"    case note: {w['case_reason']}")
    else:
        print("Wrong cases: none")
    for e in errors:
        print(f"ERROR {e}")
    print(f"identifier byte equality: {ident_ok}/{ident_total}")

    report = {
        "source_file": "in_sample.txt",
        "cases_total": n_cases,
        "confusion": confusion,
        "relevant_precision": precision,
        "relevant_recall": recall,
        "hidden_by_qty_accuracy": hidden_acc,
        "overall_accuracy": overall,
        "wrong_cases": wrong,
        "errors": errors,
        "identifier_byte_equality": f"{ident_ok}/{ident_total}",
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    failed = bool(wrong) or bool(errors) or ident_ok != ident_total
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
