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
# A bare `pip3 install .` resolves cffi -- the one runtime dependency
# pyproject.toml declares -- from whatever the index serves that day,
# ignoring uv.lock. `COPY .` above already carries uv.lock and
# pyproject.toml into this container, so the fix is exported from them
# here rather than committed as a second file: a committed mirror needs
# its own freshness check to not drift from uv.lock, where a file
# generated from it every time cannot. `uv` itself reaches this
# container through the Dockerfile's own `COPY --from=uv`, pinned by the
# digest that stage's `FROM` names, rather than through a `pip3 install
# uv` in this script: Scorecard's PinnedDependenciesID reads a plain
# version constraint given to `pip install` as unpinned, the same way it
# read the bare `pip3 install .` this replaces
# (btclib-org/btclib-secp256k1#1040).
uv export --locked --no-default-groups --no-emit-project \
    -o requirements-fuzz.txt
pip3 install --require-hashes -r requirements-fuzz.txt

# `pip3 install -e .` builds the vendored library and the cffi extension
# over it inside this container, and the sanitizer and coverage
# instrumentation in the ambient CFLAGS reach both: CMake initialises
# CMAKE_C_FLAGS from it, and the static glue's compile reads it the way
# setuptools does for any extension (btclib-org/btclib-secp256k1#1019),
# an editable install running the same build hook as a wheel and
# force-including the same compiled artifacts (`scripts/hatch_build.py`'s
# `initialize` docstring). So a fault in the glue's own marshalling is
# caught where it happens, not only once it reaches the library.
# `--no-deps` is what keeps this install from re-resolving cffi outside
# the hashed step above; `-e` is there because Scorecard's own reading
# of `pip install` never accepts a plain local source, `--no-deps` or
# not, only an *editable* one -- the same `--no-deps .` with no `-e`
# still reads as unpinned to it, which is why the flag is added rather
# than kept implicit. This still builds a wheel through an isolated PEP
# 517 backend, which resolves hatchling and cffi as *build* requirements
# fresh from the index regardless -- uv.lock cannot pin those either,
# `pyproject.toml`'s `[build-system]` comment says why, and that is true
# of every isolated build of this package, not only this container's.
#
# Nothing here imports the package after installing it. The installed
# extension resolves the instrumentation's references only under the
# fuzzer's own preload, so `python3 -c "import btclib_secp256k1"` fails
# in this container on an undefined `__sancov_lowest_stack`, and is not
# a check the build can carry.
pip3 install --no-deps -e .

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
