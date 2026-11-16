"""Turn vendor disagreements (feedback.jsonl) into CANDIDATE eval cases. Never edits tests/cases.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import feedback  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "candidate_cases.json"


def candidates(latest: dict) -> list[dict]:
    out = []
    for rec in latest.values():
        if not feedback.is_disagreement(rec):
            continue
        out.append({"sol": rec["sol"], "nsn": rec["nsn"], "pr": rec["pr"],
                    "label": "relevant" if rec["decision"] == "quote" else "not_relevant",
                    "reason": f"from vendor feedback: {rec.get('note') or 'no note'}",
                    "status": "candidate"})
    return out


def main(out: Path = OUT) -> int:
    cands = candidates(feedback.latest())
    profile = next((r["profile"] for r in feedback.latest().values() if r.get("profile")), {})
    out.write_text(json.dumps({"profile": profile, "cases": cands}, indent=1) + "\n")
    print(f"{len(cands)} candidate case(s) written to {out}")
    print("Promote by moving entries into tests/cases.json after review.")
    return len(cands)


if __name__ == "__main__":
    main()
