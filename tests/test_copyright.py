# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""LICENSE and pyproject.toml's author, checked together.

btclib's own LICENSE named "Ferdinando M. Ametrano and btclib
contributors" for years after the rest of that project had moved to "The
btclib developers", with nothing comparing the two (btclib#389). LICENSE
here named "Giacomo Caironi" the same way, against this project's own
COPYRIGHT and `authors` already saying "The btclib developers" -- caught
by hand, not by a check, which is what this one is.

Regex rather than `tomllib` for the one line wanted out of
pyproject.toml: the floor here is 3.10, and `tomllib` is 3.11. Once that
floor moves, this can read the file directly instead.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).parents[1]
# the holder line, with no year group to make a range optional: section
# 14 of the organization standard has LICENSE name the holder and no
# range, so a year left in the file is read as part of the holder here
# and disagrees with `authors`, which is the direction that reports it
# rather than tolerating it
_HOLDER_RE = r"Copyright \([Cc]\) (.+)"
_AUTHOR_RE = r'authors\s*=\s*\[\{\s*name\s*=\s*"([^"]+)"'


def _license_holder() -> str:
    text = (_ROOT / "LICENSE").read_text(encoding="utf-8")
    match = re.search(_HOLDER_RE, text)
    assert match, f"LICENSE has no 'Copyright (c) holder' line: {text[:80]!r}"
    return match.group(1)


def _pyproject_author() -> str:
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(_AUTHOR_RE, text)
    assert match, "pyproject.toml has no 'authors = [{ name = ... }]' line"
    return match.group(1)


def test_license_holder_matches_the_declared_author() -> None:
    """The wheel's `Author` metadata is the same holder LICENSE names."""
    license_holder = _license_holder()
    author = _pyproject_author()
    assert license_holder == author, (
        f"LICENSE names {license_holder!r}, pyproject.toml's author "
        f"{author!r}. A wheel built from one and read from the other "
        "would disagree about who holds the copyright"
    )
