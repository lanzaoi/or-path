#!/usr/bin/env python3
"""L2 release gate: zip integrity + unpack + doctor + seed presence."""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PI_REL = "runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def check_sums(zip_path: Path, sums_path: Path | None) -> None:
    if not sums_path or not sums_path.is_file():
        print("WARN no SHA256SUMS")
        return
    text = sums_path.read_text(encoding="utf-8")
    name = zip_path.name
    m = re.search(rf"^([0-9a-fA-F]{{64}})\s+\*?{re.escape(name)}\s*$", text, re.M)
    if not m:
        raise SystemExit(f"FAIL SHA256SUMS missing {name}")
    expect = m.group(1).lower()
    actual = sha256(zip_path)
    if expect != actual:
        raise SystemExit(f"FAIL checksum {actual} != {expect}")
    print(f"OK checksum {actual[:12]}…")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--sums", type=Path, default=None)
    ap.add_argument("--quick", action="store_true", help="skip setup/doctor subprocess")
    args = ap.parse_args(argv)

    zpath = args.zip.resolve()
    if not zpath.is_file():
        print(f"FAIL missing zip {zpath}")
        return 1

    sums = args.sums
    if sums is None:
        cand = zpath.parent / "SHA256SUMS"
        if cand.is_file():
            sums = cand
    check_sums(zpath, sums)

    banned_hits: list[str] = []
    required = [
        "orpath.bat",
        PI_REL.replace("\\", "/"),
        "demo/seed/live-btube/outputs/live-btube-solution.json",
        "demo/seed/m0/outputs/m0-solution.json",
        "scripts/bootstrap_orpath.py",
        "VERSION",
    ]
    found = {r: False for r in required}

    with zipfile.ZipFile(zpath, "r") as zf:
        names = zf.namelist()
        for n in names:
            low = n.lower().replace("\\", "/")
            if low.endswith("/.env") or low.endswith(".env"):
                banned_hits.append(n)
            if "/.agents/" in low.replace("\\", "/"):
                banned_hits.append(f"agents:{n}")
            for r in required:
                if n.replace("\\", "/").endswith(r) or n.replace("\\", "/").endswith(r.replace("/", "\\")):
                    found[r] = True
                # zip has top folder prefix
                if n.replace("\\", "/").endswith("/" + r):
                    found[r] = True

        for r, ok in found.items():
            if not ok:
                # softer match
                if any(r in x.replace("\\", "/") for x in names):
                    found[r] = True
                    print(f"OK contains …{r}")
                else:
                    print(f"FAIL zip missing {r}")
                    return 1
            else:
                print(f"OK contains {r}")

    if banned_hits:
        print("FAIL banned paths in zip:")
        for b in banned_hits[:20]:
            print(f"  - {b}")
        return 1
    print("OK no .env / .agents in zip")

    if args.quick:
        print("PASS l2_release_gate (--quick)")
        return 0

    with tempfile.TemporaryDirectory(prefix="orpath-l2gate-", ignore_cleanup_errors=True) as td:
        td_path = Path(td)
        print(f"==> unpack to {td_path}")
        ext = ROOT / "scripts" / "extract_zip_longpath.py"
        r = subprocess.run(
            [sys.executable, str(ext), str(zpath), str(td_path / "x")],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            print("FAIL extract")
            return 1
        root = Path((r.stdout or "").strip() or str(td_path / "x"))
        if not root.is_dir():
            tops = list((td_path / "x").iterdir()) if (td_path / "x").is_dir() else []
            root = tops[0] if tops else td_path
        print(f"==> bundle root {root}")
        # Prefer system/venv python for bootstrap
        py = sys.executable
        import os

        env = {
            **os.environ,
            "ORPATH_HOME": str(root),
            "ORPATH_WORKDIR": str(root),
            "PYTHONPATH": "",
            "PYTHONHOME": "",
            "PYTHONNOUSERSITE": "1",
        }
        print("==> bootstrap --skip-npm (node_modules prefilled)")
        boot_py = py
        candidates: list[str] = []
        for which_name in ("python3.12", "python3.11", "python3", "python"):
            w = shutil.which(which_name)
            if w:
                candidates.append(w)
        # Common Windows install locations
        local = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        for base in filter(None, [local, pf, os.environ.get("USERPROFILE", "")]):
            for ver in ("Python312", "Python311", "Python313"):
                cand = str(Path(base) / "Programs" / "Python" / ver / "python.exe")
                if Path(cand).is_file():
                    candidates.append(cand)
                cand2 = str(Path(base) / "AppData" / "Local" / "Programs" / "Python" / ver / "python.exe")
                if Path(cand2).is_file():
                    candidates.append(cand2)
        for cand in candidates:
            try:
                chk = subprocess.run(
                    [cand, "-c", "import sys; v=sys.version_info; raise SystemExit(0 if (3,11)<=(v[0],v[1])<(3,14) else 1)"],
                    capture_output=True,
                )
                if chk.returncode == 0:
                    boot_py = cand
                    break
            except OSError:
                continue
        print(f"  bootstrap python: {boot_py}")
        r = subprocess.run(
            [boot_py, str(root / "scripts" / "bootstrap_orpath.py"), "--skip-npm", "--python", boot_py],
            cwd=str(root),
            env=env,
        )
        if r.returncode != 0:
            print("FAIL bootstrap")
            return 1
        # doctor via venv if created
        vpy = root / ".venv-314" / "Scripts" / "python.exe"
        if not vpy.is_file():
            vpy = root / ".venv-314" / "bin" / "python"
        dpy = str(vpy if vpy.is_file() else py)
        r = subprocess.run([dpy, str(root / "scripts" / "orpath_doctor.py")], cwd=str(root), env=env)
        if r.returncode != 0:
            print("FAIL doctor in unpacked tree")
            return 1
        sol = root / "outputs" / "live-btube-solution.json"
        if not sol.is_file():
            print("FAIL seed not installed to workdir")
            return 1
        print(f"OK seed face {sol}")

        # Watch face must open as ok (not blocked repair loop)
        try:
            sys.path.insert(0, str(root))
            from orpath.paths import apply_workdir  # type: ignore
            from orpath.watch_snapshot import build_snapshot  # type: ignore

            apply_workdir(root)
            snap = build_snapshot(
                slug="live-btube",
                thread_id="live-btube",
                root=root,
                workdir=root,
            )
            st = snap.get("status")
            nst = len(snap.get("stages") or [])
            if st != "ok":
                print(f"FAIL watch snapshot status={st!r} (want ok), stages={nst}")
                return 1
            if nst < 6:
                print(f"FAIL watch snapshot stages too few: {nst}")
                return 1
            print(f"OK watch face status=ok stages={nst}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL watch snapshot check: {exc}")
            return 1

    print("PASS l2_release_gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
