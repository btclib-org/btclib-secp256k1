# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for `.github/scripts/check_wheel_reproducibility.py`.

`diff_wheels` is exercised against archives built by hand, one member
disagreeing at a time, so that each assertion names the one thing that
changed. `_extract_archive` and `copy_source_tree` are exercised against
real git repositories built by hand instead: what makes `#509`'s own
fix worth trusting is that a commit and an uncommitted edit come out
differently, and a mock of `subprocess.run` cannot tell the two apart --
it would have to reimplement `git archive` to do so, at which point the
test measures the mock rather than the script. `build_wheel` and `main`
never invoke the real `uv build`, though: what they are asked to build
is a fake, `check.subprocess.run` replaced the way
`tests/submodule_pin_test.py` and `tests/check_vendored_vectors.py`
replace it, so the suite measures this script's plumbing rather than a
real compile. The fake answers a `git archive` call too, now that `main`
calls `copy_source_tree` before every build, with a real, empty tar
archive -- `_extract_archive`'s own `tarfile.open` still runs unmocked
against that, extracting nothing rather than being skipped.

The script is loaded by path, `.github/scripts` being no package, as the
other scripts under it are tested.
"""

from __future__ import annotations

import importlib.util
import io
import runpy
import shutil
import subprocess
import sys
import tarfile
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
    else.
    """
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.external_attr = external_attr
            info.compress_type = compress_type
            archive.writestr(info, content)


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


def _empty_tar_bytes() -> bytes:
    """Return the bytes of a valid, empty tar archive.

    What a faked `git archive` call answers with below: `_extract_archive`
    still runs its own `tarfile.open`/`extractall` against this, for real,
    rather than having that call skipped the way a mock returning `None`
    would force it to.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w"):
        pass
    return buffer.getvalue()


def dispatching_run(build_call: Any) -> Any:
    """Return a `subprocess.run` stand-in that fakes `git archive` calls.

    `main` now runs `copy_source_tree` -- two `git archive` calls -- ahead
    of every `build_wheel`, and both go through the same `subprocess.run`
    a test here replaces. `--out-dir` is what only a `uv build` call
    carries, so its absence is what marks a `git archive` call, answered
    with an empty archive rather than reaching `build_call`, which does
    not expect one; `args[0]` is not what tells the two apart, since it
    names `_GIT`'s own resolved, and possibly absolute, path rather than
    the literal string "git".
    """

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        if "--out-dir" not in args:
            return subprocess.CompletedProcess(args, 0, stdout=_empty_tar_bytes())
        return build_call(args, **kwargs)

    return fake_run


def fake_run_writing(wheels: dict[str, list[tuple[str, bytes]]]) -> Any:
    """Return a `subprocess.run` stand-in that writes a canned wheel.

    `wheels` maps a wheel's own filename to the members it should
    contain; `--out-dir` is read out of the faked command line, and every
    call writes every one of `wheels` there -- `build_wheel`'s own
    "exactly one" check is what a test then leans on to pick one out.
    """

    def fake_run(args: list[str], **_kwargs: Any) -> Any:
        out_dir = Path(args[args.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, members in wheels.items():
            write_wheel(out_dir / name, members)
        return None

    return fake_run


def test_extract_archive_copies_head_and_not_an_uncommitted_edit(
    check: ModuleType, tmp_path: Path
) -> None:
    """`git archive HEAD` is a commit's content, not the working tree's.

    `#509`'s own reason for building from an archive rather than the
    checkout in place: two builds sharing a working directory would share
    whatever is sitting there uncommitted too. This is the property that
    makes the sentinel measure a commit rather than a checkout, and it is
    real git commands answering it, not a stand-in for them.
    """
    source = tmp_path / "source"
    init_repo(source, {"tracked.py": b"committed"})
    (source / "tracked.py").write_bytes(b"edited-but-not-committed")
    (source / "untracked.py").write_bytes(b"never added")

    dest = tmp_path / "dest"
    check._extract_archive(source, dest)

    assert (dest / "tracked.py").read_bytes() == b"committed"
    assert not (dest / "untracked.py").exists()


def test_copy_source_tree_extracts_the_submodule_from_its_own_repository(
    check: ModuleType, tmp_path: Path
) -> None:
    """The submodule is a gitlink, and its own commit is archived on its own.

    `root`'s own `git archive` never descends into a gitlink -- it leaves
    an empty directory at that path instead -- so `copy_source_tree`'s
    second `git archive`, against `root/secp256k1` itself, is what a real
    submodule checkout actually needs and what this asserts landed.
    """
    root = tmp_path / "root"
    init_repo(root, {"pyproject.toml": b"[project]\n"})
    init_repo(root / "secp256k1", {"CMakeLists.txt": b"vendored\n"})
    run_git("add", "-A", cwd=root)
    run_git("commit", "-q", "-m", "pin submodule", cwd=root)

    dest = tmp_path / "dest"
    check.copy_source_tree(root, dest)

    assert (dest / "pyproject.toml").read_bytes() == b"[project]\n"
    assert (dest / "secp256k1" / "CMakeLists.txt").read_bytes() == b"vendored\n"


def test_build_wheel_returns_the_one_wheel_uv_left(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success path: one call, one wheel, its path comes back."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]}),
    )

    wheel = check.build_wheel(tmp_path / "source", tmp_path / "out")

    assert wheel == tmp_path / "out" / "pkg-1.0-py3-none-any.whl"


def test_build_wheel_refuses_an_empty_out_dir(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv build` leaving nothing behind is named, not `KeyError`'d."""
    monkeypatch.setattr(check.subprocess, "run", fake_run_writing({}))

    with pytest.raises(RuntimeError, match="expected exactly one wheel"):
        check.build_wheel(tmp_path / "source", tmp_path / "out")


def test_build_wheel_refuses_more_than_one_wheel(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale wheel sharing the directory is named rather than picked."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing({
            "pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")],
            "pkg-0.9-py3-none-any.whl": [("pkg/a.py", b"x")],
        }),
    )

    with pytest.raises(RuntimeError, match="expected exactly one wheel"):
        check.build_wheel(tmp_path / "source", tmp_path / "out")


def test_diff_wheels_reports_nothing_for_identical_archives(
    check: ModuleType, tmp_path: Path
) -> None:
    """Two builds that agree, member for member, complain about nothing."""
    members = [("pkg/a.py", b"one"), ("pkg/b.py", b"two")]
    write_wheel(tmp_path / "a.whl", members)
    write_wheel(tmp_path / "b.whl", members)

    assert check.diff_wheels(tmp_path / "a.whl", tmp_path / "b.whl") == []


def test_diff_wheels_names_a_member_only_the_first_carries(
    check: ModuleType, tmp_path: Path
) -> None:
    """A member absent from the other side is named, not folded into a count."""
    write_wheel(tmp_path / "a.whl", [("pkg/a.py", b"one"), ("pkg/extra.py", b"x")])
    write_wheel(tmp_path / "b.whl", [("pkg/a.py", b"one")])

    complaints = check.diff_wheels(tmp_path / "a.whl", tmp_path / "b.whl")

    assert any("only in a.whl" in c and "pkg/extra.py" in c for c in complaints)


def test_diff_wheels_names_a_member_only_the_second_carries(
    check: ModuleType, tmp_path: Path
) -> None:
    """The same check from the other side: a member the second build added."""
    write_wheel(tmp_path / "a.whl", [("pkg/a.py", b"one")])
    write_wheel(tmp_path / "b.whl", [("pkg/a.py", b"one"), ("pkg/extra.py", b"x")])

    complaints = check.diff_wheels(tmp_path / "a.whl", tmp_path / "b.whl")

    assert any("only in b.whl" in c and "pkg/extra.py" in c for c in complaints)


def test_diff_wheels_reports_content_with_size_and_crc(
    check: ModuleType, tmp_path: Path
) -> None:
    """A content mismatch names both sizes and both CRCs, not just "differs"."""
    write_wheel(tmp_path / "a.whl", [("pkg/a.py", b"one")])
    write_wheel(tmp_path / "b.whl", [("pkg/a.py", b"two!")])

    (complaint,) = check.diff_wheels(tmp_path / "a.whl", tmp_path / "b.whl")

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
    kwargs_a = {field: value_a}
    kwargs_b = {field: value_b}
    write_wheel(tmp_path / "a.whl", [("pkg/a.py", b"same")], **kwargs_a)  # type: ignore[arg-type]
    write_wheel(tmp_path / "b.whl", [("pkg/a.py", b"same")], **kwargs_b)  # type: ignore[arg-type]

    (complaint,) = check.diff_wheels(tmp_path / "a.whl", tmp_path / "b.whl")

    assert f"pkg/a.py: {field}" in complaint
    assert repr(value_a) in complaint
    assert repr(value_b) in complaint


def test_diff_wheels_reports_member_order(check: ModuleType, tmp_path: Path) -> None:
    """Two archives holding the same members in a different order are named."""
    write_wheel(tmp_path / "a.whl", [("pkg/a.py", b"x"), ("pkg/b.py", b"y")])
    write_wheel(tmp_path / "b.whl", [("pkg/b.py", b"y"), ("pkg/a.py", b"x")])

    complaints = check.diff_wheels(tmp_path / "a.whl", tmp_path / "b.whl")

    assert any("member order differs" in c for c in complaints)
    # the two members agree in content and metadata, so order is the only
    # thing either side has to say
    assert len(complaints) == 1


def test_main_says_how_to_be_called_when_it_is_not(
    check: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """An argument on the command line is the usage message, not a crash."""
    assert check.main(["prog", "unexpected"]) == 2
    assert capsys.readouterr().err == "usage: prog\n"


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
        check.subprocess,
        "run",
        fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]}),
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
        dispatching_run(
            fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]})
        ),
    )

    assert check.main(["prog"]) == 0

    out = capsys.readouterr().out
    assert "pkg-1.0-py3-none-any.whl" in out
    assert "agree, member for member" in out


def test_main_reports_a_content_difference_and_exits_nonzero(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real divergence between the two builds is what turns main() red."""
    calls = {"n": 0}

    def build_call(args: list[str], **_kwargs: Any) -> None:
        out_dir = Path(args[args.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        calls["n"] += 1
        content = b"first" if calls["n"] == 1 else b"second"
        write_wheel(out_dir / "pkg-1.0-py3-none-any.whl", [("pkg/a.py", content)])

    monkeypatch.setattr(check.subprocess, "run", dispatching_run(build_call))

    assert check.main(["prog"]) == 1

    err = capsys.readouterr().err
    assert "::error::" in err
    assert "pkg/a.py" in err
    assert "content differs" in err


def test_main_names_two_builds_that_disagree_on_the_wheel_name(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A platform tag that moves between the two builds is named, not diffed."""
    calls = {"n": 0}

    def build_call(args: list[str], **_kwargs: Any) -> None:
        out_dir = Path(args[args.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        calls["n"] += 1
        name = (
            "pkg-1.0-py3-none-any.whl"
            if calls["n"] == 1
            else "pkg-1.0-py3-none-other.whl"
        )
        write_wheel(out_dir / name, [("pkg/a.py", b"x")])

    monkeypatch.setattr(check.subprocess, "run", dispatching_run(build_call))

    assert check.main(["prog"]) == 1

    err = capsys.readouterr().err
    assert "named the wheel differently" in err
    assert "pkg-1.0-py3-none-any.whl" in err
    assert "pkg-1.0-py3-none-other.whl" in err


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
        dispatching_run(
            fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]})
        ),
    )
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert excinfo.value.code == 0
