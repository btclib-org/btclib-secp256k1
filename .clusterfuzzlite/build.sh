# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.
#
# Runs inside the container the Dockerfile beside this file builds, cwd
# at $SRC/btclib-secp256k1 (the Dockerfile's WORKDIR), as
# `bash -eux $SRC/build.sh` from OSS-Fuzz's own `compile` script, which
# is why there is no shebang and no execute bit here. $CC, $CFLAGS, $SRC
# and $OUT are exported before it runs.
#
# `pip3 install .` builds the vendored library and the cffi extension
# over it inside this container: CMake initialises CMAKE_C_FLAGS from
# the ambient CFLAGS, and the sanitizer and coverage instrumentation
# land in the vendored C that way. The cffi glue is compiled from
# `sysconfig`'s flags instead and carries none of it;
# btclib-org/.github#342 measured both and accepts it, the memory a
# target can reach being the library's.
#
# Nothing here imports the package after installing it. The installed
# extension resolves the instrumentation's references only under the
# fuzzer's own preload, so `python3 -c "import btclib_secp256k1"` fails
# in this container on an undefined `__sancov_lowest_stack`, and is not
# a check the build can carry.
pip3 install .

# compile_python_fuzzer forwards every extra argument to pyinstaller.
# --hidden-import=_cffi_backend names the module cffi loads by name and
# PyInstaller's analysis cannot trace: without it pyinstaller exits 0
# and the frozen target dies at its first execution with
# ModuleNotFoundError, a green build over a target that never ran.
#
# The same loop zips each target's seed corpus, fuzz/corpus/<name>/,
# under the name OSS-Fuzz reads a seed corpus from beside a target in
# $OUT, so a new fuzz_*.py with a corpus directory beside it needs no
# second list here; tests/fuzz_corpus_test.py is what holds every
# target to having one.
for fuzzer in "$SRC/btclib-secp256k1/fuzz"/fuzz_*.py; do
  compile_python_fuzzer "$fuzzer" --hidden-import=_cffi_backend
  name=$(basename "$fuzzer" .py)
  zip -j "$OUT/${name}_seed_corpus.zip" "$SRC/btclib-secp256k1/fuzz/corpus/$name"/*.bin
done
