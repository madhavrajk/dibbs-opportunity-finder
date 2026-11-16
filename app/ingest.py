"""Ingest: parse the DIBBS daily `in` and `as` files, refresh from DIBBS, store/load SQLite.
Identifiers are raw slices, never stripped or fixed; failures are flagged, rows are kept."""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

from app.contracts import (DATA_DIR, DB_PATH, NSN_RE, SOL_RE, ApprovedSource, RefreshResult, Snapshot,
                           Solicitation)

RECENT_URL = "https://www.dibbs.bsm.dla.mil/Rfq/RfqDates.aspx?category=recent"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
TIMEOUT = 30
RETRIES = 2


def parse_in(text: str, posted: date) -> list[Solicitation]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        sol, nsn = line[0:13], line[13:26]
        flags = []
        if not SOL_RE.match(sol):
            flags.append("invalid solicitation number")
        if not NSN_RE.match(nsn):
            flags.append("non-standard NSN")
        try:
            return_by = datetime.strptime(line[72:80], "%m/%d/%y").date()
        except ValueError:
            return_by = None
            flags.append("unparsed return-by date")
        try:
            qty = int(line[97:106].strip())
        except ValueError:
            qty = None
            flags.append("unparsed quantity")
        rows.append(Solicitation(
            sol=sol, nsn=nsn, fsc=nsn[:4], pr=line[62:72], return_by=return_by, qty=qty,
            ui=line[106:108], nomenclature=line[108:128].rstrip(), codes=line[128:140],
            posted=posted, flags=flags))
    return rows


def parse_as(text: str) -> list[ApprovedSource]:
    out = []
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) >= 3:
            out.append(ApprovedSource(nsn=rec[0], cage=rec[1], part_no=rec[2]))
    return out


# ---- network ----
def needs_consent(body: str) -> bool:
    return 'name="butAgree"' in body


def _hidden_inputs(html: str) -> tuple[str | None, dict[str, str]]:
    from bs4 import BeautifulSoup
    form = BeautifulSoup(html, "lxml").find("form")
    if form is None:
        return None, {}
    data = {i["name"]: i.get("value", "") for i in form.find_all("input")
            if i.get("name") and i.get("type") == "hidden"}
    return form.get("action", ""), data


def _get(s: requests.Session, url: str) -> requests.Response:
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            r = s.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            if r.content[:4] == b"%PDF" or r.content[:2] == b"PK" or not needs_consent(r.text[:50000]):
                return r
            action, data = _hidden_inputs(r.text)
            data["butAgree"] = "OK"
            p = s.post(urljoin(r.url, action or r.url), data=data, headers={"Referer": r.url}, timeout=TIMEOUT)
            p.raise_for_status()
            r = s.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            if needs_consent(r.text[:50000]) and r.content[:2] != b"PK":
                raise RuntimeError("consent banner still showing after accepting")
            return r
        except (requests.RequestException, RuntimeError) as e:
            last = e
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"DIBBS request failed for {url}: {last}")


def _find_latest(html: str, base: str) -> tuple[str, str, str]:
    """Return (yymmdd, in_url, bq_url) of the newest in file that has a matching bq zip."""
    ins = {m.group(2): m.group(1) for m in re.finditer(r"""href=["']([^"']*?/in(\d{6})\.txt)["']""", html, re.I)}
    bqs = {m.group(2): m.group(1) for m in re.finditer(r"""href=["']([^"']*?/bq(\d{6})\.zip)["']""", html, re.I)}
    common = sorted(set(ins) & set(bqs))
    if not common:
        raise RuntimeError("No matching in*.txt and bq*.zip links found on the DIBBS Recent page")
    d = common[-1]
    return d, urljoin(base, ins[d]), urljoin(base, bqs[d])


def _cached(s: requests.Session, url: str, path: Path) -> bytes:
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    body = _get(s, url).content
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def _store(db_path: Path, posted: date, source_file: str, sols: list[Solicitation],
           approved: list[ApprovedSource]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        with con:
            con.executescript("""
                DROP TABLE IF EXISTS meta; DROP TABLE IF EXISTS solicitations; DROP TABLE IF EXISTS approved;
                CREATE TABLE meta(posted TEXT, fetched_at TEXT, source_file TEXT);
                CREATE TABLE solicitations(idx INTEGER, sol TEXT, nsn TEXT, fsc TEXT, pr TEXT, return_by TEXT,
                    qty INTEGER, ui TEXT, nomenclature TEXT, codes TEXT, posted TEXT, flags TEXT);
                CREATE TABLE approved(idx INTEGER, nsn TEXT, cage TEXT, part_no TEXT, name TEXT);
            """)
            con.execute("INSERT INTO meta VALUES (?,?,?)",
                        (posted.isoformat(), datetime.now().isoformat(timespec="seconds"), source_file))
            con.executemany(
                "INSERT INTO solicitations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(i, x.sol, x.nsn, x.fsc, x.pr, x.return_by.isoformat() if x.return_by else None, x.qty, x.ui,
                  x.nomenclature, x.codes, x.posted.isoformat(), json.dumps(x.flags)) for i, x in enumerate(sols)])
            con.executemany("INSERT INTO approved VALUES (?,?,?,?,?)",
                            [(i, a.nsn, a.cage, a.part_no, a.name) for i, a in enumerate(approved)])
    finally:
        con.close()


def load(db_path: Path = DB_PATH) -> Snapshot | None:
    if not Path(db_path).exists():
        return None
    con = sqlite3.connect(db_path)
    try:
        meta = con.execute("SELECT posted, fetched_at, source_file FROM meta").fetchone()
        if meta is None:
            return None
        sols = [Solicitation(
            sol=r[0], nsn=r[1], fsc=r[2], pr=r[3], return_by=date.fromisoformat(r[4]) if r[4] else None,
            qty=r[5], ui=r[6], nomenclature=r[7], codes=r[8], posted=date.fromisoformat(r[9]),
            flags=json.loads(r[10]))
            for r in con.execute("SELECT sol,nsn,fsc,pr,return_by,qty,ui,nomenclature,codes,posted,flags "
                                 "FROM solicitations ORDER BY idx")]
        approved: dict[str, list[ApprovedSource]] = {}
        for r in con.execute("SELECT nsn,cage,part_no,name FROM approved ORDER BY idx"):
            approved.setdefault(r[0], []).append(ApprovedSource(nsn=r[0], cage=r[1], part_no=r[2], name=r[3]))
    except sqlite3.Error:
        return None
    finally:
        con.close()
    return Snapshot(posted=date.fromisoformat(meta[0]), fetched_at=datetime.fromisoformat(meta[1]),
                    source_file=meta[2], solicitations=sols, approved=approved)


def refresh(db_path: Path = DB_PATH) -> RefreshResult:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*",
                      "Accept-Language": "en-US,en;q=0.9"})
    page = _get(s, RECENT_URL)
    yymmdd, in_url, bq_url = _find_latest(page.text, page.url)
    cache = DATA_DIR / yymmdd
    in_name = f"in{yymmdd}.txt"
    in_bytes = _cached(s, in_url, cache / in_name)
    bq_bytes = _cached(s, bq_url, cache / f"bq{yymmdd}.zip")
    try:
        with zipfile.ZipFile(io.BytesIO(bq_bytes)) as z:
            as_names = [n for n in z.namelist() if re.fullmatch(r"as\d{6}\.txt", n.rsplit("/", 1)[-1], re.I)]
            if not as_names:
                raise RuntimeError(f"no as*.txt inside bq{yymmdd}.zip")
            as_text = z.read(as_names[0]).decode("latin-1")
    except zipfile.BadZipFile as e:
        (cache / f"bq{yymmdd}.zip").unlink(missing_ok=True)
        raise RuntimeError(f"bq{yymmdd}.zip is not a valid zip (deleted from cache): {e}") from e
    posted = datetime.strptime(yymmdd, "%y%m%d").date()
    sols = parse_in(in_bytes.decode("latin-1"), posted)
    if not sols:
        (cache / in_name).unlink(missing_ok=True)
        raise RuntimeError(f"{in_name} contained no rows")
    approved = parse_as(as_text)
    _store(db_path, posted, in_name, sols, approved)
    return RefreshResult(posted=posted, source_file=in_name, rows=len(sols),
                         unique_solicitations=len({x.sol for x in sols}),
                         flagged=sum(1 for x in sols if x.flags),
                         approved_nsns=len({a.nsn for a in approved}))


if __name__ == "__main__":
    print(refresh())
