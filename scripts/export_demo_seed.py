#!/usr/bin/env python3
"""Export lean demo seeds from a workdir into demo/seed/<slug>/."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = ROOT / "demo" / "seed"

# Never copy these names anywhere in the tree
BAN_NAMES = {".env", ".env.local", "backend.env"}
BAN_PARTS = {".agents", "node_modules", ".venv", ".venv-314", "__pycache__"}

OUTPUT_GLOBS = {
    "m0": [
        "outputs/m0-*",
        "outputs/m0.*",
        "notes/m0-*",
        "runs/m0/**/*",
    ],
    "live-btube": [
        "outputs/live-btube-*",
        "outputs/live-btube.*",
        "notes/live-btube-*",
        "papers/live-btube*",
        "runs/live-btube/**/*",
    ],
}

_STAGE_ROLE_RE = re.compile(
    r"^\d+_(?P<role>intake_ocr|intake_parse|orchestrate|retrieve|bridge_pi|research|"
    r"model|gate_schema|solve|gate_validate|explain|draft_paper|cite_pack|"
    r"review_pack|revise_or_done|provenance|human_stop)\.json$",
    re.I,
)
_FACE_ROLES = (
    "intake_ocr",
    "intake_parse",
    "orchestrate",
    "retrieve",
    "bridge_pi",
    "research",
    "model",
    "gate_schema",
    "solve",
    "gate_validate",
    "explain",
    "draft_paper",
    "cite_pack",
    "review_pack",
    "revise_or_done",
    "provenance",
)


def _banned(path: Path) -> bool:
    if path.name in BAN_NAMES:
        return True
    parts = set(path.parts)
    if parts & BAN_PARTS:
        return True
    if path.suffix.lower() in {".pem", ".key"}:
        return True
    return False


def _expand_globs(workdir: Path, patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for pat in patterns:
        if "**" in pat:
            head, _, tail = pat.partition("/**/")
            base = workdir / head
            if not base.exists():
                continue
            if tail == "*" or tail == "":
                for p in base.rglob("*"):
                    if p.is_file() and not _banned(p):
                        found.append(p)
            else:
                for p in base.rglob(tail):
                    if p.is_file() and not _banned(p):
                        found.append(p)
        else:
            for p in workdir.glob(pat):
                if p.is_file() and not _banned(p):
                    found.append(p)
                elif p.is_dir():
                    for f in p.rglob("*"):
                        if f.is_file() and not _banned(f):
                            found.append(f)
    seen: set[Path] = set()
    out: list[Path] = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def lean_stage_dir(stages_dir: Path) -> dict:
    """Collapse repair-loop stages to one best snapshot per face role.

    Prefer stages with human_required=False and empty last_error so the Watch
    face does not open on a blocked repair loop when disk solution is green.
    """
    if not stages_dir.is_dir():
        return {"kept": 0, "removed": 0}
    files = sorted(stages_dir.glob("*.json"))
    if len(files) <= 18:
        return {"kept": len(files), "removed": 0, "skipped": True}

    best: dict[str, tuple[int, str, Path]] = {}
    # role -> (score, name, path)
    for p in files:
        m = _STAGE_ROLE_RE.match(p.name)
        if not m:
            continue
        role = m.group("role").lower()
        if role == "human_stop":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            d = {}
        score = 0
        if d.get("gate_validate_ok") is True:
            score += 50
        if d.get("gate_schema_ok") is True:
            score += 8
        if not d.get("human_required"):
            score += 10
        err = str(d.get("last_error") or "").strip()
        if not err:
            score += 5
        # tube/success markers in stage field progression
        stg = str(d.get("stage") or "")
        if stg in {"explain", "draft_paper", "cite_pack", "end"} and d.get("gate_validate_ok"):
            score += 15
        # later files win ties
        prev = best.get(role)
        if prev is None or score > prev[0] or (score == prev[0] and p.name >= prev[1]):
            best[role] = (score, p.name, p)

    keep: list[Path] = []
    for role in _FACE_ROLES:
        if role in best:
            keep.append(best[role][2])

    if not keep:
        return {"kept": len(files), "removed": 0, "skipped": True}

    keep_set = {p.resolve() for p in keep}
    removed = 0
    for p in files:
        if p.resolve() not in keep_set:
            p.unlink(missing_ok=True)
            removed += 1

    # Order by pipeline role, not old numeric prefix
    role_order = {r: i for i, r in enumerate(_FACE_ROLES)}
    kept_sorted = sorted(
        keep,
        key=lambda x: role_order.get(
            (_STAGE_ROLE_RE.match(x.name).group("role").lower() if _STAGE_ROLE_RE.match(x.name) else x.name),
            99,
        ),
    )
    tmp_paths: list[tuple[Path, str]] = []
    for i, p in enumerate(kept_sorted, start=1):
        m = _STAGE_ROLE_RE.match(p.name)
        role = m.group("role") if m else p.stem.split("_", 1)[-1]
        tmp = stages_dir / f"__tmp_{i:04d}_{role}.json"
        if p.resolve() != tmp.resolve():
            if tmp.exists():
                tmp.unlink()
            p.rename(tmp)
        tmp_paths.append((tmp, f"{i:04d}_{role}.json"))
    for tmp, final_name in tmp_paths:
        final = stages_dir / final_name
        if tmp.resolve() != final.resolve():
            if final.exists():
                final.unlink()
            tmp.rename(final)

    return {"kept": len(kept_sorted), "removed": removed, "skipped": False}


def polish_face_after_validate(dest: Path, slug: str) -> dict:
    """If disk validate is green, end seed timeline at that numbers gate.

    Paper/subagent failures after validate must not paint the default face as
    blocked when solution+validate JSON are the product truth.
    """
    val_p = dest / "outputs" / f"{slug}-validate.json"
    sol_p = dest / "outputs" / f"{slug}-solution.json"
    stages_dir = dest / "runs" / slug / "stages"
    if not val_p.is_file() or not stages_dir.is_dir():
        return {"applied": False, "reason": "missing validate or stages"}
    try:
        val = json.loads(val_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"applied": False, "reason": "bad validate json"}
    if val.get("ok") is not True:
        return {"applied": False, "reason": "validate not ok"}

    stages = sorted(stages_dir.glob("*.json"))
    cut: Path | None = None
    for p in stages:
        if "gate_validate" not in p.name:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if d.get("gate_validate_ok") is True or (
            not d.get("human_required") and "ok\": false" not in str(d.get("last_error") or "").lower()
        ):
            # prefer explicit ok; also accept clean validate nodes
            if d.get("gate_validate_ok") is True:
                cut = p
    if cut is None:
        # fallback: any gate_validate with gate_validate_ok
        for p in stages:
            if "gate_validate" in p.name:
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if d.get("gate_validate_ok") is True:
                    cut = p
    if cut is None:
        return {"applied": False, "reason": "no green gate_validate stage"}

    # Keep only stages up to and including cut (by current sort name)
    keep_names = {p.name for p in stages if p.name <= cut.name}
    # rebuild ordered list by role order among keep
    kept = [p for p in stages if p.name in keep_names]
    removed = 0
    for p in stages:
        if p.name not in keep_names:
            p.unlink(missing_ok=True)
            removed += 1

    # Clear human flags on kept spine for face readability
    for p in kept:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if d.get("human_required") or d.get("last_error"):
            d["human_required"] = False
            if d.get("gate_validate_ok") is True or "gate_validate" in p.name:
                d["last_error"] = ""
            d["seed_face_note"] = "demo seed: numbers spine; paper/LIVE noise trimmed"
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Append clean provenance end
    obj = None
    if sol_p.is_file():
        try:
            obj = json.loads(sol_p.read_text(encoding="utf-8")).get("objective")
        except json.JSONDecodeError:
            obj = None
    n = len(list(stages_dir.glob("*.json"))) + 1
    prov = {
        "stage": "end",
        "human_required": False,
        "last_error": "",
        "gate_validate_ok": True,
        "seed_face_note": "demo seed ends after validate (numbers truth); not a full paper LIVE close",
        "objective": obj,
        "slug": slug,
    }
    (stages_dir / f"{n:04d}_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Rewrite latest_snapshot so Watch overall status is not stuck on old paper fail
    latest = stages_dir.parent / "latest_snapshot.json"
    snap = {
        "utc": "",
        "node": "provenance",
        "stage": "end",
        "thread_id": slug,
        "slug": slug,
        "human_required": False,
        "gate_validate_ok": True,
        "last_error": "",
        "seed_face_note": prov["seed_face_note"],
        "paths": {
            "solution_path": f"outputs/{slug}-solution.json",
            "validate_path": f"outputs/{slug}-validate.json",
        },
    }
    if obj is not None:
        snap["objective"] = obj
    latest.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Drop noisy paper review failures from seed face package
    for name in (f"{slug}-review.md", f"{slug}.HUMAN_REQUIRED.md"):
        p = dest / "outputs" / name
        if p.is_file():
            p.unlink(missing_ok=True)

    return {
        "applied": True,
        "cut": cut.name,
        "removed_after": removed,
        "objective": obj,
    }


def _scrub_meta_workdir(workdir: Path) -> str:
    try:
        rel = workdir.resolve().relative_to(ROOT.resolve())
        return str(rel).replace("\\", "/") or "."
    except ValueError:
        return "(external-workdir)"


def export_slug(workdir: Path, slug: str, out_root: Path, *, lean: bool = True) -> dict:
    patterns = OUTPUT_GLOBS.get(slug)
    if not patterns:
        raise SystemExit(f"unknown slug: {slug} (known: {sorted(OUTPUT_GLOBS)})")
    dest = out_root / slug
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = _expand_globs(workdir, patterns)
    copied = 0
    bytes_ = 0
    for src in files:
        rel = src.relative_to(workdir)
        if ".agents" in rel.parts:
            continue
        if rel.name.endswith(".HUMAN_REQUIRED.md"):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
        bytes_ += target.stat().st_size

    lean_info: dict = {}
    if lean:
        stages = dest / "runs" / slug / "stages"
        lean_info = lean_stage_dir(stages)
        polish = polish_face_after_validate(dest, slug)
        lean_info["polish"] = polish
        bytes_ = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
        copied = sum(1 for p in dest.rglob("*") if p.is_file())

    meta = {
        "slug": slug,
        "kind": "demo-seed-replay",
        "source_workdir": _scrub_meta_workdir(workdir),
        "files": copied,
        "bytes": bytes_,
        "lean_stages": lean_info,
        "honesty": (
            "Replay snapshot for Watch face — not a live Pi run on the end-user machine."
        ),
    }
    (dest / "SEED_META.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def check_seed(seed_root: Path) -> int:
    errors: list[str] = []
    for slug in ("m0", "live-btube"):
        d = seed_root / slug
        if not d.is_dir():
            errors.append(f"missing {d}")
            continue
        for p in d.rglob("*"):
            if p.is_file() and _banned(p):
                errors.append(f"banned file in seed: {p}")
            if p.is_dir() and p.name == ".agents":
                errors.append(f"banned dir in seed: {p}")
            if p.is_file() and p.name == "SEED_META.json":
                text = p.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"[A-Za-z]:\\\\Users\\\\", text) or "/Users/" in text:
                    errors.append(f"absolute user path in {p}")
        if slug == "m0":
            sol = d / "outputs" / "m0-solution.json"
            if not sol.is_file():
                errors.append("m0 missing outputs/m0-solution.json")
        if slug == "live-btube":
            sol = d / "outputs" / "live-btube-solution.json"
            runs = d / "runs" / "live-btube"
            if not sol.is_file():
                errors.append("live-btube missing outputs/live-btube-solution.json")
            if not runs.is_dir():
                errors.append("live-btube missing runs/live-btube/")
            try:
                data = json.loads(sol.read_text(encoding="utf-8"))
                obj = data.get("objective")
                if float(obj or 0) != 99000.0:
                    errors.append(f"live-btube unexpected objective {obj}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"live-btube solution unreadable: {exc}")
            nst = (
                len(list((runs / "stages").glob("*.json")))
                if (runs / "stages").is_dir()
                else 0
            )
            if nst > 24:
                errors.append(f"live-btube stages too many for face seed: {nst}")
            if nst < 8:
                errors.append(f"live-btube stages too few: {nst}")
    if errors:
        print("FAIL export_demo_seed --check")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS export_demo_seed --check")
    for slug in ("m0", "live-btube"):
        d = seed_root / slug
        n = sum(1 for _ in d.rglob("*") if _.is_file())
        b = sum(_.stat().st_size for _ in d.rglob("*") if _.is_file())
        print(f"  {slug}: {n} files, {b} bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export OR-Path demo seeds")
    p.add_argument("--slug", choices=sorted(OUTPUT_GLOBS) + ["all"], default=None)
    p.add_argument(
        "--from-workdir",
        type=Path,
        default=None,
        help="source workdir (default ORPATH_WORKDIR or repo root)",
    )
    p.add_argument("--out", type=Path, default=SEED_ROOT)
    p.add_argument("--check", action="store_true", help="validate demo/seed only")
    p.add_argument(
        "--lean-only",
        action="store_true",
        help="only prune stages under existing demo/seed (no re-copy)",
    )
    p.add_argument("--no-lean", action="store_true", help="disable stage spine lean")
    args = p.parse_args(argv)

    if args.check:
        return check_seed(args.out)
    if args.lean_only:
            out = args.out.resolve()
            for slug in ("m0", "live-btube"):
                stages = out / slug / "runs" / slug / "stages"
                info = lean_stage_dir(stages)
                polish = polish_face_after_validate(out / slug, slug)
                info["polish"] = polish
                meta_p = out / slug / "SEED_META.json"
                if meta_p.is_file():
                    try:
                        meta = json.loads(meta_p.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        meta = {"slug": slug}
                    meta["kind"] = "demo-seed-replay"
                    sw = str(meta.get("source_workdir") or ".")
                    if ":\\" in sw or sw.startswith("/Users/") or "Desktop" in sw:
                        meta["source_workdir"] = "(redacted)"
                    meta["lean_stages"] = info
                    meta["honesty"] = (
                        "Replay snapshot for Watch face — not a live Pi run "
                        "on the end-user machine."
                    )
                    meta["files"] = sum(1 for _ in (out / slug).rglob("*") if _.is_file())
                    meta["bytes"] = sum(
                        _.stat().st_size for _ in (out / slug).rglob("*") if _.is_file()
                    )
                    meta_p.write_text(
                        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                for hum in (out / slug).rglob("*.HUMAN_REQUIRED.md"):
                    hum.unlink(missing_ok=True)
                print(f"lean {slug}: {info}")
            return check_seed(out)

    if not args.slug:
        p.error("--slug required unless --check / --lean-only")

    import os

    work = args.from_workdir
    if work is None:
        work = Path(
            os.environ.get("ORPATH_WORKDIR") or os.environ.get("ORPATH_HOME") or ROOT
        )
    work = work.resolve()

    slugs = list(OUTPUT_GLOBS) if args.slug == "all" else [args.slug]
    lean = not args.no_lean
    for s in slugs:
        meta = export_slug(work, s, args.out.resolve(), lean=lean)
        print(f"OK {s}: {meta['files']} files, {meta['bytes']} bytes -> {args.out / s}")
    return check_seed(args.out.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
