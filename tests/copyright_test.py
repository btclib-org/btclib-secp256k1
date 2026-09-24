# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""LICENSE, COPYRIGHT and pyproject.toml, checked against each other.

A sibling repository's own LICENSE named "Ferdinando M. Ametrano and
btclib contributors" for years after the rest of that project had
moved to "The btclib developers", with nothing comparing the two
(btclib-org/btclib#389). LICENSE here named "Giacomo Caironi" the same
way, against this project's own COPYRIGHT and `authors` already saying
"The btclib developers" -- caught by hand, not by a check, which is what
this one is.

`[tool.ruff.lint.flake8-copyright]`'s `notice-rgx` is COPYRIGHT's text
transcribed by hand as a regex, and the CPY hook it configures checks
every source file's header against the regex rather than against the
file it was transcribed from: a COPYRIGHT edited without the regex, or
the other way round, passes every gate (btclib-org/.github#135).
"""

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_PYPROJECT = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
# the holder line, with no year group to make a range optional: section
# 14 of the organization standard has LICENSE name the holder and no
# range, so a year left in the file is read as part of the holder here
# and disagrees with `authors`, which is the direction that reports it
# rather than tolerating it
_HOLDER_RE = r"Copyright \([Cc]\) (.+)"
# the regex metacharacters notice-rgx itself has to escape to stay a
# literal match for COPYRIGHT's text: this is deliberately narrower than
# `re.escape`, whose own special-character set is the same across every
# CPython and PyPy version this package supports (verified against
# 3.15.0b4 too) but is unconditionally wider than what
# notice-rgx actually escapes -- it also escapes "#" and whitespace, for
# re.VERBOSE safety, which the committed notice-rgx does not. A
# derivation through re.escape would fail this test's round trip on
# every interpreter alike, not on some of them; the mismatch is with
# notice-rgx's own narrower escaping, not with Python's version history
_REGEX_SPECIAL_RE = re.compile(r"([\\^$.|?*+()\[\]{}])")


def _license_holder() -> str:
    text = (_ROOT / "LICENSE").read_text(encoding="utf-8")
    match = re.search(_HOLDER_RE, text)
    assert match, f"LICENSE has no 'Copyright (c) holder' line: {text[:80]!r}"
    return match.group(1)


def _pyproject_author() -> str:
    return str(_PYPROJECT["project"]["authors"][0]["name"])


def _pyproject_notice_rgx() -> str:
    return str(_PYPROJECT["tool"]["ruff"]["lint"]["flake8-copyright"]["notice-rgx"])


def _copyright_as_regex() -> str:
    text = (_ROOT / "COPYRIGHT").read_text(encoding="utf-8")
    escaped = _REGEX_SPECIAL_RE.sub(r"\\\1", text.rstrip("\n"))
    # `(#![^\n]*\n)?` ahead of the notice means only a `#!` line may
    # precede it, matching pyproject.toml's own notice-rgx comment
    return r"^(#![^\n]*\n)?" + escaped.replace("\n", "\\n")


def test_license_holder_matches_the_declared_author() -> None:
    """The wheel's `Author` metadata is the same holder LICENSE names."""
    license_holder = _license_holder()
    author = _pyproject_author()
    assert license_holder == author, (
        f"LICENSE names {license_holder!r}, pyproject.toml's author "
        f"{author!r}. A wheel built from one and read from the other "
        "would disagree about who holds the copyright"
    )


def test_notice_rgx_is_copyright_transcribed() -> None:
    """`notice-rgx` is COPYRIGHT, regex-escaped, after an optional `#!` line."""
    notice_rgx = _pyproject_notice_rgx()
    derived = _copyright_as_regex()
    assert notice_rgx == derived, (
        f"pyproject.toml's notice-rgx is {notice_rgx!r}, which COPYRIGHT's "
        f"own text does not derive: expected {derived!r}. Every source "
        "header is checked against notice-rgx and not against COPYRIGHT "
        "itself, so a drift between the two passes CPY either way"
    )
