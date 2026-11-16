"""Read-only DIBBS recon: accept the consent banner, then save pages for inspection.
usage: recon.py <outdir> <path-or-url> [<path-or-url> ...]"""
import pickle
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.dibbs.bsm.dla.mil"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
out = Path(sys.argv[1]); out.mkdir(exist_ok=True)
jar = out / "session.pkl"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*",
                      "Accept-Language": "en-US,en;q=0.9"})
    if jar.exists():
        s.cookies.update(pickle.loads(jar.read_bytes()))
    return s


def consent(s: requests.Session, r: requests.Response) -> requests.Response:
    soup = BeautifulSoup(r.text, "lxml")
    form = soup.find("form")
    data = {i["name"]: i.get("value", "") for i in form.find_all("input") if i.get("name") and i.get("type") == "hidden"}
    data["butAgree"] = "OK"
    action = requests.compat.urljoin(r.url, form["action"])
    return s.post(action, data=data, headers={"Referer": r.url}, timeout=30)


s = session()
for i, target in enumerate(sys.argv[2:]):
    url = target if target.startswith("http") else BASE + target
    r = s.get(url, timeout=30)
    if "dodwarning" in r.url.lower() or b'name="butAgree"' in r.content[:20000]:
        print("  consent banner -> accepting")
        r = consent(s, r)
        if r.content[:4] != b"%PDF" and (b'name="butAgree"' in r.content[:20000] or r.url.rstrip("/") != url.rstrip("/")):
            r = s.get(url, timeout=30)
    name = out / f"page{i}.{'pdf' if r.content[:4] == b'%PDF' else 'zip' if r.content[:2] == b'PK' else 'txt' if b'<html' not in r.content[:3000].lower() else 'html'}"
    name.write_bytes(r.content)
    title = BeautifulSoup(r.text, "lxml").title if b"<html" in r.content[:3000].lower() else None
    print(f"{r.status_code} {r.url} -> {name.name} ({len(r.content)} B) title={title.get_text(strip=True) if title else '-'}")
jar.write_bytes(pickle.dumps(s.cookies))
