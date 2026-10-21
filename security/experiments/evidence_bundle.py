"""Create/verify a local evidence recovery ZIP. No network, CAN, or extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def verify(archive):
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("BUNDLE-MANIFEST.json"))
        names = bundle.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest) | {"BUNDLE-MANIFEST.json"}:
            raise ValueError("archive members mismatch")
        for name, record in manifest.items():
            if Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
                raise ValueError("unsafe archive path")
            with bundle.open(name) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != record["sha256"] or bundle.getinfo(name).file_size != record["bytes"]:
                raise ValueError("archive member hash mismatch: " + name)
    return len(manifest)


def create(root, archive):
    root, archive = root.resolve(), archive.resolve()
    files = set()
    for base in (root / "docs", root / "plan", root / "security"):
        for p in base.rglob("*"):
            if not p.is_file() or p.is_symlink() or "__pycache__" in p.parts or ".pytest_cache" in p.parts:
                continue
            evidence = p.is_relative_to(root / "docs/development/experiments") or p.is_relative_to(root / "docs/development/reviews/experiment-evidence-audit-2026-10-04")
            if evidence or p.suffix in {".md", ".py", ".json"} or p.name == "requirements.txt":
                files.add(p)
    manifest = {}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as bundle:
        for p in sorted(files):
            name = p.relative_to(root).as_posix()
            hasher = hashlib.sha256()
            size = 0
            with p.open("rb") as source, bundle.open(name, "w", force_zip64=True) as target:
                while block := source.read(1024 * 1024):
                    hasher.update(block)
                    size += len(block)
                    target.write(block)
            manifest[name] = {"sha256": hasher.hexdigest(), "bytes": size}
        bundle.writestr("BUNDLE-MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    count = verify(archive)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"file_count": count, "archive_bytes": archive.stat().st_size,
              "archive_sha256": digest, "all_member_hashes_verified": True,
              "storage_grade": "LOCAL_RECOVERY_COPY_NOT_OFF_DEVICE_BACKUP",
              "members": manifest}
    archive.with_suffix(archive.suffix + ".manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "members"}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    if bool(args.out) == bool(args.verify):
        parser.error("choose exactly one of --out / --verify")
    if args.verify:
        print("Verified members:", verify(args.verify))
    else:
        if args.out.resolve().is_relative_to((args.root / "docs").resolve()):
            parser.error("archive must be outside docs to avoid self inclusion")
        create(args.root, args.out)


if __name__ == "__main__":
    main()
