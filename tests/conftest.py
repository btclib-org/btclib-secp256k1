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
"""

import argparse
from pathlib import Path

import pytest

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


def pytest_configure(config: pytest.Config) -> None:
    """Gate a whole run at `fail_under`, and a selective one at nothing.

    The threshold is written to `known_args_namespace` and not to
    `config.option`: pytest builds the first by parsing the known
    arguments into a *copy* of the second, and pytest-cov holds on to
    that copy. Writing to `config.option` instead runs without error and
    changes nothing, the plugin never reading it back, so the run still
    fails on the whole tree's coverage.

    Args:
        config: the pytest configuration of this run.
    """
    namespace = config.known_args_namespace
    namespace.cov_fail_under = coverage_fail_under(
        namespace.cov_fail_under,
        config.option,
        config.getini("testpaths"),
        config.rootpath,
    )
