"""Human-in-the-loop log: one JSON line per vendor decision on a row, latest wins. Identifiers are stored exactly
as given (never edited). Disagreements with the ranking are the useful signal."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app import contracts

DECISIONS = ("quote", "not_for_us")
PATH: Path | None = None   # tests override; default is data/feedback.jsonl


def path() -> Path:
    return PATH or Path(contracts.DATA_DIR) / "feedback.jsonl"


def record(sol: str, nsn: str, pr: str, decision: str, note: str = "", profile_snapshot: dict | None = None,
           match_score: int = 0, reasons: list[str] | None = None) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"), "sol": sol, "nsn": nsn, "pr": pr,
           "decision": decision, "note": note.strip(), "profile": profile_snapshot or {},
           "match_score": match_score, "reasons": list(reasons or [])}
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def latest() -> dict[tuple[str, str, str], dict]:
    out: dict[tuple[str, str, str], dict] = {}
    p = path()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            out[(r["sol"], r["nsn"], r["pr"])] = r    # file order is time order: later lines win
        except (ValueError, KeyError):
            continue
    return out


def is_disagreement(rec: dict) -> bool:
    """not_for_us on a row the ranker liked, or quote on a row it scored 0."""
    return (rec["decision"] == "not_for_us" and rec.get("match_score", 0) > 0) or \
           (rec["decision"] == "quote" and rec.get("match_score", 0) == 0)
