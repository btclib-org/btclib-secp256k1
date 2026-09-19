# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A hook's pins are what `uv.lock` resolves, wherever it resolves them.

The type gate runs in an environment of its own: `.pre-commit-config.yaml`
gives the mirror a `rev` and a list of `additional_dependencies`, and
pre-commit builds that environment once and keeps it. The editor cannot
use it -- this package is a compiled extension and the import does not
resolve where nothing built one -- so what the editor reads is the
project environment instead, and the two are the same mypy only while the
two declarations say the same thing.

Nothing made them say it. `.pre-commit-config.yaml` records that they are
"moved by hand, with the lint and test groups of uv.lock", which is a
procedure rather than a check, and section 4 of the organization standard
names that second declaration as the price of this branch. This module is
what turns the procedure into a red test: a `uv lock` that moves one of
these and a hand that does not follow is the whole of what it catches,
and it is silent -- both environments still build, and mypy still passes
in each, against different versions.

That procedure is about a hand-moved pin rather than about mypy, so every
`additional_dependencies` pin in the file is read here and asserted
against the lock wherever the lock resolves its package
(btclib-org/btclib-secp256k1#779). Where it does not, the pin is the only
declaration there is and nothing can disagree with it: `uv.lock` resolves
neither `shellcheck-py` nor `typos`, each being a tool installed for one
hook and declared by no dependency group, and a pin absent from the lock
is left alone rather than failed. The mypy block keeps the stronger
reading of the two, `test_every_mypy_pin_is_one_the_lock_resolves` below
requiring each of its pins to be in the lock at all: they are what the
checked files import, and the project installs those.

The pins follow the highest resolution, which is the one `uv.lock` holds.
A lock written by another -- `deps-oldest.yml` writes one on purpose,
resolving to `lowest-direct` -- records it in its own `[options]` table,
and against such a lock `test_the_rev_is_the_locked_mypy` and
`test_every_pin_is_the_locked_version` are skipped: the pins were moved
to agree with the highest resolution, and a lock that takes every direct
dependency to its floor is not that one. The mode is read from the lock
and not from `UV_RESOLUTION`, the lock being what those two tests
compare against.

Parsed rather than loaded. `uv.lock` is toml and the floor here is 3.10,
where `tomllib` is not yet in the standard library, which is the reason
`copyright_test.py` beside this one reads pyproject.toml the same way;
`.pre-commit-config.yaml` is yaml and no group here carries a parser for
it. Three shapes are narrow enough to match: a `[[package]]` table with a
name and a version, and the two this file writes an
`additional_dependencies` value in -- a bracketed list on the key's own
line, and `- ` items indented under it.

A value is read whole or not at all. The comma separates a flow
sequence's items in yaml and a specifier set's clauses in PEP 440, so
the split that reads the first has to know where a quoted scalar begins
and ends, and the set that survives the split is read as one thing
rather than as text around an `==`. An item the walk still cannot
resolve into a requirement makes the whole value nothing, which
`test_every_additional_dependencies_key_was_read` fails on rather than
asserting the pins beside it while the rest goes unread.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pytest

_ROOT = Path(__file__).parents[1]
_CONFIG = _ROOT / ".pre-commit-config.yaml"
_LOCK = _ROOT / "uv.lock"

# the mypy hook's block, from its repo line to the next hook's: what
# `test_every_mypy_pin_is_one_the_lock_resolves` reads is that hook's and
# not another's, `shellcheck-py` being pinned one hook over
_MYPY_BLOCK = re.compile(
    r"^  - repo: https://github\.com/pre-commit/mirrors-mypy\n(.*?)(?=^  - repo: )",
    re.MULTILINE | re.DOTALL,
)
_REV = re.compile(r"^    rev: v?(?P<version>[0-9][0-9a-z.]*)\s*$", re.MULTILINE)
# an additional_dependencies key and whatever shares its line: nothing,
# where the requirements are the "- " items indented under it
_KEY = re.compile(r"^(?P<indent> *)additional_dependencies:(?P<inline>.*)$")
# a requirement's name, its specifier set, and the marker the set ends
# at: [build-system]'s own requires, copied into this file verbatim,
# write a floor and a marker where a hook's own pin writes a version
_NAME = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)(?P<specifiers>[^;]*)(?:;.*)?$")
# one clause of a specifier set, which PEP 440 writes comma-separated:
# `===` ahead of `==` so that arbitrary equality is read as itself rather
# than as `==` naming a version beginning with `=`
_CLAUSE = re.compile(r"^(?P<op>===|==|!=|~=|<=|>=|<|>)\s*(?P<version>[^\s,;]+)$")
# where uv records a resolution other than its default: the `[options]`
# table, whose `resolution-mode` key a lock resolved to `lowest-direct`
# carries as `"lowest-direct"` and the ordinary lock of this tree has no
# such table to carry it in
_OPTIONS = re.compile(r"^\[options\]\n(?P<keys>(?:[^\n\[].*\n)*)", re.MULTILINE)
_MODE = re.compile(r'^resolution-mode = "(?P<mode>[^"]+)"$', re.MULTILINE)


class _Requirement(NamedTuple):
    """One requirement of an `additional_dependencies` value.

    Attributes:
        name: the package it asks for.
        pinned: the one version its specifier set names, or None where
            it names none.
    """

    name: str
    pinned: str | None


def _unquoted(item: str) -> str:
    """Return `item` without the pair of quotes yaml wrote it in.

    A pair, rather than any quote at either end: a requirement whose
    marker quotes a version -- `python_version<"3.13"` -- is written
    inside single quotes, and stripping quote characters wherever they
    fall takes the marker's closing one with them.

    Args:
        item: one requirement, as the file writes it.

    Returns:
        The requirement.
    """
    quoted = len(item) > 1 and item[0] == item[-1] and item[0] in "\"'"
    return item[1:-1] if quoted else item


def _split(items: str) -> list[str]:
    """Return `items` cut at the commas yaml reads as separators.

    A comma inside a quoted scalar is that scalar's own, and a specifier
    set is comma-separated: `"name==1.2.3,!=1.2.4"` is one requirement,
    where a cut at every comma answers pieces that are requirements none
    of them and that a check for an unread value cannot tell from pieces
    that are.

    Args:
        items: what a flow sequence holds between its brackets.

    Returns:
        The items, as the file quotes them.
    """
    found: list[str] = []
    start = 0
    quote = ""
    for index, char in enumerate(items):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == ",":
            found.append(items[start:index])
            start = index + 1
    found.append(items[start:])
    return found


def _flow(value: str) -> list[str]:
    """Return the requirements of a value written on the key's own line.

    Args:
        value: what follows the key, stripped.

    Returns:
        The requirements, unquoted; empty where the value is not a
        bracketed list, which is a shape this walk does not read.
    """
    if not (value.startswith("[") and value.endswith("]")):
        return []
    items = (_unquoted(item.strip()) for item in _split(value[1:-1]))
    return [item for item in items if item]


def _items(lines: list[str], indent: int) -> list[str]:
    """Return the "- " items indented deeper than `indent`.

    A comment between two items is read through, the mypy block writing
    one; anything else -- a blank line, a line at the key's own
    indentation or shallower, a line that is no item -- ends the value,
    since what follows it belongs to something other than this key.

    Args:
        lines: the lines after the key's own.
        indent: the key's indentation.

    Returns:
        The requirements, unquoted.
    """
    found: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or len(line) - len(line.lstrip(" ")) <= indent:
            break
        if stripped.startswith("#"):
            continue
        if not stripped.startswith("- "):
            break
        found.append(_unquoted(stripped[2:].strip()))
    return found


def _clauses(specifiers: str) -> tuple[tuple[str, str], ...] | None:
    """Return the operator and version of each clause of a specifier set.

    Args:
        specifiers: what follows a requirement's name, up to its marker.

    Returns:
        One pair per clause, or None where a clause is not one: a set
        read in part describes a requirement the file does not hold.
    """
    found: list[tuple[str, str]] = []
    for clause in specifiers.split(","):
        match = _CLAUSE.match(clause.strip())
        if match is None:
            return None
        found.append((match["op"], match["version"]))
    return tuple(found)


def _read(item: str) -> _Requirement | None:
    """Return the requirement `item` is, or None where it is not one.

    A specifier set names a version where one of its clauses is an
    equality naming one, so `name==1.2.3,!=1.2.4` pins 1.2.3 as plainly
    as `name==1.2.3` does and is asserted against the lock the same way.
    `hatchling>=1.27,<2` names a range and pins nothing, and `name==1.2.*`
    is a range written with an equality.

    Args:
        item: one item of a value, unquoted.

    Returns:
        The requirement, or None where the walk cannot resolve `item`
        into one -- a mapping, or a specifier followed by anything but a
        marker, a yaml comment on the item's own line among them.
    """
    parts = _NAME.match(item)
    if parts is None:
        return None
    specifiers = parts["specifiers"].strip()
    clauses = _clauses(specifiers) if specifiers else ()
    if clauses is None:
        return None
    pinned = [
        version
        for operator, version in clauses
        if operator in ("==", "===") and "*" not in version
    ]
    return _Requirement(parts["name"], pinned[0] if len(pinned) == 1 else None)


def _requirements(items: list[str]) -> list[_Requirement]:
    """Return the requirements `items` are, or nothing where one is not.

    Args:
        items: one value's items, unquoted.

    Returns:
        One requirement per item, in the order the file writes them;
        empty where the walk resolves any of them into no requirement.
    """
    found: list[_Requirement] = []
    for item in items:
        requirement = _read(item)
        if requirement is None:
            return []
        found.append(requirement)
    return found


def _values(text: str) -> list[list[_Requirement]]:
    """Return the requirements of every `additional_dependencies` key.

    Args:
        text: the configuration, or a block of it.

    Returns:
        One list per key, in the order the keys are written.
    """
    lines = text.splitlines()
    return [
        _requirements(
            _flow(key["inline"].strip())
            if key["inline"].strip()
            else _items(lines[index + 1 :], len(key["indent"]))
        )
        for index, line in enumerate(lines)
        if (key := _KEY.match(line)) is not None
    ]


def _pins(values: list[list[_Requirement]]) -> tuple[tuple[str, str], ...]:
    """Return the name and version of every pin among `values`.

    Args:
        values: the requirement lists to read.

    Returns:
        The pairs, sorted and without repetition -- two hooks pinning
        one package at one version ask the lock one question, and at two
        versions ask it two.
    """
    found = {
        (requirement.name, requirement.pinned)
        for value in values
        for requirement in value
        if requirement.pinned is not None
    }
    return tuple(sorted(found))


def _locked(name: str) -> str | None:
    """Return the version `uv.lock` resolves for `name`, or None."""
    pattern = re.compile(
        rf'^name = "{re.escape(name)}"\nversion = "(?P<version>[^"]+)"$',
        re.MULTILINE,
    )
    match = pattern.search(_LOCK.read_text(encoding="utf-8"))
    return match["version"] if match else None


def _resolution_mode(lock: str) -> str:
    """Return the resolution `lock` was written under.

    Args:
        lock: the text of a `uv.lock`.

    Returns:
        The mode its `[options]` table records, or "highest" where it
        records none: uv's default, and the one the hook pins follow.
    """
    options = _OPTIONS.search(lock)
    mode = _MODE.search(options["keys"]) if options else None
    return mode["mode"] if mode else "highest"


def _block() -> str:
    """Return the mypy hook's block of `.pre-commit-config.yaml`."""
    match = _MYPY_BLOCK.search(_CONFIG.read_text(encoding="utf-8"))
    assert match, "no mirrors-mypy hook in .pre-commit-config.yaml"
    return match[1]


_BLOCK = _block()
_MYPY_PINS = _pins(_values(_BLOCK))
_VALUES = _values(_CONFIG.read_text(encoding="utf-8"))
_PINS = tuple(pin for pin in _pins(_VALUES) if _locked(pin[0]) is not None)
_RESOLUTION = _resolution_mode(_LOCK.read_text(encoding="utf-8"))
_MOVED_WITH_THE_HIGHEST = pytest.mark.skipif(
    _RESOLUTION != "highest",
    reason=f"uv.lock records a {_RESOLUTION} resolution, and the hook pins"
    " follow the highest one",
)


def test_the_hook_block_was_read() -> None:
    """A block that parsed to nothing satisfies every check below.

    The patterns are anchored on an indentation `.pre-commit-config
    .yaml` happens to use, so a reformat that changed it would leave the
    pins unread and the assertions quantifying over nothing.
    """
    assert _MYPY_PINS, "the mirrors-mypy hook lists no pinned additional_dependencies"


def test_every_additional_dependencies_key_was_read() -> None:
    """A key whose value the walk cannot read is the same silence, hook-wide.

    `test_the_hook_block_was_read` above covers the mypy block alone,
    and a value written in a third shape would be read as a key
    declaring nothing: the pins under it would go unasserted with every
    parametrisation below still green.
    """
    assert _VALUES, "no additional_dependencies key in .pre-commit-config.yaml"
    assert all(_VALUES), "an additional_dependencies key read as declaring nothing"


def test_a_value_that_is_not_a_bracketed_list_reads_as_nothing() -> None:
    """A shape the walk does not read is nothing, never a partial answer.

    `test_every_additional_dependencies_key_was_read` above is what
    turns that nothing into a failure, and it can only do so because
    the walk declines rather than salvaging what it recognizes.
    """
    assert _flow("{pathspec: 1.1.1}") == []
    assert _flow('["pathspec==1.1.1", typos==1.49.0]') == [
        "pathspec==1.1.1",
        "typos==1.49.0",
    ]


def test_a_quoted_comma_belongs_to_the_specifier_set_and_not_the_sequence() -> None:
    """One separator serves yaml and PEP 440, and the quotes tell them apart.

    Cut at every comma, a specifier set answers pieces that are
    requirements none of them, and a piece is as truthy as a requirement
    is: the value reads as declaring something, and every check below
    quantifies over what is left of it.
    """
    assert _flow('["name==1.2.3,!=1.2.4", pytest==9.1.1]') == [
        "name==1.2.3,!=1.2.4",
        "pytest==9.1.1",
    ]


def test_a_specifier_set_pins_where_one_of_its_clauses_names_a_version() -> None:
    """A pin beside another clause is a pin, and a range is not one.

    The lock resolves one version per package, so a requirement naming
    one is a question to ask it however many clauses stand beside that
    one; a range and a wildcard name no version and ask it nothing.
    """
    assert _read("name==1.2.3,!=1.2.4") == ("name", "1.2.3")
    assert _read("name===1.2.3") == ("name", "1.2.3")
    assert _read("hatchling>=1.27,<2") == ("hatchling", None)
    assert _read("name==1.2.*") == ("name", None)


def test_an_item_that_is_no_requirement_makes_the_whole_value_nothing() -> None:
    """A comment on an item's own line is a shape the walk does not read.

    `_items` above ends a value at a line that is no item, which a line
    carrying an item and a comment is not; what the walk cannot resolve
    is declined here instead, so that
    `test_every_additional_dependencies_key_was_read` sees the nothing.
    Reading the items around it would assert the pins it recognized and
    drop the rest with nothing red.
    """
    text = (
        "        additional_dependencies:\n"
        "          - cffi==2.1.1\n"
        "          - pathspec==1.1.1  # why this one carries a version"
    )

    assert _items(text.splitlines()[1:], 8) == [
        "cffi==2.1.1",
        "pathspec==1.1.1  # why this one carries a version",
    ]
    assert _values(text) == [[]]
    assert _read("{pathspec: 1.1.1}") is None


def test_a_block_value_ends_at_the_first_line_that_is_not_an_item() -> None:
    """A comment between two items is read through; anything else is not.

    The mypy hook writes such a comment. What follows a hook's items is
    another key of that hook, or the next hook at a shallower
    indentation, and neither declares a requirement -- so a line that is
    no item ends the value where it stands rather than being skipped
    the way a comment is.
    """
    lines = [
        "          - cffi==2.1.1",
        "          # why the next one carries a version",
        "          - pathspec==1.1.1",
        "          this line is no item",
        "          - unreachable==9.9",
    ]

    assert _items(lines, 8) == ["cffi==2.1.1", "pathspec==1.1.1"]


def test_a_block_value_running_to_the_end_of_the_text_is_read_whole() -> None:
    """The last key of the text has no following line to stop at."""
    assert _items(["          - cffi==2.1.1"], 8) == ["cffi==2.1.1"]


def test_a_quoted_requirement_keeps_the_quotes_inside_its_marker() -> None:
    """Only the pair yaml wrote goes, so a marker's own quotes survive.

    `[build-system]`'s requires are copied into this file verbatim, and
    each marker-gated one is single-quoted around a double-quoted
    version; stripping quote characters wherever they fall would take
    the marker's closing one and answer a requirement the file does not
    hold.
    """
    assert _flow("""['cffi>=1.6; python_version<"3.13"']""") == [
        'cffi>=1.6; python_version<"3.13"'
    ]


def test_a_lock_names_its_resolution_only_where_it_is_not_the_default() -> None:
    """The `[options]` table is the one place the mode is written.

    An `[options]` table that names no `resolution-mode` is the default
    resolution too: the two skips below rest on this reading, and a
    misread that answered a mode where the lock names none would skip
    them on an ordinary lock, silently.
    """
    header = 'version = 1\nrequires-python = ">=3.10"\n'
    package = '\n[[package]]\nname = "cffi"\nversion = "1.14.1"\n'
    lowest = '\n[options]\nresolution-mode = "lowest-direct"\n'
    dated = '\n[options]\nexclude-newer = "2026-01-01T00:00:00Z"\n'

    assert _resolution_mode(header + package) == "highest"
    assert _resolution_mode(header + lowest + package) == "lowest-direct"
    assert _resolution_mode(header + dated + package) == "highest"


@_MOVED_WITH_THE_HIGHEST
def test_the_rev_is_the_locked_mypy() -> None:
    """The isolated environment's mypy and the project's are one version.

    They have to be: the editor reads the project's, the gate reads the
    hook's, and a developer told the two disagree learns it from a
    finding one reports and the other does not.
    """
    rev = _REV.search(_BLOCK)
    assert rev, "the mirrors-mypy hook declares no rev"
    assert rev["version"] == _locked("mypy"), (
        f"the hook pins mypy {rev['version']} where uv.lock resolves {_locked('mypy')}"
    )


@pytest.mark.parametrize("name, version", _MYPY_PINS, ids=lambda v: v)
def test_every_mypy_pin_is_one_the_lock_resolves(name: str, version: str) -> None:
    """The mypy hook installs what the checked files import, and so does uv."""
    assert _locked(name) is not None, (
        f"the mypy hook pins {name}=={version} and uv.lock resolves no"
        f" {name}: it is not one of the packages the lock keeps level"
    )


@_MOVED_WITH_THE_HIGHEST
@pytest.mark.parametrize("name, version", _PINS, ids=lambda v: v)
def test_every_pin_is_the_locked_version(name: str, version: str) -> None:
    """Each pinned package the project also installs is the one version."""
    assert version == _locked(name), (
        f"a hook pins {name}=={version} where uv.lock resolves {_locked(name)}"
    )
