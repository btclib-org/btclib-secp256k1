# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for `.github/scripts/check_wheel_reproducibility.py`.

`diff_wheels` is exercised against archives built by hand, one member
disagreeing at a time, so that each assertion names the one thing that
changed. Both sides carry the same filename, in two directories, which
is what two builds of one commit produce and what makes the label a
caller passes -- rather than the path -- the only thing a complaint can
name the sides by. `copy_source_tree` is
exercised against real git repositories built by hand instead: what
makes `#509`'s own fix worth trusting is that a commit and an
uncommitted edit come out differently, and a mock of `subprocess.run`
cannot tell the two apart -- it would have to reimplement `git clone`
to do so, at which point the test measures the mock rather than the
script.
`build_wheel` and `main` never invoke the real `uv build`,
though: what they are asked to build is a fake, `check.subprocess.run`
replaced the way `tests/submodule_pin_test.py` and
`tests/vendored_vectors_test.py` replace it, so the suite measures this
script's plumbing rather than a real compile. The fake answers the
`git` calls too, now that `main` calls `copy_source_tree` before every
build, with a commit hash and nothing else. `python -m build` and the two
repair tools are stood in for the same way on the `--dynamic` and
`--cross-windows` paths, which is what lets a test on any machine say
which tool the script reached for.

`--across-images` needs no build at all: what it reads is a directory of
wheels two jobs already built, so its tests write that directory by hand
and the wheels in it are the same hand-built archives `diff_wheels` gets.

The script is loaded by path, `.github/scripts` being no package, as the
other scripts under it are tested.
"""

from __future__ import annotations

import importlib.util
import runpy
import shutil
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = (
    Path(__file__).parents[1] / ".github" / "scripts" / "check_wheel_reproducibility.py"
)
# resolved once, the same way check_wheel_reproducibility.py itself
# resolves it, so a bare "git" in a subprocess list is never what makes
# this file's own real-git tests trip ruff's S607
_GIT = shutil.which("git") or "git"
# what two builds of one commit call the wheel, and what these tests
# call it on both sides of a comparison unless the filename is the
# subject
_WHEEL = "pkg-1.0-py3-none-any.whl"
# an arbitrary commit time, set for every --repaired test below since
# build_repaired_twice_and_compare refuses to run without it
_EPOCH = 1_700_000_000
# the member every wheel a build here leaves must carry, which the fake
# builds below add to what a test asks them to write
_SBOM = ("pkg-1.0.dist-info/sboms/btclib_secp256k1.cdx.json", b"{}")
# what a faked `git rev-parse HEAD` answers
_COMMIT = "c0ffee"


@pytest.fixture
def check() -> ModuleType:
    """Return the script, imported by path."""
    spec = importlib.util.spec_from_file_location(
        "check_wheel_reproducibility", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_wheel(
    path: Path,
    members: list[tuple[str, bytes]],
    *,
    date_time: tuple[int, int, int, int, int, int] = (2020, 2, 2, 0, 0, 0),
    external_attr: int = 0o644 << 16,
    compress_type: int = zipfile.ZIP_DEFLATED,
) -> None:
    """Write a wheel with exactly the given members, in the given order.

    Every member gets the same metadata unless the caller overrides it,
    which is what lets a test change one field of one member and nothing
    else. The parent directory is created, so that two wheels sharing a
    filename can be written side by side under their own directories.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.external_attr = external_attr
            info.compress_type = compress_type
            archive.writestr(info, content)


def two_wheels(
    tmp_path: Path,
    first: list[tuple[str, bytes]],
    second: list[tuple[str, bytes]],
    **kwargs: Any,
) -> tuple[Path, Path]:
    """Write one wheel per side, same filename, and return the two paths.

    `kwargs` reaches `write_wheel` for the second side alone, which is
    how a test moves one metadata field without touching the first.
    """
    paths = (tmp_path / "one" / _WHEEL, tmp_path / "other" / _WHEEL)
    write_wheel(paths[0], first)
    write_wheel(paths[1], second, **kwargs)
    return paths


def diff(check: ModuleType, first: Path, second: Path) -> list[str]:
    """Call `diff_wheels` with the labels these tests assert against."""
    complaints: list[str] = check.diff_wheels(
        first, second, first_label="one-image", second_label="other-image"
    )
    return complaints


def run_git(*args: str, cwd: Path) -> None:
    """Run git with `args` in `cwd`, raising if it exits non-zero.

    The one place this file's real-git tests shell out, so `# noqa: S603`
    is written once rather than beside every call site.
    """
    subprocess.run([_GIT, *args], cwd=cwd, check=True)  # noqa: S603


def init_repo(path: Path, files: dict[str, bytes]) -> None:
    """Stand up a real, one-commit git repository at `path`.

    Args:
        path: created if it does not exist.
        files: each path relative to `path`, and the bytes to commit there.
            Parent directories are created as needed.
    """
    path.mkdir(parents=True, exist_ok=True)
    run_git("init", "-q", "-b", "main", cwd=path)
    run_git("config", "user.email", "test@example.invalid", cwd=path)
    run_git("config", "user.name", "test", cwd=path)
    for name, content in files.items():
        file_path = path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
    run_git("add", "-A", cwd=path)
    run_git("commit", "-q", "-m", "init", cwd=path)


def dispatching_run(build_call: Any, *, out_flag: str = "--out-dir") -> Any:
    """Return a `subprocess.run` stand-in that fakes `git` calls.

    `main` now runs `copy_source_tree` -- a handful of `git` calls --
    ahead of every build, and all go through the same `subprocess.run`
    a test here replaces. The flag naming the output directory is what
    only a build call carries, so its absence is what marks a `git`
    call, answered with a commit hash rather than reaching
    `build_call`, which does not expect one; `args[0]` is not what tells
    the two apart, since it names `_GIT`'s own resolved, and possibly
    absolute, path rather than the literal string "git".

    `out_flag` is what a caller changes to fake the `--repaired` path
    instead: `uv build` takes `--out-dir` and `cibuildwheel`
    `--output-dir`, and reading the flag off the command line rather
    than assuming one is what keeps a `git` call from being
    mistaken for a build in either.
    """

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        if out_flag not in args:
            return subprocess.CompletedProcess(args, 0, stdout=_COMMIT + "\n")
        return build_call(args, **kwargs)

    return fake_run


def fake_run_writing(
    wheels: dict[str, list[tuple[str, bytes]]], *, out_flag: str = "--out-dir"
) -> Any:
    """Return a `subprocess.run` stand-in that writes a canned wheel.

    `wheels` maps a wheel's own filename to the members it should
    contain; the output directory is read out of the faked command line
    at `out_flag`, and every call writes every one of `wheels` there --
    `build_wheel`'s own "exactly one" check is what a test then leans on
    to pick one out, where `build_repaired_wheels` takes them all.
    """

    def fake_run(args: list[str], **_kwargs: Any) -> Any:
        out_dir = Path(args[args.index(out_flag) + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, members in wheels.items():
            write_wheel(out_dir / name, [*members, _SBOM])
        return None

    return fake_run


def repair_copying_the_wheel_across(record: list[list[str]]) -> Any:
    """Return a repair stand-in that records its command and copies the wheel.

    `delocate` grafts nothing into a dynamic wheel, the shared object
    being inside the archive already, so a repair that hands the same
    members back is the behaviour these tests give the script. `record`
    is what a test reads to say which tool was called, and how many
    times a repair ran at all.
    """

    def fake_run(args: list[str], **_kwargs: Any) -> None:
        record.append(args)
        out_dir = Path(args[args.index("-w") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args[-1], out_dir / Path(args[-1]).name)

    return fake_run


def dynamic_dispatching_run(build_call: Any, record: list[list[str]]) -> Any:
    """Return a `subprocess.run` stand-in for the `--dynamic` path.

    The flag naming an output directory is what tells apart the kinds
    of call that reach it there -- `--outdir` for a
    `python -m build`, `-w` for a repair, and neither for the
    `git` calls `copy_source_tree` makes, which are answered
    with a commit hash as `dispatching_run` answers them.
    """
    repair = repair_copying_the_wheel_across(record)

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        if "--outdir" in args:
            return build_call(args, **kwargs)
        if "-w" in args:
            return repair(args, **kwargs)
        return subprocess.CompletedProcess(args, 0, stdout=_COMMIT + "\n")

    return fake_run


def build_writing_in_turn(contents: list[bytes], *, out_flag: str = "--out-dir") -> Any:
    """Return a build stand-in writing a different wheel on each call.

    One entry per build, in order, so that a test says what the second
    build produces without reaching for a counter of its own.
    """
    remaining = list(contents)

    def build_call(args: list[str], **_kwargs: Any) -> None:
        out_dir = Path(args[args.index(out_flag) + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        write_wheel(out_dir / _WHEEL, [("pkg/a.py", remaining.pop(0)), _SBOM])

    return build_call


def test_copy_source_tree_clones_the_commit_with_its_submodule(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The copy is a clone of the commit, which is what holds a `.git`.

    `scripts/hatch_build.py` writes the wheel's bill of materials only
    in a tree with a `.git`, so a copy without one builds a wheel the
    release does not. The submodule is a real one, its gitlink pins the
    commit, and an uncommitted edit or an untracked file in `root`
    reaches neither the clone nor the submodule's checkout.

    The machine's git configuration is replaced by an empty one first:
    the clone is checked out under it, and the GitHub Windows images set
    `core.autocrlf` globally, which would turn the committed LF into CRLF
    and make the assertion on bytes measure the runner.
    """
    empty = tmp_path / "gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    vendored = tmp_path / "vendored"
    init_repo(vendored, {"CMakeLists.txt": b"vendored\n"})
    root = tmp_path / "root"
    init_repo(root, {"pyproject.toml": b"[project]\n"})
    run_git(
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(vendored),
        "secp256k1",
        cwd=root,
    )
    run_git("commit", "-q", "-m", "pin submodule", cwd=root)
    (root / "pyproject.toml").write_bytes(b"edited-but-not-committed")
    (root / "untracked.py").write_bytes(b"never added")
    (root / "secp256k1" / "CMakeLists.txt").write_bytes(b"edited too")

    dest = tmp_path / "dest"
    check.copy_source_tree(root, dest)

    assert (dest / ".git").exists()
    assert (dest / "pyproject.toml").read_bytes() == b"[project]\n"
    assert not (dest / "untracked.py").exists()
    assert (dest / "secp256k1" / "CMakeLists.txt").read_bytes() == b"vendored\n"
    pinned = check._git("ls-tree", "HEAD", "--", "secp256k1", cwd=dest)
    assert pinned == check._git("ls-tree", "HEAD", "--", "secp256k1", cwd=root)
    assert pinned.startswith("160000 commit ")


def test_build_wheel_returns_the_one_wheel_uv_left(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success path: one call, one wheel, its path comes back."""
    monkeypatch.setattr(
        check.subprocess, "run", fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})
    )

    wheel = check.build_wheel(tmp_path / "source", tmp_path / "out")

    assert wheel == tmp_path / "out" / _WHEEL


def test_build_wheel_constrains_the_build_requirements(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv build` reads the copy's constraints, as the shipped build does."""
    seen: dict[str, Any] = {}
    write = fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})

    def spy(args: list[str], **kwargs: Any) -> None:
        seen["env"] = kwargs["env"]
        write(args, **kwargs)

    monkeypatch.setattr(check.subprocess, "run", spy)
    monkeypatch.setenv("A_VARIABLE_THE_BUILD_INHERITS", "kept")

    check.build_wheel(tmp_path / "source", tmp_path / "out")

    assert seen["env"]["UV_BUILD_CONSTRAINT"] == str(
        tmp_path / "source" / "build-constraints.txt"
    )
    assert seen["env"]["A_VARIABLE_THE_BUILD_INHERITS"] == "kept"


def test_build_wheel_refuses_an_empty_out_dir(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv build` leaving nothing behind is named, not `KeyError`'d."""
    monkeypatch.setattr(check.subprocess, "run", fake_run_writing({}))

    with pytest.raises(RuntimeError, match="expected exactly one wheel"):
        check.build_wheel(tmp_path / "source", tmp_path / "out")


def test_build_wheel_refuses_a_wheel_without_a_bill_of_materials(
    check: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A build that wrote no document fails, and one that did names it.

    Two builds without a `.git` agree with each other, so the comparison
    alone would pass them; this is what turns that into a failure.
    """

    def build(args: list[str], **_kwargs: Any) -> None:
        out_dir = Path(args[args.index("--out-dir") + 1])
        write_wheel(out_dir / _WHEEL, [("pkg/a.py", b"x")])

    monkeypatch.setattr(check.subprocess, "run", build)
    with pytest.raises(RuntimeError, match="no bill of materials"):
        check.build_wheel(tmp_path / "source", tmp_path / "out")

    monkeypatch.setattr(
        check.subprocess, "run", fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})
    )
    check.build_wheel(tmp_path / "source", tmp_path / "out-with")
    assert capsys.readouterr().out.endswith(f"carries {_SBOM[0]}\n")


def test_build_wheel_refuses_more_than_one_wheel(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale wheel sharing the directory is named rather than picked."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing({
            _WHEEL: [("pkg/a.py", b"x")],
            "pkg-0.9-py3-none-any.whl": [("pkg/a.py", b"x")],
        }),
    )

    with pytest.raises(RuntimeError, match="expected exactly one wheel"):
        check.build_wheel(tmp_path / "source", tmp_path / "out")


def test_build_repaired_wheels_returns_every_wheel_cibuildwheel_left(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """More than one wheel is the ordinary Linux answer, not a failure.

    `build_wheel` refuses a second wheel because `uv build` writing two
    means a stale one shared the directory; one `cibuildwheel` run of
    one interpreter writes a `manylinux` wheel and a `musllinux` one,
    so here both come back.
    """
    musl = "pkg-1.0-cp314-cp314-musllinux_1_2_x86_64.whl"
    many = "pkg-1.0-cp314-cp314-manylinux_2_17_x86_64.whl"
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing(
            {musl: [("pkg/a.py", b"x")], many: [("pkg/a.py", b"x")]},
            out_flag="--output-dir",
        ),
    )

    wheels = check.build_repaired_wheels(tmp_path / "source", tmp_path / "out")

    assert [wheel.name for wheel in wheels] == sorted([many, musl])


def test_build_repaired_wheels_runs_in_the_directory_it_builds(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cibuildwheel refuses a package directory outside its own cwd.

    So the package argument is `.` and the working directory is the
    copy, rather than the copy's path being passed from the checkout
    the environment was built in.
    """
    seen: dict[str, Any] = {}

    def spy(args: list[str], **kwargs: Any) -> None:
        seen["args"] = args
        seen["cwd"] = kwargs["cwd"]
        out_dir = Path(args[args.index("--output-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        write_wheel(out_dir / _WHEEL, [("pkg/a.py", b"x"), _SBOM])

    monkeypatch.setattr(check.subprocess, "run", spy)

    check.build_repaired_wheels(tmp_path / "source", tmp_path / "out")

    assert seen["cwd"] == tmp_path / "source"
    assert seen["args"][-1] == "."


def test_build_repaired_wheels_refuses_an_empty_out_dir(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cibuildwheel exiting zero with nothing built is named, not indexed."""
    monkeypatch.setattr(
        check.subprocess, "run", fake_run_writing({}, out_flag="--output-dir")
    )

    with pytest.raises(RuntimeError, match="left no wheel"):
        check.build_repaired_wheels(tmp_path / "source", tmp_path / "out")


def test_build_dynamic_wheel_carries_the_linkage_its_environment_names(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The variable selecting the linkage reaches the build, not the caller.

    A run without it builds the static wheel, which would agree with
    itself and report green on a question nothing had asked.
    """
    seen: dict[str, Any] = {}

    def spy(args: list[str], **kwargs: Any) -> None:
        seen["args"] = args
        seen["cwd"] = kwargs["cwd"]
        seen["env"] = kwargs["env"]
        out_dir = Path(args[args.index("--outdir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        write_wheel(out_dir / _WHEEL, [("pkg/a.py", b"x"), _SBOM])

    monkeypatch.setattr(check.subprocess, "run", spy)
    monkeypatch.setenv("A_VARIABLE_THE_BUILD_INHERITS", "kept")

    wheel = check.build_dynamic_wheel(
        tmp_path / "source", tmp_path / "out", check._CROSS_WINDOWS_ENV
    )

    assert wheel.name == _WHEEL
    assert seen["cwd"] == tmp_path / "source"
    assert seen["args"][1:3] == ["-m", "build"]
    assert seen["env"]["BTCLIB_LIBSECP256K1_CROSS_COMPILE"] == "true"
    assert seen["env"]["CFFI_PLATFORM"] == "Windows"
    assert seen["env"]["A_VARIABLE_THE_BUILD_INHERITS"] == "kept"
    assert seen["env"]["PIP_CONSTRAINT"] == str(
        tmp_path / "source" / "build-constraints.txt"
    )


def test_repair_wheel_runs_delocate_on_macos(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`build-dynamic` repairs a macOS wheel with delocate, so this does.

    Two assertions, because there are two things to get wrong and one
    of them is invisible to the other. Which branch ran is the constant
    the argument list was built from, and the two constants differ
    whether they resolved or fell back to their own literals. Which
    tool that constant names is the stem, and it is asked for
    separately because both sides of the first comparison come from the
    same module: definitions swapped between them would satisfy it.

    Neither reads the whole of `shutil.which`'s answer, which is a path
    where the tool is installed and a bare name where it is not, and on
    Windows carries a `.EXE` the stem drops.
    """
    monkeypatch.setattr(check.sys, "platform", "darwin")
    built = tmp_path / "out" / _WHEEL
    write_wheel(built, [("pkg/a.py", b"x"), _SBOM])
    record: list[list[str]] = []
    monkeypatch.setattr(
        check.subprocess, "run", repair_copying_the_wheel_across(record)
    )

    repaired = check.repair_wheel(built, tmp_path / "repaired")

    assert repaired == tmp_path / "repaired" / _WHEEL
    assert record[0][0] == check._DELOCATE
    assert Path(check._DELOCATE).stem.lower() == "delocate-wheel"


def test_repair_wheel_runs_auditwheel_off_macos(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And with auditwheel everywhere else, which there means Linux."""
    monkeypatch.setattr(check.sys, "platform", "linux")
    built = tmp_path / "out" / _WHEEL
    write_wheel(built, [("pkg/a.py", b"x"), _SBOM])
    record: list[list[str]] = []
    monkeypatch.setattr(
        check.subprocess, "run", repair_copying_the_wheel_across(record)
    )

    check.repair_wheel(built, tmp_path / "repaired")

    assert record[0][0] == check._AUDITWHEEL
    assert Path(check._AUDITWHEEL).stem.lower() == "auditwheel"
    assert record[0][1] == "repair"


def test_pair_wheels_by_name_is_silent_where_both_builds_match(
    check: ModuleType, tmp_path: Path
) -> None:
    """Two builds leaving the same wheels, member for member, is green."""
    first, second = two_wheels(tmp_path, [("pkg/a.py", b"x")], [("pkg/a.py", b"x")])

    assert (
        check.pair_wheels_by_name(
            [first], [second], first_label="one", second_label="other"
        )
        == []
    )


def test_pair_wheels_by_name_names_a_wheel_only_one_build_left(
    check: ModuleType, tmp_path: Path
) -> None:
    """A wheel missing on one side is not the two of them disagreeing.

    One build reaching an interpreter or a libc the other did not means
    the pair was never compared, which has to read differently from
    their bytes differing.
    """
    write_wheel(tmp_path / "one" / _WHEEL, [("pkg/a.py", b"x")])
    write_wheel(tmp_path / "one" / "pkg-1.0-cp314-cp314-musl.whl", [("a", b"x")])
    write_wheel(tmp_path / "other" / _WHEEL, [("pkg/a.py", b"x")])
    write_wheel(tmp_path / "other" / "pkg-1.0-cp314-cp314-many.whl", [("a", b"x")])

    complaints = check.pair_wheels_by_name(
        sorted((tmp_path / "one").glob("*.whl")),
        sorted((tmp_path / "other").glob("*.whl")),
        first_label="one",
        second_label="other",
    )

    assert complaints == [
        "only one built pkg-1.0-cp314-cp314-musl.whl",
        "only other built pkg-1.0-cp314-cp314-many.whl",
    ]


def test_pair_wheels_by_name_compares_the_wheels_both_builds_left(
    check: ModuleType, tmp_path: Path
) -> None:
    """A wheel present on both sides is compared member by member."""
    first, second = two_wheels(tmp_path, [("pkg/a.py", b"x")], [("pkg/a.py", b"y")])

    complaints = check.pair_wheels_by_name(
        [first], [second], first_label="one", second_label="other"
    )

    assert len(complaints) == 1
    assert "pkg/a.py" in complaints[0]
    assert "content differs" in complaints[0]


def test_pair_wheels_by_name_says_which_wheel_each_line_is_about(
    check: ModuleType, tmp_path: Path
) -> None:
    """One build leaves two wheels on Linux, and the members repeat.

    Every member of the package appears once per wheel, so a line
    naming only the member says nothing about which of the two
    disagreed: with the `manylinux` and the `musllinux` wheel differing
    in the same member, the two entries would be the same words twice.
    """
    for side, content in (("one", b"x"), ("other", b"y")):
        for wheel in (
            "pkg-1.0-cp314-cp314-manylinux_2_17_x86_64.whl",
            "pkg-1.0-cp314-cp314-musllinux_1_2_x86_64.whl",
        ):
            write_wheel(tmp_path / side / wheel, [("pkg/a.py", content)])

    complaints = check.pair_wheels_by_name(
        sorted((tmp_path / "one").glob("*.whl")),
        sorted((tmp_path / "other").glob("*.whl")),
        first_label="the first build",
        second_label="the second build",
    )

    # the length first: both assertions below hold of an empty list, so
    # without it a pair_wheels_by_name returning nothing at all would
    # satisfy a test written to witness two lines telling each other
    # apart
    assert len(complaints) == 2
    assert len(complaints) == len(set(complaints))
    assert all(complaint.startswith("pkg-1.0-cp314-cp314-") for complaint in complaints)


def test_diff_wheels_reports_nothing_for_identical_archives(
    check: ModuleType, tmp_path: Path
) -> None:
    """Two builds that agree, member for member, complain about nothing."""
    members = [("pkg/a.py", b"one"), ("pkg/b.py", b"two")]

    assert diff(check, *two_wheels(tmp_path, members, members)) == []


def test_diff_wheels_names_a_member_only_the_first_carries(
    check: ModuleType, tmp_path: Path
) -> None:
    """A member absent from the other side is named, not folded into a count."""
    first, second = two_wheels(
        tmp_path,
        [("pkg/a.py", b"one"), ("pkg/extra.py", b"x")],
        [("pkg/a.py", b"one")],
    )

    complaints = diff(check, first, second)

    assert any("only in one-image" in c and "pkg/extra.py" in c for c in complaints)


def test_diff_wheels_names_a_member_only_the_second_carries(
    check: ModuleType, tmp_path: Path
) -> None:
    """The same check from the other side: a member the second build added."""
    first, second = two_wheels(
        tmp_path,
        [("pkg/a.py", b"one")],
        [("pkg/a.py", b"one"), ("pkg/extra.py", b"x")],
    )

    complaints = diff(check, first, second)

    assert any("only in other-image" in c and "pkg/extra.py" in c for c in complaints)


def test_diff_wheels_reports_content_with_size_and_crc(
    check: ModuleType, tmp_path: Path
) -> None:
    """A content mismatch names both sizes and both CRCs, not just "differs"."""
    (complaint,) = diff(
        check, *two_wheels(tmp_path, [("pkg/a.py", b"one")], [("pkg/a.py", b"two!")])
    )

    assert "pkg/a.py" in complaint
    assert "content differs" in complaint
    assert "3 vs 4 bytes" in complaint
    assert f"{zlib.crc32(b'one'):08x}" in complaint
    assert f"{zlib.crc32(b'two!'):08x}" in complaint


@pytest.mark.parametrize(
    "field, value_a, value_b",
    [
        # the zip format stores a two-second granularity, so an odd
        # second here would round-trip to the even one below it and the
        # two sides would read back equal
        ("date_time", (2020, 2, 2, 0, 0, 0), (2021, 3, 3, 1, 1, 2)),
        ("external_attr", 0o644 << 16, 0o755 << 16),
        ("compress_type", zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED),
    ],
)
def test_diff_wheels_reports_a_metadata_field_by_name(
    check: ModuleType,
    tmp_path: Path,
    field: str,
    value_a: object,
    value_b: object,
) -> None:
    """Each of the fields #497 checked by hand is named when it disagrees."""
    member = [("pkg/a.py", b"same")]
    first = tmp_path / "one" / _WHEEL
    second = tmp_path / "other" / _WHEEL
    write_wheel(first, member, **{field: value_a})  # type: ignore[arg-type]
    write_wheel(second, member, **{field: value_b})  # type: ignore[arg-type]

    (complaint,) = diff(check, first, second)

    assert f"pkg/a.py: {field}" in complaint
    assert repr(value_a) in complaint
    assert repr(value_b) in complaint


def test_diff_wheels_reports_member_order(check: ModuleType, tmp_path: Path) -> None:
    """Two archives holding the same members in a different order are named."""
    complaints = diff(
        check,
        *two_wheels(
            tmp_path,
            [("pkg/a.py", b"x"), ("pkg/b.py", b"y")],
            [("pkg/b.py", b"y"), ("pkg/a.py", b"x")],
        ),
    )

    assert any("member order differs" in c for c in complaints)
    # the two members agree in content and metadata, so order is the only
    # thing either side has to say
    assert len(complaints) == 1


def test_diff_wheels_names_the_filename_and_compares_the_members_anyway(
    check: ModuleType, tmp_path: Path
) -> None:
    """A tag that moves between two images is one line, and not the last.

    #514's own case: a macOS runner's deployment target reaches the
    platform tag, so the two wheels can be named differently while the
    question about their members is still open. Stopping at the name
    would answer it with the name.
    """
    first = tmp_path / "one" / "pkg-1.0-cp314-cp314-macosx_15_0_x86_64.whl"
    second = tmp_path / "other" / "pkg-1.0-cp314-cp314-macosx_26_0_x86_64.whl"
    write_wheel(first, [("pkg/a.py", b"one")])
    write_wheel(second, [("pkg/a.py", b"two!")])

    named, content = diff(check, first, second)

    assert "macosx_15_0_x86_64" in named
    assert "macosx_26_0_x86_64" in named
    assert "one-image" in named
    assert "other-image" in named
    assert "pkg/a.py: content differs" in content


def test_main_says_how_to_be_called_when_it_is_not(
    check: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """An argument the script does not take is a usage message, not a crash."""
    assert check.main(["prog", "unexpected"]) == 2
    assert capsys.readouterr().err == (
        "usage: prog [--keep-wheel DIR | --across-images DIR"
        " | --across-toolchains DIR"
        " | --repaired [--keep-wheel DIR] | --dynamic | --cross-windows]\n"
    )


def test_main_builds_from_two_differently_named_directories(
    check: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`#509`: the two builds run from two directories, not one.

    `copy_source_tree` is where `main` names the two directories, so a
    spy on it, rather than on `subprocess.run`, is what can see the two
    names `main` actually chose and check the property the issue asks
    for: not merely two directories, but two of different lengths, since
    a same-length pair could still hide a path-dependent difference a
    real one would expose.
    """
    seen_dests: list[Path] = []

    def fake_copy(_root: Path, dest: Path) -> None:
        seen_dests.append(dest)
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(check, "copy_source_tree", fake_copy)
    monkeypatch.setattr(
        check.subprocess, "run", fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})
    )

    assert check.main(["prog"]) == 0

    assert len(seen_dests) == 2
    assert seen_dests[0] != seen_dests[1]
    assert len(seen_dests[0].name) != len(seen_dests[1].name)


def test_main_reports_success_when_the_two_builds_agree(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two builds landing the same wheel, byte for byte, is the green path."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})),
    )

    assert check.main(["prog"]) == 0

    out = capsys.readouterr().out
    assert _WHEEL in out
    assert "agree, member for member" in out


def test_main_reports_a_content_difference_and_exits_nonzero(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real divergence between the two builds is what turns main() red."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(build_writing_in_turn([b"first", b"second"])),
    )

    assert check.main(["prog"]) == 1

    err = capsys.readouterr().err
    assert "::error::" in err
    assert "pkg/a.py" in err
    assert "content differs" in err


def test_main_keeps_the_first_builds_wheel_where_it_is_asked_to(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--keep-wheel` leaves this image's half of the later comparison."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})),
    )
    kept = tmp_path / "wheel" / "linux-x86-64" / "ubuntu-latest"

    assert check.main(["prog", "--keep-wheel", str(kept)]) == 0

    with zipfile.ZipFile(kept / _WHEEL) as archive:
        assert archive.read("pkg/a.py") == b"x"


def test_main_keeps_the_wheel_even_where_the_two_builds_disagree(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The copy is taken before the comparison, and a red run still leaves it.

    An image whose own two builds disagree is one whose wheel the
    across-images comparison still wants: that comparison is a different
    question, and the workflow's upload step runs on `!cancelled()` for
    this reason.
    """
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(build_writing_in_turn([b"first", b"second"])),
    )
    kept = tmp_path / "kept"

    assert check.main(["prog", "--keep-wheel", str(kept)]) == 1

    with zipfile.ZipFile(kept / _WHEEL) as archive:
        assert archive.read("pkg/a.py") == b"first"


def test_main_repaired_refuses_to_run_without_source_date_epoch(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset is a failure, not "now": two builds would then disagree."""
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)

    assert check.main(["prog", "--repaired"]) == 1
    assert "SOURCE_DATE_EPOCH is not set" in capsys.readouterr().err


def test_main_repaired_reports_success_when_the_two_builds_agree(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The green path of `--repaired`, naming every wheel it compared."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(
            fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]}, out_flag="--output-dir"),
            out_flag="--output-dir",
        ),
    )

    assert check.main(["prog", "--repaired"]) == 0

    out = capsys.readouterr().out
    assert _WHEEL in out
    assert "two repaired builds of this commit agree" in out


def test_main_repaired_reports_a_difference_and_exits_nonzero(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A divergence between two repaired builds is what turns it red."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(
            build_writing_in_turn([b"first", b"second"], out_flag="--output-dir"),
            out_flag="--output-dir",
        ),
    )

    assert check.main(["prog", "--repaired"]) == 1

    err = capsys.readouterr().err
    assert "::error::" in err
    assert "pkg/a.py" in err
    assert "content differs" in err


def test_main_repaired_builds_from_two_differently_named_directories(
    check: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`#503`'s property holds on this path too, both taking one helper."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    seen_dests: list[Path] = []

    def fake_copy(_root: Path, dest: Path) -> None:
        seen_dests.append(dest)
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(check, "copy_source_tree", fake_copy)
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]}, out_flag="--output-dir"),
    )

    assert check.main(["prog", "--repaired"]) == 0

    assert len(seen_dests) == 2
    assert seen_dests[0] != seen_dests[1]
    assert len(seen_dests[0].name) != len(seen_dests[1].name)


def test_main_repaired_keeps_the_first_builds_wheels_where_it_is_asked_to(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--repaired --keep-wheel` leaves every wheel the first build left.

    A Linux `cibuildwheel` run leaves a `manylinux` wheel and a
    `musllinux` one from the one interpreter, and both are what
    `across-images` wants kept, not one.
    """
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    musl = "pkg-1.0-cp314-cp314-musllinux_1_2_x86_64.whl"
    many = "pkg-1.0-cp314-cp314-manylinux_2_17_x86_64.whl"
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(
            fake_run_writing(
                {musl: [("pkg/a.py", b"x")], many: [("pkg/a.py", b"x")]},
                out_flag="--output-dir",
            ),
            out_flag="--output-dir",
        ),
    )
    kept = tmp_path / "wheel-repaired" / "linux-x86-64" / "ubuntu-latest"

    assert check.main(["prog", "--repaired", "--keep-wheel", str(kept)]) == 0

    with zipfile.ZipFile(kept / musl) as archive:
        assert archive.read("pkg/a.py") == b"x"
    with zipfile.ZipFile(kept / many) as archive:
        assert archive.read("pkg/a.py") == b"x"


def test_main_repaired_keeps_the_wheels_even_where_the_two_builds_disagree(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The copy is taken before the comparison, as `--keep-wheel` alone does."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(
            build_writing_in_turn([b"first", b"second"], out_flag="--output-dir"),
            out_flag="--output-dir",
        ),
    )
    kept = tmp_path / "kept"

    assert check.main(["prog", "--repaired", "--keep-wheel", str(kept)]) == 1

    with zipfile.ZipFile(kept / _WHEEL) as archive:
        assert archive.read("pkg/a.py") == b"first"


def test_main_dynamic_refuses_to_run_without_source_date_epoch(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repair reads it, so this refuses it unset as `--repaired` does."""
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)

    assert check.main(["prog", "--dynamic"]) == 1
    assert "SOURCE_DATE_EPOCH is not set" in capsys.readouterr().err


def test_main_dynamic_repairs_each_build_before_comparing(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The published file is the repaired one, so that is what is compared."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    record: list[list[str]] = []
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dynamic_dispatching_run(
            fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]}, out_flag="--outdir"),
            record,
        ),
    )

    assert check.main(["prog", "--dynamic"]) == 0

    assert len(record) == 2
    assert _WHEEL in capsys.readouterr().out


def test_main_dynamic_reports_a_difference_and_exits_nonzero(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A divergence between two dynamic builds is what turns it red."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dynamic_dispatching_run(
            build_writing_in_turn([b"first", b"second"], out_flag="--outdir"),
            [],
        ),
    )

    assert check.main(["prog", "--dynamic"]) == 1

    err = capsys.readouterr().err
    assert "::error::" in err
    assert "pkg/a.py" in err
    assert "content differs" in err


def test_main_cross_windows_compares_what_no_tool_repaired(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`build-windows` runs no repair, so the build's own file is compared.

    Running one here would compare an archive the release never
    uploads, and on a Linux host it would be `auditwheel` reading a
    `win_amd64` wheel.
    """
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    record: list[list[str]] = []
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dynamic_dispatching_run(
            fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]}, out_flag="--outdir"),
            record,
        ),
    )

    assert check.main(["prog", "--cross-windows"]) == 0

    assert record == []
    assert "two builds of this commit agree" in capsys.readouterr().out


def test_across_images_is_green_where_both_images_built_one_wheel(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#514's green answer: the environment did not reach the bytes."""
    member = [("pkg/a.py", b"same")]
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-latest" / _WHEEL, member)
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-22.04" / _WHEEL, member)

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 0

    assert (
        "linux-x86-64: its images agree, member for member" in capsys.readouterr().out
    )


def test_across_images_pairs_more_than_one_wheel_per_image(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#524's own shape: one Linux image can leave two wheels, not one.

    Both images built through `--repaired --keep-wheel` leave a
    `manylinux` wheel and a `musllinux` one, paired by name rather than
    compared as one wheel each.
    """
    musl = "pkg-1.0-cp314-cp314-musllinux_1_2_x86_64.whl"
    many = "pkg-1.0-cp314-cp314-manylinux_2_17_x86_64.whl"
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-latest" / musl, [("pkg/a.py", b"x")]
    )
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-latest" / many, [("pkg/a.py", b"y")]
    )
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-22.04" / musl, [("pkg/a.py", b"x")])
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-22.04" / many, [("pkg/a.py", b"y")])

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 0

    assert (
        "linux-x86-64: its images agree, member for member" in capsys.readouterr().out
    )


def test_across_images_names_the_wheel_within_a_pair_that_differs(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only the wheel whose member moved is named, not the one that agrees."""
    musl = "pkg-1.0-cp314-cp314-musllinux_1_2_x86_64.whl"
    many = "pkg-1.0-cp314-cp314-manylinux_2_17_x86_64.whl"
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-latest" / musl, [("pkg/a.py", b"x")]
    )
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-latest" / many, [("pkg/a.py", b"y")]
    )
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-22.04" / musl, [("pkg/a.py", b"x")])
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-22.04" / many, [("pkg/a.py", b"moved")]
    )

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert f"::error::linux-x86-64: {many}: pkg/a.py: content differs" in err
    assert musl not in err


def test_across_images_names_a_wheel_only_one_image_built(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wheel one image alone left is unpaired, not a member difference."""
    musl = "pkg-1.0-cp314-cp314-musllinux_1_2_x86_64.whl"
    many = "pkg-1.0-cp314-cp314-manylinux_2_17_x86_64.whl"
    write_wheel(
        tmp_path / "linux-aarch64" / "ubuntu-24.04-arm" / musl, [("pkg/a.py", b"x")]
    )
    write_wheel(
        tmp_path / "linux-aarch64" / "ubuntu-24.04-arm" / many, [("pkg/a.py", b"x")]
    )
    write_wheel(
        tmp_path / "linux-aarch64" / "ubuntu-22.04-arm" / many, [("pkg/a.py", b"x")]
    )

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert f"only ubuntu-24.04-arm built {musl}" in err


def test_across_images_names_the_image_and_the_member_that_differ(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#514's red answer names which member moved and between which images."""
    write_wheel(
        tmp_path / "macos-x86-64" / "macos-15-intel" / _WHEEL, [("pkg/_ext.so", b"aa")]
    )
    write_wheel(
        tmp_path / "macos-x86-64" / "macos-26-intel" / _WHEEL, [("pkg/_ext.so", b"bbb")]
    )

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert "::error::macos-x86-64: pkg/_ext.so: content differs" in err
    assert "2 vs 3 bytes" in err


def test_across_images_compares_members_of_two_differently_named_singletons(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#514's own case, exercised at the level `across-images` actually calls.

    A macOS or Windows runner's deployment target reaches the platform
    tag, so the one wheel each image built can be named differently with
    the question about their members still open. `compare_one_platform`
    has to route this -- one wheel on each side -- through `diff_wheels`
    directly rather than through `pair_wheels_by_name`, which pairs
    strictly by filename: two differently-named singletons would then
    overlap in nothing and `diff_wheels` would never run, silently
    dropping the member comparison the mismatched name was never meant
    to excuse.
    """
    write_wheel(
        tmp_path
        / "macos-arm64"
        / "macos-15"
        / "pkg-1.0-cp314-cp314-macosx_15_0_arm64.whl",
        [("pkg/_ext.so", b"aa")],
    )
    write_wheel(
        tmp_path
        / "macos-arm64"
        / "macos-latest"
        / "pkg-1.0-cp314-cp314-macosx_26_0_arm64.whl",
        [("pkg/_ext.so", b"bbb")],
    )

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert "the wheel is named" in err
    assert "::error::macos-arm64: pkg/_ext.so: content differs" in err
    assert "only macos-15 built" not in err
    assert "only macos-latest built" not in err


def test_across_images_refuses_a_platform_only_one_image_built(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One image left is a comparison that did not happen, not agreement."""
    write_wheel(
        tmp_path / "windows-arm64" / "windows-11-arm" / _WHEEL, [("pkg/a.py", b"x")]
    )

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert "no two images" in err
    assert "windows-11-arm" in err


def test_across_images_names_an_image_that_left_no_wheel(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A build that produced nothing is named by the image it ran on."""
    member = [("pkg/a.py", b"x")]
    write_wheel(tmp_path / "linux-aarch64" / "ubuntu-24.04-arm" / _WHEEL, member)
    write_wheel(tmp_path / "linux-aarch64" / "ubuntu-22.04-arm" / _WHEEL, member)
    (tmp_path / "linux-aarch64" / "ubuntu-26.04-arm").mkdir()

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert "ubuntu-26.04-arm left no wheel" in err


def test_across_images_refuses_a_directory_no_platform_reached(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every build failing downloads nothing, which is not an agreement."""
    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1

    assert "no platform built a wheel" in capsys.readouterr().err


def toolchain_members(
    extension: bytes, *, tag: str = "linux_x86_64"
) -> list[tuple[str, bytes]]:
    """Return a compiled wheel's members, its `RECORD` hashing `extension`.

    The `RECORD` row of the extension carries a hash and a size of those
    bytes, so two compilers' extensions differ in that row as well: what
    `--across-toolchains` has to tell apart from any other `RECORD` row
    moving.
    """
    extension_name = "_ext.cpython-314-x86_64-linux-gnu.so"
    record = (
        "pkg/a.py,sha256=same,4\n"
        f"pkg-1.0.dist-info/WHEEL,sha256={tag},9\n"
        f"{extension_name},sha256={zlib.crc32(extension):08x},{len(extension)}\n"
        "pkg-1.0.dist-info/RECORD,,\n"
    )
    return [
        ("pkg/a.py", b"same"),
        (extension_name, extension),
        ("pkg-1.0.dist-info/WHEEL", f"Tag: {tag}".encode()),
        ("pkg-1.0.dist-info/RECORD", record.encode()),
    ]


def test_across_toolchains_leaves_the_extension_and_its_record_row_out(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#992's green answer: two compilers, and nothing else, moved.

    The same pair is red under `--across-images`, which is what makes the
    green here the narrowing's doing rather than the fixture's.
    """
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-22.04" / _WHEEL,
        toolchain_members(b"gcc-11"),
    )
    write_wheel(
        tmp_path / "linux-x86-64" / "ubuntu-latest" / _WHEEL,
        toolchain_members(b"gcc-13!"),
    )

    assert check.main(["prog", "--across-toolchains", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        "linux-x86-64: its images agree on every member but the compiled"
        " extension's bytes\n"
    )

    assert check.main(["prog", "--across-images", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "_ext.cpython-314-x86_64-linux-gnu.so: content differs" in err
    assert "pkg-1.0.dist-info/RECORD: content differs" in err


def test_across_toolchains_names_a_member_that_is_not_compiled(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#992's own macOS case: an image reaching the tag is still red.

    A deployment target left to the runner moves the tag in the filename,
    in `WHEEL`, and in `WHEEL`'s own `RECORD` row, none of which the
    compiler wrote.
    """
    write_wheel(
        tmp_path
        / "macos-arm64"
        / "macos-15"
        / "pkg-1.0-cp314-cp314-macosx_15_0_arm64.whl",
        toolchain_members(b"ld-1167", tag="macosx_15_0_arm64"),
    )
    write_wheel(
        tmp_path
        / "macos-arm64"
        / "macos-latest"
        / "pkg-1.0-cp314-cp314-macosx_26_0_arm64.whl",
        toolchain_members(b"ld-1267", tag="macosx_26_0_arm64"),
    )

    assert check.main(["prog", "--across-toolchains", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert "::error::macos-arm64: the wheel is named" in err
    assert "::error::macos-arm64: pkg-1.0.dist-info/WHEEL: content differs" in err
    assert "::error::macos-arm64: pkg-1.0.dist-info/RECORD: content differs" in err
    assert "_ext" not in err


@pytest.mark.parametrize(
    "reserialize",
    [
        pytest.param(lambda record: record.replace(b"\n", b"\r\n"), id="crlf"),
        pytest.param(lambda record: record.rstrip(b"\n"), id="no-final-newline"),
        pytest.param(
            lambda record: record.replace(b"pkg/a.py,", b'"pkg/a.py",'),
            id="quoted-row",
        ),
    ],
)
def test_across_toolchains_keeps_every_other_record_row_byte_for_byte(
    check: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    reserialize: Any,
) -> None:
    """Only the extension's row is cut: the rest of `RECORD` is bytes.

    A `RECORD` that reads as the same CSV rows but is written differently
    -- another line ending, no final newline, a row quoted -- is a
    difference no compiler made, and stays red.
    """
    first = toolchain_members(b"gcc-11")
    second = [
        (name, reserialize(content) if name.endswith("RECORD") else content)
        for name, content in toolchain_members(b"gcc-13!")
    ]
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-22.04" / _WHEEL, first)
    write_wheel(tmp_path / "linux-x86-64" / "ubuntu-latest" / _WHEEL, second)

    assert check.main(["prog", "--across-toolchains", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert "::error::linux-x86-64: pkg-1.0.dist-info/RECORD: content differs" in err
    assert "_ext" not in err


def test_across_toolchains_still_compares_the_extensions_metadata(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only the extension's bytes are the compiler's; its mode is not."""
    extension = "_ext.cp314-win_amd64.pyd"
    write_wheel(
        tmp_path / "windows-x86-64" / "windows-2022" / _WHEEL, [(extension, b"a")]
    )
    write_wheel(
        tmp_path / "windows-x86-64" / "windows-latest" / _WHEEL,
        [(extension, b"bb")],
        external_attr=0o755 << 16,
    )

    assert check.main(["prog", "--across-toolchains", str(tmp_path)]) == 1

    err = capsys.readouterr().err
    assert f"::error::windows-x86-64: {extension}: external_attr" in err
    assert "content differs" not in err


def test_the_main_guard_runs_the_script_as___main__(
    check: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover `if __name__ == "__main__":` without a subprocess.

    This project collects no coverage from a child interpreter, so a real
    subprocess would leave the guard as uncovered as it is in
    `normalize_sdist.py`. `runpy.run_path` executes the file fresh with
    `__name__` set to `"__main__"` in this one; `check.subprocess` is the
    real stdlib module the freshly executed copy also imports, the way
    `tests/submodule_pin_test.py`'s own guard test stubs the same module.
    """
    monkeypatch.setattr(
        check.subprocess,
        "run",
        dispatching_run(fake_run_writing({_WHEEL: [("pkg/a.py", b"x")]})),
    )
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert excinfo.value.code == 0
