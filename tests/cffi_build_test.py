# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The static glue's compile and link honour the compiler variables.

`scripts/cffi_build.py`'s `_customized_compile_link` composes `CC`,
`CFLAGS` and `LDSHARED` the way the Unix compiler's `configure_system`
does in the setuptools `uv.lock` resolves, and `_cmake_build_type` reads
`CMAKE_BUILD_TYPE` for the vendored library's build type. Both are pure
functions of their arguments -- no `sysconfig`, no `os.environ`, no
subprocess -- so what is checked here is the argv each one builds, never
a compile (btclib-org/btclib-secp256k1#1019).

Neither is read by importing `scripts/cffi_build.py`, for the reason
`tests/module_flags_test.py`'s own docstring gives: the module's own top
level constructs `Secp256k1CFFIExtension()`, whose `__init__` runs
`clean()` and deletes the CMake build directory and any local build
artifact this suite may be running against. Each function is instead
taken out of the syntax tree and executed on its own -- real code, not a
reimplementation of it, but never the module-level construction that
comes with it.
"""

from __future__ import annotations

import ast
import shlex
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

_ROOT = Path(__file__).parents[1]
_BUILD = _ROOT / "scripts" / "cffi_build.py"


def _extracted(name: str) -> Callable[..., object]:
    """Compile and run one top-level function definition, on its own.

    Args:
        name: the function's own name, as `scripts/cffi_build.py` spells
            it.

    Returns:
        The callable that function's own code defines: real code, taken
        out of the file rather than duplicated by hand, and run with
        nothing else in the module -- so a rename or a signature change
        there is what breaks this rather than a copy drifting from it.
    """
    tree = ast.parse(_BUILD.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            only = ast.Module(body=[node], type_ignores=[])
            namespace: dict[str, object] = {"shlex": shlex}
            exec(compile(only, str(_BUILD), "exec"), namespace)
            return namespace[name]  # type: ignore[return-value]
    raise AssertionError(f"{name} not found in {_BUILD}")


customized_compile_link = cast(
    "Callable[[str, str, str, Mapping[str, str]], tuple[list[str], list[str], list[str]]]",
    _extracted("_customized_compile_link"),
)
cmake_build_type = cast(
    "Callable[[Mapping[str, str]], str]", _extracted("_cmake_build_type")
)


def test_both_functions_were_read() -> None:
    """The positive control for `_extracted`: a rename answers here first.

    Without it, a `name` that stopped matching would leave every test
    below calling nothing -- `_extracted` raises in that case, so this
    is what turns the raise into a named failure rather than a collection
    error attributed to the wrong line.
    """
    assert callable(customized_compile_link)
    assert callable(cmake_build_type)


def test_nothing_set_leaves_every_value_untouched() -> None:
    """With none of the variables set, the sysconfig values pass through.

    This is the case `wheel-reproducibility.yml` and the sdist-rebuild
    gate measure: a build with nothing exported has to compose exactly
    what it composed before this function existed.
    """
    cc, cflags, ldshared = customized_compile_link("cc", "-O2 -Wall", "gcc -shared", {})
    assert cc == ["cc"]
    assert cflags == ["-O2", "-Wall"]
    assert ldshared == ["gcc", "-shared"]


def test_cc_is_replaced_not_extended() -> None:
    """`CC` overrides the sysconfig value outright, on the compile alone."""
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"CC": "clang-18"}
    )
    assert cc == ["clang-18"]
    assert cflags == ["-O2"]
    assert ldshared == ["gcc", "-shared"]


def test_cc_replaces_the_link_command_it_starts() -> None:
    """A `CC` override also replaces the old `CC` that begins `LDSHARED`.

    setuptools does this where `LDSHARED` is not itself set, so that a
    caller changing the compiler does not link with the old one.
    """
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "cc -shared", {"CC": "clang-18"}
    )
    assert cc == ["clang-18"]
    assert cflags == ["-O2"]
    assert ldshared == ["clang-18", "-shared"]
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "cc -shared", {"CC": "clang-18", "LDSHARED": "ld -shared"}
    )
    assert cc == ["clang-18"]
    assert cflags == ["-O2"]
    assert ldshared == ["ld", "-shared"]


def test_ldshared_is_replaced_not_extended() -> None:
    """`LDSHARED` overrides the sysconfig value outright, on the link alone."""
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"LDSHARED": "clang-18 -shared"}
    )
    assert cc == ["cc"]
    assert cflags == ["-O2"]
    assert ldshared == ["clang-18", "-shared"]


def test_ldflags_extends_the_link_alone() -> None:
    """`LDFLAGS` is appended to `LDSHARED`, and never reaches the compile."""
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"LDFLAGS": "-Wl,--as-needed"}
    )
    assert cc == ["cc"]
    assert cflags == ["-O2"]
    assert ldshared == ["gcc", "-shared", "-Wl,--as-needed"]


def test_cflags_replaces_the_compile_and_extends_the_link() -> None:
    """`CFLAGS` is the whole of the compile's flags, and reaches `LDSHARED` too.

    Replacing rather than extending is what setuptools does for every
    other extension; extending the link is what carries an `-arch` pair
    to the link that consumes the object.
    """
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"CFLAGS": "-arch x86_64 -arch arm64"}
    )
    assert cc == ["cc"]
    assert cflags == ["-arch", "x86_64", "-arch", "arm64"]
    assert ldshared == ["gcc", "-shared", "-arch", "x86_64", "-arch", "arm64"]


def test_cppflags_extends_both_compile_and_link() -> None:
    """`CPPFLAGS` reaches `LDSHARED` too, the same way `CFLAGS` does."""
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"CPPFLAGS": "-DFOO_MARKER"}
    )
    assert cc == ["cc"]
    assert cflags == ["-O2", "-DFOO_MARKER"]
    assert ldshared == ["gcc", "-shared", "-DFOO_MARKER"]


def test_all_four_compose_in_order() -> None:
    """`LDFLAGS`, then `CFLAGS`, then `CPPFLAGS`, is the order each extends in.

    `CC` and `LDSHARED` are read first and replaced outright, so what
    this checks is that the three extensions land on `LDSHARED` in the
    same order `configure_system` applies them in, beside the override
    of the other two.
    """
    cc, cflags, ldshared = customized_compile_link(
        "cc",
        "-O2",
        "gcc -shared",
        {
            "CC": "clang-18",
            "LDSHARED": "clang-18 -shared",
            "LDFLAGS": "-Wl,--as-needed",
            "CFLAGS": "-DFOO_MARKER",
            "CPPFLAGS": "-DBAR_MARKER",
        },
    )
    assert cc == ["clang-18"]
    assert cflags == ["-DFOO_MARKER", "-DBAR_MARKER"]
    assert ldshared == [
        "clang-18",
        "-shared",
        "-Wl,--as-needed",
        "-DFOO_MARKER",
        "-DBAR_MARKER",
    ]


def test_an_empty_variable_is_read_as_setuptools_reads_it() -> None:
    """An empty extension adds nothing; an empty `CFLAGS` still replaces."""
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"LDFLAGS": "", "CPPFLAGS": ""}
    )
    assert cc == ["cc"]
    assert cflags == ["-O2"]
    assert ldshared == ["gcc", "-shared"]
    cc, cflags, ldshared = customized_compile_link(
        "cc", "-O2", "gcc -shared", {"CFLAGS": ""}
    )
    assert cc == ["cc"]
    assert cflags == []
    assert ldshared == ["gcc", "-shared"]


def test_each_value_is_shlex_split() -> None:
    """A multi-token override is split into separate argv elements.

    Unsplit, a two-flag `CFLAGS` would land in the compile command as one
    argv element no compiler parses as two flags.
    """
    cc, cflags, ldshared = customized_compile_link(
        "cc", "", "gcc -shared", {"CFLAGS": "-O0 -g"}
    )
    assert cc == ["cc"]
    assert cflags == ["-O0", "-g"]
    assert ldshared == ["gcc", "-shared", "-O0", "-g"]


@pytest.mark.parametrize(
    "env,expected",
    [
        pytest.param({}, "Release", id="unset"),
        pytest.param({"CMAKE_BUILD_TYPE": "Debug"}, "Debug", id="set"),
    ],
)
def test_cmake_build_type(env: dict[str, str], expected: str) -> None:
    """`CMAKE_BUILD_TYPE` overrides the default; `Release` is the default."""
    assert cmake_build_type(env) == expected
