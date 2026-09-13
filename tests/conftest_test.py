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

The guard beside it is driven the same way, with one exception: the run
it refuses cannot be the run reporting on it either, so the case it
exists for is taken in a subprocess started from `tests/`.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from tests.conftest import (
    SELECTING_OPTIONS,
    CoverageConfiguration,
    configuration_went_unread,
    coverage_configuration,
    coverage_fail_under,
    pytest_configure,
)

_ROOT = Path(__file__).parents[1]
# what pytest reads its own configuration from here, which the guard
# compares against what coverage read and the message names
_INIPATH = _ROOT / "pyproject.toml"
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
        "help": False,
        "collectonly": False,
    }
    return argparse.Namespace(**(bare | asked))


def _cov_config(config_file: str | None) -> CoverageConfiguration:
    """Build what the guard reads of coverage's own configuration.

    Args:
        config_file: the file coverage took its settings from, `None`
            where it took them from none.

    Returns:
        A stand-in carrying that one attribute.
    """
    return cast("CoverageConfiguration", SimpleNamespace(config_file=config_file))


def _config(
    option: argparse.Namespace,
    known: argparse.Namespace,
    controller: object | None,
) -> pytest.Config:
    """Build what `pytest_configure` reads of a `pytest.Config`.

    Building the real thing means starting a second pytest inside this
    one, so what the hook reads of one is stood in for instead.

    Args:
        option: what the command line and `addopts` asked for.
        known: the copy pytest-cov holds and reads the threshold from.
        controller: pytest-cov's own controller, `None` under
            `--no-cov`.

    Returns:
        The stand-in the hook is driven with.
    """
    plugin = SimpleNamespace(cov_controller=controller)
    return cast(
        "pytest.Config",
        SimpleNamespace(
            known_args_namespace=known,
            option=option,
            getini=lambda _name: _TESTPATHS,
            rootpath=_ROOT,
            inipath=_INIPATH,
            pluginmanager=SimpleNamespace(getplugin=lambda _name: plugin),
        ),
    )


def _controller(config_file: str | None) -> object:
    """Build the controller pytest-cov leaves on its plugin.

    Args:
        config_file: the file coverage took its settings from.

    Returns:
        A stand-in reachable by the attribute path the hook walks.
    """
    return SimpleNamespace(cov=SimpleNamespace(config=_cov_config(config_file)))


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


def test_a_parent_directory_segment_names_the_whole_suite_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`..` survives into the path object, so the command line resolves.

    `.` and the trailing separator are collapsed as the path is built,
    which is why they sit in
    `test_a_path_that_collects_the_suite_is_a_whole_run` and this is its
    own case: a `..` segment is kept instead, so `tests/../tests` and
    `tests` are two objects that compare unequal until the command
    line's side is resolved. Both spellings here collect the suite, and
    with the call on `given` gone each reads as a selection and is gated
    at nothing. Neither asks for a symlink or a privilege.

    The second is spelled from `tests/`, and that is the case pinning
    which directory the command line is read against: a positional
    argument is joined onto the directory pytest was invoked from and a
    `testpaths` entry onto the rootdir, so a `given` built from
    `rootpath` instead answers `../tests` with the directory above the
    tree. No other test in the suite tells that rewrite from the call.
    """
    monkeypatch.chdir(_ROOT)
    re_entering_the_directory = coverage_fail_under(
        100.0, _options(file_or_dir=["tests/../tests"]), *_ARGS
    )
    assert re_entering_the_directory == 100.0
    monkeypatch.chdir(_ROOT / "tests")
    from_the_tests_directory = coverage_fail_under(
        100.0, _options(file_or_dir=["../tests"]), *_ARGS
    )
    assert from_the_tests_directory == 100.0


# the pragma sits on the `def` because an exclusion on a line that
# introduces a block takes the whole block: this case's body is reachable
# only where the platform makes a symbolic link, so a floor over a
# `source` naming `tests` asks about the runner rather than about the
# suite. An exclusion on the `except` reaches the handler and the
# `pytest.skip` alone, which are the lines that do not run wherever the
# link is made, and the platform the guard is for then meets a skip and a
# floor it cannot reach in the same run. What it costs is that dead code
# inside the case stops being flagged; the case's assertions are its
# whole subject, so the trade is cheap and is still a trade.
def test_a_symlinked_spelling_of_one_tree_is_still_the_whole_suite(  # pragma: no cover -- the body needs a symlink
    tmp_path: Path,
) -> None:
    """Both sides are resolved, so one directory named twice is one path.

    A path on the command line and a `testpaths` entry joined onto the
    rootdir can each be spelled through a symlink -- `/tmp` is one on
    macOS, and a checkout under a linked home is another. pytest builds
    `rootpath` with `os.path.abspath`, which leaves the link alone, so
    the two sides meet only once `Path.resolve` has followed it:
    unresolved on one side, `/tmp/...` neither equals `/private/tmp/...`
    nor is above it, and the run that collects everything is gated at
    nothing.

    One assertion per call, and neither stands in for the other: the
    first fails with the command line's own call gone and passes with
    the `testpaths` side's gone, the second the other way round. This
    case is also what reaches a rewrite making the path absolute without
    following a link, which the `..` above leaves green.

    The link is made here rather than taken from the machine, so what
    the case is about is the comparison and not which directories an
    operating system happens to link. Creating one on Windows takes a
    privilege a runner need not hold, so a platform that refuses says so
    as a skip, which `-ra` reports.
    """
    base = tmp_path.resolve()
    real = base / "real"
    (real / "tests").mkdir(parents=True)
    link = base / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError as refused:
        pytest.skip(f"this platform will not create a symlink: {refused}")
    named_through_the_link = coverage_fail_under(
        100.0, _options(file_or_dir=[str(link / "tests")]), _TESTPATHS, real
    )
    assert named_through_the_link == 100.0
    rootdir_through_the_link = coverage_fail_under(
        100.0, _options(file_or_dir=[str(real / "tests")]), _TESTPATHS, link
    )
    assert rootdir_through_the_link == 100.0


def test_a_testpaths_entry_is_the_directory_its_parent_segment_reaches(
    tmp_path: Path,
) -> None:
    """`tests/../src` is `src`, which a command line naming `tests` misses.

    `pathlib` keeps a parent-directory segment where it collapses `.`
    and a trailing separator, so the unresolved join carries `..` into a
    path whose parents include the directory that segment left: `tests`
    then reads as above `tests/../src`, and a run collecting nothing of
    `src` is handed the whole suite's ratchet. Resolving the join makes
    the entry the directory it reaches, which `tests` is not above.

    That is the `testpaths` side's second reason to resolve, the first
    being the symlinked spelling named in `asks_for_everything`'s own
    docstring. This one asks for no symlink and no privilege. A `..` that
    re-enters the directory it left -- `tests/../tests` -- cannot see
    it: the unresolved target then has more parents and the command
    line's path is one of them, so containment answers the same with
    the call and without it.
    """
    # both sides are spelled from the same base, so the `..` is the only
    # difference between them and the case cannot pass for a second
    # reason
    base = tmp_path.resolve()
    entry_that_leaves_the_directory = coverage_fail_under(
        100.0, _options(file_or_dir=[str(base / "tests")]), ["tests/../src"], base
    )
    assert entry_that_leaves_the_directory == 0


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

    The configuration is a stand-in rather than a real `Config`, for
    the reason `_config` gives, and it carries a coverage configuration
    read from a file so that the guard beside the threshold stays out
    of what this case is about.
    """
    option = _options(file_or_dir=["tests/keys_test.py"])
    known = argparse.Namespace(cov_fail_under=100.0)
    config = _config(option, known, _controller(str(_INIPATH)))
    monkeypatch.chdir(_ROOT)

    pytest_configure(config)

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


def test_a_run_coverage_read_a_configuration_for_is_not_refused() -> None:
    """Verify the guard is silent where the configuration reached it.

    The gate itself is this case -- `uv run pytest` from the rootdir,
    where coverage reads `pyproject.toml` -- so a guard firing here
    would refuse the run it exists to protect.
    """
    assert not configuration_went_unread(
        _cov_config(str(_INIPATH)), _INIPATH, _options()
    )


def test_a_run_coverage_read_no_configuration_for_is_refused() -> None:
    """Verify a run held to a floor it cannot see is refused.

    This is the defect the guard is for: coverage looks for its
    configuration in the directory the process started in, so from
    `tests/` it finds no `fail_under`, no `source` and no
    `branch = true`, which leaves the run measuring a different set of
    files against nothing (btclib-org/.github#443). pytest reads its
    own configuration all the same, and that asymmetry is what the
    guard keys on.
    """
    assert configuration_went_unread(_cov_config(None), _INIPATH, _options())


@pytest.mark.parametrize(
    "asked",
    [
        {"file_or_dir": ["keys_test.py"]},
        {"keyword": "compressed"},
        {"markexpr": "not slow"},
        {"lf": True},
    ],
    ids=["one file", "-k", "-m", "--lf"],
)
def test_a_selection_is_refused_the_same_way(asked: dict[str, object]) -> None:
    """Verify asking for less does not excuse the configuration missing.

    A selective run is gated at zero by the threshold above, so nothing
    was taken from it -- but `source` and `branch = true` went unread as
    well, and its report is a measurement of a different set of files.
    Iterating on one module from inside `tests/` reads a percentage
    that is not about this tree, which is what the guard says instead.
    """
    assert configuration_went_unread(_cov_config(None), _INIPATH, _options(**asked))


def test_nothing_measuring_is_not_an_ungated_run() -> None:
    """Verify `--no-cov` is left alone.

    Section 8 of the organization standard has a platform sentinel pass
    it, and a run measuring no coverage has no configuration to be
    missing.
    """
    assert not configuration_went_unread(None, _INIPATH, _options())


def test_an_explicit_threshold_is_not_overruled_by_the_guard() -> None:
    """Verify `--cov-fail-under` outranks the guard as it does the hook.

    The standard has the hook never overruling a caller who named the
    threshold, and the guard is that same hook: what it exists to catch
    is a floor going off with nobody having asked, which is not what a
    named one is. Zero is a threshold somebody asked for, so it has to
    survive the `is not None` test rather than be read as falsy.
    """
    assert not configuration_went_unread(
        _cov_config(None), _INIPATH, _options(cov_fail_under=0)
    )


@pytest.mark.parametrize("asked", [{"help": True}, {"collectonly": True}])
def test_a_run_no_floor_applies_to_is_not_refused(asked: dict[str, object]) -> None:
    """Verify the two runs pytest-cov never gates are left alone.

    `--help` exits before a session, and pytest-cov never fails a
    `--collect-only` run on the floor whatever its report prints;
    refusing either would answer a question about a floor neither is
    held to.
    """
    assert not configuration_went_unread(_cov_config(None), _INIPATH, _options(**asked))


def test_without_a_configuration_pytest_read_there_is_nothing_to_name() -> None:
    """Verify the guard needs pytest's own answer, not only coverage's.

    What the message tells a reader is where the configuration pytest
    found is, so a run that found none leaves it with nothing to say;
    and the two tools finding none alike is no asymmetry to report.
    """
    assert not configuration_went_unread(_cov_config(None), None, _options())


def test_no_pytest_cov_plugin_is_nothing_measuring() -> None:
    """Verify a run without the plugin registered reads as unmeasured.

    pytest-cov registers its plugin only where a `--cov` reached the
    parser, from `addopts` here rather than from a command line, and
    `getplugin` hands back `None` where none did.
    """
    config = cast(
        "pytest.Config",
        SimpleNamespace(pluginmanager=SimpleNamespace(getplugin=lambda _name: None)),
    )
    assert coverage_configuration(config) is None


def test_no_cov_leaves_the_controller_unbuilt() -> None:
    """Verify the plugin without a controller reads as unmeasured too.

    `--no-cov` returns from `CovPlugin.__init__` before `start()`, so
    the plugin is registered and its `cov_controller` is still `None`:
    the same `getattr` default answers for that and for no plugin.
    """
    assert coverage_configuration(_config(_options(), _options(), None)) is None


def test_the_configuration_is_the_controllers_own() -> None:
    """Verify the attribute path to coverage's configuration.

    The hook is keyed on a path through pytest-cov it does not own:
    the plugin under `_cov`, its `cov_controller`, that controller's
    `cov` and the `config` on it. Renaming either of the first two
    reads as nothing measuring and leaves the guard silent, which is
    the direction that fails without saying so; renaming what is below
    them raises instead.
    """
    config = _config(_options(), _options(), _controller("/somewhere/setup.cfg"))
    measuring = coverage_configuration(config)

    assert measuring is not None
    assert measuring.config_file == "/somewhere/setup.cfg"


def test_the_guards_own_names_are_ones_pytest_fills_in(
    pytestconfig: pytest.Config,
) -> None:
    """Verify `help` and `collectonly` are still pytest's own spellings.

    The guard reads them as attributes rather than with a default,
    both being pytest's own rather than a plugin's, so a rename is an
    `AttributeError` in `pytest_configure` and not a silent refusal.
    This run's own configuration is what says they are still there.
    """
    absent = [
        name
        for name in ("help", "collectonly")
        if not hasattr(pytestconfig.option, name)
    ]
    assert not absent, f"pytest no longer fills in {absent}"


def test_the_hook_refuses_a_run_that_cannot_see_its_floor() -> None:
    """Verify `pytest_configure` raises, and what the message names.

    The function above decides; this is what wires it to a run.
    `pytest.UsageError` is what pytest prints without a traceback and
    exits `4` for, so the exit code says the run measured nothing
    rather than that something in the tree failed. The message carries
    both paths because the asymmetry is the finding: naming only the
    directory the run started in would leave a reader to guess which
    configuration was meant.
    """
    known = argparse.Namespace(cov_fail_under=0.0)
    config = _config(_options(), known, _controller(None))

    with pytest.raises(pytest.UsageError) as raised:
        pytest_configure(config)

    assert str(_INIPATH) in str(raised.value)
    assert str(_ROOT) in str(raised.value)
    # --cov-config is named with what it does not restore and never on
    # its own: a reader sent to it alone gets a run held to the floor
    # over fewer files, which is what this message opens by naming
    assert "--cov-config restores the floor and not the file set" in str(raised.value)
    # the raise is ahead of the write, so the copy pytest-cov reads is
    # left holding what pytest-cov itself put there
    assert known.cov_fail_under == 0.0


def test_a_run_started_from_tests_says_it_is_ungated(tmp_path: Path) -> None:
    """Verify the guard stops a real run started from `tests/`.

    Everything above is the decision driven as a function; this is the
    invocation the issue is about, and the only case that says the two
    are wired together -- that `tests/conftest.py` is loaded at all on
    such a run, and that what it raises reaches whoever typed it. The
    run costs no collection: `pytest_configure` is ahead of it, so the
    subprocess is refused before it imports a test module.

    `COVERAGE_FILE` is redirected because pytest-cov erases the data
    file it is pointed at as it starts, absent `--cov-append`, which
    would otherwise destroy the data file of the run reading this.
    """
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment["COVERAGE_FILE"] = str(tmp_path / "coverage-data")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
        cwd=_ROOT / "tests",
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == pytest.ExitCode.USAGE_ERROR
    # pytest writes a usage error to stderr, where nothing of the run's
    # own output is, so the assertion is on the stream that carries it
    assert "coverage read no configuration" in completed.stderr
    assert str(_ROOT) in completed.stderr
