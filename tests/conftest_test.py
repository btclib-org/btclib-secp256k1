# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the coverage threshold `conftest.py` hands each run.

The run that reaches that hook with a subset selected is, by
construction, not the run that measures this file: a suite gated at 100%
is a whole run, and what the hook does to a partial one is invisible to
it. So the decision is driven here as a function, over the namespace
pytest's own parser fills in.

The position of `--cov` in `addopts` is here for the same reason -- it
is a property of a command line no run of that command line can report
on. `--cov` last swallows the first path the command line gives, and
what the swallowed path becomes is coverage's `source`: a module name
nothing imports, so the run collects nothing and reports zero against a
floor of 100.
"""

import argparse
import re
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from tests.conftest import SELECTING_OPTIONS, coverage_fail_under, pytest_configure

_ROOT = Path(__file__).parents[1]
# what pyproject.toml's `testpaths` holds, passed in rather than read:
# what is under test is what a command line means against a given
# `testpaths`, and reading the real one would make these a test of the
# configuration as well
_TESTPATHS = ["tests"]
# the two the cases below never vary, spelled once: what each is about
# is the namespace, and repeating the pair at every call would bury it
_ARGS = (_TESTPATHS, _ROOT)


def _options(**asked: object) -> argparse.Namespace:
    """Build what pytest's parser leaves in `config.option`.

    The defaults are what a bare run produces, so a case names the one
    flag it is about.

    Args:
        asked: the options this run named, by their pytest spelling.

    Returns:
        The namespace the hook reads.
    """
    bare: dict[str, object] = {
        "cov_fail_under": None,
        "file_or_dir": [],
        "keyword": "",
        "markexpr": "",
        "deselect": [],
        "ignore": [],
        "ignore_glob": [],
        "lf": False,
    }
    return argparse.Namespace(**(bare | asked))


def test_a_whole_run_is_gated_at_what_pyproject_configured() -> None:
    """Verify no selection is handed back the configured threshold.

    The number comes back as it was handed in, which is the property
    worth pinning: pyproject.toml is where 100 is decided, and a copy of
    it here would be a second place to change it.
    """
    assert coverage_fail_under(100.0, _options(), _TESTPATHS, _ROOT) == 100.0
    assert coverage_fail_under(42.0, _options(), _TESTPATHS, _ROOT) == 42.0


def test_an_unconfigured_threshold_stays_unset() -> None:
    """Verify `None` survives, `[tool.coverage.report]` naming none.

    Zero would be a threshold this file invented, and nothing here is
    entitled to decide that a tree without a `fail_under` has one.
    """
    assert coverage_fail_under(None, _options(), _TESTPATHS, _ROOT) is None


@pytest.mark.parametrize(
    "file_or_dir",
    [["tests"], ["./tests"], ["tests/"], ["."], [str(_ROOT)], None],
    ids=[
        "the suite",
        "./ before it",
        "trailing slash",
        "the cwd",
        "absolute",
        "--help",
    ],
)
def test_a_path_that_collects_the_suite_is_a_whole_run(
    file_or_dir: list[str] | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a path at or above `testpaths` is gated like a bare run.

    `uv run pytest tests` is what somebody types who means the whole
    suite and says so, and every path here collects exactly what a bare
    run collects. Equality against `testpaths` would take in `tests`
    alone: `./tests` and `tests/` are that same directory spelled
    otherwise, and `.` and the rootdir are above it, which is why
    containment and not equality is what decides
    (btclib-org/.github#430).

    `None` is the `--help` path, where the parse is abandoned before the
    positional is filled in; it reaches the hook like any other run, and
    answering it by iterating would be a traceback rather than a
    threshold.

    The relative spellings are read against the working directory, which
    is what pytest does with them, so the run has to be standing in the
    rootdir for them to mean the suite.
    """
    monkeypatch.chdir(_ROOT)
    assert (
        coverage_fail_under(100.0, _options(file_or_dir=file_or_dir), *_ARGS) == 100.0
    )


@pytest.mark.parametrize(
    "asked",
    [
        {"file_or_dir": ["tests/keys_test.py"]},
        {"keyword": "compressed"},
        {"markexpr": "not slow"},
        {"deselect": ["tests/keys_test.py::test_pubkey_from_prvkey"]},
        {"ignore": ["tests/keys_test.py"]},
        {"ignore_glob": ["*/keys_test.py"]},
        {"lf": True},
        {"file_or_dir": ["tests"], "keyword": "compressed"},
    ],
    ids=[
        "one file",
        "-k",
        "-m",
        "--deselect",
        "--ignore",
        "--ignore-glob",
        "--lf",
        "the suite, -k",
    ],
)
def test_a_run_that_asked_for_less_is_gated_at_nothing(
    asked: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify each of section 8's selections drops the threshold to zero.

    Zero and not `None`: `None` is what pytest-cov reads the configured
    threshold into, so it would restore the very gate this removes.

    Every one of these runs the same source with fewer tests, so what
    its report is short of is the tests it did not run and its red says
    nothing about the tree. The last case is the whole suite named
    beside a `-k`: the path takes everything in and the expression then
    selects out of it, so what decides is the selection and not the
    path.
    """
    monkeypatch.chdir(_ROOT)
    assert coverage_fail_under(100.0, _options(**asked), *_ARGS) == 0


def test_without_testpaths_a_named_path_is_a_subset() -> None:
    """Verify a path is a selection where nothing names the suite.

    A bare run then collects the rootdir, so a path on the command line
    asks for less whatever it is. `all` over an empty `testpaths` would
    answer the opposite -- every run a whole one, and the floor never
    relaxed for the one-file run it exists for.
    """
    assert coverage_fail_under(100.0, _options(file_or_dir=["tests"]), [], _ROOT) == 0


def test_an_explicit_threshold_survives_either_kind_of_run() -> None:
    """Verify `--cov-fail-under` outranks both branches.

    The caller naming a threshold is the one thing the hook must not
    overrule, and `test.yml`'s coverage job depends on that: no
    run of it reaches 100 on its own, so each asks for zero by name and
    only the union after them is gated. `coverage_fail_under`'s own
    docstring names the command that finds those runs.
    """
    subset = _options(cov_fail_under=90.0, file_or_dir=["tests/keys_test.py"])
    assert coverage_fail_under(100.0, subset, *_ARGS) == 90.0
    assert coverage_fail_under(100.0, _options(cov_fail_under=90.0), *_ARGS) == 90.0
    # zero is a threshold somebody asked for, not a missing answer, so it
    # has to survive the `is not None` test rather than be read as falsy
    assert coverage_fail_under(100.0, _options(cov_fail_under=0), *_ARGS) == 0


def test_an_option_the_run_does_not_carry_is_not_a_selection() -> None:
    """Verify a namespace missing one of the names is read as a bare run.

    `-p no:cacheprovider` takes `--lf` out of the parser, and with it
    the attribute the hook reads, so the names are read with a default
    rather than as attributes.
    """
    options = _options()
    del options.lf
    assert coverage_fail_under(100.0, options, *_ARGS) == 100.0


def test_every_selecting_option_is_a_name_pytest_fills_in(
    pytestconfig: pytest.Config,
) -> None:
    """Verify the hook's names are the ones pytest's parser stores.

    The hook is keyed on attribute names it does not own: a name pytest
    renames stops matching, and the floor then stays at 100 for a run
    that asked for less -- silently, which is what a default on the read
    costs. This run's own configuration is what says the names are still
    pytest's, `--lf` being stored as `lf` and every other one under its
    long spelling.
    """
    absent = [
        name for name in SELECTING_OPTIONS if not hasattr(pytestconfig.option, name)
    ]
    assert not absent, f"pytest no longer fills in {absent}"


def test_the_threshold_is_written_where_pytest_cov_reads_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the hook writes `known_args_namespace` and not `option`.

    Everything above drives the decision as a function, and a function
    nothing calls decides nothing: `pytest_configure` is what wires it
    to a run, and which namespace it writes is the half that fails in
    silence. pytest parses the known arguments into a *copy* of
    `config.option` and pytest-cov holds that copy, so the obvious
    spelling runs without error, changes nothing, and leaves the
    selective run failing on the whole tree's coverage.

    The configuration is a stand-in rather than a real `Config`: four
    attributes are what the hook reads of one, and building the real
    thing means starting a second pytest inside this one.
    """
    option = _options(file_or_dir=["tests/keys_test.py"])
    known = argparse.Namespace(cov_fail_under=100.0)
    config = SimpleNamespace(
        known_args_namespace=known,
        option=option,
        getini=lambda _name: _TESTPATHS,
        rootpath=_ROOT,
    )
    monkeypatch.chdir(_ROOT)

    pytest_configure(cast("pytest.Config", config))

    assert known.cov_fail_under == 0
    # the copy the command line filled is left as it was: it is what
    # says whether a threshold was asked for, and overwriting it would
    # make the next read of it answer this hook rather than the caller
    assert option.cov_fail_under is None


def test_cov_is_not_the_last_token_of_addopts() -> None:
    """Verify `addopts` carries `--cov`, and not at the end of it.

    `--cov` takes an optional value, so as the final token it is handed
    whatever the command line goes on to say: `pytest
    tests/keys_test.py` becomes `--cov=tests/keys_test.py`, which leaves
    no path to select on and makes that path coverage's `source`.
    coverage answers `Module tests/keys_test.py was never imported` and
    `No data was collected`, so the whole suite runs, the report is
    `Total coverage: 0.00%`, and the run fails the `fail_under` of 100.

    `pytest -q tests/...` hides it, a token starting with `-` not being
    consumed, so the habitual spelling is green and the documented one
    is not. Nothing about a run reports its own `addopts`, which is why
    this reads the file; the assertion is that weak on purpose, the
    order of the rest being nobody's business here.
    """
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^addopts = "(.*)"$', text, re.MULTILINE)
    assert match, "pyproject.toml has no single-line 'addopts = \"...\"'"

    addopts = match.group(1).split()
    assert "--cov" in addopts, "the local coverage gate is --cov in addopts"
    assert addopts[-1] != "--cov", (
        "--cov is the last token of addopts, so it will swallow the first "
        "positional argument of any command line that has one"
    )
