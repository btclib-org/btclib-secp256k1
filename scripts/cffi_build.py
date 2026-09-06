# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Build the vendored libsecp256k1 and the cffi extension over it.

Three build paths, and which one runs is decided by the environment
rather than by an argument: static with MSVC on native Windows, static
with the interpreter's own toolchain everywhere else, and dynamic (cffi
ABI mode) where no C is compiled at all. `BTCLIB_LIBSECP256K1_DYNAMIC`
picks the third, `BTCLIB_LIBSECP256K1_CROSS_COMPILE` forces it for a
target whose interpreter cannot be run here, and `CFFI_PLATFORM` names
the platform being built for when it is not the one running.

A fourth, orthogonal thing the environment decides:
`BTCLIB_LIBSECP256K1_ZKP=true` builds a second extension,
`_btclib_secp256k1_zkp`, over the vendored secp256k1-zkp submodule --
static only, `Secp256k1ZkpCFFIExtension`'s own docstring has the reason.
The comparison below is against that literal, so every other value
leaves the fourth path off exactly as no value at all does: nothing
about the three paths above changes, `ffi_ext_zkp` below is `None`, and
`scripts/hatch_build.py` never calls into this module a second time.

Three classes: `FFIExtension` is the shape of a build with the three
steps a subclass has to answer; `VendoredCMakeExtension` is what this
project's two extensions share -- the CMake invocation, the
architecture and deployment-target options, and the header-to-cdef
derivation, none of which depends on which of the two submodules is
being built; `Secp256k1CFFIExtension` and `Secp256k1ZkpCFFIExtension`
are the two of them, differing only in which submodule they read, which
of its modules they turn on, and which of its headers the cdef comes
from. scripts/README.md walks the file; the module is also loaded by
`exec()` from scripts/hatch_build.py, which is why nothing here depends
on being importable.
"""

from __future__ import annotations

import os
import pathlib
import platform
import re
import shlex
import shutil
import subprocess
import sys
from subprocess import PIPE, Popen
from sysconfig import get_config_var, get_path, get_platform
from typing import Any

import cffi

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

cross_compile = os.environ.get("BTCLIB_LIBSECP256K1_CROSS_COMPILE", "false") == "true"
static = os.environ.get("BTCLIB_LIBSECP256K1_DYNAMIC", "false") != "true"
zkp = os.environ.get("BTCLIB_LIBSECP256K1_ZKP", "false") == "true"

# do-nothing implementations of the external default callbacks: they replace
# the abort()ing upstream defaults, so that illegal inputs never crash the
# hosting Python process; compiled as a separate unit, without mutating the
# vendored sources.
#
# These are the defaults, which apply to every context whose callbacks are
# not set: the shared context of the bindings sets them to record what was
# reported, so that context.check() can raise it
CALLBACK_STUBS = """
void secp256k1_default_illegal_callback_fn(const char* str, void* data) {
    (void)str;
    (void)data;
}

void secp256k1_default_error_callback_fn(const char* str, void* data) {
    (void)str;
    (void)data;
}
"""

# add the callback stubs to the vendored library target, so that the
# static archive and the shared object alike define the symbols that
# SECP256K1_USE_EXTERNAL_DEFAULT_CALLBACKS leaves undefined.
#
# CMake includes this file at the end of every project() call, when the
# target does not exist yet: hence the deferred call, which runs at the
# end of the top level directory, once add_subdirectory(src) has created
# the target, and still before generation. cmake_language(DEFER) needs
# CMake 3.19; the vendored library already requires 3.22.
#
# Nothing of this is written inside the vendored tree: the stubs and this
# file live in the CMake binary directory, which is outside the submodule
PROJECT_INCLUDE = """
if(NOT DEFINED BTCLIB_CALLBACKS_ADDED)
  set(BTCLIB_CALLBACKS_ADDED ON)
  cmake_language(DEFER DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
                 CALL target_sources secp256k1 PRIVATE "${BTCLIB_CALLBACKS}")
endif()
"""

# hatchling's own get_reproducible_timestamp() fallback (2020-02-02
# 00:00 UTC), already the stamp every member of the wheel's own archive
# carries -- reused here, for the same reason, on the one file this
# build compiles that a linker later reads the mtime of
_FIXED_MTIME = 1580601600


# every subprocess call below drives the vendored CMake build with
# argument lists assembled here: no shell, no untrusted input. The
# executables (cmake, cc) are looked up on PATH, as a build from source
# has to do
class FFIExtension:
    """A cffi extension over a C library this build compiles first.

    What a subclass answers is the three steps below -- `clean`,
    `build_c`, `generate_def` -- plus the class attributes naming what
    comes out of them. What this class owns is the part that does not
    depend on which library it is: the cdef, the choice among the three
    compilation paths, and the artifacts each hands back.
    """

    # the contract a subclass has to fulfil before calling __init__
    name: str
    static: bool
    clean_patterns: list[str]
    library_dirs: list[pathlib.Path]
    libraries: list[str]

    def __init__(self) -> None:
        """Clean the previous build, and record the platform being built for.

        Called by a subclass *after* it has set the attributes above, the
        clean needing to know what to remove. `CFFI_PLATFORM` overrides
        the running system, which is what makes cross-compilation
        possible: everything downstream reads this attribute rather than
        asking the host.
        """
        self.clean()
        self.platform = os.environ.get("CFFI_PLATFORM", platform.system())

    @property
    def shared_library_extension(self) -> str:
        """Suffix a shared object carries on the platform being built for.

        Raises RuntimeError on a platform this build does not know, rather
        than guessing a suffix that would make the search below silently
        find nothing.
        """
        if self.platform == "Windows":
            return ".dll"
        if self.platform == "Darwin":
            return ".dylib"
        if self.platform == "Linux":
            return ".so"
        raise RuntimeError

    def clean(self) -> None:
        """Remove what a previous build of this extension left behind."""
        raise NotImplementedError

    def build_c(self) -> None:
        """Build the C library the extension is compiled or linked against."""
        raise NotImplementedError

    def generate_def(self) -> tuple[str, str]:
        """Return the header to compile against and the cdef to declare.

        Two values because cffi wants them separately: the first is C that
        a compiler reads, the second the subset cffi's own parser can.
        """
        raise NotImplementedError

    def create_cffi(self, build_dir: pathlib.Path) -> tuple[Any, list[pathlib.Path]]:
        """Build the C, declare the cdef, and take one of the three paths.

        Returns the `cffi.FFI` and the artifacts to package. The
        `ffi._assigned_source` a caller reads afterwards is what says
        which path was taken, a static build having a C source assigned
        and a dynamic one not.
        """
        build_dir = pathlib.Path(build_dir)

        self.build_c()
        ffi = cffi.FFI()
        header, definitions = self.generate_def()
        ffi.cdef(definitions)

        if self.static and platform.system() == "Windows":
            return ffi, self.compile_static_msvc(ffi, header, build_dir)
        # a dynamic (cffi ABI mode) extension is generated from the cdef
        # alone: there is no C source to compile
        ffi.set_source(self.name, header if self.static else None)
        if self.static:
            return ffi, self.compile_static_unix(ffi, build_dir)
        return ffi, self.emit_dynamic(ffi, build_dir)

    def compile_static_msvc(
        self, ffi: Any, ffi_header: str, build_dir: pathlib.Path
    ) -> list[pathlib.Path]:
        """Compile a static extension with the setuptools/MSVC toolchain."""
        # native Windows: compile the extension with the standard
        # setuptools/MSVC toolchain instead of the manual Unix one;
        # SECP256K1_STATIC selects the static-consumer declarations
        # in the header
        ffi.set_source(
            self.name,
            ffi_header,
            library_dirs=[str(d) for d in self.library_dirs],
            libraries=self.libraries,
            define_macros=[("SECP256K1_STATIC", "1")],
            # link.exe's own TimeDateStamp for the PE it emits is the
            # moment that link ran, freshly generated on every
            # invocation regardless of what any input object or archive
            # carries: two builds of one checkout produced two `.pyd`
            # files identical in every other respect, differing only in
            # that field and in the one debug directory entry
            # (IMAGE_DEBUG_TYPE_POGO, signature GCTL) whose own
            # TimeDateStamp mirrors it -- measured directly, PE header
            # against PE header, rather than assumed from #510's two
            # candidates. /Brepro tells
            # link.exe to derive that field from the linked content
            # instead. It is a linker option and not a compiler one --
            # cl.exe's own /Brepro instead stops it stamping the wall
            # clock into an *object* file's own COFF header, which
            # nothing downstream of this build ever reads: the final
            # image's TimeDateStamp is link.exe's alone to set, never
            # copied from an input .obj or from the static
            # libsecp256k1.lib CMake produces, so extra_compile_args
            # carries nothing here. The second candidate #510 named, the
            # CodeView debug directory's GUID, is not in play either:
            # this link carries no /DEBUG and emits no CodeView entry at
            # all, on this extension or on the vendored library CMake
            # builds ahead of it -- CMake's own summary prints
            # RelWithDebInfo's /Zi purely as one of several supported
            # configurations, and `build_c` below actually builds
            # `--config Release`, which carries no such flag
            # (btclib-org/btclib-secp256k1#510)
            extra_link_args=["/Brepro"],
        )
        return [pathlib.Path(ffi.compile(tmpdir=str(build_dir)))]

    def compile_static_unix(
        self, ffi: Any, build_dir: pathlib.Path
    ) -> list[pathlib.Path]:
        """Compile and link a static extension by hand, with `cc`.

        The interpreter's own configuration decides the compiler, the
        flags and the extension suffix, so that the result matches the ABI
        of the interpreter that will import it.

        CC, CFLAGS and CCSHARED in that order is what `customize_compiler`
        composes for the extensions the interpreter builds for itself, and
        composing anything else here is how the two come apart. CFLAGS is
        where the optimization comes from: without it the glue alone is
        compiled unoptimized, beside a vendored library `build_c` builds
        Release. It is also where a universal2 interpreter's
        `-arch x86_64 -arch arm64` reaches the compile -- LDSHARED
        carries them to the link either way, so a compile without them
        hands the link a single-arch object to make dual-arch -- the
        universal2 case among the macOS ones target_architecture_options
        covers.

        Nothing is filtered out of them: on macOS `sysconfig` has already
        run the flags through `_osx_support`, which is what rewrites an
        `-arch` the toolchain cannot build and an `-isysroot` pointing at
        an SDK that is not installed. Each is split rather than passed
        whole: unsplit, CCSHARED is a single argv element, an empty one
        on a mac (clang tolerates it, gcc reads it as a missing input
        file) and an unrecognized one the day it carries two flags.
        """
        c_filename = f"{self.name}.c"
        o_filename = f"{self.name}.o"
        so_filename = self.name + get_config_var("EXT_SUFFIX")
        c_path = build_dir / c_filename
        o_path = build_dir / o_filename
        so_path = build_dir / so_filename

        ffi.emit_c_code(str(c_path))
        # ld64 attaches a debug map to the binary it links whenever the
        # compile carries -g, as this interpreter's own CFLAGS always
        # does below: one N_SO/N_OSO stab pair per object, the first
        # naming the directory the compile ran in and the second the
        # object's own path -- both absolute, both this build's own
        # worktree, neither touched by cee5f6d's mtime pin, which
        # addresses the mtime the N_OSO stab also carries rather than
        # the path. -fdebug-compilation-dir=. stops the compiler
        # recording the first at compile time; -oso_prefix . asks ld64
        # to strip its own cwd from the second at link time, and passing
        # "." rather than a literal path is what makes it strip whatever
        # directory this build happens to run in rather than naming one.
        # Measured with two builds of one checkout from two differently
        # named directories: nm -pa's OSO stab and a raw grep -a over
        # the linked object name only the bare filename with both flags,
        # where either alone leaves the other stab carrying the absolute
        # path (btclib-org/btclib-secp256k1#503)
        #
        # Everywhere else that same -g records the compile's own
        # working directory as the compile unit's DW_AT_comp_dir, whose
        # string the link copies into the extension's own
        # .debug_line_str: two builds of one commit from two directories
        # differ there by the difference between the two names, and
        # there is no debug map and no second stab for a linker flag to
        # reach, so one compile flag is the whole of it.
        # -ffile-prefix-map is a map rather than an instruction to write
        # a given directory, which is why it is handed one -- the
        # directory subprocess.run below makes this compile's cwd,
        # resolved because what the compiler records is the path the
        # kernel answers with. Both compilers take it, where the
        # -fdebug-compilation-dir above is clang's alone -- gcc, which
        # is /usr/bin/cc on the Linux images, rejects that one as an
        # unrecognized option. -fdebug-prefix-map would serve here too,
        # and is taken by both as well; -ffile-prefix-map is preferred
        # to it because gcc's own manual defines -ffile-prefix-map as
        # equivalent to specifying all the individual -f*-prefix-map
        # options, __FILE__ and the profile paths along with the debug
        # information. An option a compiler does not have is an error
        # and not a warning, so a toolchain too old for this one fails
        # the build outright rather than quietly reproducing the
        # difference. Measured with two builds of one commit from two
        # differently named directories: readelf reads DW_AT_comp_dir as
        # "." and a raw scan of the linked extension finds neither
        # directory, where without the flag each extension carries its
        # own. Nothing of this reaches the vendored library CMake builds
        # beside it, whose objects carry no debug information at all --
        # build_c's own note beside the configure has the reason
        # (btclib-org/btclib-secp256k1#522)
        build_path_flags = (
            ["-fdebug-compilation-dir=."]
            if platform.system() == "Darwin"
            else [f"-ffile-prefix-map={build_dir.resolve()}=."]
        )
        compile_command = [
            *shlex.split(get_config_var("CC")),
            *shlex.split(get_config_var("CFLAGS") or ""),
            *shlex.split(get_config_var("CCSHARED") or ""),
            f"-I{get_path('include')}",
            f"-I{get_path('platinclude')}",
            *build_path_flags,
            "-c",
            str(c_filename),
            "-o",
            str(o_filename),
        ]
        ldshared = shlex.split(get_config_var("LDSHARED"))
        link_command = [
            ldshared[0],
            str(o_filename),
            *ldshared[1:],
            *[f"-L{libs_dir}" for libs_dir in self.library_dirs],
            *[f"-l{lib}" for lib in self.libraries],
            *(["-Wl,-oso_prefix,."] if platform.system() == "Darwin" else []),
            "-o",
            str(so_filename),
        ]

        subprocess.run(compile_command, cwd=build_dir, check=True)
        if platform.system() == "Darwin":
            # ld64 attaches a debug map to the binary it links whenever
            # the compile carries -g, as this interpreter's own CFLAGS
            # always does above: one N_OSO stab per object, recording
            # that object's own mtime. A fresh compile of the same source
            # therefore links a different object every time, seconds
            # apart being enough to change it -- and ld64's own default
            # UUID, a hash of the linked output's content rather than a
            # value it invents, changes right along with the input it
            # hashes. `-Wl,-no_uuid` reads like the fix and instead
            # trades one non-determinism for a binary dyld refuses to
            # load at all: "missing LC_UUID load command", measured on
            # this machine's dyld against a minimal bundle built the same
            # way. Pinning the object's mtime addresses what actually
            # varies; nothing reads it once the object it names is gone,
            # which is before the wheel ships
            # (btclib-org/btclib-secp256k1#498, #502)
            os.utime(o_path, (_FIXED_MTIME, _FIXED_MTIME))
        subprocess.run(link_command, cwd=build_dir, check=True)
        return [so_path]

    def emit_dynamic(self, ffi: Any, build_dir: pathlib.Path) -> list[pathlib.Path]:
        """Emit the ABI-mode python module, and collect the shared objects.

        No C is compiled: the module is generated from the cdef alone and
        the library is shipped beside it, to be `dlopen`ed at import. The
        search raises rather than guessing when a library is missing or
        when two candidates match, either of which would produce a wheel
        that imports the wrong object or none.
        """
        py_filename = f"{self.name}.py"
        py_path = build_dir / py_filename

        ffi.emit_python_code(str(py_path))
        artifacts = [py_path]
        for lib in self.libraries:
            # every candidate directory is searched before giving up: the
            # shared library is in lib on POSIX and in bin on Windows, and
            # which of them exists is not known here
            found: pathlib.Path | None = None
            for libs_dir in self.library_dirs:
                pattern = f"lib{lib}*{self.shared_library_extension}"
                for file in libs_dir.glob(pattern):
                    if not file.is_file():
                        continue
                    # skip the versioned names of the symlink chain, as in
                    # libsecp256k1.2.dylib or libsecp256k1.so.2
                    if len(file.suffixes) > 1:
                        continue
                    if found is not None:
                        msg = f"multiple shared objects found for library: {lib}"
                        raise RuntimeError(msg)
                    found = file
            if found is None:
                raise RuntimeError(f"no shared object found for library: {lib}")
            shutil.copy(found, build_dir / found.name)
            artifacts.append(build_dir / found.name)

        return artifacts


class VendoredCMakeExtension(FFIExtension):
    """A vendored secp256k1-shaped submodule, built with CMake, wrapped by cffi.

    What `Secp256k1CFFIExtension` and `Secp256k1ZkpCFFIExtension` do not
    share is which submodule is read, which of its CMake modules are
    turned on, and which of its headers the cdef comes from -- the three
    arguments `configure` below takes. Everything else is a property of
    building this shape of upstream CMake project, once per submodule,
    and lives here so that it is written once: the architecture and
    deployment-target options, the callback stubs, the choice among the
    three compilation paths `FFIExtension.create_cffi` makes, and the
    header concatenation and preprocessing.
    """

    def configure(
        self,
        submodule: str,
        name: str,
        headers: list[str],
        module_flags: list[str],
        extra_clean_patterns: tuple[str, ...] = (),
    ) -> None:
        """Name the sources, the headers and where the build output goes.

        Called by a subclass's own `__init__` so that the two subclasses
        read the same way: each names what is its own and defers the
        rest to this method, which sets every attribute
        `FFIExtension.__init__` requires of a subclass and ends by
        calling it.

        Also decides whether this build is static: the dynamic path is
        asked for by environment variable, and cross-compilation forces
        it, the target's interpreter not being runnable here. This is a
        property of the environment the whole file was loaded under, not
        of which submodule is being built, so it is set the same way for
        both subclasses.

        Args:
            submodule: the vendored submodule's directory name, directly
                under the repository root.
            name: the name of the extension this build produces.
            headers: the public headers the cdef is derived from, in an
                order that satisfies their `#include` dependencies --
                stripped before preprocessing, so the list order is what
                still expresses them.
            module_flags: the `-DSECP256K1_ENABLE_MODULE_*` CMake
                arguments this submodule's modules are turned on or off
                with, explicit rather than left to upstream's own
                defaults, which are not part of its API.
            extra_clean_patterns: glob patterns, beyond the extension's
                own name, that a previous build of this extension alone
                may have left behind. Empty for a submodule whose build
                leaves nothing else, which is every one but the first.
        """
        self.name = name
        self.static = static and not cross_compile
        self.clean_patterns = [f"{name}.*", *extra_clean_patterns]
        # working directory
        self.wd = pathlib.Path(__file__).parent.parent.resolve() / submodule
        self.include_dir = self.wd / "include"
        self.headers = headers
        self.module_flags = module_flags
        # the library is built out of tree, so that the vendored sources
        # are never written to: build/ is where a wheel build puts its
        # own artifacts too, and is removed wholesale before each of them
        self.cmake_dir = self.wd.parent / "build" / submodule
        self.library_dirs = [self.cmake_dir / "lib"]
        self.libraries = ["secp256k1"]
        super().__init__()

    @override
    def clean(self) -> None:
        """Remove the out-of-tree CMake build and the emitted extensions."""
        # a stale CMake cache remembers the previous configuration
        # (static or shared, host or cross): reconfigure from scratch
        if self.cmake_dir.exists():
            shutil.rmtree(self.cmake_dir)
        for pattern in self.clean_patterns:
            for file in pathlib.Path().glob(pattern):
                file.unlink()

    def target_architecture_options(self) -> list[str]:
        """CMake options aiming the build at the interpreter's architecture.

        The extension is compiled by the interpreter's own toolchain, which
        targets the architecture that interpreter was built for; CMake
        instead defaults to the one of the host. That is the same thing
        only as long as the two agree, and on Windows arm64 they need not:
        uv installs an emulated x86-64 CPython there by default (native
        aarch64 "is not yet mature"), and MSVC then compiles the extension
        for x86-64 against an arm64 archive, leaving every secp256k1
        symbol unresolved at link time (LNK2001). The macOS counterparts
        are an x86-64 interpreter under Rosetta, and the universal2 one of
        the python.org installer, which compiles for both architectures
        and so needs both in the archive it links.

        sysconfig.get_platform() is where setuptools reads its own target
        from, so deriving this from it keeps the two in agreement by
        construction; on POSIX it also follows the _PYTHON_HOST_PLATFORM
        that a cross-compiling cibuildwheel sets, so an arm64 macOS wheel
        built on an Intel runner is built for arm64 throughout.

        Linux has no equivalent option to set: a 32-bit interpreter on a
        64-bit host would need the -m32 of a multilib toolchain, which is
        not a target CMake selects.
        """
        if cross_compile:
            # the target is the toolchain file's, not this machine's
            return []
        target = get_platform()
        if platform.system() == "Windows":
            # -A belongs to the Visual Studio generators, and the others
            # reject it: CMake picks one of them unless told otherwise
            generator = os.environ.get("CMAKE_GENERATOR", "Visual Studio")
            if not generator.startswith("Visual Studio"):
                return []
            arch = {
                "win32": "Win32",
                "win-amd64": "x64",
                "win-arm32": "ARM",
                "win-arm64": "ARM64",
            }.get(target)
            # an unknown platform leaves CMake its default: guessing an
            # architecture would be worse than building for the host
            return ["-A", arch] if arch else []
        if platform.system() == "Darwin":
            arch = target.rsplit("-", 1)[-1]
            if arch == "universal2":
                arch = "x86_64;arm64"
            return [f"-DCMAKE_OSX_ARCHITECTURES={arch}"]
        return []

    def macos_deployment_target_options(self) -> list[str]:
        """CMake option pinning the *static* build to the interpreter's floor.

        `build_c` runs for both linkages, but only a static build feeds
        its result into a second, separate toolchain:
        `compile_static_unix` links CMake's own archive into an
        extension compiled by the interpreter's own `cc`, whose CFLAGS
        already carry `-mmacosx-version-min`. Where nothing sets
        `CMAKE_OSX_DEPLOYMENT_TARGET`, CMake compiles that archive for
        whatever the build machine runs, and `ld` warns on every member
        of it built newer than the extension's own floor
        (btclib-org/btclib-secp256k1#526). A dynamic build compiles
        nothing this extension links against -- the shared object it
        produces is `dlopen`ed at import, by a process whose own
        toolchain never touches it -- so guarding to `self.static` is
        what keeps this from reaching that path at all, leaving
        `dynamic_platform_tag`'s own coupling between the environment
        variable and the library CMake builds (see scripts/README.md)
        untouched.

        Where `MACOSX_DEPLOYMENT_TARGET` is already exported --
        `cibuildwheel` sets it itself for every static release wheel --
        that value is left to CMake's own initialization of
        `CMAKE_OSX_DEPLOYMENT_TARGET` from the environment, and nothing
        is returned here: an explicit `-D` on the configure's command
        line would instead define the cache entry unconditionally,
        ahead of and regardless of that initialization, so passing one
        derived from `sysconfig` whenever `cibuildwheel`'s own is also
        present would silently override it rather than agree with it.
        `sysconfig.get_config_var` -- fixed at interpreter-build time,
        unmoved by what the calling process's environment holds -- is
        read only as the fallback for the unexported case, which is
        what a bare `uv build --wheel` is and what
        btclib-org/btclib-secp256k1#526 was filed against. Deferring
        this way is not exhaustive: an export that disagrees with the
        interpreter's own floor still reaches CMake unchallenged, and
        the warning this closes can still fire -- measured with
        `MACOSX_DEPLOYMENT_TARGET=13.0` against an 11.0 interpreter.
        """
        # self.static is already False under cross-compilation (see
        # __init__), so this needs no separate cross_compile check the
        # way target_architecture_options above does for its own flags,
        # which apply to a cross-compiled build too
        if not self.static or platform.system() != "Darwin":
            return []
        if os.environ.get("MACOSX_DEPLOYMENT_TARGET"):
            return []
        deployment_target = get_config_var("MACOSX_DEPLOYMENT_TARGET")
        return (
            [f"-DCMAKE_OSX_DEPLOYMENT_TARGET={deployment_target}"]
            if deployment_target
            else []
        )

    @override
    def build_c(self) -> None:
        """Build the vendored library with CMake, on every platform."""
        self.cmake_dir.mkdir(parents=True, exist_ok=True)
        callbacks = self.cmake_dir / "btclib_default_callbacks.c"
        callbacks.write_text(CALLBACK_STUBS, encoding="utf-8")
        project_include = self.cmake_dir / "btclib_callbacks.cmake"
        project_include.write_text(PROJECT_INCLUDE, encoding="utf-8")

        configure = [
            "cmake",
            "-S",
            str(self.wd),
            "-B",
            str(self.cmake_dir),
            # single configuration generators need it at configure time
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DBUILD_SHARED_LIBS={'OFF' if self.static else 'ON'}",
            # the static archive is linked into a shared extension
            "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
            "-DSECP256K1_USE_EXTERNAL_DEFAULT_CALLBACKS=ON",
            f"-DCMAKE_PROJECT_INCLUDE={project_include}",
            f"-DBTCLIB_CALLBACKS={callbacks}",
            # the one upstream option whose answer is what happens to be
            # *installed* on the machine: AUTO means
            # find_package(Valgrind), which is the only find_package in
            # the vendored CMake, and a header on an include path is
            # enough -- the module's compile check only rejects
            # NVALGRIND, so valgrind itself need not be there. Where one
            # is, the library is compiled with -DVALGRIND, which turns
            # the SECP256K1_CHECKMEM_* of src/checkmem.h from no-ops into
            # valgrind client requests, and SECP256K1_BUILD_CTIME_TESTS
            # defaults to it besides (already pinned OFF below). So a
            # runner that happens to have a header ships a different
            # library from the same commit, in a wheel that says nothing
            # about which one it is, and this package exists to behave
            # identically everywhere.
            #
            # The instrumentation in such a wheel runs rather than merely
            # being present: SECP256K1_CHECKMEM_RUNNING() is a client
            # request under VALGRIND (checkmem.h, deliberately, memcheck
            # having to be detected specifically), it is the left operand
            # of the && that secp256k1_context_preallocated_size guards
            # its DECLASSIFY flag with, and secp256k1_context_create
            # reaches that function twice. So two of them at import, and
            # none afterwards: the other call site is
            # secp256k1_declassify, behind ctx->declassify, which that
            # same guard refuses to set outside memcheck at all. A
            # handful of instructions, once -- and the pin is not about
            # the cost but about the wheel being a function of the
            # source. Functions rather than line numbers: a vendored
            # file's lines move with the next submodule bump and nothing
            # here would notice, where these names survive it
            "-DSECP256K1_VALGRIND=OFF",
            # every module this extension wraps, named by the subclass's
            # own __init__ and passed to configure(): upstream defaults
            # are not part of its API (recovery, in particular, is
            # disabled by default in both submodules)
            *self.module_flags,
            "-DSECP256K1_BUILD_BENCHMARK=OFF",
            "-DSECP256K1_BUILD_TESTS=OFF",
            "-DSECP256K1_BUILD_EXHAUSTIVE_TESTS=OFF",
            "-DSECP256K1_BUILD_CTIME_TESTS=OFF",
            "-DSECP256K1_BUILD_EXAMPLES=OFF",
            "-DSECP256K1_INSTALL=OFF",
            *self.target_architecture_options(),
            *self.macos_deployment_target_options(),
        ]
        # not in that list, and deliberately: SECP256K1_ASM,
        # SECP256K1_ECMULT_WINDOW_SIZE and SECP256K1_ECMULT_GEN_KB are
        # the three options that decide how fast the result is, and all
        # three are left at upstream's defaults. The two table sizes are
        # what upstream recommends for a desktop. ASM asks the build
        # machine a question too -- AUTO is a compile check, and it falls
        # back to OFF in silence where that check fails -- but it cannot
        # be pinned in one line: the mingw cell cross-compiles, and the
        # macOS universal2 one compiles two architectures in a single
        # pass, which is the `x86_64;arm64` target_architecture_options
        # names above. Pinning an architecture here would contradict it.
        # #211 records the values, and why they are left alone
        #
        # Also not in that list: anything pinning the mtime of an object
        # for the shared libsecp256k1 this configuration links in the
        # dynamic build, the way compile_static_unix pins the mtime of
        # the object it compiles by hand. This configure's own summary
        # carries no -g -- CMake's Release type is -O2 alone -- so the
        # objects it produces carry no debug map for ld64 to build one
        # from, and repeated builds of this -dynamiclib target, from one
        # worktree, produced one digest every time, LC_UUID included --
        # measured rather than assumed, and the reason a fix for the
        # other link does not follow this one
        # (btclib-org/btclib-secp256k1#498, #502)

        if cross_compile:
            # the toolchain file is the vendored one, upstream tested
            toolchain = self.wd / "cmake" / "x86_64-w64-mingw32.toolchain.cmake"
            configure.append(f"-DCMAKE_TOOLCHAIN_FILE={toolchain}")
        subprocess.run(configure, check=True)
        subprocess.run(
            ["cmake", "--build", str(self.cmake_dir), "--config", "Release"],
            check=True,
        )

        # multi configuration generators (MSVC) append the configuration
        # name; the shared library goes to lib on POSIX, being a DLL, to
        # bin on Windows
        candidates = ("lib/Release", "lib", "bin/Release", "bin")
        self.library_dirs = [
            directory
            for directory in (self.cmake_dir / c for c in candidates)
            if directory.is_dir()
        ]
        # the MSVC static archive is named libsecp256k1.lib, while the
        # MSVC DLL and every mingw and POSIX artifact keeps the plain name
        if self.static and platform.system() == "Windows":
            self.libraries = ["libsecp256k1"]

    @override
    def generate_def(self) -> tuple[str, str]:
        """Concatenate the public headers, and preprocess them for cffi.

        The `#include` directives are stripped and the concatenation order
        satisfies the dependencies between the headers instead; `gcc -E`
        then expands the `__attribute__ ((...))` that cffi's parser cannot
        read. Raises RuntimeError if the preprocessing fails, a partial
        cdef being a wrapper that compiles and declares the wrong thing.

        The pattern allows whitespace between `#` and `include`: every
        header of the primary submodule spells it `#include`, but three
        of secp256k1-zkp's own (`secp256k1_bppp.h`, `secp256k1_generator.h`,
        `secp256k1_rangeproof.h`) spell their own include of `secp256k1.h`
        `# include`, which an unspaced pattern leaves in the concatenated
        blob for `gcc -E` to fail on -- there being no `-I` on the command
        below for it to resolve against, every header read by path and
        concatenated instead.
        """
        ffi_header = ""
        for h in self.headers:
            location = self.include_dir / h
            with location.open(encoding="utf-8") as f:
                ffi_header += f.read() + "\n"

        ffi_header = re.sub(r"#\s*include .*", "", ffi_header)

        # expand all __attribute__ ((...)) to nothing: cffi cannot parse them
        command = [
            "gcc",
            "-P",
            "-E",
            "-D",
            "SECP256K1_BUILD",
            "-D",
            "__attribute__(x)=",
            "-",
        ]
        with Popen(command, stdin=PIPE, stdout=PIPE) as p:
            definitions = p.communicate(input=ffi_header.encode())[0].decode()
            definitions = definitions.replace("\r", "\n")
        if p.returncode != 0:
            raise RuntimeError(f"header preprocessing failed: {p.returncode}")
        return ffi_header, definitions


class Secp256k1CFFIExtension(VendoredCMakeExtension):
    """The vendored libsecp256k1, built with CMake and wrapped by cffi."""

    def __init__(self) -> None:
        """Name the sources, the headers and where the build output goes."""
        self.configure(
            submodule="secp256k1",
            name="_btclib_secp256k1",
            # #include directives are stripped before preprocessing, so
            # the concatenation order must satisfy the inter-header
            # dependencies: musig and silentpayments need the extrakeys
            # types, everything needs secp256k1.h
            headers=[
                "secp256k1.h",
                "secp256k1_ecdh.h",
                "secp256k1_recovery.h",
                "secp256k1_extrakeys.h",
                "secp256k1_schnorrsig.h",
                "secp256k1_musig.h",
                "secp256k1_ellswift.h",
                "secp256k1_silentpayments.h",
            ],
            module_flags=[
                "-DSECP256K1_ENABLE_MODULE_ECDH=ON",
                "-DSECP256K1_ENABLE_MODULE_RECOVERY=ON",
                "-DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON",
                "-DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON",
                "-DSECP256K1_ENABLE_MODULE_MUSIG=ON",
                "-DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON",
                "-DSECP256K1_ENABLE_MODULE_SILENTPAYMENTS=ON",
            ],
            # a leftover of a previous local dynamic build: emit_dynamic
            # copies the shared library beside the emitted ABI-mode
            # module, which an editable install places inside
            # src/btclib_secp256k1/ next to __init__.py -- harmless to a
            # later static build, _load_lib returning before it ever
            # globs for one, but stale all the same, and switching a
            # local build back to dynamic must not pick up the wrong
            # commit's copy. secp256k1-zkp never builds dynamic (see
            # Secp256k1ZkpCFFIExtension), so it never leaves this behind
            extra_clean_patterns=("src/btclib_secp256k1/libsecp256k1.*",),
        )


class Secp256k1ZkpCFFIExtension(VendoredCMakeExtension):
    """The vendored secp256k1-zkp, built with CMake and wrapped by cffi.

    Static only, by decision -- #605's own issue body has the reasoning
    this class executes rather than restates: two statically linked
    cores, `RTLD_LOCAL`. A dynamic build instead `dlopen`s a shared
    object at import, which this project has not built or tested two of
    side by side, so `BTCLIB_LIBSECP256K1_ZKP` declines rather than
    shipping a second one -- raising here, before any CMake or cffi work
    starts, rather than letting the dynamic path build something nobody
    asked for (btclib-org/btclib-secp256k1#603, #605).

    Every module secp256k1-zkp defines is turned on, not the modules
    beyond mainline's own alone: #603 measured trimming the shared ones
    (ecdh, recovery, ellswift, musig) at 85 KB of a 1.5 MB library, and
    zkp's own musig -- the adaptor-capable one, a superset of mainline's
    -- is needed regardless. secp256k1-zkp has no silentpayments module
    at the pinned commit, secp256k1-zkp#368's 0.8.0 sync that would add
    one not yet merged upstream (#603's own survey), so this extension's
    header list and module flags have no entry for it where
    `Secp256k1CFFIExtension`'s does.
    """

    def __init__(self) -> None:
        """Name the sources, the headers and where the build output goes.

        Raises:
            RuntimeError: where `BTCLIB_LIBSECP256K1_ZKP` is `true`
                alongside `BTCLIB_LIBSECP256K1_DYNAMIC=true` or
                `BTCLIB_LIBSECP256K1_CROSS_COMPILE=true`, either of
                which takes the *other* extension down the dynamic path
                this class's own docstring declines. Every other value
                of the zkp flag leaves this class unconstructed, so
                there is nothing here to raise.
        """
        if not static or cross_compile:
            msg = (
                "BTCLIB_LIBSECP256K1_ZKP is static-only: unset "
                "BTCLIB_LIBSECP256K1_DYNAMIC and BTCLIB_LIBSECP256K1_CROSS_COMPILE, "
                "or unset BTCLIB_LIBSECP256K1_ZKP"
            )
            raise RuntimeError(msg)
        self.configure(
            submodule="secp256k1-zkp",
            name="_btclib_secp256k1_zkp",
            # secp256k1.h before everything; extrakeys before schnorrsig,
            # musig and schnorrsig_halfagg, which need its types;
            # rangeproof before surjectionproof, which needs its types --
            # the same #include-stripped concatenation this file's other
            # extension needs, over zkp's own copies of the headers the
            # two submodules share, which differ from mainline's own
            # (zkp's musig and schnorrsig each add the adaptor-signature
            # entry points, and secp256k1.h a deprecated alias)
            headers=[
                "secp256k1.h",
                "secp256k1_ecdh.h",
                "secp256k1_recovery.h",
                "secp256k1_extrakeys.h",
                "secp256k1_schnorrsig.h",
                "secp256k1_musig.h",
                "secp256k1_ellswift.h",
                "secp256k1_generator.h",
                "secp256k1_rangeproof.h",
                "secp256k1_surjectionproof.h",
                "secp256k1_whitelist.h",
                "secp256k1_ecdsa_adaptor.h",
                "secp256k1_ecdsa_s2c.h",
                "secp256k1_bppp.h",
                "secp256k1_schnorrsig_halfagg.h",
            ],
            module_flags=[
                "-DSECP256K1_ENABLE_MODULE_ECDH=ON",
                "-DSECP256K1_ENABLE_MODULE_RECOVERY=ON",
                "-DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON",
                "-DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON",
                "-DSECP256K1_ENABLE_MODULE_MUSIG=ON",
                "-DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON",
                "-DSECP256K1_ENABLE_MODULE_GENERATOR=ON",
                "-DSECP256K1_ENABLE_MODULE_RANGEPROOF=ON",
                "-DSECP256K1_ENABLE_MODULE_SURJECTIONPROOF=ON",
                "-DSECP256K1_ENABLE_MODULE_WHITELIST=ON",
                "-DSECP256K1_ENABLE_MODULE_ECDSA_ADAPTOR=ON",
                "-DSECP256K1_ENABLE_MODULE_ECDSA_S2C=ON",
                "-DSECP256K1_ENABLE_MODULE_BPPP=ON",
                "-DSECP256K1_ENABLE_MODULE_SCHNORRSIG_HALFAGG=ON",
            ],
        )


ffi_ext = Secp256k1CFFIExtension()
# None where the flag is not `true`, which is every build this project
# ships today: scripts/hatch_build.py's own loop skips a cffi_modules
# entry that resolves to None rather than building it, so the extension
# this module's docstring calls a fourth path is, unflagged, not merely
# empty but absent
ffi_ext_zkp = Secp256k1ZkpCFFIExtension() if zkp else None

if __name__ == "__main__":
    ffi_ext.create_cffi(pathlib.Path())
    if ffi_ext_zkp is not None:
        ffi_ext_zkp.create_cffi(pathlib.Path())
