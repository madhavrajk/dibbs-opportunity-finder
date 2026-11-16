"""Streamlit UI. Data prep (pure functions) is kept apart from rendering so it can be restyled.

Rules this file keeps: identifiers are displayed only through fmt_sol / fmt_nsn, links only through record_url /
pdf_url / nsn_url, and nothing here calls DIBBS while rendering. The two network actions are explicit button clicks:
Refresh (ingest.refresh) and "Load company names from the solicitation PDF" (sources.approved_names).
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app import contracts, feedback
from app.contracts import (ApprovedSource, Match, Profile, Snapshot, Solicitation, fmt_nsn, fmt_sol, nsn_url,
                           pdf_url, record_url)

COLUMNS = ["Status", "Solicitation", "Line", "PR", "NSN", "Description", "Qty", "Unit", "Return by", "Due in",
           "Score", "Why it matched", "Approved sources", "PDF", "Flags"]
DUE_SOON_DAYS = 3


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


def line_key(s: Solicitation) -> tuple[str, str, str]:
    return (s.sol, s.pr, s.nsn)


def line_numbers(snapshot: Snapshot) -> dict[tuple[str, str, str], tuple[int, int]]:
    """(sol, pr, nsn) -> (line n, lines on that solicitation), in file order. Lines are never merged or dropped."""
    totals = Counter(s.sol for s in snapshot.solicitations)
    seen: Counter = Counter()
    out = {}
    for s in snapshot.solicitations:
        k = line_key(s)
        if k not in out:
            seen[s.sol] += 1
            out[k] = (seen[s.sol], totals[s.sol])
    return out


def status_word(m: Match, today: date) -> str:
    """Status in words (colour is never the only signal)."""
    if m.hidden_by:
        return "Hidden (qty)"
    d = days_left(m, today)
    if d is None:
        return "No date"
    if d < 0:
        return "Past due"
    if d == 0:
        return "Due today"
    if d <= DUE_SOON_DAYS:
        return "Due soon"
    return "Open"


def build_rows(matches: list[Match], snapshot: Snapshot, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    lines = line_numbers(snapshot)
    rows = []
    for m in matches:
        s = m.sol
        why = " · ".join(m.reasons)
        if m.hidden_by:
            why = f"HIDDEN: {m.hidden_by}" + (f" · {why}" if why else "")
        n, total = lines.get(line_key(s), (1, 1))
        rows.append({
            "Status": status_word(m, today),
            "Solicitation": record_url(s.sol) + "#" + fmt_sol(s.sol),
            "Line": f"{n} of {total}" if total > 1 else "",
            "PR": s.pr,
            "NSN": fmt_nsn(s.nsn),
            "Description": s.nomenclature,
            "Qty": s.qty,
            "Unit": s.ui,
            "Return by": s.return_by,
            "Due in": days_left(m, today),
            "Score": m.score,
            "Why it matched": why,
            "Approved sources": len(snapshot.approved.get(s.nsn, [])),
            "PDF": pdf_url(s.sol),
            "Flags": ", ".join(s.flags),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def for_you(matches: list[Match], include_hidden: bool) -> list[Match]:
    shown = [m for m in matches if m.score > 0 and not m.hidden_by]
    if include_hidden:
        shown += [m for m in matches if m.score > 0 and m.hidden_by]   # matches the "hidden" KPI
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


def row_label(m: Match, lines: dict) -> str:
    s = m.sol
    n, total = lines.get(line_key(s), (1, 1))
    line = f" · line {n} of {total}" if total > 1 else ""
    return f"{fmt_sol(s.sol)}{line} · PR {s.pr} · {fmt_nsn(s.nsn)} · {s.nomenclature}"


def merge_sources(as_sources: list[ApprovedSource], pdf_sources: list[ApprovedSource] | None) -> pd.DataFrame:
    """As-file rows first (the as-file wins for CAGE); PDF adds company names and any PDF-only CAGEs. Nothing dropped."""
    pdf_by_cage = {p.cage: p for p in (pdf_sources or [])}
    rows = []
    for a in as_sources:
        p = pdf_by_cage.get(a.cage)
        rows.append({"CAGE": a.cage, "Part number": a.part_no, "Company": (p.name if p else a.name) or "",
                     "Listed in": "as-file + PDF" if p else "as-file"})
    as_cages = {a.cage for a in as_sources}
    for p in pdf_sources or []:
        if p.cage not in as_cages:
            rows.append({"CAGE": p.cage, "Part number": p.part_no, "Company": p.name or "", "Listed in": "PDF only"})
    return pd.DataFrame(rows, columns=["CAGE", "Part number", "Company", "Listed in"])


def kpis(matches: list[Match], snapshot: Snapshot, profile: Profile) -> dict:
    shown = [m for m in matches if m.score > 0 and not m.hidden_by]
    you = sum(1 for m in shown if any(r.startswith("You're an approved source") for r in m.reasons))
    listed = sum(1 for m in shown if snapshot.approved.get(m.sol.nsn))
    return {"solicitations": len({s.sol for s in snapshot.solicitations}),
            "flagged": sum(1 for s in snapshot.solicitations if s.flags),
            "approved_you": you, "approved_listed": listed,
            "multi_line": sum(1 for c in Counter(s.sol for s in snapshot.solicitations).values() if c > 1)}


def age_text(fetched: datetime, now: datetime | None = None) -> str:
    mins = int(((now or datetime.now()) - fetched).total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} min ago"
    if mins < 48 * 60:
        return f"{mins // 60} h ago"
    return f"{mins // 1440} days ago"


# ---------- rendering ----------
def column_config(max_score: int = 1) -> dict:
    cc = st.column_config
    return {
        "Status": cc.TextColumn("Status", width="small", help="Due today / Due soon (3 days) / Open / Hidden (qty)"),
        "Solicitation": cc.LinkColumn("Solicitation", display_text=r"#(.*)$", help="Opens the DIBBS record page",
                                      pinned=True),
        "Line": cc.TextColumn("Line", width="small",
                              help="Solicitations with several lines (one per purchase request) show 'n of N'"),
        "PR": cc.TextColumn("PR", help="Purchase request number; tells lines of one solicitation apart"),
        "NSN": cc.TextColumn("NSN"),
        "Description": cc.TextColumn("Description", width="medium"),
        "Qty": cc.NumberColumn("Qty", format="%d"),
        "Unit": cc.TextColumn("Unit", width="small"),
        "Return by": cc.DateColumn("Return by", format="YYYY-MM-DD"),
        "Due in": cc.NumberColumn("Due in", format="%d d", help="Days until the return-by date"),
        "Score": cc.ProgressColumn("Score", format="%d", min_value=0, max_value=max(max_score, 1),
                                   help="Higher = more profile criteria hit. See 'Why it matched'."),
        "Why it matched": cc.TextColumn("Why it matched", width="large"),
        "Approved sources": cc.NumberColumn("Approved sources", format="%d",
                                            help="Approved CAGE/part numbers on file for this NSN"),
        "PDF": cc.LinkColumn("PDF", display_text="PDF", width="small"),
        "Flags": cc.TextColumn("Flags", help="Identifier issues: shown exactly as published, never corrected"),
    }


def show_table(matches: list[Match], snapshot: Snapshot, key: str) -> int | None:
    """Renders the table; returns the clicked row index, if any."""
    df = build_rows(matches, snapshot)
    order = [c for c in COLUMNS if c != "Flags" or df["Flags"].astype(bool).any()]
    ev = st.dataframe(df, column_config=column_config(max((m.score for m in matches), default=1)),
                      column_order=order, hide_index=True, width="stretch", height=420,
                      on_select="rerun", selection_mode="single-row", key=f"{key}_table")
    rows = getattr(getattr(ev, "selection", None), "rows", None) or []
    return rows[0] if rows else None


def _fact(col, label: str, value) -> None:
    col.markdown(f"<span style='color:#6B7280;font-size:0.8rem'>{label}</span><br>{value}",
                 unsafe_allow_html=True)


def show_pdf_names(s: Solicitation, src: list[ApprovedSource], key: str) -> list[ApprovedSource] | None:
    """On-demand only: the button click is the one place this tab touches the network."""
    store = st.session_state.setdefault("pdf_names", {})
    if st.button("Load company names from the solicitation PDF", key=f"{key}_pdf",
                 help="Downloads this solicitation's PDF from DIBBS once (cached in data/pdf/)"):
        from app import sources
        try:
            with st.spinner(f"Reading the solicitation PDF for {fmt_sol(s.sol)}..."):
                store[s.sol] = sources.approved_names(s.sol, s.nsn)
        except Exception as e:  # shown, never fatal
            store[s.sol] = f"{type(e).__name__}: {e}"
    got = store.get(s.sol)
    if isinstance(got, str):
        st.error(f"Could not load names from the PDF. {got}")
        return None
    if got is not None:
        from app import sources
        st.caption(f"{len(got)} source(s) read from the solicitation PDF.")
        for f in sources.reconcile(got, src):
            st.warning("Check: " + f.replace(f"NSN {s.nsn}", f"NSN {fmt_nsn(s.nsn)}"))
    return got


DECISION_TEXT = {"quote": "Shortlisted to quote", "not_for_us": "Marked not for us"}


def decision_key(s: Solicitation) -> tuple[str, str, str]:
    return (s.sol, s.nsn, s.pr)


def shortlist(matches: list[Match], decisions: dict) -> list[Match]:
    return [m for m in matches if decisions.get(decision_key(m.sol), {}).get("decision") == "quote"]


def trace_lines(path=None) -> dict | None:
    """Latest refresh trace (read-only), or None when no refresh has been recorded."""
    p = Path(path) if path else Path(contracts.DATA_DIR) / "refresh_log.jsonl"
    try:
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None


def show_trace() -> None:
    with st.expander("How this batch was fetched"):
        tr = trace_lines()
        if not tr:
            st.caption("Run Refresh to record a trace.")
            return
        st.caption(f"Last refresh {tr.get('ts', '')} · outcome: {tr.get('outcome', '?')}")
        for ln in tr.get("story", []):
            st.markdown(f"- {ln}")
        st.dataframe(pd.DataFrame([{"Stage": x["name"], "Seconds": x["seconds"], "Note": x["note"]}
                                   for x in tr.get("stages", [])]), hide_index=True, width="stretch")


def show_decision(m: Match, key: str, profile: Profile | None) -> None:
    """Approve / reject in one place. Every click is appended to data/feedback.jsonl; the latest decision wins."""
    s = m.sol
    cur = feedback.latest().get(decision_key(s))
    note = st.text_input("Note (optional)", key=f"{key}_note", max_chars=140, placeholder="why? e.g. we do not stock this")
    d1, d2, d3 = st.columns([1, 1, 3], vertical_alignment="center")
    pick = None
    if d1.button("Shortlist to quote", key=f"{key}_quote", type="primary", width="stretch"):
        pick = "quote"
    if d2.button("Not for us", key=f"{key}_nfu", width="stretch"):
        pick = "not_for_us"
    if pick:
        feedback.record(s.sol, s.nsn, s.pr, pick, note, profile.model_dump() if profile else {}, m.score,
                        m.reasons)
        st.rerun()
    if cur:
        d3.caption(f"{DECISION_TEXT[cur['decision']]} on {cur['ts'][:16].replace('T', ' ')} UTC"
                   + (f": {cur['note']}" if cur.get("note") else ""))
    else:
        d3.caption("No decision yet. Your choices are recorded and help tune the ranking.")


def show_detail(matches: list[Match], snapshot: Snapshot, key: str, clicked: int | None = None,
                profile: Profile | None = None) -> None:
    if not matches:
        return
    lines = line_numbers(snapshot)
    idx = list(range(len(matches)))
    if clicked is not None and clicked < len(matches) and st.session_state.get(f"{key}_last") != clicked:
        st.session_state[f"{key}_last"] = clicked
        st.session_state[key] = clicked
    if st.session_state.get(key) is not None and st.session_state[key] >= len(matches):
        st.session_state[key] = 0
    i = st.selectbox("Row detail (click a row above, or pick one)", idx, key=key,
                     format_func=lambda j: row_label(matches[j], lines))
    m = matches[i]
    s = m.sol
    n, total = lines.get(line_key(s), (1, 1))
    with st.container(border=True):
        word = status_word(m, date.today())
        color = {"Due today": "red", "Past due": "red", "Due soon": "orange", "Hidden (qty)": "gray"}.get(word, "blue")
        h1, h2 = st.columns([4, 1])
        h1.markdown(f"#### {fmt_sol(s.sol)}" + (f" &nbsp;·&nbsp; line {n} of {total}" if total > 1 else ""))
        h1.markdown(f"NSN {fmt_nsn(s.nsn)} · FSC {s.fsc} · {s.nomenclature}")
        with h2:
            st.badge(word, color=color)
        c = st.columns(6)
        _fact(c[0], "Quantity", f"{s.qty if s.qty is not None else 'unknown'} {s.ui}")
        _fact(c[1], "Return by", f"{s.return_by:%Y-%m-%d}" if s.return_by else "unknown")
        _fact(c[2], "Purchase request", s.pr or "–")
        _fact(c[3], "Score", m.score)
        _fact(c[4], "Posted", f"{s.posted:%Y-%m-%d}")
        _fact(c[5], "Codes", s.codes or "–")
        st.markdown("**Why it matched:** " + (" · ".join(m.reasons) or "no profile criteria hit"))
        if m.hidden_by:
            st.info(f"Hidden by your quantity filter: {m.hidden_by}. Kept here so nothing is missed.")
        for f in s.flags:
            st.warning(f"Flagged: {f}. Shown exactly as published.")
        if total > 1:
            sib = [x for x in snapshot.solicitations if x.sol == s.sol]
            st.markdown(f"**All {total} lines on this solicitation**")
            st.dataframe(pd.DataFrame([{"Line": f"{lines.get(line_key(x), (0, 0))[0]} of {total}", "PR": x.pr,
                                        "NSN": fmt_nsn(x.nsn), "Description": x.nomenclature, "Qty": x.qty,
                                        "Unit": x.ui} for x in sib]), hide_index=True, width="stretch")
        src = snapshot.approved.get(s.nsn, [])
        st.markdown(f"**Approved sources ({len(src)})**")
        pdf_src = show_pdf_names(s, src, key)
        table = merge_sources(src, pdf_src)
        if len(table):
            st.dataframe(table, hide_index=True, width="stretch")
        else:
            st.caption("No approved sources on file for this NSN.")
        show_decision(m, key, profile)
        b1, b2, b3, _ = st.columns([1, 1, 1, 2])
        b1.link_button("DIBBS record", record_url(s.sol), width="stretch")
        b2.link_button("Solicitation PDF", pdf_url(s.sol), width="stretch")
        b3.link_button("NSN history", nsn_url(s.nsn), width="stretch")


def sidebar_profile() -> Profile:
    saved = load_profile()
    sb = st.sidebar
    sb.header("Your profile")
    sb.caption("Setup, done once. Rankings update as you type; Save keeps it for tomorrow.")
    company = sb.text_input("Company name", saved.company)
    sb.subheader("What you sell")
    sb.caption("Any one of these is enough. Rows that hit more criteria rank higher.")
    kw = sb.text_area("Keywords (comma or newline separated)", ", ".join(saved.keywords),
                      help="Matched against the DIBBS description, e.g. screw, bolt, washer")
    nsn_text = sb.text_area("NSNs (one per line; dashes ok)", "\n".join(saved.nsns))
    up = sb.file_uploader("Upload NSN list (CSV/TXT)", type=["csv", "txt"])
    nsns = parse_nsn_text(nsn_text)
    if up is not None:
        nsns += parse_nsn_upload(up.getvalue())
    fsc = sb.text_input("FSCs (comma separated)", ", ".join(saved.fscs),
                        help="First 4 digits of the NSN, e.g. 5305 screws, 5310 nuts and washers")
    cage = sb.text_input("Your CAGE code", saved.cage, help="Boosts RFQs where you are an approved source")
    sb.subheader("Quantity filter")
    sb.caption("The only filter that hides rows. The page always says how many.")
    c1, c2 = sb.columns(2)
    qmin = c1.number_input("Qty min (0 = unset)", min_value=0, value=saved.qty_min or 0, step=1)
    qmax = c2.number_input("Qty max (0 = unset)", min_value=0, value=saved.qty_max or 0, step=1)
    p = Profile(company=company.strip(), keywords=dedupe(split_terms(kw)), nsns=dedupe(nsns),
                fscs=dedupe(split_terms(fsc)), cage=cage.strip(),
                qty_min=int(qmin) or None, qty_max=int(qmax) or None)
    if sb.button("Save profile", type="primary", width="stretch"):
        save_profile(p)
        sb.success("Profile saved.")
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


def header(snapshot: Snapshot | None, profile: Profile) -> None:
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    c1.title("DIBBS Opportunity Finder")
    who = profile.company or "your profile"
    c1.caption(f"Today's DLA RFQs from DIBBS, ranked for {who}, each with the reason it matched.")
    clicked = c2.button("Refresh", help="Fetch today's DIBBS batch (the only time the page contacts DIBBS)",
                        width="stretch")
    if snapshot:
        st.markdown(f"Latest DIBBS batch: **posted {snapshot.posted:%Y-%m-%d}** · "
                    f"fetched {snapshot.fetched_at:%Y-%m-%d %H:%M} ({age_text(snapshot.fetched_at)}) · "
                    f"source `{snapshot.source_file}` (DIBBS daily file)")
    show_trace()
    if clicked:
        from app import ingest
        try:
            with st.spinner("Fetching today's DIBBS batch..."):
                ingest.refresh(Path(contracts.DB_PATH))
            st.cache_data.clear()
            st.rerun()
        except RuntimeError as e:
            st.error(str(e))


def kpi_row(s: dict, k: dict, profile: Profile) -> None:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("RFQs in batch", s["total"], delta=f"{k['solicitations']:,} solicitations", delta_color="off",
              delta_arrow="off", border=True, help="Lines in today's file; a solicitation can have several lines")
    ap = (f"{k['approved_you']} where you're an approved source" if profile.cage
          else f"{k['approved_listed']} with approved sources on file")
    m2.metric("Matches for you", s["matched"], delta=ap, delta_color="off", delta_arrow="off", border=True)
    m3.metric("Hidden by your qty filter", s["hidden"], delta="kept; toggle to show", delta_color="off",
              delta_arrow="off", border=True)
    m4.metric("Due within 3 days", s["due_soon"], delta="of your matches", delta_color="off", delta_arrow="off",
              border=True)


def main() -> None:
    st.set_page_config(page_title="DIBBS Opportunity Finder", layout="wide")
    profile = sidebar_profile()
    snapshot = get_snapshot()
    header(snapshot, profile)
    if snapshot is None:
        st.info("No data yet. Click Refresh to fetch today's DIBBS batch (about 2,500 RFQ lines, under a minute).")
        return
    from app import match
    matches = match.rank(profile, snapshot)
    s = match.summary(matches)
    k = kpis(matches, snapshot, profile)
    kpi_row(s, k, profile)
    notes = []
    if k["flagged"]:
        notes.append(f"{k['flagged']} lines have non-standard identifiers: flagged and shown exactly as published.")
    if k["multi_line"]:
        notes.append(f"{k['multi_line']} solicitations have several lines (one per purchase request); "
                     "each line is its own row, numbered 'n of N'.")
    if notes:
        st.caption(" ".join(notes))

    decisions = feedback.latest()
    short = shortlist(matches, decisions)
    tab1, tab2, tab3 = st.tabs([f"For you ({s['matched']})", f"All RFQs ({s['total']})",
                                f"Shortlist ({len(short)})"])
    with tab1:
        if profile_is_empty(profile):
            st.info("Tell us what you sell and we will rank today's RFQs. Three ways to match, set in the sidebar: "
                    "**keywords** in the description (e.g. screw, washer), a list of **NSNs** (type or upload), or "
                    "**FSC** groups (first 4 digits of the NSN, e.g. 5305).")
        hidden = [m for m in matches if m.score > 0 and m.hidden_by]
        show_h = st.toggle(f"Show {len(hidden)} rows hidden by your qty filter", key="show_hidden")
        view = for_you(matches, show_h)
        if view:
            st.caption(f"{len(view)} lines across {len({m.sol.sol for m in view})} solicitations, best match first.")
        elif not profile_is_empty(profile):
            st.info("Nothing in today's batch matches your profile. Try broader keywords or more FSCs, "
                    "or browse All RFQs.")
        clicked = show_table(view, snapshot, "you")
        show_detail(view, snapshot, "detail_you", clicked, profile)
    with tab2:
        f1, f2, f3 = st.columns([2, 2, 2])
        q = f1.text_input("Search (solicitation, NSN, description)", placeholder="e.g. SPE4A0-27-T-0616 or washer")
        fscs = f2.multiselect("FSC", sorted({m.sol.fsc for m in matches}))
        within = f3.slider("Due within days", 0, 60, 60, help="60 = no limit")
        view = filter_all(matches, q, fscs, None if within >= 60 else within)
        st.caption(f"{len(view)} of {len(matches)} RFQs")
        clicked = show_table(view, snapshot, "all")
        show_detail(view, snapshot, "detail_all", clicked, profile)
    with tab3:
        if short:
            st.caption(f"{len(short)} lines you marked to quote. Newest decision wins; change one from its detail.")
            clicked = show_table(short, snapshot, "short")
            show_detail(short, snapshot, "detail_short", clicked, profile)
        else:
            st.info("Nothing shortlisted yet. Open a row and click Shortlist to quote.")


if __name__ == "__main__":
    main()
