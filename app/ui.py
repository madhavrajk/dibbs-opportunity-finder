"""Streamlit UI. Data prep (pure functions) is kept apart from rendering so it can be restyled."""
from __future__ import annotations

import csv
import io
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app import contracts
from app.contracts import (Match, Profile, Snapshot, fmt_nsn, fmt_sol, nsn_url, pdf_url, record_url)

COLUMNS = ["Solicitation", "NSN", "Description", "Qty", "Return by", "Why it matched", "Score",
           "PDF", "Approved sources", "Flags"]


# ---------- data prep (no streamlit) ----------
def split_terms(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,\n]", text or "") if t.strip()]


def clean_nsn(raw: str) -> str:
    """User-entered NSNs only: drop dashes and spaces."""
    return re.sub(r"[\s-]", "", raw)


def parse_nsn_text(text: str) -> list[str]:
    return [n for n in (clean_nsn(t) for t in re.split(r"[,\n]", text or "")) if n]


def parse_nsn_upload(data: bytes) -> list[str]:
    """CSV/TXT: one NSN per line or first column. Skips a header row that has no digits."""
    out = []
    for row in csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))):
        if row and (n := clean_nsn(row[0])) and any(c.isdigit() for c in n):
            out.append(n)
    return out


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def profile_is_empty(p: Profile) -> bool:
    return not (p.keywords or p.nsns or p.fscs)


def load_profile() -> Profile:
    try:
        return Profile.model_validate_json(Path(contracts.PROFILE_PATH).read_text())
    except Exception:
        return Profile()


def save_profile(p: Profile) -> None:
    path = Path(contracts.PROFILE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(p.model_dump_json(indent=2))


def days_left(m: Match, today: date) -> int | None:
    return (m.sol.return_by - today).days if m.sol.return_by else None


def build_rows(matches: list[Match], snapshot: Snapshot, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    rows = []
    for m in matches:
        s = m.sol
        d = days_left(m, today)
        why = " · ".join(m.reasons)
        if m.hidden_by:
            why = f"HIDDEN: {m.hidden_by}" + (f" · {why}" if why else "")
        rows.append({
            "Solicitation": record_url(s.sol) + "#" + fmt_sol(s.sol),
            "NSN": fmt_nsn(s.nsn),
            "Description": s.nomenclature,
            "Qty": f"{s.qty} {s.ui}".strip() if s.qty is not None else f"? {s.ui}".strip(),
            "Return by": (f"{s.return_by:%Y-%m-%d} ({d}d)" if s.return_by else "unknown"),
            "Why it matched": why,
            "Score": m.score,
            "PDF": pdf_url(s.sol),
            "Approved sources": len(snapshot.approved.get(s.nsn, [])),
            "Flags": ", ".join(s.flags),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def for_you(matches: list[Match], include_hidden: bool) -> list[Match]:
    shown = [m for m in matches if m.score > 0 and not m.hidden_by]
    if include_hidden:
        shown += [m for m in matches if m.hidden_by]
    return shown


def filter_all(matches: list[Match], query: str, fscs: list[str], within: int | None,
               today: date | None = None) -> list[Match]:
    today = today or date.today()
    q = (query or "").strip().lower()
    q_nsn = clean_nsn(q)
    out = []
    for m in matches:
        s = m.sol
        if q:
            hay = [s.sol.lower(), fmt_sol(s.sol).lower(), s.nsn.lower(), fmt_nsn(s.nsn).lower(),
                   s.nomenclature.lower()]
            if not (any(q in h for h in hay) or (q_nsn and q_nsn in s.nsn.lower())):
                continue
        if fscs and s.fsc not in fscs:
            continue
        if within is not None:
            d = days_left(m, today)
            if d is None or d > within:
                continue
        out.append(m)
    return out


# ---------- rendering ----------
def column_config() -> dict:
    return {
        "Solicitation": st.column_config.LinkColumn("Solicitation", display_text=r"#(.*)$"),
        "PDF": st.column_config.LinkColumn("PDF", display_text="PDF"),
        "Score": st.column_config.NumberColumn("Score"),
        "Approved sources": st.column_config.NumberColumn("Approved sources"),
        "Why it matched": st.column_config.TextColumn("Why it matched", width="large"),
    }


def show_table(matches: list[Match], snapshot: Snapshot) -> None:
    st.dataframe(build_rows(matches, snapshot), column_config=column_config(),
                 hide_index=True, use_container_width=True)


def show_detail(matches: list[Match], snapshot: Snapshot, key: str) -> None:
    if not matches:
        return
    by_label = {fmt_sol(m.sol.sol): m for m in matches}
    label = st.selectbox("Row detail (solicitation)", list(by_label), key=key)
    m = by_label[label]
    s = m.sol
    st.markdown(f"**{fmt_sol(s.sol)}** · NSN {fmt_nsn(s.nsn)} · FSC {s.fsc}")
    st.write({"Description": s.nomenclature, "Qty": s.qty, "Unit": s.ui, "Return by": str(s.return_by),
              "Purchase request": s.pr, "Codes": s.codes, "Posted": str(s.posted), "Score": m.score,
              "Why": " · ".join(m.reasons), "Hidden by": m.hidden_by})
    for f in s.flags:
        st.warning(f)
    src = snapshot.approved.get(s.nsn, [])
    st.markdown(f"**Approved sources ({len(src)})**")
    if src:
        st.dataframe(pd.DataFrame([{"CAGE": a.cage, "Part number": a.part_no, "Name": a.name or ""}
                                   for a in src]), hide_index=True)
    c1, c2, c3 = st.columns(3)
    c1.link_button("DIBBS record", record_url(s.sol))
    c2.link_button("Solicitation PDF", pdf_url(s.sol))
    c3.link_button("NSN history", nsn_url(s.nsn))


def sidebar_profile() -> Profile:
    saved = load_profile()
    st.sidebar.header("Your profile")
    company = st.sidebar.text_input("Company name", saved.company)
    kw = st.sidebar.text_area("Keywords (comma or newline separated)", ", ".join(saved.keywords))
    nsn_text = st.sidebar.text_area("NSNs (one per line; dashes ok)", "\n".join(saved.nsns))
    up = st.sidebar.file_uploader("Upload NSN list (CSV/TXT)", type=["csv", "txt"])
    nsns = parse_nsn_text(nsn_text)
    if up is not None:
        nsns += parse_nsn_upload(up.getvalue())
    fsc = st.sidebar.text_input("FSCs (comma separated)", ", ".join(saved.fscs))
    cage = st.sidebar.text_input("Your CAGE code", saved.cage)
    c1, c2 = st.sidebar.columns(2)
    qmin = c1.number_input("Qty min (0 = unset)", min_value=0, value=saved.qty_min or 0, step=1)
    qmax = c2.number_input("Qty max (0 = unset)", min_value=0, value=saved.qty_max or 0, step=1)
    p = Profile(company=company.strip(), keywords=dedupe(split_terms(kw)), nsns=dedupe(nsns),
                fscs=dedupe(split_terms(fsc)), cage=cage.strip(),
                qty_min=int(qmin) or None, qty_max=int(qmax) or None)
    if st.sidebar.button("Save profile"):
        save_profile(p)
        st.sidebar.success("Profile saved.")
    return p


def _mtime(path) -> float:
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False)
def _cached_load(db_path: str, mtime: float):
    from app import ingest
    return ingest.load(Path(db_path))


def get_snapshot() -> Snapshot | None:
    return _cached_load(str(contracts.DB_PATH), _mtime(contracts.DB_PATH))


def header(snapshot: Snapshot | None) -> None:
    c1, c2 = st.columns([5, 1])
    if snapshot:
        c1.markdown(f"Latest DIBBS batch: posted {snapshot.posted:%Y-%m-%d} · "
                    f"fetched {snapshot.fetched_at:%H:%M} · {snapshot.source_file}")
    if c2.button("Refresh", help="Fetch today's DIBBS batch"):
        from app import ingest
        try:
            with st.spinner("Fetching today's DIBBS batch..."):
                ingest.refresh(Path(contracts.DB_PATH))
            st.cache_data.clear()
            st.rerun()
        except RuntimeError as e:
            st.error(str(e))


def main() -> None:
    st.set_page_config(page_title="DIBBS Opportunity Finder", layout="wide")
    st.title("DIBBS Opportunity Finder")
    profile = sidebar_profile()
    snapshot = get_snapshot()
    header(snapshot)
    if snapshot is None:
        st.info("No data yet. Click Refresh to fetch today's DIBBS batch.")
        return
    from app import match
    matches = match.rank(profile, snapshot)
    s = match.summary(matches)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("RFQs in batch", s["total"])
    m2.metric("Matches for you", s["matched"])
    m3.metric("Hidden by your qty filter", s["hidden"])
    m4.metric("Due within 3 days", s["due_soon"])

    tab1, tab2 = st.tabs(["For you", "All RFQs"])
    with tab1:
        if profile_is_empty(profile):
            st.info("Tell us what you sell and we will rank today's RFQs. Three ways to match: "
                    "keywords in the description, a list of NSNs, or FSC groups (first 4 digits of the NSN).")
        hidden = [m for m in matches if m.hidden_by]
        show_h = st.toggle(f"Show {len(hidden)} rows hidden by your qty filter", key="show_hidden")
        view = for_you(matches, show_h)
        show_table(view, snapshot)
        show_detail(view, snapshot, "detail_you")
    with tab2:
        f1, f2, f3 = st.columns([2, 2, 2])
        q = f1.text_input("Search (solicitation, NSN, description)")
        fscs = f2.multiselect("FSC", sorted({m.sol.fsc for m in matches}))
        within = f3.slider("Due within days", 0, 60, 60)
        view = filter_all(matches, q, fscs, None if within >= 60 else within)
        st.caption(f"{len(view)} of {len(matches)} RFQs")
        show_table(view, snapshot)
        show_detail(view, snapshot, "detail_all")


if __name__ == "__main__":
    main()
