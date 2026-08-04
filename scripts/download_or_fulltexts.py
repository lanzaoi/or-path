#!/usr/bin/env python3
"""Concurrent OA fulltext downloader for Top500 → knowledge/inbox_pdf/or_fulltext."""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
TOP = ROOT / "knowledge" / "or_papers_top500.json"
INBOX = ROOT / "knowledge" / "inbox_pdf" / "or_fulltext"
MANIFEST = ROOT / "knowledge" / "or_fulltext_download_manifest.json"
MAILTO = "orpath-rag@users.noreply.github.com"
WORKERS = 6

UA_API = f"OR-Path-fulltext/1.2 (mailto:{MAILTO})"
UA_DL = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

INBOX.mkdir(parents=True, exist_ok=True)
LOCK = Lock()


def load_man() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"items": {}}


def save_man(m: dict) -> None:
    with LOCK:
        MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def get_json(url: str, timeout: int = 45) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA_API, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def get_bytes(url: str, timeout: int = 100) -> tuple[int, bytes, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA_DL,
            "Accept": "application/pdf,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type") or "", r.geturl()
    except urllib.error.HTTPError as e:
        try:
            b = e.read()
        except Exception:
            b = b""
        return e.code, b, "", url
    except Exception as e:
        return 0, str(e).encode(), "", url


def pdf_bytes(body: bytes) -> bytes | None:
    if body[:4] == b"%PDF":
        return body
    i = body.find(b"%PDF")
    if 0 <= i < 4096:
        return body[i:]
    return None


def html_pdf_link(html: bytes, base: str) -> str | None:
    t = html.decode("utf-8", errors="ignore")
    for pat in (
        r'citation_pdf_url"\s+content="([^"]+)"',
        r'content="([^"]+\.pdf[^"]*)"\s+name="citation_pdf_url"',
        r'href="([^"]+\.pdf[^"]*)"',
        r'"pdfUrl"\s*:\s*"([^"]+)"',
    ):
        m = re.search(pat, t, re.I)
        if m:
            return urllib.parse.urljoin(base, m.group(1).replace("\\/", "/"))
    return None


def download(url: str, dest: Path, depth: int = 0) -> tuple[bool, str]:
    if depth > 2:
        return False, "depth"
    code, body, ctype, final = get_bytes(url)
    if code != 200:
        return False, f"http_{code}"
    pb = pdf_bytes(body)
    if pb and len(pb) > 2500:
        dest.write_bytes(pb)
        return True, f"bytes={len(pb)}"
    if b"<" in body[:200]:
        nest = html_pdf_link(body, final or url)
        if nest and nest != url:
            return download(nest, dest, depth + 1)
    return False, f"not_pdf/{ctype[:24]}/{len(body)}"


def resolve(p: dict) -> list[tuple[str, str]]:
    doi = (p.get("doi") or "").strip()
    arxiv = (p.get("arxiv_id") or "").strip()
    cands: list[tuple[str, str]] = []

    if arxiv:
        aid = re.sub(r"v\d+$", "", arxiv)
        cands.append(("arxiv", f"https://arxiv.org/pdf/{aid}.pdf"))

    if doi:
        up = get_json(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={MAILTO}") or {}
        locs = []
        if up.get("best_oa_location"):
            locs.append(up["best_oa_location"])
        locs.extend(up.get("oa_locations") or [])
        for loc in locs:
            for k in ("url_for_pdf", "url"):
                u = loc.get(k)
                if u:
                    cands.append((f"up:{k}", u))

        # publisher heuristics
        if doi.startswith("10.1007/") or doi.startswith("10.1038/"):
            cands.append(("springer", f"https://link.springer.com/content/pdf/{doi}.pdf"))
        if doi.startswith("10.1137/"):
            cands.append(("siam", f"https://epubs.siam.org/doi/pdf/{doi}"))
        if doi.startswith("10.1287/"):
            cands.append(("informs", f"https://pubsonline.informs.org/doi/pdf/{doi}"))

        oa = get_json(
            f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}?mailto={MAILTO}"
        ) or {}
        prim = oa.get("primary_location") or {}
        if prim.get("pdf_url"):
            cands.append(("oa_primary", prim["pdf_url"]))
        oau = (oa.get("open_access") or {}).get("oa_url")
        if oau:
            cands.append(("oa_url", oau))
        for loc in oa.get("locations") or []:
            if loc.get("pdf_url"):
                cands.append(("oa_loc", loc["pdf_url"]))

        s2 = get_json(
            "https://api.semanticscholar.org/graph/v1/paper/DOI:"
            + urllib.parse.quote(doi)
            + "?fields=openAccessPdf,externalIds"
        )
        if s2:
            pdf = (s2.get("openAccessPdf") or {}).get("url")
            if pdf:
                cands.append(("s2", pdf))
            ext = s2.get("externalIds") or {}
            if ext.get("ArXiv"):
                cands.append(("s2arxiv", f"https://arxiv.org/pdf/{ext['ArXiv']}.pdf"))
            pmc = ext.get("PubMedCentral") or ext.get("PMC")
            if pmc:
                pmcid = str(pmc)
                if not pmcid.upper().startswith("PMC"):
                    pmcid = f"PMC{pmcid}"
                cands.append(("pmc", f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf"))

    seen = set()
    out = []
    for s, u in cands:
        u = (u or "").strip()
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        out.append((s, u))
    return out


def process_one(p: dict) -> tuple[str, dict, str]:
    """Return (key, record, logmsg). Does not mutate shared manifest."""
    rank = int(p.get("rank") or 0)
    key = f"r{rank:03d}"

    doi = (p.get("doi") or "").strip()
    if doi:
        dsafe = re.sub(r"[^\w.\-]+", "_", doi)[:40]
        dest = INBOX / f"r{rank:03d}_{dsafe}.pdf"
    else:
        dest = INBOX / f"r{rank:03d}.pdf"
    if len(str(dest)) > 230:
        dest = INBOX / f"r{rank:03d}.pdf"

    # already on disk
    if dest.exists() and dest.stat().st_size > 2500:
        rel = str(dest.relative_to(ROOT)).replace("\\", "/")
        rec = {
            "rank": rank,
            "title": p.get("title"),
            "doi": doi,
            "status": "ok",
            "path": rel,
            "source": "disk_cache",
        }
        return key, rec, f"disk {key}"

    try:
        cands = resolve(p)
        err = ""
    except Exception as e:  # noqa: BLE001
        cands = []
        err = str(e)

    rec = {
        "rank": rank,
        "title": p.get("title"),
        "doi": doi,
        "status": "skip_no_oa",
        "path": None,
        "source": None,
        "n_cand": len(cands),
        "err": err or None,
    }
    if not cands:
        return key, rec, f"skip {key}"

    for src, url in cands:
        ok, msg = download(url, dest)
        if ok:
            rel = str(dest.relative_to(ROOT)).replace("\\", "/")
            rec.update({"status": "ok", "path": rel, "source": src, "detail": msg, "url": url})
            dest.with_suffix(".meta.json").write_text(
                json.dumps(
                    {
                        "rank": rank,
                        "title": p.get("title"),
                        "doi": doi,
                        "year": p.get("year"),
                        "venue": p.get("venue"),
                        "domains": p.get("domains"),
                        "source": src,
                        "url": url,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return key, rec, f"ok {key} {src}"
        time.sleep(0.05)
    rec["status"] = "fail_download"
    return key, rec, f"fail {key} cands={len(cands)}"


def main() -> None:
    papers = json.loads(TOP.read_text(encoding="utf-8"))["papers"]
    man = load_man()
    items = man.setdefault("items", {})

    todo = []
    for p in papers:
        key = f"r{int(p['rank']):03d}"
        prev = items.get(key) or {}
        # terminal states — do not thrash APIs forever
        if prev.get("status") == "ok" and prev.get("path") and (ROOT / prev["path"]).exists():
            continue
        if prev.get("status") in ("skip_no_oa", "fail_download"):
            continue
        existing = list(INBOX.glob(f"r{int(p['rank']):03d}*.pdf"))
        if existing and existing[0].stat().st_size > 2500:
            rel = str(existing[0].relative_to(ROOT)).replace("\\", "/")
            items[key] = {
                "rank": int(p["rank"]),
                "title": p.get("title"),
                "doi": p.get("doi"),
                "status": "ok",
                "path": rel,
                "source": "disk_scan",
            }
            continue
        todo.append(p)

    print(f"todo={len(todo)} already_ok≈{500 - len(todo)} workers={WORKERS}", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(process_one, p) for p in todo]
        for fut in as_completed(futs):
            key, rec, msg = fut.result()
            items[key] = rec
            done += 1
            print(msg, flush=True)
            if done % 15 == 0 or done == len(todo):
                st = {"ok": 0, "skip_no_oa": 0, "fail_download": 0}
                for v in items.values():
                    s = v.get("status")
                    if s in st:
                        st[s] += 1
                man["stats"] = st
                man["pdf_count"] = len(list(INBOX.glob("*.pdf")))
                man["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                save_man(man)
                print("progress", done, "/", len(todo), st, "pdfs", man["pdf_count"], flush=True)

    st = {"ok": 0, "skip_no_oa": 0, "fail_download": 0}
    for v in items.values():
        s = v.get("status")
        if s in st:
            st[s] += 1
    man["stats"] = st
    man["pdf_count"] = len(list(INBOX.glob("*.pdf")))
    man["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_man(man)
    print("DONE", st, "pdfs", man["pdf_count"], flush=True)


if __name__ == "__main__":
    main()
