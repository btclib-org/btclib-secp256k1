# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The static glue's compile and link honour the compiler variables.

`scripts/cffi_build.py`'s `_customized_compile_link` composes `CC`,
`CFLAGS` and `LDSHARED` the way the Unix compiler's `configure_system`
does in the setuptools `uv.lock` resolves, and `_cmake_build_type` reads
`CMAKE_BUILD_TYPE` for the vendored library's build type;
`_macos_architectures` and `_pin_architectures` aim the macOS compile and
link at the wheel's architectures. Beside them, `_hardening_options` says
which flags harden the native code, `_hardened_environment` puts them in
front of the caller's, and `_link_command` does the same for the glue's
link. `_ffi_backend` and `_ios_cmake_options` say what an iOS build
changes, and `_python_library` what an Android one does. Each is a pure
function of its arguments -- no `sysconfig`, no `os.environ`, no
subprocess -- so what is checked here is the argv each one builds, never
a compile (btclib-org/btclib-secp256k1#1019).

None is read by importing `scripts/cffi_build.py`, for the reason
`tests/module_flags_test.py`'s own docstring gives: the module's own top
level constructs `Secp256k1CFFIExtension()`, whose `__init__` runs
`clean()` and deletes the CMake build directory and any local build
artifact this suite may be running against. Each function is instead
taken out of the syntax tree and executed on its own -- real code, not a
reimplementation of it, but never the module-level construction that
comes with it. The tests that read the real cdef run the module up to
that construction, through `_headers`, and run the preprocessor
`generate_def` calls.
"""

from __future__ import annotations

import ast
import re
import shlex
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

import cffi
import pytest
from cffi.backend_ctypes import CTypesBackend

from .ios_test import STARTS_A_PROCESS

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
macos_architectures = cast(
    "Callable[[str], list[str]]", _extracted("_macos_architectures")
)
pin_architectures = cast(
    "Callable[[str, list[str]], str]", _extracted("_pin_architectures")
)
cmake_build_type = cast(
    "Callable[[Mapping[str, str]], str]", _extracted("_cmake_build_type")
)
hardening_options = cast(
    "Callable[[str, str, bool], tuple[list[str], list[str]]]",
    _extracted("_hardening_options"),
)
link_command = cast(
    "Callable[..., list[str]]",
    _extracted("_link_command"),
)
hardened_environment = cast(
    "Callable[[Mapping[str, str], list[str], list[str]], dict[str, str]]",
    _extracted("_hardened_environment"),
)
ffi_backend = cast("Callable[[str], list[Any]]", _extracted("_ffi_backend"))
ios_cmake_options = cast(
    "Callable[[str, str, str | None], list[str]]", _extracted("_ios_cmake_options")
)
python_library = cast("Callable[[str, str], list[str]]", _extracted("_python_library"))


def test_every_function_was_read() -> None:
    """The positive control for `_extracted`: a rename answers here first.

    Without it, a `name` that stopped matching would leave every test
    below calling nothing -- `_extracted` raises in that case, so this
    is what turns the raise into a named failure rather than a collection
    error attributed to the wrong line.
    """
    assert callable(customized_compile_link)
    assert callable(cmake_build_type)
    assert callable(macos_architectures)
    assert callable(pin_architectures)
    assert callable(hardening_options)
    assert callable(hardened_environment)
    assert callable(link_command)
    assert callable(ffi_backend)
    assert callable(ios_cmake_options)
    assert callable(python_library)


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


@pytest.mark.parametrize(
    "target, expected",
    [
        ("macosx-11.0-arm64", ["arm64"]),
        ("macosx-10.13-x86_64", ["x86_64"]),
        ("macosx-10.13-universal2", ["x86_64", "arm64"]),
    ],
)
def test_macos_architectures(target: str, expected: list[str]) -> None:
    """The tag's last field names the architectures, universal2 both."""
    assert macos_architectures(target) == expected


def test_a_universal2_interpreter_building_arm64_is_made_arm64_only() -> None:
    """The `-arch` pairs of python.org's universal2 flags become one.

    The fixtures are the values python.org's 3.13.16 universal2
    interpreter reports with `ARCHFLAGS="-arch arm64"` set: the pair
    ending each value survived the override, and an arm64 wheel built
    with it had an extension whose x86_64 slice had no library in it
    (btclib-org/btclib-secp256k1#1205).
    """
    cflags = (
        "-fno-strict-overflow -Wsign-compare -Wunreachable-code -fno-common "
        "-dynamic -DNDEBUG -g -O3 -Wall  -arch x86_64 -arch arm64"
    )
    ldshared = "clang -bundle -undefined dynamic_lookup  -arch x86_64 -arch arm64"
    assert pin_architectures(cflags, ["arm64"]) == (
        "-fno-strict-overflow -Wsign-compare -Wunreachable-code -fno-common "
        "-dynamic -DNDEBUG -g -O3 -Wall -arch arm64"
    )
    assert (
        pin_architectures(ldshared, ["arm64"])
        == "clang -bundle -undefined dynamic_lookup -arch arm64"
    )


def test_universal2_keeps_both_architectures() -> None:
    """A universal2 build gets both pairs, in the order of the tag."""
    assert pin_architectures("-O3 -arch arm64 -g", ["x86_64", "arm64"]) == (
        "-O3 -arch x86_64 -arch arm64 -g"
    )


def test_flags_without_an_arch_are_left_alone() -> None:
    """No `-arch` is added where the interpreter records none."""
    assert pin_architectures("-O2 -Wall", ["arm64"]) == "-O2 -Wall"


_COMMON = ["-fstack-protector-strong", "-U_FORTIFY_SOURCE", "-D_FORTIFY_SOURCE=2"]


@pytest.mark.parametrize(
    "machine, branch",
    [
        ("x86_64", "-fcf-protection=full"),
        ("AMD64", "-fcf-protection=full"),
        ("aarch64", "-mbranch-protection=standard"),
        ("arm64", "-mbranch-protection=standard"),
    ],
)
def test_linux_gets_the_compile_flags_of_its_architecture(
    machine: str, branch: str
) -> None:
    """Linux is compiled with all four flags and linked `relro` and `now`."""
    assert hardening_options("Linux", machine, False) == (
        [*_COMMON, branch],
        ["-Wl,-z,relro", "-Wl,-z,now"],
    )


def test_linux_on_another_architecture_has_no_branch_protection() -> None:
    """A machine neither flag names gets the others, not a flag it rejects."""
    assert hardening_options("Linux", "riscv64", False) == (
        _COMMON,
        ["-Wl,-z,relro", "-Wl,-z,now"],
    )


@pytest.mark.parametrize("machine", ["arm64", "x86_64"])
def test_macos_gets_no_branch_protection_and_no_linker_flag(machine: str) -> None:
    """Mach-O has neither `relro` nor `now` nor a marking to read back."""
    assert hardening_options("Darwin", machine, False) == (_COMMON, [])


@pytest.mark.parametrize(
    "machine, branch",
    [
        ("x86_64", "-fcf-protection=full"),
        ("aarch64", "-mbranch-protection=standard"),
    ],
)
def test_android_gets_branch_protection_and_no_linker_flag(
    machine: str, branch: str
) -> None:
    """Android takes Linux's compile flags; the NDK links `relro` and `now`."""
    assert hardening_options("Android", machine, False) == ([*_COMMON, branch], [])


@pytest.mark.parametrize("machine", ["AMD64", "ARM64"])
def test_msvc_gets_gs_and_control_flow_guard(machine: str) -> None:
    """MSVC takes `/GS` and `/guard:cf` to compile and `/GUARD:CF` to link."""
    assert hardening_options("Windows", machine, False) == (
        ["/GS", "/guard:cf"],
        ["/GUARD:CF"],
    )


def test_the_mingw_cross_compile_is_linked_for_aslr_and_dep_only() -> None:
    """The stack protector would link a `libssp` DLL, so mingw gets none."""
    assert hardening_options("Windows", "x86_64", True) == (
        [],
        ["-Wl,--dynamicbase", "-Wl,--nxcompat", "-Wl,--high-entropy-va"],
    )


def test_the_hardening_comes_before_the_callers_flags() -> None:
    """A caller's own `CFLAGS` and `LDFLAGS` follow, so that they win."""
    env = hardened_environment(
        {"CFLAGS": "-fno-stack-protector", "LDFLAGS": "-Wl,-z,lazy", "HOME": "/h"},
        ["-fstack-protector-strong"],
        ["-Wl,-z,now"],
    )
    assert env == {
        "CFLAGS": "-fstack-protector-strong -fno-stack-protector",
        "LDFLAGS": "-Wl,-z,now -Wl,-z,lazy",
        "HOME": "/h",
    }


def test_the_hardening_alone_is_the_whole_value_where_nothing_is_set() -> None:
    """An empty variable adds no stray space, and `env` is not mutated."""
    env = {"CFLAGS": ""}
    assert hardened_environment(env, ["-a", "-b"], []) == {
        "CFLAGS": "-a -b",
        "LDFLAGS": "",
    }
    assert env == {"CFLAGS": ""}


@pytest.mark.parametrize("system", ["Darwin", "Linux", "Windows"])
def test_a_build_for_the_running_system_takes_the_compiled_backend(
    system: str,
) -> None:
    """No argument leaves `cffi.FFI` its compiled `_cffi_backend`."""
    assert ffi_backend(system) == []


def test_an_ios_build_takes_the_ctypes_backend() -> None:
    """The iOS cffi backend does not load in the cross environment."""
    (backend,) = ffi_backend("iOS")
    assert isinstance(backend, CTypesBackend)


def _module_without_its_extensions() -> dict[str, object]:
    """Run `scripts/cffi_build.py` up to the extensions it constructs.

    Returns:
        The module's namespace, its classes and functions defined and
        neither extension constructed, so that nothing is cleaned.
    """
    tree = ast.parse(_BUILD.read_text(encoding="utf-8"))
    # `next` raises where the module constructs no `ffi_ext`, failing the
    # test rather than running the construction it exists to leave out
    end = next(
        index
        for index, node in enumerate(tree.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "ffi_ext"
            for target in node.targets
        )
    )
    namespace: dict[str, object] = {"__name__": "__cffi__", "__file__": str(_BUILD)}
    module = ast.Module(body=tree.body[:end], type_ignores=[])
    exec(compile(module, str(_BUILD), "exec"), namespace)
    return namespace


def _headers() -> Any:
    """Construct the primary extension, cleaning nothing.

    Returns:
        A `Secp256k1CFFIExtension` whose `generate_def` reads the real
        headers, static or dynamic as the environment of the suite asks.
    """
    namespace = _module_without_its_extensions()
    extension = cast("type", namespace["Secp256k1CFFIExtension"])

    class Headers(extension):  # type: ignore[misc, valid-type]
        def clean(self) -> None:
            """Remove nothing: no build is made."""

    return Headers()


@STARTS_A_PROCESS
def test_the_ctypes_backend_emits_the_c_the_compiled_one_does(
    tmp_path: Path,
) -> None:
    """The C of the static extension does not depend on the backend.

    The cdef and the header are the real ones, which `generate_def` reads
    from the vendored submodule. The compiled backend's C is the side the
    ctypes one is held to. The extension is pinned static whatever the
    suite's lane, an iOS build being static, so the compared cdef holds
    the `extern "Python"` declaration.
    """
    headers = _headers()
    headers.static = True
    header, definitions = headers.generate_def()
    emitted = []
    for name, arguments in (("compiled", []), ("ctypes", ffi_backend("iOS"))):
        ffi = cffi.FFI(*arguments)
        ffi.cdef(definitions)
        ffi.set_source("_btclib_secp256k1", header)
        path = tmp_path / f"{name}.c"
        ffi.emit_c_code(str(path))
        emitted.append(path.read_bytes())
    assert emitted[0] == emitted[1]


@STARTS_A_PROCESS
def test_only_a_static_cdef_declares_the_illegal_callback(tmp_path: Path) -> None:
    """The `extern "Python"` callback is in the static cdef alone.

    cffi refuses that declaration in ABI mode: the static cdef cannot
    emit the dynamic extension's module, and the dynamic cdef can.
    """
    headers = _headers()
    headers.static = True
    _, static_definitions = headers.generate_def()
    headers.static = False
    _, dynamic_definitions = headers.generate_def()
    assert 'extern "Python" void btclib_secp256k1_record_illegal(' in static_definitions
    assert 'extern "Python"' not in dynamic_definitions

    static = cffi.FFI()
    static.cdef(static_definitions)
    static.set_source("_btclib_secp256k1", None)
    with pytest.raises(cffi.VerificationError, match="ABI mode"):
        static.emit_python_code(str(tmp_path / "static.py"))
    dynamic = cffi.FFI()
    dynamic.cdef(dynamic_definitions)
    dynamic.set_source("_btclib_secp256k1", None)
    dynamic.emit_python_code(str(tmp_path / "dynamic.py"))


def test_a_build_for_the_running_system_takes_no_ios_option() -> None:
    """A macOS build takes no iOS option."""
    assert ios_cmake_options("Darwin", "macosx-11.0-arm64", "13.0") == []


@pytest.mark.parametrize(
    "target, arch, sdk",
    [
        ("ios-13.0-arm64-iphonesimulator", "arm64", "iphonesimulator"),
        ("ios-13.0-x86_64-iphonesimulator", "x86_64", "iphonesimulator"),
        ("ios-13.0-arm64-iphoneos", "arm64", "iphoneos"),
    ],
)
def test_ios_names_the_system_the_sdk_and_the_architecture(
    target: str, arch: str, sdk: str
) -> None:
    """Each of cibuildwheel's iOS targets reaches CMake whole."""
    assert ios_cmake_options("iOS", target, "15.0") == [
        "-DCMAKE_SYSTEM_NAME=iOS",
        f"-DCMAKE_OSX_SYSROOT={sdk}",
        f"-DCMAKE_OSX_ARCHITECTURES={arch}",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0",
    ]


@pytest.mark.parametrize(
    "target",
    [
        "ios-arm64-iphonesimulator",
        "ios-13.0-arm64-iphone-simulator",
        "ios-13.0--iphoneos",
    ],
)
def test_ios_refuses_a_tag_without_four_fields(target: str) -> None:
    """A tag of three or five fields, or an empty one, is named, not misread."""
    with pytest.raises(RuntimeError, match=re.escape(repr(target))):
        ios_cmake_options("iOS", target, "13.0")


def test_ios_without_a_deployment_target_leaves_the_default() -> None:
    """No deployment target is no option, not an empty one."""
    assert ios_cmake_options("iOS", "ios-13.0-arm64-iphoneos", None) == [
        "-DCMAKE_SYSTEM_NAME=iOS",
        "-DCMAKE_OSX_SYSROOT=iphoneos",
        "-DCMAKE_OSX_ARCHITECTURES=arm64",
    ]


@pytest.mark.parametrize("system", ["Darwin", "iOS", "Linux"])
def test_only_an_android_glue_links_libpython(system: str) -> None:
    """Elsewhere the interpreter resolves the glue's Python symbols."""
    assert python_library(system, "3.14") == []


@pytest.mark.parametrize("ldversion", ["3.13", "3.14", "3.14t"])
def test_an_android_glue_links_the_interpreters_libpython(ldversion: str) -> None:
    """The library's name is `LDVERSION`'s, a free-threaded `t` included."""
    assert python_library("Android", ldversion) == [f"-lpython{ldversion}"]


def test_the_link_hardening_precedes_the_callers_ldflags() -> None:
    """The caller's `LDFLAGS`, in `ldshared[1:]`, follow the hardening."""
    argv = link_command(
        ["cc", "-shared", "-Wl,-z,lazy"],
        ["-Wl,-z,relro", "-Wl,-z,now"],
        ["x.o"],
        ["-L/lib"],
        ["-lsecp256k1"],
        ["-Wl,-oso_prefix,."],
        "x.so",
    )
    assert argv == [
        "cc",
        "x.o",
        "-Wl,-z,relro",
        "-Wl,-z,now",
        "-shared",
        "-Wl,-z,lazy",
        "-L/lib",
        "-lsecp256k1",
        "-Wl,-oso_prefix,.",
        "-o",
        "x.so",
    ]
