# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for `.github/scripts/check_wheel_reproducibility.py`.

`diff_wheels` is exercised against archives built by hand, one member
disagreeing at a time, so that each assertion names the one thing that
changed. `build_wheel` and `main` never invoke the real `uv build`: what
they are asked to build is a fake, `check.subprocess.run` replaced the
way `tests/submodule_pin_test.py` and `tests/check_vendored_vectors.py`
replace it, so the suite measures this script rather than a real
compile.

The script is loaded by path, `.github/scripts` being no package, as the
other scripts under it are tested.
"""

from __future__ import annotations

import importlib.util
import runpy
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


def test_build_wheel_returns_the_one_wheel_uv_left(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success path: one call, one wheel, its path comes back."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]}),
    )

    wheel = check.build_wheel(tmp_path / "out")

    assert wheel == tmp_path / "out" / "pkg-1.0-py3-none-any.whl"


def test_build_wheel_refuses_an_empty_out_dir(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv build` leaving nothing behind is named, not `KeyError`'d."""
    monkeypatch.setattr(check.subprocess, "run", fake_run_writing({}))

    with pytest.raises(RuntimeError, match="expected exactly one wheel"):
        check.build_wheel(tmp_path / "out")


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
        check.build_wheel(tmp_path / "out")


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


def test_main_reports_success_when_the_two_builds_agree(
    check: ModuleType,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two builds landing the same wheel, byte for byte, is the green path."""
    monkeypatch.setattr(
        check.subprocess,
        "run",
        fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]}),
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

    def fake_run(args: list[str], **_kwargs: Any) -> None:
        out_dir = Path(args[args.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        calls["n"] += 1
        content = b"first" if calls["n"] == 1 else b"second"
        write_wheel(out_dir / "pkg-1.0-py3-none-any.whl", [("pkg/a.py", content)])

    monkeypatch.setattr(check.subprocess, "run", fake_run)

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

    def fake_run(args: list[str], **_kwargs: Any) -> None:
        out_dir = Path(args[args.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        calls["n"] += 1
        name = (
            "pkg-1.0-py3-none-any.whl"
            if calls["n"] == 1
            else "pkg-1.0-py3-none-other.whl"
        )
        write_wheel(out_dir / name, [("pkg/a.py", b"x")])

    monkeypatch.setattr(check.subprocess, "run", fake_run)

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
        fake_run_writing({"pkg-1.0-py3-none-any.whl": [("pkg/a.py", b"x")]}),
    )
    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert excinfo.value.code == 0
