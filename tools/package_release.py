#!/usr/bin/env python3
"""Rebuild, test, package, and verify one Rival Empires release ZIP."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import build_pack
import update_checksums
import validate_pack


ROOT = Path(__file__).resolve().parents[1]
VERSION = build_pack.VERSION
OUTPUT = ROOT.parent / f"rtw2_rival_empires_v{VERSION}.zip"
PREFIX = f"rtw2_rival_empires_v{VERSION}"
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


def verify_archive(files: list[Path], output: Path = OUTPUT) -> str:
    expected = expected_archive_names(files)
    with zipfile.ZipFile(output, "r") as archive:
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
    return hashlib.sha256(output.read_bytes()).hexdigest()


def rebuild_release_inputs() -> None:
    settings = build_pack.balanced_settings()
    build_pack.validate_settings(settings)
    build_pack.emit_source(settings, ROOT / "source")

    standalone = build_pack.build_pack(settings)
    module_only = build_pack.build_pack(settings, module_only=True)
    validate_pack.validate_pack_bytes(standalone, module_only=False)
    validate_pack.validate_pack_bytes(module_only, module_only=True)

    standalone_paths = (
        ROOT / "@rtw2_rival_empires_balanced.pack",
        ROOT / "build" / "@rtw2_rival_empires_balanced.pack",
    )
    for path in standalone_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(standalone)
    module_path = (
        ROOT
        / "compatibility"
        / "@rtw2_rival_empires_balanced_module_only.pack"
    )
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_bytes(module_only)
    update_checksums.main()


def build_archive(output: Path = OUTPUT) -> str:
    files = included_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
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
    return verify_archive(files, output)


def run_release_tests() -> None:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tools",
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    configured_lua = os.environ.get("RIVAL_LUA")
    lua = (
        (shutil.which(configured_lua) if configured_lua else None)
        or shutil.which("lua5.1")
        or shutil.which("lua")
        or shutil.which("luajit")
        or shutil.which("fengari")
    )
    if not lua:
        raise RuntimeError(
            "a Lua-compatible executable is required; set RIVAL_LUA if it "
            "is not on PATH"
        )
    subprocess.run(
        [lua, "tools/test_lua_runtime.lua"],
        cwd=ROOT,
        env=environment,
        check=True,
    )


def main() -> int:
    rebuild_release_inputs()
    digest = build_archive()
    run_release_tests()
    digest = verify_archive(included_files())
    print(
        f"built {OUTPUT.name} ({OUTPUT.stat().st_size} bytes, "
        f"sha256 {digest})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
