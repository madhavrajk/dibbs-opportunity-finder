"""Approved-source company names from the solicitation PDF (S4). Cached per solicitation under data/pdf/."""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import requests

from app.contracts import DATA_DIR, ApprovedSource, pdf_url

PDF_DIR = DATA_DIR / "pdf"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
SOURCE_RE = re.compile(r"^\s*(?P<name>.+?)\s+(?P<cage>[A-Z0-9]{5})\s+P/N\s+(?P<pn>\S+)\s*$")
_session: requests.Session | None = None


def parse_sources(text: str) -> list[ApprovedSource]:
    """Name/CAGE/part-number lines; nsn is unknown here (caller fills). Deduped by (cage, pn), identifiers verbatim."""
    out, seen = [], set()
    for line in text.splitlines():
        m = SOURCE_RE.match(line)
        if not m or (m["cage"], m["pn"]) in seen:
            continue
        seen.add((m["cage"], m["pn"]))
        out.append(ApprovedSource(nsn="", cage=m["cage"], part_no=m["pn"], name=m["name"]))
    return out


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": UA, "Accept": "text/html,application/pdf,*/*",
                                 "Accept-Language": "en-US,en;q=0.9"})
    return _session


def _consent(s: requests.Session, r: requests.Response) -> requests.Response:
    from bs4 import BeautifulSoup
    form = BeautifulSoup(r.text, "lxml").find("form")
    if form is None:
        raise RuntimeError("consent page has no form")
    data = {i["name"]: i.get("value", "") for i in form.find_all("input")
            if i.get("name") and i.get("type") == "hidden"}
    data["butAgree"] = "OK"
    return s.post(urljoin(r.url, form.get("action", "")), data=data, headers={"Referer": r.url}, timeout=30)


def _download(sol: str) -> bytes:
    url = pdf_url(sol)
    s = _get_session()
    last = "unknown error"
    for _ in range(3):  # first try + 2 retries
        try:
            r = s.get(url, timeout=30)
            if r.content[:4] != b"%PDF" and b'name="butAgree"' in r.content[:50000]:
                _consent(s, r)
                r = s.get(url, timeout=30)
            if r.content[:4] == b"%PDF":
                return r.content
            last = f"HTTP {r.status_code}, not a PDF (starts {r.content[:20]!r})"
        except requests.RequestException as e:
            last = str(e)
    raise RuntimeError(f"could not fetch solicitation PDF for {sol} from {url}: {last}")


def approved_names(sol: str, nsn: str = "") -> list[ApprovedSource]:
    cache = PDF_DIR / f"{sol}.json"
    if cache.exists():
        return [ApprovedSource(**d) for d in json.loads(cache.read_text())]
    import pymupdf
    data = _download(sol)
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
    except Exception as e:
        raise RuntimeError(f"could not read PDF for {sol}: {e}") from e
    sources = [s.model_copy(update={"nsn": nsn}) for s in parse_sources(text)]
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([s.model_dump() for s in sources], indent=1))
    return sources


def names_for(sols: list[tuple[str, str]], limit: int = 20) -> dict[str, list[ApprovedSource] | str]:
    """Sequential and polite. Value is the list, or an error string for that sol."""
    out: dict[str, list[ApprovedSource] | str] = {}
    for sol, nsn in sols[:limit]:
        try:
            out[sol] = approved_names(sol, nsn)
        except Exception as e:  # one bad PDF never stops the rest
            out[sol] = f"{type(e).__name__}: {e}"
    return out


def reconcile(pdf_sources: list[ApprovedSource], as_sources: list[ApprovedSource]) -> list[str]:
    """Report CAGE differences per NSN. The as-file wins for the CAGE; this only reports."""
    flags = []
    nsns = {s.nsn for s in pdf_sources} | {s.nsn for s in as_sources}
    for nsn in sorted(nsns):
        p = {s.cage: s for s in pdf_sources if s.nsn == nsn}
        a = {s.cage: s for s in as_sources if s.nsn == nsn}
        for c in sorted(p.keys() - a.keys()):
            flags.append(f"NSN {nsn}: CAGE {c} ({p[c].name}) is in the PDF but not in the as-file; as-file wins")
        for c in sorted(a.keys() - p.keys()):
            flags.append(f"NSN {nsn}: CAGE {c} is in the as-file but not in the PDF")
    return flags
