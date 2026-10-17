# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the wheel-content check of `.github/scripts`.

What CI can show is that a real build passes: `test.yml`'s `check-dist`
job runs the script on every wheel it downloads. What CI cannot show is
that anything *fails* -- a wheel with a second compiled extension in it
is not something a workflow can produce on purpose -- so the archives
here are synthetic, one member planted per rule, and the assertion is
the complaint.

The last two tests ask a different question: whether
`docs/source/package-content-policy.md` states the same policy. A page
beside a script is a second copy of one list, and two copies are one
that can be wrong -- the page saying `.so` is a shared-library suffix
while the script's tuple does not carry it, with nothing to notice.
Those two compare the page against the script's own constants in both
directions, the same way a sibling repository's own
`tests/verify_dist_contents_test.py` does; the parsing helpers below
are copied from there rather than written twice, the two pages having
the same "list stated by the paragraph naming it" shape.

The script is loaded by path, `.github/scripts` being no package, as
`submodule_pin_test.py` loads its own subject.
"""

from __future__ import annotations

import importlib.util
import re
import runpy
import struct
import sys
import zipfile
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "verify_wheel_contents.py"
_PAGE = Path(__file__).parents[1] / "docs" / "source" / "package-content-policy.md"

_VERSION = "0.8.0.5"
_DIST_INFO = f"btclib_secp256k1-{_VERSION}.dist-info"
_SO = "_btclib_secp256k1.cpython-314-darwin.so"
_DYLIB = "libsecp256k1.dylib"

# the smallest static wheel that passes: the package, its typed marker,
# the compiled extension, and the metadata hatchling writes
_PACKAGE = ("btclib_secp256k1/__init__.py", "btclib_secp256k1/py.typed")
_DIST_INFO_MEMBERS = (
    f"{_DIST_INFO}/METADATA",
    f"{_DIST_INFO}/RECORD",
    f"{_DIST_INFO}/WHEEL",
    f"{_DIST_INFO}/licenses/AUTHORS.md",
    f"{_DIST_INFO}/licenses/LICENSE",
    f"{_DIST_INFO}/licenses/secp256k1/COPYING",
    f"{_DIST_INFO}/sboms/btclib_secp256k1.cdx.json",
)


# --- compiled files small enough to write by hand --------------------------
#
# What the hardening check reads is the ELF, Mach-O or PE structure, and
# nothing of the code: so a file here is the headers and tables that
# structure has, and the properties are the parts left in or out.

_CHECKS = ("__stack_chk_fail", "__memcpy_chk")


def elf(  # noqa: PLR0913
    machine: int = 62,
    *,
    imports: tuple[str, ...] = _CHECKS,
    relro: bool = True,
    dynamic: tuple[tuple[int, int], ...] = ((0x6FFFFFFB, 1),),
    feature: int | None = 3,
    other_note: bool = False,
    note_align: int = 8,
    long_name: bool = False,
) -> bytes:
    """Write a 64-bit little-endian ELF with the parts asked for.

    `machine` is `e_machine`, 62 for x86_64 and 183 for aarch64; `imports`
    the undefined dynamic symbols; `dynamic` the `(tag, value)` entries
    before the terminator; `feature` the GNU property value of the
    architecture's feature word, and `None` writes no GNU note at all;
    `other_note` puts a note of another type ahead of it; `note_align` is
    the alignment of the note segment, 4 or 8, which aligns each note's
    descriptor and the next note; `long_name` gives the other note an
    8-byte name.
    """
    kind = {62: 0xC0000002, 183: 0xC0000000}.get(machine, 0)
    dyn = b"".join(struct.pack("<qQ", tag, value) for tag, value in dynamic)
    dyn += struct.pack("<qQ", 0, 0)
    note = b""
    if other_note:
        label = b"ABCDEFG\0" if long_name else b"ABC\0"
        note = struct.pack("<III", len(label), 4, 1) + label
        note += bytes(-len(note) % note_align) + bytes(4)
        note += bytes(-len(note) % note_align)
    if feature is not None:
        note += struct.pack("<III4s", 4, 16, 5, b"GNU\0")
        note += struct.pack("<IIII", kind, 4, feature, 0)
    strtab = b"\0" + b"".join(name.encode() + b"\0" for name in imports)
    symbols = bytes(24)
    position = 1
    for name in imports:
        symbols += struct.pack("<IBBHQQ", position, 0x10, 0, 0, 0, 0)
        position += len(name) + 1
    phdrs = [(2, len(dyn)), (4, len(note))] + ([(0x6474E552, 0)] if relro else [])
    offset = 64 + 56 * len(phdrs)
    layout = {}
    body = b""
    for key, blob in (("dyn", dyn), ("note", note), ("sym", symbols), ("str", strtab)):
        layout[key] = offset + len(body)
        body += blob
    shoff = offset + len(body)
    sizes = {"dyn": len(dyn), "note": len(note)}
    header = b"\x7fELF\x02\x01\x01" + bytes(9)
    header += struct.pack(
        "<HHIQQQIHHHHHH", 3, machine, 1, 0, 64, shoff, 0, 64, 56, len(phdrs), 64, 3, 0
    )
    out = header
    for ptype, _ in phdrs:
        where = {2: "dyn", 4: "note"}.get(ptype)
        out += struct.pack(
            "<IIQQQQQQ",
            ptype,
            0,
            layout[where] if where else 0,
            0,
            0,
            sizes.get(where, 0) if where else 0,
            0,
            note_align if ptype == 4 else 8,
        )
    out += body
    out += bytes(64)
    out += struct.pack(
        "<IIQQQQIIQQ", 0, 11, 0, 0, layout["sym"], len(symbols), 2, 0, 8, 24
    )
    out += struct.pack(
        "<IIQQQQIIQQ", 0, 3, 0, 0, layout["str"], len(strtab), 0, 0, 1, 0
    )
    return out


def macho(
    imports: tuple[str, ...] = ("___stack_chk_fail", "___memcpy_chk"),
    *,
    uuid: bool = False,
) -> bytes:
    """Write a 64-bit little-endian Mach-O with the undefined symbols given.

    `uuid` puts an `LC_UUID` load command ahead of the symbol table's.
    """
    strtab = b"\0" + b"".join(name.encode() + b"\0" for name in imports)
    symbols = b""
    position = 1
    for name in imports:
        symbols += struct.pack("<IBBHQ", position, 0x01, 0, 0, 0)
        position += len(name) + 1
    other = struct.pack("<II16s", 0x1B, 24, bytes(16)) if uuid else b""
    symoff = 32 + len(other) + 24
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x0100000C,
        0,
        6,
        2 if uuid else 1,
        len(other) + 24,
        0,
        0,
    )
    command = struct.pack(
        "<IIIIII", 2, 24, symoff, len(imports), symoff + len(symbols), len(strtab)
    )
    return header + other + command + symbols + strtab


def fat(*slices: bytes) -> bytes:
    """Wrap Mach-O slices in a fat header, big endian."""
    offset = 8 + 20 * len(slices)
    out = struct.pack(">II", 0xCAFEBABE, len(slices))
    body = b""
    for blob in slices:
        out += struct.pack(">IIIII", 0x0100000C, 0, offset + len(body), len(blob), 0)
        body += blob
    return out + body


def pe(  # noqa: PLR0913
    *,
    characteristics: int = 0x4160,
    cookie: int = 1,
    guard: int = 0x500,
    load_config: bool = True,
    other_section: bool = False,
    mapped: bool = True,
) -> bytes:
    """Write a PE32+ with one section holding the load configuration.

    `characteristics` is `DllCharacteristics`: the default is high entropy,
    dynamic base, DEP and control flow guard. `load_config` False leaves
    the directory entry empty; `other_section` puts a section that does not
    hold it ahead of the one that does, and `mapped` False moves that one
    away, so that no section holds the address.
    """
    config = bytearray(152)
    struct.pack_into("<I", config, 0, 152)
    struct.pack_into("<Q", config, 88, cookie)
    struct.pack_into("<I", config, 144, guard)
    dos = bytearray(64)
    dos[:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 64)
    coff = struct.pack(
        "<HHIIIHH", 0x8664, 2 if other_section else 1, 0, 0, 0, 240, 0x2022
    )
    optional = bytearray(240)
    struct.pack_into("<H", optional, 0, 0x20B)
    struct.pack_into("<H", optional, 70, characteristics)
    if load_config:
        struct.pack_into("<II", optional, 112 + 10 * 8, 0x1000, 152)
    section = struct.pack(
        "<8sIIIIIIHHI",
        b".rdata",
        152,
        0x1000 if mapped else 0x3000,
        152,
        0x200,
        0,
        0,
        0,
        0,
        0,
    )
    if other_section:
        section = (
            struct.pack("<8sIIIIIIHHI", b".text", 16, 0x2000, 16, 0x300, 0, 0, 0, 0, 0)
            + section
        )
    head = bytes(dos) + b"PE\0\0" + coff + bytes(optional) + section
    return head.ljust(0x200, b"\0") + bytes(config)


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    """Return the script, imported by path, reading a fake checkout.

    `PACKAGE_DIR` is a module-level constant computed from `__file__` at
    import time, so it is patched after the fact rather than by
    controlling where the script is loaded from -- the script itself
    stays at its real path, which is what the pairing tests below read
    the source of.
    """
    spec = importlib.util.spec_from_file_location("verify_wheel_contents", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    package_dir = tmp_path / "btclib_secp256k1"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "py.typed").write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "PACKAGE_DIR", package_dir)
    return module


def write_wheel(
    path: Path,
    *,
    kind: str = "static",
    extra: tuple[str, ...] = (),
    omit: tuple[str, ...] = (),
    payloads: Mapping[str, bytes] | None = None,
) -> Path:
    """Write a wheel at `path` and return it.

    `kind` selects the tag and the top-level artifact a clean wheel of
    that kind carries; `extra` and `omit` perturb the member set from
    there, and `payloads` writes the bytes it names for a member in place
    of the default: the hardened Mach-O above for a compiled artifact,
    and one byte for any other.
    """
    toplevel = (
        (_SO,) if kind == "static" else ("_btclib_secp256k1.py", "libsecp256k1.dylib")
    )
    members = {*_PACKAGE, *_DIST_INFO_MEMBERS, *toplevel, *extra} - set(omit)

    with zipfile.ZipFile(path, "w") as archive:
        for member in sorted(members):
            data = b"x"
            if member in toplevel and member.endswith((".so", ".dylib", ".pyd")):
                data = macho()
            archive.writestr(member, (payloads or {}).get(member, data))
    return path


def test_a_clean_static_wheel_has_no_complaints(
    script: ModuleType, tmp_path: Path
) -> None:
    """The smallest passing static wheel is accepted."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl"
    )
    assert script.verify_wheel(wheel) == []


def test_a_clean_dynamic_wheel_has_no_complaints(
    script: ModuleType, tmp_path: Path
) -> None:
    """The smallest passing dynamic wheel is accepted."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-py3-none-any.whl", kind="dynamic"
    )
    assert script.verify_wheel(wheel) == []


@pytest.mark.parametrize("member", ["btclib_secp256k1/x.pth", "btclib_secp256k1/x.egg"])
def test_a_forbidden_suffix_under_the_package_is_refused(
    script: ModuleType, tmp_path: Path, member: str
) -> None:
    """Every suffix `FORBIDDEN_SUFFIXES` names is refused."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=(member,),
    )
    complaints = script.verify_wheel(wheel)
    assert any(member in c for c in complaints)


def test_a_forbidden_name_under_the_package_is_refused(
    script: ModuleType, tmp_path: Path
) -> None:
    """`sitecustomize.py` under the package is refused by name."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=("btclib_secp256k1/sitecustomize.py",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("sitecustomize.py" in c for c in complaints)


def test_pycache_is_refused_by_name(script: ModuleType, tmp_path: Path) -> None:
    """A `__pycache__` member fails, whether or not it carries a `.pyc`."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=("btclib_secp256k1/__pycache__/x",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("__pycache__" in c for c in complaints)


def test_a_dist_info_member_outside_the_allowlist_is_refused(
    script: ModuleType, tmp_path: Path
) -> None:
    """`entry_points.txt` under `.dist-info` is not one of its files."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=(f"{_DIST_INFO}/entry_points.txt",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("entry_points.txt" in c for c in complaints)


def test_a_missing_dist_info_file_is_reported(
    script: ModuleType, tmp_path: Path
) -> None:
    """A wheel with no `RECORD` says so."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        omit=(f"{_DIST_INFO}/RECORD",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("RECORD" in c and "missing" in c for c in complaints)


def test_a_missing_vendored_notice_is_reported(
    script: ModuleType, tmp_path: Path
) -> None:
    """A wheel without libsecp256k1's MIT notice says so (#1066)."""
    notice = f"{_DIST_INFO}/licenses/secp256k1/COPYING"
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        omit=(notice,),
    )
    assert script.verify_wheel(wheel) == [f"{wheel.name}: {notice} is missing"]


def test_a_missing_bill_of_materials_is_reported(
    script: ModuleType, tmp_path: Path
) -> None:
    """A wheel without its PEP 770 document says so (#1093)."""
    sbom = f"{_DIST_INFO}/sboms/btclib_secp256k1.cdx.json"
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        omit=(sbom,),
    )
    assert script.verify_wheel(wheel) == [f"{wheel.name}: {sbom} is missing"]


def test_a_second_bill_of_materials_is_refused(
    script: ModuleType, tmp_path: Path
) -> None:
    """A document under `sboms/` that the build does not write is refused."""
    stray = f"{_DIST_INFO}/sboms/another.spdx.json"
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=(stray,),
    )
    complaints = script.verify_wheel(wheel)
    assert complaints == [
        f"{wheel.name}: {stray} is under {_DIST_INFO}/ and is not one of its files"
    ]


def test_a_missing_package_file_is_reported(script: ModuleType, tmp_path: Path) -> None:
    """`py.typed` dropped from the wheel is caught against the checkout."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        omit=("btclib_secp256k1/py.typed",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("py.typed" in c and "missing" in c for c in complaints)


def test_an_untracked_package_file_is_reported(
    script: ModuleType, tmp_path: Path
) -> None:
    """A package member the checkout does not have is caught too."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=("btclib_secp256k1/stray.py",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("stray.py" in c and "not in the checkout" in c for c in complaints)


def test_a_second_static_extension_is_refused(
    script: ModuleType, tmp_path: Path
) -> None:
    """A second top-level compiled extension fails a static wheel."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        extra=("_btclib_secp256k1_second.so",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("exactly one" in c for c in complaints)


def test_a_missing_shared_library_fails_a_dynamic_wheel(
    script: ModuleType, tmp_path: Path
) -> None:
    """The dynamic wheel's shared library is required, not just allowed."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-py3-none-any.whl",
        kind="dynamic",
        omit=("libsecp256k1.dylib",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("dynamic wheel carries" in c for c in complaints)


def test_a_versioned_shared_library_name_is_not_the_expected_one(
    script: ModuleType, tmp_path: Path
) -> None:
    """`libsecp256k1.so.2`, alone, does not satisfy the shared-library rule.

    `scripts/cffi_build.py` itself skips a candidate with more than one
    suffix when it copies the artifact into the wheel -- this is the
    versioned name that skip exists to leave behind, and if one reached
    the wheel regardless it would not read as the shared library the
    dynamic wheel is required to carry.
    """
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-py3-none-any.whl",
        kind="dynamic",
        omit=("libsecp256k1.dylib",),
        extra=("libsecp256k1.so.2",),
    )
    complaints = script.verify_wheel(wheel)
    assert any("dynamic wheel carries" in c for c in complaints)


def test_an_empty_toplevel_artifact_is_reported(
    script: ModuleType, tmp_path: Path
) -> None:
    """A zero-byte extension is a member, and a broken one."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl",
        payloads={_SO: b""},
    )
    complaints = script.verify_wheel(wheel)
    assert any("empty" in c for c in complaints)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("btclib_secp256k1-0.8.0.5-cp314-cp314-macosx_11_0_arm64.whl", "static"),
        ("btclib_secp256k1-0.8.0.5-py3-none-macosx_11_0_arm64.whl", "dynamic"),
    ],
)
def test_wheel_kind_reads_the_python_tag(
    script: ModuleType, name: str, kind: str
) -> None:
    """`py3` in the python-tag position means dynamic, anything else static."""
    assert script.wheel_kind(name) == kind


def test_main_reports_every_argument(script: ModuleType, tmp_path: Path) -> None:
    """`main` checks every wheel named on the line, not just the first."""
    clean = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl"
    )
    broken = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-py3-none-any.whl",
        kind="dynamic",
        omit=("btclib_secp256k1/py.typed",),
    )
    assert script.main(["prog", str(clean), str(broken)]) == 1


def test_main_needs_at_least_one_wheel(script: ModuleType) -> None:
    """No argument is a usage error, not a silent pass."""
    assert script.main(["prog"]) == 2


def test_main_prints_the_all_clear_for_every_clean_wheel(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run with nothing to complain about still says so, once per wheel.

    `test_main_reports_every_argument` above pairs a clean wheel with a
    broken one, so the aggregate complaint list is never empty and this
    branch of `main` never runs there.
    """
    first = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl"
    )
    second = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-py3-none-any.whl", kind="dynamic"
    )

    assert script.main(["prog", str(first), str(second)]) == 0

    out = capsys.readouterr().out
    assert f"{first.name}: carries what it may and no more" in out
    assert f"{second.name}: carries what it may and no more" in out


def test_the_main_guard_runs_the_script_as___main__(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover `if __name__ == "__main__":` without a subprocess.

    This project collects no coverage from a child interpreter, so a
    real subprocess would leave the guard as uncovered as it is
    elsewhere in `.github/scripts`. `runpy.run_path` executes the file
    fresh with `__name__` set to `"__main__"` in this one, against the
    real `src/btclib_secp256k1/` of this checkout, which the fixture
    above does not patch here since nothing constructs this module
    through it.
    """
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl"
    )
    monkeypatch.setattr(sys, "argv", ["prog", str(wheel)])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    # the real package tree, not the fixture's empty one: __init__.py
    # alone is missing every other module this checkout's package has,
    # so this run is expected to complain and only its exit status --
    # nonzero rather than a crash -- is what this test is about
    assert excinfo.value.code == 1


# --- the compiled file is read back for what it was built with -------------

_ARM64_LINUX = f"btclib_secp256k1-{_VERSION}-cp314-cp314-manylinux_2_28_aarch64.whl"
_X86_64_LINUX = f"btclib_secp256k1-{_VERSION}-cp314-cp314-manylinux_2_28_x86_64.whl"
_MUSL = f"btclib_secp256k1-{_VERSION}-cp314-cp314-musllinux_1_2_x86_64.whl"
_MACOS = f"btclib_secp256k1-{_VERSION}-cp314-cp314-macosx_11_0_arm64.whl"
_WINDOWS = f"btclib_secp256k1-{_VERSION}-cp314-cp314-win_amd64.whl"

_NOW = ((0x6FFFFFFB, 1),)


def gaps(
    script: ModuleType, name: str, data: bytes, *, fortify: bool = True
) -> list[str]:
    """Return what `hardening_gaps` says of `data`."""
    result = script.hardening_gaps(name, data, fortify=fortify)
    assert isinstance(result, list)
    return result


def test_a_hardened_elf_has_no_gaps(script: ModuleType) -> None:
    """The control: the properties all in, on both architectures."""
    assert gaps(script, "x.so", elf(62)) == []
    assert gaps(script, "x.so", elf(183, feature=1)) == []
    assert gaps(script, "x.so", elf(183, feature=3)) == []


@pytest.mark.parametrize(
    "dynamic",
    [((0x6FFFFFFB, 1),), ((30, 8),), ((24, 0),), ((30, 0x18), (0x6FFFFFFB, 0))],
)
def test_every_way_to_bind_at_load_is_read(
    script: ModuleType, dynamic: tuple[tuple[int, int], ...]
) -> None:
    """`DT_FLAGS_1` NOW, `DT_FLAGS` BIND_NOW and `DT_BIND_NOW` all count."""
    assert gaps(script, "x.so", elf(dynamic=dynamic)) == []


@pytest.mark.parametrize(
    "data, phrase",
    [
        (elf(imports=("__memcpy_chk",)), "__stack_chk_fail"),
        (elf(imports=("__stack_chk_fail", "memcpy")), "fortified"),
        (elf(relro=False), "relro"),
        (elf(dynamic=()), "-z now"),
        (elf(dynamic=((0x6FFFFFFB, 0x8),)), "-z now"),
        (elf(feature=None), "IBT and SHSTK"),
        (elf(feature=1), "IBT and SHSTK"),
        (elf(feature=2), "IBT and SHSTK"),
        (elf(183, feature=None), "BTI"),
        (elf(183, feature=2), "BTI"),
    ],
)
def test_an_elf_without_a_property_is_told_which(
    script: ModuleType, data: bytes, phrase: str
) -> None:
    """Each property left out is the one phrase named, and no other."""
    result = gaps(script, "x.so", data)
    assert len(result) == 1
    assert phrase in result[0]


def test_an_elf_note_for_the_other_architecture_does_not_count(
    script: ModuleType,
) -> None:
    """The aarch64 property word on an x86_64 file is no CET marking."""
    other = elf(62, feature=3).replace(
        struct.pack("<I", 0xC0000002), struct.pack("<I", 0xC0000000)
    )
    assert any("IBT" in gap for gap in gaps(script, "x.so", other))


def test_musl_is_not_asked_for_a_fortified_function(script: ModuleType) -> None:
    """Musl has none, so the property is waived for it and no other."""
    data = elf(imports=("__stack_chk_fail",))
    assert gaps(script, "x.so", data, fortify=False) == []
    assert gaps(script, "x.so", data, fortify=True) != []


def test_an_elf_of_the_wrong_class_is_refused(script: ModuleType) -> None:
    """A 32-bit file is not read as though it were 64-bit."""
    data = bytearray(elf())
    data[4] = 1
    assert gaps(script, "x.so", bytes(data)) == [
        "is not a 64-bit little-endian ELF file"
    ]


def test_a_hardened_macho_has_no_gaps(script: ModuleType) -> None:
    """The control for the Mach-O cases, thin and fat."""
    assert gaps(script, "x.so", macho()) == []
    assert gaps(script, "x.so", fat(macho(), macho())) == []


@pytest.mark.parametrize(
    "data, phrase",
    [
        (macho(("___memcpy_chk",)), "___stack_chk_fail"),
        (macho(("___stack_chk_fail", "_memcpy")), "fortified"),
        (fat(macho(), macho(("___memcpy_chk",))), "___stack_chk_fail"),
    ],
)
def test_a_macho_without_a_property_is_told_which(
    script: ModuleType, data: bytes, phrase: str
) -> None:
    """A fat file is judged slice by slice."""
    result = gaps(script, "x.so", data)
    assert len(result) == 1
    assert phrase in result[0]


def test_a_defined_macho_symbol_is_not_an_import(script: ModuleType) -> None:
    """Only an undefined external symbol is a call into the C library."""
    data = bytearray(macho())
    # the second symbol's n_type: external, defined in a section
    data[56 + 16 + 4] = 0x0F
    assert any("fortified" in gap for gap in gaps(script, "x.so", bytes(data)))


def test_a_macho_of_the_wrong_magic_is_refused(script: ModuleType) -> None:
    """A fat file wrapping a 32-bit slice is refused, not skipped."""
    data = bytearray(macho())
    data[:4] = b"\xce\xfa\xed\xfe"
    assert gaps(script, "x.so", fat(bytes(data))) == [
        "in its arm64 slice is not a 64-bit little-endian Mach-O file"
    ]


def test_a_msvc_pyd_has_no_gaps(script: ModuleType) -> None:
    """The control for the PE cases."""
    assert gaps(script, "x.pyd", pe()) == []


@pytest.mark.parametrize(
    "data, phrase",
    [
        (pe(characteristics=0x4120), "address space layout randomization"),
        (pe(characteristics=0x4060), "DEP"),
        (pe(characteristics=0x4140), "high entropy"),
        (pe(characteristics=0x0160), "/GUARD:CF"),
        (pe(cookie=0), "/GS"),
        (pe(guard=0x100), "/guard:cf"),
        (pe(guard=0x400), "/guard:cf"),
        (pe(load_config=False), "load configuration"),
    ],
)
def test_a_pyd_without_a_property_is_told_which(
    script: ModuleType, data: bytes, phrase: str
) -> None:
    """Each property left out is the one phrase named."""
    result = gaps(script, "x.pyd", data)
    assert len(result) == 1
    assert phrase in result[0]


def test_a_mingw_dll_is_asked_for_aslr_and_dep_alone(script: ModuleType) -> None:
    """A `.dll` carries no guard and no cookie, and is not asked for them."""
    plain = pe(characteristics=0x0160, cookie=0, guard=0, load_config=False)
    assert gaps(script, "x.dll", plain) == []
    assert gaps(script, "x.dll", pe(characteristics=0x0020)) != []


@pytest.mark.parametrize("data", [elf(), macho(), pe(), fat(macho())])
def test_a_truncated_file_is_a_complaint_not_a_crash(
    script: ModuleType, data: bytes
) -> None:
    """A table past the end of the file is reported, whatever the kind."""
    name = "x.pyd" if data[:2] == b"MZ" else "x.so"
    assert gaps(script, name, data[: len(data) // 2]) == ["is truncated or malformed"]


def test_an_elf_note_of_another_type_is_skipped(script: ModuleType) -> None:
    """The GNU property note is found behind a note of another type."""
    assert gaps(script, "x.so", elf(other_note=True)) == []
    assert any(
        "IBT" in g for g in gaps(script, "x.so", elf(other_note=True, feature=None))
    )


def test_notes_are_padded_by_the_alignment_of_their_segment(
    script: ModuleType,
) -> None:
    """The segment's alignment, 4 or 8, aligns each descriptor and note.

    Padding every descriptor to 8 misreads the second note of a 4-aligned
    segment, and aligning the name to 4 only misreads it behind an 8-byte
    name in an 8-aligned one.
    """
    for align, long_name in ((4, False), (8, False), (8, True)):
        data = elf(other_note=True, note_align=align, long_name=long_name)
        assert gaps(script, "x.so", data) == []
        data = elf(other_note=True, note_align=align, long_name=long_name, feature=None)
        assert any("IBT" in g for g in gaps(script, "x.so", data))


def test_a_macho_load_command_of_another_kind_is_skipped(script: ModuleType) -> None:
    """The symbol table is found behind a load command that is not it."""
    assert gaps(script, "x.so", macho(uuid=True)) == []
    assert gaps(script, "x.so", macho(("_memcpy",), uuid=True)) != []


def test_the_load_config_is_found_in_the_section_that_holds_it(
    script: ModuleType,
) -> None:
    """A section before the right one does not hold the address."""
    assert gaps(script, "x.pyd", pe(other_section=True)) == []
    assert gaps(script, "x.pyd", pe(other_section=True, cookie=0)) != []


def test_a_load_config_no_section_holds_is_a_complaint(script: ModuleType) -> None:
    """An address that no section maps is no load configuration."""
    result = gaps(script, "x.pyd", pe(mapped=False))
    assert len(result) == 1
    assert "load configuration" in result[0]


def test_a_fat_complaint_names_the_architecture(script: ModuleType) -> None:
    """A gap in one slice says which slice."""
    result = gaps(script, "x.so", fat(macho(), macho(("_memcpy",))))
    assert result
    assert all(g.startswith("in its arm64 slice ") for g in result)


def test_a_file_of_no_known_format_is_refused(script: ModuleType) -> None:
    """Bytes that are not a binary are not hardened."""
    assert gaps(script, "x.so", b"x") == ["is not an ELF, Mach-O or PE file"]


def test_the_wheel_reports_the_file_and_the_gap(
    script: ModuleType, tmp_path: Path
) -> None:
    """`verify_wheel` names the member, then what it lacks."""
    wheel = write_wheel(tmp_path / _X86_64_LINUX, payloads={_SO: elf(relro=False)})
    member = "_btclib_secp256k1.cpython-314-darwin.so"
    assert script.verify_wheel(wheel) == [
        f"{wheel.name}: {member} has no read-only relocation segment (relro)"
    ]


def test_a_hardened_linux_wheel_passes(script: ModuleType, tmp_path: Path) -> None:
    """The control for the wheel-level cases."""
    assert (
        script.verify_wheel(
            write_wheel(tmp_path / _X86_64_LINUX, payloads={_SO: elf()})
        )
        == []
    )
    assert (
        script.verify_wheel(
            write_wheel(tmp_path / _ARM64_LINUX, payloads={_SO: elf(183, feature=1)})
        )
        == []
    )


def test_a_musllinux_wheel_is_not_asked_for_a_fortified_call(
    script: ModuleType, tmp_path: Path
) -> None:
    """The tag says musl, and musl has no fortified function."""
    data = elf(imports=("__stack_chk_fail",))
    assert (
        script.verify_wheel(write_wheel(tmp_path / _MUSL, payloads={_SO: data})) == []
    )
    assert script.verify_wheel(
        write_wheel(tmp_path / _X86_64_LINUX, payloads={_SO: data})
    )


@pytest.mark.parametrize(
    "tag, expected",
    [
        ("manylinux_2_28_x86_64", True),
        ("manylinux_2_17_x86_64.manylinux2014_x86_64", True),
        ("manylinux_2_28_aarch64", False),
        ("manylinux_2_34_aarch64", False),
        ("manylinux_2_17_aarch64.manylinux2014_aarch64", False),
        ("musllinux_1_2_x86_64", False),
        ("musllinux_1_2_aarch64", False),
    ],
)
def test_the_marking_is_asked_of_the_images_that_can_carry_it(
    script: ModuleType, tag: str, expected: bool
) -> None:
    """Only a C runtime whose start files carry the marking is asked for it."""
    name = f"btclib_secp256k1-{_VERSION}-cp314-cp314-{tag}.whl"
    assert script.start_files_mark(name) is expected


def test_an_image_that_cannot_mark_is_not_asked_to(
    script: ModuleType, tmp_path: Path
) -> None:
    """An unmarked aarch64 or musl file passes; only the marking is waived."""
    unmarked = elf(183, feature=None)
    wheel = write_wheel(tmp_path / _ARM64_LINUX, payloads={_SO: unmarked})
    assert script.verify_wheel(wheel) == []
    musl = write_wheel(tmp_path / _MUSL, payloads={_SO: elf(feature=None, relro=False)})
    assert len(script.verify_wheel(musl)) == 1
    x86 = write_wheel(tmp_path / _X86_64_LINUX, payloads={_SO: elf(feature=None)})
    assert len(script.verify_wheel(x86)) == 1


def test_an_unhardened_macos_wheel_is_refused(
    script: ModuleType, tmp_path: Path
) -> None:
    """A Mach-O with no stack protector and no fortified call is refused."""
    wheel = write_wheel(tmp_path / _MACOS, payloads={_SO: macho(("_memcpy",))})
    assert len(script.verify_wheel(wheel)) == 2


def test_a_dynamic_wheels_shared_library_is_read_too(
    script: ModuleType, tmp_path: Path
) -> None:
    """The `.dylib` beside the ABI-mode module is the artifact judged."""
    wheel = write_wheel(
        tmp_path / f"btclib_secp256k1-{_VERSION}-py3-none-macosx_11_0_arm64.whl",
        kind="dynamic",
        payloads={_DYLIB: macho(("_memcpy",))},
    )
    complaints = script.verify_wheel(wheel)
    assert len(complaints) == 2
    assert all("libsecp256k1.dylib" in c for c in complaints)


def test_a_windows_wheel_is_read_as_a_pyd(script: ModuleType, tmp_path: Path) -> None:
    """A `.pyd` at the root is read through the PE reader."""
    wheel = write_wheel(
        tmp_path / _WINDOWS,
        extra=("_btclib_secp256k1.pyd",),
        omit=(_SO,),
        payloads={"_btclib_secp256k1.pyd": pe(cookie=0)},
    )
    assert script.verify_wheel(wheel) == [
        f"{wheel.name}: _btclib_secp256k1.pyd has no security cookie (/GS)"
    ]


def test_an_empty_artifact_is_not_also_reported_unhardened(
    script: ModuleType, tmp_path: Path
) -> None:
    """The empty member has its own complaint, and gets only that one."""
    wheel = write_wheel(tmp_path / _MACOS, payloads={_SO: b""})
    assert len(script.verify_wheel(wheel)) == 1


# --- the page states the script's constants, and no more ------------------

_CONSTANT = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")
_CODE_SPAN = re.compile(r"`([^`]+)`")
_REASON = " \N{EM DASH} "


def _rules(text: str) -> list[tuple[set[str], set[str]]]:
    """Pair every rule list of the page with the constants above it.

    A list introduced by a paragraph naming no constant is not a rule
    list and is skipped. Each item contributes the code spans before its
    dash.
    """
    rules: list[tuple[set[str], set[str]]] = []
    paragraph: list[str] = []
    lead: list[str] = []
    items: list[str] = []
    for line in (*text.splitlines(), ""):
        if line.startswith("- "):
            items.append(line[2:])
        elif items and line.startswith("  "):
            items[-1] += " " + line.strip()
        elif items:
            named = set(_CONSTANT.findall(" ".join(lead)))
            if named:
                rules.append((named, _stated(items)))
            items, lead = [], []
        elif line.strip():
            paragraph.append(line)
        elif paragraph:
            lead, paragraph = paragraph, []
    return rules


def _stated(items: list[str]) -> set[str]:
    """Every code span a rule list states, before each item's reason."""
    spans: set[str] = set()
    for item in items:
        rule, dash, _ = item.partition(_REASON)
        assert dash, f"a rule with no reason after it: {item}"
        spans.update(_CODE_SPAN.findall(rule))
    return spans


def test_rules_skips_a_list_whose_paragraph_names_no_constant() -> None:
    """A list is a rule list only once its lead paragraph names one.

    `_rules` is exercised directly, on synthetic text, because
    `docs/source/package-content-policy.md` -- the only text the other
    two tests parse -- never carries a stray list of this shape, and
    planting one there to cover a helper would leave the page
    misstating its own policy.
    """
    text = "Prose that names nothing in backticks.\n\n- one \N{EM DASH} reason\n"
    assert _rules(text) == []


def test_rules_treats_consecutive_blank_lines_as_one_gap() -> None:
    """A blank line with no paragraph pending starts nothing.

    Two blank lines ahead of the first paragraph -- the page's own
    opening never has the second -- are what the first exercises.
    """
    text = "\n\nParagraph naming `A_CONSTANT`.\n\n- `one` \N{EM DASH} reason\n"
    assert _rules(text) == [({"A_CONSTANT"}, {"one"})]


def _policy_constants(
    script: ModuleType,
) -> dict[str, tuple[str, ...] | frozenset[str]]:
    """Every constant of the script that is a list of members."""
    return {
        name: value
        for name, value in vars(script).items()
        if name.isupper() and isinstance(value, (tuple, frozenset))
    }


def test_the_page_states_what_the_script_enforces(script: ModuleType) -> None:
    """Every rule list on the page is its constants, exactly."""
    constants = _policy_constants(script)

    for named, stated in _rules(_PAGE.read_text(encoding="utf-8")):
        expected = {value for name in named for value in constants.get(name, ())}
        assert stated == expected, sorted(named)


def test_the_page_states_every_rule_the_script_has(script: ModuleType) -> None:
    """And no constant is left off the page, or stated twice."""
    named = [
        name for names, _ in _rules(_PAGE.read_text(encoding="utf-8")) for name in names
    ]

    assert sorted(named) == sorted(_policy_constants(script))
