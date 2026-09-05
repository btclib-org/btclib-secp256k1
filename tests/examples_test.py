# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Every example in the documentation is executed.

An example nobody runs is documentation that stops being true silently,
and the README's own example was one: it sat there through five
releases with nothing to notice if the call it shows had changed shape.

`doctest` is used through the standard library rather than through
pytest's `--doctest-modules`, and the reason is what this package is.
`testpaths` is `tests`, and widening it to the package would collect the
*source* tree -- which is the right thing locally, where the extension
is an editable build of it, and the wrong thing in the wheel jobs, where
what has to be exercised is the module inside the installed wheel.
Importing the package by name gets whichever of the two is installed, on
every kind of wheel, which is the point.

The examples are therefore constrained to be deterministic: fixed keys,
and a verification rather than a signature wherever the value depends on
randomness that is not pinned.
"""

from __future__ import annotations

import doctest
import importlib
import pkgutil
from pathlib import Path

import pytest

import btclib_secp256k1

_ROOT = Path(__file__).parents[1]

# the subpackage whose examples need the flagged extension to run
_ZKP = f"{btclib_secp256k1.__name__}.zkp"


def _modules() -> list[str]:
    """Every module of the installed package, the package itself included.

    `walk_packages` descends into `zkp`, where `iter_modules` stops at
    the top package's own children and leaves a docstring under a
    subpackage collected by nothing.

    Returns:
        The dotted names, sorted, read off the imported package rather
        than off the source tree: what is documented has to be what a
        user imports.
    """
    prefix = f"{btclib_secp256k1.__name__}."
    found = pkgutil.walk_packages(btclib_secp256k1.__path__, prefix)
    return sorted([btclib_secp256k1.__name__, *(info.name for info in found)])


def _needs_the_zkp_extension(name: str) -> bool:
    """Whether this module's examples need the flagged extension to run.

    Args:
        name: the dotted name of the module.

    Returns:
        Whether it is the `zkp` subpackage or a module under it.
    """
    return name == _ZKP or name.startswith(f"{_ZKP}.")


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name, marks=[pytest.mark.zkp] if _needs_the_zkp_extension(name) else []
        )
        for name in _modules()
    ],
)
def test_the_examples_of_a_module_run(name: str) -> None:
    """Run the doctests of one module, and require that none failed.

    A module under `zkp` carries the `zkp` marker `-m zkp` selects and
    an `importorskip` that skips it where `BTCLIB_LIBSECP256K1_ZKP`
    built no extension for its examples to call into: the same pair the
    test modules under `tests/` use, and `pyproject.toml`'s comment on
    the marker says why one does not stand for the other.

    Args:
        name: the dotted name of the module.
    """
    if _needs_the_zkp_extension(name):
        pytest.importorskip("_btclib_secp256k1_zkp")
    results = doctest.testmod(importlib.import_module(name))
    assert results.failed == 0, (
        f"{results.failed} of {results.attempted} examples failed in {name};"
        " the captured output above is what doctest reported"
    )


def test_the_package_carries_examples_at_all() -> None:
    """Guard the test above against passing on a package with no examples.

    The examples are parsed and not run: the test above skips a module
    under `zkp` on an unflagged build, and running its examples here
    would be running what that skip refused. `DocTestFinder` is what
    `doctest.testmod` finds them with, so what it counts is what a
    flagged run attempts.
    """
    finder = doctest.DocTestFinder()
    examples = sum(
        len(parsed.examples)
        for name in _modules()
        for parsed in finder.find(importlib.import_module(name))
    )
    assert examples > 0, "no module of the package carries a doctest any more"


def test_the_readme_examples_run() -> None:
    """Run the quickstart, which is the README's own examples.

    The README is the documentation of this package, and the quickstart
    is the page a reader arriving from `pip install` lands on: it is
    executed here for the same reason the docstrings are.
    """
    results = doctest.testfile(
        str(_ROOT / "README.md"), module_relative=False, verbose=False
    )
    assert results.attempted > 0, "the README carries no doctest any more"
    assert results.failed == 0, (
        f"{results.failed} of {results.attempted} README examples failed;"
        " the captured output above is what doctest reported"
    )
