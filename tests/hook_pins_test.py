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

Two environments carry `[build-system]`'s `requires` rather than a pin.
`check-sdist`'s `additional_dependencies` is those requirements verbatim,
and pre-commit builds a hook's environment once and keeps it, so a copy
left behind is not noticed by its hook until that environment is rebuilt
(btclib-org/btclib-secp256k1#945). The `pyroma` hook has no environment of
its own: it runs out of a dependency group, which its `entry` names, and
that group holds the `hatchling` one of the requirements.
`test_check_sdist_installs_what_build_system_requires` and
`test_pyroma_installs_the_backend_build_system_declares` compare each
copy with `pyproject.toml`, the hook found by its `id`.

Parsed rather than loaded. `uv.lock` is toml and the floor here is 3.10,
where `tomllib` is not yet in the standard library, which is the reason
`copyright_test.py` beside this one reads pyproject.toml the same way;
`.pre-commit-config.yaml` is yaml and no group here carries a parser for
it. The shapes narrow enough to match are a `[[package]]` table with a
name and a version, the two this file writes an `additional_dependencies`
value in -- a bracketed list on the key's own line, and `- ` items
indented under it -- a hook's `entry` and its `args` on one line, and an
array of `pyproject.toml` -- `[build-system]`'s `requires` and a
dependency group -- opened alone on its line, one string to a line.

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
_PYPROJECT = _ROOT / "pyproject.toml"

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
# a hook's first line, whatever the indentation its list is written at
_HOOK = re.compile(r"^(?P<indent> *)- id: (?P<id>[^\s#]+)\s*$")
# a hook's `entry` written on the key's own line: a block scalar has an
# indicator after its key, which the pattern does not accept
_ENTRY_LINE = re.compile(r"^ +entry: (?P<value>[^|>\s].*)$", re.MULTILINE)
# a hook's `args` written as one flow sequence on the key's own line
_ARGS_LINE = re.compile(r"^ +args: (?P<value>\[.*\])$", re.MULTILINE)
# the dependency group `uv run` is asked for, with the flag alone naming it
_ONLY_GROUP = re.compile(r"(?:^|\s)--only-group[= ](?P<group>[A-Za-z0-9_.-]+)(?=\s|$)")
# one toml string alone on its line: a basic one with no escape in it, or
# a literal one, which is how the marker-gated requirements quote their
# double-quoted versions. The trailing comma is the array's own
_ENTRY = re.compile(r"""^(?:"(?P<basic>[^"\\]*)"|'(?P<literal>[^']*)'),?$""")


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


def _written(text: str) -> list[list[str]]:
    """Return the items of every `additional_dependencies` key, as written.

    Args:
        text: the configuration, or a block of it.

    Returns:
        One list per key, in the order the keys are written, each item
        unquoted and otherwise as the file has it.
    """
    lines = text.splitlines()
    return [
        _flow(key["inline"].strip())
        if key["inline"].strip()
        else _items(lines[index + 1 :], len(key["indent"]))
        for index, line in enumerate(lines)
        if (key := _KEY.match(line)) is not None
    ]


def _values(text: str) -> list[list[_Requirement]]:
    """Return the requirements of every `additional_dependencies` key.

    Args:
        text: the configuration, or a block of it.

    Returns:
        One list per key, in the order the keys are written.
    """
    return [_requirements(items) for items in _written(text)]


def _hook_block(text: str, hook_id: str) -> str:
    """Return the lines of the hook `id` names, after its `- id:` line.

    The hook is the lines from its `- id:` line to the first non-blank
    line indented no deeper than that one, which is the next hook's or
    the next repo's. `check-sdist` is an `id` and `check-sdist-isolated`
    is another, so the line is matched whole.

    Args:
        text: the configuration.
        hook_id: the hook's `id`.

    Returns:
        The lines, joined; empty where no hook has that `id` and where
        two do.
    """
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if (hook := _HOOK.match(line)) is not None and hook["id"] == hook_id
    ]
    if len(starts) != 1:
        return ""
    indent = len(lines[starts[0]]) - len(lines[starts[0]].lstrip(" "))
    block = []
    for line in lines[starts[0] + 1 :]:
        if line.strip() and len(line) - len(line.lstrip(" ")) <= indent:
            break
        block.append(line)
    return "\n".join(block)


def _hook_dependencies(text: str, hook_id: str) -> list[str]:
    """Return the `additional_dependencies` of the hook `id` names.

    Args:
        text: the configuration.
        hook_id: the hook's `id`.

    Returns:
        The items as the file writes them, unquoted; empty where no hook
        has that `id`, where two do, and where the hook does not declare
        exactly one list -- so that a hook renamed or restructured reads
        as nothing, which `test_the_lists_compared_below_were_read`
        fails on.
    """
    keys = _written(_hook_block(text, hook_id))
    return keys[0] if len(keys) == 1 else []


def _hook_entry(text: str, hook_id: str) -> str:
    """Return the `entry` of the hook `id` names, on one line.

    Args:
        text: the configuration.
        hook_id: the hook's `id`.

    Returns:
        The command, unquoted; empty where no hook has that `id`, where
        two do, and where the hook does not write exactly one `entry` on
        one line -- a block scalar has nothing after its key, which the
        pattern does not match.
    """
    entries = _ENTRY_LINE.findall(_hook_block(text, hook_id))
    return _unquoted(entries[0].strip()) if len(entries) == 1 else ""


def _hook_args(text: str, hook_id: str) -> list[str]:
    """Return the `args` of the hook `hook_id` names, one item each.

    Args:
        text: the configuration.
        hook_id: the hook's `id`.

    Returns:
        The items, unquoted; empty where no hook has that `id`, where
        two do, and where the hook does not write exactly one `args` as
        a flow sequence on one line.
    """
    found = _ARGS_LINE.findall(_hook_block(text, hook_id))
    if len(found) != 1:
        return []
    return _flow(found[0])


def _only_group(entry: str) -> str:
    """Return the dependency group `entry` asks `uv run` for alone.

    Args:
        entry: a hook's command.

    Returns:
        The group `--only-group` names; empty where the command names no
        group that way or names two, a command running out of two groups
        having no one of them to compare.
    """
    groups = _ONLY_GROUP.findall(entry)
    return groups[0] if len(groups) == 1 else ""


def _array(pyproject: str, table: str, key: str) -> list[str]:
    """Return the entries of `key`'s array in `table`, each as written.

    A line-based walk, as `check_sdist_exclude.py`'s is of its own
    array: a comment inside this one is free to hold a `]`, and only a
    line that is exactly `]` ends it. The array opens on a line
    that is `<key> = [` and nothing else, and every entry is one
    string alone on its line, with blank lines and whole-line comments
    free to sit between them. Anything else is refused rather than read
    in part, since a list read in part is an array the file does not
    hold and a comparison against it passes on the part -- an entry
    that is a table, as a group's `include-group` is, included.

    Args:
        pyproject: the file's text.
        table: the table's header, brackets included.
        key: the array's key.

    Returns:
        The entries, in the order they are written; empty where the
        table has no such key in that shape.
    """
    opening = re.compile(rf"^{re.escape(key)}\s*=\s*\[$")
    in_table = False
    in_array = False
    found: list[str] = []
    for line in pyproject.splitlines():
        stripped = line.strip()
        if in_array:
            if stripped == "]":
                return found
            if not stripped or stripped.startswith("#"):
                continue
            entry = _ENTRY.match(stripped)
            if entry is None:
                return []
            found.append(
                entry["basic"] if entry["basic"] is not None else entry["literal"]
            )
        elif stripped.startswith("["):
            in_table = stripped == table
        elif in_table and opening.match(stripped):
            in_array = True
    return []


def _build_requires(pyproject: str) -> list[str]:
    """Return `[build-system]`'s `requires`, each entry as it is written."""
    return _array(pyproject, "[build-system]", "requires")


def _group(pyproject: str, name: str) -> list[str]:
    """Return the requirements of the dependency group `name`, as written."""
    return _array(pyproject, "[dependency-groups]", name)


def _backend(items: list[str]) -> list[str]:
    """Return the items among `items` that ask for `hatchling`."""
    return [
        item
        for item in items
        if (requirement := _read(item)) is not None and requirement.name == "hatchling"
    ]


def _drift(declared: list[str], copied: list[str]) -> str:
    """Return how `copied` parts from `declared`, or "" where it does not.

    The order is not compared: what a hook installs is a set of
    requirements, and only the requirements themselves are its
    environment.

    Args:
        declared: the requirements `pyproject.toml` writes.
        copied: the requirements a hook lists.

    Returns:
        What `copied` lacks of `declared` and what it adds, as text.
    """
    lacks = [item for item in declared if item not in copied]
    adds = [item for item in copied if item not in declared]
    return "; ".join(
        f"{verb} {items}" for verb, items in (("lacks", lacks), ("adds", adds)) if items
    )


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
_BUILD_REQUIRES = _build_requires(_PYPROJECT.read_text(encoding="utf-8"))
_CHECK_SDIST = _hook_dependencies(_CONFIG.read_text(encoding="utf-8"), "check-sdist")
_PYROMA_ENTRY = _hook_entry(_CONFIG.read_text(encoding="utf-8"), "pyroma")
_PYROMA_GROUP = _only_group(_PYROMA_ENTRY)
_PYROMA_ENVIRONMENT = (
    _group(_PYPROJECT.read_text(encoding="utf-8"), _PYROMA_GROUP)
    if _PYROMA_GROUP
    else []
)
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


_SAMPLE = """\
repos:
  # a comment between two repos
  - repo: https://example.com/a
    hooks:
      - id: check-sdist
        args: [--flag]
        additional_dependencies:
          - "hatchling>=1.27,<2"
          # a note inside the list
          - 'cffi>=1.14.1; python_version<"3.13"'

      - id: check-sdist-isolated
        additional_dependencies: [other]
  # what the next repo is for
  - repo: https://example.com/b
    hooks:
      - id: another-hook
        additional_dependencies: ["hatchling>=1.27,<2"]
      - id: nodeps
        name: no dependencies
        entry: uv run --locked --only-group check pyroma -d
      - id: blockentry
        entry: |-
          a pattern
      - id: twoentries
        entry: one
        entry: two
"""


def test_a_hook_is_found_by_its_id_and_read_to_where_the_next_begins() -> None:
    """The list is the named hook's own, however many hooks stand around it.

    `check-sdist-isolated` follows `check-sdist` and lists another
    package, and a walk that ran on past the first hook would answer
    with that one's list, or with both.
    """
    assert _hook_dependencies(_SAMPLE, "check-sdist") == [
        "hatchling>=1.27,<2",
        'cffi>=1.14.1; python_version<"3.13"',
    ]
    assert _hook_dependencies(_SAMPLE, "check-sdist-isolated") == ["other"]
    assert _hook_dependencies(_SAMPLE, "another-hook") == ["hatchling>=1.27,<2"]


def test_a_hook_without_exactly_one_list_reads_as_nothing() -> None:
    """A rename, a removal, a repeated `id` and a hook with no list are nothing.

    `test_the_lists_compared_below_were_read` is what turns that
    nothing into a failure; a walk that answered the first of two hooks,
    or a neighbour's list for a hook that is gone, would leave the
    comparison green on a hook it never read.
    """
    assert _hook_dependencies(_SAMPLE, "check-sdist-renamed") == []
    assert _hook_dependencies(_SAMPLE, "nodeps") == []
    assert _hook_dependencies(_SAMPLE + _SAMPLE, "another-hook") == []


def test_an_entry_is_the_one_command_on_the_hooks_own_line() -> None:
    """A block scalar, two entries and an absent hook read as no command.

    `test_the_lists_compared_below_were_read` is what fails on the
    nothing: an `entry` read from a neighbour, or the first of two, would
    name a group the hook may not run from.
    """
    assert (
        _hook_entry(_SAMPLE, "nodeps") == "uv run --locked --only-group check pyroma -d"
    )
    assert _hook_entry(_SAMPLE, "blockentry") == ""
    assert _hook_entry(_SAMPLE, "twoentries") == ""
    assert _hook_entry(_SAMPLE, "another-hook") == ""
    assert _hook_entry(_SAMPLE, "absent") == ""
    assert _hook_entry('  - id: q\n    entry: "uv run"\n', "q") == "uv run"


def test_args_are_the_one_flow_sequence_on_the_hooks_own_line() -> None:
    """A repeated key, a block list and an absent hook read as no arguments.

    `test_the_pyroma_hook_asks_for_the_rating_the_workflows_ask_for` is
    what fails on the nothing: an `args` read from a neighbour, or the
    first of two, would hold `--min=10` for a hook that does not ask for
    it. A comma inside a quoted item is that item's own.
    """
    assert _hook_args(_SAMPLE, "check-sdist") == ["--flag"]
    assert _hook_args(_SAMPLE, "nodeps") == []
    assert _hook_args(_SAMPLE, "absent") == []
    assert _hook_args("  - id: q\n    args: ['a,b', c]\n", "q") == ["a,b", "c"]
    assert _hook_args("  - id: q\n    args: [a]\n    args: [b]\n", "q") == []
    assert _hook_args("  - id: q\n    args:\n      - a\n", "q") == []
    assert _hook_args("  - id: q\n    args: []\n", "q") == []


@pytest.mark.parametrize(
    "entry, group",
    [
        ("uv run --locked --only-group check pyroma -d", "check"),
        ("uv run --only-group=check pyroma", "check"),
        ("uv run --only-group check", "check"),
        ("uv run --only-group check --only-group lint pyroma", ""),
        ("uv run --group check pyroma", ""),
        ("uv run --no-only-group check pyroma", ""),
        ("pyroma -d .", ""),
    ],
    ids=[
        "the flag and its group",
        "written with an equals sign",
        "at the end of the command",
        "two groups",
        "a group that is not alone",
        "another flag ending the same way",
        "no uv at all",
    ],
)
def test_the_group_is_the_one_only_group_names(entry: str, group: str) -> None:
    """`--only-group` alone names the environment; anything else names none."""
    assert _only_group(entry) == group


def test_a_dependency_group_is_read_where_a_table_holds_no_string() -> None:
    """A group of strings is read, and one holding a table is not read in part.

    `dev` includes the other groups by `{ include-group = ... }`, which
    is no requirement and no string alone on its line: read in part, the
    group would compare as though it were the whole.
    """
    text = (
        '[build-system]\ncheck = [\n    "not-this",\n]\n\n'
        "[dependency-groups]\n# a note about the group [and a bracket]\n"
        'check = [\n    "twine>=7.0.0",\n'
        "    # why the next one\n"
        "    \"pyroma>=5.1b2; python_version >= '3.11'\",\n]\n"
        'dev = [\n    { include-group = "check" },\n]\n'
    )

    assert _group(text, "check") == [
        "twine>=7.0.0",
        "pyroma>=5.1b2; python_version >= '3.11'",
    ]
    assert _group(text, "dev") == []
    assert _group(text, "absent") == []


def test_the_build_requires_are_read_through_comments_and_blank_lines() -> None:
    """Both quotings are read, and a comment may hold a bracket.

    The marker-gated requirements are single-quoted around a
    double-quoted version, and another table's `requires` is nobody's
    build requirement.
    """
    text = (
        '[tool.other]\nrequires = [\n    "not-this",\n]\n\n'
        "[build-system]\n# a comment with a ] of its own\nrequires = [\n"
        "    # a note between two entries [and a bracket]\n"
        '    "hatchling>=1.27,<2",\n\n'
        """    'cffi>=1.14.1; python_version<"3.13"',\n"""
        '    "cmake>=3.22"\n]\nbuild-backend = "hatchling.build"\n'
    )

    assert _build_requires(text) == [
        "hatchling>=1.27,<2",
        'cffi>=1.14.1; python_version<"3.13"',
        "cmake>=3.22",
    ]


@pytest.mark.parametrize(
    "text",
    [
        '[build-system]\nrequires = ["hatchling"]\n',
        '[build-system]\nrequires = ["a",\n    "b",\n]\n',
        '[build-system]\nrequires = [\n    "a",\n    "b",  # why\n]\n',
        '[build-system]\nrequires = [\n    "a",\n    "b\\tc",\n]\n',
        '[build-system]\nrequires = [\n    "a", "b",\n]\n',
        '[build-system]\nrequires = [\n    "a",\n',
        '[tool.other]\nrequires = [\n    "a",\n]\n',
        '[build-system]\nbuild-backend = "hatchling.build"\n',
    ],
    ids=[
        "inline",
        "entry on the opening line",
        "comment on an entry",
        "escape",
        "two entries to a line",
        "unterminated",
        "another table's",
        "no requires",
    ],
)
def test_a_shape_the_walk_does_not_read_is_nothing_and_not_a_part(text: str) -> None:
    """A `requires` read in part is one the file does not hold.

    The comparison below quantifies over what this returns, so a part
    would be compared as though it were the whole and the entries beyond
    it would go unchecked.
    """
    assert _build_requires(text) == []


def test_the_array_walk_reads_of_the_real_file_what_tomllib_reads() -> None:
    """The canary: this walk and a TOML parser agree on `pyproject.toml`.

    Every test above builds its own text, so none of them would notice
    the real arrays being rewritten into a shape the walk reads as a
    different list. `tomllib` answers what TOML says is there, where
    the interpreter has it.
    """
    tomllib = pytest.importorskip("tomllib")
    text = _PYPROJECT.read_text(encoding="utf-8")
    loaded = tomllib.loads(text)

    assert _build_requires(text) == loaded["build-system"]["requires"]
    assert loaded["dependency-groups"][_PYROMA_GROUP] == _PYROMA_ENVIRONMENT


def test_the_backend_is_the_requirement_whose_name_is_hatchling() -> None:
    """A name that only begins with `hatchling` is another package."""
    items = [
        "hatchling>=1.27",
        'cffi>=1.6; python_version<"3.13"',
        "hatchling-plugin>=1",
        "{hatchling: 1}",
    ]

    assert _backend(items) == ["hatchling>=1.27"]


def test_a_copy_that_lacks_or_adds_a_requirement_is_drift() -> None:
    """What differs is named, and the order a copy lists it in is not drift."""
    declared = ["hatchling>=1.27,<1.32.1", "cmake>=3.22"]

    assert _drift(declared, ["cmake>=3.22", "hatchling>=1.27,<1.32.1"]) == ""
    assert _drift(declared, ["hatchling>=1.27", "cmake>=3.22"]) == (
        "lacks ['hatchling>=1.27,<1.32.1']; adds ['hatchling>=1.27']"
    )
    assert _drift(declared, declared[:1]) == "lacks ['cmake>=3.22']"
    assert _drift(declared, [*declared, "setuptools"]) == "adds ['setuptools']"


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


def test_the_lists_compared_below_were_read() -> None:
    """A list that parsed to nothing is one both comparisons pass on.

    Two empty lists do not differ, so a `requires` that was not read, a
    hook that was renamed or one whose list moved to a shape the walk
    does not read would each leave the tests below green on nothing.
    """
    assert _BUILD_REQUIRES, "no [build-system] requires read from pyproject.toml"
    assert _backend(_BUILD_REQUIRES), "[build-system] requires names no hatchling"
    assert _CHECK_SDIST, "no additional_dependencies read for the check-sdist hook"
    assert _PYROMA_GROUP, "the pyroma hook's entry names no --only-group"
    assert _PYROMA_ENVIRONMENT, f"no requirements read for the {_PYROMA_GROUP} group"


def test_check_sdist_installs_what_build_system_requires() -> None:
    """`build --no-isolation` checks the whole of `requires` before it builds.

    The hook's environment is what it checks against, and pre-commit
    builds that environment once and keeps it: a list left behind is an
    environment `build` refuses, found by whoever next edits the list.
    """
    drift = _drift(_BUILD_REQUIRES, _CHECK_SDIST)

    assert not drift, (
        "the check-sdist hook's additional_dependencies is not"
        f" pyproject.toml's [build-system] requires: it {drift}"
    )


def test_pyroma_installs_the_backend_build_system_declares() -> None:
    """The hook's `hatchling` is `[build-system]`'s, bounds included.

    pyroma builds this project to read its metadata, and section 12 of
    the organization standard asks that a hook doing so use a backend
    the declaration admits. A hook run out of a dependency group has no
    `additional_dependencies`: the group its `entry` names is the
    environment the backend is imported from.
    """
    drift = _drift(_backend(_BUILD_REQUIRES), _backend(_PYROMA_ENVIRONMENT))

    assert not drift, (
        f"the {_PYROMA_GROUP} group's hatchling is not pyproject.toml's"
        f" [build-system] hatchling: it {drift}"
    )


def test_the_pyroma_hook_runs_the_locked_tool_and_writes_no_lock() -> None:
    """`uv run --locked` is what makes the pin the lock's and no other.

    Without `--locked` a `uv run` re-resolves a lock that no longer
    matches `pyproject.toml` and writes the answer into the tree, which
    a gate that only reads must not leave behind. The command runs
    `pyroma`, and the group it runs out of holds a requirement for it.
    """
    words = _PYROMA_ENTRY.split()

    assert words[:2] == ["uv", "run"], _PYROMA_ENTRY
    assert "--locked" in words, _PYROMA_ENTRY
    assert "pyroma" in words, _PYROMA_ENTRY
    assert any(
        requirement.name == "pyroma"
        for requirement in map(_read, _PYROMA_ENVIRONMENT)
        if requirement is not None
    ), f"the {_PYROMA_GROUP} group holds no pyroma"


def test_the_pyroma_hook_asks_for_the_rating_the_workflows_ask_for() -> None:
    """The hook takes `--min=10`, the rating its workflows hold pyroma to.

    A hook that drops the flag runs pyroma with its own default minimum,
    which a tree short of one field can pass. `test.yml` and
    `deps-latest.yml` ask the same tool for 10, and the hook is that gate
    run before a commit. The flag is read as `--min=10`, the spelling the
    hook writes.
    """
    args = _hook_args(_CONFIG.read_text(encoding="utf-8"), "pyroma")

    assert "--min=10" in args, args
