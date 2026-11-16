"""Stage contracts. Nothing else crosses a module boundary.

Modules and their public functions (each owned by one builder):
  app/ingest.py   parse_in(text: str, posted: date) -> list[Solicitation]
                  parse_as(text: str) -> list[ApprovedSource]
                  refresh(db_path: Path = DB_PATH) -> RefreshResult        # the only function that touches DIBBS
                  load(db_path: Path = DB_PATH) -> Snapshot | None         # read-only, used by the UI
  app/match.py    rank(profile: Profile, snapshot: Snapshot) -> list[Match] # pure, no I/O
  app/sources.py  approved_names(sol: str) -> list[ApprovedSource]          # PDF parse, cached (S4)
  app/verify.py   python -m app.verify --sample 50                          # live cross-check (S3)
  app/ui.py       Streamlit; reads load() and rank(); never calls DIBBS on render
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "dibbs.db"
PROFILE_PATH = DATA_DIR / "profile.json"

# Verified against the full 11-16-2026 file (docs/dibbs_recon.md). Validation flags; it never edits.
SOL_RE = re.compile(r"^SP[A-Z0-9]{4}\d{2}[A-Z][A-Z0-9]{4}$")
NSN_RE = re.compile(r"^\d{13}$")


class Solicitation(BaseModel):
    """One line of the daily `in` file. Identifier fields hold the source bytes exactly."""
    sol: str                          # raw, e.g. SPE1C127T0119
    nsn: str                          # raw 13 chars, e.g. 8465012768198 (may be non-standard, then flagged)
    fsc: str                          # nsn[:4]
    pr: str                           # purchase request number
    return_by: date | None            # None only if the date failed to parse (then flagged)
    qty: int | None
    ui: str                           # unit of issue, e.g. EA
    nomenclature: str                 # truncated to 20 chars by DIBBS
    codes: str                        # trailing code field, meaning unverified
    posted: date                      # date in the file name (inYYMMDD.txt)
    flags: list[str] = Field(default_factory=list)   # e.g. "non-standard NSN", "invalid solicitation number"


class ApprovedSource(BaseModel):
    nsn: str
    cage: str
    part_no: str
    name: str | None = None           # only from the solicitation PDF (S4)


class Snapshot(BaseModel):
    """Everything the UI needs, loaded from SQLite."""
    posted: date
    fetched_at: datetime
    source_file: str                  # e.g. in261115.txt
    solicitations: list[Solicitation]
    approved: dict[str, list[ApprovedSource]]   # keyed by raw NSN


class RefreshResult(BaseModel):
    posted: date
    source_file: str
    rows: int
    unique_solicitations: int
    flagged: int
    approved_nsns: int


class Profile(BaseModel):
    """The one vendor profile. Soft criteria rank; only qty_min/qty_max hide rows."""
    company: str = ""
    keywords: list[str] = Field(default_factory=list)
    nsns: list[str] = Field(default_factory=list)      # raw 13 chars; UI strips dashes from user input only
    fscs: list[str] = Field(default_factory=list)      # 4 digits
    cage: str = ""                                     # vendor's own CAGE, boosts rows where it is an approved source
    qty_min: int | None = None
    qty_max: int | None = None


class Match(BaseModel):
    sol: Solicitation
    score: int                        # 0 = no profile hit (still listed under "All RFQs")
    reasons: list[str] = Field(default_factory=list)   # human sentences, e.g. "NSN on your list", "FSC 5305", "keyword: screw"
    hidden_by: str | None = None      # e.g. "qty 1 < your minimum 2"; row kept, UI shows the count


# Shared formatting and links. Built from the raw solicitation number only.
def record_url(sol: str) -> str:
    return f"https://www.dibbs.bsm.dla.mil/rfq/rfqrec.aspx?sn={sol}"


def pdf_url(sol: str) -> str:
    return f"https://dibbs2.bsm.dla.mil/Downloads/RFQ/{sol[-1]}/{sol}.PDF"


def nsn_url(nsn: str) -> str:
    return f"https://www.dibbs.bsm.dla.mil/RFQ/RFQNsn.aspx?value={nsn}&category=issue&Scope="


def fmt_nsn(nsn: str) -> str:
    """5305-01-234-5678 for standard NSNs; anything else is shown exactly as stored."""
    return f"{nsn[:4]}-{nsn[4:6]}-{nsn[6:9]}-{nsn[9:]}" if NSN_RE.match(nsn) else nsn


def fmt_sol(sol: str) -> str:
    """SPE4A5-27-Q-0073, as DIBBS displays it; anything invalid is shown exactly as stored."""
    return f"{sol[:6]}-{sol[6:8]}-{sol[8]}-{sol[9:]}" if SOL_RE.match(sol) else sol
