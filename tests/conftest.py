# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The threshold a run is held to, which is not the same for every run.

`--cov` is in `addopts`, so the ratchet in `[tool.coverage.report]` is
what a bare `uv run pytest` measures rather than something the coverage
job of `test.yml` alone reaches. What that costs is this file:
`fail_under` applies to every report coverage writes, a partial one
included, so `pytest tests/keys_test.py` would end in `Required test
coverage of 100.0% not reached` -- true of that run and saying nothing
about the tree. A gate whose red cannot be read is what teaches whoever
runs it to reach for `--no-cov`, so a run that asked for less than the
suite is gated at zero instead, and its report still prints.

The second thing here is a guard on that threshold reaching the run at
all. coverage looks for its configuration in the directory the process
started in, so a run started from `tests/` finds no `fail_under`, no
`source` and no `branch = true`. Section 8 of the organization standard
leaves a tree to point such a run at its configuration or to make it say
it is ungated, and this file is the second of the two: such a run is
refused (btclib-org/.github#443).

The last thing here is the fixture `scan_python_calls`, shared by the tests
of Silent Payments scanning. It is why this file imports the built package
when pytest collects it.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Protocol

import pytest

from btclib_secp256k1 import lib, silentpayments

# what section 8 of the organization standard counts as asking for less
# than the suite, beside a path that leaves part of it out: `-k`, `-m`,
# `--deselect`, `--ignore`, `--ignore-glob` and `--lf`, spelled as
# pytest's own parser stores them. A run of any of them measures the
# same source with fewer tests, so what its report is short of is the
# tests it did not run. An early `-x` is outside the set, what cuts that
# run short being a failure rather than what the invocation asked for.
# `--lf` is `lf`, `--last-failed` being the long spelling of one option;
# it is absent from the namespace under `-p no:cacheprovider`, which is
# why these are read with a default rather than as attributes
SELECTING_OPTIONS = ("keyword", "markexpr", "deselect", "ignore", "ignore_glob", "lf")


def asks_for_everything(
    file_or_dir: list[str] | None, testpaths: list[str], rootpath: Path
) -> bool:
    """Return whether the paths on the command line take the suite in.

    No path at all narrows nothing. A path at or above every `testpaths`
    entry collects it too, so what decides is containment and not
    equality: `pytest tests` is what a bare run already collects, and a
    hook reading any path as a subset switches the floor off for the run
    that is the suite (btclib-org/.github#430). `./tests` and `tests/`
    are that same directory under another name, and `.` is above it.

    The two sides are relative to different directories -- a path on the
    command line to where pytest was run from, a `testpaths` entry to
    the rootdir, which is what `testpaths` means -- and both are
    resolved: pytest builds `rootpath` with `os.path.abspath`, which
    leaves a symlink alone where `Path.resolve` follows one, so a tree
    reached through `/tmp` on macOS would compare `/tmp/...` against
    `/private/tmp/...` and find containment nowhere.

    Args:
        file_or_dir: the paths the command line named, `None` on the
            `--help` path, where pytest's `HelpAction` raises to skip
            the rest of the parse and leaves the positional at
            argparse's own default.
        testpaths: the `testpaths` of `[tool.pytest.ini_options]`.
        rootpath: the rootdir, which `testpaths` is relative to.

    Returns:
        Whether every `testpaths` entry is at or below a named path.
    """
    given = [Path(path).resolve() for path in file_or_dir or []]
    if not given:
        return True
    wanted = [(rootpath / path).resolve() for path in testpaths]
    if not wanted:
        # `all` over nothing is true, which would read every path named
        # here as the whole suite. With `testpaths` unset there is
        # nothing to measure containment against, so this errs toward
        # dropping the floor rather than gating a run it cannot call
        # whole
        return False
    return all(
        any(target == path or path in target.parents for path in given)
        for target in wanted
    )


def coverage_fail_under(
    configured: float | None,
    options: argparse.Namespace,
    testpaths: list[str],
    rootpath: Path,
) -> float | None:
    """Return the threshold this run's selection has to meet.

    A whole run is handed back `configured`, the threshold pytest-cov
    has already read out of the coverage configuration, so
    `pyproject.toml` stays the one place the number lives. A selective
    run is gated at zero rather than having coverage switched off, which
    is what keeps the report worth reading while iterating on one
    module.

    The two thresholds are two arguments because by the time this runs
    they no longer agree. pytest-cov fills `cov_fail_under` from the
    coverage configuration in `pytest_load_initial_conftests`, before
    `pytest_configure`, so "the option is set" has stopped meaning
    "somebody asked for it": what still means that is `config.option`,
    which carries only what the command line and `addopts` put there. An
    explicit `--cov-fail-under` is therefore handed back untouched
    whichever kind of run it is -- the caller naming the threshold is
    the one thing this must not overrule, and
    `git grep cov-fail-under -- .github/workflows/` finds the runs that
    ask for it.

    Args:
        configured: what pytest-cov read out of the coverage
            configuration, which is `fail_under`.
        options: `config.option`, i.e. what the command line and
            `addopts` asked for.
        testpaths: the `testpaths` of `[tool.pytest.ini_options]`.
        rootpath: the rootdir, which `testpaths` is relative to.

    Returns:
        The threshold, or `None` where the configuration named none.
    """
    # annotated because the namespace hands back `Any`, and a return of
    # that is what mypy's --strict refuses here
    asked: float | None = options.cov_fail_under
    if asked is not None:
        return asked
    if any(getattr(options, name, None) for name in SELECTING_OPTIONS):
        return 0
    if not asks_for_everything(options.file_or_dir, testpaths, rootpath):
        return 0
    return configured


class CoverageConfiguration(Protocol):
    """What this file reads of coverage's own configuration object.

    `config_file` is the file coverage took its settings from, and
    `None` where it took them from none: coverage sets it as it reads a
    file, so the attribute is the run's own answer to whether the
    configuration reached it, rather than an inference from a value
    that reached it.
    """

    config_file: str | None


def coverage_configuration(config: pytest.Config) -> CoverageConfiguration | None:
    """Return the configuration coverage is measuring with, or `None`.

    `None` is the two ways there is nothing to ask about: `--no-cov`,
    where pytest-cov registers its plugin and returns from `__init__`
    with the controller left unbuilt, and a run whose plugin was never
    registered, where `getplugin` hands back `None` and the same
    `getattr` default answers for both.

    Args:
        config: the pytest configuration of this run.

    Returns:
        coverage's configuration, or `None` where nothing is measuring.
    """
    plugin = config.pluginmanager.getplugin("_cov")
    controller = getattr(plugin, "cov_controller", None)
    if controller is None:
        return None
    # annotated because the plugin manager hands back `Any`, and a
    # return of that is what mypy's --strict refuses here
    measuring: CoverageConfiguration = controller.cov.config
    return measuring


def configuration_went_unread(
    cov_config: CoverageConfiguration | None,
    inipath: Path | None,
    options: argparse.Namespace,
) -> bool:
    """Return whether a run held to the floor cannot see one.

    A guard and not a sentence in `CONTRIBUTING.md`. What it catches is
    a plausible spelling switching the floor off, and a reader told to
    start from the root is not the run that does not: the sentence
    leaves the same failure, with somebody having been told about it.

    What it compares is not the threshold. `pyproject.toml` is the one
    place the number lives, and a `== 100` here would be the second, so
    what decides is whether coverage read a file at all against whether
    pytest read one -- the asymmetry the defect leaves behind, pytest
    walking up from where it was invoked to find its configuration and
    coverage looking only where the process started.

    Args:
        cov_config: what `coverage_configuration` answered.
        inipath: `config.inipath`, the configuration pytest read.
        options: `config.option`, i.e. what the command line and
            `addopts` asked for.

    Returns:
        Whether this run is held to a floor it cannot see.
    """
    if cov_config is None:
        return False
    if options.cov_fail_under is not None:
        # section 8 of the organization standard has the hook never
        # overruling an explicit `--cov-fail-under`, and a caller who
        # named the floor has not had one taken away in silence
        return False
    if options.help or options.collectonly:
        # neither run is held to a floor to begin with: `--help` exits
        # before a session, and pytest-cov never fails a
        # `--collect-only` run on the floor whatever its report prints.
        # The pair is an enumeration rather than every run pytest-cov
        # leaves ungated, and `--markers` and `--fixtures` are refused
        # knowingly. Widening it is the rejected alternative: what
        # would decide the question is whether pytest-cov would have
        # gated this run, which is no property to read here, so a
        # longer list is the same guess under more names
        return False
    # `inipath` is what the message has to name, so a run pytest read no
    # configuration for is one this cannot tell anybody anything about
    return cov_config.config_file is None and inipath is not None


def pytest_configure(config: pytest.Config) -> None:
    """Gate a whole run at `fail_under`, and a selective one at nothing.

    The threshold is written to `known_args_namespace` and not to
    `config.option`: pytest builds the first by parsing the known
    arguments into a *copy* of the second, and pytest-cov holds on to
    that copy. Writing to `config.option` instead runs without error and
    changes nothing, the plugin never reading it back, so the run still
    fails on the whole tree's coverage.

    A run coverage's configuration never reached is refused instead,
    `pytest.UsageError` being what pytest prints without a traceback and
    exits `4` for -- an exit of its own, so the code says the run
    measured nothing rather than that something failed.

    Args:
        config: the pytest configuration of this run.
    """
    if configuration_went_unread(
        coverage_configuration(config), config.inipath, config.option
    ):
        raise pytest.UsageError(
            "coverage read no configuration, so this run is held to no floor"
            " and measures a different set of files: coverage looks only in"
            f" the directory the run started in, {Path.cwd()}, and pytest"
            f" read {config.inipath}. Run from {config.rootpath};"
            " --cov-config restores the floor and not the file set, a"
            " relative source entry being resolved against the directory"
            " the run started in."
        )
    namespace = config.known_args_namespace
    namespace.cov_fail_under = coverage_fail_under(
        namespace.cov_fail_under,
        config.option,
        config.getini("testpaths"),
        config.rootpath,
    )


@pytest.fixture
def scan_python_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the Python functions that run inside each native scan.

    `silentpayments.lib` is replaced by a proxy that wraps the call into
    `secp256k1_silentpayments_recipient_scan_outputs` in a profile hook,
    and a Python function called from there -- which is what a cffi
    callback is -- counts. The Python around the call does not.

    Args:
        monkeypatch: the fixture the proxy is installed through.

    Returns:
        One count per native scan, in the order they ran.
    """
    counts: list[int] = []

    class CountingLib:
        def __getattr__(self, name: str) -> Any:
            attribute = getattr(lib, name)
            if name != "secp256k1_silentpayments_recipient_scan_outputs":
                return attribute

            def counted(*args: Any) -> Any:
                calls = 0

                def profile(  # pragma: no cover -- a profile hook is never traced
                    _frame: object, event: str, _arg: object
                ) -> None:
                    nonlocal calls
                    if event == "call":
                        calls += 1

                sys.setprofile(profile)
                try:
                    return attribute(*args)
                finally:
                    sys.setprofile(None)
                    counts.append(calls)

            return counted

    monkeypatch.setattr(silentpayments, "lib", CountingLib())
    return counts
