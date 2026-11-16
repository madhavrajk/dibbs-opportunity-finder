"""Rank a snapshot against a vendor profile. Pure: no I/O, never edits identifiers."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.contracts import Match, Profile, Snapshot, Solicitation, fmt_nsn

NSN_PTS, CAGE_PTS, FSC_PTS, KW_PTS = 100, 80, 40, 30
DIBBS_NOMEN_LEN = 20


def _tokens(nomenclature: str) -> list[str]:
    return [t for t in re.split(r"[ ,]+", nomenclature.upper()) if t]


def _word_hit(kw: str, tok: str, truncated_last: bool) -> bool:
    if tok == kw or tok == kw + "S" or tok == kw + "ES" or (kw.endswith("S") and tok == kw[:-1]):
        return True
    return truncated_last and len(tok) >= 3 and kw.startswith(tok)


def _keyword_hit(keyword: str, nomenclature: str) -> bool:
    kws = keyword.upper().split()
    toks = _tokens(nomenclature)
    if not kws or not toks:
        return False
    # DIBBS pads to 20 chars; the last word is cut only when all 20 are used by text.
    cut = len(nomenclature.rstrip()) >= DIBBS_NOMEN_LEN
    last = len(toks) - 1
    return all(
        any(_word_hit(kw, t, cut and i == last) for i, t in enumerate(toks)) for kw in kws
    )


def _score(profile: Profile, sol: Solicitation, approved: dict, nsns: set[str], cage: str) -> Match:
    score, reasons = 0, []
    if sol.nsn in nsns:
        score += NSN_PTS
        reasons.append(f"NSN {fmt_nsn(sol.nsn)} on your list")
    if cage and any(a.cage.strip().upper() == cage for a in approved.get(sol.nsn, [])):
        score += CAGE_PTS
        reasons.append(f"You're an approved source (CAGE {profile.cage.strip()})")
    if sol.fsc[:4] in {f.strip()[:4] for f in profile.fscs if f.strip()}:
        score += FSC_PTS
        reasons.append(f"FSC {sol.fsc[:4]}")
    seen: set[str] = set()
    for kw in profile.keywords:
        key = " ".join(kw.upper().split())
        if key and key not in seen and _keyword_hit(key, sol.nomenclature):
            seen.add(key)
            score += KW_PTS
            reasons.append(f"keyword: {kw.strip()}")
    hidden = None
    if sol.qty is not None:
        if profile.qty_min is not None and sol.qty < profile.qty_min:
            hidden = f"qty {sol.qty} below your minimum {profile.qty_min}"
        elif profile.qty_max is not None and sol.qty > profile.qty_max:
            hidden = f"qty {sol.qty} above your maximum {profile.qty_max}"
    return Match(sol=sol, score=score, reasons=reasons, hidden_by=hidden)


def rank(profile: Profile, snapshot: Snapshot) -> list[Match]:
    nsns = {re.sub(r"[-\s]", "", n) for n in profile.nsns}
    cage = profile.cage.strip().upper()
    out = [_score(profile, s, snapshot.approved, nsns, cage) for s in snapshot.solicitations]
    out.sort(key=lambda m: (-m.score, m.sol.return_by is None, m.sol.return_by or date.max, m.sol.sol))
    return out


def summary(matches: list[Match]) -> dict:
    today = date.today()
    limit = today + timedelta(days=3)
    shown = [m for m in matches if m.score > 0 and m.hidden_by is None]
    return {
        "total": len(matches),
        "matched": len(shown),
        "hidden": sum(1 for m in matches if m.score > 0 and m.hidden_by is not None),
        "due_soon": sum(1 for m in shown if m.sol.return_by is not None and m.sol.return_by <= limit),
    }
