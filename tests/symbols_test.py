# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A libsecp256k1 symbol this repository names is a symbol upstream declares.

`tests/citations_test.py` holds a test name written in this tree's prose to
a test that exists. Nothing did the same for the other family of names this
prose is full of: the libsecp256k1 and secp256k1-zkp symbols that
docstrings and comments name to say which C entry point they are about.
That class rots on a submodule bump rather than on a rename here, so no
author is in a position to notice it -- `src/btclib_secp256k1/ssa.py` named
`secp256k1_schnorrsig_sign` twice after the mainline pin move removed the
alias, found by hand while measuring something else (closes #805, issue
#796).

What is read out of this repository's own files is every run of
`secp256k1_[a-z0-9_]+` and `SECP256K1_[A-Z0-9_]+`, and what it is checked
against is every name a `.h`, `.c`, `CMakeLists.txt` or `.cmake` file under
`secp256k1/` or `secp256k1-zkp/` spells the same way.

## The oracle has to exclude upstream's own prose

Measured, and it is the trap: an oracle built from *every* file in the
vendored trees answers "present" for `secp256k1_schnorrsig_sign`, because
upstream's own `CHANGELOG.md` records removing it. Such a check passes on
the very defect it exists for. Restricting the oracle to `.h`, `.c`,
`CMakeLists.txt` and `.cmake` is what makes it work --
`test_the_oracle_excludes_what_upstream_removed` is the control that keeps
it working: the restricted oracle does not have the alias, and
`secp256k1/CHANGELOG.md` -- the file that would leak it into an
unrestricted oracle -- does, so the absence above is the restriction's
doing and not a typo in the name being looked for.

## CMake options are read as declarations, not exempted

`SECP256K1_VALGRIND`, `SECP256K1_ASM`, `SECP256K1_ECMULT_WINDOW_SIZE`,
`SECP256K1_ECMULT_GEN_KB`, `SECP256K1_BUILD_CTIME_TESTS` and
`SECP256K1_USE_EXTERNAL_DEFAULT_CALLBACKS` are declared in `CMakeLists.txt`
and `cmake/`, not in C, so an oracle built from `.h` and `.c` alone would
report every one of them absent. The alternative to widening the oracle is
exempting them by name, which is weaker: a rename upstream gives one of
them would go unnoticed either way, where reading the declaration catches
it the same way `tests/module_flags_test.py` already reads
`option(SECP256K1_ENABLE_MODULE_*)` out of the same files rather than
hand-listing the modules.

## A trailing underscore is a glob, not a name

`secp256k1_musig_*`, `secp256k1_generator_*`, `secp256k1_pedersen_*`,
`SECP256K1_ENABLE_MODULE_*` and `SECP256K1_CHECKMEM_*` appear in prose as
prefixes, one entry point or one CMake option among several. Stripping the
`*` before matching leaves the prefix looking like a name this repository
invented and the submodule never declared, so a mention ending in `*` is
read as a prefix instead: `test_no_prefix_glob_has_gone_stale` holds each
one to still resolving to at least one real name in the oracle, so a
prefix nothing matches any more fails rather than sitting there.

## What counts as this repository's prose

`CHANGELOG.md` and `RELEASE_NOTES.md` are out of scope, for the reasons
`tests/citations_test.py` gives for exempting them from its own sweep: a
released section is that release's own account of itself, and the open
section is where the record of a name as it used to be survives a rename
here.

A `.py` file is read for its comments and its module, class and function
docstrings, not for the rest of its text: `scripts/cffi_build.py` and
`tests/module_flags_test.py` both hold real `secp256k1_*` and
`SECP256K1_*` substrings in code that is not a citation -- a CLI flag such
as `-DSECP256K1_ENABLE_MODULE_ECDH=ON`, a header filename such as
`secp256k1_ecdh.h`, a regular expression built to *match* a declaration
rather than to name one. Every one of those is a value this package
computes with, checked by building and importing the extension, not a
claim in prose that can go stale on a submodule bump. Every other file
this repository tracks is read whole.

## Prose wraps

A citation is not always backticked -- `ssa.py`'s `EXTRAPARAMS_MAGIC`
comment names `SECP256K1_SCHNORRSIG_EXTRAPARAMS_MAGIC` with no backticks
around it -- so the reader here matches raw text rather than a delimited
span, and a line-oriented pattern would not see a name the reflow wrapped
across two lines. `tests/citations_test.py` names the shape: a wrap always
falls at an underscore, so the continuation line always starts with one.
That is what lets a wrap be told apart from two unrelated words that
simply landed on either side of a line break, which do not: the line
above a wrap is collapsed into the one below it only where what follows
the break, once a leading `#` and indentation are stripped, is an
underscore.
"""

from __future__ import annotations

import ast
import io
import re
import shutil
import subprocess
import tokenize
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[1]

# resolved once, the way check_sdist_exclude.py's own _GIT is: a bare
# "git" in a subprocess list is what S607 is about
_GIT = shutil.which("git") or "git"

# the vendored trees the oracle is read from, and the only ones this
# file's own prose is checked against
_SUBMODULES = ("secp256k1", "secp256k1-zkp")

# a symbol named this repository's own prose way: lower-case for a
# function, a type or a macro spelled in a signature; upper-case for a
# macro or a CMake option
_LOWER = re.compile(r"\bsecp256k1_[a-z0-9_]+")
_UPPER = re.compile(r"\bSECP256K1_[A-Z0-9_]+")

# a name immediately followed by `*`: a prefix rather than the name of one
# entry point, matched and removed before `_LOWER`/`_UPPER` run so the
# prefix itself -- ending in the underscore the `*` was stripped from --
# is not reported as a citation of its own
_GLOB = re.compile(r"(secp256k1_[a-z0-9_]+|SECP256K1_[A-Z0-9_]+)\*")

# a line break the reflow put inside one identifier: the character before
# it is part of a name already in progress, and what follows -- past an
# optional comment marker and its own indentation -- is the underscore
# that continues it. `[\s#]+` is what `tests/citations_test.py`'s own
# `_cited` collapses for the same reason
_WRAP = re.compile(r"\n[ \t]*#?[ \t]*(?=_)")

# CHANGELOG.md and RELEASE_NOTES.md hold a removed name deliberately, and
# this file's own text holds the pattern that finds one
_EXCLUDED_FILES = frozenset({
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "tests/" + Path(__file__).name,
})
# fuzz/corpus/ holds the fuzzing seeds, octets rather than prose: a
# public key or a DER signature decodes as no text at all
_EXCLUDED_DIRECTORIES = ("fuzz/corpus/",)


def _collapse(text: str) -> str:
    """Rejoin an identifier the reflow split across a line break.

    Args:
        text: prose to read, a comment block, a docstring or a whole file.

    Returns:
        The same text with a mid-identifier wrap closed up.
    """
    return _WRAP.sub("", text)


def _names(text: str) -> set[str]:
    """Every `secp256k1_*` or `SECP256K1_*` name a text mentions.

    A glob such as `` `secp256k1_musig_*` `` is removed before matching, so
    what is left of it -- the prefix, ending in an underscore -- is not
    reported as a name of its own.

    Args:
        text: prose to read.

    Returns:
        The names it mentions.
    """
    collapsed = _GLOB.sub("", _collapse(text))
    return {m.group(0) for m in _LOWER.finditer(collapsed)} | {
        m.group(0) for m in _UPPER.finditer(collapsed)
    }


def _prefixes(text: str) -> set[str]:
    """Every glob prefix a text mentions, `*` included in none of them.

    Args:
        text: prose to read.

    Returns:
        The prefixes it mentions, each ending in an underscore.
    """
    return {m.group(1) for m in _GLOB.finditer(_collapse(text))}


def _declared(patterns: tuple[str, ...]) -> set[str]:
    """Every name a submodule's own files spell, matched by their glob.

    Args:
        patterns: the glob patterns naming which files to read, relative
            to each submodule's own root.

    Returns:
        The names declared across the submodules.
    """
    names: set[str] = set()
    for submodule in _SUBMODULES:
        base = _ROOT / submodule
        for pattern in patterns:
            for path in sorted(base.rglob(pattern)):
                names |= _names(path.read_text(encoding="utf-8"))
    return names


def _oracle() -> set[str]:
    """Every name declared in either submodule's C sources or CMake.

    Returns:
        The set `test_every_named_symbol_is_declared` checks a mention
        against.
    """
    return _declared(("*.h", "*.c")) | _declared(("CMakeLists.txt", "*.cmake"))


def _comment_blocks(source: str) -> list[str]:
    """Every run of consecutive `#` comment lines in a module's source.

    Two comments on adjacent source lines are one block, so a name the
    reflow wrapped between them is read whole; a comment followed by a
    blank line, or by code, closes the block it was in.

    Args:
        source: a `.py` file's text.

    Returns:
        One entry per run of adjacent comment lines.
    """
    blocks: list[str] = []
    current: list[str] = []
    last_row: int | None = None
    # tokenize always closes the stream with an ENDMARKER, which is
    # neither COMMENT nor NL/NEWLINE, so a block left open at end of
    # file is always closed by the elif branch below -- nothing after
    # this loop is ever reached
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            row = tok.start[0]
            if current and last_row is not None and row != last_row + 1:
                blocks.append("\n".join(current))
                current = []
            current.append(tok.string)
            last_row = row
        elif tok.type not in (tokenize.NL, tokenize.NEWLINE):
            if current:
                blocks.append("\n".join(current))
                current = []
            last_row = None
    return blocks


def _docstrings(source: str) -> list[str]:
    """Every module, class and function docstring in a module's source.

    Args:
        source: a `.py` file's text.

    Returns:
        One entry per docstring the module defines.
    """
    tree = ast.parse(source)
    docs = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            doc = ast.get_docstring(node)
            if doc is not None:
                docs.append(doc)
    return docs


def _units(path: Path) -> list[str]:
    """Return the prose a file contributes: comments and docstrings for `.py`.

    A `.py` file's code is not read at all -- `scripts/cffi_build.py`'s
    CLI flags and header filenames, and `tests/module_flags_test.py`'s own
    regular expressions, are real `secp256k1_*` and `SECP256K1_*`
    substrings that are not a citation. Every other file is read whole.

    Args:
        path: the file to read.

    Returns:
        One entry per comment block or docstring, or the whole text for
        anything that is not Python.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return [text]
    return _comment_blocks(text) + _docstrings(text)


def _sources() -> list[Path]:
    """Every tracked file outside the vendored trees and the seed corpus.

    `git ls-files` rather than a filesystem walk: a build, a coverage
    database and a `.pyc` all sit inside this worktree without being part
    of it, and none is prose this file has anything to say about.

    Returns:
        The paths `_mentions` and `_prefix_mentions` read, sorted.
    """
    listed = subprocess.run(  # noqa: S603
        [_GIT, "-C", str(_ROOT), "ls-files"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout.splitlines()
    paths = []
    for rel in listed:
        if rel in _SUBMODULES or rel.startswith((
            f"{_SUBMODULES[0]}/",
            f"{_SUBMODULES[1]}/",
        )):
            continue
        if rel in _EXCLUDED_FILES or rel.startswith(_EXCLUDED_DIRECTORIES):
            continue
        paths.append(_ROOT / rel)
    return sorted(paths)


def _mentions() -> dict[str, list[str]]:
    """Every name this repository's own prose cites, and where.

    Returns:
        A mapping of name to the files citing it.
    """
    where: dict[str, list[str]] = {}
    for path in _sources():
        rel = path.relative_to(_ROOT).as_posix()
        for unit in _units(path):
            for name in sorted(_names(unit)):
                where.setdefault(name, []).append(rel)
    return where


def _prefix_mentions() -> dict[str, list[str]]:
    """Every glob prefix this repository's own prose cites, and where.

    Returns:
        A mapping of prefix to the files citing it.
    """
    where: dict[str, list[str]] = {}
    for path in _sources():
        rel = path.relative_to(_ROOT).as_posix()
        for unit in _units(path):
            for prefix in sorted(_prefixes(unit)):
                where.setdefault(prefix, []).append(rel)
    return where


def test_every_named_symbol_is_declared() -> None:
    """A `secp256k1_*` or `SECP256K1_*` name in prose is one upstream owns.

    The independent side is the oracle: the names come out of this
    repository's own comments, docstrings and markdown, and what they are
    checked against comes out of the submodules' `.h`, `.c` and CMake
    files, read separately from anything this repository itself claims
    about them.
    """
    oracle = _oracle()
    dangling = {
        name: files for name, files in _mentions().items() if name not in oracle
    }
    assert not dangling, (
        f"prose names a symbol neither submodule declares: {dangling}. Fix"
        " the spelling, or -- where the fix is that libsecp256k1 removed"
        " or renamed it -- fix what the prose says about it."
    )


def test_no_prefix_glob_has_gone_stale() -> None:
    """A glob prefix exempted from the check above still means something."""
    oracle = _oracle()
    stale = {
        prefix: files
        for prefix, files in _prefix_mentions().items()
        if not any(name.startswith(prefix) for name in oracle)
    }
    assert not stale, (
        f"prose names a glob prefix neither submodule has a member of:"
        f" {stale}. Nothing exported starts this way any more, so the"
        " sentence citing it as a family of entry points is itself stale."
    )


def test_the_oracle_excludes_what_upstream_removed() -> None:
    """Restricting the oracle to `.h`/`.c`/CMake is what avoids the trap.

    An oracle built from every file in the vendored trees would answer
    "present" for a name upstream's own `CHANGELOG.md` records removing,
    which is the defect this file exists to catch. Both halves of that
    claim are checked: the restricted oracle lacks the alias, and the
    file that would have leaked it in has it.
    """
    removed = "secp256k1_schnorrsig_sign"
    assert removed not in _oracle()
    upstream_changelog = (_ROOT / "secp256k1" / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    assert removed in _names(upstream_changelog)


def test_the_prose_was_read_at_all() -> None:
    """The two guards above pass for free over an empty population.

    Neither says anything if the reader finds no mention, which is what a
    broken pattern or a wrong path would look like.
    """
    sources = _sources()
    assert len(sources) > 1
    mentions = _mentions()
    assert mentions
    assert mentions.keys() <= _oracle()


@pytest.mark.parametrize(
    "text, expected",
    [
        ("`secp256k1_context_no_precomp`", {"secp256k1_context_no_precomp"}),
        # ssa.py's EXTRAPARAMS_MAGIC comment: a citation with no backticks
        (
            "# SECP256K1_SCHNORRSIG_EXTRAPARAMS_MAGIC: the macros do not",
            {"SECP256K1_SCHNORRSIG_EXTRAPARAMS_MAGIC"},
        ),
        # the wrap, at the underscore, inside a docstring
        (
            "derives through `_sign32` and\n`secp256k1_schnorrsig\n_sign32`",
            {"secp256k1_schnorrsig_sign32"},
        ),
        # the same wrap across two comment lines, marker included
        (
            "# names `secp256k1_long_name\n# _split_here` in prose",
            {"secp256k1_long_name_split_here"},
        ),
        # an ordinary line break between two unrelated words is not a wrap
        ("secp256k1_context_create makes\none", {"secp256k1_context_create"}),
    ],
)
def test_the_reader_reads_a_mention(text: str, expected: set[str]) -> None:
    """`_names` on the shapes this tree actually holds, wrapped or not.

    Args:
        text: prose to read.
        expected: the names it mentions.
    """
    assert _names(text) == expected


def test_the_reader_strips_a_glob_before_matching() -> None:
    """A prefix ending in `*` is read as a prefix, not as its own name."""
    text = "the five `secp256k1_musig_*` structs the header declares"
    assert _names(text) == set()
    assert _prefixes(text) == {"secp256k1_musig_"}


def test_code_is_not_read_as_a_citation() -> None:
    """A `.py` file's non-comment, non-docstring text is not scanned.

    `tests/module_flags_test.py`'s own `_OPTION` pattern spells
    `SECP256K1_ENABLE_MODULE_` as a regular expression, not as a citation
    of that half of a name -- reading `_units` rather than the file's raw
    text is what keeps that regex out of `_mentions`.
    """
    source = (
        '"""A docstring citing `secp256k1_ecdh`."""\n'
        "import re\n"
        '_OPTION = re.compile(r"option\\(SECP256K1_ENABLE_MODULE_")\n'
        "# a comment citing SECP256K1_ASM\n"
    )
    units = _comment_blocks(source) + _docstrings(source)
    mentioned: set[str] = set()
    for unit in units:
        mentioned |= _names(unit)
    assert mentioned == {"secp256k1_ecdh", "SECP256K1_ASM"}
