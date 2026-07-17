#!/usr/bin/env python3
"""Create and verify the one deterministic Rival Empires release ZIP."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "rtw2_rival_empires_v0.9.0.zip"
PREFIX = "rtw2_rival_empires_v0.9.0"
FIXED_DATE = (2026, 7, 17, 0, 0, 0)

PACK_FILES = (
    Path("@rtw2_rival_empires_balanced.pack"),
    Path("compatibility/@rtw2_rival_empires_balanced_module_only.pack"),
)
DOCUMENT_FILES = tuple(
    Path(name)
    for name in (
        "BALANCE.md",
        "CHANGELOG.md",
        "COMPATIBILITY.md",
        "LICENSE.txt",
        "MANIFEST.json",
        "QUICK_INSTALL.txt",
        "README.md",
        "SHA256SUMS.txt",
        "TEST_CHECKLIST.md",
    )
)
SOURCE_DIRECTORIES = (Path("source"), Path("tools"))


def included_files() -> list[Path]:
    relative_paths = list(PACK_FILES) + list(DOCUMENT_FILES)
    for directory in SOURCE_DIRECTORIES:
        relative_paths.extend(
            path.relative_to(ROOT)
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.relative_to(ROOT).parts
            and path.suffix != ".pyc"
        )
    if len(relative_paths) != len(set(relative_paths)):
        raise ValueError("duplicate release path")
    missing = [path for path in relative_paths if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(f"missing release files: {missing}")
    return [ROOT / path for path in sorted(relative_paths)]


def expected_archive_names(files: list[Path]) -> list[str]:
    return [
        f"{PREFIX}/{path.relative_to(ROOT).as_posix()}"
        for path in files
    ]


def verify_archive(files: list[Path]) -> str:
    expected = expected_archive_names(files)
    with zipfile.ZipFile(OUTPUT, "r") as archive:
        names = archive.namelist()
        if names != expected:
            raise ValueError("release ZIP contents differ from curated input")
        if len(names) != len(set(names)):
            raise ValueError("release ZIP contains duplicate paths")
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"release ZIP CRC failure: {bad_member}")
        for path, name in zip(files, names, strict=True):
            if archive.read(name) != path.read_bytes():
                raise ValueError(f"release ZIP payload mismatch: {name}")
    return hashlib.sha256(OUTPUT.read_bytes()).hexdigest()


def main() -> int:
    files = included_files()
    with zipfile.ZipFile(
        OUTPUT,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{PREFIX}/{relative}", FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    digest = verify_archive(files)
    print(
        f"built {OUTPUT.name} ({OUTPUT.stat().st_size} bytes, "
        f"sha256 {digest})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
