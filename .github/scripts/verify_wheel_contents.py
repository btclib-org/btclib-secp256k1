# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

r"""Check a built wheel against an allowlist of its members.

`twine check`, `check-wheel-contents` and `pyroma` read the *metadata* of
a wheel: whether it is syntactically valid, whether the long description
renders, whether the classifiers a package should declare are there.
None of them reads every member, and what is in the archive is what a
user installs.

`check-wheel-contents --package btclib_secp256k1`, the same option a
sibling repository's own `pyproject.toml` configures for its own
package, is the closest built-in answer, and it does not fit here: it
diffs the wheel's whole library against the one named package tree,
and this package's wheel is not one package tree. Every wheel this
project ships also carries a compiled artifact at the wheel's own
root, beside `btclib_secp256k1/` rather than inside it -- the
extension module for a static wheel, that module's ABI-mode source and
the shared `libsecp256k1` for a dynamic one -- which `--package` reports
as "files not in package tree" whether or not they are the ones this
project intends. `[tool.check-wheel-contents]` keeps `ignore = ["W003",
"W009"]` for the same reason, on the dynamic wheel specifically: the
checks those codes name are about a *non-package* file at the top level,
which for this project's dynamic wheel is not a mistake but the shared
library.

The questions, and what answers them:

**Which top-level artifact must be there.** A wheel's tag says whether it
is static (an `infer_tag`ed `cpNN-...`, one compiled extension) or
dynamic (`py3-none-<platform>`, an ABI-mode module and the shared library
beside it) -- `scripts/hatch_build.py`'s own distinction, and this reads
the same tag it writes. Which artifacts a wheel of that kind must carry,
and refusing an extra one -- a stray file that is not part of
`btclib_secp256k1/` and not one of them -- is what `--package` cannot
phrase without also refusing the artifact that belongs.

**Whether the artifact is really there**, and not a zero-byte member a
half-finished build step left behind: `scripts/cffi_build.py` raises when
it cannot find one to copy, not when it copies an empty one, so an empty
file is a shape that check has no report for. `toplevel_reason` below
checks the kind-appropriate artifact for size as well as presence, which
none of `check-wheel-contents`'s codes do for any member.

**Whether `btclib_secp256k1/` itself is complete.** Everything under
that directory in the wheel has to be everything the checkout has under
it -- source, `py.typed`, nothing more and nothing less -- which is
`--package`'s own question, asked here by hand rather than through a
flag that would also judge the sibling artifact.

**Whether the compiled artifact is hardened.** The extension of a static
wheel and the shared library of a dynamic one are read back for the
properties `scripts/cffi_build.py` builds them with. They are read from
the ELF, Mach-O or PE file itself, with no tool beyond the standard
library, so the check runs on whichever runner holds the wheels. Which
property each platform has to carry is `hardening_gaps` below.

The sdist is not this script's subject. A sibling repository's own
script checks it because `MANIFEST.in` there is an *include* list -- a
file the tree gains and MANIFEST.in does not name is a file the sdist
silently drops, which is the failure this whole class of check exists
for.
`[tool.hatch.build.targets.sdist] exclude` here is the opposite shape: a
file the tree gains ships by default, and has to be named to be left
out, so the failure mode is an sdist too wide rather than one silently
narrow. What that leaves unchecked -- an exclude pattern that lists a
file this build still needs -- is a build failure, not a silent gap,
which is a different question with a different check to answer it.

Run it against one built wheel:

    uv run --no-project --python 3.15 \\
        .github/scripts/verify_wheel_contents.py dist/*.whl

`test.yml`'s `check-dist` job runs it on every wheel it downloads --
`build-cibuildwheel`, `build-dynamic` and `build-windows` between them --
which are the artifacts `release.yml`'s own `test` job produces and the
publish jobs upload: one build, checked and shipped, so this judges the
files this project actually publishes rather than a copy of them.
"""

from __future__ import annotations

import re
import struct
import sys
import zipfile
from pathlib import Path

# the package this repository ships, read fresh from the checkout rather
# than hard-coded: a module added to it is a module the next wheel has to
# carry, and a copy of the file list here would drift the day one is
# added or removed without anybody editing this script to match
PACKAGE_DIR = Path(__file__).parents[2] / "src" / "btclib_secp256k1"

# no member of this wheel carries any of these, whichever top-level
# artifact the kind below admits: a `.pth` executes at interpreter
# startup, before the first import; a `.pyc` is a compiled module nobody
# reviewed; an archive inside an archive is a second package installing
# with the first. Checked against `btclib_secp256k1/` and the
# top-level artifact -- not against `.dist-info`, which is already
# validated member by member, against its own allowlist, above
FORBIDDEN_SUFFIXES = (".egg", ".pth", ".pyc", ".tar.gz", ".whl", ".zip")
FORBIDDEN_NAMES = ("sitecustomize.py", "usercustomize.py")

# what hatchling writes into `.dist-info`, and no more. No
# `top_level.txt`: that is a setuptools file, and this build backend is
# hatchling
WHEEL_METADATA_FILES = frozenset({"METADATA", "RECORD", "WHEEL"})
# `license-files` in pyproject.toml, copied into `licenses/` verbatim and
# at the path each has in the checkout; a missing one is a complaint like
# any other missing member, which is what keeps a build change from
# dropping the vendored library's notice unnoticed
WHEEL_LICENSE_FILES = frozenset({"AUTHORS.md", "LICENSE", "secp256k1/COPYING"})
# the PEP 770 bill of materials scripts/hatch_build.py hands hatchling,
# under `sboms/`, named by .github/scripts/generate_sbom.py's
# `write_wheel_sbom`. Required: every wheel this checks is built from a
# checkout, which is where the hook writes one
WHEEL_SBOM_FILES = frozenset({"btclib_secp256k1.cdx.json"})

# suffixes a compiled extension module carries, keyed by platform: cffi's
# static path compiles one of these, named `_btclib_secp256k1` with an
# ABI tag before the suffix on POSIX (cffi's own convention) and without
# one on Windows -- `scripts/cffi_build.py`'s MSVC path names the
# extension `_btclib_secp256k1.pyd` outright
EXTENSION_SUFFIXES = (".so", ".pyd")
# the shared library a dynamic wheel carries beside the ABI-mode module,
# by the platform suffix `shared_library_extension` in cffi_build.py
# names for it. No version suffix: the same function skips a candidate
# with more than one, which is the symlink chain's own name and not the
# file CMake just built
SHARED_LIBRARY_SUFFIXES = (".dll", ".dylib", ".so")


# what the readers below look for. ELF: the program header and dynamic
# section tags that mean "bind at load" and "relocations read-only", and
# the GNU property bits CET and BTI are recorded in
_PT_DYNAMIC = 2
_PT_NOTE = 4
_PT_GNU_PROPERTY = 0x6474E553
_PT_GNU_RELRO = 0x6474E552
_DT_BIND_NOW = 24
_DT_FLAGS = 30
_DT_FLAGS_1 = 0x6FFFFFFB
_DF_BIND_NOW = 0x8
_DF_1_NOW = 0x1
_SHT_DYNSYM = 11
_NT_GNU_PROPERTY_TYPE_0 = 5
_GNU_PROPERTY_AARCH64_FEATURE_1_AND = 0xC0000000
_GNU_PROPERTY_X86_FEATURE_1_AND = 0xC0000002
_AARCH64_FEATURE_1_BTI = 0x1
_X86_FEATURE_1_IBT = 0x1
_X86_FEATURE_1_SHSTK = 0x2
_EM_X86_64 = 62
_EM_AARCH64 = 183
# Mach-O: the load command that carries the symbol table, and the fat
# header magic (big endian) that wraps one slice per architecture
_LC_SYMTAB = 2
_MACHO_MAGIC_64 = b"\xcf\xfa\xed\xfe"
_FAT_MAGIC = b"\xca\xfe\xba\xbe"
_MACHO_ARCHITECTURES = {0x01000007: "x86_64", 0x0100000C: "arm64"}
# PE: DllCharacteristics bits, and the guard flags of the load
# configuration directory
_PE_HIGH_ENTROPY_VA = 0x0020
_PE_DYNAMIC_BASE = 0x0040
_PE_NX_COMPAT = 0x0100
_PE_GUARD_CF = 0x4000
_PE_GUARD_CF_INSTRUMENTED = 0x100
_PE_GUARD_CF_FUNCTION_TABLE_PRESENT = 0x400
# the PE32+ optional header magic, and where the 64-bit load configuration
# directory keeps the security cookie, the guard flags and its own end
_PE_OPTIONAL_MAGIC_64 = 0x20B
_PE_SECURITY_COOKIE = 88
_PE_GUARD_FLAGS = 144
_PE_LOAD_CONFIG_SIZE = 148
# a fortified libc function: `__memcpy_chk`, `___memcpy_chk` on macOS
_FORTIFIED = re.compile(r"^_?__\w+_chk$")


def _binds_now(tag: int, value: int) -> bool:
    """Say whether one entry of an ELF dynamic section asks to bind at load."""
    return (
        tag == _DT_BIND_NOW
        or (tag == _DT_FLAGS and value & _DF_BIND_NOW != 0)
        or (tag == _DT_FLAGS_1 and value & _DF_1_NOW != 0)
    )


def _elf_imports(data: bytes, shoff: int, shentsize: int, shnum: int) -> set[str]:
    """Return the names of the undefined dynamic symbols of an ELF file."""
    imports = set()
    for i in range(shnum):
        _, kind, _, _, offset, size, link, _, _, entsize = struct.unpack_from(
            "<IIQQQQIIQQ", data, shoff + i * shentsize
        )
        if kind != _SHT_DYNSYM:
            continue
        strtab = struct.unpack_from("<QQ", data, shoff + link * shentsize + 24)[0]
        for index in range(size // entsize):
            name, _, _, shndx = struct.unpack_from(
                "<IBBH", data, offset + index * entsize
            )
            if shndx == 0 and name:
                end = data.index(b"\0", strtab + name)
                imports.add(data[strtab + name : end].decode("ascii", "replace"))
    return imports


def _elf_gaps(data: bytes, *, fortify: bool, marked: bool) -> list[str]:
    """Return the hardening an ELF file lacks."""
    if data[4:6] != b"\x02\x01":
        return ["is not a 64-bit little-endian ELF file"]
    machine = struct.unpack_from("<H", data, 18)[0]
    phoff, shoff = struct.unpack_from("<QQ", data, 32)
    phentsize, phnum = struct.unpack_from("<HH", data, 54)
    shentsize, shnum = struct.unpack_from("<HH", data, 58)
    segments = [
        struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize)
        for i in range(phnum)
    ]
    gaps = []

    if _PT_GNU_RELRO not in {segment[0] for segment in segments}:
        gaps.append("has no read-only relocation segment (relro)")
    if not any(
        _binds_now(tag, value)
        for kind, _, offset, _, _, filesz, _, _ in segments
        if kind == _PT_DYNAMIC
        for tag, value in struct.iter_unpack("<qQ", data[offset : offset + filesz])
    ):
        gaps.append("is not linked to bind at load (-z now)")

    imports = _elf_imports(data, shoff, shentsize, shnum)
    if "__stack_chk_fail" not in imports:
        gaps.append("does not call __stack_chk_fail (-fstack-protector-strong)")
    if fortify and not any(_FORTIFIED.match(name) for name in imports):
        gaps.append("calls no fortified function (-D_FORTIFY_SOURCE)")

    if marked:
        features = _gnu_features(data, segments, machine)
        cet = _X86_FEATURE_1_IBT | _X86_FEATURE_1_SHSTK
        if machine == _EM_X86_64 and features & cet != cet:
            gaps.append("is not marked for IBT and SHSTK (-fcf-protection=full)")
        if machine == _EM_AARCH64 and features & _AARCH64_FEATURE_1_BTI == 0:
            gaps.append("is not marked for BTI (-mbranch-protection)")
    return gaps


def _gnu_features(data: bytes, segments: list[tuple[int, ...]], machine: int) -> int:
    """Return the CET or BTI bits of the GNU property notes, 0 if none."""
    wanted = {
        _EM_X86_64: _GNU_PROPERTY_X86_FEATURE_1_AND,
        _EM_AARCH64: _GNU_PROPERTY_AARCH64_FEATURE_1_AND,
    }.get(machine)
    for segment in segments:
        if segment[0] not in {_PT_NOTE, _PT_GNU_PROPERTY}:
            continue
        position, end = segment[2], segment[2] + segment[5]
        # the segment's alignment, 4 or 8, aligns each note's descriptor
        # and the next note (the ELF gABI); a property's own data is
        # padded to 8
        pad = 8 if segment[7] == 8 else 4
        while position + 12 <= end:
            namesz, descsz, kind = struct.unpack_from("<III", data, position)
            body = position + (12 + namesz + pad - 1) // pad * pad
            if kind == _NT_GNU_PROPERTY_TYPE_0:
                cursor = body
                while cursor + 8 <= body + descsz:
                    ptype, datasz = struct.unpack_from("<II", data, cursor)
                    if ptype == wanted and datasz >= 4:
                        return int(struct.unpack_from("<I", data, cursor + 8)[0])
                    cursor += 8 + (datasz + 7) // 8 * 8
            position = body + (descsz + pad - 1) // pad * pad
    return 0


def _macho_slice_gaps(data: bytes, *, fortify: bool) -> list[str]:
    """Return the hardening one Mach-O slice lacks."""
    if data[:4] != _MACHO_MAGIC_64:
        return ["is not a 64-bit little-endian Mach-O file"]
    ncmds = struct.unpack_from("<I", data, 16)[0]
    position = 32
    imports = set()
    for _ in range(ncmds):
        command, size = struct.unpack_from("<II", data, position)
        if command == _LC_SYMTAB:
            symoff, nsyms, stroff, _ = struct.unpack_from("<IIII", data, position + 8)
            for index in range(nsyms):
                strx, kind = struct.unpack_from("<IB", data, symoff + index * 16)
                # an external symbol with no section: an import
                if kind & 0x0F == 0x01:
                    end = data.index(b"\0", stroff + strx)
                    imports.add(data[stroff + strx : end].decode("ascii", "replace"))
        position += size
    gaps = []
    if "___stack_chk_fail" not in imports:
        gaps.append("does not call ___stack_chk_fail (-fstack-protector-strong)")
    if fortify and not any(_FORTIFIED.match(name) for name in imports):
        gaps.append("calls no fortified function (-D_FORTIFY_SOURCE)")
    return gaps


def _macho_gaps(data: bytes, *, fortify: bool) -> list[str]:
    """Return the hardening a Mach-O file, fat or thin, lacks."""
    if data[:4] != _FAT_MAGIC:
        return _macho_slice_gaps(data, fortify=fortify)
    gaps = []
    count = struct.unpack_from(">I", data, 4)[0]
    for index in range(count):
        cputype, _, offset, size = struct.unpack_from(">IIII", data, 8 + index * 20)
        arch = _MACHO_ARCHITECTURES.get(cputype, hex(cputype))
        gaps += [
            f"in its {arch} slice {gap}"
            for gap in _macho_slice_gaps(data[offset : offset + size], fortify=fortify)
        ]
    return gaps


def _pe_load_config(data: bytes, pe: int) -> int | None:
    """Return the file offset of a PE32+ load configuration, or None.

    `pe` is the offset of the `PE` signature. The directory entry holds a
    relative address, which a section of the file maps to an offset.
    """
    sections = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    rva, size = struct.unpack_from("<II", data, optional + 112 + 10 * 8)
    if size < _PE_LOAD_CONFIG_SIZE:
        return None
    for i in range(sections):
        _, vsize, vaddr, rawsize, rawptr = struct.unpack_from(
            "<8sIIII", data, optional + optional_size + i * 40
        )
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return int(rawptr + rva - vaddr)
    return None


def _pe_gaps(data: bytes, *, msvc: bool) -> list[str]:
    """Return the hardening a PE file lacks.

    `msvc` is whether the file is one MSVC linked: it adds control flow
    guard and the security cookie to the address space layout
    randomization and DEP that every PE needs.
    """
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    optional = pe + 24
    plus = struct.unpack_from("<H", data, optional)[0] == _PE_OPTIONAL_MAGIC_64
    characteristics = struct.unpack_from("<H", data, optional + 70)[0]
    gaps = []
    if characteristics & _PE_DYNAMIC_BASE == 0:
        gaps.append("is not linked for address space layout randomization")
    if characteristics & _PE_NX_COMPAT == 0:
        gaps.append("is not marked DEP compatible")
    if plus and characteristics & _PE_HIGH_ENTROPY_VA == 0:
        gaps.append("is not marked for high entropy address space layout")
    if not msvc:
        return gaps
    if characteristics & _PE_GUARD_CF == 0:
        gaps.append("is not linked with control flow guard (/GUARD:CF)")

    config = _pe_load_config(data, pe) if plus else None
    if config is None:
        gaps.append("has no load configuration with a security cookie and guard flags")
        return gaps
    if struct.unpack_from("<Q", data, config + _PE_SECURITY_COOKIE)[0] == 0:
        gaps.append("has no security cookie (/GS)")
    guard = struct.unpack_from("<I", data, config + _PE_GUARD_FLAGS)[0]
    wanted = _PE_GUARD_CF_INSTRUMENTED | _PE_GUARD_CF_FUNCTION_TABLE_PRESENT
    if guard & wanted != wanted:
        gaps.append("has no control flow guard function table (/guard:cf)")
    return gaps


def hardening_gaps(
    name: str, data: bytes, *, fortify: bool = True, marked: bool = True
) -> list[str]:
    """Return the hardening the compiled file `name` lacks, as phrases.

    The properties each platform has to carry are listed in
    `docs/source/package-content-policy.md`, under *What the compiled
    file has to be built with*.

    Args:
        name: the member's name, the suffix of which says a PE from MSVC
            from one from mingw-w64.
        data: the member's bytes.
        fortify: whether a fortified libc function has to be called,
            which musl, with no such function, cannot do.
        marked: whether an ELF file has to carry the CET or BTI marking,
            which the linker writes only if every input does, the C
            runtime's start files among them. `start_files_mark` says
            which wheels have those.

    Returns:
        One phrase per property missing, empty for a hardened file.
    """
    try:
        if data[:4] == b"\x7fELF":
            return _elf_gaps(data, fortify=fortify, marked=marked)
        if data[:4] in {_MACHO_MAGIC_64, _FAT_MAGIC}:
            return _macho_gaps(data, fortify=fortify)
        if data[:2] == b"MZ":
            return _pe_gaps(data, msvc=name.endswith(".pyd"))
    except (struct.error, ValueError):
        # a header or table that runs past the end of the file
        return ["is truncated or malformed"]
    return ["is not an ELF, Mach-O or PE file"]


def start_files_mark(wheel_name: str) -> bool:
    """Say whether the C runtime a wheel was linked against marks CET or BTI.

    The linker writes the marking into a file only if every input carries
    it, and the start files of the image link in with the rest. Measured
    on the `crti.o` of the images `pyproject.toml` pins, with
    `llvm-readelf -n`: AlmaLinux 8's glibc 2.28 marks IBT and SHSTK on
    x86_64 and nothing on aarch64; the musllinux images' musl marks
    neither architecture. A file linked against them cannot carry what its
    own objects do, and forcing the marking (`-z force-bti`) would claim
    it for an `_init` that has no `bti` instruction. A pinned image that
    does mark aarch64 is one more case here.

    Args:
        wheel_name: the wheel's file name, the platform tag of which
            names the C runtime.

    Returns:
        Whether an ELF file in the wheel has to carry the marking.
    """
    tag = wheel_name[: -len(".whl")].rsplit("-", 1)[-1]
    return "musllinux" not in tag and "aarch64" not in tag


def wheel_kind(name: str) -> str:
    """Return "static" or "dynamic" for the wheel named `name`.

    The python tag is the second-to-last dash-separated field before the
    platform tag in a three-tag wheel name, and it is what
    scripts/hatch_build.py itself sets: `py3-none-<platform>` for a
    dynamic wheel, an inferred `cpNN-cpNN-<platform>` for a static one.
    Reading the filename rather than the `WHEEL` file's Root-Is-Purelib
    line: that line is `false` for both kinds here, since the build hook
    clears `pure_python` before either is tagged.
    """
    tags = name[: -len(".whl")].split("-")
    return "dynamic" if tags[-3] == "py3" else "static"


def toplevel_reason(members: set[str], kind: str) -> str | None:
    """Say why the wheel's top-level artifact does not match `kind`.

    Returns None if it does. `members` is every member outside
    `btclib_secp256k1/` and the `.dist-info` directory.
    """
    if kind == "static":
        matches = [
            m
            for m in members
            if m.startswith("_btclib_secp256k1") and m.endswith(EXTENSION_SUFFIXES)
        ]
        rest = members - set(matches)
        if len(matches) != 1 or rest:
            return (
                "a static wheel carries exactly one _btclib_secp256k1 extension "
                f"module and nothing else at its root; found {sorted(members)}"
            )
        return None
    py_module = "_btclib_secp256k1.py"
    libs = [
        m
        for m in members
        if m.startswith("libsecp256k1") and m.endswith(SHARED_LIBRARY_SUFFIXES)
    ]
    rest = members - {py_module, *libs}
    if py_module not in members or len(libs) != 1 or rest:
        return (
            "a dynamic wheel carries _btclib_secp256k1.py and one "
            f"libsecp256k1 shared library and nothing else at its root; "
            f"found {sorted(members)}"
        )
    return None


def forbidden_reason(path: str) -> str | None:
    """Say why this member may never be in the wheel, or None."""
    name = path.rsplit("/", 1)[-1]
    if name in FORBIDDEN_NAMES:
        return f"is {name}, which Python imports at startup"
    for suffix in FORBIDDEN_SUFFIXES:
        if path.endswith(suffix):
            return f"carries the forbidden suffix {suffix}"
    if "__pycache__" in path.split("/"):
        return "is under __pycache__"
    return None


def package_payload_complaints(members: set[str]) -> list[str]:
    """Diff the wheel's `btclib_secp256k1/` against this checkout's.

    What `check-wheel-contents --package btclib_secp256k1` would report,
    asked directly instead: every check against the checkout beside this
    tree, and so every complaint this function returns, applies equally
    to a wheel judged in the sdist-install jobs, which have no compiled
    artifact for `toplevel_reason` to be right or wrong about.
    """
    on_disk = {
        f"btclib_secp256k1/{path.relative_to(PACKAGE_DIR)}"
        for path in PACKAGE_DIR.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    missing = on_disk - members
    extra = members - on_disk
    complaints = [f"btclib_secp256k1/ is missing {name}" for name in sorted(missing)]
    complaints += [
        f"wheel carries {name}, not in the checkout" for name in sorted(extra)
    ]
    return complaints


def compiled_names(members: set[str]) -> list[str]:
    """Return the members at the wheel's root that are compiled files.

    These are the only ones the hardening check reads; a member of
    another name at the root is refused by `toplevel_reason`.
    """
    return sorted(
        name
        for name in members
        if "/" not in name
        and name.endswith((*EXTENSION_SUFFIXES, *SHARED_LIBRARY_SUFFIXES))
    )


def hardening_complaints(wheel_name: str, compiled: dict[str, bytes]) -> list[str]:
    """Return what the compiled files of the wheel `wheel_name` lack.

    An empty file has its own complaint and is not read.
    """
    complaints = []
    for name, data in compiled.items():
        if data:
            # musl has no fortified functions to call
            gaps = hardening_gaps(
                name,
                data,
                fortify="musllinux" not in wheel_name,
                marked=start_files_mark(wheel_name),
            )
            complaints += [f"{name} {gap}" for gap in gaps]
    return complaints


def verify_wheel(wheel: Path) -> list[str]:
    """Return every complaint about the wheel at `wheel`."""
    kind = wheel_kind(wheel.name)
    distribution, version = wheel.name.split("-")[:2]
    dist_info = f"{distribution}-{version}.dist-info"

    with zipfile.ZipFile(wheel) as archive:
        infos = [info for info in archive.infolist() if not info.filename.endswith("/")]
        sizes = {info.filename: info.file_size for info in infos}
        compiled = {name: archive.read(name) for name in compiled_names(set(sizes))}
    members = set(sizes)

    complaints = []

    dist_info_members = {m for m in members if m.startswith(f"{dist_info}/")}
    package_members = {m for m in members if m.startswith("btclib_secp256k1/")}
    toplevel_members = members - dist_info_members - package_members

    for name in dist_info_members:
        relative = name[len(dist_info) + 1 :]
        if relative in WHEEL_METADATA_FILES:
            continue
        if relative.startswith("sboms/") and relative[len("sboms/") :] in (
            WHEEL_SBOM_FILES
        ):
            continue
        if relative.startswith("licenses/") and relative[len("licenses/") :] in (
            WHEEL_LICENSE_FILES
        ):
            continue
        complaints.append(f"{name} is under {dist_info}/ and is not one of its files")
    required_dist_info = (
        WHEEL_METADATA_FILES
        | {f"licenses/{name}" for name in WHEEL_LICENSE_FILES}
        | {f"sboms/{name}" for name in WHEEL_SBOM_FILES}
    )
    complaints += [
        f"{dist_info}/{name} is missing"
        for name in sorted(
            required_dist_info - {m[len(dist_info) + 1 :] for m in dist_info_members}
        )
    ]

    for name in package_members | toplevel_members:
        reason = forbidden_reason(name)
        if reason is not None:
            complaints.append(f"{name} {reason}")

    complaints += package_payload_complaints(package_members)

    toplevel_error = toplevel_reason(toplevel_members, kind)
    if toplevel_error is not None:
        complaints.append(toplevel_error)
    else:
        for name in toplevel_members:
            if sizes[name] == 0:
                complaints.append(f"{name} is present and empty")
        complaints += hardening_complaints(wheel.name, compiled)

    return [f"{wheel.name}: {c}" for c in complaints]


def main(argv: list[str]) -> int:
    """Verify every wheel named on the command line."""
    if len(argv) < 2:
        print(f"usage: {argv[0]} <wheel> [<wheel> ...]", file=sys.stderr)
        return 2

    complaints = [c for arg in argv[1:] for c in verify_wheel(Path(arg))]
    for complaint in complaints:
        # the workflow annotation, so a failure is readable from the run
        # summary rather than only from the log
        print(f"::error::{complaint}", file=sys.stderr)
    if not complaints:
        for arg in argv[1:]:
            print(f"{Path(arg).name}: carries what it may and no more")
    return 1 if complaints else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
